from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from prachar_shared.adapters.registry import get_organic

from prachar_workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _load_content_item(content_item_id: str) -> dict[str, Any] | None:
    """Load a content item row by id. Returns dict or None if DB unavailable."""
    try:
        from sqlalchemy import text

        from prachar_workers.db import session_scope

        with session_scope() as session:
            row = session.execute(
                text(
                    "SELECT id, brand_id, channel, locale, payload, policy_status, "
                    "published_ref, published_at, tenant_id "
                    "FROM content_items WHERE id = :cid"
                ),
                {"cid": content_item_id},
            ).first()
            if not row:
                return None
            return {
                "id": str(row[0]),
                "brand_id": str(row[1]),
                "channel": row[2],
                "locale": row[3],
                "payload": row[4] or {},
                "policy_status": row[5],
                "published_ref": row[6],
                "published_at": row[7],
                "tenant_id": str(row[8]) if row[8] else None,
            }
    except Exception as exc:  # pragma: no cover - DB optional in S0
        logger.warning("load content_item failed: %s", exc)
        return None


def _persist_content_item(content_item_id: str, **fields: Any) -> None:
    """Update fields on a content item row."""
    try:
        from sqlalchemy import text

        from prachar_workers.db import session_scope

        sets: list[str] = []
        params: dict[str, Any] = {"cid": content_item_id}
        json_cols = {"payload"}
        for k, v in fields.items():
            params[k] = v
            sets.append(f"{k} = :{k}")
        if not sets:
            return
        sql = text(f"UPDATE content_items SET {', '.join(sets)} WHERE id = :cid")
        with session_scope() as session:
            for k in json_cols:
                if k in params:
                    params[k] = json.dumps(params[k], default=str)
            session.execute(sql, params)
    except Exception as exc:  # pragma: no cover - DB optional in S0
        logger.warning("persist content_item failed: %s", exc)


def _load_connection_tokens(brand_id: str, channel: str) -> Any:
    """Load + decrypt OAuth tokens for a brand/channel connection."""
    try:
        from prachar_shared.contracts import TokenSet
        from prachar_shared.security import decrypt_token
        from sqlalchemy import text

        from prachar_workers.db import session_scope

        with session_scope() as session:
            row = session.execute(
                text(
                    "SELECT oauth_tokens_enc, expires_at, scopes "
                    "FROM connections WHERE brand_id = :bid AND channel = :ch "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"bid": brand_id, "ch": channel},
            ).first()
            if not row or not row[0]:
                return None
            raw = decrypt_token(row[0])
            data = json.loads(raw)
            return TokenSet(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                expires_at=datetime.fromisoformat(data["expires_at"]),
                scopes=data.get("scopes", []),
            )
    except Exception as exc:  # pragma: no cover - DB optional in S0
        logger.warning("load connection tokens failed: %s", exc)
        return None


@celery_app.task(
    name="prachar_workers.organic.generate_content",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def generate_content(brand_id: str, channel: str, locale: str) -> dict[str, Any]:
    """Generate content for a brand+channel+locale and store as a ContentItem."""
    logger.info("generate_content brand=%s channel=%s locale=%s", brand_id, channel, locale)
    import asyncio

    payload: dict[str, Any]
    if channel == "gsc":
        from prachar_workers.organic.generate import generate_page_content

        # brand_graph fetched from DB; fall back to empty if unavailable.
        brand_graph: dict[str, Any] = {}
        try:
            from sqlalchemy import text

            from prachar_workers.db import session_scope

            with session_scope() as session:
                row = session.execute(
                    text("SELECT brand_graph FROM brands WHERE id = :bid"),
                    {"bid": brand_id},
                ).first()
                if row and row[0]:
                    brand_graph = row[0]
        except Exception as exc:  # pragma: no cover - DB optional in S0
            logger.warning("load brand_graph failed: %s", exc)

        target_keyword = (brand_graph.get("entities") or ["brand"])[0]
        payload = asyncio.run(
            generate_page_content(uuid.UUID(brand_id), target_keyword, locale, brand_graph)
        )
    else:
        adapter = get_organic(channel)
        payload = {"channel": channel, "locale": locale, "type": "copy", "payload": {}}
        _ = adapter  # adapter loaded for non-gsc channels (stub for now)

    content_item = {
        "brand_id": brand_id,
        "channel": channel,
        "locale": locale,
        "type": "copy",
        "payload": payload,
        "policy_status": "pending",
    }

    # Persist to DB if available.
    try:
        from sqlalchemy import text

        from prachar_workers.db import session_scope

        with session_scope() as session:
            row = session.execute(
                text("SELECT tenant_id FROM brands WHERE id = :bid"), {"bid": brand_id}
            ).first()
            tenant_id = str(row[0]) if row else None
            if tenant_id:
                session.execute(
                    text("SELECT set_config('app.tenant_id', :tid, true)"),
                    {"tid": tenant_id},
                )
            session.execute(
                text(
                    "INSERT INTO content_items (id, tenant_id, brand_id, channel, locale, "
                    "payload, policy_status, version) "
                    "VALUES (:id, :tid, :bid, :ch, :loc, :payload::jsonb, 'pending', 1)"
                ),
                {
                    "id": uuid.uuid4(),
                    "tid": tenant_id,
                    "bid": brand_id,
                    "ch": channel,
                    "loc": locale,
                    "payload": json.dumps(payload, default=str),
                },
            )
    except Exception as exc:  # pragma: no cover - DB optional in S0
        logger.warning("persist content_item failed: %s", exc)

    return content_item


@celery_app.task(
    name="prachar_workers.organic.policy_check",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def policy_check(brand_id: str, content_item_id: str) -> dict[str, Any]:
    """Load content item, run adapter policy_gate, update policy_status."""
    logger.info("policy_check brand=%s content=%s", brand_id, content_item_id)
    item = _load_content_item(content_item_id) or {}
    channel = item.get("channel") or "gsc"
    payload = item.get("payload") or {}
    adapter = get_organic(channel)
    result = adapter.policy_gate(payload)
    status = "passed" if result.passed else "blocked"
    _persist_content_item(content_item_id, policy_status=status)
    return {
        "passed": result.passed,
        "blocked_reasons": result.blocked_reasons,
        "warnings": result.warnings,
    }


@celery_app.task(
    name="prachar_workers.organic.publish",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def publish(brand_id: str, content_item_id: str) -> dict[str, Any]:
    """Load content item + connection tokens, call adapter.publish."""
    logger.info("publish brand=%s content=%s", brand_id, content_item_id)
    item = _load_content_item(content_item_id) or {}
    channel = item.get("channel") or "gsc"
    payload = item.get("payload") or {}
    tokens = _load_connection_tokens(brand_id, channel)
    adapter = get_organic(channel)
    if tokens is None:
        logger.warning("publish: no tokens for brand=%s channel=%s; stub ref", brand_id, channel)
        ref = {
            "channel": channel,
            "native_id": content_item_id,
            "url": None,
            "published_at": datetime.now(UTC).isoformat(),
        }
    else:
        published = adapter.publish(tokens, payload)
        ref = {
            "channel": published.channel,
            "native_id": published.native_id,
            "url": published.url,
            "published_at": published.published_at.isoformat(),
        }
    _persist_content_item(
        content_item_id,
        published_ref=ref["native_id"],
        published_at=datetime.now(UTC),
    )
    return ref
