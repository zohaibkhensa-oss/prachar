"""Publish worker (P3.8 + Phase C.3.1-C.3.4).

When a campaign is approved + published via ``POST /review/{id}/publish`` the
API enqueues the ``publish_campaign`` Celery task.  This task loads the
campaign from the DB, resolves the brand's *active* channel connections, and
publishes to every connected platform:

* **C.3.1** — Google Business Profile posts (offers, photos, updates)
* **C.3.2** — Meta organic: Facebook page posts + Instagram feed/reels
* **C.3.3** — WhatsApp Business broadcast messages (opt-in compliant)
* **C.3.4** — Google Ads + Meta Ads campaign launch

The returned native campaign id is stored on ``Campaign.network_campaign_id``.

Design notes
------------
* Follows the same pattern as ``performance.py`` (P4.2): pure helpers are
  separated from the DB/Celery glue so they can be unit-tested with fakes.
* Per-channel errors are isolated — one adapter blowing up is logged and the
  loop continues with the next channel.
* An ``AuditEvent`` row is written recording the publish action and the
  per-channel results.
* Campaigns with no active connections complete successfully (nothing to do).
* Missing OAuth tokens / unconnected channels produce a graceful ``skipped``
  status — the worker never crashes.
* WhatsApp requires opt-in compliance — only opted-in recipients are messaged.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any, Callable, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from prachar_workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _stub_tokens() -> Any:
    """Build a placeholder ``TokenSet`` (oauth_tokens_enc decryption not yet wired)."""
    from prachar_shared.contracts import TokenSet

    return TokenSet(access_token="stub", expires_at=datetime.now(UTC) + timedelta(hours=1))


def campaign_to_dict(campaign: Any) -> dict[str, Any]:
    """Serialise a ``Campaign`` ORM row into the dict expected by adapters.

    ``AdNetworkAdapter.create_campaign`` receives a plain dict describing the
    campaign.  We include the fields the stub adapters use (objective,
    budget, currency, network, audience_spec, bid_strategy, dry_run).
    """
    return {
        "id": str(getattr(campaign, "id", "")),
        "network": str(getattr(campaign, "network", "")),
        "objective": str(getattr(campaign, "objective", "")),
        "budget_daily": float(getattr(campaign, "budget_daily", 0.0) or 0.0),
        "currency": str(getattr(campaign, "currency", "INR")),
        "audience_spec": getattr(campaign, "audience_spec", {}) or {},
        "bid_strategy": getattr(campaign, "bid_strategy", {}) or {},
        "dry_run": bool(getattr(campaign, "dry_run", True)),
    }


def get_ads_adapter(network: str) -> Any:
    """Resolve an ``AdNetworkAdapter`` for ``network`` via the shared registry."""
    from prachar_shared.adapters.registry import get_ads

    return get_ads(network)


def get_organic_adapter(channel: str) -> Any:
    """Resolve a ``ChannelAdapter`` for ``channel`` via the shared registry."""
    from prachar_shared.adapters.registry import get_organic

    return get_organic(channel)


# ─── Async / connection helpers ───────────────────────────────────────────────


def _call_publish(adapter: Any, tokens: Any, payload: dict[str, Any]) -> Any:
    """Invoke ``adapter.publish`` supporting both sync and async adapters.

    Organic adapters (Facebook/Instagram/WhatsApp) expose ``async def publish``
    while the GMB adapter is synchronous.  The Celery worker is synchronous, so
    any awaitable result is resolved with ``asyncio.run``.
    """
    result = adapter.publish(tokens, payload)
    if inspect.isawaitable(result):
        result = asyncio.run(result)
    return result


def _find_connection(connections: Iterable[Any] | None, channel: str) -> Any | None:
    """Return the first connection whose ``channel`` matches *channel*, or None."""
    for conn in connections or []:
        if str(getattr(conn, "channel", "")) == channel:
            return conn
    return None


def _brand_name(brand: Any) -> str:
    return str(getattr(brand, "name", "")) if brand else ""


def _brand_website(brand: Any) -> str:
    return str(getattr(brand, "website", "") or "") if brand else ""


# ─── Payload builders ─────────────────────────────────────────────────────────


def _build_gbp_payload(campaign: Any, brand: Any) -> dict[str, Any]:
    """Build a Google Business Profile local-post payload from a campaign."""
    objective = str(getattr(campaign, "objective", ""))
    return {
        "summary": f"{_brand_name(brand)} — {objective} campaign is now live!",
        "cta_type": "LEARN_MORE",
        "cta_url": _brand_website(brand) or "https://example.com",
    }


def _build_facebook_payload(campaign: Any, brand: Any) -> dict[str, Any]:
    """Build a Facebook page-post payload from a campaign."""
    objective = str(getattr(campaign, "objective", ""))
    return {
        "message": f"{_brand_name(brand)} — {objective} campaign is now live! "
        f"Check it out: {_brand_website(brand)}",
        "link": _brand_website(brand) or None,
    }


def _build_instagram_payload(campaign: Any, brand: Any) -> dict[str, Any]:
    """Build an Instagram media payload from a campaign."""
    objective = str(getattr(campaign, "objective", ""))
    return {
        "caption": f"{_brand_name(brand)} — {objective} #marketing #growth",
        "post_type": "feed",
        "media_urls": ["https://example.com/placeholder.jpg"],
    }


def _build_whatsapp_payload(
    campaign: Any, brand: Any, recipient: dict[str, Any]
) -> dict[str, Any]:
    """Build a WhatsApp template-message payload for a single recipient."""
    return {
        "to_phone": str(recipient.get("phone", "")),
        "template_name": "campaign_launch_notification",
        "template_language": "en_US",
        "opted_in": True,
        "components": [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": _brand_name(brand)},
                    {"type": "text", "text": str(getattr(campaign, "objective", ""))},
                ],
            }
        ],
    }


# ─── C.3.1: Publish to Google Business Profile ───────────────────────────────


def publish_to_gbp(
    campaign: Any,
    brand: Any,
    connections: Iterable[Any] | None = None,
    adapter: Any | None = None,
    tokens: Any | None = None,
) -> dict[str, Any]:
    """Publish Google Business Profile posts (offers, photos, updates).

    Returns ``{"channel": "gmb", "status": "published"|"skipped"|"error", ...}``.
    Gracefully skips when GBP is not connected.
    """
    channel = "gmb"
    conn = _find_connection(connections, channel)
    if conn is None:
        return {"channel": channel, "status": "skipped", "reason": "not connected"}
    try:
        if adapter is None:
            adapter = get_organic_adapter(channel)
        if tokens is None:
            tokens = _stub_tokens()
        payload = _build_gbp_payload(campaign, brand)
        policy = adapter.policy_gate(payload)
        if not policy.passed:
            return {
                "channel": channel,
                "status": "error",
                "error": f"policy gate: {policy.blocked_reasons}",
            }
        ref = _call_publish(adapter, tokens, payload)
        return {
            "channel": channel,
            "status": "published",
            "native_id": ref.native_id,
            "url": ref.url,
        }
    except Exception as exc:  # noqa: BLE001 - per-channel isolation
        logger.warning(
            "publish_to_gbp failed campaign=%s: %s",
            getattr(campaign, "id", "?"),
            exc,
        )
        return {"channel": channel, "status": "error", "error": str(exc)}


# ─── C.3.2: Publish to Meta (Facebook + Instagram) ────────────────────────────


def publish_to_meta(
    campaign: Any,
    brand: Any,
    connections: Iterable[Any] | None = None,
    facebook_adapter: Any | None = None,
    instagram_adapter: Any | None = None,
    tokens: Any | None = None,
) -> dict[str, Any]:
    """Publish Facebook page posts and Instagram posts/reels.

    Returns ``{"channel": "meta", "status": ..., "posts": [per-channel dicts]}``.
    Each sub-channel gracefully skips when not connected.
    """
    posts: list[dict[str, Any]] = []
    for ch, adp in (("facebook", facebook_adapter), ("instagram", instagram_adapter)):
        conn = _find_connection(connections, ch)
        if conn is None:
            posts.append({"channel": ch, "status": "skipped", "reason": "not connected"})
            continue
        try:
            if adp is None:
                adp = get_organic_adapter(ch)
            if tokens is None:
                tokens = _stub_tokens()
            if ch == "facebook":
                payload = _build_facebook_payload(campaign, brand)
            else:
                payload = _build_instagram_payload(campaign, brand)
            policy = adp.policy_gate(payload)
            if not policy.passed:
                posts.append(
                    {
                        "channel": ch,
                        "status": "error",
                        "error": f"policy gate: {policy.blocked_reasons}",
                    }
                )
                continue
            ref = _call_publish(adp, tokens, payload)
            posts.append(
                {
                    "channel": ch,
                    "status": "published",
                    "native_id": ref.native_id,
                    "url": ref.url,
                }
            )
        except Exception as exc:  # noqa: BLE001 - per-channel isolation
            logger.warning(
                "publish_to_meta %s failed campaign=%s: %s",
                ch,
                getattr(campaign, "id", "?"),
                exc,
            )
            posts.append({"channel": ch, "status": "error", "error": str(exc)})

    any_published = any(p["status"] == "published" for p in posts)
    any_error = any(p["status"] == "error" for p in posts)
    overall = "published" if any_published else ("error" if any_error else "skipped")
    return {"channel": "meta", "status": overall, "posts": posts}


# ─── C.3.3: Publish to WhatsApp Business ──────────────────────────────────────


def publish_to_whatsapp(
    campaign: Any,
    brand: Any,
    connections: Iterable[Any] | None = None,
    adapter: Any | None = None,
    tokens: Any | None = None,
    recipients: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Send WhatsApp broadcast messages with opt-in compliance.

    Only recipients who have ``opted_in=True`` are messaged.  If no opted-in
    recipients are available the function gracefully skips.

    Returns ``{"channel": "whatsapp", "status": "published"|"skipped"|"error", ...}``.
    """
    channel = "whatsapp"
    conn = _find_connection(connections, channel)
    if conn is None:
        return {"channel": channel, "status": "skipped", "reason": "not connected"}

    # ── Opt-in compliance: filter to opted-in recipients only ──
    opted_in = [
        r for r in (recipients or []) if isinstance(r, dict) and r.get("opted_in")
    ]
    if not opted_in:
        return {
            "channel": channel,
            "status": "skipped",
            "reason": "no opted-in recipients",
        }

    try:
        if adapter is None:
            adapter = get_organic_adapter(channel)
        if tokens is None:
            tokens = _stub_tokens()

        sent: list[dict[str, Any]] = []
        for recipient in opted_in:
            payload = _build_whatsapp_payload(campaign, brand, recipient)
            policy = adapter.policy_gate(payload)
            if not policy.passed:
                sent.append(
                    {
                        "to": recipient.get("phone"),
                        "status": "error",
                        "error": f"policy gate: {policy.blocked_reasons}",
                    }
                )
                continue
            ref = _call_publish(adapter, tokens, payload)
            sent.append(
                {
                    "to": recipient.get("phone"),
                    "status": "published",
                    "native_id": ref.native_id,
                }
            )

        any_published = any(s["status"] == "published" for s in sent)
        any_error = any(s["status"] == "error" for s in sent)
        overall = "published" if any_published else ("error" if any_error else "skipped")
        return {"channel": channel, "status": overall, "sent": sent}
    except Exception as exc:  # noqa: BLE001 - per-channel isolation
        logger.warning(
            "publish_to_whatsapp failed campaign=%s: %s",
            getattr(campaign, "id", "?"),
            exc,
        )
        return {"channel": channel, "status": "error", "error": str(exc)}


