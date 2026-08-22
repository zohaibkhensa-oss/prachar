"""CURV AI subscription plans — single source of truth for pricing & deliverables.

Nothing in the app hardcodes plan prices or features. Everything reads from this
module, which itself reads numeric values from Settings (env-driven). This lets
you change pricing in one place (.env) without touching code.

Plans:
  - starter : ₹999/mo  — 1 brand, 2 videos/mo, 1 platform, weekly loop
  - growth  : ₹2,999/mo — 1 brand, 8 videos/mo, 3 platforms, Google Ads, priority
  - agency  : ₹9,999/mo — 5 brands, unlimited videos, all platforms, white-label

Currency: INR by default. Stripe charges in USD (converted at config rate);
Razorpay charges in INR directly. The `price_inr` and `price_usd` fields on
each plan let the checkout endpoint pick the right amount per provider.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import get_settings


@dataclass(frozen=True)
class PlanDeliverable:
    """A single line-item shown on the pricing page."""
    label: str
    value: str
    included: bool = True


@dataclass(frozen=True)
class PlanSpec:
    """Full specification of a subscription plan.

    All monetary values come from Settings (env-driven) so pricing can be
    changed without code edits. The `key` matches the `Plan` enum in
    `apps/api/prachar_api/models/enums.py`.
    """
    key: str
    name: str
    tagline: str
    price_inr: int          # monthly price in INR (paise = *100)
    price_usd: int          # monthly price in USD (cents = *100)
    currency_inr: str = "INR"
    currency_usd: str = "USD"
    popular: bool = False
    # Deliverables (limits)
    brands_limit: int = 1
    videos_per_month: int = 2
    images_per_month: int = 10
    platforms_limit: int = 1
    weekly_loop: bool = True
    google_ads: bool = False
    meta_ads: bool = False
    white_label: bool = False
    api_access: bool = False
    priority_support: bool = False
    ai_budget_inr: int = 0  # internal AI spend budget (paise)
    video_quality_tier: str = "lite"  # max video quality allowed
    # Display
    accent: str = "accent"
    icon: str = "Sparkles"
    deliverables: list[PlanDeliverable] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "tagline": self.tagline,
            "price_inr": self.price_inr,
            "price_usd": self.price_usd,
            "currency_inr": self.currency_inr,
            "currency_usd": self.currency_usd,
            "popular": self.popular,
            "brands_limit": self.brands_limit,
            "videos_per_month": self.videos_per_month,
            "images_per_month": self.images_per_month,
            "platforms_limit": self.platforms_limit,
            "weekly_loop": self.weekly_loop,
            "google_ads": self.google_ads,
            "meta_ads": self.meta_ads,
            "white_label": self.white_label,
            "api_access": self.api_access,
            "priority_support": self.priority_support,
            "ai_budget_inr": self.ai_budget_inr,
            "video_quality_tier": self.video_quality_tier,
            "accent": self.accent,
            "icon": self.icon,
            "deliverables": [
                {"label": d.label, "value": d.value, "included": d.included}
                for d in self.deliverables
            ],
        }


def _build_plans() -> dict[str, PlanSpec]:
    """Build plan specs from env-driven settings.

    Reads price/budget values from Settings so they can be overridden via .env
    without code changes. Default values reflect the published pricing.
    """
    s = get_settings()

    # Prices (in whole rupees / whole dollars; convert to paise/cents at checkout)
    starter_price_inr = getattr(s, "plan_starter_price_inr", 999)
    growth_price_inr = getattr(s, "plan_growth_price_inr", 2999)
    agency_price_inr = getattr(s, "plan_agency_price_inr", 9999)
    starter_price_usd = getattr(s, "plan_starter_price_usd", 12)
    growth_price_usd = getattr(s, "plan_growth_price_usd", 36)
    agency_price_usd = getattr(s, "plan_agency_price_usd", 120)

    # Internal AI budgets (paise) — reuses existing ai_budget_*_inr settings
    starter_ai = getattr(s, "ai_budget_starter_inr", 50000)
    growth_ai = getattr(s, "ai_budget_growth_inr", 200000)
    agency_ai = getattr(s, "ai_budget_agency_inr", 1000000)

    starter = PlanSpec(
        key="starter",
        name="Starter",
        tagline="For small businesses getting started with AI marketing",
        price_inr=starter_price_inr,
        price_usd=starter_price_usd,
        popular=False,
        brands_limit=1,
        videos_per_month=2,
        images_per_month=10,
        platforms_limit=1,
        weekly_loop=True,
        google_ads=False,
        meta_ads=False,
        white_label=False,
        api_access=False,
        priority_support=False,
        ai_budget_inr=starter_ai,
        video_quality_tier="lite",
        accent="success",
        icon="Sparkles",
        deliverables=[
            PlanDeliverable("Brands", "1 brand"),
            PlanDeliverable("AI videos", "2 per month (Standard quality)"),
            PlanDeliverable("AI images", "10 per month"),
            PlanDeliverable("Platforms", "1 platform (organic)"),
            PlanDeliverable("Weekly loop", "Auto post every week"),
            PlanDeliverable("Campaign Brain", "Full AI strategy engine"),
            PlanDeliverable("Agency Council", "9 AI Directors review"),
            PlanDeliverable("Performance", "Basic analytics"),
            PlanDeliverable("Google Ads", "Not included", included=False),
            PlanDeliverable("Meta Ads", "Not included", included=False),
            PlanDeliverable("White-label", "Not included", included=False),
            PlanDeliverable("API access", "Not included", included=False),
            PlanDeliverable("Support", "Email (48h response)"),
        ],
    )

    growth = PlanSpec(
        key="growth",
        name="Growth",
        tagline="For growing businesses that want paid ads + more content",
        price_inr=growth_price_inr,
        price_usd=growth_price_usd,
        popular=True,
        brands_limit=1,
        videos_per_month=8,
        images_per_month=40,
        platforms_limit=3,
        weekly_loop=True,
        google_ads=True,
        meta_ads=True,
        white_label=False,
        api_access=False,
        priority_support=True,
        ai_budget_inr=growth_ai,
        video_quality_tier="fast",
        accent="accent",
        icon="Zap",
        deliverables=[
            PlanDeliverable("Brands", "1 brand"),
            PlanDeliverable("AI videos", "8 per month (High quality)"),
            PlanDeliverable("AI images", "40 per month"),
            PlanDeliverable("Platforms", "3 platforms (organic + ads)"),
            PlanDeliverable("Weekly loop", "Auto post every week"),
            PlanDeliverable("Campaign Brain", "Full AI strategy engine"),
            PlanDeliverable("Agency Council", "9 AI Directors review"),
            PlanDeliverable("Google Ads", "Up to ₹10K/mo ad spend managed"),
            PlanDeliverable("Meta Ads", "Up to ₹10K/mo ad spend managed"),
            PlanDeliverable("Performance", "Full analytics + attribution"),
            PlanDeliverable("White-label", "Not included", included=False),
            PlanDeliverable("API access", "Not included", included=False),
            PlanDeliverable("Support", "Priority email (24h response)"),
        ],
    )

    agency = PlanSpec(
        key="agency",
        name="Agency",
        tagline="For agencies managing multiple brands at scale",
        price_inr=agency_price_inr,
        price_usd=agency_price_usd,
        popular=False,
        brands_limit=5,
        videos_per_month=50,
        images_per_month=500,
        platforms_limit=-1,
        weekly_loop=True,
        google_ads=True,
        meta_ads=True,
        white_label=True,
        api_access=True,
        priority_support=True,
        ai_budget_inr=agency_ai,
        video_quality_tier="standard",
        accent="info",
        icon="Crown",
        deliverables=[
            PlanDeliverable("Brands", "5 brands"),
            PlanDeliverable("AI videos", "50 per month (Premium quality)"),
            PlanDeliverable("AI images", "500 per month"),
            PlanDeliverable("Platforms", "All platforms (organic + ads)"),
            PlanDeliverable("Weekly loop", "Auto post every week"),
            PlanDeliverable("Campaign Brain", "Full AI strategy engine"),
            PlanDeliverable("Agency Council", "9 AI Directors review"),
            PlanDeliverable("Google Ads", "Up to ₹1L/mo ad spend managed"),
            PlanDeliverable("Meta Ads", "Up to ₹1L/mo ad spend managed"),
            PlanDeliverable("Performance", "Full analytics + attribution"),
            PlanDeliverable("White-label", "Custom branding on reports"),
            PlanDeliverable("API access", "Full REST API + webhooks"),
            PlanDeliverable("Support", "Dedicated account manager"),
        ],
    )

    return {"starter": starter, "growth": growth, "agency": agency}


_PLANS_CACHE: dict[str, PlanSpec] | None = None


def get_plans() -> dict[str, PlanSpec]:
    """Return all plan specs (cached)."""
    global _PLANS_CACHE
    if _PLANS_CACHE is None:
        _PLANS_CACHE = _build_plans()
    return _PLANS_CACHE


def get_plan(key: str) -> PlanSpec | None:
    return get_plans().get(key)


def list_plans() -> list[PlanSpec]:
    return list(get_plans().values())


def reset_plans_cache() -> None:
    """Force re-read on next access (used by tests)."""
    global _PLANS_CACHE
    _PLANS_CACHE = None
