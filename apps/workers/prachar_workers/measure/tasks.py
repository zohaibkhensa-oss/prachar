from __future__ import annotations

import logging
from datetime import date
from typing import Any

from prachar_workers.celery_app import celery_app

logger = logging.getLogger(__name__)

VISIBILITY_WEIGHTS = {
    "organic_rank_index": 0.35,
    "ai_citation_rate": 0.15,
    "social_reach_index": 0.25,
    "paid_efficiency": 0.15,
    "momentum": 0.10,
}


@celery_app.task(
    name="prachar_workers.measure.pull_metrics",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def pull_metrics(brand_id: str, channel: str, since: str) -> list[dict[str, Any]]:
    logger.info("pull_metrics brand=%s channel=%s since=%s", brand_id, channel, since)
    # S0 stub: would call adapter.metrics.
    return []


def compute_visibility_score(
    brand_id: str, components: dict[str, float] | None = None
) -> dict[str, Any]:
    logger.info("compute_visibility_score brand=%s", brand_id)
    components = components or {k: 0.0 for k in VISIBILITY_WEIGHTS}
    from prachar_shared.contracts import VisibilityScore

    score = VisibilityScore.compute(
        organic_rank_index=components.get("organic_rank_index", 0.0),
        ai_citation_rate=components.get("ai_citation_rate", 0.0),
        social_reach_index=components.get("social_reach_index", 0.0),
        paid_efficiency=components.get("paid_efficiency", 0.0),
        momentum=components.get("momentum", 0.0),
        week=date.today(),
    )
    return score.model_dump(mode="json")


@celery_app.task(
    name="prachar_workers.measure.compute_visibility_score",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def compute_visibility_score_task(
    brand_id: str, components: dict[str, float] | None = None
) -> dict[str, Any]:
    return compute_visibility_score(brand_id, components)
