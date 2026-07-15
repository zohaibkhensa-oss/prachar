from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

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

_NAVER_TITLE_MAX = 100


@register_organic
class NaverAdapter(ChannelAdapter):
    """Naver Search Advisor adapter (spec 05 regional table — Korea).

    Naver has limited public API for blog posting; this adapter focuses on
    Search Advisor (webmaster tools) SEO and provides a schema for Naver blog
    posts used in manual-assist mode.
    """

    channel = "naver"

    def auth_url(self, state: str) -> str:
        # Naver Search Advisor / Naver Developers console.
        return f"https://developers.naver.com/console/?state={state}"

    def exchange_code(self, code: str) -> TokenSet:
        return TokenSet(
            access_token=code,
            refresh_token=None,
            expires_at=datetime.now(UTC) + timedelta(days=30),
            scopes=["searchadvisor"],
        )

    async def fetch_profile(self, tokens: TokenSet) -> ChannelProfile:
        # Naver Search Advisor profile is limited; return a stub profile.
        return ChannelProfile(
            channel=self.channel,
            handle="",
            display_name="Naver Search Advisor",
            follower_count=None,
            metadata={},
        )

    def generate_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "maxLength": _NAVER_TITLE_MAX},
                "content": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "category": {"type": "string"},
            },
            "required": ["title", "content"],
        }

    def policy_gate(self, payload: dict[str, Any]) -> PolicyResult:
        title = payload.get("title", "")
        content = payload.get("content", "")
        text = f"{title} {content}"
        result = claims_gate(text)
        if len(title) > _NAVER_TITLE_MAX:
            result.blocked_reasons.append(f"Title exceeds {_NAVER_TITLE_MAX} characters")
        # Korean content check (stub): warn if content appears non-Korean and no ko locale.
        has_korean = any("\uac00" <= ch <= "\ud7a3" for ch in content)
        if not has_korean:
            result.warnings.append("Content does not appear to contain Korean text")
        result.passed = len(result.blocked_reasons) == 0
        return result

    async def publish(self, tokens: TokenSet, payload: dict[str, Any]) -> PublishedRef:
        # Naver blog posting is via manual-assist mode; no public publish API.
        raise NotImplementedError(
            "Naver blog publishing is manual-assist only; no public API"
        )

    async def metrics(self, tokens: TokenSet, since: datetime) -> list[MetricEvent]:
        # Naver Search Advisor offers limited stats via webmaster tools.
        return []
