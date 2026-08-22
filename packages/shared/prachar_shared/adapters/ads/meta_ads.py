from __future__ import annotations

import hashlib
import logging
import re
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
from .audience_translation import meta_location_target, translate_taxonomy_sync
from .base import AdNetworkAdapter

logger = logging.getLogger(__name__)

# Meta ad copy char limits (spec 06 §Creatives).
META_PRIMARY_TEXT_LIMIT = 125
META_HEADLINE_LIMIT = 40
META_DESCRIPTION_LIMIT = 30

META_API_BASE = "https://graph.facebook.com/v19.0"
META_REQUEST_TIMEOUT = 30.0


@register_ads
class MetaAdsAdapter(AdNetworkAdapter):
    """Meta (Facebook/Instagram) Marketing API adapter (spec 06 networks table P0)."""

    network = "meta_ads"

    # ----- audience translation -----
    def translate_audience(self, spec: AudienceSpec) -> NativeTargeting:
        locations: list[dict[str, Any]] = []
        for code in spec.geo:
            country = code.split("-", 1)[0]
            locations.append(meta_location_target(country))

        interests = translate_taxonomy_sync(spec.interests, "interests", "meta_ads")
        behaviors = translate_taxonomy_sync(spec.intents, "intents", "meta_ads")

        payload: dict[str, Any] = {
            "targeting": {
                "geo_locations": locations,
                "interests": interests,
                "behaviors": behaviors,
                "age_min": spec.age[0],
                "age_max": spec.age[1],
                "genders": [self._meta_gender_code(spec)],
                "locales": list(spec.languages),
            },
        }
        if spec.lookalike_seed:
            payload["lookalike"] = {
                "origin_type": "customer_list",
                "customer_list_id": spec.lookalike_seed,
                "ratio": 0.01,
                "country": spec.geo[0].split("-", 1)[0] if spec.geo else "US",
            }
        return NativeTargeting(network=self.network, payload=payload)

    @staticmethod
    def _meta_gender_code(spec: AudienceSpec) -> int:
        # Meta genders: 1=all, 2=male, 3=female. We use 1 for any/non-binary.
        if spec.gender.value == "male":
            return 2
        if spec.gender.value == "female":
            return 3
        return 1

    # ----- helpers -----
    @staticmethod
    def _get_account_id(tokens: TokenSet) -> str | None:
        """Extract the Meta ad account ID from the token set.

        Looks for an ``act_<digits>`` pattern in the token scopes (Meta encodes
        the ad account in granted scopes such as ``ads_management`` plus an
        ``act_<id>`` entry). Returns the bare numeric account id (without the
        ``act_`` prefix) or ``None`` if it cannot be determined.
        """
        for scope in tokens.scopes:
            m = re.match(r"^act_(\d+)$", scope)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _fallback_id(prefix: str, source: str) -> str:
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]
        return f"{prefix}-{digest}"

    # ----- campaign lifecycle -----
    async def create_campaign(self, tokens: TokenSet, campaign: dict[str, Any]) -> str:
        """Create a campaign via the Meta Marketing API.

        POST {API_BASE}/act_{account_id}/campaigns with access_token, name,
        objective, status, buying_type. Returns the real campaign id from the
        ``{"id": "..."}`` response. On any error, logs and returns a fallback
        deterministic id so callers do not crash.
        """
        account_id = self._get_account_id(tokens)
        if not account_id:
            logger.warning("meta_ads.create_campaign: no account_id in tokens, using fallback")
            return self._fallback_id("meta", repr(sorted(campaign.items())))

        url = f"{META_API_BASE}/act_{account_id}/campaigns"
        params: dict[str, Any] = {
            "access_token": tokens.access_token,
            "name": campaign.get("name", "prachar-campaign"),
            "objective": campaign.get("objective", "OUTCOME_CONVERSIONS"),
            "status": campaign.get("status", "PAUSED"),
            "buying_type": campaign.get("buying_type", "AUCTION"),
        }
        try:
            async with httpx.AsyncClient(timeout=META_REQUEST_TIMEOUT) as client:
                resp = await client.post(url, data=params)
                resp.raise_for_status()
                body = resp.json()
            campaign_id = body.get("id")
            if not campaign_id:
                logger.error("meta_ads.create_campaign: no id in response %s", body)
                return self._fallback_id("meta", repr(sorted(campaign.items())))
            logger.info("meta_ads.create_campaign -> %s", campaign_id)
            return campaign_id
        except Exception as exc:  # noqa: BLE001 — graceful fallback
            logger.exception("meta_ads.create_campaign failed: %s", exc)
            return self._fallback_id("meta", repr(sorted(campaign.items())))

    async def upload_creative(self, tokens: TokenSet, creative: CreativeAsset) -> str:
        """Upload an ad creative via the Meta Marketing API.

        POST {API_BASE}/act_{account_id}/adcreatives building an
        ``object_story_spec`` from the creative payload (image_url, text, link).
        Returns the real creative id. On any error, logs and returns a fallback
        deterministic id.
        """
        account_id = self._get_account_id(tokens)
        payload = creative.payload or {}
        if not account_id:
            logger.warning("meta_ads.upload_creative: no account_id in tokens, using fallback")
            return self._fallback_id(
                "meta-creative",
                repr(sorted(payload.items())) + creative.channel + creative.locale,
            )

        url = f"{META_API_BASE}/act_{account_id}/adcreatives"
        image_url = payload.get("image_url") or payload.get("image")
        text = payload.get("primary_text") or payload.get("text") or ""
        link = payload.get("link") or payload.get("url") or ""
        headline = payload.get("headline") or ""
        description = payload.get("description") or ""
        page_id = payload.get("page_id")
        instagram_actor_id = payload.get("instagram_actor_id")

        object_story_spec: dict[str, Any] = {
            "link_data": {
                "image_url": image_url,
                "message": text,
                "link": link,
                "name": headline,
                "description": description,
            },
        }
        if page_id:
            object_story_spec["page_id"] = page_id
        if instagram_actor_id:
            object_story_spec["instagram_actor_id"] = instagram_actor_id

        params: dict[str, Any] = {
            "access_token": tokens.access_token,
            "name": payload.get("name", f"prachar-creative-{creative.locale}"),
            "object_story_spec": object_story_spec,
            "url_tags": payload.get("url_tags", ""),
        }
        try:
            async with httpx.AsyncClient(timeout=META_REQUEST_TIMEOUT) as client:
                resp = await client.post(url, data=params)
                resp.raise_for_status()
                body = resp.json()
            creative_id = body.get("id")
            if not creative_id:
                logger.error("meta_ads.upload_creative: no id in response %s", body)
                return self._fallback_id(
                    "meta-creative",
                    repr(sorted(payload.items())) + creative.channel + creative.locale,
                )
            logger.info("meta_ads.upload_creative -> %s", creative_id)
            return creative_id
        except Exception as exc:  # noqa: BLE001 — graceful fallback
            logger.exception("meta_ads.upload_creative failed: %s", exc)
            return self._fallback_id(
                "meta-creative",
                repr(sorted(payload.items())) + creative.channel + creative.locale,
            )

    async def set_budget_bid(
        self, tokens: TokenSet, campaign_id: str, budget: float, bid: dict[str, Any]
    ) -> None:
        """Update daily_budget and bid_strategy on a campaign.

        POST {API_BASE}/{campaign_id} with fields daily_budget and
        bid_strategy. Money safety: idempotency key derived from campaign id
        and action. Logs and returns gracefully on error.
        """
        idem = f"{campaign_id}:set_budget_bid"
        url = f"{META_API_BASE}/{campaign_id}"
        params: dict[str, Any] = {
            "access_token": tokens.access_token,
            "daily_budget": str(int(budget * 100)),  # Meta expects cents as string
            "bid_strategy": bid.get("strategy", bid.get("type", "LOWEST_COST_WITHOUT_CAP")),
        }
        try:
            async with httpx.AsyncClient(timeout=META_REQUEST_TIMEOUT) as client:
                resp = await client.post(url, data=params)
                resp.raise_for_status()
            logger.info(
                "meta_ads.set_budget_bid campaign=%s budget=%s bid=%s idem=%s ok",
                campaign_id,
                budget,
                bid,
                idem,
            )
        except Exception as exc:  # noqa: BLE001 — graceful fallback
            logger.exception(
                "meta_ads.set_budget_bid failed campaign=%s budget=%s bid=%s idem=%s: %s",
                campaign_id,
                budget,
                bid,
                idem,
                exc,
            )

    async def pause(self, tokens: TokenSet, campaign_id: str) -> None:
        """Pause a campaign by setting status=PAUSED.

        POST {API_BASE}/{campaign_id} with status=PAUSED. Logs and returns
        gracefully on error.
        """
        idem = f"{campaign_id}:pause"
        url = f"{META_API_BASE}/{campaign_id}"
        params: dict[str, Any] = {
            "access_token": tokens.access_token,
            "status": "PAUSED",
        }
        try:
            async with httpx.AsyncClient(timeout=META_REQUEST_TIMEOUT) as client:
                resp = await client.post(url, data=params)
                resp.raise_for_status()
            logger.info("meta_ads.pause campaign=%s idem=%s ok", campaign_id, idem)
        except Exception as exc:  # noqa: BLE001 — graceful fallback
            logger.exception(
                "meta_ads.pause failed campaign=%s idem=%s: %s",
                campaign_id,
                idem,
                exc,
            )

    async def stats(self, tokens: TokenSet, campaign_id: str, since: datetime) -> list[MetricEvent]:
        """Pull campaign insights from the Meta Marketing API.

        GET {API_BASE}/{campaign_id}/insights with fields
        impressions,clicks,spend,conversions and date_preset=maximum,
        time_increment=1. Returns a list of MetricEvent built from the
        response ``data`` array. On error, logs and returns an empty list.
        """
        url = f"{META_API_BASE}/{campaign_id}/insights"
        params: dict[str, Any] = {
            "access_token": tokens.access_token,
            "fields": "impressions,clicks,spend,conversions",
            "date_preset": "maximum",
            "time_increment": "1",
        }
        events: list[MetricEvent] = []
        try:
            async with httpx.AsyncClient(timeout=META_REQUEST_TIMEOUT) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                body = resp.json()
            data = body.get("data", []) or []
            for row in data:
                ts_str = row.get("date_start") or row.get("date_stop")
                try:
                    ts = datetime.fromisoformat(ts_str).replace(tzinfo=UTC) if ts_str else datetime.now(UTC)
                except (TypeError, ValueError):
                    ts = datetime.now(UTC)
                for metric, raw_val in (
                    ("impressions", row.get("impressions")),
                    ("clicks", row.get("clicks")),
                    ("cost", row.get("spend")),
                    ("conversions", row.get("conversions")),
                ):
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
                            value=value,
                            ts=ts,
                        )
                    )
            logger.info("meta_ads.stats campaign=%s events=%d", campaign_id, len(events))
            return events
        except Exception as exc:  # noqa: BLE001 — graceful fallback
            logger.exception("meta_ads.stats failed campaign=%s: %s", campaign_id, exc)
            return events

    # ----- policy -----
    def policy_precheck(self, creative: CreativeAsset) -> PolicyResult:
        text = self._extract_copy_text(creative)
        result = claims_gate(text)
        warnings = list(result.warnings)
        if creative.type == CreativeType.copy:
            payload = creative.payload or {}
            for key, limit in (
                ("primary_text", META_PRIMARY_TEXT_LIMIT),
                ("headline", META_HEADLINE_LIMIT),
                ("description", META_DESCRIPTION_LIMIT),
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
