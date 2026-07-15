from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from ..audit import log_audit
from ..deps import CurrentUser, SessionDep
from ..models import Actor, Brand
from ..schemas import BrandIn, BrandOut, VisibilityScoreOut

router = APIRouter(prefix="/brands", tags=["brands"])


@router.post("", response_model=BrandOut, status_code=status.HTTP_201_CREATED)
async def create_brand(body: BrandIn, user: CurrentUser, session: SessionDep) -> BrandOut:
    brand = Brand(tenant_id=user.tenant_id, **body.model_dump())
    session.add(brand)
    await session.flush()
    await log_audit(
        session, tenant_id=user.tenant_id, actor=Actor.user, action="brand.create",
        entity_type="brand", entity_id=brand.id, payload={"name": brand.name},
    )
    await session.commit()
    return BrandOut.model_validate(brand)


@router.get("", response_model=list[BrandOut])
async def list_brands(user: CurrentUser, session: SessionDep) -> list[BrandOut]:
    res = await session.execute(
        select(Brand).where(Brand.tenant_id == user.tenant_id).order_by(Brand.created_at.desc())
    )
    return [BrandOut.model_validate(b) for b in res.scalars().all()]


@router.get("/{brand_id}", response_model=BrandOut)
async def get_brand(brand_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> BrandOut:
    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
    )
    brand = res.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")
    return BrandOut.model_validate(brand)


@router.get("/{brand_id}/score", response_model=VisibilityScoreOut)
async def get_score(brand_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> VisibilityScoreOut:
    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
    )
    brand = res.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")
    # S0: return a stub score derived from brand.visibility_score (or zeros).
    overall = brand.visibility_score or 0.0
    return VisibilityScoreOut(
        overall=overall,
        organic_rank_index=overall * 0.35 / 0.85 if overall else 0.0,
        ai_citation_rate=overall * 0.15 / 0.85 if overall else 0.0,
        social_reach_index=overall * 0.25 / 0.85 if overall else 0.0,
        paid_efficiency=overall * 0.15 / 0.85 if overall else 0.0,
        momentum=overall * 0.10 / 0.85 if overall else 0.0,
        week="1970-W01",
        breakdown={
            "organic_rank_index": overall * 0.35 / 0.85 if overall else 0.0,
            "ai_citation_rate": overall * 0.15 / 0.85 if overall else 0.0,
            "social_reach_index": overall * 0.25 / 0.85 if overall else 0.0,
            "paid_efficiency": overall * 0.15 / 0.85 if overall else 0.0,
            "momentum": overall * 0.10 / 0.85 if overall else 0.0,
        },
    )
