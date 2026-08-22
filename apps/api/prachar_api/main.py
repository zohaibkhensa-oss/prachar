from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .middleware import TenantMiddleware, SecurityHeadersMiddleware, GlobalRateLimitMiddleware, RequestMetricsMiddleware
from .routers import admin, agency_council, analytics, attribution, auth, audits, billing, brands, campaign_brain, campaigns, chat, connections, consult, creative_studio, creator, integrations, knowledge, misc, performance, proactive, reports, review, runtime, unified_consult, video_gen, webhooks
from .routers import admin_runtime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("prachar.api")


def create_app() -> FastAPI:
    app = FastAPI(
        title="CURV AI API",
        version="1.0.0",
        description="""# CURV AI API

AI-driven global advertising agency platform.

## Authentication

All endpoints (except `/auth/*` and `/health*`) require a JWT bearer token:

```
Authorization: Bearer <access_token>
```

Tokens are obtained via `POST /auth/login` or `POST /auth/register`.

## Rate Limiting

- **Authenticated**: 300 req/min per IP
- **Unauthenticated**: 60 req/min per IP
- **Health checks**: 1200 req/min per IP
- **Auth endpoints**: 5 req/min per IP (brute-force protection)

Exceeding the limit returns `429 Too Many Requests` with a `Retry-After` header.

## Multi-Tenancy

Every request is scoped to the tenant extracted from the JWT.
Row-Level Security (RLS) in PostgreSQL enforces isolation at the database level.

## Orb Runtime

The Orb (`/runtime/invoke`) is the AI execution layer:
1. Classifies intent
2. Plans a tool execution graph
3. Loads relevant context (16 providers)
4. Executes tools (30 tools)
5. Composes a response
6. Streams events via SSE

## Webhooks

Register webhooks at `POST /webhooks` to receive real-time events.

## Architecture

See `docs/adr/` for Architecture Decision Records.
See `LAUNCH_READINESS.md` for the feature matrix.
""",
        contact={
            "name": "CURV AI Support",
            "url": "https://curv.ai/support",
            "email": "support@curv.ai",
        },
        license_info={
            "name": "Proprietary",
            "url": "https://curv.ai/terms",
        },
        openapi_tags=[
            {"name": "meta", "description": "Health checks and metrics"},
            {"name": "auth", "description": "Authentication (login, register, refresh, logout)"},
            {"name": "brands", "description": "Brand management (create, list, update, delete)"},
            {"name": "audits", "description": "Visibility audit (free funnel + paid deep audit)"},
            {"name": "connections", "description": "Platform connections (OAuth, channels, ad networks)"},
            {"name": "campaigns", "description": "Campaign management (create, list, approve, pause)"},
            {"name": "review", "description": "Review queue (pending approvals, publish/reject)"},
            {"name": "reports", "description": "Weekly performance reports (PDF, JSON)"},
            {"name": "attribution", "description": "Attribution tracking (touchpoints, conversions, ROI)"},
            {"name": "analytics", "description": "Analytics dashboard (metrics, trends, charts)"},
            {"name": "integrations", "description": "Integration marketplace (list, connect, disconnect)"},
            {"name": "webhooks", "description": "Webhook management (register, list, test)"},
            {"name": "knowledge", "description": "Knowledge Hub (upload, search, RAG)"},
            {"name": "admin", "description": "Admin operations (AI metrics, tenant management)"},
            {"name": "billing", "description": "Billing (subscription, usage, invoices)"},
            {"name": "chat", "description": "BRO chat (conversational AI assistant)"},
            {"name": "video-gen", "description": "AI video generation"},
            {"name": "campaign-brain", "description": "Marketing Intelligence Engine (9 engines)"},
            {"name": "agency-council", "description": "Agency Council (9 AI Directors + Consensus)"},
            {"name": "consult", "description": "Conversational onboarding (business → campaign)"},
            {"name": "creative-studio", "description": "Creative generation (ad copy, headlines, variants)"},
            {"name": "creator", "description": "Creator Growth (YouTube, repurpose, content plans)"},
            {"name": "performance", "description": "Performance Engine (story, why, next actions)"},
            {"name": "proactive", "description": "Proactive notifications and recommendations"},
            {"name": "runtime", "description": "Orb Runtime (invoke, sessions, events)"},
            {"name": "unified-consult", "description": "Universal consult (all domain packs)"},
        ],
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000", "http://127.0.0.1:3000",
            "http://localhost:3001", "http://127.0.0.1:3001",
            "http://localhost:3002", "http://127.0.0.1:3002",
            "https://prachar-web.onrender.com",
            "https://prachar.app",
            "https://www.prachar.app",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TenantMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(GlobalRateLimitMiddleware)
    app.add_middleware(RequestMetricsMiddleware)
    app.include_router(misc.router)
    app.include_router(auth.router)
    app.include_router(brands.router)
    app.include_router(audits.router)
    app.include_router(connections.router)
    app.include_router(campaigns.router)
    app.include_router(review.router)
    app.include_router(reports.router)
    app.include_router(attribution.router)
    app.include_router(analytics.router)
    app.include_router(integrations.router)
    app.include_router(webhooks.router)
    app.include_router(knowledge.router)
    app.include_router(admin.router)
    app.include_router(billing.router)
    app.include_router(chat.router)
    app.include_router(video_gen.router)
    app.include_router(campaign_brain.router)
    app.include_router(agency_council.router)
    app.include_router(consult.router)
    app.include_router(creative_studio.router)
    app.include_router(creator.router)
    app.include_router(unified_consult.router)
    app.include_router(performance.router)
    app.include_router(proactive.router)
    app.include_router(runtime.router)
    app.include_router(runtime.timeline_router)
    app.include_router(runtime.dashboard_router)
    app.include_router(admin_runtime.router)
    return app


app = create_app()
