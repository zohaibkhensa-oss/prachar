# PRACHAR Product Roadmap — Five Programmes

> **Goal:** Transform PRACHAR from a campaign generator into an AI marketing agency.
>
> **Operating principle:** Every part must leave the workspace unbroken.
> After each part: tests pass, build passes, typecheck passes, no regressions.
> Each part is one PR-sized chunk — small enough to review, big enough to matter.

## How this roadmap is structured

- **Programme** = a strategic initiative (5 total)
- **Phase** = a milestone within a programme (2-4 per programme)
- **Part** = a single deliverable chunk (one Devin session, one PR)
  - Each part has: deliverable, files touched, verification, dependencies, scope
  - Scope: 🟢 small (≤200 lines), 🟡 medium (200-600 lines), 🔴 large (600+ lines)
- **Order:** Programmes are ordered by ROI and dependencies, but parts within
  a programme can run in parallel with parts from other programmes if they
  don't touch the same files.

## Dependency graph (programme level)

```
P1 Campaign Quality ──┐
                      ├─→ P2 Creative Studio ──→ P3 Human-in-the-loop ──→ P4 Performance Intelligence ──→ P5 AI Marketing Director
                      └───────────────────────────────────────────────────────────────────────┘
```

- **P1 is foundational** — better campaigns make every downstream programme better.
- **P2 depends on P1** — creatives are generated from campaign concepts.
- **P3 depends on P2** — you review creatives, not abstract campaigns.
- **P4 depends on P3** — you measure published campaigns, not drafts.
- **P5 depends on P4** — proactive recommendations need performance data.

**Recommended execution order:** P1 → P2 → P3 → P4 → P5. But P1 parts can run in parallel with P2 scaffolding, etc.

## Workspace-safety rules (apply to every part)

1. **Before starting a part:** run `make test` and confirm green baseline.
2. **During a part:** write/extend tests alongside code. No untested code.
3. **After a part:** run `make test` (pytest + typecheck + build). Must be green.
4. **Backward compatibility:** never break existing endpoints/UI. Add new ones; deprecate old ones later.
5. **One concern per part:** don't mix schema changes with UI changes with prompt changes.
6. **Migration files:** one Alembic migration per schema change. Never edit a merged migration.

---

# Programme 1: Campaign Quality

> **Goal:** Every campaign feels like it came from a top marketing agency.
>
> **Why first:** Highest ROI. Every downstream programme (Creative Studio,
> Human-in-the-loop, Performance) depends on campaign quality. Bad campaigns
> → bad creatives → bad reviews → bad performance → bad recommendations.
>
> **Approach:** Enhance the Domain Pack campaign prompts + add "quality modules"
> that layer agency-grade thinking on top of the existing CampaignBrain output.
> No new engines — we extend the existing CreativeDirectionEngine and add
> post-processing layers.

## P1 Phase 1: Multi-creative-direction foundation

### Part 1.1 — Add `creative_directions` field to campaign preview 🟢
- **Deliverable:** Campaign preview returns 3 creative directions (not 1).
  Each direction has: hook, angle, tone, sample headline, sample CTA.
- **Files:**
  - `packages/shared/prachar_shared/domain_packs/base.py` (add `creative_directions_schema` to DomainPack)
  - `packages/shared/prachar_shared/domain_packs/*/pack.py` (add creative directions prompt fragment to each pack)
  - `apps/api/prachar_api/infrastructure/consult_engine.py` (extend `_generate_campaign_preview` to include directions)
  - `apps/web/src/components/consult/SharedPresentation.tsx` (render 3 directions in CampaignDeck)
- **Verification:** `test_unified_consult.py` updated to check directions field. Build passes.
- **Dependencies:** None (builds on Unified Intelligence Sprint).
- **Why this first:** Unblocks A/B concepts (Part 1.8) and Creative Studio (P2).

