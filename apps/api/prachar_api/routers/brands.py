from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from ..audit import log_audit
from ..deps import CurrentUser, SessionDep, get_tenant_plan
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

    # Single expression object — separate date_trunc() calls compile to
    # different param nodes ($1 vs $5) which Postgres treats as different
    # expressions: the SELECT'd one is then "ungrouped" → GroupingError.
    day_expr = func.date_trunc("day", MetricEvent.ts).label("d")
    rows = await session.execute(
        select(
            MetricEvent.metric,
            day_expr,
            func.sum(MetricEvent.value),
        )
        .where(
            MetricEvent.brand_id == brand_id,
            MetricEvent.tenant_id == user.tenant_id,
            MetricEvent.ts >= prev_start,
        )
        .group_by(MetricEvent.metric, day_expr)
        .order_by(day_expr)
    )

    # Canonicalise provider metric names into the dashboard's four buckets.
    # (reach = impressions+views documented as "times content was seen";
    # engagements = likes/comments/shares; visits = clicks; spend = spend/cost)
    _BUCKETS = {
        "impressions": "impressions",
        "views": "impressions",
        "likes": "engagements",
        "comments": "engagements",
        "shares": "engagements",
        "saves": "engagements",
        "engagements": "engagements",
        "clicks": "clicks",
        "website_visits": "clicks",
        "spend": "spend",
        "cost": "spend",
    }

    totals: dict[str, dict[str, float]] = {}
    series: dict[str, dict[str, float]] = {}
    raw_metrics: set[str] = set()
    for metric, day, value in rows.all():
        canonical = _BUCKETS.get(metric)
        raw_metrics.add(metric)
        if canonical is None:
            continue
        t = totals.setdefault(canonical, {"current": 0.0, "previous": 0.0})
        bucket = "current" if day >= start else "previous"
        t[bucket] += float(value or 0)
        if day >= start:
            series.setdefault(canonical, {})[day.date().isoformat()] = (
                series.setdefault(canonical, {}).get(day.date().isoformat(), 0.0) + float(value or 0)
            )

    # When the last metrics.sync ran (empty if never)
    from ..models import AuditEvent
    sync_res = await session.execute(
        select(func.max(AuditEvent.ts)).where(
            AuditEvent.tenant_id == user.tenant_id,
            AuditEvent.action == "metrics.sync",
        )
    )
    last_synced = sync_res.scalar()

    return {
        "days": days,
        "period_start": start.isoformat(),
        "totals": totals,
        "series": {
            m: [{"date": d, "value": v} for d, v in sorted(s.items())]
            for m, s in series.items()
        },
        "last_synced": last_synced.isoformat() if last_synced else None,
        "raw_metrics": sorted(raw_metrics),
    }


# ─── Metrics sync (pull provider analytics → metric_events) ──────────────────


@router.post("/{brand_id}/metrics/sync")
async def brand_metrics_sync(
    brand_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> dict:
    """Pull the latest provider metrics for every active connection on this
    brand and persist them as MetricEvent rows.

    Idempotent per (channel, day): rows written by an earlier same-day sync
    are replaced, so repeated syncs never double-count. Provider calls run
    through the organic adapters — all platform logic stays in the adapter
    layer per architecture rules.
    """
    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
    )
    if res.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")

    from datetime import datetime, timedelta

    from sqlalchemy import delete, func

    from ..models import Connection, MetricEvent

    conns = (await session.execute(
        select(Connection).where(
            Connection.brand_id == brand_id,
            Connection.tenant_id == user.tenant_id,
            Connection.status == "active",
        )
    )).scalars().all()
    if not conns:
        conns = (await session.execute(
            select(Connection).where(
                Connection.tenant_id == user.tenant_id,
                Connection.status == "active",
            )
        )).scalars().all()
    if not conns:
        return {"ok": False, "reason": "no_connected_channels", "synced": []}

    import asyncio
    import json

    from prachar_shared.contracts import TokenSet
    from prachar_shared.security import decrypt_token

    from .connections import _organic_adapter

    since = datetime.now(UTC) - timedelta(days=30)
    today = datetime.now(UTC).date()
    results: list[dict] = []

    for conn in conns:
        ch = conn.channel
        try:
            adapter = _organic_adapter(ch)
        except HTTPException:
            results.append({"channel": ch, "status": "unsupported"})
            continue
        if not hasattr(adapter, "metrics") and not hasattr(adapter, "fetch_metrics"):
            results.append({"channel": ch, "status": "no_metrics_api"})
            continue

        try:
            bundle = json.loads(decrypt_token(conn.oauth_tokens_enc))
            tokens = TokenSet(
                access_token=bundle["access_token"],
                refresh_token=bundle.get("refresh_token"),
                expires_at=datetime.fromisoformat(bundle["expires_at"])
                    if bundle.get("expires_at") else datetime.now(UTC),
                scopes=bundle.get("scopes") or [],
                metadata=bundle.get("metadata") or {},
            )
            # refresh if expiring (same rule as publish)
            if tokens.expires_at <= datetime.now(UTC) + timedelta(seconds=30):
                rt = bundle.get("refresh_token")
                if rt and hasattr(adapter, "refresh_access_token"):
                    new_tokens = await asyncio.to_thread(adapter.refresh_access_token, rt)
                    bundle.update({
                        "access_token": new_tokens.access_token,
                        "refresh_token": new_tokens.refresh_token or rt,
                        "expires_at": new_tokens.expires_at.isoformat(),
                        "scopes": new_tokens.scopes,
                    })
                    from prachar_shared.security import encrypt_token
                    conn.oauth_tokens_enc = encrypt_token(json.dumps(bundle, default=str))
                    conn.expires_at = new_tokens.expires_at
                    await session.flush()
                    tokens = new_tokens

            fn = getattr(adapter, "metrics", None) or getattr(adapter, "fetch_metrics", None)
            if asyncio.iscoroutinefunction(fn):
                events = await fn(tokens, since)
            else:
                events = await asyncio.to_thread(fn, tokens, since)

            # Idempotent: replace today's rows for this channel before insert
            await session.execute(
                delete(MetricEvent).where(
                    MetricEvent.brand_id == brand_id,
                    MetricEvent.channel == ch,
                    func.date(MetricEvent.ts) == today,
                )
            )
            written = 0
            for ev in events or []:
                session.add(MetricEvent(
                    tenant_id=user.tenant_id,
                    brand_id=brand_id,
                    channel=ev.channel or ch,
                    entity_type=ev.entity_type,
                    entity_id=ev.entity_id,
                    metric=ev.metric,
                    value=ev.value,
                ))
                written += 1
            results.append({"channel": ch, "status": "ok", "events": written})
        except Exception as exc:  # noqa: BLE001 — isolate per channel
            results.append({"channel": ch, "status": "error", "error": str(exc)[:200]})

    await log_audit(
        session, tenant_id=user.tenant_id, actor=Actor.user,
        action="metrics.sync", entity_type="brand", entity_id=str(brand_id),
        payload={"results": results},
    )
    await session.commit()
    return {"ok": True, "synced": results}


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


def _upload_bytes_to_s3(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    tenant_id: uuid.UUID,
    brand_id: uuid.UUID,
) -> tuple[str, str]:
    """Upload bytes to S3 and return (presigned_url, s3_key). Falls back to a
    base64 data-URI only when S3 is unreachable in local/test environments."""
    import base64

    from prachar_shared.config import get_settings

    s = get_settings()
    safe_name = (filename or "media").replace("/", "_")
    s3_key = f"posts/{tenant_id}/{brand_id}/{uuid.uuid4()}-{safe_name}"
    try:
        import boto3
        from botocore.config import Config as BotoConfig

        kwargs: dict = {"config": BotoConfig(signature_version="s3v4")}
        if s.s3_access_key and s.s3_secret_key:
            kwargs.update(
                endpoint_url=s.s3_endpoint if s.s3_endpoint.startswith("http") else None,
                aws_access_key_id=s.s3_access_key,
                aws_secret_access_key=s.s3_secret_key,
            )
        region = s.s3_region
        if (not region or region == "us-east-1") and "s3." in s.s3_endpoint:
            region = s.s3_endpoint.split("s3.")[1].split(".")[0] or region
        if region:
            kwargs["region_name"] = region
        client = boto3.client("s3", **kwargs)
        bucket = s.s3_bucket
        client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type or "application/octet-stream",
        )
        media_url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": s3_key},
            ExpiresIn=6 * 3600,
        )
        return media_url, s3_key
    except Exception:
        b64 = base64.b64encode(file_bytes).decode("ascii")
        return f"data:{content_type};base64,{b64}", s3_key


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

    media_url, s3_key = _upload_bytes_to_s3(
        file_bytes,
        file.filename or "media",
        file.content_type or "application/octet-stream",
        user.tenant_id,
        brand_id,
    )
    return {"media_url": media_url, "s3_key": s3_key, "content_type": file.content_type}


