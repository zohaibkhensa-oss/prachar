"""Tests for the poster format generator (formats/poster.py).

Covers:
- generate_poster returns a dict with all 7 required fields
- color_palette is a list
- graceful fallback to empty-valued dict on gateway failure
- graceful fallback on unparseable JSON
- works with different domain contexts (restaurant vs clinic)
- BudgetExceeded re-raises (not swallowed)
- prompt is domain-aware (contains domain context content)
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import BudgetExceeded, Completion
from prachar_shared.creative_studio.formats.poster import (
    POSTER,
    generate_poster,
)

REQUIRED_FIELDS = [
    "headline",
    "subheadline",
    "body",
    "cta",
    "visual_brief",
    "color_palette",
    "layout_hint",
]


# ─── Fixtures ──────────────────────────────────────────────────────────────


def _completion(payload: dict, tokens: int = 80) -> Completion:
    return Completion(
        text=json.dumps(payload),
        json_value=payload,
        tokens_used=tokens,
        model="test-model",
    )


def _restaurant_payload() -> dict:
    return {
        "headline": "Sizzling Summer Thali",
        "subheadline": "Unlimited refills, every evening",
        "body": "Feast on our chef's seasonal thali — 12 dishes, one plate.",
        "cta": "Book a table",
        "visual_brief": "Overhead shot of a steaming thali with warm lighting",
        "color_palette": ["#C0392B", "#E67E22", "#F1C40F", "#2C2C2C"],
        "layout_hint": "Hero food image top 65%, copy bottom 35% left-aligned",
    }


def _clinic_payload() -> dict:
    return {
        "headline": "Your Health, Our Priority",
        "subheadline": "Same-day appointments available",
        "body": "Compassionate care from trusted specialists, 7 days a week.",
        "cta": "Book a consult",
        "visual_brief": "Clean clinical interior with a smiling doctor",
        "color_palette": ["#2C3E50", "#3498DB", "#ECF0F1", "#1ABC9C"],
        "layout_hint": "Doctor portrait left 50%, copy right 50% centred",
    }


@pytest.fixture()
def sample_campaign() -> dict:
    return {
        "id": "camp-123",
        "name": "Summer Sale Campaign",
        "goal": "increase sales",
        "budget": "₹50,000",
    }


@pytest.fixture()
def sample_creative_direction() -> dict:
    return {
        "id": "cd-456",
        "hook": "Beat the heat",
        "angle": "Urgency + value",
        "tone": "energetic",
    }


@pytest.fixture()
def restaurant_domain() -> dict:
    return {
        "id": "restaurant",
        "label": "Restaurant",
        "customer_type": "diner",
        "domain_notes": "Appetising food photography, warm colours, urgency for offers.",
    }


@pytest.fixture()
def clinic_domain() -> dict:
    return {
        "id": "clinic",
        "label": "Clinic",
        "customer_type": "patient",
        "domain_notes": "Trust-building, calm clinical imagery, empathetic copy.",
    }


def _mock_gateway(payload: dict) -> MagicMock:
    gw = MagicMock()
    gw.complete = MagicMock(return_value=_completion(payload))
    return gw


# ─── Spec sanity ───────────────────────────────────────────────────────────


class TestPosterSpec:
    def test_spec_id_and_label(self):
        assert POSTER.id == "poster"
        assert POSTER.label == "Poster"

    def test_spec_has_required_schema_fields(self):
        props = POSTER.output_schema["properties"]
        for field in REQUIRED_FIELDS:
            assert field in props, f"schema missing {field}"

    def test_spec_required_list_matches(self):
        assert set(POSTER.output_schema["required"]) == set(REQUIRED_FIELDS)

    def test_prompt_template_has_placeholders(self):
        for ph in ("{campaign}", "{creative_direction}", "{domain_context}"):
            assert ph in POSTER.prompt_template

    def test_prompt_template_is_domain_aware(self):
        # The enhanced prompt must instruct the model to adapt to the domain
        assert "restaurant" in POSTER.prompt_template.lower()
        assert "clinic" in POSTER.prompt_template.lower()
        assert "domain" in POSTER.prompt_template.lower()


# ─── generate_poster — success ─────────────────────────────────────────────


class TestGeneratePosterSuccess:
    def test_returns_dict_with_all_required_fields(
        self, sample_campaign, sample_creative_direction, restaurant_domain
    ):
        gw = _mock_gateway(_restaurant_payload())
        result = generate_poster(
            sample_campaign,
            sample_creative_direction,
            restaurant_domain,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert isinstance(result, dict)
        for field in REQUIRED_FIELDS:
            assert field in result, f"missing field {field}"

    def test_field_values_populated_from_gateway(
        self, sample_campaign, sample_creative_direction, restaurant_domain
    ):
        payload = _restaurant_payload()
        gw = _mock_gateway(payload)
        result = generate_poster(
            sample_campaign,
            sample_creative_direction,
            restaurant_domain,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert result["headline"] == payload["headline"]
        assert result["subheadline"] == payload["subheadline"]
        assert result["body"] == payload["body"]
        assert result["cta"] == payload["cta"]
        assert result["visual_brief"] == payload["visual_brief"]
        assert result["layout_hint"] == payload["layout_hint"]

    def test_color_palette_is_list(
        self, sample_campaign, sample_creative_direction, restaurant_domain
    ):
        gw = _mock_gateway(_restaurant_payload())
        result = generate_poster(
            sample_campaign,
            sample_creative_direction,
            restaurant_domain,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert isinstance(result["color_palette"], list)
        assert len(result["color_palette"]) > 0
        assert all(isinstance(c, str) for c in result["color_palette"])

    def test_gateway_called_with_large_tier(
        self, sample_campaign, sample_creative_direction, restaurant_domain
    ):
        gw = _mock_gateway(_restaurant_payload())
        generate_poster(
            sample_campaign,
            sample_creative_direction,
            restaurant_domain,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        gw.complete.assert_called_once()
        kwargs = gw.complete.call_args.kwargs
        assert kwargs["tier"] is not None
        # Tier is a StrEnum; check the value
        assert str(kwargs["tier"]) == "large"

    def test_gateway_called_with_poster_schema(
        self, sample_campaign, sample_creative_direction, restaurant_domain
    ):
        gw = _mock_gateway(_restaurant_payload())
        generate_poster(
            sample_campaign,
            sample_creative_direction,
            restaurant_domain,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        kwargs = gw.complete.call_args.kwargs
        assert kwargs["schema"] == POSTER.output_schema

    def test_prompt_includes_domain_context(
        self, sample_campaign, sample_creative_direction, restaurant_domain
    ):
        gw = _mock_gateway(_restaurant_payload())
        generate_poster(
            sample_campaign,
            sample_creative_direction,
            restaurant_domain,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        prompt = gw.complete.call_args.kwargs["prompt"]
        assert "restaurant" in prompt.lower()
        assert "diner" in prompt.lower()


# ─── generate_poster — domain variation ────────────────────────────────────


class TestGeneratePosterDomainVariation:
    def test_restaurant_domain_uses_restaurant_payload(
        self, sample_campaign, sample_creative_direction, restaurant_domain
    ):
        gw = _mock_gateway(_restaurant_payload())
        result = generate_poster(
            sample_campaign,
            sample_creative_direction,
            restaurant_domain,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert "thali" in result["headline"].lower()
        assert any("#C0392B" in c for c in result["color_palette"])

    def test_clinic_domain_uses_clinic_payload(
        self, sample_campaign, sample_creative_direction, clinic_domain
    ):
        gw = _mock_gateway(_clinic_payload())
        result = generate_poster(
            sample_campaign,
            sample_creative_direction,
            clinic_domain,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert "health" in result["headline"].lower()
        assert any("#3498DB" in c for c in result["color_palette"])

    def test_different_domains_produce_different_posters(
        self, sample_campaign, sample_creative_direction, restaurant_domain, clinic_domain
    ):
        gw_rest = _mock_gateway(_restaurant_payload())
        rest = generate_poster(
            sample_campaign,
            sample_creative_direction,
            restaurant_domain,
            gateway=gw_rest,
            tenant_id="tenant-1",
            plan="agency",
        )
        gw_clinic = _mock_gateway(_clinic_payload())
        clinic = generate_poster(
            sample_campaign,
            sample_creative_direction,
            clinic_domain,
            gateway=gw_clinic,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert rest != clinic
        assert rest["headline"] != clinic["headline"]
        assert rest["color_palette"] != clinic["color_palette"]

    def test_prompt_differs_by_domain_context(
        self, sample_campaign, sample_creative_direction, restaurant_domain, clinic_domain
    ):
        gw_rest = _mock_gateway(_restaurant_payload())
        generate_poster(
            sample_campaign,
            sample_creative_direction,
            restaurant_domain,
            gateway=gw_rest,
            tenant_id="tenant-1",
            plan="agency",
        )
        gw_clinic = _mock_gateway(_clinic_payload())
        generate_poster(
            sample_campaign,
            sample_creative_direction,
            clinic_domain,
            gateway=gw_clinic,
            tenant_id="tenant-1",
            plan="agency",
        )
        rest_prompt = gw_rest.complete.call_args.kwargs["prompt"]
        clinic_prompt = gw_clinic.complete.call_args.kwargs["prompt"]
        assert "restaurant" in rest_prompt.lower()
        assert "clinic" in clinic_prompt.lower()
        assert rest_prompt != clinic_prompt


# ─── generate_poster — fallback ────────────────────────────────────────────


class TestGeneratePosterFallback:
    def test_gateway_exception_returns_empty_poster(
        self, sample_campaign, sample_creative_direction, restaurant_domain
    ):
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=RuntimeError("LLM exploded"))
        result = generate_poster(
            sample_campaign,
            sample_creative_direction,
            restaurant_domain,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        # All fields present but empty
        assert isinstance(result, dict)
        for field in REQUIRED_FIELDS:
            assert field in result
        assert result["headline"] == ""
        assert result["subheadline"] == ""
        assert result["body"] == ""
        assert result["cta"] == ""
        assert result["visual_brief"] == ""
        assert result["color_palette"] == []
        assert result["layout_hint"] == ""

    def test_unparseable_json_returns_empty_poster(
        self, sample_campaign, sample_creative_direction, restaurant_domain
    ):
        comp = Completion(text="not json at all <<<", tokens_used=10, model="test")
        gw = MagicMock()
        gw.complete = MagicMock(return_value=comp)
        result = generate_poster(
            sample_campaign,
            sample_creative_direction,
            restaurant_domain,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert isinstance(result, dict)
        for field in REQUIRED_FIELDS:
            assert field in result
        assert result["headline"] == ""
        assert result["color_palette"] == []

    def test_partial_json_fills_missing_fields(
        self, sample_campaign, sample_creative_direction, restaurant_domain
    ):
        # Only headline provided — other fields should be filled with defaults
        partial = {"headline": "Only headline"}
        comp = Completion(
            text=json.dumps(partial),
            json_value=partial,
            tokens_used=10,
            model="test",
        )
        gw = MagicMock()
        gw.complete = MagicMock(return_value=comp)
        result = generate_poster(
            sample_campaign,
            sample_creative_direction,
            restaurant_domain,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert result["headline"] == "Only headline"
        assert result["subheadline"] == ""
        assert result["body"] == ""
        assert result["color_palette"] == []

    def test_color_palette_non_list_coerced_to_list(
        self, sample_campaign, sample_creative_direction, restaurant_domain
    ):
        bad = {"headline": "X", "color_palette": "not a list"}
        comp = Completion(
            text=json.dumps(bad),
            json_value=bad,
            tokens_used=10,
            model="test",
        )
        gw = MagicMock()
        gw.complete = MagicMock(return_value=comp)
        result = generate_poster(
            sample_campaign,
            sample_creative_direction,
            restaurant_domain,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert isinstance(result["color_palette"], list)
        assert result["color_palette"] == []

    def test_budget_exceeded_reraises(
        self, sample_campaign, sample_creative_direction, restaurant_domain
    ):
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=BudgetExceeded("over budget"))
        with pytest.raises(BudgetExceeded):
            generate_poster(
                sample_campaign,
                sample_creative_direction,
                restaurant_domain,
                gateway=gw,
                tenant_id="tenant-1",
                plan="agency",
            )
