# PRACHAR Roadmap 2 — Polish, AI Quality, Integrations

> **Goal:** Transform PRACHAR from "feature-complete" to "feels like a senior marketing agency partner".
>
> **Three phases, executed sequentially:** A (Polish) → B (AI Quality) → C (Integrations).
> Phase A must complete before B — polish exposes the UX problems that B's strategy layer needs to sit inside.
> Phase B must complete before C — BRO needs to reason strategically before reasoning from live data.

## How this differs from Roadmap 1

| Roadmap 1 | Roadmap 2 |
|-----------|-----------|
| Additive (new files, new endpoints) | Phase A is **refactor** (touches existing files) |
| Easy to parallelize (one file per part) | Phase A touches shared components → careful splitting |
| 47 parts, 8 waves | ~20 parts, smaller waves |
| Backend-heavy | Phase A is **frontend-heavy** |

## Workspace-safety rules (same as Roadmap 1)

1. `make test` green before starting each part
2. Tests written alongside code
3. `make test` green after each part (pytest + typecheck + build)
4. Backward compatible — don't break existing journeys
5. One concern per part
6. **NEW for Phase A:** never run two parts that touch the same shared component in parallel

---

# Phase A — Product Polish (2-3 weeks)

> **Mandatory rule:** No new features. Audit and improve what exists.
>
> **Approach:** Split by screen. Each screen is one part. Shared components (SharedPresentation.tsx, layout.tsx) get their own part, done sequentially after screens.

## A.0 — Polish audit document (mandatory, no code until complete)

### Part A.0.1 — UX audit of every screen 🟢
- **Deliverable:** A `POLISH_AUDIT.md` document auditing every screen against the founder's criteria:
  - Dashboard: does every card answer "Why should I care?"? List empty states. Loading animation quality. Typography. Spacing. Mobile-first issues.
  - Campaign Builder: does it feel like a form or a consultant? Are recommendations explained?
  - Creative Studio: what's editable? What regeneration granularity exists?
  - Review Queue: how does it compare to Google Docs? Inline comments? Version history?
  - Performance: is it dashboards or stories? What stories should it tell?
- **Files:** `POLISH_AUDIT.md` (new)
- **Verification:** Document exists and is comprehensive.
- **Dependencies:** None.
- **Why first:** Mandatory — no code until the audit identifies the actual problems.

## A.1 — Dashboard polish

### Part A.1.1 — Dashboard "why should I care?" pass 🟡
- **Deliverable:** Every card on the dashboard has a clear value proposition. Remove cards that don't answer "why should I care?". Add 1-line context to each card explaining what it means for the user.
- **Files:** `apps/web/src/app/app/page.tsx`
- **Verification:** Typecheck + build pass. Visual review.
- **Dependencies:** A.0.1.

