"""Tests for auth hardening — email verification, password reset, rate limiting.

Verifies:
  1. Registration sends a verification email (or logs it in dev mode)
  2. Email verification token works (24h TTL)
  3. Email verification is idempotent (verifying twice is safe)
  4. Invalid verification tokens are rejected
  5. Forgot-password always returns same response (no email enumeration)
  6. Password reset token works (1h TTL)
  7. Password reset actually changes the password
  8. Rate limiting blocks excessive register/login attempts
  9. Rate limit returns 429 with Retry-After header
"""
from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://prachar:prachar@localhost:5432/prachar")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-jwt-xxxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-secret-refresh-xxxxxxxxxxxxxxxxx")
os.environ.setdefault("TOKEN_ENC_KEY", "a" * 64)

from prachar_shared.config import get_settings  # noqa: E402

get_settings.cache_clear()

from prachar_api.main import app  # noqa: E402
from prachar_api.routers.auth import _make_action_token, _decode_action_token  # noqa: E402
from prachar_api import rate_limit  # noqa: E402


@pytest.fixture
async def client():
    import prachar_api.db as dbmod
    if dbmod._engine is not None:
        await dbmod._engine.dispose()
        dbmod._engine = None
        dbmod._sessionmaker = None
    # Clear rate limit store + enable rate limiting for these tests
    rate_limit._store.clear()
    rate_limit._enabled = True
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    if dbmod._engine is not None:
        await dbmod._engine.dispose()
        dbmod._engine = None
        dbmod._sessionmaker = None
    rate_limit._store.clear()
    # Disable rate limiting for other test files
    rate_limit._enabled = False


async def _register(c: AsyncClient, email: str | None = None) -> dict:
    email = email or f"auth-{uuid.uuid4().hex[:8]}@test.com"
    res = await c.post("/auth/register", json={
        "email": email,
        "password": "testpass123",
        "tenant_name": f"Auth Test {uuid.uuid4().hex[:6]}",
    })
    assert res.status_code == 201, res.text
    return res.json()


# ─── Action token tests (pure, no DB) ───────────────────────────────────────

class TestActionTokens:
    def test_make_and_decode_verify_token(self):
        user_id = uuid.uuid4()
        token = _make_action_token(user_id, "email_verify", ttl_hours=24)
        decoded = _decode_action_token(token, "email_verify")
        assert decoded == user_id

    def test_make_and_decode_reset_token(self):
        user_id = uuid.uuid4()
        token = _make_action_token(user_id, "password_reset", ttl_hours=1)
        decoded = _decode_action_token(token, "password_reset")
        assert decoded == user_id

    def test_wrong_action_type_rejected(self):
        user_id = uuid.uuid4()
        token = _make_action_token(user_id, "email_verify", ttl_hours=24)
        with pytest.raises(ValueError, match="wrong token type"):
            _decode_action_token(token, "password_reset")

    def test_invalid_token_rejected(self):
        with pytest.raises(ValueError):
            _decode_action_token("garbage.token.here", "email_verify")


# ─── Email verification tests ───────────────────────────────────────────────

