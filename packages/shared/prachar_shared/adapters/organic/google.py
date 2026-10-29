from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

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

_GOOGLE_OAUTH_BASE = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


def _settings():
    from ...config import get_settings

    return get_settings()


def _client_id(s) -> str:
    return (s.google_client_id or s.google_ads_client_id or "").strip()


def _client_secret(s) -> str:
    return (s.google_client_secret or s.google_ads_client_secret or "").strip()


@register_organic
class GoogleSearchAdapter(ChannelAdapter):
    """Generic Google search presence adapter (SERP monitoring & Google OAuth)."""

    channel = "google"

    def auth_url(self, state: str) -> str:
        s = _settings()
        client_id = _client_id(s) or "GOOGLE_CLIENT_ID_PLACEHOLDER"
        params = {
            "client_id": client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": _GOOGLE_SCOPE,
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{_GOOGLE_OAUTH_BASE}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenSet:
        s = _settings()
        cid, csec = _client_id(s), _client_secret(s)
        if not (cid and csec):
            raise NotImplementedError(
                "Google OAuth exchange requires GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
            )
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": cid,
                    "client_secret": csec,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            resp.raise_for_status()
            body = resp.json()
        expires_in = int(body.get("expires_in", 3600))
        return TokenSet(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
            scopes=(body.get("scope") or _GOOGLE_SCOPE).split(" "),
        )

    def refresh_access_token(self, refresh_token: str) -> TokenSet:
        s = _settings()
        cid, csec = _client_id(s), _client_secret(s)
        if not (cid and csec):
            raise NotImplementedError("Google refresh requires GOOGLE_CLIENT_ID/SECRET")
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "refresh_token": refresh_token,
                    "client_id": cid,
                    "client_secret": csec,
                    "grant_type": "refresh_token",
                },
            )
            resp.raise_for_status()
            body = resp.json()
        expires_in = int(body.get("expires_in", 3600))
        return TokenSet(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token") or refresh_token,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
            scopes=(body.get("scope") or _GOOGLE_SCOPE).split(" "),
        )

    def fetch_profile(self, tokens: TokenSet) -> ChannelProfile:
        return ChannelProfile(
            channel=self.channel,
            handle="google-search",
            display_name="Google Search",
        )

    def generate_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "rank": {"type": "integer"},
                "url": {"type": "string"},
            },
            "required": ["query", "rank", "url"],
        }

    def policy_gate(self, payload: dict[str, Any]) -> PolicyResult:
        return PolicyResult(passed=True)

    def publish(self, tokens: TokenSet, payload: dict[str, Any]) -> PublishedRef:
        raise NotImplementedError(
            "Google organic search has no publish API; content is published via GSC indexing."
        )

    def metrics(self, tokens: TokenSet, since: datetime) -> list[MetricEvent]:
        """Pull SERP positions via SERP API if a key is configured."""
        s = _settings()
        if not s.serp_api_key.strip():
            logger.debug("google metrics: no SERP_API_KEY, returning empty list")
            return []
        # SERP API integration is delegated to the audit/serp module; here we
        # return an empty list as a stub (real implementation in S6 attribution).
        return []
