from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime
from typing import Any

from celery import chain

from prachar_workers.celery_app import celery_app
from prachar_workers.db import _settings

logger = logging.getLogger(__name__)

CHANNELS = ("google", "gsc", "gmb", "youtube", "instagram", "facebook", "tiktok", "linkedin", "x", "pinterest")


def _shard_queue(brand_id: str) -> str:
    """Return the shard queue name for a brand.

    Brands are distributed across N shard queues by hash(brand_id) % N so
    multiple workers can process weekly loops in parallel without overlap.
    At 10K brands with 8 shards: ~1,250 brands per shard, each shard worker
    with concurrency=4 processes its brands in ~2.5 hours.
    """
    n = _settings().celery_loop_shards
    idx = hash(str(brand_id)) % n
    return f"loop-{idx}"


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

    # Batch enqueue to avoid Redis spike when dispatching 10K+ brands at once.
    # Each brand is routed to its shard queue so multiple workers can process
    # loops in parallel.
    batch_size = _settings().celery_dispatch_batch_size
    enqueued: list[str] = []
    for i, brand_id in enumerate(due):
        shard = _shard_queue(brand_id)
        enqueue_weekly_loop.apply_async(
            args=[brand_id],
            queue=shard,
        )
        enqueued.append(brand_id)
        if (i + 1) % batch_size == 0:
            logger.info("dispatch_due progress: %d/%d enqueued", i + 1, len(due))
    logger.info("dispatch_due enqueued=%d", len(enqueued))
    return {"enqueued": enqueued, "count": len(enqueued)}


def _run_step(prev: Any, stage: str) -> dict[str, Any]:
    if isinstance(prev, dict):
        brand_id = str(prev.get("brand_id", "unknown"))
        week = prev.get("week") or _week_key()
    else:
        brand_id = str(prev) if prev is not None else "unknown"
        week = _week_key()

    # ─── Idempotency check ─────────────────────────────────────────────
    from prachar_workers.reliability import IdempotencyGuard

    guard = IdempotencyGuard()
    idem_key = guard.make_key("loop_step", brand_id, week, stage)
    if guard.is_completed(idem_key):
        logger.info("loop step %s for %s week %s already completed — skipping", stage, brand_id, week)
        return {
            "brand_id": brand_id,
            "week": week,
            "stage": stage,
            "status": "skipped",
            "channels": {},
            "idempotent_skip": True,
        }

    if not guard.acquire(idem_key, ttl_seconds=3600):
        logger.warning("loop step %s for %s week %s already running — skipping", stage, brand_id, week)
        return {
            "brand_id": brand_id,
            "week": week,
            "stage": stage,
            "status": "already_running",
            "channels": {},
        }

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

    # Mark as completed for idempotency
    guard.complete(idem_key, result)

    return result


@celery_app.task(
    name="prachar_workers.loop.measure",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def measure(self, brand_id: Any) -> dict[str, Any]:  # noqa: ANN001
    result = _run_step(brand_id, "measure")
    # Fire-and-forget daily performance ingestion (P4.2) alongside the weekly
    # measure step.  Failures here must not break the weekly chain.
    try:
        from prachar_workers.performance import pull_daily_performance

        pull_daily_performance.apply_async()
    except Exception as exc:  # pragma: no cover
        logger.warning("performance pull enqueue failed: %s", exc)
    return result


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
    Call `.apply_async()` on the result to enqueue, or `.apply()` for eager mode.

    The chain is routed to the brand's shard queue so multiple workers can
    process loops in parallel without overlap.
    """
    shard = _shard_queue(brand_id)
    return chain(
        measure.s(brand_id).set(queue=shard),
        diagnose.s().set(queue=shard),
        regenerate.s().set(queue=shard),
        policy_check.s().set(queue=shard),
        publish.s().set(queue=shard),
        budget_realloc.s().set(queue=shard),
        report.s().set(queue=shard),
    )


@celery_app.task(
    name="prachar_workers.loop.enqueue_weekly_loop",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def enqueue_weekly_loop(brand_id: str) -> Any:
    """Celery task that enqueues the 7-step weekly loop chain.

    The chain runs on the brand's shard queue (loop-0..N-1) so multiple
    workers can process brands in parallel.
    """
    return run_weekly_loop(brand_id).apply_async()
