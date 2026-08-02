"""Tests for the LinkedIn creative format generator (P2.10)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import BudgetExceeded, Completion
from prachar_shared.creative_studio.formats.linkedin import (
    LINKEDIN,
    LINKEDIN_BODY_MAX_CHARS,
    generate_linkedin,
)


# ─── Helpers ────────────────────────────────────────────────────────────────


def _make_completion(text: str, tokens: int = 100) -> Completion:
    return Completion(
        text=text,
        tokens_used=tokens,
        model="test-model",
        confidence=0.9,
    )


def _valid_linkedin_json(
    *,
    hook: str = "Stop scrolling if you run a B2B SaaS.",
    body: str = "Here is the insight that changed how we sell.",
    cta: str = "DM me 'GROWTH' for the full playbook.",
    hashtags: list[str] | None = None,
) -> str:
    if hashtags is None:
        hashtags = ["saas", "b2b", "growth", "marketing"]
    return json.dumps(
        {"hook": hook, "body": body, "cta": cta, "hashtags": hashtags}
    )


@pytest.fixture()
def mock_gateway():
    """A MagicMock AIGateway whose complete() returns valid LinkedIn JSON."""
    gw = MagicMock()
    gw.complete = MagicMock(
        return_value=_make_completion(_valid_linkedin_json(), tokens=120)
    )
    return gw


@pytest.fixture()
def failing_gateway():
    """A gateway whose complete() always raises a generic error."""
    gw = MagicMock()
    gw.complete = MagicMock(side_effect=RuntimeError("boom"))
    return gw


@pytest.fixture()
def budget_gateway():
    """A gateway whose complete() always raises BudgetExceeded."""
    gw = MagicMock()
    gw.complete = MagicMock(side_effect=BudgetExceeded("over budget"))
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
    return {
        "id": "business",
        "label": "Business Growth",
        "customer_type": "business",
    }


# ─── Spec sanity ────────────────────────────────────────────────────────────


class TestSpec:
    def test_spec_id_and_label(self):
        assert LINKEDIN.id == "linkedin"
        assert LINKEDIN.label == "LinkedIn"

    def test_schema_has_required_fields(self):
        props = LINKEDIN.output_schema["properties"]
        for key in ["hook", "body", "cta", "hashtags"]:
            assert key in props
        assert props["body"]["maxLength"] == 3000
        assert "hook" in LINKEDIN.output_schema["required"]

    def test_prompt_has_placeholders(self):
        for ph in ["{campaign}", "{creative_direction}", "{domain_context}"]:
            assert ph in LINKEDIN.prompt_template

    def test_body_max_constant(self):
        assert LINKEDIN_BODY_MAX_CHARS == 3000


# ─── generate_linkedin — success ────────────────────────────────────────────


class TestGenerateLinkedInSuccess:
    def test_returns_dict_with_required_keys(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_linkedin(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert isinstance(result, dict)
        for key in ["hook", "body", "cta", "hashtags"]:
            assert key in result

    def test_hook_is_string(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_linkedin(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert isinstance(result["hook"], str)
        assert result["hook"]

    def test_body_is_string_and_within_limit(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_linkedin(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert isinstance(result["body"], str)
        assert len(result["body"]) <= LINKEDIN_BODY_MAX_CHARS

    def test_cta_is_string(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_linkedin(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert isinstance(result["cta"], str)

    def test_hashtags_is_list_of_strings(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_linkedin(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert isinstance(result["hashtags"], list)
        assert len(result["hashtags"]) >= 0
        for h in result["hashtags"]:
            assert isinstance(h, str)

    def test_gateway_called_with_large_tier(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        from prachar_shared.ai_gateway import Tier

        generate_linkedin(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert mock_gateway.complete.called
        kwargs = mock_gateway.complete.call_args.kwargs
        assert kwargs["tier"] == Tier.large
        assert kwargs["task"] == "creative_studio_linkedin"
        assert kwargs["plan"] == "agency"
        assert kwargs["tenant_id"] == "tenant-1"

    def test_prompt_contains_campaign_context(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        generate_linkedin(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
            tenant_id="tenant-1",
            plan="agency",
        )
        sent_prompt = mock_gateway.complete.call_args.kwargs["prompt"]
        assert "Summer Sale Campaign" in sent_prompt
        assert "Beat the heat" in sent_prompt
        assert "Business Growth" in sent_prompt


# ─── generate_linkedin — body truncation ────────────────────────────────────


class TestBodyTruncation:
    def test_body_truncated_to_3000_chars(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        long_body = "A" * 5000
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_make_completion(
                _valid_linkedin_json(body=long_body), tokens=200
            )
        )
        result = generate_linkedin(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert len(result["body"]) == LINKEDIN_BODY_MAX_CHARS
        assert result["body"] == "A" * LINKEDIN_BODY_MAX_CHARS

    def test_body_exactly_3000_not_truncated(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        exact_body = "B" * LINKEDIN_BODY_MAX_CHARS
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_make_completion(
                _valid_linkedin_json(body=exact_body), tokens=200
            )
        )
        result = generate_linkedin(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert len(result["body"]) == LINKEDIN_BODY_MAX_CHARS


# ─── generate_linkedin — hashtag normalisation ──────────────────────────────


class TestHashtagNormalisation:
    def test_leading_hash_stripped(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_make_completion(
                _valid_linkedin_json(hashtags=["#saas", "#b2b", "growth"]),
                tokens=100,
            )
        )
        result = generate_linkedin(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert result["hashtags"] == ["saas", "b2b", "growth"]

    def test_non_list_hashtags_become_empty_list(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_make_completion(
                json.dumps(
                    {
                        "hook": "h",
                        "body": "b",
                        "cta": "c",
                        "hashtags": "not a list",
                    }
                ),
                tokens=100,
            )
        )
        result = generate_linkedin(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert result["hashtags"] == []


# ─── generate_linkedin — graceful fallback ──────────────────────────────────


class TestGracefulFallback:
    def test_gateway_error_returns_empty_dict(
        self,
        failing_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_linkedin(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=failing_gateway,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert isinstance(result, dict)
        assert result == {"hook": "", "body": "", "cta": "", "hashtags": []}

    def test_unparseable_json_returns_empty_dict(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_make_completion("this is not json at all", tokens=10)
        )
        result = generate_linkedin(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert result == {"hook": "", "body": "", "cta": "", "hashtags": []}

    def test_empty_response_returns_empty_dict(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_make_completion("", tokens=0)
        )
        result = generate_linkedin(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert result == {"hook": "", "body": "", "cta": "", "hashtags": []}

    def test_budget_exceeded_is_raised(
        self,
        budget_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        with pytest.raises(BudgetExceeded):
            generate_linkedin(
                sample_campaign,
                sample_creative_direction,
                sample_domain_context,
                gateway=budget_gateway,
                tenant_id="tenant-1",
                plan="agency",
            )

    def test_fallback_body_within_limit(
        self,
        failing_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_linkedin(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=failing_gateway,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert len(result["body"]) <= LINKEDIN_BODY_MAX_CHARS


# ─── generate_linkedin — markdown-fenced JSON ───────────────────────────────


class TestMarkdownFencedJSON:
    def test_parses_fenced_json(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        fenced = (
            "Here is your post:\n"
            "```json\n"
            + _valid_linkedin_json()
            + "\n```\n"
        )
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=_make_completion(fenced, tokens=120)
        )
        result = generate_linkedin(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
            tenant_id="tenant-1",
            plan="agency",
        )
        assert result["hook"] == "Stop scrolling if you run a B2B SaaS."
        assert result["cta"] == "DM me 'GROWTH' for the full playbook."
        assert "saas" in result["hashtags"]
