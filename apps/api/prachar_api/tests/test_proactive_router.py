"""Tests for the proactive notifications router (P5.2).

Verifies:
- GET /proactive/notifications returns 200 with notifications structure
- Auth required (401 without token)
- Works with no stored anomalies (empty list)

The anomaly cache and recommendation engine are mocked — these tests focus
on the HTTP layer.
"""
from __future__ import annotations

import os
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure env is loaded before settings is cached.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://prachar:prachar@localhost:5432/prachar")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-jwt-xxxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-secret-refresh-xxxxxxxxxxxxxxxxx")
os.environ.setdefault("TOKEN_ENC_KEY", "a" * 64)

from prachar_shared.config import get_settings  # noqa: E402

get_settings.cache_clear()

from prachar_api.main import app  # noqa: E402


@pytest.fixture
async def client():
    import prachar_api.db as dbmod
    if dbmod._engine is not None:
        await dbmod._engine.dispose()
        dbmod._engine = None
        dbmod._sessionmaker = None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    if dbmod._engine is not None:
        await dbmod._engine.dispose()
        dbmod._engine = None
        dbmod._sessionmaker = None


async def _register(c: AsyncClient, email: str, tenant_name: str):
    res = await c.post(
        "/auth/register",
        json={"email": email, "password": "testpass123", "tenant_name": tenant_name},
    )
    assert res.status_code == 201, res.text
    return res.json()


async def _create_brand(c: AsyncClient, headers: dict) -> str:
    res = await c.post(
        "/brands",
        json={"name": "Proactive Brand", "website": "https://example.com", "category": "tech"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


# ─── auth required ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_proactive_notifications_requires_auth(client: AsyncClient):
    res = await client.get("/proactive/notifications")
    assert res.status_code == 401


# ─── 200 with empty notifications ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_notifications_returns_200_with_empty_list(client: AsyncClient):
    tok = await _register(client, f"pr{uuid.uuid4().hex[:8]}@test.com", "Proactive Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)

    with patch(
        "prachar_workers.proactive.get_anomalies",
        return_value=[],
    ):
        res = await client.get("/proactive/notifications", headers=headers)

    assert res.status_code == 200, res.text
    body = res.json()
    assert "notifications" in body
    assert isinstance(body["notifications"], list)
    assert body["count"] == 0


# ─── 200 with stored anomalies ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_notifications_returns_200_with_anomalies(client: AsyncClient):
    tok = await _register(client, f"pr2{uuid.uuid4().hex[:8]}@test.com", "Proactive Tenant 2")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)

    fake_anomalies = [
        {
            "brand_id": brand_id,
            "campaign_id": str(uuid.uuid4()),
            "metric": "conversions",
            "magnitude": -0.35,
            "timeframe": "last 7 days vs previous 7 days",
            "severity": "medium",
            "direction": "drop",
        }
    ]

    fake_rec = {
        "what_to_do": "Refresh the ad creative",
        "why": "Conversions have dropped 35%.",
        "creative_directions": ["New hook", "Bold visual", "Urgency CTA"],
        "expected_impact": "Recover 15-20% of lost conversions.",
    }

    with patch(
        "prachar_workers.proactive.get_anomalies",
        return_value=fake_anomalies,
    ), patch(
        "prachar_api.routers.proactive.ProactiveEngine.generate_recommendation",
        new_callable=AsyncMock,
        return_value=fake_rec,
    ):
        res = await client.get("/proactive/notifications", headers=headers)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["count"] == 1
    notif = body["notifications"][0]
    assert "anomaly" in notif
    assert notif["anomaly"]["metric"] == "conversions"
    assert notif["anomaly"]["direction"] == "drop"
    assert "recommendation" in notif
    assert notif["recommendation"]["what_to_do"] == "Refresh the ad creative"
    assert len(notif["recommendation"]["creative_directions"]) == 3
