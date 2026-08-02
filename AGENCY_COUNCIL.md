# Agency Council — Architecture

> **The core IP of PRACHAR.** No single AI agent makes the final campaign decision. Every campaign is reviewed by 9 independent specialist AI Directors, and the Consensus Engine produces a weighted decision.

## Overview

The Agency Council transforms PRACHAR from a content-generation platform into a true AI Advertising Agency. Before any campaign goes live, it passes through an executive council review — simulating a real advertising agency's decision-making process.

```
BRO Chat → Campaign Brain → Agency Council → Consensus Engine
                                              ↓
                                         Creative Orchestrator → Workers → Publishing → Learning
```

## The 9 Directors

Every Director owns exactly one responsibility. No Director may call another Director. They work independently and return a 9-field contract.

| # | Director | Responsibility |
|---|----------|---------------|
| 1 | Chief Strategy Officer | Business positioning, campaign objective, market opportunity, brand differentiation, long-term growth |
| 2 | Chief Creative Officer | Creative concept, storytelling, visual language, emotion, brand identity, creative originality |
| 3 | Chief Media Officer | Channel mix, publishing schedule, frequency, reach, platform optimisation |
| 4 | Chief Performance Officer | ROI, CAC, CPA, CTR, expected conversions, growth modelling |
| 5 | Chief Brand Officer | Brand consistency, tone, messaging, colours, typography, brand safety |
| 6 | Chief Financial Officer | Budget approval, expected return, risk, cost efficiency, financial viability |
| 7 | Chief Compliance Officer | Advertising policies, legal risk, sensitive industries, claims review, regulatory compliance |
| 8 | Chief Customer Officer | Audience fit, customer psychology, pain points, buying behaviour, user journey |
| 9 | Chief Analytics Officer | Historical performance, previous campaigns, business memory, insights, recommendations |

### The 9-Field Contract

Every Director returns a `DirectorOpinion` with exactly these fields:

| Field | Type | Description |
|-------|------|-------------|
| `opinion` | str | Main opinion (1-3 sentences) |
| `reasoning` | str | Detailed reasoning |
| `confidence` | float | 0.0-1.0 |
| `risks` | list[str] | Identified risks |
| `alternatives` | list[str] | Alternative approaches |
| `recommendations` | list[str] | Actionable recommendations |
| `evidence` | list[str] | Internal evidence cited (from the brief) |
| `priority` | str | low, medium, high, critical |
| `approval` | bool | Does this director approve? |

Plus metadata: `director`, `role`, `latency_ms`, `tokens_used`, `cost_usd`, `model`, `provider`, `round_number`.

## The Consensus Engine

The Consensus Engine gathers every Director's opinion and produces a single `ConsensusDecision`. It does **NOT** use majority voting. It uses **weighted consensus**.

### Weight Calculation

Weights are deterministic and depend on:
- **Industry** (restaurant, ecommerce, healthcare, finance, technology, default)
- **Campaign objective** (increase_sales, brand_awareness, lead_generation, customer_retention, product_launch)
- **Budget** (low budgets elevate CFO weight, high budgets elevate CSO weight)
- **Campaign type** (launch, promotional, always-on)

Weights always sum to 1.0. See `compute_weights()` in `consensus.py`.

**Example — Restaurant + Increase Sales:**
```
chief_strategy_officer:     0.24  (highest — strategy is king for restaurants)
chief_creative_officer:     0.19
chief_media_officer:        0.14
chief_performance_officer:  0.13  (elevated by sales objective)
chief_customer_officer:     0.10
chief_financial_officer:    0.06
chief_brand_officer:        0.05
chief_compliance_officer:   0.05
chief_analytics_officer:    0.05
```

**Example — Healthcare:**
```
chief_compliance_officer:   0.25  (highest — compliance is critical in healthcare)
chief_strategy_officer:     0.15
chief_customer_officer:     0.15
chief_creative_officer:     0.10
chief_brand_officer:        0.10
chief_media_officer:        0.10
chief_financial_officer:    0.05
chief_performance_officer:  0.05
chief_analytics_officer:    0.05
```

### Multi-Round Review

If disagreement is high (> 0.45 on a 0-1 scale), the engine runs another round. Maximum 3 rounds.

