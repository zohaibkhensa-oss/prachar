from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# Per-network best-practice structural constants (spec 06 §Scaffold).
GOOGLE_AD_GROUPS = 2
META_AD_SETS = 3
META_CREATIVES_PER_AD_SET = 3


def _short_id(prefix: str, *parts: str) -> str:
    raw = "|".join(parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{digest}"


def scaffold_google_campaign(
    brand_id: str | uuid.UUID,
    audience_spec: dict[str, Any],
    objective: str,
    budget_daily: float,
    guardrails: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Google Ads best-practice structure: 1 campaign / 2 ad groups / RSAs."""
    bid_strategy = _google_bid_strategy(objective)
    campaign_id = _short_id("gcmp", str(brand_id), objective, str(budget_daily))
    ad_groups: list[dict[str, Any]] = []
    for i in range(GOOGLE_AD_GROUPS):
        ad_groups.append(
            {
                "ad_group_id": _short_id("gag", campaign_id, str(i)),
                "name": f"{objective}-ag{i + 1}",
                "rsa": {
                    "headlines": [],  # filled by creative.generate_ad_copy
                    "descriptions": [],
                    "final_url": "",
                },
                "bid_modifier": 1.0,
            }
        )
    return {
        "network": "google_ads",
        "brand_id": str(brand_id),
        "objective": objective,
        "audience_spec": audience_spec,
        "budget_daily": budget_daily,
        "currency": (guardrails or {}).get("currency", "INR"),
        "bid_strategy": bid_strategy,
        "guardrails": guardrails or {},
        "campaign_id": campaign_id,
        "ad_groups": ad_groups,
        "dry_run": True,
    }


def scaffold_meta_campaign(
    brand_id: str | uuid.UUID,
    audience_spec: dict[str, Any],
    objective: str,
    budget_daily: float,
    guardrails: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Meta CBO structure: 1 campaign / 3 ad sets / 3 creatives each."""
    bid_strategy = {"type": "CBO", "optimization_goal": _meta_optimization_goal(objective)}
    campaign_id = _short_id("mcmp", str(brand_id), objective, str(budget_daily))
    ad_sets: list[dict[str, Any]] = []
    for i in range(META_AD_SETS):
        creatives = [
            {
                "creative_id": _short_id("mcr", campaign_id, str(i), str(j)),
                "primary_text": "",
                "headline": "",
                "description": "",
                "image_s3_key": None,
            }
            for j in range(META_CREATIVES_PER_AD_SET)
        ]
        ad_sets.append(
            {
                "ad_set_id": _short_id("mas", campaign_id, str(i)),
                "name": f"{objective}-as{i + 1}",
                "creatives": creatives,
                "targeting": audience_spec,
            }
        )
    return {
        "network": "meta_ads",
        "brand_id": str(brand_id),
        "objective": objective,
        "audience_spec": audience_spec,
        "budget_daily": budget_daily,
        "currency": (guardrails or {}).get("currency", "INR"),
        "bid_strategy": bid_strategy,
        "guardrails": guardrails or {},
        "campaign_id": campaign_id,
        "ad_sets": ad_sets,
        "dry_run": True,
    }


def scaffold_for_network(
    network: str,
    brand_id: str | uuid.UUID,
    audience_spec: dict[str, Any],
    objective: str,
    budget_daily: float,
    guardrails: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dispatch to the per-network scaffolder."""
    if network == "google_ads":
        return scaffold_google_campaign(
            brand_id, audience_spec, objective, budget_daily, guardrails
        )
    if network == "meta_ads":
        return scaffold_meta_campaign(
            brand_id, audience_spec, objective, budget_daily, guardrails
        )
    raise ValueError(f"no scaffolder registered for network={network!r}")


def _google_bid_strategy(objective: str) -> dict[str, Any]:
    mapping = {
        "awareness": {"type": "TARGET_CPM", "target": 0.0},
        "traffic": {"type": "TARGET_CPA", "target": 0.0},
        "leads": {"type": "TARGET_CPA", "target": 0.0},
        "conversions": {"type": "TARGET_CPA", "target": 0.0},
        "app_installs": {"type": "TARGET_CPA", "target": 0.0},
        "video_views": {"type": "TARGET_CPV", "target": 0.0},
    }
    return mapping.get(objective, {"type": "MANUAL_CPC", "target": 0.0})


def _meta_optimization_goal(objective: str) -> str:
    mapping = {
        "awareness": "REACH",
        "traffic": "LINK_CLICKS",
        "leads": "LEAD_GENERATION",
        "conversions": "OFFSITE_CONVERSIONS",
        "app_installs": "APP_INSTALLS",
        "video_views": "VIDEO_VIEWS",
    }
    return mapping.get(objective, "LINK_CLICKS")
