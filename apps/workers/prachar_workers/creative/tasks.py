from __future__ import annotations

import asyncio
import logging
from typing import Any

from prachar_workers.celery_app import celery_app
from prachar_workers.creative.generate import (
    HOOK_TYPES,
    NETWORK_CHAR_LIMITS,
    generate_ad_copy,
    generate_ad_image,
)

logger = logging.getLogger(__name__)


@celery_app.task(
    name="prachar_workers.creative.generate_copy",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def generate_copy(
    brand_id: str, channel: str, locale: str, hook_types: list[str] | None = None
) -> list[str]:
    """Generate ad copy variants for a channel/locale.

    Delegates to :func:`generate_ad_copy` (async) and returns a flat list of
    headline strings for backward compatibility with the S0 stub contract.
    """
    hooks = hook_types or list(HOOK_TYPES)
    logger.info("generate_copy brand=%s channel=%s locale=%s hooks=%s", brand_id, channel, locale, hooks)
    limits = NETWORK_CHAR_LIMITS.get(channel, {"headline": 60, "description": 155})
    variants = asyncio.run(
        generate_ad_copy(brand_id, channel, locale, hooks, limits)
    )
    out: list[str] = []
    for v in variants:
        if "headlines" in v and isinstance(v["headlines"], list):
            out.extend(str(h) for h in v["headlines"])
        elif "headline" in v:
            out.append(str(v["headline"]))
        else:
            out.append(str(v))
    return out


@celery_app.task(
    name="prachar_workers.creative.generate_image",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def generate_image(brand_id: str, brief: str, sizes: list[str]) -> dict[str, Any]:
    """Generate image variants at the requested sizes (e.g. '1200x628').

    Delegates to :func:`generate_ad_image` (async). Returns s3_keys keyed by size.
    """
    logger.info("generate_image brand=%s brief=%s sizes=%s", brand_id, brief, sizes)
    parsed: list[tuple[int, int]] = []
    for s in sizes:
        try:
            w, h = s.split("x")
            parsed.append((int(w), int(h)))
        except Exception:
            parsed.append((1200, 628))
    keys = asyncio.run(generate_ad_image(brand_id, brief, parsed))
    return {
        "brand_id": brand_id,
        "brief": brief,
        "s3_keys": dict(zip(sizes, keys, strict=False)),
    }


@celery_app.task(
    name="prachar_workers.creative.evolve_variants",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def evolve_variants(campaign_id: str) -> dict[str, Any]:
    logger.info("evolve_variants campaign=%s", campaign_id)
    # S4 stub: losers (CTR < median-1sigma over 7d) retired; winners spawn children.
    # Children would be generated via generate_ad_copy with mutation prompts.
    return {
        "campaign_id": campaign_id,
        "retired": [],
        "spawned": [],
        "status": "ok",
    }
