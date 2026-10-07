# CURV AI — End-to-End Forensic Audit

**Date:** 2026-10-06 · **Scope:** code + config + RDS + ECS + live staging (`*.curvai.org`)
**Method:** source of truth = code, deployed task defs, Secrets Manager keys, live API probes — not docs.

---

## 1. System map

```
                         ┌─────────────────────────────────────────┐
                         │  CloudFront  (curvai.org / app.*)       │
                         │  static Next.js 15 export (web-v2)      │
                         └───────────────┬─────────────────────────┘
                                         │ HTTPS /api → ALB
┌────────────────────────────────────────▼─────────────────────────┐
│  FastAPI (prachar-api, ECS Fargate)                              │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │
│  │ 27 routers  │  │ Runtime/Orb  │  │  /chat compat endpoint  │  │
│  │ (144 routes)│  │ invoke → SSE │  │  (same gateway/plan)    │  │
│  └─────────────┘  └──────┬───────┘  └─────────────────────────┘  │
│                          │ planner → executor → composer         │
│                          │ 75 registered tools                   │
└──────────┬───────────────┼──────────────────┬────────────────────┘
           │               │                  │
   ┌───────▼───────┐  ┌────▼─────────┐  ┌─────▼──────────────┐
   │ RDS Postgres  │  │ ElastiCache  │  │ Celery worker+beat │
   │ 37 tables+RLS │  │ Redis        │  │ 5 task modules     │
   │ tenant_id RLS │  │ budget/celery│  │ +weekly loop+beat  │
   └───────────────┘  └──────────────┘  └─────────┬──────────┘
                                                  │ channel adapters
           ┌──────────────────────────────────────▼──────────┐
           │ AI Gateway (shared pkg)                          │
           │ Groq gpt-oss-20b/120b (primary) → Anthropic →    │
           │ OpenAI fallbacks · cache · atomic Redis budget   │
           └──────────────────────────────────────────────────┘
```

## 2. Component classification

