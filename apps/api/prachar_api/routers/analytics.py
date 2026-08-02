"""Analytics tracking — receives batched events from the frontend.

Records user interaction events as AuditEvents for product analytics.
No third-party analytics — all data stays in-house.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from ..deps import SessionDep, current_user
from ..audit import log_audit as audit_event

log = logging.getLogger("prachar.api.analytics")
router = APIRouter(prefix="/analytics", tags=["analytics"])


class AnalyticsEvent(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default="")


class AnalyticsBatch(BaseModel):
    events: list[AnalyticsEvent] = Field(default_factory=list, max_length=50)


@router.post("/track")
async def track_events(
    body: AnalyticsBatch,
    request: Request,
    session: SessionDep,
    user=Depends(current_user),
) -> dict[str, Any]:
    """Receive a batch of analytics events from the frontend.

    Events are recorded as AuditEvents with action="analytics.{name}".
    This keeps all analytics data in-house (no third-party scripts).
    """
    if not body.events:
        return {"status": "ok", "recorded": 0}

    tenant_id = getattr(user, "tenant_id", None)
    user_id = getattr(user, "id", None)

    for evt in body.events:
        try:
            await audit_event(
                session,
                tenant_id=tenant_id,
                actor=str(user_id) if user_id else "anonymous",
                action=f"analytics.{evt.name}",
                entity_type="analytics_event",
                entity_id=evt.name,
                payload={
                    "payload": evt.payload,
                    "timestamp": evt.timestamp,
                    "user_agent": request.headers.get("user-agent", ""),
                },
            )
        except Exception:
            log.warning("Failed to record analytics event: %s", evt.name, exc_info=True)

    await session.commit()
    return {"status": "ok", "recorded": len(body.events)}
