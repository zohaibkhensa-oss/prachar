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

# TikTok Ads copy char limits (spec 06 §Creatives).
TT_PRIMARY_TEXT_LIMIT = 100
TT_HEADLINE_LIMIT = 100

# Stub ISO-3166-1 -> TikTok region code (ISO-2 used by TikTok Business Center).
_TT_GEO_CODES: dict[str, str] = {
    "US": "US",
    "IN": "IN",
    "GB": "GB",
    "CA": "CA",
    "AU": "AU",
    "DE": "DE",
    "FR": "FR",
    "AE": "AE",
    "SG": "SG",
    "JP": "JP",
}


def _tt_geo(code: str) -> str:
    country = code.split("-", 1)[0].upper()
    return _TT_GEO_CODES.get(country, country)


@register_ads
class TikTokAdsAdapter(AdNetworkAdapter):
    """TikTok Marketing API adapter (spec 06 networks table P1)."""

    network = "tiktok_ads"

    # ----- audience translation -----
    def translate_audience(self, spec: AudienceSpec) -> NativeTargeting:
        locations = [{"region": _tt_geo(c), "country_code": c.split("-", 1)[0]} for c in spec.geo]
        interests = translate_taxonomy_sync(spec.interests, "interests", "tiktok_ads")
        # intents → hashtag audiences (TikTok-specific).
        hashtag_audiences = translate_taxonomy_sync(spec.intents, "intents", "tiktok_ads")

        payload: dict[str, Any] = {
            "location": locations,
            "interests": interests,
            "hashtag_audiences": hashtag_audiences,
            "age_range": {"min": spec.age[0], "max": spec.age[1]},
            "gender": spec.gender.value,
            "languages": list(spec.languages),
        }
        if spec.lookalike_seed:
            payload["lookalike"] = {
                "customer_file_id": spec.lookalike_seed,
                "type": "EXPANSION",
            }
        return NativeTargeting(network=self.network, payload=payload)

    # ----- campaign lifecycle -----
    def create_campaign(self, tokens: TokenSet, campaign: dict[str, Any]) -> str:
        raw = repr(sorted(campaign.items()))
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        campaign_id = f"ttads-{digest}"
        logger.info("tiktok_ads.create_campaign stub -> %s", campaign_id)
        return campaign_id

    def upload_creative(self, tokens: TokenSet, creative: CreativeAsset) -> str:
        raw = repr(sorted(creative.payload.items())) + creative.channel + creative.locale
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        creative_id = f"ttads-creative-{digest}"
        logger.info("tiktok_ads.upload_creative stub -> %s", creative_id)
        return creative_id

    def set_budget_bid(
        self, tokens: TokenSet, campaign_id: str, budget: float, bid: dict[str, Any]
    ) -> None:
        idem = f"{campaign_id}:set_budget_bid"
        logger.info(
            "tiktok_ads.set_budget_bid stub campaign=%s budget=%s bid=%s idem=%s",
            campaign_id,
            budget,
            bid,
            idem,
        )

    def pause(self, tokens: TokenSet, campaign_id: str) -> None:
        idem = f"{campaign_id}:pause"
        logger.info("tiktok_ads.pause stub campaign=%s idem=%s", campaign_id, idem)

    def stats(self, tokens: TokenSet, campaign_id: str, since: datetime) -> list[MetricEvent]:
        events: list[MetricEvent] = []
        base = max(since, datetime.now(UTC) - timedelta(days=3))
        seed = int(hashlib.sha256(campaign_id.encode("utf-8")).hexdigest()[:8], 16)
        for d in range(3):
            ts = base + timedelta(days=d)
            for metric, base_val in (
                ("impressions", 1200.0),
                ("clicks", 40.0),
                ("cost", 8.0),
                ("conversions", 1.2),
            ):
                events.append(
                    MetricEvent(
                        channel=self.network,
                        entity_type="campaign",
                        entity_id=campaign_id,
                        metric=metric,
                        value=round(base_val + (seed % 11) * (d + 1) * 0.1, 4),
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
            for key, limit in (
                ("primary_text", TT_PRIMARY_TEXT_LIMIT),
                ("headline", TT_HEADLINE_LIMIT),
            ):
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
        for key in ("text", "headline", "primary_text", "description"):
            v = payload.get(key)
            if isinstance(v, str):
                parts.append(v)
        return " ".join(parts)
