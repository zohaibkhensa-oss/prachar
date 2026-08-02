# ADR-0005: Integration Framework

**Status:** Accepted
**Date:** 2026-08-02

## Context

PRACHAR AI connects to 20+ external platforms (Google, Meta, TikTok, YouTube, LinkedIn, Pinterest, X, WhatsApp, Telegram, LINE, VK, Reddit, Naver, Microsoft Ads, Snap Ads, Yandex, etc.). Platform logic must not leak into the core system. Adding a new platform must not require changes to the runtime, planner, or context builder.

## Decision

Two adapter abstractions:

1. **ChannelAdapter** (organic) — publish content, fetch insights, manage presence
2. **AdNetworkAdapter** (paid) — create campaigns, manage budgets/bids, upload creatives, fetch stats

Every adapter implements a common interface. The Integration Framework provides:
- OAuth flow management (start, callback, refresh)
- Connection persistence (`Connection` model)
- Sync policies (how often to pull data, what to pull)
- Secrets vault (OAuth tokens encrypted at rest)
- Health checks per integration
- Webhook ingestion

Adding a new platform = implementing the adapter interface + registering it. Zero core changes.

## Current Adapters (20+)

**Organic:** Google Search, GMB, YouTube, Instagram, Facebook, TikTok, LinkedIn, Pinterest, X/Twitter, WhatsApp, Telegram, LINE, VK, Reddit, Naver
**Paid:** Google Ads, Meta Ads, TikTok Ads, Microsoft Ads, Snap Ads, Reddit Ads, Yandex Direct

## Consequences

- Platform logic is fully isolated
- New platforms are added in days, not weeks
- The Orb sees integrations via `IntegrationsProvider` + `integrations.list` tool
- Failed integrations are visible in health checks
- Secrets never appear in logs or code

## Frozen

The Integration Framework is frozen. New platforms must be added as adapters, not as inline platform code. No exceptions.
