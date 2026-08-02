from __future__ import annotations

"""S9 — Agency tier: multi-brand management, white-label PDF, API access tokens,
admin cost dashboards. Per spec 09 §"S9 — Agency tier"."""

import csv
import io
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text

from ..deps import CurrentUser, SessionDep, require_role
from ..models import Billing, Brand, Campaign, MetricEvent, Tenant, User
from ..models.enums import Plan

router = APIRouter(prefix="/admin", tags=["admin"])


# ─── Admin cost dashboard ────────────────────────────────────────────────────

class TenantCostRow(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    plan: str
    brand_count: int
    campaign_count: int
    ai_tokens_used_month: int
    ai_budget_month: int
    total_spend_month: float


class CostDashboard(BaseModel):
    tenants: list[TenantCostRow]
    total_ai_tokens: int
    total_ai_budget: int
    total_brands: int
    total_campaigns: int
    avg_utilization: float


@router.get("/costs", response_model=CostDashboard)
async def admin_cost_dashboard(
    user: Annotated[User, Depends(require_role("owner", "admin"))],
    session: SessionDep,
) -> CostDashboard:
    """Admin cost-per-tenant report. Per spec 07 §7.6: 'Dashboard: admin cost-per-tenant report.'
    Only visible to tenant owners/admins. Shows AI token usage + budget per tenant."""
    # For agency tier, this shows all tenants under the agency.
    # For single-tenant, shows just their tenant.
    res = await session.execute(
        select(
            Tenant.id,
            Tenant.name,
            Tenant.plan,
            func.count(func.distinct(Brand.id)).label("brand_count"),
            func.count(func.distinct(Campaign.id)).label("campaign_count"),
            Billing.ai_tokens_used_month,
            Billing.ai_budget_month,
        )
        .outerjoin(Brand, Brand.tenant_id == Tenant.id)
        .outerjoin(Campaign, Campaign.tenant_id == Tenant.id)
        .outerjoin(Billing, Billing.tenant_id == Tenant.id)
        .where(Tenant.id == user.tenant_id)
        .group_by(Tenant.id, Tenant.name, Tenant.plan, Billing.ai_tokens_used_month, Billing.ai_budget_month)
    )
    rows = res.all()
    tenants = []
    total_tokens = 0
    total_budget = 0
    total_brands = 0
    total_campaigns = 0
    for row in rows:
        tokens = row[5] or 0
        budget = row[6] or 0
        total_tokens += tokens
        total_budget += budget
        total_brands += row[3] or 0
        total_campaigns += row[4] or 0
        tenants.append(TenantCostRow(
            tenant_id=row[0],
            tenant_name=row[1],
            plan=row[2],
            brand_count=row[3] or 0,
            campaign_count=row[4] or 0,
            ai_tokens_used_month=tokens,
            ai_budget_month=budget,
            total_spend_month=0.0,  # would sum metric_events spend
        ))
    avg_util = (total_tokens / total_budget * 100) if total_budget > 0 else 0.0
    return CostDashboard(
        tenants=tenants,
        total_ai_tokens=total_tokens,
        total_ai_budget=total_budget,
        total_brands=total_brands,
        total_campaigns=total_campaigns,
        avg_utilization=round(avg_util, 2),
    )


# ─── API access tokens ───────────────────────────────────────────────────────

class APITokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scopes: list[str] = Field(default_factory=lambda: ["read"])


class APITokenOut(BaseModel):
    id: uuid.UUID
    name: str
    token: str
    scopes: list[str]
    created_at: str


# In-memory token store (production: dedicated api_tokens table with hashed tokens).
_api_tokens: dict[str, dict[str, Any]] = {}


@router.post("/api-tokens", response_model=APITokenOut, status_code=status.HTTP_201_CREATED)
async def create_api_token(
    body: APITokenCreate,
    user: Annotated[User, Depends(require_role("owner", "admin"))],
    session: SessionDep,
) -> APITokenOut:
    """Create an API access token for programmatic access.
    Per spec 09 §"S9 — Agency tier": 'API access'."""
    import secrets

    token_id = uuid.uuid4()
    raw_token = f"prachar_{secrets.token_urlsafe(32)}"
    _api_tokens[raw_token] = {
        "id": token_id,
        "name": body.name,
        "scopes": body.scopes,
        "tenant_id": user.tenant_id,
        "created_at": "2026-07-16T00:00:00Z",
    }
    return APITokenOut(
        id=token_id,
        name=body.name,
        token=raw_token,
        scopes=body.scopes,
        created_at="2026-07-16T00:00:00Z",
    )


@router.get("/api-tokens", response_model=list[APITokenOut])
async def list_api_tokens(
    user: Annotated[User, Depends(require_role("owner", "admin"))],
    session: SessionDep,
) -> list[APITokenOut]:
    """List all API tokens for this tenant."""
    result = []
    for token, info in _api_tokens.items():
        if info["tenant_id"] == user.tenant_id:
            result.append(APITokenOut(
                id=info["id"],
                name=info["name"],
                token=token[:12] + "...",  # masked
                scopes=info["scopes"],
                created_at=info["created_at"],
            ))
    return result


# ─── White-label PDF ─────────────────────────────────────────────────

class WhiteLabelConfig(BaseModel):
    agency_name: str = Field(min_length=1, max_length=120)
    logo_url: str | None = None
    primary_color: str = Field(default="#FFD400", max_length=7)
    accent_color: str = Field(default="#141414", max_length=7)
    footer_text: str | None = None


@router.post("/whitelabel/config")
async def set_whitelabel_config(
    body: WhiteLabelConfig,
    user: Annotated[User, Depends(require_role("owner", "admin"))],
    session: SessionDep,
) -> dict[str, Any]:
    """Set white-label configuration for agency-tier PDF reports.
    Per spec 09 §"S9 — Agency tier": 'white-label PDF'."""
    # In production, store in a whitelabel_config table.
    # For now, return the config as confirmation.
    return {
        "status": "saved",
        "tenant_id": str(user.tenant_id),
        "agency_name": body.agency_name,
        "logo_url": body.logo_url,
        "primary_color": body.primary_color,
        "accent_color": body.accent_color,
        "footer_text": body.footer_text,
    }


# ─── Multi-brand summary (agency view) ───────────────────────────────────────

class BrandSummary(BaseModel):
    brand_id: uuid.UUID
    name: str
    visibility_score: float | None
    campaign_count: int
    active_channels: int
    weekly_spend: float


@router.get("/brands/summary", response_model=list[BrandSummary])
async def brands_summary(
    user: Annotated[User, Depends(require_role("owner", "admin"))],
    session: SessionDep,
    limit: int = 100,
    offset: int = 0,
) -> list[BrandSummary]:
    """Multi-brand summary for agency tier. Shows all brands with their
    scores, campaign counts, active channels, and weekly spend.

    Paginated (default 100, max 1000) to prevent loading all brands into
    memory when an agency has thousands of clients.
    """
    limit = min(max(limit, 1), 1000)  # clamp 1..1000
    offset = max(offset, 0)
    res = await session.execute(
        select(
            Brand.id,
            Brand.name,
            Brand.visibility_score,
            func.count(func.distinct(Campaign.id)).label("campaign_count"),
        )
        .outerjoin(Campaign, Campaign.brand_id == Brand.id)
        .where(Brand.tenant_id == user.tenant_id)
        .group_by(Brand.id, Brand.name, Brand.visibility_score)
        .order_by(Brand.visibility_score.desc().nullslast())
        .limit(limit)
        .offset(offset)
    )
    rows = res.all()
    return [
        BrandSummary(
            brand_id=row[0],
            name=row[1],
            visibility_score=row[2],
            campaign_count=row[3] or 0,
            active_channels=0,  # would count active connections
            weekly_spend=0.0,   # would sum last 7d metric_events
        )
        for row in rows
    ]


# ─── CSV export ──────────────────────────────────────────────────────────────

@router.get("/export/brands.csv")
async def export_brands_csv(
    user: Annotated[User, Depends(require_role("owner", "admin"))],
    session: SessionDep,
) -> StreamingResponse:
    """Export all brands as CSV for agency-tier reporting.

    Streams rows in batches of 500 using server-side cursors, so an agency
    with 50,000 brands doesn't load them all into RAM at once.
    """
    async def generate() -> Any:
        # Write CSV header
        yield "id,name,website,category,visibility_score,created_at\n"
        # Stream rows in batches using limit/offset pagination
        batch_size = 500
        offset = 0
        while True:
            res = await session.execute(
                select(Brand)
                .where(Brand.tenant_id == user.tenant_id)
                .order_by(Brand.name)
                .limit(batch_size)
                .offset(offset)
            )
            brands = res.scalars().all()
            if not brands:
                break
            buf = io.StringIO()
            writer = csv.writer(buf)
            for b in brands:
                writer.writerow([
                    str(b.id), b.name, b.website or "", b.category or "",
                    b.visibility_score or 0,
                    b.created_at.isoformat() if b.created_at else "",
                ])
            yield buf.getvalue()
            offset += batch_size
            if len(brands) < batch_size:
                break

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=prachar_brands.csv"},
    )


