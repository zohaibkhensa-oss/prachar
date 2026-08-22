# CURV AI — Full Backend Architecture & Frontend Integration Guide

> Complete reference for frontend v2 to integrate with the backend.
> 87 endpoints · 30+ database tables · 10 AI engines · 9 AI directors · 26 channel adapters

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js)                          │
│   v1 (port 3000)  ·  v2 (port 3002)  →  /api proxy → :8000         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ Bearer JWT
┌──────────────────────────────▼──────────────────────────────────────┐
│                     API (FastAPI · port 8000)                       │
│  21 routers · 87 endpoints · RLS multi-tenant · SSE streaming      │
├─────────────────────────────────────────────────────────────────────┤
│  AUTH     BRANDS   CAMPAIGNS   CAMPAIGN-BRAIN   CONSULT   CREATOR  │
│  CREATIVE-STUDIO  REVIEW  PERFORMANCE  PROACTIVE  CHAT  CONNECTIONS│
│  BILLING  AUDITS  REPORTS  AGENCY-COUNCIL  UNIFIED-CONSULT          │
│  VIDEO-GEN  ADMIN  ATTRIBUTION  MISC                               │
└────────┬────────────────┬──────────────────┬────────────────────────┘
         │                │                  │
┌────────▼──────┐ ┌──────▼───────┐ ┌────────▼─────────────────────────┐
│  PostgreSQL   │ │   Redis      │ │  Celery Workers (9 queues)       │
│  30+ tables   │ │  cache+DLQ   │ │  loop·ingest·organic·ads·measure │
│  RLS per-     │ │  progress    │ │  creative·dispatch·publish·shards│
│  tenant       │ │              │ │  Beat: dispatch·perf·proactive   │
└───────────────┘ └──────────────┘ └───────────────────────────────────┘
         │
┌────────▼────────────────────────────────────────────────────────────┐
│              packages/shared (prachar_shared)                       │
│                                                                     │
│  ┌─────────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ Marketing Intel │  │ Agency       │  │ AI Gateway            │  │
│  │ 10 engines      │  │ Council      │  │ Anthropic/OpenAI/Groq │  │
│  │ CampaignBrain   │  │ 9 Directors  │  │ tiering·cache·budget  │  │
│  │ ProactiveEngine │  │ Consensus    │  │ safety·observability  │  │
│  └─────────────────┘  └──────────────┘  └───────────────────────┘  │
│  ┌─────────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ Domain Packs    │  │ Creative     │  │ Adapters (26)         │  │
│  │ business        │  │ Studio       │  │ 16 organic channels   │  │
│  │ creator         │  │ 10 formats   │  │ 10 ad networks        │  │
│  │ restaurant      │  │              │  │                       │  │
│  │ clinic          │  │              │  │                       │  │
│  └─────────────────┘  └──────────────┘  └───────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Authentication & Multi-Tenancy

### Auth Flow
```
Register → POST /auth/register {email, password, tenant_name, plan?}
         → Returns {access_token, refresh_token, user}
         → Store: prachar_token, prachar_refresh_token, prachar_email

Login    → POST /auth/login {email, password}
         → Returns {access_token, refresh_token, user}

Refresh  → POST /auth/refresh {refresh_token}
         → Returns new {access_token, refresh_token, user}

Me       → GET /auth/me (with Bearer token)
         → Returns {id, email, role, tenant_id}
```

### Token Storage (localStorage keys)
| Key | Purpose |
|-----|---------|
| `prachar_token` | JWT access token (15 min TTL) |
| `prachar_refresh_token` | JWT refresh token (30 day TTL) |
| `prachar_email` | User email (for UI + re-login) |
| `prachar_password` | Saved password (dev/demo silent re-login) |
| `prachar_onboarded` | "1" after onboarding complete |
| `prachar_active_brand` | Active brand UUID |
| `prachar_customer_type` | "business" or "creator" |

### RLS (Row-Level Security)
- Every tenant-scoped table has `tenant_id` column
- `TenantMiddleware` extracts tenant_id from JWT → sets on `request.state`
- DB session sets `SET LOCAL app.tenant_id = <uuid>` for RLS
- Users can ONLY see their own tenant's data

### Roles
| Role | Access |
|------|--------|
| `owner` | Full access + admin endpoints |
| `admin` | Administrative access |
| `member` | Limited access |

