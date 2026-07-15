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

_REDDIT_HEADLINE_LIMIT = 100
_REDDIT_BODY_LIMIT = 300


@register_ads
class RedditAdsAdapter(AdNetworkAdapter):
    """Reddit Ads API adapter (spec 06 networks table P2 — US/tech)."""

    network = "reddit_ads"

    # ----- audience translation -----
    def translate_audience(self, spec: AudienceSpec) -> NativeTargeting:
        # interests -> subreddit targeting.
        subreddits = translate_taxonomy_sync(spec.interests, "interests", "reddit_ads")
        # geo -> location.
        locations: list[dict[str, Any]] = []
        for code in spec.geo:
            country = code.split("-", 1)[0]
            locations.append({"country": country, "sub_code": code})
        # intents -> search keywords.
        keywords = translate_taxonomy_sync(spec.intents, "intents", "reddit_ads")

        payload: dict[str, Any] = {
            "subreddits": subreddits,
            "locations": locations,
            "search_keywords": keywords,
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
        campaign_id = f"rdads-{digest}"
        logger.info("reddit_ads.create_campaign stub -> %s", campaign_id)
        return campaign_id

    def upload_creative(self, tokens: TokenSet, creative: CreativeAsset) -> str:
        raw = repr(sorted(creative.payload.items())) + creative.channel + creative.locale
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        creative_id = f"rdads-creative-{digest}"
        logger.info("reddit_ads.upload_creative stub -> %s", creative_id)
        return creative_id

    def set_budget_bid(
        self, tokens: TokenSet, campaign_id: str, budget: float, bid: dict[str, Any]
    ) -> None:
        idem = f"{campaign_id}:set_budget_bid"
        logger.info(
            "reddit_ads.set_budget_bid stub campaign=%s budget=%s bid=%s idem=%s",
            campaign_id, budget, bid, idem,
        )

    def pause(self, tokens: TokenSet, campaign_id: str) -> None:
        idem = f"{campaign_id}:pause"
        logger.info("reddit_ads.pause stub campaign=%s idem=%s", campaign_id, idem)

    def stats(self, tokens: TokenSet, campaign_id: str, since: datetime) -> list[MetricEvent]:
        events: list[MetricEvent] = []
        base = max(since, datetime.now(UTC) - timedelta(days=3))
        seed = int(hashlib.sha256(campaign_id.encode("utf-8")).hexdigest()[:8], 16)
        for d in range(3):
            ts = base + timedelta(days=d)
            for metric, base_val in (
                ("impressions", 400.0), ("clicks", 12.0), ("cost", 4.0), ("conversions", 0.5),
            ):
                events.append(
                    MetricEvent(
                        channel=self.network,
                        entity_type="campaign",
                        entity_id=campaign_id,
                        metric=metric,
                        value=round(base_val + (seed % 9) * (d + 1) * 0.1, 4),
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
            for key, limit in (("headline", _REDDIT_HEADLINE_LIMIT), ("body", _REDDIT_BODY_LIMIT)):
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
        for key in ("text", "headline", "primary_text", "description", "body"):
            v = payload.get(key)
            if isinstance(v, str):
                parts.append(v)
        return " ".join(parts)
