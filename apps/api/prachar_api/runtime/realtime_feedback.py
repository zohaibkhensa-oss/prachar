"""Real-time Feedback Loop — mid-campaign learning checkpoint.

Instead of waiting for campaign completion to run the LearningEngine, this
module runs lightweight learning checkpoints on partial performance data
during the campaign. This enables the system to adapt mid-flight.

Plugs into:
  - LearningEngine (marketing_intelligence/learning_engine.py)
  - BusinessMemoryStore (marketing_intelligence/memory.py)
  - Performance Engine (metric_events table)
  - Creative Lineage Store (creative_lineage.py)

Architecture Freeze: Extends the existing LearningEngine and BusinessMemoryStore.
No new core abstractions.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

log = logging.getLogger("prachar.runtime.realtime_feedback")


async def run_learning_checkpoint(
    tenant_id: uuid.UUID,
    brand_id: uuid.UUID,
    campaign_id: uuid.UUID | None = None,
    days: int = 3,
) -> dict[str, Any]:
    """Run a lightweight learning checkpoint on recent performance data.

    This is a mid-campaign version of brain.learn_from_campaign() that:
    1. Pulls partial performance data from metric_events (last N days)
    2. Runs the LearningEngine on the partial data
    3. Stores interim learnings in BusinessMemory
    4. Feeds back into the creative evolution loop

    Returns a summary of what was learned.
    """
    try:
        # 1. Pull partial performance data
        perf_data = await _pull_partial_performance(tenant_id, brand_id, days)
        if not perf_data.get("has_data"):
            return {"status": "no_data", "days": days, "learnings": []}

        # 2. Run LearningEngine on partial data
        learnings = await _run_partial_learning(
            tenant_id=tenant_id,
            brand_id=brand_id,
            perf_data=perf_data,
        )

        # 3. Store interim learnings in BusinessMemory
        if learnings:
            await _store_interim_learnings(tenant_id, brand_id, learnings)

        # 4. Feed creative performance into evolution loop
        creative_insights = await _feed_creative_performance(brand_id, perf_data)

        return {
            "status": "completed",
            "days": days,
            "learnings": learnings,
            "creative_insights": creative_insights,
            "checkpoint_time": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:
        log.warning("learning checkpoint failed: %s", exc)
        return {"status": "failed", "error": str(exc)[:200]}


async def _pull_partial_performance(
    tenant_id: uuid.UUID,
    brand_id: uuid.UUID,
    days: int,
) -> dict[str, Any]:
    """Pull partial performance data from metric_events for the last N days."""
    try:
        from sqlalchemy import text

        from ..db import get_session_factory

        since = datetime.now(UTC) - timedelta(days=days)

        async with get_session_factory() as session:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )

            # Aggregate metrics by channel
            rows = await session.execute(
                text(
                    "SELECT channel, metric, SUM(value) as total, COUNT(*) as events "
                    "FROM metric_events "
                    "WHERE brand_id = :bid AND ts >= :since "
                    "GROUP BY channel, metric "
                    "ORDER BY channel, metric"
                ),
                {"bid": str(brand_id), "since": since},
            )
            channels: dict[str, dict[str, float]] = {}
            has_data = False
            for r in rows.all():
                has_data = True
                ch = r[0]
                metric = r[1]
                total = float(r[2])
                channels.setdefault(ch, {})[metric] = total

            # Pull creative-level performance
            creative_rows = await session.execute(
                text(
                    "SELECT entity_id, metric, SUM(value) as total "
                    "FROM metric_events "
                    "WHERE brand_id = :bid AND ts >= :since AND entity_type = 'creative' "
                    "GROUP BY entity_id, metric"
                ),
                {"bid": str(brand_id), "since": since},
            )
            creatives: dict[str, dict[str, float]] = {}
            for r in creative_rows.all():
                cid = r[0]
                metric = r[1]
                total = float(r[2])
                creatives.setdefault(cid, {})[metric] = total

        return {
            "has_data": has_data,
            "days": days,
            "channels": channels,
            "creatives": creatives,
            "total_metrics": sum(len(v) for v in channels.values()),
        }
    except Exception as exc:
        log.warning("pull partial performance failed: %s", exc)
        return {"has_data": False, "error": str(exc)[:200]}


async def _run_partial_learning(
    tenant_id: uuid.UUID,
    brand_id: uuid.UUID,
    perf_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run the LearningEngine on partial performance data.

    Generates lightweight interim learnings without a full campaign plan.
    """
    try:
        from prachar_shared.ai_gateway import AIGateway, Tier

        gw = AIGateway()
        channels_summary = perf_data.get("channels", {})
        creatives_summary = perf_data.get("creatives", {})

        prompt = f"""\
Analyze these PARTIAL performance metrics (last {perf_data.get('days', 3)} days) and extract
3-5 key interim learnings. Focus on actionable insights that can improve the campaign
while it's still running.

Channel performance:
{channels_summary}

Creative-level performance:
{creatives_summary}

OUTPUT (JSON array of 3-5 learning objects):
[{{"insight": "string", "channel": "string", "action": "string", "confidence": 0.0-1.0}}]
"""

        result = await gw.complete(
            prompt=prompt,
            tier=Tier.small,
            task="realtime_learning",
            tenant_id=brand_id,
            plan="starter",
        )

        if result.json_value and isinstance(result.json_value, list):
            return result.json_value[:5]
    except Exception as exc:
        log.warning("partial learning AI call failed: %s", exc)

    # Fallback: generate simple statistical learnings
    learnings: list[dict[str, Any]] = []
    for ch, metrics in channels_summary.items():
        impressions = metrics.get("impressions", 0)
        clicks = metrics.get("clicks", 0)
        if impressions > 0 and clicks > 0:
            ctr = clicks / impressions
            if ctr > 0.02:
                learnings.append({
                    "insight": f"{ch} is performing well with CTR={ctr:.2%}",
                    "channel": ch,
                    "action": "increase_budget",
                    "confidence": 0.7,
                })
            elif ctr < 0.005 and impressions > 1000:
                learnings.append({
                    "insight": f"{ch} underperforming with CTR={ctr:.2%}",
                    "channel": ch,
                    "action": "pause_or_refresh_creative",
                    "confidence": 0.6,
                })
    return learnings[:5]


