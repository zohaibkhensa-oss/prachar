"""A/B Testing Loop — generate multiple creative variants, test them against
each other, declare a winner, and feed the winner into the evolution loop.

This extends the existing Creative Evolution system with structured A/B testing:
1. Generate N variants of a creative (different hooks, angles, CTAs)
2. Distribute traffic evenly across variants
3. Track performance per variant
4. Declare a winner when statistical significance is reached
5. Feed the winner into the creative evolution loop for child generation

Plugs into:
  - Creative Studio (generate variants)
  - Creative model (store variants with same variant_group)
  - Creative Evolution (classify winners/losers)
  - Creative Lineage Store (track parent-child relationships)
  - Audit Engine (log every test action)

Architecture Freeze: Extends the existing Creative Evolution system.
No new core abstractions.
"""
from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

log = logging.getLogger("prachar.runtime.ab_testing")


@dataclass
class VariantResult:
    """Result of a single variant in an A/B test."""
    creative_id: uuid.UUID
    variant_label: str
    impressions: int
    clicks: int
    conversions: int
    ctr: float
    cvr: float


@dataclass
class ABTestResult:
    """Result of an A/B test comparison."""
    winner_id: uuid.UUID | None
    winner_label: str
    winner_ctr: float
    loser_ctr: float
    lift: float  # percentage improvement
    confidence: float  # 0.0-1.0
    is_significant: bool
    variants: list[VariantResult]