class PublishIn(BaseModel):
    channel: str = Field(min_length=1, max_length=40)
    text: str = Field(default="", max_length=3000)
    media_url: str | None = None
    media_urls: list[str] | None = None
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
    import json
    from datetime import datetime

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
    if conn is None:
        # Fallback: if the tenant connected this channel under another brand
        # in the same workspace, reuse the newest active connection so switching
        # brands never breaks publishing.
        res_any = await session.execute(
            select(Connection)
            .where(
                Connection.tenant_id == user.tenant_id,
                Connection.channel == body.channel,
                Connection.status == "active",
            )
            .order_by(Connection.created_at.desc())
            .limit(1)
        )
        conn = res_any.scalar_one_or_none()
    if conn is None or not conn.oauth_tokens_enc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{body.channel} is not connected")

    from .connections import _organic_adapter
    try:
        adapter = _organic_adapter(body.channel)
    except KeyError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unsupported channel: {body.channel}") from None

    bundle = json.loads(decrypt_token(conn.oauth_tokens_enc))
    md = bundle.get("metadata") or {}

    # Refresh an expired/expiring access token before publish — Google/X tokens
    # live 1-2h; without this every post fails 401 once the window lapses.
    from prachar_shared.publishing import (
        build_channel_payload,
        call_adapter_publish,
        refresh_if_expiring,
        tokens_from_bundle,
    )

    try:
        bundle, changed = refresh_if_expiring(adapter, bundle)
    except PermissionError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            f"{body.channel.upper()}_REAUTH_REQUIRED: token refresh failed — reconnect {body.channel} in Channels",
        ) from exc
    if changed:
        from prachar_shared.security import encrypt_token
        conn.oauth_tokens_enc = encrypt_token(json.dumps(bundle, default=str))
        conn.expires_at = datetime.fromisoformat(bundle["expires_at"])
        await session.commit()

    tokens = tokens_from_bundle(bundle)
    ch = body.channel

    # Backfill missing channel identity metadata (e.g. ig_id, page_id, member_id)
    # on connections created before callback profile discovery was added.
    needs_profile = (
        (ch == "instagram" and not md.get("ig_id"))
        or (ch == "facebook" and not md.get("page_id"))
        or (ch == "linkedin" and not md.get("member_id"))
    )
    if needs_profile and hasattr(adapter, "fetch_profile"):
        import asyncio as _asyncio

        try:
            if _asyncio.iscoroutinefunction(adapter.fetch_profile):
                prof = await adapter.fetch_profile(tokens)
            else:
                prof = await _asyncio.to_thread(adapter.fetch_profile, tokens)
            if prof and prof.metadata:
                md.update(prof.metadata)
                bundle["metadata"] = md
                from prachar_shared.security import encrypt_token

                conn.oauth_tokens_enc = encrypt_token(json.dumps(bundle, default=str))
                await session.commit()
        except Exception:
            pass
    try:
        payload = build_channel_payload(
            ch, body.text, body.media_url, body.media_type, body.chat_id, md, media_urls=body.media_urls
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    try:
        published = await call_adapter_publish(adapter, tokens, payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)[:300]) from exc

    primary_media = (body.media_urls[0] if body.media_urls else None) or body.media_url
    item = ContentItem(
        tenant_id=user.tenant_id, brand_id=brand_id, channel=ch,
        payload={
            "copy": body.text,
            "image_url": primary_media,
            "media_urls": body.media_urls or ([body.media_url] if body.media_url else []),
            "published_ref": published.native_id,
        },
        policy_status=PolicyStatus.passed,
    )
    session.add(item)
    await log_audit(
        session, tenant_id=user.tenant_id, actor=Actor.user, action="content.publish",
        entity_type="channel", entity_id=None,
        payload={"channel": ch, "native_id": published.native_id, "brand_id": str(brand_id)},
    )
    await session.commit()
    return {
        "ok": True,
        "channel": published.channel,
        "native_id": published.native_id,
        "url": published.url,
        "published_at": published.published_at.isoformat(),
    }


# ─── Scheduled publishing ───────────────────────────────────────────────────

class ScheduleIn(BaseModel):
    channel: str = Field(min_length=1, max_length=40)
    text: str = Field(default="", max_length=3000)
    media_url: str | None = None
    media_urls: list[str] | None = None
    media_type: str = Field(default="image")  # image | video
    chat_id: str | None = None  # telegram
    scheduled_at: datetime


class RescheduleIn(BaseModel):
    scheduled_at: datetime


def _scheduled_item_out(item: ContentItem) -> dict:
    p = item.payload or {}
    media_url = p.get("media_url")
    media_urls = p.get("media_urls") or ([media_url] if media_url else [])
    return {
        "id": str(item.id),
        "channel": item.channel,
        "text": p.get("copy", ""),
        "media_url": media_url or (media_urls[0] if media_urls else None),
        "media_urls": media_urls,
        "media_type": p.get("media_type", "image"),
        "pillar": p.get("pillar"),
        "scheduled_at": item.scheduled_at.isoformat() if item.scheduled_at else None,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "published_ref": item.published_ref,
        "state": "published" if item.published_at else p.get("schedule_state", "scheduled"),
        "error": p.get("schedule_error"),
    }


