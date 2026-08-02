"""Campaign Quality regression suite (P1.10).

Verifies that every campaign preview includes ALL 9 quality modules:
  1. creative_directions (3)
  2. hooks (5)
  3. audience_psychology
  4. offers (3)
  5. pricing_psychology (3)
  6. seasonal_ideas
  7. local_ideas
  8. differentiation
  9. ab_concepts (6)

The AIGateway is mocked to return valid responses for each module. The
CampaignBrain is mocked so no real AI/DB is needed. Tests run for all 4
domains (business, creator, restaurant, clinic).
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from prachar_shared.ai_gateway import Completion
from prachar_shared.domain_packs import register_all

# Ensure packs are registered
register_all()

ALL_DOMAINS = ["business", "creator", "restaurant", "clinic"]


# ─── Canned AI responses ───────────────────────────────────────────────────


def _preview_response() -> dict:
    """Canned campaign preview response."""
    return {
        "reply": "Here's your campaign!",
        "preview": {
            "title": "Test Campaign",
            "hero_image_concept": "A great image",
            "video_concept": "A great video",
            "post_ideas": ["Post 1", "Post 2"],
            "estimated_reach": "10,000-20,000",
            "expected_enquiries": "20-40",
            "budget_estimate": "₹15,000/month",
            "why_this_campaign": "Because it works.",
            "confidence": 85,
            "expected_benefit": "More customers",
            "risks": ["Slow first week"],
            "alternative": "Try a different angle",
        },
    }


def _creative_directions_response() -> dict:
    """Canned 3 creative directions response."""
    return {
        "creative_directions": [
            {
                "id": "direction_1",
                "hook": "Hook 1",
                "angle": "Angle 1",
                "tone": "Tone 1",
                "sample_headline": "Headline 1",
                "sample_cta": "CTA 1",
            },
            {
                "id": "direction_2",
                "hook": "Hook 2",
                "angle": "Angle 2",
                "tone": "Tone 2",
                "sample_headline": "Headline 2",
                "sample_cta": "CTA 2",
            },
            {
                "id": "direction_3",
                "hook": "Hook 3",
                "angle": "Angle 3",
                "tone": "Tone 3",
                "sample_headline": "Headline 3",
                "sample_cta": "CTA 3",
            },
        ]
    }


def _hooks_response() -> dict:
    """Canned 5 hooks response."""
    return {
        "hooks": [
            {"pattern": "Question", "copy": "Did you know?", "why_it_works": "Curiosity"},
            {"pattern": "Stat", "copy": "90% of people...", "why_it_works": "Authority"},
            {"pattern": "Story", "copy": "Once upon a time...", "why_it_works": "Emotion"},
            {"pattern": "Contrast", "copy": "Before vs after", "why_it_works": "Transformation"},
            {"pattern": "Direct", "copy": "Get yours now", "why_it_works": "Clarity"},
        ]
    }


def _audience_psychology_response() -> dict:
    """Canned audience psychology response."""
    return {
        "audience_psychology": {
            "motivations": ["Save time", "Save money"],
            "objections": ["Too expensive", "Not sure it works"],
            "emotional_triggers": ["Fear of missing out", "Desire for status"],
            "decision_style": "Research-heavy, price-sensitive",
        }
    }


def _offers_response() -> dict:
    """Canned 3 offers response."""
    return {
        "offers": [
            {
                "structure": "BOGO",
                "copy": "Buy one get one free",
                "psychology_lever": "Reciprocity",
                "expected_conversion_lift": "15%",
            },
            {
                "structure": "Limited-time discount",
                "copy": "20% off this week only",
                "psychology_lever": "Scarcity",
                "expected_conversion_lift": "25%",
            },
            {
                "structure": "Bundle",
                "copy": "Get 3 for the price of 2",
                "psychology_lever": "Value anchoring",
                "expected_conversion_lift": "10%",
            },
        ]
    }


def _pricing_psychology_response() -> dict:
    """Canned 3 pricing presentations response."""
    return {
        "pricing_psychology": [
            {
                "technique": "Charm pricing",
                "copy": "₹999 instead of ₹1000",
                "rationale": "Prices ending in 9 feel cheaper",
            },
            {
                "technique": "Decoy pricing",
                "copy": "Three tiers: ₹500, ₹1500, ₹2000",
                "rationale": "The middle option looks like the best value",
            },
            {
                "technique": "Anchor pricing",
                "copy": "Was ₹2000, now ₹999",
                "rationale": "Anchoring to a high reference price",
            },
        ]
    }


def _seasonal_ideas_response() -> dict:
    """Canned seasonal ideas response."""
    return {
        "seasonal_ideas": [
            {"month": "October", "occasion": "Diwali", "idea": "Festive combo", "copy": "Celebrate Diwali with us"},
            {"month": "December", "occasion": "New Year", "idea": "New Year deal", "copy": "Start the year right"},
            {"month": "August", "occasion": "Independence Day", "idea": "Patriotic offer", "copy": "Freedom sale"},
        ]
    }


def _local_ideas_response() -> dict:
    """Canned local marketing ideas response."""
    return {
        "local_ideas": [
            {"type": "Community event", "idea": "Sponsor a local festival", "copy": "We support our community"},
            {"type": "Local partnership", "idea": "Partner with nearby shops", "copy": "Shop local, save more"},
            {"type": "Geo-targeted ad", "idea": "Target 5km radius", "copy": "Right around the corner"},
        ]
    }


def _differentiation_response() -> dict:
    """Canned competitor differentiation response."""
    return {
        "differentiation": [
            {
                "competitor_claim": "We're the cheapest",
                "our_counter": "We focus on quality",
                "evidence": "Premium ingredients",
            },
            {
                "competitor_claim": "Fastest delivery",
                "our_counter": "Fresh to order",
                "evidence": "No reheated food",
            },
            {
                "competitor_claim": "Biggest portions",
                "our_counter": "Crafted with care",
                "evidence": "Every bite is perfect",
            },
        ]
    }


def _ab_concepts_response() -> dict:
    """Canned 6 A/B concepts response (3 directions × 2 variants)."""
    return {
        "ab_concepts": [
            {
                "direction_id": "direction_1",
                "variant_label": "A",
                "what_changed": "Refined headline",
                "why": "More sensory detail",
                "expected_audience_segment": "Foodies",
                "hook": "Hook A1",
                "headline": "Headline A1",
                "cta": "CTA A1",
            },
            {
                "direction_id": "direction_1",
                "variant_label": "B",
                "what_changed": "Social proof angle",
                "why": "Builds trust",
                "expected_audience_segment": "New customers",
                "hook": "Hook B1",
                "headline": "Headline B1",
                "cta": "CTA B1",
            },
            {
                "direction_id": "direction_2",
                "variant_label": "A",
                "what_changed": "Kept original angle",
                "why": "Heritage resonates",
                "expected_audience_segment": "Locals",
                "hook": "Hook A2",
                "headline": "Headline A2",
                "cta": "CTA A2",
            },
            {
                "direction_id": "direction_2",
                "variant_label": "B",
                "what_changed": "Nostalgia angle",
                "why": "Emotional trigger",
                "expected_audience_segment": "Expats",
                "hook": "Hook B2",
                "headline": "Headline B2",
                "cta": "CTA B2",
            },
            {
                "direction_id": "direction_3",
                "variant_label": "A",
                "what_changed": "Added urgency",
                "why": "Drives faster conversion",
                "expected_audience_segment": "Budget-conscious",
                "hook": "Hook A3",
                "headline": "Headline A3",
                "cta": "CTA A3",
            },
            {
                "direction_id": "direction_3",
                "variant_label": "B",
                "what_changed": "Family angle",
                "why": "Expands audience",
                "expected_audience_segment": "Families",
                "hook": "Hook B3",
                "headline": "Headline B3",
                "cta": "CTA B3",
            },
        ]
    }


# ─── Fake gateway ──────────────────────────────────────────────────────────


def _make_fake_gateway() -> MagicMock:
    """Build a mock AIGateway that returns canned JSON for each module.

    The task name is used to distinguish which module is being called:
      - {pack_id}_campaign_preview → preview response
      - {pack.id}_creative_directions → creative directions response
      - {pack_id}_hooks → hooks response
      - {pack_id}_audience_psychology → audience psychology response
      - {pack_id}_offers → offers response
      - {pack_id}_pricing_psychology → pricing psychology response
      - {pack_id}_seasonal_ideas → seasonal ideas response
      - {pack_id}_local_ideas → local ideas response
      - {pack_id}_differentiation → differentiation response
      - ab_concepts → A/B concepts response
    """
    def fake_complete(prompt, **kwargs):
        task = kwargs.get("task", "")
        if "creative_directions" in task:
            return Completion(
                text=json.dumps(_creative_directions_response()),
                tokens_used=200, model="test", confidence=0.9,
            )
        if "hooks" in task:
            return Completion(
                text=json.dumps(_hooks_response()),
                tokens_used=200, model="test", confidence=0.9,
            )
        if "audience_psychology" in task:
            return Completion(
                text=json.dumps(_audience_psychology_response()),
                tokens_used=200, model="test", confidence=0.9,
            )
        if "offers" in task:
            return Completion(
                text=json.dumps(_offers_response()),
                tokens_used=200, model="test", confidence=0.9,
            )
        if "pricing_psychology" in task:
            return Completion(
                text=json.dumps(_pricing_psychology_response()),
                tokens_used=200, model="test", confidence=0.9,
            )
        if "seasonal_ideas" in task:
            return Completion(
                text=json.dumps(_seasonal_ideas_response()),
                tokens_used=200, model="test", confidence=0.9,
            )
        if "local_ideas" in task:
            return Completion(
                text=json.dumps(_local_ideas_response()),
                tokens_used=200, model="test", confidence=0.9,
            )
        if "differentiation" in task:
            return Completion(
                text=json.dumps(_differentiation_response()),
                tokens_used=200, model="test", confidence=0.9,
            )
        if "ab_concepts" in task:
            return Completion(
                text=json.dumps(_ab_concepts_response()),
                tokens_used=300, model="test", confidence=0.9,
            )
        # Default: campaign preview
        return Completion(
            text=json.dumps(_preview_response()),
            tokens_used=500, model="test", confidence=0.85,
        )

    gw = MagicMock()
    gw.complete = MagicMock(side_effect=fake_complete)
    return gw


# ─── Shared fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def fake_brand():
    """A fake Brand object with the attributes the engine reads."""
    brand = MagicMock()
    brand.id = uuid.uuid4()
    brand.name = "Test Brand"
    brand.website = "https://example.com"
    brand.category = "business"
    brand.brand_graph = {}
    return brand


@pytest.fixture
def fake_user():
    """A fake CurrentUser with a tenant."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = uuid.uuid4()
    user.tenant = MagicMock()
    user.tenant.plan = "agency"
    return user