async def create_variant_test(
    tenant_id: uuid.UUID,
    brand_id: uuid.UUID,
    base_prompt: str,
    creative_type: str,  # "video" | "image" | "copy"
    num_variants: int = 3,
    campaign_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Create an A/B test by generating N creative variants.

    Each variant gets a different hook/angle while preserving the core message.
    All variants share the same variant_group so the evolution loop can
    classify them together.

    Returns the test configuration with variant IDs.
    """
    from prachar_shared.ai_gateway import AIGateway, Tier

    # Generate variant prompts with different hooks
    hooks = ["pain_point", "social_proof", "curiosity", "offer", "urgency"]
    selected_hooks = hooks[:num_variants]

    gw = AIGateway()
    try:
        result = await gw.complete(
            prompt=f"""\
You are an expert ad copywriter. Create {num_variants} A/B test variants of this ad:

Base prompt: {base_prompt}

Each variant should test a different psychological hook:
{chr(10).join(f"{i+1}. {h.replace('_', ' ')}" for i, h in enumerate(selected_hooks))}

OUTPUT (JSON array of {num_variants} objects):
[{{"prompt": "string (full creative prompt with the hook applied)", "hook_type": "string", "label": "short label"}}]
""",
            tier=Tier.small,
            task="ab_test_variant_generation",
            tenant_id=brand_id,
            plan="starter",
        )
        variants = result.json_value if result.json_value and isinstance(result.json_value, list) else []
    except Exception as exc:
        log.warning("variant generation AI call failed, using stub: %s", exc)
        variants = [
            {"prompt": f"{base_prompt} (variant {i+1})", "hook_type": h, "label": f"v{i+1}-{h}"}
            for i, h in enumerate(selected_hooks)
        ]

    # Store each variant as a Creative with the same variant_group
    from .creative_lineage import _variant_group, store_generated_creative

    variant_group = _variant_group(base_prompt, creative_type)
    variant_ids: list[dict[str, Any]] = []

    for i, v in enumerate(variants[:num_variants]):
        variant_prompt = v.get("prompt", base_prompt)
        hook_type = v.get("hook_type", f"variant_{i}")
        label = v.get("label", f"v{i+1}-{hook_type}")

        # For image/video, generate the actual creative
        if creative_type in ("image", "video"):
            try:
                if creative_type == "image":
                    from ..routers.video_gen import _generate_image_core
                    result = await _generate_image_core(prompt=variant_prompt)
                    url = result.image_url
                    model = result.model
                else:
                    from ..routers.video_gen import _call_fal_video, VideoGenRequest
                    from ..config import get_settings
                    fal_key = get_settings().fal_key.strip()
                    if fal_key:
                        req = VideoGenRequest(prompt=variant_prompt, duration="5")
                        resp = await _call_fal_video(fal_key, req, variant_prompt, "16:9")
                        url = resp.video_url
                        model = resp.model
                    else:
                        continue
            except Exception as exc:
                log.warning("variant %d generation failed: %s", i + 1, exc)
                continue
        else:
            url = ""
            model = "text"

        creative_id = await store_generated_creative(
            tenant_id=tenant_id,
            brand_id=brand_id,
            creative_type=creative_type,
            url=url,
            prompt=variant_prompt,
            model=model,
            campaign_id=campaign_id,
            metadata={
                "variant_group": variant_group,
                "hook_type": hook_type,
                "variant_label": label,
                "ab_test": True,
                "base_prompt": base_prompt[:200],
            },
        )

        if creative_id:
            variant_ids.append({
                "creative_id": str(creative_id),
                "label": label,
                "hook_type": hook_type,
                "prompt": variant_prompt[:100],
            })

    # Audit the test creation
    try:
        from sqlalchemy import text
        from ..db import get_session_factory
        import json

        async with get_session_factory() as session:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )
            await session.execute(
                text(
                    "INSERT INTO audit_events "
                    "(tenant_id, actor, action, entity_type, entity_id, payload) "
                    "VALUES (:tid, 'ai', 'ab_test.created', 'brand', :bid, :payload::jsonb)"
                ),
                {
                    "tid": str(tenant_id),
                    "bid": str(brand_id),
                    "payload": json.dumps({
                        "variant_group": variant_group,
                        "num_variants": len(variant_ids),
                        "creative_type": creative_type,
                        "base_prompt": base_prompt[:200],
                    }),
                },
            )
            await session.commit()
    except Exception as exc:
        log.warning("ab_test audit failed: %s", exc)

    return {
        "status": "created",
        "variant_group": variant_group,
        "variants": variant_ids,
        "creative_type": creative_type,
    }


async def evaluate_variant_test(
    tenant_id: uuid.UUID,
    brand_id: uuid.UUID,
    variant_group: str,
) -> ABTestResult:
    """Evaluate an A/B test — compare variant performance and declare a winner.

    Uses a simple Z-test for proportions to determine statistical significance.
    Requires at least 100 impressions per variant for meaningful results.
    """
    from .creative_lineage import get_variants_for_evolution

    variants_data = await get_variants_for_evolution(brand_id, days=7)
    # Filter to the specified variant group
    group_variants = [v for v in variants_data if v.get("variant_group") == variant_group]

    if len(group_variants) < 2:
        return ABTestResult(
            winner_id=None, winner_label="", winner_ctr=0, loser_ctr=0,
            lift=0, confidence=0, is_significant=False, variants=[],
        )

    # Build VariantResult list
    results: list[VariantResult] = []
    for v in group_variants:
        impressions = v.get("impressions_7d", 0)
        clicks = v.get("clicks_7d", 0)
        conversions = v.get("conversions_7d", 0)
        ctr = clicks / impressions if impressions > 0 else 0.0
        cvr = conversions / clicks if clicks > 0 else 0.0
        results.append(VariantResult(
            creative_id=uuid.UUID(v["creative_id"]),
            variant_label=v.get("variant_group", ""),
            impressions=impressions,
            clicks=clicks,
            conversions=conversions,
            ctr=ctr,
            cvr=cvr,
        ))

    # Sort by CTR descending
    results.sort(key=lambda r: r.ctr, reverse=True)
    winner = results[0]
    runner_up = results[1] if len(results) > 1 else results[0]

    # Z-test for proportions (CTR comparison)
    lift = ((winner.ctr - runner_up.ctr) / runner_up.ctr * 100) if runner_up.ctr > 0 else 0
    confidence = _z_test_proportion(
        winner.clicks, winner.impressions,
        runner_up.clicks, runner_up.impressions,
    )
    is_significant = confidence >= 0.95 and winner.impressions >= 100 and runner_up.impressions >= 100

    return ABTestResult(
        winner_id=winner.creative_id if is_significant else None,
        winner_label=winner.variant_label,
        winner_ctr=winner.ctr,
        loser_ctr=runner_up.ctr,
        lift=lift,
        confidence=confidence,
        is_significant=is_significant,
        variants=results,
    )


async def promote_winner(
    tenant_id: uuid.UUID,
    test_result: ABTestResult,
) -> dict[str, Any]:
    """Promote the winning variant — pause losers and feed winner into evolution.

    Called after evaluate_variant_test() declares a significant winner.
    """
    if not test_result.is_significant or not test_result.winner_id:
        return {"status": "no_significant_winner"}

    try:
        from sqlalchemy import text
        from ..db import get_session_factory
        import json

        async with get_session_factory() as session:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )

            # Pause losing variants (set policy_status to 'paused')
            loser_ids = [str(v.creative_id) for v in test_result.variants if v.creative_id != test_result.winner_id]
            for lid in loser_ids:
                await session.execute(
                    text("UPDATE creatives SET policy_status = 'paused' WHERE id = :cid"),
                    {"cid": lid},
                )

            # Mark winner as 'approved' (active)
            await session.execute(
                text("UPDATE creatives SET policy_status = 'approved' WHERE id = :cid"),
                {"cid": str(test_result.winner_id)},
            )

            # Audit
            await session.execute(
                text(
                    "INSERT INTO audit_events "
                    "(tenant_id, actor, action, entity_type, entity_id, payload) "
                    "VALUES (:tid, 'ai', 'ab_test.winner_promoted', 'creative', :eid, :payload::jsonb)"
                ),
                {
                    "tid": str(tenant_id),
                    "eid": str(test_result.winner_id),
                    "payload": json.dumps({
                        "winner_ctr": test_result.winner_ctr,
                        "lift": test_result.lift,
                        "confidence": test_result.confidence,
                        "losers_paused": loser_ids,
                    }),
                },
            )
            await session.commit()

        log.info(
            "promoted winner %s (CTR=%.2f%%, lift=%.1f%%, confidence=%.1f%%)",
            test_result.winner_id, test_result.winner_ctr * 100,
            test_result.lift, test_result.confidence * 100,
        )

        return {
            "status": "promoted",
            "winner_id": str(test_result.winner_id),
            "losers_paused": len(loser_ids),
            "lift": test_result.lift,
            "confidence": test_result.confidence,
        }
    except Exception as exc:
        log.warning("promote_winner failed: %s", exc)
        return {"status": "failed", "error": str(exc)[:200]}


def _z_test_proportion(
    clicks_a: int, impressions_a: int,
    clicks_b: int, impressions_b: int,
) -> float:
    """Two-proportion Z-test. Returns confidence (0.0-1.0).

    Compares the CTR of variant A vs variant B.
    """
    if impressions_a == 0 or impressions_b == 0:
        return 0.0

    p_a = clicks_a / impressions_a
    p_b = clicks_b / impressions_b
    p_pool = (clicks_a + clicks_b) / (impressions_a + impressions_b)

    if p_pool == 0 or p_pool == 1:
        return 0.0

    se = math.sqrt(p_pool * (1 - p_pool) * (1 / impressions_a + 1 / impressions_b))
    if se == 0:
        return 0.0

    z = abs(p_a - p_b) / se

    # Convert Z-score to confidence using normal CDF approximation
    # Z=1.96 → 95% confidence, Z=2.58 → 99%
    confidence = 2 * _normal_cdf(z) - 1
    return min(max(confidence, 0.0), 1.0)


def _normal_cdf(z: float) -> float:
    """Approximation of the standard normal CDF."""
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))
