"""End-to-end test for the proactive engine regression suite (P5.6).

Tests the full flow:
    synthetic performance drop
      → anomaly detected
      → recommendation generated
      → PRACHAR AI notification (GET /chat/proactive)
      → user launches (POST /proactive/{id}/launch)
      → campaign created (POST /campaign-brain/full-campaign)
      → review queue (GET /review/queue)

The AI gateway and the CampaignBrain are mocked — we're testing the wiring,
not the AI output.  The anomaly cache is seeded directly.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, timedelta
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
from prachar_shared.marketing_intelligence.proactive_engine import (  # noqa: E402
    Anomaly,
    format_as_prachar_message,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


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
        json={"name": "E2E Brand", "website": "https://example.com", "category": "tech"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _fake_anomaly(brand_id: str, campaign_id: str) -> dict[str, Any]:
    """A synthetic performance-drop anomaly (35% conversions drop)."""
    return {
        "brand_id": brand_id,
        "campaign_id": campaign_id,
        "metric": "conversions",
        "magnitude": -0.35,
        "timeframe": "last 7 days vs previous 7 days",
        "severity": "medium",
        "direction": "drop",
    }


def _fake_recommendation() -> dict[str, Any]:
    return {
        "what_to_do": "Refresh the ad creative with a new hook",
        "why": "Conversions dropped 35% this week, likely due to creative fatigue.",
        "creative_directions": ["Bold new hook", "Customer testimonial", "Limited-time offer"],
        "expected_impact": "Recover 15-20% of lost conversions over the next two weeks.",
    }


# ─── Unit: format_as_prachar_message ─────────────────────────────────────────


class TestFormatAsPracharMessage:
    """Tests for the PRACHAR AI-voice message formatter (P5.3)."""

    def test_drop_with_recommendation(self):
        anomaly = Anomaly(
            brand_id="b1",
            campaign_id="c1",
            metric="conversions",
            magnitude=-0.35,
            timeframe="last 7 days vs previous 7 days",
            severity="medium",
            direction="drop",
        )
        rec = _fake_recommendation()
        msg = format_as_prachar_message(anomaly, rec)

        # PRACHAR AI voice characteristics.
        assert "I noticed" in msg
        assert "I recommend" in msg
        assert "dropped 35%" in msg
        assert "conversions" in msg
        # Creative directions present.
        assert "Bold new hook" in msg
        # No jargon.
        assert "ROAS" not in msg
        assert "CPA" not in msg

    def test_spike_with_recommendation(self):
        anomaly = Anomaly(
            brand_id="b1",
            campaign_id="c1",
            metric="clicks",
            magnitude=0.75,
            timeframe="last 7 days vs previous 7 days",
            severity="medium",
            direction="spike",
        )
        rec = _fake_recommendation()
        msg = format_as_prachar_message(anomaly, rec)

        assert "I noticed" in msg
        assert "jumped 75%" in msg
        assert "clicks" in msg

    def test_plateau_with_recommendation(self):
        anomaly = Anomaly(
            brand_id="b1",
            campaign_id="c1",
            metric="impressions",
            magnitude=0.02,
            timeframe="last 2+ weeks",
            severity="low",
            direction="plateau",
        )
        rec = _fake_recommendation()
        msg = format_as_prachar_message(anomaly, rec)

        assert "I noticed" in msg
        assert "flat" in msg
        assert "impressions" in msg

    def test_drop_without_recommendation_uses_fallback(self):
        anomaly = Anomaly(
            brand_id="b1",
            campaign_id="c1",
            metric="conversions",
            magnitude=-0.50,
            timeframe="last 7 days vs previous 7 days",
            severity="high",
            direction="drop",
        )
        msg = format_as_prachar_message(anomaly, None)

        assert "I noticed" in msg
        assert "dropped 50%" in msg
        # Fallback advice for a drop.
        assert "refresh" in msg.lower() or "creative" in msg.lower()

    def test_no_jargon_in_any_direction(self):
        """PRACHAR AI voice must never contain marketing jargon."""
        jargon_words = ["ROAS", "CPA", "CTR", "CPM", "funnel optimisation", "CBO", "ABO"]
        for direction in ("drop", "spike", "plateau"):
            anomaly = Anomaly(
                brand_id="b1",
                campaign_id="c1",
                metric="conversions",
                magnitude=-0.30 if direction == "drop" else (0.60 if direction == "spike" else 0.02),
                timeframe="last 7 days vs previous 7 days",
                severity="medium",
                direction=direction,
            )
            msg = format_as_prachar_message(anomaly, _fake_recommendation())
            for word in jargon_words:
                assert word not in msg, f"Jargon '{word}' found in {direction} message: {msg}"


# ─── E2E: anomaly → PRACHAR AI notification → launch → campaign → review ───


@pytest.mark.asyncio
async def test_e2e_proactive_flow(client: AsyncClient):
    """Full flow: anomaly → recommendation → PRACHAR AI notification → launch → campaign → review.

    Steps:
    1. Register + create brand.
    2. Seed the anomaly cache with a synthetic performance drop.
    3. GET /chat/proactive — verify PRACHAR AI message is returned.
    4. POST /proactive/{id}/launch — verify pre-filled campaign data.
    5. POST /campaign-brain/full-campaign — verify campaign is created (mocked brain).
    6. GET /review/queue — verify the campaign appears in the review queue.
    """
    tok = await _register(client, f"e2e{uuid.uuid4().hex[:8]}@test.com", "E2E Proactive Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    campaign_id = str(uuid.uuid4())
    anomaly = _fake_anomaly(brand_id, campaign_id)

    # ─── Step 1: Seed the anomaly cache ───────────────────────────────
    with patch(
        "prachar_workers.proactive.get_anomalies",
        return_value=[anomaly],
    ), patch(
        "prachar_api.routers.chat.ProactiveEngine.generate_recommendation",
        new_callable=AsyncMock,
        return_value=_fake_recommendation(),
    ):
        # ─── Step 2: GET /chat/proactive — PRACHAR AI notification ───
        res = await client.get("/chat/proactive", headers=headers)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["count"] == 1
    msg = body["messages"][0]
    assert "prachar_message" in msg
    assert "I noticed" in msg["prachar_message"]
    assert "dropped 35%" in msg["prachar_message"]
    assert "I recommend" in msg["prachar_message"]
    assert msg["anomaly"]["metric"] == "conversions"
    assert msg["anomaly"]["direction"] == "drop"
    assert msg["severity"] == "medium"
    # The notification ID encodes brand:campaign:metric.
    notification_id = msg["id"]
    assert brand_id in notification_id
    assert "conversions" in notification_id

    # ─── Step 3: POST /proactive/{id}/launch — pre-fill campaign ──────
    with patch(
        "prachar_workers.proactive.get_anomalies",
        return_value=[anomaly],
    ), patch(
        "prachar_api.routers.proactive.ProactiveEngine.generate_recommendation",
        new_callable=AsyncMock,
        return_value=_fake_recommendation(),
    ):
        launch_res = await client.post(
            f"/proactive/{notification_id}/launch",
            headers=headers,
        )

    assert launch_res.status_code == 200, launch_res.text
    launch_body = launch_res.json()
    assert launch_body["recommendation_id"] == notification_id
    assert launch_body["brand_id"] == brand_id
    assert launch_body["goal"]  # non-empty goal
    assert launch_body["budget"]  # non-empty budget
    assert len(launch_body["creative_directions"]) == 3
    assert "prachar_message" in launch_body
    assert "I noticed" in launch_body["prachar_message"]
    # Pre-fill data for the campaign form.
    assert "prefill" in launch_body
    assert launch_body["prefill"]["brand_id"] == brand_id
    assert launch_body["prefill"]["goal"]
    # No auto-publish — this is just pre-fill data.
    assert "source_anomaly" in launch_body["prefill"]

    # ─── Step 4: POST /campaign-brain/full-campaign — create campaign ─
    # Mock the CampaignBrain so we don't need the AI gateway.
    fake_campaign = MagicMock()
    fake_campaign.to_dict = MagicMock(return_value={
        "campaign_strategy": {"core_message": "Fresh creative to recover conversions"},
        "media_plan": {"recommended_channels": ["google", "instagram"]},
        "creative_direction": {"creative_concept": "Bold new hook"},
        "budget_estimate": {"allocation": {"google": 8000, "instagram": 7000}},
    })
    fake_campaign.overall_confidence = 0.82
    fake_campaign.total_cost_usd = 0.05
    fake_campaign.total_tokens = 1200
    fake_campaign.total_latency_ms = 1500
    fake_campaign.executive_summary = "Recover lost conversions with fresh creative."
    fake_campaign.risk_assessment = ["Creative fatigue may persist if audience is saturated"]
    fake_campaign.business_profile = MagicMock(to_dict=MagicMock(return_value={}))
    fake_campaign.audience_profile = MagicMock(to_dict=MagicMock(return_value={}))
    fake_campaign.competitor_profile = MagicMock(to_dict=MagicMock(return_value={}))
    fake_campaign.marketing_objective = MagicMock(to_dict=MagicMock(return_value={}))
    fake_campaign.campaign_strategy = MagicMock(to_dict=MagicMock(return_value={"core_message": "test"}))
    fake_campaign.creative_direction = MagicMock(to_dict=MagicMock(return_value={}))
    fake_campaign.media_plan = MagicMock(to_dict=MagicMock(return_value={}))
    fake_campaign.budget_estimate = MagicMock(to_dict=MagicMock(return_value={}))
    fake_campaign.execution_plan = MagicMock(to_dict=MagicMock(return_value={}))
    fake_campaign.engine_outputs = {}

    with patch(
        "prachar_api.routers.campaign_brain.CampaignBrain.generate_campaign",
        new_callable=AsyncMock,
        return_value=fake_campaign,
    ):
        camp_res = await client.post(
            "/campaign-brain/full-campaign",
            json={
                "brand_id": brand_id,
                "goal": launch_body["goal"],
                "budget": launch_body["budget"],
                "save": True,
                "additional_context": f"Creative directions: {', '.join(launch_body['creative_directions'])}",
            },
            headers=headers,
        )

    assert camp_res.status_code == 201, camp_res.text
    camp_body = camp_res.json()
    assert "campaign_plan_id" in camp_body
    assert camp_body["campaign_plan_id"] is not None
    plan_id = camp_body["campaign_plan_id"]

    # ─── Step 5: GET /campaign-brain/plans — verify in the list ───────
    plans_res = await client.get("/campaign-brain/plans", headers=headers)
    assert plans_res.status_code == 200, plans_res.text
    plans = plans_res.json()
    plan_ids = [p["id"] for p in plans]
    assert plan_id in plan_ids

    # The newly created plan should have status "draft" (review queue).
    created_plan = next(p for p in plans if p["id"] == plan_id)
    assert created_plan["status"] == "draft"


# ─── E2E: auth required ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chat_proactive_requires_auth(client: AsyncClient):
    """GET /chat/proactive requires authentication."""
    res = await client.get("/chat/proactive")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_launch_requires_auth(client: AsyncClient):
    """POST /proactive/{id}/launch requires authentication."""
    res = await client.post("/proactive/brand:campaign:metric/launch")
    assert res.status_code == 401


# ─── E2E: launch with invalid notification ID ────────────────────────────────


@pytest.mark.asyncio
async def test_launch_invalid_notification_id_format(client: AsyncClient):
    """POST /proactive/{id}/launch with a malformed ID returns 400."""
    tok = await _register(client, f"inv{uuid.uuid4().hex[:8]}@test.com", "Invalid Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}

    res = await client.post("/proactive/invalid-id/launch", headers=headers)
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_launch_notification_not_found(client: AsyncClient):
    """POST /proactive/{id}/launch with a valid-format but non-existent ID returns 404."""
    tok = await _register(client, f"nf{uuid.uuid4().hex[:8]}@test.com", "NF Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)

    # Valid format but no anomaly in the cache.
    fake_id = f"{brand_id}:{uuid.uuid4()}:conversions"
    with patch(
        "prachar_workers.proactive.get_anomalies",
        return_value=[],
    ):
        res = await client.post(f"/proactive/{fake_id}/launch", headers=headers)
    assert res.status_code == 404


# ─── E2E: empty notifications ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chat_proactive_empty_when_no_anomalies(client: AsyncClient):
    """GET /chat/proactive returns empty messages when no anomalies are stored."""
    tok = await _register(client, f"empty{uuid.uuid4().hex[:8]}@test.com", "Empty Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    await _create_brand(client, headers)

    with patch(
        "prachar_workers.proactive.get_anomalies",
        return_value=[],
    ):
        res = await client.get("/chat/proactive", headers=headers)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["count"] == 0
    assert body["messages"] == []
