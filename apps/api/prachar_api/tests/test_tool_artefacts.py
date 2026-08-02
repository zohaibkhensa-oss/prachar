"""Phase F tests — artefact emission from tool wrappers.

Verifies that every tool that produces user-facing output includes
artefacts in its result dict, so the conversation becomes a live workspace.
"""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prachar_api.runtime.artefacts import Artefact
from prachar_api.runtime.context import AIContext
from prachar_api.runtime.tools import (
    campaign_brain_analyse,
    campaign_brain_strategy,
    campaign_brain_creative,
    campaign_brain_media,
    campaign_brain_full_campaign,
    council_review,
    creative_studio_generate,
    creative_studio_generate_image,
    performance_story,
    performance_why,
    performance_next,
    proactive_notifications,
    memory_retrieve,
    consult_understand,
)
from prachar_api.runtime.memory_categories import MemoryStore


def _make_ctx() -> AIContext:
    return AIContext(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        brand_id=uuid.uuid4(),
        conversation=[],
        memory=MemoryStore(),
    )


class TestCampaignBrainArtefacts:
    """CampaignBrain tools emit artefacts."""

    async def test_analyse_emits_audience_and_competitor_cards(self):
        ctx = _make_ctx()
        with patch("prachar_shared.marketing_intelligence.CampaignBrain") as MockBrain:
            mock_instance = MockBrain.return_value
            mock_instance.analyse = AsyncMock(return_value={
                "business_profile": {"name": "Test"},
                "audience_profile": {
                    "demographics": {"age": "25-34"},
                    "interests": ["food"],
                    "behaviours": ["weekend diners"],
                    "platforms": ["instagram"],
                },
                "competitor_profile": {
                    "name": "Comp X",
                    "strengths": ["strong SEO"],
                    "weaknesses": ["weak social"],
                    "market_share": "15%",
                },
            })
            result = await campaign_brain_analyse(ctx, {"goal": "sales", "budget": "₹5000"})
        artefacts = result.get("artefacts", [])
        assert len(artefacts) >= 2
        kinds = [a["kind"] for a in artefacts]
        assert "audience_card" in kinds
        assert "competitor_card" in kinds

    async def test_strategy_emits_campaign_card(self):
        ctx = _make_ctx()
        with patch("prachar_shared.marketing_intelligence.CampaignBrain") as MockBrain:
            mock_instance = MockBrain.return_value
            mock_instance.generate_strategy = AsyncMock(return_value={
                "marketing_objective": {"primary_goal": "awareness"},
                "campaign_strategy": {"name": "Diwali Sale", "channels": ["instagram", "google"]},
            })
            result = await campaign_brain_strategy(ctx, {"goal": "sales", "budget": "₹5000"})
        artefacts = result.get("artefacts", [])
        assert any(a["kind"] == "campaign_card" for a in artefacts)

    async def test_creative_emits_creative_brief(self):
        ctx = _make_ctx()
        with patch("prachar_shared.marketing_intelligence.CampaignBrain") as MockBrain:
            mock_instance = MockBrain.return_value
            mock_instance.generate_creative_direction = AsyncMock(return_value={
                "creative_direction": {
                    "concept": "Festive joy",
                    "style": "Vibrant",
                    "tone": "Warm",
                    "references": ["ref1"],
                    "colors": ["#FFD700"],
                },
            })
            result = await campaign_brain_creative(ctx, {})
        artefacts = result.get("artefacts", [])
        assert any(a["kind"] == "creative_brief" for a in artefacts)

    async def test_media_emits_media_plan_and_budget(self):
        ctx = _make_ctx()
        with patch("prachar_shared.marketing_intelligence.CampaignBrain") as MockBrain:
            mock_instance = MockBrain.return_value
            mock_instance.generate_media_plan = AsyncMock(return_value={
                "media_plan": {
                    "channels": [{"channel": "Google", "amount": "₹2000"}],
                    "schedule": "4 weeks",
                },
            })
            result = await campaign_brain_media(ctx, {"budget": "₹5000"})
        artefacts = result.get("artefacts", [])
        kinds = [a["kind"] for a in artefacts]
        assert "media_plan" in kinds
        assert "budget_table" in kinds

    async def test_full_campaign_emits_multiple_artefacts(self):
        ctx = _make_ctx()
        with patch("prachar_shared.marketing_intelligence.CampaignBrain") as MockBrain:
            mock_instance = MockBrain.return_value
            mock_instance.generate_campaign = AsyncMock(return_value={
                "campaign_name": "Diwali Sale",
                "audience_profile": {"demographics": {}, "interests": [], "behaviours": []},
                "competitor_profile": {"name": "Comp", "strengths": [], "weaknesses": []},
                "creative_direction": {"concept": "Joy", "style": "Vibrant", "tone": "Warm"},
                "media_plan": {"channels": []},
                "execution_plan": {"timeline": []},
            })
            result = await campaign_brain_full_campaign(ctx, {"goal": "sales", "budget": "₹5000"})
        artefacts = result.get("artefacts", [])
        assert len(artefacts) >= 3
        kinds = [a["kind"] for a in artefacts]
        assert "campaign_card" in kinds


