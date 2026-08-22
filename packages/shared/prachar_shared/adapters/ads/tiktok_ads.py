from __future__ import annotations

import json
import logging
import os
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

# TikTok Marketing API base (spec 06 networks table P1).
_TT_API_BASE = "https://business-api.tiktok.com/open_api/v1.3"
_TT_TIMEOUT = 30.0

# TikTok Ads copy char limits (spec 06 §Creatives).
TT_PRIMARY_TEXT_LIMIT = 100
TT_HEADLINE_LIMIT = 100

# ISO-3166-1 -> TikTok region code (ISO-2 used by TikTok Business Center).
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


class TikTokAdsError(RuntimeError):
    """Raised when a TikTok Marketing API call fails."""


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

    # ----- helpers -----
    @staticmethod
    def _get_advertiser_id(tokens: TokenSet) -> str:
        """Resolve the TikTok advertiser_id for this TokenSet.

        TokenSet is a sealed contract with no advertiser_id field, so the
        advertiser id is sourced from the ``TIKTOK_ADVERTISER_ID`` env var
        (per-channel OAuth creds block in .env). Callers may also override by
        passing ``advertiser_id`` in the campaign/creative dict where relevant.
        """
        adv_id = os.environ.get("TIKTOK_ADVERTISER_ID", "").strip()
        if not adv_id:
            raise TikTokAdsError(
                "TIKTOK_ADVERTISER_ID env var is required for TikTok Ads API calls"
            )
        return adv_id

    @staticmethod
    def _headers(tokens: TokenSet) -> dict[str, str]:
        return {
            "Access-Token": tokens.access_token,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _check_response(resp: httpx.Response, action: str) -> dict[str, Any]:
        """Validate a TikTok API response and return its data payload."""
        try:
            body = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise TikTokAdsError(
                f"tiktok_ads.{action}: non-JSON response ({resp.status_code}): {exc}"
            ) from exc
        code = body.get("code")
        if code != 0:
            raise TikTokAdsError(
                f"tiktok_ads.{action}: API error code={code} message={body.get('message')!r}"
            )
        return body.get("data") or {}

    # ----- campaign lifecycle -----
    async def create_campaign(self, tokens: TokenSet, campaign: dict[str, Any]) -> str:
        """Create a campaign via TikTok Marketing API; return native campaign id."""
        advertiser_id = campaign.get("advertiser_id") or self._get_advertiser_id(tokens)
        body = {
            "advertiser_id": advertiser_id,
            "campaign_name": campaign.get("campaign_name") or campaign.get("name", "prachar-campaign"),
            "objective_type": campaign.get("objective_type", "CONVERSIONS"),
            "budget_mode": campaign.get("budget_mode", "BUDGET_MODE_TOTAL"),
            "budget": int(campaign.get("budget", 0) * 1000000),  # cents -> micros
        }
        # Optional fields.
        if "budget_optimize_on" in campaign:
            body["budget_optimize_on"] = campaign["budget_optimize_on"]
        if "campaign_app_type" in campaign:
            body["campaign_app_type"] = campaign["campaign_app_type"]

        try:
            async with httpx.AsyncClient(timeout=_TT_TIMEOUT) as client:
                resp = await client.post(
                    f"{_TT_API_BASE}/campaign/create/",
                    headers=self._headers(tokens),
                    json=body,
                )
            data = self._check_response(resp, "create_campaign")
        except httpx.HTTPError as exc:
            raise TikTokAdsError(f"tiktok_ads.create_campaign: HTTP error: {exc}") from exc
        campaign_id = str(data.get("campaign_id", ""))
        if not campaign_id:
            raise TikTokAdsError(f"tiktok_ads.create_campaign: no campaign_id in response data={data!r}")
        logger.info("tiktok_ads.create_campaign -> %s", campaign_id)
        return campaign_id

    async def upload_creative(self, tokens: TokenSet, creative: CreativeAsset) -> str:
        """Upload a video/image creative to TikTok; return native file_id."""
        advertiser_id = creative.payload.get("advertiser_id") or self._get_advertiser_id(tokens)
        payload = creative.payload or {}
        # Prefer an explicit video_url / image_url; fall back to s3_key-derived URL.
        video_url = payload.get("video_url") or payload.get("image_url")
        if not video_url and creative.s3_key:
            video_url = creative.s3_key  # assume publicly reachable URL stored as s3_key
        if not video_url:
            raise TikTokAdsError("tiktok_ads.upload_creative: creative has no video_url/image_url/s3_key")

        body: dict[str, Any] = {
            "advertiser_id": advertiser_id,
            "upload_type": "UPLOAD_BY_URL",
            "video_url": video_url,
            "file_name": payload.get("file_name", creative.s3_key or "creative"),
        }
        if creative.type == CreativeType.image:
            # Image upload uses a different endpoint.
            try:
                async with httpx.AsyncClient(timeout=_TT_TIMEOUT) as client:
                    resp = await client.post(
                        f"{_TT_API_BASE}/file/image/ad/upload/",
                        headers=self._headers(tokens),
                        json=body,
                    )
                data = self._check_response(resp, "upload_creative")
            except httpx.HTTPError as exc:
                raise TikTokAdsError(f"tiktok_ads.upload_creative: HTTP error: {exc}") from exc
        else:
            try:
                async with httpx.AsyncClient(timeout=_TT_TIMEOUT) as client:
                    resp = await client.post(
                        f"{_TT_API_BASE}/file/video/ad/upload/",
                        headers=self._headers(tokens),
                        json=body,
                    )
                data = self._check_response(resp, "upload_creative")
            except httpx.HTTPError as exc:
                raise TikTokAdsError(f"tiktok_ads.upload_creative: HTTP error: {exc}") from exc

        file_id = str(data.get("file_id") or data.get("video_id") or data.get("image_id") or "")
        if not file_id:
            raise TikTokAdsError(f"tiktok_ads.upload_creative: no file_id in response data={data!r}")
        logger.info("tiktok_ads.upload_creative -> %s", file_id)
        return file_id

    async def set_budget_bid(
        self, tokens: TokenSet, campaign_id: str, budget: float, bid: dict[str, Any]
    ) -> None:
        """Update campaign budget and bid_type via TikTok Marketing API."""
        advertiser_id = self._get_advertiser_id(tokens)
        body: dict[str, Any] = {
            "advertiser_id": advertiser_id,
            "campaign_id": campaign_id,
            "budget": int(budget * 1000000),  # currency units -> micros
        }
        if bid.get("type"):
            body["bid_type"] = bid["type"]
        if bid.get("value"):
            body["bid"] = int(float(bid["value"]) * 1000000)

        try:
            async with httpx.AsyncClient(timeout=_TT_TIMEOUT) as client:
                resp = await client.post(
                    f"{_TT_API_BASE}/campaign/update/",
                    headers=self._headers(tokens),
                    json=body,
                )
            self._check_response(resp, "set_budget_bid")
        except httpx.HTTPError as exc:
            raise TikTokAdsError(f"tiktok_ads.set_budget_bid: HTTP error: {exc}") from exc
        logger.info(
            "tiktok_ads.set_budget_bid campaign=%s budget=%s bid=%s",
            campaign_id,
            budget,
            bid,
        )

    async def pause(self, tokens: TokenSet, campaign_id: str) -> None:
        """Pause a campaign by setting status=CAMPAIGN_STATUS_DISABLED."""
        advertiser_id = self._get_advertiser_id(tokens)
        body = {
            "advertiser_id": advertiser_id,
            "campaign_id": campaign_id,
            "status": "CAMPAIGN_STATUS_DISABLED",
        }
        try:
            async with httpx.AsyncClient(timeout=_TT_TIMEOUT) as client:
                resp = await client.post(
                    f"{_TT_API_BASE}/campaign/update/",
                    headers=self._headers(tokens),
                    json=body,
                )
            self._check_response(resp, "pause")
        except httpx.HTTPError as exc:
            raise TikTokAdsError(f"tiktok_ads.pause: HTTP error: {exc}") from exc
        logger.info("tiktok_ads.pause campaign=%s", campaign_id)

    async def stats(self, tokens: TokenSet, campaign_id: str, since: datetime) -> list[MetricEvent]:
        """Pull campaign-level report metrics from TikTok and map to MetricEvent."""
        advertiser_id = self._get_advertiser_id(tokens)
        end = datetime.now(UTC).date()
        start = max(since.astimezone(UTC).date(), end - timedelta(days=30))
        if start > end:
            start = end

        params = {
            "advertiser_id": advertiser_id,
            "report_type": "BASIC",
            "data_level": "AUCTION_CAMPAIGN",
            "dimensions": json.dumps(["campaign_id"]),
            "metrics": json.dumps(["impressions", "clicks", "cost", "conversion"]),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "page": 1,
            "page_size": 100,
        }
        try:
            async with httpx.AsyncClient(timeout=_TT_TIMEOUT) as client:
                resp = await client.get(
                    f"{_TT_API_BASE}/report/integrated/get/",
                    headers=self._headers(tokens),
                    params=params,
                )
            data = self._check_response(resp, "stats")
        except httpx.HTTPError as exc:
            raise TikTokAdsError(f"tiktok_ads.stats: HTTP error: {exc}") from exc

        events: list[MetricEvent] = []
        rows = data.get("list") or []
        for row in rows:
            ts_raw = row.get("stat_time") or row.get("date")
            try:
                ts = datetime.fromisoformat(str(ts_raw)).astimezone(UTC)
            except (TypeError, ValueError):
                ts = datetime.now(UTC)
            metrics = row.get("metrics") or {}
            for metric, value in (
                ("impressions", metrics.get("impressions")),
                ("clicks", metrics.get("clicks")),
                ("cost", metrics.get("cost")),
                ("conversions", metrics.get("conversion")),
            ):
                if value is None:
                    continue
                try:
                    fval = float(value)
                except (TypeError, ValueError):
                    continue
                events.append(
                    MetricEvent(
                        channel=self.network,
                        entity_type="campaign",
                        entity_id=str(row.get("campaign_id", campaign_id)),
                        metric=metric,
                        value=round(fval, 4),
                        ts=ts,
                    )
                )
        logger.info("tiktok_ads.stats campaign=%s events=%d", campaign_id, len(events))
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
