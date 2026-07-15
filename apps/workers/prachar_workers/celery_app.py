from __future__ import annotations

from celery import Celery
from kombu import Queue

from prachar_workers.db import _settings


def _build_app() -> Celery:
    settings = _settings()
    app = Celery("prachar_workers", broker=settings.redis_url, backend=settings.redis_url)
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_default_queue="prachar",
        task_queues=(
            Queue("prachar"),
            Queue("ingest"),
            Queue("organic"),
            Queue("ads"),
            Queue("measure"),
            Queue("creative"),
        ),
        beat_schedule={
            "loop-dispatch-due": {
                "task": "prachar_workers.loop.dispatch_due",
                "schedule": 60.0,
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
            "prachar_workers.loop",
        ]
    )
    return app


celery_app: Celery = _build_app()
