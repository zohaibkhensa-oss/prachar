from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
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

# Pinterest Ads API v5 base (spec 06 networks table P2, US/EU commerce).
_PIN_API_BASE = "https://api.pinterest.com/v5"
_PIN_TIMEOUT = 30.0

# Pinterest Ads copy char limits (spec 06 §Creatives).
PIN_TITLE_LIMIT = 100
PIN_DESCRIPTION_LIMIT = 500

# Stub ISO-3166-1 -> Pinterest country code.
_PIN_GEO_CODES: dict[str, str] = {
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


class PinterestAdsError(RuntimeError):
    """Raised when a Pinterest Ads API v5 call fails."""


def _pin_geo(code: str) -> str:
    country = code.split("-", 1)[0].upper()
    return _PIN_GEO_CODES.get(country, country)


@register_ads
class PinterestAdsAdapter(AdNetworkAdapter):
    """Pinterest Ads API adapter (spec 06 networks table P2, US/EU commerce)."""

    network = "pinterest_ads"

    # ----- audience translation -----
    def translate_audience(self, spec: AudienceSpec) -> NativeTargeting:
        locations = [{"country": _pin_geo(c)} for c in spec.geo]
        # interests → Pinterest interest categories (LLM-assisted, cached).
        interest_categories = translate_taxonomy_sync(
            spec.interests, "interests", "pinterest_ads"
        )
        # intents → Pinterest actalike / act-audience targeting.
        act_audiences = translate_taxonomy_sync(
            spec.intents, "intents", "pinterest_ads"
        )

        payload: dict[str, Any] = {
            "geo": locations,
            "interest_categories": interest_categories,
            "act_audiences": act_audiences,
            "age_range": {"min": spec.age[0], "max": spec.age[1]},
            "gender": spec.gender.value,
            "languages": list(spec.languages),
        }
        if spec.lookalike_seed:
            payload["actalike"] = {
                "seed_audience_id": spec.lookalike_seed,
                "country": _pin_geo(spec.geo[0]) if spec.geo else "US",
            }
        return NativeTargeting(network=self.network, payload=payload)

    # ----- helpers -----
    @staticmethod
    def _auth_headers(tokens: TokenSet) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {tokens.access_token}",
            "Content-Type": "application/json",
        }

    async def _get_ad_account_id(self, tokens: TokenSet) -> str:
        """Resolve the Pinterest ad account id for the authorised user.

        TokenSet carries no ad_account_id, so we list the user's ad accounts via
        ``GET /v5/user_account/ad_accounts`` and pick the first one.
        """
        headers = self._auth_headers(tokens)
        url = f"{_PIN_API_BASE}/user_account/ad_accounts"
        try:
            async with httpx.AsyncClient(timeout=_PIN_TIMEOUT) as client:
                resp = await client.get(url, headers=headers, params={"page_size": 1})
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.error("pinterest_ads._get_ad_account_id failed: %s", exc)
            raise PinterestAdsError(f"failed to list ad accounts: {exc}") from exc
        items = data.get("items") or []
        if not items:
            raise PinterestAdsError("no Pinterest ad accounts available for user")
        ad_account_id = items[0].get("id")
        if not ad_account_id:
            raise PinterestAdsError("Pinterest ad account response missing id")
        return str(ad_account_id)

    # ----- campaign lifecycle -----
    async def create_campaign(self, tokens: TokenSet, campaign: dict[str, Any]) -> str:
        """Create a campaign via POST /v5/ad_accounts/{id}/campaigns; return id."""
        ad_account_id = await self._get_ad_account_id(tokens)
        headers = self._auth_headers(tokens)
        url = f"{_PIN_API_BASE}/ad_accounts/{ad_account_id}/campaigns"
        body: dict[str, Any] = {
            "name": campaign.get("name", "prachar-campaign"),
            "status": campaign.get("status", "ACTIVE"),
            "objective_type": campaign.get("objective_type", "AWARENESS"),
        }
        daily_budget = campaign.get("daily_budget")
        if daily_budget is not None:
            body["daily_budget"] = int(float(daily_budget) * 10000)  # micro-currency
        lifetime_cap = campaign.get("lifetime_spend_cap")
        if lifetime_cap is not None:
            body["lifetime_spend_cap"] = int(float(lifetime_cap) * 10000)
        try:
            async with httpx.AsyncClient(timeout=_PIN_TIMEOUT) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.error("pinterest_ads.create_campaign failed: %s", exc)
            raise PinterestAdsError(f"create_campaign failed: {exc}") from exc
        campaign_id = data.get("id")
        if not campaign_id:
            raise PinterestAdsError("create_campaign response missing id")
        logger.info("pinterest_ads.create_campaign -> %s", campaign_id)
        return str(campaign_id)

    async def upload_creative(self, tokens: TokenSet, creative: CreativeAsset) -> str:
        """Create a pin ad via POST /v5/ad_accounts/{id}/ads; return ad id."""
        ad_account_id = await self._get_ad_account_id(tokens)
        headers = self._auth_headers(tokens)
        url = f"{_PIN_API_BASE}/ad_accounts/{ad_account_id}/ads"
        payload = creative.payload or {}
        pin_data: dict[str, Any] = {
            "title": payload.get("title", ""),
            "description": payload.get("description", ""),
            "link": payload.get("link", ""),
            "alt_text": payload.get("alt_text", ""),
        }
        if creative.s3_key:
            pin_data["media_source"] = {
                "source_type": "image_url",
                "url": payload.get("image_url", ""),
            }
        body: dict[str, Any] = {
            "ad_group_id": payload.get("ad_group_id", ""),
            "pin_id": payload.get("pin_id", ""),
            "creative": pin_data,
            "status": payload.get("status", "ACTIVE"),
        }
        try:
            async with httpx.AsyncClient(timeout=_PIN_TIMEOUT) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.error("pinterest_ads.upload_creative failed: %s", exc)
            raise PinterestAdsError(f"upload_creative failed: {exc}") from exc
        ad_id = data.get("id")
        if not ad_id:
            raise PinterestAdsError("upload_creative response missing id")
        logger.info("pinterest_ads.upload_creative -> %s", ad_id)
        return str(ad_id)

    async def set_budget_bid(
        self, tokens: TokenSet, campaign_id: str, budget: float, bid: dict[str, Any]
    ) -> None:
        """Update daily budget via PATCH /v5/ad_accounts/{id}/campaigns."""
        ad_account_id = await self._get_ad_account_id(tokens)
        headers = self._auth_headers(tokens)
        url = f"{_PIN_API_BASE}/ad_accounts/{ad_account_id}/campaigns"
        body: dict[str, Any] = {
            "id": campaign_id,
            "daily_budget": int(float(budget) * 10000),  # micro-currency
        }
        try:
            async with httpx.AsyncClient(timeout=_PIN_TIMEOUT) as client:
                resp = await client.patch(url, headers=headers, json=body)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("pinterest_ads.set_budget_bid failed: %s", exc)
            raise PinterestAdsError(f"set_budget_bid failed: {exc}") from exc
        logger.info(
            "pinterest_ads.set_budget_bid campaign=%s budget=%s bid=%s",
            campaign_id,
            budget,
            bid,
        )

    async def pause(self, tokens: TokenSet, campaign_id: str) -> None:
        """Pause a campaign via PATCH /v5/ad_accounts/{id}/campaigns."""
        ad_account_id = await self._get_ad_account_id(tokens)
        headers = self._auth_headers(tokens)
        url = f"{_PIN_API_BASE}/ad_accounts/{ad_account_id}/campaigns"
        body: dict[str, Any] = {
            "id": campaign_id,
            "entity_status": "PAUSED",
        }
        try:
            async with httpx.AsyncClient(timeout=_PIN_TIMEOUT) as client:
                resp = await client.patch(url, headers=headers, json=body)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("pinterest_ads.pause failed: %s", exc)
            raise PinterestAdsError(f"pause failed: {exc}") from exc
        logger.info("pinterest_ads.pause campaign=%s", campaign_id)

    async def stats(self, tokens: TokenSet, campaign_id: str, since: datetime) -> list[MetricEvent]:
        """Pull analytics via GET /v5/ad_accounts/{id}/analytics; return MetricEvents."""
        ad_account_id = await self._get_ad_account_id(tokens)
        headers = self._auth_headers(tokens)
        url = f"{_PIN_API_BASE}/ad_accounts/{ad_account_id}/analytics"
        end = datetime.now(UTC).date()
        start = max(since.date(), end - timedelta(days=90))
        params = {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "campaign_ids": campaign_id,
            "columns": "IMPRESSION_1,CLICK_1,SPEND_IN_DOLLAR,TOTAL_CHECKOUTS",
            "granularity": "DAY",
        }
        try:
            async with httpx.AsyncClient(timeout=_PIN_TIMEOUT) as client:
                resp = await client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.error("pinterest_ads.stats failed: %s", exc)
            raise PinterestAdsError(f"stats failed: {exc}") from exc
        events: list[MetricEvent] = []
        rows = data if isinstance(data, list) else data.get("items", [])
        for row in rows:
            ts_str = row.get("date") or row.get("DATE")
            try:
                ts = datetime.fromisoformat(ts_str).replace(tzinfo=UTC) if ts_str else datetime.now(UTC)
            except (TypeError, ValueError):
                ts = datetime.now(UTC)
            for src_col, metric in (
                ("IMPRESSION_1", "impressions"),
                ("CLICK_1", "clicks"),
                ("SPEND_IN_DOLLAR", "cost"),
                ("TOTAL_CHECKOUTS", "conversions"),
            ):
                raw_val = row.get(src_col)
                if raw_val is None:
                    continue
                try:
                    value = float(raw_val)
                except (TypeError, ValueError):
                    continue
                events.append(
                    MetricEvent(
                        channel=self.network,
                        entity_type="campaign",
                        entity_id=campaign_id,
                        metric=metric,
                        value=round(value, 4),
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
                ("title", PIN_TITLE_LIMIT),
                ("description", PIN_DESCRIPTION_LIMIT),
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
        for key in ("text", "title", "headline", "primary_text", "description"):
            v = payload.get(key)
            if isinstance(v, str):
                parts.append(v)
        return " ".join(parts)
