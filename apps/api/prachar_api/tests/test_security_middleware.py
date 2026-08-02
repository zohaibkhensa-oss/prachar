"""Tests for SecurityHeadersMiddleware and GlobalRateLimitMiddleware."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from prachar_api.middleware import SecurityHeadersMiddleware, GlobalRateLimitMiddleware


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/test")
    def test_endpoint():
        return {"data": "test"}

    return app


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


class TestSecurityHeaders:
    def test_hsts_header(self, client):
        resp = client.get("/health")
        assert resp.headers.get("Strict-Transport-Security") == "max-age=63072000; includeSubDomains; preload"

    def test_nosniff_header(self, client):
        resp = client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_frame_options_header(self, client):
        resp = client.get("/health")
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_referrer_policy(self, client):
        resp = client.get("/health")
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy(self, client):
        resp = client.get("/health")
        assert "geolocation=()" in resp.headers.get("Permissions-Policy", "")

    def test_csp_header(self, client):
        resp = client.get("/health")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_xss_protection(self, client):
        resp = client.get("/health")
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"


class TestGlobalRateLimit:
    def test_rate_limit_disabled_by_default(self):
        """Rate limiting should be disabled in test mode."""
        GlobalRateLimitMiddleware._enabled = False
        GlobalRateLimitMiddleware._store.clear()

        app = FastAPI()
        app.add_middleware(GlobalRateLimitMiddleware)

        @app.get("/test")
        def test():
            return {"ok": True}

        client = TestClient(app)
        # Should not be rate limited even with many requests
        for _ in range(100):
            resp = client.get("/test")
            assert resp.status_code == 200

    def test_rate_limit_enabled_blocks_excess(self):
        """When enabled, excess requests should get 429."""
        GlobalRateLimitMiddleware._enabled = True
        GlobalRateLimitMiddleware._store.clear()

        try:
            app = FastAPI()
            app.add_middleware(GlobalRateLimitMiddleware)

            @app.get("/test")
            def test():
                return {"ok": True}

            client = TestClient(app)
            # 60 unauthenticated requests should be allowed, 61st should fail
            for i in range(60):
                resp = client.get("/test")
                assert resp.status_code == 200, f"Request {i+1} failed"

            resp = client.get("/test")
            assert resp.status_code == 429
            assert "Retry-After" in resp.headers
        finally:
            GlobalRateLimitMiddleware._enabled = False
            GlobalRateLimitMiddleware._store.clear()


class TestMetricsEndpoint:
    def test_metrics_returns_prometheus_format(self):
        from prachar_api.routers.misc import router, record_request, _request_count

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers.get("content-type", "")
        body = resp.text
        assert "prachar_http_requests_total" in body
        assert "prachar_process_uptime_seconds" in body
        assert "prachar_process_pid" in body

    def test_metrics_counts_requests(self):
        from prachar_api.routers.misc import router, record_request

        app = FastAPI()
        app.include_router(router)

        @app.get("/ping")
        def ping():
            return {"ok": True}

        client = TestClient(app)
        # Make some requests
        for _ in range(5):
            client.get("/ping")

        resp = client.get("/metrics")
        body = resp.text
        # The request count should be > 0 (at least the /metrics calls + /ping calls)
        assert "prachar_http_requests_total" in body
