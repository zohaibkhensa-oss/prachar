from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime
from typing import Any

from celery import chain

from prachar_workers.celery_app import celery_app

logger = logging.getLogger(__name__)

CHANNELS = ("google", "gsc", "gmb", "youtube", "instagram", "facebook", "tiktok", "linkedin", "x", "pinterest")


def _week_key() -> str:
    iso = date.today().isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _now() -> datetime:
    return datetime.now(UTC)


def _audit(event: str, brand_id: str, stage: str, payload: dict[str, Any] | None = None) -> None:
    logger.info("audit brand=%s stage=%s event=%s", brand_id, stage, event)
    try:
        from sqlalchemy import text

        from prachar_workers.db import session_scope

        with session_scope() as session:
            # Look up tenant_id for this brand (brands table has no RLS issue
            # because we're using a sync session without tenant context — but
            # we need the tenant_id for the audit_events row).
            row = session.execute(
                text("SELECT tenant_id FROM brands WHERE id = :bid"), {"bid": brand_id}
            ).first()
            tenant_id = str(row[0]) if row else None
            if tenant_id is None:
                logger.warning("audit: brand %s not found", brand_id)
                return
            session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": tenant_id},
            )
            session.execute(
                text(
                    "INSERT INTO audit_events (tenant_id, actor, action, entity_type, entity_id, payload) "
                    "VALUES (:tid, 'system', :action, 'brand', :eid, :payload::jsonb)"
                ),
                {
                    "tid": tenant_id,
                    "action": f"loop.{stage}.{event}",
                    "eid": brand_id,
                    "payload": _json_dumps(payload or {}),
                },
            )
    except Exception as exc:  # pragma: no cover - DB optional
        logger.warning("audit write failed: %s", exc)


def _json_dumps(obj: Any) -> str:
    import json

    return json.dumps(obj, default=str)


def _channels_result(status: str = "ok") -> dict[str, Any]:
    return {ch: {"status": status} for ch in CHANNELS}


@celery_app.task(
    name="prachar_workers.loop.dispatch_due",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def dispatch_due() -> dict[str, Any]:
    due: list[str] = []
    try:
        from sqlalchemy import text

        from prachar_workers.db import session_scope

        with session_scope() as session:
            try:
                rows = session.execute(
                    text("SELECT id FROM brands WHERE next_loop_at <= now() OR next_loop_at IS NULL")
                ).all()
                due = [str(r[0]) for r in rows]
            except Exception:
                rows = session.execute(text("SELECT id FROM brands")).all()
                now = _now()
                due = [
                    str(r[0])
                    for r in rows
                    if (hash(str(r[0])) % 168) <= now.hour
                ]
    except Exception as exc:  # pragma: no cover
        logger.warning("dispatch_due DB read failed: %s", exc)

    enqueued: list[str] = []
    for brand_id in due:
        enqueue_weekly_loop.delay(brand_id)
        enqueued.append(brand_id)
    logger.info("dispatch_due enqueued=%d", len(enqueued))
    return {"enqueued": enqueued, "count": len(enqueued)}


def _run_step(prev: Any, stage: str) -> dict[str, Any]:
    if isinstance(prev, dict):
        brand_id = str(prev.get("brand_id", "unknown"))
        week = prev.get("week") or _week_key()
    else:
        brand_id = str(prev) if prev is not None else "unknown"
        week = _week_key()
    _audit("start", brand_id, stage)
    channels: dict[str, Any] = {}
    for ch in CHANNELS:
        try:
            channels[ch] = {"status": "ok"}
        except Exception as exc:  # pragma: no cover
            logger.warning("loop %s channel %s failed: %s", stage, ch, exc)
            channels[ch] = {"status": "error", "error": str(exc)}
    result = {
        "brand_id": brand_id,
        "week": week,
        "stage": stage,
        "status": "ok",
        "channels": channels,
    }
    _audit("end", brand_id, stage, {"status": result["status"]})
    return result


@celery_app.task(
    name="prachar_workers.loop.measure",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def measure(self, brand_id: Any) -> dict[str, Any]:  # noqa: ANN001
    return _run_step(brand_id, "measure")


@celery_app.task(
    name="prachar_workers.loop.diagnose",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def diagnose(self, prev: Any) -> dict[str, Any]:  # noqa: ANN001
    return _run_step(prev, "diagnose")


@celery_app.task(
    name="prachar_workers.loop.regenerate",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def regenerate(self, prev: Any) -> dict[str, Any]:  # noqa: ANN001
    return _run_step(prev, "regenerate")


@celery_app.task(
    name="prachar_workers.loop.policy_check",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def policy_check(self, prev: Any) -> dict[str, Any]:  # noqa: ANN001
    return _run_step(prev, "policy_check")


@celery_app.task(
    name="prachar_workers.loop.publish",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def publish(self, prev: Any) -> dict[str, Any]:  # noqa: ANN001
    return _run_step(prev, "publish")


@celery_app.task(
    name="prachar_workers.loop.budget_realloc",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def budget_realloc(self, prev: Any) -> dict[str, Any]:  # noqa: ANN001
    return _run_step(prev, "budget_realloc")


@celery_app.task(
    name="prachar_workers.loop.report",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def report(self, prev: Any) -> dict[str, Any]:  # noqa: ANN001
    result = _run_step(prev, "report")
    # Generate the PDF report.
    try:
        from prachar_workers.report import generate_pdf

        brand_id = result["brand_id"]
        week = result["week"]
        generate_pdf.apply_async(args=[brand_id, week, result])
    except Exception as exc:  # pragma: no cover
        logger.warning("report PDF generation failed: %s", exc)
    return result


def run_weekly_loop(brand_id: str) -> Any:
    """Build and return the 7-step Celery chain (does NOT execute it).
    Call `.apply_async()` on the result to enqueue, or `.apply()` for eager mode."""
    return chain(
        measure.s(brand_id),
        diagnose.s(),
        regenerate.s(),
        policy_check.s(),
        publish.s(),
        budget_realloc.s(),
        report.s(),
    )


@celery_app.task(
    name="prachar_workers.loop.enqueue_weekly_loop",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def enqueue_weekly_loop(brand_id: str) -> Any:
    """Celery task that enqueues the 7-step weekly loop chain."""
    return run_weekly_loop(brand_id).apply_async()
