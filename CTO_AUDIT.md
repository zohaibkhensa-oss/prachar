# PRACHAR — Official CTO Production Readiness Audit

**Date:** 2026-07-25
**Auditor:** Chief Technology Officer
**Repository:** `~/projects/prachar`
**Version Audited:** Post-Sprint S9 (154 tests passing)

---

## 1. Executive Summary

PRACHAR is an ambitious AI-driven multi-tenant advertising platform that has executed 9 sprints (S0–S9) covering 16 organic channels, 10 ad networks, 14 locale packs, an AI gateway with 3-provider fallback, a Celery-driven weekly autonomous loop, and a premium Next.js 15 frontend with 33 routes. The codebase demonstrates **strong architectural foundations** — particularly in Row-Level Security, audit logging, design system quality, and AI provider abstraction — but contains **critical production-readiness gaps** in security (token storage, rate limiting), operational resilience (no pagination, in-memory state, no observability), and infrastructure (no Terraform, no backups, no monitoring).

**The product is feature-complete for a beta launch but NOT yet production-hardened.** With ~2–3 weeks of focused hardening work, it can reach a defensible production state.

### Headline Scores

| Dimension | Score | Verdict |
|-----------|-------|---------|
| Architecture | 8.0/10 | Excellent design, solid foundations |
| Backend | 6.5/10 | Good structure, missing production features |
| Frontend | 8.5/10 | Premium UX, accessibility gaps |
| Security | 5.0/10 | **Critical vulnerabilities** |
| Performance | 6.5/10 | Adequate, untested at scale |
| AI Architecture | 7.0/10 | Good abstraction, missing safety nets |
| Infrastructure | 4.5/10 | **Significant gaps** |
| Launch Readiness | 5.5/10 | Beta-ready, not production-ready |
| **Overall** | **6.5/10** | **Hardening sprint required** |

---

## 2. Architecture Score: 8.0/10

### Strengths
- **Clean monorepo layout** — `apps/{api,web,workers,ai-gen}` + `packages/shared` enforces separation of concerns
- **Multi-tenant RLS** — defense-in-depth with middleware → session → DB policy layers
- **Provider abstraction** — `ChannelAdapter` and `AdNetworkAdapter` base classes keep platform logic isolated (zero platform logic outside adapters, per spec)
- **AI gateway** — clean tiering, caching, budget tracking, 3-provider fallback chain
- **Audit immutability** — `REVOKE UPDATE, DELETE ON audit_events` enforced at DB level
- **Weekly loop orchestration** — 7-step Celery chain (measure → diagnose → regenerate → policy → publish → budget_realloc → report)

### Weaknesses
- **No service layer** — routers talk directly to DB, mixing request handling with business logic
- **No repository pattern** — queries scattered across routers, hard to test in isolation
- **In-memory state in critical paths** — API tokens, attribution touchpoints, white-label config all lost on restart
- **No bounded contexts** — all routers in one app, no module boundaries
- **Stub implementations** — OAuth callbacks, S3 uploads, visibility score are stubs

---

## 3. Backend Score: 6.5/10

**File:** `apps/api/prachar_api/`

### What's Done Well
- Factory pattern (`create_app()`) with proper middleware ordering
- `Annotated` dependency injection pattern (`SessionDep`, `CurrentUser`, `require_role`)
- Async engine with `pool_pre_ping=True`, pool_size=10, max_overflow=20
- bcrypt password hashing with 72-byte truncation
- Separate JWT secrets for access/refresh tokens
- `SECURITY DEFINER` function for login bypasses RLS correctly
- 11 routers, consistent `HTTPException` usage, proper status codes

### Critical Gaps
| # | Issue | Impact |
|---|-------|--------|
| 1 | **No rate limiting** anywhere | Brute force, abuse, DDoS exposure |
| 2 | **No pagination** on any list endpoint | Will fail with production data |
| 3 | **Access token TTL = 24 hours** | Excessive; should be 15–60 min |
| 4 | **No global exception handler** | Unhandled errors leak stack traces |
| 5 | **In-memory storage** for API tokens, attribution touchpoints, white-label config | Data loss on restart |
| 6 | **No request ID/correlation ID** | Cannot trace requests in production |
| 7 | **No structured logging** | Plain text, no JSON, no log aggregation |
| 8 | **No refresh token rotation** | Token replay attack risk |
| 9 | **No token revocation/blacklist** | Cannot invalidate compromised tokens |
| 10 | **Audit funnel has no auth or rate limit** | Free endpoint vulnerable to abuse |