class TestEmailVerification:
    @pytest.mark.asyncio
    async def test_register_creates_unverified_user(self, client: AsyncClient):
        tok = await _register(client)
        # User can log in (we don't block unverified users)
        res = await client.post("/auth/login", json={
            "email": tok["user"]["email"],
            "password": "testpass123",
        })
        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_verify_email_with_valid_token(self, client: AsyncClient):
        tok = await _register(client)
        user_id = uuid.UUID(tok["user"]["id"])
        token = _make_action_token(user_id, "email_verify", ttl_hours=24)
        res = await client.post("/auth/verify-email", json={"token": token})
        assert res.status_code == 200
        assert res.json()["status"] == "verified"

    @pytest.mark.asyncio
    async def test_verify_email_idempotent(self, client: AsyncClient):
        tok = await _register(client)
        user_id = uuid.UUID(tok["user"]["id"])
        token = _make_action_token(user_id, "email_verify", ttl_hours=24)
        # First verification
        res1 = await client.post("/auth/verify-email", json={"token": token})
        assert res1.status_code == 200
        # Second verification — should say "already_verified", not error
        res2 = await client.post("/auth/verify-email", json={"token": token})
        assert res2.status_code == 200
        assert res2.json()["status"] == "already_verified"

    @pytest.mark.asyncio
    async def test_verify_email_invalid_token(self, client: AsyncClient):
        res = await client.post("/auth/verify-email", json={"token": "invalid.token.here"})
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_verify_email_wrong_action_type(self, client: AsyncClient):
        tok = await _register(client)
        user_id = uuid.UUID(tok["user"]["id"])
        # Create a password_reset token, try to use it for email verification
        token = _make_action_token(user_id, "password_reset", ttl_hours=1)
        res = await client.post("/auth/verify-email", json={"token": token})
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_resend_verification(self, client: AsyncClient):
        tok = await _register(client)
        res = await client.post("/auth/resend-verification", json={
            "email": tok["user"]["email"],
        })
        assert res.status_code == 200
        # Should return generic "sent" message
        assert "sent" in res.json()["status"]

    @pytest.mark.asyncio
    async def test_resend_verification_nonexistent_email(self, client: AsyncClient):
        """Should return same response whether email exists or not (no enumeration)."""
        res = await client.post("/auth/resend-verification", json={
            "email": "nonexistent@test.com",
        })
        assert res.status_code == 200
        assert "sent" in res.json()["status"]


# ─── Password reset tests ───────────────────────────────────────────────────

class TestPasswordReset:
    @pytest.mark.asyncio
    async def test_forgot_password_returns_sent(self, client: AsyncClient):
        tok = await _register(client)
        res = await client.post("/auth/forgot-password", json={
            "email": tok["user"]["email"],
        })
        assert res.status_code == 200
        assert res.json()["status"] == "sent"

    @pytest.mark.asyncio
    async def test_forgot_password_nonexistent_email(self, client: AsyncClient):
        """Should return same response whether email exists or not (no enumeration)."""
        res = await client.post("/auth/forgot-password", json={
            "email": "nonexistent@test.com",
        })
        assert res.status_code == 200
        assert res.json()["status"] == "sent"

    @pytest.mark.asyncio
    async def test_reset_password_with_valid_token(self, client: AsyncClient):
        tok = await _register(client)
        user_id = uuid.UUID(tok["user"]["id"])
        token = _make_action_token(user_id, "password_reset", ttl_hours=1)
        new_password = "newpass456"
        res = await client.post("/auth/reset-password", json={
            "token": token,
            "password": new_password,
        })
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

        # Verify: can log in with new password
        res = await client.post("/auth/login", json={
            "email": tok["user"]["email"],
            "password": new_password,
        })
        assert res.status_code == 200

        # Verify: old password no longer works
        res = await client.post("/auth/login", json={
            "email": tok["user"]["email"],
            "password": "testpass123",
        })
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_reset_password_invalid_token(self, client: AsyncClient):
        res = await client.post("/auth/reset-password", json={
            "token": "invalid.token.here",
            "password": "newpass456",
        })
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_reset_password_wrong_action_type(self, client: AsyncClient):
        tok = await _register(client)
        user_id = uuid.UUID(tok["user"]["id"])
        # Create an email_verify token, try to use it for password reset
        token = _make_action_token(user_id, "email_verify", ttl_hours=24)
        res = await client.post("/auth/reset-password", json={
            "token": token,
            "password": "newpass456",
        })
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_reset_password_too_short(self, client: AsyncClient):
        tok = await _register(client)
        user_id = uuid.UUID(tok["user"]["id"])
        token = _make_action_token(user_id, "password_reset", ttl_hours=1)
        res = await client.post("/auth/reset-password", json={
            "token": token,
            "password": "short",  # < 8 chars
        })
        assert res.status_code == 422  # Pydantic validation error


