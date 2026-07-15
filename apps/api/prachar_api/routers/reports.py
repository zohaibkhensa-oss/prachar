from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..deps import CurrentUser, SessionDep
from ..models import Brand, Report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/brands/{brand_id}/report/latest")
async def get_latest_report(brand_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> dict[str, Any]:
    res = await session.execute(
        select(Report)
        .where(Report.brand_id == brand_id, Report.tenant_id == user.tenant_id)
        .order_by(Report.created_at.desc())
        .limit(1)
    )
    report = res.scalar_one_or_none()
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no report found")
    return {
        "id": str(report.id),
        "brand_id": str(report.brand_id),
        "week": report.week,
        "pdf_s3_key": report.pdf_s3_key,
        "score_snapshot": report.score_snapshot,
        "sent_via": report.sent_via,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


@router.get("/brands/{brand_id}/reports")
async def list_reports(brand_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> list[dict[str, Any]]:
    res = await session.execute(
        select(Report)
        .where(Report.brand_id == brand_id, Report.tenant_id == user.tenant_id)
        .order_by(Report.created_at.desc())
    )
    return [
        {
            "id": str(r.id),
            "week": r.week,
            "pdf_s3_key": r.pdf_s3_key,
            "score_snapshot": r.score_snapshot,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in res.scalars().all()
    ]
