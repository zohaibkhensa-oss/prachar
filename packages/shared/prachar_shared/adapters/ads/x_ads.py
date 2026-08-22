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

# X Ads API v11 base URL.
_X_ADS_API_BASE = "https://ads-api.x.com/11"
_X_ADS_TIMEOUT = 30.0

# X Ads copy char limits (spec 06 §Creatives).
X_TEXT_LIMIT = 280
X_HEADLINE_LIMIT = 50

# Canonical metric name -> X Ads stats API metric field mapping.
_X_METRIC_FIELDS: dict[str, str] = {
    "impressions": "impressions",
    "clicks": "clicks",
    "cost": "billed_charge_local_micro",  # spend in local micro currency
    "conversions": "conversion_purchases",
}

# Stub ISO-3166-1 -> X location targeting (uses ISO-2 names).
_X_GEO_CODES: dict[str, str] = {
    "US": "United States",
    "IN": "India",
    "GB": "United Kingdom",
    "CA": "Canada",
    "AU": "Australia",
    "DE": "Germany",
    "FR": "France",
    "AE": "United Arab Emirates",
    "SG": "Singapore",
    "JP": "Japan",
}


def _x_geo(code: str) -> str:
    country = code.split("-", 1)[0].upper()
    return _X_GEO_CODES.get(country, country)


