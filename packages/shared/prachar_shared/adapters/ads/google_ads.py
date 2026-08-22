from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from ...config import get_settings
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

# Google Ads API base (v17).
GOOGLE_ADS_API_BASE = "https://googleads.googleapis.com/v17"
# Micros-per-unit conversion (Google Ads reports money as integer micros).
MICROS_PER_UNIT = 1_000_000.0
# Match a 10-digit Google Ads customer id, optionally embedded in a scope string.
_CUSTOMER_ID_RE = re.compile(r"(\d{10})")


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

    # ----- helpers -----
    @staticmethod
    def _get_customer_id(tokens: TokenSet) -> str:
        """Extract the Google Ads customer id from the token set.

        The customer id is a 10-digit number. It may be encoded in a scope
        string (e.g. ``"google_ads:customer_id:1234567890"``) or stored in a
        ``metadata`` mapping when the ``TokenSet`` is extended by callers.
        Returns the bare digit string (no dashes) or an empty string when it
        cannot be determined.
        """
        # 1. Look for an explicit "customer_id:" prefix in any scope.
        for scope in tokens.scopes:
            low = scope.lower()
            if "customer_id:" in low:
                _, _, rest = low.partition("customer_id:")
                m = _CUSTOMER_ID_RE.search(rest)
                if m:
                    return m.group(1)
        # 2. Fall back to any 10-digit number found in the scopes.
        for scope in tokens.scopes:
            m = _CUSTOMER_ID_RE.search(scope)
            if m:
                return m.group(1)
        # 3. Some callers attach a metadata dict to the token set.
        meta = getattr(tokens, "metadata", None)
        if isinstance(meta, dict):
            for key in ("customer_id", "google_ads_customer_id", "login_customer_id"):
                val = meta.get(key)
                if isinstance(val, str) and val:
                    m = _CUSTOMER_ID_RE.search(val)
                    if m:
                        return m.group(1)
                if isinstance(val, int):
                    return str(val).zfill(10)
        return ""

    @staticmethod
    def _headers(tokens: TokenSet, customer_id: str) -> dict[str, str]:
        """Build the auth headers required by the Google Ads API."""
        settings = get_settings()
        developer_token = settings.google_ads_developer_token
        # login-customer-id is the manager account; for non-MCC setups it is
        # the same as the customer id. We prefer an explicit config value when
        # present, otherwise fall back to the customer id.
        login_customer_id = getattr(settings, "google_ads_login_customer_id", "") or customer_id
        return {
            "Authorization": f"Bearer {tokens.access_token}",
            "developer-token": developer_token,
            "login-customer-id": login_customer_id,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _resource_id(resource_name: str) -> str:
        """Extract the trailing numeric id from a Google Ads resource name."""
        if not resource_name:
            return ""
        return resource_name.rsplit("/", 1)[-1]

    # ----- campaign lifecycle -----
    async def create_campaign(self, tokens: TokenSet, campaign: dict[str, Any]) -> str:
        """Create a campaign via the Google Ads API and return the native id.

        POST /customers/{customer_id}/campaigns:mutate
        """
        customer_id = self._get_customer_id(tokens)
        if not customer_id:
            logger.warning("google_ads.create_campaign: missing customer_id in tokens")
            return ""
        url = f"{GOOGLE_ADS_API_BASE}/customers/{customer_id}/campaigns:mutate"
        budget = campaign.get("budget_daily") or campaign.get("budget") or 0.0
        budget_micros = int(round(float(budget) * MICROS_PER_UNIT))
        # If a campaign_budget resource name was supplied, use it directly;
        # otherwise reference a budget by the campaign id suffix.
        campaign_budget = campaign.get("campaign_budget")
        if not campaign_budget:
            budget_id = str(campaign.get("id", "")).replace("-", "") or "1"
            campaign_budget = f"customers/{customer_id}/campaignBudgets/{budget_id}"
        create_op: dict[str, Any] = {
            "name": campaign.get("name", f"prachar-{campaign.get('id', uuid.uuid4().hex[:8])}"),
            "status": campaign.get("status", "PAUSED"),
            "advertising_channel_type": campaign.get("advertising_channel_type", "SEARCH"),
            "campaign_budget": campaign_budget,
        }
        if campaign.get("advertising_channel_sub_type"):
            create_op["advertising_channel_sub_type"] = campaign["advertising_channel_sub_type"]
        body = {"operations": [{"create": create_op}]}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=self._headers(tokens, customer_id), json=body)
                resp.raise_for_status()
                data = resp.json()
            results = data.get("results") or []
            if results:
                rid = self._resource_id(results[0].get("resource_name", ""))
                logger.info("google_ads.create_campaign -> %s", rid)
                return rid
            logger.warning("google_ads.create_campaign: no results in response %s", data)
            return ""
        except Exception as exc:  # noqa: BLE001 - graceful degradation
            logger.error("google_ads.create_campaign failed: %s", exc)
            return ""

    async def upload_creative(self, tokens: TokenSet, creative: CreativeAsset) -> str:
        """Upload a Responsive Search Ad creative via the Google Ads API.

        POST /customers/{customer_id}/adGroupAds:mutate
        """
        customer_id = self._get_customer_id(tokens)
        if not customer_id:
            logger.warning("google_ads.upload_creative: missing customer_id in tokens")
            return ""
        url = f"{GOOGLE_ADS_API_BASE}/customers/{customer_id}/adGroupAds:mutate"
        payload = creative.payload or {}
        headlines = [str(h) for h in payload.get("headlines", []) if isinstance(h, (str, int, float))]
        descriptions = [str(d) for d in payload.get("descriptions", []) if isinstance(d, (str, int, float))]
        final_url = payload.get("final_url") or payload.get("url") or "https://example.com"
        # Default ad group resource; callers may override via payload.
        ad_group = payload.get("ad_group") or f"customers/{customer_id}/adGroups/1"
        ad: dict[str, Any] = {
            "final_urls": [final_url],
            "responsive_search_ad": {
                "headlines": [{"text": h[:GOOGLE_RSA_HEADLINE_LIMIT]} for h in headlines[:GOOGLE_RSA_MAX_HEADLINES]],
                "descriptions": [
                    {"text": d[:GOOGLE_RSA_DESCRIPTION_LIMIT]} for d in descriptions[:GOOGLE_RSA_MAX_DESCRIPTIONS]
                ],
            },
        }
        body = {
            "operations": [
                {
                    "create": {
                        "ad_group": ad_group,
                        "ad": ad,
                        "status": payload.get("status", "PAUSED"),
                    }
                }
            ]
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=self._headers(tokens, customer_id), json=body)
                resp.raise_for_status()
                data = resp.json()
            results = data.get("results") or []
            if results:
                rid = self._resource_id(results[0].get("resource_name", ""))
                logger.info("google_ads.upload_creative -> %s", rid)
                return rid
            logger.warning("google_ads.upload_creative: no results in response %s", data)
            return ""
        except Exception as exc:  # noqa: BLE001 - graceful degradation
            logger.error("google_ads.upload_creative failed: %s", exc)
            return ""

    async def set_budget_bid(
        self, tokens: TokenSet, campaign_id: str, budget: float, bid: dict[str, Any]
    ) -> None:
        """Update the daily budget amount and bid strategy for a campaign.

        Uses ``campaignBudgets:mutate`` for the daily amount and
        ``campaigns:mutate`` for the bidding strategy.
        """
        customer_id = self._get_customer_id(tokens)
        if not customer_id:
            logger.warning("google_ads.set_budget_bid: missing customer_id in tokens")
            return
        headers = self._headers(tokens, customer_id)
        budget_micros = int(round(float(budget) * MICROS_PER_UNIT))
        # Derive a budget resource name. Google Ads links a campaign to a
        # campaign_budget; we update that budget's amount_micros.
        budget_resource = f"customers/{customer_id}/campaignBudgets/{campaign_id}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 1. Update daily budget amount.
                budget_body = {
                    "operations": [
                        {
                            "update": {
                                "resource_name": budget_resource,
                                "amount_micros": budget_micros,
                            },
                            "update_mask": "amount_micros",
                        }
                    ]
                }
                budget_url = f"{GOOGLE_ADS_API_BASE}/customers/{customer_id}/campaignBudgets:mutate"
                await client.post(budget_url, headers=headers, json=budget_body)
                # 2. Update bid strategy on the campaign.
                campaign_resource = f"customers/{customer_id}/campaigns/{campaign_id}"
                update_fields: dict[str, Any] = {"resource_name": campaign_resource}
                field_mask: list[str] = []
                strategy = (bid or {}).get("strategy") or (bid or {}).get("type")
                if strategy:
                    # Map common strategy names to Google Ads bidding strategy
                    # enum fields.
                    strategy_map = {
                        "maximize_clicks": "manual_cpc",
                        "target_cpa": "target_cpa",
                        "target_roas": "target_roas",
                        "maximize_conversions": "maximize_conversions",
                        "manual_cpc": "manual_cpc",
                        "manual_cpm": "manual_cpm",
                    }
                    mapped = strategy_map.get(strategy, strategy)
                    update_fields["bidding_strategy_type"] = mapped
                    field_mask.append("bidding_strategy_type")
                    target_cpa = (bid or {}).get("target_cpa")
                    if target_cpa is not None and mapped == "target_cpa":
                        update_fields["target_cpa"] = {
                            "target_cpa_micros": int(round(float(target_cpa) * MICROS_PER_UNIT))
                        }
                        field_mask.append("target_cpa.target_cpa_micros")
                if field_mask:
                    campaign_body = {
                        "operations": [
                            {"update": update_fields, "update_mask": ",".join(field_mask)}
                        ]
                    }
                    campaign_url = f"{GOOGLE_ADS_API_BASE}/customers/{customer_id}/campaigns:mutate"
                    await client.post(campaign_url, headers=headers, json=campaign_body)
            logger.info(
                "google_ads.set_budget_bid campaign=%s budget=%s bid=%s",
                campaign_id,
                budget,
                bid,
            )
        except Exception as exc:  # noqa: BLE001 - graceful degradation
            logger.error("google_ads.set_budget_bid failed campaign=%s: %s", campaign_id, exc)

    async def pause(self, tokens: TokenSet, campaign_id: str) -> None:
        """Pause a campaign by mutating its status to PAUSED."""
        customer_id = self._get_customer_id(tokens)
        if not customer_id:
            logger.warning("google_ads.pause: missing customer_id in tokens")
            return
        url = f"{GOOGLE_ADS_API_BASE}/customers/{customer_id}/campaigns:mutate"
        campaign_resource = f"customers/{customer_id}/campaigns/{campaign_id}"
        body = {
            "operations": [
                {
                    "update": {
                        "resource_name": campaign_resource,
                        "status": "PAUSED",
                    },
                    "update_mask": "status",
                }
            ]
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=self._headers(tokens, customer_id), json=body)
                resp.raise_for_status()
            logger.info("google_ads.pause campaign=%s", campaign_id)
        except Exception as exc:  # noqa: BLE001 - graceful degradation
            logger.error("google_ads.pause failed campaign=%s: %s", campaign_id, exc)

    async def stats(self, tokens: TokenSet, campaign_id: str, since: datetime) -> list[MetricEvent]:
        """Pull real campaign metrics via GAQL search.

        POST /customers/{customer_id}/googleAds:search
        """
        customer_id = self._get_customer_id(tokens)
        if not customer_id:
            logger.warning("google_ads.stats: missing customer_id in tokens")
            return []
        url = f"{GOOGLE_ADS_API_BASE}/customers/{customer_id}/googleAds:search"
        since_date = since.astimezone(UTC).strftime("%Y-%m-%d")
        query = (
            "SELECT campaign.id, segments.date, "
            "metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions "
            "FROM campaign "
            f"WHERE campaign.id = {campaign_id} "
            f"AND segments.date >= '{since_date}' "
            "ORDER BY segments.date ASC"
        )
        body = {"query": query}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=self._headers(tokens, customer_id), json=body)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001 - graceful degradation
            logger.error("google_ads.stats failed campaign=%s: %s", campaign_id, exc)
            return []

        events: list[MetricEvent] = []
        results = data.get("results") or []
        for row in results:
            metrics = row.get("metrics") or {}
            segments = row.get("segments") or {}
            date_str = segments.get("date")
            try:
                ts = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC) if date_str else datetime.now(UTC)
            except ValueError:
                ts = datetime.now(UTC)
            impressions = float(metrics.get("impressions") or 0)
            clicks = float(metrics.get("clicks") or 0)
            cost_micros = float(metrics.get("cost_micros") or 0)
            cost = round(cost_micros / MICROS_PER_UNIT, 4)
            conversions = float(metrics.get("conversions") or 0)
            for metric, value in (
                ("impressions", impressions),
                ("clicks", clicks),
                ("cost", cost),
                ("conversions", conversions),
            ):
                events.append(
                    MetricEvent(
                        channel=self.network,
                        entity_type="campaign",
                        entity_id=str(campaign_id),
                        metric=metric,
                        value=value,
                        ts=ts,
                    )
                )
        logger.info("google_ads.stats campaign=%s events=%s", campaign_id, len(events))
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
