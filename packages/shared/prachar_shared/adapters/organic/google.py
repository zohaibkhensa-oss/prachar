from __future__ import annotations

import logging
from datetime import datetime
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

_GOOGLE_OAUTH_BASE = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


def _settings():
    from ...config import get_settings

    return get_settings()


@register_organic
class GoogleSearchAdapter(ChannelAdapter):
    """Generic Google search presence adapter (SERP monitoring).

    Google does not expose an organic publish API; this adapter is used for
    SERP monitoring / rank tracking only.
    """

    channel = "google"

    def auth_url(self, state: str) -> str:
        s = _settings()
        client_id = s.google_client_id or "GOOGLE_CLIENT_ID_PLACEHOLDER"
        params = {
            "client_id": client_id,
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
            "response_type": "code",
            "scope": _GOOGLE_SCOPE,
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{_GOOGLE_OAUTH_BASE}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenSet:
        raise NotImplementedError(
            "GoogleSearchAdapter does not support OAuth exchange; use SERP API key instead."
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