@register_ads
class XAdsAdapter(AdNetworkAdapter):
    """X (Twitter) Ads API adapter (spec 06 networks table P2).

    Uses real Twitter Ads API v11 endpoints via httpx.AsyncClient.
    """

    network = "x_ads"

    # ----- helpers -----
    @staticmethod
    def _auth_headers(tokens: TokenSet) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {tokens.access_token}",
            "Content-Type": "application/json",
        }

    async def _get_account_id(self, tokens: TokenSet) -> str:
        """Resolve the X Ads account id for the authorised token.

        Calls GET /accounts and returns the first account's id. The Twitter Ads
        API returns the set of ads accounts the authenticated user has access to.
        """
        url = f"{_X_ADS_API_BASE}/accounts"
        async with httpx.AsyncClient(timeout=_X_ADS_TIMEOUT) as client:
            resp = await client.get(url, headers=self._auth_headers(tokens))
            resp.raise_for_status()
            body = resp.json()
        data = body.get("data") or []
        if not data:
            raise RuntimeError("x_ads: no ads accounts available for token")
        account = data[0]
        account_id = account.get("id")
        if not account_id:
            raise RuntimeError("x_ads: account response missing id")
        return str(account_id)

    # ----- audience translation -----
    def translate_audience(self, spec: AudienceSpec) -> NativeTargeting:
        locations = [{"name": _x_geo(c)} for c in spec.geo]
        # interests → X conversation topics (LLM-assisted, cached).
        conversation_topics = translate_taxonomy_sync(
            spec.interests, "interests", "x_ads"
        )
        # intents → followers targeting (heuristic: map intent to handle-like tokens).
        followers_targeting = translate_taxonomy_sync(
            spec.intents, "intents", "x_ads"
        )

        payload: dict[str, Any] = {
            "location": locations,
            "conversation_topics": conversation_topics,
            "followers_targeting": followers_targeting,
            "age_range": {"min": spec.age[0], "max": spec.age[1]},
            "gender": spec.gender.value,
            "languages": list(spec.languages),
        }
        if spec.lookalike_seed:
            payload["tailored_audience"] = {
                "audience_id": spec.lookalike_seed,
                "type": "FOLLOWERS",
            }
        return NativeTargeting(network=self.network, payload=payload)

    # ----- campaign lifecycle -----
    async def create_campaign(self, tokens: TokenSet, campaign: dict[str, Any]) -> str:
        """Create a campaign via POST /accounts/{account_id}/campaigns.

        Returns the real campaign id from the API response (data.id).
        """
        account_id = await self._get_account_id(tokens)
        url = f"{_X_ADS_API_BASE}/accounts/{account_id}/campaigns"

        # Build the campaign body from the canonical campaign dict.
        start_time = campaign.get("start_time")
        if isinstance(start_time, datetime):
            start_time = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        elif start_time is None:
            start_time = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        body: dict[str, Any] = {
            "name": campaign.get("name", f"prachar-campaign-{int(datetime.now(UTC).timestamp())}"),
            "funding_instrument_id": campaign.get("funding_instrument_id", ""),
            "daily_budget_amount_local_micro": int(
                float(campaign.get("daily_budget", 0)) * 1_000_000
            ),
            "total_budget_amount_local_micro": int(
                float(campaign.get("total_budget", 0)) * 1_000_000
            ),
            "start_time": start_time,
            "standard_delivery": bool(campaign.get("standard_delivery", True)),
        }
        # Optional fields.
        if "end_time" in campaign and campaign["end_time"]:
            end_time = campaign["end_time"]
            if isinstance(end_time, datetime):
                end_time = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            body["end_time"] = end_time
        if "objective" in campaign and campaign["objective"]:
            body["objective"] = campaign["objective"]

        try:
            async with httpx.AsyncClient(timeout=_X_ADS_TIMEOUT) as client:
                resp = await client.post(url, headers=self._auth_headers(tokens), json=body)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "x_ads.create_campaign HTTP %s: %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise
        except httpx.HTTPError as exc:
            logger.error("x_ads.create_campaign request error: %s", exc)
            raise

        data = payload.get("data") or {}
        campaign_id = data.get("id")
        if not campaign_id:
            raise RuntimeError(f"x_ads: create_campaign response missing data.id: {payload}")
        logger.info("x_ads.create_campaign -> %s", campaign_id)
        return str(campaign_id)

    async def upload_creative(self, tokens: TokenSet, creative: CreativeAsset) -> str:
        """Create a promoted tweet via POST /accounts/{account_id}/tweets.

        Returns the real tweet id from the API response (data.id).
        """
        account_id = await self._get_account_id(tokens)
        url = f"{_X_ADS_API_BASE}/accounts/{account_id}/tweets"

        text = self._extract_copy_text(creative) or creative.payload.get("text", "")
        body: dict[str, Any] = {
            "text": text[:X_TEXT_LIMIT],
        }
        # Optional nullcast (promoted-only) flag — default true for ad creatives.
        body["nullcast"] = bool(creative.payload.get("nullcast", True))

        try:
            async with httpx.AsyncClient(timeout=_X_ADS_TIMEOUT) as client:
                resp = await client.post(url, headers=self._auth_headers(tokens), json=body)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "x_ads.upload_creative HTTP %s: %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise
        except httpx.HTTPError as exc:
            logger.error("x_ads.upload_creative request error: %s", exc)
            raise

        data = payload.get("data") or {}
        tweet_id = data.get("id") or data.get("id_str")
        if not tweet_id:
            raise RuntimeError(f"x_ads: upload_creative response missing data.id: {payload}")
        logger.info("x_ads.upload_creative -> %s", tweet_id)
        return str(tweet_id)

    async def set_budget_bid(
        self, tokens: TokenSet, campaign_id: str, budget: float, bid: dict[str, Any]
    ) -> None:
        """Update daily budget via PUT /accounts/{account_id}/campaigns/{campaign_id}."""
        account_id = await self._get_account_id(tokens)
        url = f"{_X_ADS_API_BASE}/accounts/{account_id}/campaigns/{campaign_id}"

        body: dict[str, Any] = {
            "daily_budget_amount_local_micro": int(float(budget) * 1_000_000),
        }
        # Optional bid strategy fields.
        if bid:
            if "bid_amount_local_micro" in bid:
                body["bid_amount_local_micro"] = int(float(bid["bid_amount_local_micro"]))
            elif "bid" in bid:
                body["bid_amount_local_micro"] = int(float(bid["bid"]) * 1_000_000)

        try:
            async with httpx.AsyncClient(timeout=_X_ADS_TIMEOUT) as client:
                resp = await client.put(url, headers=self._auth_headers(tokens), json=body)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "x_ads.set_budget_bid HTTP %s: %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise
        except httpx.HTTPError as exc:
            logger.error("x_ads.set_budget_bid request error: %s", exc)
            raise

        logger.info(
            "x_ads.set_budget_bid campaign=%s budget=%s bid=%s",
            campaign_id,
            budget,
            bid,
        )

    async def pause(self, tokens: TokenSet, campaign_id: str) -> None:
        """Pause a campaign via PUT /accounts/{account_id}/campaigns/{campaign_id}."""
        account_id = await self._get_account_id(tokens)
        url = f"{_X_ADS_API_BASE}/accounts/{account_id}/campaigns/{campaign_id}"

        body: dict[str, Any] = {"paused": True}

        try:
            async with httpx.AsyncClient(timeout=_X_ADS_TIMEOUT) as client:
                resp = await client.put(url, headers=self._auth_headers(tokens), json=body)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "x_ads.pause HTTP %s: %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise
        except httpx.HTTPError as exc:
            logger.error("x_ads.pause request error: %s", exc)
            raise

        logger.info("x_ads.pause campaign=%s", campaign_id)

    async def stats(self, tokens: TokenSet, campaign_id: str, since: datetime) -> list[MetricEvent]:
        """Pull campaign stats via GET /stats/accounts/{account_id}.

        Returns a list of MetricEvent with real impressions, clicks, spend and
        conversions broken down by day.
        """
        account_id = await self._get_account_id(tokens)
        url = f"{_X_ADS_API_BASE}/stats/accounts/{account_id}"

        end_time = datetime.now(UTC)
        start_time = max(since, end_time - timedelta(days=30))

        params: dict[str, str] = {
            "entity": "CAMPAIGN",
            "entity_ids": campaign_id,
            "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_time": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "granularity": "DAY",
            "metric_groups": "ENGAGEMENT,BILLING",
            "placement": "ALL_ON_PLATFORM",
        }

        try:
            async with httpx.AsyncClient(timeout=_X_ADS_TIMEOUT) as client:
                resp = await client.get(url, headers=self._auth_headers(tokens), params=params)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "x_ads.stats HTTP %s: %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise
        except httpx.HTTPError as exc:
            logger.error("x_ads.stats request error: %s", exc)
            raise

        events: list[MetricEvent] = []
        data = payload.get("data") or {}
        # Twitter returns a time-series keyed by entity id, each with per-day arrays.
        series = data.get(campaign_id) or {}
        # The stats API returns arrays indexed by day for each metric.
        for canonical, field in _X_METRIC_FIELDS.items():
            values = series.get(field)
            if not values:
                continue
            for idx, raw_val in enumerate(values):
                if raw_val is None:
                    continue
                value = float(raw_val)
                # cost/billed_charge_local_micro is in local micro currency units.
                if canonical == "cost":
                    value = value / 1_000_000.0
                ts = start_time + timedelta(days=idx)
                events.append(
                    MetricEvent(
                        channel=self.network,
                        entity_type="campaign",
                        entity_id=campaign_id,
                        metric=canonical,
                        value=round(value, 4),
                        ts=ts,
                    )
                )
        logger.info(
            "x_ads.stats campaign=%s events=%s since=%s",
            campaign_id,
            len(events),
            since.isoformat(),
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
                ("text", X_TEXT_LIMIT),
                ("headline", X_HEADLINE_LIMIT),
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
