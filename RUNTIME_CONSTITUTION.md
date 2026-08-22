# CURV AI Runtime Constitution

> The behavioural contract of the Runtime. Every engineer follows it.
> Architecture Freeze v2.0 — APPROVED. Do not change unless a fundamental flaw is found.

---

## Rule 1 — Single Entry Point

The Runtime is the only public AI entry point.

Never call CampaignBrain, Agency Council, Creative Studio, or Review directly from the frontend.

```
Frontend → Runtime → Tools
```

---

## Rule 2 — Tool Isolation

Tools never know about each other. Only the Planner coordinates them.

---

## Rule 3 — Decision Contract

Every execution creates exactly one Decision Contract. Never execute work without one.

---

## Rule 4 — Timeline is Mandatory

Every Decision creates Timeline entries. Nothing happens outside the Timeline.

---

## Rule 5 — Replayability

Every Timeline event is replayable. No exceptions.

---

## Rule 6 — Tool Manifests

Every tool must expose a Tool Manifest. No hidden behaviour.

---

## Rule 7 — Planner Reasons from Manifests

Never hard-code intent→tool mappings. The Planner discovers capabilities through the Tool Registry.

---

## Rule 8 — Events Always

Everything emits Runtime Events. No silent execution.

---

## Rule 9 — CURV AI Owns the Conversation

Internal engines are invisible. Users never see CampaignBrain, Council, or Creative. They only see CURV AI.

---

## Rule 10 — Shared Memory

No tool owns memory. The Runtime owns memory.

---

## Rule 11 — Runtime Owns Approval

CampaignBrain doesn't ask for approval. Creative Studio doesn't ask for approval. Runtime decides.

---

## Rule 12 — Runtime Owns Cancellation

Any task must be cancellable. Cancellation belongs to the Runtime.

---

## Rule 13 — Unified Streaming

Streaming belongs to the Event Bus. Never build individual streaming logic. Everything streams through Runtime Events.

---

## Rule 14 — Immutable Timeline

The Workspace Timeline is immutable. Never edit history. Only append. Like Git.

---

## Rule 15 — Explainability

Every response is explainable. Every recommendation traces back to the Decision Contract.

---

## Phase A Split

### Phase A.1 — Infrastructure (no UI)
- Runtime service
- Tool Registry
- Planner
- Decision Contract
- Event Bus
- Timeline
- Session management

### Phase A.2 — Experience (UI wiring)
- Orb integration
- Voice
- Streaming UI
- Response Composer
- Dashboard Overview
- Workspace updates

Validate the runtime independently before connecting the new experience.

---

## Discipline

The architecture is frozen. New capabilities are added through the Tool Registry and Runtime. Avoid bypassing the Runtime for convenience, even if an existing endpoint seems tempting.
