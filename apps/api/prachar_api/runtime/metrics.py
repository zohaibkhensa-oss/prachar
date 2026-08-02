"""Runtime Metrics — automatically collected for every execution.

Constitution V6: Every execution should collect planning time, execution time,
waiting time, tool time, LLM time, tokens, cost, retries, failures,
cancellation, and approval delay.

This is NOT a user feature. It's for the internal Runtime Certification
Dashboard and for future cost/performance optimisation.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("prachar.runtime.metrics")


@dataclass
class ToolMetrics:
    """Metrics for a single tool execution."""

    tool: str
    node_id: str
    started_at: float = 0.0
    completed_at: float = 0.0
    duration_ms: int = 0
    cost_usd: float = 0.0
    tokens_used: int = 0
    retries: int = 0
    success: bool = True
    error: str | None = None
    cancelled: bool = False
    timed_out: bool = False

    @property
    def llm_time_ms(self) -> int:
        """LLM time is approximated as tool duration (most tools are LLM-bound)."""
        return self.duration_ms


@dataclass
class RuntimeMetrics:
    """Metrics collected for a single Runtime session.

    Every execution automatically collects these. Stored in the Decision
    Contract and in the Timeline for later analysis.
    """

    session_id: str = ""
    decision_id: str = ""

    # Phase timings (epoch seconds → converted to ms)
    request_started_at: float = 0.0
    context_assembled_at: float = 0.0
    intent_classified_at: float = 0.0
    plan_created_at: float = 0.0
    decision_created_at: float = 0.0
    execution_started_at: float = 0.0
    execution_completed_at: float = 0.0
    response_composed_at: float = 0.0
    session_completed_at: float = 0.0

    # Approval tracking
    approval_requested_at: float = 0.0
    approval_granted_at: float = 0.0

    # Tool metrics
    tool_metrics: list[ToolMetrics] = field(default_factory=list)

    # Aggregate counts
    total_tools: int = 0
    successful_tools: int = 0
    failed_tools: int = 0
    cancelled_tools: int = 0
    retried_tools: int = 0

    # Costs
    total_cost_usd: float = 0.0
    total_tokens: int = 0

    # Outcome
    outcome: str = ""  # "completed", "completed_with_warnings", "cancelled", "failed"

    # ─── Derived properties ─────────────────────────────────────────────────

    @property
    def planning_time_ms(self) -> int:
        """Time from request start to plan creation."""
        if self.plan_created_at and self.request_started_at:
            return int((self.plan_created_at - self.request_started_at) * 1000)
        return 0

    @property
    def context_assembly_time_ms(self) -> int:
        if self.context_assembled_at and self.request_started_at:
            return int((self.context_assembled_at - self.request_started_at) * 1000)
        return 0

    @property
    def intent_classification_time_ms(self) -> int:
        if self.intent_classified_at and self.context_assembled_at:
            return int((self.intent_classified_at - self.context_assembled_at) * 1000)
        return 0

    @property
    def planner_time_ms(self) -> int:
        if self.plan_created_at and self.intent_classified_at:
            return int((self.plan_created_at - self.intent_classified_at) * 1000)
        return 0

    @property
    def execution_time_ms(self) -> int:
        if self.execution_completed_at and self.execution_started_at:
            return int((self.execution_completed_at - self.execution_started_at) * 1000)
        return 0

    @property
    def waiting_time_ms(self) -> int:
        """Time spent waiting for approval."""
        if self.approval_requested_at and self.approval_granted_at:
            return int((self.approval_granted_at - self.approval_requested_at) * 1000)
        return 0

    @property
    def response_composition_time_ms(self) -> int:
        if self.response_composed_at and self.execution_completed_at:
            return int((self.response_composed_at - self.execution_completed_at) * 1000)
        return 0

    @property
    def total_duration_ms(self) -> int:
        if self.session_completed_at and self.request_started_at:
            return int((self.session_completed_at - self.request_started_at) * 1000)
        return 0

    @property
    def tool_time_ms(self) -> int:
        """Sum of all tool durations."""
        return sum(tm.duration_ms for tm in self.tool_metrics)

    @property
    def llm_time_ms(self) -> int:
        """Approximate LLM time (most tools are LLM-bound)."""
        return sum(tm.llm_time_ms for tm in self.tool_metrics)

    # ─── Recording helpers ──────────────────────────────────────────────────

    def mark_request_started(self) -> None:
        self.request_started_at = time.time()

    def mark_context_assembled(self) -> None:
        self.context_assembled_at = time.time()

    def mark_intent_classified(self) -> None:
        self.intent_classified_at = time.time()

    def mark_plan_created(self) -> None:
        self.plan_created_at = time.time()

    def mark_decision_created(self) -> None:
        self.decision_created_at = time.time()

    def mark_execution_started(self) -> None:
        self.execution_started_at = time.time()

    def mark_execution_completed(self) -> None:
        self.execution_completed_at = time.time()

    def mark_response_composed(self) -> None:
        self.response_composed_at = time.time()

    def mark_session_completed(self) -> None:
        self.session_completed_at = time.time()

    def mark_approval_requested(self) -> None:
        self.approval_requested_at = time.time()

    def mark_approval_granted(self) -> None:
        self.approval_granted_at = time.time()

    def record_tool(self, tm: ToolMetrics) -> None:
        self.tool_metrics.append(tm)
        self.total_tools += 1
        if tm.success:
            self.successful_tools += 1
        elif tm.cancelled:
            self.cancelled_tools += 1
        else:
            self.failed_tools += 1
        if tm.retries > 0:
            self.retried_tools += 1
        self.total_cost_usd += tm.cost_usd
        self.total_tokens += tm.tokens_used

    # ─── Serialisation ──────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "decision_id": self.decision_id,
            "outcome": self.outcome,
            "timings": {
                "total_duration_ms": self.total_duration_ms,
                "context_assembly_ms": self.context_assembly_time_ms,
                "intent_classification_ms": self.intent_classification_time_ms,
                "planner_ms": self.planner_time_ms,
                "planning_time_ms": self.planning_time_ms,
                "execution_time_ms": self.execution_time_ms,
                "tool_time_ms": self.tool_time_ms,
                "llm_time_ms": self.llm_time_ms,
                "waiting_time_ms": self.waiting_time_ms,
                "response_composition_ms": self.response_composition_time_ms,
            },
            "tools": {
                "total": self.total_tools,
                "successful": self.successful_tools,
                "failed": self.failed_tools,
                "cancelled": self.cancelled_tools,
                "retried": self.retried_tools,
            },
            "costs": {
                "total_usd": round(self.total_cost_usd, 6),
                "total_tokens": self.total_tokens,
            },
            "tool_details": [
                {
                    "tool": tm.tool,
                    "node_id": tm.node_id,
                    "duration_ms": tm.duration_ms,
                    "cost_usd": tm.cost_usd,
                    "tokens": tm.tokens_used,
                    "retries": tm.retries,
                    "success": tm.success,
                    "error": tm.error,
                    "cancelled": tm.cancelled,
                    "timed_out": tm.timed_out,
                }
                for tm in self.tool_metrics
            ],
        }
