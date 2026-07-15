from __future__ import annotations

import logging
import os
from typing import Any

from prachar_workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _s3_key(brand_id: str, week: str) -> str:
    return f"reports/{brand_id}/{week}.pdf"


def _save_local(path: str, data: bytes) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    return path


def _save_to_s3(key: str, data: bytes) -> str | None:
    try:
        from prachar_shared.config import get_settings

        settings = get_settings()
        if not settings.s3_access_key or not settings.s3_secret_key:
            return None
        import boto3  # type: ignore

        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )
        client.put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType="application/pdf")
        return key
    except Exception as exc:  # pragma: no cover - S3 optional in S0
        logger.warning("s3 upload failed: %s", exc)
        return None


@celery_app.task(
    name="prachar_workers.report.generate_pdf",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def generate_pdf(brand_id: str, week: str, score: dict[str, Any] | None = None) -> str:
    logger.info("generate_pdf brand=%s week=%s", brand_id, week)
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    score = score or {}
    overall = score.get("overall", 0.0)
    breakdown = score.get("breakdown", {}) or {}

    buf_path = f"./reports/{brand_id}/{week}.pdf"
    os.makedirs(os.path.dirname(buf_path), exist_ok=True)

    c = canvas.Canvas(buf_path, pagesize=A4)
    width, height = A4
    y = height - 20 * mm
    c.setFont("Helvetica-Bold", 20)
    c.drawString(20 * mm, y, f"Weekly Report — {brand_id}")
    y -= 10 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Week: {week}")
    y -= 12 * mm

    c.setFont("Helvetica-Bold", 36)
    c.drawString(20 * mm, y, f"Visibility Score: {overall:.1f}")
    y -= 14 * mm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Breakdown")
    y -= 7 * mm
    c.setFont("Helvetica", 10)
    for comp, val in breakdown.items():
        bar = "#" * int(val / 5)
        c.drawString(20 * mm, y, f"{comp}: {val:.1f}  {bar}")
        y -= 6 * mm

    y -= 4 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Top findings")
    y -= 7 * mm
    c.setFont("Helvetica", 10)
    for finding in (score.get("findings") or [])[:5]:
        c.drawString(20 * mm, y, f"- {finding}")
        y -= 6 * mm

    y -= 4 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Per-channel summary")
    y -= 7 * mm
    c.setFont("Helvetica", 10)
    for ch, info in (score.get("channels") or {}).items():
        c.drawString(20 * mm, y, f"{ch}: {info}")
        y -= 6 * mm

    c.showPage()
    c.save()

    with open(buf_path, "rb") as fh:
        data = fh.read()
    key = _s3_key(brand_id, week)
    s3 = _save_to_s3(key, data)
    if s3:
        return s3
    return _save_local(buf_path, data)


@celery_app.task(
    name="prachar_workers.report.send_digest",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def send_digest(brand_id: str, report_path: str) -> dict[str, Any]:
    logger.info("send_digest brand=%s report=%s", brand_id, report_path)
    # S0 stub: would send WhatsApp/email digest.
    return {"brand_id": brand_id, "report_path": report_path, "sent": False}