### Part A.1.2 — Dashboard empty states + loading 🟢
- **Deliverable:** Remove all empty states (per founder's instruction). Replace with skeleton loading that matches the final content shape. Improve loading animations (smooth transitions, not jarring jumps).
- **Files:** `apps/web/src/app/app/page.tsx`
- **Verification:** Typecheck + build pass.
- **Dependencies:** A.1.1 (same file — sequential).

### Part A.1.3 — Dashboard typography + spacing + mobile 🟡
- **Deliverable:** Audit typography hierarchy (headings, body, captions). Fix spacing inconsistencies. Make it mobile-first (test at 375px, 768px, 1024px). Cards stack on mobile, grid on desktop.
- **Files:** `apps/web/src/app/app/page.tsx`, possibly `apps/web/src/components/ui/` for shared spacing utilities
- **Verification:** Typecheck + build pass. Visual review at 3 mobile breakpoints.
- **Dependencies:** A.1.2.

## A.2 — Campaign Builder polish

### Part A.2.1 — Campaign Builder "consultant not form" pass 🔴
- **Deliverable:** Reframe the campaign creation flow as a conversation with a senior marketing consultant. Every recommendation explains "Why this campaign?". Add reasoning blocks: "I'm recommending this because your audience is X, your goal is Y, and this approach worked for similar businesses."
- **Files:** `apps/web/src/app/app/brands/[id]/campaigns/new/page.tsx`, possibly `apps/web/src/components/consult/SharedPresentation.tsx`
- **Verification:** Typecheck + build pass. The flow reads like a consultant, not a form.
- **Dependencies:** A.0.1.

### Part A.2.2 — Campaign results "why" explanations 🟡
- **Deliverable:** Every section of the campaign results (Executive Summary, Budget, What we'll post, Next actions) has a "Why" explanation. "Why this budget split? Because Instagram delivers 3x ROAS for your industry."
- **Files:** `apps/web/src/components/consult/SharedPresentation.tsx` (the results deck)
- **Verification:** Typecheck + build pass.
- **Dependencies:** A.2.1 (shared component — sequential).

## A.3 — Creative Studio polish

### Part A.3.1 — Creative Studio granular regeneration 🔴
- **Deliverable:** Each generated creative is editable. Add per-field regeneration:
  - Regenerate only headline
  - Regenerate only CTA
  - Regenerate only offer
  - Regenerate only colours
  - Regenerate only tone
  - (Not regenerate everything)
- **Files:**
  - `apps/web/src/app/app/creative-studio/page.tsx` (add per-field regenerate buttons)
  - `apps/web/src/components/creative-studio/FormatPreview.tsx` (make fields editable)
  - `apps/api/prachar_api/routers/creative_studio.py` (add `POST /creative-studio/regenerate-field` endpoint)
  - `packages/shared/prachar_shared/creative_studio/studio.py` (add `regenerate_field()` method)
  - `packages/shared/prachar_shared/creative_studio/formats/*.py` (each format adds a `regenerate_field()` function)
- **Verification:** Typecheck + build pass. New tests for the regenerate-field endpoint.
- **Dependencies:** A.0.1.
- **Note:** This is the largest part in Phase A. May need to be split further.

### Part A.3.2 — Creative Studio inline editing 🟡
- **Deliverable:** Every generated creative field is inline-editable (click to edit, like the Review queue). Save edits to the package.
- **Files:** `apps/web/src/components/creative-studio/FormatPreview.tsx`, `apps/web/src/app/app/creative-studio/page.tsx`
- **Verification:** Typecheck + build pass.
- **Dependencies:** A.3.1 (same files — sequential).

## A.4 — Review Queue polish

### Part A.4.1 — Review Queue Google Docs-style inline comments 🔴
- **Deliverable:** Add inline comments to the review detail page. Users can highlight a section and add a comment. Comments are threaded. Resolvable.
- **Files:**
  - `apps/web/src/app/app/review/[id]/page.tsx`
  - NEW `apps/web/src/components/review/InlineComments.tsx`
  - `apps/api/prachar_api/routers/review.py` (add comment endpoints: POST /{id}/comments, GET /{id}/comments, POST /{id}/comments/{cid}/resolve)
  - `apps/api/prachar_api/models/tables.py` (add ReviewComment table)
  - NEW migration
- **Verification:** Typecheck + build pass. New tests for comment endpoints.
- **Dependencies:** A.0.1.

### Part A.4.2 — Review Queue version history 🟡
- **Deliverable:** Every edit creates a version. Users can view version history, compare versions, restore a previous version. Like Google Docs.
- **Files:**
  - `apps/api/prachar_api/routers/review.py` (add GET /{id}/versions, GET /{id}/versions/{vid})
  - `apps/api/prachar_api/models/tables.py` (add ReviewVersion table, or use existing audit log)
  - NEW migration
  - `apps/web/src/app/app/review/[id]/page.tsx` (version history panel)
  - NEW `apps/web/src/components/review/VersionHistory.tsx`
- **Verification:** Typecheck + build pass. New tests.
- **Dependencies:** A.4.1 (same router — sequential).

### Part A.4.3 — Review Queue approve/reject flow polish 🟢
- **Deliverable:** Approve and Reject feel deliberate. Confirm modal. Reject requires a reason. Approve triggers a "What happens next" explanation.
- **Files:** `apps/web/src/app/app/review/[id]/page.tsx`
- **Verification:** Typecheck + build pass.
- **Dependencies:** A.4.1.

## A.5 — Performance polish

### Part A.5.1 — Performance "stories not dashboards" rewrite 🔴
- **Deliverable:** Rewrite the performance page to tell stories instead of showing dashboards. Example:
  > "This week's campaign generated 31 enquiries. Instagram delivered 74%. WhatsApp generated the highest conversion. Weekend campaigns outperform weekdays by 28%."
- **Files:**
  - `apps/web/src/app/app/performance/[id]/page.tsx` (rewrite)
  - `apps/api/prachar_api/routers/performance.py` (add `GET /{campaign_id}/story` endpoint that returns a narrative)
  - `packages/shared/prachar_shared/marketing_intelligence/performance_engine.py` (add `tell_story()` method)
- **Verification:** Typecheck + build pass. New tests for story endpoint.
- **Dependencies:** A.0.1.

### Part A.5.2 — Performance keep charts as supporting evidence 🟢
- **Deliverable:** Charts remain, but as supporting evidence for the story, not the main content. Place charts below the narrative, labeled "Here's the data behind this story."
- **Files:** `apps/web/src/app/app/performance/[id]/page.tsx`
- **Verification:** Typecheck + build pass.
- **Dependencies:** A.5.1 (same file — sequential).

## A.6 — Shared component polish (sequential, after screens)

### Part A.6.1 — SharedPresentation polish 🟡
- **Deliverable:** Audit and polish the SharedPresentation component (used by dashboard, campaign results, creative studio). Consistent typography, spacing, mobile-first.
- **Files:** `apps/web/src/components/consult/SharedPresentation.tsx`
- **Verification:** Typecheck + build pass. All screens that use it still render correctly.
- **Dependencies:** A.1-A.5 (after all screens are polished, so changes here don't conflict).

### Part A.6.2 — Layout + sidebar polish 🟢
- **Deliverable:** Audit the sidebar and top bar. Mobile-first (collapsible sidebar on mobile). Bell icon, user menu, brand switcher all work on mobile.
- **Files:** `apps/web/src/app/app/layout.tsx`
- **Verification:** Typecheck + build pass. Mobile sidebar works.
- **Dependencies:** A.6.1.

---

# Phase B — AI Quality (1-2 weeks)

> **Goal:** BRO thinks like a strategist, not just a generator. For every campaign, generate 3 strategies (primary, alternative, contrarian) and explain why BRO chose the primary.
>
> **Why after Phase A:** The strategy layer sits inside the campaign builder UX. If the builder feels like a form (Phase A problem), the strategy explanation won't land.

## B.1 — Strategy generation

### Part B.1.1 — Strategy engine 🟡
- **Deliverable:** A `StrategyEngine` that generates 3 strategies per campaign:
  - **Primary strategy** — the recommended approach
  - **Alternative strategy** — a different valid approach
  - **Contrarian strategy** — an unconventional approach that could work
  Each strategy: {name, approach, why_it_works, risks, expected_outcome}
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/strategy_engine.py` (new)
  - `packages/shared/prachar_shared/domain_packs/base.py` (add `strategy_prompt` field)
  - 4 domain packs (add strategy_prompt)
  - `apps/api/prachar_api/infrastructure/consult_engine.py` (call strategy engine in campaign flow)
- **Verification:** New tests. All existing tests pass.
- **Dependencies:** Phase A complete.

### Part B.1.2 — Strategy explanation ("Why A not B") 🟡
- **Deliverable:** After generating 3 strategies, BRO explains why it chose the primary over the alternative and contrarian. The explanation considers: brand context, audience, budget, past performance (from P4.6 feedback loop).
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/strategy_engine.py` (add `explain_choice()` method)
  - `apps/api/prachar_api/infrastructure/consult_engine.py` (attach explanation to preview)
- **Verification:** New tests. All existing tests pass.
- **Dependencies:** B.1.1.

## B.2 — Strategy UI

### Part B.2.1 — Strategy presentation in campaign builder 🔴
- **Deliverable:** The campaign builder shows 3 strategies as cards. Primary is highlighted. Clicking "Why?" shows BRO's explanation. User can switch to alternative or contrarian (which regenerates the campaign with that strategy).
- **Files:**
  - `apps/web/src/app/app/brands/[id]/campaigns/new/page.tsx`
  - `apps/web/src/components/consult/SharedPresentation.tsx` (add StrategySection)
  - `apps/web/src/lib/unified-consult.ts` (add strategy types)
- **Verification:** Typecheck + build pass.
- **Dependencies:** B.1.2.

### Part B.2.2 — Strategy comparison view 🟡
- **Deliverable:** A side-by-side comparison of the 3 strategies (approach, risks, expected outcome). Helps the user understand the tradeoffs.
- **Files:** `apps/web/src/components/consult/SharedPresentation.tsx` (add StrategyComparison component)
- **Verification:** Typecheck + build pass.
- **Dependencies:** B.2.1.

---

# Phase C — Integrations (2-3 weeks)

> **Goal:** Connect to real platforms so BRO reasons from live performance, not assumptions.
>
> **Why after Phase B:** BRO needs to think strategically (Phase B) before it can reason from live data (Phase C). Otherwise it's just a dashboard.
>
> **Approach:** The adapters already exist (from S2-S8 sprints). The work is: (1) wire adapters to pull live data into the performance engine, (2) surface live data in BRO's reasoning, (3) let BRO publish to real platforms.

## C.1 — Live data ingestion

### Part C.1.1 — Wire Google Business Profile 🟡
- **Deliverable:** Pull live data from Google Business Profile (search impressions, directions, calls, photos views) into CampaignPerformance. BRO reasons from it.
- **Files:**
  - `apps/workers/prachar_workers/performance.py` (add GBP ingestion)
  - `packages/shared/prachar_shared/adapters/organic/` (verify GMBAdapter works)
- **Verification:** New tests. Worker pulls GBP data.
- **Dependencies:** Phase B complete.

### Part C.1.2 — Wire Meta (Facebook + Instagram) 🟡
- **Deliverable:** Pull live data from Meta (reach, impressions, clicks, conversions) into CampaignPerformance.
- **Files:** `apps/workers/prachar_workers/performance.py`, `packages/shared/prachar_shared/adapters/ads/meta.py`
- **Verification:** New tests.
- **Dependencies:** C.1.1 (same file — sequential).

### Part C.1.3 — Wire LinkedIn 🟢
- **Deliverable:** Pull live data from LinkedIn (impressions, clicks, engagement).
- **Files:** `apps/workers/prachar_workers/performance.py`, `packages/shared/prachar_shared/adapters/`
- **Verification:** New tests.
- **Dependencies:** C.1.2.

### Part C.1.4 — Wire WhatsApp Business 🟢
- **Deliverable:** Pull live data from WhatsApp Business (messages sent, delivered, read, replied).
- **Files:** `apps/workers/prachar_workers/performance.py`, `packages/shared/prachar_shared/adapters/`
- **Verification:** New tests.
- **Dependencies:** C.1.2.

### Part C.1.5 — Wire Google Ads + Meta Ads 🟡
- **Deliverable:** Pull live ad performance (impressions, clicks, conversions, spend, ROAS) from Google Ads and Meta Ads.
- **Files:** `apps/workers/prachar_workers/performance.py`, `packages/shared/prachar_shared/adapters/ads/`
- **Verification:** New tests.
- **Dependencies:** C.1.2.

### Part C.1.6 — Wire YouTube 🟢
- **Deliverable:** Pull live YouTube analytics (views, watch time, subscribers, clicks).
- **Files:** `apps/workers/prachar_workers/performance.py`, `packages/shared/prachar_shared/adapters/`
- **Verification:** New tests.
- **Dependencies:** C.1.2.

## C.2 — BRO reasons from live data

### Part C.2.1 — BRO live data context 🟡
- **Deliverable:** When BRO generates a campaign or proactive recommendation, it includes live performance data from connected platforms. "Your Instagram reached 12K people last week with 3% engagement. I recommend doubling down on Reels."
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/brain.py` (load live data in generate_campaign)
  - `packages/shared/prachar_shared/marketing_intelligence/proactive_engine.py` (include live data in anomaly context)
- **Verification:** New tests. BRO mentions live data in output.
- **Dependencies:** C.1.1-C.1.6 (all ingestion wired).

### Part C.2.2 — Live data in performance stories 🟢
- **Deliverable:** The performance stories (from A.5.1) now include live data from all connected platforms. "Instagram delivered 74% of enquiries. WhatsApp had the highest conversion rate at 12%."
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/performance_engine.py` (tell_story uses live data)
  - `apps/api/prachar_api/routers/performance.py` (story endpoint includes live data)
- **Verification:** New tests.
- **Dependencies:** C.2.1.

## C.3 — BRO publishes to real platforms

### Part C.3.1 — Publish to Google Business Profile 🟢
- **Deliverable:** When a campaign is approved, BRO publishes the Google Business Profile posts (offers, photos, updates).
- **Files:** `apps/workers/prachar_workers/publish.py`, `packages/shared/prachar_shared/adapters/organic/gmb.py`
- **Verification:** New tests.
- **Dependencies:** C.2.1.

### Part C.3.2 — Publish to Meta (Facebook + Instagram) 🟡
- **Deliverable:** BRO publishes Facebook posts and Instagram posts/reels from approved campaigns.
- **Files:** `apps/workers/prachar_workers/publish.py`, `packages/shared/prachar_shared/adapters/organic/`
- **Verification:** New tests.
- **Dependencies:** C.3.1.

### Part C.3.3 — Publish to WhatsApp Business 🟢
- **Deliverable:** BRO sends WhatsApp broadcast messages (with opt-in compliance) from approved campaigns.
- **Files:** `apps/workers/prachar_workers/publish.py`, `packages/shared/prachar_shared/adapters/organic/whatsapp.py`
- **Verification:** New tests.
- **Dependencies:** C.3.1.

### Part C.3.4 — Launch Google Ads + Meta Ads campaigns 🟡
- **Deliverable:** BRO creates and launches Google Ads and Meta Ads campaigns from approved campaign plans.
- **Files:** `apps/workers/prachar_workers/publish.py`, `packages/shared/prachar_shared/adapters/ads/`
- **Verification:** New tests.
- **Dependencies:** C.3.2.

---

# Execution summary

## Part count by phase

| Phase | Parts | Small 🟢 | Medium 🟡 | Large 🔴 |
|-------|-------|----------|-----------|----------|
| A Polish | 14 | 4 | 6 | 4 |
| B AI Quality | 4 | 0 | 3 | 1 |
| C Integrations | 13 | 6 | 5 | 2 |
| **Total** | **31** | **10** | **14** | **7** |

## Recommended execution order

### Phase A (sequential within screens, parallel across screens where safe)
1. **A.0.1** — UX audit document (mandatory, no code)
2. **A.1.1 + A.2.1 + A.3.1 + A.4.1 + A.5.1** — First pass on all 5 screens (parallel if no shared component overlap — A.2.1 and A.5.1 both touch SharedPresentation, so run sequentially)
3. **A.1.2 + A.3.2 + A.4.3 + A.5.2** — Second pass on screens (parallel)
4. **A.1.3 + A.4.2** — Third pass (parallel)
5. **A.6.1** — SharedPresentation polish (after all screens)
6. **A.6.2** — Layout polish (after A.6.1)

### Phase B (sequential)
1. **B.1.1** — Strategy engine
2. **B.1.2** — Strategy explanation
3. **B.2.1** — Strategy UI in campaign builder
4. **B.2.2** — Strategy comparison view

### Phase C (parallel within phases)
1. **C.1.1** — Wire GBP
2. **C.1.2** — Wire Meta (after C.1.1)
3. **C.1.3 + C.1.4 + C.1.5 + C.1.6** — Wire LinkedIn, WhatsApp, Ads, YouTube (parallel after C.1.2)
4. **C.2.1** — BRO live data context (after all C.1)
5. **C.2.2** — Live data in stories
6. **C.3.1** — Publish to GBP
7. **C.3.2** — Publish to Meta (after C.3.1)
8. **C.3.3 + C.3.4** — Publish to WhatsApp + Ads (parallel after C.3.2)

## Files touched per phase (overlap analysis)

| Phase | Primary files | Shared files |
|-------|---------------|--------------|
| A | `apps/web/src/app/app/*.tsx` (per screen) | `SharedPresentation.tsx`, `layout.tsx` (A.6 only) |
| B | `marketing_intelligence/strategy_engine.py` (new), domain packs, `consult_engine.py`, `SharedPresentation.tsx` | `SharedPresentation.tsx` (B.2) |
| C | `apps/workers/prachar_workers/performance.py`, `publish.py`, `adapters/` | `performance.py` (all C.1 share it — sequential) |

## Key risk: Phase A touches existing files

Unlike Roadmap 1 (mostly new files), Phase A modifies existing screens. **Mitigation:**
- Split by screen (one part per screen)
- Shared components (SharedPresentation, layout) get their own part, done last
- Never run two parts that touch the same file in parallel
- Visual review after each part (not just tests)

## Success metrics

| Phase | Metric |
|-------|--------|
| A Polish | Founder reviews each screen and says "this feels right". Mobile works at 375px. No empty states. Every card answers "why should I care?". |
| B AI Quality | Every campaign shows 3 strategies + "why A not B" explanation. Founder can switch strategies. |
| C Integrations | BRO references live data in recommendations. Founder can publish to Google, Meta, WhatsApp, YouTube from one approve button. |
