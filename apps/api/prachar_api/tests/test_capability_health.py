"""Phase E1.2: Capability Health tests.

Tests the health registry, tool health properties, auto-degrade/recover
logic, ToolRegistry health filtering, and ExecutionPlan health_warnings.
"""
from __future__ import annotations

import pytest

from prachar_api.runtime.health import (
    HealthRegistry,
    HealthStatus,
    ToolHealth,
    get_health_registry,
)
from prachar_api.runtime.registry import (
    ToolCategory,
    ToolManifest,
    ToolRegistry,
)
from prachar_api.runtime.planner import ExecutionPlan


# ─── HealthStatus enum ──────────────────────────────────────────────────────


class TestHealthStatus:
    def test_health_status_values(self):
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.OFFLINE.value == "offline"

    def test_health_status_is_str_enum(self):
        assert isinstance(HealthStatus.HEALTHY, str)
        assert HealthStatus.HEALTHY == "healthy"


# ─── ToolHealth properties ──────────────────────────────────────────────────


class TestToolHealth:
    def test_is_available_when_healthy(self):
        h = ToolHealth(tool_name="test.tool", status=HealthStatus.HEALTHY)
        assert h.is_available is True

    def test_is_available_when_degraded(self):
        h = ToolHealth(tool_name="test.tool", status=HealthStatus.DEGRADED)
        assert h.is_available is True

    def test_is_not_available_when_offline(self):
        h = ToolHealth(tool_name="test.tool", status=HealthStatus.OFFLINE)
        assert h.is_available is False

    def test_is_healthy_only_when_healthy(self):
        assert ToolHealth(tool_name="t", status=HealthStatus.HEALTHY).is_healthy is True
        assert ToolHealth(tool_name="t", status=HealthStatus.DEGRADED).is_healthy is False
        assert ToolHealth(tool_name="t", status=HealthStatus.OFFLINE).is_healthy is False

    def test_to_dict(self):
        h = ToolHealth(
            tool_name="test.tool",
            status=HealthStatus.DEGRADED,
            error_count=5,
            success_count=2,
            latency_ms=300,
            message="slow",
        )
        d = h.to_dict()
        assert d["tool_name"] == "test.tool"
        assert d["status"] == "degraded"
        assert d["error_count"] == 5
        assert d["success_count"] == 2
        assert d["latency_ms"] == 300
        assert d["message"] == "slow"

    def test_defaults(self):
        h = ToolHealth(tool_name="new.tool")
        assert h.status == HealthStatus.HEALTHY
        assert h.error_count == 0
        assert h.success_count == 0
        assert h.latency_ms == 0
        assert h.message == ""


# ─── HealthRegistry register/get/update ─────────────────────────────────────


class TestHealthRegistry:
    def test_register_creates_healthy_entry(self):
        reg = HealthRegistry()
        reg.register("my.tool")
        h = reg.get("my.tool")
        assert h.tool_name == "my.tool"
        assert h.status == HealthStatus.HEALTHY

    def test_get_unknown_tool_returns_healthy_default(self):
        reg = HealthRegistry()
        h = reg.get("nonexistent.tool")
        assert h.status == HealthStatus.HEALTHY
        assert h.is_available is True

    def test_update_sets_status_and_message(self):
        reg = HealthRegistry()
        reg.register("my.tool")
        reg.update("my.tool", HealthStatus.DEGRADED, "high latency")
        h = reg.get("my.tool")
        assert h.status == HealthStatus.DEGRADED
        assert h.message == "high latency"
        assert h.last_check != ""

    def test_update_unknown_tool_creates_entry(self):
        reg = HealthRegistry()
        reg.update("new.tool", HealthStatus.OFFLINE, "down")
        h = reg.get("new.tool")
        assert h.status == HealthStatus.OFFLINE
        assert h.message == "down"


# ─── record_success auto-recovery ───────────────────────────────────────────


