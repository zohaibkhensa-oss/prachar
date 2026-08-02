"""Tests for the seasonal ideas generator (P1.6).

Verifies that generate_seasonal_ideas returns SeasonalIdea objects with the
required fields (month, occasion, idea, copy), falls back gracefully on AI
failure, works across all 4 domain packs, and produces domain-specific
seasonal differences (restaurant vs clinic).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import BudgetExceeded, Completion
from prachar_shared.domain_packs import register_all
from prachar_shared.marketing_intelligence.seasonal_engine import (
    SeasonalIdea,
    generate_seasonal_ideas,
    _get_target_months,
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
def seasonal_response():
    """A well-formed seasonal ideas JSON response from the AI gateway."""
    now = datetime.now()
    months = _get_target_months(now)
    return {
        "seasonal_ideas": [
            {
                "month": months[0],
                "occasion": "Festive season",
                "idea": "Launch a festive family combo for the holiday season.",
                "copy": "Celebrate with our special festive family combo — order now!",
            },
            {
                "month": months[1],
                "occasion": "Winter warm-up",
                "idea": "Promote hot biryani and kebabs as perfect winter comfort food.",
                "copy": "Warm up this winter with our signature Hyderabadi biryani.",
            },
            {
                "month": months[2],
                "occasion": "New Year celebrations",
                "idea": "New Year feast package for groups and families.",
                "copy": "Ring in the New Year with our grand feast package!",
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


class TestGetTargetMonths:
    """Tests for the _get_target_months helper."""

    def test_returns_3_months(self):
        """_get_target_months returns exactly 3 month names."""
        months = _get_target_months(datetime(2024, 10, 15))
        assert len(months) == 3

    def test_returns_current_month_first(self):
        """The first month is the current month."""
        months = _get_target_months(datetime(2024, 10, 15))
        assert months[0] == "October"

    def test_wraps_around_year_end(self):
        """Months wrap around December → January correctly."""
        months = _get_target_months(datetime(2024, 12, 15))
        assert months[0] == "December"
        assert months[1] == "January"
        assert months[2] == "February"

    def test_returns_full_month_names(self):
        """All returned values are valid full month names."""
        valid_months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        months = _get_target_months(datetime(2024, 6, 15))
        for m in months:
            assert m in valid_months


class TestGenerateSeasonalIdeas:
    """Tests for generate_seasonal_ideas()."""

    def test_returns_list_of_seasonal_ideas(
        self, business_pack, campaign_context, seasonal_response,
    ):
        """generate_seasonal_ideas returns a list of SeasonalIdea objects."""
        gw = _make_gateway(seasonal_response)
        ideas = generate_seasonal_ideas(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert isinstance(ideas, list)
        assert all(isinstance(i, SeasonalIdea) for i in ideas)

    def test_returns_ideas_for_3_months(
        self, business_pack, campaign_context, seasonal_response,
    ):
        """generate_seasonal_ideas returns ideas for 3 months."""
        gw = _make_gateway(seasonal_response)
        ideas = generate_seasonal_ideas(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(ideas) == 3

    def test_has_required_fields(
        self, business_pack, campaign_context, seasonal_response,
    ):
        """Each idea has all 4 required fields."""
        gw = _make_gateway(seasonal_response)
        ideas = generate_seasonal_ideas(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        required = {"month", "occasion", "idea", "copy"}
        for idea in ideas:
            assert required.issubset(set(idea.to_dict().keys()))

    def test_month_is_string(
        self, business_pack, campaign_context, seasonal_response,
    ):
        """Each idea's month is a non-empty string."""
        gw = _make_gateway(seasonal_response)
        ideas = generate_seasonal_ideas(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for idea in ideas:
            assert isinstance(idea.month, str)
            assert idea.month

    def test_occasion_is_string(
        self, business_pack, campaign_context, seasonal_response,
    ):
        """Each idea's occasion is a non-empty string."""
        gw = _make_gateway(seasonal_response)
        ideas = generate_seasonal_ideas(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for idea in ideas:
            assert isinstance(idea.occasion, str)
            assert idea.occasion

    def test_idea_is_string(
        self, business_pack, campaign_context, seasonal_response,
    ):
        """Each idea's idea is a non-empty string."""
        gw = _make_gateway(seasonal_response)
        ideas = generate_seasonal_ideas(
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
        self, business_pack, campaign_context, seasonal_response,
    ):
        """Each idea's copy is a non-empty string."""
        gw = _make_gateway(seasonal_response)
        ideas = generate_seasonal_ideas(
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
        self, business_pack, campaign_context, seasonal_response,
    ):
        """SeasonalIdea.to_dict() returns a dict with all 4 fields."""
        gw = _make_gateway(seasonal_response)
        ideas = generate_seasonal_ideas(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for idea in ideas:
            d = idea.to_dict()
            assert isinstance(d, dict)
            assert set(d.keys()) == {"month", "occasion", "idea", "copy"}
            assert d["month"] == idea.month
            assert d["occasion"] == idea.occasion
            assert d["idea"] == idea.idea
            assert d["copy"] == idea.copy

    def test_uses_domain_pack_seasonal_prompt_in_request(
        self, business_pack, campaign_context, seasonal_response,
    ):
        """The prompt sent to the gateway includes the pack's seasonal_prompt."""
        gw = _make_gateway(seasonal_response)
        generate_seasonal_ideas(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        gw.complete.assert_called_once()
        call_kwargs = gw.complete.call_args.kwargs
        call_prompt = call_kwargs["prompt"]
        assert business_pack.seasonal_prompt in call_prompt
        assert call_kwargs["task"] == "business_seasonal_ideas"
        assert call_kwargs["tier"] == "large"

    def test_prompt_includes_target_months(
        self, business_pack, campaign_context, seasonal_response,
    ):
        """The prompt sent to the gateway includes the target months."""
        gw = _make_gateway(seasonal_response)
        generate_seasonal_ideas(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        call_prompt = gw.complete.call_args.kwargs["prompt"]
        # The prompt should mention at least the current month
        current_month = _get_target_months()[0]
        assert current_month in call_prompt

    def test_works_with_minimal_domain_pack(
        self, campaign_context, seasonal_response,
    ):
        """generate_seasonal_ideas works with a bare BaseDomainPack."""
        from prachar_shared.domain_packs.base import BaseDomainPack

        class MinimalPack(BaseDomainPack):
            id = "minimal"
            label = "Minimal"
            seasonal_prompt = "Keep seasonal ideas simple."

        pack = MinimalPack()
        gw = _make_gateway(seasonal_response)
        ideas = generate_seasonal_ideas(
            campaign_context=campaign_context,
            domain_pack=pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(ideas) == 3


class TestGracefulFallback:
    """Tests for graceful fallback on failure."""

    def test_falls_back_to_empty_list_on_ai_failure(
        self, business_pack, campaign_context,
    ):
        """When the AI gateway raises, generate_seasonal_ideas returns []."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=RuntimeError("AI is down"))
        ideas = generate_seasonal_ideas(
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
        ideas = generate_seasonal_ideas(
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
            generate_seasonal_ideas(
                campaign_context=campaign_context,
                domain_pack=business_pack,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )


class TestAllDomainPacks:
    """Tests that generate_seasonal_ideas works for all 4 domain packs."""

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
        months = _get_target_months()
        return {
            "seasonal_ideas": [
                {"month": months[0], "occasion": "Festive", "idea": "Festive campaign.", "copy": "Celebrate!"},
                {"month": months[1], "occasion": "Winter", "idea": "Winter campaign.", "copy": "Stay warm!"},
                {"month": months[2], "occasion": "New Year", "idea": "New Year campaign.", "copy": "New beginnings!"},
            ]
        }

    def test_all_packs_have_seasonal_prompt(self, all_packs):
        """Every domain pack defines a seasonal_prompt."""
        for pack in all_packs:
            assert hasattr(pack, "seasonal_prompt"), (
                f"Pack {pack.id} missing seasonal_prompt"
            )
            assert isinstance(pack.seasonal_prompt, str)
            assert pack.seasonal_prompt, (
                f"Pack {pack.id} has empty seasonal_prompt"
            )

    def test_generate_works_for_all_packs(self, all_packs, ctx, resp):
        """generate_seasonal_ideas returns valid output for every pack."""
        gw = _make_gateway(resp)
        for pack in all_packs:
            ideas = generate_seasonal_ideas(
                campaign_context=ctx,
                domain_pack=pack,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )
            assert isinstance(ideas, list), f"Pack {pack.id} did not return a list"
            for idea in ideas:
                assert isinstance(idea, SeasonalIdea)

    def test_all_packs_fallback_gracefully(self, all_packs, ctx):
        """Every pack falls back to [] on AI failure."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=RuntimeError("down"))
        for pack in all_packs:
            ideas = generate_seasonal_ideas(
                campaign_context=ctx,
                domain_pack=pack,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )
            assert isinstance(ideas, list)
            assert len(ideas) == 0


class TestDomainSpecificSeasonal:
    """Tests that domain packs produce domain-specific seasonal guidance."""

    def test_restaurant_prompt_mentions_festive_or_menu(
        self, restaurant_pack,
    ):
        """The restaurant seasonal_prompt mentions restaurant-specific seasonal ideas."""
        prompt = restaurant_pack.seasonal_prompt.lower()
        assert "festive" in prompt or "menu" in prompt or "seasonal" in prompt or "festival" in prompt, (
            "Restaurant seasonal_prompt should mention festive menus, festivals, or seasonal dishes"
        )

    def test_clinic_prompt_mentions_checkup_or_seasonal_health(
        self, clinic_pack,
    ):
        """The clinic seasonal_prompt mentions clinic-specific seasonal ideas."""
        prompt = clinic_pack.seasonal_prompt.lower()
        assert "checkup" in prompt or "seasonal" in prompt or "health" in prompt or "monsoon" in prompt, (
            "Clinic seasonal_prompt should mention seasonal checkups, health, or monsoon"
        )

    def test_restaurant_and_clinic_prompts_differ(
        self, restaurant_pack, clinic_pack,
    ):
        """Restaurant and clinic seasonal_prompts are genuinely different."""
        assert restaurant_pack.seasonal_prompt != clinic_pack.seasonal_prompt, (
            "Restaurant and clinic seasonal_prompts should be different"
        )

    def test_restaurant_prompt_differs_from_business(
        self, restaurant_pack, business_pack,
    ):
        """Restaurant seasonal_prompt differs from business."""
        assert restaurant_pack.seasonal_prompt != business_pack.seasonal_prompt, (
            "Restaurant and business seasonal_prompts should be different"
        )

    def test_clinic_prompt_differs_from_business(
        self, clinic_pack, business_pack,
    ):
        """Clinic seasonal_prompt differs from business."""
        assert clinic_pack.seasonal_prompt != business_pack.seasonal_prompt, (
            "Clinic and business seasonal_prompts should be different"
        )
