from __future__ import annotations

import logging
import os
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

_SNAP_HEADLINE_LIMIT = 34
_SNAP_DESCRIPTION_LIMIT = 250

# Snapchat Marketing API base (spec 06 networks table P2 — MENA/US youth).
_SNAP_API_BASE = "https://api.snapchat.com/v1"
_SNAP_TIMEOUT = 30.0


class SnapAdsError(RuntimeError):
    """Raised when a Snapchat Marketing API call fails."""


@register_ads
class SnapAdsAdapter(AdNetworkAdapter):
    """Snapchat Ads (Snap Marketing API) adapter (spec 06 networks table P2 — MENA/US youth)."""

    network = "snap_ads"

    # ----- helpers -----
    @staticmethod
    def _get_ad_account_id(tokens: TokenSet) -> str:
        """Resolve the Snap ad account id for the given tokens.

        Priority: explicit ``ad_account_id`` field on the token set's scopes
        metadata (encoded as ``snap_ad_account:<id>``) → ``SNAP_AD_ACCOUNT_ID``
        env var. Raises :class:`SnapAdsError` if none can be resolved.
        """
        for scope in tokens.scopes:
            if scope.startswith("snap_ad_account:"):
                return scope.split(":", 1)[1]
        env_id = os.environ.get("SNAP_AD_ACCOUNT_ID")
        if env_id:
            return env_id
        raise SnapAdsError(
            "cannot resolve Snap ad_account_id: set SNAP_AD_ACCOUNT_ID env var "
            "or include a 'snap_ad_account:<id>' scope in the TokenSet"
        )

    @staticmethod
    def _headers(tokens: TokenSet) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {tokens.access_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _raise_for_status(resp: httpx.Response, action: str) -> dict[str, Any]:
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body: Any = None
            try:
                body = exc.response.json()
            except Exception:
                body = exc.response.text
            logger.error("snap_ads.%s failed status=%s body=%s", action, exc.response.status_code, body)
            raise SnapAdsError(f"{action} failed: HTTP {exc.response.status_code}: {body}") from exc
        data = resp.json()
        # Snap API envelopes: {"request_status": "SUCCESS", "campaigns": [...]} etc.
        if isinstance(data, dict) and data.get("request_status") not in (None, "SUCCESS"):
            raise SnapAdsError(f"{action} failed: request_status={data.get('request_status')} body={data}")
        return data

    # ----- audience translation -----
    def translate_audience(self, spec: AudienceSpec) -> NativeTargeting:
        # geo -> Snap location targeting.
        locations: list[dict[str, Any]] = []
        for code in spec.geo:
            country = code.split("-", 1)[0]
            locations.append({"country_code": country, "sub_code": code})
        # age/gender -> Snap demographics.
        demographics: dict[str, Any] = {
            "min_age": spec.age[0],
            "max_age": spec.age[1],
            "gender": spec.gender.value,
        }
        # interests -> Snap interest categories.
        interests = translate_taxonomy_sync(spec.interests, "interests", "snap_ads")
        intents = translate_taxonomy_sync(spec.intents, "intents", "snap_ads")

        payload: dict[str, Any] = {
            "geo_locations": locations,
            "demographics": demographics,
            "interest_categories": interests,
            "intents": intents,
            "languages": list(spec.languages),
        }
        if spec.lookalike_seed:
            payload["lookalike_seed"] = spec.lookalike_seed
        return NativeTargeting(network=self.network, payload=payload)

    # ----- campaign lifecycle -----
    async def create_campaign(self, tokens: TokenSet, campaign: dict[str, Any]) -> str:
        """Create a campaign via POST /v1/campaigns; return the native campaign id."""
        ad_account_id = campaign.get("ad_account_id") or self._get_ad_account_id(tokens)
        body: dict[str, Any] = {
            "ad_account_id": ad_account_id,
            "name": campaign.get("name", "prachar-campaign"),
            "status": campaign.get("status", "ACTIVE"),
        }
        if "start_time" in campaign:
            body["start_time"] = campaign["start_time"]
        if "end_time" in campaign:
            body["end_time"] = campaign["end_time"]
        if "daily_budget_micro" in campaign:
            body["daily_budget_micro"] = campaign["daily_budget_micro"]
        elif "daily_budget" in campaign:
            # Convert dollars to micros (1M micros per dollar).
            body["daily_budget_micro"] = int(float(campaign["daily_budget"]) * 1_000_000)

        payload = {"campaigns": [body]}
        try:
            async with httpx.AsyncClient(timeout=_SNAP_TIMEOUT) as client:
                resp = await client.post(
                    f"{_SNAP_API_BASE}/campaigns",
                    headers=self._headers(tokens),
                    json=payload,
                )
        except httpx.RequestError as exc:
            logger.error("snap_ads.create_campaign request error: %s", exc)
            raise SnapAdsError(f"create_campaign request failed: {exc}") from exc

        data = self._raise_for_status(resp, "create_campaign")
        campaigns = data.get("campaigns") or []
        if not campaigns:
            raise SnapAdsError(f"create_campaign returned no campaigns: {data}")
        campaign_id = campaigns[0]["campaign"]["id"]
        logger.info("snap_ads.create_campaign -> %s", campaign_id)
        return campaign_id

    async def upload_creative(self, tokens: TokenSet, creative: CreativeAsset) -> str:
        """Create an ad with creative via POST /v1/ads; return the native ad id."""
        ad_account_id = self._get_ad_account_id(tokens)
        payload_dict = creative.payload or {}
        ad_spec: dict[str, Any] = {
            "ad_account_id": ad_account_id,
            "name": payload_dict.get("name", f"prachar-ad-{creative.variant_group}"),
            "status": payload_dict.get("status", "ACTIVE"),
            "type": "AD",
        }
        if "top_snap_media_id" in payload_dict:
            ad_spec["top_snap_media_id"] = payload_dict["top_snap_media_id"]
        if "ad_headline" in payload_dict:
            ad_spec["ad_headline"] = payload_dict["ad_headline"]
        if "web_view_properties" in payload_dict:
            ad_spec["web_view_properties"] = payload_dict["web_view_properties"]

        body = {"ads": [ad_spec]}
        try:
            async with httpx.AsyncClient(timeout=_SNAP_TIMEOUT) as client:
                resp = await client.post(
                    f"{_SNAP_API_BASE}/ads",
                    headers=self._headers(tokens),
                    json=body,
                )
        except httpx.RequestError as exc:
            logger.error("snap_ads.upload_creative request error: %s", exc)
            raise SnapAdsError(f"upload_creative request failed: {exc}") from exc

        data = self._raise_for_status(resp, "upload_creative")
        ads = data.get("ads") or []
        if not ads:
            raise SnapAdsError(f"upload_creative returned no ads: {data}")
        ad_id = ads[0]["ad"]["id"]
        logger.info("snap_ads.upload_creative -> %s", ad_id)
        return ad_id

    async def set_budget_bid(
        self, tokens: TokenSet, campaign_id: str, budget: float, bid: dict[str, Any]
    ) -> None:
        """Update daily_budget_micro and bid_strategy via PUT /v1/campaigns/{id}."""
        ad_account_id = self._get_ad_account_id(tokens)
        campaign_spec: dict[str, Any] = {
            "id": campaign_id,
            "ad_account_id": ad_account_id,
            "daily_budget_micro": int(float(budget) * 1_000_000),
        }
        if "bid_strategy" in bid:
            campaign_spec["bid_strategy"] = bid["bid_strategy"]
        if "bid_micro" in bid:
            campaign_spec["bid_micro"] = bid["bid_micro"]
        if "objective" in bid:
            campaign_spec["objective"] = bid["objective"]

        body = {"campaigns": [campaign_spec]}
        try:
            async with httpx.AsyncClient(timeout=_SNAP_TIMEOUT) as client:
                resp = await client.put(
                    f"{_SNAP_API_BASE}/campaigns/{campaign_id}",
                    headers=self._headers(tokens),
                    json=body,
                )
        except httpx.RequestError as exc:
            logger.error("snap_ads.set_budget_bid request error: %s", exc)
            raise SnapAdsError(f"set_budget_bid request failed: {exc}") from exc

        self._raise_for_status(resp, "set_budget_bid")
        logger.info(
            "snap_ads.set_budget_bid campaign=%s budget=%s bid=%s",
            campaign_id, budget, bid,
        )

    async def pause(self, tokens: TokenSet, campaign_id: str) -> None:
        """Pause a campaign via PUT /v1/campaigns/{id} with status=PAUSED."""
        ad_account_id = self._get_ad_account_id(tokens)
        body = {
            "campaigns": [
                {
                    "id": campaign_id,
                    "ad_account_id": ad_account_id,
                    "status": "PAUSED",
                }
            ]
        }
        try:
            async with httpx.AsyncClient(timeout=_SNAP_TIMEOUT) as client:
                resp = await client.put(
                    f"{_SNAP_API_BASE}/campaigns/{campaign_id}",
                    headers=self._headers(tokens),
                    json=body,
                )
        except httpx.RequestError as exc:
            logger.error("snap_ads.pause request error: %s", exc)
            raise SnapAdsError(f"pause request failed: {exc}") from exc

        self._raise_for_status(resp, "pause")
        logger.info("snap_ads.pause campaign=%s", campaign_id)

    async def stats(self, tokens: TokenSet, campaign_id: str, since: datetime) -> list[MetricEvent]:
        """Pull canonical MetricEvents via POST /v1/campaigns/{id}/stats."""
        end_time = datetime.now(UTC)
        start_time = max(since, end_time - timedelta(days=30))
        body = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "granularity": "DAY",
            "fields": ["impressions", "clicks", "spend", "swipes", "conversions"],
            "stats_type": "CAMPAIGN",
        }
        try:
            async with httpx.AsyncClient(timeout=_SNAP_TIMEOUT) as client:
                resp = await client.post(
                    f"{_SNAP_API_BASE}/campaigns/{campaign_id}/stats",
                    headers=self._headers(tokens),
                    json=body,
                )
        except httpx.RequestError as exc:
            logger.error("snap_ads.stats request error: %s", exc)
            raise SnapAdsError(f"stats request failed: {exc}") from exc

        data = self._raise_for_status(resp, "stats")
        timeseries_stats = (
            data.get("timeseries_stats")
            or data.get("total_stats")
            or []
        )
        events: list[MetricEvent] = []
        # timeseries_stats is a list of per-day entries each with a "start_time" and "stats".
        for entry in timeseries_stats:
            ts_raw = entry.get("start_time") or entry.get("date")
            if isinstance(ts_raw, str):
                try:
                    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                except ValueError:
                    ts = datetime.now(UTC)
            elif isinstance(ts_raw, datetime):
                ts = ts_raw if ts_raw.tzinfo else ts_raw.replace(tzinfo=UTC)
            else:
                ts = datetime.now(UTC)
            stats = entry.get("stats") or entry
            for metric in ("impressions", "clicks", "spend", "swipes", "conversions"):
                if metric in stats:
                    try:
                        value = float(stats[metric])
                    except (TypeError, ValueError):
                        continue
                    events.append(
                        MetricEvent(
                            channel=self.network,
                            entity_type="campaign",
                            entity_id=campaign_id,
                            metric=metric,
                            value=value,
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
            for key, limit in (("headline", _SNAP_HEADLINE_LIMIT), ("description", _SNAP_DESCRIPTION_LIMIT)):
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
