"""Tests for the review suggestion engine (P3.3).

Verifies that generate_suggestions returns 3-5 suggestions with the required
fields (what_to_change, why, suggested_replacement), falls back gracefully on
AI failure, and that Suggestion.to_dict() is correct.
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import Completion
from prachar_shared.marketing_intelligence.review_engine import (
    Suggestion,
    generate_suggestions,
)


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def campaign_context():
    """A minimal campaign context dict."""
    return {
        "brand_name": "Paradise Biryani",
        "goal": "get more catering orders",
        "budget": "₹15,000",
        "network": "google_ads",
        "objective": "traffic",
        "audience": "Hyderabad professionals aged 25-45",
        "campaign_analysis": "The brand is known for Hyderabadi biryani.",
    }


@pytest.fixture
def suggestions_response():
    """A well-formed 4-suggestion JSON response from the AI gateway."""
    return {
        "suggestions": [
            {
                "what_to_change": "Headline",
                "why": "The current headline is too generic; adding a specific dish name increases relevance.",
                "suggested_replacement": "Hyderabad's Best Biryani — Order for Your Office Lunch",
            },
            {
                "what_to_change": "Call-to-action",
                "why": "A clearer CTA drives higher click-through rates.",
                "suggested_replacement": "Book your catering order today and get 10% off.",
            },
            {
                "what_to_change": "Audience targeting",
                "why": "Narrowing to office workers near IT corridors improves ROI.",
                "suggested_replacement": "Target: Hyderabad IT corridor, age 25-45, interest: corporate events",
            },
            {
                "what_to_change": "Budget allocation",
                "why": "Spreading budget across lunch hours captures decision-makers.",
                "suggested_replacement": "Daypart: 70% budget 11am-2pm, 30% evenings",
            },
        ]
    }


def _make_gateway(response_dict: dict) -> MagicMock:
    """Build a mock AIGateway whose complete() returns the given dict as JSON."""
    gw = MagicMock()
    gw.complete = MagicMock(
        return_value=Completion(
            text=json.dumps(response_dict),
            tokens_used=400,
            model="test-model",
            confidence=0.9,
        )
    )
    return gw


# ─── Tests ─────────────────────────────────────────────────────────────────


class TestGenerateSuggestions:
    """Tests for generate_suggestions()."""

    def test_returns_3_to_5_suggestions(
        self, campaign_context, suggestions_response,
    ):
        """generate_suggestions returns between 3 and 5 suggestions."""
        gw = _make_gateway(suggestions_response)
        suggestions = generate_suggestions(
            campaign_context=campaign_context,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert 3 <= len(suggestions) <= 5
        assert len(suggestions) == 4

    def test_each_suggestion_has_required_fields(
        self, campaign_context, suggestions_response,
    ):
        """Each suggestion has what_to_change, why, and suggested_replacement."""
        gw = _make_gateway(suggestions_response)
        suggestions = generate_suggestions(
            campaign_context=campaign_context,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        required = {"what_to_change", "why", "suggested_replacement"}
        for s in suggestions:
            assert isinstance(s, Suggestion)
            d = s.to_dict()
            assert required.issubset(d.keys()), (
                f"Suggestion missing keys: {required - set(d.keys())}"
            )

    def test_suggestion_fields_are_non_empty(
        self, campaign_context, suggestions_response,
    ):
        """Each suggestion's fields are non-empty strings."""
        gw = _make_gateway(suggestions_response)
        suggestions = generate_suggestions(
            campaign_context=campaign_context,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for s in suggestions:
            assert isinstance(s.what_to_change, str) and s.what_to_change
            assert isinstance(s.why, str) and s.why
            assert isinstance(s.suggested_replacement, str) and s.suggested_replacement

    def test_falls_back_to_empty_list_on_ai_failure(
        self, campaign_context,
    ):
        """When the AI gateway raises, generate_suggestions returns []."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=RuntimeError("AI is down"))
        suggestions = generate_suggestions(
            campaign_context=campaign_context,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert suggestions == []

    def test_falls_back_to_empty_list_on_bad_json(
        self, campaign_context,
    ):
        """When the AI returns unparseable JSON, generate_suggestions returns []."""
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=Completion(
                text="this is not json at all",
                tokens_used=10,
                model="test-model",
                confidence=0.1,
            )
        )
        suggestions = generate_suggestions(
            campaign_context=campaign_context,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert suggestions == []

    def test_handles_missing_suggestions_key(
        self, campaign_context,
    ):
        """If the JSON has no 'suggestions' key, returns []."""
        gw = _make_gateway({"other": "data"})
        suggestions = generate_suggestions(
            campaign_context=campaign_context,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert suggestions == []

    def test_handles_five_suggestions(
        self, campaign_context,
    ):
        """When the AI returns 5 suggestions, all 5 are returned."""
        five = {
            "suggestions": [
                {
                    "what_to_change": f"Element {i}",
                    "why": f"Reason {i}",
                    "suggested_replacement": f"Replacement {i}",
                }
                for i in range(1, 6)
            ]
        }
        gw = _make_gateway(five)
        suggestions = generate_suggestions(
            campaign_context=campaign_context,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(suggestions) == 5

    def test_uses_tier_large(
        self, campaign_context, suggestions_response,
    ):
        """generate_suggestions calls the gateway with Tier.large."""
        from prachar_shared.ai_gateway import Tier

        gw = _make_gateway(suggestions_response)
        generate_suggestions(
            campaign_context=campaign_context,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        gw.complete.assert_called_once()
        assert gw.complete.call_args.kwargs["tier"] == Tier.large


class TestSuggestionToDict:
    """Tests for Suggestion.to_dict()."""

    def test_to_dict_returns_all_fields(self):
        """to_dict() returns a dict with all three fields."""
        s = Suggestion(
            what_to_change="Headline",
            why="Too generic",
            suggested_replacement="New headline",
        )
        d = s.to_dict()
        assert d == {
            "what_to_change": "Headline",
            "why": "Too generic",
            "suggested_replacement": "New headline",
        }

    def test_to_dict_keys_match_dataclass_fields(self):
        """to_dict() keys are exactly the dataclass field names."""
        s = Suggestion(what_to_change="a", why="b", suggested_replacement="c")
        d = s.to_dict()
        assert set(d.keys()) == {"what_to_change", "why", "suggested_replacement"}

    def test_to_dict_preserves_empty_strings(self):
        """to_dict() preserves empty string values."""
        s = Suggestion(what_to_change="", why="", suggested_replacement="")
        d = s.to_dict()
        assert d["what_to_change"] == ""
        assert d["why"] == ""
        assert d["suggested_replacement"] == ""