@router.post("/{brand_id}/schedule")
async def schedule_post(
    brand_id: uuid.UUID,
    body: ScheduleIn,
    user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Create a scheduled post — published by the worker at `scheduled_at`."""
    from datetime import UTC, datetime, timedelta

    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
    )
    if res.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")

    if body.scheduled_at <= datetime.now(UTC) + timedelta(seconds=60):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "scheduled_at must be in the future")

    res = await session.execute(
        select(Connection).where(
            Connection.tenant_id == user.tenant_id,
            Connection.brand_id == brand_id,
            Connection.channel == body.channel,
            Connection.status == "active",
        )
    )
    if res.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{body.channel} is not connected")

    from prachar_shared.publishing import build_channel_payload
    try:
        build_channel_payload(
            body.channel, body.text, body.media_url, body.media_type, body.chat_id, {}, media_urls=body.media_urls
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    urls = [u for u in (body.media_urls or []) if u]
    if not urls and body.media_url:
        urls = [body.media_url]
    primary_media = urls[0] if urls else None

    item = ContentItem(
        tenant_id=user.tenant_id, brand_id=brand_id, channel=body.channel,
        payload={
            "copy": body.text,
            "media_url": primary_media,
            "media_urls": urls,
            "media_type": body.media_type,
            "chat_id": body.chat_id,
            "schedule_state": "scheduled",
        },
        policy_status=PolicyStatus.passed,
        scheduled_at=body.scheduled_at,
    )
    session.add(item)
    await session.flush()
    await log_audit(
        session, tenant_id=user.tenant_id, actor=Actor.user, action="content.schedule",
        entity_type="content_item", entity_id=item.id,
        payload={"channel": body.channel, "scheduled_at": body.scheduled_at.isoformat()},
    )
    await session.commit()
    return _scheduled_item_out(item)


@router.get("/{brand_id}/scheduled")
async def list_scheduled(brand_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> list[dict]:
    """All scheduled items for the calendar (scheduled, published, failed)."""
    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
    )
    if res.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")
    res = await session.execute(
        select(ContentItem).where(
            ContentItem.brand_id == brand_id,
            ContentItem.scheduled_at.is_not(None),
        ).order_by(ContentItem.scheduled_at.asc())
    )
    return [_scheduled_item_out(i) for i in res.scalars().all()]


@router.patch("/{brand_id}/schedule/{item_id}")
async def reschedule_post(
    brand_id: uuid.UUID,
    item_id: uuid.UUID,
    body: RescheduleIn,
    user: CurrentUser,
    session: SessionDep,
) -> dict:
    from datetime import UTC, datetime, timedelta

    res = await session.execute(
        select(ContentItem).where(
            ContentItem.id == item_id,
            ContentItem.brand_id == brand_id,
            ContentItem.tenant_id == user.tenant_id,
        )
    )
    item = res.scalar_one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "scheduled post not found")
    if item.published_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "post already published")
    if body.scheduled_at <= datetime.now(UTC) + timedelta(seconds=60):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "scheduled_at must be in the future")

    item.scheduled_at = body.scheduled_at
    item.payload = {**(item.payload or {}), "schedule_state": "scheduled", "schedule_attempts": 0}
    await session.commit()
    return _scheduled_item_out(item)


@router.delete("/{brand_id}/schedule/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_scheduled(
    brand_id: uuid.UUID, item_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> None:
    res = await session.execute(
        select(ContentItem).where(
            ContentItem.id == item_id,
            ContentItem.brand_id == brand_id,
            ContentItem.tenant_id == user.tenant_id,
        )
    )
    item = res.scalar_one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "scheduled post not found")
    if item.published_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "post already published")
    await session.delete(item)
    await session.commit()


# ─── Autopilot (tiered autonomy + one-click week filler) ────────────────────

_DEFAULT_PILLARS = [
    "Educational & Insights",
    "Customer Proof & Wins",
    "Product / Service Spotlight",
    "Behind the Scenes & Founder POV",
]

_BEST_HOUR_BY_CHANNEL: dict[str, int] = {
    "linkedin": 10,
    "x": 9,
    "facebook": 13,
    "instagram": 13,
    "youtube": 15,
    "tiktok": 18,
    "pinterest": 14,
    "threads": 11,
}

_MEDIA_REQUIRED_CHANNELS = frozenset({"instagram", "youtube", "tiktok", "pinterest"})


class AutopilotConfigIn(BaseModel):
    enabled: bool | None = None
    mode: str | None = Field(default=None, pattern="^(full_auto|approve_first|draft_only)$")
    posts_per_week: int | None = Field(default=None, ge=1, le=14)
    channels: list[str] | None = None
    pillars: list[str] | None = None


class FillWeekIn(BaseModel):
    posts_per_week: int | None = Field(default=None, ge=1, le=14)
    channels: list[str] | None = None
    mode: str | None = Field(default=None, pattern="^(full_auto|approve_first|draft_only)$")
    focus_topic: str | None = Field(default=None, max_length=500)
    media_url: str | None = None


def _autopilot_state(brand: Brand, active_channels: list[str], queued_count: int) -> dict:
    raw = dict((brand.brand_graph or {}).get("autopilot") or {})
    channels = raw.get("channels") or active_channels or ["linkedin", "facebook", "x"]
    pillars = raw.get("pillars") or list(_DEFAULT_PILLARS)
    mode = raw.get("mode") if raw.get("mode") in ("full_auto", "approve_first", "draft_only") else "approve_first"
    posts_per_week = int(raw.get("posts_per_week") or 5)
    enabled = bool(raw.get("enabled", brand.next_loop_at is not None))
    return {
        "enabled": enabled,
        "mode": mode,
        "posts_per_week": max(1, min(14, posts_per_week)),
        "channels": channels,
        "pillars": pillars,
        "connected_channels": active_channels,
        "next_loop_at": brand.next_loop_at.isoformat() if brand.next_loop_at else None,
        "queued_count": queued_count,
    }


async def _load_brand_autopilot_context(
    brand_id: uuid.UUID, tenant_id: uuid.UUID, session: SessionDep
) -> tuple[Brand, list[str], int]:
    from datetime import UTC, datetime

    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == tenant_id)
    )
    brand = res.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")

    conn_res = await session.execute(
        select(Connection.channel).where(
            Connection.brand_id == brand_id,
            Connection.tenant_id == tenant_id,
            Connection.status == "active",
        )
    )
    active_channels = [
        ch for (ch,) in conn_res.all()
        if ch not in ("gsc", "gmb", "google")
    ]
    if not active_channels:
        conn_any = await session.execute(
            select(Connection.channel).where(
                Connection.tenant_id == tenant_id,
                Connection.status == "active",
            )
        )
        active_channels = list(dict.fromkeys(
            ch for (ch,) in conn_any.all()
            if ch not in ("gsc", "gmb", "google")
        ))

    sched_res = await session.execute(
        select(ContentItem).where(
            ContentItem.brand_id == brand_id,
            ContentItem.tenant_id == tenant_id,
            ContentItem.scheduled_at.is_not(None),
            ContentItem.published_at.is_(None),
            ContentItem.scheduled_at >= datetime.now(UTC),
        )
    )
    queued_count = len(sched_res.scalars().all())
    return brand, active_channels, queued_count


@router.get("/{brand_id}/autopilot")
async def get_autopilot(
    brand_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> dict:
    brand, active_channels, queued_count = await _load_brand_autopilot_context(
        brand_id, user.tenant_id, session
    )
    return _autopilot_state(brand, active_channels, queued_count)


@router.patch("/{brand_id}/autopilot")
async def update_autopilot(
    brand_id: uuid.UUID,
    body: AutopilotConfigIn,
    user: CurrentUser,
    session: SessionDep,
) -> dict:
    from datetime import UTC, datetime, timedelta

    brand, active_channels, queued_count = await _load_brand_autopilot_context(
        brand_id, user.tenant_id, session
    )
    graph = dict(brand.brand_graph or {})
    ap = dict(graph.get("autopilot") or {})
    if body.enabled is not None:
        ap["enabled"] = body.enabled
        brand.next_loop_at = (
            datetime.now(UTC) + timedelta(days=7) if body.enabled else None
        )
    if body.mode is not None:
        ap["mode"] = body.mode
    if body.posts_per_week is not None:
        ap["posts_per_week"] = body.posts_per_week
    if body.channels is not None:
        ap["channels"] = [c.strip().lower() for c in body.channels if c.strip()]
    if body.pillars is not None:
        ap["pillars"] = [p.strip() for p in body.pillars if p.strip()]

    graph["autopilot"] = ap
    brand.brand_graph = graph
    await log_audit(
        session,
        tenant_id=user.tenant_id,
        actor=Actor.user,
        action="brand.autopilot.update",
        entity_type="brand",
        entity_id=brand.id,
        payload=ap,
    )
    await session.commit()
    return _autopilot_state(brand, active_channels, queued_count)


@router.post("/{brand_id}/schedule/{item_id}/approve")
async def approve_scheduled_post(
    brand_id: uuid.UUID,
    item_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Promote a draft / pending_approval post to 'scheduled' so the worker publishes it at scheduled_at."""
    from datetime import UTC, datetime, timedelta

    res = await session.execute(
        select(ContentItem).where(
            ContentItem.id == item_id,
            ContentItem.brand_id == brand_id,
            ContentItem.tenant_id == user.tenant_id,
        )
    )
    item = res.scalar_one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "scheduled post not found")
    if item.published_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "post already published")

    now = datetime.now(UTC)
    if item.scheduled_at is None or item.scheduled_at <= now + timedelta(seconds=60):
        item.scheduled_at = now + timedelta(minutes=5)
    item.payload = {**(item.payload or {}), "schedule_state": "scheduled", "schedule_attempts": 0}
    await log_audit(
        session,
        tenant_id=user.tenant_id,
        actor=Actor.user,
        action="content.approve",
        entity_type="content_item",
        entity_id=item.id,
        payload={"channel": item.channel, "scheduled_at": item.scheduled_at.isoformat()},
    )
    await session.commit()
    return _scheduled_item_out(item)


