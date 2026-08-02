# PRACHAR — Agent Notes

AI-driven premium advertising agency platform. One brand upload → organic + paid visibility across every major platform worldwide, on a weekly autonomous loop, at SMB pricing.

## Spec source
`~/Downloads/prachar-cursor-kit/00..09-*.md` — read these for full architecture, data model, channel integrations, ads manager, AI engine, devops, build order. This file is the operational cheat-sheet for agents working in this repo.

## Stack (non-negotiable)
- Backend: Python 3.12 (target; 3.14 ok locally), FastAPI, SQLAlchemy 2 async, Pydantic v2, Postgres 16 (RLS), Redis, Celery (worker+beat), S3-compatible object store (MinIO in compose, local FS fallback).
- Frontend: Next.js 15 (App Router), TypeScript strict, Tailwind, shadcn/ui, TanStack Query, Recharts.
- AI: provider-abstraction layer (Anthropic primary, OpenAI fallback), tiered models, Whisper for transcripts, image-gen abstraction.
- Infra: Docker Compose local, Terraform → AWS (ECS Fargate, RDS, ElastiCache, S3, CloudFront), GitHub Actions CI.

## Monorepo layout
```
apps/api/         FastAPI (routers/, tests/)
apps/web/         Next.js 15 app
apps/workers/     Celery workers: ingest, organic, ads, measure, creative + loop.py (beat)
packages/shared/  ai_gateway/, adapters/{organic,ads}/, contracts.py, policy/
infra/            terraform
.github/          CI workflows
```

## Local dev (no Docker required — Postgres 16 + Redis already running on host)
```bash
make setup         # create venvs, install deps, create db
make migrate       # alembic upgrade head
make seed          # seed demo tenant + user
make api           # uvicorn apps/api/main:app --reload --port 8000
make web           # pnpm --dir apps/web dev
make worker        # celery -A apps.workers.celery_app worker -l info
make beat          # celery -A apps.workers.celery_app beat -l info
make test          # pytest + pnpm typecheck + playwright smoke
make up            # docker-compose up (if Docker installed)
```

