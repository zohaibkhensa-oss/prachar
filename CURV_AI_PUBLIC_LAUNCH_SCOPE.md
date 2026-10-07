# CURV AI — Public Launch Scope

**Date:** 2026-10-06 · Principle: smallest capability set that makes CURV legitimately launchable. Not every integration.

## MUST HAVE

| Capability | Status | Required action |
|---|---|---|
| AI Brain (Orb, Runtime, Planner, 75 tools, Campaign Brain, Council, Consult, RAG, Creative Studio) | 🟢 LIVE | none — verified |
| Campaign intelligence (strategy→media plan→execution plan→learning) | 🟢 LIVE | none |
| Creative generation — LLM formats | 🟢 LIVE | none |
| Generative media (video+images) | 🟡 CREDENTIAL | sync `FAL_KEY` + `GEMINI_API_KEY` → staging secrets |
| ≥1 publishing channel | 🟡 CREDENTIAL | Meta + Google (creds exist locally) → staging |
| ≥1 advertising channel | 🟠 CODE+CRED | fix Meta `act_{id}` discovery + `fb_exchange_token`; sync `META_*` |
| Billing (checkout + entitlement) | 🟡 CREDENTIAL | webhook secrets only — code verified |
| Email | 🟡 CREDENTIAL | M365 SMTP env block |
| Analytics/audit funnel | 🟢 LIVE | none |
| Automation (dispatch + beats + weekly loop) | 🟢 LIVE | none |
| Auth/multi-tenant/RLS | 🟢 LIVE | none |

## SHOULD HAVE

- LinkedIn organic (creds exist) · X organic (creds exist) · WhatsApp broadcast (creds exist)
- Anthropic/OpenAI fallback verified as failover
- Frontend silent-MOCK removal (content page)
- `apps/web` retirement (vuln surface)

## CAN WAIT

- TikTok/Pinterest/Reddit/LINE/VK/Naver/Kakao, Google Ads + all other ads networks
- GA4/HubSpot/Mailchimp/Shopify/WordPress integrations
- Apple sign-in, SERP_API real data, Modal GPU svc, white-label agency tier polish

## Feasibility verdict

**Achievable with current architecture — zero new abstractions required.** Every MUST HAVE is either already live or gated solely by credential sync + one ~½-day Meta fix (ad-account discovery + long-lived tokens). The frozen architecture supports the launch scope as-is.
