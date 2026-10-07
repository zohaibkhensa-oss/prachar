# CURV AI — Public Launch Certification

**Date:** 2026-10-07 · Deploys: `5e88e26`, `03a3b0d` (green) · API task-def :31+ (36 secrets)
**Executive Verdict: 🟡 READY WITH NON-BLOCKING LIMITATIONS**
*(everything code-side is verified working; Stripe key + SMTP creds remain user-owned — see §12)*

## 1. AI Brain — 🟢 CERTIFIED
`/runtime/invoke` live: real session_id, planner decision, SSE stream URL. 75 tools, 17 context providers, Campaign Brain, Council, Consult→plan, RAG — all verified this session.

## 2. Agency Execution — 🟢 CERTIFIED
Brands/campaigns/review/approval gates verified. `dry_run` default + `approved`-required publish + spend-cap worker = no silent spend.

## 3. Media Generation — 🟢 CERTIFIED (FAL), 🟡 fallback
- **Image:** real `v3b.fal.media` PNG live ✓ (Seedream v4.5)
- **Video:** real `v3b.fal.media` MP4 live ✓ (Wan-3.0, fal queue accepted+completed)
- Gemini fallback: configured but account credits depleted (402) — top up AI Studio to activate fallback.

## 4. Social Channels — 🟡 CERTIFIED-READY
OAuth URLs return **real client_ids** for Meta (`163310***`) and Google (`93468144004-***`) post-sync. LinkedIn/X/WhatsApp/Telegram/LINE/GSC/YouTube creds all injected. Remaining: **console-side** — register `https://app.curvai.org/app/connections/{channel}/callback` in each provider dashboard, then a human completes one OAuth flow per channel.

## 5. Advertising — 🟡 CODE-READY
Meta `act_` discovery + `fb_exchange_token` + encrypted-token hydration fixed & tested (`test_meta_account_discovery.py`, 6 tests). Worker `_stub_tokens` eliminated from publish/metrics/watchdog/resume. First real Meta campaign needs OAuth completion + a funded ad account.

## 6. Billing — 🟢 RAZORPAY CERTIFIED / 🟠 STRIPE PENDING
Ledger, atomic budgets, `AI_BUDGET_EXCEEDED` live ✓. **Razorpay: live-verified** — real keys + registered webhook `TkyI3vmczWKJhA`; unsigned→400, signed `subscription.activated`→tenant plan `starter→growth` on staging ✓. Stripe: `STRIPE_API_KEY` still empty — needs dashboard key.

## 7. Email — 🟡 DEFERRED (user choice)
`SMTP_*` wired into task defs (empty placeholders, port 587). Fill `SMTP_USER/PASSWORD` in `.env`/secrets → M365 activate instantly. Verify/reset emails currently log-only.

## 8. Automation — 🟢 CERTIFIED
`dispatch_due` 60s + daily performance/proactive beats firing live; retry/DLQ/idempotency in place.

## 9. Security — 🟢 CERTIFIED
RLS verified on tenant tables incl. connections; PyJWT auth round-trips; OAuth tokens Fernet-encrypted; injection guard; no secrets in logs/code/commits.

## 10. Observability — 🟢 CERTIFIED
Runtime events persisted per-session; structured logs carry tenant/brand/context; admin metrics live.

## 11. Infrastructure — 🟢 CERTIFIED
ECS api/worker/beat stable on task-defs with 36 secrets; Terraform is the durable secret-map source (fixed this session after pipeline overwrites).

## 12. End-to-end matrix

| # | Test | Result |
|---|---|---|
| 1 | Signup/login | ✅ |
| 2 | Orb runtime invoke | ✅ real session+SSE |
| 3 | Campaign Brain | ✅ endpoints live |
| 4 | RAG knowledge | ✅ /knowledge/stats 200 |
| 5 | Billing usage ledger | ✅ real counters |
| 6 | Image generation | ✅ real fal.media asset |
| 7 | Video generation | ✅ real fal.media MP4 (Wan-3.0) |
| 8 | Meta OAuth URL | ✅ real client_id |
| 9 | Google OAuth URL | ✅ real client_id |
| 10 | Brand content | ✅ `/brands/{id}/content` 200 |
| 11 | Brand reports | ✅ `/reports/brands/{id}/reports` 200 |
| 12 | Campaign budget | ✅ new endpoint live |
| 13 | Budget-exceeded UX | ✅ correct `AI_BUDGET_EXCEEDED` surface |
| 14 | Razorpay webhook | ✅ signed→plan flip starter→growth live |
| 15 | Stripe webhook | ⚠ `STRIPE_API_KEY` empty — needs dashboard key |
| 16 | Email send | ⚠ deferred — no SMTP creds |
| 17 | Meta OAuth completion | ⏳ needs human consent in browser |
| 18 | Scheduled worker | ✅ dispatch firing |
| 19 | Tenant isolation | ✅ RLS verified |
| 20 | `?session=` history | ✅ loaded sessions |

## What shipped this session
`5fd1839` Meta/token fixes+contracts · `88f4250` fal/genai deps · `ec710a9` OAuth callback page · `4906c85`+`14e50a7` secret wiring · `0c3b822`/`5e88e26` worker test conftest · `03a3b0d` video duration fix.

## Remaining to reach 🟢
1. ~~Real Razorpay keys~~ ✅ done — live keys + webhook `TkyI3vmczWKJhA` verified.
2. Real `STRIPE_API_KEY` + Stripe webhook endpoint → `STRIPE_WEBHOOK_SECRET`.
3. M365 `SMTP_USER`/`SMTP_PASSWORD` → `.env`.
4. Register OAuth redirect URIs in Meta/Google consoles; one human OAuth connect.
5. Top up Gemini AI Studio credits (optional — fal is canonical).
