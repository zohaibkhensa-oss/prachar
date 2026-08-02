"""Integrations package — common interface for all platform integrations."""
from __future__ import annotations

from .base import (
    IntegrationCapability,
    IntegrationHealth,
    IntegrationInfo,
    IntegrationRegistry,
    IntegrationStatus,
    MarketingIntegration,
    SyncResult,
    WebhookEvent,
    WebhookSubscription,
    get_integration_registry,
    register_integration,
)
from .event_bus import IntegrationEventBus, get_event_bus
from .sync_policy import SyncMode, SyncPolicy
from .data_mapping import DataMapping, FieldMapping, get_mapping_registry
from .secrets import CredentialBundle, ConnectionHealthRecord, SecretsVault, get_secrets_vault
from .workflow_engine import (
    ActionType,
    ConditionOperator,
    Workflow,
    WorkflowAction,
    WorkflowCondition,
    WorkflowEngine,
    WorkflowExecution,
    get_workflow_engine,
)

__all__ = [
    # Base
    "IntegrationCapability",
    "IntegrationHealth",
    "IntegrationInfo",
    "IntegrationRegistry",
    "IntegrationStatus",
    "MarketingIntegration",
    "SyncResult",
    "WebhookEvent",
    "WebhookSubscription",
    "get_integration_registry",
    "register_integration",
    # Event bus
    "IntegrationEventBus",
    "get_event_bus",
    # Sync policies
    "SyncMode",
    "SyncPolicy",
    # Data mapping
    "DataMapping",
    "FieldMapping",
    "get_mapping_registry",
    # Secrets
    "CredentialBundle",
    "ConnectionHealthRecord",
    "SecretsVault",
    "get_secrets_vault",
    # Workflow engine
    "ActionType",
    "ConditionOperator",
    "Workflow",
    "WorkflowAction",
    "WorkflowCondition",
    "WorkflowEngine",
    "WorkflowExecution",
    "get_workflow_engine",
]
