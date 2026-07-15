from __future__ import annotations

"""Creative evolution — per spec 06 §"Creative evolution":
losers (CTR < group median − 1σ over 7d) retired; LLM generates children of winners
(mutation prompts). Log lineage."""

import logging
import math
import statistics
import uuid
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CreativePerf:
    creative_id: uuid.UUID
    variant_group: str
    ctr_7d: float
    impressions_7d: int
    clicks_7d: int
    conversions_7d: int


def classify_variants(perfs: list[CreativePerf]) -> tuple[list[CreativePerf], list[CreativePerf], list[CreativePerf]]:
    """Split creatives into winners, losers, and neutral based on CTR.
    Winners: CTR > median + 1σ. Losers: CTR < median − 1σ. Rest: neutral.
    Per spec 06 §"Creative evolution"."""
    if not perfs:
        return [], [], []
    ctrs = [p.ctr_7d for p in perfs]
    if len(ctrs) < 2:
        return list(perfs), [], []
    med = statistics.median(ctrs)
    try:
        stdev = statistics.stdev(ctrs)
    except statistics.StatisticsError:
        stdev = 0.0
    threshold_hi = med + stdev
    threshold_lo = med - stdev
    winners = [p for p in perfs if p.ctr_7d > threshold_hi]
    losers = [p for p in perfs if p.ctr_7d < threshold_lo]
    neutral = [p for p in perfs if threshold_lo <= p.ctr_7d <= threshold_hi]
    return winners, losers, neutral


async def generate_winner_children(
    brand_id: uuid.UUID,
    winner: CreativePerf,
    brand_graph: dict[str, Any],
    count: int = 3,
) -> list[dict[str, Any]]:
    """Generate mutated children of a winning creative via LLM.
    Uses mutation prompts: take the winner's copy and create N variations
    with different hooks/angles while preserving the winning elements.
    Per spec 06 §"Creative evolution": 'LLM generates children of winners (mutation prompts). Log lineage.'"""
    try:
        from prachar_shared.ai_gateway import AIGateway, Tier

        gw = AIGateway()
        mutation_prompt = f"""\
You are a world-class ad copywriter. This ad creative is a TOP PERFORMER (CTR={winner.ctr_7d:.2%}).

Create {count} mutated variations that preserve the winning elements but test new angles:
- Keep the core value proposition
- Try different hooks (pain, proof, curiosity, offer)
- Try different lengths (shorter and longer)
- Vary the CTA

Winner copy (variant_group={winner.variant_group}):
 impressions={winner.impressions_7d}, clicks={winner.clicks_7d}, conversions={winner.conversions_7d}

Brand: {brand_graph}

OUTPUT (JSON array of {count} objects):
[{{"copy": "string", "hook_type": "pain|proof|curiosity|offer", "rationale": "string"}}]
"""
        result = await gw.complete(
            prompt=mutation_prompt,
            tier=Tier.small,
            task="creative_copy",
            tenant_id=brand_id,
            plan="starter",
        )
        if result.json_value and isinstance(result.json_value, list):
            return result.json_value[:count]
    except Exception as exc:
        logger.warning("winner children AI call failed, using stub: %s", exc)

    # Stub: generate simple mutations.
    hooks = ["pain", "proof", "curiosity", "offer"]
    return [
        {"copy": f"Variation {i+1} of winner (hook: {hooks[i % len(hooks)]})", "hook_type": hooks[i % len(hooks)], "rationale": "stub mutation"}
        for i in range(count)
    ]


def log_lineage(parent_id: uuid.UUID, child_ids: list[uuid.UUID], mutation_type: str) -> None:
    """Log the creative lineage (parent → children) as an audit event.
    Per spec: 'Log lineage.'"""
    try:
        from sqlalchemy import text

        from prachar_workers.db import session_scope

        with session_scope() as session:
            # Look up tenant from parent creative.
            row = session.execute(
                text("SELECT tenant_id FROM creatives WHERE id = :cid"),
                {"cid": str(parent_id)},
            ).first()
            if not row:
                return
            tenant_id = str(row[0])
            session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": tenant_id},
            )
            import json
            session.execute(
                text(
                    "INSERT INTO audit_events (tenant_id, actor, action, entity_type, entity_id, payload) "
                    "VALUES (:tid, 'ai', :action, 'creative', :eid, :payload::jsonb)"
                ),
                {
                    "tid": tenant_id,
                    "action": "creative.evolution",
                    "eid": str(parent_id),
                    "payload": json.dumps({
                        "mutation_type": mutation_type,
                        "children": [str(c) for c in child_ids],
                    }),
                },
            )
    except Exception as exc:
        logger.warning("lineage log failed: %s", exc)


async def evolve_campaign(campaign_id: uuid.UUID) -> dict[str, Any]:
    """Full creative evolution cycle for a campaign:
    1. Pull 7-day CTR per creative variant
    2. Classify into winners/losers/neutral
    3. Retire losers (pause)
    4. Generate children of winners
    5. Log lineage
    Per spec 06 §"Creative evolution"."""
    # S6: pull perf from DB, classify, evolve.
    # For now, return a summary dict. Full DB integration in production.
    return {
        "campaign_id": str(campaign_id),
        "winners": 0,
        "losers_retired": 0,
        "children_generated": 0,
        "status": "stub",
    }
