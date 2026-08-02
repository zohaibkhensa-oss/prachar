"""Tests for Cost-Aware Planning (Phase E2.2).

Verifies that ToolManifest exposes estimated_latency_ms, quality_score, and a
cost_efficiency property; that the Planner prompt includes cost/latency/quality;
that the Planner can select the best tool by preference; and that
ExecutionPlan / DecisionContract carry a cost_breakdown.
"""
from __future__ import annotations

import pytest

from prachar_api.runtime.registry import (
    SideEffects,
    ToolCategory,
    ToolManifest,
    ToolRegistry,
)
from prachar_api.runtime.planner import ExecutionPlan, Planner
from prachar_api.runtime.decision import DecisionContract


# ─── helpers ────────────────────────────────────────────────────────────────


def _manifest(
    name: str,
    cost: float = 0.05,
    latency: int = 5000,
    quality: float = 0.8,
) -> ToolManifest:
    return ToolManifest(
        name=name,
        display_name=name,
        description=f"{name} tool",
        category=ToolCategory.CAMPAIGN,
        estimated_cost_usd=cost,
        estimated_latency_ms=latency,
        quality_score=quality,
        side_effects=SideEffects.READS,
    )


def _registry_with(*manifests: ToolManifest) -> ToolRegistry:
    reg = ToolRegistry()

    async def _noop(ctx, input):  # pragma: no cover - never called in tests
        return {}

    for m in manifests:
        reg.register(m, _noop)
    return reg


# ─── ToolManifest fields ────────────────────────────────────────────────────


class TestToolManifestFields:
    def test_has_estimated_latency_ms(self):
        m = _manifest("t.a", latency=3000)
        assert m.estimated_latency_ms == 3000

    def test_has_quality_score(self):
        m = _manifest("t.a", quality=0.92)
        assert m.quality_score == 0.92

    def test_defaults(self):
        m = ToolManifest(
            name="t.default",
            display_name="d",
            description="desc",
            category=ToolCategory.CONVERSATION,
        )
        assert m.estimated_latency_ms == 5000
        assert m.quality_score == 0.8

    def test_cost_efficiency_calculation(self):
        m = _manifest("t.a", cost=0.1, quality=0.9)
        # quality / cost = 0.9 / 0.1 = 9.0
        assert m.cost_efficiency == pytest.approx(9.0)

    def test_cost_efficiency_zero_cost_guarded(self):
        m = _manifest("t.a", cost=0.0, quality=0.8)
        # cost clamped to 0.001 -> 0.8 / 0.001 = 800.0
        assert m.cost_efficiency == pytest.approx(800.0)

    def test_to_dict_includes_new_fields(self):
        m = _manifest("t.a", cost=0.05, latency=4000, quality=0.85)
        d = m.to_dict()
        assert d["estimated_latency_ms"] == 4000
        assert d["quality_score"] == 0.85
        assert "cost_efficiency" in d
        assert d["cost_efficiency"] == pytest.approx(0.85 / 0.05)


# ─── Planner _select_best_tool ──────────────────────────────────────────────