class TestRecordSuccess:
    def test_record_success_increments_count(self):
        reg = HealthRegistry()
        reg.register("my.tool")
        reg.record_success("my.tool", latency_ms=150)
        h = reg.get("my.tool")
        assert h.success_count == 1
        assert h.latency_ms == 150

    def test_auto_recover_from_degraded(self):
        """After enough successes, a degraded tool becomes healthy."""
        reg = HealthRegistry()
        reg.register("my.tool")
        # Degrade it first
        reg.update("my.tool", HealthStatus.DEGRADED, "slow")
        h = reg.get("my.tool")
        h.error_count = 2  # simulate 2 prior errors
        # Need success_count > error_count * 3, i.e. > 6
        for _ in range(7):
            reg.record_success("my.tool")
        h = reg.get("my.tool")
        assert h.status == HealthStatus.HEALTHY
        assert h.message == ""

    def test_no_recover_if_not_enough_successes(self):
        reg = HealthRegistry()
        reg.register("my.tool")
        reg.update("my.tool", HealthStatus.DEGRADED, "slow")
        h = reg.get("my.tool")
        h.error_count = 2
        reg.record_success("my.tool")  # success_count=1, need > 6
        h = reg.get("my.tool")
        assert h.status == HealthStatus.DEGRADED


# ─── record_error auto-degrade and auto-offline ─────────────────────────────


class TestRecordError:
    def test_auto_degrade_after_3_errors(self):
        reg = HealthRegistry()
        reg.register("my.tool")
        for i in range(3):
            reg.record_error("my.tool", f"error {i}")
        h = reg.get("my.tool")
        assert h.status == HealthStatus.DEGRADED
        assert h.error_count == 3

    def test_no_degrade_before_3_errors(self):
        reg = HealthRegistry()
        reg.register("my.tool")
        reg.record_error("my.tool", "error 1")
        reg.record_error("my.tool", "error 2")
        h = reg.get("my.tool")
        assert h.status == HealthStatus.HEALTHY

    def test_auto_offline_after_10_errors(self):
        reg = HealthRegistry()
        reg.register("my.tool")
        for i in range(10):
            reg.record_error("my.tool", f"error {i}")
        h = reg.get("my.tool")
        assert h.status == HealthStatus.OFFLINE
        assert h.error_count == 10

    def test_record_error_increments_count(self):
        reg = HealthRegistry()
        reg.register("my.tool")
        reg.record_error("my.tool", "boom")
        h = reg.get("my.tool")
        assert h.error_count == 1
        assert h.message == "boom"


# ─── get_available_tools / get_healthy_tools ─────────────────────────────────


class TestHealthFiltering:
    def test_get_available_tools_excludes_offline(self):
        reg = HealthRegistry()
        reg.register("healthy.tool")
        reg.register("degraded.tool")
        reg.register("offline.tool")
        reg.update("degraded.tool", HealthStatus.DEGRADED)
        reg.update("offline.tool", HealthStatus.OFFLINE)
        available = reg.get_available_tools()
        assert "healthy.tool" in available
        assert "degraded.tool" in available
        assert "offline.tool" not in available

    def test_get_healthy_tools_excludes_degraded_and_offline(self):
        reg = HealthRegistry()
        reg.register("healthy.tool")
        reg.register("degraded.tool")
        reg.register("offline.tool")
        reg.update("degraded.tool", HealthStatus.DEGRADED)
        reg.update("offline.tool", HealthStatus.OFFLINE)
        healthy = reg.get_healthy_tools()
        assert "healthy.tool" in healthy
        assert "degraded.tool" not in healthy
        assert "offline.tool" not in healthy

    def test_list_all_returns_all(self):
        reg = HealthRegistry()
        reg.register("a.tool")
        reg.register("b.tool")
        all_health = reg.list_all()
        assert len(all_health) == 2
        names = {h.tool_name for h in all_health}
        assert names == {"a.tool", "b.tool"}


# ─── ToolRegistry health integration ────────────────────────────────────────


