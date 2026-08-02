"""Tests for Campaign Strategy, Creative Direction, and Media Planning engines."""
from __future__ import annotations

import uuid
from typing import Any

import pytest

from prachar_shared.ai_gateway import Completion
from prachar_shared.marketing_intelligence import (
    CampaignStrategy,
    CampaignStrategyEngine,
    CreativeDirection,
    CreativeDirectionEngine,
    MediaPlan,
    MediaPlanningEngine,
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


# ─── Campaign Strategy Engine ───────────────────────────────────────────────


class TestCampaignStrategyEngine:
    def _result(self) -> dict[str, Any]:
        return {
            "core_message": "Every cup tells a farmer's story",
            "communication_theme": "Traceability and craft",
            "emotional_angle": "Pride and connection",
            "marketing_funnel": [{"stage": "TOFU", "goal": "Awareness", "content_intent": "Video storytelling"}],
            "customer_journey": [{"step": "1", "action": "See ad", "touchpoint": "Instagram", "content": "Video"}],
            "content_pillars": [{"pillar": "Origin stories", "description": "Farmer profiles", "content_types": ["video"]}],
            "channel_intent": "Lead with Instagram for visual storytelling, YouTube for long-form education",
            "budget_philosophy": "Concentrate spend on 2 high-ROI channels rather than spreading thin",
            "campaign_duration": "3 months",
            "key_insights": ["Audience responds to authenticity"],
            "reasoning": "Synthesized business + audience + competitor",
            "confidence": 0.7,
            "recommendations": [],
        }

    def test_engine_name(self) -> None:
        assert CampaignStrategyEngine.ENGINE_NAME == "campaign_strategy"

    def test_build_prompt_contains_all_inputs(self) -> None:
        engine = CampaignStrategyEngine()
        prompt = engine._build_prompt(
            business_profile={"industry": "Coffee"},
            audience_profile={"buying_intent": "high"},
            competitor_profile={"competitors": []},
            objective={"objective_type": "increase_sales"},
            budget="₹5L",
            locale="en-IN",
        )
        assert "Coffee" in prompt
        assert "increase_sales" in prompt
        assert "₹5L" in prompt
        assert "Ogilvy" in prompt  # Role

    def test_run_and_to_strategy(self) -> None:
        gw = _StubGateway(self._result())
        engine = CampaignStrategyEngine(gateway=gw)
        out = engine.run(
            tenant_id=uuid.uuid4(),
            plan="agency",
            business_profile={},
            audience_profile={},
            competitor_profile={},
            objective={},
        )
        assert out.result["core_message"] == "Every cup tells a farmer's story"
        assert out.confidence == 0.7
        strat = engine.to_strategy(out)
        assert isinstance(strat, CampaignStrategy)
        assert strat.core_message == "Every cup tells a farmer's story"
        assert strat.emotional_angle == "Pride and connection"
        assert len(strat.content_pillars) == 1
        assert strat.campaign_duration == "3 months"
        # Verify removed fields are gone (owned by other engines now)
        assert not hasattr(strat, "media_mix")
        assert not hasattr(strat, "budget_allocation")
        assert not hasattr(strat, "success_metrics")
        # Verify new strategic-intent fields exist
        assert "Instagram" in strat.channel_intent
        assert "Concentrate" in strat.budget_philosophy

    def test_to_strategy_empty(self) -> None:
        from prachar_shared.marketing_intelligence.base import EngineOutput
        s = CampaignStrategyEngine().to_strategy(EngineOutput(result={}))
        assert s.core_message == ""
        assert s.content_pillars == []


# ─── Creative Direction Engine ──────────────────────────────────────────────


class TestCreativeDirectionEngine:
    def _result(self) -> dict[str, Any]:
        return {
            "visual_style": "Warm, editorial, natural light",
            "mood": "Aspirational yet grounded",
            "colour_palette": {
                "primary": "#3D2817",
                "secondary": "#C9A87C",
                "accent": "#E8D5B7",
                "colours": [{"name": "Espresso", "hex": "#3D2817", "usage": "Primary"}],
            },
            "typography": {"primary_font": "Playfair Display", "secondary_font": "Inter"},
            "photography_style": "Lifestyle product photography with natural light",
            "motion_style": "Slow, cinematic, documentary feel",
            "brand_consistency_rules": ["Always show brand logo bottom-right"],
            "creative_references": [{"name": "Blue Tokai", "style": "Minimal editorial", "why_it_works": "Authentic"}],
            "do_list": ["Use natural light", "Show real people"],
            "dont_list": ["Don't use stock photos", "Don't over-saturate"],
            "image_prompt_template": "Editorial photo of {product}, natural light, warm tones",
            "video_prompt_template": "Cinematic 15s video, slow pan over {product}, warm grade",
            "reasoning": "Aligned with brand and audience",
            "confidence": 0.75,
            "recommendations": [],
        }

    def test_engine_name(self) -> None:
        assert CreativeDirectionEngine.ENGINE_NAME == "creative_direction"

    def test_build_prompt_contains_brand_assets(self) -> None:
        engine = CreativeDirectionEngine()
        prompt = engine._build_prompt(
            business_profile={},
            audience_profile={},
            campaign_strategy={"core_message": "test"},
            brand_colors=[{"name": "blue", "hex": "#0000FF"}],
            brand_logo_url="https://logo.png",
            brand_fonts=["Inter"],
        )
        assert "#0000FF" in prompt
        assert "logo.png" in prompt
        assert "Inter" in prompt

    def test_run_and_to_direction(self) -> None:
        gw = _StubGateway(self._result())
        engine = CreativeDirectionEngine(gateway=gw)
        out = engine.run(tenant_id=uuid.uuid4(), plan="agency", business_profile={}, audience_profile={})
        assert out.confidence == 0.75
        d = engine.to_direction(out)
        assert isinstance(d, CreativeDirection)
        assert d.visual_style == "Warm, editorial, natural light"
        assert d.colour_palette["primary"] == "#3D2817"
        assert len(d.do_list) == 2
        assert "image_prompt_template" in d.to_dict()


# ─── Media Planning Engine ──────────────────────────────────────────────────


class TestMediaPlanningEngine:
    def _result(self) -> dict[str, Any]:
        return {
            "recommended_channels": [
                {"channel": "Instagram", "type": "digital", "rationale": "Audience", "budget_percentage": 35, "priority": "high"},
                {"channel": "YouTube", "type": "digital", "rationale": "Video content", "budget_percentage": 25, "priority": "high"},
            ],
            "budget_split": {"digital_paid": 60, "digital_organic": 30, "traditional": 10, "total": "₹5L"},
            "scheduling": {"peak_times": "7-9 PM", "frequency": "daily", "duration_weeks": 12},
            "reach_estimate": {"total_reach": "2M", "total_impressions": "8M", "average_frequency": "4"},
            "channel_rationale": {"selected": ["Instagram", "YouTube"], "rejected": ["TV"], "rejection_reasons": ["Budget too low"]},
            "reasoning": "Based on audience platform preferences",
            "confidence": 0.65,
            "recommendations": [],
        }

    def test_engine_name(self) -> None:
        assert MediaPlanningEngine.ENGINE_NAME == "media_planning"

    def test_build_prompt(self) -> None:
        engine = MediaPlanningEngine()
        prompt = engine._build_prompt(
            business_profile={},
            audience_profile={"platforms": ["instagram"]},
            objective={},
            budget="₹5L",
            campaign_strategy={},
            locale="en-IN",
        )
        assert "₹5L" in prompt
        assert "en-IN" in prompt

    def test_run_and_to_plan(self) -> None:
        gw = _StubGateway(self._result())
        engine = MediaPlanningEngine(gateway=gw)
        out = engine.run(tenant_id=uuid.uuid4(), plan="agency", business_profile={}, audience_profile={})
        assert out.confidence == 0.65
        plan = engine.to_plan(out)
        assert isinstance(plan, MediaPlan)
        assert len(plan.recommended_channels) == 2
        assert plan.recommended_channels[0]["channel"] == "Instagram"
        assert plan.budget_split["digital_paid"] == 60
