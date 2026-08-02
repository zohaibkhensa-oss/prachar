"""Tests for the A/B concept generator (P1.9).

Verifies that generate_ab_concepts returns 6 ABConcept objects (3 directions
× 2 variants), each with the required fields, variant labels are A and B,
falls back gracefully on AI failure, and re-raises BudgetExceeded.
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import BudgetExceeded, Completion
from prachar_shared.marketing_intelligence.ab_concepts import (
    ABConcept,
    generate_ab_concepts,
)

# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def creative_directions():
    """3 creative directions (as dicts, matching P1.1 output)."""
    return [
        {
            "id": "signature_dish_hero",
            "hook": "The biryani that Hyderabad can't stop talking about",
            "angle": "Lead with the signature dish as the hero",
            "tone": "Mouth-watering and proud",
            "sample_headline": "12 hours of marination. One unforgettable bite.",
            "sample_cta": "Order now on Swiggy",
        },
        {
            "id": "local_pride",
            "hook": "Hyderabad's own biryani, made the old-fashioned way",
            "angle": "Lean into local heritage and pride",
            "tone": "Warm and nostalgic",
            "sample_headline": "Made in Hyderabad. Loved by Hyderabad.",
            "sample_cta": "Visit us today",
        },
        {
            "id": "value_combo",
            "hook": "Feast for two at a price that makes sense",
            "angle": "Lead with a value combo offer",
            "tone": "Bold and practical",
            "sample_headline": "Biryani + kebab combo for two at ₹399",
            "sample_cta": "Grab the combo",
        },
    ]


@pytest.fixture
def campaign_context():
    """A minimal campaign context dict."""
    return {
        "brand_name": "Paradise Biryani",
        "goal": "get more customers",
        "budget": "₹15,000",
        "campaign_analysis": "The brand is known for Hyderabadi biryani.",
    }


@pytest.fixture
def ab_concepts_response():
    """A well-formed A/B concepts JSON response from the AI gateway."""
    return {
        "ab_concepts": [
            {
                "direction_id": "signature_dish_hero",
                "variant_label": "A",
                "what_changed": "Refined the headline to emphasise the 12-hour marination.",
                "why": "Sensory detail creates stronger craving.",
                "expected_audience_segment": "Foodies who value authenticity",
                "hook": "12 hours of marination. One unforgettable bite.",
                "headline": "The biryani worth waiting 12 hours for.",
                "cta": "Order now on Swiggy",
            },
            {
                "direction_id": "signature_dish_hero",
                "variant_label": "B",
                "what_changed": "Shifted to a social-proof angle.",
                "why": "Social proof builds trust faster than sensory claims.",
                "expected_audience_segment": "First-time customers who are hesitant",
                "hook": "Over 10,000 orders this month alone.",
                "headline": "Hyderabad's most-ordered biryani.",
                "cta": "See what the hype is about",
            },
            {
                "direction_id": "local_pride",
                "variant_label": "A",
                "what_changed": "Kept the heritage angle, sharpened the headline.",
                "why": "Heritage resonates with local pride.",
                "expected_audience_segment": "Local Hyderabad residents",
                "hook": "Hyderabad's own biryani, made the old-fashioned way.",
                "headline": "Made in Hyderabad. Loved by Hyderabad.",
                "cta": "Visit us today",
            },
            {
                "direction_id": "local_pride",
                "variant_label": "B",
                "what_changed": "Shifted to a nostalgia-for-home angle.",
                "why": "Nostalgia triggers emotional purchase decisions.",
                "expected_audience_segment": "Expats missing home-cooked biryani",
                "hook": "Tastes like home, no matter where home is.",
                "headline": "The biryani that brings Hyderabad to you.",
                "cta": "Order for a taste of home",
            },
            {
                "direction_id": "value_combo",
                "variant_label": "A",
                "what_changed": "Kept the value combo, added urgency.",
                "why": "Urgency drives faster conversion.",
                "expected_audience_segment": "Budget-conscious couples",
                "hook": "Feast for two at a price that makes sense.",
                "headline": "Biryani + kebab combo for two at ₹399 — today only.",
                "cta": "Grab the combo",
            },
            {
                "direction_id": "value_combo",
                "variant_label": "B",
                "what_changed": "Shifted to a family-sharing angle.",
                "why": "Family positioning expands the audience.",
                "expected_audience_segment": "Families looking for a shared meal",
                "hook": "One platter. The whole family. Happy.",
                "headline": "Family biryani platter — feeds four, ₹699.",
                "cta": "Order the family platter",
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


class TestGenerateABConcepts:
    """Tests for generate_ab_concepts()."""

    def test_returns_6_concepts(
        self, creative_directions, campaign_context, ab_concepts_response,
    ):
        """generate_ab_concepts returns 6 concepts (3 directions × 2 variants)."""
        gw = _make_gateway(ab_concepts_response)
        concepts = generate_ab_concepts(
            creative_directions=creative_directions,
            campaign_context=campaign_context,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert isinstance(concepts, list)
        assert len(concepts) == 6

    def test_returns_abconcept_objects(
        self, creative_directions, campaign_context, ab_concepts_response,
    ):
        """Each concept is an ABConcept dataclass instance."""
        gw = _make_gateway(ab_concepts_response)
        concepts = generate_ab_concepts(
            creative_directions=creative_directions,
            campaign_context=campaign_context,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert all(isinstance(c, ABConcept) for c in concepts)

    def test_each_concept_has_required_fields(
        self, creative_directions, campaign_context, ab_concepts_response,
    ):
        """Each concept has all 8 required fields."""
        gw = _make_gateway(ab_concepts_response)
        concepts = generate_ab_concepts(
            creative_directions=creative_directions,
            campaign_context=campaign_context,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        required = {
            "direction_id",
            "variant_label",
            "what_changed",
            "why",
            "expected_audience_segment",
            "hook",
            "headline",
            "cta",
        }
        for concept in concepts:
            d = concept.to_dict()
            assert required.issubset(set(d.keys())), (
                f"Concept missing keys: {required - set(d.keys())}"
            )

    def test_variant_labels_are_a_and_b(
        self, creative_directions, campaign_context, ab_concepts_response,
    ):
        """Each direction has exactly one A and one B variant."""
        gw = _make_gateway(ab_concepts_response)
        concepts = generate_ab_concepts(
            creative_directions=creative_directions,
            campaign_context=campaign_context,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        # Group by direction_id
        by_dir: dict[str, list[str]] = {}
        for c in concepts:
            by_dir.setdefault(c.direction_id, []).append(c.variant_label)
        assert len(by_dir) == 3
        for dir_id, labels in by_dir.items():
            assert sorted(labels) == ["A", "B"], (
                f"Direction {dir_id} has labels {labels}, expected ['A', 'B']"
            )

    def test_direction_ids_match_input(
        self, creative_directions, campaign_context, ab_concepts_response,
    ):
        """Each concept's direction_id matches one of the input creative directions."""
        gw = _make_gateway(ab_concepts_response)
        concepts = generate_ab_concepts(
            creative_directions=creative_directions,
            campaign_context=campaign_context,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        input_ids = {d["id"] for d in creative_directions}
        for c in concepts:
            assert c.direction_id in input_ids

    def test_to_dict_returns_all_fields(
        self, creative_directions, campaign_context, ab_concepts_response,
    ):
        """ABConcept.to_dict() returns a dict with all 8 fields."""
        gw = _make_gateway(ab_concepts_response)
        concepts = generate_ab_concepts(
            creative_directions=creative_directions,
            campaign_context=campaign_context,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for concept in concepts:
            d = concept.to_dict()
            assert isinstance(d, dict)
            assert set(d.keys()) == {
                "direction_id",
                "variant_label",
                "what_changed",
                "why",
                "expected_audience_segment",
                "hook",
                "headline",
                "cta",
            }

    def test_graceful_fallback_on_ai_failure(
        self, creative_directions, campaign_context,
    ):
        """generate_ab_concepts returns [] when the AI gateway raises a non-budget error."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=RuntimeError("AI is down"))
        concepts = generate_ab_concepts(
            creative_directions=creative_directions,
            campaign_context=campaign_context,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert concepts == []

    def test_budget_exceeded_reraised(
        self, creative_directions, campaign_context,
    ):
        """generate_ab_concepts re-raises BudgetExceeded."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=BudgetExceeded("budget exceeded"))
        with pytest.raises(BudgetExceeded):
            generate_ab_concepts(
                creative_directions=creative_directions,
                campaign_context=campaign_context,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )

    def test_empty_creative_directions_returns_empty(
        self, campaign_context, ab_concepts_response,
    ):
        """generate_ab_concepts returns [] when creative_directions is empty."""
        gw = _make_gateway(ab_concepts_response)
        concepts = generate_ab_concepts(
            creative_directions=[],
            campaign_context=campaign_context,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert concepts == []

    def test_uses_tier_large(
        self, creative_directions, campaign_context, ab_concepts_response,
    ):
        """generate_ab_concepts uses Tier.large for the AI call."""
        from prachar_shared.ai_gateway import Tier

        gw = _make_gateway(ab_concepts_response)
        generate_ab_concepts(
            creative_directions=creative_directions,
            campaign_context=campaign_context,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        call_kwargs = gw.complete.call_args.kwargs
        assert call_kwargs["tier"] == Tier.large

    def test_fills_missing_variants(
        self, creative_directions, campaign_context,
    ):
        """If the AI returns fewer than 2 variants per direction, the missing
        ones are filled with empty-string defaults but still labelled A/B."""
        partial_response = {
            "ab_concepts": [
                {
                    "direction_id": "signature_dish_hero",
                    "variant_label": "A",
                    "what_changed": "Refined headline.",
                    "why": "Better sensory detail.",
                    "expected_audience_segment": "Foodies",
                    "hook": "12 hours of marination.",
                    "headline": "The biryani worth waiting for.",
                    "cta": "Order now",
                },
                # Missing variant B for signature_dish_hero
                # Missing both variants for local_pride and value_combo
            ]
        }
        gw = _make_gateway(partial_response)
        concepts = generate_ab_concepts(
            creative_directions=creative_directions,
            campaign_context=campaign_context,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        # Still 6 concepts (2 per direction), with missing ones filled
        assert len(concepts) == 6
        labels_by_dir: dict[str, list[str]] = {}
        for c in concepts:
            labels_by_dir.setdefault(c.direction_id, []).append(c.variant_label)
        for dir_id, labels in labels_by_dir.items():
            assert sorted(labels) == ["A", "B"]
