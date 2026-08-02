"""Automation Engine — autonomous AI operations through the Runtime.

Phase H: The Runtime can operate autonomously, performing:
1. Autonomous campaign reviews — review active campaigns weekly
2. Proactive recommendations — detect anomalies and recommend actions
3. Scheduled marketing audits — periodic brand/performance audits
4. Auto-generated campaign drafts — generate campaign drafts for upcoming events
5. Approval workflows — route auto-generated content through human approval

All automation goes through the Runtime (Constitution Rule: nothing bypasses
the Runtime). The automation engine creates Runtime sessions in AUTOMATION mode.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

log = logging.getLogger("prachar.runtime.automation")


# ─── Automation Types ───────────────────────────────────────────────────────


class AutomationType(str, Enum):
    """Types of automated tasks the Runtime can perform."""

    CAMPAIGN_REVIEW = "campaign_review"          # weekly review of active campaigns
    PROACTIVE_ALERT = "proactive_alert"          # anomaly detection + recommendations
    MARKETING_AUDIT = "marketing_audit"          # periodic brand/visibility audit
    CAMPAIGN_DRAFT = "campaign_draft"            # auto-generate campaign drafts
    PERFORMANCE_CHECK = "performance_check"      # scheduled performance analysis
    BUDGET_REVIEW = "budget_review"              # budget utilisation review
    CONTENT_CALENDAR = "content_calendar"        # auto-generate weekly content calendar


class AutomationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"          # skipped because conditions not met
    AWAITING_APPROVAL = "awaiting_approval"


class AutomationFrequency(str, Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class AutomationTask:
    """A single automation task to be executed by the Runtime."""

    id: str = ""
    type: AutomationType = AutomationType.CAMPAIGN_REVIEW
    brand_id: UUID | None = None
    tenant_id: UUID | None = None
    frequency: AutomationFrequency = AutomationFrequency.WEEKLY
    status: AutomationStatus = AutomationStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    executed_at: str = ""
    next_run_at: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    requires_approval: bool = False
    approved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "brand_id": str(self.brand_id) if self.brand_id else None,
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "frequency": self.frequency.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "executed_at": self.executed_at,
            "next_run_at": self.next_run_at,
            "config": self.config,
            "result": self.result,
            "error": self.error,
            "requires_approval": self.requires_approval,
            "approved": self.approved,
        }


# ─── Automation Rules ───────────────────────────────────────────────────────


@dataclass
class AutomationRule:
    """A rule that defines when an automation task should be created.

    Rules are evaluated periodically. When a rule's conditions are met,
    an AutomationTask is created and queued for execution.
    """

    id: str = ""
    name: str = ""
    type: AutomationType = AutomationType.CAMPAIGN_REVIEW
    frequency: AutomationFrequency = AutomationFrequency.WEEKLY
    enabled: bool = True
    conditions: dict[str, Any] = field(default_factory=dict)
    actions: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False

    def should_run(self, context: dict[str, Any]) -> bool:
        """Check if this rule's conditions are met."""
        if not self.enabled:
            return False

        # Campaign review: run if brand has active campaigns
        if self.type == AutomationType.CAMPAIGN_REVIEW:
            return context.get("active_campaigns", 0) > 0

        # Proactive alert: run if there are anomalies
        if self.type == AutomationType.PROACTIVE_ALERT:
            return context.get("anomaly_count", 0) > 0

        # Marketing audit: run if last audit was > 7 days ago
        if self.type == AutomationType.MARKETING_AUDIT:
            days_since = context.get("days_since_audit", 999)
            return days_since >= 7

        # Campaign draft: run if there's an upcoming event
        if self.type == AutomationType.CAMPAIGN_DRAFT:
            return context.get("upcoming_events", 0) > 0

        # Performance check: run if campaign has been active > 3 days
        if self.type == AutomationType.PERFORMANCE_CHECK:
            return context.get("active_campaigns", 0) > 0

        # Budget review: run if budget utilisation > 50%
        if self.type == AutomationType.BUDGET_REVIEW:
            utilisation = context.get("budget_utilisation", 0)
            return utilisation > 0.5

        # Content calendar: always run weekly
        if self.type == AutomationType.CONTENT_CALENDAR:
            return True

        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "frequency": self.frequency.value,
            "enabled": self.enabled,
            "conditions": self.conditions,
            "actions": self.actions,
            "requires_approval": self.requires_approval,
        }


