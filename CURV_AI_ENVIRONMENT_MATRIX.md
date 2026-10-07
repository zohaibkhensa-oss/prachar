# CURV AI — Environment Matrix

**Date:** 2026-10-06 · LOCAL = repo `.env` · STAGING = AWS Secrets Manager `/prachar/staging/app/env` + ECS task env · PRODUCTION = not yet provisioned (staging is the only deployed env).
Values never printed — only SET / MISSING / PLACEHOLDER.

## Core platform

| Variable | Local | Staging | Production | Required | Purpose |
|---|---|---|---|---|---|
| DATABASE_URL / _SYNC | SET | SET | — | yes | Postgres |
| REDIS_URL | SET | SET | — | yes | budget/cache/broker |
| JWT_SECRET / REFRESH | SET | SET | — | yes | auth |
| TOKEN_ENC_KEY | SET | SET | — | yes | OAuth token vault |
| CORS_ORIGINS | SET | SET | — | yes | web→API |
| S3_* | SET | SET | — | yes | assets/reports |
| WEB_URL | SET | SET | — | yes | links in emails |

## LLM providers

| Variable | Local | Staging | Production | Required | Purpose |
|---|---|---|---|---|---|
| GROQ_API_KEY | SET | SET | — | yes | primary tier (gpt-oss-20b/120b) |
| ANTHROPIC_API_KEY | PLACEHOLDER | SET | — | optional | fallback tier |
| OPENAI_API_KEY | PLACEHOLDER | SET | — | yes* | *required for RAG embeddings |
| GEMINI_API_KEY | SET | MISSING | — | optional | Veo/Imagen media fallback |
| AI_SMALL/LARGE_MODEL | — | SET (gpt-oss-*) | — | yes | tier routing |

## Generative media

| Variable | Local | Staging | Production | Required | Purpose |
|---|---|---|---|---|---|
| FAL_KEY | SET (len 69) | **MISSING** | — | yes | Wan-3.0 video + Seedream images |
| GEMINI_API_KEY | SET | **MISSING** | — | yes | Veo/Imagen fallback |
| AI_GEN_URL | MISSING | MISSING | — | no | dead Modal path |
| RUNPOD_* | MISSING | MISSING | — | no | unused |

## Organic channel OAuth

| Variable | Local | Staging | Production | Required | Purpose |
|---|---|---|---|---|---|
| GOOGLE_CLIENT_ID/SECRET | SET | **MISSING** | — | T1 | GSC/GMB/YouTube |
| META_APP_ID/SECRET | SET | **MISSING** | — | T1 | FB+IG+ads scope |
| LINKEDIN_CLIENT_ID/SECRET | SET | **MISSING** | — | T2 | LinkedIn organic |
| X_CLIENT_ID/SECRET | SET | **MISSING** | — | T2 | X organic |
| TIKTOK_CLIENT_KEY/SECRET | PLACEHOLDER | MISSING | — | T3 | TikTok |
| PINTEREST_CLIENT_ID/SECRET | PLACEHOLDER | MISSING | — | T3 | Pinterest |
| REDDIT_CLIENT_ID | PLACEHOLDER | MISSING | — | T3 | Reddit |
| WHATSAPP_PHONE_NUMBER_ID/TOKEN | SET | MISSING | — | T2 | WhatsApp (no OAuth) |
| TELEGRAM_BOT_TOKEN | SET | MISSING | — | T3 | Telegram |
| LINE_CHANNEL_ID/SECRET | SET | MISSING | — | T3 | LINE |
| VK_*, KAKAO_*, NAVER_* | PLACEHOLDER/MISSING | MISSING | — | T3 | regional |
| APPLE_SIGN_IN_CLIENT_ID | MISSING | MISSING | — | no | Apple login (disabled) |

## Ads networks

| Variable | Local | Staging | Production | Required | Purpose |
|---|---|---|---|---|---|
| META_ADS_APP_ID/SECRET | PLACEHOLDER | MISSING | — | T1* | *reuses META_APP_* typically |
| GOOGLE_ADS_* (dev token+client+refresh) | PLACEHOLDER | MISSING | — | T2 | Google Ads |
| TIKTOK_ADS_*, MICROSOFT_*, LINKEDIN_ADS_*, X_ADS_* | PLACEHOLDER | MISSING | — | T3 | paid expansion |

## Billing

| Variable | Local | Staging | Production | Required | Purpose |
|---|---|---|---|---|---|
| STRIPE_API_KEY | PLACEHOLDER | SET | — | yes | checkout |
| STRIPE_WEBHOOK_SECRET | PLACEHOLDER | **MISSING** | — | yes | entitlement activation |
| STRIPE_PRICE_{STARTER,GROWTH,AGENCY}_ID | PLACEHOLDER | MISSING | — | optional | inline-price fallback exists |
| RAZORPAY_KEY_ID/SECRET | PLACEHOLDER | SET | — | yes | checkout (INR) |
| RAZORPAY_WEBHOOK_SECRET | PLACEHOLDER | **MISSING** | — | yes | entitlement activation |
| RAZORPAY_PLAN_*_ID | PLACEHOLDER | MISSING | — | optional | payment-link fallback exists |

## Email

| Variable | Local | Staging | Production | Required | Purpose |
|---|---|---|---|---|---|
| SMTP_HOST/PORT/USER/PASSWORD | PLACEHOLDER | MISSING | — | yes | verify/reset/invoices — **M365 available** |
| RESEND_API_KEY | PLACEHOLDER | MISSING | — | alt | alternative provider |
| EMAIL_FROM / _NAME | SET | MISSING | — | yes | sender identity (founder@curvai.org) |

## Intelligence/data

| Variable | Local | Staging | Production | Required | Purpose |
|---|---|---|---|---|---|
| SERP_API_KEY | PLACEHOLDER | MISSING | — | optional | real SERP data (mock exists) |
| PAGE_SPEED_API_KEY | PLACEHOLDER | MISSING | — | optional | audit enrichment |

## Actionable gap summary

**Staging activation requires syncing exactly these local→AWS secrets:** `FAL_KEY`, `GEMINI_API_KEY`, `GOOGLE_CLIENT_ID/SECRET`, `META_APP_ID/SECRET`, `LINKEDIN_*`, `X_*`, `WHATSAPP_*`, `TELEGRAM_BOT_TOKEN`, `LINE_*` — plus newly generating `STRIPE_WEBHOOK_SECRET`, `RAZORPAY_WEBHOOK_SECRET` and configuring `SMTP_*`/`EMAIL_FROM` against Microsoft 365 (founder@curvai.org mailbox already exists).