### Auth Endpoints (8)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/auth/register` | Register new user + tenant |
| POST | `/auth/login` | Login |
| POST | `/auth/refresh` | Refresh token |
| GET | `/auth/me` | Current user profile |
| POST | `/auth/verify-email` | Verify email with token |
| POST | `/auth/forgot-password` | Send reset email |
| POST | `/auth/reset-password` | Reset password with token |
| POST | `/auth/resend-verification` | Resend verification email |

---

## 3. Data Model (30+ Tables)

### Core Hierarchy
```
Tenant (1) ──< (N) User
Tenant (1) ──< (N) Brand
Tenant (1) ──< (1) Billing
Brand  (1) ──< (N) Connection    (channel OAuth)
Brand  (1) ──< (N) Asset         (videos, images, pages)
Brand  (1) ──< (N) ContentItem   (generated content, versioned)
Brand  (1) ──< (N) Campaign      (ad campaigns)
Brand  (1) ──< (N) Diagnosis     (weekly findings)
Brand  (1) ──< (N) Report        (weekly PDF reports)
Campaign (1) ──< (N) Creative    (ad creatives)
Campaign (1) ──< (N) ReviewComment   (inline comments, threaded)
Campaign (1) ──< (N) ReviewVersion   (version snapshots)
Campaign (1) ──< (N) CampaignPerformance (daily metrics)
```

### Marketing Intelligence Tables
```
Brand (1) ──< (1) BusinessMemoryRecord    (persistent learnings)
Brand (1) ──< (N) BusinessProfileRecord   (business analysis)
Brand (1) ──< (N) AudienceProfileRecord   (audience analysis)
Brand (1) ──< (N) CompetitorProfileRecord (competitor analysis)
Brand (1) ──< (N) MarketingStrategyRecord (objective + strategy)
Brand (1) ──< (N) CreativeDirectionRecord (creative direction)
Brand (1) ──< (N) MediaPlanRecord         (media plan)
Brand (1) ──< (N) CampaignPlanRecord      (full campaign, 9 engines)
CampaignPlan (1) ──< (N) ExecutionPlanRecord
CampaignPlan (1) ──< (N) LearningReportRecord
```

### Agency Council Tables
```
CampaignPlan (1) ──< (N) CouncilSessionRecord
CouncilSession (1) ──< (N) DirectorOpinionRecord   (9 directors × N rounds)
CouncilSession (1) ──< (1) ConsensusDecisionRecord
CouncilSession (1) ──< (1) CampaignScoreRecord     (7-dimension score)
CouncilSession (1) ──< (1) CouncilLearningRecord   (persistent learnings)
```

### Key Enums
| Enum | Values |
|------|--------|
| `Plan` | starter, growth, agency |
| `Role` | owner, admin, member |
| `Channel` | google, gsc, gmb, youtube, instagram, facebook, tiktok, x, linkedin, pinterest, snapchat, reddit, whatsapp, telegram, line, kakao, vk, yandex, naver, amazon |
| `AdsNetwork` | google_ads, meta_ads, tiktok_ads, x_ads, linkedin_ads, pinterest_ads, snap_ads, reddit_ads, microsoft_ads, spotify_ads, taboola, outbrain, amazon_ads, yandex_direct, kakao_moment, line_ads |
| `CampaignObjective` | awareness, traffic, leads, conversions, app_installs, video_views |
| `CampaignStatus` | draft, active, paused, ended, in_review, changes_requested, approved |
| `ConnectionStatus` | pending, active, expired, revoked |
| `PolicyStatus` | pending, passed, blocked |
| `BillingStatus` | active, past_due, canceled, trialing |

---

## 4. API Endpoints (87 total)

### Brands (4)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/brands` | Create brand |
| GET | `/brands` | List tenant's brands |
| GET | `/brands/{id}` | Get brand |
| GET | `/brands/{id}/score` | Get visibility score |

### Campaigns (4)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/campaigns` | Create campaign |
| GET | `/campaigns` | List campaigns |
| POST | `/campaigns/{id}/pause` | Pause campaign |
| POST | `/campaigns/{id}/resume` | Resume campaign |

