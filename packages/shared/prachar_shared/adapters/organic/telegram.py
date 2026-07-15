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

_TG_API_BASE = "https://api.telegram.org"
_TG_TEXT_MAX = 4096

# Naive spam pattern detection.
_SPAM_PATTERNS = ["http://", "https://", "buy now", "click here", "free money", "casino"]


@register_organic
class TelegramAdapter(ChannelAdapter):
    """Telegram Bot API adapter (spec 05 regional table)."""

    channel = "telegram"

    def auth_url(self, state: str) -> str:
        # Bot registration URL via BotFather.
        return f"https://t.me/botfather?start=register&state={state}"

    def exchange_code(self, code: str) -> TokenSet:
        # Uses TELEGRAM_BOT_TOKEN from env.
        s = get_settings()
        token = s.telegram_bot_token or code
        return TokenSet(
            access_token=token,
            refresh_token=None,
            expires_at=datetime.now(UTC) + timedelta(days=365),
            scopes=["bot"],
        )

    async def fetch_profile(self, tokens: TokenSet) -> ChannelProfile:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{_TG_API_BASE}/bot{tokens.access_token}/getMe")
            resp.raise_for_status()
            data = resp.json().get("result", {})
        return ChannelProfile(
            channel=self.channel,
            handle=str(data.get("username", "")),
            display_name=str(data.get("first_name", "")),
            follower_count=None,
            metadata={"bot_id": data.get("id")},
        )

    def generate_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "chat_id": {"type": "string"},
                "text": {"type": "string", "maxLength": _TG_TEXT_MAX},
                "parse_mode": {"type": "string", "enum": ["HTML", "MarkdownV2", "Markdown", ""]},
                "reply_markup": {"type": "object"},
                "media_url": {"type": "string"},
                "media_type": {"type": "string", "enum": ["photo", "video", "document", "none"]},
            },
            "required": ["chat_id", "text"],
        }

    def policy_gate(self, payload: dict[str, Any]) -> PolicyResult:
        text = payload.get("text", "")
        result = claims_gate(text)
        if len(text) > _TG_TEXT_MAX:
            result.blocked_reasons.append(f"Text exceeds {_TG_TEXT_MAX} characters")
        text_lower = text.lower()
        for pat in _SPAM_PATTERNS:
            if pat in text_lower:
                result.warnings.append(f"Potential spam pattern: {pat!r}")
        result.passed = len(result.blocked_reasons) == 0
        return result

    async def publish(self, tokens: TokenSet, payload: dict[str, Any]) -> PublishedRef:
        media_type = payload.get("media_type", "none")
        media_url = payload.get("media_url", "")
        async with httpx.AsyncClient() as client:
            if media_type == "photo" and media_url:
                resp = await client.post(
                    f"{_TG_API_BASE}/bot{tokens.access_token}/sendPhoto",
                    json={
                        "chat_id": payload["chat_id"],
                        "photo": media_url,
                        "caption": payload.get("text", ""),
                        "parse_mode": payload.get("parse_mode") or None,
                    },
                )
            else:
                resp = await client.post(
                    f"{_TG_API_BASE}/bot{tokens.access_token}/sendMessage",
                    json={
                        "chat_id": payload["chat_id"],
                        "text": payload["text"],
                        "parse_mode": payload.get("parse_mode") or None,
                        "reply_markup": payload.get("reply_markup"),
                    },
                )
            resp.raise_for_status()
            data = resp.json().get("result", {})
        message_id = str(data.get("message_id", ""))
        chat_id = str(payload["chat_id"])
        return PublishedRef(
            channel=self.channel,
            native_id=f"{chat_id}:{message_id}",
            url=f"https://t.me/c/{chat_id}/{message_id}",
            published_at=datetime.now(UTC),
        )

    async def metrics(self, tokens: TokenSet, since: datetime) -> list[MetricEvent]:
        # Telegram does not expose per-message views via Bot API; use getChatMemberCount
        # as a proxy for channel reach. Views/forwards are best-effort stubs.
        events: list[MetricEvent] = []
        chat_id = "0"  # caller may inject via tokens metadata in production
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_TG_API_BASE}/bot{tokens.access_token}/getChatMemberCount",
                json={"chat_id": chat_id},
            )
            if resp.status_code == 200:
                count = resp.json().get("result", 0)
                events.append(
                    MetricEvent(
                        channel=self.channel,
                        entity_type="chat",
                        entity_id=chat_id,
                        metric="member_count",
                        value=float(count),
                        ts=datetime.now(UTC),
                    )
                )
        # Stub view/forward metrics (not available via Bot API).
        for metric in ("views", "forwards"):
            events.append(
                MetricEvent(
                    channel=self.channel,
                    entity_type="chat",
                    entity_id=chat_id,
                    metric=metric,
                    value=0.0,
                    ts=datetime.now(UTC),
                )
            )
        return events
