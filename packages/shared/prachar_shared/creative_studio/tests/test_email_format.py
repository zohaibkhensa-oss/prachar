"""Tests for the email creative format generator (P2.11)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import BudgetExceeded, Completion
from prachar_shared.creative_studio.formats.email import EMAIL, generate_email


# ─── Fixtures ──────────────────────────────────────────────────────────────


def _make_completion(text: str, tokens: int = 120) -> Completion:
    return Completion(
        text=text,
        tokens_used=tokens,
        model="test-model",
        confidence=0.9,
    )


@pytest.fixture()
def sample_campaign() -> dict:
    return {
        "id": "camp-123",
        "name": "Summer Sale Campaign",
        "goal": "increase sales",
        "budget": "₹50,000",
        "preview": {"title": "Summer Sale"},
    }


@pytest.fixture()
def sample_creative_direction() -> dict:
    return {
        "id": "cd-456",
        "hook": "Beat the heat",
        "angle": "Urgency + value",
        "tone": "energetic",
        "sample_headline": "Summer's hottest deals",
        "sample_cta": "Shop now",
    }


@pytest.fixture()
def sample_domain_context() -> dict:
    return {
        "id": "business",
        "label": "Business Growth",
        "customer_type": "business",
    }


def _valid_email_payload() -> dict:
    return {
        "subject_lines": [
            "Last chance: Summer Sale ends tonight",
            "Your 40% off code is inside",
            "Don't let these deals melt away",
        ],
        "preview_text": "Open now — the season's best prices won't last.",
        "body_html_brief": "Hero banner with offer → 3 benefit blocks → social proof → CTA button → PS.",
        "cta": "Shop the Summer Sale",
        "ps_line": "P.S. Free shipping on orders over ₹999 — today only.",
    }


@pytest.fixture()
def mock_gateway():
    gw = MagicMock()
    gw.complete = MagicMock(
        return_value=_make_completion(json.dumps(_valid_email_payload()))
    )
    return gw


@pytest.fixture()
def failing_gateway():
    gw = MagicMock()
    gw.complete = MagicMock(side_effect=RuntimeError("email generation exploded"))
    return gw


@pytest.fixture()
def budget_exceeded_gateway():
    gw = MagicMock()
    gw.complete = MagicMock(side_effect=BudgetExceeded("budget exhausted"))
    return gw


@pytest.fixture()
def malformed_gateway():
    gw = MagicMock()
    gw.complete = MagicMock(return_value=_make_completion("not json at all <<<"))
    return gw


# ─── Spec sanity ───────────────────────────────────────────────────────────


class TestEmailSpec:
    def test_spec_id_and_label(self):
        assert EMAIL.id == "email"
        assert EMAIL.label == "Email"

    def test_spec_schema_requires_3_subject_lines(self):
        props = EMAIL.output_schema["properties"]
        assert props["subject_lines"]["minItems"] == 3
        assert props["subject_lines"]["maxItems"] == 3
        for key in ["subject_lines", "preview_text", "body_html_brief", "cta", "ps_line"]:
            assert key in props
        assert "subject_lines" in EMAIL.output_schema["required"]

    def test_prompt_template_has_placeholders(self):
        for ph in ["{campaign}", "{creative_direction}", "{domain_context}"]:
            assert ph in EMAIL.prompt_template

    def test_prompt_template_asks_for_exactly_3_subject_lines(self):
        assert "exactly 3" in EMAIL.prompt_template.lower()


# ─── generate_email — happy path ───────────────────────────────────────────


class TestGenerateEmailHappyPath:
    def test_returns_dict_with_required_keys(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_email(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert isinstance(result, dict)
        for key in ["subject_lines", "preview_text", "body_html_brief", "cta", "ps_line"]:
            assert key in result, f"missing key {key}"

    def test_returns_exactly_3_subject_lines(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_email(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert isinstance(result["subject_lines"], list)
        assert len(result["subject_lines"]) == 3
        assert all(isinstance(s, str) for s in result["subject_lines"])

    def test_subject_lines_match_payload(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_email(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert result["subject_lines"] == _valid_email_payload()["subject_lines"]
        assert result["preview_text"] == _valid_email_payload()["preview_text"]
        assert result["cta"] == _valid_email_payload()["cta"]
        assert result["ps_line"] == _valid_email_payload()["ps_line"]

    def test_calls_gateway_with_large_tier(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        from prachar_shared.ai_gateway import Tier

        generate_email(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert mock_gateway.complete.called
        _, kwargs = mock_gateway.complete.call_args
        assert kwargs["tier"] == Tier.large

    def test_calls_gateway_with_email_task(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        generate_email(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
            tenant_id="tenant-1",
            plan="growth",
        )
        _, kwargs = mock_gateway.complete.call_args
        assert kwargs["task"] == "creative_studio_email"
        assert kwargs["plan"] == "growth"
        assert kwargs["tenant_id"] == "tenant-1"


# ─── generate_email — fallback / failure ───────────────────────────────────


class TestGenerateEmailFallback:
    def test_failing_gateway_returns_empty_dict_with_3_subject_lines(
        self,
        failing_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_email(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=failing_gateway,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert isinstance(result, dict)
        assert isinstance(result["subject_lines"], list)
        assert len(result["subject_lines"]) == 3
        assert result["subject_lines"] == ["", "", ""]
        assert result["preview_text"] == ""
        assert result["body_html_brief"] == ""
        assert result["cta"] == ""
        assert result["ps_line"] == ""

    def test_malformed_response_falls_back_gracefully(
        self,
        malformed_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_email(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=malformed_gateway,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert isinstance(result, dict)
        assert len(result["subject_lines"]) == 3
        # All fields empty since JSON could not be parsed.
        assert result["preview_text"] == ""
        assert result["cta"] == ""

    def test_budget_exceeded_is_raised_not_swallowed(
        self,
        budget_exceeded_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        with pytest.raises(BudgetExceeded):
            generate_email(
                sample_campaign,
                sample_creative_direction,
                sample_domain_context,
                gateway=budget_exceeded_gateway,
                tenant_id="tenant-1",
                plan="agency",
            )


# ─── generate_email — subject line normalisation ───────────────────────────


class TestSubjectLineNormalisation:
    def test_fewer_than_3_subject_lines_padded(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_make_completion(
                json.dumps({"subject_lines": ["only one"], "preview_text": "p"})
            )
        )
        result = generate_email(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
            tenant_id="t",
            plan="agency",
        )
        assert len(result["subject_lines"]) == 3
        assert result["subject_lines"][0] == "only one"
        assert result["subject_lines"][1] == ""
        assert result["subject_lines"][2] == ""

    def test_more_than_3_subject_lines_truncated(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_make_completion(
                json.dumps({"subject_lines": ["a", "b", "c", "d", "e"]})
            )
        )
        result = generate_email(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
            tenant_id="t",
            plan="agency",
        )
        assert len(result["subject_lines"]) == 3
        assert result["subject_lines"] == ["a", "b", "c"]

    def test_missing_subject_lines_key_yields_3_empty(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_make_completion(
                json.dumps({"preview_text": "p", "cta": "c"})
            )
        )
        result = generate_email(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
            tenant_id="t",
            plan="agency",
        )
        assert len(result["subject_lines"]) == 3
        assert result["subject_lines"] == ["", "", ""]
