# ADR-0003: Context Builder & Ranking

**Status:** Accepted
**Date:** 2026-08-02

## Context

The Orb needs relevant context to answer questions well. Loading everything is too expensive (token budget). Loading nothing produces poor answers. The system must adaptively select what context to load based on the user's message, rank it by relevance, and trim to fit a token budget.

## Decision

A `ContextBuilder` holds `ContextProvider` instances. Each provider:

- Has a `name` (e.g., "audit", "attribution", "timeline")
- Has `is_relevant(message, intent)` — returns True if the provider should load
- Has `async load(session, tenant_id, brand_id, message)` — returns a dict of context data

The builder:
1. Always loads "always-on" providers (capabilities, knowledge, marketing_intelligence)
2. Checks `is_relevant()` for each optional provider
3. Loads relevant providers in parallel
4. Wraps results in `EnrichedContext` with ranking scores
5. Trims to token budget (default 4000 tokens)
6. Logs `providers_used` for observability

Ranking uses: recency, relevance score, source authority, token cost. The context evaluation loop tracks whether loaded context was actually used in the response (feedback for adaptive learning).

## Current Providers (16/16 subsystems)

| Provider | Trigger | Always-on? |
|----------|---------|:----------:|
| CapabilityProvider | all | ✅ |
| KnowledgeContextProvider | all | ✅ |
| MarketingIntelligenceProvider | all | ✅ |
| CouncilMemoryProvider | "council", "review", "decision" | ❌ |
| IntegrationsProvider | "integration", "channel", "connect" | ❌ |
| PerformanceProvider | "performance", "campaign", "metric" | ❌ |
| ReviewProvider | "review", "approve", "publish" | ❌ |
| DomainPackProvider | "industry", "best practice", "domain" | ❌ |
| AuditContextProvider | "audit", "visibility", "seo", "score" | ❌ |
| AttributionContextProvider | "conversion", "roi", "revenue", "channel" | ❌ |
| TimelineContextProvider | "recently", "history", "what did you do" | ❌ |
| WorkflowContextProvider | "automation", "workflow", "rules" | ❌ |
| ReportsContextProvider | "report", "weekly summary", "results" | ❌ |
| BillingContextProvider | "billing", "plan", "subscription", "usage" | ❌ |
| CreativeStudioContextProvider | "creative", "ad copy", "headline", "variant" | ❌ |
| VideoGenContextProvider | "video", "reel", "image", "generate", "media" | ❌ |

## Consequences

- The Orb is aware of all 16 backend subsystems
- Context is loaded adaptively — only what's relevant
- Token budget is respected
- Feedback loop improves provider selection over time
- Adding awareness of a new subsystem = adding a ContextProvider. No runtime changes.

## Frozen

The Context Builder pattern is frozen. New subsystems must be exposed via a new ContextProvider, not a new context-loading mechanism.
