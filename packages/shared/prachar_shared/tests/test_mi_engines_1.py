"""Tests for Audience, Competitor, and Objective engines."""
from __future__ import annotations

import uuid
from typing import Any

import pytest

from prachar_shared.ai_gateway import Completion
from prachar_shared.marketing_intelligence import (
    AudienceIntelligenceEngine,
    AudienceProfile,
    CompetitorIntelligenceEngine,
    CompetitorProfile,
    MarketingObjective,
    MarketingObjectiveEngine,
)


class _StubGateway:
    def __init__(self, json_value: dict[str, Any]) -> None:
        self._json = json_value

    def complete(self, **kw: Any) -> Completion:
        return Completion(
            text="[stub]",
            json_value=self._json,
            tokens_used=100,
            model="stub",
            provider="stub",
            latency_ms=5.0,
            cost_usd=0.001,
            request_id="req-test",
            confidence=0.7,
        )


# ─── Audience Intelligence Engine ───────────────────────────────────────────


class TestAudienceIntelligenceEngine:
    def _result(self) -> dict[str, Any]:
        return {
            "primary_audience": {
                "description": "Urban millennials",
                "age_range": "25-34",
                "gender": "all",
                "income_bracket": "₹8-15L PA",
                "buying_intent": "high",
            },
            "secondary_audience": {"description": "Gen Z early adopters", "buying_intent": "medium"},
            "buying_intent": "high",
            "pain_points": ["No time to brew", "Inconsistent quality"],
            "demographics": {"primary_age": "25-34"},
            "psychographics": {"values": ["quality", "sustainability"]},
            "language_preference": ["en-IN", "hi-IN"],
            "platforms": ["instagram", "youtube"],
            "content_preferences": ["video", "carousel"],
            "buying_journey": [{"stage": "awareness", "touchpoints": ["Instagram ads"]}],
            "reasoning": "Analyzed business + market",
            "confidence": 0.8,
            "recommendations": [],
        }

    def test_engine_name(self) -> None:
        assert AudienceIntelligenceEngine.ENGINE_NAME == "audience_intelligence"

    def test_build_prompt_contains_business_profile(self) -> None:
        engine = AudienceIntelligenceEngine()
        prompt = engine._build_prompt(
            business_profile={"industry": "Coffee"},
            business_name="Acme",
            goal="increase sales",
            locale="en-IN",
        )
        assert "Acme" in prompt
        assert "Coffee" in prompt
        assert "increase sales" in prompt

    def test_schema_has_required_fields(self) -> None:
        schema = AudienceIntelligenceEngine().build_schema() if hasattr(AudienceIntelligenceEngine, "build_schema") else AudienceIntelligenceEngine()._build_schema()
        assert "primary_audience" in schema["required"]
        assert "buying_intent" in schema["required"]

    def test_run_returns_output(self) -> None:
        gw = _StubGateway(self._result())
        engine = AudienceIntelligenceEngine(gateway=gw)
        out = engine.run(tenant_id=uuid.uuid4(), plan="agency", business_profile={}, business_name="Acme")
        assert out.result["buying_intent"] == "high"
        assert out.confidence == 0.8

    def test_to_profile(self) -> None:
        gw = _StubGateway(self._result())
        engine = AudienceIntelligenceEngine(gateway=gw)
        out = engine.run(tenant_id=uuid.uuid4(), plan="agency", business_profile={})
        profile = engine.to_profile(out)
        assert isinstance(profile, AudienceProfile)
        assert profile.buying_intent == "high"
        assert "instagram" in profile.platforms
        assert len(profile.pain_points) == 2

    def test_to_profile_empty(self) -> None:
        from prachar_shared.marketing_intelligence.base import EngineOutput
        profile = AudienceIntelligenceEngine().to_profile(EngineOutput(result={}))
        assert profile.platforms == []
        assert profile.pain_points == []


# ─── Competitor Intelligence Engine ─────────────────────────────────────────


