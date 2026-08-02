"""Phase H tests — Automation Engine.

Tests automation rules, task creation, approval workflow, and context building.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from prachar_api.runtime.automation import (
    AutomationEngine,
    AutomationFrequency,
    AutomationRule,
    AutomationStatus,
    AutomationTask,
    AutomationType,
    create_default_rules,
    build_automation_context,
)


class TestAutomationTypes:
    """Automation enums and data classes."""

    def test_automation_type_values(self):
        assert AutomationType.CAMPAIGN_REVIEW.value == "campaign_review"
        assert AutomationType.PROACTIVE_ALERT.value == "proactive_alert"
        assert AutomationType.MARKETING_AUDIT.value == "marketing_audit"
        assert AutomationType.CAMPAIGN_DRAFT.value == "campaign_draft"

    def test_automation_status_values(self):
        assert AutomationStatus.PENDING.value == "pending"
        assert AutomationStatus.RUNNING.value == "running"
        assert AutomationStatus.COMPLETED.value == "completed"
        assert AutomationStatus.AWAITING_APPROVAL.value == "awaiting_approval"

    def test_automation_frequency_values(self):
        assert AutomationFrequency.ONCE.value == "once"
        assert AutomationFrequency.DAILY.value == "daily"
        assert AutomationFrequency.WEEKLY.value == "weekly"

    def test_automation_task_to_dict(self):
        task = AutomationTask(
            id="test_1",
            type=AutomationType.CAMPAIGN_REVIEW,
            brand_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
        )
        d = task.to_dict()
        assert d["id"] == "test_1"
        assert d["type"] == "campaign_review"
        assert d["status"] == "pending"
        assert d["requires_approval"] is False


class TestAutomationRules:
    """Automation rule conditions and evaluation."""

    def test_default_rules_created(self):
        rules = create_default_rules()
        assert len(rules) == 7
        types = [r.type for r in rules]
        assert AutomationType.CAMPAIGN_REVIEW in types
        assert AutomationType.PROACTIVE_ALERT in types
        assert AutomationType.MARKETING_AUDIT in types

    def test_campaign_review_rule_with_active_campaigns(self):
        rule = AutomationRule(type=AutomationType.CAMPAIGN_REVIEW)
        assert rule.should_run({"active_campaigns": 3}) is True

    def test_campaign_review_rule_without_active_campaigns(self):
        rule = AutomationRule(type=AutomationType.CAMPAIGN_REVIEW)
        assert rule.should_run({"active_campaigns": 0}) is False

    def test_proactive_alert_rule_with_anomalies(self):
        rule = AutomationRule(type=AutomationType.PROACTIVE_ALERT)
        assert rule.should_run({"anomaly_count": 2}) is True

    def test_proactive_alert_rule_without_anomalies(self):
        rule = AutomationRule(type=AutomationType.PROACTIVE_ALERT)
        assert rule.should_run({"anomaly_count": 0}) is False

    def test_marketing_audit_rule_after_7_days(self):
        rule = AutomationRule(type=AutomationType.MARKETING_AUDIT)
        assert rule.should_run({"days_since_audit": 7}) is True
        assert rule.should_run({"days_since_audit": 3}) is False

    def test_budget_review_rule_over_50_percent(self):
        rule = AutomationRule(type=AutomationType.BUDGET_REVIEW)
        assert rule.should_run({"budget_utilisation": 0.6}) is True
        assert rule.should_run({"budget_utilisation": 0.3}) is False

    def test_content_calendar_always_runs(self):
        rule = AutomationRule(type=AutomationType.CONTENT_CALENDAR)
        assert rule.should_run({}) is True

    def test_disabled_rule_never_runs(self):
        rule = AutomationRule(type=AutomationType.CAMPAIGN_REVIEW, enabled=False)
        assert rule.should_run({"active_campaigns": 10}) is False

    def test_rule_to_dict(self):
        rule = AutomationRule(id="test", name="Test Rule", type=AutomationType.CAMPAIGN_REVIEW)
        d = rule.to_dict()
        assert d["id"] == "test"
        assert d["name"] == "Test Rule"
        assert d["type"] == "campaign_review"


class TestAutomationEngine:
    """Automation engine task creation and lifecycle."""

    def test_evaluate_creates_tasks_for_matching_rules(self):
        engine = AutomationEngine(rules=[
            AutomationRule(id="r1", type=AutomationType.CAMPAIGN_REVIEW),
        ])
        bid = uuid.uuid4()
        tid = uuid.uuid4()
        tasks = engine.evaluate(bid, tid, {"active_campaigns": 2})
        assert len(tasks) == 1
        assert tasks[0].type == AutomationType.CAMPAIGN_REVIEW
        assert tasks[0].brand_id == bid

    def test_evaluate_skips_non_matching_rules(self):
        engine = AutomationEngine(rules=[
            AutomationRule(id="r1", type=AutomationType.CAMPAIGN_REVIEW),
        ])
        tasks = engine.evaluate(uuid.uuid4(), uuid.uuid4(), {"active_campaigns": 0})
        assert len(tasks) == 0

    def test_get_pending_tasks(self):
        engine = AutomationEngine(rules=[
            AutomationRule(id="r1", type=AutomationType.CAMPAIGN_REVIEW),
        ])
        engine.evaluate(uuid.uuid4(), uuid.uuid4(), {"active_campaigns": 1})
        pending = engine.get_pending_tasks()
        assert len(pending) == 1
        assert pending[0].status == AutomationStatus.PENDING

    def test_mark_running(self):
        engine = AutomationEngine(rules=[
            AutomationRule(id="r1", type=AutomationType.CAMPAIGN_REVIEW),
        ])
        tasks = engine.evaluate(uuid.uuid4(), uuid.uuid4(), {"active_campaigns": 1})
        engine.mark_running(tasks[0].id)
        assert tasks[0].status == AutomationStatus.RUNNING
        assert tasks[0].executed_at != ""

    def test_mark_completed(self):
        engine = AutomationEngine(rules=[
            AutomationRule(id="r1", type=AutomationType.CAMPAIGN_REVIEW),
        ])
        tasks = engine.evaluate(uuid.uuid4(), uuid.uuid4(), {"active_campaigns": 1})
        engine.mark_completed(tasks[0].id, {"summary": "All good"})
        assert tasks[0].status == AutomationStatus.COMPLETED
        assert tasks[0].result["summary"] == "All good"

    def test_mark_failed(self):
        engine = AutomationEngine(rules=[
            AutomationRule(id="r1", type=AutomationType.CAMPAIGN_REVIEW),
        ])
        tasks = engine.evaluate(uuid.uuid4(), uuid.uuid4(), {"active_campaigns": 1})
        engine.mark_failed(tasks[0].id, "LLM timeout")
        assert tasks[0].status == AutomationStatus.FAILED
        assert tasks[0].error == "LLM timeout"

    def test_approval_workflow(self):
        engine = AutomationEngine(rules=[
            AutomationRule(id="r1", type=AutomationType.CAMPAIGN_DRAFT, requires_approval=True),
        ])
        tasks = engine.evaluate(uuid.uuid4(), uuid.uuid4(), {"upcoming_events": 1})
        assert tasks[0].requires_approval is True

        engine.mark_awaiting_approval(tasks[0].id)
        assert tasks[0].status == AutomationStatus.AWAITING_APPROVAL

        success = engine.approve(tasks[0].id)
        assert success is True
        assert tasks[0].approved is True
        assert tasks[0].status == AutomationStatus.PENDING

    def test_reject_workflow(self):
        engine = AutomationEngine(rules=[
            AutomationRule(id="r1", type=AutomationType.CAMPAIGN_DRAFT, requires_approval=True),
        ])
        tasks = engine.evaluate(uuid.uuid4(), uuid.uuid4(), {"upcoming_events": 1})
        engine.mark_awaiting_approval(tasks[0].id)

        success = engine.reject(tasks[0].id)
        assert success is True
        assert tasks[0].status == AutomationStatus.SKIPPED

    def test_approve_nonexistent_task_fails(self):
        engine = AutomationEngine()
        assert engine.approve("nonexistent") is False

    def test_get_tasks_for_brand(self):
        engine = AutomationEngine(rules=[
            AutomationRule(id="r1", type=AutomationType.CAMPAIGN_REVIEW),
        ])
        bid = uuid.uuid4()
        engine.evaluate(bid, uuid.uuid4(), {"active_campaigns": 1})
        engine.evaluate(uuid.uuid4(), uuid.uuid4(), {"active_campaigns": 1})
        brand_tasks = engine.get_tasks_for_brand(bid)
        assert len(brand_tasks) == 1


class TestAutomationContext:
    """Automation context builder."""

    async def test_build_context_with_mock_session(self):
        session = MagicMock()
        # Mock the query results
        mock_result1 = MagicMock()
        mock_result1.scalar.return_value = 3
        mock_result2 = MagicMock()
        mock_result2.scalar.return_value = None
        session.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

        context = await build_automation_context(session, uuid.uuid4(), uuid.uuid4())
        assert context["active_campaigns"] == 3
        assert context["days_since_audit"] == 999


class TestDefaultRules:
    """Default automation rules are correctly configured."""

    def test_campaign_review_does_not_require_approval(self):
        rules = create_default_rules()
        review_rule = next(r for r in rules if r.type == AutomationType.CAMPAIGN_REVIEW)
        assert review_rule.requires_approval is False

    def test_campaign_draft_requires_approval(self):
        rules = create_default_rules()
        draft_rule = next(r for r in rules if r.type == AutomationType.CAMPAIGN_DRAFT)
        assert draft_rule.requires_approval is True

    def test_content_calendar_requires_approval(self):
        rules = create_default_rules()
        calendar_rule = next(r for r in rules if r.type == AutomationType.CONTENT_CALENDAR)
        assert calendar_rule.requires_approval is True

    def test_all_rules_have_unique_ids(self):
        rules = create_default_rules()
        ids = [r.id for r in rules]
        assert len(ids) == len(set(ids))
