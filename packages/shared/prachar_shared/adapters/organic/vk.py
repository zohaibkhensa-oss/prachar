from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from ...config import get_settings
from ...contracts import (
    ChannelProfile,
    MetricEvent,
    PolicyResult,
    PublishedRef,
    TokenSet,
)
from ...policy.claims_gate import claims_gate
from ..registry import register_organic
from .base import ChannelAdapter

logger = logging.getLogger(__name__)

_VK_API_BASE = "https://api.vk.com/method"
_VK_API_VERSION = "5.199"
_VK_MESSAGE_MAX = 16000


@register_organic
class VKAdapter(ChannelAdapter):
    """VK API adapter (spec 05 regional table — CIS/Russia)."""

    channel = "vk"

    def auth_url(self, state: str) -> str:
        s = get_settings()
        client_id = s.vk_client_id or "PLACEHOLDER"
        params = urlencode({
            "client_id": client_id,
            "redirect_uri": "https://example.com/oauth/vk/callback",
            "scope": "wall,photos,stats,offline",
            "response_type": "code",
            "state": state,
            "v": _VK_API_VERSION,
        })
        return f"https://oauth.vk.com/authorize?{params}"

    def exchange_code(self, code: str) -> TokenSet:
        s = get_settings()
        if not s.vk_client_id or not s.vk_client_secret:
            raise NotImplementedError("VK_CLIENT_ID/VK_CLIENT_SECRET not configured")
        # Synchronous stub — real implementation would POST to oauth.vk.com/access_token.
        return TokenSet(
            access_token=code,
            refresh_token=None,
            expires_at=datetime.now(UTC) + timedelta(days=365),
            scopes=["wall", "photos", "stats", "offline"],
        )

    async def fetch_profile(self, tokens: TokenSet) -> ChannelProfile:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_VK_API_BASE}/account.getProfileInfo",
                params={"access_token": tokens.access_token, "v": _VK_API_VERSION},
            )
            resp.raise_for_status()
            data = resp.json().get("response", {})
        return ChannelProfile(
            channel=self.channel,
            handle=str(data.get("screen_name", "")),
            display_name=f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
            follower_count=None,
            metadata={"user_id": data.get("id")},
        )

    def generate_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "owner_id": {"type": "string"},
                "message": {"type": "string", "maxLength": _VK_MESSAGE_MAX},
                "attachments": {"type": "array", "items": {"type": "string"}},
                "from_group": {"type": "integer", "enum": [0, 1]},
                "publish_date": {"type": "integer"},
            },
            "required": ["owner_id", "message"],
        }

    def policy_gate(self, payload: dict[str, Any]) -> PolicyResult:
        message = payload.get("message", "")
        result = claims_gate(message)
        if len(message) > _VK_MESSAGE_MAX:
            result.blocked_reasons.append(f"Message exceeds {_VK_MESSAGE_MAX} characters")
        if not payload.get("owner_id"):
            result.blocked_reasons.append("owner_id is required")
        result.passed = len(result.blocked_reasons) == 0
        return result

    async def publish(self, tokens: TokenSet, payload: dict[str, Any]) -> PublishedRef:
        params: dict[str, Any] = {
            "owner_id": payload["owner_id"],
            "message": payload["message"],
            "from_group": payload.get("from_group", 1),
            "access_token": tokens.access_token,
            "v": _VK_API_VERSION,
        }
        attachments = payload.get("attachments", [])
        if attachments:
            params["attachments"] = ",".join(attachments)
        if payload.get("publish_date"):
            params["publish_date"] = payload["publish_date"]
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{_VK_API_BASE}/wall.post", params=params)
            resp.raise_for_status()
            data = resp.json().get("response", {})
        post_id = str(data.get("post_id", ""))
        owner_id = str(payload["owner_id"])
        return PublishedRef(
            channel=self.channel,
            native_id=f"{owner_id}_{post_id}",
            url=f"https://vk.com/wall{owner_id}_{post_id}",
            published_at=datetime.now(UTC),
        )

    async def metrics(self, tokens: TokenSet, since: datetime) -> list[MetricEvent]:
        # wall.getStats / stats.getPostReach for views, likes, reposts, comments.
        events: list[MetricEvent] = []
        owner_id = "0"  # caller injects target in production
        post_id = "0"
        async with httpx.AsyncClient() as client:
            for metric in ("views", "likes", "reposts", "comments"):
                resp = await client.get(
                    f"{_VK_API_BASE}/wall.getById",
                    params={
                        "posts": f"{owner_id}_{post_id}",
                        "access_token": tokens.access_token,
                        "v": _VK_API_VERSION,
                    },
                )
                if resp.status_code == 200:
                    items = resp.json().get("response", {}).get("items", [])
                    if items:
                        stats = items[0].get("stats", {})
                        events.append(
                            MetricEvent(
                                channel=self.channel,
                                entity_type="post",
                                entity_id=f"{owner_id}_{post_id}",
                                metric=metric,
                                value=float(stats.get(metric, 0)),
                                ts=datetime.now(UTC),
                            )
                        )
        return events
