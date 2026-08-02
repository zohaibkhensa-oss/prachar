# PRACHAR AI — Launch 1.0 Program

**Architecture:** FROZEN (v1). See ADR-0007.
**Mode:** Release engineering. No new core abstractions.
**Goal:** Move from "architecture complete" to "public launch ready."

## Launch Readiness Assessment

| Area | Status |
|------|--------|
| Core architecture | ✅ Complete |
| Backend platform | ✅ Complete |
| Frontend product | ✅ Complete |
| AI runtime | ✅ Complete |
| Knowledge system | ✅ Complete |
| Integrations framework | ✅ Complete |
| Governance (ADRs, freeze, CI guards) | ✅ Complete |
| Testing (763 backend, 0 TS errors) | ✅ Strong |
| Production infrastructure | 🟡 Remaining |
| Security hardening | 🟡 Remaining |
| Load testing | 🟡 Remaining |
| Operations tooling | 🟡 Remaining |
| Documentation | 🟡 Remaining |
| Beta validation | 🔴 Not started |

---

## Phase A — Production Infrastructure ✅ IMPLEMENTED

### A1. AWS Infrastructure (Terraform) ✅
- [ ] VPC + subnets (public/private)
- [ ] ECS Fargate cluster (API + workers)
- [ ] RDS PostgreSQL 16 (multi-AZ, automated backups)
- [ ] ElastiCache Redis (HA)
- [ ] S3 bucket (object storage)
- [ ] CloudFront distribution (CDN for frontend)
- [ ] Route53 (DNS)
- [ ] WAF (web application firewall)
- [ ] SSL/TLS certificates (ACM)
- [ ] Secrets Manager (OAuth keys, JWT secrets)
- [ ] NAT gateway
- [ ] Load balancer (ALB)

### A2. Observability
- [ ] OpenTelemetry instrumentation (traces)
- [ ] Prometheus (metrics scraping)
- [ ] Grafana (dashboards)
- [ ] Loki (log aggregation)
- [ ] Sentry (error tracking, frontend + backend)
- [ ] CloudWatch (AWS infrastructure metrics)
- [ ] PagerDuty (alerting + on-call)
- [ ] Health check dashboard (extend existing `/health/ready`)

### A3. Security
- [ ] Penetration testing (external firm)
- [ ] Dependency scanning (Dependabot / Snyk)
- [ ] Secret scanning (git-secrets / TruffleHog)
- [ ] SBOM generation (CycloneDX)
- [ ] OWASP Top 10 review
- [ ] CSP (Content Security Policy) headers
- [ ] Audit logging review (verify every mutation writes AuditEvent)
- [ ] Encryption review (at rest + in transit)
- [ ] API rate limiting (slowapi or nginx)
- [ ] JWT rotation policy
- [ ] RLS policy audit (every tenant table)

### A4. CI/CD
- [ ] Staging environment (auto-deploy from main)
- [ ] Production deployment pipeline (manual gate)
- [ ] Database migration rollback procedure
- [ ] Blue/green or canary deployments
- [ ] Feature flag system (LaunchDarkly or self-hosted)

---

## Phase B — Scale Testing ✅ SCRIPTS READY

### B1. Load Targets

| Subsystem | Target | Method |
|-----------|--------|--------|
| Orb (concurrent chats) | 500 | k6 or Locust |
| Campaign Brain (concurrent generations) | 200 | k6 |
| Knowledge Hub (chunks) | 1M | seed + query |
| Context Builder (latency) | <100ms | p99 measurement |
| Runtime (response time) | <2s avg | p50/p99 |
| Database (TPS) | 500 | pgbench |
| Frontend (LCP) | <2.5s | Lighthouse |

### B2. Chaos Testing
- [ ] Kill API pod mid-request → graceful degradation
- [ ] Kill Redis → inline fallback works
- [ ] Kill worker mid-loop → task retried
- [ ] Database failover → app recovers
- [ ] AI provider down → fallback provider works
- [ ] AI provider rate-limited → queue + retry works

### B3. Capacity Planning
- [ ] Document resource limits per ECS task
- [ ] Document auto-scaling thresholds
- [ ] Document database connection pool sizing
- [ ] Document Redis memory budget
- [ ] Document S3 storage growth estimate

---

## Phase C — Provider Expansion

Adapters only. No architecture work. Each follows ADR-0005.

### C1. Marketing / Email
- [ ] Brevo
- [ ] Klaviyo
- [ ] ActiveCampaign

### C2. CRM
- [ ] Salesforce
- [ ] Zoho

### C3. Commerce
- [ ] WooCommerce
- [ ] Magento

### C4. Ads
- [ ] TikTok Ads (expand existing organic adapter)
- [ ] Snapchat Ads (expand existing)
- [ ] LinkedIn Ads (expand existing)

### C5. Social
- [ ] Instagram Graph (expand existing)
- [ ] Threads
- [ ] Pinterest (expand existing)

### C6. Each adapter delivers
- [ ] OAuth flow
- [ ] Connection persistence
- [ ] Sync policy
- [ ] Health check
- [ ] Context provider update (if new data source)
- [ ] Tool registry entry (if new action)
- [ ] Tests
- [ ] Frontend integration card

---

## Phase D — Mobile

Reuse everything. Flutter consumes the same APIs.

### D1. Flutter App
- [ ] Auth flow (JWT)
- [ ] Orb chat interface
- [ ] Dashboard (real API data)
- [ ] Campaign creation
- [ ] Review queue
- [ ] Push notifications
- [ ] Offline state handling

