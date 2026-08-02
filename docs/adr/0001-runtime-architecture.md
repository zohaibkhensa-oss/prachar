# ADR-0001: Runtime Architecture

**Status:** Accepted
**Date:** 2026-08-02

## Context

PRACHAR AI needs an execution layer that takes a user message, classifies intent, plans a tool execution graph, executes tools in parallel/sequence, composes a response, and streams events to the frontend. This must be tenant-isolated, observable, and resilient to tool failures.

## Decision

The Runtime is a 7-stage pipeline:

1. **Session creation** — `SessionManager` creates a session ID + event bus
2. **Context assembly** — `ContextBuilder` loads relevant providers (see ADR-0003)
3. **Intent classification** — LLM classifies the message into an intent
4. **Planning** — `Planner` produces an `ExecutionGraph` (DAG of tool calls)
5. **Decision contract** — `DecisionContract` captures goal, reasoning, tools, cost estimate
6. **Timeline append** — Decision is immutably recorded (see ADR-0006)
7. **Execution** — `Executor` runs tools with retries, streams events via SSE

Key invariants:
- Every tool call goes through the Tool Registry (see ADR-0002)
- Every decision is recorded in the Timeline (immutable, append-only)
- Every AI request is logged by the Observability layer
- Session state is held in memory; DB sessions are per-request
- `user.tenant_id` and `user.id` are captured before any DB operation to avoid lazy-load failures after rollback

## Consequences

- Tool failures are isolated — one tool failing does not crash the session
- The Timeline provides full auditability and replay capability
- Observability provides per-request cost, latency, and success tracking
- The Runtime is the single entry point for all AI work — no bypassing

## Components

| Component | File | Responsibility |
|-----------|------|----------------|
| Runtime | `runtime/runtime.py` | Orchestrates the 7-stage pipeline |
| Planner | `runtime/planner.py` | Produces execution graphs from intent + context |
| Composer | `runtime/composer.py` | Composes user-facing response from tool outputs |
| Executor | `runtime/executor.py` | Runs tools with retries, emits events |
| SessionManager | `runtime/session.py` | Manages session state + event bus |
| EventReplay | `runtime/event_replay.py` | Persists runtime events to DB |
| Observability | `ai_gateway/observability.py` | Logs every AI request with metrics |

## Frozen

This architecture is frozen. New AI capabilities must be added as tools in the Tool Registry, not as new runtime stages.
