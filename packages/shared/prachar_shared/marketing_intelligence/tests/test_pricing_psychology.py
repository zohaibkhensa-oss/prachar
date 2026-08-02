"""Tests for the pricing psychology generator (P1.5).

Verifies that generate_pricing_psychology returns 3 PricingPresentation objects
with the required fields (technique, copy, rationale), falls back gracefully on
AI failure, works across all 4 domain packs, and produces domain-specific
pricing differences (restaurant vs clinic).
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import BudgetExceeded, Completion
from prachar_shared.domain_packs import register_all
from prachar_shared.marketing_intelligence.pricing_psychology import (
    PricingPresentation,
    generate_pricing_psychology,
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
def pricing_response():
    """A well-formed pricing JSON response from the AI gateway."""
    return {
        "pricing": [
            {
                "technique": "charm",
                "copy": "Get our signature biryani for just ₹99 — not ₹100.",
                "rationale": "Charm pricing makes the price feel significantly lower.",
            },
            {
                "technique": "tier",
                "copy": "Choose: Solo ₹149, Duo ₹249, Family ₹399.",
                "rationale": "Tiered pricing gives customers a sense of control and value.",
            },
            {
                "technique": "bundle",
                "copy": "Biryani + kebab + dessert for ₹299 (saves ₹80).",
                "rationale": "Bundling increases perceived value and average order size.",
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


class TestGeneratePricingPsychology:
    """Tests for generate_pricing_psychology()."""

    def test_returns_list_of_pricing_presentations(
        self, business_pack, campaign_context, pricing_response,
    ):
        """generate_pricing_psychology returns a list of PricingPresentation objects."""
        gw = _make_gateway(pricing_response)
        presentations = generate_pricing_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert isinstance(presentations, list)
        assert all(isinstance(p, PricingPresentation) for p in presentations)

    def test_returns_exactly_3_presentations(
        self, business_pack, campaign_context, pricing_response,
    ):
        """generate_pricing_psychology returns exactly 3 presentations."""
        gw = _make_gateway(pricing_response)
        presentations = generate_pricing_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(presentations) == 3

    def test_has_required_fields(
        self, business_pack, campaign_context, pricing_response,
    ):
        """Each presentation has all 3 required fields."""
        gw = _make_gateway(pricing_response)
        presentations = generate_pricing_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        required = {"technique", "copy", "rationale"}
        for pres in presentations:
            assert required.issubset(set(pres.to_dict().keys()))

    def test_technique_is_string(
        self, business_pack, campaign_context, pricing_response,
    ):
        """Each presentation's technique is a non-empty string."""
        gw = _make_gateway(pricing_response)
        presentations = generate_pricing_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for pres in presentations:
            assert isinstance(pres.technique, str)
            assert pres.technique

    def test_copy_is_string(
        self, business_pack, campaign_context, pricing_response,
    ):
        """Each presentation's copy is a non-empty string."""
        gw = _make_gateway(pricing_response)
        presentations = generate_pricing_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for pres in presentations:
            assert isinstance(pres.copy, str)
            assert pres.copy

    def test_rationale_is_string(
        self, business_pack, campaign_context, pricing_response,
    ):
        """Each presentation's rationale is a non-empty string."""
        gw = _make_gateway(pricing_response)
        presentations = generate_pricing_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for pres in presentations:
            assert isinstance(pres.rationale, str)
            assert pres.rationale

    def test_to_dict_returns_all_fields(
        self, business_pack, campaign_context, pricing_response,
    ):
        """PricingPresentation.to_dict() returns a dict with all 3 fields."""
        gw = _make_gateway(pricing_response)
        presentations = generate_pricing_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for pres in presentations:
            d = pres.to_dict()
            assert isinstance(d, dict)
            assert set(d.keys()) == {"technique", "copy", "rationale"}
            assert d["technique"] == pres.technique
            assert d["copy"] == pres.copy
            assert d["rationale"] == pres.rationale

    def test_uses_domain_pack_pricing_psychology_prompt_in_request(
        self, business_pack, campaign_context, pricing_response,
    ):
        """The prompt sent to the gateway includes the pack's pricing_psychology_prompt."""
        gw = _make_gateway(pricing_response)
        generate_pricing_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        gw.complete.assert_called_once()
        call_kwargs = gw.complete.call_args.kwargs
        call_prompt = call_kwargs["prompt"]
        assert business_pack.pricing_psychology_prompt in call_prompt
        assert call_kwargs["task"] == "business_pricing_psychology"
        assert call_kwargs["tier"] == "large"

    def test_works_with_minimal_domain_pack(
        self, campaign_context, pricing_response,
    ):
        """generate_pricing_psychology works with a bare BaseDomainPack."""
        from prachar_shared.domain_packs.base import BaseDomainPack

        class MinimalPack(BaseDomainPack):
            id = "minimal"
            label = "Minimal"
            pricing_psychology_prompt = "Keep pricing simple."

        pack = MinimalPack()
        gw = _make_gateway(pricing_response)
        presentations = generate_pricing_psychology(
            campaign_context=campaign_context,
            domain_pack=pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(presentations) == 3


class TestGracefulFallback:
    """Tests for graceful fallback on failure."""

    def test_falls_back_to_3_empty_presentations_on_ai_failure(
        self, business_pack, campaign_context,
    ):
        """When the AI gateway raises, generate_pricing_psychology returns 3 empty presentations."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=RuntimeError("AI is down"))
        presentations = generate_pricing_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert isinstance(presentations, list)
        assert len(presentations) == 3
        for pres in presentations:
            assert isinstance(pres, PricingPresentation)
            assert pres.technique == ""
            assert pres.copy == ""
            assert pres.rationale == ""

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
        presentations = generate_pricing_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(presentations) == 3
        for pres in presentations:
            assert pres.technique == ""
            assert pres.copy == ""

    def test_handles_partial_response(
        self, business_pack, campaign_context,
    ):
        """Fewer than 3 presentations in the AI response are padded to 3."""
        response = {
            "pricing": [
                {
                    "technique": "charm",
                    "copy": "Just ₹99!",
                    "rationale": "Charm pricing feels cheaper.",
                },
            ]
        }
        gw = _make_gateway(response)
        presentations = generate_pricing_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(presentations) == 3
        assert presentations[0].technique == "charm"
        assert presentations[0].copy == "Just ₹99!"
        assert presentations[1].technique == ""
        assert presentations[2].technique == ""

    def test_handles_extra_presentations_by_capping_at_3(
        self, business_pack, campaign_context,
    ):
        """More than 3 presentations in the AI response are capped at 3."""
        response = {
            "pricing": [
                {"technique": "charm", "copy": "a", "rationale": "r"},
                {"technique": "tier", "copy": "b", "rationale": "r"},
                {"technique": "bundle", "copy": "c", "rationale": "r"},
                {"technique": "anchor", "copy": "d", "rationale": "r"},
                {"technique": "loss_leader", "copy": "e", "rationale": "r"},
            ]
        }
        gw = _make_gateway(response)
        presentations = generate_pricing_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(presentations) == 3
        assert presentations[0].technique == "charm"
        assert presentations[1].technique == "tier"
        assert presentations[2].technique == "bundle"

    def test_budget_exceeded_is_re_raised(
        self, business_pack, campaign_context,
    ):
        """BudgetExceeded is re-raised, not swallowed."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=BudgetExceeded("budget exceeded"))
        with pytest.raises(BudgetExceeded):
            generate_pricing_psychology(
                campaign_context=campaign_context,
                domain_pack=business_pack,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )


class TestAllDomainPacks:
    """Tests that generate_pricing_psychology works for all 4 domain packs."""

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
            "pricing": [
                {"technique": "charm", "copy": "Just ₹99.", "rationale": "Feels cheaper."},
                {"technique": "tier", "copy": "Basic ₹199, Pro ₹399.", "rationale": "Choice."},
                {"technique": "bundle", "copy": "All 3 for ₹499.", "rationale": "Value."},
            ]
        }

    def test_all_packs_have_pricing_psychology_prompt(self, all_packs):
        """Every domain pack defines a pricing_psychology_prompt."""
        for pack in all_packs:
            assert hasattr(pack, "pricing_psychology_prompt"), (
                f"Pack {pack.id} missing pricing_psychology_prompt"
            )
            assert isinstance(pack.pricing_psychology_prompt, str)
            assert pack.pricing_psychology_prompt, (
                f"Pack {pack.id} has empty pricing_psychology_prompt"
            )

    def test_generate_works_for_all_packs(self, all_packs, ctx, resp):
        """generate_pricing_psychology returns valid output for every pack."""
        gw = _make_gateway(resp)
        for pack in all_packs:
            presentations = generate_pricing_psychology(
                campaign_context=ctx,
                domain_pack=pack,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )
            assert isinstance(presentations, list), f"Pack {pack.id} did not return a list"
            assert len(presentations) == 3, f"Pack {pack.id} returned {len(presentations)} presentations"
            for pres in presentations:
                assert isinstance(pres, PricingPresentation)

    def test_all_packs_fallback_gracefully(self, all_packs, ctx):
        """Every pack falls back to 3 empty presentations on AI failure."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=RuntimeError("down"))
        for pack in all_packs:
            presentations = generate_pricing_psychology(
                campaign_context=ctx,
                domain_pack=pack,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )
            assert len(presentations) == 3
            for pres in presentations:
                assert pres.technique == ""
                assert pres.copy == ""


class TestDomainSpecificPricing:
    """Tests that domain packs produce domain-specific pricing guidance."""

    def test_restaurant_prompt_mentions_food_pricing(
        self, restaurant_pack,
    ):
        """The restaurant pricing_psychology_prompt mentions restaurant-specific pricing."""
        prompt = restaurant_pack.pricing_psychology_prompt.lower()
        assert "combo" in prompt or "thali" in prompt or "meal" in prompt or "menu" in prompt, (
            "Restaurant pricing_psychology_prompt should mention combo, thali, meal, or menu"
        )

    def test_clinic_prompt_mentions_health_pricing(
        self, clinic_pack,
    ):
        """The clinic pricing_psychology_prompt mentions clinic-specific pricing."""
        prompt = clinic_pack.pricing_psychology_prompt.lower()
        assert "consult" in prompt or "session" in prompt or "checkup" in prompt or "package" in prompt, (
            "Clinic pricing_psychology_prompt should mention consult, session, checkup, or package"
        )

    def test_restaurant_and_clinic_prompts_differ(
        self, restaurant_pack, clinic_pack,
    ):
        """Restaurant and clinic pricing_psychology_prompts are genuinely different."""
        assert restaurant_pack.pricing_psychology_prompt != clinic_pack.pricing_psychology_prompt, (
            "Restaurant and clinic pricing_psychology_prompts should be different"
        )

    def test_restaurant_prompt_differs_from_business(
        self, restaurant_pack, business_pack,
    ):
        """Restaurant pricing_psychology_prompt differs from business."""
        assert restaurant_pack.pricing_psychology_prompt != business_pack.pricing_psychology_prompt, (
            "Restaurant and business pricing_psychology_prompts should be different"
        )

    def test_clinic_prompt_differs_from_business(
        self, clinic_pack, business_pack,
    ):
        """Clinic pricing_psychology_prompt differs from business."""
        assert clinic_pack.pricing_psychology_prompt != business_pack.pricing_psychology_prompt, (
            "Clinic and business pricing_psychology_prompts should be different"
        )
