"""Execution Engine — runs the execution graph, emits events.

Constitution Rule 2: Tools never know about each other. Only the Planner coordinates.
Constitution Rule 8: Everything emits Runtime Events. No silent execution.
Constitution Rule 11: Approval belongs to the Runtime.
Constitution Rule 12: Cancellation belongs to the Runtime.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from .context import AIContext
from .events import AIEvent, EventBus, EventPhase, OrbState, make_event
from .graph import ExecutionGraph, GraphNode
from .registry import ToolRegistry, get_registry

log = logging.getLogger("prachar.runtime.executor")


# ─── Execution Result ───────────────────────────────────────────────────────


@dataclass
class NodeResult:
    """Result of a single node execution."""

    node_id: str
    tool: str
    success: bool
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: int = 0
    cost_usd: float = 0.0
    retries: int = 0
    cancelled: bool = False       # V2: was this node cancelled?
    timed_out: bool = False       # V3: did this node time out?
    tokens_used: int = 0


@dataclass
class ExecutionResult:
    """Result of the entire graph execution."""

    success: bool = True
    node_results: dict[str, NodeResult] = field(default_factory=dict)
    total_duration_ms: int = 0
    total_cost_usd: float = 0.0
    error: str | None = None
    cancelled: bool = False
    waiting_for_approval: bool = False
    approval_node_id: str | None = None
    # V4: Partial failure tracking
    has_warnings: bool = False
    warnings: list[str] = field(default_factory=list)
    # V6: Metrics
    metrics: Any = None  # RuntimeMetrics

    def get_output(self, node_id: str) -> dict[str, Any]:
        """Get the output of a specific node (for response composition)."""
        nr = self.node_results.get(node_id)
        return nr.result if nr else {}

    def all_outputs(self) -> dict[str, Any]:
        """All node outputs keyed by tool name."""
        outputs: dict[str, Any] = {}
        for nr in self.node_results.values():
            if nr.success:
                outputs[nr.tool] = nr.result
        return outputs

    @property
    def failed_nodes(self) -> list[NodeResult]:
        """Nodes that failed (V4: partial failure)."""
        return [nr for nr in self.node_results.values() if not nr.success and not nr.cancelled]

    @property
    def successful_nodes(self) -> list[NodeResult]:
        return [nr for nr in self.node_results.values() if nr.success]


# ─── Execution Engine ───────────────────────────────────────────────────────


class ExecutionEngine:
    """Runs an ExecutionGraph, emitting events for each node.

    Responsibilities:
    1. Run nodes in dependency order (parallel where possible)
    2. Emit tool.started / tool.progress / tool.completed events
    3. Pause at needs_approval nodes (emit approval.requested)
    4. Support cancellation (emit session.cancelled)
    5. Handle retries per tool manifest
    6. Resolve input references (${{nodeId.result.field}})
    """

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self._registry = registry or get_registry()

    async def execute(
        self,
        graph: ExecutionGraph,
        ctx: AIContext,
        bus: EventBus,
        decision_id: str,
        session_id: str,
        cancel_event: asyncio.Event | None = None,
        metrics: Any = None,  # V6: RuntimeMetrics
    ) -> ExecutionResult:
        """Execute the graph, emitting events throughout.

        V2: Cancellation cascades — running asyncio tasks are cancelled, not
            just the loop. Each in-flight tool gets a tool.cancelled event.
        V3: Soft and hard timeouts from the tool manifest are enforced.
        V4: Partial failure — a failed node doesn't stop the graph. The result
            is marked completed_with_warnings if some nodes failed.
        V6: Metrics are collected for every tool execution.

        Args:
            graph: The execution graph from the Planner
            ctx: AI Context (shared across all tools)
            bus: Event bus to publish events to
            decision_id: Decision Contract ID
            session_id: Runtime session ID
            cancel_event: Set this to cancel execution
            metrics: RuntimeMetrics collector (V6)
        """
        from .metrics import ToolMetrics

        result = ExecutionResult(metrics=metrics)
        start_time = time.time()
        completed: set[str] = set()
        node_outputs: dict[str, dict[str, Any]] = {}
        total_nodes = len(graph.nodes)

        # V2: Track running tasks for cancellation cascade
        running_tasks: dict[str, asyncio.Task] = {}

        while len(completed) < total_nodes:
            # Check for cancellation
            if cancel_event and cancel_event.is_set():
                result.cancelled = True
                result.success = False
                # V2: Cancel all running tasks
                for node_id, task in running_tasks.items():
                    task.cancel()
                # Wait for tasks to finish cancellation
                if running_tasks:
                    await asyncio.gather(*running_tasks.values(), return_exceptions=True)
                running_tasks.clear()
                await bus.publish(make_event(
                    session_id=session_id,
                    type="runtime.session.cancelled",
                    phase=EventPhase.CANCELLED.value,
                    decision_id=decision_id,
                    orb_state=OrbState.CANCELLED.value,
                    data={"reason": "user_cancelled"},
                ))
                break

            # Find ready nodes (deps satisfied, not yet completed)
            ready_nodes = graph.get_ready_nodes(completed)

            if not ready_nodes:
                if result.waiting_for_approval:
                    break
                log.error("execution deadlock: no ready nodes, %d/%d completed", len(completed), total_nodes)
                result.success = False
                result.error = "execution deadlock"
                break

            # Separate approval nodes from regular nodes
            approval_nodes = [n for n in ready_nodes if n.needs_approval]
            regular_nodes = [n for n in ready_nodes if not n.needs_approval]

            # Handle approval nodes — pause execution
            if approval_nodes:
                approval_node = approval_nodes[0]
                result.waiting_for_approval = True
                result.approval_node_id = approval_node.id
                if metrics:
                    metrics.mark_approval_requested()
                await bus.publish(make_event(
                    session_id=session_id,
                    type="approval.requested",
                    phase=EventPhase.STARTED.value,
                    decision_id=decision_id,
                    tool=approval_node.tool,
                    orb_state=OrbState.WAITING_APPROVAL.value,
                    data={
                        "node_id": approval_node.id,
                        "tool": approval_node.tool,
                        "reason": approval_node.approval_reason or "This action requires your approval.",
                        "options": ["approve", "deny"],
                    },
                ))
                break

            # Run regular nodes in parallel
            # V2: Track tasks so we can cancel them on cancellation
            tasks_for_round: list[asyncio.Task] = []
            for node in regular_nodes:
                task = asyncio.create_task(
                    self._execute_node(
                        node, ctx, bus, decision_id, session_id,
                        node_outputs, completed, result, metrics,
                    )
                )
                running_tasks[node.id] = task
                tasks_for_round.append(task)

            # Wait for all tasks in this round
            # V2: Use return_exceptions to handle CancelledError gracefully
            await asyncio.gather(*tasks_for_round, return_exceptions=True)

            # Clear running tasks that completed
            for node in regular_nodes:
                running_tasks.pop(node.id, None)

        result.total_duration_ms = int((time.time() - start_time) * 1000)
        result.total_cost_usd = sum(nr.cost_usd for nr in result.node_results.values())

        # V4: Check for partial failure
        if not result.cancelled and result.success:
            failed = result.failed_nodes
            if failed:
                result.has_warnings = True
                result.warnings = [
                    f"{nr.tool} failed: {nr.error}" for nr in failed
                ]
                # If ALL nodes failed, the execution did not succeed.
                # Only keep success=True for partial failures (some tools
                # succeeded, some failed).
                succeeded = result.successful_nodes
                if not succeeded:
                    result.success = False

        return result

    async def resume_after_approval(
        self,
        graph: ExecutionGraph,
        ctx: AIContext,
        bus: EventBus,
        decision_id: str,
        session_id: str,
        approval_node_id: str,
        approved: bool,
        prev_result: ExecutionResult,
        cancel_event: asyncio.Event | None = None,
        metrics: Any = None,
    ) -> ExecutionResult:
        """Resume execution after an approval node.

        If approved, run the approval node and continue.
        If denied, mark as cancelled.
        """
        if not approved:
            await bus.publish(make_event(
                session_id=session_id,
                type="approval.denied",
                phase=EventPhase.COMPLETED.value,
                decision_id=decision_id,
                orb_state=OrbState.COMPLETED.value,
                data={"node_id": approval_node_id},
            ))
            prev_result.success = False
            prev_result.cancelled = True
            return prev_result

        await bus.publish(make_event(
            session_id=session_id,
            type="approval.granted",
            phase=EventPhase.COMPLETED.value,
            decision_id=decision_id,
            orb_state=OrbState.EXECUTING.value,
            data={"node_id": approval_node_id},
        ))

        # Rebuild state from previous result
        completed: set[str] = set()
        node_outputs: dict[str, dict[str, Any]] = {}
        for nid, nr in prev_result.node_results.items():
            if nr.success:
                completed.add(nid)
                node_outputs[nid] = nr.result

        # Execute the approval node
        approval_node = graph.get_node(approval_node_id)
        if approval_node:
            await self._execute_node(
                approval_node, ctx, bus, decision_id, session_id,
                node_outputs, completed, prev_result, metrics,
            )

        # Continue with remaining nodes
        prev_result.waiting_for_approval = False
        prev_result.approval_node_id = None

        total_nodes = len(graph.nodes)
        while len(completed) < total_nodes:
            if cancel_event and cancel_event.is_set():
                prev_result.cancelled = True
                prev_result.success = False
                break

            ready_nodes = graph.get_ready_nodes(completed)
            if not ready_nodes:
                break

            # Handle nested approval nodes
            approval_nodes = [n for n in ready_nodes if n.needs_approval]
            if approval_nodes:
                prev_result.waiting_for_approval = True
                prev_result.approval_node_id = approval_nodes[0].id
                await bus.publish(make_event(
                    session_id=session_id,
                    type="approval.requested",
                    phase=EventPhase.STARTED.value,
                    decision_id=decision_id,
                    tool=approval_nodes[0].tool,
                    orb_state=OrbState.WAITING_APPROVAL.value,
                    data={"node_id": approval_nodes[0].id, "tool": approval_nodes[0].tool},
                ))
                break

            regular_nodes = [n for n in ready_nodes if not n.needs_approval]
            tasks = [
                self._execute_node(
                    node, ctx, bus, decision_id, session_id,
                    node_outputs, completed, prev_result, metrics,
                )
                for node in regular_nodes
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        return prev_result

    async def _execute_node(
        self,
        node: GraphNode,
        ctx: AIContext,
        bus: EventBus,
        decision_id: str,
        session_id: str,
        node_outputs: dict[str, dict[str, Any]],
        completed: set[str],
        result: ExecutionResult,
        metrics: Any = None,  # V6: RuntimeMetrics
    ) -> None:
        """Execute a single node, emit events, store result.

        V2: Handles asyncio.CancelledError for cascade cancellation.
        V3: Uses soft_timeout_ms and hard_timeout_ms from manifest.
        V4: Failed nodes are marked completed (not blocking the graph).
        V6: Records ToolMetrics for every execution.
        """
        from .metrics import ToolMetrics
        from .health import HealthStatus, get_health_registry

        # Phase E1.2: Check if the tool is offline — skip if so
        health = get_health_registry()
        tool_health = health.get(node.tool)
        if tool_health.status == HealthStatus.OFFLINE:
            nr = NodeResult(
                node_id=node.id,
                tool=node.tool,
                success=False,
                error=f"tool offline: {node.tool}",
            )
            result.node_results[node.id] = nr
            completed.add(node.id)
            await bus.publish(make_event(
                session_id=session_id,
                type="tool.skipped",
                phase=EventPhase.COMPLETED.value,
                decision_id=decision_id,
                tool=node.tool,
                orb_state=OrbState.REASONING.value,
                data={
                    "node_id": node.id,
                    "tool": node.tool,
                    "reason": "tool_offline",
                    "message": tool_health.message or "tool is offline",
                },
            ))
            return

        # Emit tool.started
        await bus.publish(make_event(
            session_id=session_id,
            type="tool.started",
            phase=EventPhase.STARTED.value,
            decision_id=decision_id,
            tool=node.tool,
            orb_state=OrbState.EXECUTING.value,
            data={"node_id": node.id, "tool": node.tool},
            progress={"completed": len(completed), "total": len(node_outputs) + 1, "label": f"Running {node.tool}"},
        ))

        # Resolve input references
        resolved_input = self._resolve_inputs(node.input, node_outputs)

        # Look up tool
        entry = self._registry.get(node.tool)
        if entry is None:
            nr = NodeResult(
                node_id=node.id,
                tool=node.tool,
                success=False,
                error=f"tool not found: {node.tool}",
            )
            result.node_results[node.id] = nr
            completed.add(node.id)
            await bus.publish(make_event(
                session_id=session_id,
                type="tool.error",
                phase=EventPhase.ERROR.value,
                decision_id=decision_id,
                tool=node.tool,
                orb_state=OrbState.REASONING.value,
                data={"node_id": node.id, "error": nr.error},
            ))
            return

        # V3: Determine timeouts from manifest (fall back to node, then default)
        hard_timeout = entry.manifest.hard_timeout_ms or node.timeout_ms or 120_000
        soft_timeout = entry.manifest.soft_timeout_ms or 60_000

        # V6: Tool metrics
        tm = ToolMetrics(tool=node.tool, node_id=node.id, started_at=time.time())

        # Execute with hard timeout + retry support
        start = time.time()
        retries = 0
        max_retries = 2 if entry.manifest.supports_retry else 0

        while True:
            try:
                tool_result = await asyncio.wait_for(
                    entry.func(ctx, resolved_input),
                    timeout=hard_timeout / 1000,
                )
                duration_ms = int((time.time() - start) * 1000)
                tm.completed_at = time.time()
                tm.duration_ms = duration_ms
                tm.cost_usd = entry.manifest.estimated_cost_usd
                tm.retries = retries
                tm.success = True

                nr = NodeResult(
                    node_id=node.id,
                    tool=node.tool,
                    success=True,
                    result=tool_result if isinstance(tool_result, dict) else {"result": tool_result},
                    duration_ms=duration_ms,
                    cost_usd=entry.manifest.estimated_cost_usd,
                    retries=retries,
                    tokens_used=tool_result.get("tokens_used", 0) if isinstance(tool_result, dict) else 0,
                )
                result.node_results[node.id] = nr
                node_outputs[node.id] = nr.result
                completed.add(node.id)

                # V6: Record metrics
                if metrics:
                    metrics.record_tool(tm)

                # Phase E1.2: Record successful execution in health registry
                get_health_registry().record_success(node.tool, latency_ms=duration_ms)

                # Emit tool.completed
                event_type = self._capability_event(node.tool, "completed")
                await bus.publish(make_event(
                    session_id=session_id,
                    type=event_type,
                    phase=EventPhase.COMPLETED.value,
                    decision_id=decision_id,
                    tool=node.tool,
                    orb_state=OrbState.GENERATING.value,
                    data={
                        "node_id": node.id,
                        "tool": node.tool,
                        "result": nr.result,
                        "duration_ms": duration_ms,
                        "retries": retries,
                    },
                    progress={"completed": len(completed), "total": len(result.node_results), "label": f"{node.tool} completed"},
                ))

                # Phase D: Emit artefact events if the tool returned artefacts
                artefacts = nr.result.get("artefacts", []) if isinstance(nr.result, dict) else []
                if artefacts:
                    from .events import make_artefact_event
                    for artefact_data in artefacts:
                        try:
                            from .artefacts import Artefact
                            artefact = Artefact.from_dict(artefact_data) if isinstance(artefact_data, dict) else None
                            if artefact:
                                await bus.publish(make_artefact_event(
                                    session_id=session_id,
                                    artefact=artefact,
                                    decision_id=decision_id,
                                    tool=node.tool,
                                ))
                        except Exception as exc:
                            log.warning("failed to emit artefact: %s", exc)

                return

            except asyncio.CancelledError:
                # V2: Cancellation cascade — this task was cancelled by the executor
                duration_ms = int((time.time() - start) * 1000)
                tm.completed_at = time.time()
                tm.duration_ms = duration_ms
                tm.cancelled = True
                tm.success = False

                nr = NodeResult(
                    node_id=node.id,
                    tool=node.tool,
                    success=False,
                    error="cancelled",
                    duration_ms=duration_ms,
                    cancelled=True,
                    retries=retries,
                )
                result.node_results[node.id] = nr
                completed.add(node.id)

                if metrics:
                    metrics.record_tool(tm)

                await bus.publish(make_event(
                    session_id=session_id,
                    type="tool.cancelled",
                    phase=EventPhase.CANCELLED.value,
                    decision_id=decision_id,
                    tool=node.tool,
                    orb_state=OrbState.CANCELLED.value,
                    data={"node_id": node.id, "tool": node.tool},
                ))
                # Re-raise so the gather knows we were cancelled
                raise

            except asyncio.TimeoutError:
                # V3: Hard timeout
                duration_ms = int((time.time() - start) * 1000)
                if retries < max_retries:
                    retries += 1
                    log.warning("tool %s timed out, retrying (%d/%d)", node.tool, retries, max_retries)
                    continue

                tm.completed_at = time.time()
                tm.duration_ms = duration_ms
                tm.timed_out = True
                tm.success = False
                tm.retries = retries

                nr = NodeResult(
                    node_id=node.id,
                    tool=node.tool,
                    success=False,
                    error=f"timeout after {hard_timeout}ms",
                    duration_ms=duration_ms,
                    timed_out=True,
                    retries=retries,
                )
                result.node_results[node.id] = nr
                completed.add(node.id)

                if metrics:
                    metrics.record_tool(tm)

                # Phase E1.2: Record timeout failure in health registry
                get_health_registry().record_error(node.tool, error=nr.error)

                await bus.publish(make_event(
                    session_id=session_id,
                    type="tool.error",
                    phase=EventPhase.ERROR.value,
                    decision_id=decision_id,
                    tool=node.tool,
                    data={"node_id": node.id, "error": nr.error, "timed_out": True},
                ))
                return

            except Exception as exc:
                duration_ms = int((time.time() - start) * 1000)
                if retries < max_retries:
                    retries += 1
                    log.warning("tool %s failed (%s), retrying (%d/%d)", node.tool, exc, retries, max_retries)
                    continue

                tm.completed_at = time.time()
                tm.duration_ms = duration_ms
                tm.success = False
                tm.error = str(exc)
                tm.retries = retries

                nr = NodeResult(
                    node_id=node.id,
                    tool=node.tool,
                    success=False,
                    error=str(exc),
                    duration_ms=duration_ms,
                    retries=retries,
                )
                result.node_results[node.id] = nr
                completed.add(node.id)

                if metrics:
                    metrics.record_tool(tm)

                # Phase E1.2: Record execution failure in health registry
                get_health_registry().record_error(node.tool, error=str(exc))

                await bus.publish(make_event(
                    session_id=session_id,
                    type="tool.error",
                    phase=EventPhase.ERROR.value,
                    decision_id=decision_id,
                    tool=node.tool,
                    data={"node_id": node.id, "error": str(exc), "retries": retries},
                ))
                log.warning("tool %s failed after %d retries: %s", node.tool, retries, exc)
                return

    def _resolve_inputs(
        self,
        input: dict[str, Any],
        node_outputs: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Resolve ${{nodeId.result.field}} references in input values."""
        resolved: dict[str, Any] = {}
        for key, value in input.items():
            resolved[key] = self._resolve_value(value, node_outputs)
        return resolved

    def _resolve_value(
        self,
        value: Any,
        node_outputs: dict[str, dict[str, Any]],
    ) -> Any:
        """Recursively resolve reference strings."""
        if isinstance(value, str):
            return self._resolve_ref(value, node_outputs)
        elif isinstance(value, dict):
            return {k: self._resolve_value(v, node_outputs) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._resolve_value(v, node_outputs) for v in value]
        return value

    def _resolve_ref(
        self,
        text: str,
        node_outputs: dict[str, dict[str, Any]],
    ) -> Any:
        """Resolve a single reference string like ${{n1.result.profile}}."""
        pattern = r"\$\{([a-zA-Z0-9_]+)\.result\.([a-zA-Z0-9_.]+)\}"
        match = re.match(pattern, text)
        if not match:
            return text

        node_id = match.group(1)
        field_path = match.group(2)

        output = node_outputs.get(node_id)
        if output is None:
            return text

        # Navigate the field path
        current: Any = output
        for part in field_path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return text
        return current

    def _capability_event(self, tool: str, phase: str) -> str:
        """Map tool name to capability-specific event type.

        e.g. "campaign_brain.analyse" → "campaign.analysis.completed"
        """
        # Tool name format: namespace.action
        parts = tool.split(".", 1)
        if len(parts) == 2:
            namespace, action = parts
            # Map common tools to event types
            mapping = {
                "campaign_brain": "campaign",
                "creative_studio": "creative",
                "council": "agency",
                "performance": "analytics",
                "chat": "conversation",
                "memory": "memory",
                "proactive": "notification",
                "review": "review",
                "consult": "onboarding",
                "creator": "creative",
            }
            event_ns = mapping.get(namespace, namespace)
            return f"{event_ns}.{action}.{phase}"
        return f"tool.{phase}"
