# CURV AI — Launch Blocker Matrix

**Date:** 2026-10-06 · All findings re-validated live on staging + code.

## BLOCKING — cannot launch without fixing

| # | Issue | Severity | User impact | Fix | Credential required | Engineering | ETA* |
|---|---|---|---|---|---|---|---|
| B1 | Media gen unconfigured on staging — `/video/generate` + images return 503 | P0 | Core promise "AI makes your ads" fails | sync `FAL_KEY` + `GEMINI_API_KEY` → `/prachar/staging/app/env` | yes (have them locally) | none | ~15 min |
| B2 | Every channel OAuth URL carries `client_id=placeholder` — no social connect possible | P0 | Connections UI is a dead end; nothing can publish | sync Google/Meta creds → AWS secrets | yes (local .env has real ones) | none | ~15 min |
| B3 | Payment webhooks rejected (503) — paying customer stays on Starter | P0 | Paid users get no entitlement → support/complaints | `STRIPE_WEBHOOK_SECRET` + `RAZORPAY_WEBHOOK_SECRET` + register endpoints in dashboards | yes (new secrets from dashboards) | none — code verified w/ signed test | ~30 min |
| B4 | Transactional email dead — verify-email/reset links log-only | P0 | Forgot-password broken; unverified signups pile up | M365 SMTP (`smtp.office365.com:587`, `founder@curvai.org` app password) → `SMTP_*` + `EMAIL_FROM` | yes (mailbox exists) | none | ~30 min |
| B5 | Meta ad-account discovery missing — `act_{id}` read from scopes that never contain it | P0 for paid | Meta campaigns silently get fake `meta-<sha>` ids | call `/me/adaccounts` post-OAuth, persist `act_id` in Connection metadata | META_* (already needed) | ~½ day | ½ day |

## IMPORTANT — should fix before broad public release

| # | Issue | Severity | User impact | Fix | Cred | Eng |
|---|---|---|---|---|---|---|
| I1 | Meta long-lived token exchange absent — tokens expire with no renewal | P1 | Connections die silently ~60d | `fb_exchange_token` flow + refresh beat | — | ½ day |
| I2 | Anthropic/OpenAI fallback tiers untested live (keys set, never exercised) | P1 | single-provider dependency on Groq | exercise fallback path | have | 1 h |
| I3 | Stripe/Razorpay checkout untested end-to-end live | P1 | unknown checkout UX edge cases | sandbox test post-secrets | dashboard | 1 h |
| I4 | Frontend mock fallbacks mask API failures (content page showed MOCK on error) | P1 | users see fake data on outages | remove silent-MOCK on error path | — | 1 h |
| I5 | `apps/web` legacy app still in workspace → inflates vuln surface | P1 | audit noise, stale vulns (`braces`) | move to `archive/` or remove | — | 1 h |
| I6 | Report PDFs have no frontend download wiring until this fix (now fixed) | P1 | reports existed but undownloadable | **DONE today** | — | done |

## POST-LAUNCH — safe to defer

| # | Issue | Cred | Eng |
|---|---|---|---|
| P1 | Tier-3 channels (TikTok/Pinterest/Reddit/LINE/VK/Naver/Kakao) — creds absent | register apps | per-channel |
| P2 | GA4/HubSpot/Mailchimp/Shopify/WordPress — classes exist, only GA registered | configure | per-integration |
| P3 | Apple social sign-in (`APPLE_SIGN_IN_CLIENT_ID`) | register | small |
| P4 | SSE `?token=` in ALB logs → short-lived stream tokens | — | small |
| P5 | Redis-backed rate limiter (fine at desired=1) | — | small |

## DEPRECATED — should not be activated

| # | Component | Why | Disposition |
|---|---|---|---|
| D1 | `apps/ai-gen` Modal GPU service | never called by API path (fal.ai is canonical); never deployed | DEPRECATE → archive |
| D2 | `apps/web` legacy Next app | superseded by web-v2; deployed nowhere | DEPRECATE → archive |
| D3 | `apps/api/routers/`, `apps/workers/{ads,organic,ingest,measure,creative}` | empty skeleton dirs | REMOVE (empty) |

*ETAs are effort estimates for the listed fix only, not calendar commitments.
