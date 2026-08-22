from __future__ import annotations

import csv
import io
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

# Microsoft (Bing) Ads copy limits.
_MS_HEADLINE_LIMIT = 30
_MS_DESCRIPTION_LIMIT = 90

# Microsoft Advertising API base (spec 06 networks table P1).
_MS_API_BASE = "https://api.ads.microsoft.com/v13"
_MS_TIMEOUT = 30.0


class MicrosoftAdsError(RuntimeError):
    """Raised when a Microsoft Advertising API call fails."""


def _get_developer_token() -> str:
    """Resolve the Microsoft Ads developer token from the environment."""
    token = os.environ.get("MS_ADS_DEVELOPER_TOKEN", "")
    if not token:
        raise MicrosoftAdsError(
            "MS_ADS_DEVELOPER_TOKEN env var is required for Microsoft Advertising API calls"
        )
    return token


def _get_customer_id(tokens: TokenSet) -> str:
    """Resolve the Microsoft Ads customer id.

    The customer id is not part of the OAuth ``TokenSet`` (which is strictly
    scoped to access/refresh tokens), so it is sourced from the environment
    (``MS_ADS_CUSTOMER_ID``) or an explicit override.
    """
    customer_id = os.environ.get("MS_ADS_CUSTOMER_ID", "")
    if not customer_id:
        raise MicrosoftAdsError(
            "MS_ADS_CUSTOMER_ID env var is required for Microsoft Advertising API calls"
        )
    return customer_id


def _get_account_id(tokens: TokenSet) -> str:
    """Resolve the Microsoft Ads customer account id."""
    account_id = os.environ.get("MS_ADS_ACCOUNT_ID", "")
    if not account_id:
        raise MicrosoftAdsError(
            "MS_ADS_ACCOUNT_ID env var is required for Microsoft Advertising API calls"
        )
    return account_id


