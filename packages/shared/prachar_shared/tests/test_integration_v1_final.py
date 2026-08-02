"""Tests for Integration v1 finalisation — Sync Policies, Data Mapping, Secrets, Workflow Engine."""
from __future__ import annotations

import asyncio
import json
import pytest
from datetime import datetime, timedelta, timezone

from prachar_shared.integrations import (
    # Sync policies
    SyncMode, SyncPolicy,
    # Data mapping
    DataMapping, FieldMapping, get_mapping_registry,
    # Secrets
    CredentialBundle, SecretsVault,
    # Workflow engine
    Workflow, WorkflowAction, WorkflowCondition, WorkflowExecution,
    ActionType, ConditionOperator, WorkflowEngine,
)
from prachar_shared.integrations.workflow_engine import get_workflow_engine


# ─── Sync Policy Tests ──────────────────────────────────────────────────────


class TestSyncMode:
    def test_all_modes_exist(self):
        assert SyncMode.REALTIME
        assert SyncMode.WEBHOOK
        assert SyncMode.POLLING
        assert SyncMode.MANUAL
        assert SyncMode.SCHEDULE
        assert SyncMode.DISABLED

    def test_mode_values(self):
        assert SyncMode.REALTIME.value == "realtime"
        assert SyncMode.POLLING.value == "polling"
        assert SyncMode.DISABLED.value == "disabled"


class TestSyncPolicy:
    def test_default_for_ecommerce(self):
        policy = SyncPolicy.default_for("shopify", "ecommerce")
        assert policy.integration == "shopify"
        assert policy.mode == SyncMode.REALTIME

    def test_default_for_analytics(self):
        policy = SyncPolicy.default_for("ga4", "analytics")
        assert policy.mode == SyncMode.POLLING
        assert policy.poll_interval_seconds == 3600

    def test_default_for_cms(self):
        policy = SyncPolicy.default_for("wordpress", "cms")
        assert policy.mode == SyncMode.MANUAL

    def test_default_for_crm(self):
        policy = SyncPolicy.default_for("hubspot", "crm")
        assert policy.mode == SyncMode.POLLING
        assert policy.poll_interval_seconds == 900

    def test_default_for_email(self):
        policy = SyncPolicy.default_for("mailchimp", "email")
        assert policy.mode == SyncMode.POLLING

    def test_should_sync_disabled(self):
        policy = SyncPolicy(integration="test", mode=SyncMode.DISABLED)
        assert policy.should_sync() is False

    def test_should_sync_manual(self):
        policy = SyncPolicy(integration="test", mode=SyncMode.MANUAL)
        assert policy.should_sync() is False

    def test_should_sync_realtime(self):
        policy = SyncPolicy(integration="test", mode=SyncMode.REALTIME)
        assert policy.should_sync() is True

    def test_should_sync_polling_no_history(self):
        policy = SyncPolicy(integration="test", mode=SyncMode.POLLING, poll_interval_seconds=60)
        assert policy.should_sync() is True

    def test_should_sync_polling_recent_sync(self):
        policy = SyncPolicy(integration="test", mode=SyncMode.POLLING, poll_interval_seconds=3600)
        policy.last_sync_at = datetime.now(timezone.utc)
        assert policy.should_sync() is False

    def test_should_sync_polling_expired(self):
        policy = SyncPolicy(integration="test", mode=SyncMode.POLLING, poll_interval_seconds=60)
        policy.last_sync_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        assert policy.should_sync() is True

    def test_record_success(self):
        policy = SyncPolicy(integration="test", mode=SyncMode.POLLING)
        policy.record_success(synced_count=50)
        assert policy.total_syncs == 1
        assert policy.successful_syncs == 1
        assert policy.last_successful_sync_at is not None
        assert policy.last_error == ""

    def test_record_failure(self):
        policy = SyncPolicy(integration="test", mode=SyncMode.POLLING)
        policy.record_failure("Connection timeout")
        assert policy.total_syncs == 1
        assert policy.failed_syncs == 1
        assert policy.last_error == "Connection timeout"
        assert policy.last_failed_sync_at is not None

    def test_success_rate(self):
        policy = SyncPolicy(integration="test")
        policy.record_success()
        policy.record_success()
        policy.record_failure("error")
        assert policy.success_rate == pytest.approx(66.67, abs=0.1)

    def test_to_dict_and_from_dict_roundtrip(self):
        policy = SyncPolicy(integration="shopify", mode=SyncMode.POLLING, poll_interval_seconds=300)
        policy.record_success(100)
        d = policy.to_dict()
        restored = SyncPolicy.from_dict(d)
        assert restored.integration == "shopify"
        assert restored.mode == SyncMode.POLLING
        assert restored.poll_interval_seconds == 300
        assert restored.total_syncs == 1
        assert restored.successful_syncs == 1


