"""Proactive anomaly detection worker (P5.1).

A Celery task ``check_anomalies`` runs daily, iterating over all active
brands (brands that have at least one active campaign).  For each brand it
calls :class:`ProactiveEngine.detect_anomalies` and stores the results so
they can be retrieved later by the ``/proactive/notifications`` API endpoint.

Design notes
------------
* One Celery task iterates over all brands with active campaigns.
* Per-brand failures are isolated — one brand blowing up is logged and the
  loop continues with the next brand.
* Anomalies are stored in a module-level in-memory cache (suitable for a
  single-worker deployment) and also returned from the task so they can be
  persisted by a future enhancement.  The API router reads from the same
  cache.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from prachar_workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# ─── In-memory anomaly cache ──────────────────────────────────────────────────
#
# Maps brand_id -> list[dict].  In a multi-worker deployment this would be
# replaced by a Redis-backed store, but for the current single-worker setup
# an in-memory dict is sufficient and keeps the worker self-contained.

_anomaly_cache: dict[str, list[dict[str, Any]]] = {}


def store_anomalies(brand_id: str, anomalies: list[dict[str, Any]]) -> None:
    """Store anomalies for a brand in the in-memory cache."""
    _anomaly_cache[brand_id] = anomalies


def get_anomalies(brand_id: str) -> list[dict[str, Any]]:
    """Retrieve stored anomalies for a brand from the in-memory cache."""
    return _anomaly_cache.get(brand_id, [])


def get_all_anomalies() -> dict[str, list[dict[str, Any]]]:
    """Return the full anomaly cache (brand_id -> anomalies)."""
    return dict(_anomaly_cache)


def clear_cache() -> None:
    """Clear the in-memory anomaly cache (used in tests)."""
    _anomaly_cache.clear()


# ─── DB loaders ───────────────────────────────────────────────────────────────


def _load_active_brands(session: Session) -> list[Any]:
    """Load all brand IDs that have at least one active campaign.

    Returns a list of brand_id strings (deduplicated).
    """
    from prachar_api.models.tables import Campaign
    from prachar_api.models.enums import CampaignStatus

    rows = session.execute(
        select(Campaign.brand_id).where(Campaign.status == CampaignStatus.active).distinct()
    ).all()
    return [str(r[0]) for r in rows]


# ─── Core per-brand check ─────────────────────────────────────────────────────


async def _check_brand(brand_id: str, session_factory: Any) -> list[dict[str, Any]]:
    """Run anomaly detection for a single brand and return anomaly dicts."""
    from prachar_shared.marketing_intelligence.proactive_engine import ProactiveEngine

    engine = ProactiveEngine(session_factory=session_factory)
    anomalies = await engine.detect_anomalies(brand_id, days=30)
    return [a.to_dict() for a in anomalies]


# ─── Celery task ──────────────────────────────────────────────────────────────


@celery_app.task(
    name="prachar_workers.proactive.check_anomalies",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def check_anomalies() -> dict[str, Any]:
    """Run daily anomaly detection across all active brands.

    Iterates over every brand that has at least one active campaign, calls
    :meth:`ProactiveEngine.detect_anomalies`, and stores the results in the
    in-memory cache for later retrieval by the API.

    Per-brand failures are isolated — one brand error never blocks the
    others.
    """
    import asyncio

    from prachar_workers.db import session_scope

    logger.info("check_anomalies starting")

    try:
        with session_scope() as session:
            brand_ids = _load_active_brands(session)
    except Exception as exc:  # pragma: no cover - DB optional
        logger.warning("check_anomalies DB load failed: %s", exc)
        return {"status": "error", "error": str(exc), "brands_checked": 0, "anomalies": {}}

    results: dict[str, list[dict[str, Any]]] = {}
    total_anomalies = 0

    for brand_id in brand_ids:
        try:
            # The ProactiveEngine uses an async session.  We create a thin
            # async session factory wrapper around the sync session for the
            # duration of the detection call.
            from prachar_workers.db import get_sessionmaker

            sync_session = get_sessionmaker()()

            class _AsyncSessionFactory:
                """Returns the sync session — the engine's queries work with
                both sync and async sessions via ``await session.execute()``."""

                def __call__(self) -> Any:
                    return _AsyncSessionWrapper(sync_session)

            anomalies = asyncio.run(_check_brand(brand_id, _AsyncSessionFactory()))
            store_anomalies(brand_id, anomalies)
            results[brand_id] = anomalies
            total_anomalies += len(anomalies)
            sync_session.close()
        except Exception as exc:  # noqa: BLE001 - per-brand isolation
            logger.warning("check_anomalies failed for brand=%s: %s", brand_id, exc)
            results[brand_id] = []

    logger.info(
        "check_anomalies done brands=%d anomalies=%d",
        len(brand_ids),
        total_anomalies,
    )
    return {
        "status": "ok",
        "brands_checked": len(brand_ids),
        "total_anomalies": total_anomalies,
        "anomalies": results,
    }


class _AsyncSessionWrapper:
    """Thin wrapper that makes a sync SQLAlchemy session awaitable.

    The ProactiveEngine calls ``await session.execute(stmt)``.  A sync
    session's ``execute`` returns a result directly (not a coroutine), so
    we wrap it to be awaitable.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    async def execute(self, stmt: Any) -> Any:
        return self._session.execute(stmt)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)