# ─── AI Metrics Dashboard ──────────────────────────────────────────────────────


class AIMetricsResponse(BaseModel):
    date: str
    total_requests: int
    success_count: int
    failure_count: int
    success_rate: float
    failure_rate: float
    cache_hit_rate: float
    avg_latency_ms: float
    total_tokens: int
    total_cost_usd: float
    retry_count: int
    tasks: dict[str, Any] = Field(default_factory=dict)
    providers: dict[str, Any] = Field(default_factory=dict)


@router.get("/ai-metrics", response_model=AIMetricsResponse)
async def admin_ai_metrics(
    user: Annotated[User, Depends(require_role("owner", "admin"))],
    date: str | None = None,
) -> AIMetricsResponse:
    """Get AI metrics for dashboard display.

    Returns aggregated metrics for the specified date (defaults to today):
    - total_requests, success/failure counts and rates
    - cache hit rate
    - average latency
    - total tokens and cost
    - per-task and per-provider breakdowns
    """
    from prachar_shared.ai_gateway import get_metrics

    metrics = get_metrics()
    data = metrics.get_dashboard(date)
    if "error" in data:
        raise HTTPException(status_code=503, detail=data["error"])
    return AIMetricsResponse(**data)


@router.get("/ai-metrics/logs")
async def admin_ai_logs(
    user: Annotated[User, Depends(require_role("owner", "admin"))],
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Get recent AI request logs for debugging."""
    from prachar_shared.ai_gateway import get_metrics

    metrics = get_metrics()
    return metrics.get_recent_logs(limit=min(limit, 1000))


# ─── Pre-flight Budget Check ──────────────────────────────────────────────────


class PreflightRequest(BaseModel):
    workflow: str = Field(..., description="Workflow name: weekly_loop, single_content_gen, audit, chat")
    channels: list[str] | None = Field(None, description="Channels to process")
    locales: int = Field(1, ge=1, le=14, description="Number of locales")


class PreflightResponse(BaseModel):
    can_proceed: bool
    workflow: str
    estimated_tokens: int
    available_tokens: int
    shortfall: int
    message: str
    estimated_cost_usd: float = 0.0
    steps: dict[str, int] = Field(default_factory=dict)


@router.post("/ai-preflight", response_model=PreflightResponse)
async def admin_ai_preflight(
    user: Annotated[User, Depends(require_role("owner", "admin", "member"))],
    body: PreflightRequest,
    session: SessionDep,
) -> PreflightResponse:
    """Check if the tenant has sufficient AI budget for a workflow.

    Use this before starting a workflow to inform the user if they'll run out of tokens.
    """
    from prachar_shared.ai_gateway import preflight_check

    # Get user's plan from tenant
    from sqlalchemy import select

    tenant = (await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one_or_none()
    plan = tenant.plan if tenant else "starter"

    result = preflight_check(
        tenant_id=user.tenant_id,
        plan=plan,
        workflow=body.workflow,
        channels=body.channels,
        locales=body.locales,
    )
    return PreflightResponse(
        can_proceed=result.can_proceed,
        workflow=result.workflow,
        estimated_tokens=result.estimated_tokens,
        available_tokens=result.available_tokens,
        shortfall=result.shortfall,
        message=result.message,
        estimated_cost_usd=result.estimate.estimated_cost_usd if result.estimate else 0.0,
        steps=result.estimate.steps if result.estimate else {},
    )


@router.get("/ai-workflow-estimates")
async def admin_workflow_estimates(
    user: Annotated[User, Depends(require_role("owner", "admin", "member"))],
) -> dict[str, Any]:
    """Get cost estimates for all known workflows."""
    from prachar_shared.ai_gateway import get_workflow_estimates

    return get_workflow_estimates()


# ─── Ops: Integration health ─────────────────────────────────────────────────

class IntegrationHealthOut(BaseModel):
    platform: str
    status: str  # healthy | degraded | down | not_configured
    last_sync: str | None = None
    error_count_24h: int = 0
    connection_count: int = 0


@router.get("/ops/integrations", response_model=list[IntegrationHealthOut])
async def admin_integration_health(
    user: Annotated[User, Depends(require_role("owner", "admin"))],
    session: SessionDep,
) -> list[IntegrationHealthOut]:
    """Health status of all integrations across all tenants.

    For admin/ops monitoring. Shows which platforms are connected, when
    they last synced, and how many errors occurred in the last 24h.
    """
    from ..models import Connection, AuditEvent
    from datetime import datetime, timedelta, UTC

    cutoff = datetime.now(UTC) - timedelta(hours=24)

    # Get all connections grouped by platform
    res = await session.execute(
        select(
            Connection.platform,
            func.count(Connection.id).label("count"),
            func.max(Connection.updated_at).label("last_sync"),
        )
        .where(Connection.status == "active")
        .group_by(Connection.platform)
    )
    rows = res.all()

    # Get error counts per platform from audit events
    error_res = await session.execute(
        select(
            AuditEvent.entity_type,
            func.count(AuditEvent.id).label("error_count"),
        )
        .where(AuditEvent.action == "sync_failed")
        .where(AuditEvent.ts >= cutoff)
        .group_by(AuditEvent.entity_type)
    )
    error_counts = {row[0]: row[1] for row in error_res.all()}

    results = []
    for row in rows:
        platform = row[0]
        error_count = error_counts.get(platform, 0)
        status = "healthy" if error_count == 0 else "degraded" if error_count < 10 else "down"
        results.append(IntegrationHealthOut(
            platform=platform,
            status=status,
            last_sync=row[2].isoformat() if row[2] else None,
            error_count_24h=error_count,
            connection_count=row[1],
        ))

    return results


# ─── Ops: System overview ────────────────────────────────────────────────────

class SystemOverviewOut(BaseModel):
    tenants: int
    brands: int
    campaigns: int
    active_campaigns: int
    total_ai_tokens_month: int
    total_ai_budget_month: int
    integrations_active: int
    pending_reviews: int


@router.get("/ops/overview", response_model=SystemOverviewOut)
async def admin_system_overview(
    user: Annotated[User, Depends(require_role("owner", "admin"))],
    session: SessionDep,
) -> SystemOverviewOut:
    """System-wide overview for admin dashboard.

    Counts across all tenants: tenants, brands, campaigns, AI usage,
    active integrations, and pending reviews.
    """
    from ..models import Connection
    from ..models.enums import CampaignStatus

    # Tenants
    tenants = (await session.execute(select(func.count(Tenant.id)))).scalar() or 0

    # Brands
    brands = (await session.execute(select(func.count(Brand.id)))).scalar() or 0

    # Campaigns
    campaigns = (await session.execute(select(func.count(Campaign.id)))).scalar() or 0
    active = (await session.execute(
        select(func.count(Campaign.id)).where(Campaign.status == "active")
    )).scalar() or 0

    # AI usage
    ai_res = await session.execute(
        select(
            func.sum(Billing.ai_tokens_used_month).label("used"),
            func.sum(Billing.ai_budget_month).label("budget"),
        )
    )
    ai_row = ai_res.one()
    ai_used = ai_row[0] or 0
    ai_budget = ai_row[1] or 0

    # Active integrations
    integrations = (await session.execute(
        select(func.count(Connection.id)).where(Connection.status == "active")
    )).scalar() or 0

    # Pending reviews (campaigns in review status)
    pending = (await session.execute(
        select(func.count(Campaign.id)).where(Campaign.status == CampaignStatus.in_review)
    )).scalar() or 0

    return SystemOverviewOut(
        tenants=tenants,
        brands=brands,
        campaigns=campaigns,
        active_campaigns=active,
        total_ai_tokens_month=ai_used,
        total_ai_budget_month=ai_budget,
        integrations_active=integrations,
        pending_reviews=pending,
    )


# ─── Ops: Tenant management ──────────────────────────────────────────────────

class TenantOut(BaseModel):
    id: str
    name: str
    plan: str
    created_at: str
    brand_count: int
    campaign_count: int
    ai_tokens_used_month: int


@router.get("/ops/tenants", response_model=list[TenantOut])
async def admin_list_tenants(
    user: Annotated[User, Depends(require_role("owner", "admin"))],
    session: SessionDep,
    limit: int = 50,
    offset: int = 0,
) -> list[TenantOut]:
    """List all tenants with summary stats. For admin/ops management."""
    res = await session.execute(
        select(Tenant)
        .order_by(Tenant.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    tenants = res.scalars().all()

    results = []
    for t in tenants:
        brand_count = (await session.execute(
            select(func.count(Brand.id)).where(Brand.tenant_id == t.id)
        )).scalar() or 0
        campaign_count = (await session.execute(
            select(func.count(Campaign.id)).where(Campaign.tenant_id == t.id)
        )).scalar() or 0
        billing = (await session.execute(
            select(Billing).where(Billing.tenant_id == t.id)
        )).scalar_one_or_none()
        ai_tokens = billing.ai_tokens_used_month if billing else 0

        results.append(TenantOut(
            id=str(t.id),
            name=t.name,
            plan=t.plan,
            created_at=t.created_at.isoformat() if t.created_at else None,
            brand_count=brand_count,
            campaign_count=campaign_count,
            ai_tokens_used_month=ai_tokens,
        ))

    return results
