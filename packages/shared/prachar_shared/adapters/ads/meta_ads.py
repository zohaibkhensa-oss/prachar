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
from .audience_translation import meta_location_target, translate_taxonomy_sync
from .base import AdNetworkAdapter

logger = logging.getLogger(__name__)

# Meta ad copy char limits (spec 06 §Creatives).
META_PRIMARY_TEXT_LIMIT = 125
META_HEADLINE_LIMIT = 40
META_DESCRIPTION_LIMIT = 30


@register_ads
class MetaAdsAdapter(AdNetworkAdapter):
    """Meta (Facebook/Instagram) Marketing API adapter (spec 06 networks table P0)."""

    network = "meta_ads"

    # ----- audience translation -----
    def translate_audience(self, spec: AudienceSpec) -> NativeTargeting:
        locations: list[dict[str, Any]] = []
        for code in spec.geo:
            country = code.split("-", 1)[0]
            locations.append(meta_location_target(country))

        interests = translate_taxonomy_sync(spec.interests, "interests", "meta_ads")
        behaviors = translate_taxonomy_sync(spec.intents, "intents", "meta_ads")

        payload: dict[str, Any] = {
            "targeting": {
                "geo_locations": locations,
                "interests": interests,
                "behaviors": behaviors,
                "age_min": spec.age[0],
                "age_max": spec.age[1],
                "genders": [self._meta_gender_code(spec)],
                "locales": list(spec.languages),
            },
        }
        if spec.lookalike_seed:
            payload["lookalike"] = {
                "origin_type": "customer_list",
                "customer_list_id": spec.lookalike_seed,
                "ratio": 0.01,
                "country": spec.geo[0].split("-", 1)[0] if spec.geo else "US",
            }
        return NativeTargeting(network=self.network, payload=payload)

    @staticmethod
    def _meta_gender_code(spec: AudienceSpec) -> int:
        # Meta genders: 1=all, 2=male, 3=female. We use 1 for any/non-binary.
        if spec.gender.value == "male":
            return 2
        if spec.gender.value == "female":
            return 3
        return 1

    # ----- campaign lifecycle -----
    def create_campaign(self, tokens: TokenSet, campaign: dict[str, Any]) -> str:
        raw = repr(sorted(campaign.items()))
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        campaign_id = f"meta-{digest}"
        logger.info("meta_ads.create_campaign stub -> %s", campaign_id)
        return campaign_id

    def upload_creative(self, tokens: TokenSet, creative: CreativeAsset) -> str:
        raw = repr(sorted(creative.payload.items())) + creative.channel + creative.locale
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        creative_id = f"meta-creative-{digest}"
        logger.info("meta_ads.upload_creative stub -> %s", creative_id)
        return creative_id

    def set_budget_bid(
        self, tokens: TokenSet, campaign_id: str, budget: float, bid: dict[str, Any]
    ) -> None:
        idem = f"{campaign_id}:set_budget_bid"
        logger.info(
            "meta_ads.set_budget_bid stub campaign=%s budget=%s bid=%s idem=%s",
            campaign_id,
            budget,
            bid,
            idem,
        )

    def pause(self, tokens: TokenSet, campaign_id: str) -> None:
        idem = f"{campaign_id}:pause"
        logger.info("meta_ads.pause stub campaign=%s idem=%s", campaign_id, idem)

    def stats(self, tokens: TokenSet, campaign_id: str, since: datetime) -> list[MetricEvent]:
        events: list[MetricEvent] = []
        base = max(since, datetime.now(UTC) - timedelta(days=3))
        seed = int(hashlib.sha256(campaign_id.encode("utf-8")).hexdigest()[:8], 16)
        for d in range(3):
            ts = base + timedelta(days=d)
            for metric, base_val in (("impressions", 800.0), ("clicks", 30.0), ("cost", 9.0), ("conversions", 1.5)):
                events.append(
                    MetricEvent(
                        channel=self.network,
                        entity_type="campaign",
                        entity_id=campaign_id,
                        metric=metric,
                        value=round(base_val + (seed % 13) * (d + 1) * 0.1, 4),
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
                ("primary_text", META_PRIMARY_TEXT_LIMIT),
                ("headline", META_HEADLINE_LIMIT),
                ("description", META_DESCRIPTION_LIMIT),
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