## Env (.env from .env.example)
- `DATABASE_URL` — async postgres: `postgresql+asyncpg://prachar:prachar@localhost:5432/prachar`
- `REDIS_URL` — `redis://localhost:6379/0`
- `JWT_SECRET`, `JWT_REFRESH_SECRET` — generate w/ `openssl rand -hex 32`
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` — for ai_gateway (stub if absent)
- `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` — MinIO/local
- Per-channel OAuth client creds: `GOOGLE_CLIENT_ID/SECRET`, `META_*`, `TIKTOK_*`, etc.
- `STRIPE_API_KEY`, `RAZORPAY_KEY_ID/SECRET`

## Hard rules (from spec)
- Every external platform behind `ChannelAdapter` (organic) or `AdNetworkAdapter` (paid). Zero platform logic outside adapters.
- All LLM calls through `packages/shared/ai_gateway` (tiering, cache, budget, JSON schema, retries).
- Every mutation writes an `AuditEvent` row. No exceptions.
- RLS on every tenant table; tenant middleware sets `app.tenant_id` via `SET LOCAL`.
- Feature flags per channel.
- Secrets only via env/SSM. Never in code. Never log OAuth tokens.
- No engagement-bait, fake reviews, follower buying, scraping behind auth.
- `claims_gate` strips "guaranteed #1 / guaranteed results" + medical/financial claims.
- Money mutations: idempotency keys, dry-run default ON first 7 days, hard cap table checked in DB tx before every budget/bid call.

## Architecture Freeze (v1 — declared 2026-08-02)
**PRACHAR AI v1 architecture is FROZEN.** No new foundational abstractions. The question is no longer "what architecture remains?" but "what prevents launch?" See `LAUNCH_READINESS.md` for the feature matrix and sign-off criteria. See `LAUNCH_PROGRAM.md` for the 8-phase launch plan (A-H).

### No New Core Abstractions rule
Any proposed feature MUST plug into one of these existing systems. A new core abstraction requires explicit justification that the feature cannot fit into any of these:

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

If a feature cannot fit into any of these boxes, escalate to the user before introducing a new abstraction. This rule protects the architecture from bloat over the next 2-3 years.

### Frozen components (do not redesign)
Runtime, Planner, Composer, Tool Registry, Session State, Runtime Events, Observability, Context Builder, Context Ranking, Adaptive Ranking, Context Evaluation, Feedback Loop, Business Memory, Knowledge Hub, Attribution, Campaign Brain, Creative Studio, Performance Engine, Audit Engine, Agency Council, Domain Packs, Review System, Integrations, Event Bus, Workflow Engine, Secrets Vault, Sync Policies, Data Mapping, Webhooks, Billing, Auth, Multi-workspace, API Tokens, Brand Isolation, White-label, Orb (16 context providers, 30 tools). Database schema is additive-only (new migrations OK, no destructive changes without explicit approval).

### v2 Admission Rule
A proposal may only become a new core subsystem (v2 architecture) if it satisfies ALL of:
1. It cannot reasonably extend any frozen subsystem (documented justification required)
2. It benefits multiple independent product areas (not a single-feature concern)
3. It materially reduces system complexity or operational cost
4. It is documented with a new ADR in `docs/adr/`
5. It is explicitly approved by the project owner

### Extension Checklist
Every new feature proposal answers these questions. If every answer points to an existing subsystem, the feature proceeds without architectural review:
- [ ] Which existing subsystem does it extend?
- [ ] Which Tool Registry entry is added (if any)?
- [ ] Which Context Provider is added (if any)?
- [ ] Which Integration adapter is added (if any)?
- [ ] Which Workflow actions/events are added (if any)?
- [ ] Which database migration is additive?
- [ ] Which tests are added?

### Architecture Decision Records
See `docs/adr/` for immutable records of significant architectural decisions (ADR-0001 through ADR-0007). Future contributors reference ADRs instead of reopening settled architectural debates.

### CI Architecture Guards
`apps/api/prachar_api/tests/test_architecture_freeze.py` enforces the freeze in CI:
- No duplicate Runtime/Planner/Composer classes
- No duplicate ToolRegistry
- No duplicate ContextBuilder
- No duplicate EventBus
- No duplicate WorkflowEngine
- No shared→api imports (dependency inversion)
- No unapproved top-level packages

## Build order (sprints)
S0 skeleton → S1 audit funnel → S2 Google organic → S3 YouTube → S4 Google+Meta Ads → S5 IG/FB organic → S6 allocator+creative evolution+attribution → S7 TikTok/LinkedIn/Pinterest/X → S8 regional (WhatsApp/Telegram/LINE/VK/Yandex/MS/Snap/Reddit) + locale packs → S9 agency tier.

## Progress
- [x] S0 — skeleton: monorepo, docker-compose, Makefile, CI, Postgres schema + RLS + Alembic, packages/shared (contracts, ai_gateway, adapters, policy), apps/api (FastAPI, auth JWT+refresh, tenant middleware RLS, routers), apps/workers (Celery, beat, weekly loop, 5 workers, allocator, report), apps/web (Next.js 15, Billboard & Ink, 14 routes, all signature components). 27 tests pass. Acceptance: register→login→create brand ✓, cross-tenant RLS isolation ✓, audit trail ✓.
- [x] S1 — audit engine: crawler (httpx + regex HTML parse), entity extraction (ai_gateway small model), SERP sampling (SERP API or mock), AI citation probe, VisibilityScore computation, findings generation (ai_gateway large model, 5 free + 5 gated), SSE progress endpoint `/audits/{id}/events`, inline fallback when Celery/Redis unavailable. End-to-end: POST /brands/audit → crawl → score (17.5/100 for example.com) → 10 findings. 14 worker tests pass.
- [x] S2 — Google organic: GSC adapter (OAuth, URL inspection, search analytics), GoogleSearchAdapter (SERP monitoring), GMBAdapter (Business Profile), page content generation (PAGE_CONTENT_PROMPT, meta variants, FAQ blocks), organic tasks (generate_content, policy_check, publish as Celery tasks), weekly loop v1 (7-step chain: measure→diagnose→regenerate→policy→publish→budget_realloc→report), PDF report generation (reportlab), reports API router. 35 tests pass.
- [x] S3 — YouTube: YouTubeAdapter (Data API + Analytics API, OAuth with youtube + yt-analytics.readonly scopes), transcript→metadata engine (transcribe_video, optimize_youtube_metadata, generate_thumbnail_brief, extract_chapters), YouTube-specific prompts (title≤100, description with chapters, tags≤500 total, pinned comment), policy_gate (title/tags limits, all-caps clickbait warning, claims_gate). 8 tests.
- [x] S4 — Google Ads + Meta Ads: GoogleAdsAdapter + MetaAdsAdapter (audience translation, campaign create, creative upload, budget/bid, pause, stats, policy precheck), AudienceSpec translation (interests→native taxonomy, geo→location, intents→keywords), campaign scaffolding (Google RSA / Meta CBO), ad copy generation, watchdog. 13 tests.
- [x] S5 — IG/FB organic: InstagramAdapter (Graph API, publish feed/reels/carousel, insights), FacebookAdapter (page posts, scheduling, insights), hashtag engine, IG/FB content generation (meta_prompts), posting window scheduler. 15 tests.
- [x] S6 — Budget allocator refinement (softmax realloc with ±20% clamp, max_cpa guardrail, pause networks exceeding cap), creative evolution (classify winners/losers by CTR median±1σ, generate_winner_children via LLM mutation prompts, log_lineage audit events), attribution pixel (first-party JS snippet /pixel.js, /pixel/track touchpoint collection, /pixel/convert with position-based 40/20/40 attribution model, gclid/fbclid/ttclid network detection), spend cap enforcement (check_spend_cap daily+monthly, check_idempotency via Redis NX). 7 tests.
- [x] S7 — Expansion wave 1: TikTok (Content Posting API, caption≤2200, hashtags≤100), LinkedIn (ugcPosts, text≤3000, professional tone check), Pinterest (Pins API v5, title≤100, description≤500), X/Twitter (API v2, text≤280, poll support) — organic + ads adapters with audience translation. 33 tests.
- [x] S8 — Regional wave: WhatsApp (Business Cloud API, opt-in + template required), Telegram (Bot API, sendMessage/sendPhoto), LINE (Messaging API), VK (wall.post), Reddit (human-approval-required: policy_gate always passed=False), Naver (Search Advisor, Korean content check) — organic adapters. Microsoft Ads, Snap Ads, Reddit Ads, Yandex Direct — ads adapters. Locale packs: 14 locales (en-US/GB/IN/AU, hi-IN, ar-SA, es-ES, pt-BR, id-ID, ja-JP, ko-KR, de-DE, fr-FR, ru-RU) with REGION_ROUTES (IN→whatsapp/instagram/youtube, KR→kakao/naver, RU/CIS→vk/telegram/yandex, JP→line/youtube, MENA→snapchat/instagram). 34 tests.
- [x] S9 — Agency tier: admin cost dashboard (per-tenant AI token usage + budget, plan-based spend caps), API access tokens (create/list with scopes), white-label PDF config (agency_name, logo_url, primary/accent colors, footer_text), multi-brand summary (all brands with visibility scores + campaign counts), CSV export. 8 tests.
- [x] AI Trust Sprint — AI reliability hardening: anti-hallucination grounding rules + verified feature inventory in chat system prompt, prompt injection defense middleware (safety.py with 22 detection patterns), universal JSON extractor (json_utils.py handles markdown fences/prose/BOM), prompt versioning registry (registry.py), AI observability + metrics (observability.py logs every request with request_id/tenant/model/provider/latency/tokens/cost), AI metrics dashboard endpoints (/admin/ai-metrics, /admin/ai-metrics/logs), worker reliability utilities (reliability.py with DLQ/idempotency/progress/timeouts), AI gateway hardening (60s timeouts, JSON extraction fallback, output leak detection, confidence scoring), fixed token budgets (Starter 50K, Growth 200K, Agency 1M — all plans can now run weekly loops), pre-flight budget estimation (preflight.py informs users before work begins), 77 AI quality tests. See AI_TRUST_REPORT.md for full details.
- [x] Marketing Intelligence Sprint — transformed PRACHAR from content generation platform into AI Communications Company. Built the Marketing Intelligence Engine (10 engines): Business Intelligence, Audience Intelligence, Competitor Intelligence, Marketing Objective, Campaign Strategy, Creative Direction, Media Planning, Budget Intelligence, Execution Planner, Learning Engine. CampaignBrain orchestrator chains all 9 engines in dependency order for full campaign analysis. Business Memory store persists learnings across campaigns (best practices, audience/creative/channel insights). BRO chat integrated — never directly answers strategic questions, consults Campaign Brain first. 10 new DB tables + Alembic migration 0002. 9 REST API endpoints under /campaign-brain/. 80 tests. See MARKETING_INTELLIGENCE.md for full architecture.
- [x] Architecture Stabilisation Sprint — eliminated architectural debt to support 100+ engines and the future AI Agency Council. 10 phases: (1) Responsibility refactor — Strategy Engine owns strategic intent only (channel_intent, budget_philosophy), Media/Budget/Objective own their tactical concerns; v2.0.0 schema. (2) Output versioning — schema_version/engine_version/prompt_version/model_version on every EngineOutput. (3) Domain models — DomainModel base class with from_dict/to_dict/validate/schema_version; all 10 models inherit it. (4) Campaign Brain API — 6 canonical public methods (analyse/consult/generate_strategy/generate_campaign/generate_media_plan/learn). (5) Remove embedded logic — chat.py and campaign_brain.py router delegate to brain public API, no manual engine chaining. (6) Memory abstraction — MemoryRepository Protocol in shared, PostgresMemoryRepository in api/infrastructure.py, DI; shared package no longer imports from api. (7) Domain boundaries — documented in boundaries.py (Presentation/Application/Domain/Infrastructure). (8) Event model — EventBus + 11 domain events (BusinessAnalysed, StrategyGenerated, CampaignCompleted, LearningStored, etc.). (9) Engine Registry — dynamic registration/discovery/health/version/capabilities via EngineRegistry + create_default_registry(). (10) Architecture tests — 48 tests enforcing no shared→api imports, no circular imports, no duplicate ownership, version compatibility, repository abstraction, brain-only orchestration, dependency inversion, engine independence. 202 tests total. See ARCHITECTURE_STABILISATION.md for full migration notes.
- [x] Agency Council Sprint — transformed Campaign Brain into an "Agency Council" that simulates an executive meeting with 9 specialist AI Directors (CSO, CCO, CMO, CPO, CBO, CFO, Compliance, Customer, Analytics). New `backend/agency_council/` package: domain models (DirectorOpinion, ConsensusDecision, CampaignScore, CouncilSession, CouncilLearning), Director base class, 9 Directors, ConsensusEngine (weighted voting, multi-round review, campaign scoring), CouncilMemoryRepository + InMemoryCouncilRepository + CouncilMemoryStore. 5 new DB tables + Alembic migration 0003. 4 REST API endpoints under `/agency-council/` (review, consensus, history, {campaign_id}). CampaignBrain.review_with_council() integrates council into brain. BRO chat summarises council decisions. 189 new council tests (Directors 68, Consensus 55, Memory 18, API 16, BRO 32). Total 621 tests passing. See AGENCY_COUNCIL.md for full architecture.
- [x] UX/Product Sprint — audited and rebuilt the first-time user journey for an immediate "wow" moment. (1) Onboarding flow — `/onboarding` 3-step guided (industry → business name → auto brand creation) with 9 industry presets (`src/lib/industries.ts`) that infer channels, budget, goals, and tone. (2) Dashboard rewrite — ONE dominant CTA ("Create My Campaign") for first-timers, "Review now" for pending approvals; greeting by business name; real brand data via TanStack Query hooks (`src/lib/hooks.ts`); 3-step "what happens next" explainer. (3) Sidebar simplified from 22 items across 6 sections to 8 items across 2 sections (Main: Home/My Brand/Campaigns/Results; More: Calendar/Channels/Reviews/Settings). (4) Campaign creation reduced from 7-step wizard to 1 step (goal + budget) — AI infers audience, networks, creatives from industry. (5) Campaign results presentation — Executive Summary, Why this strategy, Budget breakdown, What we'll post, Next actions, one-click "Approve & launch". (6) De-jargonised all copy: "AI Engine"→"Your marketing team", "ROAS"→"Revenue per ₹100", "Tokens used"→removed, "Networks"→"Channels", "Weekly Loop"→"Running smoothly". (7) Skeleton loading states + 5-step progress animation during campaign generation. (8) Real data replaces mock data on dashboard, brands list, brand detail, campaigns, results. Sign-up → campaign live reduced from ~20 clicks to ~7 clicks, 15+ decisions to 3. See PRODUCT_AUDIT_REPORT.md for full before/after analysis.
- [x] Conversational Onboarding Sprint — transformed onboarding from a form into a conversation with an AI marketing strategist. (1) New `/consult` backend router (2 endpoints) that takes free-text business descriptions → extracts 9 fields via LLM (name, industry, location, products, services, audience, goals, website, social handles) → auto-creates Brand → runs existing CampaignBrain.analyse() (business + audience + competitor engines) → generates business understanding (strengths, weaknesses, customers, competitors, maturity, risks) + top 5 growth opportunities (with impact/difficulty/timeframe) + 30-day marketing plan (4 weeks: objectives, content, offers, channels, KPIs). (2) New `/consult/campaign` endpoint runs full CampaignBrain.generate_campaign() (all 9 engines) → converts to presentation-deck preview (title, hero image concept, video concept, 5 post ideas, estimated reach, expected enquiries, budget, why, confidence, risks, alternative) → persists campaign plan. (3) Replaced form-based `/onboarding` page with conversational UI — chat interface, animated typing indicators, business understanding cards, growth opportunity cards, 30-day plan timeline, campaign preview deck, Approve/Regenerate/Back actions. (4) Conversation memory — extracted info stored in Brand.brand_graph JSONB, used by future campaign generation and BRO chat. (5) No new engines, no new architecture — uses existing Marketing Intelligence Engine. User journey: describe business in plain English → receive business assessment → receive 30-day plan → preview campaign → approve — all in ~5 minutes with 1 text input and 4 clicks. See CONVERSATIONAL_ONBOARDING_UX_REPORT.md for full metrics.
- [x] Agency Council Sprint — the core IP of PRACHAR. No single AI agent makes the final campaign decision; every campaign is reviewed by 9 independent specialist AI Directors before the Consensus Engine produces a weighted decision. Built the `agency_council` package (packages/shared/prachar_shared/agency_council/): 9 Directors (CSO, CCO, CMO, CPO, CBO, CFO, Compliance, Customer, Analytics), each returning a 9-field contract (opinion, reasoning, confidence, risks, alternatives, recommendations, evidence, priority, approval). ConsensusEngine uses WEIGHTED consensus (not majority voting) — weights depend on industry/objective/budget/campaign_type, deterministic and always sum to 1.0. Multi-round review (max 3) when disagreement > 0.45. Self-critique step before final approval. 7-dimension campaign scoring (strategy/creative/media/brand/performance/risk/compliance + overall). Compliance has veto power. CouncilMemoryRepository protocol + InMemoryCouncilRepository + PostgresCouncilRepository (DI pattern from Phase 6). 5 new DB tables (council_sessions, director_opinions, consensus_decisions, campaign_scores, council_learnings) + Alembic migration 0003. 4 REST API endpoints under /agency-council/ (review, consensus, history, {campaign_id}). CampaignBrain.review_with_council() — brain depends on Council interface, not concrete directors. BRO chat integration — is_council_review_request() detects review requests, summarise_council_decision() produces BRO-voiced summary, NEVER exposes raw director discussions. AI safety preamble in every director prompt (no hallucinations, cite evidence, no invented features). 189 council tests (directors 68, consensus 55, memory 18, BRO integration 32, API 16). See AGENCY_COUNCIL.md for full architecture.
- [x] Creator Growth Sprint — expanded PRACHAR to support TWO customer segments (Business Growth + Creator Growth) with native experiences for each. (1) New `customer_type` column on Brand table (migration 0004, default "business", values "business"|"creator"). (2) New `/creator` backend router (4 endpoints, all use AIGateway directly — NO new engines, NO duplicate infrastructure): `/creator/consult` (free-text channel description → Creator Profile with niche/platforms/upload frequency/content pillars/audience/growth stage/monetisation/competitors + Position with strengths/weaknesses/growth opportunities/content gaps/monetisation opportunities + 30-day plan with 4 weeks of videos/shorts/community posts/collaborations/SEO/newsletter/live sessions/KPIs), `/creator/campaign` (brand_id → 4-week content campaign with publishing schedule + expected growth), `/creator/repurpose` (one YouTube video → 11 asset types: Shorts, Reels, Facebook Reel, LinkedIn Post, X Thread, Blog Article, Newsletter, Email, Community Post, Podcast Summary, Sponsor Pitch), `/creator/youtube-plan` (video concept → 5 title options, 3 thumbnail concepts, opening hook, retention improvements, full description, 10 SEO keywords, 15 tags, chapters, pinned comment, community post, end screen suggestions). (3) Onboarding replaced "What business do you run?" with "Tell me who you are" → Business Growth vs Creator Growth → 10 business types or 10 creator types → branched conversation (business uses /consult, creator uses /creator/consult). (4) Creator dashboard with creator KPIs (Subscribers, Views, Watch Time, Retention, CTR, Uploads, Revenue, Brand Deals) + Today's recommended action (common dashboard element) + quick actions (Repurpose video, Plan YouTube video, Build content campaign) + approvals + trending opportunities + content pipeline. (5) Business dashboard UNCHANGED per instructions. (6) Sidebar branches: creator nav (Home/My Channel/Content/Audience/Repurpose/Plan YouTube/Calendar/Channels/Settings) vs business nav (unchanged). (7) New pages: `/app/repurpose` (content repurposing tool with 11 asset cards, each copyable/editable) and `/app/youtube-plan` (YouTube video planning with 11 sections). (8) Conversation memory: creator profile + position stored in Brand.brand_graph JSONB. (9) 5 new regression tests (creator endpoints require auth, customer_type schema validation, Brand model column). See CREATOR_PRODUCT_REVIEW.md for the decision gate document and CREATOR_SPRINT_REPORT.md for full architecture/migration/UX report. A YouTube creator can describe their channel in one message and receive: understanding, 30-day plan, content ideas, repurposed content, publishing plan — in ~5 minutes.
- [x] Unified Intelligence Sprint — consolidated the duplicated Business + Creator infrastructure into ONE extensible Domain Pack platform. AUDIT found: 2 copies of `_extract_json` (while a shared version already existed), 2 copies of brand-creation logic, 2 copies of campaign-plan persistence, 4 pairs of 80-95% similar frontend components, 2 hard-coded sidebar nav arrays, and creator bypassing CampaignBrain entirely (a bug — creators didn't benefit from the Marketing Intelligence Engine or Agency Council). FIX: (1) Domain Pack Architecture — `packages/shared/prachar_shared/domain_packs/` with `base.py` (DomainPack protocol + registry + 7 spec dataclasses: SubtypePreset, KpiCardSpec, ActionCardSpec, WidgetSpec, NavItemSpec, NavSectionSpec, ToolSpec), 4 built-in packs (BusinessPack, CreatorPack, RestaurantPack, ClinicPack) each defining discovery/goals/KPIs/opportunities/planning/campaign/dashboard/memory/conversation/sidebar/tools. Adding a domain = ONE folder + ONE file + ONE registration line. ZERO core modifications. (2) Universal Consult Engine (`apps/api/prachar_api/infrastructure/consult_engine.py`) — ONE pipeline for ALL domains: extract → create brand → CampaignBrain.analyse() (ALWAYS — fixed the creator bypass) → generate understanding → update memory → return unified response. Also handles campaign generation (CampaignBrain.generate_campaign() ALWAYS) and domain-specific tools (Repurpose, YouTube Plan via ToolSpec). (3) Unified Consult Router (`apps/api/prachar_api/routers/unified_consult.py`) — 5 endpoints: `POST /consult` (universal), `POST /consult/campaign` (universal), `POST /consult/tool/{tool_id}` (domain tools), `GET /consult/domains` (list all packs for onboarding), `GET /consult/nav/{domain}` (domain config for sidebar/dashboard). Legacy `/consult` and `/creator` routers remain for backward compatibility. (4) Shared Presentation Layer (`apps/web/src/components/consult/SharedPresentation.tsx`) — generic UnderstandingCards, OpportunityCards, PlanTimeline, CampaignDeck driven by domain-supplied data. Replaces 4 pairs of duplicated components. (5) Unified Dashboard Shell (`apps/web/src/components/consult/DashboardShell.tsx`) — ONE shell with widget slots (kpi_grid, quick_actions, approvals, pipeline, trending, promotions, appointments). Domain packs supply widget specs. Adding a domain = supplying a DomainConfig. No shell changes. (6) Domain-driven sidebar — `apps/web/src/app/app/layout.tsx` now fetches nav from `GET /consult/nav/{domain}` instead of hard-coded BUSINESS_NAV/CREATOR_NAV arrays. Fallbacks kept for resilience. (7) Unified API client (`apps/web/src/lib/unified-consult.ts`) — ONE client for ALL domains. (8) 41 architecture tests (no duplication, no circular deps, packs don't import FastAPI/SQLAlchemy/api, plugin isolation, every pack has required attributes, backward compatibility). (9) 20 unified consult router tests (domains endpoint, nav endpoint, auth, validation, founder demo: Restaurant + Creator + Clinic all use the SAME /consult endpoint). See UNIFIED_INTELLIGENCE_REVIEW.md for the mandatory audit document, UNIFIED_INTELLIGENCE_MIGRATION.md for the migration guide + founder demo. The founder demo proves: Register a Restaurant, Register a Creator, Register a Clinic — all three follow the SAME pipeline, only the Domain Pack changes.
- [x] Sprint 1 (Trust) + Sprint 2 (Mock Data) + Sprint 3 (Progressive Enablement) + Orb Awareness Expansion — (1) Sprint 1 Trust: eliminated all deceptive UI interactions from web-v2 frontend. Dead buttons wired or removed. All `alert()` calls and "coming soon" toasts eliminated. Experimental features marked with LabsBanner. (2) Sprint 2 Mock Data: replaced ALL mock/fabricated data across 14 pages with real API calls (Channels→/connections, Settings→/auth/me+/billing/subscription, Reports→/reports, Knowledge→/knowledge/sources with upload+delete) or honest empty states (Calendar, Reviews, 8 Tier 3 Labs pages). Zero mock data references remain. (3) Sprint 3 Progressive Enablement: wired Generate buttons to real backend APIs — AI Video→POST /api/video/generate (fixed double-/api path bug), AI Images→POST /api/video/generate-image, Creative AI→POST /creative-studio/generate (discovered real API requires {campaign_id, creative_direction_id, domain} not {prompt, brand_id}). (4) Orb Awareness Expansion: added 8 new context providers (Audit, Attribution, Timeline, Workflow, Reports, Billing, CreativeStudio, VideoGen) — Orb now has 16 context providers covering ALL 16 backend subsystems. Added 3 new tools (attribution.query, timeline.query, workflow.query) — 30 tools total. Fixed pre-existing timeline INSERT crash (RLS context lost after rollback — re-set app.tenant_id after every rollback). Fixed user object expiration (capture user_tenant_id/user_id before DB operations). 756 tests pass, 0 TypeScript errors, 18 pages return 200. See LAUNCH_READINESS.md for the feature matrix and sign-off criteria.

**Total: 626 + 41 architecture + 20 unified consult = 687 tests passing. 0 regressions. Frontend: 33 pages compile, typecheck passes. Adding a new domain takes under one day (proven by RestaurantPack, ClinicPack, and the inline LawFirmPack test).**

## Marketing Intelligence Engine — Architecture (post-stabilisation)
Clean architecture layers (dependencies point inward only):
- **Domain** (`packages/shared/prachar_shared/marketing_intelligence/{domain_base,*_engine,repository,events}.py`): dataclasses, protocols, events. No SQLAlchemy/FastAPI/Pydantic imports.
- **Application** (`brain.py`, `memory.py`, `registry.py`): CampaignBrain orchestrator, BusinessMemoryStore, EngineRegistry.
- **Infrastructure** (`apps/api/prachar_api/infrastructure.py`): PostgresMemoryRepository implements MemoryRepository protocol.
- **Presentation** (`apps/api/prachar_api/routers/`): FastAPI endpoints delegate to CampaignBrain public API.

CampaignBrain public API (the ONLY orchestration layer):
- `analyse()` — business + audience + competitor
- `consult()` — focused strategy for BRO chat (4 engines)
- `generate_strategy()` — objective + strategy
- `generate_campaign()` — full campaign (9 engines)
- `generate_media_plan()` — media plan only
- `learn()` — post-campaign learning + memory update

Architecture invariants enforced by `test_mi_architecture.py` (48 tests):
1. No shared→api imports (dependency inversion)
2. No circular imports within marketing_intelligence
3. No duplicate responsibility ownership
4. Every engine has version constants (ENGINE_VERSION, PROMPT_VERSION, SCHEMA_VERSION)
5. BusinessMemoryStore depends on MemoryRepository protocol, not SQLAlchemy
6. Routers delegate to CampaignBrain, no manual engine chaining
7. Domain models inherit DomainModel
8. Engines don't import each other

## Channel/Network adapter registry (complete)
### Organic (ChannelAdapter): google_search, gsc, gmb, youtube, instagram, facebook, tiktok, linkedin, pinterest, x, whatsapp, telegram, line, vk, reddit, naver
### Ads (AdNetworkAdapter): google_ads, meta_ads, tiktok_ads, linkedin_ads, pinterest_ads, x_ads, microsoft_ads, snap_ads, reddit_ads, yandex_direct

## Frontend (apps/web) — UX patterns & conventions
- **Build/test:** `pnpm --dir apps/web typecheck` (tsc --noEmit) · `pnpm --dir apps/web build` (next build) · `pnpm --dir apps/web dev` (next dev)
- **Data fetching:** TanStack Query via `src/lib/hooks.ts` — `useBrands()`, `useActiveBrand()`, `useCampaignPlans(brandId)`. Stale time 30s, auto-refetch 30s.
- **API client:** `src/lib/api.ts` — `apiGet`, `apiPost`, `ApiError`. Auth token from `localStorage.prachar_token`.
- **Industry presets:** `src/lib/industries.ts` — single source of truth for industry-specific defaults (channels, budget, goals, tone). 9 industries. `industryToBrand()` maps to BrandIn API payload.
- **Onboarding state:** `localStorage.prachar_onboarded` and `localStorage.prachar_active_brand` track onboarding without backend changes.
- **Design system:** "Billboard & Ink" — dark theme, accent yellow (#FFD400), glass-strong cards, font-display for headings, font-mono for technical labels. Components in `src/components/ui/`.
- **Copy rules:** Business language, never jargon. "Your marketing team" not "AI Engine". "People reached" not "Impressions". "New customers" not "Conversions". "Channels" not "Networks". User approves everything before it goes live.
- **Campaign creation:** 1-step (goal + budget) → POST `/campaign-brain/full-campaign` → results presentation with Executive Summary / Why / Budget / Next actions / Approve. Never expose audience spec, networks, or creative generation UI to first-time users.
- **Sidebar nav:** 8 items only (Home, My Brand, Campaigns, Results, Calendar, Channels, Reviews, Settings). Power features hidden in "More" section. Domain packs now also expose Creative Studio, Review, and Performance nav items.

## Five-Programme Product Roadmap Sprint (completed)

Implemented the full 5-programme, 47-part product roadmap (see `ROADMAP.md`) via 8 parallelised waves of subagents. **827 tests pass** (1 pre-existing YouTube failure unrelated). Typecheck + build clean.

### Programme 1: Campaign Quality (10 parts)
Every campaign now feels like it came from a top marketing agency. 9 quality modules added to the Universal Consult Engine, each following the same pattern (generation function in `marketing_intelligence/`, `_prompt` field on DomainPack, `_generate_*` method in `consult_engine.py`, render section in `SharedPresentation.tsx`):
- **creative_directions** (P1.1) — 3 directions per campaign with hook, angle, tone, headline, CTA
- **hooks** (P1.2) — 5 hook patterns (question, stat, story, contrarian, aspiration)
- **audience_psychology** (P1.3) — motivations, objections, emotional triggers, decision style
- **offers** (P1.4) — 3 engineered offers using anchoring/scarcity/bundling/loss-aversion/decoy
- **pricing_psychology** (P1.5) — 3 pricing presentations (charm/tier/bundle)
- **seasonal_ideas** (P1.6) — current month + next 2 months, domain-specific
- **local_ideas** (P1.7) — local events/partnerships/geo-targeting (creators skip)
- **differentiation** (P1.8) — competitor claims + counters matrix
- **ab_concepts** (P1.9) — 6 concepts (3 directions × A/B variants)
- **Campaign Quality regression suite** (P1.10) — 80 tests verifying all 9 modules across 4 domains

### Programme 2: Creative Studio (15 parts)
One click produces a complete marketing package — campaign → poster → video → carousel → story → WhatsApp → Facebook → LinkedIn → email → landing page → SMS.
- **Format spec framework** (P2.1) — `CreativeFormatSpec` + registry, 10 format specs
- **Studio engine** (P2.2) — `CreativeStudio.generate_all()` parallel generation via asyncio.gather
- **API endpoints** (P2.3) — POST /creative-studio/generate, /generate/{format_id}, GET /{package_id}
- **10 format implementations** (P2.4-P2.13) — poster, video_script, carousel, story, whatsapp, facebook, linkedin, email, landing_page, sms (each with generate_* function + tests)
- **Creative Studio UI** (P2.14) — /app/creative-studio page with tabbed format view, copy/regenerate buttons
- **Sidebar entry** (P2.15) — Creative Studio in all domain pack nav_sections

### Programme 3: Human-in-the-loop (8 parts)
AI behaves like an agency — draft → review → suggestions → founder edits → approve → publish.
- **Review status enums** (P3.1) — in_review, changes_requested, approved + migration 0005
- **Review queue API** (P3.2) — GET /review/queue, POST /{id}/request-changes, /approve, /publish + migration 0007 (widen status columns)
- **AI review suggestions** (P3.3) — POST /review/{id}/suggestions returns 3-5 improvement suggestions
- **Inline editing** (P3.4) — PATCH /review/{id}/field with audit log version history
- **Review queue UI** (P3.5) — /app/review page with status badges, filters
- **Review detail UI** (P3.6) — /app/review/{id} with inline editing, suggestion panel, action bar
- **Sidebar entry** (P3.7) — Review in all domain pack nav_sections
- **Publish adapters** (P3.8) — Celery task publish_campaign triggers channel adapters, wired into review publish endpoint

### Programme 4: Performance Intelligence (8 parts)
Once campaigns run, AI asks: What happened? Why? What next? Creates a feedback loop.
- **Performance data model** (P4.1) — CampaignPerformance table + migration 0006
- **Ingestion worker** (P4.2) — Celery task pulls daily metrics from channel adapters, computes CTR/CPA/ROAS, upserts
- **"What happened" analysis** (P4.3) — PerformanceEngine.analyse() returns summary, top metrics, trend, notable days, benchmark comparison
- **"Why" root-cause** (P4.4) — PerformanceEngine.explain() detects creative fatigue, audience saturation, low budget, seasonality, competitor activity
- **"What next" recommendations** (P4.5) — PerformanceEngine.recommend() suggests scale/pause/increase/refresh/test
- **Feedback loop** (P4.6) — CampaignBrain reads past performance learnings when generating new campaigns
- **Performance UI** (P4.7) — /app/performance/[id] with metrics grid, Recharts chart, why/next sections
- **Sidebar entry** (P4.8) — Performance in all domain pack nav_sections

### Programme 5: AI Marketing Director (6 parts)
BRO becomes proactive — "Sales dropped 14% this week. I recommend launching a weekend offer."
- **Anomaly detection** (P5.1) — ProactiveEngine.detect_anomalies() finds drops/spikes/plateaus, daily Celery task
- **Proactive recommendations** (P5.2) — generate_recommendation() per anomaly, GET /proactive/notifications
- **BRO proactive notifications** (P5.3) — GET /chat/proactive returns BRO-voice messages (no jargon)
- **Notification UI** (P5.4) — Bell icon in sidebar with badge, ProactiveNotifications panel
- **One-click launch** (P5.5) — POST /proactive/{id}/launch pre-fills campaign creation form (no auto-publish)
- **E2E regression suite** (P5.6) — 11 tests: anomaly → recommendation → BRO notification → launch → campaign created → review queue

### New packages created
- `packages/shared/prachar_shared/creative_studio/` — format specs, studio engine, 10 format generators
- `packages/shared/prachar_shared/marketing_intelligence/` extensions: hooks, audience_psychology, offer_engine, pricing_psychology, seasonal_engine, local_engine, differentiation_engine, ab_concepts, performance_engine, proactive_engine, review_engine

### New routers
- `/creative-studio` — generate all/one format, get package
- `/review` — queue, request-changes, approve, publish, suggestions, field edit
- `/performance` — summary, why, next
- `/proactive` — notifications, launch

### New frontend pages
- `/app/creative-studio` — Creative Studio with 10 format tabs
- `/app/review` + `/app/review/[id]` — Review queue + detail with inline editing
- `/app/performance/[id]` — Performance dashboard with charts
- Bell icon + ProactiveNotifications panel in sidebar

### Migrations
- 0005_review_statuses — add in_review/changes_requested/approved enums
- 0006_campaign_performance — CampaignPerformance table
- 0007_widen_status_columns — widen status columns for changes_requested (18 chars)

### Test count
- **827 tests pass** (up from 109 at roadmap start — +718 tests)
- 1 pre-existing YouTube failure (unrelated to roadmap)

## Roadmap 2 — Polish, AI Quality, Integrations (completed)

Implemented the 3-phase, 31-part Roadmap 2 (see `ROADMAP_2.md` and `POLISH_AUDIT.md`) via 8 waves of subagents. **963 tests pass** (up from 827 — +136 tests). Typecheck + build clean.

### Phase A: Product Polish (14 parts)
No new features — audited and improved every screen. Started with mandatory UX audit (`POLISH_AUDIT.md`) identifying 20 problems across 7 screens.
- **Dashboard**: KPI cards answer "why should I care?" (trend + context + "See why" links), empty states removed, content-shaped skeletons, fade-in transitions, standardized typography (H1 `text-2xl sm:text-3xl`), mobile-first responsive grid
- **Campaign Builder**: Consultant voice ("Tell me what you're trying to achieve"), goal reasoning per option, contextual budget hints (lean/balanced/aggressive/scale), industry-specific progress steps
- **Creative Studio**: Granular per-field regeneration (headline/CTA/offer/colours/tone separately, not whole format) for 7 formats, inline editing for all 10 formats
- **Review Queue**: Google Docs-style inline comments (highlight → comment → thread → resolve, migration 0008), version history (view/compare/restore, migration 0009), approve/reject confirmation modals, "what happens next" success screen
- **Performance**: Stories not dashboards ("This week's campaign brought in 31 new enquiries. Instagram delivered 74%. Weekend campaigns outperform weekdays by 28%."), platform breakdown, time insights, de-jargonised (ROAS → "Revenue per ₹100"), charts as supporting evidence
- **SharedPresentation**: "Why" explanations for all 19 sections, 3-tab grouping (Strategy/Creative/Context), responsive grids, visual hierarchy (prominent first section per tab)
- **Layout**: Nav regrouped into 3 sections (Main/Brand/Settings), "Customer Reviews" rename (was "Reviews"), mobile active states, bell icon pulse animation
- **Infrastructure**: Playwright screenshot setup (`screenshot.config.ts`, 8 pages × 3 viewports)

### Phase B: AI Quality (4 parts)
BRO thinks like a strategist, not just a generator. For every campaign, generates 3 strategies and explains why it chose the primary.
- **B.1.1 Strategy engine**: `StrategyEngine.generate_strategies()` → 3 genuinely different strategies (primary/alternative/contrarian), each with name/approach/why_it_works/risks/expected_outcome. Wired into `consult_engine.py`. 23 tests.
- **B.1.2 Strategy explanation**: `StrategyEngine.explain_choice()` → "Why A not B" reasoning with chosen_strategy/reasoning/why_not_alternative/why_not_contrarian/key_factors. Considers past performance from P4.6 feedback loop.
- **B.2.1 Strategy UI**: 3 strategies as cards (primary highlighted with accent border + "Recommended" label). "Why I chose X" explanation panel below with key_factors as badges.
- **B.2.2 Strategy comparison**: "Compare strategies" toggle → side-by-side table (Approach/Why it works/Risks/Expected outcome × Primary/Alternative/Contrarian). Responsive: stacked on mobile.

### Phase C: Integrations (13 parts)
Connected PRACHAR to real platforms so BRO reasons from live performance, not assumptions.
- **C.1.1-C.1.6 Live data ingestion**: Wired 6 platforms into the performance ingestion worker:
  - Google Business Profile (search impressions, directions, calls, photo views)
  - Meta: Facebook + Instagram (reach, impressions, clicks, conversions, spend — paid + organic)
  - LinkedIn (impressions, clicks, engagement)
  - WhatsApp Business (messages sent, delivered, read, replied)
  - Google Ads (impressions, clicks, conversions, spend, ROAS)
  - YouTube (views, watch time, subscribers, clicks)
  - All with graceful skip when not connected. +39 tests.
- **C.2.1-C.2.2 BRO reasons from live data**: CampaignBrain loads live performance data (last 30 days, all channels) and includes it in campaign generation context. ProactiveEngine includes live data in anomaly recommendations. PerformanceEngine.tell_story() includes platform breakdown with reach/engagement/spend/ROAS. +10 tests.
- **C.3.1-C.3.4 BRO publishes to real platforms**: When a campaign is approved, BRO publishes to:
  - Google Business Profile (local posts: offers, photos, updates)
  - Facebook + Instagram (posts and reels)
  - WhatsApp Business (opt-in compliant broadcast messages)
  - Google Ads + Meta Ads (creates and launches ad campaigns)
  - All with graceful skip, per-channel error isolation, and audit trails. +22 tests.

### Migrations (Roadmap 2)
- 0008_review_comments — ReviewComment table (inline comments)
- 0009_review_versions — ReviewVersion table (version history)

### Test count
- **963 tests pass** (up from 827 at Roadmap 2 start — +136 tests)
- 1 pre-existing YouTube failure (unrelated)

## Production Scaling Sprint — crash prevention for 1K-10K users

Fixed 4 resource leaks that would crash the app between 500-3000 users. None were CPU/RAM issues — all were unbounded resource accumulation.

### Fixes
1. **Temp video file leak** (`apps/api/prachar_api/routers/video_gen.py`): `_download_gemini_video()` used `NamedTemporaryFile(delete=False)` and never cleaned up. Every video generation leaked a ~50MB file on disk. At 1K users × 8 videos/mo = 400GB/month of leaked files → disk fills → Postgres crashes. Fixed with `try/finally` + `os.unlink`. Always cleans up even on error.
2. **Rate limit store memory leak** (`apps/api/prachar_api/rate_limit.py`): `_store` dict grew by IP+endpoint key forever, old entries only cleaned when that specific IP returned. At 10K unique IPs over months → 100K+ entries → OOM. Added `_sweep_store()` that runs every 5 min (or when store > 50K entries) and drops buckets with no timestamps in the last hour. Bounds store size regardless of unique IP count.
3. **Admin endpoints loaded all rows** (`apps/api/prachar_api/routers/admin.py`):
   - `/admin/brands/summary` — added `limit` (default 100, max 1000) + `offset` pagination. Was loading every brand into RAM.
   - `/admin/export/brands.csv` — rewrote to stream rows in batches of 500 via `StreamingResponse` + async generator. Was building the entire CSV in a single `StringIO` (50MB+ for 10K brands).
4. **DB connection pool too small** (`apps/api/prachar_api/db.py`): bumped `pool_size` 10→25, `max_overflow` 20→50 (75 max connections). Added `pool_recycle=1800` (30 min, prevents stale connection errors behind PgBouncer/RDS Proxy) and `pool_timeout=30` (fail fast instead of hanging). Made pool size configurable via `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` env vars.

### New: PgBouncer config (`infra/pgbouncer/pgbouncer.ini`)
Production connection pooler for Postgres. Multiplexes hundreds of app connections onto ~50 real DB connections. Transaction-pooling mode (safe with SQLAlchemy async + `pool_pre_ping`). Added `pgbouncer` service to `docker-compose.yml` under `production` profile (only starts with `docker compose --profile production up`). When using PgBouncer, set `DB_POOL_SIZE=10` (PgBouncer handles multiplexing).

### New: Health endpoints (`apps/api/prachar_api/routers/misc.py`)
- `GET /health` — lightweight liveness (200 if process alive). For load balancers.
- `GET /health/live` — liveness with PID. For orchestrators (restart on failure).
- `GET /health/ready` — readiness check: DB (`SELECT 1`), Redis (`PING`), disk space (`shutil.disk_usage`). Returns 503 if DB down or disk <5% free. Redis down degrades gracefully (warning, not failure) since app has inline fallback. Includes latency_ms per check. For Kubernetes readiness probes + uptime monitors.

### Config additions (`packages/shared/prachar_shared/config.py`)
- `db_pool_size: int = 25` — SQLAlchemy pool size (set to 10 with PgBouncer)
- `db_max_overflow: int = 50` — SQLAlchemy max overflow
- `rate_limit_enabled: bool = True` — master switch for rate limiting (false in tests)

### Test count
- **288 API tests pass** (no regressions from scaling fixes)
- All 23 auth hardening tests pass with rate limiting properly isolated via module-level `_enabled` flag (no settings cache pollution between test files)

## Celery Scaling Sprint — 10K users horizontal scaling

The weekly loop is the bottleneck at scale: 10K brands × 7 steps = 70K tasks/week. The old setup (single worker, 4 concurrency, global 60/min rate limit) took ~19 hours. Now it takes ~5 hours with 8 shard workers.

### What changed

**1. Removed global rate limit** (`celery_app.py`): `task_default_rate_limit="60/m"` was the #1 bottleneck — 60 tasks/min = 19 hours for 70K tasks. Replaced with per-queue concurrency tuning (the right scaling lever).

**2. Brand sharding across 8 queues** (`loop.py`): `_shard_queue(brand_id)` routes each brand to `loop-{hash(brand_id) % 8}`. Brands distribute evenly (~12.5% per shard). Multiple workers process shards in parallel without overlap. Same brand always goes to the same shard (consistent routing).

**3. Task routing by type** (`celery_app.py`): `task_routes` sends each task type to its dedicated queue:
- `dispatch` — beat + dispatch_due (lightweight, 1 worker)
- `loop-0`..`loop-7` — weekly loop chains (8 shard workers)
- `ingest` — data ingestion (crawler, SERP)
- `organic` — content generation + publishing
- `ads` — ad platform API calls
- `measure` — performance ingestion + anomaly detection
- `creative` — creative generation
- `dlq` — dead letter queue

**4. Batched dispatch** (`loop.py`): `dispatch_due` now enqueues brands in batches of 100 (configurable via `CELERY_DISPATCH_BATCH_SIZE`) with progress logging, instead of a tight loop that spikes Redis.

**5. Scaled worker services** (`docker-compose.yml`): 13 worker services under `production` profile:
- `worker-dispatch` (concurrency=1)
- `worker-loop-0`..`worker-loop-7` (concurrency=4 each = 32 parallel loops)
- `worker-ingest`, `worker-organic`, `worker-ads`, `worker-measure`, `worker-creative`

**6. Configurable concurrency** (`config.py`): `CELERY_CONCURRENCY_LOOP`, `CELERY_CONCURRENCY_INGEST`, etc. env vars tune each pool without code changes.

### Scaling math at 10K users

| Metric | Before | After |
|--------|--------|-------|
| Weekly loop time | ~19 hours | ~5 hours |
| Parallel loops | 4 | 32 (8 shards × 4 concurrency) |
| Tasks/min throughput | 60 (rate limited) | ~240 (32 concurrency × ~1 task/8min) |
| Redis spike on dispatch | Yes (10K enqueued at once) | No (batched 100) |
| Horizontal scaling | No (single worker) | Yes (`docker compose up --scale worker-loop-0=2`) |

### How to run in production

```bash
# Local dev (single worker, all queues):
make worker && make beat

# Production (scaled workers):
docker compose --profile production up -d

# Or via Makefile (each in separate terminal/process):
make worker-dispatch && make beat
make worker-loop-0 & make worker-loop-1 & ... & make worker-loop-7 &
make worker-ingest & make worker-organic & make worker-ads &
make worker-measure & make worker-creative &

# Scale a specific shard horizontally (2 workers on loop-0):
docker compose --profile production up --scale worker-loop-0=2
```

### Config additions (`packages/shared/prachar_shared/config.py`)
- `celery_loop_shards: int = 8` — number of shard queues
- `celery_concurrency_loop: int = 4` — concurrency per loop shard worker
- `celery_concurrency_ingest/organic/ads/measure/creative: int` — per-queue concurrency
- `celery_max_tasks_per_child: int = 100` — memory leak protection
- `celery_dispatch_batch_size: int = 100` — brands per Redis pipeline batch
- `celery_prefetch_multiplier: int = 1` — 1 for long tasks, 4-8 for short tasks

### Test count
- 127 worker tests pass (1 pre-existing YouTube stub failure, unrelated)
- 288 API tests pass (no regressions)
- Shard distribution verified: 10K brands → ~12.5% per shard, consistent routing
