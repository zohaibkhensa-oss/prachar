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

# LinkedIn Ads copy char limits (spec 06 §Creatives).
LI_INTRO_TEXT_LIMIT = 150
LI_HEADLINE_LIMIT = 70
LI_DESCRIPTION_LIMIT = 100

# Stub ISO-3166-1 -> LinkedIn region URN country code.
_LI_GEO_CODES: dict[str, str] = {
    "US": "us",
    "IN": "in",
    "GB": "gb",
    "CA": "ca",
    "AU": "au",
    "DE": "de",
    "FR": "fr",
    "AE": "ae",
    "SG": "sg",
    "JP": "jp",
}

# Stub company-size buckets (LinkedIn employeeCountRanges).
_COMPANY_SIZE_BUCKETS = [
    "B_1_10",
    "B_11_50",
    "B_51_200",
    "B_201_500",
    "B_501_1000",
    "B_1001_5000",
    "B_5001_10000",
    "B_10001_PLUS",
]


def _li_geo_urn(code: str) -> str:
    country = code.split("-", 1)[0].lower()
    cc = _LI_GEO_CODES.get(country.upper(), country)
    return f"urn:li:country:{cc}"


@register_ads
class LinkedInAdsAdapter(AdNetworkAdapter):
    """LinkedIn Marketing API adapter (spec 06 networks table P1, B2B)."""

    network = "linkedin_ads"

    # ----- audience translation -----
    def translate_audience(self, spec: AudienceSpec) -> NativeTargeting:
        locations = [{"geo_urn": _li_geo_urn(c)} for c in spec.geo]
        # interests → job titles / skills mapping (LLM-assisted, cached via translate_taxonomy_sync).
        job_titles = translate_taxonomy_sync(spec.interests, "interests", "linkedin_ads")
        skills = translate_taxonomy_sync(spec.interests, "skills", "linkedin_ads")
        # intents → company-size targeting (heuristic bucket selection).
        company_sizes: list[str] = []
        if spec.intents:
            # Map intent count to a deterministic bucket for stub determinism.
            idx = (len(spec.intents) - 1) % len(_COMPANY_SIZE_BUCKETS)
            company_sizes.append(_COMPANY_SIZE_BUCKETS[idx])

        payload: dict[str, Any] = {
            "locations": locations,
            "job_titles": job_titles,
            "skills": skills,
            "company_sizes": company_sizes,
            "age_range": {"min": spec.age[0], "max": spec.age[1]},
            "gender": spec.gender.value,
            "languages": list(spec.languages),
        }
        if spec.lookalike_seed:
            payload["lookalike"] = {
                "audience_definition": "urn:li:audienceMatchAccount:...",
                "source_urn": spec.lookalike_seed,
            }
        return NativeTargeting(network=self.network, payload=payload)

    # ----- campaign lifecycle -----
    def create_campaign(self, tokens: TokenSet, campaign: dict[str, Any]) -> str:
        raw = repr(sorted(campaign.items()))
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        campaign_id = f"liads-{digest}"
        logger.info("linkedin_ads.create_campaign stub -> %s", campaign_id)
        return campaign_id

    def upload_creative(self, tokens: TokenSet, creative: CreativeAsset) -> str:
        raw = repr(sorted(creative.payload.items())) + creative.channel + creative.locale
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        creative_id = f"liads-creative-{digest}"
        logger.info("linkedin_ads.upload_creative stub -> %s", creative_id)
        return creative_id

    def set_budget_bid(
        self, tokens: TokenSet, campaign_id: str, budget: float, bid: dict[str, Any]
    ) -> None:
        idem = f"{campaign_id}:set_budget_bid"
        logger.info(
            "linkedin_ads.set_budget_bid stub campaign=%s budget=%s bid=%s idem=%s",
            campaign_id,
            budget,
            bid,
            idem,
        )

    def pause(self, tokens: TokenSet, campaign_id: str) -> None:
        idem = f"{campaign_id}:pause"
        logger.info("linkedin_ads.pause stub campaign=%s idem=%s", campaign_id, idem)

    def stats(self, tokens: TokenSet, campaign_id: str, since: datetime) -> list[MetricEvent]:
        events: list[MetricEvent] = []
        base = max(since, datetime.now(UTC) - timedelta(days=3))
        seed = int(hashlib.sha256(campaign_id.encode("utf-8")).hexdigest()[:8], 16)
        for d in range(3):
            ts = base + timedelta(days=d)
            for metric, base_val in (
                ("impressions", 600.0),
                ("clicks", 18.0),
                ("cost", 15.0),
                ("conversions", 0.8),
            ):
                events.append(
                    MetricEvent(
                        channel=self.network,
                        entity_type="campaign",
                        entity_id=campaign_id,
                        metric=metric,
                        value=round(base_val + (seed % 19) * (d + 1) * 0.1, 4),
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
                ("intro_text", LI_INTRO_TEXT_LIMIT),
                ("headline", LI_HEADLINE_LIMIT),
                ("description", LI_DESCRIPTION_LIMIT),
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
        for key in ("text", "headline", "intro_text", "primary_text", "description"):
            v = payload.get(key)
            if isinstance(v, str):
                parts.append(v)
        return " ".join(parts)
