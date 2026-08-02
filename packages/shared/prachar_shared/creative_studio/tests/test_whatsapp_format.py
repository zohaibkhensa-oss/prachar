"""Tests for the WhatsApp creative format generator (formats/whatsapp.py).

Part P2.8 of the PRACHAR roadmap. Verifies that ``generate_whatsapp``:
  - returns a dict with status_text, status_image_brief, broadcast_message,
  - parses the AIGateway JSON response via extract_json,
  - falls back gracefully to an empty-shaped dict on failure,
  - re-raises BudgetExceeded (budget enforcement not swallowed),
  - passes Tier.large to the gateway.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import BudgetExceeded, Completion, Tier
from prachar_shared.creative_studio.formats.whatsapp import (
    WHATSAPP,
    generate_whatsapp,
)


# ─── Helpers ───────────────────────────────────────────────────────────────


def _make_completion(text: str, tokens: int = 80) -> Completion:
    return Completion(
        text=text,
        tokens_used=tokens,
        model="test-model",
        confidence=0.9,
    )


def _valid_payload() -> dict:
    return {
        "status_text": "Beat the heat with 40% off ☀️",
        "status_image_brief": "Bright yellow background, sunglasses, sale tag",
        "broadcast_message": (
            "Hi! You opted in to our updates. Beat the heat with 40% off "
            "this week only. Reply STOP to opt out."
        ),
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
def sample_domain_context() -> dict:
    return {
        "id": "business",
        "label": "Business Growth",
        "customer_type": "business",
    }


@pytest.fixture()
def mock_gateway():
    """A MagicMock AIGateway whose complete() returns valid WhatsApp JSON."""
    gw = MagicMock()
    gw.complete = MagicMock(
        return_value=_make_completion(json.dumps(_valid_payload()))
    )
    return gw


@pytest.fixture()
def failing_gateway():
    """A gateway whose complete() always raises RuntimeError."""
    gw = MagicMock()
    gw.complete = MagicMock(side_effect=RuntimeError("boom"))
    return gw


# ─── Spec sanity ───────────────────────────────────────────────────────────


class TestWhatsappSpec:
    def test_spec_id(self):
        assert WHATSAPP.id == "whatsapp"

    def test_spec_required_output_keys(self):
        props = WHATSAPP.output_schema["properties"]
        for key in ("status_text", "status_image_brief", "broadcast_message"):
            assert key in props

    def test_spec_prompt_has_placeholders(self):
        for ph in ("{campaign}", "{creative_direction}", "{domain_context}"):
            assert ph in WHATSAPP.prompt_template

    def test_spec_prompt_mentions_compliance(self):
        assert "opt-out" in WHATSAPP.prompt_template.lower()
        assert "opt-in" in WHATSAPP.prompt_template.lower()


# ─── generate_whatsapp — success ───────────────────────────────────────────


class TestGenerateWhatsappSuccess:
    def test_returns_dict_with_required_keys(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_whatsapp(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
        )
        assert isinstance(result, dict)
        for key in ("status_text", "status_image_brief", "broadcast_message"):
            assert key in result
            assert isinstance(result[key], str)

    def test_parses_gateway_json(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_whatsapp(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
        )
        assert result["status_text"] == "Beat the heat with 40% off ☀️"
        assert "sunglasses" in result["status_image_brief"]
        assert "Reply STOP" in result["broadcast_message"]

    def test_calls_gateway_with_tier_large(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        generate_whatsapp(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
        )
        assert mock_gateway.complete.called
        kwargs = mock_gateway.complete.call_args.kwargs
        assert kwargs["tier"] is Tier.large

    def test_calls_gateway_with_whatsapp_task(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        generate_whatsapp(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
        )
        kwargs = mock_gateway.complete.call_args.kwargs
        assert kwargs["task"] == "creative_studio_whatsapp"

    def test_prompt_includes_campaign_content(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        generate_whatsapp(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
        )
        prompt = mock_gateway.complete.call_args.kwargs["prompt"]
        assert "Summer Sale Campaign" in prompt
        assert "Beat the heat" in prompt

    def test_passes_tenant_id_and_plan(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        generate_whatsapp(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
            tenant_id="tenant-abc",
            plan="growth",
        )
        kwargs = mock_gateway.complete.call_args.kwargs
        assert kwargs["tenant_id"] == "tenant-abc"
        assert kwargs["plan"] == "growth"


# ─── generate_whatsapp — parsing edge cases ────────────────────────────────


class TestGenerateWhatsappParsing:
    def test_handles_markdown_fenced_json(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_make_completion(
                "```json\n" + json.dumps(_valid_payload()) + "\n```"
            )
        )
        result = generate_whatsapp(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
        )
        assert result["status_text"] == "Beat the heat with 40% off ☀️"

    def test_normalises_missing_keys(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_make_completion(
                json.dumps({"status_text": "only status"})
            )
        )
        result = generate_whatsapp(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
        )
        assert result["status_text"] == "only status"
        assert result["status_image_brief"] == ""
        assert result["broadcast_message"] == ""

    def test_normalises_non_dict_response(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_make_completion("not json at all")
        )
        result = generate_whatsapp(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
        )
        assert isinstance(result, dict)
        for key in ("status_text", "status_image_brief", "broadcast_message"):
            assert result[key] == ""


# ─── generate_whatsapp — fallback ──────────────────────────────────────────


class TestGenerateWhatsappFallback:
    def test_falls_back_to_empty_dict_on_gateway_error(
        self,
        failing_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_whatsapp(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=failing_gateway,
        )
        assert isinstance(result, dict)
        for key in ("status_text", "status_image_brief", "broadcast_message"):
            assert key in result
            assert result[key] == ""

    def test_reraises_budget_exceeded(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=BudgetExceeded("over budget"))
        with pytest.raises(BudgetExceeded):
            generate_whatsapp(
                sample_campaign,
                sample_creative_direction,
                sample_domain_context,
                gateway=gw,
            )
