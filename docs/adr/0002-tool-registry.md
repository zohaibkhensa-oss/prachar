# ADR-0002: Tool Registry Design

**Status:** Accepted
**Date:** 2026-08-02

## Context

The Runtime needs to call backend functions (query performance, generate creatives, search knowledge, etc.) in a uniform way. Tools must be discoverable, typed, cost-estimated, and retryable. The Orb needs to know what tools exist so it can plan execution graphs.

## Decision

A `ToolRegistry` holds `Tool` instances. Each Tool has:

- `name` — dotted identifier (e.g., `performance.story`, `knowledge.search`)
- `category` — ANALYTICS, CREATIVE, KNOWLEDGE, AUTOMATION, etc.
- `description` — natural language description for the planner
- `input_schema` — dict of required/optional parameters
- `output_schema` — dict describing the return shape
- `cost_estimate` — estimated latency, token cost, quality score
- `handler` — async callable that executes the tool

Tools are registered at startup. The planner sees the full registry and selects tools based on intent + context. The executor calls tools with retries (max 2).

## Current Registry (30 tools)

| Category | Tools |
|----------|-------|
| CONVERSATION | `chat.respond` |
| CAMPAIGN | `campaign_brain.analyse`, `campaign_brain.strategy`, `campaign_brain.creative`, `campaign_brain.media`, `campaign_brain.full_campaign` |
| CONSULT | `consult.understand` |
| COUNCIL | `council.review`, `council.history` |
| CREATIVE | `creative_studio.generate`, `creative_studio.generate_image`, `video_gen.generate` |
| KNOWLEDGE | `knowledge.search` |
| MEMORY | `memory.retrieve`, `memory.update` |
| PERFORMANCE | `performance.story`, `performance.why`, `performance.next` |
| REVIEW | `review.list`, `review.publish` |
| INTEGRATIONS | `integrations.list` |
| AUDIT | `audit.run` |
| ATTRIBUTION | `attribution.query` |
| TIMELINE | `timeline.query` |
| WORKFLOW | `workflow.query` |
| BILLING | `billing.usage` |
| DOMAIN | `domain_pack.apply` |
| CREATOR | `creator.repurpose`, `creator.youtube_plan` |
| PROACTIVE | `proactive.notifications` |

## Consequences

- Adding a new AI capability = adding a Tool + registering it. No runtime changes.
- The planner automatically discovers new tools.
- Tools are isolated — failures don't crash the runtime.
- Cost estimation enables budget-aware planning.

## Frozen

The Tool Registry pattern is frozen. New capabilities must be added as tools, not as new execution mechanisms.
