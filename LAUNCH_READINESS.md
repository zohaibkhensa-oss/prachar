# CURV AI — Launch Readiness Gate

**Architecture status:** FROZEN (v1) — declared 2026-08-02. No new foundational abstractions.
**Product completion:** ~90%. Remaining work is feature implementation, not architecture.
**Mode:** Release engineering. See `LAUNCH_PROGRAM.md` for the 8-phase launch plan (A-H).
**The question is no longer "what architecture remains?" but "what prevents launch?"**

---

## Definition of Done

A feature is launch-ready when ALL of these are true:

| Gate | Meaning |
|------|---------|
| **Backend** | Router + service layer implemented, RLS-protected, audited |
| **Frontend** | Page renders real API data, loading/empty/error states, no mock data |
| **Orb** | Context provider feeds data to the Orb; tool registered for actions |
| **Tests** | Unit + integration tests pass in CI |
| **Prod Ready** | Health checks, monitoring, rate limiting, error tracking |
| **Docs** | API endpoint documented, user-facing copy reviewed |

---

## Feature Matrix

### Tier 1 — Core Product (must be green to launch)

| Feature | Backend | Frontend | Orb | Tests | Prod | Docs |
|---------|:-------:|:--------:|:---:|:-----:|:----:|:----:|
| **Auth & Billing** | ✅ | ✅ | ✅ `billing.usage` | ✅ 18 tests | ✅ health/ready | ⚠️ |
| **Brands & Workspaces** | ✅ | ✅ | ✅ | ✅ 3 tests | ✅ RLS | ⚠️ |
| **Campaign Brain** | ✅ | ✅ | ✅ 5 tools | ✅ 16 tests | ⚠️ no rate limit | ⚠️ |
| **Agency Council** | ✅ | ✅ | ✅ 2 tools | ✅ 16 tests | ⚠️ | ⚠️ |
| **Conversational Onboarding** | ✅ | ✅ | ✅ `consult.understand` | ✅ 23 tests | ⚠️ | ⚠️ |
| **Creative Studio** | ✅ | ✅ | ✅ 2 tools + ctx | ✅ 12 tests | ⚠️ | ⚠️ |
| **Knowledge Hub (RAG)** | ✅ | ✅ | ✅ `knowledge.search` | ⚠️ 2 files | ⚠️ | ⚠️ |
| **Performance Engine** | ✅ | ✅ | ✅ 3 tools + ctx | ✅ 13 tests | ⚠️ | ⚠️ |
| **Review Workflow** | ✅ | ✅ | ✅ 2 tools | ✅ 50 tests | ✅ | ⚠️ |
| **Timeline** | ✅ | ✅ | ✅ `timeline.query` | ✅ 17 tests | ✅ immutable | ⚠️ |
| **Integrations** | ✅ | ✅ | ✅ `integrations.list` | ⚠️ | ⚠️ | ⚠️ |
| **Audit Engine** | ✅ | ✅ | ✅ 2 tools | ✅ 8 files | ⚠️ | ⚠️ |
| **Attribution** | ✅ | ✅ | ✅ `attribution.query` | ⚠️ 2 files | ⚠️ | ⚠️ |
| **Workflow Automation** | ✅ | ✅ | ✅ `workflow.query` | ✅ 29 tests | ⚠️ | ⚠️ |
| **Orb / Runtime** | ✅ | ✅ | ✅ 30 tools | ✅ 45 tests | ⚠️ | ⚠️ |

### Tier 2 — Secondary Pages

| Feature | Backend | Frontend | Orb | Tests | Prod | Docs |
|---------|:-------:|:--------:|:---:|:-----:|:----:|:----:|
| **Channels** | ✅ `/connections` | ✅ real API | ✅ | ⚠️ | ⚠️ | ❌ |
| **Reports** | ✅ `/reports` | ✅ real API | ✅ `reports` | ⚠️ | ⚠️ | ❌ |
| **Knowledge Page** | ✅ `/knowledge` | ✅ real API | ✅ | ⚠️ | ⚠️ | ❌ |
| **Settings** | ✅ `/auth/me` | ✅ real API | ✅ | ✅ | ✅ | ❌ |
| **Calendar** | ❌ no backend | ✅ empty state | ❌ | — | — | ❌ |
| **Reviews (customer)** | ❌ no backend | ✅ empty state | ❌ | — | — | ❌ |

