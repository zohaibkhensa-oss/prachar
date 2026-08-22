# CURV AI UX Polish Audit (Phase A — A.0.1)

> **Mandatory document.** No code changes until this audit is complete and reviewed.
>
> **Auditor role:** UI/UX Engineer + CTO + Chief Engineer
>
> **Method:** Code-level audit of every screen the founder called out, plus the shared layout. Each screen is evaluated against the founder's criteria:
> 1. Does every card answer "Why should I care?"
> 2. Are there empty states? (Should be removed)
> 3. Loading animation quality
> 4. Typography and spacing
> 5. Mobile-first polish
> 6. Does it feel like a form or a consultant?
> 7. Are recommendations explained?
> 8. Is everything editable?
> 9. Does it feel like Google Docs? (Review)
> 10. Is it dashboards or stories? (Performance)

---

## 1. Dashboard — `/app/page.tsx`

### What exists
- Uses `DashboardShell` (from Domain Pack config) for both business and creator
- Fallback path shows: `LoadingState` → `NoBrandState` → `FirstCampaignState` → `ActiveDashboard`
- `FirstCampaignState`: ONE dominant CTA ("Create My Campaign") — good
- `ActiveDashboard`: greeting + KPI cards + quick actions + approvals + pipeline
- KPI cards: Customers, Revenue, Enquiries, Reach (business); Subscribers, Views, Watch time, etc. (creator)

### Problems found

**P1.1 — Empty states exist (founder wants them removed)**
- `NoBrandState` (line 180): shows when user has no brand. Should redirect to onboarding instead of showing an empty state.
- `FirstCampaignState` (line 182): shows when user has no campaigns. This is actually a GOOD state (one dominant CTA), but it's technically an "empty state". The founder said "remove empty states" — but this one is the onboarding CTA. **Recommendation: keep this, but reframe it as "Your first campaign" not "No campaigns yet".**
- `LoadingState` (line 177): generic spinner. Should be skeleton matching final content shape.

**P1.2 — KPI cards don't answer "Why should I care?"**
- Cards show: "Customers", "Revenue", "Enquiries", "Reach" with numbers
- But they don't explain: What does this number mean? Is it good? Bad? Should I act?
- **Example fix:** Instead of "Customers: 42", show "42 new customers this month — up 18% from last month. Your Instagram campaign is driving most of them."
- Each card needs: a number, a trend indicator, a 1-line context, and (if actionable) a "See why" link

**P1.3 — Loading animation is generic**
- `LoadingState` uses a simple spinner (line 177)
- Should use skeleton cards that match the dashboard layout
- Transitions from loading → loaded are jarring (no fade-in)

**P1.4 — Typography hierarchy is inconsistent**
- Greeting: `text-3xl font-semibold` (good)
- Card titles: mixed — some `text-sm`, some `text-xs`, some `font-mono`
- Card values: `text-2xl font-semibold` (good) but not consistently applied
- **Recommendation:** Define a clear type scale: H1 (3xl), H2 (2xl), H3 (xl), Body (sm), Caption (xs), Mono (xs font-mono)

**P1.5 — Spacing is inconsistent**
- Greeting to first card: `space-y-8` (good)
- Between cards: `gap-4` in grid (ok)
- Inside cards: varies — some `p-6`, some `p-8`, some `p-10`
- **Recommendation:** Standardize card padding to `p-5` or `p-6`, section spacing to `space-y-6`

**P1.6 — Mobile-first issues**
- Dashboard uses `grid grid-cols-2 md:grid-cols-4` for KPIs — good
- But the greeting is `text-3xl` which is too big on mobile (375px)
- Quick actions stack on mobile but the CTA button is full-width — good
- **Recommendation:** Greeting should be `text-2xl sm:text-3xl`

### Action items for Dashboard
1. Remove `NoBrandState` — redirect to onboarding instead
2. Reframe `FirstCampaignState` as "Your first campaign" (not empty state)
3. Replace `LoadingState` spinner with skeleton cards matching dashboard layout
4. Add trend + context to every KPI card ("42 customers — up 18%. Instagram is driving growth.")
5. Standardize typography: H1 `text-2xl sm:text-3xl`, cards `p-5`, sections `space-y-6`
6. Add fade-in transition from loading → loaded

---

## 2. Campaign Builder — `/app/brands/[id]/campaigns/new/page.tsx`