# ─── Default Rules ──────────────────────────────────────────────────────────


def create_default_rules() -> list[AutomationRule]:
    """Create the default set of automation rules."""
    return [
        AutomationRule(
            id="weekly_campaign_review",
            name="Weekly Campaign Review",
            type=AutomationType.CAMPAIGN_REVIEW,
            frequency=AutomationFrequency.WEEKLY,
            requires_approval=False,
            conditions={"min_active_campaigns": 1},
            actions={"tools": ["performance.story", "performance.why", "council.review"]},
        ),
        AutomationRule(
            id="proactive_alerts",
            name="Proactive Anomaly Alerts",
            type=AutomationType.PROACTIVE_ALERT,
            frequency=AutomationFrequency.DAILY,
            requires_approval=False,
            conditions={"check_anomalies": True},
            actions={"tools": ["proactive.notifications"]},
        ),
        AutomationRule(
            id="weekly_marketing_audit",
            name="Weekly Marketing Audit",
            type=AutomationType.MARKETING_AUDIT,
            frequency=AutomationFrequency.WEEKLY,
            requires_approval=False,
            conditions={"min_days_since_audit": 7},
            actions={"tools": ["campaign_brain.analyse"]},
        ),
        AutomationRule(
            id="auto_campaign_draft",
            name="Auto-Generate Campaign Drafts",
            type=AutomationType.CAMPAIGN_DRAFT,
            frequency=AutomationFrequency.WEEKLY,
            requires_approval=True,  # auto-drafts need human approval before publishing
            conditions={"check_upcoming_events": True},
            actions={"tools": ["campaign_brain.full_campaign"]},
        ),
        AutomationRule(
            id="daily_performance_check",
            name="Daily Performance Check",
            type=AutomationType.PERFORMANCE_CHECK,
            frequency=AutomationFrequency.DAILY,
            requires_approval=False,
            conditions={"min_active_campaigns": 1},
            actions={"tools": ["performance.story"]},
        ),
        AutomationRule(
            id="weekly_budget_review",
            name="Weekly Budget Review",
            type=AutomationType.BUDGET_REVIEW,
            frequency=AutomationFrequency.WEEKLY,
            requires_approval=False,
            conditions={"min_budget_utilisation": 0.5},
            actions={"tools": ["performance.story"]},
        ),
        AutomationRule(
            id="weekly_content_calendar",
            name="Weekly Content Calendar",
            type=AutomationType.CONTENT_CALENDAR,
            frequency=AutomationFrequency.WEEKLY,
            requires_approval=True,
            conditions={},
            actions={"tools": ["creative_studio.generate"]},
        ),
    ]


# ─── Automation Engine ──────────────────────────────────────────────────────


