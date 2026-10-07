# CURV AI — Channel Readiness Report

**Date:** 2026-10-06 · Verified: adapter code → OAuth URL → token exchange → vault → publish → metrics → live staging probe.

## OAuth flow status (all channels)

Every `/connections/{channel}/oauth` URL builder exists and produces a well-formed auth URL with correct scopes — but on staging **every `client_id` is the literal string `placeholder`** (live-probed). Token exchange, Fernet-encrypted vault (`TOKEN_ENC_KEY` set), `Connection` rows, and the callback dispatcher are real and tested.

| Channel | Adapter | OAuth URL | Token exchange | Publish | Metrics | Ads | Webhook | Creds (local `.env`) | Creds (staging) | Launch |
|---|---|---|---|---|---|---|---|---|---|---|
| Google (GSC/GMB/YouTube) | google, gsc, gmb, youtube ✔ | ✔ | ✔ | ✔ | ✔ | google_ads ✔ | via /webhooks/{integration} | GOOGLE_* SET | absent | **T1** |
| Meta (FB page + IG) | facebook, instagram ✔ | ✔ | ✔ | ✔ | ✔ | meta_ads ⚠ | — | META_* SET | absent | **T1** |
| LinkedIn | linkedin ✔ | ✔ | ✔ | ✔ | ✔ | linkedin_ads ✔ | — | LINKEDIN_* SET | absent | **T2** |
| X/Twitter | x ✔ (+PKCE) | ✔ | ✔ | ✔ | ✔ | x_ads ✔ | — | X_* SET | absent | **T2** |
| WhatsApp | whatsapp ✔ (token, no OAuth) | n/a | n/a | ✔ | — | — | — | WHATSAPP_* SET | absent | **T2** |
| Telegram | telegram ✔ (bot token) | n/a | n/a | ✔ | — | — | — | TELEGRAM SET | absent | **T3** |
| Pinterest | pinterest ✔ | ✔ | ✔ | ✔ | ✔ | pinterest_ads ✔ | — | placeholder | absent | **T3** |
| TikTok | tiktok ✔ | ✔ | ✔ | ✔ | ✔ | tiktok_ads ✔ | — | placeholder | absent | **T3** |
| Reddit | reddit ✔ (approval-gated by design) | ✔ | ✔ | ✔ | ✔ | reddit_ads ✔ | — | partial | absent | **T3** |
| LINE | line ✔ | n/a | n/a | ✔ | — | — | — | LINE_ID set | absent | **T3** |
| VK / Naver / Kakao | vk, naver, kakao prompts ✔ | ✔ | ✔ | ✔ | ✔ | yandex/snap ads ✔ | — | absent/placeholder | absent | **T3** |
| Microsoft Ads / Snap / Yandex | — | n/a | n/a | n/a | n/a | ads only ✔ | — | absent | absent | **T3** |

## Meta dedicated audit (T1 chain)

```
CURV ──OAuth──▶ META_APP_ID/SECRET ──/me/accounts──▶ FB Page / IG
                    │                                         │
                    ├──(ads_management scope)                 ▼
                    │                                   organic publish ✔
                    ▼
              ad account (act_{id})  ◄── ❌ NEVER DISCOVERED
                    │
              MetaAdsAdapter: create_campaign → upload_creative
              → set_budget_bid → pause → stats → policy_precheck ✔
```

**Meta findings:**
1. `_build_meta_oauth` requests correct scopes: `pages_manage_posts, pages_read_engagement, instagram_basic, instagram_content_publish, ads_management`. ✔
2. `FacebookAdapter.exchange_code` — real Graph API token exchange. ✔
3. `fetch_profile` — `/me/accounts` page discovery. ✔
4. **❌ BUG (launch-blocking for paid):** `MetaAdsAdapter._get_account_id` looks for `act_<digits>` **inside `tokens.scopes`** — Meta never returns `act_` entries in scope arrays. `FacebookAdapter.exchange_code` sets `scopes=FB_SCOPES` (the constant), so `create_campaign` will **always** take the deterministic-fallback path and return a fake `meta-<sha>` campaign id — silently. Fix: after OAuth, call `GET /me/adaccounts`, persist `act_id` in `Connection.metadata`/`TokenSet.metadata`, and read it there. ~40 lines.
5. **❌ No long-lived-token exchange** — no `fb_exchange_token` call anywhere; user tokens die in ~2h-60d with no refresh path.
6. Required env: `META_APP_ID`, `META_APP_SECRET` (SET locally, absent staging); ads reuse the same app.

## Minimum channel set for public launch

- **TIER 1 (launch-critical):** Google organic (GSC+GMB+YouTube), Meta organic (FB+IG) — creds already exist locally; sync to staging. Meta Ads only after the `act_` discovery fix.
- **TIER 2 (post-launch):** LinkedIn, X, WhatsApp, Telegram (creds exist), Google Ads (creds needed).
- **TIER 3 (dormant):** TikTok, Pinterest, Reddit, LINE, VK, Naver, Kakao, Microsoft/Snap/Yandex ads — no creds, regional.

**Do not activate anything Tier 3 — keep adapters dormant behind feature flags until a market requires them.**