| # | Component | Status | Evidence |
|---|-----------|--------|----------|
| **Frontend (web-v2)** | 52 routes, static export on CloudFront | CONNECTED | Deployed, serving; api client w/ token refresh |
| Frontend `/app` Orb chat | invoke→SSE→tools→composer | ACTIVELY USED | Verified live end-to-end |
| Chat history | rail + `/app/chat-history` + `/runtime/sessions` | ACTIVELY USED | brand_id now persisted on session.started |
| VoiceAssistant | Web Speech API → `/chat` | ACTIVELY USED | contract verified |
| **Dead frontend calls** | `/brands/{id}/campaigns`, `/brands/{id}/content`, `/brands/{id}/reports`, `/campaigns/{id}/budget` | **BROKEN (404)** | live-probed: all 404; those pages render empty/error |
| Legacy `apps/web` | full duplicate Next app (117 files) | **DEAD/DUPLICATED** | not deployed; still audits + drags dependency surface |
| `apps/api/routers/`, `apps/workers/{ads,organic,...}` | empty dirs | **DEAD** | leftover skeletons |
| `apps/ai-gen` (Modal GPU svc) | Wan/other GPU gen | **DISCONNECTED** | exists as separate Modal app; API video path uses fal.ai/Gemini instead; `ai_gen_url` unused on staging |
| **Auth** | register/login/refresh, PyJWT, social (Google tokeninfo / Apple) | ACTIVELY USED | PyJWT migration verified live; Apple needs `apple_sign_in_client_id` (unset) |
| Email verify/reset | SMTP or Resend → **console-log fallback** | PARTIALLY | no SMTP/Resend env on staging — links land in API logs only |
| **Multi-tenancy** | RLS on tenant tables, `app.tenant_id` per session, SECURITY DEFINER helpers for cross-tenant discovery | ACTIVELY USED | verified w/ 2-tenant dispatch test; worker never BYPASSRLS |
| **Database** | 37 tables, Alembic 0001→0016 | ACTIVELY USED | migrations applied on RDS |
| **Redis** | budget ledger (atomic Lua), completions cache, rate limit, idempotency, Celery broker | ACTIVELY USED | rediss:// w/ CERT_NONE normalization |
| **AI Gateway** | `complete()` w/ tier routing, cache, `check_and_reserve`+settle | ACTIVELY USED | verified: ~103 tok/chat w/ reasoning_effort=low |
| LLM providers | Groq configured; Anthropic+OpenAI keys present (fallback); **Gemini key absent** | PARTIALLY | gemini provider unreachable on staging |
| **Runtime/Orb** | planner, executor, composer, event bus, timeline, event replay | ACTIVELY USED | SSE events persist → chat history works |
| Tools | 75 registered (`tools*.py`) | MOSTLY CONNECTED | all route through gateway/DB; channel-publish tools depend on OAuth'd connections (none exist yet) |
| Context Builder | 17 providers | ACTIVELY USED | evaluated per invoke (context.build.evaluated events) |
| **Campaign Brain** | 10 engines chained (BI→audience→competitor→objective→strategy→creative→media→budget→execution→learning) | CONNECTED | real LLM chains; works under starter budget now |
| **Agency Council** | 9 directors + consensus engine + council memory | CONNECTED | real; council.review/council.history tools registered |
| **Consult flow** | free-text → brand → brain.analyse → 30-day plan | CONNECTED | `/consult`, `/consult/domains` 200 live |
| Knowledge Hub / RAG | sources → chunks → OpenAI embeddings → `knowledge_embeddings` → semantic search | CONNECTED | OPENAI_API_KEY set → real embeddings (hash fallback only if absent) |
| **Creative Studio** | 10 formats generated via LLM | CONNECTED | `creative_studio.*` tools + regenerate-field |
| **Video generation** | fal.ai Wan-3.0 primary / Gemini Veo fallback / image via Seedream/Imagen | **UNCONFIGURED** | live probe: `"No video generation service configured"` — no FAL_KEY/GEMINI_API_KEY |
| **Billing** | Stripe + Razorpay checkout, plans, usage, invoices | CONNECTED | keys set; checkout code real |
| Billing webhooks | signature-verified receivers | PARTIALLY | `stripe_webhook_secret`/`razorpay_webhook_secret` not in secrets → webhooks will reject |
| **Channel OAuth** | google/meta/instagram/tiktok/linkedin/x/pinterest auth URL builders + callback + token vault (TOKEN_ENC_KEY set) | **BUILT, UNUSABLE** | live probe: `client_id=placeholder` in auth URLs — zero OAuth app creds in secrets |
| Adapters (organic) | 19 files: google/gsc/gmb/youtube/meta/IG/FB/tiktok/linkedin/x/pinterest/reddit/whatsapp/telegram/line/vk/naver | BUILT, DORMANT | real API code; zero connections exist → nothing to publish |
| Adapters (ads) | 12 networks incl. budget/bid/policy | BUILT, DORMANT | same — no creds/connections |
| **Workers/beat** | dispatch_due 60s · performance-pull 03:00 · proactive-anomalies 04:00 | ACTIVELY USED | verified live: due brand dispatched → measure → idempotency hit |
| Proactive notifications | anomaly detection → `/proactive/notifications` | CONNECTED | endpoint 200; feed depends on channel data (none yet) |
| Integrations framework | GA4, HubSpot, Mailchimp, Shopify, WordPress classes + sync/mapping | PARTIALLY | only `google_analytics` registered live; OAuth creds missing for the rest |
| Review system | versions/comments/approve/publish | CONNECTED | routes real |
| Webhooks | `POST /webhooks/{integration}` | CONNECTED | single generic ingress |
| Observability | admin ai-metrics/logs/costs, ops overview, audit_events | CONNECTED | real |
| Security | injection guard, claims gate, CORS, rate limiter, PyJWT, TOKEN_ENC_KEY | ACTIVELY USED | verified |
| **Deployment** | ECS×4 + RDS + ElastiCache + S3 + CloudFront + ALB, deploy.yml green | ACTIVELY USED | latest deploys green |

## 3. Intelligence flow (verified)

```
user msg → /runtime/invoke → TenantMiddleware(RLS) → ContextBuilder(17 providers)
  → IntentEngine → Planner → ExecutionGraph → Executor → tools
  → AI Gateway [budget reserve → provider call → settle actual usage]
  → Composer → SSE events → persisted runtime_events → chat history
Billing: Redis counter (authoritative) → mirrored to billing.ai_tokens_used_month
Errors: tool.error{code} → runtime.session.error{code,upgrade_required} → OrbPanel
```

## 4. Critical findings (launch-relevant)

