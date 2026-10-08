"""Tests for OAuth state signing and PKCE verifier persistence.

Verifies:
  1. Signed state contains nonce, brand_id, tenant_id, user_id, exp
  2. State signature verification rejects tampered tokens
  3. Expired state is rejected
  4. PKCE verifier is embedded in state for X/Twitter
  5. PKCE verifier can be retrieved from verified state
"""
from __future__ import annotations

import os
import time
import uuid

import pytest

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-jwt-xxxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-secret-refresh-xxxxxxxxxxxxxxxxx")
os.environ.setdefault("TOKEN_ENC_KEY", "a" * 64)

from prachar_shared.config import get_settings  # noqa: E402

get_settings.cache_clear()

from prachar_api.routers.connections import _sign_state, _verify_state  # noqa: E402


class TestOAuthStateSigning:
    def test_state_contains_required_fields(self):
        brand_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        payload = {
            "nonce": "test-nonce",
            "brand_id": str(brand_id),
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "exp": int(time.time()) + 600,
        }
        state = _sign_state(payload)
        decoded = _verify_state(state)
        assert decoded["brand_id"] == str(brand_id)
        assert decoded["tenant_id"] == str(tenant_id)
        assert decoded["user_id"] == str(user_id)
        assert decoded["nonce"] == "test-nonce"

    def test_tampered_state_rejected(self):
        payload = {
            "nonce": "test",
            "brand_id": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "exp": int(time.time()) + 600,
        }
        state = _sign_state(payload)
        # Tamper with the body
        body, sig = state.rsplit(".", 1)
        tampered = body + "x." + sig
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _verify_state(tampered)
        assert exc_info.value.status_code == 400

    def test_expired_state_rejected(self):
        payload = {
            "nonce": "test",
            "brand_id": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "exp": int(time.time()) - 100,  # expired 100s ago
        }
        state = _sign_state(payload)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _verify_state(state)
        assert exc_info.value.status_code == 400
        assert "expired" in exc_info.value.detail.lower()

    def test_pkce_verifier_embedded_in_state(self):
        """X/Twitter PKCE verifier should be retrievable from signed state."""
        pkce_verifier = "test-verifier-12345"
        payload = {
            "nonce": "test",
            "brand_id": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "exp": int(time.time()) + 600,
            "pkce_verifier": pkce_verifier,
        }
        state = _sign_state(payload)
        decoded = _verify_state(state)
        assert decoded["pkce_verifier"] == pkce_verifier

    def test_state_without_pkce_verifier(self):
        """Non-X channels should not have pkce_verifier in state."""
        payload = {
            "nonce": "test",
            "brand_id": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "exp": int(time.time()) + 600,
        }
        state = _sign_state(payload)
        decoded = _verify_state(state)
        assert "pkce_verifier" not in decoded
