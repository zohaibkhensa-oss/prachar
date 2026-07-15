from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from prachar_workers.celery_app import celery_app
from prachar_workers.ads.scaffold import scaffold_for_network

logger = logging.getLogger(__name__)

# Money safety (spec 06 §Money safety): dry_run default ON for first 7 days.
DRY_RUN_DEFAULT = True


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, default=str)


def _audit_campaign(
    campaign_id: str,
    action: str,
    payload: dict[str, Any] | None = None,
    *,
    entity_type: str = "campaign",
) -> None:
    """Write an audit_events row for a campaign action (best-effort, DB optional)."""
    try:
        from sqlalchemy import text

        from prachar_workers.db import session_scope

        with session_scope() as session:
            row = session.execute(
                text("SELECT tenant_id, brand_id FROM campaigns WHERE id = :cid"),
                {"cid": campaign_id},
            ).first()
            if row is None:
                logger.warning("audit: campaign %s not found", campaign_id)
                return
            tenant_id, brand_id = str(row[0]), str(row[1])
            session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": tenant_id},
            )
            session.execute(
                text(
                    "INSERT INTO audit_events (tenant_id, actor, action, entity_type, entity_id, payload) "
                    "VALUES (:tid, 'system', :action, :etype, :eid, :payload::jsonb)"
                ),
                {
                    "tid": tenant_id,
                    "action": action,
                    "etype": entity_type,
                    "eid": campaign_id,
                    "payload": _json_dumps(payload or {}),
                },
            )
    except Exception as exc:  # pragma: no cover - DB optional
        logger.warning("audit write failed: %s", exc)


def _insert_campaign_row(struct: dict[str, Any]) -> str | None:
    """Insert a Campaign row (dry_run=True) and return the DB id, or None if DB unavailable."""
    try:
        from sqlalchemy import text

        from prachar_workers.db import session_scope

        brand_id = struct["brand_id"]
        with session_scope() as session:
            row = session.execute(
                text("SELECT tenant_id FROM brands WHERE id = :bid"),
                {"bid": brand_id},
            ).first()
            if row is None:
                logger.warning("scaffold: brand %s not found", brand_id)
                return None
            tenant_id = str(row[0])
            session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": tenant_id},
            )
            db_id = str(uuid.uuid4())
            session.execute(
                text(
                    "INSERT INTO campaigns "
                    "(id, tenant_id, brand_id, network, objective, audience_spec, "
                    " budget_daily, currency, bid_strategy, status, network_campaign_id, "
                    " guardrails, dry_run, created_at, updated_at) "
                    "VALUES (:id, :tid, :bid, :network, :objective, :spec::jsonb, "
                    "        :budget, :currency, :bid::jsonb, 'draft', :ncid, "
                    "        :guard::jsonb, :dry, now(), now())"
                ),
                {
                    "id": db_id,
                    "tid": tenant_id,
                    "bid": brand_id,
                    "network": struct["network"],
                    "objective": struct["objective"],
                    "spec": _json_dumps(struct["audience_spec"]),
                    "budget": struct["budget_daily"],
                    "currency": struct.get("currency", "INR"),
                    "bid": _json_dumps(struct.get("bid_strategy") or {}),
                    "ncid": struct.get("campaign_id"),
                    "guard": _json_dumps(struct.get("guardrails") or {}),
                    "dry": struct.get("dry_run", DRY_RUN_DEFAULT),
                },
            )
            return db_id
    except Exception as exc:  # pragma: no cover - DB optional
        logger.warning("campaign insert failed: %s", exc)
        return None


