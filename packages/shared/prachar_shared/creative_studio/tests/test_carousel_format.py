"""Tests for the carousel creative format generator (P2.6)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import BudgetExceeded, Completion
from prachar_shared.creative_studio.formats.carousel import (
    CAROUSEL,
    generate_carousel,
)


# ─── Helpers ────────────────────────────────────────────────────────────────


def _completion(text: str, tokens: int = 80) -> Completion:
    return Completion(text=text, tokens_used=tokens, model="test-model")


def _valid_payload() -> dict:
    return {
        "slides": [
            {
                "slide_no": 1,
                "headline": "Why most ads fail",
                "body": "They talk about features, not outcomes.",
                "visual_brief": "Bold typography on a dark background",
            },
            {
                "slide_no": 2,
                "headline": "The fix",
                "body": "Lead with the transformation the buyer gets.",
                "visual_brief": "Before/after split screen",
            },
            {
                "slide_no": 3,
                "headline": "Your turn",
                "body": "Rewrite your first line around the outcome.",
                "visual_brief": "Checklist with one item ticked",
            },
        ],
        "cta_slide": "Reply 'ADFIX' and we'll rewrite yours free.",
    }


@pytest.fixture()
def campaign() -> dict:
    return {
        "id": "camp-1",
        "name": "Diwali Sale",
        "brand_name": "Bright Bazaar",
        "goal": "increase online sales",
        "budget": "₹50,000",
    }


@pytest.fixture()
def creative_direction() -> dict:
    return {
        "id": "cd-1",
        "hook": "Stop scrolling",
        "angle": "Outcome over feature",
        "tone": "confident",
        "sample_cta": "Shop the Diwali collection",
    }


@pytest.fixture()
def domain_context() -> dict:
    return {
        "id": "ecommerce",
        "label": "E-commerce Growth",
        "carousel_prompt": "Use festive colours; keep slides under 50 words.",
    }


@pytest.fixture()
def mock_gateway():
    gw = MagicMock()
    gw.complete = MagicMock(return_value=_completion(json.dumps(_valid_payload())))
    return gw


# ─── Spec sanity ────────────────────────────────────────────────────────────


class TestCarouselSpec:
    def test_spec_id_and_label(self):
        assert CAROUSEL.id == "carousel"
        assert CAROUSEL.label == "Carousel"

    def test_spec_schema_has_required_keys(self):
        props = CAROUSEL.output_schema["properties"]
        assert "slides" in props
        assert "cta_slide" in props
        slide_props = props["slides"]["items"]["properties"]
        for key in ["slide_no", "headline", "body", "visual_brief"]:
            assert key in slide_props

    def test_spec_prompt_has_placeholders(self):
        for ph in ["{campaign}", "{creative_direction}", "{domain_context}"]:
            assert ph in CAROUSEL.prompt_template


# ─── generate_carousel — success ────────────────────────────────────────────


class TestGenerateCarouselSuccess:
    def test_returns_dict(self, mock_gateway, campaign, creative_direction, domain_context):
        result = generate_carousel(
            campaign, creative_direction, domain_context, gateway=mock_gateway
        )
        assert isinstance(result, dict)

    def test_has_slides_list(self, mock_gateway, campaign, creative_direction, domain_context):
        result = generate_carousel(
            campaign, creative_direction, domain_context, gateway=mock_gateway
        )
        assert "slides" in result
        assert isinstance(result["slides"], list)
        assert len(result["slides"]) == 3

    def test_has_cta_slide(self, mock_gateway, campaign, creative_direction, domain_context):
        result = generate_carousel(
            campaign, creative_direction, domain_context, gateway=mock_gateway
        )
        assert "cta_slide" in result
        assert isinstance(result["cta_slide"], str)
        assert result["cta_slide"]

    def test_each_slide_has_required_fields(
        self, mock_gateway, campaign, creative_direction, domain_context
    ):
        result = generate_carousel(
            campaign, creative_direction, domain_context, gateway=mock_gateway
        )
        for slide in result["slides"]:
            assert isinstance(slide, dict)
            for key in ["slide_no", "headline", "body", "visual_brief"]:
                assert key in slide, f"slide missing {key}"
            assert isinstance(slide["slide_no"], int)
            assert isinstance(slide["headline"], str)
            assert isinstance(slide["body"], str)
            assert isinstance(slide["visual_brief"], str)

    def test_uses_tier_large(self, mock_gateway, campaign, creative_direction, domain_context):
        from prachar_shared.ai_gateway import Tier

        generate_carousel(
            campaign, creative_direction, domain_context, gateway=mock_gateway
        )
        assert mock_gateway.complete.called
        kwargs = mock_gateway.complete.call_args.kwargs
        assert kwargs["tier"] == Tier.large

    def test_task_name_set(self, mock_gateway, campaign, creative_direction, domain_context):
        generate_carousel(
            campaign, creative_direction, domain_context, gateway=mock_gateway
        )
        kwargs = mock_gateway.complete.call_args.kwargs
        assert kwargs["task"] == "creative_studio_carousel"

    def test_passes_tenant_and_plan(self, mock_gateway, campaign, creative_direction, domain_context):
        generate_carousel(
            campaign,
            creative_direction,
            domain_context,
            gateway=mock_gateway,
            tenant_id="t-42",
            plan="growth",
        )
        kwargs = mock_gateway.complete.call_args.kwargs
        assert kwargs["tenant_id"] == "t-42"
        assert kwargs["plan"] == "growth"


# ─── generate_carousel — parsing robustness ─────────────────────────────────


class TestGenerateCarouselParsing:
    def test_handles_markdown_fenced_json(
        self, campaign, creative_direction, domain_context
    ):
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_completion("```json\n" + json.dumps(_valid_payload()) + "\n```")
        )
        result = generate_carousel(campaign, creative_direction, domain_context, gateway=gw)
        assert len(result["slides"]) == 3
        assert result["cta_slide"]

    def test_coerces_missing_slide_no(
        self, campaign, creative_direction, domain_context
    ):
        payload = {
            "slides": [
                {"headline": "H1", "body": "B1", "visual_brief": "V1"},
                {"headline": "H2", "body": "B2", "visual_brief": "V2"},
            ],
            "cta_slide": "Go!",
        }
        gw = MagicMock()
        gw.complete = MagicMock(return_value=_completion(json.dumps(payload)))
        result = generate_carousel(campaign, creative_direction, domain_context, gateway=gw)
        assert [s["slide_no"] for s in result["slides"]] == [1, 2]

    def test_coerces_non_string_cta(
        self, campaign, creative_direction, domain_context
    ):
        payload = {"slides": [], "cta_slide": 12345}
        gw = MagicMock()
        gw.complete = MagicMock(return_value=_completion(json.dumps(payload)))
        result = generate_carousel(campaign, creative_direction, domain_context, gateway=gw)
        assert isinstance(result["cta_slide"], str)
        assert result["cta_slide"] == "12345"

    def test_empty_slides_list_handled(
        self, campaign, creative_direction, domain_context
    ):
        payload = {"slides": [], "cta_slide": "Do something"}
        gw = MagicMock()
        gw.complete = MagicMock(return_value=_completion(json.dumps(payload)))
        result = generate_carousel(campaign, creative_direction, domain_context, gateway=gw)
        assert result["slides"] == []
        assert result["cta_slide"] == "Do something"


# ─── generate_carousel — graceful fallback ──────────────────────────────────


class TestGenerateCarouselFallback:
    def test_gateway_exception_returns_empty_dict(
        self, campaign, creative_direction, domain_context
    ):
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=RuntimeError("boom"))
        result = generate_carousel(campaign, creative_direction, domain_context, gateway=gw)
        assert result == {}

    def test_unparseable_text_returns_empty_dict(
        self, campaign, creative_direction, domain_context
    ):
        gw = MagicMock()
        gw.complete = MagicMock(return_value=_completion("no json here at all"))
        result = generate_carousel(campaign, creative_direction, domain_context, gateway=gw)
        assert result == {}

    def test_non_dict_json_returns_empty_dict(
        self, campaign, creative_direction, domain_context
    ):
        gw = MagicMock()
        gw.complete = MagicMock(return_value=_completion('["not", "an", "object"]'))
        result = generate_carousel(campaign, creative_direction, domain_context, gateway=gw)
        assert result == {}

    def test_budget_exceeded_propagates(
        self, campaign, creative_direction, domain_context
    ):
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=BudgetExceeded("over cap"))
        with pytest.raises(BudgetExceeded):
            generate_carousel(campaign, creative_direction, domain_context, gateway=gw)
