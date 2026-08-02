"""Tests for Business Memory and Campaign Brain orchestrator."""
from __future__ import annotations

import uuid
from typing import Any

import pytest

from prachar_shared.ai_gateway import Completion
from prachar_shared.marketing_intelligence import (
    BusinessMemory,
    BusinessMemoryStore,
    CampaignBrain,
    FullCampaign,
)
from prachar_shared.marketing_intelligence.base import EngineOutput


class _StubGateway:
    """Returns different results based on the task (engine name)."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def complete(self, **kw: Any) -> Completion:
        self.calls.append(kw)
        task = kw.get("task", "generic")
        results: dict[str, dict[str, Any]] = {
            "business_intelligence": {"industry": "Coffee", "business_model": "D2C", "usp": "Direct trade", "confidence": 0.8, "reasoning": "r"},
            "audience_intelligence": {"primary_audience": {"age_range": "25-34"}, "buying_intent": "high", "confidence": 0.75, "reasoning": "r"},
            "competitor_intelligence": {"competitors": [{"name": "Blue Tokai"}], "market_gaps": ["subscription"], "confidence": 0.6, "reasoning": "r"},
            "marketing_objective": {"objective_type": "increase_sales", "description": "30% growth", "kpis": [], "confidence": 0.85, "reasoning": "r"},
            "campaign_strategy": {"core_message": "Every cup tells a story", "communication_theme": "Traceability", "confidence": 0.7, "reasoning": "r"},
            "creative_direction": {"visual_style": "Editorial", "mood": "Warm", "colour_palette": {"primary": "#3D2817"}, "confidence": 0.75, "reasoning": "r"},
            "media_planning": {"recommended_channels": [{"channel": "Instagram"}], "budget_split": {"digital_paid": 60}, "confidence": 0.65, "reasoning": "r"},
            "budget_intelligence": {"total_cost": {"amount": "₹3,93,000"}, "roi_projection": {"expected_roas": "3.8x"}, "confidence": 0.6, "reasoning": "r"},
            "execution_planner": {"phases": [{"phase": "Strategy"}], "tasks": [{"task": "Generate images"}], "confidence": 0.8, "reasoning": "r"},
            "learning_engine": {"performance_summary": {"overall_grade": "B"}, "key_learnings": ["Video wins"], "updated_best_practices": ["Lead with video"], "confidence": 0.75, "reasoning": "r"},
        }
        result = results.get(task, {"confidence": 0.5, "reasoning": "stub"})
        return Completion(
            text="[stub]",
            json_value=result,
            tokens_used=100,
            model="stub",
            provider="stub",
            latency_ms=5.0,
            cost_usd=0.001,
            request_id=f"req-{task}",
            confidence=result.get("confidence", 0.7),
        )


# ─── BusinessMemory ─────────────────────────────────────────────────────────


class TestBusinessMemory:
    def test_defaults(self) -> None:
        mem = BusinessMemory()
        assert mem.industry == ""
        assert mem.campaign_history == []
        assert mem.best_practices == []

    def test_to_dict_and_from_dict_roundtrip(self) -> None:
        mem = BusinessMemory(
            industry="Coffee",
            brand_voice="Warm, expert",
            preferred_platforms=["instagram", "youtube"],
            best_practices=["Lead with video"],
        )
        d = mem.to_dict()
        assert d["industry"] == "Coffee"
        assert "instagram" in d["preferred_platforms"]
        mem2 = BusinessMemory.from_dict(d)
        assert mem2.industry == "Coffee"
        assert mem2.best_practices == ["Lead with video"]

    def test_from_dict_filters_unknown_keys(self) -> None:
        mem = BusinessMemory.from_dict({"industry": "Tech", "unknown_key": "value"})
        assert mem.industry == "Tech"
        assert not hasattr(mem, "unknown_key")

    def test_from_dict_none(self) -> None:
        mem = BusinessMemory.from_dict(None)
        assert mem.industry == ""


# ─── BusinessMemoryStore ────────────────────────────────────────────────────


class TestBusinessMemoryStore:
    def test_in_memory_get_returns_empty(self) -> None:
        store = BusinessMemoryStore()  # No session
        mem = asyncio_run(store.get(uuid.uuid4(), uuid.uuid4()))
        assert mem.industry == ""

    def test_in_memory_save_no_crash(self) -> None:
        store = BusinessMemoryStore()
        asyncio_run(store.save(uuid.uuid4(), uuid.uuid4(), BusinessMemory(industry="Coffee")))

    def test_update_from_learning_adds_best_practices(self) -> None:
        store = BusinessMemoryStore()
        mem = BusinessMemory(industry="Coffee")
        report = {
            "updated_best_practices": ["Lead with video", "Show real people"],
            "audience_insights": {"surprising_findings": ["Tier-2 converts higher"]},
            "creative_insights": {"patterns": ["People > products"]},
            "channel_insights": {"best_roi_channels": ["Instagram"]},
            "performance_summary": {"overall_grade": "B", "headline_finding": "Good reach"},
        }
        store.update_from_learning(mem, report)
        assert "Lead with video" in mem.best_practices
        assert "Show real people" in mem.best_practices
        assert "Tier-2 converts higher" in mem.audience_insights
        assert "People > products" in mem.creative_insights
        assert "Instagram" in mem.channel_insights
        assert mem.total_campaigns == 1
        assert mem.last_campaign_at != ""

    def test_update_from_learning_dedupes(self) -> None:
        store = BusinessMemoryStore()
        mem = BusinessMemory(best_practices=["Lead with video"])
        report = {"updated_best_practices": ["Lead with video", "New practice"]}
        store.update_from_learning(mem, report)
        assert mem.best_practices.count("Lead with video") == 1
        assert "New practice" in mem.best_practices

    def test_update_from_learning_caps_growth(self) -> None:
        store = BusinessMemoryStore()
        mem = BusinessMemory()
        # Add 60 practices
        report = {"updated_best_practices": [f"Practice {i}" for i in range(60)]}
        store.update_from_learning(mem, report)
        assert len(mem.best_practices) <= 50

    def test_to_prompt_context_empty(self) -> None:
        store = BusinessMemoryStore()
        assert store.to_prompt_context(BusinessMemory()) == ""

    def test_to_prompt_context_with_data(self) -> None:
        store = BusinessMemoryStore()
        mem = BusinessMemory(
            industry="Coffee",
            brand_voice="Warm",
            preferred_platforms=["instagram"],
            best_practices=["Lead with video"],
        )
        ctx = store.to_prompt_context(mem)
        assert "Coffee" in ctx
        assert "instagram" in ctx
        assert "Lead with video" in ctx


# ─── CampaignBrain ──────────────────────────────────────────────────────────


class TestCampaignBrain:
    def test_lazy_engine_init(self) -> None:
        brain = CampaignBrain()
        # Access each engine property — should not raise
        assert brain.business_engine is not None
        assert brain.audience_engine is not None
        assert brain.competitor_engine is not None
        assert brain.objective_engine is not None
        assert brain.strategy_engine is not None
        assert brain.creative_engine is not None
        assert brain.media_engine is not None
        assert brain.budget_engine is not None
        assert brain.execution_engine is not None
        assert brain.learning_engine is not None

    def test_individual_engine_runners(self) -> None:
        brain = CampaignBrain(gateway=_StubGateway())
        tid = uuid.uuid4()
        out = brain.analyse_business(tenant_id=tid, plan="agency", business_name="Acme")
        assert out.result["industry"] == "Coffee"
        out = brain.analyse_audience(tenant_id=tid, plan="agency", business_profile={})
        assert out.result["buying_intent"] == "high"
        out = brain.analyse_competitors(tenant_id=tid, plan="agency", business_name="Acme")
        assert len(out.result["competitors"]) == 1
        out = brain.derive_objective(tenant_id=tid, plan="agency", user_request="grow")
        assert out.result["objective_type"] == "increase_sales"
        out = brain.create_strategy(tenant_id=tid, plan="agency", business_profile={}, audience_profile={}, competitor_profile={}, objective={})
        assert out.result["core_message"] == "Every cup tells a story"
        out = brain.create_creative_direction(tenant_id=tid, plan="agency", business_profile={}, audience_profile={})
        assert out.result["visual_style"] == "Editorial"
        out = brain.create_media_plan(tenant_id=tid, plan="agency", business_profile={}, audience_profile={})
        assert len(out.result["recommended_channels"]) == 1
        out = brain.estimate_budget(tenant_id=tid, plan="agency", business_profile={})
        assert out.result["total_cost"]["amount"] == "₹3,93,000"
        out = brain.create_execution_plan(tenant_id=tid, plan="agency", campaign_strategy={})
        assert len(out.result["phases"]) == 1
        out = brain.generate_learning_report(tenant_id=tid, plan="agency", campaign_plan={}, performance_data={})
        assert out.result["performance_summary"]["overall_grade"] == "B"

    @pytest.mark.asyncio
    async def test_analyse_full_chains_all_engines(self) -> None:
        brain = CampaignBrain(gateway=_StubGateway())
        campaign = await brain.analyse_full(
            tenant_id=uuid.uuid4(),
            plan="agency",
            business_name="Acme Coffee",
            website="acme.com",
            goal="increase sales by 30%",
            budget="₹5,00,000",
            locale="en-IN",
        )
        assert isinstance(campaign, FullCampaign)
        # All 9 analyses should be populated
        assert campaign.business_profile.industry == "Coffee"
        assert campaign.audience_profile.buying_intent == "high"
        assert len(campaign.competitor_profile.competitors) == 1
        assert campaign.marketing_objective.objective_type == "increase_sales"
        assert campaign.campaign_strategy.core_message == "Every cup tells a story"
        assert campaign.creative_direction.visual_style == "Editorial"
        assert len(campaign.media_plan.recommended_channels) == 1
        assert campaign.budget_estimate.total_cost["amount"] == "₹3,93,000"
        assert len(campaign.execution_plan.phases) == 1
        # Engine outputs should have all 9
        assert len(campaign.engine_outputs) == 9
        assert "business" in campaign.engine_outputs
        assert "execution" in campaign.engine_outputs
        # Metadata
        assert campaign.overall_confidence > 0
        assert campaign.total_tokens == 900  # 9 engines × 100 tokens
        assert campaign.executive_summary != ""
        assert isinstance(campaign.risk_assessment, list)

    @pytest.mark.asyncio
    async def test_learn_from_campaign_updates_memory(self) -> None:
        brain = CampaignBrain(gateway=_StubGateway(), memory_store=BusinessMemoryStore())
        report = await brain.learn_from_campaign(
            tenant_id=uuid.uuid4(),
            brand_id=uuid.uuid4(),
            campaign_plan={},
            performance_data={"ctr": "3%"},
        )
        assert report.performance_summary["overall_grade"] == "B"
        assert "Lead with video" in report.updated_best_practices


# ─── Public API (Phase 4: Architecture Stabilisation) ──────────────────────


class TestCampaignBrainPublicAPI:
    """Tests for the canonical public API methods added in Phase 4."""

    @pytest.mark.asyncio
    async def test_analyse_returns_three_profiles(self) -> None:
        brain = CampaignBrain(gateway=_StubGateway())
        result = await brain.analyse(
            tenant_id=uuid.uuid4(),
            plan="agency",
            business_name="Acme",
            goal="grow sales",
        )
        assert "business_profile" in result
        assert "audience_profile" in result
        assert "competitor_profile" in result
        assert "engine_outputs" in result
        assert set(result["engine_outputs"].keys()) == {"business", "audience", "competitor"}
        assert result["business_profile"]["industry"] == "Coffee"

    @pytest.mark.asyncio
    async def test_consult_returns_four_analyses(self) -> None:
        brain = CampaignBrain(gateway=_StubGateway())
        result = await brain.consult(
            tenant_id=uuid.uuid4(),
            plan="agency",
            question="How should I launch my coffee brand?",
        )
        assert set(result.keys()) == {
            "business_profile", "audience_profile",
            "marketing_objective", "campaign_strategy", "engine_outputs",
        }
        assert set(result["engine_outputs"].keys()) == {
            "business", "audience", "objective", "strategy",
        }
        assert result["campaign_strategy"]["core_message"] == "Every cup tells a story"

    @pytest.mark.asyncio
    async def test_generate_strategy_returns_objective_and_strategy(self) -> None:
        brain = CampaignBrain(gateway=_StubGateway())
        result = await brain.generate_strategy(
            tenant_id=uuid.uuid4(),
            plan="agency",
            goal="increase sales by 30%",
            business_name="Acme",
        )
        assert result["marketing_objective"]["objective_type"] == "increase_sales"
        assert result["campaign_strategy"]["core_message"] == "Every cup tells a story"

    @pytest.mark.asyncio
    async def test_generate_campaign_delegates_to_analyse_full(self) -> None:
        brain = CampaignBrain(gateway=_StubGateway())
        campaign = await brain.generate_campaign(
            tenant_id=uuid.uuid4(),
            plan="agency",
            business_name="Acme",
            goal="grow",
        )
        assert isinstance(campaign, FullCampaign)
        assert campaign.business_profile.industry == "Coffee"

    @pytest.mark.asyncio
    async def test_generate_media_plan_returns_media_plan(self) -> None:
        brain = CampaignBrain(gateway=_StubGateway())
        result = await brain.generate_media_plan(
            tenant_id=uuid.uuid4(),
            plan="agency",
            business_profile={},
            audience_profile={},
            objective={},
        )
        assert "media_plan" in result
        assert len(result["media_plan"]["recommended_channels"]) == 1
        assert result["media_plan"]["recommended_channels"][0]["channel"] == "Instagram"

    @pytest.mark.asyncio
    async def test_learn_delegates_to_learn_from_campaign(self) -> None:
        brain = CampaignBrain(gateway=_StubGateway(), memory_store=BusinessMemoryStore())
        report = await brain.learn(
            tenant_id=uuid.uuid4(),
            brand_id=uuid.uuid4(),
            campaign_plan={},
            performance_data={},
        )
        assert report.performance_summary["overall_grade"] == "B"

    @pytest.mark.asyncio
    async def test_analyse_with_brand_id_loads_memory(self) -> None:
        """analyse() should not crash when brand_id is provided (memory lookup)."""
        brain = CampaignBrain(gateway=_StubGateway(), memory_store=BusinessMemoryStore())
        result = await brain.analyse(
            tenant_id=uuid.uuid4(),
            plan="agency",
            business_name="Acme",
            brand_id=uuid.uuid4(),
        )
        assert result["business_profile"]["industry"] == "Coffee"

    @pytest.mark.asyncio
    async def test_consult_without_brand_id_works(self) -> None:
        """consult() should work without a brand_id (no memory lookup)."""
        brain = CampaignBrain(gateway=_StubGateway())
        result = await brain.consult(
            tenant_id=uuid.uuid4(),
            question="What channels should I use?",
        )
        assert "campaign_strategy" in result


# ─── Helpers ────────────────────────────────────────────────────────────────


def asyncio_run(coro):
    """Helper to run async coroutines in sync tests."""
    import asyncio
    return asyncio.run(coro)
