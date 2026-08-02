"""Tests for the Campaign Brain REST API router and DB models.

Uses FastAPI TestClient with stub-mode AI (no API keys needed).
"""
from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ─── DB model tests (no DB needed — just class structure) ───────────────────


class TestDBModels:
    def test_all_models_import(self) -> None:
        from prachar_api.models import (
            AudienceProfileRecord,
            BusinessMemoryRecord,
            BusinessProfileRecord,
            CampaignPlanRecord,
            CompetitorProfileRecord,
            CreativeDirectionRecord,
            ExecutionPlanRecord,
            LearningReportRecord,
            MarketingStrategyRecord,
            MediaPlanRecord,
        )
        assert BusinessMemoryRecord.__tablename__ == "business_memories"
        assert BusinessProfileRecord.__tablename__ == "business_profiles"
        assert AudienceProfileRecord.__tablename__ == "audience_profiles"
        assert CompetitorProfileRecord.__tablename__ == "competitor_profiles"
        assert MarketingStrategyRecord.__tablename__ == "marketing_strategies"
        assert CreativeDirectionRecord.__tablename__ == "creative_directions"
        assert MediaPlanRecord.__tablename__ == "media_plans"
        assert CampaignPlanRecord.__tablename__ == "campaign_plans"
        assert ExecutionPlanRecord.__tablename__ == "execution_plans"
        assert LearningReportRecord.__tablename__ == "learning_reports"

    def test_campaign_plan_has_required_columns(self) -> None:
        from prachar_api.models import CampaignPlanRecord
        cols = {c.name for c in CampaignPlanRecord.__table__.columns}
        assert "id" in cols
        assert "tenant_id" in cols
        assert "brand_id" in cols
        assert "name" in cols
        assert "goal" in cols
        assert "campaign" in cols
        assert "overall_confidence" in cols
        assert "status" in cols


# ─── API router tests (stub mode — no real AI calls) ────────────────────────


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Create a test client with stub AI and mocked DB session."""
    # No API keys → stub mode
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY", "")
    from prachar_shared.config import get_settings
    get_settings.cache_clear()

    from prachar_api.main import create_app
    app = create_app()
    return TestClient(app)


@pytest.fixture
def auth_headers(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Register + login to get auth token."""
    # Mock the DB session for auth
    # Use a unique email per test run
    email = f"test_{uuid.uuid4().hex[:8]}@test.com"
    # We need to mock the DB — use the real test DB if available, else mock
    # For simplicity, we'll test the router logic without full DB
    # by mocking the session dependency
    return {}


class TestCampaignBrainRouter:
    def test_router_registered(self, client: TestClient) -> None:
        """Verify the campaign-brain router is mounted."""
        # The OpenAPI schema should include campaign-brain endpoints
        schema = client.get("/openapi.json").json()
        paths = schema.get("paths", {})
        cb_paths = [p for p in paths if p.startswith("/campaign-brain")]
        assert len(cb_paths) >= 6, f"Expected >=6 campaign-brain paths, got {cb_paths}"

    def test_full_campaign_endpoint_requires_auth(self, client: TestClient) -> None:
        """POST /campaign-brain/full-campaign should require auth."""
        res = client.post("/campaign-brain/full-campaign", json={
            "brand_id": str(uuid.uuid4()),
            "goal": "increase sales",
        })
        assert res.status_code == 401  # Unauthorized — no token

    def test_analyse_endpoint_requires_auth(self, client: TestClient) -> None:
        res = client.post("/campaign-brain/analyse", json={
            "brand_id": str(uuid.uuid4()),
        })
        assert res.status_code == 401

    def test_strategy_endpoint_requires_auth(self, client: TestClient) -> None:
        res = client.post("/campaign-brain/strategy", json={
            "brand_id": str(uuid.uuid4()),
            "goal": "grow",
        })
        assert res.status_code == 401

    def test_creative_direction_requires_auth(self, client: TestClient) -> None:
        res = client.post("/campaign-brain/creative-direction", json={
            "brand_id": str(uuid.uuid4()),
        })
        assert res.status_code == 401

    def test_media_plan_requires_auth(self, client: TestClient) -> None:
        res = client.post("/campaign-brain/media-plan", json={
            "brand_id": str(uuid.uuid4()),
        })
        assert res.status_code == 401

    def test_execution_plan_requires_auth(self, client: TestClient) -> None:
        res = client.post("/campaign-brain/execution-plan", json={
            "brand_id": str(uuid.uuid4()),
        })
        assert res.status_code == 401

    def test_list_plans_requires_auth(self, client: TestClient) -> None:
        res = client.get("/campaign-brain/plans")
        assert res.status_code == 401

    def test_get_plan_requires_auth(self, client: TestClient) -> None:
        res = client.get(f"/campaign-brain/plans/{uuid.uuid4()}")
        assert res.status_code == 401

    def test_learn_requires_auth(self, client: TestClient) -> None:
        res = client.post(f"/campaign-brain/{uuid.uuid4()}/learn", json={
            "performance_data": {},
        })
        assert res.status_code == 401


# ─── Request/Response schema tests ──────────────────────────────────────────


class TestSchemas:
    def test_full_campaign_request_validates(self) -> None:
        from prachar_api.routers.campaign_brain import FullCampaignRequest
        req = FullCampaignRequest(
            brand_id=uuid.uuid4(),
            goal="increase sales by 30%",
            budget="₹5,00,000",
        )
        assert req.goal == "increase sales by 30%"
        assert req.save is True  # default
        assert req.locale == "en-IN"

    def test_full_campaign_request_requires_brand_id(self) -> None:
        from pydantic import ValidationError
        from prachar_api.routers.campaign_brain import FullCampaignRequest
        with pytest.raises(ValidationError):
            FullCampaignRequest(goal="test")  # missing brand_id

    def test_analyse_request_defaults(self) -> None:
        from prachar_api.routers.campaign_brain import AnalyseRequest
        req = AnalyseRequest(brand_id=uuid.uuid4())
        assert req.goal == ""
        assert req.locale == "en-IN"

    def test_full_campaign_out_schema(self) -> None:
        from prachar_api.routers.campaign_brain import FullCampaignOut
        out = FullCampaignOut(
            business_profile={},
            audience_profile={},
            competitor_profile={},
            marketing_objective={},
            campaign_strategy={},
            creative_direction={},
            media_plan={},
            budget_estimate={},
            execution_plan={},
            engine_outputs={},
            overall_confidence=0.7,
            total_cost_usd=0.009,
            total_latency_ms=45.0,
            total_tokens=900,
            executive_summary="Test",
            risk_assessment=[],
        )
        assert out.overall_confidence == 0.7
        assert out.total_tokens == 900
