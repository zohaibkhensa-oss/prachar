"""Tests for the StrategyEngine (B.1.1 + B.1.2).

Verifies:
- generate_strategies() returns 3 Strategy objects (primary, alternative, contrarian)
- each Strategy has the required fields
- explain_choice() returns reasoning + why_not fields
- fallback on AI failure
- BudgetExceeded re-raise
- _parse_strategies and _normalise_explanation helpers
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import is_dataclass
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import BudgetExceeded, Completion
from prachar_shared.marketing_intelligence.strategy_engine import (
    Strategy,
    StrategyEngine,
    _default_strategies,
    _parse_strategies,
)


# ─── Fixtures ──────────────────────────────────────────────────────────────


def _make_gateway(text: str = "{}") -> MagicMock:
    """Return a mock AIGateway whose .complete() returns Completion(text=text)."""
    gw = MagicMock()
    comp = Completion(text=text, model="test", provider="test")
    gw.complete.return_value = comp
    return gw


def _make_engine(text: str = "{}") -> StrategyEngine:
    return StrategyEngine(gateway=_make_gateway(text), tenant_id=uuid.uuid4(), plan="agency")


GOOD_STRATEGIES_JSON = """{
  "strategies": [
    {
      "name": "Signature Dish Hero",
      "approach": "Lead with your most photogenic dish across Instagram and WhatsApp.",
      "why_it_works": "Visual food content drives higher engagement for restaurants.",
      "risks": ["Depends on dish quality", "Needs professional food photography"],
      "expected_outcome": "30% increase in weekend footfall within 30 days.",
      "strategy_type": "primary"
    },
    {
      "name": "Local Influencer Network",
      "approach": "Partner with 5-10 local food influencers to review the restaurant.",
      "why_it_works": "Local influencers have high trust within their communities.",
      "risks": ["Influencer quality varies", "Requires relationship management"],
      "expected_outcome": "Reach 50K local audience with trusted endorsements.",
      "strategy_type": "alternative"
    },
    {
      "name": "Secret Menu Mystery",
      "approach": "Launch a secret menu available only via WhatsApp code words.",
      "why_it_works": "Exclusivity and mystery drive curiosity and word-of-mouth.",
      "risks": ["May confuse some customers", "Hard to scale"],
      "expected_outcome": "Viral local buzz and high WhatsApp engagement.",
      "strategy_type": "contrarian"
    }
  ]
}"""

GOOD_EXPLANATION_JSON = """{
  "chosen_strategy": "Signature Dish Hero",
  "reasoning": "Visual food content performs best on Instagram for restaurants in your area.",
  "why_not_alternative": "Influencer partnerships take longer to set up and cost more upfront.",
  "why_not_contrarian": "Secret menus can confuse new customers and slow initial adoption.",
  "key_factors": ["Budget fits Instagram focus", "Audience is visual-first", "Fast time to market"]
}"""


# ─── Strategy dataclass ────────────────────────────────────────────────────


def test_strategy_is_dataclass():
    assert is_dataclass(Strategy)


def test_strategy_to_dict_returns_all_fields():
    s = Strategy(
        name="Test",
        approach="approach",
        why_it_works="why",
        risks=["r1", "r2"],
        expected_outcome="outcome",
        strategy_type="primary",
    )
    d = s.to_dict()
    assert d["name"] == "Test"
    assert d["approach"] == "approach"
    assert d["why_it_works"] == "why"
    assert d["risks"] == ["r1", "r2"]
    assert d["expected_outcome"] == "outcome"
    assert d["strategy_type"] == "primary"


# ─── _default_strategies ───────────────────────────────────────────────────


def test_default_strategies_returns_3():
    defaults = _default_strategies()
    assert len(defaults) == 3
    types = [s.strategy_type for s in defaults]
    assert types == ["primary", "alternative", "contrarian"]


def test_default_strategies_have_required_fields():
    for s in _default_strategies():
        assert s.name
        assert s.approach
        assert s.why_it_works
        assert isinstance(s.risks, list) and len(s.risks) > 0
        assert s.expected_outcome
        assert s.strategy_type in ("primary", "alternative", "contrarian")


# ─── _parse_strategies ─────────────────────────────────────────────────────


def test_parse_strategies_valid_input():
    raw = __import__("json").loads(GOOD_STRATEGIES_JSON)
    result = _parse_strategies(raw)
    assert len(result) == 3
    assert result[0].strategy_type == "primary"
    assert result[0].name == "Signature Dish Hero"
    assert result[1].strategy_type == "alternative"
    assert result[2].strategy_type == "contrarian"


def test_parse_strategies_missing_type_falls_back_to_default():
    raw = {"strategies": [{"name": "Only One", "approach": "x", "strategy_type": "primary"}]}
    result = _parse_strategies(raw)
    assert len(result) == 3
    assert result[0].name == "Only One"
    # alternative and contrarian fall back to defaults
    assert result[1].strategy_type == "alternative"
    assert result[2].strategy_type == "contrarian"


def test_parse_strategies_empty_input():
    result = _parse_strategies({})
    assert len(result) == 3
    assert all(s.name for s in result)  # defaults have names


def test_parse_strategies_non_dict_input():
    result = _parse_strategies("not a dict")
    assert len(result) == 3


def test_parse_strategies_risks_non_list_becomes_list():
    raw = {
        "strategies": [
            {"name": "S", "approach": "a", "risks": "single risk string", "strategy_type": "primary"},
        ]
    }
    result = _parse_strategies(raw)
    assert result[0].risks == ["single risk string"]


# ─── StrategyEngine.generate_strategies ────────────────────────────────────


def test_generate_strategies_returns_3_strategies():
    engine = _make_engine(GOOD_STRATEGIES_JSON)
    result = asyncio.run(
        engine.generate_strategies(
            business_context={"name": "Test Restaurant"},
            audience_context={"age": "25-40"},
            competitor_context={"count": 5},
            budget="₹50,000",
            goal="Get more customers",
        )
    )
    assert len(result) == 3
    types = [s.strategy_type for s in result]
    assert types == ["primary", "alternative", "contrarian"]


def test_generate_strategies_each_has_required_fields():
    engine = _make_engine(GOOD_STRATEGIES_JSON)
    result = asyncio.run(
        engine.generate_strategies(
            business_context={}, audience_context={}, competitor_context={},
            budget="₹50,000", goal="growth",
        )
    )
    for s in result:
        assert s.name
        assert s.approach
        assert s.why_it_works
        assert isinstance(s.risks, list)
        assert s.expected_outcome
        assert s.strategy_type in ("primary", "alternative", "contrarian")


def test_generate_strategies_ai_failure_returns_defaults():
    gw = MagicMock()
    gw.complete.side_effect = RuntimeError("AI down")
    engine = StrategyEngine(gateway=gw, tenant_id=uuid.uuid4(), plan="agency")
    result = asyncio.run(
        engine.generate_strategies(
            business_context={}, audience_context={}, competitor_context={},
            budget="₹50,000", goal="growth",
        )
    )
    assert len(result) == 3
    # Should be the default strategies
    defaults = _default_strategies()
    assert [s.name for s in result] == [d.name for d in defaults]


def test_generate_strategies_budget_exceeded_reraises():
    gw = MagicMock()
    gw.complete.side_effect = BudgetExceeded("over budget")
    engine = StrategyEngine(gateway=gw, tenant_id=uuid.uuid4(), plan="agency")
    with pytest.raises(BudgetExceeded):
        asyncio.run(
            engine.generate_strategies(
                business_context={}, audience_context={}, competitor_context={},
                budget="₹50,000", goal="growth",
            )
        )


def test_generate_strategies_malformed_json_returns_defaults():
    engine = _make_engine("not json at all")
    result = asyncio.run(
        engine.generate_strategies(
            business_context={}, audience_context={}, competitor_context={},
            budget="₹50,000", goal="growth",
        )
    )
    assert len(result) == 3
    # Falls back to defaults since parsing yields nothing usable
    defaults = _default_strategies()
    assert [s.name for s in result] == [d.name for d in defaults]


# ─── StrategyEngine.explain_choice ─────────────────────────────────────────


def test_explain_choice_returns_required_fields():
    engine = _make_engine(GOOD_EXPLANATION_JSON)
    strategies = _default_strategies()
    result = asyncio.run(
        engine.explain_choice(
            strategies=strategies,
            business_context={"name": "Test"},
            audience_context={"age": "25-40"},
            budget="₹50,000",
            goal="growth",
        )
    )
    assert "chosen_strategy" in result
    assert "reasoning" in result
    assert "why_not_alternative" in result
    assert "why_not_contrarian" in result
    assert "key_factors" in result
    assert isinstance(result["key_factors"], list)


def test_explain_choice_uses_primary_name_when_chosen_missing():
    # Explanation JSON has no chosen_strategy field
    engine = _make_engine('{"reasoning": "because", "key_factors": ["budget"]}')
    strategies = _default_strategies()
    primary_name = next(s.name for s in strategies if s.strategy_type == "primary")
    result = asyncio.run(
        engine.explain_choice(
            strategies=strategies,
            business_context={}, audience_context={},
            budget="₹50,000", goal="growth",
        )
    )
    assert result["chosen_strategy"] == primary_name


def test_explain_choice_ai_failure_returns_normalised_empty():
    gw = MagicMock()
    gw.complete.side_effect = RuntimeError("AI down")
    engine = StrategyEngine(gateway=gw, tenant_id=uuid.uuid4(), plan="agency")
    strategies = _default_strategies()
    result = asyncio.run(
        engine.explain_choice(
            strategies=strategies,
            business_context={}, audience_context={},
            budget="₹50,000", goal="growth",
        )
    )
    # Should return normalised dict with empty strings + primary name
    assert "chosen_strategy" in result
    assert "reasoning" in result
    assert result["reasoning"] == ""  # empty on failure
    assert isinstance(result["key_factors"], list)


def test_explain_choice_budget_exceeded_reraises():
    gw = MagicMock()
    gw.complete.side_effect = BudgetExceeded("over budget")
    engine = StrategyEngine(gateway=gw, tenant_id=uuid.uuid4(), plan="agency")
    strategies = _default_strategies()
    with pytest.raises(BudgetExceeded):
        asyncio.run(
            engine.explain_choice(
                strategies=strategies,
                business_context={}, audience_context={},
                budget="₹50,000", goal="growth",
            )
        )


def test_explain_choice_with_past_performance():
    engine = _make_engine(GOOD_EXPLANATION_JSON)
    strategies = _default_strategies()
    past_perf = [
        {"campaign_id": "c1", "roas": 3.2, "ctr": 0.025, "top_performing_hook": "question"},
    ]
    result = asyncio.run(
        engine.explain_choice(
            strategies=strategies,
            business_context={}, audience_context={},
            budget="₹50,000", goal="growth",
            past_performance=past_perf,
        )
    )
    assert "chosen_strategy" in result
    # Verify the gateway was called (past_performance was included in prompt)
    assert engine._gateway.complete.called


def test_explain_choice_key_factors_non_list_becomes_list():
    engine = _make_engine('{"key_factors": "single factor string"}')
    strategies = _default_strategies()
    result = asyncio.run(
        engine.explain_choice(
            strategies=strategies,
            business_context={}, audience_context={},
            budget="₹50,000", goal="growth",
        )
    )
    assert result["key_factors"] == ["single factor string"]


# ─── Prompt builders (smoke tests) ─────────────────────────────────────────


def test_build_strategy_prompt_contains_required_sections():
    engine = _make_engine()
    prompt = engine._build_strategy_prompt(
        business_context={"name": "TestBiz"},
        audience_context={"age": "25-40"},
        competitor_context={"count": 5},
        budget="₹50,000",
        goal="Get more customers",
    )
    assert "PRIMARY" in prompt
    assert "ALTERNATIVE" in prompt
    assert "CONTRARIAN" in prompt
    assert "TestBiz" in prompt
    assert "₹50,000" in prompt
    assert "Get more customers" in prompt


def test_build_explanation_prompt_contains_strategies_and_performance():
    engine = _make_engine()
    strategies = _default_strategies()
    past_perf = [{"campaign_id": "c1", "roas": 3.0}]
    prompt = engine._build_explanation_prompt(
        strategies=strategies,
        business_context={"name": "TestBiz"},
        audience_context={"age": "25-40"},
        budget="₹50,000",
        goal="growth",
        past_performance=past_perf,
    )
    assert "PRIMARY" in prompt
    assert "ALTERNATIVE" in prompt
    assert "CONTRARIAN" in prompt
    assert "PAST CAMPAIGN PERFORMANCE" in prompt
    assert "TestBiz" in prompt


def test_build_explanation_prompt_without_past_performance():
    engine = _make_engine()
    strategies = _default_strategies()
    prompt = engine._build_explanation_prompt(
        strategies=strategies,
        business_context={}, audience_context={},
        budget="₹50,000", goal="growth",
        past_performance=None,
    )
    assert "PAST CAMPAIGN PERFORMANCE" not in prompt