### Tier 3 — Labs (experimental, clearly marked)

| Feature | Backend | Frontend | Orb | Tests | Prod | Docs |
|---------|:-------:|:--------:|:---:|:-----:|:----:|:----:|
| **AI Video** | ✅ `/api/video/generate` | ✅ wired | ✅ `video_gen.generate` | ⚠️ | ⚠️ | ❌ |
| **AI Images** | ✅ `/api/video/generate-image` | ✅ wired | ✅ `creative_studio.generate_image` | ⚠️ | ⚠️ | ❌ |
| **Creative AI** | ✅ `/creative-studio/generate` | ✅ wired | ✅ `creative_studio.generate` | ✅ | ⚠️ | ❌ |
| **Design AI** | ⚠️ `/chat` only | ✅ empty state | ❌ | — | — | ❌ |
| **Influencers** | ❌ | ✅ empty state | ❌ | — | — | ❌ |
| **Advocacy** | ❌ | ✅ empty state | ❌ | — | — | ❌ |
| **Marketplace** | ❌ | ✅ empty state | ❌ | — | — | ❌ |
| **Shop** | ❌ | ✅ empty state | ❌ | — | — | ❌ |
| **Bio** | ❌ | ✅ empty state | ❌ | — | — | ❌ |
| **Audience** | ❌ | ✅ empty state | ❌ | — | — | ❌ |
| **Listening** | ❌ | ✅ empty state | ❌ | — | — | ❌ |

---

## Architecture Inventory (FROZEN — do not redesign)

| Component | Status | Tests |
|-----------|--------|:-----:|
| AI Runtime (planner + composer + executor) | ✅ frozen | 45 |
| Tool Registry (30 tools) | ✅ frozen | 14 |
| Context Builder (16 providers, adaptive ranking) | ✅ frozen | 134 |
| Context Ranking (recency, relevance, decay) | ✅ frozen | 134 |
| Knowledge Hub (RAG, embeddings, chunking) | ✅ frozen | 2 |
| Business Memory (categories, persistence) | ✅ frozen | 35 |
| Agency Council (9 directors, consensus) | ✅ frozen | 16 |
| Marketing Intelligence (10 engines) | ✅ frozen | 16 |
| Workflow Engine (rules, tasks, event bus) | ✅ frozen | 29 |
| Event Bus + Timeline (immutable append-only) | ✅ frozen | 17 |
| Integration Framework (ChannelAdapter abstraction) | ✅ frozen | — |
| Attribution (position-based 40/20/40) | ✅ frozen | 2 |
| Audit Engine (crawler, scorer, findings) | ✅ frozen | 8 |
| Multi-Workspace (RLS, tenant middleware) | ✅ frozen | 3 |
| Runtime Telemetry (metrics, observability) | ✅ frozen | 21 |
| AI Gateway (provider abstraction, tiering, cache) | ✅ frozen | 77 |
| Prompt Versioning Registry | ✅ frozen | — |
| Prompt Injection Defense (22 patterns) | ✅ frozen | — |
| Secrets Vault | ✅ frozen | — |
| Sync Policies | ✅ frozen | — |

**Total: 756 tests passing. 13 Alembic migrations. 27 backend routers. 51 frontend pages.**

---

## Infrastructure Readiness

