from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..audit import log_audit
from ..deps import CurrentUser, SessionDep
from ..models import Actor, Campaign
from ..schemas import CampaignIn, CampaignOut

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
async def create_campaign(body: CampaignIn, user: CurrentUser, session: SessionDep) -> CampaignOut:
    camp = Campaign(tenant_id=user.tenant_id, **body.model_dump())
    session.add(camp)
    await session.flush()
    await log_audit(
        session, tenant_id=user.tenant_id, actor=Actor.user, action="campaign.create",
        entity_type="campaign", entity_id=camp.id,
        payload={"network": camp.network, "budget_daily": camp.budget_daily, "dry_run": camp.dry_run},
    )
    await session.commit()
    return CampaignOut.model_validate(camp)


@router.get("", response_model=list[CampaignOut])
async def list_campaigns(user: CurrentUser, session: SessionDep) -> list[CampaignOut]:
    res = await session.execute(
        select(Campaign).where(Campaign.tenant_id == user.tenant_id).order_by(Campaign.created_at.desc())
    )
    return [CampaignOut.model_validate(c) for c in res.scalars().all()]


@router.post("/{campaign_id}/pause", response_model=CampaignOut)
async def pause(campaign_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> CampaignOut:
    res = await session.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.tenant_id == user.tenant_id)
    )
    camp = res.scalar_one_or_none()
    if camp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "campaign not found")
    camp.status = "paused"
    await log_audit(
        session, tenant_id=user.tenant_id, actor=Actor.user, action="campaign.pause",
        entity_type="campaign", entity_id=camp.id,
    )
    await session.commit()
    return CampaignOut.model_validate(camp)


@router.post("/{campaign_id}/resume", response_model=CampaignOut)
async def resume(campaign_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> CampaignOut:
    res = await session.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.tenant_id == user.tenant_id)
    )
    camp = res.scalar_one_or_none()
    if camp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "campaign not found")
    camp.status = "active"
    await log_audit(
        session, tenant_id=user.tenant_id, actor=Actor.user, action="campaign.resume",
        entity_type="campaign", entity_id=camp.id,
    )
    await session.commit()
    return CampaignOut.model_validate(camp)