@pytest.fixture
def fake_session(fake_brand):
    """A fake AsyncSession that returns the fake brand on select."""
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=fake_brand)
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def fake_gateway():
    """A fake AIGateway that returns canned JSON for every module."""
    return _make_fake_gateway()


async def _run_campaign(pack_id, gateway, fake_brand, fake_user, fake_session):
    """Helper: run the consult engine's campaign method with mocked brain + audit."""
    from prachar_api.infrastructure.consult_engine import ConsultEngine

    engine = ConsultEngine(gateway=gateway)
    with patch(
        "prachar_shared.marketing_intelligence.CampaignBrain.generate_campaign",
        new_callable=AsyncMock,
        return_value={"engine_outputs": {}},
    ), patch(
        "prachar_api.infrastructure.consult_engine.log_audit",
        new_callable=AsyncMock,
    ):
        result = await engine.campaign(
            pack_id=pack_id,
            brand_id=fake_brand.id,
            goal="get more customers",
            budget="₹15,000",
            user=fake_user,
            session=fake_session,
        )
    return result


from unittest.mock import patch


# ─── Tests: all 9 modules present ──────────────────────────────────────────


class TestAllModulesPresent:
    """Verify that every campaign preview includes ALL 9 quality modules."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_preview_has_creative_directions(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """The preview contains creative_directions."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        assert "creative_directions" in result.preview
        assert isinstance(result.preview["creative_directions"], list)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_preview_has_hooks(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """The preview contains hooks."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        assert "hooks" in result.preview
        assert isinstance(result.preview["hooks"], list)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_preview_has_audience_psychology(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """The preview contains audience_psychology."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        assert "audience_psychology" in result.preview
        assert isinstance(result.preview["audience_psychology"], dict)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_preview_has_offers(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """The preview contains offers."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        assert "offers" in result.preview
        assert isinstance(result.preview["offers"], list)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_preview_has_pricing_psychology(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """The preview contains pricing_psychology."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        assert "pricing_psychology" in result.preview
        assert isinstance(result.preview["pricing_psychology"], list)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_preview_has_seasonal_ideas(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """The preview contains seasonal_ideas."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        assert "seasonal_ideas" in result.preview
        assert isinstance(result.preview["seasonal_ideas"], list)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_preview_has_local_ideas(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """The preview contains local_ideas."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        assert "local_ideas" in result.preview
        assert isinstance(result.preview["local_ideas"], list)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_preview_has_differentiation(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """The preview contains differentiation."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        assert "differentiation" in result.preview
        assert isinstance(result.preview["differentiation"], list)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_preview_has_ab_concepts(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """The preview contains ab_concepts."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        assert "ab_concepts" in result.preview
        assert isinstance(result.preview["ab_concepts"], list)


# ─── Tests: correct counts per module ──────────────────────────────────────


class TestModuleCounts:
    """Verify each module has the correct count of items."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_creative_directions_count_is_3(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """creative_directions has exactly 3 entries."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        assert len(result.preview["creative_directions"]) == 3

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_hooks_count_is_5(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """hooks has exactly 5 entries."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        assert len(result.preview["hooks"]) == 5

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_offers_count_is_3(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """offers has exactly 3 entries."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        assert len(result.preview["offers"]) == 3

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_pricing_psychology_count_is_3(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """pricing_psychology has exactly 3 entries."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        assert len(result.preview["pricing_psychology"]) == 3

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_ab_concepts_count_is_6(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """ab_concepts has exactly 6 entries (3 directions × 2 variants)."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        assert len(result.preview["ab_concepts"]) == 6

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_seasonal_ideas_non_empty(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """seasonal_ideas is non-empty."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        assert len(result.preview["seasonal_ideas"]) > 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_local_ideas_non_empty(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """local_ideas is non-empty (except creator, which has no local presence)."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        if pack_id == "creator":
            # Creator pack has no local presence — local_ideas is [] by design
            assert result.preview["local_ideas"] == []
        else:
            assert len(result.preview["local_ideas"]) > 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_differentiation_non_empty(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """differentiation is non-empty."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        assert len(result.preview["differentiation"]) > 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_audience_psychology_has_fields(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """audience_psychology has the required fields."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        psych = result.preview["audience_psychology"]
        assert "motivations" in psych
        assert "objections" in psych
        assert "emotional_triggers" in psych
        assert "decision_style" in psych


# ─── Tests: all 9 modules in a single preview ──────────────────────────────


class TestAllModulesInOnePreview:
    """Verify that a single campaign preview has ALL 9 modules at once."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_all_9_modules_present(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """A single campaign preview contains all 9 quality modules."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        preview = result.preview
        required_modules = [
            "creative_directions",
            "hooks",
            "audience_psychology",
            "offers",
            "pricing_psychology",
            "seasonal_ideas",
            "local_ideas",
            "differentiation",
            "ab_concepts",
        ]
        for module in required_modules:
            assert module in preview, (
                f"Pack {pack_id}: preview missing module {module!r}"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack_id", ALL_DOMAINS)
    async def test_all_counts_correct(
        self, pack_id, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """All module counts are correct in a single preview."""
        result = await _run_campaign(pack_id, fake_gateway, fake_brand, fake_user, fake_session)
        preview = result.preview
        assert len(preview["creative_directions"]) == 3
        assert len(preview["hooks"]) == 5
        assert len(preview["offers"]) == 3
        assert len(preview["pricing_psychology"]) == 3
        assert len(preview["ab_concepts"]) == 6
        assert len(preview["seasonal_ideas"]) > 0
        # Creator pack has no local presence — local_ideas is [] by design
        if pack_id != "creator":
            assert len(preview["local_ideas"]) > 0
        else:
            assert preview["local_ideas"] == []
        assert len(preview["differentiation"]) > 0
        assert isinstance(preview["audience_psychology"], dict)
