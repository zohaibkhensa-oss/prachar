"""Tests for the performance analysis router (P4.3).

Verifies:
- GET /performance/{campaign_id} returns 200 with a summary
- 404 for a non-existent (or other-tenant) campaign
- Auth required (401 without token)

The engine itself is mocked — these tests focus on the HTTP layer.  The
engine's logic is covered by ``test_performance_engine.py``.
"""
from __future__ import annotations

import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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
        json={"name": "Perf Brand", "website": "https://example.com", "category": "tech"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _create_campaign(c: AsyncClient, headers: dict, brand_id: str) -> dict:
    res = await c.post(
        "/campaigns",
        json={
            "brand_id": brand_id,
            "network": "google_ads",
            "objective": "traffic",
            "audience_spec": {"geo": ["IN"]},
            "budget_daily": 100.0,
            "currency": "INR",
            "dry_run": True,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _fake_summary(campaign_id: str):
    """Build a fake PerformanceSummary-like object with to_dict()."""
    return SimpleNamespace(
        to_dict=lambda: {
            "campaign_id": campaign_id,
            "summary": f"Campaign {campaign_id} generated 100 conversions.",
            "top_metrics": {"impressions": 100_000, "clicks": 2000, "conversions": 100},
            "trend": "up",
            "notable_days": [],
            "benchmark_comparison": {"ctr": {"actual": 0.03, "benchmark": 0.02, "status": "better"}},
        }
    )


# ─── auth required ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_performance_requires_auth(client: AsyncClient):
    res = await client.get(f"/performance/{uuid.uuid4()}")
    assert res.status_code == 401


# ─── 200 with summary (engine mocked) ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_performance_returns_200_with_summary(client: AsyncClient):
    tok = await _register(client, f"p{uuid.uuid4().hex[:8]}@test.com", "Perf Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    with patch(
        "prachar_api.routers.performance.PerformanceEngine.analyse",
        new_callable=AsyncMock,
        return_value=_fake_summary(camp["id"]),
    ):
        res = await client.get(f"/performance/{camp['id']}", headers=headers)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["campaign_id"] == camp["id"]
    assert "summary" in body and body["summary"]
    assert body["trend"] == "up"
    assert "top_metrics" in body
    assert "benchmark_comparison" in body


# ─── 404 for non-existent campaign ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_performance_404_for_nonexistent_campaign(client: AsyncClient):
    tok = await _register(client, f"pn{uuid.uuid4().hex[:8]}@test.com", "Perf 404 Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}

    # Engine should not even be called for a missing campaign.
    with patch(
        "prachar_api.routers.performance.PerformanceEngine.analyse",
        new_callable=AsyncMock,
    ) as mock_analyse:
        res = await client.get(f"/performance/{uuid.uuid4()}", headers=headers)

    assert res.status_code == 404
    mock_analyse.assert_not_called()


# ─── 404 for other-tenant campaign ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_performance_404_for_other_tenant_campaign(client: AsyncClient):
    # Tenant A creates a campaign.
    tok_a = await _register(client, f"pa{uuid.uuid4().hex[:8]}@test.com", "Tenant A")
    headers_a = {"Authorization": f"Bearer {tok_a['access_token']}"}
    brand_id_a = await _create_brand(client, headers_a)
    camp_a = await _create_campaign(client, headers_a, brand_id_a)

    # Tenant B tries to read it.
    tok_b = await _register(client, f"pb{uuid.uuid4().hex[:8]}@test.com", "Tenant B")
    headers_b = {"Authorization": f"Bearer {tok_b['access_token']}"}

    res = await client.get(f"/performance/{camp_a['id']}", headers=headers_b)
    assert res.status_code == 404


# ─── GET /{campaign_id}/why — root-cause analysis (P4.4) ───────────────────────


def _fake_explanation(campaign_id: str):
    return {
        "campaign_id": campaign_id,
        "likely_causes": [
            {
                "cause": "creative_fatigue",
                "evidence": "CTR declined from 3% to 1%.",
                "confidence": "high",
            }
        ],
    }


@pytest.mark.asyncio
async def test_why_requires_auth(client: AsyncClient):
    res = await client.get(f"/performance/{uuid.uuid4()}/why")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_why_returns_200_with_causes(client: AsyncClient):
    tok = await _register(client, f"wy{uuid.uuid4().hex[:8]}@test.com", "Why Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    with patch(
        "prachar_api.routers.performance.PerformanceEngine.explain",
        new_callable=AsyncMock,
        return_value=_fake_explanation(camp["id"]),
    ):
        res = await client.get(f"/performance/{camp['id']}/why", headers=headers)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["campaign_id"] == camp["id"]
    assert isinstance(body["likely_causes"], list)
    assert len(body["likely_causes"]) >= 1
    cause = body["likely_causes"][0]
    assert cause["cause"] == "creative_fatigue"
    assert cause["confidence"] in ("high", "medium", "low")
    assert isinstance(cause["evidence"], str) and cause["evidence"]


@pytest.mark.asyncio
async def test_get_why_404_for_nonexistent_campaign(client: AsyncClient):
    tok = await _register(client, f"wy404{uuid.uuid4().hex[:8]}@test.com", "Why 404 Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}

    with patch(
        "prachar_api.routers.performance.PerformanceEngine.explain",
        new_callable=AsyncMock,
    ) as mock_explain:
        res = await client.get(f"/performance/{uuid.uuid4()}/why", headers=headers)

    assert res.status_code == 404
    mock_explain.assert_not_called()


# ─── GET /{campaign_id}/next — recommendations (P4.5) ──────────────────────────


def _fake_recommendations(campaign_id: str):
    return {
        "campaign_id": campaign_id,
        "recommendations": [
            {
                "action": "Scale winning creative",
                "expected_impact": "ROAS is 5x; scaling should lift revenue.",
                "priority": "high",
            }
        ],
    }


@pytest.mark.asyncio
async def test_next_requires_auth(client: AsyncClient):
    res = await client.get(f"/performance/{uuid.uuid4()}/next")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_next_returns_200_with_recommendations(client: AsyncClient):
    tok = await _register(client, f"nx{uuid.uuid4().hex[:8]}@test.com", "Next Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    with patch(
        "prachar_api.routers.performance.PerformanceEngine.recommend",
        new_callable=AsyncMock,
        return_value=_fake_recommendations(camp["id"]),
    ):
        res = await client.get(f"/performance/{camp['id']}/next", headers=headers)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["campaign_id"] == camp["id"]
    assert isinstance(body["recommendations"], list)
    assert len(body["recommendations"]) >= 1
    rec = body["recommendations"][0]
    assert rec["action"] == "Scale winning creative"
    assert rec["priority"] in ("high", "medium", "low")
    assert isinstance(rec["expected_impact"], str) and rec["expected_impact"]


@pytest.mark.asyncio
async def test_get_next_404_for_nonexistent_campaign(client: AsyncClient):
    tok = await _register(client, f"nx404{uuid.uuid4().hex[:8]}@test.com", "Next 404 Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}

    with patch(
        "prachar_api.routers.performance.PerformanceEngine.recommend",
        new_callable=AsyncMock,
    ) as mock_recommend:
        res = await client.get(f"/performance/{uuid.uuid4()}/next", headers=headers)

    assert res.status_code == 404
    mock_recommend.assert_not_called()


# ─── GET /{campaign_id}/story — narrative story (A.5.1) ────────────────────────


def _fake_story(campaign_id: str):
    return {
        "campaign_id": campaign_id,
        "headline": "This week's campaign brought in 31 new enquiries — up 12 from last week.",
        "paragraphs": [
            "Over the last 14 days, your campaign reached 100,000 people and turned that into 200 enquiries.",
            "Instagram was your star performer, delivering 74% of enquiries.",
        ],
        "highlights": [
            {"metric": "New enquiries this week", "value": "31", "insight": "Up 12 from last week"},
            {"metric": "Revenue per ₹100 spent", "value": "₹300", "insight": "Every ₹100 you put in brings this back"},
        ],
        "platform_breakdown": [
            {"platform": "Instagram", "share": 0.74, "conversion_rate": 0.12, "conversions": 148},
            {"platform": "WhatsApp", "share": 0.26, "conversion_rate": 0.20, "conversions": 52},
        ],
        "time_insights": [
            {"period": "weekend_vs_weekday", "insight": "Weekend campaigns outperformed weekdays by 28%."},
        ],
    }


@pytest.mark.asyncio
async def test_story_requires_auth(client: AsyncClient):
    res = await client.get(f"/performance/{uuid.uuid4()}/story")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_story_returns_200_with_narrative(client: AsyncClient):
    tok = await _register(client, f"st{uuid.uuid4().hex[:8]}@test.com", "Story Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    with patch(
        "prachar_api.routers.performance.PerformanceEngine.tell_story",
        new_callable=AsyncMock,
        return_value=_fake_story(camp["id"]),
    ):
        res = await client.get(f"/performance/{camp['id']}/story", headers=headers)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["campaign_id"] == camp["id"]
    assert isinstance(body["headline"], str) and body["headline"]
    assert isinstance(body["paragraphs"], list) and len(body["paragraphs"]) >= 1
    assert isinstance(body["highlights"], list)
    assert isinstance(body["platform_breakdown"], list)
    assert isinstance(body["time_insights"], list)


@pytest.mark.asyncio
async def test_get_story_404_for_nonexistent_campaign(client: AsyncClient):
    tok = await _register(client, f"st404{uuid.uuid4().hex[:8]}@test.com", "Story 404 Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}

    with patch(
        "prachar_api.routers.performance.PerformanceEngine.tell_story",
        new_callable=AsyncMock,
    ) as mock_story:
        res = await client.get(f"/performance/{uuid.uuid4()}/story", headers=headers)

    assert res.status_code == 404
    mock_story.assert_not_called()
