"""Shared fixtures for worker tests.

Token loading is stubbed: tests exercise aggregation/upsert/error-isolation
logic with injected fake adapters, and real token decryption requires a DB.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest


@pytest.fixture(autouse=True)
def _fake_oauth_tokens(monkeypatch):
    from prachar_shared.contracts import TokenSet

    def _load(brand_id, channel):
        return TokenSet(access_token="test", expires_at=datetime.now(UTC) + timedelta(hours=1))

    monkeypatch.setattr("prachar_workers.tokens.load_connection_tokens", _load)
