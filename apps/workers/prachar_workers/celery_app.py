from __future__ import annotations

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from prachar_workers.db import _settings


def _build_app() -> Celery:
    settings = _settings()
    app = Celery("prachar_workers", broker=settings.redis_url, backend=settings.redis_url)

    # Build shard queue names: loop-0, loop-1, ..., loop-(N-1)
    shard_count = settings.celery_loop_shards
    loop_shard_queues = [Queue(f"loop-{i}") for i in range(shard_count)]

    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=settings.celery_prefetch_multiplier,
        task_default_queue="prachar",
        # ─── Reliability settings ────────────────────────────────────────
        task_soft_time_limit=300,  # 5 min soft limit (task gets exception)
        task_time_limit=360,  # 6 min hard limit (task is killed)
        task_default_retry_delay=60,  # 60s between retries
        task_default_max_retries=3,
        # NOTE: removed global task_default_rate_limit="60/m" — at 10K brands
        # the weekly loop enqueues 70K tasks, and 60/min = 19 hours. Per-queue
        # concurrency is the right scaling lever, not a global rate limit.
        # Per-task rate limits are set on specific tasks that need them (e.g.
        # ad platform API calls).
        worker_max_tasks_per_child=settings.celery_max_tasks_per_child,
        worker_lost_wait=10,
        # ─── Queue routing ───────────────────────────────────────────────
        # Tasks are routed to dedicated queues so each worker pool can scale
        # independently. The weekly loop tasks go to shard queues (loop-0..N-1)
        # so multiple workers can process brands in parallel without overlap.
        task_routes={
            "prachar_workers.loop.dispatch_due": {"queue": "dispatch"},
            "prachar_workers.loop.enqueue_weekly_loop": {"queue": "dispatch"},
            # Loop step tasks are routed dynamically by enqueue_weekly_loop
            # based on hash(brand_id) % shard_count — see loop.py.
            "prachar_workers.ingest.*": {"queue": "ingest"},
            "prachar_workers.organic.*": {"queue": "organic"},
            "prachar_workers.ads.*": {"queue": "ads"},
            "prachar_workers.measure.*": {"queue": "measure"},
            "prachar_workers.creative.*": {"queue": "creative"},
            "prachar_workers.performance.*": {"queue": "measure"},
            "prachar_workers.proactive.*": {"queue": "measure"},
            "prachar_workers.publish.*": {"queue": "organic"},
        },
        task_queues=(
            Queue("prachar"),  # default / catch-all
            Queue("dispatch"),  # beat + dispatch_due (lightweight, 1 worker)
            Queue("ingest"),
            Queue("organic"),
            Queue("ads"),
            Queue("measure"),
            Queue("creative"),
            Queue("dlq"),  # Dead letter queue for failed tasks
            *loop_shard_queues,  # loop-0 .. loop-(N-1)
        ),
        # ─── Beat schedule ───────────────────────────────────────────────
        beat_schedule={
            "loop-dispatch-due": {
                "task": "prachar_workers.loop.dispatch_due",
                "schedule": 60.0,
                "options": {"queue": "dispatch"},
            },
            # Daily performance ingestion (P4.2) — 03:00 UTC daily.
            "performance-pull-daily": {
                "task": "prachar_workers.performance.pull_daily_performance",
                "schedule": crontab(hour=3, minute=0),
                "options": {"queue": "measure"},
            },
            # Daily proactive anomaly detection (P5.1) — 04:00 UTC daily.
            "proactive-check-anomalies": {
                "task": "prachar_workers.proactive.check_anomalies",
                "schedule": crontab(hour=4, minute=0),
                "options": {"queue": "measure"},
            },
        },
    )
    app.autodiscover_tasks(
        [
            "prachar_workers.ingest",
            "prachar_workers.organic",
            "prachar_workers.ads",
            "prachar_workers.measure",
            "prachar_workers.creative",
            "prachar_workers.performance",
            "prachar_workers.proactive",
            "prachar_workers.publish",
            "prachar_workers.loop",
        ]
    )
    return app


celery_app: Celery = _build_app()
