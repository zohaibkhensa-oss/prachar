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

# Yandex region code map (ISO-3166-1 -> Yandex region id, representative subset).
_YANDEX_REGION_MAP: dict[str, int] = {
    "RU": 225,
    "UA": 187,
    "KZ": 159,
    "BY": 149,
    "US": 84,
}

_YANDEX_TITLE_LIMIT = 56
_YANDEX_TEXT_LIMIT = 81
_YANDEX_API_BASE = "https://api.direct.yandex.com/v5"


@register_ads
class YandexDirectAdapter(AdNetworkAdapter):
    """Yandex Direct API v5 adapter (spec 06 networks table P3 — CIS)."""

    network = "yandex_direct"

    # ----- audience translation -----
    def translate_audience(self, spec: AudienceSpec) -> NativeTargeting:
        # geo -> Yandex regions.
        regions: list[dict[str, Any]] = []
        for code in spec.geo:
            country = code.split("-", 1)[0]
            region_id = _YANDEX_REGION_MAP.get(country, 225)
            regions.append({"region_id": region_id, "country": country, "sub_code": code})
        # keywords -> search targeting.
        keywords = translate_taxonomy_sync(spec.intents, "intents", "yandex_direct")
        interests = translate_taxonomy_sync(spec.interests, "interests", "yandex_direct")

        payload: dict[str, Any] = {
            "regions": regions,
            "keywords": keywords,
            "interests": interests,
            "languages": list(spec.languages),
            "age_range": {"min": spec.age[0], "max": spec.age[1]},
            "gender": spec.gender.value,
        }
        if spec.lookalike_seed:
            payload["lookalike_seed"] = spec.lookalike_seed
        return NativeTargeting(network=self.network, payload=payload)

    @staticmethod
    def _get_login(tokens: TokenSet) -> str:
        """Extract Yandex login from token scopes or metadata."""
        for scope in tokens.scopes:
            if scope.startswith("login:"):
                return scope.split(":", 1)[1]
        return ""

    @staticmethod
    def _headers(tokens: TokenSet) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {tokens.access_token}",
            "Accept-Language": "en",
            "Content-Type": "application/json; charset=utf-8",
        }

    # ----- campaign lifecycle -----
    async def create_campaign(self, tokens: TokenSet, campaign: dict[str, Any]) -> str:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{_YANDEX_API_BASE}/campaigns",
                    headers=self._headers(tokens),
                    json={
                        "method": "add",
                        "params": {
                            "Campaigns": [{
                                "Name": campaign.get("name", "CURV AI Campaign"),
                                "StartDate": datetime.now(UTC).date().isoformat(),
                                "DailyBudget": int(campaign.get("budget_daily", 300) * 1_000_000),  # micros
                                "TextCampaign": {
                                    "BiddingStrategy": {
                                        "Search": {"BiddingStrategyType": "HIGHEST_POSITION"},
                                        "Network": {"BiddingStrategyType": "SERVING_OFF"},
                                    },
                                },
                            }],
                        },
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("result", {}).get("AddResults", [])
                if results and results[0].get("Id"):
                    return str(results[0]["Id"])
                return ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("yandex_direct.create_campaign failed: %s", exc)
            return ""

    async def upload_creative(self, tokens: TokenSet, creative: CreativeAsset) -> str:
        payload = creative.payload or {}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{_YANDEX_API_BASE}/ads",
                    headers=self._headers(tokens),
                    json={
                        "method": "add",
                        "params": {
                            "Ads": [{
                                "TextAd": {
                                    "Title": payload.get("title", "")[:_YANDEX_TITLE_LIMIT],
                                    "Text": payload.get("text", payload.get("body", ""))[:_YANDEX_TEXT_LIMIT],
                                    "Href": payload.get("href", payload.get("link_url", "")),
                                },
                            }],
                        },
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("result", {}).get("AddResults", [])
                if results and results[0].get("Id"):
                    return str(results[0]["Id"])
                return ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("yandex_direct.upload_creative failed: %s", exc)
            return ""

    async def set_budget_bid(
        self, tokens: TokenSet, campaign_id: str, budget: float, bid: dict[str, Any]
    ) -> None:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                await client.post(
                    f"{_YANDEX_API_BASE}/campaigns",
                    headers=self._headers(tokens),
                    json={
                        "method": "update",
                        "params": {
                            "Campaigns": [{
                                "Id": int(campaign_id),
                                "DailyBudget": int(budget * 1_000_000),  # micros
                            }],
                        },
                    },
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("yandex_direct.set_budget_bid failed: %s", exc)

    async def pause(self, tokens: TokenSet, campaign_id: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                await client.post(
                    f"{_YANDEX_API_BASE}/campaigns",
                    headers=self._headers(tokens),
                    json={
                        "method": "update",
                        "params": {
                            "Campaigns": [{
                                "Id": int(campaign_id),
                                "Status": "PAUSED",
                            }],
                        },
                    },
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("yandex_direct.pause failed: %s", exc)

    async def stats(self, tokens: TokenSet, campaign_id: str, since: datetime) -> list[MetricEvent]:
        end_date = datetime.now(UTC).date().isoformat()
        start_date = since.date().isoformat()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{_YANDEX_API_BASE}/reports",
                    headers=self._headers(tokens),
                    json={
                        "params": {
                            "SelectionCriteria": {
                                "CampaignIds": [int(campaign_id)],
                                "DateFrom": start_date,
                                "DateTo": end_date,
                            },
                            "FieldNames": ["Impressions", "Clicks", "Cost", "Conversions"],
                            "ReportType": "CUSTOM_REPORT",
                            "DateRangeType": "CUSTOM_DATE",
                            "Format": "TSV",
                            "IncludeVAT": "NO",
                        },
                    },
                )
                resp.raise_for_status()
                # Yandex returns TSV data; parse it
                lines = resp.text.strip().split("\n")
                if len(lines) < 2:
                    return []
                headers = lines[0].split("\t")
                events: list[MetricEvent] = []
                for line in lines[1:]:
                    values = line.split("\t")
                    row = dict(zip(headers, values))
                    try:
                        ts = datetime.strptime(row.get("Date", start_date), "%Y-%m-%d")
                    except (ValueError, TypeError):
                        ts = datetime.now(UTC)
                    metric_map = {
                        "Impressions": "impressions",
                        "Clicks": "clicks",
                        "Cost": "cost",
                        "Conversions": "conversions",
                    }
                    for raw_name, canonical in metric_map.items():
                        if raw_name in row and row[raw_name]:
                            try:
                                val = float(row[raw_name])
                                if raw_name == "Cost":
                                    val = val / 1_000_000  # micros to currency
                                events.append(MetricEvent(
                                    channel=self.network,
                                    entity_type="campaign",
                                    entity_id=campaign_id,
                                    metric=canonical,
                                    value=val,
                                    ts=ts,
                                ))
                            except (ValueError, TypeError):
                                pass
                return events
        except Exception as exc:  # noqa: BLE001
            logger.warning("yandex_direct.stats failed: %s", exc)
            return []

    # ----- policy -----
    def policy_precheck(self, creative: CreativeAsset) -> PolicyResult:
        text = self._extract_copy_text(creative)
        result = claims_gate(text)
        warnings = list(result.warnings)
        if creative.type == CreativeType.copy:
            payload = creative.payload or {}
            for key, limit in (("title", _YANDEX_TITLE_LIMIT), ("text", _YANDEX_TEXT_LIMIT)):
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
        for key in ("text", "title", "headline", "description"):
            v = payload.get(key)
            if isinstance(v, str):
                parts.append(v)
        return " ".join(parts)
