# Realtime Architecture — Staging Deployment

## Current Architecture

CURV AI uses **Server-Sent Events (SSE)** for all realtime communication.
There are no WebSockets in the stack.

### Components

| Component | Location | Scope |
|-----------|----------|-------|
| EventBus | `packages/shared/prachar_shared/event_bus.py` | Process-local |
| SessionManager | `packages/shared/prachar_shared/runtime/session.py` | Process-local |
| SSE endpoints | `apps/api/prachar_api/routers/runtime.py` | Per-request |
| Audit event stream | `apps/api/prachar_api/routers/audits.py` | Per-request |

### How SSE Works

1. Client opens `GET /runtime/{session_id}/stream` (SSE connection)
2. Server holds the connection open and streams events
3. Events are published to the process-local EventBus
4. The SSE handler subscribes to the EventBus and forwards events to the client
5. Connection closes when the session completes or client disconnects

## Staging Deployment: Single API Replica

For the initial staging deployment, the API runs as a **single Fargate task**
(`api_desired_count = 1`). This means:

- **All SSE connections hit the same process**
- **EventBus is process-local → all subscribers see all events**
- **No cross-instance event loss**
- **No Redis pub/sub needed**

This is the simplest correct configuration and works perfectly for staging.

## Production: Multi-Replica Considerations

When scaling to `api_desired_count >= 2`, the process-local EventBus becomes
a problem:

1. User opens SSE connection to replica A
2. A tool execution on replica B publishes an event to its local EventBus
3. Replica A's SSE handler never sees the event → user misses updates

### Solutions (NOT implemented in this phase — documented for future)

**Option A: Sticky Sessions (ALB)**
- Configure ALB target group with `stickiness.type = lb_cookie`
- All requests from a given user route to the same replica
- EventBus stays process-local but the user always hits the same process
- **Pros**: No code changes, minimal infrastructure changes
- **Cons**: Uneven load distribution, session migration on deploy

**Option B: Redis Pub/Sub**
- Replace process-local EventBus with Redis pub/sub
- All replicas subscribe to a Redis channel
- Events published to Redis are received by all replicas
- **Pros**: True multi-replica support, no sticky sessions needed
- **Cons**: Requires EventBus refactor (architecture freeze consideration)

**Option C: EventBridge + SQS**
- Publish events to EventBridge
- Each replica has its own SQS queue
- **Pros**: Durable, scalable, AWS-native
- **Cons**: High latency, over-engineered for current needs

### Recommendation

For staging: **single replica** (current architecture, no changes needed).

For initial production: **sticky sessions** (Option A) — minimal changes,
works with the architecture freeze.

For scale: **Redis pub/sub** (Option B) — requires ADR and architecture
freeze review before implementing.

## ALB Configuration

The Terraform ALB is configured with:
- `idle_timeout = 120` seconds (raised from default 60s for SSE)
- HTTPS listener with TLS 1.2+ (regional ACM certificate)
- HTTP listener redirects to HTTPS

For SSE to work correctly:
- ALB must NOT buffer responses (default behavior is fine)
- Connection draining should be enabled (default in AWS)
- The 120s idle timeout allows long-running SSE streams

## What NOT to Claim

- Do NOT claim multi-replica realtime support if EventBus remains process-local
- Do NOT claim Redis pub/sub is in use unless it's actually implemented
- The staging deployment is explicitly **single-replica** to avoid these issues
