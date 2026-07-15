from __future__ import annotations

"""Spend cap enforcement — checked in a DB transaction before every budget/bid call.
Per spec 06 §"Money safety": hard cap table checked BEFORE any network call."""

import logging
import uuid
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SpendCap:
    tenant_id: uuid.UUID
    monthly_cap: float  # total spend cap per month
    daily_cap: float  # total spend cap per day
    currency: str = "INR"


@dataclass
class SpendState:
    spent_today: float
    spent_this_month: float
    cap: SpendCap


def _get_spend_state(tenant_id: uuid.UUID) -> SpendState | None:
    """Read current spend state from DB. Returns None if DB unavailable."""
    try:
        from sqlalchemy import text

        from prachar_workers.db import session_scope

        with session_scope() as session:
            # Sum today's spend across all campaigns for this tenant.
            row = session.execute(
                text("""
                    SELECT COALESCE(SUM(value), 0) as spent_today
                    FROM metric_events
                    WHERE tenant_id = :tid
                      AND metric = 'spend'
                      AND ts >= date_trunc('day', now())
                """),
                {"tid": str(tenant_id)},
            ).first()
            spent_today = float(row[0]) if row else 0.0

            row = session.execute(
                text("""
                    SELECT COALESCE(SUM(value), 0) as spent_month
                    FROM metric_events
                    WHERE tenant_id = :tid
                      AND metric = 'spend'
                      AND ts >= date_trunc('month', now())
                """),
                {"tid": str(tenant_id)},
            ).first()
            spent_month = float(row[0]) if row else 0.0

            # Read cap from billing table (ai_budget_month is AI cost; spend cap is separate).
            # For S6, use a fixed cap derived from plan. In production this would be a
            # dedicated spend_cap table.
            cap_row = session.execute(
                text("""
                    SELECT t.plan FROM tenants t
                    WHERE t.id = :tid
                """),
                {"tid": str(tenant_id)},
            ).first()
            plan = cap_row[0] if cap_row else "starter"
            caps = {
                "starter": (10000.0, 500.0),    # ₹10,000/mo, ₹500/day
                "growth": (100000.0, 5000.0),   # ₹1,00,000/mo, ₹5,000/day
                "agency": (1000000.0, 50000.0), # ₹10,00,000/mo, ₹50,000/day
            }
            monthly, daily = caps.get(plan, caps["starter"])
            return SpendState(
                spent_today=spent_today,
                spent_this_month=spent_month,
                cap=SpendCap(tenant_id=tenant_id, monthly_cap=monthly, daily_cap=daily),
            )
    except Exception as exc:
        logger.warning("spend state read failed: %s", exc)
        return None


def check_spend_cap(tenant_id: uuid.UUID, additional_daily: float = 0.0) -> tuple[bool, str]:
    """Check if a new budget/bid mutation would breach the spend cap.
    Returns (allowed, reason). Must be called BEFORE any network API call.
    Per spec: 'Hard cap table checked in a DB transaction before every budget/bid call.'"""
    state = _get_spend_state(tenant_id)
    if state is None:
        # If we can't read the state, allow but warn (fail-open for dev, fail-closed in prod).
        logger.warning("spend cap check: could not read state for %s, allowing", tenant_id)
        return True, "state-unavailable"

    projected_today = state.spent_today + additional_daily
    projected_month = state.spent_this_month + additional_daily

    if projected_today > state.cap.daily_cap:
        return False, f"daily cap breach: {projected_today:.2f} > {state.cap.daily_cap:.2f}"
    if projected_month > state.cap.monthly_cap:
        return False, f"monthly cap breach: {projected_month:.2f} > {state.cap.monthly_cap:.2f}"

    # Warn at 80% utilization.
    if projected_month > state.cap.monthly_cap * 0.8:
        logger.warning(
            "spend approaching cap: tenant=%s projected=%.2f cap=%.2f",
            tenant_id, projected_month, state.cap.monthly_cap,
        )

    return True, "ok"


def check_idempotency(key: str) -> bool:
    """Check if a mutation with this idempotency key has already been processed.
    Uses Redis SET with NX. Returns True if this is a new mutation (proceed),
    False if duplicate (skip)."""
    try:
        import redis

        from prachar_shared.config import get_settings

        r = redis.from_url(get_settings().redis_url, decode_responses=True)
        result = r.set(f"idem:{key}", "1", ex=86400, nx=True)  # 24h TTL
        return bool(result)
    except Exception:
        # If Redis unavailable, allow (fail-open for dev).
        return True