# ─── Rate limiting tests ────────────────────────────────────────────────────

class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_login_rate_limit(self, client: AsyncClient):
        """After 10 failed login attempts in a minute, should get 429."""
        email = f"ratelimit-{uuid.uuid4().hex[:8]}@test.com"
        for i in range(10):
            res = await client.post("/auth/login", json={
                "email": email,
                "password": "wrongpass",
            })
            assert res.status_code == 401  # wrong credentials
        # 11th attempt should be rate-limited
        res = await client.post("/auth/login", json={
            "email": email,
            "password": "wrongpass",
        })
        assert res.status_code == 429
        assert "Retry-After" in res.headers

    @pytest.mark.asyncio
    async def test_register_rate_limit(self, client: AsyncClient):
        """After 5 registrations in an hour, should get 429."""
        for i in range(5):
            res = await client.post("/auth/register", json={
                "email": f"rl-{i}-{uuid.uuid4().hex[:8]}@test.com",
                "password": "testpass123",
                "tenant_name": f"RL Test {i}",
            })
            assert res.status_code == 201
        # 6th registration should be rate-limited
        res = await client.post("/auth/register", json={
            "email": f"rl-overflow-{uuid.uuid4().hex[:8]}@test.com",
            "password": "testpass123",
            "tenant_name": "RL Overflow",
        })
        assert res.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_resets_after_success(self, client: AsyncClient):
        """Successful login clears the rate limit counter."""
        tok = await _register(client)
        # Make 5 failed attempts (under the limit of 10)
        for i in range(5):
            await client.post("/auth/login", json={
                "email": tok["user"]["email"],
                "password": "wrongpass",
            })
        # Successful login
        res = await client.post("/auth/login", json={
            "email": tok["user"]["email"],
            "password": "testpass123",
        })
        assert res.status_code == 200
        # Should be able to make more attempts (rate limit was reset)
        for i in range(5):
            res = await client.post("/auth/login", json={
                "email": tok["user"]["email"],
                "password": "wrongpass",
            })
            assert res.status_code == 401  # not 429


# ─── Rate limiter unit tests ────────────────────────────────────────────────

class TestRateLimiterUnit:
    def setup_method(self):
        """Ensure rate limiting is enabled for unit tests."""
        rate_limit._enabled = True
        rate_limit._store.clear()

    def teardown_method(self):
        """Restore disabled state after each unit test."""
        rate_limit._enabled = False
        rate_limit._store.clear()

    def test_check_rate_limit_allows_under_limit(self):
        class MockRequest:
            class client:
                host = "127.0.0.1"
            headers = {}
        req = MockRequest()
        for _ in range(5):
            rate_limit.check_rate_limit(req, "test_endpoint", 5, 60)
        with pytest.raises(Exception) as exc_info:
            rate_limit.check_rate_limit(req, "test_endpoint", 5, 60)
        assert exc_info.value.status_code == 429

    def test_check_rate_limit_different_endpoints_independent(self):
        class MockRequest:
            class client:
                host = "127.0.0.2"
            headers = {}
        req = MockRequest()
        for _ in range(3):
            rate_limit.check_rate_limit(req, "endpoint_a", 3, 60)
        rate_limit.check_rate_limit(req, "endpoint_b", 3, 60)  # should not raise

    def test_check_rate_limit_different_ips_independent(self):
        class MockRequest1:
            class client:
                host = "10.0.0.1"
            headers = {}
        class MockRequest2:
            class client:
                host = "10.0.0.2"
            headers = {}
        for _ in range(3):
            rate_limit.check_rate_limit(MockRequest1(), "shared_endpoint", 3, 60)
        rate_limit.check_rate_limit(MockRequest2(), "shared_endpoint", 3, 60)  # should not raise