### Campaign Brain (9) — the 10-engine AI orchestrator
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/campaign-brain/analyse` | Business + audience + competitor analysis |
| POST | `/campaign-brain/strategy` | Marketing objective + campaign strategy |
| POST | `/campaign-brain/creative-direction` | Creative direction |
| POST | `/campaign-brain/media-plan` | Media plan |
| POST | `/campaign-brain/execution-plan` | Execution plan |
| POST | `/campaign-brain/full-campaign` | **All 9 engines** → FullCampaign |
| GET | `/campaign-brain/plans` | List saved campaign plans |
| GET | `/campaign-brain/plans/{id}` | Get saved plan |
| POST | `/campaign-brain/{id}/learn` | Learning report from performance |

### Consult (2) — business onboarding
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/consult` | Free-text → business understanding + 30-day plan |
| POST | `/consult/campaign` | Generate campaign preview from consultation |

### Creator (4)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/creator/consult` | Creator onboarding |
| POST | `/creator/campaign` | Creator campaign |
| POST | `/creator/repurpose` | 1 video → 11 asset types |
| POST | `/creator/youtube-plan` | Full YouTube video plan |

### Unified Consult (5) — domain-agnostic (replaces consult + creator)
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/consult/domains` | List all domains + subtypes |
| POST | `/consult` | Universal consult (any domain) |
| POST | `/consult/campaign` | Universal campaign generation |
| POST | `/consult/tool/{tool_id}` | Invoke domain-specific tool |
| GET | `/consult/nav/{domain}` | Get sidebar nav for domain |

### Creative Studio (4)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/creative-studio/generate` | Generate all 10 formats |
| POST | `/creative-studio/generate/{format_id}` | Generate single format |
| POST | `/creative-studio/regenerate-field` | Regenerate single field |
| GET | `/creative-studio/{package_id}` | Get saved package |

**10 formats**: poster, video_script, carousel, story, whatsapp, facebook, linkedin, email, landing_page, sms

### Review (8)
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/review/queue` | Campaigns awaiting review |
| POST | `/review/{id}/request-changes` | Send back with feedback |
| POST | `/review/{id}/approve` | Approve campaign |
| POST | `/review/{id}/publish` | Publish (enqueues Celery) |
| POST | `/review/{id}/suggestions` | AI improvement suggestions |
| PATCH | `/review/{id}/field` | Inline edit field |
| GET | `/review/{id}/comments` | List comments |
| POST | `/review/{id}/comment` | Add comment |
| GET | `/review/{id}/versions` | Version history |

### Performance (4)
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/performance/{id}` | Performance summary |
| GET | `/performance/{id}/why` | Root-cause analysis |
| GET | `/performance/{id}/next` | Recommendations |
| GET | `/performance/{id}/story` | Narrative story (de-jargonised) |

### Proactive (2)
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/proactive/notifications` | Pending anomalies + AI recommendations |
| POST | `/proactive/{id}/launch` | One-click launch (returns pre-fill) |

### Chat (1) — CURV AI assistant
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/chat` | Voice assistant chat (Siri-like, advertising expert) |

### Connections (3)
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/connections` | List channel connections |
| POST | `/connections/{channel}/oauth` | Start OAuth flow |
| GET | `/connections/{channel}/callback` | OAuth callback |

### Billing (7)
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/billing/plans` | List plans + pricing |
| GET | `/billing/subscription` | Current subscription |
| POST | `/billing/checkout` | Create checkout (Stripe/Razorpay) |
| POST | `/billing/cancel` | Cancel at period end |
| GET | `/billing/usage` | Usage vs limits |
| POST | `/billing/webhook/stripe` | Stripe webhook |
| POST | `/billing/webhook/razorpay` | Razorpay webhook |

### Audits (3) — free funnel, no auth
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/brands/audit` | Start audit (URL → crawl → score) |
| GET | `/audits/{id}` | Get audit status |
| GET | `/audits/{id}/events` | **SSE stream** of audit progress |

### Reports (2)
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/reports/brands/{id}/report/latest` | Latest weekly report |
| GET | `/reports/brands/{id}/reports` | All reports for brand |

### Agency Council (4) — 9 AI Directors
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/agency-council/review` | Submit campaign for council review |
| POST | `/agency-council/consensus` | Get consensus decision |
| GET | `/agency-council/history` | List council sessions |
| GET | `/agency-council/{campaign_id}` | Get session by campaign |

### Video Gen (2)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/video/generate` | Generate AI video |
| POST | `/api/video/generate-image` | Generate AI image |