### Part 1.2 — Strengthen hooks module 🟢
- **Deliverable:** A `hooks.py` module that generates 5 hook patterns per campaign
  (question, stat, story, contrarian, aspiration). Each hook has: pattern, copy, why-it-works.
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/hooks.py` (new)
  - `packages/shared/prachar_shared/domain_packs/*/pack.py` (add `hooks_prompt` fragment)
  - `apps/api/prachar_api/infrastructure/consult_engine.py` (call hooks module in campaign flow)
- **Verification:** New `test_hooks.py`. Existing tests pass.
- **Dependencies:** Part 1.1.

### Part 1.3 — Audience psychology layer 🟡
- **Deliverable:** Each campaign includes an "audience psychology" section:
  top 3 motivations, top 3 objections, emotional triggers, decision style.
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/audience_psychology.py` (new)
  - `packages/shared/prachar_shared/domain_packs/*/pack.py` (add psychology prompt fragment)
  - `apps/api/prachar_api/infrastructure/consult_engine.py` (call psychology module)
  - `apps/web/src/components/consult/SharedPresentation.tsx` (render psychology section)
- **Verification:** New `test_audience_psychology.py`. Build passes.
- **Dependencies:** Part 1.1.

## P1 Phase 2: Offer & pricing engineering

### Part 1.4 — Offer engineering module 🟡
- **Deliverable:** Each campaign includes 3 engineered offers (not just "20% off").
  Offers use: anchoring, scarcity, bundling, loss-aversion, decoy pricing.
  Each offer has: structure, copy, psychology lever, expected conversion lift.
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/offer_engine.py` (new)
  - `packages/shared/prachar_shared/domain_packs/*/pack.py` (offer prompt fragments per domain — restaurant offers differ from clinic offers)
  - `apps/api/prachar_api/infrastructure/consult_engine.py`
  - `apps/web/src/components/consult/SharedPresentation.tsx`
- **Verification:** `test_offer_engine.py`. Domain-specific offer tests (restaurant vs clinic).
- **Dependencies:** Part 1.1.

### Part 1.5 — Pricing psychology module 🟢
- **Deliverable:** For campaigns with pricing, generate 3 pricing presentations
  (charm pricing, tier pricing, bundle pricing) with rationale.
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/pricing_psychology.py` (new)
  - Domain packs (pricing prompt fragments)
- **Verification:** `test_pricing_psychology.py`.
- **Dependencies:** Part 1.4.

## P1 Phase 3: Contextual intelligence

### Part 1.6 — Seasonal ideas module 🟢
- **Deliverable:** Each campaign includes seasonal hooks (current month + next 2 months).
  Domain-specific: restaurant (festive menus), clinic (seasonal checkups), creator (trending topics).
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/seasonal_engine.py` (new)
  - Domain packs (seasonal prompt fragments)
- **Verification:** `test_seasonal_engine.py`. Tests for current-month awareness.
- **Dependencies:** Part 1.1.

### Part 1.7 — Local marketing module 🟢
- **Deliverable:** For businesses with a location, generate local marketing ideas
  (local events, local partnerships, geo-targeted copy, local SEO terms).
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/local_engine.py` (new)
  - Domain packs (local prompt fragments — only for business-type packs, not creator)
- **Verification:** `test_local_engine.py`. Skip test for creator pack.
- **Dependencies:** Part 1.1.

### Part 1.8 — Competitor differentiation module 🟡
- **Deliverable:** Each campaign includes a "differentiation matrix" —
  3-5 competitor claims + how this brand's campaign counters each.
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/differentiation_engine.py` (new)
  - Domain packs (differentiation prompt fragments)
  - `apps/web/src/components/consult/SharedPresentation.tsx` (render differentiation matrix)
- **Verification:** `test_differentiation_engine.py`.
- **Dependencies:** Part 1.1.

## P1 Phase 4: A/B concepts

