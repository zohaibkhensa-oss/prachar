# Architecture Stabilisation Sprint — Migration Notes

**Date:** 2026-07-25
**Status:** Complete — all 10 phases delivered, 202 tests passing.

## Summary

The Marketing Intelligence Engine has been refactored from a working-but-coupled
implementation into a clean-architecture system ready to support 100+ engines
and the future AI Agency Council. No new AI capabilities were added — this was
purely architectural debt elimination.

---

## What Changed (by Phase)

### Phase 1: Responsibility Refactor
**Before:** Strategy Engine owned `media_mix`, `budget_allocation`, `success_metrics` — overlapping with Media Planning, Budget, and Objective engines.

**After:** Strategy Engine owns *strategic intent* only:
- `channel_intent` (text: "lead with Instagram, video-first")
- `budget_philosophy` (text: "concentrate spend on 2 channels")

**Migration impact:** `CampaignStrategy` dataclass changed. Old persisted dicts with `media_mix`/`budget_allocation` will deserialize fine (unknown keys ignored by `from_dict`), but those fields will be empty. **Bump `SCHEMA_VERSION` to "2.0.0".**

### Phase 2: Output Versioning
**Before:** `EngineOutput` had only `prompt_version`. No way to detect old persisted results.

**After:** `EngineOutput` has `schema_version`, `engine_version`, `prompt_version`, `model_version`, `generated_by`, `created_at`. All populated on every run (including failures).

**Migration impact:** New fields are optional (default to empty string). Old persisted outputs will have empty version fields — detectable and upgradable.

### Phase 3: Domain Models
**Before:** Each engine had a `to_profile()`/`to_strategy()` method that manually parsed dicts into dataclasses. Parsing logic was coupled to engines.

**After:** All domain models inherit from `DomainModel` which provides `from_dict()`, `to_dict()`, `validate()`, `schema_version()`. Engines call `Model.from_dict(output.result)` — the model owns parsing.

**Migration impact:** `VersionMismatchError` is raised when deserializing dicts with `schema_version` < `MIN_SUPPORTED_VERSION`. Currently all models default to MIN="1.0.0" so no existing data is rejected.

### Phase 4: Campaign Brain API
**Before:** `CampaignBrain` had `analyse_full()` and individual engine runners. External callers manually chained engines.

**After:** `CampaignBrain` has 6 canonical public API methods:
- `analyse()` — business + audience + competitor
- `consult()` — focused strategy for BRO chat (4 engines)
- `generate_strategy()` — objective + strategy
- `generate_campaign()` — full campaign (9 engines)
- `generate_media_plan()` — media plan only
- `learn()` — post-campaign learning + memory update

**Migration impact:** Old methods (`analyse_full`, `learn_from_campaign`, `analyse_business`, etc.) still exist as private runners for backward compatibility. New code should use the public API.

### Phase 5: Remove Embedded Logic
**Before:** `chat.py` manually chained 4 engines (business → audience → objective → strategy) inline. `campaign_brain.py` router manually chained engines in every endpoint.

**After:** `chat.py` calls `brain.consult()`. Router calls `brain.analyse()`, `brain.generate_strategy()`, `brain.generate_media_plan()`, `brain.generate_campaign()`, `brain.learn()`.

**Migration impact:** BRO chat now uses `prompt_version="chat_brain_v2.0"` (was v1.0). Behavior is identical but the brain handles all orchestration.

### Phase 6: Memory Abstraction
**Before:** `BusinessMemoryStore` in the shared package imported `prachar_api.models.tables` — a layering violation (shared → api dependency).

**After:** `MemoryRepository` Protocol defined in shared package. `InMemoryRepository` for tests/stub. `PostgresMemoryRepository` in `apps/api/prachar_api/infrastructure.py`. `BusinessMemoryStore` takes a repository via dependency injection.

**Migration impact:** `BusinessMemoryStore(session=...)` constructor changed to `BusinessMemoryStore(repository=...)`. Old code passing a session will need to wrap it: `BusinessMemoryStore(repository=PostgresMemoryRepository(session))`.

### Phase 7: Domain Boundaries
Documented in `boundaries.py`. The layers are:
- **Domain:** `domain_base.py`, `*_engine.py` (dataclasses), `repository.py`, `events.py`
- **Application:** `brain.py`, `memory.py` (BusinessMemoryStore), `registry.py`
- **Infrastructure:** `apps/api/prachar_api/infrastructure.py`
- **Presentation:** `apps/api/prachar_api/routers/`

Rule: dependencies point inward only. Enforced by Phase 10 architecture tests.

### Phase 8: Event Model
**New:** `EventBus` + 11 domain events (`BusinessAnalysed`, `StrategyGenerated`, `CampaignCompleted`, `LearningStored`, etc.). `CampaignBrain` accepts an optional `event_bus` and publishes events as engines complete.

**Migration impact:** None — event bus is optional. Without it, behavior is identical.

### Phase 9: Engine Registry
**New:** `EngineRegistry` with `register()`, `get()`, `list()`, `health()`, `names()`. `create_default_registry()` pre-populates all 10 engines with descriptions and capabilities.