### Admin (8) — requires owner/admin role
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/costs` | Cost-per-tenant dashboard |
| POST | `/admin/api-tokens` | Create API token |
| GET | `/admin/api-tokens` | List API tokens |
| POST | `/admin/whitelabel/config` | Set white-label config |
| GET | `/admin/brands/summary` | Multi-brand summary |
| GET | `/admin/ai-metrics` | AI usage metrics |
| GET | `/admin/ai-metrics/logs` | AI request logs |
| GET | `/admin/export/brands` | Export brands as CSV |

### Attribution (3)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/pixel/track` | First-party pixel tracking |
| POST | `/pixel/convert` | Record conversion (40/20/40 attribution) |
| GET | `/pixel.js` | Tracking pixel JS snippet |

### Misc (3)
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| GET | `/health/ready` | Readiness (DB, Redis, disk) |
| GET | `/health/live` | Liveness |

---

## 5. AI Architecture

### 5.1 Marketing Intelligence Engine (10 engines)

The "think before create" brain. Every campaign starts with strategy, never with creative assets.

```
CampaignBrain.generate_campaign()
  │
  ├─ 1. BusinessIntelligenceEngine    → BusinessProfile (18 fields)
  ├─ 2. AudienceIntelligenceEngine    → AudienceProfile (10 fields)
  ├─ 3. CompetitorIntelligenceEngine  → CompetitorProfile (6 fields)
  ├─ 4. MarketingObjectiveEngine      → MarketingObjective (7 fields)
  ├─ 5. CampaignStrategyEngine        → CampaignStrategy (12 fields)
  ├─ 6. CreativeDirectionEngine       → CreativeDirection (12 fields)
  ├─ 7. MediaPlanningEngine           → MediaPlan (5 fields)
  ├─ 8. BudgetIntelligenceEngine      → BudgetEstimate (12 fields)
  ├─ 9. ExecutionPlanner              → ExecutionPlan (7 fields)
  └─ 10. LearningEngine               → LearningReport (10 fields) [post-campaign]
```

**Dependency order**: Business → Audience → Competitor → Objective → Strategy → Creative → Media → Budget → Execution

**Output**: `FullCampaign` with all 9 profiles + executive_summary + risk_assessment + overall_confidence

### 5.2 Agency Council (9 AI Directors)

Simulates an executive meeting where 9 specialist AI Directors independently review campaigns.

| Director | Role | Weight (default) |
|----------|------|------------------|
| ChiefStrategyOfficer | Business positioning, market opportunity | 15% |
| ChiefCreativeOfficer | Creative concept, storytelling | 15% |
| ChiefMediaOfficer | Channel mix, reach | 10% |
| ChiefPerformanceOfficer | ROI, CAC, CPA | 10% |
| ChiefBrandOfficer | Brand consistency, tone | 10% |
| ChiefFinancialOfficer | Budget, cost efficiency | 10% |
| ChiefComplianceOfficer | Policies, legal, claims | 15% |
| ChiefCustomerOfficer | Audience fit, psychology | 10% |
| ChiefAnalyticsOfficer | Historical performance, memory | 5% |

**Consensus**: Weighted (not majority voting). Multi-round (max 3) when disagreement > 0.45. Self-critique step before final approval.

**Scoring**: 7 dimensions (strategy, creative, media, brand, performance, risk, compliance) + overall weighted score.

### 5.3 AI Gateway

All LLM calls go through this. Provider abstraction + safety + budgeting.

| Feature | What it does |
|---------|-------------|
| Providers | Anthropic (primary), OpenAI (fallback), Groq (fast) |
| Tiering | `small` (Haiku, cheap) · `large` (Sonnet, capable) |
| Caching | Redis cache by (model, prompt, schema) key |
| Budget | Per-tenant token limits: Starter 50K, Growth 200K, Agency 1M |
| Safety | 22 prompt injection patterns, output leak detection |
| Observability | Every request logged with request_id, latency, tokens, cost |
| Preflight | Cost estimation before running workflows |

### 5.4 Domain Packs

Pluggable architecture for customer segments. Zero core modifications when adding new domains.