async def _store_interim_learnings(
    tenant_id: uuid.UUID,
    brand_id: uuid.UUID,
    learnings: list[dict[str, Any]],
) -> None:
    """Store interim learnings in BusinessMemory for the next generation cycle."""
    try:
        from sqlalchemy import text

        from ..db import get_session_factory

        now = datetime.now(UTC)
        async with get_session_factory() as session:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )
            # Store as a performance learning (same table as post-campaign learnings)
            import json
            await session.execute(
                text(
                    "INSERT INTO performance_learnings "
                    "(tenant_id, brand_id, campaign_id, learning_data, created_at) "
                    "VALUES (:tid, :bid, NULL, :data::jsonb, :now)"
                ),
                {
                    "tid": str(tenant_id),
                    "bid": str(brand_id),
                    "data": json.dumps({
                        "type": "realtime_checkpoint",
                        "learnings": learnings,
                        "checkpoint_time": now.isoformat(),
                    }),
                    "now": now,
                },
            )
            # Audit
            await session.execute(
                text(
                    "INSERT INTO audit_events "
                    "(tenant_id, actor, action, entity_type, entity_id, payload) "
                    "VALUES (:tid, 'system', 'realtime_learning', 'brand', :bid, :payload::jsonb)"
                ),
                {
                    "tid": str(tenant_id),
                    "bid": str(brand_id),
                    "payload": json.dumps({
                        "learnings_count": len(learnings),
                        "checkpoint_time": now.isoformat(),
                    }),
                },
            )
            await session.commit()
        log.info("stored %d interim learnings for brand %s", len(learnings), brand_id)
    except Exception as exc:
        log.warning("store interim learnings failed: %s", exc)


async def _feed_creative_performance(
    brand_id: uuid.UUID,
    perf_data: dict[str, Any],
) -> dict[str, Any]:
    """Feed creative-level performance back into the creative evolution loop.

    Updates the perf JSONB on creatives rows so classify_variants() can
    classify winners/losers in real-time.
    """
    try:
        from .creative_lineage import update_creative_performance
        from sqlalchemy import text

        from ..db import get_session_factory

        creatives = perf_data.get("creatives", {})
        updated = 0
        for creative_id_str, metrics in creatives.items():
            try:
                creative_id = uuid.UUID(creative_id_str)
                await update_creative_performance(
                    creative_id=creative_id,
                    impressions=int(metrics.get("impressions", 0)),
                    clicks=int(metrics.get("clicks", 0)),
                    conversions=int(metrics.get("conversions", 0)),
                )
                updated += 1
            except (ValueError, Exception):
                continue

        return {"creatives_updated": updated, "total_creatives": len(creatives)}
    except Exception as exc:
        log.warning("feed creative performance failed: %s", exc)
        return {"creatives_updated": 0, "error": str(exc)[:200]}
