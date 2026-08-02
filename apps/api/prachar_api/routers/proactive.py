"""Proactive notifications router (P5.2 / P5.5).

Exposes ``GET /proactive/notifications`` which returns pending anomalies and
any generated recommendations for the current user's brands.

Anomalies are detected by the daily ``check_anomalies`` Celery task
(P5.1) and stored in the worker's in-memory cache.  This router reads from
that cache and augments each anomaly with an AI-generated recommendation on
demand.

``POST /proactive/{id}/launch`` (P5.5) takes a proactive recommendation,
pre-fills a campaign creation request, and returns the pre-filled campaign
data.  The user still reviews and approves — no auto-publish.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import CurrentUser, SessionDep, get_tenant_plan
from ..models import Brand
from prachar_shared.ai_gateway import AIGateway
from prachar_shared.marketing_intelligence.proactive_engine import (
    Anomaly,
    ProactiveEngine,
    format_as_prachar_message,
)

router = APIRouter(prefix="/proactive", tags=["proactive"])


@router.get("/notifications", response_model=dict[str, Any])
async def get_notifications(
    user: CurrentUser,
    session: SessionDep,
) -> dict[str, Any]:
    """Return pending anomalies and recommendations for the user's brands.

    Loads all brands belonging to the current user's tenant, retrieves
    stored anomalies from the proactive worker's cache, and generates an
    AI recommendation for each anomaly on demand.

    Requires authentication.
    """
    # Load the user's brands.
    res = await session.execute(
        select(Brand).where(Brand.tenant_id == user.tenant_id)
    )
    brands = res.scalars().all()
    brand_ids = [str(b.id) for b in brands]

    # Retrieve stored anomalies from the worker cache.
    try:
        from prachar_workers.proactive import get_anomalies
    except Exception:  # noqa: BLE001 - worker may not be importable in all envs
        get_anomalies = None  # type: ignore[assignment]

    notifications: list[dict[str, Any]] = []
    gw = AIGateway()
    plan = await get_tenant_plan(session, user)
    engine = ProactiveEngine(session_factory=lambda: session)

    for brand_id in brand_ids:
        anomalies: list[dict[str, Any]] = []
        if get_anomalies is not None:
            anomalies = get_anomalies(brand_id)

        for anomaly_dict in anomalies:
            entry: dict[str, Any] = {"anomaly": anomaly_dict}
            # Generate a recommendation for this anomaly.
            try:
                anomaly = Anomaly(
                    brand_id=anomaly_dict.get("brand_id", brand_id),
                    campaign_id=anomaly_dict.get("campaign_id", ""),
                    metric=anomaly_dict.get("metric", ""),
                    magnitude=float(anomaly_dict.get("magnitude", 0.0)),
                    timeframe=anomaly_dict.get("timeframe", ""),
                    severity=anomaly_dict.get("severity", "low"),
                    direction=anomaly_dict.get("direction", "plateau"),
                )
                rec = await engine.generate_recommendation(
                    anomaly,
                    gateway=gw,
                    tenant_id=user.tenant_id,
                    plan=plan,
                )
                entry["recommendation"] = rec
            except Exception:  # noqa: BLE001 - recommendation is best-effort
                entry["recommendation"] = {}
            notifications.append(entry)

    return {
        "notifications": notifications,
        "count": len(notifications),
    }


# ─── POST /proactive/{id}/launch — one-click launch (P5.5) ────────────────────


class LaunchResponse(BaseModel):
    """Pre-filled campaign data returned by the launch endpoint.

    The user reviews this in the campaign creation form and approves —
    nothing is auto-published.
    """

    recommendation_id: str = Field(description="The proactive notification ID")
    brand_id: str
    campaign_name: str
    goal: str
    budget: str
    creative_directions: list[str] = Field(default_factory=list)
    what_to_do: str = ""
    why: str = ""
    expected_impact: str = ""
    prachar_message: str = Field(description="PRACHAR AI summary of the recommendation")
    prefill: dict[str, Any] = Field(
        default_factory=dict,
        description="Pre-filled fields for the campaign creation form",
    )


def _build_prefill(
    anomaly: Anomaly,
    recommendation: dict[str, Any],
    brand_id: str,
) -> dict[str, Any]:
    """Build the pre-fill dict for the campaign creation form."""
    directions = recommendation.get("creative_directions", [])
    if not isinstance(directions, list):
        directions = []
    directions = [str(d) for d in directions if d]

    # Infer a goal from the anomaly direction.
    if anomaly.direction == "drop":
        goal = "Recover lost performance with fresh creative"
    elif anomaly.direction == "spike":
        goal = "Scale what's working and maximise reach"
    else:  # plateau
        goal = "Break out of the plateau with a new angle"

    # Suggest a budget based on the metric — modest recovery budget.
    budget = "₹15,000/month"

    return {
        "brand_id": brand_id,
        "goal": goal,
        "budget": budget,
        "creative_directions": directions,
        "what_to_do": str(recommendation.get("what_to_do", "")),
        "why": str(recommendation.get("why", "")),
        "expected_impact": str(recommendation.get("expected_impact", "")),
        "source_anomaly": anomaly.to_dict(),
    }


@router.post("/{notification_id}/launch", response_model=LaunchResponse)
async def launch_recommendation(
    notification_id: str,
    user: CurrentUser,
    session: SessionDep,
) -> LaunchResponse:
    """Take a proactive recommendation and return pre-filled campaign data.

    The notification ID encodes ``brand_id:campaign_id:metric`` (as produced
    by ``GET /chat/proactive``).  This endpoint looks up the stored anomaly,
    generates a fresh recommendation if needed, and returns a pre-filled
    campaign creation request in PRACHAR AI's voice.

    **No campaign is created or published.**  The user reviews the pre-filled
    form and approves manually (human-in-the-loop from P3).

    Requires authentication.
    """
    # Parse the notification ID: brand_id:campaign_id:metric
    parts = notification_id.split(":", 2)
    if len(parts) < 3:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Invalid notification ID. Expected format: brand_id:campaign_id:metric",
        )
    brand_id, campaign_id, metric = parts[0], parts[1], parts[2]

    # Verify the brand belongs to the user's tenant.
    res = await session.execute(
        select(Brand).where(
            Brand.id == uuid.UUID(brand_id),
            Brand.tenant_id == user.tenant_id,
        )
    )
    brand = res.scalar_one_or_none()
    if brand is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Brand not found or not accessible",
        )

    # Retrieve the stored anomaly from the worker cache.
    try:
        from prachar_workers.proactive import get_anomalies
    except Exception:  # noqa: BLE001
        get_anomalies = None  # type: ignore[assignment]

    anomaly_dict: dict[str, Any] | None = None
    if get_anomalies is not None:
        for a in get_anomalies(brand_id):
            if (
                str(a.get("campaign_id", "")) == campaign_id
                and str(a.get("metric", "")) == metric
            ):
                anomaly_dict = a
                break

    if anomaly_dict is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Proactive notification not found. It may have been resolved or expired.",
        )

    # Build the Anomaly object.
    anomaly = Anomaly(
        brand_id=anomaly_dict.get("brand_id", brand_id),
        campaign_id=anomaly_dict.get("campaign_id", campaign_id),
        metric=anomaly_dict.get("metric", metric),
        magnitude=float(anomaly_dict.get("magnitude", 0.0)),
        timeframe=anomaly_dict.get("timeframe", ""),
        severity=anomaly_dict.get("severity", "low"),
        direction=anomaly_dict.get("direction", "plateau"),
    )

    # Generate a recommendation for this anomaly.
    gw = AIGateway()
    plan = await get_tenant_plan(session, user)
    engine = ProactiveEngine(session_factory=lambda: session)
    try:
        rec = await engine.generate_recommendation(
            anomaly,
            gateway=gw,
            tenant_id=user.tenant_id,
            plan=plan,
        )
    except Exception:  # noqa: BLE001 - recommendation is best-effort
        rec = {}

    prachar_message = format_as_prachar_message(anomaly, rec)
    prefill = _build_prefill(anomaly, rec, brand_id)

    directions = prefill.get("creative_directions", [])
    if not isinstance(directions, list):
        directions = []

    return LaunchResponse(
        recommendation_id=notification_id,
        brand_id=brand_id,
        campaign_name=f"{brand.name} — {prefill['goal'][:50]}",
        goal=prefill["goal"],
        budget=prefill["budget"],
        creative_directions=directions,
        what_to_do=prefill["what_to_do"],
        why=prefill["why"],
        expected_impact=prefill["expected_impact"],
        prachar_message=prachar_message,
        prefill=prefill,
    )