class TestCompetitorIntelligenceEngine:
    def _result(self) -> dict[str, Any]:
        return {
            "competitors": [
                {
                    "name": "Blue Tokai",
                    "market_position": "leader",
                    "messaging_strategy": "Direct trade, Indian specialty",
                    "strengths": ["Brand recognition"],
                    "weaknesses": ["Premium pricing"],
                }
            ],
            "market_gaps": ["Affordable subscription", "Tier-2 city presence"],
            "swot_comparison": {"our_strengths": ["Agility"]},
            "positioning_map": {"x_axis": "price", "y_axis": "quality"},
            "messaging_analysis": {"common_themes": ["direct trade"], "white_space": ["convenience"]},
            "pricing_comparison": {"our_position": "mid-premium"},
            "reasoning": "Analyzed 3 competitors",
            "confidence": 0.65,
            "recommendations": [],
        }

    def test_engine_name(self) -> None:
        assert CompetitorIntelligenceEngine.ENGINE_NAME == "competitor_intelligence"

    def test_build_prompt(self) -> None:
        engine = CompetitorIntelligenceEngine()
        prompt = engine._build_prompt(
            business_profile={"industry": "Coffee"},
            business_name="Acme",
            industry="Coffee",
            known_competitors=["Blue Tokai"],
        )
        assert "Acme" in prompt
        assert "Blue Tokai" in prompt

    def test_run_and_to_profile(self) -> None:
        gw = _StubGateway(self._result())
        engine = CompetitorIntelligenceEngine(gateway=gw)
        out = engine.run(tenant_id=uuid.uuid4(), plan="agency", business_name="Acme")
        assert out.confidence == 0.65
        profile = engine.to_profile(out)
        assert isinstance(profile, CompetitorProfile)
        assert len(profile.competitors) == 1
        assert profile.competitors[0]["name"] == "Blue Tokai"
        assert len(profile.market_gaps) == 2


# ─── Marketing Objective Engine ─────────────────────────────────────────────


class TestMarketingObjectiveEngine:
    def _result(self) -> dict[str, Any]:
        return {
            "objective_type": "increase_sales",
            "description": "Increase online sales by 30% in Q3",
            "kpis": [
                {"metric": "Revenue", "target": "₹50L", "measurement_method": "GA4", "benchmark": "₹38L"},
                {"metric": "Conversion Rate", "target": "2.5%", "measurement_method": "Pixel", "benchmark": "1.8%"},
            ],
            "target_metrics": {"expected_reach": "5M", "expected_roas": "4x"},
            "timeline": "3 months",
            "success_criteria": "₹50L revenue with 4x ROAS",
            "funnel_stage": "conversion",
            "reasoning": "Based on business maturity and budget",
            "confidence": 0.85,
            "recommendations": [],
        }

    def test_engine_name(self) -> None:
        assert MarketingObjectiveEngine.ENGINE_NAME == "marketing_objective"

    def test_build_prompt_contains_user_request(self) -> None:
        engine = MarketingObjectiveEngine()
        prompt = engine._build_prompt(
            user_request="increase sales by 30%",
            business_profile={"industry": "Coffee"},
            audience_profile={"buying_intent": "high"},
            budget="₹5,00,000",
        )
        assert "increase sales by 30%" in prompt
        assert "₹5,00,000" in prompt

    def test_run_and_to_objective(self) -> None:
        gw = _StubGateway(self._result())
        engine = MarketingObjectiveEngine(gateway=gw)
        out = engine.run(
            tenant_id=uuid.uuid4(),
            plan="agency",
            user_request="increase sales",
            business_profile={},
            audience_profile={},
        )
        assert out.result["objective_type"] == "increase_sales"
        assert out.confidence == 0.85
        obj = engine.to_objective(out)
        assert isinstance(obj, MarketingObjective)
        assert obj.objective_type == "increase_sales"
        assert len(obj.kpis) == 2
        assert obj.funnel_stage == "conversion"

    def test_to_objective_empty(self) -> None:
        from prachar_shared.marketing_intelligence.base import EngineOutput
        obj = MarketingObjectiveEngine().to_objective(EngineOutput(result={}))
        assert obj.objective_type == ""
        assert obj.kpis == []