# ─── C.3.4: Launch Google Ads + Meta Ads campaigns ────────────────────────────


def launch_google_ads(
    campaign: Any,
    brand: Any,
    connections: Iterable[Any] | None = None,
    adapter: Any | None = None,
    tokens: Any | None = None,
) -> dict[str, Any]:
    """Create and launch a Google Ads campaign from an approved campaign plan.

    Returns ``{"channel": "google_ads", "status": "published"|"skipped"|"error", ...}``.
    Gracefully skips when Google Ads is not connected.
    """
    network = "google_ads"
    conn = _find_connection(connections, network)
    if conn is None:
        return {"channel": network, "status": "skipped", "reason": "not connected"}
    try:
        if adapter is None:
            adapter = get_ads_adapter(network)
        if tokens is None:
            tokens = _stub_tokens()
        native_id = adapter.create_campaign(tokens, campaign_to_dict(campaign))
        return {
            "channel": network,
            "status": "published",
            "network_campaign_id": native_id,
        }
    except Exception as exc:  # noqa: BLE001 - per-channel isolation
        logger.warning(
            "launch_google_ads failed campaign=%s: %s",
            getattr(campaign, "id", "?"),
            exc,
        )
        return {"channel": network, "status": "error", "error": str(exc)}


def launch_meta_ads(
    campaign: Any,
    brand: Any,
    connections: Iterable[Any] | None = None,
    adapter: Any | None = None,
    tokens: Any | None = None,
) -> dict[str, Any]:
    """Create and launch a Meta Ads campaign from an approved campaign plan.

    Returns ``{"channel": "meta_ads", "status": "published"|"skipped"|"error", ...}``.
    Gracefully skips when Meta Ads is not connected.
    """
    network = "meta_ads"
    conn = _find_connection(connections, network)
    if conn is None:
        return {"channel": network, "status": "skipped", "reason": "not connected"}
    try:
        if adapter is None:
            adapter = get_ads_adapter(network)
        if tokens is None:
            tokens = _stub_tokens()
        native_id = adapter.create_campaign(tokens, campaign_to_dict(campaign))
        return {
            "channel": network,
            "status": "published",
            "network_campaign_id": native_id,
        }
    except Exception as exc:  # noqa: BLE001 - per-channel isolation
        logger.warning(
            "launch_meta_ads failed campaign=%s: %s",
            getattr(campaign, "id", "?"),
            exc,
        )
        return {"channel": network, "status": "error", "error": str(exc)}