### What exists
- 1-step form: goal (select from industry presets) + budget (slider)
- 3 phases: `form` → `generating` → `result` / `error`
- `generating` phase: 5-step progress animation
- `result` phase: shows campaign preview (Executive Summary, Budget, What we'll post, Next actions)
- BRO pre-fill banner (from P5.5 proactive recommendations)

### Problems found

**P2.1 — It feels like a form, not a consultant**
- The form says: "Answer two questions. We'll build the entire campaign for you"
- This is FORM language. A consultant would say: "Tell me what you're trying to achieve. I'll look at your business and recommend the best approach."
- The goal selection is a multiple-choice grid — no context on WHY each goal is an option
- **Example fix:** Before the goal selection, add: "Based on your industry (Restaurant) and current stage, I'd recommend focusing on getting more customers. Here's why: [explanation]. But you know your business best — what's your priority?"

**P2.2 — No "Why this campaign?" explanation**
- The form → generation → result flow doesn't explain WHY the campaign is structured the way it is
- The result shows WHAT (Executive Summary, Budget, Posts) but not WHY
- **Example fix:** Add a "Why I'm recommending this" section at the top of the result:
  > "I'm recommending a customer-acquisition campaign focused on Instagram and WhatsApp because:
> 1. Your audience (25-40, local) is most active on Instagram
> 2. WhatsApp has the highest conversion rate for restaurants in your area
> 3. Your budget (₹15K) is best spent on 2 channels rather than spreading thin"

**P2.3 — Budget slider lacks context**
- The slider shows ₹5K - ₹100K but doesn't explain what each level gets you
- **Example fix:** Add contextual hints as the slider moves:
  - ₹5K: "Lean start — 1 channel, organic focus"
  - ₹15K: "Balanced — 2 channels, small paid boost"
  - ₹50K: "Aggressive — 3 channels, significant paid spend"
  - ₹100K: "Scale — all channels, dominant local presence"

**P2.4 — Generation progress is good but could be better**
- 5-step progress animation exists (good)
- But the steps are generic ("Analysing your business", "Choosing channels", etc.)
- **Recommendation:** Make steps specific to the campaign being built: "Analysing Restaurant industry trends", "Selecting Instagram + WhatsApp based on your audience", etc.

**P2.5 — Result page lacks "what happens next" clarity**
- Shows Next Actions but doesn't explain the review → approve → publish flow
- **Recommendation:** Add a "Here's what happens next" timeline: "1. You review this campaign. 2. You approve or request changes. 3. We publish to your channels. 4. You see results in Performance."

### Action items for Campaign Builder
1. Rewrite form copy from form-language to consultant-language
2. Add "Why I'm recommending this" section at the top of results
3. Add contextual budget hints to the slider
4. Make generation progress steps specific to the campaign
5. Add "What happens next" timeline to results
6. Add reasoning to each goal option ("Get more customers — best for growing businesses")

---

## 3. Creative Studio — `/app/creative-studio/page.tsx`

### What exists
- Campaign selector + creative direction selector
- "Generate All" button with progress indicator
- Tabbed view of 10 formats (poster, video_script, carousel, etc.)
- Each tab: FormatPreview + Copy JSON button + Regenerate button
- Regenerate regenerates the ENTIRE format

### Problems found

**P3.1 — No granular regeneration (CRITICAL — founder explicitly called this out)**
- Current: "Regenerate" button regenerates the entire format
- Founder wants: regenerate only headline, only CTA, only offer, only colours, only tone
- **This is the biggest gap in Creative Studio**
- **Fix:** Add per-field regenerate buttons. Each editable field has a small "regenerate" icon next to it.

**P3.2 — No inline editing**
- Fields are display-only — can't edit them directly
- Founder wants: every generated creative should be editable
- **Fix:** Make each field inline-editable (click to edit, like the Review queue's EditableField component)

**P3.3 — Copy button copies JSON (technical, not user-friendly)**
- `JSON.stringify(data, null, 2)` — this is for developers, not founders
- **Fix:** Copy should copy the actual content (e.g., for a poster: copy the headline + body + CTA as plain text). Add a "Copy as JSON" option in a dropdown for advanced users.

**P3.4 — Creative direction selector is fake**
- `deriveDirectionOptions()` creates 3 fake options (Primary, Bold, Minimal) from the same plan
- They all send the same `creative_direction_id` (the plan id)
- **Fix:** Either fetch real creative directions from the backend, or remove the selector and use the campaign's primary direction.

**P3.5 — No "why this creative" explanation**
- The generated creatives don't explain why they're structured that way
- **Fix:** Add a 1-line explanation per format: "This poster uses a hunger-appeal hook because your audience responds to visual food cues."

**P3.6 — Empty state when no campaign selected**
- Shows input panel with dropdowns — OK, but could be friendlier
- **Fix:** Add a "Select a campaign to start" prompt with a link to create one if none exist.

### Action items for Creative Studio
1. **CRITICAL:** Add per-field regeneration (headline, CTA, offer, colours, tone separately)
2. Add inline editing for every field
3. Change Copy to copy plain text (not JSON); add "Copy as JSON" option
4. Fix or remove the fake creative direction selector
5. Add "why this creative" explanation per format
6. Improve empty state

---

## 4. Review Queue — `/app/review/page.tsx` + `/app/review/[id]/page.tsx`

### What exists
- Queue page: list of campaigns with status badges, filter dropdown, sort by date
- Detail page: campaign preview + AI suggestions panel + inline-editable fields + action bar (Request Changes, Approve, Publish)
- Inline editing exists (EditableField component) — good
- AI suggestions exist (SuggestionPanel) — good

### Problems found

**P4.1 — Empty state exists (founder wants removed)**
- Queue page: "No campaigns awaiting review" with ClipboardList icon
- **Fix:** Replace with a positive state: "You're all caught up! BRO is working on your next campaign." Or redirect to campaigns page if no drafts exist.

**P4.2 — No inline comments (CRITICAL — founder explicitly called this out)**
- Founder wants: Google Docs-style inline comments
- Current: no commenting capability at all
- **Fix:** Add inline comments — highlight a section, add a comment, thread, resolve. This is a significant feature.

**P4.3 — No version history (CRITICAL — founder explicitly called this out)**
- Founder wants: version history like Google Docs
- Current: edits write to audit log but there's no UI to view/compare/restore versions
- **Fix:** Add version history panel — view all versions, compare two versions, restore a previous version.

**P4.4 — Approve/Reject flow is too simple**
- Approve is a single click — no confirmation
- Reject (Request Changes) requires feedback but no confirmation modal
- **Fix:** Approve should show a confirmation modal: "Approve this campaign? It will be published to your channels." Reject should require a reason.

**P4.5 — No "what happens after I approve" explanation**
- User approves but doesn't know what happens next
- **Fix:** After approval, show: "Campaign approved! Here's what happens next: 1. We're publishing to Instagram, Facebook, WhatsApp. 2. You'll see results in Performance within 7 days."

**P4.6 — Queue list lacks context**
- Each row shows: name, network, objective, date, status badge
- But doesn't show: what the campaign is about, how much budget, expected results
- **Fix:** Add a 1-line summary to each row: "Instagram campaign to get 50 new customers. Budget ₹15K."

### Action items for Review Queue
1. **CRITICAL:** Add inline comments (highlight → comment → thread → resolve)
2. **CRITICAL:** Add version history (view, compare, restore)
3. Remove empty state — replace with positive "all caught up" state
4. Add confirmation modals for Approve and Reject
5. Add "what happens next" explanation after approval
6. Add 1-line summary to each queue row

---

## 5. Performance — `/app/performance/[id]/page.tsx`

### What exists
- 3 sections: "What happened" (summary + metrics grid + chart + notable days), "Why" (likely causes), "What next" (recommendations)
- Recharts bar chart of notable days
- Metrics grid: 8 metrics (Impressions, Clicks, Conversions, Spend, Revenue, CTR, CPA, ROAS)
- Trend badge (up/down/flat)
- "Apply" button on recommendations (shows toast — not implemented)

### Problems found

**P5.1 — It's a dashboard, not a story (CRITICAL — founder explicitly called this out)**
- Founder wants: "This week's campaign generated 31 enquiries. Instagram delivered 74%. WhatsApp generated the highest conversion. Weekend campaigns outperform weekdays by 28%."
- Current: metrics grid + chart + notable days — this IS a dashboard
- **Fix:** Rewrite the page to lead with a NARRATIVE story. The metrics grid and chart become supporting evidence at the bottom, under "Here's the data behind this story."

**P5.2 — Summary text is generic**
- The summary from the backend is a plain string — likely "Campaign X had Y impressions and Z conversions..."
- **Fix:** Make the story specific and comparative:
  > "This week's campaign brought in 31 new enquiries — that's 12 more than last week.
  > Instagram was your star performer, delivering 74% of those enquiries.
  > WhatsApp had the highest conversion rate at 12% — your audience prefers personal messaging.
  > Interesting finding: weekend campaigns outperformed weekdays by 28%."

**P5.3 — No platform breakdown**
- The story should break down by platform (Instagram, WhatsApp, Google, etc.)
- Current: metrics are aggregated, not per-platform
- **Fix:** The backend needs to return per-platform breakdowns. The story should say "Instagram delivered 74%" not just "you got 31 enquiries."

**P5.4 — No time-based comparisons**
- Founder's example: "Weekend campaigns outperform weekdays by 28%"
- Current: no day-of-week or time-based analysis
- **Fix:** Add time-based analysis to the performance engine — compare weekdays vs weekends, this week vs last week, this month vs last month.

**P5.5 — Chart is prominent but should be supporting**
- The Recharts bar chart takes up 2/3 of the width — it's the main visual
- **Fix:** Move the chart below the story, labeled "Here's the data behind this story." Make it smaller (1/2 width or collapsible).

**P5.6 — "Apply" button doesn't do anything**
- Shows a toast: "Recommendation noted — apply flow coming soon"
- **Fix:** Wire the Apply button to actually apply the recommendation (e.g., increase budget, pause audience, refresh creative). This connects to the review queue — the applied change creates a new campaign version for review.

**P5.7 — ROAS, CPA, CTR are jargon**
- The founder's UX sprint de-jargonised these: "ROAS" → "Revenue per ₹100", "Conversions" → "New customers"
- But the Performance page still uses ROAS, CPA, CTR
- **Fix:** Use plain language: "Revenue per ₹100 spent" (ROAS), "Cost per new customer" (CPA), "Click rate" (CTR)

### Action items for Performance
1. **CRITICAL:** Rewrite page to lead with a narrative story (not metrics grid)
2. Move metrics grid + chart to supporting section at bottom
3. Add platform breakdown to the story ("Instagram delivered 74%")
4. Add time-based comparisons ("Weekend campaigns outperform weekdays by 28%")
5. Wire "Apply" button to actually apply recommendations
6. De-jargonise: ROAS → "Revenue per ₹100", CPA → "Cost per new customer", CTR → "Click rate"

---

## 6. Layout — `/app/layout.tsx`

### What exists
- Sidebar with: logo, workspace selector, nav sections (from domain pack), collapse button
- Mobile: hamburger menu, overlay, slide-in sidebar
- Top bar: search, bell icon (notifications), user menu
- Bell icon shows notification count badge
- ProactiveNotifications panel (slide-in from right)

### Problems found

**P6.1 — Nav has too many items now**
- After Roadmap 1, nav includes: Home, Brand, Campaigns, Results, Creative Studio, Review, Performance, Calendar, Channels, Reviews, Settings
- That's 11 items — too many for a sidebar
- **Fix:** Group into 3 sections: Main (Home, Campaigns, Creative Studio, Review, Performance), Brand (My Brand, Channels, Calendar), Settings. Hide "Reviews" (the public reviews page) — it's confusing alongside "Review" (the workflow).

**P6.2 — "Review" vs "Reviews" confusion**
- "Review" = the campaign review workflow (new)
- "Reviews" = public customer reviews (existing)
- These are confusingly named
- **Fix:** Rename "Reviews" to "Customer Reviews" or remove it from the main nav (move to brand detail page).

**P6.3 — Mobile sidebar is functional but not polished**
- Overlay works, slide-in works
- But the nav items don't have active states on mobile
- The workspace selector is hidden when collapsed — but on mobile, collapsed doesn't apply
- **Fix:** Ensure active nav item is highlighted on mobile. Test at 375px.

**P6.4 — Bell icon badge is minimal**
- Shows a count but no animation
- **Fix:** Add a subtle pulse animation when count increases. Show a tooltip "BRO has X recommendations for you."

### Action items for Layout
1. Regroup nav into 3 sections (Main, Brand, Settings)
2. Rename "Reviews" to "Customer Reviews" or remove from main nav
3. Ensure active nav item highlighted on mobile
4. Add pulse animation to bell icon when count increases
5. Test sidebar at 375px, 768px, 1024px

---

## 7. SharedPresentation — `SharedPresentation.tsx`

### What exists
- Renders campaign preview: CreativeDirections, HookPatterns, AudiencePsychologySection, OfferSection, PricingPsychologySection, SeasonalIdeasSection, LocalIdeasSection, DifferentiationSection, ABConceptsSection
- Each section is a card-based layout with badges and grids

### Problems found

**P7.1 — Too many sections, no hierarchy**
- 9 sections are rendered — that's a LOT of information
- No visual hierarchy — they all look equally important
- **Fix:** Group into 3 tabs: "Strategy" (directions, psychology, differentiation), "Creative" (hooks, offers, pricing, A/B), "Context" (seasonal, local). Or collapse sections by default with a summary.

**P7.2 — Sections don't explain "why should I care?"**
- Each section shows data but doesn't explain what it means for the user
- **Fix:** Add a 1-line "what this means for you" at the top of each section.

**P7.3 — Not mobile-optimized**
- Grids use `grid-cols-2` or `grid-cols-3` — on mobile these are cramped
- **Fix:** Use `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3` responsive grids.

### Action items for SharedPresentation
1. Group 9 sections into 3 tabs (Strategy, Creative, Context)
2. Add "what this means for you" to each section
3. Make grids responsive (1 col mobile, 2 col tablet, 3 col desktop)

---

## Priority ranking

### Critical (founder explicitly called out)
1. **P3.1** — Creative Studio granular regeneration
2. **P4.2** — Review Queue inline comments
3. **P4.3** — Review Queue version history
4. **P5.1** — Performance stories not dashboards

### High (founder's criteria, not explicitly called out but clear)
5. **P2.1** — Campaign Builder consultant-not-form
6. **P2.2** — Campaign Builder "why this campaign" explanation
7. **P1.2** — Dashboard KPI cards "why should I care?"
8. **P5.3** — Performance platform breakdown
9. **P5.4** — Performance time-based comparisons

### Medium (polish)
10. **P1.1** — Remove empty states
11. **P1.3** — Loading animations
12. **P3.2** — Creative Studio inline editing
13. **P5.7** — De-jargonise Performance
14. **P6.1** — Regroup nav
15. **P7.1** — SharedPresentation section grouping

### Low (nice to have)
16. **P1.4** — Typography hierarchy
17. **P1.5** — Spacing consistency
18. **P1.6** — Mobile greeting size
19. **P3.3** — Copy as plain text
20. **P6.4** — Bell icon animation

---

## Recommended execution order

Based on priority and file-overlap analysis:

### Wave 1 (parallel — no shared file overlap)
- **A.1.1** — Dashboard "why should I care?" (touches `page.tsx` only)
- **A.3.1** — Creative Studio granular regeneration (touches `creative-studio/page.tsx` + `FormatPreview.tsx` + backend)
- **A.4.1** — Review Queue inline comments (touches `review/[id]/page.tsx` + backend + new migration)
- **A.5.1** — Performance stories rewrite (touches `performance/[id]/page.tsx` + backend)

### Wave 2 (parallel — no shared file overlap)
- **A.1.2** — Dashboard empty states + loading (touches `page.tsx` — after A.1.1)
- **A.2.1** — Campaign Builder consultant pass (touches `campaigns/new/page.tsx`)
- **A.3.2** — Creative Studio inline editing (touches `FormatPreview.tsx` — after A.3.1)
- **A.4.2** — Review Queue version history (touches `review/[id]/page.tsx` + backend — after A.4.1)

### Wave 3 (sequential — shared components)
- **A.2.2** — Campaign results "why" explanations (touches `SharedPresentation.tsx`)
- **A.6.1** — SharedPresentation polish (touches `SharedPresentation.tsx` — after A.2.2)
- **A.6.2** — Layout polish (touches `layout.tsx`)

### Wave 4 (parallel — finishing touches)
- **A.1.3** — Dashboard typography + mobile (touches `page.tsx` — after A.1.2)
- **A.4.3** — Review approve/reject polish (touches `review/[id]/page.tsx` — after A.4.2)
- **A.5.2** — Performance charts as supporting (touches `performance/[id]/page.tsx` — after A.5.1)

---

## Infrastructure needed before starting

### Playwright screenshot setup
The founder chose "Use Playwright screenshots" for visual verification. Playwright is NOT installed.
- Install `@playwright/test` in `apps/web`
- Create a screenshot script that captures each page at 375px, 768px, 1024px
- Run before and after each polish part to verify visual changes
- Store screenshots in `apps/web/screenshots/` for comparison

### This should be Part A.0.2 (infrastructure) before any polish parts start.
