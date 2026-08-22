"""Weekly Loop tools — let the Orb trigger and monitor the autonomous marketing loop.

The weekly loop is a 7-step Celery chain:
  measure → diagnose → regenerate → policy_check → publish → budget_realloc → report

These tools let the Orb:
  • Trigger the loop for the current brand on demand
  • Check the loop status / last run time

Architecture Freeze: Plugs into the existing Tool Registry + Celery loop tasks.
"""
from __future__ import annotations

import logging
from typing import Any

from .context import AIContext
from .registry import SideEffects, ToolCategory, ToolManifest, register_tool

log = logging.getLogger("prachar.runtime.tools_loop")


# ─── loop.trigger — Trigger the weekly autonomous loop for this brand ─────────


@register_tool(ToolManifest(
    name="loop.trigger",
    display_name="Trigger Marketing Loop",
    description=(
        "Trigger the 7-step autonomous weekly marketing loop for the current "
        "brand. The loop: measures performance → diagnoses issues → regenerates "
        "content → runs policy checks → publishes to channels → reallocates "
        "budget → generates a report. Use when the user says 'run my marketing' "
        "or 'do this week's marketing' or 'run the loop now'."
    ),
    category=ToolCategory.AUTOMATION,
    input_schema={},
    output_schema={"status": "string", "brand_id": "string"},
    estimated_cost_usd=0.0,
    estimated_time_ms=1000,
    estimated_tokens=0,
    estimated_latency_ms=1000,
    quality_score=0.9,
    requires_brand=True,
    requires_user_approval=True,
    side_effects=SideEffects.EXTERNAL,
    required_permissions=("can_publish",),
))
async def loop_trigger(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Trigger the weekly loop for the current brand via Celery."""
    try:
        brand_id_str = str(ctx.brand_id)

        # Try to enqueue via Celery
        try:
            from prachar_workers.celery_app import app as celery_app

            celery_app.send_task(
                "prachar_workers.loop.enqueue_weekly_loop",
                args=[brand_id_str],
                queue="loop-0",
            )
            return {
                "status": "triggered",
                "brand_id": brand_id_str,
                "message": "Weekly marketing loop has been triggered. It will run in the background.",
            }
        except Exception:
            # Fallback: run inline in a background thread (local dev)
            import threading

            def _run() -> None:
                try:
                    import asyncio as _aio
                    from prachar_workers.loop import run_weekly_loop

                    chain_obj = run_weekly_loop(brand_id_str)
                    chain_obj.apply()  # eager mode
                except Exception as exc:  # noqa: BLE001
                    log.error("inline loop failed: %s", exc)

            threading.Thread(target=_run, daemon=True).start()
            return {
                "status": "triggered_inline",
                "brand_id": brand_id_str,
                "message": "Loop triggered in inline mode (no Celery worker detected).",
            }
    except Exception as exc:  # noqa: BLE001
        log.exception("loop.trigger failed: %s", exc)
        return {"error": f"loop trigger failed: {exc}", "status": "failed"}


# ─── loop.status — Check the loop status for this brand ──────────────────────


@register_tool(ToolManifest(
    name="loop.status",
    display_name="Loop Status",
    description=(
        "Check the status of the weekly marketing loop for the current brand. "
        "Returns the last run time, next scheduled run, and current step if "
        "running. Use when the user asks 'when did my marketing last run' or "
        "'is the loop running'."
    ),
    category=ToolCategory.ANALYTICS,
    input_schema={},
    output_schema={"last_run": "string", "next_run": "string", "status": "string"},
    estimated_cost_usd=0.0,
    estimated_time_ms=500,
    estimated_tokens=100,
    estimated_latency_ms=500,
    quality_score=0.9,
    requires_brand=True,
    side_effects=SideEffects.READS,
))
async def loop_status(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Check the loop status by querying the brand's next_loop_at field."""
    try:
        from ..models import Brand
        from sqlalchemy import select

        session = ctx.session
        if session is None:
            return {"error": "no database session", "status": "unknown"}

        res = await session.execute(
            select(Brand).where(Brand.id == ctx.brand_id)
        )
        brand = res.scalar_one_or_none()
        if not brand:
            return {"error": "brand not found", "status": "unknown"}

        # Check for recent timeline entries about loop
        from .timeline import TimelineService

        svc = TimelineService()
        entries, _ = await svc.list(
            session=session,
            tenant_id=ctx.tenant_id,
            brand_id=ctx.brand_id,
            limit=5,
        )

        loop_entries = [e for e in entries if "loop" in (e.title or "").lower() or "weekly" in (e.title or "").lower()]

        next_loop = getattr(brand, "next_loop_at", None)
        next_loop_str = next_loop.isoformat() if next_loop and hasattr(next_loop, "isoformat") else None

        return {
            "last_run": loop_entries[0].created_at.isoformat() if loop_entries and hasattr(loop_entries[0].created_at, "isoformat") else None,
            "next_run": next_loop_str,
            "status": "scheduled" if next_loop else "not_scheduled",
            "recent_loop_events": [
                {"title": e.title, "when": e.created_at.isoformat() if hasattr(e.created_at, "isoformat") else str(e.created_at)}
                for e in loop_entries[:3]
            ],
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("loop.status failed: %s", exc)
        return {"error": f"loop status failed: {exc}", "status": "unknown"}