# ─── Core per-campaign publish (generic, for other ad networks) ───────────────


def publish_for_campaign(
    session: Session | None,
    campaign: Any,
    connections: Iterable[Any],
    adapter_factory: Callable[[str], Any] = get_ads_adapter,
) -> dict[str, Any]:
    """Publish a single campaign to each connected channel.

    ``campaign`` exposes ``id``, ``network``, ``network_campaign_id``,
    ``brand_id`` and ``tenant_id``.  ``connections`` are ``Connection``-like
    objects with a ``channel`` attribute.

    For each connection the matching ``AdNetworkAdapter.create_campaign`` is
    called.  The first successful native campaign id is stored on
    ``campaign.network_campaign_id`` (if not already set).  Per-channel errors
    are caught and reported — one failure never blocks the others.

    Returns a result dict with per-channel statuses.
    """
    channels_result: dict[str, Any] = {}
    network_campaign_id = getattr(campaign, "network_campaign_id", None)
    campaign_id = getattr(campaign, "id", None)

    for conn in connections:
        channel = getattr(conn, "channel", None)
        if channel is None:
            continue
        try:
            adapter = adapter_factory(str(channel))
            native_id = adapter.create_campaign(_stub_tokens(), campaign_to_dict(campaign))
            channels_result[str(channel)] = {
                "status": "ok",
                "network_campaign_id": native_id,
            }
            # Store the first returned native id on the campaign row.
            if network_campaign_id is None and native_id and session is not None:
                campaign.network_campaign_id = str(native_id)
                network_campaign_id = str(native_id)
        except Exception as exc:  # noqa: BLE001 - per-channel isolation
            logger.warning(
                "publish failed campaign=%s channel=%s: %s",
                campaign_id,
                channel,
                exc,
            )
            channels_result[str(channel)] = {
                "status": "error",
                "error": str(exc),
            }

    return {
        "campaign_id": str(campaign_id) if campaign_id is not None else None,
        "network_campaign_id": str(network_campaign_id) if network_campaign_id else None,
        "channels": channels_result,
    }