### Part 1.9 — A/B concept generator 🟡
- **Deliverable:** For each creative direction (from 1.1), generate an A/B variant
  with a different hook/angle. Total: 6 concepts (3 directions × 2 variants).
  Each variant has: what changed, why, expected audience segment.
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/ab_concepts.py` (new)
  - `apps/api/prachar_api/infrastructure/consult_engine.py`
  - `apps/web/src/components/consult/SharedPresentation.tsx` (A/B toggle UI)
- **Verification:** `test_ab_concepts.py`. Build passes.
- **Dependencies:** Parts 1.1, 1.2.

### Part 1.10 — Campaign Quality regression suite 🟢
- **Deliverable:** A test suite that verifies every campaign includes all quality
  modules (directions, hooks, psychology, offers, pricing, seasonal, local, differentiation, A/B).
- **Files:**
  - `apps/api/prachar_api/tests/test_campaign_quality.py` (new)
- **Verification:** The suite itself. Run after every P1 part.
- **Dependencies:** All P1 parts.

---

# Programme 2: Creative Studio

> **Goal:** One click produces a complete marketing package — campaign → poster →
> video → carousel → story → WhatsApp → Facebook → LinkedIn → email → landing page.
>
> **Why:** This is Prachar's "wow". The user shouldn't feel like they're juggling tools.
>
> **Approach:** Build on the Domain Pack architecture. Each creative format is a
> `CreativeFormatSpec` (like `ToolSpec`). The Creative Studio orchestrates all
> formats from one campaign. No new engines — uses AIGateway with format-specific
> prompts.

## P2 Phase 1: Format specs & orchestration

### Part 2.1 — Creative Format Spec framework 🟢
- **Deliverable:** `CreativeFormatSpec` dataclass + registry (like DomainPack registry).
  Each spec defines: id, label, output_schema, prompt_template, max_tokens, tier.
  10 format specs defined: poster, video_script, carousel, story, whatsapp, facebook, linkedin, email, landing_page, sms.
- **Files:**
  - `packages/shared/prachar_shared/creative_studio/base.py` (new)
  - `packages/shared/prachar_shared/creative_studio/formats/` (10 format files)
  - `packages/shared/prachar_shared/creative_studio/__init__.py` (registry)
- **Verification:** `test_creative_formats.py`. Each format has a spec.
- **Dependencies:** P1 Part 1.1 (campaign needs creative_directions to seed formats).

### Part 2.2 — Creative Studio engine 🟡
- **Deliverable:** `CreativeStudio` class that takes a campaign + creative_direction
  and generates all 10 formats in parallel (async). Returns a `CreativePackage`.
- **Files:**
  - `packages/shared/prachar_shared/creative_studio/studio.py` (new)
  - `apps/api/prachar_api/infrastructure/creative_studio_engine.py` (new — wraps studio for API)
- **Verification:** `test_creative_studio.py`. Mock AIGateway, verify all 10 formats generated.
- **Dependencies:** Part 2.1.

### Part 2.3 — Creative Studio API endpoints 🟢
- **Deliverable:** 3 endpoints:
  - `POST /creative-studio/generate` — generate all formats from a campaign
  - `POST /creative-studio/generate/{format_id}` — generate one format
  - `GET /creative-studio/{package_id}` — retrieve a saved package
- **Files:**
  - `apps/api/prachar_api/routers/creative_studio.py` (new)
  - `apps/api/prachar_api/models/tables.py` (add `CreativePackage` table)
  - `apps/api/alembic/versions/0005_creative_package.py` (new migration)
- **Verification:** `test_creative_studio_api.py`. Auth required, packages persisted.
- **Dependencies:** Part 2.2.

## P2 Phase 2: Format implementations

> Each format is ONE file. Can be done in parallel. Each is 🟢 small.

### Part 2.4 — Poster format 🟢
- **Deliverable:** Poster spec with: headline, subheadline, body, CTA, visual brief,
  color palette, layout hint. Domain-specific (restaurant poster ≠ clinic poster).
- **Files:** `packages/shared/prachar_shared/creative_studio/formats/poster.py`
- **Verification:** `test_poster_format.py`.
- **Dependencies:** Part 2.1.

### Part 2.5 — Video script format 🟢
- **Deliverable:** 30-sec video script with: scene-by-scene, voiceover, on-screen text,
  b-roll suggestions, music mood. Domain-specific.
- **Files:** `packages/shared/prachar_shared/creative_studio/formats/video_script.py`
- **Verification:** `test_video_script_format.py`.
- **Dependencies:** Part 2.1.

### Part 2.6 — Carousel format 🟢
- **Deliverable:** 5-7 slide carousel with: slide number, headline, body, visual brief, CTA on last slide.
- **Files:** `packages/shared/prachar_shared/creative_studio/formats/carousel.py`
- **Verification:** `test_carousel_format.py`.
- **Dependencies:** Part 2.1.

### Part 2.7 — Instagram Story format 🟢
- **Deliverable:** 3-5 story frames with: frame type (poll/question/quiz/text),
  copy, visual brief, sticker suggestions.
- **Files:** `packages/shared/prachar_shared/creative_studio/formats/story.py`
- **Verification:** `test_story_format.py`.
- **Dependencies:** Part 2.1.

### Part 2.8 — WhatsApp format 🟢
- **Deliverable:** WhatsApp status (text + image brief) + broadcast message template.
  Compliance-aware (opt-in language for broadcast).
- **Files:** `packages/shared/prachar_shared/creative_studio/formats/whatsapp.py`
- **Verification:** `test_whatsapp_format.py`.
- **Dependencies:** Part 2.1.

### Part 2.9 — Facebook post format 🟢
- **Deliverable:** Facebook post with: copy (≤500 chars), image brief, link description.
- **Files:** `packages/shared/prachar_shared/creative_studio/formats/facebook.py`
- **Verification:** `test_facebook_format.py`.
- **Dependencies:** Part 2.1.

### Part 2.10 — LinkedIn post format 🟢
- **Deliverable:** LinkedIn post with: professional copy (≤3000 chars), hook, body, CTA, hashtags.
- **Files:** `packages/shared/prachar_shared/creative_studio/formats/linkedin.py`
- **Verification:** `test_linkedin_format.py`.
- **Dependencies:** Part 2.1.

### Part 2.11 — Email format 🟡
- **Deliverable:** Email with: subject line (3 variants), preview text, body (HTML brief),
  CTA, P.S. line. Domain-specific.
- **Files:** `packages/shared/prachar_shared/creative_studio/formats/email.py`
- **Verification:** `test_email_format.py`.
- **Dependencies:** Part 2.1.

### Part 2.12 — Landing page format 🟡
- **Deliverable:** Landing page brief with: hero headline, hero subhead, 3 benefit sections,
  social proof section, FAQ, CTA, form fields. Section-by-section copy.
- **Files:** `packages/shared/prachar_shared/creative_studio/formats/landing_page.py`
- **Verification:** `test_landing_page_format.py`.
- **Dependencies:** Part 2.1.

### Part 2.13 — SMS format 🟢
- **Deliverable:** SMS with: 2 variants (160 char, 320 char), compliance-aware (opt-out language).
- **Files:** `packages/shared/prachar_shared/creative_studio/formats/sms.py`
- **Verification:** `test_sms_format.py`.
- **Dependencies:** Part 2.1.

## P2 Phase 3: Creative Studio UI

### Part 2.14 — Creative Studio page 🔴
- **Deliverable:** `/app/creative-studio` page. Input: select campaign + creative direction.
  Output: tabbed view of all 10 formats. Each format: preview + copy button + regenerate button.
  "Generate All" button with progress indicator.
- **Files:**
  - `apps/web/src/app/app/creative-studio/page.tsx` (new)
  - `apps/web/src/components/creative-studio/` (format preview components)
  - `apps/web/src/lib/creative-studio.ts` (API client)
- **Verification:** Typecheck passes. Build passes. Page renders.
- **Dependencies:** Parts 2.3-2.13 (all formats).

### Part 2.15 — Creative Studio sidebar entry 🟢
- **Deliverable:** Add "Creative Studio" to all domain pack nav_sections.
- **Files:** `packages/shared/prachar_shared/domain_packs/*/pack.py`
- **Verification:** Architecture tests pass. Nav endpoint returns Creative Studio.
- **Dependencies:** Part 2.14.

---

# Programme 3: Human-in-the-loop

> **Goal:** AI behaves like an agency — draft → review → suggestions → founder edits → approve → publish.
>
> **Why:** Trust. Users won't auto-publish. They need to feel in control.
>
> **Approach:** Extend the existing `CampaignStatus` enum + `AssetStatus` enum with
> review states. Add a review queue. Add inline editing. No new engines —
> this is workflow + UI.

## P3 Phase 1: Review state machine

### Part 3.1 — Extend campaign/asset status enums 🟢
- **Deliverable:** Add `in_review`, `changes_requested`, `approved` to CampaignStatus.
  Add same to AssetStatus. Migration to update existing rows.
- **Files:**
  - `apps/api/prachar_api/models/enums.py`
  - `apps/api/alembic/versions/0006_review_statuses.py`
- **Verification:** Existing tests pass (enum changes are additive). Migration up/down works.
- **Dependencies:** None (foundational for P3).

### Part 3.2 — Review queue API 🟡
- **Deliverable:** Endpoints:
  - `GET /review/queue` — list all drafts + in_review items for tenant
  - `POST /review/{id}/request-changes` — move to changes_requested with feedback
  - `POST /review/{id}/approve` — move to approved
  - `POST /review/{id}/publish` — move to published (triggers channel publish)
- **Files:**
  - `apps/api/prachar_api/routers/review.py` (new)
- **Verification:** `test_review_router.py`. State transitions enforced.
- **Dependencies:** Part 3.1.

## P3 Phase 2: AI suggestions on drafts

### Part 3.3 — AI review suggestions engine 🟡
- **Deliverable:** Given a draft campaign/creative, AI generates 3-5 suggestions:
  "Make the hook more emotional", "Add a scarcity element", "Tighten the CTA".
  Each suggestion: what to change, why, suggested replacement.
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/review_engine.py` (new)
  - `apps/api/prachar_api/routers/review.py` (add `POST /review/{id}/suggestions`)
- **Verification:** `test_review_engine.py`.
- **Dependencies:** Parts 3.2, P1 Part 1.1.

### Part 3.4 — Inline editing API 🟢
- **Deliverable:** `PATCH /review/{id}/field` — update a specific field (headline, copy, CTA).
  Writes audit log. Keeps version history.
- **Files:**
  - `apps/api/prachar_api/routers/review.py`
  - `apps/api/prachar_api/models/tables.py` (add `ReviewVersion` table or use audit log)
- **Verification:** `test_review_editing.py`. Version history retrievable.
- **Dependencies:** Part 3.2.

## P3 Phase 3: Review UI

### Part 3.5 — Review queue page 🔴
- **Deliverable:** `/app/review` page. List of drafts with: thumbnail, title, status badge,
  "Review" button. Filter by status. Sort by date.
- **Files:**
  - `apps/web/src/app/app/review/page.tsx` (new)
  - `apps/web/src/lib/review.ts` (API client)
- **Verification:** Typecheck passes. Build passes.
- **Dependencies:** Part 3.2.

### Part 3.6 — Review detail page 🔴
- **Deliverable:** `/app/review/{id}` page. Shows: campaign/creative preview,
  AI suggestions panel (right side), inline-editable fields, approve/request-changes/publish buttons.
- **Files:**
  - `apps/web/src/app/app/review/[id]/page.tsx` (new)
  - `apps/web/src/components/review/` (editable field components, suggestion panel)
- **Verification:** Typecheck passes. Build passes.
- **Dependencies:** Parts 3.3, 3.4, 3.5.

### Part 3.7 — Review sidebar entry 🟢
- **Deliverable:** Add "Review" to all domain pack nav_sections. Badge with pending count.
- **Files:** Domain packs.
- **Verification:** Architecture tests pass.
- **Dependencies:** Part 3.5.

## P3 Phase 4: Publish integration

### Part 3.8 — Publish to channel adapters 🟡
- **Deliverable:** When a campaign is approved + published, trigger the existing
  channel adapters (Google, Meta, etc.) to actually post. Use the existing
  `apps/workers/` Celery tasks. Add a `publish_campaign` task.
- **Files:**
  - `apps/workers/publish.py` (new)
  - `apps/api/prachar_api/routers/review.py` (enqueue publish task on approve)
- **Verification:** `test_publish.py`. Mock adapters, verify task enqueued.
- **Dependencies:** Parts 3.2, P2 Phase 1 (need creatives to publish).

---

# Programme 4: Performance Intelligence

> **Goal:** Once campaigns run, AI asks: What happened? Why? What next?
>
> **Why:** Creates a feedback loop. Without it, PRACHAR is a one-shot tool.
>
> **Approach:** Build on the existing attribution pixel (`/pixel/track`, `/pixel/convert`)
> and the existing `LearningEngine`. Add a `PerformanceEngine` that analyses
> campaign results and feeds back into CampaignBrain.

## P4 Phase 1: Performance data ingestion

### Part 4.1 — Performance data model 🟡
- **Deliverable:** `CampaignPerformance` table: campaign_id, date, impressions, clicks,
  conversions, spend, revenue, ctr, cpa, roas. Populated from channel adapters + attribution pixel.
- **Files:**
  - `apps/api/prachar_api/models/tables.py`
  - `apps/api/alembic/versions/0007_campaign_performance.py`
- **Verification:** Migration works. Model tests pass.
- **Dependencies:** P3 Part 3.8 (need published campaigns).

### Part 4.2 — Performance ingestion worker 🟡
- **Deliverable:** Celery task that pulls performance data from each channel adapter
  daily. Stores in `CampaignPerformance`. Handles errors per-channel (one failure doesn't block others).
- **Files:**
  - `apps/workers/performance.py` (new)
  - `apps/workers/loop.py` (add performance step to weekly loop)
- **Verification:** `test_performance_worker.py`. Mock adapters.
- **Dependencies:** Part 4.1.

## P4 Phase 2: Analysis engine

### Part 4.3 — "What happened" analysis 🟡
- **Deliverable:** `PerformanceEngine.analyse(campaign_id)` returns: summary,
  top metrics, trend (up/down/flat), notable days, comparison to benchmark.
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/performance_engine.py` (new)
  - `apps/api/prachar_api/routers/performance.py` (new — `GET /performance/{campaign_id}`)
- **Verification:** `test_performance_engine.py`.
- **Dependencies:** Part 4.1.

### Part 4.4 — "Why" root-cause analysis 🟡
- **Deliverable:** `PerformanceEngine.explain(campaign_id)` returns: likely causes
  for performance changes (creative fatigue, audience saturation, budget too low,
  seasonality, competitor activity). Each cause: evidence, confidence.
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/performance_engine.py` (extend)
  - `apps/api/prachar_api/routers/performance.py` (add `GET /performance/{campaign_id}/why`)
- **Verification:** `test_performance_why.py`.
- **Dependencies:** Part 4.3.

### Part 4.5 — "What next" recommendations 🟡
- **Deliverable:** `PerformanceEngine.recommend(campaign_id)` returns: 3-5 recommendations
  (scale winning creative, pause losing audience, increase budget, refresh creative, test new hook).
  Each: action, expected impact, priority.
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/performance_engine.py` (extend)
  - `apps/api/prachar_api/routers/performance.py` (add `GET /performance/{campaign_id}/next`)
- **Verification:** `test_performance_next.py`.
- **Dependencies:** Part 4.4.

## P4 Phase 3: Feedback loop

### Part 4.6 — Feed performance back into CampaignBrain 🟡
- **Deliverable:** When generating a new campaign, CampaignBrain reads the performance
  of past campaigns for the same brand and uses it as context. "Your last campaign
  achieved 3x ROAS with emotional hooks — doubling down on emotional messaging."
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/brain.py` (extend `generate_campaign` to read past performance)
  - `packages/shared/prachar_shared/marketing_intelligence/memory.py` (store performance learnings)
- **Verification:** `test_performance_feedback.py`. Mock past performance, verify it's in the prompt.
- **Dependencies:** Part 4.5.

## P4 Phase 4: Performance UI

### Part 4.7 — Performance dashboard page 🔴
- **Deliverable:** `/app/performance/{campaign_id}` page. Shows: "What happened" summary,
  metrics chart (Recharts), "Why" analysis, "What next" recommendations with "Apply" buttons.
- **Files:**
  - `apps/web/src/app/app/performance/[id]/page.tsx` (new)
  - `apps/web/src/lib/performance.ts` (API client)
- **Verification:** Typecheck passes. Build passes.
- **Dependencies:** Parts 4.3-4.5.

### Part 4.8 — Performance sidebar entry 🟢
- **Deliverable:** Add "Performance" to all domain pack nav_sections.
- **Files:** Domain packs.
- **Verification:** Architecture tests pass.
- **Dependencies:** Part 4.7.

---

# Programme 5: AI Marketing Director

> **Goal:** BRO becomes proactive. Instead of the user asking "Create a campaign",
> BRO says "Sales dropped 14% this week. I recommend launching a weekend offer.
> Here are three creative directions."
>
> **Why:** Changes the relationship from tool to assistant. This is the long-term moat.
>
> **Approach:** Build on P4 (Performance Intelligence). Add a `ProactiveEngine`
> that monitors performance, detects anomalies, and generates recommendations
> without being asked. BRO delivers them via chat + notifications.

## P5 Phase 1: Proactive monitoring

### Part 5.1 — Anomaly detection 🟡
- **Deliverable:** `ProactiveEngine.detect_anomalies(brand_id)` returns: drops, spikes,
  plateaus. Each anomaly: metric, magnitude, timeframe, severity.
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/proactive_engine.py` (new)
  - `apps/workers/proactive.py` (daily check task)
- **Verification:** `test_anomaly_detection.py`. Synthetic data with known anomalies.
- **Dependencies:** P4 Part 4.1.

### Part 5.2 — Proactive recommendation generation 🟡
- **Deliverable:** For each anomaly, generate a recommendation: what to do, why,
  3 creative directions, expected impact. Uses CampaignBrain + PerformanceEngine.
- **Files:**
  - `packages/shared/prachar_shared/marketing_intelligence/proactive_engine.py` (extend)
  - `apps/api/prachar_api/routers/proactive.py` (new — `GET /proactive/notifications`)
- **Verification:** `test_proactive_recommendations.py`.
- **Dependencies:** Parts 5.1, P4 Part 4.5.

## P5 Phase 2: BRO proactive delivery

### Part 5.3 — BRO proactive notifications 🟡
- **Deliverable:** BRO chat can deliver proactive messages. New chat endpoint:
  `GET /chat/proactive` — returns pending proactive messages for the user.
  BRO voice: "Hey, I noticed sales dropped 14% this week. I recommend..."
- **Files:**
  - `apps/api/prachar_api/routers/chat.py` (extend)
  - `packages/shared/prachar_shared/marketing_intelligence/proactive_engine.py` (BRO voice wrapper)
- **Verification:** `test_bro_proactive.py`. BRO voice, no jargon.
- **Dependencies:** Part 5.2.

### Part 5.4 — Proactive notification UI 🟡
- **Deliverable:** Bell icon in sidebar shows pending proactive notifications.
  Clicking opens BRO chat with the proactive message pre-loaded. User can accept
  (→ campaign generation) or dismiss.
- **Files:**
  - `apps/web/src/app/app/layout.tsx` (bell icon + badge)
  - `apps/web/src/components/ProactiveNotifications.tsx` (new)
- **Verification:** Typecheck passes. Build passes.
- **Dependencies:** Part 5.3.

## P5 Phase 3: Auto-suggest campaigns

### Part 5.5 — One-click "Launch recommended campaign" 🔴
- **Deliverable:** When BRO suggests a campaign, user can click "Launch" →
  pre-fills the campaign creation flow with BRO's recommendation. User reviews + approves.
  No auto-publish (human-in-the-loop from P3).
- **Files:**
  - `apps/web/src/app/app/campaigns/new/page.tsx` (accept pre-fill from query params)
  - `apps/api/prachar_api/routers/proactive.py` (add `POST /proactive/{id}/launch`)
- **Verification:** `test_proactive_launch.py`. E2E: anomaly → recommendation → launch → review.
- **Dependencies:** Parts 5.4, P3 Part 3.2.

### Part 5.6 — Proactive engine regression suite 🟢
- **Deliverable:** End-to-end test: synthetic performance drop → anomaly detected →
  recommendation generated → BRO notification → user launches → campaign created → review queue.
- **Files:**
  - `apps/api/prachar_api/tests/test_proactive_e2e.py` (new)
- **Verification:** The suite itself.
- **Dependencies:** All P5 parts.

---

# Execution summary

## Part count by programme

| Programme | Parts | Small 🟢 | Medium 🟡 | Large 🔴 |
|-----------|-------|----------|-----------|----------|
| P1 Campaign Quality | 10 | 6 | 4 | 0 |
| P2 Creative Studio | 15 | 11 | 2 | 2 |
| P3 Human-in-the-loop | 8 | 2 | 3 | 3 |
| P4 Performance Intelligence | 8 | 1 | 6 | 1 |
| P5 AI Marketing Director | 6 | 1 | 4 | 1 |
| **Total** | **47** | **21** | **19** | **7** |

## Recommended execution order (first 10 parts)

1. **P1.1** — Creative directions in campaign preview (🟢, unblocks P1 + P2)
2. **P1.2** — Hooks module (🟢)
3. **P1.3** — Audience psychology (🟡)
4. **P1.4** — Offer engineering (🟡)
5. **P2.1** — Creative Format Spec framework (🟢, can run parallel with P1)
6. **P2.2** — Creative Studio engine (🟡)
7. **P2.3** — Creative Studio API (🟢)
8. **P2.4-2.13** — Format implementations (10 × 🟢, parallelisable)
9. **P3.1** — Review status enums (🟢, can run parallel with P2)
10. **P3.2** — Review queue API (🟡)

## Parallelisation rules

- **P1 parts** can run in parallel with **P2 scaffolding** (different files)
- **P2 format parts** (2.4-2.13) can ALL run in parallel (each is one file)
- **P3 Phase 1** can run in parallel with **P2 Phase 3** (different files)
- **P4 Phase 1** can run in parallel with **P3 Phase 3** (different files)
- **Never run two parts that touch the same file in parallel.**

## Files touched per programme (no overlap)

| Programme | Primary files |
|-----------|---------------|
| P1 | `marketing_intelligence/*.py`, domain packs |
| P2 | `creative_studio/*`, `routers/creative_studio.py`, `web/creative-studio/` |
| P3 | `models/enums.py`, `routers/review.py`, `web/review/` |
| P4 | `models/tables.py` (performance), `routers/performance.py`, `web/performance/` |
| P5 | `marketing_intelligence/proactive_engine.py`, `routers/proactive.py`, `routers/chat.py` |

**Only shared files (touched by multiple programmes):**
- `apps/api/prachar_api/models/tables.py` — P2 (package table), P3 (review versions), P4 (performance table). Coordinate via separate migrations.
- `apps/api/prachar_api/main.py` — each programme adds one router import. Coordinate by adding routers in separate parts.
- Domain packs — P1 (quality fragments), P2 (creative studio nav), P3 (review nav), P4 (performance nav). Each part adds to nav_sections; no conflict if done sequentially.

## How to run a part (Devin session protocol)

1. **Start:** `git status` + `make test` → confirm green baseline.
2. **Read:** the part's deliverable + files + dependencies in this roadmap.
3. **Implement:** write code + tests together.
4. **Verify:** `make test` (pytest + typecheck + build). Must be green.
5. **Document:** update `AGENTS.md` with the part's completion.
6. **Commit:** one commit per part, referencing the part ID (e.g. "P1.1: creative directions in campaign preview").

## Success metrics per programme

| Programme | Metric |
|-----------|--------|
| P1 Campaign Quality | Campaigns include 9 quality modules. A/B test: new campaigns vs old, blind rating by 3 reviewers. |
| P2 Creative Studio | One click → 10 formats generated in <60 seconds. User NPS on "wow" factor. |
| P3 Human-in-the-loop | 100% of campaigns go through review queue before publish. Founder edit rate. |
| P4 Performance Intelligence | Every published campaign has a "what happened / why / what next" report within 7 days. |
| P5 AI Marketing Director | BRO sends ≥1 proactive recommendation per week per active brand. Acceptance rate. |
