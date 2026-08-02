"""Decision Contract — structured object created BEFORE execution.

Constitution Rule 3: Every execution creates exactly one Decision Contract.
Never execute work without one.

The Decision Contract becomes: audit trail, explainability, debugging,
analytics, learning, replay source. Everything later can reference it.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .context import AIContext


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"  # V4: partial failure
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class DecisionContract:
    """A structured decision object created before any tool executes.

    Stored in the Workspace Timeline as entry_type="decision_contract".
    Every event references decision_id. Every timeline entry references it.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # The decision
    goal: str = ""                                # "Create Diwali Campaign"
    reasoning: str = ""                           # why this plan was chosen (internal)
    user_explanation: str = ""                    # Step 2: user-facing explanation (no tool names)
    intent: str = ""                              # "campaign.create"
    mode: str = ""                                # "creation"

    # The plan
    tools: list[str] = field(default_factory=list)  # ["campaign_brain.analyse", ...]
    graph: dict[str, Any] = field(default_factory=dict)  # serialised ExecutionGraph

    # Risk & approval
    risk_level: str = RiskLevel.LOW.value
    requires_approval: bool = False
    approval_reason: str | None = None

    # Estimates
    estimated_duration: str = "—"
    estimated_cost_usd: float = 0.0
    expected_outputs: list[str] = field(default_factory=list)

    # Context snapshot (for replay/debugging)
    context_snapshot: dict[str, Any] = field(default_factory=dict)

    # Lifecycle
    status: str = DecisionStatus.PENDING.value
    approved_by: str | None = None
    approved_at: str | None = None

    # Results (filled after execution)
    actual_duration_ms: int = 0
    actual_cost_usd: float = 0.0
    error: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)  # V6: RuntimeMetrics snapshot
    warnings: list[str] = field(default_factory=list)       # V4: partial failure details
    health_warnings: list[str] = field(default_factory=list)  # Phase E1.2: degraded/offline notices
    cost_breakdown: list[dict] = field(default_factory=list)  # Phase E2.2: per-tool {tool, cost, latency, quality}

    @classmethod
    def create(
        cls,
        session_id: str,
        goal: str,
        reasoning: str,
        intent: str,
        mode: str,
        tools: list[str],
        graph: dict[str, Any],
        risk_level: str,
        requires_approval: bool,
        approval_reason: str | None,
        estimated_duration: str,
        estimated_cost_usd: float,
        expected_outputs: list[str],
        context: AIContext,
        user_explanation: str = "",
        health_warnings: list[str] | None = None,
        cost_breakdown: list[dict] | None = None,
    ) -> "DecisionContract":
        """Create a Decision Contract from the Planner's output."""
        return cls(
            session_id=session_id,
            goal=goal,
            reasoning=reasoning,
            user_explanation=user_explanation,
            intent=intent,
            mode=mode,
            tools=tools,
            graph=graph,
            risk_level=risk_level,
            requires_approval=requires_approval,
            approval_reason=approval_reason,
            estimated_duration=estimated_duration,
            estimated_cost_usd=estimated_cost_usd,
            expected_outputs=expected_outputs,
            context_snapshot=context.to_snapshot(),
            health_warnings=health_warnings or [],
            cost_breakdown=cost_breakdown or [],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "goal": self.goal,
            "reasoning": self.reasoning,
            "user_explanation": self.user_explanation,
            "intent": self.intent,
            "mode": self.mode,
            "tools": self.tools,
            "graph": self.graph,
            "risk_level": self.risk_level,
            "requires_approval": self.requires_approval,
            "approval_reason": self.approval_reason,
            "estimated_duration": self.estimated_duration,
            "estimated_cost_usd": self.estimated_cost_usd,
            "expected_outputs": self.expected_outputs,
            "context_snapshot": self.context_snapshot,
            "status": self.status,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "actual_duration_ms": self.actual_duration_ms,
            "actual_cost_usd": self.actual_cost_usd,
            "error": self.error,
            "metrics": self.metrics,
            "warnings": self.warnings,
            "health_warnings": self.health_warnings,
            "cost_breakdown": self.cost_breakdown,
        }

    def to_timeline_entry(self) -> dict[str, Any]:
        """Format for storage in workspace_timeline."""
        return {
            "entry_type": "decision_contract",
            "actor": "ai",
            "title": f"Plan: {self.goal}",
            "summary": self.reasoning[:200] if self.reasoning else "",
            "detail": self.to_dict(),
            "replayable": True,
            "replay_inputs": {
                "intent": self.intent,
                "mode": self.mode,
                "context_snapshot": self.context_snapshot,
            },
        }
