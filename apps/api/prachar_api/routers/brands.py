from __future__ import annotations

import uuid
from datetime import UTC
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from ..audit import log_audit
from ..deps import CurrentUser, SessionDep
from ..models import Actor, Brand, Connection, ContentItem, PolicyStatus
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


@router.get("/{brand_id}/content")
async def list_brand_content(brand_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> list[dict]:
    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
    )
    if res.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")
    res = await session.execute(
        select(ContentItem)
        .where(ContentItem.brand_id == brand_id, ContentItem.tenant_id == user.tenant_id)
        .order_by(ContentItem.created_at.desc())
        .limit(200)
    )
    out = []
    for c in res.scalars().all():
        payload = c.payload or {}
        out.append({
            "id": str(c.id),
            "type": "copy",
            "locale": c.locale or "en",
            "channel": c.channel,
            "variant_group": str(c.parent_id or c.id),
            "policy_status": c.policy_status.value if hasattr(c.policy_status, "value") else str(c.policy_status),
            "copy": payload.get("copy") or payload.get("text") or "",
            "image_url": payload.get("image_url") or "",
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return out


# ─── Metrics summary (dashboard) ─────────────────────────────────────────────


@router.get("/{brand_id}/metrics/summary")
async def brand_metrics_summary(
    brand_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    days: int = 30,
) -> dict:
    """Real aggregation over metric_events: current-period totals, previous-
    period comparison, and a daily series per metric. Empty when no telemetry
    has been collected yet — the UI must not invent figures."""
    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
    )
    if res.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")

    from datetime import datetime, timedelta

    from sqlalchemy import func

    from ..models import MetricEvent

    now = datetime.now(UTC)
    start = now - timedelta(days=max(1, min(days, 365)))
    prev_start = start - (now - start)

    rows = await session.execute(
        select(
            MetricEvent.metric,
            func.date_trunc("day", MetricEvent.ts).label("d"),
            func.sum(MetricEvent.value),
        )
        .where(
            MetricEvent.brand_id == brand_id,
            MetricEvent.tenant_id == user.tenant_id,
            MetricEvent.ts >= prev_start,
        )
        .group_by(MetricEvent.metric, func.date_trunc("day", MetricEvent.ts))
        .order_by(func.date_trunc("day", MetricEvent.ts))
    )

    totals: dict[str, dict[str, float]] = {}
    series: dict[str, dict[str, float]] = {}
    for metric, day, value in rows.all():
        t = totals.setdefault(metric, {"current": 0.0, "previous": 0.0})
        bucket = "current" if day >= start else "previous"
        t[bucket] += float(value or 0)
        if day >= start:
            series.setdefault(metric, {})[day.date().isoformat()] = (
                series.setdefault(metric, {}).get(day.date().isoformat(), 0.0) + float(value or 0)
            )

    return {
        "days": days,
        "period_start": start.isoformat(),
        "totals": totals,
        "series": {
            m: [{"date": d, "value": v} for d, v in sorted(s.items())]
            for m, s in series.items()
        },
    }


class ContentCreateIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    channel: str = Field(min_length=1, max_length=40)
    copy_: str = Field(default="", alias="copy")
    image_url: str | None = None
    locale: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/{brand_id}/content", status_code=status.HTTP_201_CREATED)
async def create_brand_content(
    brand_id: uuid.UUID, body: ContentCreateIn, user: CurrentUser, session: SessionDep
) -> dict:
    """Save a generated post/content item as a draft (policy pending)."""
    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
    )
    if res.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")
    payload = dict(body.payload)
    if body.copy_:
        payload.setdefault("copy", body.copy_)
    if body.image_url:
        payload.setdefault("image_url", body.image_url)
    item = ContentItem(
        brand_id=brand_id,
        tenant_id=user.tenant_id,
        channel=body.channel,
        locale=body.locale,
        payload=payload,
        policy_status=PolicyStatus.pending,
    )
    session.add(item)
    await session.flush()
    await log_audit(
        session, tenant_id=user.tenant_id, actor=Actor.user, action="content.draft",
        entity_type="content_item", entity_id=item.id,
        payload={"channel": body.channel, "brand_id": str(brand_id)},
    )
    await session.commit()
    return {"id": str(item.id), "status": "draft", "channel": body.channel}


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


# ─── Quick post: media upload + publish ──────────────────────────────────────


