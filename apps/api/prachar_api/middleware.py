from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .security import decode_token

log = logging.getLogger("prachar.middleware")


class TenantMiddleware(BaseHTTPMiddleware):
    """Extracts the tenant_id from the JWT and stashes it on request.state.
    The actual Postgres RLS context (SET LOCAL app.tenant_id) is applied inside
    the get_session dependency on the same connection used by the handler."""

    async def dispatch(self, request: Request, call_next) -> Response:
        auth = request.headers.get("authorization")
        tenant_id: uuid.UUID | None = None
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            try:
                payload = decode_token(token, kind="access")
                tid = payload.get("tenant_id")
                if tid:
                    tenant_id = uuid.UUID(str(tid))
            except (ValueError, KeyError):
                pass
        request.state.tenant_id = tenant_id
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to every response.

    Implements OWASP-recommended headers:
    - Strict-Transport-Security (HSTS)
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - Content-Security-Policy (restrictive default)
    - Referrer-Policy
    - Permissions-Policy
    - X-XSS-Protection (legacy browsers)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # CSP — restrictive default. API doesn't render HTML, but this protects
        # any error pages or docs UI.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        return response


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """Global per-IP rate limiter using in-memory sliding window.

    Limits:
    - 300 req/min per IP for authenticated endpoints
    - 60 req/min per IP for unauthenticated endpoints
    - 1200 req/min per IP for health checks

    This is a coarse backstop. Fine-grained limits are in rate_limit.py
    (auth endpoints) and the WAF (Terraform, 2000 req/5min).

    Disabled in tests via _enabled=False.
    """
    _enabled: bool | None = None
    _store: dict[str, list[float]] = {}
    _MAX_STORE = 10_000

    def _is_enabled(self) -> bool:
        if GlobalRateLimitMiddleware._enabled is None:
            try:
                from prachar_shared.config import get_settings
                GlobalRateLimitMiddleware._enabled = get_settings().rate_limit_enabled
            except Exception:
                GlobalRateLimitMiddleware._enabled = False
        return GlobalRateLimitMiddleware._enabled

    def _get_ip(self, request: Request) -> str:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()
        return request.client.host if request.client else "unknown"

    def _limit_for(self, request: Request) -> tuple[int, int]:
        """Returns (max_requests, window_sec) based on the path."""
        path = request.url.path
        if path.startswith("/health"):
            return (1200, 60)
        # Check if tenant_id is set (authenticated). Use getattr to avoid
        # AttributeError when TenantMiddleware hasn't run (e.g. test apps).
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id is not None:
            return (300, 60)
        return (60, 60)

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self._is_enabled():
            return await call_next(request)

        ip = self._get_ip(request)
        max_req, window = self._limit_for(request)
        now = time.time()
        key = f"global:{ip}"
        bucket = GlobalRateLimitMiddleware._store.setdefault(key, [])
        cutoff = now - window
        bucket[:] = [t for t in bucket if t > cutoff]

        if len(bucket) >= max_req:
            from starlette.responses import JSONResponse
            retry = int(window - (now - bucket[0]))
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded. Try again in {max(retry, 1)} seconds."},
                headers={"Retry-After": str(max(retry, 1))},
            )

        bucket.append(now)

        # Periodic cleanup
        if len(GlobalRateLimitMiddleware._store) > GlobalRateLimitMiddleware._MAX_STORE:
            GlobalRateLimitMiddleware._store = {
                k: v for k, v in GlobalRateLimitMiddleware._store.items()
                if v and v[-1] > (now - 3600)
            }

        return await call_next(request)


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """Counts requests and errors for the /metrics endpoint.

    Records:
    - Total request count
    - Total error count (5xx responses)
    - Per-request latency (logged at debug level)

    This is the lightweight observability layer. For production at scale,
    swap for OpenTelemetry or prometheus_client.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip metrics endpoint itself to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.monotonic()
        try:
            response = await call_next(request)
            return response
        finally:
            from .routers.misc import record_request, record_error
            latency_ms = (time.monotonic() - start) * 1000
            record_request()
            status_code = response.status_code if "response" in dir() else 500
            if status_code >= 500:
                record_error()
            log.debug("request %s %s → %d (%.1fms)",
                      request.method, request.url.path, status_code, latency_ms)
