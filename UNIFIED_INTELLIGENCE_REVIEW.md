# UNIFIED INTELLIGENCE REVIEW

> **Decision gate.** This document is mandatory. No code is written until it is complete and the path forward is clear. If the duplication cannot be cleanly consolidated, we stop and redesign before writing a single line.

## 0. Verdict (read this first)

**The current implementation has measurable architectural fragmentation. It is fixable.** The Creator Sprint shipped working features but introduced parallel infrastructure that will compound with every new domain (Restaurant, Clinic, Hotel, Education, Real Estate, Retail, Agency, Fitness, Manufacturing, Law Firm, Architecture Firm, Travel Agency, Fitness Coach).

If we add 10 more domains the way we added Creator, we will have:
- 12 copies of `_extract_json` (one per domain router)
- 12 copies of brand-creation logic
- 12 copies of campaign-plan persistence
- 12 copies of the onboarding state machine
- 12 near-duplicate dashboards
- 12 near-duplicate campaign decks
- ~12,000 lines of code that should be ~2,000

**This sprint consolidates everything into ONE extensible platform where adding a domain = adding ONE folder + ONE registration line. Zero core modifications.**

The audit below is the evidence. The architecture at the end is the fix.

---

## 1. Scope of the audit

Files audited in full:

**Backend (orchestration & persistence):**
- `apps/api/prachar_api/routers/consult.py` (827 lines) — Business conversational onboarding
- `apps/api/prachar_api/routers/creator.py` (913 lines) — Creator conversational onboarding
- `apps/api/prachar_api/routers/campaign_brain.py` (740 lines) — CampaignBrain API
- `apps/api/prachar_api/routers/chat.py` (626 lines) — BRO chat
- `apps/api/prachar_api/routers/campaigns.py` (69 lines) — Live campaign persistence
- `apps/api/prachar_api/models/tables.py` — Brand, CampaignPlanRecord models
- `apps/api/prachar_api/schemas.py` — BrandIn/BrandOut
- `packages/shared/prachar_shared/ai_gateway/json_utils.py` — existing `extract_json`

**Frontend (UI & state):**
- `apps/web/src/app/onboarding/page.tsx` (1532 lines) — onboarding conversation
- `apps/web/src/app/app/page.tsx` (434 lines) — business dashboard
- `apps/web/src/app/app/creator-dashboard.tsx` (324 lines) — creator dashboard
- `apps/web/src/app/app/layout.tsx` — sidebar nav
- `apps/web/src/lib/consult.ts`, `apps/web/src/lib/creator.ts`, `apps/web/src/lib/creator-types.ts`, `apps/web/src/lib/hooks.ts`

---

## 2. Duplicate prompts

### Finding
Both `consult.py` and `creator.py` define their own LLM prompt templates that follow the **same structural pattern** with domain-specific wording:

| Prompt pattern | consult.py | creator.py |
|----------------|------------|------------|
| Extract structured info from free text | `_EXTRACT_PROMPT` (lines 177-210) | (none — extraction is fused into `_CONSULT_PROMPT`) |
| Generate understanding + opportunities + plan | `_UNDERSTANDING_PROMPT` (lines 212-278) | `_CONSULT_PROMPT` (lines 185-270) |
| Generate campaign preview | `_CAMPAIGN_PREVIEW_PROMPT` (lines 280-329) | `_CREATOR_CAMPAIGN_PROMPT` (lines 399-452) |
| Repurpose / YouTube plan | (none) | `_REPURPOSE_PROMPT`, `_YOUTUBE_PLAN_PROMPT` (creator-only) |

**The structural skeleton is identical in all of these:**
1. "You are a world-class [domain] strategist having a conversation with a [domain] owner."
2. "The [domain] said: \"{message}\""
3. "Write a response that makes the [domain] feel understood. Speak like a knowledgeable friend ('bro' energy). Never use the words 'AI', 'engine', 'algorithm'."
4. "Respond as JSON only: { reply, profile/understanding, opportunities, plan }"
5. Tone rules: no jargon (ROAS, CPA, CTR for business; ROAS, CPA, conversions, customers for creator)

