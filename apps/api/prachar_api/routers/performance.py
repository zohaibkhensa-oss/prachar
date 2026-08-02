"""Performance analysis router (P4.3).

Exposes ``GET /performance/{campaign_id}`` which runs the
``PerformanceEngine`` against the campaign's ``CampaignPerformance`` rows
and returns a ``PerformanceSummary`` describing what happened.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..deps import CurrentUser, SessionDep
from ..models import Campaign
from prachar_shared.marketing_intelligence.performance_engine import (
    PerformanceEngine,
    PerformanceSummary,
)

router = APIRouter(prefix="/performance", tags=["performance"])


async def _get_tenant_campaign(
    session: SessionDep, campaign_id: uuid.UUID, tenant_id: uuid.UUID
) -> Campaign:
    """Return the campaign if it belongs to the tenant, else 404."""
    res = await session.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant_id)
    )
    camp = res.scalar_one_or_none()
    if camp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "campaign not found")
    return camp


@router.get("/{campaign_id}", response_model=dict[str, Any])
async def analyse_performance(
    campaign_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    days: int = 30,
) -> dict[str, Any]:
    """Return a performance analysis summary for the campaign.

    Requires authentication.  Returns 404 if the campaign does not exist or
    belongs to a different tenant.
    """
    await _get_tenant_campaign(session, campaign_id, user.tenant_id)

    engine = PerformanceEngine(session_factory=lambda: session)
    summary: PerformanceSummary = await engine.analyse(str(campaign_id), days=days)
    return summary.to_dict()


@router.get("/{campaign_id}/why", response_model=dict[str, Any])
async def explain_performance(
    campaign_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    days: int = 30,
) -> dict[str, Any]:
    """Return root-cause analysis ("Why") for the campaign's performance.

    Requires authentication.  Returns 404 if the campaign does not exist or
    belongs to a different tenant.
    """
    await _get_tenant_campaign(session, campaign_id, user.tenant_id)

    engine = PerformanceEngine(session_factory=lambda: session)
    return await engine.explain(str(campaign_id), days=days)


@router.get("/{campaign_id}/next", response_model=dict[str, Any])
async def recommend_performance(
    campaign_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    days: int = 30,
) -> dict[str, Any]:
    """Return recommendations ("What next") for the campaign.

    Requires authentication.  Returns 404 if the campaign does not exist or
    belongs to a different tenant.
    """
    await _get_tenant_campaign(session, campaign_id, user.tenant_id)

    engine = PerformanceEngine(session_factory=lambda: session)
    return await engine.recommend(str(campaign_id), days=days)


@router.get("/{campaign_id}/story", response_model=dict[str, Any])
async def story_performance(
    campaign_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    days: int = 30,
) -> dict[str, Any]:
    """Return a narrative *story* for the campaign's performance.

    Instead of a dashboard, this returns a human-readable story with a
    headline, paragraphs, highlights, platform breakdown, and time insights.
    All metrics are de-jargonised.

    The platform breakdown includes live data from all connected platforms
    (reach, engagement rate, conversion rate, spend, ROAS per platform).

    Requires authentication.  Returns 404 if the campaign does not exist or
    belongs to a different tenant.
    """
    await _get_tenant_campaign(session, campaign_id, user.tenant_id)

    engine = PerformanceEngine(session_factory=lambda: session)
    return await engine.tell_story(str(campaign_id), days=days)
