"""Worker reliability utilities for Celery tasks.

Provides:
- Retry policy with exponential backoff
- Timeout enforcement
- Idempotency keys
- Dead-letter queue (DLQ) hooks
- Failure logging
- Progress updates

Usage:
    from prachar_workers.reliability import reliable_task, with_dlq, IdempotencyGuard

    @celery_app.task(bind=True)
    @with_dlq
    def my_task(self, brand_id):
        ...
"""
from __future__ import annotations

import functools
import hashlib
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any, Callable

import redis

logger = logging.getLogger(__name__)


# ─── Dead Letter Queue ────────────────────────────────────────────────────────


def send_to_dlq(
    task_name: str,
    task_id: str,
    args: tuple,
    kwargs: dict,
    exception: Exception,
    *,
    max_retries: int = 3,
) -> None:
    """Send a failed task to the dead-letter queue for manual inspection.

    The DLQ is a Redis list keyed by task name. Each entry contains:
    - task_name, task_id, args, kwargs, exception, timestamp, retry_count
    """
    try:
        from prachar_workers.db import _settings

        client = redis.Redis.from_url(_settings().redis_url, decode_responses=True)
        entry = {
            "task_name": task_name,
            "task_id": task_id,
            "args": list(args) if args else [],
            "kwargs": kwargs if kwargs else {},
            "exception_type": type(exception).__name__,
            "exception_message": str(exception)[:1000],
            "timestamp": datetime.now(UTC).isoformat(),
            "max_retries": max_retries,
        }
        client.lpush("dlq:tasks", json.dumps(entry, default=str))
        client.ltrim("dlq:tasks", 0, 9999)  # Keep last 10000
        logger.error("task %s sent to DLQ: %s", task_name, entry["exception_message"])
    except Exception:
        logger.error("failed to send task to DLQ", exc_info=True)


def with_dlq(func: Callable) -> Callable:
    """Decorator that catches exceptions and sends failed tasks to DLQ.

    Use on Celery task functions (after @celery_app.task).
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            # Extract task info from bound self (Celery bind=True)
            task = args[0] if args and hasattr(args[0], "request") else None
            task_name = task.name if task else func.__name__
            task_id = task.request.id if task else "unknown"
            send_to_dlq(
                task_name=task_name,
                task_id=task_id,
                args=getattr(task.request, "args", ()) if task else args,
                kwargs=getattr(task.request, "kwargs", {}) if task else kwargs,
                exception=exc,
            )
            raise

    return wrapper


# ─── Idempotency Guard ────────────────────────────────────────────────────────


class IdempotencyGuard:
    """Prevents duplicate task execution using Redis-based idempotency keys.

    Usage:
        guard = IdempotencyGuard()
        key = guard.make_key("generate_content", brand_id, week, channel)
        if not guard.acquire(key):
            # Already running or completed — skip
            return None
        try:
            # do work
            guard.complete(key, result)
        except Exception:
            guard.fail(key)
            raise
    """

    def __init__(self, client: redis.Redis | None = None) -> None:
        self._client = client

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            from prachar_workers.db import _settings

            self._client = redis.Redis.from_url(_settings().redis_url, decode_responses=True)
        return self._client

    @staticmethod
    def make_key(*parts: Any) -> str:
        """Generate an idempotency key from task parameters."""
        raw = ":".join(str(p) for p in parts)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"idem:{digest}"

    def acquire(self, key: str, ttl_seconds: int = 3600) -> bool:
        """Try to acquire an idempotency lock. Returns True if acquired."""
        # SETNX with TTL
        result = self.client.set(key, "running", nx=True, ex=ttl_seconds)
        return bool(result)

    def complete(self, key: str, result: Any = None) -> None:
        """Mark task as completed with optional result."""
        value = json.dumps({"status": "completed", "result": result}) if result else "completed"
        self.client.set(key, value, ex=86400)  # Keep for 24h

    def fail(self, key: str) -> None:
        """Mark task as failed (allows retry)."""
        self.client.delete(key)

    def is_completed(self, key: str) -> bool:
        """Check if a task with this key was already completed."""
        val = self.client.get(key)
        if val is None:
            return False
        return val in ("completed",) or (isinstance(val, str) and '"completed"' in val)


# ─── Progress Updates ─────────────────────────────────────────────────────────


def update_progress(task: Any, step: str, current: int, total: int, message: str = "") -> None:
    """Update task progress for real-time UI feedback.

    Stores progress in Redis under a task-specific key and updates Celery state.
    """
    try:
        from prachar_workers.db import _settings

        client = redis.Redis.from_url(_settings().redis_url, decode_responses=True)
        task_id = task.request.id if hasattr(task, "request") else str(task)
        progress = {
            "step": step,
            "current": current,
            "total": total,
            "percentage": round(current / total * 100, 1) if total > 0 else 0,
            "message": message,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        client.set(f"progress:{task_id}", json.dumps(progress), ex=3600)

        # Also update Celery state if available
        if hasattr(task, "update_state"):
            task.update_state(
                state="PROGRESS",
                meta=progress,
            )
    except Exception:
        logger.debug("progress update failed", exc_info=True)


def get_progress(task_id: str) -> dict[str, Any] | None:
    """Get the current progress of a task."""
    try:
        from prachar_workers.db import _settings

        client = redis.Redis.from_url(_settings().redis_url, decode_responses=True)
        data = client.get(f"progress:{task_id}")
        return json.loads(data) if data else None
    except Exception:
        return None


# ─── Timeout Enforcement ──────────────────────────────────────────────────────


class TaskTimeout:
    """Context manager for enforcing soft timeouts on task segments.

    Usage:
        with TaskTimeout(seconds=30, task_name="generate_content"):
            # this block must complete in 30s
            ...
    """

    def __init__(self, seconds: float, task_name: str = "") -> None:
        self.seconds = seconds
        self.task_name = task_name
        self.start = 0.0

    def __enter__(self) -> TaskTimeout:
        self.start = time.monotonic()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        elapsed = time.monotonic() - self.start
        if elapsed > self.seconds:
            logger.warning(
                "task %s exceeded soft timeout: %.1fs > %.1fs",
                self.task_name,
                elapsed,
                self.seconds,
            )
        return None  # Don't suppress exceptions

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.start

    @property
    def remaining(self) -> float:
        return max(0, self.seconds - self.elapsed)


# ─── Retry Policy Helper ──────────────────────────────────────────────────────


def retry_with_backoff(
    func: Callable,
    *,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Any:
    """Execute a function with exponential backoff retry.

    Args:
        func: The function to execute.
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds.
        max_delay: Maximum delay between retries.
        exceptions: Tuple of exception types to retry on.

    Returns:
        The function result.

    Raises:
        The last exception if all retries fail.
    """
    import asyncio

    last_exc: Exception | None = None
    delay = initial_delay

    for attempt in range(max_retries + 1):
        try:
            return func()
        except exceptions as exc:
            last_exc = exc
            if attempt < max_retries:
                logger.warning(
                    "attempt %d/%d failed for %s: %s — retrying in %.1fs",
                    attempt + 1,
                    max_retries + 1,
                    func.__name__,
                    exc,
                    delay,
                )
                time.sleep(delay)
                delay = min(delay * 2, max_delay)
            else:
                logger.error(
                    "all %d attempts failed for %s: %s",
                    max_retries + 1,
                    func.__name__,
                    exc,
                )

    raise last_exc  # type: ignore[misc]