class TestCouncilArtefacts:
    """Council review emits artefacts."""

    async def test_council_emits_review_feedback_and_summary(self):
        ctx = _make_ctx()
        mock_opinion = MagicMock()
        mock_opinion.to_dict.return_value = {
            "director": "CSO",
            "opinion": "Good strategy",
            "confidence": 0.9,
            "score": 8.5,
            "risks": ["budget risk"],
        }
        mock_decision = MagicMock()
        mock_decision.to_dict.return_value = {
            "approved": True,
            "key_points": ["strong creative"],
            "consensus": "Approved",
            "recommendations": [{"title": "Launch", "priority": "high"}],
        }
        mock_score = MagicMock()
        mock_score.to_dict.return_value = {"overall": 8.5}
        mock_result = MagicMock()
        mock_result.opinions = [mock_opinion]
        mock_result.decision = mock_decision
        mock_result.campaign_score = mock_score

        with patch("prachar_shared.agency_council.ConsensusEngine") as MockEngine:
            mock_instance = MockEngine.return_value
            mock_instance.review = AsyncMock(return_value=mock_result)
            with patch("prachar_shared.agency_council.ALL_DIRECTORS", {}):
                result = await council_review(ctx, {"campaign_brief": {}})
        artefacts = result.get("artefacts", [])
        kinds = [a["kind"] for a in artefacts]
        assert "review_feedback" in kinds
        assert "review_summary" in kinds
        assert "task_list" in kinds


