"""Tests for the hook pattern generator (P1.2).

Verifies that generate_hooks returns exactly 5 hooks with the required fields
(pattern, copy, why_it_works) and the 5 canonical pattern types in order.
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import Completion
from prachar_shared.domain_packs import register_all
from prachar_shared.domain_packs.base import BaseDomainPack
from prachar_shared.marketing_intelligence.hooks import (
    HOOK_PATTERNS,
    Hook,
    HookPattern,
    generate_hooks,
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
def hooks_response():
    """A well-formed 5-hook JSON response from the AI gateway."""
    return {
        "hooks": [
            {
                "pattern": "question",
                "copy": "Ever wondered why Hyderabad can't stop talking about biryani?",
                "why_it_works": "Curiosity gap — the brain needs to resolve the unanswered question.",
            },
            {
                "pattern": "stat",
                "copy": "We marinate our biryani for 12 hours before it reaches your plate.",
                "why_it_works": "Specificity builds credibility and makes the claim tangible.",
            },
            {
                "pattern": "story",
                "copy": "Three generations of one family have made this biryani the same way.",
                "why_it_works": "Narrative transport — stories create emotional connection.",
            },
            {
                "pattern": "contrarian",
                "copy": "The best biryani isn't about spice. It's about patience.",
                "why_it_works": "Pattern interrupt — challenges a common assumption to grab attention.",
            },
            {
                "pattern": "aspiration",
                "copy": "Be the friend who always knows where the legendary biryani is.",
                "why_it_works": "Identity appeal — positions the product as a status symbol.",
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


class TestGenerateHooks:
    """Tests for generate_hooks()."""

    def test_returns_exactly_5_hooks(
        self, business_pack, campaign_context, hooks_response,
    ):
        """generate_hooks returns exactly 5 hooks."""
        gw = _make_gateway(hooks_response)
        hooks = generate_hooks(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(hooks) == 5

    def test_each_hook_has_required_fields(
        self, business_pack, campaign_context, hooks_response,
    ):
        """Each hook has pattern, copy, and why_it_works."""
        gw = _make_gateway(hooks_response)
        hooks = generate_hooks(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        required = {"pattern", "copy", "why_it_works"}
        for hook in hooks:
            assert isinstance(hook, Hook)
            hook_dict = hook.to_dict()
            assert required.issubset(hook_dict.keys()), (
                f"Hook {hook.pattern} missing keys: {required - set(hook_dict.keys())}"
            )

    def test_hooks_are_in_canonical_pattern_order(
        self, business_pack, campaign_context, hooks_response,
    ):
        """The 5 hooks are in canonical order: question, stat, story, contrarian, aspiration."""
        gw = _make_gateway(hooks_response)
        hooks = generate_hooks(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        patterns = [h.pattern for h in hooks]
        assert patterns == HOOK_PATTERNS
        assert patterns == [
            HookPattern.QUESTION.value,
            HookPattern.STAT.value,
            HookPattern.STORY.value,
            HookPattern.CONTRARIAN.value,
            HookPattern.ASPIRATION.value,
        ]

    def test_hook_copy_and_why_it_works_are_non_empty(
        self, business_pack, campaign_context, hooks_response,
    ):
        """Each hook's copy and why_it_works are non-empty strings."""
        gw = _make_gateway(hooks_response)
        hooks = generate_hooks(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for hook in hooks:
            assert isinstance(hook.copy, str) and hook.copy, (
                f"Hook {hook.pattern} copy is empty"
            )
            assert isinstance(hook.why_it_works, str) and hook.why_it_works, (
                f"Hook {hook.pattern} why_it_works is empty"
            )

    def test_falls_back_to_5_empty_hooks_on_ai_failure(
        self, business_pack, campaign_context,
    ):
        """When the AI gateway raises, generate_hooks returns 5 placeholder hooks."""
        gw = MagicMock()
        gw.complete = MagicMock(side_effect=RuntimeError("AI is down"))
        hooks = generate_hooks(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(hooks) == 5
        # All 5 canonical patterns present
        patterns = [h.pattern for h in hooks]
        assert patterns == HOOK_PATTERNS
        # Copy and why_it_works are empty strings (graceful fallback)
        for hook in hooks:
            assert hook.copy == ""
            assert hook.why_it_works == ""

    def test_fills_missing_patterns_with_placeholders(
        self, business_pack, campaign_context,
    ):
        """If the AI only returns 3 hooks, the missing 2 are filled with placeholders."""
        partial = {
            "hooks": [
                {"pattern": "question", "copy": "Q?", "why_it_works": "Curiosity."},
                {"pattern": "stat", "copy": "S!", "why_it_works": "Credibility."},
                {"pattern": "aspiration", "copy": "A!", "why_it_works": "Identity."},
            ]
        }
        gw = _make_gateway(partial)
        hooks = generate_hooks(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(hooks) == 5
        # story and contrarian should be placeholders
        by_pattern = {h.pattern: h for h in hooks}
        assert by_pattern["story"].copy == ""
        assert by_pattern["contrarian"].copy == ""
        # The returned ones should have their values
        assert by_pattern["question"].copy == "Q?"
        assert by_pattern["stat"].copy == "S!"
        assert by_pattern["aspiration"].copy == "A!"

    def test_uses_domain_pack_hooks_prompt_in_request(
        self, business_pack, campaign_context, hooks_response,
    ):
        """The prompt sent to the gateway includes the pack's hooks_prompt."""
        gw = _make_gateway(hooks_response)
        generate_hooks(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        gw.complete.assert_called_once()
        call_kwargs = gw.complete.call_args.kwargs
        call_prompt = call_kwargs["prompt"]
        # The hooks_prompt from the business pack should appear in the prompt
        assert business_pack.hooks_prompt in call_prompt
        # Task name should include the pack id + "hooks"
        assert call_kwargs["task"] == "business_hooks"
        # Should use Tier.large
        assert call_kwargs["tier"] == "large"

    def test_works_with_all_domain_packs(
        self, campaign_context, hooks_response,
    ):
        """generate_hooks works for business, creator, restaurant, clinic."""
        from prachar_shared.domain_packs import get_registry

        reg = get_registry()
        for pack_id in ["business", "creator", "restaurant", "clinic"]:
            pack = reg.get_required(pack_id)
            gw = _make_gateway(hooks_response)
            hooks = generate_hooks(
                campaign_context=campaign_context,
                domain_pack=pack,
                gateway=gw,
                tenant_id=uuid.uuid4(),
                plan="agency",
            )
            assert len(hooks) == 5, f"Pack {pack_id} returned {len(hooks)} hooks"
            assert pack.hooks_prompt, f"Pack {pack_id} has empty hooks_prompt"

    def test_works_with_minimal_domain_pack(
        self, campaign_context, hooks_response,
    ):
        """generate_hooks works with a bare BaseDomainPack (empty hooks_prompt)."""

        class MinimalPack(BaseDomainPack):
            id = "minimal"
            label = "Minimal"
            hooks_prompt = "Keep hooks simple."

        pack = MinimalPack()
        gw = _make_gateway(hooks_response)
        hooks = generate_hooks(
            campaign_context=campaign_context,
            domain_pack=pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        assert len(hooks) == 5

    def test_to_dict_returns_all_fields(
        self, business_pack, campaign_context, hooks_response,
    ):
        """Hook.to_dict() returns a dict with pattern, copy, why_it_works."""
        gw = _make_gateway(hooks_response)
        hooks = generate_hooks(
            campaign_context=campaign_context,
            domain_pack=business_pack,
            gateway=gw,
            tenant_id=uuid.uuid4(),
            plan="agency",
        )
        for hook in hooks:
            d = hook.to_dict()
            assert set(d.keys()) == {"pattern", "copy", "why_it_works"}
            assert d["pattern"] == hook.pattern
            assert d["copy"] == hook.copy
            assert d["why_it_works"] == hook.why_it_works
