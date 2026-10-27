"""Scheduled content publishing — beat scans due items, worker publishes.

Same pattern as ``loop.dispatch_due``: a SECURITY DEFINER function exposes
only (tenant_id, content_item_id) identifiers so the worker role needs no
BYPASSRLS. Publishing reuses the shared adapter publish path — the same
payload builder and token-refresh logic as the API's synchronous endpoint.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from prachar_workers.celery_app import celery_app
from prachar_workers.db import session_scope

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3


def _call_sync(maybe_awaitable: Any) -> Any:
    if asyncio.iscoroutine(maybe_awaitable) or hasattr(maybe_awaitable, "__await__"):
        return asyncio.run(maybe_awaitable)
    return maybe_awaitable


@celery_app.task(name="prachar_workers.schedule.due")
def dispatch_due_scheduled() -> dict[str, Any]:
    """Beat task — find content_items whose scheduled_at has passed and
    enqueue per-item publish tasks."""
    from sqlalchemy import text

    try:
        with session_scope() as session:
            rows = session.execute(
                text("SELECT content_item_id FROM due_scheduled_content(now())")
            ).all()
    except Exception as exc:
        logger.warning("dispatch_due_scheduled read failed: %s", exc)
        return {"due": 0, "error": str(exc)[:200]}

    for (item_id,) in rows:
        publish_scheduled_item.apply_async(args=[str(item_id)], queue="organic")
    return {"due": len(rows)}


@celery_app.task(name="prachar_workers.schedule.publish", max_retries=0)
def publish_scheduled_item(item_id: str) -> dict[str, Any]:
    """Publish a single scheduled content item. Idempotent — items already
    published are skipped."""
    import uuid as _uuid

    from sqlalchemy import text

    iid = _uuid.UUID(item_id)
    with session_scope() as session:
        row = session.execute(
            text("SELECT content_item_tenant(:iid)"), {"iid": iid}
        ).first()
        if row is None or row[0] is None:
            logger.warning("publish_scheduled_item: item %s not found", item_id)
            return {"ok": False, "error": "item not found"}
        session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(row[0])},
        )

        item = session.execute(
            text(
                "SELECT id, brand_id, channel, payload, published_at "
                "FROM content_items WHERE id = :iid"
            ),
            {"iid": iid},
        ).mappings().first()
        if item is None:
            return {"ok": False, "error": "item not found"}
        if item["published_at"] is not None:
            return {"ok": True, "skipped": "already published"}

        payload = dict(item["payload"] or {})
        attempts = int(payload.get("schedule_attempts") or 0)
        # Claim the item so a concurrent beat tick can't double-publish.
        session.execute(
            text(
                "UPDATE content_items SET payload = payload || "
                "jsonb_build_object('schedule_state','publishing','schedule_attempts',:n) "
                "WHERE id = :iid"
            ),
            {"iid": iid, "n": attempts + 1},
        )
        session.commit()

        try:
            published = _publish(item, session)
        except Exception as exc:
            attempts += 1
            state = "failed" if attempts >= _MAX_ATTEMPTS else "scheduled"
            session.execute(
                text(
                    "UPDATE content_items SET payload = payload || "
                    "jsonb_build_object('schedule_state',:s,'schedule_attempts',:n,"
                    "'schedule_error',:e) WHERE id = :iid"
                ),
                {"iid": iid, "s": state, "n": attempts, "e": str(exc)[:300]},
            )
            session.commit()
            logger.warning(
                "publish_scheduled_item %s failed (attempt %s): %s", item_id, attempts, exc
            )
            return {"ok": False, "state": state, "error": str(exc)[:200]}

        session.execute(
            text(
                "UPDATE content_items SET published_at = :ts, published_ref = :ref, "
                "payload = payload || jsonb_build_object('schedule_state','published','published_ref',:ref) "
                "WHERE id = :iid"
            ),
            {"iid": iid, "ts": published.published_at, "ref": published.native_id},
        )
        session.commit()
        return {"ok": True, "native_id": published.native_id, "url": published.url}


def _publish(item: Any, session: Any) -> Any:
    """Resolve tokens, refresh if needed, and call adapter.publish — same
    contract as the API publish endpoint."""
    from prachar_shared.publishing import (
        build_channel_payload,
        refresh_if_expiring,
        tokens_from_bundle,
    )
    from prachar_shared.security import decrypt_token, encrypt_token
    from sqlalchemy import text

    from prachar_workers.publish import get_organic_adapter

    payload = dict(item["payload"] or {})
    channel = str(item["channel"])
    conn = session.execute(
        text(
            "SELECT id, oauth_tokens_enc FROM connections "
            "WHERE tenant_id = current_setting('app.tenant_id')::uuid "
            "AND brand_id = :bid AND channel = :ch AND status = 'active'"
        ),
        {"bid": item["brand_id"], "ch": channel},
    ).mappings().first()
    if conn is None or not conn["oauth_tokens_enc"]:
        raise RuntimeError(f"{channel} is not connected")

    bundle = json.loads(decrypt_token(conn["oauth_tokens_enc"]))
    adapter = get_organic_adapter(channel)

    bundle, changed = refresh_if_expiring(adapter, bundle, datetime.now(UTC))
    if changed:
        session.execute(
            text("UPDATE connections SET oauth_tokens_enc = :enc, expires_at = :exp WHERE id = :cid"),
            {
                "enc": encrypt_token(json.dumps(bundle, default=str)),
                "exp": datetime.fromisoformat(bundle["expires_at"]),
                "cid": conn["id"],
            },
        )
        session.commit()

    tokens = tokens_from_bundle(bundle)
    adapter_payload = build_channel_payload(
        channel,
        payload.get("copy", ""),
        payload.get("media_url"),
        payload.get("media_type", "image"),
        payload.get("chat_id"),
        bundle.get("metadata") or {},
    )
    return _call_sync(adapter.publish(tokens, adapter_payload))
