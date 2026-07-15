from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from ...contracts import (
    ChannelProfile,
    MetricEvent,
    PolicyResult,
    PublishedRef,
    TokenSet,
)
from ..registry import register_organic
from .base import ChannelAdapter

logger = logging.getLogger(__name__)

_GMB_OAUTH_BASE = "https://accounts.google.com/o/oauth2/v2/auth"
_GMB_SCOPE = "https://www.googleapis.com/auth/business.manage"
_GMB_BASE = "https://mybusiness.googleapis.com/v4"


def _settings():
    from ...config import get_settings

    return get_settings()


@register_organic
class GMBAdapter(ChannelAdapter):
    """Google Business Profile adapter (spec 05)."""

    channel = "gmb"

    def auth_url(self, state: str) -> str:
        s = _settings()
        client_id = s.google_client_id or "GOOGLE_CLIENT_ID_PLACEHOLDER"
        params = {
            "client_id": client_id,
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
            "response_type": "code",
            "scope": _GMB_SCOPE,
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{_GMB_OAUTH_BASE}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenSet:
        s = _settings()
        if not (s.google_client_id.strip() and s.google_client_secret.strip()):
            raise NotImplementedError(
                "GMB OAuth exchange requires GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in settings."
            )
        # Reuse the GSC token-exchange helper via httpx.
        import asyncio

        import httpx

        resp = asyncio.run(
            httpx.AsyncClient(timeout=30.0).post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": s.google_client_id,
                    "client_secret": s.google_client_secret,
                    "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
                    "grant_type": "authorization_code",
                },
            )
        )
        resp.raise_for_status()
        body = resp.json()
        return TokenSet(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=datetime.now(UTC) + datetime.timedelta(seconds=int(body.get("expires_in", 3600))),
            scopes=body.get("scope", _GMB_SCOPE).split(" "),
        )

    def fetch_profile(self, tokens: TokenSet) -> ChannelProfile:
        return ChannelProfile(
            channel=self.channel,
            handle="gmb-profile",
            display_name="Google Business Profile",
        )

    def generate_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "cta_type": {"type": "string"},
                "cta_url": {"type": "string"},
                "media_url": {"type": "string"},
                "event_title": {"type": "string"},
                "event_start": {"type": "string"},
                "event_end": {"type": "string"},
            },
            "required": ["summary"],
        }

    def policy_gate(self, payload: dict[str, Any]) -> PolicyResult:
        summary = str(payload.get("summary", ""))
        if len(summary) > 500:
            return PolicyResult(passed=False, blocked_reasons=["summary too long: >500 chars"])
        return PolicyResult(passed=True)

    def publish(self, tokens: TokenSet, payload: dict[str, Any]) -> PublishedRef:
        # Stub: real implementation POSTs to {GMB_BASE}/accounts/{id}/locations/{loc}/localPosts
        logger.info("gmb publish stub payload=%s", payload)
        return PublishedRef(
            channel=self.channel,
            native_id=str(int(time.time())),
            url=payload.get("cta_url"),
            published_at=datetime.now(UTC),
        )

    def metrics(self, tokens: TokenSet, since: datetime) -> list[MetricEvent]:
        # Stub: real implementation pulls listing views from Business Profile Insights.
        logger.debug("gmb metrics stub since=%s", since)
        return []