### Endpoint Inventory (44 endpoints)
- **Auth:** 4 (register, login, refresh, me)
- **Brands:** 4 (create, list, get, score)
- **Audits:** 3 (start, get, SSE events)
- **Connections:** 3 (list, oauth, callback)
- **Campaigns:** 4 (create, list, pause, resume)
- **Reports:** 2 (latest, list)
- **Attribution:** 3 (track, convert, pixel.js)
- **Admin:** 6 (costs, api-tokens ×2, whitelabel, summary, csv export)
- **Chat:** 1 (AI assistant)
- **Video/Image Gen:** 2 (generate-video, generate-image)
- **Health:** 1
- **OAuth:** 1 (per channel)

---

## 4. Frontend Score: 8.5/10

**File:** `apps/web/`

### What's Exceptional
- **Premium design system** — Space Grotesk + Inter + IBM Plex Mono, dark-first palette (#0B0F14 bg, #FFD400 accent), 3D shadow hierarchy, glass morphism
- **Signature components** — `Card3D` (mouse-tracking tilt), `PerformanceRing` (SVG circular progress), `Metric` (animated count-up), `EmptyState` (educates instead of "No Data")
- **27 reusable components** with consistent quality
- **33 routes** all with responsive layouts, mobile sidebar, staggered animations
- **TanStack Query** with 30s stale time, 1 retry, no window-focus refetch
- **TypeScript strict** + `noUncheckedIndexedAccess` + Zod schemas
- **Custom easing curves** `[0.16, 1, 0.3, 1]` for premium feel
- **AI-themed UI** — thinking dots, confidence meters, AIThinkingOverlay

### Critical Gaps
| # | Issue | Impact |
|---|-------|--------|
| 1 | **Password stored in localStorage** (`login/page.tsx:31`) | XSS = password theft |
| 2 | **JWT in localStorage** (not httpOnly cookies) | XSS = token theft |
| 3 | **No error boundary** | Unhandled React errors crash app |
| 4 | **No 404/500 error pages** | Poor error UX |
| 5 | **No form validation library** | Manual useState validation only |
| 6 | **Limited ARIA attributes** (only 6 found) | Accessibility failures |
| 7 | **No keyboard navigation** in modals/dialogs | WCAG non-compliance |
| 8 | **No SEO** — missing OpenGraph, sitemap, structured data | Poor discoverability |
| 9 | **No code splitting** | Large initial bundle |
| 10 | **No Suspense boundaries** | No route-level loading |

### Page UX Scores (Average: 8.7/10)
| Page | Score | Page | Score |
|------|-------|------|-------|
| Landing | 9/10 | Mission Control | 9/10 |
| Login | 8/10 | Brands | 9/10 |
| Brand Detail | 9/10 | Campaigns (Kanban) | 9/10 |
| Creative AI | 9/10 | Video Studio | 9/10 |
| Image Studio | 8/10 | Channels | 9/10 |
| Analytics | 9/10 | Settings | 9/10 |
| Reports | 7/10 | Listening | 7/10 |

---

## 5. Security Score: 5.0/10

### Critical Vulnerabilities

#### CRITICAL: Password Stored in localStorage
- **File:** `apps/web/src/app/login/page.tsx:31`
- **Code:** `window.localStorage.setItem("prachar_password", password);`
- **Impact:** Any XSS attack steals user passwords. Comment says "dev/demo only" but it ships in production code.
- **Fix:** Remove immediately. Migrate to httpOnly Secure SameSite cookies.

#### CRITICAL: JWT Tokens in localStorage
- **File:** `apps/web/src/lib/auth.ts:8-13`
- **Impact:** XSS accessible. No CSRF protection (since not using cookies, but still vulnerable).
- **Fix:** Migrate to httpOnly cookies with CSRF tokens.

#### CRITICAL: No Rate Limiting
- **Files:** All routers, no middleware
- **Impact:** `/auth/login` and `/auth/register` open to brute force. `/brands/audit` (free, no auth) open to abuse. Video gen endpoints open to cost attacks.
- **Fix:** Implement `slowapi` or Redis-backed limiter. 5 req/min on auth, 10 req/min on audit, per-user limits on expensive ops.

#### CRITICAL: Weak Default Secrets
- **File:** `.env.example:11-16`, `config.py:18-23`
- **Defaults:** `JWT_SECRET=change-me-jwt`, `JWT_REFRESH_SECRET=change-me-refresh`, `TOKEN_ENC_KEY=change-me-32-byte-hex-key-please`
- **Impact:** Developers may deploy with defaults. Anyone reading the repo knows the secrets.
- **Fix:** Remove defaults. Require explicit setting with startup validation.

#### HIGH: No CSRF Protection
- **Impact:** State-changing operations vulnerable to CSRF.
- **Fix:** Implement CSRF tokens for all mutations.

#### HIGH: Docker Containers Run as Root
- **Files:** `apps/api/Dockerfile`, `apps/workers/Dockerfile`
- **Impact:** Container escape = full host compromise.
- **Fix:** Add non-root user (web Dockerfile already does this correctly).

### What's Done Well
- ✅ **RLS with FORCE ROW LEVEL SECURITY** on 11 tables
- ✅ **Audit logging** immutable at DB level (`REVOKE UPDATE, DELETE`)
- ✅ **bcrypt** password hashing
- ✅ **AES-GCM** encryption for OAuth tokens at rest
- ✅ **No `dangerouslySetInnerHTML`** in frontend
- ✅ **No hardcoded secrets** in code (only in defaults)
- ✅ **Pydantic v2** input validation throughout
- ✅ **SQLAlchemy ORM** prevents SQL injection (mostly)

---

## 6. Performance Score: 6.5/10

### Backend
- **Connection pool:** 10 base + 20 overflow = 30 max. Reasonable for small-medium.
- **No query logging** — cannot detect slow queries in production
- **No N+1 detection** — no `selectinload`/`joinedload` used
- **No caching layer** for API responses (only AI gateway cached)
- **SSE creates new DB session** per event stream (`audits.py:122`)
- **CSV export loads all brands into memory** (`admin.py`)

### Frontend
- **No code splitting** — all routes in initial bundle
- **No `next/image`** optimization extensively
- **Google Fonts via CSS import** — render-blocking
- **No service worker / PWA**
- **TanStack Query** 30s stale time — reasonable

### Database
- **30 indexes** including 3 composite — good coverage
- **Missing indexes:** `campaigns.status`, `content_items.policy_status`, `connections.status`, `audit_events.action`, `audit_jobs.status`
- **Partitioned `metric_events`** by month — excellent for time-series
- **No `pool_recycle`** — long-running connections may stale

### Missing Performance Features
- No CDN configuration
- No gzip/brotli compression config
- No query result caching
- No Redis caching for hot paths
- No connection pooling for Redis (new connection per operation in some places)

---

## 7. AI Architecture Score: 7.0/10

**Files:** `packages/shared/prachar_shared/ai_gateway/`

### What's Done Well
- **3-provider fallback chain** (Groq → Anthropic → OpenAI) with feedback loop
- **Model tiering** (small/large) via `Tier` enum
- **Redis caching** with SHA256 keys, 7-day TTL for generation tasks
- **Monthly budget tracking** per tenant with plan-based caps (Starter: 100, Growth: 1K, Agency: 100K tokens)
- **JSON schema enforcement** via Pydantic dynamic model creation
- **Claims gate** — blocks "guaranteed #1", "guaranteed results", medical claims
- **Per-channel policy gates** — YouTube title limits, IG hashtag limits, Reddit always-needs-approval

### Critical Gaps
| # | Issue | Impact |
|---|-------|--------|
| 1 | **No prompt injection protection** | User input → LLM directly, no sanitization |
| 2 | **No streaming support** | All calls blocking, poor UX for long responses |
| 3 | **No context window management** | No token counting, no truncation, relies on provider |
| 4 | **No prompt versioning** | Prompts are hardcoded constants, changes require deploy |
| 5 | **No cost calculation** | Budget is token-count, not monetary. No pricing tables. |
| 6 | **No exponential backoff** at gateway | Only provider-level fallback, no backoff within provider |
| 7 | **No dead letter queue** for failed tasks | Tasks retry then fail silently |
| 8 | **No automatic OAuth token refresh** | Tokens expire, require manual re-auth |
| 9 | **No hallucination protection** | No fact-checking, no citation verification on output |
| 10 | **No per-tenant rate limiting** | One tenant can exhaust AI budget |

### Workers Assessment
- **Celery config:** `task_acks_late=True`, `task_reject_on_worker_lost=True`, `worker_prefetch_multiplier=1` — good
- **6 queues:** prachar, ingest, organic, ads, measure, creative — well-organized
- **Beat schedule:** 60s loop dispatch — correct
- **Retry policy:** All tasks `autoretry_for=(Exception,)`, `retry_backoff=True`, max_retries=2-3
- **Idempotency:** Only for ads money mutations (Redis NX, 24h TTL). Not extended to other tasks.
- **Allocator:** Softmax with ±20% clamp, max_cpa guardrail — mathematically sound

### Adapters Assessment
- **16 organic adapters** + **10 ads adapters** — comprehensive coverage
- **Clean base classes** — `ChannelAdapter` (7 abstract methods), `AdNetworkAdapter` (7 abstract methods)
- **AES-GCM encrypted token storage** — excellent
- **Reactive 429 retry** with exponential backoff — adequate but not proactive
- **Stub mode** — graceful degradation when API keys missing (good for dev, risky for prod)

---

## 8. Infrastructure Score: 4.5/10

### What Exists
- **Docker Compose** with Postgres 16, Redis, MinIO, API, Web, Worker, Beat
- **CI/CD** (GitHub Actions) — tests, lint, typecheck, Postgres+Redis services
- **4 Dockerfiles** (API, Web, Workers, AI-Gen)
- **Health endpoint** `/health` (basic)
- **AI-Gen deployment docs** (Modal.com)

### Critical Gaps
| # | Issue | Impact |
|---|-------|--------|
| 1 | **No Terraform** — `infra/` directory empty | No IaC, manual AWS setup |
| 2 | **No monitoring/observability** | No metrics, tracing, APM |
| 3 | **No structured logging** | Plain text, no JSON, no aggregation |
| 4 | **No backup strategy** | No automated backups, no DR plan |
| 5 | **No health checks** on app services in compose | Cannot detect failures |
| 6 | **No resource limits** in compose | Unbounded CPU/memory |
| 7 | **No restart policies** in compose | Services don't auto-recover |
| 8 | **No security scanning** in CI | No SAST, SCA, container scanning |
| 9 | **No blue/green deployment** | Downtime on deploy |
| 10 | **No Sentry/error tracking** | Errors not captured centrally |

### Docker Issues
- **API & Workers Dockerfiles run as root** — security risk
- **No `.dockerignore`** — large build contexts
- **No container scanning** — unknown vulnerabilities
- **Web Dockerfile is excellent** — multi-stage, non-root `nextjs` user

### CI/CD Issues
- **Hardcoded test secrets** in workflow file (should use GitHub Actions secrets)
- **No SAST** (CodeQL, Bandit)
- **No SCA** (pip-audit, npm audit)
- **No container image building/scanning**
- **No deployment step** — CI only tests

---

## 9. Launch Readiness Score: 5.5/10

### Beta Launch Ready ✅
- [x] Core user flows work (register → login → create brand → audit → generate content)
- [x] 154 tests passing
- [x] Premium frontend UX
- [x] Multi-tenant isolation (RLS)
- [x] AI generation (video, image, text) working end-to-end
- [x] 16 organic + 10 ads adapters implemented
- [x] Weekly autonomous loop orchestration

### Production Launch NOT Ready ❌
- [ ] **Rate limiting** — critical for public endpoints
- [ ] **httpOnly cookie auth** — critical security
- [ ] **Pagination** — will fail with real data
- [ ] **Observability** — cannot debug production issues
- [ ] **Backups** — no data recovery
- [ ] **Terraform** — no reproducible infra
- [ ] **Health checks** — cannot detect failures
- [ ] **Error tracking** — no Sentry
- [ ] **Secrets management** — weak defaults
- [ ] **CSRF protection** — missing

### Verdict
**Beta launch (invite-only, monitored):** Ready with rate limiting + httpOnly cookies as prerequisites.
**Public production launch:** 2–3 weeks of hardening required.

---

## 10. Critical Issues

### C1: Password Stored in localStorage
- **Problem:** `login/page.tsx:31` stores user password in localStorage for "silent re-login"
- **Impact:** XSS attack = full password compromise for every user
- **Recommendation:** Remove password storage. Implement httpOnly Secure SameSite cookies + refresh token rotation.
- **Complexity:** Medium (2-3 days)
- **Priority:** P0 — Block all launches
- **Files:** `apps/web/src/app/login/page.tsx`, `apps/web/src/lib/auth.ts`

### C2: JWT Tokens in localStorage
- **Problem:** Auth tokens stored in `window.localStorage`, accessible to XSS
- **Impact:** Token theft, account takeover
- **Recommendation:** Migrate to httpOnly cookies. Backend sets cookies on login/refresh.
- **Complexity:** Medium (2-3 days)
- **Priority:** P0
- **Files:** `apps/web/src/lib/auth.ts`, `apps/api/prachar_api/routers/auth.py`

### C3: No Rate Limiting
- **Problem:** No rate limiting on any endpoint, including `/auth/login`, `/auth/register`, `/brands/audit` (free, no auth)
- **Impact:** Brute force attacks, abuse, cost attacks on AI endpoints
- **Recommendation:** Add `slowapi` with Redis backend. Auth: 5/min. Audit: 10/min. Video gen: 5/hour per user.
- **Complexity:** Low (1 day)
- **Priority:** P0
- **Files:** `apps/api/prachar_api/main.py`, `apps/api/prachar_api/deps.py`, all routers

### C4: Weak Default Secrets
- **Problem:** `JWT_SECRET=change-me-jwt` in `.env.example` and `config.py` defaults
- **Impact:** If defaults used in prod, anyone can forge JWTs
- **Recommendation:** Remove defaults. Startup validation: fail if secrets are placeholder values.
- **Complexity:** Low (2 hours)
- **Priority:** P0
- **Files:** `.env.example`, `packages/shared/prachar_shared/config.py`

### C5: Missing Foreign Keys in Migration
- **Problem:** Migration `0001_initial.py` doesn't create FKs for `tenant_id` columns on 9 tables, and `metric_events.brand_id` has no FK. Models define them but DB doesn't enforce.
- **Impact:** Orphaned records, data integrity violations
- **Recommendation:** New migration to add all missing FK constraints.
- **Complexity:** Low (4 hours)
- **Priority:** P0
- **Files:** `apps/api/alembic/versions/0001_initial.py`, new migration file

### C6: No CSRF Protection
- **Problem:** No CSRF middleware or token validation
- **Impact:** CSRF attacks on state-changing operations
- **Recommendation:** Implement CSRF tokens (double-submit cookie pattern).
- **Complexity:** Medium (1-2 days)
- **Priority:** P0 (if using cookies) / P1 (if keeping localStorage)
- **Files:** `apps/api/prachar_api/main.py`, new middleware

### C7: In-Memory State in Critical Paths
- **Problem:** API tokens (`admin.py:120`), attribution touchpoints (`attribution.py:49`), white-label config — all in-memory dicts, lost on restart
- **Impact:** Data loss, broken features after deploy
- **Recommendation:** Persist to database tables.
- **Complexity:** Medium (2-3 days)
- **Priority:** P0
- **Files:** `apps/api/prachar_api/routers/admin.py`, `apps/api/prachar_api/routers/attribution.py`

### C8: Docker Containers Run as Root
- **Problem:** API and Workers Dockerfiles have no non-root user
- **Impact:** Container escape = host compromise
- **Recommendation:** Add `USER app` directive, create non-root user.
- **Complexity:** Low (2 hours)
- **Priority:** P0
- **Files:** `apps/api/Dockerfile`, `apps/workers/Dockerfile`

---

## 11. High Priority Issues

### H1: No Pagination on List Endpoints
- **Problem:** All list endpoints (`/brands`, `/campaigns`, `/connections`, `/reports`) return all records
- **Impact:** OOM crashes with production data volumes, slow responses
- **Recommendation:** Cursor-based pagination, default page_size=50, max=100, total count in headers
- **Complexity:** Medium (2-3 days)
- **Priority:** P1
- **Files:** `brands.py`, `campaigns.py`, `connections.py`, `reports.py`, `admin.py`

### H2: Access Token TTL Too Long (24h)
- **Problem:** `JWT_TTL_MIN=1440` (24 hours) for access tokens
- **Impact:** Stolen tokens valid for 24h, no rotation
- **Recommendation:** Reduce to 15-60 minutes. Implement refresh token rotation.
- **Complexity:** Low (4 hours)
- **Priority:** P1
- **Files:** `packages/shared/prachar_shared/config.py`, `apps/api/prachar_api/security.py`

### H3: No Global Exception Handler
- **Problem:** No `@app.exception_handler(Exception)` registered
- **Impact:** Unhandled errors leak stack traces, inconsistent error responses
- **Recommendation:** Add global handler with structured error response, log to Sentry.
- **Complexity:** Low (4 hours)
- **Priority:** P1
- **Files:** `apps/api/prachar_api/main.py`

### H4: No Observability
- **Problem:** No metrics, tracing, structured logging, or error tracking
- **Impact:** Cannot debug production issues, no performance insights
- **Recommendation:** Add OpenTelemetry + Prometheus + Sentry + structlog
- **Complexity:** Medium (3-5 days)
- **Priority:** P1
- **Files:** `apps/api/prachar_api/main.py`, new middleware

### H5: No Prompt Injection Protection
- **Problem:** User input passed directly to LLMs, no sanitization
- **Impact:** Prompt injection attacks, data exfiltration, malicious content generation
- **Recommendation:** Add input sanitization layer, output validation, prompt boundaries
- **Complexity:** Medium (2-3 days)
- **Priority:** P1
- **Files:** `packages/shared/prachar_shared/ai_gateway/client.py`

### H6: No Automatic OAuth Token Refresh
- **Problem:** OAuth tokens stored encrypted but never refreshed
- **Impact:** Connections break when tokens expire, manual re-auth required
- **Recommendation:** Background worker to refresh expiring tokens
- **Complexity:** Medium (2-3 days)
- **Priority:** P1
- **Files:** `apps/workers/prachar_workers/`, adapter files

### H7: No Backup Strategy
- **Problem:** No automated backups, no DR plan
- **Impact:** Data loss is irreversible
- **Recommendation:** Automated pg_dump + WAL archiving, S3 cross-region replication, tested restore
- **Complexity:** Medium (2-3 days)
- **Priority:** P1
- **Files:** New infra scripts, documentation

---

## 12. Medium Priority Issues

### M1: No Error Boundary in Frontend
- **Problem:** No React error boundary component
- **Impact:** Unhandled errors crash entire app
- **Recommendation:** Add `app/error.tsx` error boundary
- **Complexity:** Low (2 hours)
- **Priority:** P2
- **Files:** `apps/web/src/app/error.tsx` (new)

### M2: Missing Database Indexes
- **Problem:** No indexes on `campaigns.status`, `content_items.policy_status`, `connections.status`, `audit_events.action`, `audit_jobs.status`
- **Impact:** Slow queries as data grows
- **Recommendation:** Add indexes in new migration
- **Complexity:** Low (2 hours)
- **Priority:** P2
- **Files:** New migration file

### M3: No Form Validation Library
- **Problem:** Forms use manual useState validation
- **Impact:** Inconsistent validation, poor UX, missed edge cases
- **Recommendation:** Add React Hook Form + Zod
- **Complexity:** Medium (2-3 days)
- **Priority:** P2
- **Files:** All form pages in `apps/web/src/app/`

### M4: Hardcoded Partition Dates
- **Problem:** `metric_events` partition hardcoded to `2026-07`
- **Impact:** Inserts fail after July 2026
- **Recommendation:** Cron job or `pg_partman` extension for auto-partitioning
- **Complexity:** Low (4 hours)
- **Priority:** P2
- **Files:** `apps/api/alembic/versions/0001_initial.py`, new cron/migration

### M5: No Streaming Support in AI Gateway
- **Problem:** All LLM calls blocking
- **Impact:** Poor UX for long responses, timeout risks
- **Recommendation:** Add streaming via SSE
- **Complexity:** Medium (3-5 days)
- **Priority:** P2
- **Files:** `packages/shared/prachar_shared/ai_gateway/client.py`

### M6: No Prompt Versioning
- **Problem:** Prompts are hardcoded Python constants
- **Impact:** Changes require deploy, no A/B testing, no rollback
- **Recommendation:** DB-backed prompt store with version numbers
- **Complexity:** Medium (3-5 days)
- **Priority:** P2
- **Files:** New table, `packages/shared/prachar_shared/adapters/organic/prompts.py`

### M7: CORS Hardcoded
- **Problem:** Origins hardcoded in `main.py`, no production domains
- **Impact:** Won't work in production
- **Recommendation:** Move to env config
- **Complexity:** Low (1 hour)
- **Priority:** P2
- **Files:** `apps/api/prachar_api/main.py`, `config.py`

### M8: No Accessibility (WCAG)
- **Problem:** Only 6 ARIA attributes, no keyboard nav, no skip link
- **Impact:** WCAG non-compliance, legal risk, excludes users
- **Recommendation:** Add ARIA labels, keyboard handlers, skip-to-content, screen reader testing
- **Complexity:** Medium (3-5 days)
- **Priority:** P2
- **Files:** All frontend components

---

## 13. Low Priority Issues

### L1: No `updated_at` Timestamps
- **Problem:** Only `created_at`, no `updated_at`
- **Impact:** Cannot track when records were last modified
- **Complexity:** Low (2 hours)

### L2: No Soft Deletes
- **Problem:** All deletions permanent
- **Impact:** No recovery from accidental deletes
- **Complexity:** Medium (2-3 days)

### L3: No SEO Metadata
- **Problem:** No OpenGraph, Twitter cards, sitemap, structured data
- **Impact:** Poor search engine visibility
- **Complexity:** Low (1 day)

### L4: No Light Mode Toggle
- **Problem:** Dark mode only, hardcoded
- **Impact:** User preference not respected
- **Complexity:** Medium (2-3 days)

### L5: No PWA Support
- **Problem:** No service worker, no manifest
- **Impact:** No offline support, no installable app
- **Complexity:** Medium (2-3 days)

### L6: No Code Splitting
- **Problem:** All routes in initial bundle
- **Impact:** Large initial JS payload
- **Complexity:** Low (1 day)

---

## 14. Technical Debt

| Area | Debt Item | Effort to Clear |
|------|-----------|-----------------|
| **Stub implementations** | OAuth callbacks, S3 uploads, visibility score | 1 week |
| **In-memory state** | API tokens, attribution, white-label | 3 days |
| **Missing service layer** | Routers contain business logic | 1 week |
| **Hardcoded prompts** | No versioning, no A/B testing | 1 week |
| **No Terraform** | Manual AWS setup | 1 week |
| **No observability** | Flying blind in production | 1 week |
| **Missing FKs** | Data integrity risk | 4 hours |
| **Missing indexes** | Performance degradation | 4 hours |
| **No pagination** | Will fail at scale | 3 days |
| **No rate limiting** | Security risk | 1 day |
| **Stub mode in prod** | Adapters return fake data when no creds | 3 days |
| **Single migration** | No incremental schema evolution | Ongoing |

**Estimated total debt:** ~6 weeks of focused work to reach enterprise-grade.

---

## 15. Quick Wins (1-2 Days Each)

1. **Remove password from localStorage** — 1 line deletion, immediate security win
2. **Add rate limiting** — `slowapi` integration, 1 day
3. **Fix weak default secrets** — Remove defaults, add validation, 2 hours
4. **Add non-root user to Dockerfiles** — 2 hours
5. **Reduce access token TTL to 15 min** — 1 config change
6. **Add global exception handler** — 4 hours
7. **Add missing FKs migration** — 4 hours
8. **Add missing indexes migration** — 2 hours
9. **Move CORS to env config** — 1 hour
10. **Add error boundary to frontend** — 2 hours
11. **Add 404/500 pages** — 2 hours
12. **Add request ID middleware** — 4 hours

**Total quick wins:** ~5 days for massive security and reliability improvement.

---

## 16. Recommended Sprint Order

### Sprint H1: Security Hardening (Week 1) — P0
1. Remove password from localStorage
2. Migrate to httpOnly cookies
3. Implement rate limiting (slowapi)
4. Fix weak default secrets
5. Add CSRF protection
6. Add non-root user to Dockerfiles
7. Reduce access token TTL to 15 min
8. Implement refresh token rotation

### Sprint H2: Data Integrity & Reliability (Week 2) — P0/P1
1. Add missing FKs migration
2. Add missing indexes migration
3. Fix hardcoded partition dates
4. Implement pagination on all list endpoints
5. Persist in-memory state to DB (API tokens, attribution, white-label)
6. Add global exception handler
7. Add request ID middleware
8. Add health checks for DB/Redis

### Sprint H3: Observability & Ops (Week 3) — P1
1. Add structured logging (structlog)
2. Add Sentry error tracking
3. Add OpenTelemetry tracing
4. Add Prometheus metrics
5. Implement backup strategy
6. Add health checks to docker-compose
7. Add restart policies to docker-compose
8. Add security scanning to CI (SAST, SCA)

### Sprint H4: AI & Frontend Polish (Week 4) — P1/P2
1. Add prompt injection protection
2. Implement automatic OAuth token refresh
3. Add error boundary + 404/500 pages
4. Add React Hook Form + Zod validation
5. Add ARIA labels and keyboard navigation
6. Add SEO metadata
7. Add code splitting
8. Add streaming support for AI responses

### Sprint H5: Infrastructure (Week 5-6) — P1
1. Implement Terraform (ECS, RDS, ElastiCache, S3, CloudFront)
2. Set up blue/green deployment
3. Add CDN configuration
4. Implement secrets management (AWS SSM)
5. Document deployment process
6. Add disaster recovery plan

---

## 17. Production Readiness Checklist

### Security
- [ ] No passwords in localStorage
- [ ] httpOnly Secure SameSite cookies
- [ ] Rate limiting on auth endpoints
- [ ] Rate limiting on free endpoints
- [ ] Rate limiting on expensive AI endpoints
- [ ] CSRF protection
- [ ] No weak default secrets
- [ ] Refresh token rotation
- [ ] Token revocation/blacklist
- [ ] Non-root Docker containers
- [ ] Security scanning in CI
- [ ] Dependency vulnerability scanning

### Data Integrity
- [ ] All FKs defined in migration
- [ ] Check constraints on critical columns
- [ ] Automatic partition management
- [ ] Soft deletes on critical entities
- [ ] `updated_at` on mutable tables

### Performance
- [ ] Pagination on all list endpoints
- [ ] Missing indexes added
- [ ] N+1 query detection in tests
- [ ] Query result caching for hot paths
- [ ] CDN configured
- [ ] Code splitting in frontend
- [ ] Image optimization (next/image)

### Reliability
- [ ] Global exception handler
- [ ] Structured logging
- [ ] Request ID correlation
- [ ] Health checks (DB, Redis, S3)
- [ ] Sentry error tracking
- [ ] Dead letter queue for failed tasks
- [ ] Automatic OAuth token refresh
- [ ] Backup strategy with tested restores
- [ ] Restart policies in docker-compose
- [ ] Resource limits in docker-compose

### Observability
- [ ] Prometheus metrics
- [ ] OpenTelemetry tracing
- [ ] Structured JSON logs
- [ ] Log aggregation (ELK/CloudWatch)
- [ ] APM integration
- [ ] Alerting on critical errors

### Infrastructure
- [ ] Terraform for all AWS resources
- [ ] Blue/green deployment
- [ ] Automated rollback
- [ ] Secrets management (SSM/Secrets Manager)
- [ ] Container image scanning
- [ ] Documentation for deployment

### AI Safety
- [ ] Prompt injection protection
- [ ] Output validation/filtering
- [ ] Hallucination detection
- [ ] Cost tracking (monetary, not just tokens)
- [ ] Per-tenant rate limits
- [ ] Prompt versioning

### Frontend
- [ ] Error boundary
- [ ] 404/500 error pages
- [ ] Form validation library
- [ ] ARIA labels
- [ ] Keyboard navigation
- [ ] Skip-to-content link
- [ ] SEO metadata
- [ ] Code splitting

---

## 18. Future Scalability Recommendations

### Near-term (0-3 months)
1. **Read replicas** — Offload analytics queries to Postgres read replicas
2. **Connection pooling** — Use PgBouncer for connection multiplexing
3. **Redis cluster** — Single Redis will bottleneck; cluster for cache + queues
4. **CDN for static assets** — CloudFront in front of S3 and Next.js
5. **Async video generation** — Move from sync polling to job queue with webhooks

### Mid-term (3-6 months)
6. **Microservices extraction** — Split AI gateway, workers, and adapters into separate services
7. **Event sourcing** — Move audit events to event store (Kafka) for replay/analytics
8. **Multi-region deployment** — Active-active for global brands
9. **GraphQL federation** — For complex frontend queries across services
10. **Feature flag service** — Move from env vars to LaunchDarkly/Unleash

### Long-term (6-12 months)
11. **Custom model fine-tuning** — Fine-tune small models for ad copy generation
12. **Real-time analytics** — ClickHouse for sub-second metric queries
13. **Edge deployment** — Cloudflare Workers for pixel/attribution endpoints
14. **SOC 2 compliance** — Audit trail, access controls, encryption at rest
15. **Multi-cloud** — AWS + GCP for vendor diversity

---

## 19. Enterprise Readiness

| Criterion | Status | Notes |
|-----------|--------|-------|
| **SOC 2 Type II** | ❌ Not ready | Needs audit trail (have it), access controls, encryption, monitoring |
| **GDPR** | ⚠️ Partial | RLS isolates tenants, but no data export/deletion endpoints |
| **HIPAA** | ❌ Not ready | No BAA, no PHI handling, no audit at required granularity |
| **PCI DSS** | ❌ Not ready | No payment handling in-house (uses Stripe/Razorpay) |
| **ISO 27001** | ❌ Not ready | Needs ISMS, risk assessment, documented policies |
| **Multi-tenant isolation** | ✅ Excellent | RLS with FORCE, defense-in-depth |
| **Audit trail** | ✅ Excellent | Immutable audit_events, all mutations logged |
| **Encryption at rest** | ✅ Good | OAuth tokens AES-GCM encrypted, DB encryption via RDS |
| **Encryption in transit** | ⚠️ Partial | HTTPS assumed but not enforced in code |
| **Access control** | ⚠️ Partial | JWT + roles, but no fine-grained permissions |
| **Data residency** | ❌ Not implemented | No region pinning for international brands |
| **SLA monitoring** | ❌ Not implemented | No uptime tracking, no SLO/SLI definitions |
| **Disaster recovery** | ❌ Not implemented | No backups, no DR plan, no RTO/RPO defined |
| **Compliance reporting** | ❌ Not implemented | No compliance dashboard, no audit export |

### Enterprise Readiness Score: 3/10
The platform has excellent foundations (RLS, audit logging, encryption) but lacks the operational maturity, compliance certifications, and disaster recovery capabilities required for enterprise sales.

---

## 20. Overall CTO Recommendation

### Verdict: **Conditional Go for Beta, No-Go for Production**

PRACHAR is an **architecturally impressive** product that has executed 9 sprints with remarkable breadth (16 channels, 10 ad networks, 14 locales) and exceptional frontend craft. The team has demonstrably shipped working software — 154 tests pass, video generation works end-to-end, the weekly loop orchestrates correctly.

However, the codebase has **critical security vulnerabilities** (password in localStorage, no rate limiting, weak defaults), **operational gaps** (no observability, no backups, no Terraform), and **scalability ceilings** (no pagination, in-memory state) that make it **unsafe for public production launch**.

### My Recommendation

1. **Do NOT launch publicly today.** The security vulnerabilities are exploitable within minutes by any attacker.

2. **Execute Sprint H1 (Security Hardening) immediately.** This is 1 week of work that closes all P0 issues. After H1, the product is safe for **invite-only beta** with monitored users.

3. **Execute Sprints H2-H3 (Data Integrity + Observability) before public launch.** This is 2 more weeks. After H3, the product is **production-ready for public launch**.

4. **Execute Sprints H4-H5 (AI Safety + Infrastructure) before enterprise sales.** This is 3 more weeks. After H5, the product is **enterprise-ready** for pilot customers.

5. **Begin SOC 2 preparation in parallel with H4-H5.** The audit trail and RLS foundations are excellent; the gaps are in monitoring, documentation, and policy.

### Total Time to Production-Ready: 3 weeks
### Total Time to Enterprise-Ready: 6 weeks

### Final Word

The architecture is sound. The craft is evident. The team can clearly build. What's missing is the **operational hardening** that separates a demo from a product. Close the P0 issues this week, and you have a defensible, premium AI advertising platform ready for beta users.

---

**Audit Complete.**
**Report saved to:** `/Users/appple/projects/prachar/CTO_AUDIT.md`