**The only things that change per domain:**
- The role ("marketing strategist" vs "creator strategist")
- The fields being extracted (business_name/industry/products vs niche/platforms/upload_frequency)
- The plan week structure (objectives/content/offers/channels vs videos/shorts/community_posts)
- The forbidden jargon list
- The KPI vocabulary

**Verdict:** The prompt *structure* is duplicated. The prompt *content* is domain-specific. The fix is a **prompt template** with domain-supplied variables (role, fields, week schema, jargon blacklist, KPI labels).

---

## 3. Duplicate APIs

### Finding
Two parallel routers expose the same conceptual operations with different names and shapes:

| Concept | consult.py | creator.py |
|---------|------------|------------|
| Conversational analysis | `POST /consult` | `POST /creator/consult` |
| Campaign generation | `POST /consult/campaign` | `POST /creator/campaign` |
| Domain-specific tool | (none) | `POST /creator/repurpose`, `POST /creator/youtube-plan` |

**Request shapes diverge for the same concept:**
- `/consult` takes `{message, brand_id?}`
- `/creator/consult` takes `{message, creator_type, brand_id?}`

**Response shapes diverge for the same concept:**
- `/consult` returns `{reply, business, growth_opportunities, plan, extracted, brand_id, brand_name, confidence, tokens_used, model}`
- `/creator/consult` returns `{reply, profile, position, plan, brand_id, brand_name, confidence, tokens_used, model}`

These are the **same response** with different field names: `business` ≈ `profile` + `position`, `growth_opportunities` ≈ `position.growth_opportunities`, `extracted` ≈ (creator has no separate extraction).

**Verdict:** Two APIs that do the same thing with different names. The fix is **ONE `/consult` endpoint** that takes a `domain` parameter and returns a **unified response shape** with domain-specific sections.

---

## 4. Duplicate orchestration

### Finding
The two routers implement the same pipeline with different steps:

**consult.py flow:**
1. Extract structured info via LLM (`consult_extract`)
2. Run `CampaignBrain.analyse()` (business + audience + competitor engines)
3. Generate understanding + opportunities + plan via LLM (`consult_understanding`)
4. Update `brand_graph`
5. Return response

**creator.py flow:**
1. Create/get brand (no extraction step)
2. Generate analysis + plan in ONE LLM call (`creator_consult`)
3. Update `brand_graph` with profile + position
4. Return response

**Critical architectural divergence:** `consult.py` uses `CampaignBrain.analyse()` (the Marketing Intelligence Engine). `creator.py` **bypasses CampaignBrain entirely** and calls `AIGateway` directly.

This means:
- Creators don't benefit from the Audience Intelligence engine
- Creators don't benefit from the Competitor Intelligence engine
- Creators don't benefit from the Agency Council review
- Creators don't benefit from Business Memory learnings
- The two flows will drift further over time as CampaignBrain evolves

**Campaign generation divergence:**
- `/consult/campaign` → `CampaignBrain.generate_campaign()` (all 9 engines) → `_CAMPAIGN_PREVIEW_PROMPT`
- `/creator/campaign` → `_CREATOR_CAMPAIGN_PROMPT` (direct LLM, no CampaignBrain)

**Verdict:** Two orchestration pipelines doing the same thing. The fix is **ONE Universal Consult Pipeline** that always runs through CampaignBrain, with the Domain Pack supplying the domain-specific prompt variables and field schemas.

---

## 5. Duplicate persistence

### Finding

**Brand creation — 90% duplicated:**
- `consult.py::_get_or_create_brand` (lines 395-443)
- `creator.py::_get_or_create_creator_brand` (lines 488-539)

Both:
1. Look up existing brand by id + tenant_id
2. If not found, create a new Brand with: tenant_id, name, category, locales=["en-IN"], tone, brand_graph
3. Write an audit log with action="*.brand_created", payload={name, category/creator_type, source="conversational_onboarding"}
4. Commit and return

**Only differences:**
- creator sets `customer_type="creator"`
- creator uses a heuristic name-from-message parser
- audit action prefix ("consult." vs "creator.")
- brand_graph initial contents