**Migration impact:** None — the registry is available but not yet required by CampaignBrain. Future versions of the brain will use the registry instead of hardcoded engine properties.

### Phase 10: Architecture Tests
**New:** 48 architecture tests in `test_mi_architecture.py` that enforce:
1. No shared→api imports
2. No circular imports
3. No duplicate responsibility ownership
4. Version compatibility (every engine has version constants)
5. Repository abstraction
6. Campaign Brain orchestration only (no manual chaining in routers)
7. Dependency inversion (domain models inherit DomainModel)
8. Engine independence (engines don't import each other)

**Migration impact:** These tests will fail CI if any rule is violated, preventing architectural drift.

---

## New Files Created

| File | Purpose |
|------|---------|
| `packages/shared/.../marketing_intelligence/domain_base.py` | DomainModel base class with from_dict/validate/schema_version |
| `packages/shared/.../marketing_intelligence/repository.py` | MemoryRepository Protocol + InMemoryRepository |
| `packages/shared/.../marketing_intelligence/events.py` | Domain events + EventBus |
| `packages/shared/.../marketing_intelligence/registry.py` | EngineRegistry + create_default_registry |
| `packages/shared/.../marketing_intelligence/boundaries.py` | Architecture boundary documentation |
| `apps/api/prachar_api/infrastructure.py` | PostgresMemoryRepository implementation |
| `packages/shared/.../tests/test_mi_domain.py` | Domain model tests (24) |
| `packages/shared/.../tests/test_mi_repository.py` | Repository abstraction tests (13) |
| `packages/shared/.../tests/test_mi_events.py` | Event model tests (13) |
| `packages/shared/.../tests/test_mi_registry.py` | Engine registry tests (14) |
| `packages/shared/.../tests/test_mi_architecture.py` | Architecture validation tests (48) |

## Files Modified

| File | Change |
|------|--------|
| `strategy_engine.py` | Removed media_mix/budget_allocation/success_metrics; added channel_intent/budget_philosophy; v2.0.0 |
| `base.py` | Added versioning fields to EngineOutput; added ENGINE_VERSION/SCHEMA_VERSION constants |
| `business_engine.py` | BusinessProfile inherits DomainModel; to_profile uses from_dict |
| `audience_engine.py` | AudienceProfile inherits DomainModel; to_profile uses from_dict |
| `competitor_engine.py` | CompetitorProfile inherits DomainModel; to_profile uses from_dict |
| `objective_engine.py` | MarketingObjective inherits DomainModel; to_objective uses from_dict |
| `creative_engine.py` | CreativeDirection inherits DomainModel; to_direction uses from_dict |
| `media_engine.py` | MediaPlan inherits DomainModel; to_plan uses from_dict |
| `budget_engine.py` | BudgetEstimate inherits DomainModel; to_estimate uses from_dict |
| `execution_engine.py` | ExecutionPlan inherits DomainModel; to_plan uses from_dict |
| `learning_engine.py` | LearningReport inherits DomainModel; to_report uses from_dict |
| `memory.py` | BusinessMemoryStore uses MemoryRepository protocol (no more SQLAlchemy imports) |
| `brain.py` | Added 6 public API methods; added event publishing; added _load_memory/_merge_context helpers |
| `__init__.py` | Exported DomainModel, VersionMismatchError, MemoryRepository, EventBus, EngineRegistry, all events |
| `apps/api/.../routers/chat.py` | Replaced manual engine chaining with brain.consult() |
| `apps/api/.../routers/campaign_brain.py` | Replaced manual engine chaining with public API methods |

---

## Test Results

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_mi_base.py` | 19 | Base classes, versioning |
| `test_mi_engines_1.py` | 13 | Audience, Competitor, Objective |
| `test_mi_engines_2.py` | 10 | Strategy, Creative, Media |
| `test_mi_engines_3.py` | 9 | Budget, Execution, Learning |
| `test_mi_brain.py` | 23 | Brain + public API |
| `test_mi_domain.py` | 24 | DomainModel base |
| `test_mi_repository.py` | 13 | Repository abstraction |
| `test_mi_events.py` | 13 | Event model |
| `test_mi_registry.py` | 14 | Engine registry |
| `test_mi_architecture.py` | 48 | Architecture invariants |
| `test_campaign_brain.py` | 16 | API router |
| **Total** | **202** | **All passing** |

---

## Architecture Scorecard (Post-Sprint)

| Criterion | Before | After |
|-----------|--------|-------|
| Clear responsibilities, minimal overlap | PARTIAL FAIL | **PASS** |
| Strongly typed + versioned outputs | PARTIAL PASS | **PASS** |
| Independent improvability | PASS | **PASS** |
| Brain orchestrates, doesn't embed | MOSTLY YES | **PASS** |
| Prompts/rules/persistence separated | PARTIAL FAIL | **PASS** |
| No shared→api imports | FAIL | **PASS** |
| No circular dependencies | Unknown | **PASS** (tested) |
| No orchestration outside Brain | FAIL | **PASS** (tested) |
| No infrastructure in Domain | Unknown | **PASS** (tested) |
| Engine independence | Unknown | **PASS** (tested) |

The engine is now architecturally ready to support the AI Agency Council.