1. **P0 — Media generation dark on staging.** `/video/generate` + image gen return "not configured" — need `FAL_KEY` (Wan 3.0) and/or `GEMINI_API_KEY` (Veo/Imagen) in `/prachar/staging/app/env`. One key each is enough.
2. **P0 — Zero OAuth channel creds.** Every `channel.connect` flow generates `client_id=placeholder` URLs — connections UI is a dead end on staging. Needs GOOGLE_CLIENT_ID/SECRET, META_*, TIKTOK_*, LINKEDIN_*, X_*, PINTEREST_* per-channel app registrations.
3. **P1 — Transactional email not sending.** No SMTP/Resend → verify-email/reset links only log. Breaks forgot-password UX. (We now have Microsoft 365 mail — SMTP relay is an easy fill.)
4. **P1 — 4 dead frontend routes** on brand detail pages (404s): `/brands/{id}/campaigns`, `/brands/{id}/content`, `/brands/{id}/reports`, `/campaigns/{id}/budget`. Map to real endpoints or remove.
5. **P1 — Billing webhooks unconfigured** (no signing secrets) → payments made in Stripe/Razorpay dashboards won't flip subscription state. Checkout itself works; plan activation is manual until webhooks wired.
6. **P2 — Dead weight:** `apps/web` (117-file legacy app), `apps/api/routers/`, `apps/workers/{ads,organic,...}` empty dirs, `apps/ai-gen` Modal svc (unreferenced by API path). Cleanup or archive; `apps/web` still shows in vuln audits.
7. **P2 — Apple social sign-in** needs `apple_sign_in_client_id` (unset).

## 5. Honest state summary

**The intelligence core is real and working:** Runtime→Planner→Tools→Gateway→Composer→SSE, campaign brain (10 engines), agency council, consult onboarding, knowledge RAG, creative studio, budget/ledger unification — all verified on staging with real model calls.

**The distribution surface is built but dormant:** 19 organic + 12 ads adapters, OAuth flows, weekly loop, performance ingestion — all real code, but nothing can connect until channel OAuth apps are registered and their creds land in Secrets Manager.

**Media generation is the only hard-blocked product feature** (no FAL/Gemini key).

Report generated from code + live staging probes; statuses marked UNKNOWN where runtime access was insufficient.

---

## 6. Production-activation state (2026-10-06, re-validated)

### Findings re-validation

| Finding | Verdict |
|---|---|
| Media gen unconfigured (no FAL/GEMINI on staging) | **CONFIRMED** live — `/video/generate` → `"No video generation service configured"`. Keys **exist in local `.env`** (FAL len 69, GEMINI len 53) — credential-sync issue, not missing creds. |
| All OAuth `client_id=placeholder` | **CONFIRMED** live. Real creds for Google/Meta/LinkedIn/X/WhatsApp/Telegram/LINE exist in local `.env` — never synced to AWS. |
| No SMTP/Resend → emails log-only | **CONFIRMED**. M365 mailbox `founder@curvai.org` now exists → SMTP fill ready. |
| Webhook secrets missing | **CONFIRMED** (503 live). Entitlement code verified with signed-payload test — **works, credential-only**. |
| 4 dead frontend calls | **FIXED TODAY** — `?brand_id=` filter, `POST /campaigns/{id}/budget`, `GET /brands/{id}/content`, reports path + presigned download. 10 tests green. |
| `apps/web`/`apps/api/routers`/`apps/workers/*`/`apps/ai-gen` dead | **CONFIRMED** — see `CURV_AI_DECOMMISSION_PLAN.md`. |
| Billing `ai_tokens_used:0` divergence | **FIXED** (earlier sprint) — ledger mirrors live (`28,872` verified). |

### New findings this pass

- **Meta ads silently fake:** `MetaAdsAdapter._get_account_id` reads `act_{id}` from `tokens.scopes` — Meta never puts `act_` in scopes → `create_campaign` always returns deterministic `meta-<sha>` fallback. Needs `/me/adaccounts` discovery + `act_id` in Connection metadata. **Launch-blocking for paid.**
- **No Meta long-lived token exchange** (`fb_exchange_token` absent) — tokens expire with no renewal.
- **Reports had no download path** — `pdf_s3_key` existed but no presigned endpoint (fixed today).
- **Local `.env` ≠ staging:** the gap is a credential *sync* problem, not a "don't have creds" problem — narrows activation to ~30 min of ops.

### Production-readiness quadrant

```
🧠 INTELLIGENCE   🟢 LIVE       🖐 EXECUTION   🟡 CREDENTIAL + Meta bug
🎨 MEDIA          🟡 CREDENTIAL 🔌 INTEGRATIONS 🟡 CREDENTIAL (T1 only)
💳 MONETIZATION   🟡 WEBHOOK SECRETS  📨 COMMUNICATION 🟡 SMTP env
⚙️ AUTOMATION     🟢 LIVE       🔐 SECURITY    🟢 LIVE
```

**Verdict: 🟡 READY AFTER CONFIGURATION** — ~1.5 eng-days + credential ops. See `CURV_AI_PRODUCTION_READINESS_REPORT.md`.
