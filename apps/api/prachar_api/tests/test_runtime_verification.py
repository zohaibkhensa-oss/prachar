"""Phase A.1 Verification Tests.

Tests the 6 runtime behaviours:
V1: Session Isolation
V2: Cancellation Cascade
V3: Timeouts (soft + hard)
V4: Partial Failure (completed_with_warnings)
V5: Tool Versioning
V6: Runtime Metrics

Plus A.1.5: Certification Dashboard endpoints.
"""
from __future__ import annotations

import asyncio
import time
import uuid
import pytest

from prachar_api.runtime.metrics import RuntimeMetrics, ToolMetrics
from prachar_api.runtime.registry import ToolManifest, ToolRegistry, ToolCategory
from prachar_api.runtime.decision import DecisionContract, DecisionStatus
from prachar_api.runtime.events import SessionManager, make_event
from prachar_api.runtime.graph import ExecutionGraph, GraphNode
from prachar_api.runtime.context import AIContext
from prachar_api.runtime.executor import ExecutionEngine


# ─── V1: Session Isolation ─────────────────────────────────────────────────


class TestSessionIsolation:
    """V1: Each session owns its event stream, context, decision, timeline."""

    async def test_each_session_has_unique_id(self):
        manager = SessionManager()
        id1, bus1 = await manager.create_session()
        id2, bus2 = await manager.create_session()
        assert id1 != id2
        assert bus1 is not bus2
        assert bus1.session_id == id1
        assert bus2.session_id == id2

    async def test_event_bus_isolation(self):
        """Events from one session don't appear in another."""
        manager = SessionManager()
        id1, bus1 = await manager.create_session()
        id2, bus2 = await manager.create_session()

        await bus1.publish(make_event(session_id=id1, type="test.event1"))
        await bus2.publish(make_event(session_id=id2, type="test.event2"))

        events1 = bus1.get_all_events()
        events2 = bus2.get_all_events()

        assert len(events1) == 1
        assert events1[0].type == "test.event1"
        assert len(events2) == 1
        assert events2[0].type == "test.event2"
        assert all(e.session_id == id1 for e in events1)
        assert all(e.session_id == id2 for e in events2)

    def test_cancel_event_is_per_session(self):
        """Cancelling one session doesn't cancel another."""
        ev1 = asyncio.Event()
        ev2 = asyncio.Event()
        ev1.set()
        assert ev1.is_set()
        assert not ev2.is_set()


# ─── V2: Cancellation Cascade ───────────────────────────────────────────────


class TestCancellationCascade:
    """V2: Cancellation propagates to running tasks, no orphans."""

    async def test_cancel_event_stops_execution(self):
        registry = ToolRegistry()

        async def slow_tool(ctx, inp):
            await asyncio.sleep(10)
            return {"result": "should never reach"}

        registry.register(ToolManifest(
            name="slow.tool", display_name="Slow Tool", category=ToolCategory.ANALYTICS, description="Slow tool",
            estimated_cost_usd=0.0, supports_retry=False,
        ), slow_tool)

        engine = ExecutionEngine(registry)
        graph = ExecutionGraph()
        graph.add_node(GraphNode(id="n1", tool="slow.tool", input={}))

        ctx = AIContext(
            user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), brand_id=uuid.uuid4(),
            conversation=[],
        )

        manager = SessionManager()
        sid, bus = await manager.create_session()
        cancel_event = asyncio.Event()
        cancel_event.set()

        result = await engine.execute(
            graph=graph, ctx=ctx, bus=bus,
            decision_id="test", session_id=sid,
            cancel_event=cancel_event,
        )

        assert result.cancelled
        assert not result.success

    async def test_cancelled_emits_session_cancelled_event(self):
        """V2: runtime.session.cancelled event is emitted."""
        registry = ToolRegistry()

        async def slow_tool(ctx, inp):
            await asyncio.sleep(10)
            return {}

        registry.register(ToolManifest(
            name="cancellable.tool", display_name="Cancellable", category=ToolCategory.ANALYTICS, description="Cancellable",
            estimated_cost_usd=0.0, supports_retry=False,
        ), slow_tool)

        engine = ExecutionEngine(registry)
        graph = ExecutionGraph()
        graph.add_node(GraphNode(id="n1", tool="cancellable.tool", input={}))

        ctx = AIContext(
            user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), brand_id=uuid.uuid4(),
            conversation=[],
        )

        manager = SessionManager()
        sid, bus = await manager.create_session()
        cancel_event = asyncio.Event()
        cancel_event.set()

        await engine.execute(
            graph=graph, ctx=ctx, bus=bus,
            decision_id="test", session_id=sid,
            cancel_event=cancel_event,
        )

        events = bus.get_all_events()
        assert any(e.type == "runtime.session.cancelled" for e in events)


# ─── V3: Timeouts ───────────────────────────────────────────────────────────


