"""Tests for the audience psychology generator (P1.3).

Verifies that generate_audience_psychology returns an AudiencePsychology with
the required fields (motivations, objections, emotional_triggers,
decision_style), caps motivations/objections at 3, falls back gracefully on
AI failure, and works across all 4 domain packs.
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import Completion
from prachar_shared.domain_packs import register_all
from prachar_shared.marketing_intelligence.audience_psychology import (
    AudiencePsychology,
    generate_audience_psychology,
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
def campaign_context():
    """A minimal campaign context dict."""
    return {
        "brand_name": "Paradise Biryani",
        "goal": "get more customers",
        "budget": "₹15,000",
        "campaign_analysis": "The brand is known for Hyderabadi biryani.",
    }


@pytest.fixture
def psychology_response():
    """A well-formed audience psychology JSON response from the AI gateway."""
    return {
        "motivations": [
            "Craving authentic Hyderabadi biryani",
            "A memorable dining experience with family",
            "Quick delivery for a weekend treat",
        ],
        "objections": [
            "Price feels high for casual dining",
            "Long wait times during peak hours",
            "Unsure about hygiene standards",
        ],
        "emotional_triggers": [
            "craving",
            "nostalgia",
            "social belonging",
            "indulgence",
        ],
        "decision_style": "spontaneous and socially influenced",
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


class TestGenerateAudiencePsychology:
    """Tests for generate_audience_psychology()."""

    def test_returns_audience_psychology_instance(
        self, business_pack, campaign_context, psychology_response,
    ):
        """generate_audience_psychology returns an AudiencePsychology object."""
        gw = _make_gateway(psychology_response)
        psych = generate_audience_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert isinstance(psych, AudiencePsychology)

    def test_has_required_fields(
        self, business_pack, campaign_context, psychology_response,
    ):
        """The returned object has all 4 required fields."""
        gw = _make_gateway(psychology_response)
        psych = generate_audience_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        required = {"motivations", "objections", "emotional_triggers", "decision_style"}
        assert required.issubset(set(psych.to_dict().keys()))

    def test_motivations_capped_at_3(
        self, business_pack, campaign_context,
    ):
        """Motivations are capped at 3 even if the AI returns more."""
        response = {
            "motivations": ["m1", "m2", "m3", "m4", "m5"],
            "objections": ["o1", "o2", "o3"],
            "emotional_triggers": ["t1"],
            "decision_style": "rational",
        }
        gw = _make_gateway(response)
        psych = generate_audience_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(psych.motivations) == 3
        assert psych.motivations == ["m1", "m2", "m3"]

    def test_objections_capped_at_3(
        self, business_pack, campaign_context,
    ):
        """Objections are capped at 3 even if the AI returns more."""
        response = {
            "motivations": ["m1"],
            "objections": ["o1", "o2", "o3", "o4"],
            "emotional_triggers": ["t1"],
            "decision_style": "cautious",
        }
        gw = _make_gateway(response)
        psych = generate_audience_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(psych.objections) == 3
        assert psych.objections == ["o1", "o2", "o3"]

    def test_emotional_triggers_not_capped(
        self, business_pack, campaign_context,
    ):
        """Emotional triggers are not capped (can be any length)."""
        response = {
            "motivations": ["m1"],
            "objections": ["o1"],
            "emotional_triggers": ["t1", "t2", "t3", "t4", "t5", "t6"],
            "decision_style": "impulse",
        }
        gw = _make_gateway(response)
        psych = generate_audience_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(psych.emotional_triggers) == 6

    def test_decision_style_is_string(
        self, business_pack, campaign_context, psychology_response,
    ):
        """decision_style is a non-empty string."""
        gw = _make_gateway(psychology_response)
        psych = generate_audience_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert isinstance(psych.decision_style, str)
        assert psych.decision_style

    def test_to_dict_returns_all_fields(
        self, business_pack, campaign_context, psychology_response,
    ):
        """to_dict() returns a dict with all 4 fields."""
        gw = _make_gateway(psychology_response)
        psych = generate_audience_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        d = psych.to_dict()
        assert isinstance(d, dict)
        assert "motivations" in d
        assert "objections" in d
        assert "emotional_triggers" in d
        assert "decision_style" in d

    def test_falls_back_to_empty_defaults_on_ai_failure(
        self, business_pack, campaign_context,
    ):
        """When the AI gateway raises, generate_audience_psychology returns empty defaults."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=RuntimeError("AI is down"))
        psych = generate_audience_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert isinstance(psych, AudiencePsychology)
        assert psych.motivations == []
        assert psych.objections == []
        assert psych.emotional_triggers == []
        assert psych.decision_style == ""

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
        psych = generate_audience_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert isinstance(psych, AudiencePsychology)
        assert psych.motivations == []
        assert psych.objections == []
        assert psych.emotional_triggers == []
        assert psych.decision_style == ""

    def test_handles_partial_response(
        self, business_pack, campaign_context,
    ):
        """Missing fields in the AI response are filled with empty defaults."""
        response = {
            "motivations": ["Only one motivation"],
        }
        gw = _make_gateway(response)
        psych = generate_audience_psychology(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert psych.motivations == ["Only one motivation"]
        assert psych.objections == []
        assert psych.emotional_triggers == []
        assert psych.decision_style == ""


class TestAllDomainPacks:
    """Tests that generate_audience_psychology works for all 4 domain packs."""

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
            "motivations": ["m1", "m2", "m3"],
            "objections": ["o1", "o2", "o3"],
            "emotional_triggers": ["t1", "t2"],
            "decision_style": "rational",
        }

    def test_all_packs_have_audience_psychology_prompt(self, all_packs):
        """Every domain pack defines an audience_psychology_prompt."""
        for pack in all_packs:
            assert hasattr(pack, "audience_psychology_prompt"), (
                f"Pack {pack.id} missing audience_psychology_prompt"
            )
            assert isinstance(pack.audience_psychology_prompt, str)
            assert pack.audience_psychology_prompt, (
                f"Pack {pack.id} has empty audience_psychology_prompt"
            )

    def test_generate_works_for_all_packs(self, all_packs, ctx, resp):
        """generate_audience_psychology returns valid output for every pack."""
        gw = _make_gateway(resp)
        for pack in all_packs:
            psych = generate_audience_psychology(
                campaign_context=ctx,
                domain_pack=pack,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )
            assert isinstance(psych, AudiencePsychology), (
                f"Pack {pack.id} did not return AudiencePsychology"
            )
            assert len(psych.motivations) == 3
            assert len(psych.objections) == 3
            assert psych.decision_style == "rational"

    def test_all_packs_fallback_gracefully(self, all_packs, ctx):
        """Every pack falls back to empty defaults on AI failure."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=RuntimeError("down"))
        for pack in all_packs:
            psych = generate_audience_psychology(
                campaign_context=ctx,
                domain_pack=pack,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )
            assert isinstance(psych, AudiencePsychology)
            assert psych.motivations == []
            assert psych.objections == []
            assert psych.emotional_triggers == []
            assert psych.decision_style == ""