**Campaign plan persistence — identical pattern:**
- `consult.py` lines 804-812 (in `/consult/campaign`)
- `creator.py` lines 880-892 (in `/creator/campaign`)

Both create a `CampaignPlanRecord` with: tenant_id, brand_id, name, goal, budget, locale, campaign (JSONB), overall_confidence, total_cost_usd, total_tokens, status="draft". Both write an audit log.

**Only difference:** the shape of the `campaign` JSONB.

**Brand graph updates — divergent schemas:**
- consult stores: `{location, products, services, audience, goals, social_handles, additional_context}`
- creator stores: `{creator_type, description}` then updates with `{profile, position}`

There is **no shared schema** for `brand_graph`. Future domains will invent their own.

**Verdict:** Persistence is 90% duplicated. The fix is **shared persistence helpers** (`create_brand_from_consult`, `persist_campaign_plan`) that take a Domain Pack parameter for the domain-specific bits (customer_type, brand_graph contents, campaign JSONB shape).

---

## 6. Duplicate UI

### Finding — Onboarding (1532 lines)

The onboarding file defines **13 component functions**, of which **4 pairs are 80-95% similar**:

| Business component | Creator component | Similarity |
|--------------------|-------------------|------------|
| `BusinessUnderstandingCards` (625-695) | `CreatorUnderstandingCards` (1100-1170) | 95% — same glass-strong cards, same InsightCard usage |
| `OpportunityCards` (734-808) | `CreatorOpportunityCards` (1180-1240) | 90% — same numbered card list |
| `PlanTimeline` (812-970) | `CreatorPlanTimeline` (1250-1320) | 85% — same vertical line + dot timeline |
| `CampaignPreviewDeck` (980-1090) | `CreatorCampaignPreview` (1330-1532) | 80% — same presentation-deck layout |

**Shared components (already shared):**
- `TypeChoiceCard`, `ChatBubble`, `InsightCard`, `PlanSection`

**Duplicated UI patterns:**
- Glass card styling (identical)
- Timeline vertical line + dot pattern (identical)
- Badge color mappings (identical)
- Phase state machine (identical: type_select → subtype_select → intro → listening → analysing → understanding → opportunities → plan → campaign_generating → campaign → approved)

### Finding — Dashboard

`apps/web/src/app/app/page.tsx` (business, 434 lines) and `apps/web/src/app/app/creator-dashboard.tsx` (creator, 324 lines) share:
- Greeting pattern (similar)
- Today's Action card (identical structure, different content)
- KPI card grid (similar structure, different metrics)
- Approvals section (identical)
- LoadingState (identical)