### D2. No new backend work
- Same Runtime
- Same Tool Registry
- Same Context Builder
- Same APIs
- Same RLS
- Same billing

---

## Phase E — Billing ✅ PRODUCTION READY

### E1. Subscription Management ✅ (existing)
- [ ] Stripe + Razorpay production keys
- [ ] Plan tiers (Starter / Growth / Agency)
- [ ] Trial period (14 days)
- [ ] Upgrade / downgrade flow
- [ ] Proration
- [ ] Cancellation

### E2. Invoicing
- [ ] GST compliance (India)
- [ ] Invoice generation
- [ ] Invoice PDF delivery
- [ ] Invoice history

### E3. Usage Billing
- [ ] AI token metering
- [ ] Overage charges
- [ ] Hard cap enforcement (existing)
- [ ] Usage dashboard

### E4. Growth
- [ ] Coupons
- [ ] Referral program
- [ ] Affiliate tracking

---

## Phase F — Internal Operations ✅ OPS ENDPOINTS READY

### F1. Admin Dashboard ✅ (existing + new ops endpoints)
- [ ] Customer management (list, search, impersonate)
- [ ] Tenant overview (brands, campaigns, spend)
- [ ] AI cost dashboard (per-tenant token usage)
- [ ] Integration health monitor
- [ ] Error rate monitor
- [ ] Feature flag controls

### F2. Support Tools
- [ ] Support portal (ticketing)
- [ ] Customer impersonation (audit-logged)
- [ ] Campaign debugging view
- [ ] Timeline viewer (per-tenant)
- [ ] Force-trigger workflow

### F3. Operations
- [ ] Rollback procedure (documented + tested)
- [ ] Database backup restore (tested)
- [ ] Secret rotation procedure
- [ ] Incident response runbook
- [ ] Status page (public)

---

## Phase G — Documentation ✅ READY

### G1. Developer Docs ✅
- [ ] Architecture overview (reference ADRs)
- [ ] Local development setup
- [ ] Adding a new tool (Extension Checklist)
- [ ] Adding a new context provider
- [ ] Adding a new integration adapter
- [ ] Adding a new domain pack
- [ ] Database migration guide
- [ ] Testing guide

### G2. API Reference
- [ ] OpenAPI/Swagger UI (auto-generated from FastAPI)
- [ ] Authentication guide
- [ ] Rate limits
- [ ] Webhooks
- [ ] Error codes

### G3. Customer Docs
- [ ] Getting started guide
- [ ] Onboarding walkthrough
- [ ] Campaign creation guide
- [ ] Review workflow guide
- [ ] Integration setup guides (per platform)
- [ ] Billing FAQ
- [ ] Knowledge Hub upload guide

### G4. Admin Docs
- [ ] Operations runbook
- [ ] Incident response
- [ ] Deployment guide
- [ ] Monitoring guide

---

## Phase H — Beta

### H1. Beta Stages

| Stage | Users | Duration | Gate to next |
|-------|-------|----------|--------------|
| Private beta | 25 companies | 2 weeks | No critical bugs |
| Closed beta | 100 companies | 4 weeks | NPS > 30 |
| Open beta | 500 companies | 4 weeks | NPS > 40, uptime > 99.5% |
| Public launch | unlimited | — | — |

### H2. Metrics to Collect

| Metric | Target | Tool |
|--------|--------|------|
| Crash rate | < 0.1% | Sentry |
| NPS | > 40 | In-app survey |
| Activation rate | > 60% | Analytics |
| 7-day retention | > 50% | Analytics |
| Campaign success rate | > 80% | DB query |
| AI acceptance rate | > 70% | Runtime metrics |
| Orb response satisfaction | > 75% | Thumbs up/down |
| Time to first campaign | < 10 min | Analytics |
| Time to first value | < 5 min | Analytics |

### H3. Feedback Loops
- [ ] In-app feedback widget
- [ ] NPS survey (after 7 days)
- [ ] Orb thumbs up/down
- [ ] Bug report flow
- [ ] Feature request board
- [ ] Weekly user interviews (private beta)

---

## Allowed Work (No ADR Required)

| Type | Examples | Rule |
|------|----------|------|
| Performance optimization | Query tuning, caching, indexing | No abstraction changes |
| Bug fixes | Any | Unlimited |
| New adapters | WooCommerce, Brevo, Salesforce | Follows ADR-0005 |
| New context providers | Any subsystem | Follows ADR-0003 |
| New tools | Any capability | Follows ADR-0002 |
| New domain packs | Industry-specific | Follows Domain Pack pattern |
| Additive migrations | New tables, new columns | OK |
| Frontend pages | New pages using existing APIs | OK |
| Tests | Any | Unlimited |

## Requires ADR + Approval

| Type | Criteria |
|------|----------|
| New core subsystem | Must satisfy v2 Admission Rule (ADR-0007) |
| Destructive schema change | Must have migration rollback plan |
| New top-level package | Must justify why it can't be a submodule |
| Replacing a frozen component | Must document why the current design is insufficient |

---

## Sprint Classification

Every future sprint is one of:

| Classification | Examples |
|----------------|----------|
| **Execution** | Features built on existing architecture (new tools, providers, adapters, pages) |
| **Production hardening** | Security, scalability, operations, monitoring |
| **Launch readiness** | UX polish, onboarding, documentation, QA |
| **Provider expansion** | New adapters and integrations |

No architecture sprints are scheduled.