# ─── Audit ────────────────────────────────────────────────────────────────────


def _write_audit(
    session: Session,
    tenant_id: Any,
    campaign_id: Any,
    payload: dict[str, Any],
) -> None:
    """Insert an ``AuditEvent`` row for the publish action (sync session)."""
    from sqlalchemy import text

    session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )
    session.execute(
        text(
            "INSERT INTO audit_events (tenant_id, actor, action, entity_type, entity_id, payload) "
            "VALUES (:tid, 'system', :action, 'campaign', :eid, :payload::jsonb)"
        ),
        {
            "tid": str(tenant_id),
            "action": "campaign.publish_worker",
            "eid": str(campaign_id),
            "payload": json.dumps(payload),
        },
    )


# ─── DB loaders ───────────────────────────────────────────────────────────────


def _load_campaign(session: Session, campaign_id: str) -> Any | None:
    from prachar_api.models.tables import Campaign

    return session.execute(
        select(Campaign).where(Campaign.id == uuid.UUID(str(campaign_id)))
    ).scalar_one_or_none()


def _load_active_connections(session: Session, brand_id: Any) -> list[Any]:
    from prachar_api.models.enums import ConnectionStatus
    from prachar_api.models.tables import Connection

    return list(
        session.execute(
            select(Connection).where(
                Connection.brand_id == brand_id,
                Connection.status == ConnectionStatus.active,
            )
        ).scalars().all()
    )


