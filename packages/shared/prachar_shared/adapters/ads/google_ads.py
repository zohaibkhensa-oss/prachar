from __future__ import annotations

import hashlib
import logging
import uuid
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
from .audience_translation import google_geo_target, translate_taxonomy_sync
from .base import AdNetworkAdapter

logger = logging.getLogger(__name__)

# Google RSA char limits (spec 06 §Creatives).
GOOGLE_RSA_HEADLINE_LIMIT = 30
GOOGLE_RSA_DESCRIPTION_LIMIT = 90
GOOGLE_RSA_MAX_HEADLINES = 15
GOOGLE_RSA_MAX_DESCRIPTIONS = 4


@register_ads
class GoogleAdsAdapter(AdNetworkAdapter):
    """Google Ads adapter (spec 03 AdNetworkAdapter, spec 06 networks table P0)."""

    network = "google_ads"

    # ----- audience translation -----
    def translate_audience(self, spec: AudienceSpec) -> NativeTargeting:
        geo_targets: list[dict[str, Any]] = []
        for code in spec.geo:
            country = code.split("-", 1)[0]
            geo_targets.append(
                {
                    "iso_code": country,
                    "geo_target_constant": f"geoTargetConstants/{google_geo_target(country)}",
                    "sub_code": code,
                }
            )

        in_market = translate_taxonomy_sync(spec.interests, "interests", "google_ads")
        keywords = translate_taxonomy_sync(spec.intents, "intents", "google_ads")

        payload: dict[str, Any] = {
            "geo_targets": geo_targets,
            "in_market_audiences": in_market,
            "keywords": keywords,
            "languages": list(spec.languages),
            "age_range": {"min": spec.age[0], "max": spec.age[1]},
            "gender": spec.gender.value,
        }
        if spec.lookalike_seed:
            payload["customer_match_list_id"] = spec.lookalike_seed
        return NativeTargeting(network=self.network, payload=payload)

    # ----- campaign lifecycle -----
    def create_campaign(self, tokens: TokenSet, campaign: dict[str, Any]) -> str:
        # Stub: deterministic fake campaign id derived from campaign dict hash.
        raw = repr(sorted(campaign.items()))
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        campaign_id = f"gads-{digest}"
        logger.info("google_ads.create_campaign stub -> %s", campaign_id)
        return campaign_id

    def upload_creative(self, tokens: TokenSet, creative: CreativeAsset) -> str:
        raw = repr(sorted(creative.payload.items())) + creative.channel + creative.locale
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        creative_id = f"gads-rsa-{digest}"
        logger.info("google_ads.upload_creative stub -> %s", creative_id)
        return creative_id

    def set_budget_bid(
        self, tokens: TokenSet, campaign_id: str, budget: float, bid: dict[str, Any]
    ) -> None:
        # Money safety: idempotency key = campaign_id + action.
        idem = f"{campaign_id}:set_budget_bid"
        logger.info(
            "google_ads.set_budget_bid stub campaign=%s budget=%s bid=%s idem=%s",
            campaign_id,
            budget,
            bid,
            idem,
        )

    def pause(self, tokens: TokenSet, campaign_id: str) -> None:
        idem = f"{campaign_id}:pause"
        logger.info("google_ads.pause stub campaign=%s idem=%s", campaign_id, idem)

    def stats(self, tokens: TokenSet, campaign_id: str, since: datetime) -> list[MetricEvent]:
        # Stub: deterministic mock metrics for the last 3 days since `since`.
        events: list[MetricEvent] = []
        base = max(since, datetime.now(UTC) - timedelta(days=3))
        seed = int(hashlib.sha256(campaign_id.encode("utf-8")).hexdigest()[:8], 16)
        for d in range(3):
            ts = base + timedelta(days=d)
            for metric, base_val in (("impressions", 1000.0), ("clicks", 50.0), ("cost", 12.5), ("conversions", 2.0)):
                events.append(
                    MetricEvent(
                        channel=self.network,
                        entity_type="campaign",
                        entity_id=campaign_id,
                        metric=metric,
                        value=round(base_val + (seed % 17) * (d + 1) * 0.1, 4),
                        ts=ts,
                    )
                )
        return events

    # ----- policy -----
    def policy_precheck(self, creative: CreativeAsset) -> PolicyResult:
        text = self._extract_copy_text(creative)
        result = claims_gate(text)
        # Google-specific: RSA field length checks (warnings, not hard blocks).
        warnings = list(result.warnings)
        if creative.type == CreativeType.copy:
            headlines = creative.payload.get("headlines", [])
            descriptions = creative.payload.get("descriptions", [])
            for i, h in enumerate(headlines):
                if isinstance(h, str) and len(h) > GOOGLE_RSA_HEADLINE_LIMIT:
                    warnings.append(f"headline[{i}] exceeds {GOOGLE_RSA_HEADLINE_LIMIT} chars")
            for i, d in enumerate(descriptions):
                if isinstance(d, str) and len(d) > GOOGLE_RSA_DESCRIPTION_LIMIT:
                    warnings.append(f"description[{i}] exceeds {GOOGLE_RSA_DESCRIPTION_LIMIT} chars")
            if len(headlines) > GOOGLE_RSA_MAX_HEADLINES:
                warnings.append(f"too many headlines: {len(headlines)} > {GOOGLE_RSA_MAX_HEADLINES}")
            if len(descriptions) > GOOGLE_RSA_MAX_DESCRIPTIONS:
                warnings.append(f"too many descriptions: {len(descriptions)} > {GOOGLE_RSA_MAX_DESCRIPTIONS}")
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
        for key in ("headlines", "descriptions"):
            v = payload.get(key)
            if isinstance(v, list):
                parts.extend(str(x) for x in v if isinstance(x, (str, int, float)))
        return " ".join(parts)