@router.post("/{brand_id}/media/upload")
async def upload_media(
    brand_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    file: UploadFile = File(...),
) -> dict:
    """Upload an image/video for publishing. Stored in S3, returned as a
    presigned URL (platforms fetch it at publish time — 6h expiry is fine)."""
    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
    )
    if res.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")

    file_bytes = await file.read()
    if len(file_bytes) > 200 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "file too large (200MB max)")

    from prachar_shared.config import get_settings
    s = get_settings()

    import boto3
    # Explicit static keys (local/MinIO) or default chain (ECS task role →
    # prachar-staging-storage is already permitted via iam:prachar-ecs-s3-access)
    kwargs: dict = {}
    if s.s3_access_key and s.s3_secret_key:
        kwargs.update(
            endpoint_url=s.s3_endpoint if s.s3_endpoint.startswith("http") else None,
            aws_access_key_id=s.s3_access_key,
            aws_secret_access_key=s.s3_secret_key,
        )
    if s.s3_region:
        kwargs["region_name"] = s.s3_region
    client = boto3.client("s3", **kwargs)
    bucket = s.s3_bucket
    safe_name = (file.filename or "media").replace("/", "_")
    s3_key = f"posts/{user.tenant_id}/{brand_id}/{uuid.uuid4()}-{safe_name}"
    client.put_object(
        Bucket=bucket, Key=s3_key, Body=file_bytes,
        ContentType=file.content_type or "application/octet-stream",
    )
    media_url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": s3_key},
        ExpiresIn=6 * 3600,
    )
    return {"media_url": media_url, "s3_key": s3_key, "content_type": file.content_type}


class PublishIn(BaseModel):
    channel: str = Field(min_length=1, max_length=40)
    text: str = Field(default="", max_length=3000)
    media_url: str | None = None
    media_type: str = Field(default="image")  # image | video
    chat_id: str | None = None  # telegram


@router.post("/{brand_id}/publish")
async def publish_post(
    brand_id: uuid.UUID,
    body: PublishIn,
    user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Synchronous publish to a connected channel via its adapter."""
    import asyncio
    import json
    from datetime import UTC, datetime

    from prachar_shared.contracts import TokenSet
    from prachar_shared.security import decrypt_token

    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
    )
    if res.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")

    res = await session.execute(
        select(Connection).where(
            Connection.tenant_id == user.tenant_id,
            Connection.brand_id == brand_id,
            Connection.channel == body.channel,
            Connection.status == "active",
        )
    )
    conn = res.scalar_one_or_none()
    if conn is None or not conn.oauth_tokens_enc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{body.channel} is not connected")

    from .connections import _organic_adapter
    try:
        adapter = _organic_adapter("facebook" if body.channel == "instagram" else body.channel)
    except KeyError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unsupported channel: {body.channel}") from None

    bundle = json.loads(decrypt_token(conn.oauth_tokens_enc))
    md = bundle.get("metadata") or {}
    tokens = TokenSet(
        access_token=bundle["access_token"],
        refresh_token=bundle.get("refresh_token"),
        expires_at=datetime.fromisoformat(bundle["expires_at"]) if bundle.get("expires_at") else datetime.now(UTC),
        scopes=bundle.get("scopes") or [],
        metadata=md,
    )

    ch = body.channel
    if ch == "facebook":
        payload = {"message": body.text, "_page_access_token": md.get("page_access_token"), "_page_id": md.get("page_id")}
        if body.media_url:
            payload["picture"] = body.media_url
    elif ch == "x":
        payload = {"text": body.text}
    elif ch == "linkedin":
        payload = {"text": body.text, "_author_urn": f"urn:li:person:{md.get('member_id', '')}"}
        if body.media_url:
            payload["media_url"] = body.media_url
    elif ch == "instagram":
        if not body.media_url:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "instagram requires an image or video")
        payload = {
            "caption": body.text,
            "media_urls": [body.media_url],
            "post_type": "reels" if body.media_type == "video" else "feed",
            "_profile_metadata": md,
        }
    elif ch == "youtube":
        if not (body.media_url and body.media_type == "video"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "youtube requires a video file")
        payload = {
            "video_url": body.media_url,
            "title": body.text[:100] or "Untitled",
            "description": body.text,
            "privacy": "public",
        }
    elif ch == "telegram":
        if not body.chat_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "telegram requires a chat_id")
        payload = {"text": body.text, "chat_id": body.chat_id, "media_type": "photo" if body.media_url else "none", "media_url": body.media_url or ""}
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"publishing to {ch} is not supported yet")

    try:
        if asyncio.iscoroutinefunction(adapter.publish):
            published = await adapter.publish(tokens, payload)
        else:
            published = await asyncio.to_thread(adapter.publish, tokens, payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)[:300]) from exc

    item = ContentItem(
        tenant_id=user.tenant_id, brand_id=brand_id, channel=ch,
        payload={"copy": body.text, "image_url": body.media_url, "published_ref": published.native_id},
        policy_status=PolicyStatus.passed,
    )
    session.add(item)
    await log_audit(
        session, tenant_id=user.tenant_id, actor=Actor.user, action="content.publish",
        entity_type="channel", entity_id=None,
        payload={"channel": ch, "native_id": published.native_id, "brand_id": str(brand_id)},
    )
    return {
        "ok": True,
        "channel": published.channel,
        "native_id": published.native_id,
        "url": published.url,
        "published_at": published.published_at.isoformat(),
    }