# ─── Data Mapping Tests ─────────────────────────────────────────────────────


class TestDataMapping:
    def test_field_mapping_basic(self):
        m = FieldMapping("lifecyclestage", "lead_stage")
        assert m.to_canonical("subscriber") == "subscriber"

    def test_field_mapping_with_transform(self):
        m = FieldMapping("lifecyclestage", "lead_stage",
                         transform=lambda v: {"subscriber": "lead", "customer": "customer"}.get(v, "lead"))
        assert m.to_canonical("subscriber") == "lead"
        assert m.to_canonical("customer") == "customer"
        assert m.to_canonical("unknown") == "lead"

    def test_field_mapping_with_default(self):
        m = FieldMapping("missing_field", "canonical_field", default="default_val")
        assert m.to_canonical(None) == "default_val"

    def test_data_mapping_to_canonical(self):
        dm = DataMapping(integration="hubspot")
        dm.add(FieldMapping("lifecyclestage", "lead_stage"))
        dm.add(FieldMapping("email", "contact.email"))
        result = dm.to_canonical({"lifecyclestage": "subscriber", "email": "test@example.com"})
        assert result["lead_stage"] == "subscriber"
        assert result["contact.email"] == "test@example.com"

    def test_data_mapping_unmapped_fields_pass_through(self):
        dm = DataMapping(integration="test")
        dm.add(FieldMapping("a", "canonical_a"))
        result = dm.to_canonical({"a": 1, "b": 2})
        assert result["canonical_a"] == 1
        assert result["_raw.b"] == 2

    def test_data_mapping_to_external(self):
        dm = DataMapping(integration="hubspot")
        dm.add(FieldMapping("lifecyclestage", "lead_stage"))
        result = dm.to_external({"lead_stage": "customer"})
        assert result["lifecyclestage"] == "customer"

    def test_custom_mapping_overrides_default(self):
        dm = DataMapping(integration="hubspot")
        dm.add(FieldMapping("lifecyclestage", "lead_stage"))
        dm.add_custom(FieldMapping("lifecyclestage", "custom_stage"))
        result = dm.to_canonical({"lifecyclestage": "subscriber"})
        assert result["custom_stage"] == "subscriber"
        assert "lead_stage" not in result

    def test_list_mappings(self):
        dm = DataMapping(integration="hubspot")
        dm.add(FieldMapping("a", "canonical_a"))
        dm.add_custom(FieldMapping("b", "canonical_b"))
        mappings = dm.list_mappings()
        assert len(mappings) == 2
        custom = [m for m in mappings if m["is_custom"]]
        assert len(custom) == 1
        assert custom[0]["external_field"] == "b"


class TestDefaultMappings:
    """Test the pre-registered default mappings."""

    def test_hubspot_mapping(self):
        registry = get_mapping_registry()
        dm = registry.get_default("hubspot")
        assert dm is not None
        result = dm.to_canonical({"lifecyclestage": "subscriber", "email": "test@example.com"})
        assert result["lead_stage"] == "lead"
        assert result["contact.email"] == "test@example.com"

    def test_shopify_mapping(self):
        registry = get_mapping_registry()
        dm = registry.get_default("shopify")
        assert dm is not None
        result = dm.to_canonical({"tags": "vip, premium", "total_price": "99.00", "financial_status": "paid"})
        assert result["audience_segments"] == ["vip", "premium"]
        assert result["order_value"] == 99.0
        assert result["order_status"] == "paid"

    def test_ga4_mapping(self):
        registry = get_mapping_registry()
        dm = registry.get_default("google_analytics")
        assert dm is not None
        result = dm.to_canonical({"sessions": "1234", "totalUsers": "567", "conversions": "10"})
        assert result["analytics.sessions"] == 1234.0
        assert result["analytics.users"] == 567.0
        assert result["campaign_kpi.conversions"] == 10.0

    def test_mailchimp_mapping(self):
        registry = get_mapping_registry()
        dm = registry.get_default("mailchimp")
        assert dm is not None
        result = dm.to_canonical({"open_rate": 0.25, "click_rate": 0.05})
        assert result["email_metrics.open_rate"] == 0.25
        assert result["email_metrics.click_rate"] == 0.05

    def test_wordpress_mapping(self):
        registry = get_mapping_registry()
        dm = registry.get_default("wordpress")
        assert dm is not None
        result = dm.to_canonical({"title": "My Post", "status": "publish"})
        assert result["content.title"] == "My Post"
        assert result["content.status"] == "published"

    def test_all_five_mappings_registered(self):
        registry = get_mapping_registry()
        defaults = registry.all_defaults()
        assert "hubspot" in defaults
        assert "shopify" in defaults
        assert "google_analytics" in defaults
        assert "mailchimp" in defaults
        assert "wordpress" in defaults


