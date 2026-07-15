from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any

from prachar_shared.ai_gateway import AIGateway, Tier

logger = logging.getLogger(__name__)

HOOK_TYPES = ("pain", "proof", "curiosity", "offer")

# Per-network char limits (spec 06 §Creatives).
NETWORK_CHAR_LIMITS: dict[str, dict[str, int]] = {
    "google_ads": {
        "headline": 30,
        "description": 90,
        "max_headlines": 15,
        "max_descriptions": 4,
    },
    "meta_ads": {
        "primary_text": 125,
        "headline": 40,
        "description": 30,
    },
}

_DEFAULT_LIMITS: dict[str, int] = {"headline": 60, "description": 155}


def _gateway() -> AIGateway:
    return AIGateway()


def _clamp(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "\u2026"


def _stub_copy_variant(
    brand_id: str | uuid.UUID,
    channel: str,
    locale: str,
    hook_type: str,
    char_limits: dict[str, int],
) -> dict[str, Any]:
    """Deterministic stub ad copy derived from brand_graph hash."""
    seed = hashlib.sha256(f"{brand_id}|{channel}|{locale}|{hook_type}".encode("utf-8")).hexdigest()
    brand_tag = str(brand_id)[:8]
    hook_templates = {
        "pain": f"Struggling with growth? {brand_tag} helps you win {channel}.",
        "proof": f"Trusted by 10k+ brands. {brand_tag} delivers real results.",
        "curiosity": f"What if your {channel} strategy finally worked? Find out how.",
        "offer": f"Get started with {brand_tag} today. Limited-time onboarding.",
    }
    base = hook_templates.get(hook_type, hook_templates["offer"])
    hl = char_limits.get("headline", _DEFAULT_LIMITS["headline"])
    desc = char_limits.get("description", _DEFAULT_LIMITS["description"])
    headline = _clamp(f"[{hook_type}/{locale}] {brand_tag} on {channel}", hl)
    if "primary_text" in char_limits:
        # Meta shape.
        return {
            "hook_type": hook_type,
            "locale": locale,
            "primary_text": _clamp(f"{base} ({seed[:6]})", char_limits["primary_text"]),
            "headline": headline,
            "description": _clamp(f"{brand_tag} — {hook_type} variant {seed[:4]}", char_limits["description"]),
        }
    # Google RSA shape.
    max_h = char_limits.get("max_headlines", 15)
    max_d = char_limits.get("max_descriptions", 4)
    headlines = [_clamp(f"[{hook_type}/{locale}] {brand_tag} h{i}", hl) for i in range(min(3, max_h))]
    descriptions = [_clamp(f"{base} variant {i} ({seed[:4]})", desc) for i in range(min(2, max_d))]
    return {
        "hook_type": hook_type,
        "locale": locale,
        "headlines": headlines,
        "descriptions": descriptions,
    }


async def generate_ad_copy(
    brand_id: str | uuid.UUID,
    channel: str,
    locale: str,
    hook_types: list[str] | None = None,
    char_limits: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Generate ad copy variants per the variant matrix {hook_type} x {locale} x {length}.

    Uses the AIGateway small model (batch). Respects per-network char limits
    (Google RSA: 15 headlines x30, 4 descriptions x90; Meta: primary_text x125,
    headline x40, description x30). In stub mode generates plausible copy from a
    brand_graph hash.
    """
    hooks = hook_types or list(HOOK_TYPES)
    limits = char_limits or NETWORK_CHAR_LIMITS.get(channel, _DEFAULT_LIMITS)
    gw = _gateway()
    if gw._stub_mode():
        return [
            _stub_copy_variant(brand_id, channel, locale, h, limits) for h in hooks
        ]
    schema = {
        "type": "object",
        "properties": {
            "variants": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "hook_type": {"type": "string"},
                        "locale": {"type": "string"},
                        "primary_text": {"type": "string"},
                        "headline": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
            },
        },
    }
    prompt = (
        f"Generate {len(hooks)} ad copy variants for channel={channel}, locale={locale}, "
        f"brand_id={brand_id}. Hook types: {hooks}. Respect char limits: {limits}."
    )
    comp = gw.complete(
        prompt,
        tier=Tier.small,
        task="creative_copy",
        schema=schema,
        tenant_id=uuid.UUID(int=0) if not isinstance(brand_id, uuid.UUID) else brand_id,
        plan="starter",
    )
    jv = comp.json_value or {}
    variants = jv.get("variants", [])
    if not variants:
        return [
            _stub_copy_variant(brand_id, channel, locale, h, limits) for h in hooks
        ]
    # Clamp each variant to the requested limits.
    out: list[dict[str, Any]] = []
    for v, h in zip(variants, hooks, strict=False):
        v = dict(v)
        v.setdefault("hook_type", h)
        v.setdefault("locale", locale)
        for k, lim in limits.items():
            if k in v and isinstance(v[k], str):
                v[k] = _clamp(v[k], lim)
        out.append(v)
    return out


async def generate_ad_image(
    brand_id: str | uuid.UUID,
    brief: str,
    sizes: list[tuple[int, int]],
) -> list[str]:
    """Generate ad image variants at the requested sizes.

    Would call an image_gen provider + Pillow post-process. Stub: returns s3_key stubs.
    """
    out: list[str] = []
    for w, h in sizes:
        digest = hashlib.sha256(f"{brand_id}|{brief}|{w}x{h}".encode("utf-8")).hexdigest()[:10]
        out.append(f"creative/{brand_id}/{w}x{h}_{digest}.png")
    return out