class TestCreativeStudioArtefacts:
    """Creative Studio tools emit artefacts."""

    async def test_generate_emits_copy_drafts(self):
        ctx = _make_ctx()
        with patch("prachar_api.infrastructure.creative_studio_engine.CreativeStudioEngine") as MockEngine:
            mock_instance = MockEngine.return_value
            mock_instance.generate = AsyncMock(return_value={
                "poster": {"headline": "Sale!", "body": "20% off", "hashtags": ["#sale"]},
                "whatsapp": {"headline": "Deal", "body": "Limited time", "cta": "Buy now"},
                "video_script": {"title": "My Video", "script": "Scene 1..."},
            })
            result = await creative_studio_generate(ctx, {"campaign_id": "test"})
        artefacts = result.get("artefacts", [])
        kinds = [a["kind"] for a in artefacts]
        assert "copy_drafts" in kinds

    async def test_generate_image_emits_image_artefact(self):
        ctx = _make_ctx()
        with patch("prachar_api.routers.video_gen.generate_image", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = {"image_url": "https://example.com/img.png", "model": "dalle"}
            result = await creative_studio_generate_image(ctx, {"prompt": "festive sale"})
        artefacts = result.get("artefacts", [])
        assert len(artefacts) == 1
        assert artefacts[0]["kind"] == "image"
        assert artefacts[0]["payload"]["url"] == "https://example.com/img.png"


class TestPerformanceArtefacts:
    """Performance tools emit artefacts."""

    async def test_story_emits_kpi_grid(self):
        ctx = _make_ctx()
        with patch("prachar_shared.marketing_intelligence.performance_engine.PerformanceEngine") as MockEngine:
            mock_instance = MockEngine.return_value
            mock_instance.tell_story = AsyncMock(return_value={
                "kpis": [{"label": "Reach", "value": "12K", "trend": "↑ 18%"}],
            })
            result = await performance_story(ctx, {"campaign_id": str(uuid.uuid4())})
        artefacts = result.get("artefacts", [])
        assert any(a["kind"] == "kpi_grid" for a in artefacts)

    async def test_why_emits_alert(self):
        ctx = _make_ctx()
        with patch("prachar_shared.marketing_intelligence.performance_engine.PerformanceEngine") as MockEngine:
            mock_instance = MockEngine.return_value
            mock_instance.explain = AsyncMock(return_value={
                "root_cause": "Low CTR due to poor creative",
                "corrective_actions": [{"title": "Refresh creative", "priority": "high"}],
            })
            result = await performance_why(ctx, {"campaign_id": str(uuid.uuid4())})
        artefacts = result.get("artefacts", [])
        kinds = [a["kind"] for a in artefacts]
        assert "alert" in kinds
        assert "task_list" in kinds

    async def test_next_emits_task_list(self):
        ctx = _make_ctx()
        with patch("prachar_shared.marketing_intelligence.performance_engine.PerformanceEngine") as MockEngine:
            mock_instance = MockEngine.return_value
            mock_instance.recommend = AsyncMock(return_value={
                "recommendations": [{"title": "Increase budget", "priority": "high"}],
            })
            result = await performance_next(ctx, {"campaign_id": str(uuid.uuid4())})
        artefacts = result.get("artefacts", [])
        assert any(a["kind"] == "task_list" for a in artefacts)


class TestProactiveArtefacts:
    """Proactive notifications emit alert artefacts."""

    async def test_notifications_emits_alerts(self):
        ctx = _make_ctx()
        ctx.session = MagicMock()
        with patch("prachar_api.routers.proactive.get_notifications", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [
                {"severity": "warning", "title": "Budget 80% used", "detail": "₹4000 of ₹5000"},
            ]
            result = await proactive_notifications(ctx, {})
        artefacts = result.get("artefacts", [])
        assert len(artefacts) == 1
        assert artefacts[0]["kind"] == "alert"


class TestMemoryArtefacts:
    """Memory retrieval emits memory insight artefacts."""

    async def test_retrieve_emits_memory_insights(self):
        from prachar_api.runtime.memory_categories import MemoryStore, MemoryEntry, MemoryCategory
        ctx = _make_ctx()
        ctx.memory = MemoryStore(
            campaign=[MemoryEntry(category=MemoryCategory.CAMPAIGN, content="Reels outperform carousels")],
            audience=[MemoryEntry(category=MemoryCategory.AUDIENCE, content="Age 25-34 most active")],
        )
        result = await memory_retrieve(ctx, {})
        artefacts = result.get("artefacts", [])
        assert len(artefacts) >= 1
        assert all(a["kind"] == "memory_insight" for a in artefacts)


class TestConsultArtefacts:
    """Consult understand emits opportunity and timeline artefacts."""

    async def test_consult_emits_opportunities_and_plan(self):
        ctx = _make_ctx()
        with patch("prachar_api.infrastructure.consult_engine.ConsultEngine") as MockEngine:
            mock_instance = MockEngine.return_value
            mock_instance.consult = AsyncMock(return_value={
                "business": {},
                "growth_opportunities": [
                    {"title": "Expand to YouTube", "impact": "high", "difficulty": "medium"},
                ],
                "plan": [{"objective": "Awareness", "content": "Brand posts"}],
            })
            result = await consult_understand(ctx, {"message": "I run a restaurant"})
        artefacts = result.get("artefacts", [])
        kinds = [a["kind"] for a in artefacts]
        assert "opportunity_card" in kinds
        assert "timeline_plan" in kinds