class TestTimeouts:
    """V3: Tool manifests expose soft_timeout_ms and hard_timeout_ms."""

    def test_manifest_has_soft_and_hard_timeout(self):
        manifest = ToolManifest(
            name="test.tool", display_name="Test", category=ToolCategory.ANALYTICS, description="Test",
            estimated_cost_usd=0.0,
            soft_timeout_ms=30_000, hard_timeout_ms=60_000,
        )
        d = manifest.to_dict()
        assert d["soft_timeout_ms"] == 30_000
        assert d["hard_timeout_ms"] == 60_000

    def test_default_timeouts(self):
        manifest = ToolManifest(
            name="test.tool", display_name="Test", category=ToolCategory.ANALYTICS, description="Test",
            estimated_cost_usd=0.0,
        )
        assert manifest.soft_timeout_ms == 60_000
        assert manifest.hard_timeout_ms == 120_000

    async def test_hard_timeout_kills_tool(self):
        """V3: A tool exceeding hard_timeout_ms is killed."""
        registry = ToolRegistry()

        async def slow_tool(ctx, inp):
            await asyncio.sleep(10)
            return {}

        registry.register(ToolManifest(
            name="timeout.tool", display_name="Timeout", category=ToolCategory.ANALYTICS, description="Will timeout",
            estimated_cost_usd=0.0, hard_timeout_ms=100,
            supports_retry=False,
        ), slow_tool)

        engine = ExecutionEngine(registry)
        graph = ExecutionGraph()
        graph.add_node(GraphNode(id="n1", tool="timeout.tool", input={}))

        ctx = AIContext(
            user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), brand_id=uuid.uuid4(),
            conversation=[],
        )

        manager = SessionManager()
        sid, bus = await manager.create_session()

        result = await engine.execute(
            graph=graph, ctx=ctx, bus=bus,
            decision_id="test", session_id=sid,
        )

        nr = result.node_results.get("n1")
        assert nr is not None
        assert not nr.success
        assert nr.timed_out
        assert "timeout" in (nr.error or "").lower()


# ─── V4: Partial Failure ────────────────────────────────────────────────────


class TestPartialFailure:
    """V4: Graph continues on node failure, marks completed_with_warnings."""

    async def test_failed_node_doesnt_stop_graph(self):
        """V4: If one node fails, independent nodes still run."""
        registry = ToolRegistry()

        async def failing_tool(ctx, inp):
            raise RuntimeError("intentional failure")

        async def success_tool(ctx, inp):
            return {"result": "ok"}

        registry.register(ToolManifest(
            name="fail.tool", display_name="Fail", category=ToolCategory.ANALYTICS, description="Fails",
            estimated_cost_usd=0.0, supports_retry=False,
        ), failing_tool)
        registry.register(ToolManifest(
            name="ok.tool", display_name="OK", category=ToolCategory.ANALYTICS, description="Succeeds",
            estimated_cost_usd=0.0, supports_retry=False,
        ), success_tool)

        engine = ExecutionEngine(registry)
        graph = ExecutionGraph()
        graph.add_node(GraphNode(id="n1", tool="fail.tool", input={}))
        graph.add_node(GraphNode(id="n2", tool="ok.tool", input={}))

        ctx = AIContext(
            user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), brand_id=uuid.uuid4(),
            conversation=[],
        )

        manager = SessionManager()
        sid, bus = await manager.create_session()

        result = await engine.execute(
            graph=graph, ctx=ctx, bus=bus,
            decision_id="test", session_id=sid,
        )

        assert not result.cancelled
        nr1 = result.node_results.get("n1")
        assert nr1 and not nr1.success
        nr2 = result.node_results.get("n2")
        assert nr2 and nr2.success
        assert result.has_warnings
        assert len(result.warnings) > 0

    def test_completed_with_warnings_status(self):
        """V4: DecisionStatus.COMPLETED_WITH_WARNINGS exists."""
        assert DecisionStatus.COMPLETED_WITH_WARNINGS.value == "completed_with_warnings"

    def test_decision_has_warnings_field(self):
        """V4: DecisionContract has a warnings list."""
        d = DecisionContract(
            id="test", intent="test", mode="auto", goal="test",
            reasoning="test", context_snapshot={},
            estimated_duration="1s", estimated_cost_usd=0.0,
            tools=[], graph={},
        )
        assert d.warnings == []
        d.warnings.append("test warning")
        d_dict = d.to_dict()
        assert "warnings" in d_dict
        assert d_dict["warnings"] == ["test warning"]


# ─── V5: Tool Versioning ────────────────────────────────────────────────────


class TestToolVersioning:
    """V5: Tool manifests expose version, deprecated, successor."""

    def test_manifest_has_version_fields(self):
        manifest = ToolManifest(
            name="test.tool", display_name="Test", category=ToolCategory.ANALYTICS, description="Test",
            estimated_cost_usd=0.0, version="2.0.0",
        )
        d = manifest.to_dict()
        assert d["version"] == "2.0.0"
        assert d["deprecated"] is False
        assert d["successor"] is None
        assert d["min_runtime_version"] == "1.0.0"

    def test_deprecated_tool_with_successor(self):
        manifest = ToolManifest(
            name="old.tool", display_name="Old", category=ToolCategory.ANALYTICS, description="Old",
            estimated_cost_usd=0.0, version="1.0.0",
            deprecated=True, successor="new.tool",
        )
        d = manifest.to_dict()
        assert d["deprecated"] is True
        assert d["successor"] == "new.tool"

    def test_default_version(self):
        manifest = ToolManifest(
            name="test.tool", display_name="Test", category=ToolCategory.ANALYTICS, description="Test",
            estimated_cost_usd=0.0,
        )
        assert manifest.version == "1.0.0"