class TestSelectBestTool:
    def _setup(self) -> ToolRegistry:
        return _registry_with(
            _manifest("t.cheap_slow_low", cost=0.01, latency=20000, quality=0.5),
            _manifest("t.expensive_fast_high", cost=0.20, latency=1000, quality=0.95),
            _manifest("t.mid", cost=0.05, latency=5000, quality=0.8),
        )

    def _planner(self, reg: ToolRegistry) -> Planner:
        # AIGateway is only used for LLM calls; _select_best_tool never calls it.
        return Planner(gateway=None, registry=reg)  # type: ignore[arg-type]

    def test_balanced_prefers_best_cost_efficiency(self):
        reg = self._setup()
        planner = self._planner(reg)
        # efficiencies: 0.5/0.01=50, 0.95/0.20=4.75, 0.8/0.05=16 -> cheap wins
        assert planner._select_best_tool(
            ["t.cheap_slow_low", "t.expensive_fast_high", "t.mid"], "balanced"
        ) == "t.cheap_slow_low"

    def test_speed_prefers_lowest_latency(self):
        reg = self._setup()
        planner = self._planner(reg)
        assert planner._select_best_tool(
            ["t.cheap_slow_low", "t.expensive_fast_high", "t.mid"], "speed"
        ) == "t.expensive_fast_high"

    def test_quality_prefers_highest_quality(self):
        reg = self._setup()
        planner = self._planner(reg)
        assert planner._select_best_tool(
            ["t.cheap_slow_low", "t.expensive_fast_high", "t.mid"], "quality"
        ) == "t.expensive_fast_high"

    def test_cost_prefers_lowest_cost(self):
        reg = self._setup()
        planner = self._planner(reg)
        assert planner._select_best_tool(
            ["t.cheap_slow_low", "t.expensive_fast_high", "t.mid"], "cost"
        ) == "t.cheap_slow_low"

    def test_default_preference_is_balanced(self):
        reg = self._setup()
        planner = self._planner(reg)
        assert planner._select_best_tool(
            ["t.cheap_slow_low", "t.expensive_fast_high", "t.mid"]
        ) == "t.cheap_slow_low"

    def test_unknown_candidates_fallback(self):
        reg = self._setup()
        planner = self._planner(reg)
        # No manifests found -> returns first candidate
        assert planner._select_best_tool(["nope.a", "nope.b"]) == "nope.a"


# ─── list_for_prompt includes cost/latency/quality ──────────────────────────


class TestListForPrompt:
    def test_includes_cost_latency_quality(self):
        reg = _registry_with(
            _manifest("t.alpha", cost=0.05, latency=3000, quality=0.9),
        )
        text = reg.list_for_prompt()
        assert "t.alpha" in text
        assert "cost:" in text
        assert "latency:" in text
        assert "quality:" in text
        assert "$0.05" in text
        assert "3s" in text
        assert "0.90" in text


# ─── ExecutionPlan cost_breakdown ───────────────────────────────────────────


class TestExecutionPlanCostBreakdown:
    def test_has_cost_breakdown_field(self):
        plan = ExecutionPlan()
        assert hasattr(plan, "cost_breakdown")
        assert plan.cost_breakdown == []

    def test_cost_breakdown_defaults_to_empty_list(self):
        plan = ExecutionPlan()
        assert isinstance(plan.cost_breakdown, list)
        assert len(plan.cost_breakdown) == 0


# ─── DecisionContract cost_breakdown ────────────────────────────────────────


class TestDecisionContractCostBreakdown:
    def test_has_cost_breakdown_field(self):
        contract = DecisionContract()
        assert hasattr(contract, "cost_breakdown")
        assert contract.cost_breakdown == []

    def test_to_dict_includes_cost_breakdown(self):
        contract = DecisionContract(
            cost_breakdown=[{"tool": "t.a", "cost": 0.05, "latency": 3000, "quality": 0.9}],
        )
        d = contract.to_dict()
        assert "cost_breakdown" in d
        assert d["cost_breakdown"] == [
            {"tool": "t.a", "cost": 0.05, "latency": 3000, "quality": 0.9}
        ]

    def test_create_accepts_cost_breakdown(self):
        # Build a minimal fake context with a to_snapshot method.
        class _FakeCtx:
            def to_snapshot(self):
                return {}

        contract = DecisionContract.create(
            session_id="s1",
            goal="g",
            reasoning="r",
            intent="i",
            mode="m",
            tools=["t.a"],
            graph={},
            risk_level="low",
            requires_approval=False,
            approval_reason=None,
            estimated_duration="—",
            estimated_cost_usd=0.05,
            expected_outputs=[],
            context=_FakeCtx(),
            cost_breakdown=[{"tool": "t.a", "cost": 0.05, "latency": 3000, "quality": 0.9}],
        )
        assert contract.cost_breakdown == [
            {"tool": "t.a", "cost": 0.05, "latency": 3000, "quality": 0.9}
        ]
