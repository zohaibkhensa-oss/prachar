# CURV AI — Public Launch Capability Matrix

**Date:** 2026-10-06 · Baseline: `CURV_AI_FORENSIC_AUDIT.md`, re-validated live.
Legend: 🟢 LIVE · 🟡 CONFIG REQUIRED · 🟠 CODE/CONTRACT FIX REQUIRED · ⚪ DORMANT · 🔴 BROKEN

## 🧠 AI BRAIN

| Capability | Code | Connected | Credentials | Staging | Live Verified | Launch Status | Priority |
|---|---|---|---|---|---|---|---|
| Runtime (invoke→SSE→persist) | ✔ | ✔ | — | ✔ | ✔ session.completed | 🟢 LIVE | — |
| Orb (16 providers evaluated) | ✔ | ✔ | — | ✔ | ✔ context.build.evaluated | 🟢 LIVE | — |
| Planner / Executor / Composer | ✔ | ✔ | — | ✔ | ✔ planner.decision.created | 🟢 LIVE | — |
| Tool gateway (75 registered) | ✔ | ✔ | — | ✔ | ✔ tool.* events | 🟢 LIVE | — |
| AI Gateway (tiering/cache/budget) | ✔ | ✔ | Groq ✔ | ✔ | ✔ ~103 tok/chat | 🟢 LIVE | — |
| LLM: Groq gpt-oss-20b/120b | ✔ | ✔ | GROQ_API_KEY set | ✔ | ✔ | 🟢 LIVE | — |
| LLM: Anthropic / OpenAI fallback | ✔ | ✔ | keys set in AWS secrets | ✔ | — not exercised | 🟡 CONFIG OK / VERIFY | P2 |
| LLM: Gemini provider | ✔ | gateway supports | **key absent everywhere usable** | ✘ | — | 🟡 CREDENTIAL | P2 |
| Campaign Brain (10 engines) | ✔ | ✔ | Groq | ✔ | ✔ consult path | 🟢 LIVE | — |
| Agency Council (9 directors+consensus) | ✔ | ✔ | Groq | ✔ | ✔ code-path verified | 🟢 LIVE | — |
| Consult → Brand → 30-day plan | ✔ | ✔ | Groq | ✔ | ✔ /consult 200 | 🟢 LIVE | — |
| Knowledge Hub + RAG | ✔ | ✔ | OPENAI key set (embeddings) | ✔ | ✔ /knowledge/* 200 | 🟢 LIVE | — |
| Creative Studio (10 formats) | ✔ | ✔ | Groq | ✔ | ✔ tools registered | 🟢 LIVE | — |
| Review system (versions/comments/approve) | ✔ | ✔ | — | ✔ | ✔ routes live | 🟢 LIVE | — |
| Timeline / replay / chat history | ✔ | ✔ | — | ✔ | ✔ /runtime/sessions | 🟢 LIVE | — |
| Chat (/chat compat + SSE Orb) | ✔ | ✔ | Groq | ✔ | ✔ both paths | 🟢 LIVE | — |
| Voice (browser Web Speech → /chat) | ✔ | ✔ | — | ✔ | ✔ | 🟢 LIVE | — |

## 🖐 AGENCY EXECUTION

| Capability | Code | Connected | Credentials | Staging | Live Verified | Launch Status | Priority |
|---|---|---|---|---|---|---|---|
| Brand CRUD / onboarding | ✔ | ✔ | — | ✔ | ✔ | 🟢 LIVE | — |
| Campaign create/list/pause/resume | ✔ | ✔ | — | ✔ | ✔ | 🟢 LIVE | — |
| Campaign list by brand | **was missing** | **fixed** (`?brand_id=`) | — | ✔ | ✔ test | 🟢 FIXED TODAY | — |
| Campaign budget update | **was missing** | **fixed** (`POST /{id}/budget`) | — | ✔ | ✔ test | 🟢 FIXED TODAY | — |
| Brand content library | **was missing** | **fixed** (`GET /brands/{id}/content`) | — | ✔ | ✔ test | 🟢 FIXED TODAY | — |
| Weekly report list + PDF download | partial | **fixed** (status+presigned URL) | S3 ✔ | ✔ | ✔ test | 🟢 FIXED TODAY | — |
| Channel publish (organic) | ✔ adapters | ✘ | **no OAuth creds** | ✘ | ✘ `client_id=placeholder` | 🟡 CREDENTIAL | P0 |
| Ads campaign lifecycle | ✔ adapters | partial | **no ads creds + Meta acct-discovery bug** | ✘ | ✘ | 🟠 CODE+CRED | P0 |
| Review→publish approval flow | ✔ | ✔ | — | ✔ | ✔ | 🟢 LIVE | — |

## 🎨 GENERATIVE MEDIA

| Capability | Code | Connected | Credentials | Staging | Live Verified | Launch Status | Priority |
|---|---|---|---|---|---|---|---|
| Video gen (fal.ai Wan-3.0 → Veo fallback) | ✔ | ✔ | **FAL_KEY/GEMINI key absent on staging; SET locally** | ✘ | ✘ live "not configured" | 🟡 CREDENTIAL | P0 |
| Image gen (Seedream → Imagen) | ✔ | ✔ | same | ✘ | ✘ | 🟡 CREDENTIAL | P0 |
| Modal `apps/ai-gen` GPU svc | ✔ | **DISCONNECTED** — API path never calls it | n/a | never deployed | ✘ | ⚪ DORMANT — deprecate candidate | P3 |

## 🔌 INTEGRATIONS

| Capability | Code | Connected | Credentials | Staging | Live Verified | Launch Status | Priority |
|---|---|---|---|---|---|---|---|
| OAuth URL builders (google/meta/IG/tiktok/linkedin/x/pinterest) | ✔ | ✔ | **all `placeholder`** | ✘ | ✘ live-probed | 🟡 CREDENTIAL | P0 |
| Token exchange + encrypted vault | ✔ | ✔ | TOKEN_ENC_KEY set | ✔ | ✔ code verified | 🟡 waiting on creds | P0 |
| Meta organic (FB page/IG publish) | ✔ | ✔ | META creds SET locally | ✘ | ✘ | 🟡 SYNC CREDENTIALS | P0 |
| Google organic (GSC/GMB/YouTube) | ✔ | ✔ | GOOGLE creds SET locally | ✘ | ✘ | 🟡 SYNC CREDENTIALS | P0 |
| LinkedIn organic | ✔ | ✔ | creds SET locally | ✘ | ✘ | 🟡 SYNC CREDENTIALS | P1 |
| X organic | ✔ | ✔ | creds SET locally | ✘ | ✘ | 🟡 SYNC CREDENTIALS | P1 |
| WhatsApp / Telegram | ✔ | ✔ | creds SET locally | ✘ | ✘ | 🟡 SYNC CREDENTIALS | P2 |
| Meta **Ads** | ✔ | **ad-account discovery missing** (`act_` scope never populated) | META_ADS creds placeholder | ✘ | ✘ | 🟠 CODE+CRED | P0 |
| Google Ads | ✔ | ✔ | creds placeholder everywhere | ✘ | ✘ | 🟡 CREDENTIAL | P0 |
| All other ads networks (TikTok/MS/LinkedIn/X/Snap/Yandex/Reddit) | ✔ | ✔ | creds absent | ✘ | ✘ | ⚪ DORMANT | P3 |
| GA4/HubSpot/Mailchimp/Shopify/WordPress integration classes | ✔ | GA4 registered only | not configured | ✘ | ✘ | ⚪ DORMANT | P3 |

## 📨 COMMUNICATION

| Capability | Code | Connected | Credentials | Staging | Live Verified | Launch Status | Priority |
|---|---|---|---|---|---|---|---|
| Verification/reset emails | ✔ SMTP+Resend paths | ✔ | **no SMTP/Resend anywhere** | ✘ | — | 🟡 CREDENTIAL (M365 SMTP available) | P0 |
| Billing invoice emails | ✔ | ✔ | same gap | ✘ | — | 🟡 CREDENTIAL | P1 |
| Campaign/proactive notification emails | ✔ | ✔ | same gap | ✘ | — | 🟡 CREDENTIAL | P2 |

## 💳 BILLING

| Capability | Code | Connected | Credentials | Staging | Live Verified | Launch Status | Priority |
|---|---|---|---|---|---|---|---|
| Plans + usage + ledger | ✔ | ✔ | — | ✔ | ✔ /billing/usage live | 🟢 LIVE | — |
| Stripe checkout | ✔ | ✔ (inline price fallback) | STRIPE_API_KEY set | ✔ | — | 🟡 untested live | P1 |
| Razorpay checkout | ✔ | ✔ (payment-link fallback) | keys set | ✔ | — | 🟡 untested live | P1 |
| Stripe webhook → entitlement | ✔ | signature-verified | **STRIPE_WEBHOOK_SECRET absent** | ✘ | ✘ 503 | 🟡 CREDENTIAL | P0 |
| Razorpay webhook → entitlement | ✔ | HMAC-verified | **RAZORPAY_WEBHOOK_SECRET absent** | ✘ | ✘ 503 | 🟡 CREDENTIAL | P0 |
| Cancel/past-due/refund states | ✔ | ✔ | via webhooks | — | ✔ tested | 🟡 depends on secrets | P1 |

## ⚙️ AUTOMATION

| Capability | Code | Connected | Credentials | Staging | Live Verified | Launch Status | Priority |
|---|---|---|---|---|---|---|---|
| dispatch_due (60s) | ✔ | ✔ | — | ✔ | ✔ fired live | 🟢 LIVE | — |
| Daily performance pull (03:00) | ✔ | ✔ | — | ✔ | ✔ | 🟢 LIVE | — |
| Proactive anomaly beat (04:00) | ✔ | ✔ | — | ✔ | ✔ | 🟢 LIVE | — |
| Weekly loop (measure→diagnose→regen→policy→publish→realloc→report) | ✔ | ✔ | publish blocked on OAuth | ✔ | ✔ dispatch verified | 🟡 works until publish step | — |
| Queue system (6 queues + DLQ + idempotency) | ✔ | ✔ | — | ✔ | ✔ | 🟢 LIVE | — |

## Analytics

| Capability | Code | Connected | Credentials | Staging | Live Verified | Launch Status | Priority |
|---|---|---|---|---|---|---|---|
| Visibility score / audit funnel | ✔ | ✔ | SERP key optional | ✔ | ✔ | 🟢 LIVE | — |
| Attribution pixel + position model | ✔ | ✔ | — | ✔ | ✔ | 🟢 LIVE | — |
| Admin ai-metrics / costs / ops | ✔ | ✔ | — | ✔ | ✔ | 🟢 LIVE | — |
| Channel metrics ingestion | ✔ | ✘ | blocked on OAuth/ads creds | ✘ | ✘ | 🟡 CREDENTIAL | P0 |