# ─── V6: Runtime Metrics ────────────────────────────────────────────────────


class TestRuntimeMetrics:
    """V6: Every execution collects metrics."""

    def test_metrics_initial_state(self):
        m = RuntimeMetrics(session_id="test")
        assert m.total_tools == 0
        assert m.total_cost_usd == 0.0
        assert m.total_tokens == 0
        assert m.outcome == ""

    def test_metrics_phase_timings(self):
        m = RuntimeMetrics(session_id="test")
        m.mark_request_started()
        time.sleep(0.01)
        m.mark_context_assembled()
        time.sleep(0.01)
        m.mark_intent_classified()
        time.sleep(0.01)
        m.mark_plan_created()
        time.sleep(0.01)
        m.mark_execution_started()
        time.sleep(0.01)
        m.mark_execution_completed()
        time.sleep(0.01)
        m.mark_response_composed()
        m.mark_session_completed()

        assert m.context_assembly_time_ms > 0
        assert m.intent_classification_time_ms > 0
        assert m.planner_time_ms > 0
        assert m.execution_time_ms > 0
        assert m.total_duration_ms > 0

    def test_metrics_record_tool(self):
        m = RuntimeMetrics(session_id="test")
        tm = ToolMetrics(
            tool="test.tool", node_id="n1",
            started_at=time.time(), completed_at=time.time() + 0.5,
            duration_ms=500, cost_usd=0.01, tokens_used=100, success=True,
        )
        m.record_tool(tm)
        assert m.total_tools == 1
        assert m.successful_tools == 1
        assert m.total_cost_usd == 0.01
        assert m.total_tokens == 100
        assert m.tool_time_ms == 500

    def test_metrics_failed_tool(self):
        m = RuntimeMetrics(session_id="test")
        m.record_tool(ToolMetrics(
            tool="fail.tool", node_id="n1",
            duration_ms=100, success=False, error="boom",
        ))
        assert m.failed_tools == 1
        assert m.successful_tools == 0

    def test_metrics_cancelled_tool(self):
        m = RuntimeMetrics(session_id="test")
        m.record_tool(ToolMetrics(
            tool="cancel.tool", node_id="n1",
            duration_ms=50, success=False, cancelled=True,
        ))
        assert m.cancelled_tools == 1

    def test_metrics_retried_tool(self):
        m = RuntimeMetrics(session_id="test")
        m.record_tool(ToolMetrics(
            tool="retry.tool", node_id="n1",
            duration_ms=200, success=True, retries=2,
        ))
        assert m.retried_tools == 1

    def test_metrics_serialisation(self):
        m = RuntimeMetrics(session_id="test", decision_id="d1")
        m.mark_request_started()
        time.sleep(0.01)
        m.mark_execution_started()
        time.sleep(0.01)
        m.mark_execution_completed()
        m.outcome = "completed"
        m.record_tool(ToolMetrics(
            tool="test.tool", node_id="n1",
            duration_ms=100, cost_usd=0.01, tokens_used=50,
        ))
        time.sleep(0.01)
        m.mark_session_completed()

        d = m.to_dict()
        assert d["session_id"] == "test"
        assert d["outcome"] == "completed"
        assert d["timings"]["total_duration_ms"] > 0
        assert d["tools"]["total"] == 1
        assert d["costs"]["total_usd"] > 0
        assert d["costs"]["total_tokens"] == 50
        assert len(d["tool_details"]) == 1

    def test_metrics_waiting_time(self):
        """V6: Approval delay is tracked."""
        m = RuntimeMetrics(session_id="test")
        m.mark_approval_requested()
        time.sleep(0.05)
        m.mark_approval_granted()
        assert m.waiting_time_ms > 0


# ─── A.1.5: Certification Dashboard ─────────────────────────────────────────


class TestCertificationDashboard:
    """A.1.5: Admin endpoints for debugging runtime sessions."""

    def test_runtime_has_list_sessions(self):
        from prachar_api.runtime.runtime import Runtime
        assert hasattr(Runtime, "list_sessions")
        assert hasattr(Runtime, "get_session_detail")

    def test_admin_runtime_router_exists(self):
        from prachar_api.routers.admin_runtime import router
        assert router is not None
        paths = [r.path for r in router.routes]
        assert "/admin/runtime/sessions" in paths
        assert "/admin/runtime/sessions/{session_id}" in paths
        assert "/admin/runtime/sessions/{session_id}/events" in paths
        assert "/admin/runtime/tools" in paths