| Component | Status | Notes |
|-----------|--------|-------|
| PostgreSQL 16 + RLS | ✅ | 13 migrations, tenant isolation enforced |
| Redis | ✅ | Used for caching, idempotency, rate limiting |
| Docker Compose | ✅ | postgres, redis, pgbouncer |
| CI (GitHub Actions) | ✅ | ruff + alembic migrate + seed + pytest + tsc |
| Health checks | ✅ | `/health`, `/health/ready`, `/health/live` |
| Terraform → AWS | ❌ | Not yet implemented |
| ECS Fargate | ❌ | Not yet implemented |
| RDS HA | ❌ | Single instance locally |
| ElastiCache | ❌ | Local Redis only |
| S3 / Object Storage | ⚠️ | Local FS fallback, no S3 in CI |
| CloudFront CDN | ❌ | Not yet implemented |
| Monitoring (Datadog/Prometheus) | ❌ | Logging only, no metrics export |
| Alerting | ❌ | Not yet implemented |
| Backups | ❌ | Not yet implemented |
| Rate Limiting | ⚠️ | AI gateway has budget caps, no API rate limiting |
| Audit Logging | ✅ | AuditEvent on every mutation |
| Disaster Recovery | ❌ | Not yet implemented |

---

## Orb Awareness Coverage

The Orb has 12 context providers and 30 tools. Here's what it can perceive and act on:

| Subsystem | Context Provider | Tool | Can Answer Questions About It? |
|-----------|:----------------:|:----:|:------------------------------:|
| Capabilities | ✅ always-on | — | ✅ "What can you do?" |
| Knowledge Hub | ✅ always-on | `knowledge.search` | ✅ "What do you know about my brand?" |
| Marketing Intelligence | ✅ always-on | 5 campaign tools | ✅ "Generate a campaign" |
| Council Memory | ✅ triggered | 2 council tools | ✅ "What did the council decide?" |
| Integrations | ✅ triggered | `integrations.list` | ✅ "What channels are connected?" |
| Performance | ✅ triggered | 3 performance tools | ✅ "How are my campaigns doing?" |
| Reviews | ✅ triggered | 2 review tools | ✅ "What's pending approval?" |
| Domain Packs | ✅ triggered | `domain_pack.apply` | ✅ "Apply industry best practices" |
| Audit | ✅ triggered | `audit.run` | ✅ "What's my visibility score?" |
| Attribution | ✅ triggered | `attribution.query` | ✅ "Which channels drive conversions?" |
| Timeline | ✅ triggered | `timeline.query` | ✅ "What have you done recently?" |
| Workflow | ✅ triggered | `workflow.query` | ✅ "What automations are running?" |
| Billing | ✅ `billing` | `billing.usage` | ✅ "What plan am I on?" |
| Reports | ✅ `reports` | ❌ | ✅ "Show me my latest report" |
| Creative Studio | ✅ `creative_studio` | 2 tools | ✅ "Show me recent creatives" |
| Video Gen | ✅ `video_gen` | `video_gen.generate` | ✅ "Show me generated videos" |

**Coverage: 16/16 subsystems have context providers. The Orb is fully aware.**

---

## Priority Work Order

### Phase 1: Close Orb gaps — ✅ COMPLETE

All 4 missing context providers have been added:
- ✅ ReportsContextProvider — triggers on "report", "weekly summary", "results overview"
- ✅ BillingContextProvider — triggers on "billing", "plan", "subscription", "usage", "cost"
- ✅ CreativeStudioContextProvider — triggers on "creative", "ad copy", "headline", "variant"
- ✅ VideoGenContextProvider — triggers on "video", "reel", "image", "generate", "media"

**Orb coverage: 16/16 subsystems. The Orb is fully aware of every backend intelligence source.**

### Phases 2-4 → Replaced by Launch 1.0 Program

The remaining work has been reorganized into the **Launch 1.0 Program** (`LAUNCH_PROGRAM.md`), an 8-phase release engineering plan:

| Phase | Name | Status |
|-------|------|--------|
| A | Production Infrastructure (AWS, observability, security) | 🟡 Not started |
| B | Scale Testing (load targets, chaos, capacity) | 🟡 Not started |
| C | Provider Expansion (Brevo, Salesforce, WooCommerce, etc.) | 🟡 Not started |
| D | Mobile (Flutter, same APIs) | 🟡 Not started |
| E | Billing (Stripe, Razorpay, GST, usage metering) | 🟡 Not started |
| F | Internal Operations (admin, support, ops) | 🟡 Not started |
| G | Documentation (dev, API, customer, admin) | 🟡 Not started |
| H | Beta (25 → 100 → 500 → public) | 🔴 Not started |

**No architecture sprints are scheduled. Every sprint is classified as Execution, Production Hardening, Launch Readiness, or Provider Expansion.**

---

## Sign-off Criteria

**A feature may ship to production when:**

1. ✅ Backend router exists and is RLS-protected
2. ✅ Frontend page shows real data (no mock)
3. ✅ Orb can discover the feature via a context provider
4. ✅ Orb can act on the feature via a tool (if applicable)
5. ✅ Tests pass in CI
6. ✅ Health check covers the dependency
7. ✅ No `alert()`, no "coming soon" toasts, no fabricated data
8. ✅ AuditEvent written for every mutation

**The platform launches when all Tier 1 features are green across all columns.**

---

## Architecture KPIs

Platform health is measured by these metrics, not by new systems built:

| KPI | Target | Current | Status |
|-----|--------|---------|--------|
| Test pass rate | 100% | 779/779 | ✅ |
| Frontend pages using real APIs | 100% | 18/18 Tier 1-2 | ✅ |
| Mock data | 0 | 0 | ✅ |
| Orb awareness (context provider coverage) | 100% | 16/16 | ✅ |
| Context build latency | < 100ms | ~25ms avg | ✅ |
| API rate limiting | enforced | ✅ global + auth | ✅ |
| Security headers | enforced | ✅ HSTS+CSP+XFO | ✅ |
| Prometheus metrics | /metrics | ✅ endpoint | ✅ |
| API documentation | /docs + /redoc | ✅ 137 paths | ✅ |
| Terraform infrastructure | validated | ✅ 12 files | ✅ |
| CI/CD pipeline | deploy.yml | ✅ staging+prod | ✅ |
| Security scanning | security.yml | ✅ pip-audit+secrets | ✅ |
| Load test scripts | k6 | ✅ 3 scripts | ✅ |
| Developer docs | docs/dev/ | ✅ complete | ✅ |
| Billing (GST + coupons) | production | ✅ implemented | ✅ |
| Admin ops endpoints | 3 new | ✅ health+overview+tenants | ✅ |
| Runtime success rate | > 99% | — | ⚠️ needs prod measurement |
| Integration health | > 99% | — | ⚠️ needs prod measurement |
| Production uptime | 99.9% SLA | — | ❌ not deployed yet |
| Backups + DR | tested | — | ❌ not deployed yet |

---

## Architecture Decision Records

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-0001](docs/adr/0001-runtime-architecture.md) | Runtime Architecture | Accepted |
| [ADR-0002](docs/adr/0002-tool-registry.md) | Tool Registry Design | Accepted |
| [ADR-0003](docs/adr/0003-context-builder.md) | Context Builder & Ranking | Accepted |
| [ADR-0004](docs/adr/0004-knowledge-hub.md) | Knowledge Hub (RAG) | Accepted |
| [ADR-0005](docs/adr/0005-integration-framework.md) | Integration Framework | Accepted |
| [ADR-0006](docs/adr/0006-workflow-engine.md) | Workflow Engine & Event Bus | Accepted |
| [ADR-0007](docs/adr/0007-architecture-freeze.md) | Architecture Freeze (v1) | Accepted |

---

## CI Architecture Guards

`test_architecture_freeze.py` (7 tests) enforces the freeze in every CI run:
- No duplicate Runtime/Planner/Composer classes
- No duplicate ToolRegistry
- No duplicate ContextBuilder
- No duplicate EventBus
- No duplicate WorkflowEngine
- No shared→api imports (dependency inversion)
- No unapproved top-level packages
