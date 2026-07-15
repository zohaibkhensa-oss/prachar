from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

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

_LINE_API_BASE = "https://api.line.me"
_LINE_TEXT_MAX = 5000


@register_organic
class LINEAdapter(ChannelAdapter):
    """LINE Messaging API adapter (spec 05 regional table — Japan)."""

    channel = "line"

    def auth_url(self, state: str) -> str:
        # LINE Developers console for channel access token configuration.
        return f"https://developers.line.biz/console/?state={state}"

    def exchange_code(self, code: str) -> TokenSet:
        # Channel access token is configured via env LINE_CHANNEL_SECRET / channel id.
        s = get_settings()
        token = code or s.line_channel_secret
        return TokenSet(
            access_token=token,
            refresh_token=None,
            expires_at=datetime.now(UTC) + timedelta(days=30),
            scopes=["channel"],
        )

    async def fetch_profile(self, tokens: TokenSet) -> ChannelProfile:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_LINE_API_BASE}/v2/bot/info",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
        basic = data.get("basic", {})
        return ChannelProfile(
            channel=self.channel,
            handle=str(basic.get("channelId", "")),
            display_name=str(basic.get("channelName", "")),
            follower_count=None,
            metadata=data,
        )

    def generate_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "messages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["text", "image", "video", "flex"]},
                            "text": {"type": "string", "maxLength": _LINE_TEXT_MAX},
                            "originalContentUrl": {"type": "string"},
                        },
                    },
                },
            },
            "required": ["to", "messages"],
        }

    def policy_gate(self, payload: dict[str, Any]) -> PolicyResult:
        messages = payload.get("messages", [])
        text_parts: list[str] = []
        for msg in messages:
            if isinstance(msg, dict):
                text_parts.append(str(msg.get("text", "")))
        text = " ".join(text_parts)
        result = claims_gate(text)
        for msg in messages:
            if isinstance(msg, dict) and isinstance(msg.get("text"), str):
                if len(msg["text"]) > _LINE_TEXT_MAX:
                    result.blocked_reasons.append(
                        f"Message text exceeds {_LINE_TEXT_MAX} characters"
                    )
        # LINE-specific: promotional messages require an official account with approved use.
        if not payload.get("to"):
            result.blocked_reasons.append("Recipient (to) is required")
        result.passed = len(result.blocked_reasons) == 0
        return result

    async def publish(self, tokens: TokenSet, payload: dict[str, Any]) -> PublishedRef:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_LINE_API_BASE}/v2/bot/message/push",
                headers={
                    "Authorization": f"Bearer {tokens.access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "to": payload["to"],
                    "messages": payload["messages"],
                },
            )
            resp.raise_for_status()
        # LINE push API returns no message id; synthesize a ref.
        return PublishedRef(
            channel=self.channel,
            native_id=f"line:{payload['to']}",
            published_at=datetime.now(UTC),
        )

    async def metrics(self, tokens: TokenSet, since: datetime) -> list[MetricEvent]:
        # LINE Messaging API offers delivery stats via /v2/bot/message/delivery.
        events: list[MetricEvent] = []
        async with httpx.AsyncClient() as client:
            for metric in ("delivered", "read"):
                resp = await client.get(
                    f"{_LINE_API_BASE}/v2/bot/message/delivery/{metric}",
                    headers={"Authorization": f"Bearer {tokens.access_token}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    events.append(
                        MetricEvent(
                            channel=self.channel,
                            entity_type="message",
                            entity_id="line",
                            metric=metric,
                            value=float(data.get("success", 0)),
                            ts=datetime.now(UTC),
                        )
                    )
        return events
