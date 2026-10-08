# CURV AI — Launch Blocker Matrix

**Date:** 2026-10-07 · Post-activation pass. Legend: ✅ resolved / 🟡 pending creds / 🔴 blocking.

## Resolution status

| # | Issue | Status | Evidence |
|---|---|---|---|
| B1 | Media gen creds missing on staging | ✅ **FIXED** — FAL_KEY+GEMINI_API_KEY synced; **image gen live-verified** (real fal.media URL, Seedream v4.5); video accepted by fal.ai queue (Wan-3.0) | fal queue 200s in logs |
| B2 | OAuth `client_id=placeholder` everywhere | ✅ **FIXED** — Google/Meta/LinkedIn/X/WhatsApp/Telegram/LINE/GSC/YouTube creds synced to AWS secrets + task defs | live probe: meta `163310***`, google `93468144004-***` |
| B3 | Webhook secrets missing | 🟡 **PARTIAL** — Razorpay test keys provided but **401 invalid**; STRIPE_API_KEY is empty string everywhere. Need real dashboard keys + webhook secrets | Razorpay API 401 |
| B4 | SMTP not configured | 🟡 **DEFERRED** (user choice). `SMTP_*` placeholders wired into task defs — fill to activate | awaiting creds |
| B5 | Meta `act_{id}` from scopes → silent fake campaigns | ✅ **FIXED** — `/me/adaccounts` discovery persisted into token bundle metadata; `MetaAdsAdapter` reads it | `test_meta_account_discovery.py` |
| B6 (new) | Worker `_stub_tokens()` — publish/metrics/pause/resume called APIs with `access_token="stub"` | ✅ **FIXED** — shared `prachar_workers.tokens.load_connection_tokens` decrypts `oauth_tokens_enc` in all worker paths | 84 worker tests green |
| B7 (new) | OAuth redirect → frontend callback page didn't exist | ✅ **FIXED** — `/app/connections/[channel]/callback` page added | typecheck+build |
| B8 (new) | `fal_client`/`google-genai` not in deps — every media call crashed | ✅ **FIXED** — added to api+workers pyproject | image gen works |
| B9 (new) | `VideoGenResponse` rejected int `duration` → 500 after successful render | ✅ **FIXED** — `str()` coercion | pushed `03a3b0d` |
| B10 (new) | `RAZORPAY_SECRET` env name ≠ `razorpay_key_secret` field | ✅ **FIXED** — task def now maps `RAZORPAY_KEY_SECRET` | ecs.tf |
| B11 (new) | Empty `SMTP_PORT=""` crashed app startup (pydantic int) | ✅ **FIXED** — `587` default in secrets | api :31 running |

## Remaining blockers — need YOU

| Issue | Needed | Impact |
|---|---|---|
| **Stripe keys absent entirely** | real `STRIPE_API_KEY` (test or live) + dashboard webhook → `STRIPE_WEBHOOK_SECRET` | paid upgrades can't activate |
| **Razorpay keys invalid** | correct `RAZORPAY_KEY_ID`+`RAZORPAY_KEY_SECRET` (paste into `.env`, not chat) + `RAZORPAY_WEBHOOK_SECRET` | INR payments can't activate |
| **SMTP creds** | `SMTP_USER`/`SMTP_PASSWORD`/`EMAIL_FROM` in `.env` (M365 app password) | verify/reset emails stay log-only |
| **Gemini credits depleted** | top up AI Studio billing | Veo fallback + gemini LLM fallback dead |
| **Groq TPD at ~100%** | upgrade Groq org tier | 429s under real load |
| Meta/Google OAuth app consoles | add redirect URIs `https://app.curvai.org/app/connections/{channel}/callback` + complete scopes approval | OAuth consent flow completes |

## IMPORTANT (engineering, non-blocking)

- Meta token refresh on expiry (long-lived exchange exists; renewal job absent)
- Silent-MOCK fallbacks in frontend error paths
- `apps/web` + `apps/ai-gen` retirement (dependency-proven)


## QA Regression Fixes (manual E2E test report — resolved 2026-10-08)

| QA Finding | Root Cause | Fix |
|---|---|---|
| Campaign create "Something went wrong" (Critical) | 9 sequential ~40s LLM calls exceeded the proxy window → 504; Groq 8K TPM 413s killed engines permanently | `/full-campaign` is now async: 202 + plan id, brain runs in background task (RLS-scoped), frontend polls `/campaign-brain/plans/{id}`. Groq: retry-after backoff on 429, transient JSON/schema retries, `reasoning_effort=low` default, max_tokens TPM headroom clamp |
| "No draft-saving feature" | `ContentItem` table existed but no create endpoint/tool | `POST /brands/{id}/content` + `content.save_draft` runtime tool (76 tools) |
| snap/kakao/yandex/amazon Connect guaranteed-fail | tiles existed with no adapter | removed from REGIONS |
| gsc/gmb "unsupported channel" | adapters had auth_url but start endpoint didn't try them | OAuth start falls back to `adapter.auth_url` |
| LinkedIn "Bummer" | OAuth requested `rw_ads`/`rw_organization` — app lacks Marketing Platform | scope now `w_member_social` only |
| 14/14 Connect no-ops | tested pre-credential-sync / API crash loop | all endpoints verified returning real auth URLs |
| Video gen "service isn't set up" | `FAL_KEY` missing + `fal_client` undeclared | synced + dependency added — live MP4 verified |
| Migration `0015` CI failure | hardcoded `GRANT ... ON DATABASE prachar` | uses `current_database()` |

**Remaining QA items (not code):** YouTube/Google OAuth "app not verified" → publish consent screen or add test users; Stripe keys; SMTP creds; Groq Dev tier (8K TPM saturates under load — campaign gen works but takes ~6 min); Gemini top-up.