def _make_manifest(name: str) -> ToolManifest:
    return ToolManifest(
        name=name,
        display_name=name,
        description="Test tool",
        category=ToolCategory.ANALYTICS,
        estimated_cost_usd=0.0,
    )


class TestToolRegistryHealth:
    def test_list_healthy_filters_by_health(self):
        """ToolRegistry.list_healthy() only returns healthy tools."""
        registry = ToolRegistry()
        health = HealthRegistry()

        async def dummy(ctx, inp):
            return {}

        # Register tools
        for name in ["good.tool", "bad.tool", "down.tool"]:
            manifest = _make_manifest(name)
            registry._tools[name] = type(
                "E", (), {"manifest": manifest, "func": dummy}
            )()
            health.register(name)

        # Mark bad.tool as degraded, down.tool as offline
        health.update("bad.tool", HealthStatus.DEGRADED)
        health.update("down.tool", HealthStatus.OFFLINE)

        # Monkey-patch the registry's health lookup to use our local registry
        import prachar_api.runtime.health as health_mod
        original = health_mod.get_health_registry
        health_mod.get_health_registry = lambda: health
        try:
            healthy = registry.list_healthy()
            healthy_names = {m.name for m in healthy}
            assert "good.tool" in healthy_names
            assert "bad.tool" not in healthy_names
            assert "down.tool" not in healthy_names
        finally:
            health_mod.get_health_registry = original

    def test_list_for_prompt_only_healthy_excludes_degraded(self):
        """list_for_prompt(only_healthy=True) excludes degraded and offline."""
        registry = ToolRegistry()
        health = HealthRegistry()

        async def dummy(ctx, inp):
            return {}

        for name in ["good.tool", "slow.tool", "dead.tool"]:
            manifest = _make_manifest(name)
            registry._tools[name] = type(
                "E", (), {"manifest": manifest, "func": dummy}
            )()
            health.register(name)

        health.update("slow.tool", HealthStatus.DEGRADED)
        health.update("dead.tool", HealthStatus.OFFLINE)

        import prachar_api.runtime.health as health_mod
        original = health_mod.get_health_registry
        health_mod.get_health_registry = lambda: health
        try:
            prompt = registry.list_for_prompt(only_healthy=True)
            assert "good.tool" in prompt
            assert "slow.tool" not in prompt
            assert "dead.tool" not in prompt
        finally:
            health_mod.get_health_registry = original

    def test_list_for_prompt_default_includes_all(self):
        """list_for_prompt() without filter includes all tools."""
        registry = ToolRegistry()
        health = HealthRegistry()

        async def dummy(ctx, inp):
            return {}

        for name in ["good.tool", "slow.tool"]:
            manifest = _make_manifest(name)
            registry._tools[name] = type(
                "E", (), {"manifest": manifest, "func": dummy}
            )()
            health.register(name)

        health.update("slow.tool", HealthStatus.DEGRADED)

        import prachar_api.runtime.health as health_mod
        original = health_mod.get_health_registry
        health_mod.get_health_registry = lambda: health
        try:
            prompt = registry.list_for_prompt()
            assert "good.tool" in prompt
            assert "slow.tool" in prompt
        finally:
            health_mod.get_health_registry = original


# ─── ExecutionPlan health_warnings ──────────────────────────────────────────


class TestExecutionPlanHealthWarnings:
    def test_health_warnings_default_empty(self):
        plan = ExecutionPlan()
        assert plan.health_warnings == []

    def test_health_warnings_can_be_set(self):
        plan = ExecutionPlan(
            health_warnings=["tool 'publish' is offline", "tool 'analyse' is degraded"],
        )
        assert len(plan.health_warnings) == 2
        assert "offline" in plan.health_warnings[0]


# ─── Singleton ──────────────────────────────────────────────────────────────


class TestHealthRegistrySingleton:
    def test_get_health_registry_returns_singleton(self):
        reg1 = get_health_registry()
        reg2 = get_health_registry()
        assert reg1 is reg2