| Domain | Customer Type | Subtypes |
|--------|--------------|----------|
| business | business | (general) |
| creator | creator | youtube_creator, instagram_creator, podcaster, influencer, gaming_creator, educator, media_company, production_studio, musician, personal_brand |
| restaurant | business | dine-in, delivery, cloud_kitchen |
| clinic | business | dental, veterinary, physiotherapy, mental_health |

Each pack defines: consult prompts, campaign template, tools, sidebar navigation.

### 5.5 Proactive Engine

"What should I worry about?" — scans campaigns for anomalies.

| Anomaly Type | Trigger |
|--------------|---------|
| Drop | >20% week-over-week decline |
| Spike | >50% week-over-week increase |
| Plateau | <5% change for 2+ consecutive weeks |

For each anomaly, generates: what_to_do, why, 3 creative_directions, expected_impact.

### 5.6 Chat (CURV AI)

**Persona**: Siri-like voice assistant specialized in advertising + PRACHAR platform.

**Knowledge**:
- PRACHAR platform (weekly loop, visibility score, channels, pricing)
- Advertising expertise (Google Ads, Meta Ads, SEO, analytics, strategy)
- Competitive intelligence (Buffer, Hootsuite, Later, Sprout Social)
- General knowledge (weather, time, math, facts)

**Context received**:
- Brand info (if brand_id provided)
- Live campaign performance (last 30 days)
- Business graph (conversation memory from onboarding)
- Proactive notifications (anomalies + recommendations)
- Council review detection (if user asks "review my campaign")

---

## 6. Workers (Autonomous Marketing)

### Weekly Loop (7 steps, runs per-brand)
```
1. measure       → Pull performance metrics across all channels
2. diagnose      → Analyze performance, identify issues
3. regenerate    → Generate new content/creatives
4. policy_check  → Run policy gates (claims, channel rules)
5. publish       → Publish approved content to channels
6. budget_realloc → Reallocate budget across networks (±20% clamp)
7. report        → Generate PDF weekly report
```

### Celery Queues (9)
| Queue | Purpose |
|-------|---------|
| `prachar` | Default/catch-all |
| `dispatch` | Beat + dispatch_due (lightweight) |
| `ingest` | Audit/crawl/ingestion |
| `organic` | Content generation + publishing |
| `ads` | Ad campaign management |
| `measure` | Performance metrics + analytics |
| `creative` | Creative generation + evolution |
| `loop-0` to `loop-N` | Shard queues for weekly loop |
| `dlq` | Dead letter queue for failed tasks |

### Beat Schedule (3)
| Task | Schedule | Purpose |
|------|----------|---------|
| `dispatch_due` | Every 60s | Enqueue brands whose weekly loop is due |
| `pull_daily_performance` | 03:00 UTC daily | Pull metrics for all active campaigns |
| `check_anomalies` | 04:00 UTC daily | Scan for performance anomalies |

### Channel Adapters (26)
**16 organic**: google, gsc, gmb, youtube, instagram, facebook, tiktok, x, linkedin, pinterest, whatsapp, telegram, line, vk, reddit, naver

**10 ads**: google_ads, meta_ads, tiktok_ads, linkedin_ads, pinterest_ads, x_ads, microsoft_ads, reddit_ads, snap_ads, yandex_direct

### Policy Gates
- **Global claims gate**: Blocks "guaranteed #1", "100% guaranteed", "risk-free investment"
- **Medical warnings**: "cure", "treat", "diagnose" → warning
- **Per-channel rules**: Character limits, hashtag limits, banned content
- **Reddit**: Always requires human approval (never auto-publish)

---

## 7. Frontend Integration Points

### 7.1 What v2 frontend already uses (from v1)