class AutomationEngine:
    """Evaluates automation rules and creates tasks for the Runtime to execute.

    The engine itself does NOT execute tasks — it creates AutomationTask objects
    that are then picked up by the Runtime (or a worker) and executed as
    Runtime sessions in AUTOMATION mode.

    This ensures Constitution Rule: nothing bypasses the Runtime.
    """

    def __init__(self, rules: list[AutomationRule] | None = None) -> None:
        self._rules = rules or create_default_rules()
        self._tasks: list[AutomationTask] = []

    @property
    def rules(self) -> list[AutomationRule]:
        return self._rules

    @property
    def tasks(self) -> list[AutomationTask]:
        return self._tasks

    def evaluate(
        self,
        brand_id: UUID,
        tenant_id: UUID,
        context: dict[str, Any],
    ) -> list[AutomationTask]:
        """Evaluate all rules against the context and create tasks for matching rules.

        Args:
            brand_id: The brand to run automation for
            tenant_id: The tenant that owns the brand
            context: Dictionary with keys like:
                - active_campaigns: int
                - anomaly_count: int
                - days_since_audit: int
                - upcoming_events: int
                - budget_utilisation: float (0.0-1.0)

        Returns:
            List of AutomationTask objects to be executed
        """
        created_tasks: list[AutomationTask] = []

        for rule in self._rules:
            if not rule.should_run(context):
                continue

            task = AutomationTask(
                id=f"{rule.id}_{brand_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                type=rule.type,
                brand_id=brand_id,
                tenant_id=tenant_id,
                frequency=rule.frequency,
                requires_approval=rule.requires_approval,
                config={
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "actions": rule.actions,
                },
            )
            self._tasks.append(task)
            created_tasks.append(task)
            log.info("automation task created: %s (%s)", task.id, task.type.value)

        return created_tasks

    def get_pending_tasks(self) -> list[AutomationTask]:
        """Return all tasks that are pending execution."""
        return [t for t in self._tasks if t.status == AutomationStatus.PENDING]

    def get_tasks_for_brand(self, brand_id: UUID) -> list[AutomationTask]:
        """Return all tasks for a specific brand."""
        return [t for t in self._tasks if t.brand_id == brand_id]

    def mark_running(self, task_id: str) -> None:
        for t in self._tasks:
            if t.id == task_id:
                t.status = AutomationStatus.RUNNING
                t.executed_at = datetime.now(timezone.utc).isoformat()
                break

    def mark_completed(self, task_id: str, result: dict[str, Any]) -> None:
        for t in self._tasks:
            if t.id == task_id:
                t.status = AutomationStatus.COMPLETED
                t.result = result
                break

    def mark_failed(self, task_id: str, error: str) -> None:
        for t in self._tasks:
            if t.id == task_id:
                t.status = AutomationStatus.FAILED
                t.error = error
                break

    def mark_awaiting_approval(self, task_id: str) -> None:
        for t in self._tasks:
            if t.id == task_id:
                t.status = AutomationStatus.AWAITING_APPROVAL
                break

    def approve(self, task_id: str) -> bool:
        """Approve a task that's awaiting approval."""
        for t in self._tasks:
            if t.id == task_id and t.status == AutomationStatus.AWAITING_APPROVAL:
                t.approved = True
                t.status = AutomationStatus.PENDING  # ready to execute
                return True
        return False

    def reject(self, task_id: str) -> bool:
        """Reject a task that's awaiting approval."""
        for t in self._tasks:
            if t.id == task_id and t.status == AutomationStatus.AWAITING_APPROVAL:
                t.status = AutomationStatus.SKIPPED
                t.error = "Rejected by user"
                return True
        return False


# ─── Automation Context Builder ─────────────────────────────────────────────


async def build_automation_context(
    session: Any,
    tenant_id: UUID,
    brand_id: UUID,
) -> dict[str, Any]:
    """Build the context dictionary for automation rule evaluation.

    Queries the database for current state: active campaigns, anomalies,
    budget utilisation, days since last audit, upcoming events.
    """
    from sqlalchemy import select, func
    from ..models import CampaignPlanRecord
    from ..runtime.timeline import WorkspaceTimeline

    context: dict[str, Any] = {}

    try:
        # Active campaigns count
        res = await session.execute(
            select(func.count(CampaignPlanRecord.id)).where(
                CampaignPlanRecord.brand_id == brand_id,
                CampaignPlanRecord.status.in_(["active", "running", "in_review"]),
            )
        )
        context["active_campaigns"] = res.scalar() or 0

        # Days since last audit
        res = await session.execute(
            select(func.max(WorkspaceTimeline.created_at)).where(
                WorkspaceTimeline.brand_id == brand_id,
                WorkspaceTimeline.entry_type == "decision_contract",
            )
        )
        last_audit = res.scalar()
        if last_audit:
            if isinstance(last_audit, str):
                last_audit_dt = datetime.fromisoformat(last_audit.replace("Z", "+00:00"))
            else:
                last_audit_dt = last_audit
            delta = datetime.now(timezone.utc) - last_audit_dt
            context["days_since_audit"] = delta.days
        else:
            context["days_since_audit"] = 999

        # Budget utilisation (placeholder — would query actual spend)
        context["budget_utilisation"] = 0.0

        # Anomaly count (placeholder — would query proactive alerts)
        context["anomaly_count"] = 0

        # Upcoming events (placeholder — would query calendar)
        context["upcoming_events"] = 0

    except Exception as exc:
        log.warning("failed to build automation context: %s", exc)

    return context


# ─── Singleton ──────────────────────────────────────────────────────────────


_automation_engine: AutomationEngine | None = None


def get_automation_engine() -> AutomationEngine:
    global _automation_engine
    if _automation_engine is None:
        _automation_engine = AutomationEngine()
    return _automation_engine
