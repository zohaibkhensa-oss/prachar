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

**Total: 154 tests passing across all packages (shared 107, workers 32, api 15).**

## Channel/Network adapter registry (complete)
### Organic (ChannelAdapter): google_search, gsc, gmb, youtube, instagram, facebook, tiktok, linkedin, pinterest, x, whatsapp, telegram, line, vk, reddit, naver
### Ads (AdNetworkAdapter): google_ads, meta_ads, tiktok_ads, linkedin_ads, pinterest_ads, x_ads, microsoft_ads, snap_ads, reddit_ads, yandex_direct
