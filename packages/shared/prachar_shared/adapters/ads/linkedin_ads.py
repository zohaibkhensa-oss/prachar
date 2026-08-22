from __future__ import annotations

import logging
from datetime import UTC, datetime
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

_LINKEDIN_API_BASE = "https://api.linkedin.com/v2"
_LINKEDIN_TIMEOUT = 30.0

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

    # ----- LinkedIn Marketing API helpers -----
    @staticmethod
    def _auth_headers(tokens: TokenSet) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {tokens.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    async def _get_account_urn(self, tokens: TokenSet) -> str:
        """Resolve the sponsored account URN for the authenticated user.

        GET /v2/adAccounts?q=search returns the ad accounts the token can
        access; we pick the first usable account and return its URN.
        """
        headers = self._auth_headers(tokens)
        async with httpx.AsyncClient(timeout=_LINKEDIN_TIMEOUT) as client:
            resp = await client.get(
                f"{_LINKEDIN_API_BASE}/adAccounts",
                params={"q": "search", "start": 0, "count": 1},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
        elements = data.get("elements", [])
        if not elements:
            raise RuntimeError("linkedin_ads: no ad accounts available for token")
        account_id = elements[0]["id"]
        return f"urn:li:sponsoredAccount:{account_id}"

    # ----- campaign lifecycle -----
    async def create_campaign(self, tokens: TokenSet, campaign: dict[str, Any]) -> str:
        """POST /v2/adCampaignsV2 — create a campaign, return native id."""
        account_urn = campaign.get("account") or await self._get_account_urn(tokens)
        body: dict[str, Any] = {
            "account": account_urn,
            "name": campaign["name"],
            "status": campaign.get("status", "ACTIVE"),
            "objective": campaign.get("objective", "AWARENESS"),
            "type": campaign.get("type", "TEXT_AD"),
            "dailyBudget": {
                "currencyCode": campaign.get("currency", "USD"),
                "amount": str(campaign.get("daily_budget", campaign.get("dailyBudget", 50.0))),
            },
        }
        headers = self._auth_headers(tokens)
        try:
            async with httpx.AsyncClient(timeout=_LINKEDIN_TIMEOUT) as client:
                resp = await client.post(
                    f"{_LINKEDIN_API_BASE}/adCampaignsV2",
                    json=body,
                    headers=headers,
                )
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPError as exc:
            logger.error("linkedin_ads.create_campaign failed: %s", exc)
            raise
        campaign_id = str(payload["id"])
        logger.info("linkedin_ads.create_campaign -> %s", campaign_id)
        return campaign_id

    async def upload_creative(self, tokens: TokenSet, creative: CreativeAsset) -> str:
        """POST /v2/adCreativesV2 — create a creative with text/image/destination."""
        payload = creative.payload or {}
        text = payload.get("intro_text") or payload.get("text") or payload.get("primary_text", "")
        headline = payload.get("headline", "")
        destination_url = payload.get("destination_url") or payload.get("landing_url", "")
        image_url = payload.get("image_url") or payload.get("s3_url")

        body: dict[str, Any] = {
            "type": payload.get("creative_type", "TEXT_AD"),
            "status": payload.get("status", "ACTIVE"),
            "content": {"text": text},
            "reference": {"destinationUrl": destination_url},
        }
        if headline:
            body["content"]["headline"] = headline
        if image_url:
            body["content"]["media"] = [{"id": image_url, "type": "IMAGE"}]

        headers = self._auth_headers(tokens)
        try:
            async with httpx.AsyncClient(timeout=_LINKEDIN_TIMEOUT) as client:
                resp = await client.post(
                    f"{_LINKEDIN_API_BASE}/adCreativesV2",
                    json=body,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.error("linkedin_ads.upload_creative failed: %s", exc)
            raise
        creative_id = str(data["id"])
        logger.info("linkedin_ads.upload_creative -> %s", creative_id)
        return creative_id

    async def set_budget_bid(
        self, tokens: TokenSet, campaign_id: str, budget: float, bid: dict[str, Any]
    ) -> None:
        """PATCH /v2/adCampaignsV2/{id} — update dailyBudget and bidType."""
        body: dict[str, Any] = {
            "dailyBudget": {
                "currencyCode": bid.get("currency", "USD"),
                "amount": str(budget),
            },
        }
        if "bid_type" in bid:
            body["bidType"] = bid["bid_type"]
        if "bid_amount" in bid:
            body["bidAmount"] = {
                "currencyCode": bid.get("currency", "USD"),
                "amount": str(bid["bid_amount"]),
            }
        headers = self._auth_headers(tokens)
        headers["X-HTTP-Method-Override"] = "PATCH"
        try:
            async with httpx.AsyncClient(timeout=_LINKEDIN_TIMEOUT) as client:
                resp = await client.post(
                    f"{_LINKEDIN_API_BASE}/adCampaignsV2/{campaign_id}",
                    json=body,
                    headers=headers,
                )
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("linkedin_ads.set_budget_bid failed campaign=%s: %s", campaign_id, exc)
            raise
        logger.info(
            "linkedin_ads.set_budget_bid campaign=%s budget=%s bid=%s",
            campaign_id,
            budget,
            bid,
        )

    async def pause(self, tokens: TokenSet, campaign_id: str) -> None:
        """PATCH /v2/adCampaignsV2/{id} — set status=PAUSED."""
        headers = self._auth_headers(tokens)
        headers["X-HTTP-Method-Override"] = "PATCH"
        try:
            async with httpx.AsyncClient(timeout=_LINKEDIN_TIMEOUT) as client:
                resp = await client.post(
                    f"{_LINKEDIN_API_BASE}/adCampaignsV2/{campaign_id}",
                    json={"status": "PAUSED"},
                    headers=headers,
                )
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("linkedin_ads.pause failed campaign=%s: %s", campaign_id, exc)
            raise
        logger.info("linkedin_ads.pause campaign=%s", campaign_id)

    async def stats(self, tokens: TokenSet, campaign_id: str, since: datetime) -> list[MetricEvent]:
        """GET /v2/adAnalytics — pull real campaign metrics since `since`."""
        start = since.astimezone(UTC)
        end = datetime.now(UTC)
        date_range = {
            "start": {"month": start.month, "day": start.day, "year": start.year},
            "end": {"month": end.month, "day": end.day, "year": end.year},
        }
        params = {
            "q": "analytics",
            "pivot": "CAMPAIGN",
            "campaigns": f"urn:li:sponsoredCampaign:{campaign_id}",
            "dateRange": date_range,
            "fields": "impressions,clicks,costInUsd,conversions",
        }
        headers = self._auth_headers(tokens)
        events: list[MetricEvent] = []
        try:
            async with httpx.AsyncClient(timeout=_LINKEDIN_TIMEOUT) as client:
                resp = await client.get(
                    f"{_LINKEDIN_API_BASE}/adAnalytics",
                    params=params,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.error("linkedin_ads.stats failed campaign=%s: %s", campaign_id, exc)
            return events

        for element in data.get("elements", []):
            ts_str = element.get("date") or element.get("timeBucket")
            try:
                if isinstance(ts_str, dict):
                    ts = datetime(
                        ts_str.get("year", end.year),
                        ts_str.get("month", end.month),
                        ts_str.get("day", end.day),
                        tzinfo=UTC,
                    )
                elif isinstance(ts_str, str):
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                else:
                    ts = end
            except (ValueError, TypeError):
                ts = end
            for metric, key in (
                ("impressions", "impressions"),
                ("clicks", "clicks"),
                ("cost", "costInUsd"),
                ("conversions", "conversions"),
            ):
                if key in element:
                    events.append(
                        MetricEvent(
                            channel=self.network,
                            entity_type="campaign",
                            entity_id=campaign_id,
                            metric=metric,
                            value=float(element[key]),
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
