"""Integration Workflow Engine — configurable if/then workflows triggered by events.

This is the layer between the Event Bus and the Planner/Tools. Instead of
hard-coded handlers, workflows are configurable:

    Webhook → Event Bus → Workflow Engine → Planner → Tools → Actions

Example workflow:
    WHEN Shopify order_created
    IF customer is new (not in CRM)
    THEN
      1. Generate welcome email via Mailchimp
      2. Create HubSpot contact
      3. Update CRM lifecycle stage to "customer"
      4. Generate follow-up WhatsApp message
      5. Notify founder

Workflows are:
- Configurable (no code changes to add/modify)
- Conditional (IF/THEN logic with field comparisons)
- Sequential (steps run in order, output feeds next step)
- Error-resilient (one step failing doesn't stop the workflow)
- Auditable (every step execution is logged)

Workflow definitions are stored as JSON and can be created/edited via API.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable

from .base import WebhookEvent
from .event_bus import IntegrationEventBus, get_event_bus

log = logging.getLogger("prachar.integrations.workflows")


# ─── Workflow Definition Model ──────────────────────────────────────────────


class ConditionOperator(str, Enum):
    """Comparison operators for workflow conditions."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    IN = "in"
    NOT_IN = "not_in"


class ActionType(str, Enum):
    """Types of actions a workflow can execute."""
    SEND_EMAIL = "send_email"
    CREATE_CRM_CONTACT = "create_crm_contact"
    UPDATE_CRM_FIELD = "update_crm_field"
    CREATE_CRM_DEAL = "create_crm_deal"
    SEND_WHATSAPP = "send_whatsapp"
    PUBLISH_POST = "publish_post"
    GENERATE_CONTENT = "generate_content"
    NOTIFY_USER = "notify_user"
    TAG_CUSTOMER = "tag_customer"
    UPDATE_AUDIENCE = "update_audience"
    TRIGGER_CAMPAIGN = "trigger_campaign"
    WEBHOOK_CALL = "webhook_call"
    LOG_EVENT = "log_event"
    CUSTOM = "custom"


