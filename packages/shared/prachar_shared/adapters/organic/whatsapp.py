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

_WA_GRAPH_BASE = "https://graph.facebook.com/v19.0"


@register_organic
class WhatsAppAdapter(ChannelAdapter):
    """WhatsApp Business Cloud API adapter (spec 05 regional table)."""

    channel = "whatsapp"

    def auth_url(self, state: str) -> str:
        # WhatsApp uses a system token configured via env, not OAuth.
        # Return a settings URL where the token / phone_number_id are configured.
        s = get_settings()
        base = s.next_public_api_base or "http://localhost:8000"
        return f"{base}/settings/channels/whatsapp?state={state}"

    def exchange_code(self, code: str) -> TokenSet:
        # Not OAuth — token is configured via env WHATSAPP_TOKEN.
        s = get_settings()
        token = s.whatsapp_token or code
        return TokenSet(
            access_token=token,
            refresh_token=None,
            expires_at=datetime.now(UTC) + timedelta(days=365),
            scopes=["whatsapp_business_messaging"],
        )

    async def fetch_profile(self, tokens: TokenSet) -> ChannelProfile:
        s = get_settings()
        phone_number_id = s.whatsapp_phone_number_id
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_WA_GRAPH_BASE}/{phone_number_id}",
                params={"fields": "display_phone_number,verified_name", "access_token": tokens.access_token},
            )
            resp.raise_for_status()
            data = resp.json()
        return ChannelProfile(
            channel=self.channel,
            handle=str(data.get("display_phone_number", "")),
            display_name=str(data.get("verified_name", "")),
            metadata={"phone_number_id": phone_number_id},
        )

    def generate_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "to_phone": {"type": "string"},
                "template_name": {"type": "string"},
                "template_language": {"type": "string"},
                "components": {"type": "array", "items": {"type": "object"}},
                "media_type": {"type": "string", "enum": ["image", "video", "document", "audio", "none"]},
                "media_url": {"type": "string"},
            },
            "required": ["to_phone", "template_name", "template_language"],
        }

    def policy_gate(self, payload: dict[str, Any]) -> PolicyResult:
        # Opt-in check: must broadcast only to opted-in lists.
        opted_in = payload.get("opted_in", False)
        template_name = payload.get("template_name", "")
        components = payload.get("components", [])
        # Gather text from components for claims_gate.
        text_parts: list[str] = [template_name]
        for comp in components:
            if isinstance(comp, dict):
                for param in comp.get("parameters", []):
                    if isinstance(param, dict) and isinstance(param.get("text"), str):
                        text_parts.append(param["text"])
        text = " ".join(text_parts)
        result = claims_gate(text)
        if not opted_in:
            result.blocked_reasons.append("Recipient must be on an opted-in list")
        # Non-template (free-form promotional) messages are not allowed.
        if not template_name:
            result.blocked_reasons.append("Promotional content requires an approved template")
        result.passed = len(result.blocked_reasons) == 0
        return result

    async def publish(self, tokens: TokenSet, payload: dict[str, Any]) -> PublishedRef:
        s = get_settings()
        phone_number_id = s.whatsapp_phone_number_id or payload.get("_phone_number_id", "")
        if not phone_number_id:
            raise ValueError("whatsapp_phone_number_id not configured")
        body: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": payload["to_phone"],
            "type": "template",
            "template": {
                "name": payload["template_name"],
                "language": {"code": payload.get("template_language", "en_US")},
                "components": payload.get("components", []),
            },
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_WA_GRAPH_BASE}/{phone_number_id}/messages",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
        message_id = data.get("messages", [{}])[0].get("id", "")
        return PublishedRef(
            channel=self.channel,
            native_id=message_id,
            published_at=datetime.now(UTC),
        )

    async def metrics(self, tokens: TokenSet, since: datetime) -> list[MetricEvent]:
        s = get_settings()
        phone_number_id = s.whatsapp_phone_number_id
        events: list[MetricEvent] = []
        async with httpx.AsyncClient() as client:
            for metric in ("delivered", "read", "failed"):
                resp = await client.get(
                    f"{_WA_GRAPH_BASE}/{phone_number_id}/message_insights",
                    params={"metric": metric, "access_token": tokens.access_token},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    events.append(
                        MetricEvent(
                            channel=self.channel,
                            entity_type="message",
                            entity_id=str(phone_number_id),
                            metric=metric,
                            value=float(data.get("data", [{}])[0].get("total", 0)) if data.get("data") else 0.0,
                            ts=datetime.now(UTC),
                        )
                    )
        return events