@router.post("/{brand_id}/autopilot/approve-all")
async def approve_all_scheduled(
    brand_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> dict:
    """One-tap approval for all pending_approval / draft posts on the calendar."""
    from datetime import UTC, datetime, timedelta

    res = await session.execute(
        select(ContentItem).where(
            ContentItem.brand_id == brand_id,
            ContentItem.tenant_id == user.tenant_id,
            ContentItem.scheduled_at.is_not(None),
            ContentItem.published_at.is_(None),
        )
    )
    items = res.scalars().all()
    now = datetime.now(UTC)
    approved = 0
    for idx, item in enumerate(items):
        st = (item.payload or {}).get("schedule_state", "scheduled")
        if st in ("pending_approval", "draft"):
            if item.scheduled_at is None or item.scheduled_at <= now + timedelta(seconds=60):
                item.scheduled_at = now + timedelta(minutes=5 + idx * 2)
            item.payload = {**(item.payload or {}), "schedule_state": "scheduled", "schedule_attempts": 0}
            approved += 1

    await log_audit(
        session,
        tenant_id=user.tenant_id,
        actor=Actor.user,
        action="content.approve_all",
        entity_type="brand",
        entity_id=brand_id,
        payload={"approved_count": approved},
    )
    await session.commit()
    return {"approved": approved}


def _fallback_post_copy(
    brand: Brand, channel: str, pillar: str, day_num: int, focus_topic: str | None
) -> str:
    topic = focus_topic or brand.category or "growth & customer outcomes"
    voice = (brand.tone or {}).get("voice") or "clear, confident, and helpful"
    templates = [
        f"{brand.name} insight ({pillar}): Most teams overcomplicate {topic}. Start with one measurable workflow, track weekly lift, and compound what works.",
        f"{brand.name} — {pillar}: Three signals your {topic} strategy is working: faster response loops, consistent creative output, and lower wasted spend.",
        f"Behind the scenes at {brand.name}: How we approach {topic} with a {voice} mindset — focus on clarity, customer proof, and repeatable execution.",
        f"{brand.name} spotlight ({pillar}): Ready to streamline {topic}? Here is the exact checklist our team runs every week to stay ahead.",
    ]
    text = templates[day_num % len(templates)]
    if channel == "x" and len(text) > 275:
        text = text[:272] + "..."
    return text


@router.post("/{brand_id}/autopilot/fill-week")
async def autopilot_fill_week(
    brand_id: uuid.UUID,
    body: FillWeekIn,
    user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Generate a full week of on-brand posts across selected channels and place
    them directly onto the Content Calendar at each platform's peak hour."""
    from datetime import UTC, datetime, timedelta

    from prachar_shared.ai_gateway import AIGateway, Tier
    from prachar_shared.ai_gateway.json_utils import extract_json
    from prachar_shared.policy.claims import claims_gate

    brand, active_channels, _ = await _load_brand_autopilot_context(
        brand_id, user.tenant_id, session
    )
    ap_cfg = _autopilot_state(brand, active_channels, 0)
    count = body.posts_per_week or ap_cfg["posts_per_week"] or 5
    mode = body.mode or ap_cfg["mode"] or "approve_first"
    channels = (
        [c.strip().lower() for c in body.channels if c.strip()]
        if body.channels
        else ap_cfg["channels"]
    )
    if not channels:
        channels = active_channels or ["linkedin", "facebook", "x"]
    pillars = ap_cfg["pillars"] or list(_DEFAULT_PILLARS)

    tone_desc = (brand.tone or {}).get("voice") or "professional, specific, and engaging"
    prompt = f"""You are the Autonomous Social Media Director for "{brand.name}".
Website: {brand.website or 'N/A'}
Category: {brand.category or 'General Business'}
Brand Voice: {tone_desc}
Content Pillars: {', '.join(pillars)}
Target Channels: {', '.join(channels)}
Focus Topic: {body.focus_topic or 'Core brand value, customer wins, and actionable tips'}

Generate {count} distinct, ready-to-publish social media posts spread across the next 7 days.
Rules:
- Adapt copy to each channel (e.g. X <= 260 chars, LinkedIn thought-leadership with line breaks, Facebook/Instagram engaging hook + CTA).
- Never make "guaranteed #1" or unverified medical/financial guarantees.
- Rotate across the target channels and content pillars.

Return ONLY valid JSON in this exact shape:
{{
  "posts": [
    {{
      "day_offset": 1,
      "channel": "{channels[0]}",
      "pillar": "{pillars[0]}",
      "text": "Full post caption ready to publish..."
    }}
  ]
}}"""

    generated_posts: list[dict] = []
    try:
        plan = await get_tenant_plan(session, user)
        gw = AIGateway()
        completion = await gw.async_complete(
            prompt=prompt,
            tier=Tier.small,
            tenant_id=user.tenant_id,
            plan=plan,
            max_tokens=1600,
        )
        parsed = extract_json(completion.text) or {}
        if isinstance(parsed, dict) and isinstance(parsed.get("posts"), list):
            generated_posts = [p for p in parsed["posts"] if isinstance(p, dict) and p.get("text")]
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(
            "autopilot fill-week LLM fallback for brand %s: %s", brand_id, exc
        )

    now = datetime.now(UTC)
    created_items: list[ContentItem] = []

    for i in range(count):
        raw_post = generated_posts[i] if i < len(generated_posts) else {}
        ch = str(raw_post.get("channel") or channels[i % len(channels)]).lower()
        if ch not in channels:
            ch = channels[i % len(channels)]
        pillar = str(raw_post.get("pillar") or pillars[i % len(pillars)])
        text = str(raw_post.get("text") or "").strip()
        if not text:
            text = _fallback_post_copy(brand, ch, pillar, i, body.focus_topic)

        # Enforce X character limit and claims_gate safety
        if ch == "x" and len(text) > 275:
            text = text[:272] + "..."
        gate = claims_gate(text)
        if not gate.passed:
            text = _fallback_post_copy(brand, ch, pillar, i, None)

        day_offset = int(raw_post.get("day_offset") or ((i % 7) + 1))
        day_offset = max(1, min(7, day_offset))
        best_hour = _BEST_HOUR_BY_CHANNEL.get(ch, 11)
        slot = (now + timedelta(days=day_offset)).replace(
            hour=best_hour, minute=(i * 7) % 60, second=0, microsecond=0
        )
        if slot <= now + timedelta(minutes=2):
            slot = now + timedelta(hours=2 + i)

        # Determine initial state based on autonomy mode + channel readiness
        is_connected = ch in active_channels
        needs_media = ch in _MEDIA_REQUIRED_CHANNELS and not body.media_url
        if mode == "draft_only":
            sched_state = "draft"
        elif mode == "approve_first" or not is_connected or needs_media:
            sched_state = "pending_approval"
        else:
            sched_state = "scheduled"

        item = ContentItem(
            tenant_id=user.tenant_id,
            brand_id=brand_id,
            channel=ch,
            payload={
                "copy": text,
                "media_url": body.media_url,
                "media_type": "image",
                "pillar": pillar,
                "autopilot": True,
                "schedule_state": sched_state,
            },
            policy_status=PolicyStatus.passed,
            scheduled_at=slot,
        )
        session.add(item)
        created_items.append(item)

    await session.flush()
    await log_audit(
        session,
        tenant_id=user.tenant_id,
        actor=Actor.user,
        action="brand.autopilot.fill_week",
        entity_type="brand",
        entity_id=brand_id,
        payload={"count": len(created_items), "mode": mode, "channels": channels},
    )
    await session.commit()
    return {
        "created": len(created_items),
        "mode": mode,
        "items": [_scheduled_item_out(it) for it in created_items],
    }


# ─── AI Carousel Slide Generator (1080x1080 brand-locked slides) ────────────

class CarouselGenerateIn(BaseModel):
    topic: str = Field(default="", max_length=600)
    slides_count: int = Field(default=5, ge=2, le=8)


def _render_carousel_slide_png(
    brand_name: str,
    headline: str,
    body_text: str,
    slide_idx: int,
    total_slides: int,
) -> bytes:
    """Render a crisp 1080x1080 branded carousel slide PNG with Pillow."""
    import io
    import textwrap

    from PIL import Image, ImageDraw, ImageFont

    size = 1080
    img = Image.new("RGB", (size, size), (12, 13, 20))
    draw = ImageDraw.Draw(img)

    # Top & bottom accent bars (CURV brand palette)
    draw.rectangle([(0, 0), (size, 10)], fill=(168, 85, 247))
    draw.rectangle([(80, 980), (size - 80, 983)], fill=(55, 60, 82))

    def _font(sz: int) -> Any:
        for candidate in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ):
            try:
                return ImageFont.truetype(candidate, sz)
            except Exception:
                continue
        return ImageFont.load_default()

    font_tag = _font(28)
    font_title = _font(58)
    font_body = _font(36)
    font_footer = _font(26)

    # Header: brand badge + slide counter
    draw.text((80, 76), brand_name.upper()[:28], fill=(192, 132, 252), font=font_tag)
    counter = f"{slide_idx:02d} / {total_slides:02d}"
    draw.text((size - 200, 76), counter, fill=(148, 163, 184), font=font_tag)

    # Wrapped headline
    y = 220
    for line in textwrap.wrap(headline.strip(), width=24)[:5]:
        draw.text((80, y), line, fill=(248, 250, 252), font=font_title)
        y += 74

    # Accent divider pill
    y += 24
    draw.rounded_rectangle([(80, y), (220, y + 8)], radius=4, fill=(245, 158, 11))
    y += 48

    # Wrapped body copy
    for line in textwrap.wrap(body_text.strip(), width=38)[:8]:
        draw.text((80, y), line, fill=(203, 213, 225), font=font_body)
        y += 52

    # Footer watermark + swipe cue
    swipe = "Swipe →" if slide_idx < total_slides else f"Follow {brand_name}"
    draw.text((80, 1005), brand_name, fill=(148, 163, 184), font=font_footer)
    draw.text((size - 280, 1005), swipe, fill=(192, 132, 252), font=font_footer)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


@router.post("/{brand_id}/carousel/generate")
async def generate_carousel_slides(
    brand_id: uuid.UUID,
    body: CarouselGenerateIn,
    user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Generate a multi-slide carousel (copy + rendered 1080x1080 PNG slides
    uploaded to S3) ready to publish or schedule on Instagram, Facebook, or LinkedIn."""
    import logging

    from prachar_shared.ai_gateway import AIGateway, Tier
    from prachar_shared.ai_gateway.json_utils import extract_json
    from prachar_shared.policy.claims import claims_gate

    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
    )
    brand = res.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")

    n = body.slides_count
    topic = body.topic.strip() or brand.category or f"How {brand.name} drives results"
    tone_desc = (brand.tone or {}).get("voice") or "sharp, authoritative, and actionable"

    prompt = f"""Design a {n}-slide social media carousel for "{brand.name}".
Topic: {topic}
Brand Voice: {tone_desc}

Slide structure:
- Slide 1: Scroll-stopping hook headline + short setup
- Slides 2..{n - 1}: One clear insight/step per slide (concise headline <= 60 chars + body <= 160 chars)
- Slide {n}: Actionable takeaway + CTA

Also write a compelling post caption (<= 600 chars) to accompany the carousel.
Never make "guaranteed #1" or unverified medical/financial claims.

Return ONLY valid JSON:
{{
  "caption": "Full post caption...",
  "slides": [
    {{"headline": "Slide 1 hook...", "body": "Supporting point..."}}
  ]
}}"""

    slides_spec: list[dict] = []
    caption = ""
    try:
        plan = await get_tenant_plan(session, user)
        gw = AIGateway()
        comp = await gw.async_complete(
            prompt=prompt,
            tier=Tier.small,
            tenant_id=user.tenant_id,
            plan=plan,
            max_tokens=1400,
        )
        parsed = extract_json(comp.text) or {}
        if isinstance(parsed, dict):
            caption = str(parsed.get("caption") or "").strip()
            if isinstance(parsed.get("slides"), list):
                slides_spec = [s for s in parsed["slides"] if isinstance(s, dict)]
    except Exception as exc:
        logging.getLogger(__name__).warning("carousel LLM fallback for %s: %s", brand_id, exc)

    default_slides = [
        {"headline": f"{topic[:48]}", "body": f"The playbook {brand.name} uses to turn strategy into measurable weekly momentum."},
        {"headline": "1. Start With Signal, Not Noise", "body": "Focus on the two channels where your buyers already spend attention before scaling breadth."},
        {"headline": "2. Systematize Creative Output", "body": "Consistent brand-locked visuals and sharp hooks outperform sporadic one-off posts."},
        {"headline": "3. Schedule at Peak Attention", "body": "Publish when your audience is active and compound every winning angle into the next week."},
        {"headline": f"Ready to Grow With {brand.name}?", "body": "Save this carousel for your next campaign review and share it with your team."},
    ]

    if not caption or not claims_gate(caption).passed:
        caption = f"{topic} — broken down in {n} slides by {brand.name}. Swipe through and save for your next sprint."

    rendered_slides: list[dict] = []
    for idx in range(n):
        raw = slides_spec[idx] if idx < len(slides_spec) else default_slides[idx % len(default_slides)]
        headline = str(raw.get("headline") or default_slides[idx % len(default_slides)]["headline"])[:80]
        slide_body = str(raw.get("body") or default_slides[idx % len(default_slides)]["body"])[:220]
        if not claims_gate(f"{headline} {slide_body}").passed:
            fb = default_slides[idx % len(default_slides)]
            headline, slide_body = fb["headline"], fb["body"]

        png_bytes = _render_carousel_slide_png(brand.name, headline, slide_body, idx + 1, n)
        media_url, _ = _upload_bytes_to_s3(
            png_bytes, f"carousel-slide-{idx + 1}.png", "image/png", user.tenant_id, brand_id
        )
        rendered_slides.append(
            {
                "slide_number": idx + 1,
                "headline": headline,
                "body": slide_body,
                "media_url": media_url,
            }
        )

    await log_audit(
        session,
        tenant_id=user.tenant_id,
        actor=Actor.user,
        action="brand.carousel.generate",
        entity_type="brand",
        entity_id=brand_id,
        payload={"slides_count": len(rendered_slides), "topic": topic[:120]},
    )
    await session.commit()
    return {
        "caption": caption,
        "slides": rendered_slides,
        "media_urls": [s["media_url"] for s in rendered_slides],
    }


# ─── Video Finishing (Hook Title + Captions + Brand Watermark Burn-In) ──────

class VideoFinishIn(BaseModel):
    video_url: str = Field(min_length=1, max_length=4096)
    hook_title: str = Field(default="", max_length=120)
    caption_text: str = Field(default="", max_length=280)
    watermark: str = Field(default="", max_length=60)
    prompt_context: str = Field(default="", max_length=500)


def _render_video_overlay_png(
    hook_title: str,
    caption_text: str,
    watermark: str,
    width: int = 1080,
    height: int = 1920,
) -> bytes:
    """Render a transparent RGBA overlay with top hook banner, brand watermark
    pill, and lower-third caption box ready for ffmpeg `scale2ref` + `overlay`."""
    import io
    import textwrap

    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def _font(sz: int) -> Any:
        for candidate in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ):
            try:
                return ImageFont.truetype(candidate, sz)
            except Exception:
                continue
        return ImageFont.load_default()

    font_wm = _font(28)
    font_hook = _font(46)
    font_cap = _font(38)

    # 1. Top-right brand watermark badge
    if watermark.strip():
        wm = watermark.strip().upper()[:26]
        draw.rounded_rectangle(
            [(width - 380, 48), (width - 48, 112)],
            radius=32,
            fill=(12, 13, 20, 190),
        )
        draw.text((width - 352, 64), wm, fill=(192, 132, 252, 255), font=font_wm)

    # 2. Top hook title banner
    if hook_title.strip():
        lines = textwrap.wrap(hook_title.strip(), width=26)[:2]
        box_h = 56 + len(lines) * 62
        draw.rounded_rectangle(
            [(64, 140), (width - 64, 140 + box_h)],
            radius=28,
            fill=(15, 16, 26, 215),
        )
        draw.rounded_rectangle(
            [(64, 140), (width - 64, 148)],
            radius=4,
            fill=(168, 85, 247, 255),
        )
        y = 168
        for ln in lines:
            draw.text((96, y), ln, fill=(255, 255, 255, 255), font=font_hook)
            y += 60

    # 3. Bottom lower-third styled captions
    if caption_text.strip():
        cap_lines = textwrap.wrap(caption_text.strip(), width=32)[:3]
        cap_h = 52 + len(cap_lines) * 52
        top_y = height - 260 - cap_h
        draw.rounded_rectangle(
            [(64, top_y), (width - 64, top_y + cap_h)],
            radius=24,
            fill=(10, 11, 18, 210),
        )
        y = top_y + 26
        for ln in cap_lines:
            draw.text((92, y), ln, fill=(250, 204, 21, 255), font=font_cap)
            y += 50

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _burn_overlay_with_ffmpeg(video_bytes: bytes, overlay_png: bytes) -> bytes | None:
    """Composite `overlay_png` onto `video_bytes` using ffmpeg scale2ref + overlay.
    Returns finished MP4 bytes, or None if ffmpeg is unavailable or fails."""
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    if not shutil.which("ffmpeg"):
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        in_video = Path(tmpdir) / "in.mp4"
        in_ovr = Path(tmpdir) / "ovr.png"
        out_video = Path(tmpdir) / "out.mp4"
        in_video.write_bytes(video_bytes)
        in_ovr.write_bytes(overlay_png)

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(in_video),
            "-i",
            str(in_ovr),
            "-filter_complex",
            "[1:v][0:v]scale2ref[ovr][base];[base][ovr]overlay=0:0",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "23",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(out_video),
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=90, check=False)
        if proc.returncode == 0 and out_video.exists() and out_video.stat().st_size > 0:
            return out_video.read_bytes()
        return None


@router.post("/{brand_id}/video/finish")
async def finish_brand_video(
    brand_id: uuid.UUID,
    body: VideoFinishIn,
    user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Post-produce a raw video clip with a burned-in hook headline, styled
    lower-third captions, and locked brand watermark."""
    import asyncio
    import base64
    import logging

    import httpx
    from prachar_shared.ai_gateway import AIGateway, Tier
    from prachar_shared.ai_gateway.json_utils import extract_json
    from prachar_shared.policy.claims import claims_gate

    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
    )
    brand = res.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")

    hook = body.hook_title.strip()
    caption = body.caption_text.strip()
    watermark = body.watermark.strip() or brand.name

    if not hook or not caption:
        ctx_topic = body.prompt_context.strip() or brand.category or brand.name
        prompt = f"""Write on-video text overlays for a short social video by "{brand.name}".
Context: {ctx_topic}
Return ONLY valid JSON:
{{
  "hook_title": "Short scroll-stopping hook (<= 48 chars)",
  "caption_text": "Punchy lower-third caption summarizing the key takeaway (<= 110 chars)"
}}"""
        try:
            plan = await get_tenant_plan(session, user)
            gw = AIGateway()
            comp = await gw.async_complete(
                prompt=prompt,
                tier=Tier.small,
                tenant_id=user.tenant_id,
                plan=plan,
                max_tokens=300,
            )
            parsed = extract_json(comp.text) or {}
            if isinstance(parsed, dict):
                hook = hook or str(parsed.get("hook_title") or "").strip()[:80]
                caption = caption or str(parsed.get("caption_text") or "").strip()[:160]
        except Exception as exc:
            logging.getLogger(__name__).warning("video finish LLM fallback: %s", exc)

    if not hook or not claims_gate(hook).passed:
        hook = f"{brand.name}: What Most Teams Miss"
    if not caption or not claims_gate(caption).passed:
        caption = f"Built for measurable momentum — {brand.name}"

    overlay_png = _render_video_overlay_png(hook, caption, watermark)

    # Fetch input video bytes (supports http(s) URL or data:video/mp4;base64,...)
    video_bytes: bytes | None = None
    try:
        if body.video_url.startswith("data:"):
            _, b64_part = body.video_url.split(",", 1)
            video_bytes = base64.b64decode(b64_part)
        else:
            async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
                r = await client.get(body.video_url)
                r.raise_for_status()
                video_bytes = r.content
    except Exception as exc:
        logging.getLogger(__name__).warning("video finish download failed: %s", exc)

    finished_url = body.video_url
    burned = False
    if video_bytes:
        out_bytes = await asyncio.to_thread(_burn_overlay_with_ffmpeg, video_bytes, overlay_png)
        if out_bytes:
            finished_url, _ = _upload_bytes_to_s3(
                out_bytes, "finished-video.mp4", "video/mp4", user.tenant_id, brand_id
            )
            burned = True

    await log_audit(
        session,
        tenant_id=user.tenant_id,
        actor=Actor.user,
        action="brand.video.finish",
        entity_type="brand",
        entity_id=brand_id,
        payload={"burned": burned, "hook_title": hook, "watermark": watermark},
    )
    await session.commit()
    return {
        "video_url": finished_url,
        "hook_title": hook,
        "caption_text": caption,
        "watermark": watermark,
        "burned": burned,
    }


# ─── Today's Ready Queue + Snap-to-Campaign (SOLO-style Teammate UX) ─────────

@router.get("/{brand_id}/daily-ready-queue")
async def get_daily_ready_queue(
    brand_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Return 3 ready-to-approve teammate cards for the Home screen so the
    founder sees finished work waiting for 1-tap approval instead of a blank page."""
    brand, active_channels, queued_count = await _load_brand_autopilot_context(
        brand_id, user.tenant_id, session
    )
    primary_ch = active_channels[0] if active_channels else "instagram"

    # Check if there is an existing pending/draft scheduled item to surface first
    res = await session.execute(
        select(ContentItem)
        .where(
            ContentItem.brand_id == brand_id,
            ContentItem.tenant_id == user.tenant_id,
            ContentItem.scheduled_at.is_not(None),
            ContentItem.published_at.is_(None),
        )
        .order_by(ContentItem.scheduled_at.asc())
        .limit(1)
    )
    next_item = res.scalar_one_or_none()
    if next_item is not None:
        social_copy = (next_item.payload or {}).get("copy") or _fallback_post_copy(
            brand, next_item.channel, "Educational & Insights", 0, None
        )
        social_item_id = str(next_item.id)
        social_channel = next_item.channel
        social_state = (next_item.payload or {}).get("schedule_state", "scheduled")
    else:
        social_copy = _fallback_post_copy(brand, primary_ch, "Customer Proof & Wins", 0, None)
        social_item_id = None
        social_channel = primary_ch
        social_state = "ready_to_queue"

    topic = brand.category or "your core offer"
    whatsapp_msg = (
        f"Hi! Quick update from {brand.name} — we've opened priority slots for {topic} this week. "
        f"Reply YES and we'll share the details right here on WhatsApp."
    )

    cards = [
        {
            "id": "tara-social",
            "teammate": "Tara · Marketing",
            "badge": "Ready to Post",
            "title": f"Today's {social_channel.capitalize()} Post",
            "preview": social_copy,
            "channel": social_channel,
            "scheduled_item_id": social_item_id,
            "state": social_state,
            "cta_label": "Approve & Schedule" if social_item_id and social_state != "scheduled" else "Edit & Post",
            "action_type": "approve_item" if (social_item_id and social_state != "scheduled") else "open_composer",
        },
        {
            "id": "ved-whatsapp",
            "teammate": "Ved · Customer & Leads",
            "badge": "WhatsApp Follow-Up",
            "title": "Warm Lead Follow-Up Broadcast",
            "preview": whatsapp_msg,
            "channel": "whatsapp",
            "scheduled_item_id": None,
            "state": "ready",
            "cta_label": "Open in Composer",
            "action_type": "open_composer",
        },
        {
            "id": "maya-growth",
            "teammate": "Maya · Creative Studio",
            "badge": f"{queued_count} Queued" if queued_count else "Autopilot",
            "title": "Fill This Week's Content Calendar" if queued_count < 3 else "Design a 5-Slide Product Carousel",
            "preview": (
                f"Generate and schedule 5 on-brand posts across {', '.join(active_channels or ['LinkedIn', 'Facebook', 'X'])} at peak hours."
                if queued_count < 3
                else f"Turn {brand.name}'s top value prop into a 1080×1080 multi-slide carousel."
            ),
            "channel": primary_ch,
            "scheduled_item_id": None,
            "state": "ready",
            "cta_label": "Fill My Week" if queued_count < 3 else "Design Carousel",
            "action_type": "fill_week" if queued_count < 3 else "open_carousel",
        },
    ]
    return {"brand_id": str(brand.id), "brand_name": brand.name, "cards": cards}


@router.post("/{brand_id}/snap-to-campaign")
async def snap_to_campaign(
    brand_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    file: UploadFile = File(...),
    note: str = "",
) -> dict:
    """Upload 1 product/service photo → returns a ready 3-slide product carousel
    (uploaded photo as slide 1 + 2 branded insight/CTA slides), channel-ready
    caption, and WhatsApp broadcast copy."""
    import logging

    from prachar_shared.ai_gateway import AIGateway, Tier
    from prachar_shared.ai_gateway.json_utils import extract_json
    from prachar_shared.policy.claims import claims_gate

    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
    )
    brand = res.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")

    raw_bytes = await file.read()
    if len(raw_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "file too large (50MB max)")

    hero_url, _ = _upload_bytes_to_s3(
        raw_bytes,
        file.filename or "product.jpg",
        file.content_type or "image/jpeg",
        user.tenant_id,
        brand_id,
    )

    context_hint = note.strip() or (file.filename or "").rsplit(".", 1)[0].replace("-", " ").replace("_", " ")
    prompt = f"""You are Tara, the AI Marketing Teammate for "{brand.name}" ({brand.category or 'Business'}).
The founder just uploaded a product/service photo ({context_hint or 'featured product'}).
Write:
1. A high-converting social caption (<= 500 chars) with hook, value, and CTA.
2. Slide 2 headline (<= 52 chars) & body (<= 140 chars) highlighting why customers love it.
3. Slide 3 headline (<= 52 chars) & body (<= 140 chars) with a clear offer / next step.
4. A short WhatsApp broadcast message (<= 220 chars) to send to warm leads.
Never use "guaranteed #1" or unverified medical/financial claims.

Return ONLY valid JSON:
{{
  "caption": "...",
  "slide2_headline": "...",
  "slide2_body": "...",
  "slide3_headline": "...",
  "slide3_body": "...",
  "whatsapp_copy": "..."
}}"""

    parsed: dict = {}
    try:
        plan = await get_tenant_plan(session, user)
        gw = AIGateway()
        comp = await gw.async_complete(
            prompt=prompt,
            tier=Tier.small,
            tenant_id=user.tenant_id,
            plan=plan,
            max_tokens=800,
        )
        parsed = extract_json(comp.text) or {}
    except Exception as exc:
        logging.getLogger(__name__).warning("snap_to_campaign LLM fallback: %s", exc)

    caption = str(parsed.get("caption") or "").strip()
    if not caption or not claims_gate(caption).passed:
        caption = (
            f" Meet the latest from {brand.name}"
            f"{f' — {context_hint}' if context_hint else ''}. "
            f"Built for real results and crafted with care. Swipe for details and DM us to order!"
        ).strip()

    s2_h = str(parsed.get("slide2_headline") or f"Why {brand.name} Stands Out")[:65]
    s2_b = str(parsed.get("slide2_body") or "Designed around customer feedback for standout quality and everyday reliability.")[:180]
    s3_h = str(parsed.get("slide3_headline") or f"Get Yours From {brand.name}")[:65]
    s3_b = str(parsed.get("slide3_body") or "Tap the link in bio or message us on WhatsApp for priority delivery.")[:180]

    slide2_png = _render_carousel_slide_png(brand.name, s2_h, s2_b, 2, 3)
    slide3_png = _render_carousel_slide_png(brand.name, s3_h, s3_b, 3, 3)
    s2_url, _ = _upload_bytes_to_s3(slide2_png, "snap-slide-2.png", "image/png", user.tenant_id, brand_id)
    s3_url, _ = _upload_bytes_to_s3(slide3_png, "snap-slide-3.png", "image/png", user.tenant_id, brand_id)

    whatsapp_copy = str(parsed.get("whatsapp_copy") or "").strip() or (
        f"Hi from {brand.name}! Check out our featured release — reply HERE to claim yours today."
    )

    media_urls = [hero_url, s2_url, s3_url]
    await log_audit(
        session,
        tenant_id=user.tenant_id,
        actor=Actor.user,
        action="brand.snap_to_campaign",
        entity_type="brand",
        entity_id=brand_id,
        payload={"slides": len(media_urls)},
    )
    await session.commit()
    return {
        "caption": caption,
        "whatsapp_copy": whatsapp_copy,
        "media_urls": media_urls,
        "slides": [
            {"slide_number": 1, "headline": "Featured Product", "media_url": hero_url},
            {"slide_number": 2, "headline": s2_h, "media_url": s2_url},
            {"slide_number": 3, "headline": s3_h, "media_url": s3_url},
        ],
    }






# ─── A) Pre-Publish Algorithm Score ──────────────────────────────────────────
# Scores a post on the four signals feed algorithms actually reward
# (3s hook hold, save/share trigger, channel fit, CTA clarity) and offers a
# 1-click AI rewrite ("Boost to 90+"). Deterministic heuristic baseline always
# runs; AIGateway refines signals + writes the boosted caption when live.


class PostScoreIn(BaseModel):
    caption: str = ""
    channels: list[str] = Field(default_factory=list)
    media_type: str = "text"  # text | image | video | carousel
    slides_count: int = 1


_CTA_TERMS = (
    "shop", "buy", "book", "order", "dm", "link in bio", "tap", "visit",
    "call", "whatsapp", "sign up", "try", "get yours", "join", "save this",
    "claim", "comment", "learn more", "swipe", "subscribe",
)
_SAVE_TERMS = (
    "save", "share", "tag", "send this", "checklist", "steps", "tips",
    "guide", "how to", "ways to", "mistakes", "recipe", "before you",
    "did you know", "vs ", "top ", "secret", "hack",
)
_CHANNEL_LIMITS = {
    "x": 280,
    "linkedin": 3000,
    "tiktok": 2200,
    "instagram": 2200,
    "telegram": 4096,
    "youtube": 5000,
}


def _heuristic_post_score(
    caption: str, channels: list[str], media_type: str, slides_count: int
) -> dict:
    """Deterministic 4-signal baseline (0-25 each). Always available."""
    text = (caption or "").strip()
    first_line = text.split("\n", 1)[0].strip()
    hook_words = len(first_line.split()) if first_line else 0
    if not text:
        hook = 0
    elif 3 <= hook_words <= 9:
        hook = 25
    elif hook_words <= 14:
        hook = 18
    elif hook_words <= 25:
        hook = 11
    else:
        hook = 6

    low = text.lower()
    save_hits = sum(1 for t in _SAVE_TERMS if t in low)
    save = 6 + min(save_hits, 2) * 6
    if media_type == "carousel" or slides_count > 1:
        save += 9  # carousels are the highest save-rate format on IG/LinkedIn
    if "?" in first_line:
        save += 2
    save = min(25, save) if text else 0

    fit = 25.0
    eval_channels = channels or ["instagram"]
    for ch in eval_channels:
        limit = _CHANNEL_LIMITS.get(ch)
        if limit and len(text) > limit:
            fit -= 10
        if ch == "instagram" and media_type == "text" and slides_count == 0:
            fit -= 8
        if ch == "youtube" and media_type != "video":
            fit -= 12
    fit = max(0.0, min(25.0, fit)) if text else 0.0

    cta_hits = sum(1 for t in _CTA_TERMS if t in low)
    cta = min(25, 8 + cta_hits * 7) if text else 0
    if any(t in low for t in ("link in bio", "dm us", "comment")):
        cta = 25

    def _tips() -> dict[str, str]:
        return {
            "hook": (
                "Lead with a punchy 3-9 word first line — it decides the "
                "3-second hold rate." if hook < 18 else "Strong scroll-stopping first line."
            ),
            "save_share": (
                "Add a save-worthy element (checklist, steps, 'save this') "
                "or convert to a carousel." if save < 18 else "Built-in save/share trigger."
            ),
            "channel_fit": (
                "Caption exceeds a channel limit or required media is missing."
                if fit < 20 else "Fits the selected channels' limits & format."
            ),
            "cta": (
                "End with one clear CTA — 'DM us', 'link in bio', 'comment YES'."
                if cta < 18 else "Clear call-to-action present."
            ),
        }

    tips = _tips()
    signals = {
        "hook": {"score": int(hook), "tip": tips["hook"]},
        "save_share": {"score": int(save), "tip": tips["save_share"]},
        "channel_fit": {"score": int(fit), "tip": tips["channel_fit"]},
        "cta": {"score": int(cta), "tip": tips["cta"]},
    }
    return {"score": int(hook + save + fit + cta), "signals": signals}


def _verdict(score: int) -> str:
    if score >= 85:
        return "viral_ready"
    if score >= 70:
        return "strong"
    if score >= 50:
        return "good"
    return "needs_work"


@router.post("/{brand_id}/post/score")
async def score_post(
    brand_id: uuid.UUID, body: PostScoreIn, user: CurrentUser, session: SessionDep
) -> dict:
    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
    )
    brand = res.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")

    result = _heuristic_post_score(
        body.caption, body.channels, body.media_type, body.slides_count
    )
    boosted_caption = ""
    boosted_hook = ""
    source = "heuristic"

    if body.caption.strip():
        import logging

        from prachar_shared.ai_gateway import AIGateway, Tier
        from prachar_shared.ai_gateway.json_utils import extract_json
        from prachar_shared.policy.claims import claims_gate

        prompt = f"""You are Maya, Creative Director for "{brand.name}" ({brand.category or 'Business'}).
Score this social post on the four signals feed algorithms reward. Channels: {', '.join(body.channels) or 'general'}. Media: {body.media_type}{f' ({body.slides_count} slides)' if body.slides_count > 1 else ''}.

POST:
\"\"\"{body.caption[:1500]}\"\"\"

Then rewrite it into a higher-scoring version (<= 400 chars) with a stronger hook, a save/share trigger, and one clear CTA. Keep the brand voice. Never use "guaranteed" or unverified claims.

Return ONLY valid JSON:
{{
  "hook_score": 0-25, "hook_tip": "...",
  "save_score": 0-25, "save_tip": "...",
  "fit_score": 0-25, "fit_tip": "...",
  "cta_score": 0-25, "cta_tip": "...",
  "boosted_caption": "...",
  "boosted_hook": "first line only, <= 60 chars"
}}"""
        try:
            plan = await get_tenant_plan(session, user)
            gw = AIGateway()
            comp = await gw.async_complete(
                prompt=prompt,
                tier=Tier.small,
                tenant_id=user.tenant_id,
                plan=plan,
                max_tokens=900,
                user_input=body.caption,
            )
            parsed = extract_json(comp.text) or {}
            if isinstance(parsed, dict):
                llm_signals: dict[str, dict] = {}
                key_map = {
                    "hook": ("hook_score", "hook_tip"),
                    "save_share": ("save_score", "save_tip"),
                    "channel_fit": ("fit_score", "fit_tip"),
                    "cta": ("cta_score", "cta_tip"),
                }
                for sig_key, (s_key, t_key) in key_map.items():
                    try:
                        s_val = int(parsed.get(s_key))
                    except (TypeError, ValueError):
                        s_val = None
                    if s_val is not None:
                        s_val = max(0, min(25, s_val))
                        llm_signals[sig_key] = {
                            "score": s_val,
                            "tip": str(parsed.get(t_key) or "")[:220],
                        }
                if len(llm_signals) == 4:
                    result = {
                        "score": sum(s["score"] for s in llm_signals.values()),
                        "signals": llm_signals,
                    }
                    source = "ai"
                bc = str(parsed.get("boosted_caption") or "").strip()
                if bc and claims_gate(bc).passed:
                    boosted_caption = bc[:600]
                bh = str(parsed.get("boosted_hook") or "").strip()
                if bh and claims_gate(bh).passed:
                    boosted_hook = bh[:80]
        except Exception as exc:  # noqa: BLE001 — heuristic already computed
            logging.getLogger(__name__).warning("post/score LLM refine skipped: %s", exc)

    return {
        "score": result["score"],
        "verdict": _verdict(result["score"]),
        "signals": result["signals"],
        "boosted_caption": boosted_caption,
        "boosted_hook": boosted_hook,
        "source": source,
    }


# ─── B) AI & Google Visibility Radar ─────────────────────────────────────────
# Surfaces the audit VisibilityScore + live AI-citation probes (does ChatGPT
# recommend the brand?) + GSC striking-distance "quick win" queries.


def _brand_domain(website: str | None) -> str | None:
    if not website or not website.strip():
        return None
    t = website.strip()
    if "://" not in t:
        t = "https://" + t
    try:
        from urllib.parse import urlparse

        host = (urlparse(t).netloc or "").lower()
    except ValueError:
        return None
    return host.removeprefix("www.") or None


@router.get("/{brand_id}/visibility-radar")
async def visibility_radar(
    brand_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> dict:
    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
    )
    brand = res.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")

    import asyncio
    import json
    import logging
    from datetime import timedelta

    from ..models import AuditJob

    log = logging.getLogger(__name__)

    # 1) Latest completed audit for this brand's domain → VisibilityScore subs
    overall = brand.visibility_score
    sub_scores: dict | None = None
    domain = _brand_domain(brand.website)
    if domain:
        jres = await session.execute(
            select(AuditJob)
            .where(AuditJob.domain == domain, AuditJob.status == "completed")
            .order_by(AuditJob.completed_at.desc())
            .limit(1)
        )
        job = jres.scalar_one_or_none()
        if job and job.score_snapshot:
            snap = job.score_snapshot
            sub_scores = {
                k: snap.get(k)
                for k in (
                    "organic_rank_index",
                    "ai_citation_rate",
                    "social_reach_index",
                    "paid_efficiency",
                    "momentum",
                )
            }
            if overall is None:
                overall = snap.get("overall")

    # 2) GSC striking-distance quick wins (positions 4-15, sorted by impressions)
    gsc_out: dict = {"connected": False, "site": None, "quick_wins": []}
    cres = await session.execute(
        select(Connection).where(
            Connection.brand_id == brand_id,
            Connection.tenant_id == user.tenant_id,
            Connection.channel == "gsc",
            Connection.status == "active",
        )
    )
    gsc_conn = cres.scalar_one_or_none()
    if gsc_conn is None:
        cres_any = await session.execute(
            select(Connection)
            .where(
                Connection.tenant_id == user.tenant_id,
                Connection.channel == "gsc",
                Connection.status == "active",
            )
            .order_by(Connection.created_at.desc())
            .limit(1)
        )
        gsc_conn = cres_any.scalar_one_or_none()
    if gsc_conn and gsc_conn.oauth_tokens_enc:
        gsc_out["connected"] = True
        try:
            from prachar_shared.contracts import TokenSet
            from prachar_shared.security import decrypt_token, encrypt_token

            from .connections import _organic_adapter

            bundle = json.loads(decrypt_token(gsc_conn.oauth_tokens_enc))
            meta = bundle.get("metadata") or {}
            sites = meta.get("verified_sites") or []
            site = sites[0] if sites else meta.get("account_name")
            gsc_out["site"] = site
            if site:
                tokens = TokenSet(
                    access_token=bundle["access_token"],
                    refresh_token=bundle.get("refresh_token"),
                    expires_at=datetime.fromisoformat(bundle["expires_at"])
                    if bundle.get("expires_at")
                    else datetime.now(UTC),
                    scopes=bundle.get("scopes") or [],
                    metadata=meta,
                )
                adapter = _organic_adapter("gsc")
                if (
                    tokens.expires_at <= datetime.now(UTC) + timedelta(seconds=30)
                    and tokens.refresh_token
                    and hasattr(adapter, "refresh_access_token")
                ):
                    new_tokens = await asyncio.to_thread(
                        adapter.refresh_access_token, tokens.refresh_token
                    )
                    bundle.update(
                        {
                            "access_token": new_tokens.access_token,
                            "refresh_token": new_tokens.refresh_token
                            or tokens.refresh_token,
                            "expires_at": new_tokens.expires_at.isoformat(),
                            "scopes": new_tokens.scopes,
                        }
                    )
                    gsc_conn.oauth_tokens_enc = encrypt_token(
                        json.dumps(bundle, default=str)
                    )
                    gsc_conn.expires_at = new_tokens.expires_at
                    await session.flush()
                    tokens = new_tokens
                if hasattr(adapter, "search_analytics"):
                    rows = await adapter.search_analytics(
                        tokens, site, datetime.now(UTC) - timedelta(days=28)
                    )
                    quick = [
                        r
                        for r in rows
                        if 4.0 <= r["position"] <= 15.0 and r["impressions"] >= 50
                    ]
                    quick.sort(key=lambda r: r["impressions"], reverse=True)
                    gsc_out["quick_wins"] = quick[:5]
        except Exception as exc:  # noqa: BLE001 — radar must stay up
            log.warning("visibility-radar gsc failed: %s", exc)
            gsc_out["error"] = str(exc)[:160]

    # 3) Live AI citation probes — does an AI answer engine name the brand?
    probes: list[dict] = []
    mentioned = 0
    try:
        from prachar_shared.ai_gateway import AIGateway, Tier
        from prachar_shared.ai_gateway.json_utils import extract_json

        gw = AIGateway()
        if not getattr(gw, "_stub_mode", lambda: True)():
            plan = await get_tenant_plan(session, user)
            category = brand.category or "business"
            queries = [
                f"best {category} brands",
                f"top {category} for small business",
                f"{category} recommendations",
            ]
            for q in queries:
                try:
                    comp = await gw.async_complete(
                        prompt=(
                            f"Answer as an AI answer engine: '{q}'. List 3-5 "
                            f"brands you would recommend. Then set mentions_brand "
                            f"to true only if '{brand.name}' appears in your answer. "
                            'Return JSON {"mentions_brand": bool, "answer": '
                            '"one-line summary of your recommendations"}'
                        ),
                        tier=Tier.small,
                        tenant_id=user.tenant_id,
                        plan=plan,
                        max_tokens=250,
                        task="geo_probes",
                    )
                    parsed = extract_json(comp.text) or {}
                    m = bool(parsed.get("mentions_brand"))
                    mentioned += int(m)
                    probes.append(
                        {
                            "query": q,
                            "mentioned": m,
                            "snippet": str(parsed.get("answer") or "")[:220],
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    log.warning("citation probe failed q=%s err=%s", q, exc)
    except Exception as exc:  # noqa: BLE001
        log.warning("citation probe setup failed: %s", exc)

    citations = {
        "queries_tested": len(probes),
        "brand_mentioned": mentioned,
        "citation_rate": round(mentioned / len(probes), 2) if probes else None,
        "probes": probes,
    }

    # 4) Recommendations derived strictly from real signals
    recs: list[str] = []
    if overall is None and sub_scores is None:
        recs.append(
            "Run a Visibility Audit to baseline your AI & search presence."
        )
    if gsc_out["connected"] and gsc_out["quick_wins"]:
        q = gsc_out["quick_wins"][0]
        recs.append(
            f"Quick win: you rank #{round(q['position'])} for "
            f'"{q["query"]}" ({int(q["impressions"]):,} impressions) — a '
            "targeted post + FAQ push can move it into the Top 3."
        )
    elif not gsc_out["connected"]:
        recs.append(
            "Connect Google Search Console to reveal striking-distance "
            "keywords you can win this week."
        )
    if citations["citation_rate"] is not None and citations["citation_rate"] < 0.5:
        recs.append(
            f"AI answer engines cited {brand.name} in "
            f"{mentioned}/{len(probes)} buyer questions — publish FAQ and "
            "comparison content so ChatGPT & Perplexity can cite you."
        )
    if not recs:
        recs.append(
            "Visibility engine healthy — keep Social Autopilot running to "
            "compound reach week over week."
        )

    return {
        "overall_score": overall,
        "sub_scores": sub_scores,
        "gsc": gsc_out,
        "ai_citations": citations,
        "recommendations": recs,
    }


# ─── C) Winner Engine — Clone What Works ─────────────────────────────────────
# Ranks published posts by real engagement metrics, then mutates the winning
# post's structure into fresh variations (creative evolution, on demand).


@router.get("/{brand_id}/winner-posts")
async def winner_posts(
    brand_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> dict:
    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
    )
    if res.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")

    from datetime import timedelta

    from sqlalchemy import func

    from ..models import MetricEvent

    ires = await session.execute(
        select(ContentItem)
        .where(
            ContentItem.brand_id == brand_id,
            ContentItem.tenant_id == user.tenant_id,
            ContentItem.published_at.is_not(None),
        )
        .order_by(ContentItem.published_at.desc())
        .limit(60)
    )
    items = ires.scalars().all()
    if not items:
        return {"posts": [], "has_metrics": False}

    candidates: set[str] = set()
    for it in items:
        candidates.add(str(it.id))
        if it.published_ref:
            candidates.add(it.published_ref)

    since = datetime.now(UTC) - timedelta(days=120)
    mres = await session.execute(
        select(
            MetricEvent.entity_id,
            MetricEvent.metric,
            func.sum(MetricEvent.value),
        )
        .where(
            MetricEvent.brand_id == brand_id,
            MetricEvent.tenant_id == user.tenant_id,
            MetricEvent.entity_id.in_(candidates),
            MetricEvent.ts >= since,
        )
        .group_by(MetricEvent.entity_id, MetricEvent.metric)
    )
    stats: dict[str, dict[str, float]] = {}
    for eid, metric, total in mres.all():
        stats.setdefault(eid, {})[metric] = float(total or 0)

    engagement_metrics = {"likes", "comments", "shares", "saves", "engagements"}
    posts: list[dict] = []
    for it in items:
        merged: dict[str, float] = {}
        for key in (str(it.id), it.published_ref):
            if not key:
                continue
            for m, v in (stats.get(key) or {}).items():
                merged[m] = merged.get(m, 0.0) + v
        impr = merged.get("impressions") or merged.get("views") or 0.0
        eng = sum(merged.get(m, 0.0) for m in engagement_metrics)
        clicks = merged.get("clicks") or merged.get("website_visits") or 0.0
        rate = (eng / impr) if impr > 0 else 0.0
        score = eng * 2 + clicks + rate * 200
        payload = it.payload or {}
        media_urls = payload.get("media_urls") or []
        posts.append(
            {
                "id": str(it.id),
                "channel": it.channel,
                "copy": payload.get("copy") or payload.get("text") or "",
                "media_url": payload.get("image_url")
                or (media_urls[0] if media_urls else None),
                "published_at": it.published_at.isoformat()
                if it.published_at
                else None,
                "impressions": int(impr),
                "engagements": int(eng),
                "score": round(score, 1),
            }
        )
    posts.sort(key=lambda p: p["score"], reverse=True)
    return {"posts": posts[:5], "has_metrics": bool(stats)}


class CloneWinnerIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    content_item_id: uuid.UUID | None = None
    copy_: str = Field(default="", alias="copy")
    channel: str | None = None
    count: int = Field(default=3, ge=1, le=5)


@router.post("/{brand_id}/clone-winner")
async def clone_winner(
    brand_id: uuid.UUID, body: CloneWinnerIn, user: CurrentUser, session: SessionDep
) -> dict:
    """Mutate a winning post's structure into fresh variations — the on-demand
    face of the creative-evolution engine (median±1σ winners spawn children)."""
    import logging

    from prachar_shared.ai_gateway import AIGateway, Tier
    from prachar_shared.ai_gateway.json_utils import extract_json
    from prachar_shared.policy.claims import claims_gate

    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
    )
    brand = res.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")

    source_copy = body.copy_.strip()
    channel = body.channel or "instagram"
    if body.content_item_id:
        ires = await session.execute(
            select(ContentItem).where(
                ContentItem.id == body.content_item_id,
                ContentItem.brand_id == brand_id,
                ContentItem.tenant_id == user.tenant_id,
            )
        )
        item = ires.scalar_one_or_none()
        if item is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "content item not found")
        payload = item.payload or {}
        source_copy = source_copy or (
            payload.get("copy") or payload.get("text") or ""
        )
        channel = body.channel or item.channel or channel
    if not source_copy:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "no source post to clone"
        )

    prompt = f"""You are Maya, Creative Director for "{brand.name}" ({brand.category or 'Business'}).
This post outperformed the brand's average on {channel}:

WINNING POST:
\"\"\"{source_copy[:1200]}\"\"\"

Generate exactly {body.count} fresh variations that KEEP the winning structure (hook pattern, format, CTA style) but change the angle. Use proven angles: data/stat hook, question hook, bold offer, customer story, myth-busting. Each caption <= 400 chars, native to {channel}, in the brand voice. Never use "guaranteed" or unverified claims.

Return ONLY valid JSON:
{{"variations": [{{"angle": "...", "hook": "...", "caption": "..."}}]}}"""

    variations: list[dict] = []
    try:
        plan = await get_tenant_plan(session, user)
        gw = AIGateway()
        comp = await gw.async_complete(
            prompt=prompt,
            tier=Tier.small,
            tenant_id=user.tenant_id,
            plan=plan,
            max_tokens=1200,
            user_input=source_copy,
        )
        parsed = extract_json(comp.text) or {}
        if isinstance(parsed, dict) and isinstance(parsed.get("variations"), list):
            for v in parsed["variations"]:
                if not isinstance(v, dict):
                    continue
                caption = str(v.get("caption") or "").strip()
                if caption and claims_gate(caption).passed:
                    variations.append(
                        {
                            "angle": str(v.get("angle") or "Variation")[:60],
                            "hook": str(v.get("hook") or "")[:80],
                            "caption": caption[:600],
                        }
                    )
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("clone-winner LLM fallback: %s", exc)

    if not variations:
        first_line = source_copy.split("\n", 1)[0][:80]
        variations = [
            {
                "angle": "Question hook",
                "hook": f"Ever wonder what makes {brand.name} different?",
                "caption": (
                    f"Ever wonder what makes {brand.name} different? "
                    f"{source_copy[:250]} — DM us to see for yourself."
                )[:400],
            },
            {
                "angle": "Bold offer",
                "hook": first_line,
                "caption": (
                    f"{first_line} — this week only at {brand.name}. "
                    "Tap the link in bio or comment YES for details."
                )[:400],
            },
            {
                "angle": "Customer story",
                "hook": f"Real results from {brand.name} customers",
                "caption": (
                    f"Our customers said it best: {source_copy[:230]} "
                    "Share this with someone who needs it."
                )[:400],
            },
        ][: body.count]

    await log_audit(
        session,
        tenant_id=user.tenant_id,
        actor=Actor.user,
        action="brand.post.clone_winner",
        entity_type="brand",
        entity_id=brand_id,
        payload={"channel": channel, "variations": len(variations)},
    )
    await session.commit()
    return {"variations": variations, "channel": channel}
