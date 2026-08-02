# Architecture Decision Records (ADR)

Immutable records of significant architectural decisions. Once an ADR is accepted, it is not edited — superseding decisions create a new ADR that references the prior one.

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-0001](0001-runtime-architecture.md) | Runtime Architecture | Accepted | 2026-08-02 |
| [ADR-0002](0002-tool-registry.md) | Tool Registry Design | Accepted | 2026-08-02 |
| [ADR-0003](0003-context-builder.md) | Context Builder & Ranking | Accepted | 2026-08-02 |
| [ADR-0004](0004-knowledge-hub.md) | Knowledge Hub (RAG) | Accepted | 2026-08-02 |
| [ADR-0005](0005-integration-framework.md) | Integration Framework | Accepted | 2026-08-02 |
| [ADR-0006](0006-workflow-engine.md) | Workflow Engine & Event Bus | Accepted | 2026-08-02 |
| [ADR-0007](0007-architecture-freeze.md) | Architecture Freeze (v1) | Accepted | 2026-08-02 |

## How to use ADRs

- **Proposing a new architectural decision:** Create a new ADR with the next sequential number. Mark status as "Proposed." Discuss with the team. When accepted, change status to "Accepted."
- **Superseding an ADR:** Create a new ADR that references the old one. Mark the old ADR as "Superseded by ADR-NNNN."
- **Referencing in PRs:** Cite the ADR number in your PR description (e.g., "Implements ADR-0002 extension: new tool `foo.bar`").
- **Architecture Freeze:** ADR-0007 declares the v1 freeze. New core abstractions require a new ADR + explicit approval (see ADR-0007 §v2 Admission Rule).
