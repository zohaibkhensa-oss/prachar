from __future__ import annotations

import shutil
import time

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from ..db import get_engine
from prachar_shared.config import get_settings

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health(response: Response) -> dict:
    """Lightweight health check — returns 200 if the process is alive.

    Used by load balancers (Railway, AWS ALB) to know whether to route
    traffic to this instance. Does NOT check dependencies — that's what
    /health/ready is for.
    """
    return {"status": "ok", "service": "prachar-api"}


@router.get("/health/ready")
async def health_ready(response: Response) -> dict:
    """Readiness check — verifies DB, Redis, and disk are available.

    Returns 200 only if ALL dependencies are healthy. Returns 503 if any
    check fails, with details about which dependency is down. Used by:
      - Kubernetes readiness probes
      - Uptime monitors (Better Stack, Pingdom)
      - Deploy scripts (wait for ready before routing traffic)
    """
    checks: dict[str, dict] = {}
    all_ok = True

    # 1. Database — can we run a trivial query?
    try:
        start = time.monotonic()
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency_ms = round((time.monotonic() - start) * 1000, 1)
        checks["database"] = {"status": "ok", "latency_ms": latency_ms}
    except Exception as e:
        checks["database"] = {"status": "down", "error": str(e)[:200]}
        all_ok = False

    # 2. Redis — can we ping it? (optional — app works without Redis via
    # inline fallback, so we warn rather than fail)
    s = get_settings()
    try:
        import redis.asyncio as aioredis
        start = time.monotonic()
        r = aioredis.from_url(s.redis_url, socket_timeout=2, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        latency_ms = round((time.monotonic() - start) * 1000, 1)
        checks["redis"] = {"status": "ok", "latency_ms": latency_ms}
    except Exception as e:
        checks["redis"] = {"status": "down", "error": str(e)[:200], "warning": "app degrades gracefully without Redis"}
        # Don't fail readiness on Redis — the app has inline fallback

    # 3. Disk space — is /tmp filling up? (catches the temp-file leak)
    try:
        disk = shutil.disk_usage("/tmp")
        free_gb = round(disk.free / (1024 ** 3), 2)
        free_pct = round((disk.free / disk.total) * 100, 1)
        if free_pct < 10:
            checks["disk"] = {"status": "warning", "free_gb": free_gb, "free_pct": free_pct, "warning": "low disk space"}
            if free_pct < 5:
                all_ok = False
        else:
            checks["disk"] = {"status": "ok", "free_gb": free_gb, "free_pct": free_pct}
    except Exception as e:
        checks["disk"] = {"status": "unknown", "error": str(e)[:200]}

    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if all_ok else "degraded",
        "service": "prachar-api",
        "checks": checks,
    }


@router.get("/health/live")
async def health_live() -> dict:
    """Liveness check — is the process alive and not deadlocked?

    Cheaper than /health/ready (no DB/Redis calls). Used by orchestrators
    to decide whether to restart the container.
    """
    return {"status": "ok", "service": "prachar-api", "pid": __import__("os").getpid()}


# ─── Metrics endpoint (Prometheus format) ────────────────────────────────────

# Lightweight in-memory metrics counters. For production at scale, swap for
# prometheus_client or OpenTelemetry. This gives basic observability without
# adding dependencies.
_metrics: dict[str, float] = {}
_request_count: int = 0
_error_count: int = 0
_start_time: float = time.time()


def record_request() -> None:
    """Called by middleware to count requests."""
    global _request_count
    _request_count += 1


def record_error() -> None:
    """Called by middleware to count errors."""
    global _error_count
    _error_count += 1


def record_metric(name: str, value: float) -> None:
    """Set a named metric value."""
    _metrics[name] = value


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus-format metrics endpoint.

    Exposes:
    - prachar_http_requests_total
    - prachar_http_errors_total
    - prachar_process_uptime_seconds
    - prachar_process_start_time_seconds
    - Custom metrics set via record_metric()
    """
    import os

    uptime = time.time() - _start_time
    lines = [
        "# HELP prachar_http_requests_total Total HTTP requests",
        "# TYPE prachar_http_requests_total counter",
        f"prachar_http_requests_total {_request_count}",
        "",
        "# HELP prachar_http_errors_total Total HTTP errors (5xx)",
        "# TYPE prachar_http_errors_total counter",
        f"prachar_http_errors_total {_error_count}",
        "",
        "# HELP prachar_process_uptime_seconds Process uptime in seconds",
        "# TYPE prachar_process_uptime_seconds gauge",
        f"prachar_process_uptime_seconds {uptime:.2f}",
        "",
        "# HELP prachar_process_start_time_seconds Start time of the process (unix timestamp)",
        "# TYPE prachar_process_start_time_seconds gauge",
        f"prachar_process_start_time_seconds {_start_time:.2f}",
        "",
        "# HELP prachar_process_pid Process ID",
        "# TYPE prachar_process_pid gauge",
        f"prachar_process_pid {os.getpid()}",
        "",
    ]

    # Custom metrics
    for name, value in sorted(_metrics.items()):
        lines.append(f"# TYPE {name} gauge")
        lines.append(f"{name} {value}")
        lines.append("")

    return Response(
        content="\n".join(lines),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


# ─── Public config (social login client IDs) ──────────────────────────────────

@router.get("/config/social")
async def social_config() -> dict:
    """Public endpoint returning social login client IDs.

    These are public values (embedded in the browser anyway via Google/Apple
    SDK), so it's safe to expose. The frontend fetches this at runtime to
    initialise the Google/Apple SDKs — avoids needing build-time args.
    """
    s = get_settings()
    return {
        "google_client_id": s.google_sign_in_client_id,
        "apple_client_id": s.apple_sign_in_client_id,
        "apple_redirect_uri": "",
    }
