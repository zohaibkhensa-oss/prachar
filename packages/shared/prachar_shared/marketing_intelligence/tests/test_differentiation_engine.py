"""Tests for the competitor differentiation generator (P1.8).

Verifies that generate_differentiation returns DifferentiationEntry objects
with the required fields (competitor_claim, our_counter, evidence), falls back
gracefully on AI failure, works across all 4 domain packs, and produces
domain-specific differentiation differences (restaurant vs clinic).
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import BudgetExceeded, Completion
from prachar_shared.domain_packs import register_all
from prachar_shared.marketing_intelligence.differentiation_engine import (
    DifferentiationEntry,
    generate_differentiation,
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
def differentiation_response():
    """A well-formed differentiation JSON response from the AI gateway."""
    return {
        "differentiation": [
            {
                "competitor_claim": "We have the biggest portions in town.",
                "our_counter": "We focus on quality over quantity — every bite is crafted.",
                "evidence": "We use 12-hour marinated chicken and authentic Hyderabadi spices.",
            },
            {
                "competitor_claim": "Fastest delivery guaranteed.",
                "our_counter": "We cook fresh to order — no reheated biryani.",
                "evidence": "Our dum biryani is sealed and cooked fresh for every order.",
            },
            {
                "competitor_claim": "Cheapest prices in the area.",
                "our_counter": "We offer authentic Hyderabadi biryani at fair prices.",
                "evidence": "Our recipe comes directly from Hyderabad, using premium ingredients.",
            },
            {
                "competitor_claim": "We've been around for decades.",
                "our_counter": "We honour tradition while innovating for modern tastes.",
                "evidence": "Our chef trained in Hyderabad and adds contemporary touches.",
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


class TestGenerateDifferentiation:
    """Tests for generate_differentiation()."""

    def test_returns_list_of_entries(
        self, business_pack, campaign_context, differentiation_response,
    ):
        """generate_differentiation returns a list of DifferentiationEntry objects."""
        gw = _make_gateway(differentiation_response)
        entries = generate_differentiation(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert isinstance(entries, list)
        assert all(isinstance(e, DifferentiationEntry) for e in entries)

    def test_returns_3_to_5_entries(
        self, business_pack, campaign_context, differentiation_response,
    ):
        """generate_differentiation returns 3-5 entries."""
        gw = _make_gateway(differentiation_response)
        entries = generate_differentiation(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert 3 <= len(entries) <= 5

    def test_has_required_fields(
        self, business_pack, campaign_context, differentiation_response,
    ):
        """Each entry has all 3 required fields."""
        gw = _make_gateway(differentiation_response)
        entries = generate_differentiation(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        required = {"competitor_claim", "our_counter", "evidence"}
        for entry in entries:
            assert required.issubset(set(entry.to_dict().keys()))

    def test_competitor_claim_is_string(
        self, business_pack, campaign_context, differentiation_response,
    ):
        """Each entry's competitor_claim is a non-empty string."""
        gw = _make_gateway(differentiation_response)
        entries = generate_differentiation(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for entry in entries:
            assert isinstance(entry.competitor_claim, str)
            assert entry.competitor_claim

    def test_our_counter_is_string(
        self, business_pack, campaign_context, differentiation_response,
    ):
        """Each entry's our_counter is a non-empty string."""
        gw = _make_gateway(differentiation_response)
        entries = generate_differentiation(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for entry in entries:
            assert isinstance(entry.our_counter, str)
            assert entry.our_counter

    def test_evidence_is_string(
        self, business_pack, campaign_context, differentiation_response,
    ):
        """Each entry's evidence is a non-empty string."""
        gw = _make_gateway(differentiation_response)
        entries = generate_differentiation(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for entry in entries:
            assert isinstance(entry.evidence, str)
            assert entry.evidence

    def test_to_dict_returns_all_fields(
        self, business_pack, campaign_context, differentiation_response,
    ):
        """DifferentiationEntry.to_dict() returns a dict with all 3 fields."""
        gw = _make_gateway(differentiation_response)
        entries = generate_differentiation(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for entry in entries:
            d = entry.to_dict()
            assert isinstance(d, dict)
            assert set(d.keys()) == {"competitor_claim", "our_counter", "evidence"}
            assert d["competitor_claim"] == entry.competitor_claim
            assert d["our_counter"] == entry.our_counter
            assert d["evidence"] == entry.evidence

    def test_uses_domain_pack_differentiation_prompt_in_request(
        self, business_pack, campaign_context, differentiation_response,
    ):
        """The prompt sent to the gateway includes the pack's differentiation_prompt."""
        gw = _make_gateway(differentiation_response)
        generate_differentiation(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        gw.complete.assert_called_once()
        call_kwargs = gw.complete.call_args.kwargs
        call_prompt = call_kwargs["prompt"]
        assert business_pack.differentiation_prompt in call_prompt
        assert call_kwargs["task"] == "business_differentiation"
        assert call_kwargs["tier"] == "large"

    def test_works_with_minimal_domain_pack(
        self, campaign_context, differentiation_response,
    ):
        """generate_differentiation works with a bare BaseDomainPack."""
        from prachar_shared.domain_packs.base import BaseDomainPack

        class MinimalPack(BaseDomainPack):
            id = "minimal"
            label = "Minimal"
            differentiation_prompt = "Keep differentiation simple."

        pack = MinimalPack()
        gw = _make_gateway(differentiation_response)
        entries = generate_differentiation(
            campaign_context=campaign_context,
            domain_pack=pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(entries) >= 3


class TestGracefulFallback:
    """Tests for graceful fallback on failure."""

    def test_falls_back_to_empty_list_on_ai_failure(
        self, business_pack, campaign_context,
    ):
        """When the AI gateway raises, generate_differentiation returns []."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=RuntimeError("AI is down"))
        entries = generate_differentiation(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert isinstance(entries, list)
        assert len(entries) == 0

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
        entries = generate_differentiation(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(entries) == 0

    def test_budget_exceeded_is_re_raised(
        self, business_pack, campaign_context,
    ):
        """BudgetExceeded is re-raised, not swallowed."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=BudgetExceeded("budget exceeded"))
        with pytest.raises(BudgetExceeded):
            generate_differentiation(
                campaign_context=campaign_context,
                domain_pack=business_pack,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )


class TestAllDomainPacks:
    """Tests that generate_differentiation works for all 4 domain packs."""

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
            "differentiation": [
                {"competitor_claim": "Biggest portions.", "our_counter": "Quality over quantity.", "evidence": "Premium ingredients."},
                {"competitor_claim": "Fastest delivery.", "our_counter": "Fresh to order.", "evidence": "Cooked fresh."},
                {"competitor_claim": "Cheapest prices.", "our_counter": "Fair value.", "evidence": "Authentic recipe."},
            ]
        }

    def test_all_packs_have_differentiation_prompt(self, all_packs):
        """Every domain pack defines a differentiation_prompt."""
        for pack in all_packs:
            assert hasattr(pack, "differentiation_prompt"), (
                f"Pack {pack.id} missing differentiation_prompt"
            )
            assert isinstance(pack.differentiation_prompt, str)
            assert pack.differentiation_prompt, (
                f"Pack {pack.id} has empty differentiation_prompt"
            )

    def test_generate_works_for_all_packs(self, all_packs, ctx, resp):
        """generate_differentiation returns valid output for every pack."""
        gw = _make_gateway(resp)
        for pack in all_packs:
            entries = generate_differentiation(
                campaign_context=ctx,
                domain_pack=pack,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )
            assert isinstance(entries, list), f"Pack {pack.id} did not return a list"
            for entry in entries:
                assert isinstance(entry, DifferentiationEntry)

    def test_all_packs_fallback_gracefully(self, all_packs, ctx):
        """Every pack falls back to [] on AI failure."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=RuntimeError("down"))
        for pack in all_packs:
            entries = generate_differentiation(
                campaign_context=ctx,
                domain_pack=pack,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )
            assert isinstance(entries, list)
            assert len(entries) == 0


class TestDomainSpecificDifferentiation:
    """Tests that domain packs produce domain-specific differentiation guidance."""

    def test_restaurant_prompt_mentions_food_or_dining(
        self, restaurant_pack,
    ):
        """The restaurant differentiation_prompt mentions restaurant-specific positioning."""
        prompt = restaurant_pack.differentiation_prompt.lower()
        assert "food" in prompt or "dining" in prompt or "taste" in prompt or "cuisine" in prompt or "quality" in prompt, (
            "Restaurant differentiation_prompt should mention food, dining, taste, cuisine, or quality"
        )

    def test_clinic_prompt_mentions_trust_or_care(
        self, clinic_pack,
    ):
        """The clinic differentiation_prompt mentions clinic-specific positioning."""
        prompt = clinic_pack.differentiation_prompt.lower()
        assert "trust" in prompt or "care" in prompt or "patient" in prompt or "expertise" in prompt or "outcome" in prompt, (
            "Clinic differentiation_prompt should mention trust, care, patient, expertise, or outcomes"
        )

    def test_restaurant_and_clinic_prompts_differ(
        self, restaurant_pack, clinic_pack,
    ):
        """Restaurant and clinic differentiation_prompts are genuinely different."""
        assert restaurant_pack.differentiation_prompt != clinic_pack.differentiation_prompt, (
            "Restaurant and clinic differentiation_prompts should be different"
        )

    def test_restaurant_prompt_differs_from_business(
        self, restaurant_pack, business_pack,
    ):
        """Restaurant differentiation_prompt differs from business."""
        assert restaurant_pack.differentiation_prompt != business_pack.differentiation_prompt, (
            "Restaurant and business differentiation_prompts should be different"
        )

    def test_clinic_prompt_differs_from_business(
        self, clinic_pack, business_pack,
    ):
        """Clinic differentiation_prompt differs from business."""
        assert clinic_pack.differentiation_prompt != business_pack.differentiation_prompt, (
            "Clinic and business differentiation_prompts should be different"
        )
