"""Tests for the landing_page creative format generator (P2.12)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import BudgetExceeded, Completion
from prachar_shared.creative_studio.formats.landing_page import (
    LANDING_PAGE,
    generate_landing_page,
)


# ─── Helpers ────────────────────────────────────────────────────────────────


def _completion(text: str, tokens: int = 80) -> Completion:
    return Completion(
        text=text,
        tokens_used=tokens,
        model="test-model",
        confidence=0.9,
    )


def _valid_payload() -> dict:
    return {
        "hero_headline": "Grow your business 3x faster",
        "hero_subhead": "The all-in-one marketing platform for SMBs",
        "benefits": [
            "Save 10 hours a week with automation",
            "Reach customers across every channel",
            "Measure ROI with real-time analytics",
        ],
        "social_proof_section": "Trusted by 5,000+ businesses with 4.8★ rating",
        "faq": [
            "Do I need marketing experience?",
            "Can I cancel anytime?",
            "Is there a free trial?",
        ],
        "cta": "Start your free trial",
        "form_fields": ["Full name", "Work email", "Company name", "Phone number"],
    }


@pytest.fixture()
def campaign() -> dict:
    return {"id": "cmp-1", "goal": "lead-gen", "budget": 5000, "brand_name": "Acme"}


@pytest.fixture()
def creative_direction() -> dict:
    return {"id": "cd-1", "tone": "confident", "angle": "time-savings"}


@pytest.fixture()
def domain_context() -> dict:
    return {"id": "saas", "label": "SaaS", "hooks_prompt": "Focus on ROI."}


@pytest.fixture()
def mock_gateway():
    """A MagicMock AIGateway whose complete() returns the valid payload JSON."""
    gw = MagicMock()
    gw.complete = MagicMock(
        return_value=_completion(json.dumps(_valid_payload()), tokens=120)
    )
    return gw


# ─── Spec sanity ────────────────────────────────────────────────────────────


class TestLandingPageSpec:
    def test_spec_id_and_label(self):
        assert LANDING_PAGE.id == "landing_page"
        assert LANDING_PAGE.label == "Landing Page"

    def test_spec_schema_has_required_fields(self):
        props = LANDING_PAGE.output_schema["properties"]
        for key in [
            "hero_headline",
            "hero_subhead",
            "benefits",
            "social_proof_section",
            "faq",
            "cta",
            "form_fields",
        ]:
            assert key in props
        assert props["benefits"]["minItems"] == 3
        assert props["benefits"]["maxItems"] == 3

    def test_spec_prompt_has_placeholders(self):
        for ph in ["{campaign}", "{creative_direction}", "{domain_context}"]:
            assert ph in LANDING_PAGE.prompt_template


# ─── Generator success ──────────────────────────────────────────────────────


class TestGenerateLandingPage:
    def test_returns_dict_with_all_required_keys(
        self, campaign, creative_direction, domain_context, mock_gateway
    ):
        result = generate_landing_page(
            campaign, creative_direction, domain_context,
            gateway=mock_gateway, tenant_id="t-1", plan="agency",
        )
        assert isinstance(result, dict)
        for key in [
            "hero_headline",
            "hero_subhead",
            "benefits",
            "social_proof_section",
            "faq",
            "cta",
            "form_fields",
        ]:
            assert key in result

    def test_hero_headline_and_subhead_are_strings(
        self, campaign, creative_direction, domain_context, mock_gateway
    ):
        result = generate_landing_page(
            campaign, creative_direction, domain_context,
            gateway=mock_gateway, tenant_id="t-1", plan="agency",
        )
        assert isinstance(result["hero_headline"], str) and result["hero_headline"]
        assert isinstance(result["hero_subhead"], str) and result["hero_subhead"]

    def test_benefits_is_exactly_3_strings(
        self, campaign, creative_direction, domain_context, mock_gateway
    ):
        result = generate_landing_page(
            campaign, creative_direction, domain_context,
            gateway=mock_gateway, tenant_id="t-1", plan="agency",
        )
        benefits = result["benefits"]
        assert isinstance(benefits, list)
        assert len(benefits) == 3
        assert all(isinstance(b, str) and b for b in benefits)

    def test_social_proof_section_is_string(
        self, campaign, creative_direction, domain_context, mock_gateway
    ):
        result = generate_landing_page(
            campaign, creative_direction, domain_context,
            gateway=mock_gateway, tenant_id="t-1", plan="agency",
        )
        assert isinstance(result["social_proof_section"], str)
        assert result["social_proof_section"]

    def test_faq_is_list(
        self, campaign, creative_direction, domain_context, mock_gateway
    ):
        result = generate_landing_page(
            campaign, creative_direction, domain_context,
            gateway=mock_gateway, tenant_id="t-1", plan="agency",
        )
        assert isinstance(result["faq"], list)
        assert all(isinstance(q, str) for q in result["faq"])
        assert len(result["faq"]) >= 1

    def test_cta_is_string(
        self, campaign, creative_direction, domain_context, mock_gateway
    ):
        result = generate_landing_page(
            campaign, creative_direction, domain_context,
            gateway=mock_gateway, tenant_id="t-1", plan="agency",
        )
        assert isinstance(result["cta"], str) and result["cta"]

    def test_form_fields_is_list(
        self, campaign, creative_direction, domain_context, mock_gateway
    ):
        result = generate_landing_page(
            campaign, creative_direction, domain_context,
            gateway=mock_gateway, tenant_id="t-1", plan="agency",
        )
        assert isinstance(result["form_fields"], list)
        assert all(isinstance(f, str) for f in result["form_fields"])
        assert len(result["form_fields"]) >= 1

    def test_gateway_called_with_tier_large(
        self, campaign, creative_direction, domain_context, mock_gateway
    ):
        from prachar_shared.ai_gateway import Tier

        generate_landing_page(
            campaign, creative_direction, domain_context,
            gateway=mock_gateway, tenant_id="t-1", plan="agency",
        )
        assert mock_gateway.complete.called
        _, kwargs = mock_gateway.complete.call_args
        assert kwargs.get("tier") == Tier.large

    def test_gateway_called_with_landing_page_task(
        self, campaign, creative_direction, domain_context, mock_gateway
    ):
        generate_landing_page(
            campaign, creative_direction, domain_context,
            gateway=mock_gateway, tenant_id="t-1", plan="agency",
        )
        _, kwargs = mock_gateway.complete.call_args
        assert kwargs.get("task") == "creative_studio_landing_page"

    def test_uses_json_value_when_provided(
        self, campaign, creative_direction, domain_context
    ):
        """When the gateway returns a pre-parsed json_value, it is preferred."""
        payload = _valid_payload()
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=Completion(
                text="ignored",
                json_value=payload,
                tokens_used=50,
                model="test-model",
                confidence=0.9,
            )
        )
        result = generate_landing_page(
            campaign, creative_direction, domain_context,
            gateway=gw, tenant_id="t-1", plan="agency",
        )
        assert result["hero_headline"] == payload["hero_headline"]
        assert len(result["benefits"]) == 3


# ─── Graceful fallback ──────────────────────────────────────────────────────


class TestLandingPageFallback:
    def test_gateway_raises_returns_well_formed_empty_dict(
        self, campaign, creative_direction, domain_context
    ):
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=RuntimeError("boom"))
        result = generate_landing_page(
            campaign, creative_direction, domain_context,
            gateway=gw, tenant_id="t-1", plan="agency",
        )
        # Fallback is a dict with all required keys + exactly 3 benefits.
        assert isinstance(result, dict)
        for key in [
            "hero_headline",
            "hero_subhead",
            "benefits",
            "social_proof_section",
            "faq",
            "cta",
            "form_fields",
        ]:
            assert key in result
        assert isinstance(result["benefits"], list)
        assert len(result["benefits"]) == 3
        assert result["benefits"] == ["", "", ""]
        assert isinstance(result["faq"], list)
        assert isinstance(result["form_fields"], list)

    def test_unparseable_json_returns_normalised_empty(
        self, campaign, creative_direction, domain_context
    ):
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_completion("not json at all {{{", tokens=10)
        )
        result = generate_landing_page(
            campaign, creative_direction, domain_context,
            gateway=gw, tenant_id="t-1", plan="agency",
        )
        assert isinstance(result, dict)
        assert len(result["benefits"]) == 3
        assert result["hero_headline"] == ""
        assert result["faq"] == []
        assert result["form_fields"] == []

    def test_missing_benefits_padded_to_3(
        self, campaign, creative_direction, domain_context
    ):
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_completion(
                json.dumps({"hero_headline": "Hi", "cta": "Go"}), tokens=10
            )
        )
        result = generate_landing_page(
            campaign, creative_direction, domain_context,
            gateway=gw, tenant_id="t-1", plan="agency",
        )
        assert len(result["benefits"]) == 3
        assert result["benefits"] == ["", "", ""]
        assert result["hero_headline"] == "Hi"
        assert result["cta"] == "Go"

    def test_too_many_benefits_trimmed_to_3(
        self, campaign, creative_direction, domain_context
    ):
        payload = _valid_payload()
        payload["benefits"] = ["b1", "b2", "b3", "b4", "b5"]
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_completion(json.dumps(payload), tokens=10)
        )
        result = generate_landing_page(
            campaign, creative_direction, domain_context,
            gateway=gw, tenant_id="t-1", plan="agency",
        )
        assert len(result["benefits"]) == 3
        assert result["benefits"] == ["b1", "b2", "b3"]

    def test_non_dict_json_returns_empty_normalised(
        self, campaign, creative_direction, domain_context
    ):
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_completion(json.dumps(["not", "an", "object"]), tokens=10)
        )
        result = generate_landing_page(
            campaign, creative_direction, domain_context,
            gateway=gw, tenant_id="t-1", plan="agency",
        )
        assert isinstance(result, dict)
        assert len(result["benefits"]) == 3

    def test_budget_exceeded_is_reraised(
        self, campaign, creative_direction, domain_context
    ):
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=BudgetExceeded("over budget"))
        with pytest.raises(BudgetExceeded):
            generate_landing_page(
                campaign, creative_direction, domain_context,
                gateway=gw, tenant_id="t-1", plan="agency",
            )
