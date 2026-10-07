from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..deps import CurrentUser, SessionDep
from ..models import Report

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
            "status": "ready" if r.pdf_s3_key else "generating",
            "download_url": f"/reports/brands/{brand_id}/reports/{r.id}/download" if r.pdf_s3_key else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in res.scalars().all()
    ]


@router.get("/brands/{brand_id}/reports/{report_id}/download")
async def get_report_download_url(
    brand_id: uuid.UUID, report_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> dict[str, Any]:
    """Return a time-limited presigned download URL for the report PDF."""
    res = await session.execute(
        select(Report).where(
            Report.id == report_id,
            Report.brand_id == brand_id,
            Report.tenant_id == user.tenant_id,
        )
    )
    report = res.scalar_one_or_none()
    if report is None or not report.pdf_s3_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report PDF not found")

    try:
        import boto3
        from prachar_shared.config import get_settings

        s = get_settings()
        client = boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint,
            aws_access_key_id=s.s3_access_key,
            aws_secret_access_key=s.s3_secret_key,
            region_name=s.s3_region,
        )
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": s.s3_bucket, "Key": report.pdf_s3_key},
            ExpiresIn=3600,
        )
        return {"url": url, "expires_in": 3600}
    except Exception as exc:  # noqa: BLE001 — storage may be unconfigured locally
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"storage unavailable: {exc}") from exc
