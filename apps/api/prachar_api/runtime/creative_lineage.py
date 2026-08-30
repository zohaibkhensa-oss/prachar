"""Creative Lineage Store — connects generated video/image creatives into the
creative evolution loop.

When video_gen.generate or creative_studio.generate_image produces a result,
this module stores it as a Creative row with a variant_group so the evolution
loop can classify it as a winner/loser and generate mutated children.

Plugs into:
  - Creative model (tables.py) — stores the generated asset
  - Creative Evolution (workers/creative/evolution.py) — reads variants for classification
  - Audit Engine — logs every creative creation as an audit event
  - Feedback Store — feeds performance data back for future generation

Architecture Freeze: This extends the existing Creative model and Creative
Evolution system. No new core abstractions.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

log = logging.getLogger("prachar.runtime.creative_lineage")


def _variant_group(prompt: str, creative_type: str) -> str:
    """Generate a deterministic variant group from the prompt + type.

    Creatives with the same core prompt are grouped together so the evolution
    loop can compare their performance against each other.
    """
    # Normalize: lowercase, strip, take first 60 chars for grouping
    normalized = prompt.lower().strip()[:60]
    h = hashlib.md5(f"{creative_type}:{normalized}".encode()).hexdigest()[:8]
    return f"auto-{h}"


async def store_generated_creative(
    tenant_id: uuid.UUID,
    brand_id: uuid.UUID,
    creative_type: str,  # "video" | "image"
    url: str,
    prompt: str,
    model: str,
    campaign_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> uuid.UUID | None:
    """Store a generated video/image as a Creative row for the evolution loop.

    Returns the creative_id, or None on failure (non-blocking — generation
    still succeeds even if lineage tracking fails).
    """
    try:
        from sqlalchemy import text

        from ..db import get_session_factory

        session_factory = get_session_factory()
        creative_id = uuid.uuid4()
        variant_group = _variant_group(prompt, creative_type)
        now = datetime.now(UTC)

        perf_data = {
            "prompt": prompt[:500],
            "model": model,
            "generated_at": now.isoformat(),
            "url": url,
            "impressions_7d": 0,
            "clicks_7d": 0,
            "conversions_7d": 0,
            "ctr_7d": 0.0,
            **(metadata or {}),
        }

        async with session_factory() as session:
            # Set tenant context for RLS
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )
            await session.execute(
                text(
                    "INSERT INTO creatives "
                    "(id, tenant_id, campaign_id, type, s3_key, variant_group, "
                    "policy_status, perf, created_at, updated_at) "
                    "VALUES (:id, :tid, :cid, :type, :s3_key, :vg, 'approved', "
                    ":perf::jsonb, :now, :now)"
                ),
                {
                    "id": str(creative_id),
                    "tid": str(tenant_id),
                    "cid": str(campaign_id) if campaign_id else None,
                    "type": creative_type,
                    "s3_key": url,
                    "vg": variant_group,
                    "perf": _json_dumps(perf_data),
                    "now": now,
                },
            )
            # Audit event
            await session.execute(
                text(
                    "INSERT INTO audit_events "
                    "(tenant_id, actor, action, entity_type, entity_id, payload) "
                    "VALUES (:tid, 'ai', :action, 'creative', :eid, :payload::jsonb)"
                ),
                {
                    "tid": str(tenant_id),
                    "action": "creative.generated",
                    "eid": str(creative_id),
                    "payload": _json_dumps({
                        "type": creative_type,
                        "model": model,
                        "variant_group": variant_group,
                        "brand_id": str(brand_id),
                    }),
                },
            )
            await session.commit()

        log.info(
            "stored creative %s type=%s variant_group=%s model=%s",
            creative_id, creative_type, variant_group, model,
        )
        return creative_id
    except Exception as exc:
        log.warning("store_generated_creative failed (non-blocking): %s", exc)
        return None


async def update_creative_performance(
    creative_id: uuid.UUID,
    impressions: int = 0,
    clicks: int = 0,
    conversions: int = 0,
) -> None:
    """Update performance metrics for a creative (called by the measure step).

    This feeds the evolution loop — classify_variants() reads perf data to
    determine winners/losers.
    """
    try:
        from sqlalchemy import text

        from ..db import get_session_factory

        ctr = clicks / impressions if impressions > 0 else 0.0

        async with get_session_factory() as session:
            await session.execute(
                text(
                    "UPDATE creatives SET perf = jsonb_set("
                    "  jsonb_set("
                    "    jsonb_set("
                    "      jsonb_set(perf, '{impressions_7d}', :imp::jsonb),"
                    "      '{clicks_7d}', :clk::jsonb),"
                    "    '{conversions_7d}', :conv::jsonb),"
                    "  '{ctr_7d}', :ctr::jsonb),"
                    "  updated_at = :now WHERE id = :cid"
                ),
                {
                    "imp": str(impressions),
                    "clk": str(clicks),
                    "conv": str(conversions),
                    "ctr": str(round(ctr, 6)),
                    "now": datetime.now(UTC),
                    "cid": str(creative_id),
                },
            )
            await session.commit()
    except Exception as exc:
        log.warning("update_creative_performance failed: %s", exc)


async def get_variants_for_evolution(
    brand_id: uuid.UUID,
    days: int = 7,
) -> list[dict[str, Any]]:
    """Pull creatives with performance data for the evolution loop.

    Returns a list of dicts with the fields needed by CreativePerf:
    creative_id, variant_group, ctr_7d, impressions_7d, clicks_7d, conversions_7d
    """
    try:
        from sqlalchemy import text

        from ..db import get_session_factory

        async with get_session_factory() as session:
            rows = await session.execute(
                text(
                    "SELECT id, variant_group, "
                    "COALESCE((perf->>'impressions_7d')::int, 0), "
                    "COALESCE((perf->>'clicks_7d')::int, 0), "
                    "COALESCE((perf->>'conversions_7d')::int, 0), "
                    "COALESCE((perf->>'ctr_7d')::float, 0.0) "
                    "FROM creatives c "
                    "JOIN campaigns camp ON c.campaign_id = camp.id "
                    "WHERE camp.brand_id = :bid "
                    "AND c.created_at >= now() - interval ':days days' "
                    "AND c.variant_group IS NOT NULL "
                    "ORDER BY c.variant_group"
                ),
                {"bid": str(brand_id), "days": days},
            )
            return [
                {
                    "creative_id": str(r[0]),
                    "variant_group": r[1],
                    "impressions_7d": r[2],
                    "clicks_7d": r[3],
                    "conversions_7d": r[4],
                    "ctr_7d": r[5],
                }
                for r in rows.all()
            ]
    except Exception as exc:
        log.warning("get_variants_for_evolution failed: %s", exc)
        return []


def _json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, default=str)