**The business dashboard is explicitly protected** ("Do NOT change. Only improve where shared."). The fix is not to rewrite the business dashboard but to extract the **shared dashboard shell** (greeting, today's action, approvals, loading) and let each domain supply **widget slots** for KPIs and quick actions.

### Finding — Sidebar

`apps/web/src/app/app/layout.tsx` defines `BUSINESS_NAV` and `CREATOR_NAV` as two hard-coded arrays. Adding a new domain requires editing this file — violating the "zero core modifications" rule.

**Verdict:** UI is heavily duplicated. The fix is a **shared presentation layer** (generic `UnderstandingCards`, `OpportunityCards`, `PlanTimeline`, `CampaignDeck` driven by domain-supplied data) and a **dashboard shell** with widget slots. The sidebar should be **driven by the Domain Pack**, not hard-coded.

---

## 7. Duplicate business rules

### Finding

**Audit action naming is inconsistent:**
- `consult.brand_created` vs `creator.brand_created`
- `consult.campaign_created` vs `creator.campaign`

**brand_graph schema is undefined:**
- No contract for what fields go in brand_graph
- Each router invents its own structure
- Future domains will further diverge

**Customer type handling is split:**
- `Brand.customer_type` is a free string ("business" | "creator")
- No enum, no validation at the model level
- No registry of valid customer types
- The frontend hard-codes `BUSINESS_NAV` and `CREATOR_NAV` based on string comparison

**Verdict:** Business rules are duplicated and inconsistent. The fix is a **Domain Pack registry** that defines valid customer types, brand_graph schema, audit action names, and sidebar nav — all in one place per domain.

---

## 8. Duplicate models

### Finding

**Pydantic models with the same shape, different names:**

| Concept | consult.py | creator.py |
|---------|------------|------------|
| Week plan | `WeekPlan` (week, theme, objectives, content, offers, channels, kpis) | `CreatorWeekPlan` (week, theme, videos, shorts, community_posts, collaborations, seo, newsletter, live_sessions, kpis) |
| Understanding | `BusinessUnderstanding` (summary, strengths, weaknesses, likely_customers, likely_competitors, marketing_opportunities, seasonal_opportunities, marketing_maturity, potential_risks) | `CreatorProfile` + `CreatorPosition` (niche, platforms, ..., strengths, weaknesses, growth_opportunities, content_gaps, monetisation_opportunities) |
| Opportunity | `GrowthOpportunity` (title, description, business_impact, difficulty, timeframe) | (creator uses plain `list[str]` for growth_opportunities — less structured) |
| Campaign preview | `CampaignPreview` (title, hero_image_concept, video_concept, post_ideas, estimated_reach, expected_enquiries, budget_estimate, why_this_campaign, confidence, expected_benefit, risks, alternative) | `CreatorCampaignResponse` (title, content_plan, publishing_schedule, expected_growth, confidence) |

**Verdict:** Models diverge in field names but share structural intent. The fix is a **base model layer** with domain-specific extensions: `WeekPlanBase` (week, theme, kpis) + domain-supplied activity slots; `UnderstandingBase` (summary, strengths, weaknesses) + domain-supplied insight slots; `CampaignPreviewBase` (title, confidence, why, risks) + domain-supplied preview slots.

---

## 9. The `_extract_json` duplication (smoking gun)

**`packages/shared/prachar_shared/ai_gateway/json_utils.py`** already defines `extract_json()` (line 27) and `extract_json_or_raise()` (line 97) — universal JSON extractors that handle markdown fences, prose, and BOM. This was built in the AI Trust Sprint.

**Both `consult.py` (line 376) and `creator.py` (line 458) define their own `_extract_json`** — a simpler, less robust copy of the shared utility.

This is the clearest evidence of fragmentation: **a shared utility already exists, but the new routers don't use it.** If this pattern continues, every new domain router will reinvent the same helper.

**Verdict:** Delete both `_extract_json` copies. Use `prachar_shared.ai_gateway.json_utils.extract_json` everywhere.

---

## 10. What is already shared (and should stay shared)

To be clear about what is NOT broken:

- **Authentication** — JWT, tenant scoping, RLS. Shared. ✅
- **AIGateway** — provider abstraction, tiering, caching, budget, retries. Shared. ✅
- **CampaignBrain** — 9-engine orchestrator. Shared (but creator bypasses it — bug). ⚠️
- **Agency Council** — 9-director review. Shared (but creator bypasses it — bug). ⚠️
- **Audit logging** — `log_audit()` helper. Shared. ✅
- **CampaignPlanRecord** — persistence table. Shared. ✅
- **Brand model** — table + RLS. Shared. ✅
- **json_utils, safety, observability** — shared utilities. Shared (but not used by new routers — bug). ⚠️
- **Frontend glass/card/badge styling** — shared CSS. Shared. ✅

The fragmentation is in the **orchestration layer** (routers) and the **presentation layer** (frontend components), not in the foundation.

---

## 11. The fix — Domain Pack Architecture

### Principle

> **Universal Intelligence → Domain Pack → Business Logic**

There is ONE intelligence platform. Every customer type is a plug-in Domain Pack. The pipeline never changes. Only the Domain Pack changes.

### The Universal Pipeline (never changes)

```
Conversation
    ↓
Entity Extraction      ← Domain Pack supplies the extraction schema
    ↓
Business Memory        ← shared store, domain-tagged
    ↓
Domain Detection       ← auto-detect or user-selected
    ↓
Load Domain Pack       ← from registry
    ↓
Marketing Intelligence ← CampaignBrain.analyse() (always)
    ↓
Campaign Brain         ← CampaignBrain.generate_campaign() (always)
    ↓
Campaign Generation    ← Domain Pack supplies the campaign template
    ↓
Presentation           ← shared components, domain-supplied data
    ↓
Learning               ← shared learning engine, domain-tagged
```

### The Domain Pack contract (what every pack defines)

```python
class DomainPack(Protocol):
    # Identity
    id: str                          # "business", "creator", "restaurant", "clinic"
    label: str                       # "Business Growth", "Creator Growth"
    customer_type: str               # "business" | "creator" (or future types)
    emoji: str

    # Discovery
    subtypes: list[SubtypePreset]    # e.g. [Restaurant, Clinic, Retail, ...] or [YouTube Creator, ...]
    extraction_schema: dict          # JSON schema for entity extraction
    extraction_prompt: str           # domain-specific extraction prompt fragment

    # Goals
    default_goal: str
    goal_options: list[str]

    # KPIs
    kpi_cards: list[KpiCardSpec]     # dashboard KPI widget specs

    # Growth Opportunities
    opportunity_prompt: str          # domain-specific opportunity prompt fragment

    # Planning
    week_schema: dict                # JSON schema for a week of the 30-day plan
    week_prompt: str                 # domain-specific week plan prompt fragment

    # Campaign Templates
    campaign_template: str           # "Promotion Campaign" | "Content Campaign" | "Patient Acquisition Campaign"
    campaign_prompt: str             # domain-specific campaign prompt fragment

    # Recommendations
    recommendations_prompt: str      # domain-specific recommendation prompt fragment

    # Dashboard Cards
    dashboard_widgets: list[WidgetSpec]  # widget slots for the unified dashboard

    # Memory Extensions
    brand_graph_schema: dict         # schema for domain-specific brand_graph fields
    memory_namespace: str            # e.g. "business.restaurant" or "creator.youtube"

    # Conversation Behaviour
    conversation_role: str           # "marketing strategist" | "creator strategist"
    forbidden_jargon: list[str]      # ["ROAS", "CPA", "CTR"] etc.
    greeting_template: str           # BRO's opening message template

    # Sidebar
    nav_items: list[NavItemSpec]     # sidebar navigation for this domain

    # Domain-specific tools (optional)
    tools: list[ToolSpec]            # e.g. creator has Repurpose + YouTube Plan
```

**NOTHING ELSE.** A Domain Pack does NOT define:
- Its own router
- Its own persistence logic
- Its own UI components
- Its own orchestration pipeline
- Its own audit logging
- Its own auth

### Plugin registration

```
packages/shared/prachar_shared/domain_packs/
    __init__.py              # registry
    base.py                  # DomainPack protocol + base classes
    business/
        __init__.py
        pack.py              # BusinessPack
        subtypes.py          # Restaurant, Clinic, Retail, Hotel, ...
    creator/
        __init__.py
        pack.py              # CreatorPack
        subtypes.py          # YouTube Creator, Instagram Creator, ...
        tools.py             # Repurpose + YouTube Plan tool specs
    restaurant/
        __init__.py
        pack.py              # RestaurantPack (subtype of Business, or standalone?)
    clinic/
        __init__.py
        pack.py              # ClinicPack
```

**Adding a new domain (e.g. Law Firm):**
1. Create `packages/shared/prachar_shared/domain_packs/lawfirm/` (ONE folder)
2. Implement `pack.py` with the DomainPack contract (ONE file)
3. Register it in `__init__.py` (ONE line)
4. **ZERO core modifications.** No router changes, no dashboard changes, no pipeline changes.

### Unified Consult Engine (replaces both /consult and /creator/consult)

```python
@router.post("/consult")
async def consult(body: ConsultRequest, user: CurrentUser, session: SessionDep):
    """Universal consult endpoint. Works for ANY domain."""
    pack = registry.get(body.domain)  # "business", "creator", "restaurant", "clinic"
    return await consult_engine.consult(message=body.message, pack=pack, user=user, session=session)
```

The `ConsultEngine` runs the Universal Pipeline:
1. Extract entities using `pack.extraction_schema` + `pack.extraction_prompt`
2. Create/get brand using shared `create_brand_from_consult(pack, ...)`
3. Run `CampaignBrain.analyse()` (always — no more bypassing)
4. Generate understanding + opportunities + plan using `pack` prompt fragments
5. Update `brand_graph` using `pack.brand_graph_schema`
6. Return unified `ConsultResponse` with domain-specific sections

### Unified Dashboard Framework

```
DashboardShell (never changes)
    ├── Greeting (domain-supplied label)
    ├── Today's Action (domain-supplied action logic)
    ├── Widget Slot: KPIs (domain-supplied KpiCardSpec list)
    ├── Widget Slot: Quick Actions (domain-supplied ActionCard list)
    ├── Approvals (shared — reads CampaignPlanRecord)
    ├── Widget Slot: Domain-specific (e.g. Trending for creators, Promotions for restaurants)
    └── Content Pipeline (shared — reads CampaignPlanRecord)
```

The shell never changes. Each Domain Pack supplies widget specs. Adding a domain = adding widget specs to the pack. No dashboard code changes.

### Unified Campaign Generator

```
CampaignGenerator (never changes)
    ├── Load Domain Pack
    ├── Run CampaignBrain.generate_campaign() (always)
    ├── Apply Domain Pack campaign_template
    ├── Generate preview using Domain Pack campaign_prompt
    └── Persist using shared persist_campaign_plan()
```

Restaurant → "Promotion Campaign" template.
Creator → "Content Campaign" template.
Clinic → "Patient Acquisition Campaign" template.

The generator is the same. Only the template changes.

### Shared Presentation Layer

Generic components driven by domain-supplied data:
- `<UnderstandingCards sections={pack.understanding_sections} data={response.understanding} />`
- `<OpportunityCards opportunities={response.opportunities} />`
- `<PlanTimeline weeks={response.plan} weekSchema={pack.week_schema} />`
- `<CampaignDeck preview={response.preview} template={pack.campaign_template} />`

No more `BusinessUnderstandingCards` + `CreatorUnderstandingCards`. One component, domain-supplied data.

---

## 12. What gets removed

| Removed | Replaced by |
|---------|-------------|
| `consult.py::_extract_json` | `prachar_shared.ai_gateway.json_utils.extract_json` |
| `creator.py::_extract_json` | `prachar_shared.ai_gateway.json_utils.extract_json` |
| `consult.py::_get_or_create_brand` | shared `create_brand_from_consult(pack, ...)` |
| `creator.py::_get_or_create_creator_brand` | shared `create_brand_from_consult(pack, ...)` |
| `consult.py` campaign persistence block | shared `persist_campaign_plan(pack, ...)` |
| `creator.py` campaign persistence block | shared `persist_campaign_plan(pack, ...)` |
| `consult.py::_EXTRACT_PROMPT` | `pack.extraction_prompt` |
| `consult.py::_UNDERSTANDING_PROMPT` | assembled from `pack` prompt fragments |
| `consult.py::_CAMPAIGN_PREVIEW_PROMPT` | `pack.campaign_prompt` |
| `creator.py::_CONSULT_PROMPT` | assembled from `pack` prompt fragments |
| `creator.py::_CREATOR_CAMPAIGN_PROMPT` | `pack.campaign_prompt` |
| `creator.py` bypassing CampaignBrain | `CampaignBrain.analyse()` always called |
| `BusinessUnderstandingCards` + `CreatorUnderstandingCards` | shared `<UnderstandingCards>` |
| `OpportunityCards` + `CreatorOpportunityCards` | shared `<OpportunityCards>` |
| `PlanTimeline` + `CreatorPlanTimeline` | shared `<PlanTimeline>` |
| `CampaignPreviewDeck` + `CreatorCampaignPreview` | shared `<CampaignDeck>` |
| `BUSINESS_NAV` + `CREATOR_NAV` hard-coded | `pack.nav_items` from registry |
| `creator-dashboard.tsx` as separate file | dashboard shell + creator widget specs |

## 13. What stays

| Stays | Why |
|-------|-----|
| `CampaignBrain` (9 engines) | It's the universal intelligence engine. Both domains use it. |
| `Agency Council` (9 directors) | Universal review. Both domains benefit. |
| `AIGateway` | Universal LLM abstraction. |
| `Brand` model + `customer_type` column | Already extended. Stays. |
| `CampaignPlanRecord` | Universal campaign persistence. |
| `log_audit()` | Universal audit. |
| `json_utils`, `safety`, `observability` | Universal utilities. |
| Business dashboard UI (mostly) | Protected by instructions. Becomes widget specs. |
| Creator-specific tools (Repurpose, YouTube Plan) | Stay as **ToolSpec** in the CreatorPack. The tools are creator-only, but they're invoked through a unified `/consult/tool` endpoint, not a separate router. |

---

## 14. Risks of the refactor

| Risk | Mitigation |
|------|------------|
| Breaking existing business flow | Business Domain Pack reproduces current behaviour exactly. Regression tests verify identical output. |
| Breaking existing creator flow | Creator Domain Pack reproduces current behaviour. Creator now benefits from CampaignBrain (improvement, not regression). |
| Creator tools (Repurpose, YouTube Plan) don't fit the universal pipeline | They're ToolSpecs in the CreatorPack, invoked via `/consult/tool/{tool_id}`. The pipeline doesn't change; the tools are domain-specific extensions. |
| Migration cost for existing brands | All existing brands have `customer_type='business'` (default). They map to the BusinessPack automatically. Zero migration. |
| Performance: creator now goes through CampaignBrain (slower) | CampaignBrain.analyse() is already fast (cached, tiered). The 30-45s generation time is dominated by the understanding LLM call, not CampaignBrain. Net change: negligible. |
| Over-engineering the DomainPack contract | The contract is driven by what the audit found to be domain-specific. Nothing more. If a field isn't domain-specific, it doesn't go in the contract. |

---

## 15. Quality gates (per refactor step)

For every refactor step, answer:

1. **What duplication was removed?** — specific files/lines
2. **How many files became shared?** — count
3. **Can a new domain be added in under one day?** — yes/no, with evidence
4. **Can it be demonstrated in under 60 seconds?** — the founder demo

If the answer to #3 is NO, redesign before coding.

---

## 16. Success criteria (founder demo)

To prove the architecture works:

1. **Register a Restaurant** — pick "Business Growth" → "Restaurant" → describe → receive understanding + 30-day plan + campaign preview. Same pipeline as today.
2. **Register a Creator** — pick "Creator Growth" → "YouTube Creator" → describe channel → receive creator profile + 30-day content plan + content campaign. Same pipeline, different Domain Pack.
3. **Register a Clinic** — pick "Business Growth" → "Clinic" → describe → receive understanding + 30-day plan + patient acquisition campaign. Same pipeline, different subtype.

All three follow the **SAME pipeline**. Only the Domain Pack changes. Everything else (router, dashboard shell, campaign generator, presentation components, memory, auth, audit) is identical.

If this demonstration cannot be completed, the sprint has failed.

---

## 17. Decision

The audit is complete. The duplication is real and measured. The fix is clear: **Domain Pack Architecture with a Universal Pipeline**. The contract is driven by the audit findings — nothing more, nothing less.

**Proceeding with implementation.**

Build order:
1. Domain Pack framework (`base.py` protocol + registry)
2. BusinessPack + CreatorPack (extract existing logic into packs)
3. Universal Consult Engine (replaces `/consult` + `/creator/consult`)
4. Unified campaign generator (replaces `/consult/campaign` + `/creator/campaign`)
5. Shared persistence helpers (`create_brand_from_consult`, `persist_campaign_plan`)
6. Shared presentation layer (generic UnderstandingCards, OpportunityCards, PlanTimeline, CampaignDeck)
7. Unified dashboard shell with widget slots
8. Sidebar driven by Domain Pack nav_items
9. Creator tools (Repurpose, YouTube Plan) as ToolSpecs
10. RestaurantPack + ClinicPack (prove the architecture — add a domain in under one day)
11. Architecture tests (no duplication, no circular deps, plugin isolation)
12. Regression tests (business + creator flows unchanged)
13. Migration guide
14. Founder demo
