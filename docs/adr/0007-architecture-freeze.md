# ADR-0007: Architecture Freeze (v1)

**Status:** Accepted
**Date:** 2026-08-02

## Context

PRACHAR AI has reached architectural completeness. All core subsystems are implemented, tested, and integrated. The Orb has 16/16 context provider coverage and 30 tools. 756 tests pass. The question is no longer "what architecture remains?" but "what prevents launch?"

Continuing to design new abstractions at this stage risks:
- Architecture bloat (competing systems doing the same thing)
- Integration debt (new systems that don't connect to the Orb)
- Delayed launch (designing instead of shipping)

## Decision

**PRACHAR AI v1 architecture is FROZEN as of 2026-08-02.**

### No New Core Abstractions Rule

Any proposed feature MUST plug into one of these existing systems:

| New Feature | Must Plug Into |
|-------------|----------------|
| AI capability | Tool Registry |
| Memory | Knowledge Hub / Business Memory |
| Context | Context Builder (add a provider) |
| Automation | Workflow Engine |
| External service | Integration Framework (add an adapter) |
| Intelligence | Context Providers |
| Review process | Review System |
| Events | Event Bus |
| Learning | Feedback Store / Context Ranking |
| Scheduling | Runtime |
| Attribution | Attribution Engine |
| Campaign intelligence | Campaign Brain / Agency Council |
| Creative generation | Creative Studio |
| Domain config | Domain Packs |
| Billing | Billing router + Billing model |
| Auth | Auth router + JWT middleware |

### Frozen Components (do not redesign)

Runtime, Planner, Composer, Tool Registry, Session State, Runtime Events, Observability, Context Builder, Context Ranking, Adaptive Ranking, Context Evaluation, Feedback Loop, Business Memory, Knowledge Hub, Attribution, Campaign Brain, Creative Studio, Performance Engine, Audit Engine, Agency Council, Domain Packs, Review System, Integrations, Event Bus, Workflow Engine, Secrets Vault, Sync Policies, Data Mapping, Webhooks, Billing, Auth, Multi-workspace, API Tokens, Brand Isolation, White-label, Orb (16 context providers, 30 tools).

Database schema is additive-only: new migrations are allowed, destructive changes require explicit approval.

### v2 Admission Rule

A proposal may only become a new core subsystem (v2 architecture) if it satisfies ALL of:

1. It cannot reasonably extend any frozen subsystem (documented justification required)
2. It benefits multiple independent product areas (not a single-feature concern)
3. It materially reduces system complexity or operational cost
4. It is documented with a new ADR
5. It is explicitly approved by the project owner

This prevents "architecture creep" while leaving room for justified evolution.

### Extension Checklist

Every new feature proposal answers:

- [ ] Which existing subsystem does it extend?
- [ ] Which Tool Registry entry is added (if any)?
- [ ] Which Context Provider is added (if any)?
- [ ] Which Integration adapter is added (if any)?
- [ ] Which Workflow actions/events are added (if any)?
- [ ] Which database migration is additive?
- [ ] Which tests are added?

If every answer points to an existing subsystem, the feature proceeds without architectural review.

### Architecture KPIs

Platform health is measured by:

| KPI | Target |
|-----|--------|
| Test pass rate | 100% |
| Frontend pages using real APIs | 100% |
| Mock data | 0 |
| Orb awareness (context provider coverage) | 100% |
| Context build latency | < 100ms |
| Runtime success rate | > 99% |
| Integration health | > 99% |
| Production uptime | 99.9% SLA |

### CI Architecture Guards

The CI pipeline enforces:
- No new top-level packages without approval
- No duplicate event buses, workflow engines, planners, or runtimes
- No `shared → api` imports (dependency inversion)
- No circular imports
- Architecture tests must pass (48 tests in `test_mi_architecture.py`)

## Consequences

- Future sprints are classified as: Execution, Production Hardening, Launch Readiness, or Provider Expansion
- No architecture sprints are scheduled
- The Launch Readiness Gate (`LAUNCH_READINESS.md`) is the primary tracking document
- Trust, reliability, documentation, observability, onboarding, and production readiness determine success — not additional backend systems

## References

- ADR-0001: Runtime Architecture
- ADR-0002: Tool Registry Design
- ADR-0003: Context Builder & Ranking
- ADR-0004: Knowledge Hub (RAG)
- ADR-0005: Integration Framework
- ADR-0006: Workflow Engine & Event Bus
- `LAUNCH_READINESS.md` — Feature matrix and sign-off criteria
- `AGENTS.md` — "No New Core Abstractions" rule