@celery_app.task(
    name="prachar_workers.ads.scaffold_campaign",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def scaffold_campaign(
    brand_id: str,
    audience_spec: dict[str, Any],
    objective: str,
    budget_daily: float,
    networks: list[str],
    guardrails: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Scaffold per-network best-practice campaign structures and persist Campaign rows.

    Money safety: dry_run defaults to True (spec 06 §Money safety — first 7 days).
    Each network structure is created via :func:`scaffold_for_network`.
    """
    logger.info(
        "scaffold_campaign brand=%s objective=%s budget=%s networks=%s",
        brand_id,
        objective,
        budget_daily,
        networks,
    )
    structures: list[dict[str, Any]] = []
    for network in networks:
        struct = scaffold_for_network(
            network,
            brand_id,
            audience_spec,
            objective,
            budget_daily,
            guardrails,
        )
        db_id = _insert_campaign_row(struct)
        struct["db_campaign_id"] = db_id
        if db_id:
            _audit_campaign(
                db_id,
                "ads.scaffold",
                {"network": network, "campaign_id": struct["campaign_id"], "dry_run": struct["dry_run"]},
            )
        structures.append(struct)
    return {
        "brand_id": brand_id,
        "objective": objective,
        "budget_daily": budget_daily,
        "networks": {s["network"]: s for s in structures},
        "structures": structures,
        "status": "scaffolded",
        "dry_run": DRY_RUN_DEFAULT,
    }


@celery_app.task(
    name="prachar_workers.ads.watchdog",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def watchdog() -> dict[str, Any]:
    """Daily beat: pull stats per active campaign, detect CPA breach (CPA > max_cpa
    for 3 consecutive days -> auto-pause + audit event). Stub: logs + summary."""
    logger.info("watchdog tick")
    checked = 0
    paused: list[str] = []
    breaches: list[dict[str, Any]] = []
    try:
        from sqlalchemy import text

        from prachar_workers.db import session_scope

        with session_scope() as session:
            rows = session.execute(
                text("SELECT id, network, network_campaign_id, guardrails FROM campaigns WHERE status = 'active'")
            ).all()
            for r in rows:
                cid, network, ncid, guard = r[0], r[1], r[2], r[3] or {}
                checked += 1
                max_cpa = (guard or {}).get("max_cpa")
                if not max_cpa or not ncid:
                    continue
                # Pull stats via adapter.
                try:
                    from prachar_shared.adapters.ads import google_ads as _ga  # noqa: F401
                    from prachar_shared.adapters.ads import meta_ads as _ma  # noqa: F401
                    from prachar_shared.adapters.registry import get_ads

                    adapter = get_ads(network)
                    events = adapter.stats(_stub_tokens(), ncid, datetime.now(UTC) - timedelta(days=3))
                except Exception as exc:
                    logger.warning("watchdog stats pull failed cid=%s: %s", cid, exc)
                    continue
                # Compute CPA per day; check 3 consecutive day breach.
                cpa_breach_days = _consecutive_cpa_breach_days(events, float(max_cpa))
                if cpa_breach_days >= 3:
                    breaches.append({"campaign_id": str(cid), "network": network, "days": cpa_breach_days})
                    _pause_campaign_internal(str(cid), network, ncid)
                    paused.append(str(cid))
    except Exception as exc:  # pragma: no cover - DB optional
        logger.warning("watchdog db failed: %s", exc)
    logger.info("watchdog done checked=%s paused=%s breaches=%s", checked, paused, breaches)
    return {"checked": checked, "paused": paused, "breaches": breaches}


def _consecutive_cpa_breach_days(events: list[Any], max_cpa: float) -> int:
    """Count trailing consecutive days where CPA > max_cpa."""
    by_day: dict[str, dict[str, float]] = {}
    for ev in events:
        metric = getattr(ev, "metric", None)
        if metric is None and isinstance(ev, dict):
            metric = ev.get("metric")
        ts = getattr(ev, "ts", None) or (ev.get("ts") if isinstance(ev, dict) else None)
        value = getattr(ev, "value", None)
        if value is None and isinstance(ev, dict):
            value = ev.get("value")
        if metric is None or ts is None or value is None:
            continue
        day = str(ts.date()) if hasattr(ts, "date") else str(ts)
        bucket = by_day.setdefault(day, {"cost": 0.0, "conversions": 0.0})
        if metric == "cost":
            bucket["cost"] += float(value)
        elif metric == "conversions":
            bucket["conversions"] += float(value)
    days = sorted(by_day.keys())
    breach = 0
    for d in reversed(days):
        b = by_day[d]
        conv = b["conversions"] or 0.0
        cpa = (b["cost"] / conv) if conv > 0 else float("inf")
        if cpa > max_cpa:
            breach += 1
        else:
            break
    return breach


def _stub_tokens() -> Any:
    from prachar_shared.contracts import TokenSet

    return TokenSet(access_token="stub", expires_at=datetime.now(UTC) + timedelta(hours=1))


def _pause_campaign_internal(campaign_id: str, network: str, network_campaign_id: str) -> None:
    """Pause a campaign via its adapter and update DB status + audit event."""
    try:
        from prachar_shared.adapters.registry import get_ads

        adapter = get_ads(network)
        adapter.pause(_stub_tokens(), network_campaign_id)
    except Exception as exc:
        logger.warning("adapter.pause failed cid=%s: %s", campaign_id, exc)
    try:
        from sqlalchemy import text

        from prachar_workers.db import session_scope

        with session_scope() as session:
            session.execute(
                text("UPDATE campaigns SET status = 'paused', updated_at = now() WHERE id = :cid"),
                {"cid": campaign_id},
            )
    except Exception as exc:  # pragma: no cover - DB optional
        logger.warning("campaign status update failed cid=%s: %s", campaign_id, exc)
    _audit_campaign(campaign_id, "ads.pause", {"network": network, "reason": "cpa_breach"})


@celery_app.task(
    name="prachar_workers.ads.pause_campaign",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def pause_campaign(campaign_id: str) -> dict[str, Any]:
    """Pause a campaign: call adapter.pause, update DB status, write audit event."""
    logger.info("pause_campaign campaign_id=%s", campaign_id)
    network, ncid = _lookup_campaign(campaign_id)
    if network and ncid:
        _pause_campaign_internal(campaign_id, network, ncid)
    else:
        _audit_campaign(campaign_id, "ads.pause", {"reason": "no_network_id"})
    return {"campaign_id": campaign_id, "status": "paused"}


@celery_app.task(
    name="prachar_workers.ads.resume_campaign",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def resume_campaign(campaign_id: str) -> dict[str, Any]:
    """Resume a campaign: call adapter.resume (via create/re-enable), update DB, audit."""
    logger.info("resume_campaign campaign_id=%s", campaign_id)
    network, ncid = _lookup_campaign(campaign_id)
    if network and ncid:
        try:
            from prachar_shared.adapters.registry import get_ads

            # Adapters expose pause(); resume is modeled as re-enabling via set_budget_bid
            # with the existing budget (stub no-ops the network call).
            adapter = get_ads(network)
            adapter.set_budget_bid(_stub_tokens(), ncid, 0.0, {"action": "resume"})
        except Exception as exc:
            logger.warning("adapter resume failed cid=%s: %s", campaign_id, exc)
    try:
        from sqlalchemy import text

        from prachar_workers.db import session_scope

        with session_scope() as session:
            session.execute(
                text("UPDATE campaigns SET status = 'active', updated_at = now() WHERE id = :cid"),
                {"cid": campaign_id},
            )
    except Exception as exc:  # pragma: no cover - DB optional
        logger.warning("campaign status update failed cid=%s: %s", campaign_id, exc)
    _audit_campaign(campaign_id, "ads.resume")
    return {"campaign_id": campaign_id, "status": "resumed"}


def _lookup_campaign(campaign_id: str) -> tuple[str | None, str | None]:
    """Return (network, network_campaign_id) for a DB campaign id, best-effort."""
    try:
        from sqlalchemy import text

        from prachar_workers.db import session_scope

        with session_scope() as session:
            row = session.execute(
                text("SELECT network, network_campaign_id FROM campaigns WHERE id = :cid"),
                {"cid": campaign_id},
            ).first()
            if row:
                return str(row[0]), str(row[1]) if row[1] is not None else None
    except Exception as exc:  # pragma: no cover - DB optional
        logger.warning("campaign lookup failed cid=%s: %s", campaign_id, exc)
    return None, None
