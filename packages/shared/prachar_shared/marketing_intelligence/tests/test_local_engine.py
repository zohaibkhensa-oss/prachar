"""Tests for the local marketing generator (P1.7).

Verifies that generate_local_ideas returns LocalIdea objects with the required
fields (type, idea, copy), falls back gracefully on AI failure, works across
all location-based domain packs (business, restaurant, clinic), returns [] for
the creator pack (no local marketing), and produces domain-specific local
marketing differences (restaurant vs clinic).
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import BudgetExceeded, Completion
from prachar_shared.domain_packs import register_all
from prachar_shared.marketing_intelligence.local_engine import (
    LocalIdea,
    generate_local_ideas,
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
def creator_pack():
    """The registered creator domain pack."""
    from prachar_shared.domain_packs import get_registry

    return get_registry().get_required("creator")


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
        "location": "Hyderabad",
    }


@pytest.fixture
def local_response():
    """A well-formed local ideas JSON response from the AI gateway."""
    return {
        "local_ideas": [
            {
                "type": "event",
                "idea": "Host a biryani tasting event at the restaurant.",
                "copy": "Join us this Saturday for a free biryani tasting — bring your friends!",
            },
            {
                "type": "partnership",
                "idea": "Partner with a nearby ice cream shop for a dessert combo.",
                "copy": "Biryani + ice cream combo — available at both locations!",
            },
            {
                "type": "geo_target",
                "idea": "Run hyper-local ads targeting people within 3 km.",
                "copy": "Craving biryani? We're just around the corner — order now!",
            },
            {
                "type": "seo",
                "idea": "Optimise Google Business Profile with biryani keywords.",
                "copy": "Search 'best biryani near me' — we're the top result in Hyderabad!",
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


class TestGenerateLocalIdeas:
    """Tests for generate_local_ideas()."""

    def test_returns_list_of_local_ideas(
        self, business_pack, campaign_context, local_response,
    ):
        """generate_local_ideas returns a list of LocalIdea objects."""
        gw = _make_gateway(local_response)
        ideas = generate_local_ideas(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert isinstance(ideas, list)
        assert all(isinstance(i, LocalIdea) for i in ideas)

    def test_returns_3_to_5_ideas(
        self, business_pack, campaign_context, local_response,
    ):
        """generate_local_ideas returns 3-5 ideas."""
        gw = _make_gateway(local_response)
        ideas = generate_local_ideas(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert 3 <= len(ideas) <= 5

    def test_has_required_fields(
        self, business_pack, campaign_context, local_response,
    ):
        """Each idea has all 3 required fields."""
        gw = _make_gateway(local_response)
        ideas = generate_local_ideas(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        required = {"type", "idea", "copy"}
        for idea in ideas:
            assert required.issubset(set(idea.to_dict().keys()))

    def test_type_is_string(
        self, business_pack, campaign_context, local_response,
    ):
        """Each idea's type is a non-empty string."""
        gw = _make_gateway(local_response)
        ideas = generate_local_ideas(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for idea in ideas:
            assert isinstance(idea.type, str)
            assert idea.type

    def test_idea_is_string(
        self, business_pack, campaign_context, local_response,
    ):
        """Each idea's idea is a non-empty string."""
        gw = _make_gateway(local_response)
        ideas = generate_local_ideas(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for idea in ideas:
            assert isinstance(idea.idea, str)
            assert idea.idea

    def test_copy_is_string(
        self, business_pack, campaign_context, local_response,
    ):
        """Each idea's copy is a non-empty string."""
        gw = _make_gateway(local_response)
        ideas = generate_local_ideas(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for idea in ideas:
            assert isinstance(idea.copy, str)
            assert idea.copy

    def test_to_dict_returns_all_fields(
        self, business_pack, campaign_context, local_response,
    ):
        """LocalIdea.to_dict() returns a dict with all 3 fields."""
        gw = _make_gateway(local_response)
        ideas = generate_local_ideas(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for idea in ideas:
            d = idea.to_dict()
            assert isinstance(d, dict)
            assert set(d.keys()) == {"type", "idea", "copy"}
            assert d["type"] == idea.type
            assert d["idea"] == idea.idea
            assert d["copy"] == idea.copy

    def test_uses_domain_pack_local_prompt_in_request(
        self, business_pack, campaign_context, local_response,
    ):
        """The prompt sent to the gateway includes the pack's local_prompt."""
        gw = _make_gateway(local_response)
        generate_local_ideas(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        gw.complete.assert_called_once()
        call_kwargs = gw.complete.call_args.kwargs
        call_prompt = call_kwargs["prompt"]
        assert business_pack.local_prompt in call_prompt
        assert call_kwargs["task"] == "business_local_ideas"
        assert call_kwargs["tier"] == "large"

    def test_works_with_minimal_domain_pack(
        self, campaign_context, local_response,
    ):
        """generate_local_ideas works with a bare BaseDomainPack."""
        from prachar_shared.domain_packs.base import BaseDomainPack

        class MinimalPack(BaseDomainPack):
            id = "minimal"
            label = "Minimal"
            local_prompt = "Keep local ideas simple."

        pack = MinimalPack()
        gw = _make_gateway(local_response)
        ideas = generate_local_ideas(
            campaign_context=campaign_context,
            domain_pack=pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(ideas) >= 3


class TestCreatorPackReturnsEmpty:
    """Tests that the creator pack returns [] (no local marketing)."""

    def test_creator_pack_returns_empty_list(
        self, creator_pack, campaign_context, local_response,
    ):
        """generate_local_ideas returns [] for the creator pack."""
        gw = _make_gateway(local_response)
        ideas = generate_local_ideas(
            campaign_context=campaign_context,
            domain_pack=creator_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert isinstance(ideas, list)
        assert len(ideas) == 0

    def test_creator_pack_does_not_call_gateway(
        self, creator_pack, campaign_context,
    ):
        """generate_local_ideas does not call the AI gateway for the creator pack."""
        gw = MagicMock()
        gw.complete = MagicMock(return_value=Completion(
            text="{}", tokens_used=0, model="test", confidence=0.5,
        ))
        generate_local_ideas(
            campaign_context=campaign_context,
            domain_pack=creator_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        gw.complete.assert_not_called()

    def test_creator_pack_has_empty_local_prompt(self, creator_pack):
        """The creator pack's local_prompt is empty."""
        assert creator_pack.local_prompt == ""


class TestGracefulFallback:
    """Tests for graceful fallback on failure."""

    def test_falls_back_to_empty_list_on_ai_failure(
        self, business_pack, campaign_context,
    ):
        """When the AI gateway raises, generate_local_ideas returns []."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=RuntimeError("AI is down"))
        ideas = generate_local_ideas(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert isinstance(ideas, list)
        assert len(ideas) == 0

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
        ideas = generate_local_ideas(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(ideas) == 0

    def test_budget_exceeded_is_re_raised(
        self, business_pack, campaign_context,
    ):
        """BudgetExceeded is re-raised, not swallowed."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=BudgetExceeded("budget exceeded"))
        with pytest.raises(BudgetExceeded):
            generate_local_ideas(
                campaign_context=campaign_context,
                domain_pack=business_pack,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )


class TestAllDomainPacks:
    """Tests that generate_local_ideas works for all domain packs."""

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
            "location": "Mumbai",
        }

    @pytest.fixture
    def resp(self):
        return {
            "local_ideas": [
                {"type": "event", "idea": "Local event.", "copy": "Join us!"},
                {"type": "partnership", "idea": "Partner up.", "copy": "Combo deal!"},
                {"type": "geo_target", "idea": "Hyper-local ads.", "copy": "Near you!"},
            ]
        }

    def test_location_packs_have_local_prompt(self, all_packs):
        """Business, restaurant, and clinic packs define a local_prompt."""
        for pack in all_packs:
            assert hasattr(pack, "local_prompt"), (
                f"Pack {pack.id} missing local_prompt"
            )
            assert isinstance(pack.local_prompt, str)

    def test_creator_pack_local_prompt_is_empty(self, all_packs):
        """The creator pack's local_prompt is empty (no local marketing)."""
        creator = next(p for p in all_packs if p.id == "creator")
        assert creator.local_prompt == ""

    def test_non_creator_packs_have_non_empty_local_prompt(self, all_packs):
        """Business, restaurant, and clinic packs have non-empty local_prompt."""
        for pack in all_packs:
            if pack.id == "creator":
                continue
            assert pack.local_prompt, (
                f"Pack {pack.id} has empty local_prompt (should be non-empty)"
            )

    def test_generate_works_for_all_packs(self, all_packs, ctx, resp):
        """generate_local_ideas returns valid output for every pack."""
        gw = _make_gateway(resp)
        for pack in all_packs:
            ideas = generate_local_ideas(
                campaign_context=ctx,
                domain_pack=pack,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )
            assert isinstance(ideas, list), f"Pack {pack.id} did not return a list"
            if pack.id == "creator":
                assert len(ideas) == 0, f"Creator pack should return [], got {len(ideas)}"
            else:
                for idea in ideas:
                    assert isinstance(idea, LocalIdea)

    def test_all_packs_fallback_gracefully(self, all_packs, ctx):
        """Every pack falls back gracefully on AI failure."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=RuntimeError("down"))
        for pack in all_packs:
            ideas = generate_local_ideas(
                campaign_context=ctx,
                domain_pack=pack,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )
            assert isinstance(ideas, list)
            if pack.id == "creator":
                assert len(ideas) == 0
            else:
                assert len(ideas) == 0  # fallback is also empty


class TestDomainSpecificLocal:
    """Tests that domain packs produce domain-specific local marketing guidance."""

    def test_restaurant_prompt_mentions_local_dining(
        self, restaurant_pack,
    ):
        """The restaurant local_prompt mentions restaurant-specific local marketing."""
        prompt = restaurant_pack.local_prompt.lower()
        assert "footfall" in prompt or "dine" in prompt or "local" in prompt or "neighbourhood" in prompt or "community" in prompt, (
            "Restaurant local_prompt should mention footfall, dining, local, or neighbourhood"
        )

    def test_clinic_prompt_mentions_local_health(
        self, clinic_pack,
    ):
        """The clinic local_prompt mentions clinic-specific local marketing."""
        prompt = clinic_pack.local_prompt.lower()
        assert "local" in prompt or "community" in prompt or "neighbourhood" in prompt or "patient" in prompt or "clinic" in prompt, (
            "Clinic local_prompt should mention local, community, neighbourhood, or patients"
        )

    def test_restaurant_and_clinic_prompts_differ(
        self, restaurant_pack, clinic_pack,
    ):
        """Restaurant and clinic local_prompts are genuinely different."""
        assert restaurant_pack.local_prompt != clinic_pack.local_prompt, (
            "Restaurant and clinic local_prompts should be different"
        )

    def test_restaurant_prompt_differs_from_business(
        self, restaurant_pack, business_pack,
    ):
        """Restaurant local_prompt differs from business."""
        assert restaurant_pack.local_prompt != business_pack.local_prompt, (
            "Restaurant and business local_prompts should be different"
        )

    def test_clinic_prompt_differs_from_business(
        self, clinic_pack, business_pack,
    ):
        """Clinic local_prompt differs from business."""
        assert clinic_pack.local_prompt != business_pack.local_prompt, (
            "Clinic and business local_prompts should be different"
        )