# ─── Secrets Management Tests ───────────────────────────────────────────────


class TestCredentialBundle:
    def test_is_expired_no_expiry(self):
        creds = CredentialBundle(access_token="test")
        assert creds.is_expired() is False

    def test_is_expired_past(self):
        creds = CredentialBundle(
            access_token="test",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert creds.is_expired() is True

    def test_is_expired_future(self):
        creds = CredentialBundle(
            access_token="test",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert creds.is_expired() is False

    def test_expires_within(self):
        creds = CredentialBundle(
            access_token="test",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
        )
        assert creds.expires_within(hours=24) is True
        assert creds.expires_within(hours=6) is False

    def test_to_dict_excludes_tokens_by_default(self):
        creds = CredentialBundle(access_token="secret", refresh_token="refresh_secret")
        d = creds.to_dict()
        assert "access_token" not in d
        assert "refresh_token" not in d
        assert d["has_refresh_token"] is True

    def test_to_dict_includes_tokens_when_requested(self):
        creds = CredentialBundle(access_token="secret")
        d = creds.to_dict(include_tokens=True)
        assert d["access_token"] == "secret"


class TestSecretsVault:
    def test_store_and_retrieve(self):
        vault = SecretsVault("test-encryption-key")
        creds = CredentialBundle(
            access_token="ya29.test_token",
            refresh_token="refresh_abc",
            scopes=["analytics.readonly"],
        )
        vault.store("conn_123", creds)
        retrieved = vault.retrieve("conn_123")
        assert retrieved is not None
        assert retrieved.access_token == "ya29.test_token"
        assert retrieved.refresh_token == "refresh_abc"
        assert "analytics.readonly" in retrieved.scopes

    def test_retrieve_nonexistent(self):
        vault = SecretsVault("test-key")
        assert vault.retrieve("nonexistent") is None

    def test_delete(self):
        vault = SecretsVault("test-key")
        vault.store("conn_1", CredentialBundle(access_token="test"))
        assert vault.has_credentials("conn_1")
        vault.delete("conn_1")
        assert not vault.has_credentials("conn_1")

    def test_encrypted_at_rest(self):
        """Credentials should not be stored in plaintext."""
        vault = SecretsVault("test-key")
        vault.store("conn_1", CredentialBundle(access_token="plaintext_secret"))
        # The internal storage should not contain the plaintext
        import json
        for stored in vault._credentials.values():
            assert "plaintext_secret" not in stored

    def test_record_sync(self):
        vault = SecretsVault("test-key")
        vault.store("conn_1", CredentialBundle(access_token="test"))
        vault.record_sync("conn_1", success=True)
        vault.record_sync("conn_1", success=True)
        vault.record_sync("conn_1", success=False, error="Timeout")
        health = vault.get_health("conn_1")
        assert health.total_syncs == 3
        assert health.successful_syncs == 2
        assert health.failed_syncs == 1
        assert health.last_error == "Timeout"

    def test_record_refresh(self):
        vault = SecretsVault("test-key")
        vault.store("conn_1", CredentialBundle(access_token="test"))
        vault.record_refresh("conn_1", success=True, new_expiry=datetime.now(timezone.utc) + timedelta(hours=1))
        health = vault.get_health("conn_1")
        assert len(health.refresh_history) == 1
        assert health.refresh_history[0].success is True
        assert health.last_refresh_success is True

    def test_expiring_within(self):
        vault = SecretsVault("test-key")
        vault.store("conn_expiring", CredentialBundle(
            access_token="test",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
        ))
        vault.store("conn_ok", CredentialBundle(
            access_token="test",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        ))
        vault.store("conn_no_expiry", CredentialBundle(access_token="test"))
        expiring = vault.expiring_within(hours=24)
        assert "conn_expiring" in expiring
        assert "conn_ok" not in expiring
        assert "conn_no_expiry" not in expiring

    def test_expired(self):
        vault = SecretsVault("test-key")
        vault.store("conn_expired", CredentialBundle(
            access_token="test",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        ))
        vault.store("conn_valid", CredentialBundle(
            access_token="test",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        expired = vault.expired()
        assert "conn_expired" in expired
        assert "conn_valid" not in expired

    def test_all_health(self):
        vault = SecretsVault("test-key")
        vault.store("conn_1", CredentialBundle(access_token="test", scopes=["read"]))
        vault.record_sync("conn_1", success=True)
        all_health = vault.all_health()
        assert len(all_health) == 1
        assert all_health[0]["connection_id"] == "conn_1"
        assert "read" in all_health[0]["permission_scopes"]


# ─── Workflow Engine Tests ──────────────────────────────────────────────────


class TestWorkflowCondition:
    def test_equals(self):
        cond = WorkflowCondition("payload.status", ConditionOperator.EQUALS, "paid")
        assert cond.evaluate({"payload": {"status": "paid"}}) is True
        assert cond.evaluate({"payload": {"status": "pending"}}) is False

    def test_not_equals(self):
        cond = WorkflowCondition("payload.status", ConditionOperator.NOT_EQUALS, "paid")
        assert cond.evaluate({"payload": {"status": "pending"}}) is True
        assert cond.evaluate({"payload": {"status": "paid"}}) is False

    def test_contains(self):
        cond = WorkflowCondition("payload.tags", ConditionOperator.CONTAINS, "vip")
        assert cond.evaluate({"payload": {"tags": ["vip", "premium"]}}) is True
        assert cond.evaluate({"payload": {"tags": ["standard"]}}) is False

    def test_is_empty(self):
        cond = WorkflowCondition("payload.email", ConditionOperator.IS_EMPTY)
        assert cond.evaluate({"payload": {"email": ""}}) is True
        assert cond.evaluate({"payload": {"email": "test@example.com"}}) is False

    def test_is_not_empty(self):
        cond = WorkflowCondition("payload.email", ConditionOperator.IS_NOT_EMPTY)
        assert cond.evaluate({"payload": {"email": "test@example.com"}}) is True
        assert cond.evaluate({"payload": {"email": ""}}) is False

    def test_greater_than(self):
        cond = WorkflowCondition("payload.amount", ConditionOperator.GREATER_THAN, 100)
        assert cond.evaluate({"payload": {"amount": 150}}) is True
        assert cond.evaluate({"payload": {"amount": 50}}) is False

    def test_in(self):
        cond = WorkflowCondition("payload.country", ConditionOperator.IN, ["US", "UK", "IN"])
        assert cond.evaluate({"payload": {"country": "US"}}) is True
        assert cond.evaluate({"payload": {"country": "DE"}}) is False

    def test_missing_field(self):
        cond = WorkflowCondition("payload.nonexistent", ConditionOperator.EQUALS, "x")
        assert cond.evaluate({"payload": {}}) is False


class TestWorkflow:
    def test_matches_trigger_exact(self):
        wf = Workflow(
            id="test", name="Test",
            trigger_integration="shopify",
            trigger_event_type="orders/create",
        )
        from prachar_shared.integrations import WebhookEvent
        event = WebhookEvent("shopify", "orders/create", "1", "order")
        assert wf.matches_trigger(event) is True

    def test_matches_trigger_wrong_integration(self):
        wf = Workflow(
            id="test", name="Test",
            trigger_integration="shopify",
            trigger_event_type="orders/create",
        )
        from prachar_shared.integrations import WebhookEvent
        event = WebhookEvent("hubspot", "orders/create", "1", "order")
        assert wf.matches_trigger(event) is False

    def test_matches_trigger_wildcard(self):
        wf = Workflow(
            id="test", name="Test",
            trigger_integration="*",
            trigger_event_type="*",
        )
        from prachar_shared.integrations import WebhookEvent
        event = WebhookEvent("anything", "any_event", "1", "any")
        assert wf.matches_trigger(event) is True

    def test_matches_trigger_inactive(self):
        wf = Workflow(
            id="test", name="Test",
            trigger_integration="*",
            trigger_event_type="*",
            is_active=False,
        )
        from prachar_shared.integrations import WebhookEvent
        event = WebhookEvent("anything", "any", "1", "any")
        assert wf.matches_trigger(event) is False

    def test_to_dict(self):
        wf = Workflow(
            id="test", name="Test Workflow",
            trigger_integration="shopify",
            trigger_event_type="orders/create",
            conditions=[WorkflowCondition("payload.is_new", ConditionOperator.EQUALS, True)],
            actions=[WorkflowAction(ActionType.SEND_EMAIL, "Welcome email")],
        )
        d = wf.to_dict()
        assert d["id"] == "test"
        assert d["trigger_integration"] == "shopify"
        assert len(d["conditions"]) == 1
        assert len(d["actions"]) == 1


class TestWorkflowEngine:
    def test_register_and_execute(self):
        engine = WorkflowEngine()
        executed_actions: list[str] = []

        @engine.executor(ActionType.NOTIFY_USER)
        async def notify(action, context):
            executed_actions.append(action.name)
            return {"notified": True}

        wf = Workflow(
            id="test_wf", name="Test",
            trigger_integration="shopify",
            trigger_event_type="orders/create",
            actions=[
                WorkflowAction(ActionType.NOTIFY_USER, "Notify founder"),
            ],
        )
        engine.register_workflow(wf)

        from prachar_shared.integrations import WebhookEvent
        event = WebhookEvent("shopify", "orders/create", "123", "order", {"is_new": True})
        execution = asyncio.run(engine.execute_workflow(wf, event))

        assert execution.status == "success"
        assert execution.actions_executed == 1
        assert executed_actions == ["Notify founder"]

    def test_conditions_not_met_skips(self):
        engine = WorkflowEngine()

        wf = Workflow(
            id="test_wf", name="Test",
            trigger_integration="shopify",
            trigger_event_type="orders/create",
            conditions=[
                WorkflowCondition("payload.is_first_order", ConditionOperator.EQUALS, True),
            ],
            actions=[WorkflowAction(ActionType.NOTIFY_USER, "Notify")],
        )
        engine.register_workflow(wf)

        from prachar_shared.integrations import WebhookEvent
        event = WebhookEvent("shopify", "orders/create", "123", "order", {"is_first_order": False})
        execution = asyncio.run(engine.execute_workflow(wf, event))

        assert execution.status == "skipped"
        assert execution.conditions_met is False
        assert execution.actions_executed == 0

    def test_action_failure_with_continue(self):
        engine = WorkflowEngine()

        @engine.executor(ActionType.SEND_EMAIL)
        async def failing_email(action, context):
            raise ValueError("Email service down")

        @engine.executor(ActionType.NOTIFY_USER)
        async def notify(action, context):
            return {"notified": True}

        wf = Workflow(
            id="test_wf", name="Test",
            trigger_integration="shopify",
            trigger_event_type="orders/create",
            actions=[
                WorkflowAction(ActionType.SEND_EMAIL, "Welcome email", continue_on_error=True),
                WorkflowAction(ActionType.NOTIFY_USER, "Notify founder"),
            ],
        )
        engine.register_workflow(wf)

        from prachar_shared.integrations import WebhookEvent
        event = WebhookEvent("shopify", "orders/create", "123", "order")
        execution = asyncio.run(engine.execute_workflow(wf, event))

        assert execution.actions_executed == 1  # Only notify succeeded
        assert execution.actions_failed == 1
        assert execution.status == "partial"

    def test_action_failure_without_continue(self):
        engine = WorkflowEngine()

        @engine.executor(ActionType.SEND_EMAIL)
        async def failing_email(action, context):
            raise ValueError("Email service down")

        @engine.executor(ActionType.NOTIFY_USER)
        async def notify(action, context):
            return {"notified": True}

        wf = Workflow(
            id="test_wf", name="Test",
            trigger_integration="shopify",
            trigger_event_type="orders/create",
            actions=[
                WorkflowAction(ActionType.SEND_EMAIL, "Welcome email", continue_on_error=False),
                WorkflowAction(ActionType.NOTIFY_USER, "Notify founder"),
            ],
        )
        engine.register_workflow(wf)

        from prachar_shared.integrations import WebhookEvent
        event = WebhookEvent("shopify", "orders/create", "123", "order")
        execution = asyncio.run(engine.execute_workflow(wf, event))

        assert execution.status == "failed"
        assert execution.actions_executed == 0  # Notify never ran

    def test_no_executor_registered(self):
        engine = WorkflowEngine()
        wf = Workflow(
            id="test_wf", name="Test",
            trigger_integration="shopify",
            trigger_event_type="orders/create",
            actions=[WorkflowAction(ActionType.SEND_EMAIL, "Email")],
        )
        engine.register_workflow(wf)

        from prachar_shared.integrations import WebhookEvent
        event = WebhookEvent("shopify", "orders/create", "123", "order")
        execution = asyncio.run(engine.execute_workflow(wf, event))

        assert execution.status == "success"  # continue_on_error defaults to True
        assert execution.actions_executed == 0
        assert len(execution.errors) == 1

    def test_execution_history(self):
        engine = WorkflowEngine()

        @engine.executor(ActionType.LOG_EVENT)
        async def log_action(action, context):
            return {"logged": True}

        wf = Workflow(
            id="test_wf", name="Test",
            trigger_integration="*",
            trigger_event_type="*",
            actions=[WorkflowAction(ActionType.LOG_EVENT, "Log")],
        )
        engine.register_workflow(wf)

        from prachar_shared.integrations import WebhookEvent
        for i in range(3):
            event = WebhookEvent("shopify", "orders/create", str(i), "order")
            asyncio.run(engine.execute_workflow(wf, event))

        history = engine.execution_history()
        assert len(history) == 3

    def test_stats(self):
        engine = WorkflowEngine()

        @engine.executor(ActionType.LOG_EVENT)
        async def log_action(action, context):
            return {"logged": True}

        engine.register_workflow(Workflow(
            id="wf1", name="WF1",
            trigger_integration="*",
            trigger_event_type="*",
            actions=[WorkflowAction(ActionType.LOG_EVENT, "Log")],
        ))

        from prachar_shared.integrations import WebhookEvent
        event = WebhookEvent("test", "test", "1", "test")
        asyncio.run(engine.execute_workflow(engine.get_workflow("wf1"), event))

        stats = engine.stats()
        assert stats["total_workflows"] == 1
        assert stats["total_executions"] == 1
        assert stats["successful_executions"] == 1

    def test_welcome_new_customer_workflow(self):
        """End-to-end: Shopify order → check if new → send email + create CRM contact."""
        engine = WorkflowEngine()
        actions_taken: list[str] = []

        @engine.executor(ActionType.SEND_EMAIL)
        async def send_email(action, context):
            actions_taken.append(f"email:{action.config.get('template', 'default')}")
            return {"campaign_id": "mc_123", "sent": True}

        @engine.executor(ActionType.CREATE_CRM_CONTACT)
        async def create_contact(action, context):
            actions_taken.append(f"crm:{action.config.get('object_type', 'contact')}")
            return {"contact_id": "hs_456", "created": True}

        @engine.executor(ActionType.NOTIFY_USER)
        async def notify(action, context):
            actions_taken.append(f"notify:{action.config.get('channel', 'email')}")
            return {"notified": True}

        wf = Workflow(
            id="welcome_new_customer",
            name="Welcome New Customer",
            description="When a new customer places their first Shopify order, send welcome email, create CRM contact, and notify founder.",
            trigger_integration="shopify",
            trigger_event_type="orders/create",
            conditions=[
                WorkflowCondition("payload.is_first_order", ConditionOperator.EQUALS, True),
            ],
            actions=[
                WorkflowAction(ActionType.SEND_EMAIL, "Welcome email",
                               config={"template": "welcome_new_customer", "list_id": "abc123"}),
                WorkflowAction(ActionType.CREATE_CRM_CONTACT, "Create HubSpot contact",
                               config={"object_type": "contact"}),
                WorkflowAction(ActionType.NOTIFY_USER, "Notify founder",
                               config={"channel": "whatsapp"}),
            ],
        )
        engine.register_workflow(wf)

        from prachar_shared.integrations import WebhookEvent

        # First order from new customer → workflow executes
        event = WebhookEvent(
            "shopify", "orders/create", "order_001", "order",
            {"is_first_order": True, "customer_email": "new@example.com", "total_price": "99.00"},
        )
        execution = asyncio.run(engine.execute_workflow(wf, event))
        assert execution.status == "success"
        assert execution.actions_executed == 3
        assert "email:welcome_new_customer" in actions_taken
        assert "crm:contact" in actions_taken
        assert "notify:whatsapp" in actions_taken

        # Repeat order → workflow skips (condition not met)
        actions_taken.clear()
        event2 = WebhookEvent(
            "shopify", "orders/create", "order_002", "order",
            {"is_first_order": False, "customer_email": "new@example.com", "total_price": "50.00"},
        )
        execution2 = asyncio.run(engine.execute_workflow(wf, event2))
        assert execution2.status == "skipped"
        assert len(actions_taken) == 0