def _headers(tokens: TokenSet) -> dict[str, str]:
    """Build the common auth headers for Microsoft Advertising API requests."""
    return {
        "Authorization": f"Bearer {tokens.access_token}",
        "DeveloperToken": _get_developer_token(),
        "CustomerAccountId": _get_account_id(tokens),
        "CustomerId": _get_customer_id(tokens),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@register_ads
class MicrosoftAdsAdapter(AdNetworkAdapter):
    """Microsoft (Bing) Ads adapter (spec 06 networks table P1)."""

    network = "microsoft_ads"

    # ----- audience translation -----
    def translate_audience(self, spec: AudienceSpec) -> NativeTargeting:
        # geo -> Microsoft location targeting (Bing Ads location intent).
        locations: list[dict[str, Any]] = []
        for code in spec.geo:
            country = code.split("-", 1)[0]
            locations.append({"country": country, "sub_code": code, "location_type": "country"})
        # interests -> Microsoft audiences (In-market audiences).
        audiences = translate_taxonomy_sync(spec.interests, "interests", "microsoft_ads")
        keywords = translate_taxonomy_sync(spec.intents, "intents", "microsoft_ads")

        payload: dict[str, Any] = {
            "locations": locations,
            "in_market_audiences": audiences,
            "keywords": keywords,
            "languages": list(spec.languages),
            "age_range": {"min": spec.age[0], "max": spec.age[1]},
            "gender": spec.gender.value,
        }
        if spec.lookalike_seed:
            payload["customer_match_list_id"] = spec.lookalike_seed
        return NativeTargeting(network=self.network, payload=payload)

    # ----- campaign lifecycle -----
    async def create_campaign(self, tokens: TokenSet, campaign: dict[str, Any]) -> str:
        """Create a campaign via the Microsoft Advertising Campaign Management API.

        POST {api_base}/campaigns with a Campaign body containing Name, Budget,
        BudgetType and Status. Returns the native campaign id from the response.
        """
        name = campaign.get("name") or campaign.get("Name") or "Prachar Campaign"
        budget = float(campaign.get("budget", campaign.get("Budget", 10.0)))
        budget_type = campaign.get("budget_type", campaign.get("BudgetType", "DailyBudgetStandard"))
        status = campaign.get("status", campaign.get("Status", "Active"))
        body: dict[str, Any] = {
            "Campaigns": [
                {
                    "Name": name,
                    "DailyBudget": budget,
                    "BudgetType": budget_type,
                    "Status": status,
                }
            ],
        }
        # Carry through any native targeting/keywords supplied by the caller.
        if "targeting" in campaign:
            body["Campaigns"][0]["Targeting"] = campaign["targeting"]
        url = f"{_MS_API_BASE}/campaigns"
        try:
            async with httpx.AsyncClient(timeout=_MS_TIMEOUT) as client:
                resp = await client.post(url, headers=_headers(tokens), json=body)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "microsoft_ads.create_campaign HTTP %s: %s",
                exc.response.status_code if exc.response else "?",
                exc.response.text if exc.response else str(exc),
            )
            raise MicrosoftAdsError(f"create_campaign failed: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.error("microsoft_ads.create_campaign transport error: %s", exc)
            raise MicrosoftAdsError(f"create_campaign transport error: {exc}") from exc

        campaigns = data.get("Campaigns") or data.get("campaigns") or []
        if not campaigns:
            # Some responses nest the created entity under "value".
            campaigns = data.get("value", [])
        if not campaigns:
            raise MicrosoftAdsError(f"create_campaign returned no campaign id: {data!r}")
        campaign_id = str(campaigns[0].get("Id") or campaigns[0].get("id"))
        logger.info("microsoft_ads.create_campaign -> %s", campaign_id)
        return campaign_id

    async def upload_creative(self, tokens: TokenSet, creative: CreativeAsset) -> str:
        """Upload a text ad via the Microsoft Advertising API.

        POST {api_base}/ads with a TextAd payload (FinalUrls, Headline, Text).
        Returns the native ad id from the response.
        """
        payload = creative.payload or {}
        headline = payload.get("headline") or payload.get("Headline") or ""
        text = payload.get("text") or payload.get("description") or payload.get("Text") or ""
        final_urls = payload.get("final_urls") or payload.get("FinalUrls") or []
        if isinstance(final_urls, str):
            final_urls = [final_urls]
        if not final_urls:
            final_urls = ["https://example.com"]
        body: dict[str, Any] = {
            "Ads": [
                {
                    "Type": "Text",
                    "Headline": headline[:_MS_HEADLINE_LIMIT],
                    "Text": text[:_MS_DESCRIPTION_LIMIT],
                    "FinalUrls": final_urls,
                }
            ],
        }
        url = f"{_MS_API_BASE}/ads"
        try:
            async with httpx.AsyncClient(timeout=_MS_TIMEOUT) as client:
                resp = await client.post(url, headers=_headers(tokens), json=body)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "microsoft_ads.upload_creative HTTP %s: %s",
                exc.response.status_code if exc.response else "?",
                exc.response.text if exc.response else str(exc),
            )
            raise MicrosoftAdsError(f"upload_creative failed: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.error("microsoft_ads.upload_creative transport error: %s", exc)
            raise MicrosoftAdsError(f"upload_creative transport error: {exc}") from exc

        ads = data.get("Ads") or data.get("ads") or data.get("value") or []
        if not ads:
            raise MicrosoftAdsError(f"upload_creative returned no ad id: {data!r}")
        ad_id = str(ads[0].get("Id") or ads[0].get("id"))
        logger.info("microsoft_ads.upload_creative -> %s", ad_id)
        return ad_id

    async def set_budget_bid(
        self, tokens: TokenSet, campaign_id: str, budget: float, bid: dict[str, Any]
    ) -> None:
        """Update the daily budget and bidding scheme for a campaign.

        POST {api_base}/campaigns with an update payload carrying DailyBudget
        and BiddingScheme. Idempotent by campaign id + action.
        """
        bidding_scheme = bid.get("scheme") or bid.get("BiddingScheme") or "ManualCpc"
        bid_amount = bid.get("amount") or bid.get("Amount")
        body: dict[str, Any] = {
            "Campaigns": [
                {
                    "Id": campaign_id,
                    "DailyBudget": float(budget),
                    "BiddingScheme": {
                        "Type": bidding_scheme,
                        **({"MaxCpc": {"Amount": float(bid_amount)}} if bid_amount is not None else {}),
                    },
                }
            ],
        }
        url = f"{_MS_API_BASE}/campaigns"
        try:
            async with httpx.AsyncClient(timeout=_MS_TIMEOUT) as client:
                resp = await client.post(url, headers=_headers(tokens), json=body)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "microsoft_ads.set_budget_bid HTTP %s: %s",
                exc.response.status_code if exc.response else "?",
                exc.response.text if exc.response else str(exc),
            )
            raise MicrosoftAdsError(f"set_budget_bid failed: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.error("microsoft_ads.set_budget_bid transport error: %s", exc)
            raise MicrosoftAdsError(f"set_budget_bid transport error: {exc}") from exc
        logger.info(
            "microsoft_ads.set_budget_bid campaign=%s budget=%s bid=%s",
            campaign_id, budget, bid,
        )

    async def pause(self, tokens: TokenSet, campaign_id: str) -> None:
        """Pause a campaign by setting Status=Paused.

        POST {api_base}/campaigns with an update payload carrying Id and Status.
        """
        body: dict[str, Any] = {
            "Campaigns": [
                {
                    "Id": campaign_id,
                    "Status": "Paused",
                }
            ],
        }
        url = f"{_MS_API_BASE}/campaigns"
        try:
            async with httpx.AsyncClient(timeout=_MS_TIMEOUT) as client:
                resp = await client.post(url, headers=_headers(tokens), json=body)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "microsoft_ads.pause HTTP %s: %s",
                exc.response.status_code if exc.response else "?",
                exc.response.text if exc.response else str(exc),
            )
            raise MicrosoftAdsError(f"pause failed: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.error("microsoft_ads.pause transport error: %s", exc)
            raise MicrosoftAdsError(f"pause transport error: {exc}") from exc
        logger.info("microsoft_ads.pause campaign=%s", campaign_id)

    async def stats(self, tokens: TokenSet, campaign_id: str, since: datetime) -> list[MetricEvent]:
        """Pull campaign performance metrics via the Reporting API.

        Submit a CampaignPerformanceReport request with CampaignId, Impressions,
        Clicks, Spend and Conversions columns. Poll for completion, then parse
        the CSV payload into canonical ``MetricEvent`` rows.
        """
        since_utc = since.astimezone(UTC) if since.tzinfo else since.replace(tzinfo=UTC)
        end = datetime.now(UTC)
        report_request: dict[str, Any] = {
            "ReportRequest": {
                "Format": "Csv",
                "ReportName": f"prachar_campaign_{campaign_id}",
                "ReportType": "CampaignPerformanceReportRequest",
                "Time": {
                    "PredefinedTime": "CustomDateRange",
                    "CustomStartDate": {
                        "Day": since_utc.day,
                        "Month": since_utc.month,
                        "Year": since_utc.year,
                    },
                    "CustomEndDate": {
                        "Day": end.day,
                        "Month": end.month,
                        "Year": end.year,
                    },
                },
                "Scope": {"CampaignIds": [{"Id": int(campaign_id)}]},
                "Columns": ["CampaignId", "Impressions", "Clicks", "Spend", "Conversions"],
            }
        }
        submit_url = f"{_MS_API_BASE}/reporting/campaignperformancereport"
        try:
            async with httpx.AsyncClient(timeout=_MS_TIMEOUT) as client:
                resp = await client.post(submit_url, headers=_headers(tokens), json=report_request)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "microsoft_ads.stats HTTP %s: %s",
                exc.response.status_code if exc.response else "?",
                exc.response.text if exc.response else str(exc),
            )
            raise MicrosoftAdsError(f"stats failed: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.error("microsoft_ads.stats transport error: %s", exc)
            raise MicrosoftAdsError(f"stats transport error: {exc}") from exc

        # The reporting API may return an inline CSV payload or a download URL.
        csv_text = data.get("ReportDownloadUrl") or data.get("Csv") or data.get("csv")
        if not csv_text:
            # Some responses embed the report content under "value".
            csv_text = data.get("value")
        if not csv_text:
            logger.warning("microsoft_ads.stats returned no report payload for %s", campaign_id)
            return []

        if isinstance(csv_text, str) and csv_text.startswith("http"):
            try:
                async with httpx.AsyncClient(timeout=_MS_TIMEOUT) as client:
                    dl = await client.get(csv_text)
                    dl.raise_for_status()
                    csv_text = dl.text
            except httpx.HTTPError as exc:
                logger.error("microsoft_ads.stats download error: %s", exc)
                raise MicrosoftAdsError(f"stats download failed: {exc}") from exc

        events: list[MetricEvent] = []
        reader = csv.DictReader(io.StringIO(csv_text))
        for row in reader:
            ts = end
            day = row.get("Day") or row.get("Date")
            if day:
                try:
                    ts = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=UTC)
                except ValueError:
                    ts = end
            for col, metric in (
                ("Impressions", "impressions"),
                ("Clicks", "clicks"),
                ("Spend", "cost"),
                ("Conversions", "conversions"),
            ):
                raw_val = row.get(col)
                if raw_val is None or raw_val == "":
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
        logger.info("microsoft_ads.stats campaign=%s events=%d", campaign_id, len(events))
        return events

    # ----- policy -----
    def policy_precheck(self, creative: CreativeAsset) -> PolicyResult:
        text = self._extract_copy_text(creative)
        result = claims_gate(text)
        warnings = list(result.warnings)
        if creative.type == CreativeType.copy:
            payload = creative.payload or {}
            for key, limit in (("headline", _MS_HEADLINE_LIMIT), ("description", _MS_DESCRIPTION_LIMIT)):
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
