"""Tests for the offer engineering generator (P1.4).

Verifies that generate_offers returns 3 Offer objects with the required fields
(structure, copy, psychology_lever, expected_conversion_lift), falls back
gracefully on AI failure, works across all 4 domain packs, and produces
domain-specific offer differences (restaurant vs clinic).
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import BudgetExceeded, Completion
from prachar_shared.domain_packs import register_all
from prachar_shared.marketing_intelligence.offer_engine import (
    Offer,
    generate_offers,
)

# Ensure packs are registered
register_all()


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def business_pack():
    """The registered business domain pack."""
    from prachar_shared.domain_packs import get_registry

    return get_registry().get_required("business")


@pytest.fixture
def restaurant_pack():
    """The registered restaurant domain pack."""
    from prachar_shared.domain_packs import get_registry

    return get_registry().get_required("restaurant")


@pytest.fixture
def clinic_pack():
    """The registered clinic domain pack."""
    from prachar_shared.domain_packs import get_registry

    return get_registry().get_required("clinic")


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
def offers_response():
    """A well-formed offers JSON response from the AI gateway."""
    return {
        "offers": [
            {
                "structure": "anchoring",
                "copy": "Premium thali at ₹499 — or our regular combo at just ₹249.",
                "psychology_lever": "The premium price anchors perception, making the combo feel like a bargain.",
                "expected_conversion_lift": "high",
            },
            {
                "structure": "scarcity",
                "copy": "Happy hour: 50% off all starters, today only 4-7 PM.",
                "psychology_lever": "A time-limited window creates urgency and fear of missing out.",
                "expected_conversion_lift": "medium",
            },
            {
                "structure": "bundling",
                "copy": "Family feast: 2 mains + 4 sides + desserts for ₹899 (saves ₹200).",
                "psychology_lever": "Bundling increases perceived value and average order size.",
                "expected_conversion_lift": "15-25%",
            },
        ]
    }


def _make_gateway(response_dict: dict) -> MagicMock:
    """Build a mock AIGateway whose complete() returns the given dict as JSON."""
    gw = MagicMock()
    gw.complete = MagicMock(
        return_value=Completion(
            text=json.dumps(response_dict),
            tokens_used=300,
            model="test-model",
            confidence=0.9,
        )
    )
    return gw


# ─── Tests ─────────────────────────────────────────────────────────────────


class TestGenerateOffers:
    """Tests for generate_offers()."""

    def test_returns_list_of_offers(
        self, business_pack, campaign_context, offers_response,
    ):
        """generate_offers returns a list of Offer objects."""
        gw = _make_gateway(offers_response)
        offers = generate_offers(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert isinstance(offers, list)
        assert all(isinstance(o, Offer) for o in offers)

    def test_returns_exactly_3_offers(
        self, business_pack, campaign_context, offers_response,
    ):
        """generate_offers returns exactly 3 offers."""
        gw = _make_gateway(offers_response)
        offers = generate_offers(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(offers) == 3

    def test_has_required_fields(
        self, business_pack, campaign_context, offers_response,
    ):
        """Each offer has all 4 required fields."""
        gw = _make_gateway(offers_response)
        offers = generate_offers(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        required = {"structure", "copy", "psychology_lever", "expected_conversion_lift"}
        for offer in offers:
            assert required.issubset(set(offer.to_dict().keys()))

    def test_structure_is_string(
        self, business_pack, campaign_context, offers_response,
    ):
        """Each offer's structure is a non-empty string."""
        gw = _make_gateway(offers_response)
        offers = generate_offers(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for offer in offers:
            assert isinstance(offer.structure, str)
            assert offer.structure

    def test_copy_is_string(
        self, business_pack, campaign_context, offers_response,
    ):
        """Each offer's copy is a non-empty string."""
        gw = _make_gateway(offers_response)
        offers = generate_offers(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for offer in offers:
            assert isinstance(offer.copy, str)
            assert offer.copy

    def test_psychology_lever_is_string(
        self, business_pack, campaign_context, offers_response,
    ):
        """Each offer's psychology_lever is a non-empty string."""
        gw = _make_gateway(offers_response)
        offers = generate_offers(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for offer in offers:
            assert isinstance(offer.psychology_lever, str)
            assert offer.psychology_lever

    def test_expected_conversion_lift_is_string(
        self, business_pack, campaign_context, offers_response,
    ):
        """Each offer's expected_conversion_lift is a non-empty string."""
        gw = _make_gateway(offers_response)
        offers = generate_offers(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for offer in offers:
            assert isinstance(offer.expected_conversion_lift, str)
            assert offer.expected_conversion_lift

    def test_to_dict_returns_all_fields(
        self, business_pack, campaign_context, offers_response,
    ):
        """Offer.to_dict() returns a dict with all 4 fields."""
        gw = _make_gateway(offers_response)
        offers = generate_offers(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for offer in offers:
            d = offer.to_dict()
            assert isinstance(d, dict)
            assert set(d.keys()) == {
                "structure",
                "copy",
                "psychology_lever",
                "expected_conversion_lift",
            }
            assert d["structure"] == offer.structure
            assert d["copy"] == offer.copy
            assert d["psychology_lever"] == offer.psychology_lever
            assert d["expected_conversion_lift"] == offer.expected_conversion_lift

    def test_uses_domain_pack_offers_prompt_in_request(
        self, business_pack, campaign_context, offers_response,
    ):
        """The prompt sent to the gateway includes the pack's offers_prompt."""
        gw = _make_gateway(offers_response)
        generate_offers(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        gw.complete.assert_called_once()
        call_kwargs = gw.complete.call_args.kwargs
        call_prompt = call_kwargs["prompt"]
        # The offers_prompt from the business pack should appear in the prompt
        assert business_pack.offers_prompt in call_prompt
        # Task name should include the pack id + "offers"
        assert call_kwargs["task"] == "business_offers"
        # Should use Tier.large
        assert call_kwargs["tier"] == "large"

    def test_works_with_minimal_domain_pack(
        self, campaign_context, offers_response,
    ):
        """generate_offers works with a bare BaseDomainPack (empty offers_prompt)."""
        from prachar_shared.domain_packs.base import BaseDomainPack

        class MinimalPack(BaseDomainPack):
            id = "minimal"
            label = "Minimal"
            offers_prompt = "Keep offers simple."

        pack = MinimalPack()
        gw = _make_gateway(offers_response)
        offers = generate_offers(
            campaign_context=campaign_context,
            domain_pack=pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(offers) == 3


class TestGracefulFallback:
    """Tests for graceful fallback on failure."""

    def test_falls_back_to_3_empty_offers_on_ai_failure(
        self, business_pack, campaign_context,
    ):
        """When the AI gateway raises, generate_offers returns 3 empty offers."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=RuntimeError("AI is down"))
        offers = generate_offers(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert isinstance(offers, list)
        assert len(offers) == 3
        for offer in offers:
            assert isinstance(offer, Offer)
            assert offer.structure == ""
            assert offer.copy == ""
            assert offer.psychology_lever == ""
            assert offer.expected_conversion_lift == ""

    def test_falls_back_on_malformed_json(
        self, business_pack, campaign_context,
    ):
        """When the AI returns non-JSON text, the generator falls back gracefully."""
        gw = MagicMock()
        gw.complete = MagicMock(
            return_value=Completion(
                text="This is not JSON at all.",
                tokens_used=10,
                model="test-model",
                confidence=0.1,
            )
        )
        offers = generate_offers(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(offers) == 3
        for offer in offers:
            assert offer.structure == ""
            assert offer.copy == ""

    def test_handles_partial_response(
        self, business_pack, campaign_context,
    ):
        """Fewer than 3 offers in the AI response are padded to 3."""
        response = {
            "offers": [
                {
                    "structure": "scarcity",
                    "copy": "Only 5 spots left!",
                    "psychology_lever": "Creates urgency.",
                    "expected_conversion_lift": "high",
                },
            ]
        }
        gw = _make_gateway(response)
        offers = generate_offers(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(offers) == 3
        assert offers[0].structure == "scarcity"
        assert offers[0].copy == "Only 5 spots left!"
        # Padded offers should be empty
        assert offers[1].structure == ""
        assert offers[2].structure == ""

    def test_handles_extra_offers_by_capping_at_3(
        self, business_pack, campaign_context,
    ):
        """More than 3 offers in the AI response are capped at 3."""
        response = {
            "offers": [
                {"structure": "anchoring", "copy": "a", "psychology_lever": "p", "expected_conversion_lift": "high"},
                {"structure": "scarcity", "copy": "b", "psychology_lever": "p", "expected_conversion_lift": "medium"},
                {"structure": "bundling", "copy": "c", "psychology_lever": "p", "expected_conversion_lift": "low"},
                {"structure": "loss-aversion", "copy": "d", "psychology_lever": "p", "expected_conversion_lift": "high"},
                {"structure": "decoy pricing", "copy": "e", "psychology_lever": "p", "expected_conversion_lift": "medium"},
            ]
        }
        gw = _make_gateway(response)
        offers = generate_offers(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(offers) == 3
        assert offers[0].structure == "anchoring"
        assert offers[1].structure == "scarcity"
        assert offers[2].structure == "bundling"

    def test_budget_exceeded_is_re_raised(
        self, business_pack, campaign_context,
    ):
        """BudgetExceeded is re-raised, not swallowed."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=BudgetExceeded("budget exceeded"))
        with pytest.raises(BudgetExceeded):
            generate_offers(
                campaign_context=campaign_context,
                domain_pack=business_pack,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )


class TestAllDomainPacks:
    """Tests that generate_offers works for all 4 domain packs."""

    @pytest.fixture
    def all_packs(self):
        from prachar_shared.domain_packs import get_registry

        return get_registry().all()

    @pytest.fixture
    def ctx(self):
        return {
            "brand_name": "Test Brand",
            "goal": "grow",
            "budget": "₹10,000",
            "campaign_analysis": "A test brand.",
        }

    @pytest.fixture
    def resp(self):
        return {
            "offers": [
                {"structure": "anchoring", "copy": "Premium at ₹999, standard at ₹499.", "psychology_lever": "Anchoring effect.", "expected_conversion_lift": "high"},
                {"structure": "scarcity", "copy": "Limited time only!", "psychology_lever": "Urgency.", "expected_conversion_lift": "medium"},
                {"structure": "bundling", "copy": "Bundle 3 for ₹999.", "psychology_lever": "Value perception.", "expected_conversion_lift": "low"},
            ]
        }

    def test_all_packs_have_offers_prompt(self, all_packs):
        """Every domain pack defines an offers_prompt."""
        for pack in all_packs:
            assert hasattr(pack, "offers_prompt"), (
                f"Pack {pack.id} missing offers_prompt"
            )
            assert isinstance(pack.offers_prompt, str)
            assert pack.offers_prompt, (
                f"Pack {pack.id} has empty offers_prompt"
            )

    def test_generate_works_for_all_packs(self, all_packs, ctx, resp):
        """generate_offers returns valid output for every pack."""
        gw = _make_gateway(resp)
        for pack in all_packs:
            offers = generate_offers(
                campaign_context=ctx,
                domain_pack=pack,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )
            assert isinstance(offers, list), f"Pack {pack.id} did not return a list"
            assert len(offers) == 3, f"Pack {pack.id} returned {len(offers)} offers"
            for offer in offers:
                assert isinstance(offer, Offer)

    def test_all_packs_fallback_gracefully(self, all_packs, ctx):
        """Every pack falls back to 3 empty offers on AI failure."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=RuntimeError("down"))
        for pack in all_packs:
            offers = generate_offers(
                campaign_context=ctx,
                domain_pack=pack,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )
            assert len(offers) == 3
            for offer in offers:
                assert offer.structure == ""
                assert offer.copy == ""


class TestDomainSpecificOffers:
    """Tests that domain packs produce domain-specific offer guidance."""

    def test_restaurant_prompt_mentions_combo_and_happy_hour(
        self, restaurant_pack,
    ):
        """The restaurant offers_prompt mentions restaurant-specific techniques."""
        prompt = restaurant_pack.offers_prompt.lower()
        assert "combo" in prompt or "happy hour" in prompt or "family bundle" in prompt, (
            "Restaurant offers_prompt should mention combo meals, happy hour, or family bundle"
        )

    def test_clinic_prompt_mentions_first_visit_and_sessions(
        self, clinic_pack,
    ):
        """The clinic offers_prompt mentions clinic-specific techniques."""
        prompt = clinic_pack.offers_prompt.lower()
        assert "first-visit" in prompt or "first visit" in prompt or "package of sessions" in prompt or "family checkup" in prompt, (
            "Clinic offers_prompt should mention first-visit discount, package of sessions, or family checkup"
        )

    def test_restaurant_and_clinic_prompts_differ(
        self, restaurant_pack, clinic_pack,
    ):
        """Restaurant and clinic offers_prompts are genuinely different."""
        assert restaurant_pack.offers_prompt != clinic_pack.offers_prompt, (
            "Restaurant and clinic offers_prompts should be different"
        )

    def test_clinic_prompt_has_no_medical_claims(
        self, clinic_pack,
    ):
        """The clinic offers_prompt explicitly avoids medical claims."""
        prompt = clinic_pack.offers_prompt.lower()
        assert "medical claim" in prompt or "never" in prompt, (
            "Clinic offers_prompt should mention avoiding medical claims"
        )

    def test_restaurant_prompt_differs_from_business(
        self, restaurant_pack, business_pack,
    ):
        """Restaurant offers_prompt differs from business offers_prompt."""
        assert restaurant_pack.offers_prompt != business_pack.offers_prompt, (
            "Restaurant and business offers_prompts should be different"
        )

    def test_clinic_prompt_differs_from_business(
        self, clinic_pack, business_pack,
    ):
        """Clinic offers_prompt differs from business offers_prompt."""
        assert clinic_pack.offers_prompt != business_pack.offers_prompt, (
            "Clinic and business offers_prompts should be different"
        )
