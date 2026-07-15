from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from ..deps import SessionDep
from ..models import AuditJob
from ..schemas import AuditJobOut, AuditRequestIn
from ..security import hash_ip

router = APIRouter(tags=["audits"])

# Free funnel — no auth. Rate limit by IP + domain at nginx/middleware layer in prod.


def _enqueue_audit_job(job_id: str, input_text: str) -> None:
    """Enqueue the Celery audit task. Falls back to inline async execution if
    Celery/Redis is unavailable (local dev without worker running)."""
    try:
        from prachar_workers.celery_app import app as celery_app

        # Check if the task is registered and Celery can reach the broker.
        if "prachar_workers.ingest.run_audit" in celery_app.tasks:
            celery_app.send_task(
                "prachar_workers.ingest.run_audit",
                args=[job_id, input_text],
                queue="ingest",
            )
            return
    except Exception:
        pass
    # Fallback: run inline in a background thread (local dev only).
    import threading

    def _run() -> None:
        try:
            import asyncio as _aio

            from prachar_workers.ingest.audit import run_audit_pipeline

            _aio.run(run_audit_pipeline(uuid.UUID(job_id), input_text))
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger("prachar.api.audit").error("inline audit failed: %s", exc)

    threading.Thread(target=_run, daemon=True).start()


@router.post("/brands/audit", response_model=AuditJobOut, status_code=status.HTTP_202_ACCEPTED)
async def start_audit(
    body: AuditRequestIn,
    request: Request,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> AuditJobOut:
    ip = request.client.host if request.client else "0.0.0.0"
    job = AuditJob(input=body.input, ip_hash=hash_ip(ip), status="pending")
    session.add(job)
    await session.commit()
    job_id_str = str(job.id)
    _enqueue_audit_job(job_id_str, body.input)
    return AuditJobOut.model_validate(job)


@router.get("/audits/{job_id}", response_model=AuditJobOut)
async def get_audit(job_id: uuid.UUID, session: SessionDep) -> AuditJobOut:
    res = await session.execute(select(AuditJob).where(AuditJob.id == job_id))
    job = res.scalar_one_or_none()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "audit not found")
    return AuditJobOut.model_validate(job)


@router.get("/audits/{job_id}/events")
async def audit_events_sse(job_id: uuid.UUID, request: Request) -> StreamingResponse:
    """SSE stream of audit progress log lines + status updates.
    The worker pushes lines to a Redis list `audit:{job_id}:progress`.
    We poll that list + the DB status until the job completes or client disconnects."""
    import redis.asyncio as aioredis

    from prachar_shared.config import get_settings

    async def _event_stream():
        settings = get_settings()
        redis = None
        try:
            redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        except Exception:
            pass

        last_status = None
        last_line_idx = 0
        timeout_count = 0
        max_timeout = 180  # 3 minutes max

        while True:
            if await request.is_disconnected():
                break

            # 1. Drain new progress lines from Redis.
            if redis is not None:
                try:
                    lines = await redis.lrange(
                        f"audit:{job_id}:progress", last_line_idx, -1
                    )
                    for line in lines:
                        yield f"data: {json.dumps({'type': 'progress', 'message': line})}\n\n"
                        last_line_idx += 1
                except Exception:
                    pass

            # 2. Check job status from DB.
            from ..db import get_sessionmaker

            sm = get_sessionmaker()
            async with sm() as db_session:
                res = await db_session.execute(
                    select(AuditJob).where(AuditJob.id == job_id)
                )
                job = res.scalar_one_or_none()
                if job is not None and job.status != last_status:
                    last_status = job.status
                    payload = {
                        "type": "status",
                        "status": job.status,
                        "score": job.score_snapshot,
                        "findings": job.findings,
                        "error": job.error,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    if job.status in ("completed", "failed"):
                        # Send a final close event.
                        yield f"data: {json.dumps({'type': 'done', 'status': job.status})}\n\n"
                        break

            if last_status in ("completed", "failed"):
                break

            timeout_count += 1
            if timeout_count > max_timeout:
                yield f"data: {json.dumps({'type': 'timeout'})}\n\n"
                break

            await asyncio.sleep(1)

        if redis is not None:
            await redis.close()

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
