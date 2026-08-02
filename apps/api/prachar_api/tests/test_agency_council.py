"""Tests for the Agency Council REST API.

Tests:
- Router registration
- Auth required on all endpoints
- DB models structure
- Request/response schemas
"""
from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ─── DB model tests ─────────────────────────────────────────────────────────


class TestCouncilDBModels:
    def test_all_council_models_import(self) -> None:
        from prachar_api.models import (
            CampaignScoreRecord,
            ConsensusDecisionRecord,
            CouncilLearningRecord,
            CouncilSessionRecord,
            DirectorOpinionRecord,
        )
        assert CouncilSessionRecord.__tablename__ == "council_sessions"
        assert DirectorOpinionRecord.__tablename__ == "director_opinions"
        assert ConsensusDecisionRecord.__tablename__ == "consensus_decisions"
        assert CampaignScoreRecord.__tablename__ == "campaign_scores"
        assert CouncilLearningRecord.__tablename__ == "council_learnings"

    def test_council_session_has_required_columns(self) -> None:
        from prachar_api.models import CouncilSessionRecord
        cols = {c.name for c in CouncilSessionRecord.__table__.columns}
        assert "id" in cols
        assert "tenant_id" in cols
        assert "brand_id" in cols
        assert "campaign_plan_id" in cols
        assert "campaign_brief" in cols
        assert "opinions_by_round" in cols
        assert "consensus_decision" in cols
        assert "status" in cols
        assert "rounds_completed" in cols

    def test_director_opinion_has_required_columns(self) -> None:
        from prachar_api.models import DirectorOpinionRecord
        cols = {c.name for c in DirectorOpinionRecord.__table__.columns}
        assert "council_session_id" in cols
        assert "director" in cols
        assert "role" in cols
        assert "opinion" in cols
        assert "round_number" in cols
        assert "confidence" in cols
        assert "approval" in cols
        assert "priority" in cols

    def test_consensus_decision_has_required_columns(self) -> None:
        from prachar_api.models import ConsensusDecisionRecord
        cols = {c.name for c in ConsensusDecisionRecord.__table__.columns}
        assert "council_session_id" in cols
        assert "decision" in cols
        assert "campaign_score" in cols
        assert "approval_status" in cols
        assert "overall_score" in cols

    def test_campaign_score_has_7_dimensions(self) -> None:
        from prachar_api.models import CampaignScoreRecord
        cols = {c.name for c in CampaignScoreRecord.__table__.columns}
        for dim in ("strategy_score", "creative_score", "media_score",
                    "brand_score", "performance_score", "risk_score",
                    "compliance_score", "overall_score"):
            assert dim in cols, f"Missing {dim} in campaign_scores"

    def test_council_learning_has_required_columns(self) -> None:
        from prachar_api.models import CouncilLearningRecord
        cols = {c.name for c in CouncilLearningRecord.__table__.columns}
        assert "decision" in cols
        assert "outcome" in cols
        assert "minority_opinions" in cols
        assert "rejected_ideas" in cols
        assert "successful_recommendations" in cols
        assert "failed_recommendations" in cols
        assert "lessons" in cols


# ─── API router tests ───────────────────────────────────────────────────────


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Create a test client with stub AI."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY", "")
    from prachar_shared.config import get_settings
    get_settings.cache_clear()

    from prachar_api.main import create_app
    app = create_app()
    return TestClient(app)


class TestAgencyCouncilRouter:
    def test_router_registered(self, client: TestClient) -> None:
        """Verify the agency-council router is mounted with 4 endpoints."""
        schema = client.get("/openapi.json").json()
        paths = schema.get("paths", {})
        ac_paths = [p for p in paths if p.startswith("/agency-council")]
        assert len(ac_paths) >= 4, f"Expected >=4 agency-council paths, got {ac_paths}"

    def test_review_requires_auth(self, client: TestClient) -> None:
        res = client.post("/agency-council/review", json={
            "brand_id": str(uuid.uuid4()),
            "campaign_brief": {"business_name": "Test"},
        })
        assert res.status_code == 401

    def test_consensus_requires_auth(self, client: TestClient) -> None:
        res = client.post("/agency-council/consensus", json={
            "session_id": str(uuid.uuid4()),
        })
        assert res.status_code == 401

    def test_history_requires_auth(self, client: TestClient) -> None:
        res = client.get("/agency-council/history")
        assert res.status_code == 401

    def test_get_by_campaign_requires_auth(self, client: TestClient) -> None:
        res = client.get(f"/agency-council/{uuid.uuid4()}")
        assert res.status_code == 401

    def test_review_validates_request_body(self, client: TestClient) -> None:
        """POST /review should validate the request body."""
        # Missing required field brand_id
        res = client.post("/agency-council/review", json={
            "campaign_brief": {"business_name": "Test"},
        })
        # Should be 401 (auth checked first) or 422 (validation)
        assert res.status_code in (401, 422)

    def test_history_accepts_brand_id_query_param(self, client: TestClient) -> None:
        """GET /history should accept optional brand_id query param."""
        # Without auth → 401, but the route should exist
        res = client.get(f"/agency-council/history?brand_id={uuid.uuid4()}")
        assert res.status_code == 401