@dataclass
class WorkflowCondition:
    """A condition that must be true for the workflow to execute."""
    field: str                    # Dot-notation path in the event payload (e.g. "payload.is_new_customer")
    operator: ConditionOperator
    value: Any = None             # Value to compare against (not needed for IS_EMPTY/IS_NOT_EMPTY)

    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate this condition against the event context."""
        # Navigate dot-notation path
        parts = self.field.split(".")
        current: Any = context
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = getattr(current, part, None)
            if current is None:
                break

        if self.operator == ConditionOperator.IS_EMPTY:
            return current is None or current == "" or current == []
        if self.operator == ConditionOperator.IS_NOT_EMPTY:
            return current is not None and current != "" and current != []
        if current is None:
            return False

        if self.operator == ConditionOperator.EQUALS:
            return current == self.value
        if self.operator == ConditionOperator.NOT_EQUALS:
            return current != self.value
        if self.operator == ConditionOperator.CONTAINS:
            if isinstance(current, (list, str)):
                return self.value in current
            return False
        if self.operator == ConditionOperator.NOT_CONTAINS:
            if isinstance(current, (list, str)):
                return self.value not in current
            return True
        if self.operator == ConditionOperator.GREATER_THAN:
            try:
                return float(current) > float(self.value)
            except (ValueError, TypeError):
                return False
        if self.operator == ConditionOperator.LESS_THAN:
            try:
                return float(current) < float(self.value)
            except (ValueError, TypeError):
                return False
        if self.operator == ConditionOperator.GREATER_THAN_OR_EQUAL:
            try:
                return float(current) >= float(self.value)
            except (ValueError, TypeError):
                return False
        if self.operator == ConditionOperator.LESS_THAN_OR_EQUAL:
            try:
                return float(current) <= float(self.value)
            except (ValueError, TypeError):
                return False
        if self.operator == ConditionOperator.IN:
            return current in (self.value if isinstance(self.value, (list, set)) else [self.value])
        if self.operator == ConditionOperator.NOT_IN:
            return current not in (self.value if isinstance(self.value, (list, set)) else [self.value])

        return False


@dataclass
class WorkflowAction:
    """A single action in a workflow."""
    action_type: ActionType
    name: str = ""                # Human-readable name
    config: dict[str, Any] = field(default_factory=dict)  # Action-specific config
    # If True, workflow continues even if this action fails
    continue_on_error: bool = True
    # Delay before executing this action (in seconds)
    delay_seconds: float = 0.0


@dataclass
class Workflow:
    """A configurable workflow triggered by integration events.

    Stored as JSON in the database. Executed by the WorkflowEngine.
    """
    id: str
    name: str
    description: str = ""
    # Trigger: which integration + event type activates this workflow
    trigger_integration: str = "*"      # "shopify", "hubspot", or "*" for any
    trigger_event_type: str = "*"       # "orders/create", "deal.creation", or "*"
    # Conditions: ALL must be true for the workflow to execute
    conditions: list[WorkflowCondition] = field(default_factory=list)
    # Actions: executed sequentially
    actions: list[WorkflowAction] = field(default_factory=list)
    # State
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Execution stats
    execution_count: int = 0
    last_executed_at: datetime | None = None
    last_execution_status: str = ""    # "success", "failed", "skipped"

    def matches_trigger(self, event: WebhookEvent) -> bool:
        """Check if this workflow should be triggered by the event."""
        if not self.is_active:
            return False
        if self.trigger_integration != "*" and self.trigger_integration != event.integration:
            return False
        if self.trigger_event_type != "*" and self.trigger_event_type != event.event_type:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "trigger_integration": self.trigger_integration,
            "trigger_event_type": self.trigger_event_type,
            "conditions": [
                {"field": c.field, "operator": c.operator.value, "value": c.value}
                for c in self.conditions
            ],
            "actions": [
                {
                    "action_type": a.action_type.value,
                    "name": a.name,
                    "config": a.config,
                    "continue_on_error": a.continue_on_error,
                    "delay_seconds": a.delay_seconds,
                }
                for a in self.actions
            ],
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "execution_count": self.execution_count,
            "last_executed_at": self.last_executed_at.isoformat() if self.last_executed_at else None,
            "last_execution_status": self.last_execution_status,
        }


# ─── Workflow Execution ─────────────────────────────────────────────────────


@dataclass
class WorkflowExecution:
    """Record of a single workflow execution."""
    workflow_id: str
    event: WebhookEvent
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    status: str = "running"     # "running", "success", "failed", "skipped"
    conditions_met: bool = True
    actions_executed: int = 0
    actions_failed: int = 0
    errors: list[str] = field(default_factory=list)
    action_results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "event": self.event.to_dict(),
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "conditions_met": self.conditions_met,
            "actions_executed": self.actions_executed,
            "actions_failed": self.actions_failed,
            "errors": self.errors,
            "action_results": self.action_results,
        }


# Type for action executors: (action, context) -> result
ActionExecutor = Callable[[WorkflowAction, dict[str, Any]], Awaitable[dict[str, Any]]]


# ─── Workflow Engine ────────────────────────────────────────────────────────


class WorkflowEngine:
    """Executes configurable workflows triggered by integration events.

    The engine subscribes to the event bus and evaluates all matching
    workflows. For each workflow whose conditions are met, it executes
    the actions sequentially.

    Action executors are registered per ActionType. This keeps the engine
    decoupled from the actual tool implementations.

    Usage:
        engine = WorkflowEngine()

        @engine.executor(ActionType.SEND_EMAIL)
        async def send_email(action: WorkflowAction, context: dict) -> dict:
            # Use Mailchimp adapter to send email
            return {"status": "sent", "campaign_id": "abc123"}

        @engine.executor(ActionType.NOTIFY_USER)
        async def notify(action: WorkflowAction, context: dict) -> dict:
            # Send notification to user
            return {"status": "notified"}

        # Register a workflow
        engine.register_workflow(Workflow(
            id="welcome_new_customer",
            name="Welcome New Customer",
            trigger_integration="shopify",
            trigger_event_type="orders/create",
            conditions=[
                WorkflowCondition("payload.is_first_order", ConditionOperator.EQUALS, True),
            ],
            actions=[
                WorkflowAction(ActionType.SEND_EMAIL, "Welcome email",
                               config={"template": "welcome", "list_id": "abc"}),
                WorkflowAction(ActionType.CREATE_CRM_CONTACT, "Create HubSpot contact",
                               config={"object_type": "contact"}),
                WorkflowAction(ActionType.NOTIFY_USER, "Notify founder",
                               config={"channel": "whatsapp"}),
            ],
        ))

        # The engine auto-subscribes to the event bus
    """

    def __init__(self, event_bus: IntegrationEventBus | None = None) -> None:
        self._event_bus = event_bus or get_event_bus()
        self._workflows: dict[str, Workflow] = {}
        self._executors: dict[ActionType, ActionExecutor] = {}
        self._executions: list[WorkflowExecution] = []
        self._subscribed = False

    def register_workflow(self, workflow: Workflow) -> None:
        """Register a workflow."""
        self._workflows[workflow.id] = workflow
        log.info("Registered workflow: %s (%s)", workflow.name, workflow.id)
        self._ensure_subscribed()

    def unregister_workflow(self, workflow_id: str) -> None:
        """Remove a workflow."""
        self._workflows.pop(workflow_id, None)

    def get_workflow(self, workflow_id: str) -> Workflow | None:
        return self._workflows.get(workflow_id)

    def list_workflows(self) -> list[Workflow]:
        return list(self._workflows.values())

    def executor(self, action_type: ActionType) -> Callable[[ActionExecutor], ActionExecutor]:
        """Decorator to register an action executor.

        @engine.executor(ActionType.SEND_EMAIL)
        async def send_email(action, context): ...
        """
        def decorator(fn: ActionExecutor) -> ActionExecutor:
            self._executors[action_type] = fn
            log.debug("Registered executor for %s", action_type.value)
            return fn
        return decorator

    def _ensure_subscribed(self) -> None:
        """Subscribe to the event bus (once)."""
        if self._subscribed:
            return
        self._event_bus.on("*", "*", self._handle_event)
        self._subscribed = True

    async def _handle_event(self, event: WebhookEvent) -> None:
        """Handle an event from the bus — evaluate all matching workflows."""
        for workflow in list(self._workflows.values()):
            if not workflow.matches_trigger(event):
                continue
            await self.execute_workflow(workflow, event)

    async def execute_workflow(self, workflow: Workflow, event: WebhookEvent) -> WorkflowExecution:
        """Execute a workflow for a given event."""
        execution = WorkflowExecution(workflow_id=workflow.id, event=event)

        # Build context from event
        context: dict[str, Any] = {
            "event": event.to_dict(),
            "payload": event.payload,
            "integration": event.integration,
            "event_type": event.event_type,
            "entity_id": event.entity_id,
            "entity_type": event.entity_type,
        }

        # Evaluate conditions
        for condition in workflow.conditions:
            if not condition.evaluate(context):
                execution.conditions_met = False
                execution.status = "skipped"
                execution.completed_at = datetime.now(timezone.utc)
                workflow.last_execution_status = "skipped"
                self._executions.append(execution)
                log.info("Workflow %s skipped (conditions not met)", workflow.name)
                return execution

        # Execute actions sequentially
        for action in workflow.actions:
            # Apply delay if configured
            if action.delay_seconds > 0:
                await asyncio.sleep(action.delay_seconds)

            executor = self._executors.get(action.action_type)
            if not executor:
                error = f"No executor registered for action type {action.action_type.value}"
                execution.errors.append(error)
                if not action.continue_on_error:
                    execution.status = "failed"
                    break
                continue

            try:
                result = await executor(action, context)
                execution.actions_executed += 1
                execution.action_results.append({
                    "action": action.name or action.action_type.value,
                    "type": action.action_type.value,
                    "result": result,
                    "success": True,
                })
                # Feed result into context for next action
                context[f"prev_action.{action.action_type.value}"] = result
            except Exception as e:
                execution.actions_failed += 1
                execution.errors.append(f"{action.name}: {e}")
                execution.action_results.append({
                    "action": action.name or action.action_type.value,
                    "type": action.action_type.value,
                    "error": str(e),
                    "success": False,
                })
                log.error("Action %s failed in workflow %s: %s", action.name, workflow.name, e, exc_info=True)
                if not action.continue_on_error:
                    execution.status = "failed"
                    break

        if execution.status == "running":
            execution.status = "success" if execution.actions_failed == 0 else "partial"

        execution.completed_at = datetime.now(timezone.utc)

        # Update workflow stats
        workflow.execution_count += 1
        workflow.last_executed_at = datetime.now(timezone.utc)
        workflow.last_execution_status = execution.status

        self._executions.append(execution)
        log.info(
            "Workflow %s completed: %s (%d actions, %d failed)",
            workflow.name, execution.status,
            execution.actions_executed, execution.actions_failed,
        )
        return execution

    def execution_history(self, workflow_id: str | None = None, limit: int = 50) -> list[WorkflowExecution]:
        """Get execution history, optionally filtered by workflow."""
        execs = self._executions
        if workflow_id:
            execs = [e for e in execs if e.workflow_id == workflow_id]
        return execs[-limit:]

    def stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        return {
            "total_workflows": len(self._workflows),
            "active_workflows": sum(1 for w in self._workflows.values() if w.is_active),
            "total_executions": len(self._executions),
            "successful_executions": sum(1 for e in self._executions if e.status == "success"),
            "failed_executions": sum(1 for e in self._executions if e.status == "failed"),
            "skipped_executions": sum(1 for e in self._executions if e.status == "skipped"),
            "registered_executors": [t.value for t in self._executors],
        }


# ─── Singleton ──────────────────────────────────────────────────────────────


_engine: WorkflowEngine | None = None


def get_workflow_engine() -> WorkflowEngine:
    """Get the global workflow engine instance."""
    global _engine
    if _engine is None:
        _engine = WorkflowEngine()
    return _engine