In rounds 2+, directors see the **disagreements and risks** from the previous round (not full reasoning) — this keeps them independent while allowing the council to converge.

### Disagreement Calculation

Disagreement is a weighted combination of:
- **Approval split** (50%) — how close to 50/50 the approval vote is
- **Confidence variance** (30%) — wide variance in director confidence
- **Priority conflicts** (20%) — directors flagging critical priority

### Self-Critique Step

Before final approval, the engine runs a self-critique step asking:
1. What is wrong with this campaign?
2. What could fail?
3. What would a competitor do?
4. What would the customer dislike?
5. What assumptions are weak?

If the self-critique finds critical issues, the approval status becomes "revise".

### Campaign Scoring

The engine produces a 7-dimensional campaign score (each 0-100):

| Dimension | Source |
|-----------|--------|
| strategy_score | Chief Strategy Officer |
| creative_score | Chief Creative Officer |
| media_score | Chief Media Officer |
| brand_score | Chief Brand Officer |
| performance_score | Chief Performance Officer |
| risk_score | Aggregate (fewer risks = higher score) |
| compliance_score | Chief Compliance Officer |

The **overall_score** is a weighted average of all 7 dimensions.

### Approval Status

| Status | Condition |
|--------|-----------|
| `approved` | compliance_score ≥ 40, risk_score ≥ 30, overall_score ≥ 60, weighted_approval ≥ 0.55, no critical self-critiques |
| `rejected` | compliance_score < 40 OR risk_score < 30 |
| `revise` | overall_score < 60 OR weighted_approval < 0.55 OR critical self-critiques |
| `pending` | (initial state, never in final output) |

**Compliance has veto power.** If the Chief Compliance Officer rejects with critical priority, the campaign cannot be approved.

## Architecture (Clean Architecture)

```
┌─────────────────────────────────────────────────────────┐
│ Presentation (apps/api/prachar_api/routers/)            │
│   agency_council.py — 4 REST endpoints                  │
│   chat.py — BRO council review handler                  │
└────────────────────┬────────────────────────────────────┘
                     │ delegates to
┌────────────────────▼────────────────────────────────────┐
│ Application (packages/shared/prachar_shared/)           │
│   marketing_intelligence/brain.py                       │
│     CampaignBrain.review_with_council()                 │
│   agency_council/consensus.py                           │
│     ConsensusEngine.reach_consensus()                   │
│   agency_council/memory.py                              │
│     CouncilMemoryStore                                  │
└────────────────────┬────────────────────────────────────┘
                     │ depends on interface
┌────────────────────▼────────────────────────────────────┐
│ Domain (packages/shared/prachar_shared/agency_council/) │
│   models.py — DirectorOpinion, ConsensusDecision, ...   │
│   director_base.py — Director base class                │
│   directors.py — 9 concrete directors                   │
│   consensus.py — weight calculation, scoring            │
│   memory.py — CouncilMemoryRepository protocol          │
│   bro_integration.py — BRO summary helpers              │
└────────────────────┬────────────────────────────────────┘
                     │ implemented by
┌────────────────────▼────────────────────────────────────┐
│ Infrastructure (apps/api/prachar_api/)                  │
│   infrastructure.py — PostgresCouncilRepository         │
│   models/tables.py — 5 SQLAlchemy tables                │
│   alembic/versions/0003_agency_council.py               │
└─────────────────────────────────────────────────────────┘
```

### Dependency Rules (Enforced)

1. **Domain never imports infrastructure** — no SQLAlchemy, no FastAPI in `agency_council/`
2. **Directors don't import each other** — each director is independent
3. **Brain depends on Council interface** — `CampaignBrain.council` property returns `ConsensusEngine`, swappable
4. **CouncilMemoryStore depends on protocol** — `CouncilMemoryRepository`, not `PostgresCouncilRepository`
5. **BRO never exposes raw director discussions** — `summarise_council_decision()` produces a user-friendly summary

## Database Schema (Migration 0003)

5 new tables, all tenant-scoped with RLS:

### `council_sessions`
Complete review sessions (multiple rounds of director review).

### `director_opinions`
Individual director opinions, separated for queryability (e.g., "show all CSO opinions").