def _load_brand(session: Session, brand_id: Any) -> Any | None:
    from prachar_api.models.tables import Brand

    return session.execute(
        select(Brand).where(Brand.id == brand_id)
    ).scalar_one_or_none()


# ─── Celery task ──────────────────────────────────────────────────────────────


@celery_app.task(
    name="prachar_workers.publish.publish_campaign",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def publish_campaign(campaign_id: str) -> dict[str, Any]:
    """Publish a campaign to all its brand's connected channels.

    Loads the campaign + brand, resolves active connections, then calls the
    Phase C publish functions:

    * ``publish_to_gbp``   — Google Business Profile posts
    * ``publish_to_meta``  — Facebook + Instagram organic posts
    * ``publish_to_whatsapp`` — WhatsApp broadcast (opt-in compliant)
    * ``launch_google_ads``   — Google Ads campaign
    * ``launch_meta_ads``     — Meta Ads campaign
    * ``publish_for_campaign`` — generic fallback for other ad networks

    All per-channel statuses are collected into a ``channels`` dict, the first
    native campaign id is stored on the campaign row, and an ``AuditEvent`` is
    written.  Per-channel failures are isolated.
    """
    logger.info("publish_campaign campaign_id=%s", campaign_id)

    from prachar_workers.db import session_scope

    try:
        with session_scope() as session:
            campaign = _load_campaign(session, campaign_id)
            if campaign is None:
                logger.warning("publish_campaign: campaign %s not found", campaign_id)
                return {"campaign_id": campaign_id, "status": "not_found"}

            brand = _load_brand(session, campaign.brand_id)
            connections = _load_active_connections(session, campaign.brand_id)

            channels: dict[str, Any] = {}
            network_campaign_id = getattr(campaign, "network_campaign_id", None)

            # ── C.3.1: Google Business Profile ──
            gbp_res = publish_to_gbp(campaign, brand, connections)
            channels["gmb"] = gbp_res

            # ── C.3.2: Meta (Facebook + Instagram) ──
            meta_res = publish_to_meta(campaign, brand, connections)
            for post in meta_res.get("posts", []):
                channels[post["channel"]] = post

            # ── C.3.3: WhatsApp Business ──
            wa_res = publish_to_whatsapp(campaign, brand, connections)
            channels["whatsapp"] = wa_res

            # ── C.3.4: Google Ads ──
            gads_res = launch_google_ads(campaign, brand, connections)
            channels["google_ads"] = gads_res
            if gads_res["status"] == "published" and network_campaign_id is None:
                native = gads_res.get("network_campaign_id")
                if native:
                    campaign.network_campaign_id = str(native)
                    network_campaign_id = str(native)

            # ── C.3.4: Meta Ads ──
            mads_res = launch_meta_ads(campaign, brand, connections)
            channels["meta_ads"] = mads_res
            if mads_res["status"] == "published" and network_campaign_id is None:
                native = mads_res.get("network_campaign_id")
                if native:
                    campaign.network_campaign_id = str(native)
                    network_campaign_id = str(native)

            # ── Generic fallback: other ad networks (tiktok_ads, etc.) ──
            _handled = {
                "gmb", "facebook", "instagram", "whatsapp",
                "google_ads", "meta_ads",
            }
            other_conns = [
                c for c in connections
                if str(getattr(c, "channel", "")) not in _handled
            ]
            if other_conns:
                other_result = publish_for_campaign(
                    session, campaign, other_conns, get_ads_adapter
                )
                channels.update(other_result["channels"])
                if network_campaign_id is None and other_result.get("network_campaign_id"):
                    network_campaign_id = other_result["network_campaign_id"]

            result = {
                "campaign_id": str(campaign.id),
                "network_campaign_id": str(network_campaign_id) if network_campaign_id else None,
                "channels": channels,
            }

            _write_audit(
                session,
                campaign.tenant_id,
                campaign.id,
                {
                    "channels": channels,
                    "network_campaign_id": result["network_campaign_id"],
                },
            )
    except Exception as exc:  # pragma: no cover - DB optional
        logger.warning("publish_campaign DB failed: %s", exc)
        return {
            "campaign_id": campaign_id,
            "status": "error",
            "error": str(exc),
        }

    ok_count = sum(
        1 for v in channels.values()
        if v.get("status") in ("ok", "published")
    )
    logger.info(
        "publish_campaign done campaign=%s channels=%d ok=%d",
        campaign_id,
        len(channels),
        ok_count,
    )
    result["status"] = "ok"
    return result