| lib file | Endpoints used |
|----------|---------------|
| `api.ts` | All (base client) |
| `auth.ts` | /auth/login, /auth/refresh |
| `hooks.ts` | /brands, /campaign-brain/plans |
| `consult.ts` | /consult, /consult/campaign |
| `creator.ts` | /creator/consult, /creator/campaign, /creator/repurpose, /creator/youtube-plan |
| `review.ts` | /review/* (8 endpoints) |
| `performance.ts` | /performance/* (4 endpoints) |
| `creative-studio.ts` | /creative-studio/* (4 endpoints) |
| `proactive.ts` | /proactive/notifications, /chat/proactive, /proactive/{id}/launch |
| `unified-consult.ts` | /consult/domains, /consult/nav/{domain}, /consult, /consult/campaign, /consult/tool/{id} |

### 7.2 What v2 should additionally use (AI-first features)

| Feature | Endpoint | v2 Use Case |
|---------|----------|-------------|
| **Agency Council** | POST /agency-council/review | AI orb can submit campaigns for 9-director review |
| **Campaign Brain (individual engines)** | POST /campaign-brain/analyse, /strategy, /creative-direction, /media-plan, /execution-plan | AI orb can run individual engines on demand |
| **Learning** | POST /campaign-brain/{id}/learn | AI orb can show what was learned from past campaigns |
| **Council history** | GET /agency-council/history | AI orb can show past council decisions |
| **Chat** | POST /chat | AI orb voice assistant (with brand context) |
| **Billing usage** | GET /billing/usage | Dashboard can show AI budget usage |
| **Admin AI metrics** | GET /admin/ai-metrics | Dashboard can show AI cost/transparency |
| **Brand score** | GET /brands/{id}/score | Dashboard can show visibility score breakdown |
| **Audit SSE** | GET /audits/{id}/events | Audit page can stream progress |
| **Reports** | GET /reports/brands/{id}/reports | Reports page can list weekly PDFs |

### 7.3 Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_BASE` | `/api` (v2 proxy) | Backend API base URL |

v2 uses `/api` relative path → Next.js rewrite proxies to `http://localhost:8000/*`. This avoids CORS entirely.

---

## 8. Key Business Flows

### 8.1 Onboarding Flow
```
User registers → /onboarding
  → Choose type (business/creator)
  → Choose subtype (restaurant/youtube_creator/etc.)
  → Free-text description
  → POST /consult (or /creator/consult)
    → Returns: understanding, opportunities, 30-day plan
  → POST /consult/campaign (or /creator/campaign)
    → Returns: campaign preview, campaign_plan_id
  → Approve → set prachar_onboarded=1 → redirect to /app
```

### 8.2 Campaign Creation Flow
```
Dashboard → "Create campaign"
  → POST /campaign-brain/full-campaign {brand_id, goal, budget}
    → Runs all 9 engines → FullCampaign
    → Saves CampaignPlanRecord
  → Review campaign
  → POST /review/{id}/approve
  → POST /review/{id}/publish
    → Enqueues Celery publish task
    → Publishes to all connected channels
```

### 8.3 Weekly Loop (Autonomous)
```
Every 60s: dispatch_due checks for due brands
  → Enqueues brand to shard queue
  → 7-step chain runs:
    measure → diagnose → regenerate → policy_check → publish → budget_realloc → report
  → Results stored in DB + audit_events
  → PDF report generated
```

### 8.4 Proactive Notifications
```
Every day 04:00 UTC: check_anomalies
  → Scans all active campaigns
  → Detects drops/spikes/plateaus
  → Stores in cache
  → Frontend polls GET /proactive/notifications
  → User clicks "Launch" → POST /proactive/{id}/launch
    → Returns pre-filled campaign data
    → User reviews + approves (human-in-the-loop)
```

### 8.5 Agency Council Review
```
User asks AI orb: "Review my campaign"
  → POST /agency-council/review {brand_id, campaign_brief}
    → 9 Directors independently review
    → ConsensusEngine calculates weighted consensus
    → Multi-round if disagreement > 0.45
    → Self-critique step
    → Returns: decision, opinions, 7-dimension score
  → AI orb summarises decision conversationally
```

---

## 9. Pricing Plans

| Plan | Price INR | Price USD | AI Budget | Brands | Videos/mo | Images/mo |
|------|-----------|-----------|-----------|--------|-----------|-----------|
| Starter | ₹499 | $9 | 50K tokens | 1 | 5 | 50 |
| Growth | ₹2,999 | $49 | 200K tokens | 3 | 20 | 200 |
| Agency | ₹9,999 | $149 | 1M tokens | Unlimited | 100 | 1000 |

---

## 10. Visibility Score

Composite 0-100 score, updated weekly:

| Component | Weight | What it measures |
|-----------|--------|------------------|
| organic_rank_index | 35% | Search ranking position |
| social_reach_index | 25% | Social media reach |
| ai_citation_rate | 15% | How often AI cites the brand |
| paid_efficiency | 15% | Ad spend efficiency |
| momentum | 10% | Week-over-week growth |