### `consensus_decisions`
Final consensus decisions, separated for decision history tracking.

### `campaign_scores`
Multi-dimensional scores, separated for tracking score trends over time.

### `council_learnings`
Persistent learnings from council decisions — used by the Analytics Director and Learning Engine.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/agency-council/review` | Submit a campaign for council review |
| POST | `/agency-council/consensus` | Get consensus decision for a session |
| GET | `/agency-council/history` | List council sessions (optional brand_id filter) |
| GET | `/agency-council/{campaign_id}` | Get council session by campaign ID |

All endpoints require authentication. All mutations write an `AuditEvent` row.

## BRO Chat Integration

When a user asks for a council review (detected by `is_council_review_request()`), BRO:
1. Delegates to `CampaignBrain.review_with_council()`
2. Receives a `ConsensusDecision`
3. Calls `summarise_council_decision()` to produce a conversational summary
4. Returns the summary — **never raw director discussions**

**Trigger keywords:** "review my campaign", "should I approve", "council review", "agency council", "is this campaign good", etc.

## AI Safety

Every Director's prompt includes a safety preamble:
- Only cite evidence from the campaign brief
- Never invent features, integrations, or capabilities
- Never fabricate statistics, benchmarks, or case studies
- If you lack information, say so explicitly
- Be honest about risks and weaknesses
- Do not use engagement-bait or make guaranteed-results claims
- Strip any medical/financial guarantees from recommendations

The Chief Compliance Officer has **veto power** — if it flags critical priority, the campaign cannot be approved.

## Observability

Every Director opinion tracks:
- `latency_ms` — time to review
- `tokens_used` — AI tokens consumed
- `cost_usd` — cost in USD
- `model` and `provider` — which AI model was used

Every ConsensusDecision tracks:
- `total_tokens`, `total_cost_usd`, `total_latency_ms`
- `rounds_completed`
- `weights` and `weighted_scores`

Every CouncilSession tracks:
- All opinions from all rounds
- The final consensus decision
- Status, timestamps, totals

## Testing

**189 council tests** across 5 test files:

| File | Tests | Coverage |
|------|-------|----------|
| `test_council_directors.py` | 68 | Director contract, independence, replaceability, safety |
| `test_council_consensus.py` | 55 | Weights, disagreement, minorities, scoring, tie-breaking, determinism |
| `test_council_memory.py` | 18 | In-memory repo, store, failure handling |
| `test_council_bro_integration.py` | 32 | Review detection, summary generation, no raw discussions |
| `test_agency_council.py` (api) | 16 | DB models, router registration, auth, schema validation |

**Total project tests: 621 passing** (was 433 before the council sprint).

## File Inventory

### Domain (`packages/shared/prachar_shared/agency_council/`)
- `__init__.py` — public API exports
- `models.py` — 5 domain models (DirectorOpinion, ConsensusDecision, CampaignScore, CouncilSession, CouncilLearning)
- `director_base.py` — Director base class + 9-field contract
- `directors.py` — 9 concrete directors
- `consensus.py` — ConsensusEngine, weight calculation, scoring, disagreement
- `memory.py` — CouncilMemoryRepository protocol, InMemoryCouncilRepository, CouncilMemoryStore
- `bro_integration.py` — BRO summary helpers

### Infrastructure (`apps/api/prachar_api/`)
- `models/tables.py` — 5 SQLAlchemy tables (appended)
- `infrastructure.py` — PostgresCouncilRepository (appended)
- `routers/agency_council.py` — 4 REST endpoints
- `alembic/versions/0003_agency_council.py` — migration

### Application (`packages/shared/prachar_shared/marketing_intelligence/`)
- `brain.py` — `CampaignBrain.review_with_council()` + `council` property (added)

### Presentation (`apps/api/prachar_api/routers/`)
- `chat.py` — BRO council review handler (added)

### Tests (`packages/shared/prachar_shared/tests/` + `apps/api/prachar_api/tests/`)
- `council_fixtures.py` — StubGateway, FailingGateway
- `test_council_directors.py`
- `test_council_consensus.py`
- `test_council_memory.py`
- `test_council_bro_integration.py`
- `test_agency_council.py`
