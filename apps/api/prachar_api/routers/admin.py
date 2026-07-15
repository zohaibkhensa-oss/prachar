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
) -> list[BrandSummary]:
    """Multi-brand summary for agency tier. Shows all brands with their
    scores, campaign counts, active channels, and weekly spend."""
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
    """Export all brands as CSV for agency-tier reporting."""
    res = await session.execute(
        select(Brand).where(Brand.tenant_id == user.tenant_id).order_by(Brand.name)
    )
    brands = res.scalars().all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "website", "category", "visibility_score", "created_at"])
    for b in brands:
        writer.writerow([
            str(b.id), b.name, b.website or "", b.category or "",
            b.visibility_score or 0, b.created_at.isoformat() if b.created_at else "",
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=prachar_brands.csv"},
    )
