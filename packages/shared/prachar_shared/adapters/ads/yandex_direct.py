from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from ...contracts import (
    AudienceSpec,
    CreativeAsset,
    CreativeType,
    MetricEvent,
    NativeTargeting,
    PolicyResult,
    TokenSet,
)
from ...policy.claims_gate import claims_gate
from ..registry import register_ads
from .audience_translation import translate_taxonomy_sync
from .base import AdNetworkAdapter

logger = logging.getLogger(__name__)

# Yandex region code map (ISO-3166-1 -> Yandex region id, representative subset).
_YANDEX_REGION_MAP: dict[str, int] = {
    "RU": 225,
    "UA": 187,
    "KZ": 159,
    "BY": 149,
    "US": 84,
}

_YANDEX_TITLE_LIMIT = 56
_YANDEX_TEXT_LIMIT = 81


@register_ads
class YandexDirectAdapter(AdNetworkAdapter):
    """Yandex Direct API adapter (spec 06 networks table P3 — CIS)."""

    network = "yandex_direct"

    # ----- audience translation -----
    def translate_audience(self, spec: AudienceSpec) -> NativeTargeting:
        # geo -> Yandex regions.
        regions: list[dict[str, Any]] = []
        for code in spec.geo:
            country = code.split("-", 1)[0]
            region_id = _YANDEX_REGION_MAP.get(country, 225)
            regions.append({"region_id": region_id, "country": country, "sub_code": code})
        # keywords -> search targeting.
        keywords = translate_taxonomy_sync(spec.intents, "intents", "yandex_direct")
        interests = translate_taxonomy_sync(spec.interests, "interests", "yandex_direct")

        payload: dict[str, Any] = {
            "regions": regions,
            "keywords": keywords,
            "interests": interests,
            "languages": list(spec.languages),
            "age_range": {"min": spec.age[0], "max": spec.age[1]},
            "gender": spec.gender.value,
        }
        if spec.lookalike_seed:
            payload["lookalike_seed"] = spec.lookalike_seed
        return NativeTargeting(network=self.network, payload=payload)

    # ----- campaign lifecycle -----
    def create_campaign(self, tokens: TokenSet, campaign: dict[str, Any]) -> str:
        raw = repr(sorted(campaign.items()))
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        campaign_id = f"ydx-{digest}"
        logger.info("yandex_direct.create_campaign stub -> %s", campaign_id)
        return campaign_id

    def upload_creative(self, tokens: TokenSet, creative: CreativeAsset) -> str:
        raw = repr(sorted(creative.payload.items())) + creative.channel + creative.locale
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        creative_id = f"ydx-creative-{digest}"
        logger.info("yandex_direct.upload_creative stub -> %s", creative_id)
        return creative_id

    def set_budget_bid(
        self, tokens: TokenSet, campaign_id: str, budget: float, bid: dict[str, Any]
    ) -> None:
        idem = f"{campaign_id}:set_budget_bid"
        logger.info(
            "yandex_direct.set_budget_bid stub campaign=%s budget=%s bid=%s idem=%s",
            campaign_id, budget, bid, idem,
        )

    def pause(self, tokens: TokenSet, campaign_id: str) -> None:
        idem = f"{campaign_id}:pause"
        logger.info("yandex_direct.pause stub campaign=%s idem=%s", campaign_id, idem)

    def stats(self, tokens: TokenSet, campaign_id: str, since: datetime) -> list[MetricEvent]:
        events: list[MetricEvent] = []
        base = max(since, datetime.now(UTC) - timedelta(days=3))
        seed = int(hashlib.sha256(campaign_id.encode("utf-8")).hexdigest()[:8], 16)
        for d in range(3):
            ts = base + timedelta(days=d)
            for metric, base_val in (
                ("impressions", 300.0), ("clicks", 10.0), ("cost", 3.0), ("conversions", 0.4),
            ):
                events.append(
                    MetricEvent(
                        channel=self.network,
                        entity_type="campaign",
                        entity_id=campaign_id,
                        metric=metric,
                        value=round(base_val + (seed % 5) * (d + 1) * 0.1, 4),
                        ts=ts,
                    )
                )
        return events

    # ----- policy -----
    def policy_precheck(self, creative: CreativeAsset) -> PolicyResult:
        text = self._extract_copy_text(creative)
        result = claims_gate(text)
        warnings = list(result.warnings)
        if creative.type == CreativeType.copy:
            payload = creative.payload or {}
            for key, limit in (("title", _YANDEX_TITLE_LIMIT), ("text", _YANDEX_TEXT_LIMIT)):
                v = payload.get(key)
                if isinstance(v, str) and len(v) > limit:
                    warnings.append(f"{key} exceeds {limit} chars")
        return PolicyResult(
            passed=result.passed,
            blocked_reasons=list(result.blocked_reasons),
            warnings=warnings,
        )

    @staticmethod
    def _extract_copy_text(creative: CreativeAsset) -> str:
        payload = creative.payload or {}
        parts: list[str] = []
        for key in ("text", "title", "headline", "description"):
            v = payload.get(key)
            if isinstance(v, str):
                parts.append(v)
        return " ".join(parts)
