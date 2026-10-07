from __future__ import annotations

import logging
from datetime import UTC
from typing import Any
from urllib.parse import urlencode

import httpx

from prachar_shared.config import get_settings
from prachar_shared.contracts import (
    ChannelProfile,
    MetricEvent,
    PolicyResult,
    PublishedRef,
    TokenSet,
)
from prachar_shared.policy.claims_gate import claims_gate

from ..registry import register_organic
from .base import ChannelAdapter

logger = logging.getLogger(__name__)

FB_GRAPH_BASE = "https://graph.facebook.com/v19.0"
FB_SCOPES = [
    "pages_manage_posts",
    "pages_read_engagement",
    "pages_show_list",
    "publish_to_groups",
]


@register_organic
class FacebookAdapter(ChannelAdapter):
    channel = "facebook"

    def auth_url(self, state: str) -> str:
        s = get_settings()
        client_id = s.meta_app_id or "PLACEHOLDER"
        params = urlencode({
            "client_id": client_id,
            "redirect_uri": self.redirect_uri,
            "scope": ",".join(FB_SCOPES),
            "response_type": "code",
            "state": state,
        })
        return f"https://www.facebook.com/v19.0/dialog/oauth?{params}"

    async def exchange_code(self, code: str) -> TokenSet:
        s = get_settings()
        if not s.meta_app_id or not s.meta_app_secret:
            raise NotImplementedError("META_APP_ID/META_APP_SECRET not configured")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{FB_GRAPH_BASE}/oauth/access_token",
                data={
                    "client_id": s.meta_app_id,
                    "client_secret": s.meta_app_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        from datetime import datetime, timedelta

        access_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)

        # Exchange the short-lived user token for a long-lived one (~60 days).
        try:
            async with httpx.AsyncClient() as client:
                ll = await client.get(
                    f"{FB_GRAPH_BASE}/oauth/access_token",
                    params={
                        "grant_type": "fb_exchange_token",
                        "client_id": s.meta_app_id,
                        "client_secret": s.meta_app_secret,
                        "fb_exchange_token": access_token,
                    },
                )
                if ll.status_code == 200:
                    ll_data = ll.json()
                    access_token = ll_data.get("access_token", access_token)
                    expires_in = ll_data.get("expires_in", expires_in)
        except Exception:
            logger.warning("facebook fb_exchange_token failed; using short-lived token", exc_info=True)

        return TokenSet(
            access_token=access_token,
            refresh_token=None,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
            scopes=FB_SCOPES,
        )

    async def fetch_ad_accounts(self, tokens: TokenSet) -> list[dict[str, Any]]:
        """Discover Meta ad accounts owned by the authenticated user.

        Returns ``[{"id": "act_123", "account_id": "123", "name": "...", "business": {...}}, ...]``.
        Empty list on error or when the user has no ad accounts.
        """
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{FB_GRAPH_BASE}/me/adaccounts",
                    params={
                        "fields": "id,account_id,name,business,account_status",
                        "access_token": tokens.access_token,
                    },
                )
                resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception:
            logger.warning("facebook.fetch_ad_accounts failed", exc_info=True)
            return []

    async def fetch_profile(self, tokens: TokenSet) -> ChannelProfile:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{FB_GRAPH_BASE}/me/accounts",
                params={"access_token": tokens.access_token},
            )
            resp.raise_for_status()
            data = resp.json()
        pages = data.get("data", [])
        if not pages:
            return ChannelProfile(channel=self.channel, handle="", display_name="")
        page = pages[0]
        # Get page details.
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{FB_GRAPH_BASE}/{page['id']}",
                params={"fields": "name,followers_count,fan_count", "access_token": page["access_token"]},
            )
            resp.raise_for_status()
            page_info = resp.json()
        return ChannelProfile(
            channel=self.channel,
            handle=page_info.get("name", ""),
            display_name=page_info.get("name", ""),
            follower_count=page_info.get("followers_count") or page_info.get("fan_count"),
            metadata={"page_id": page["id"], "page_access_token": page["access_token"]},
        )

    def generate_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "message": {"type": "string", "maxLength": 63206},
                "link": {"type": "string"},
                "picture": {"type": "string"},
                "name": {"type": "string", "maxLength": 100},
                "description": {"type": "string", "maxLength": 500},
                "scheduled_publish_time": {"type": "integer"},
                "hashtags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["message"],
        }

    def policy_gate(self, payload: dict[str, Any]) -> PolicyResult:
        message = payload.get("message", "")
        result = claims_gate(message)
        if len(message) > 63206:
            result.blocked_reasons.append("Message exceeds Facebook limit")
        result.passed = len(result.blocked_reasons) == 0
        return result

    async def publish(self, tokens: TokenSet, payload: dict[str, Any]) -> PublishedRef:
        from datetime import datetime

        # Need page access token — fetch from tokens or profile metadata.
        page_token = payload.get("_page_access_token", tokens.access_token)
        page_id = payload.get("_page_id", "me")
        async with httpx.AsyncClient() as client:
            params: dict[str, Any] = {
                "message": payload.get("message", ""),
                "access_token": page_token,
            }
            if "link" in payload:
                params["link"] = payload["link"]
            if "picture" in payload:
                params["picture"] = payload["picture"]
            if "scheduled_publish_time" in payload:
                params["scheduled_publish_time"] = payload["scheduled_publish_time"]
                params["published"] = "false"
            resp = await client.post(f"{FB_GRAPH_BASE}/{page_id}/feed", params=params)
            resp.raise_for_status()
            data = resp.json()
        post_id = data.get("id", "")
        return PublishedRef(
            channel=self.channel,
            native_id=post_id,
            url=f"https://www.facebook.com/{post_id.replace('_', '/posts/')}",
            published_at=datetime.now(UTC),
        )

    async def metrics(self, tokens: TokenSet, since: Any) -> list[MetricEvent]:
        from datetime import datetime

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{FB_GRAPH_BASE}/me/insights",
                params={
                    "metric": "page_impressions,page_post_engagements,page_fan_adds",
                    "period": "day",
                    "access_token": tokens.access_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        events = []
        ts = datetime.now(UTC)
        for metric_data in data.get("data", []):
            metric_name = f"fb_{metric_data['name']}"
            for val in metric_data.get("values", []):
                events.append(MetricEvent(
                    channel=self.channel,
                    entity_type="page",
                    entity_id="self",
                    metric=metric_name,
                    value=float(val.get("value", 0)),
                    ts=ts,
                ))
        return events
