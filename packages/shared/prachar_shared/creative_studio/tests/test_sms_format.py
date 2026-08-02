"""Tests for the SMS creative format generator (Part P2.13)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import BudgetExceeded, Completion
from prachar_shared.creative_studio.formats.sms import (
    DEFAULT_OPT_OUT_LANGUAGE,
    generate_sms,
)


# ─── Helpers ───────────────────────────────────────────────────────────────


def _make_completion(text: str, tokens: int = 80) -> Completion:
    return Completion(
        text=text,
        tokens_used=tokens,
        model="test-model",
        confidence=0.9,
    )


def _valid_sms_payload() -> dict:
    """A well-formed SMS payload the model might return."""
    return {
        "variants": [
            {"char_count": 96, "message": "Summer Sale! 40% off all tees. Shop now: prachar.io/sale Reply STOP to unsubscribe"},
            {"char_count": 88, "message": "Beat the heat with 40% off. Today only. prachar.io Reply STOP to unsubscribe"},
        ],
        "opt_out_language": "Reply STOP to unsubscribe",
    }


@pytest.fixture()
def mock_gateway():
    """A MagicMock AIGateway whose complete() returns valid SMS JSON."""
    gw = MagicMock()
    gw.complete = MagicMock(
        return_value=_make_completion(json.dumps(_valid_sms_payload()))
    )
    return gw


@pytest.fixture()
def failing_gateway():
    """A gateway whose complete() raises a generic RuntimeError."""
    gw = MagicMock()
    gw.complete = MagicMock(side_effect=RuntimeError("gateway exploded"))
    return gw


@pytest.fixture()
def budget_gateway():
    """A gateway whose complete() raises BudgetExceeded."""
    gw = MagicMock()
    gw.complete = MagicMock(side_effect=BudgetExceeded("budget exhausted"))
    return gw


@pytest.fixture()
def bad_json_gateway():
    """A gateway whose complete() returns non-JSON text."""
    gw = MagicMock()
    gw.complete = MagicMock(return_value=_make_completion("sorry, I cannot help with that"))
    return gw


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
        "sample_cta": "Shop now",
    }


@pytest.fixture()
def sample_domain_context() -> dict:
    return {"id": "business", "label": "Business Growth"}


# ─── Happy path ────────────────────────────────────────────────────────────


class TestGenerateSmsHappyPath:
    def test_returns_dict(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_sms(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
        )
        assert isinstance(result, dict)

    def test_has_two_variants(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_sms(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
        )
        assert "variants" in result
        assert isinstance(result["variants"], list)
        assert len(result["variants"]) == 2

    def test_each_variant_has_char_count_and_message(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_sms(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
        )
        for v in result["variants"]:
            assert isinstance(v, dict)
            assert "char_count" in v
            assert "message" in v
            assert isinstance(v["char_count"], int)
            assert isinstance(v["message"], str)

    def test_has_opt_out_language(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_sms(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
        )
        assert "opt_out_language" in result
        assert isinstance(result["opt_out_language"], str)
        assert result["opt_out_language"]

    def test_opt_out_language_matches_payload(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_sms(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
        )
        assert result["opt_out_language"] == "Reply STOP to unsubscribe"

    def test_gateway_called_with_large_tier(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        from prachar_shared.ai_gateway import Tier

        generate_sms(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
            tenant_id="t-1",
            plan="growth",
        )
        mock_gateway.complete.assert_called_once()
        kwargs = mock_gateway.complete.call_args.kwargs
        assert kwargs["tier"] == Tier.large
        assert kwargs["task"] == "creative_studio_sms"
        assert kwargs["tenant_id"] == "t-1"
        assert kwargs["plan"] == "growth"


# ─── Graceful fallback ─────────────────────────────────────────────────────


class TestGenerateSmsFallback:
    def test_gateway_failure_returns_schema_compliant_dict(
        self,
        failing_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_sms(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=failing_gateway,
        )
        assert isinstance(result, dict)
        assert "variants" in result
        assert len(result["variants"]) == 2
        for v in result["variants"]:
            assert "char_count" in v
            assert "message" in v
            assert v["char_count"] == 0
            assert v["message"] == ""
        assert result["opt_out_language"] == DEFAULT_OPT_OUT_LANGUAGE

    def test_bad_json_returns_schema_compliant_dict(
        self,
        bad_json_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_sms(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=bad_json_gateway,
        )
        assert isinstance(result, dict)
        assert len(result["variants"]) == 2
        assert result["opt_out_language"] == DEFAULT_OPT_OUT_LANGUAGE

    def test_missing_variants_padded_to_two(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_make_completion(json.dumps({"opt_out_language": "Text STOP to opt out"}))
        )
        result = generate_sms(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
        )
        assert len(result["variants"]) == 2
        for v in result["variants"]:
            assert v["char_count"] == 0
            assert v["message"] == ""
        assert result["opt_out_language"] == "Text STOP to opt out"

    def test_missing_opt_out_uses_default(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        payload = {
            "variants": [
                {"char_count": 50, "message": "Sale! Reply STOP to unsubscribe"},
                {"char_count": 48, "message": "40% off today. Reply STOP to unsubscribe"},
            ],
        }
        gw = MagicMock()
        gw.complete = MagicMock(return_value=_make_completion(json.dumps(payload)))
        result = generate_sms(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
        )
        assert result["opt_out_language"] == DEFAULT_OPT_OUT_LANGUAGE

    def test_extra_variants_truncated_to_two(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        payload = {
            "variants": [
                {"char_count": 50, "message": "v1 Reply STOP to unsubscribe"},
                {"char_count": 50, "message": "v2 Reply STOP to unsubscribe"},
                {"char_count": 50, "message": "v3 Reply STOP to unsubscribe"},
            ],
            "opt_out_language": "Reply STOP to unsubscribe",
        }
        gw = MagicMock()
        gw.complete = MagicMock(return_value=_make_completion(json.dumps(payload)))
        result = generate_sms(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
        )
        assert len(result["variants"]) == 2

    def test_invalid_char_count_recomputed(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        msg = "Sale! 40% off. Reply STOP to unsubscribe"
        payload = {
            "variants": [
                {"char_count": "not-a-number", "message": msg},
                {"char_count": -5, "message": msg},
            ],
            "opt_out_language": "Reply STOP to unsubscribe",
        }
        gw = MagicMock()
        gw.complete = MagicMock(return_value=_make_completion(json.dumps(payload)))
        result = generate_sms(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
        )
        for v in result["variants"]:
            assert v["char_count"] == len(msg)


# ─── Budget exceeded propagation ───────────────────────────────────────────


class TestGenerateSmsBudget:
    def test_budget_exceeded_is_raised(
        self,
        budget_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        with pytest.raises(BudgetExceeded):
            generate_sms(
                sample_campaign,
                sample_creative_direction,
                sample_domain_context,
                gateway=budget_gateway,
            )
