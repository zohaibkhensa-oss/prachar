from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

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
_REDDIT_API_BASE = "https://ads-api.reddit.com/api/v3"


@register_ads
class RedditAdsAdapter(AdNetworkAdapter):
    """Reddit Ads API v3 adapter (spec 06 networks table P2 — US/tech)."""

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

    @staticmethod
    def _get_account_id(tokens: TokenSet) -> str:
        """Extract Reddit ad account ID from token scopes or metadata."""
        for scope in tokens.scopes:
            if scope.startswith("account:"):
                return scope.split(":", 1)[1]
        return tokens.access_token.split(":")[0] if ":" in tokens.access_token else ""

    @staticmethod
    def _headers(tokens: TokenSet) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {tokens.access_token}",
            "Content-Type": "application/json",
        }

    # ----- campaign lifecycle -----
    async def create_campaign(self, tokens: TokenSet, campaign: dict[str, Any]) -> str:
        account_id = self._get_account_id(tokens)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{_REDDIT_API_BASE}/accounts/{account_id}/campaigns",
                    headers=self._headers(tokens),
                    json={
                        "name": campaign.get("name", "CURV AI Campaign"),
                        "objective": campaign.get("objective", "AWARENESS"),
                        "budget": int(campaign.get("budget_daily", 100) * 100),  # cents
                        "pacing_type": "standard",
                        "start_time": campaign.get("start_time", datetime.now(UTC).isoformat()),
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return str(data.get("data", {}).get("id", ""))
        except Exception as exc:  # noqa: BLE001
            logger.warning("reddit_ads.create_campaign failed: %s", exc)
            return ""

    async def upload_creative(self, tokens: TokenSet, creative: CreativeAsset) -> str:
        account_id = self._get_account_id(tokens)
        try:
            payload = creative.payload or {}
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{_REDDIT_API_BASE}/accounts/{account_id}/creatives",
                    headers=self._headers(tokens),
                    json={
                        "headline": payload.get("headline", ""),
                        "body": payload.get("body", payload.get("text", "")),
                        "image_url": payload.get("image_url", ""),
                        "link_url": payload.get("link_url", ""),
                        "creative_type": "text",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return str(data.get("data", {}).get("id", ""))
        except Exception as exc:  # noqa: BLE001
            logger.warning("reddit_ads.upload_creative failed: %s", exc)
            return ""

    async def set_budget_bid(
        self, tokens: TokenSet, campaign_id: str, budget: float, bid: dict[str, Any]
    ) -> None:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                await client.patch(
                    f"{_REDDIT_API_BASE}/campaigns/{campaign_id}",
                    headers=self._headers(tokens),
                    json={
                        "budget": int(budget * 100),  # cents
                        "bid": bid,
                    },
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("reddit_ads.set_budget_bid failed: %s", exc)

    async def pause(self, tokens: TokenSet, campaign_id: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                await client.patch(
                    f"{_REDDIT_API_BASE}/campaigns/{campaign_id}",
                    headers=self._headers(tokens),
                    json={"status": "PAUSED"},
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("reddit_ads.pause failed: %s", exc)

    async def stats(self, tokens: TokenSet, campaign_id: str, since: datetime) -> list[MetricEvent]:
        end_date = datetime.now(UTC).date().isoformat()
        start_date = since.date().isoformat()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{_REDDIT_API_BASE}/reports",
                    headers=self._headers(tokens),
                    json={
                        "campaign_ids": [campaign_id],
                        "start_date": start_date,
                        "end_date": end_date,
                        "granularity": "DAY",
                        "metrics": ["impressions", "clicks", "spend", "conversions"],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            events: list[MetricEvent] = []
            for row in data.get("data", []):
                ts_str = row.get("date", end_date)
                try:
                    ts = datetime.fromisoformat(ts_str)
                except (ValueError, TypeError):
                    ts = datetime.now(UTC)
                for metric in ("impressions", "clicks", "spend", "conversions"):
                    if metric in row:
                        events.append(MetricEvent(
                            channel=self.network,
                            entity_type="campaign",
                            entity_id=campaign_id,
                            metric=metric,
                            value=float(row[metric] or 0),
                            ts=ts,
                        ))
            return events
        except Exception as exc:  # noqa: BLE001
            logger.warning("reddit_ads.stats failed: %s", exc)
            return []

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
