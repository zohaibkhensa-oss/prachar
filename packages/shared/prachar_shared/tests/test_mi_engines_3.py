"""Tests for Budget Intelligence, Execution Planner, and Learning engines."""
from __future__ import annotations

import uuid
from typing import Any

import pytest

from prachar_shared.ai_gateway import Completion
from prachar_shared.marketing_intelligence import (
    BudgetEstimate,
    BudgetIntelligenceEngine,
    ExecutionPlan,
    ExecutionPlanner,
    LearningEngine,
    LearningReport,
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


# ─── Budget Intelligence Engine ─────────────────────────────────────────────


class TestBudgetIntelligenceEngine:
    def _result(self) -> dict[str, Any]:
        return {
            "creative_cost": {"ai_generated": "₹15,000", "custom_design": "₹25,000", "total": "₹40,000"},
            "ai_cost": {"content_generation": "₹2,000", "total": "₹3,000"},
            "advertising_cost": {"total": "₹3,00,000", "per_channel": [{"channel": "Instagram", "cost": "₹1,50,000"}]},
            "agency_cost": {"strategy": "₹20,000", "total": "₹50,000"},
            "total_cost": {"amount": "₹3,93,000", "currency": "INR", "breakdown_percentage": {"advertising": 76}},
            "roi_projection": {"expected_revenue": "₹15,00,000", "expected_roas": "3.8x", "payback_period": "2 months"},
            "cac_estimate": {"estimated_cac": "₹800", "ltv_comparison": "LTV ₹4,000", "viability": "Viable"},
            "expected_reach": "2M",
            "expected_engagement": "5% CTR",
            "expected_conversion": "1.5%",
            "break_even_analysis": "Need 750 sales at ₹2,000 AOV",
            "cost_breakdown": [{"item": "Instagram ads", "cost": "₹1,50,000", "notes": "Primary channel"}],
            "reasoning": "Based on market rates and campaign scope",
            "confidence": 0.6,
            "recommendations": [],
        }

    def test_engine_name(self) -> None:
        assert BudgetIntelligenceEngine.ENGINE_NAME == "budget_intelligence"

    def test_low_temperature_for_financial(self) -> None:
        assert BudgetIntelligenceEngine.TEMPERATURE == 0.2

    def test_build_prompt_contains_currency(self) -> None:
        engine = BudgetIntelligenceEngine()
        prompt = engine._build_prompt(
            business_profile={},
            audience_profile={},
            objective={},
            campaign_strategy={},
            media_plan={},
            budget="₹5L",
            currency="INR",
        )
        assert "INR" in prompt
        assert "₹5L" in prompt

    def test_run_and_to_estimate(self) -> None:
        gw = _StubGateway(self._result())
        engine = BudgetIntelligenceEngine(gateway=gw)
        out = engine.run(tenant_id=uuid.uuid4(), plan="agency", business_profile={})
        assert out.confidence == 0.6
        est = engine.to_estimate(out)
        assert isinstance(est, BudgetEstimate)
        assert est.total_cost["amount"] == "₹3,93,000"
        assert est.roi_projection["expected_roas"] == "3.8x"
        assert est.cac_estimate["estimated_cac"] == "₹800"


# ─── Execution Planner ──────────────────────────────────────────────────────


class TestExecutionPlanner:
    def _result(self) -> dict[str, Any]:
        return {
            "phases": [
                {"phase": "Strategy", "description": "Finalize strategy", "duration_days": 2, "start_after": "now"},
                {"phase": "Creative", "description": "Produce assets", "duration_days": 7, "start_after": "Strategy"},
            ],
            "tasks": [
                {"task": "Generate images", "phase": "Creative", "description": "10 product shots", "duration_hours": 4, "assigned_to": "AI", "dependencies": ["Strategy"], "deliverable": "10 images"},
            ],
            "timeline": {"total_duration_days": 30, "critical_path": "Strategy → Creative → Publishing"},
            "dependencies": [{"task": "Creative", "depends_on": "Strategy", "type": "hard"}],
            "approval_checklist": ["Brand guidelines check", "Claims gate review"],
            "ai_asset_requirements": [{"asset_type": "image", "count": 10, "specifications": "1080x1080", "channel": "Instagram", "priority": "high"}],
            "risk_mitigation": [{"risk": "AI quality issues", "probability": "medium", "impact": "high", "mitigation": "Human review"}],
            "reasoning": "Sequenced for dependency efficiency",
            "confidence": 0.8,
            "recommendations": [],
        }

    def test_engine_name(self) -> None:
        assert ExecutionPlanner.ENGINE_NAME == "execution_planner"

    def test_low_temperature_for_planning(self) -> None:
        assert ExecutionPlanner.TEMPERATURE == 0.2

    def test_run_and_to_plan(self) -> None:
        gw = _StubGateway(self._result())
        engine = ExecutionPlanner(gateway=gw)
        out = engine.run(tenant_id=uuid.uuid4(), plan="agency", campaign_strategy={})
        assert out.confidence == 0.8
        plan = engine.to_plan(out)
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.phases) == 2
        assert plan.phases[0]["phase"] == "Strategy"
        assert len(plan.tasks) == 1
        assert len(plan.approval_checklist) == 2
        assert len(plan.ai_asset_requirements) == 1


# ─── Learning Engine ────────────────────────────────────────────────────────


class TestLearningEngine:
    def _result(self) -> dict[str, Any]:
        return {
            "performance_summary": {
                "metrics_vs_target": [{"metric": "ROAS", "target": "4x", "actual": "3.2x", "status": "below"}],
                "overall_grade": "B",
                "headline_finding": "Strong reach but conversion below target",
            },
            "what_worked": ["Instagram video ads", "Influencer content"],
            "what_didnt_work": ["LinkedIn ads", "Static image posts"],
            "key_learnings": ["Video outperforms static 3:1", "Tuesday 7PM is peak"],
            "recommendations_for_next_campaign": ["Increase video budget", "Pause LinkedIn"],
            "benchmark_comparison": {"vs_industry": "Above average reach", "vs_historical": "+15% CTR"},
            "audience_insights": {"top_segments": ["25-34 urban"], "surprising_findings": ["Tier-2 cities converted higher"]},
            "creative_insights": {"best_performing": ["Farmer story video"], "worst_performing": ["Product-only shots"], "patterns": ["People > products"]},
            "channel_insights": {"best_roi_channels": ["Instagram"], "underperforming_channels": ["LinkedIn"]},
            "updated_best_practices": ["Lead with video", "Show real people"],
            "reasoning": "Analyzed 30 days of campaign data",
            "confidence": 0.75,
            "recommendations": [],
        }

    def test_engine_name(self) -> None:
        assert LearningEngine.ENGINE_NAME == "learning_engine"

    def test_run_and_to_report(self) -> None:
        gw = _StubGateway(self._result())
        engine = LearningEngine(gateway=gw)
        out = engine.run(
            tenant_id=uuid.uuid4(),
            plan="agency",
            campaign_plan={},
            performance_data={},
        )
        assert out.confidence == 0.75
        report = engine.to_report(out)
        assert isinstance(report, LearningReport)
        assert report.performance_summary["overall_grade"] == "B"
        assert len(report.what_worked) == 2
        assert len(report.key_learnings) == 2
        assert "Lead with video" in report.updated_best_practices