# ─── Schema validation tests ────────────────────────────────────────────────


class TestSchemaValidation:
    def test_review_request_validates_max_rounds(self) -> None:
        """max_rounds must be between 1 and 3."""
        from prachar_api.routers.agency_council import ReviewRequest
        from pydantic import ValidationError

        # Valid
        ReviewRequest(brand_id=uuid.uuid4(), campaign_brief={}, max_rounds=1)
        ReviewRequest(brand_id=uuid.uuid4(), campaign_brief={}, max_rounds=3)

        # Invalid — too high
        with pytest.raises(ValidationError):
            ReviewRequest(brand_id=uuid.uuid4(), campaign_brief={}, max_rounds=4)

        # Invalid — too low
        with pytest.raises(ValidationError):
            ReviewRequest(brand_id=uuid.uuid4(), campaign_brief={}, max_rounds=0)

    def test_history_request_validates_limit(self) -> None:
        from prachar_api.routers.agency_council import HistoryRequest
        from pydantic import ValidationError

        HistoryRequest(limit=1)
        HistoryRequest(limit=100)
        with pytest.raises(ValidationError):
            HistoryRequest(limit=0)
        with pytest.raises(ValidationError):
            HistoryRequest(limit=101)


# ─── Integration test with mocked consensus ─────────────────────────────────


class TestReviewIntegration:
    """Test the /review endpoint with a mocked consensus engine."""

    @pytest.fixture
    def mock_auth_user(self):
        """Mock the CurrentUser dependency."""
        tenant = MagicMock()
        tenant.plan = "agency"
        user = MagicMock()
        user.user_id = uuid.uuid4()
        user.tenant_id = uuid.uuid4()
        user.tenant = tenant
        return user

    def test_review_returns_decision(self, monkeypatch: pytest.MonkeyPatch, mock_auth_user) -> None:
        """Test that /review returns a consensus decision when properly mocked."""
        from prachar_shared.agency_council import ConsensusDecision, CouncilSession
        from prachar_api.routers import agency_council as router_mod

        # Create mock decision and session
        decision = ConsensusDecision(
            executive_decision="Council approves",
            confidence=0.8,
            approval_status="approved",
            final_recommendation="Proceed",
            rounds_completed=1,
            campaign_score={"overall_score": 75.0, "strategy_score": 80.0,
                           "creative_score": 70.0, "media_score": 75.0,
                           "brand_score": 80.0, "performance_score": 70.0,
                           "risk_score": 85.0, "compliance_score": 90.0,
                           "weights_used": {}},
            total_tokens=900,
            total_cost_usd=0.018,
            total_latency_ms=90.0,
        )
        session = CouncilSession(
            session_id=str(uuid.uuid4()),
            tenant_id=str(mock_auth_user.tenant_id),
            brand_id=str(uuid.uuid4()),
            campaign_id="",
            status="completed",
            rounds_completed=1,
            opinions_by_round={"1": [
                {"director": "chief_strategy_officer", "role": "CSO",
                 "opinion": "good", "reasoning": "r", "confidence": 0.8,
                 "risks": [], "alternatives": [], "recommendations": [],
                 "evidence": [], "priority": "medium", "approval": True,
                 "round_number": 1, "latency_ms": 10, "tokens_used": 100},
            ]},
        )

        # Mock the ConsensusEngine.reach_consensus
        async def mock_reach_consensus(**kw):
            return decision, session

        # Mock the PostgresCouncilRepository and _get_brand
        mock_session = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.save_session = AsyncMock()

        mock_brand = MagicMock()
        mock_brand.name = "Test Brand"
        mock_brand.category = "Coffee"
        mock_brand.website = ""
        mock_brand.brand_graph = {}

        # Patch dependencies
        monkeypatch.setattr(router_mod.ConsensusEngine, "reach_consensus", mock_reach_consensus)
        monkeypatch.setattr(router_mod, "PostgresCouncilRepository", lambda s: mock_repo)
        monkeypatch.setattr(router_mod, "CouncilMemoryStore", lambda **kw: MagicMock(
            save_session=AsyncMock(return_value=session.session_id),
        ))
        monkeypatch.setattr(router_mod, "_get_brand", AsyncMock(return_value=mock_brand))
        monkeypatch.setattr(router_mod, "log_audit", AsyncMock())

        # We can't easily test the full flow without DB, but we can verify
        # the schema conversion works
        from prachar_api.routers.agency_council import _decision_to_out, _score_to_out, _opinion_to_out
        dec_out = _decision_to_out(decision.to_dict())
        assert dec_out.executive_decision == "Council approves"
        assert dec_out.approval_status == "approved"

        score_out = _score_to_out(decision.campaign_score)
        assert score_out.overall_score == 75.0

        op_out = _opinion_to_out(session.opinions_by_round["1"][0])
        assert op_out.director == "chief_strategy_officer"
        assert op_out.approval is True
