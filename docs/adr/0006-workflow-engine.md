# ADR-0006: Workflow Engine & Event Bus

**Status:** Accepted
**Date:** 2026-08-02

## Context

PRACHAR AI runs autonomous weekly loops (measure → diagnose → generate → review → publish → report). It needs a way to define rules, trigger actions on events, and track what happened. This must be observable, replayable, and resilient.

## Decision

Two systems:

### Event Bus
- In-process pub/sub for domain events (BusinessAnalysed, CampaignCompleted, LearningStored, etc.)
- Events are typed (11 domain event classes)
- Subscribers react to events (e.g., store learning when campaign completes)
- Events are persisted to `RuntimeEventRecord` for replay

### Workflow Engine
- `Automation` model defines rules (trigger → condition → action)
- `AutomationTask` model tracks task execution (pending, running, completed, failed)
- Triggers: schedule (cron), event, manual
- Actions: call a tool, call an adapter, send a notification
- The weekly loop is a workflow that chains all steps

### Timeline
- `WorkspaceTimeline` is immutable, append-only
- Every decision, every action, every output is recorded
- Entries are replayable (replay_inputs stored)
- RLS-protected per tenant
- `SET LOCAL app.tenant_id` must be re-set after any session rollback (transaction-scoped)

## Consequences

- Full auditability — every action is traceable
- Replayability — any past decision can be replayed
- The Orb sees workflow state via `WorkflowContextProvider` + `workflow.query` tool
- The Orb sees history via `TimelineContextProvider` + `timeline.query` tool
- Adding a new automation = defining a rule. No engine changes.

## Frozen

The Event Bus, Workflow Engine, and Timeline are frozen. New automations must be defined as rules, not as new scheduling mechanisms. New events must be added to the existing event bus, not a parallel one.
