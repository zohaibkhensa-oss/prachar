"""Runtime Router — the 4 endpoints that constitute the entire Runtime API.

Constitution Rule 1: The Runtime is the only public AI entry point.

Endpoints:
    POST /runtime/invoke          — Start an AI session
    GET  /runtime/stream          — SSE event stream
    POST /runtime/approve         — Human approval
    POST /runtime/cancel          — Cancel session
    GET  /timeline                — Workspace timeline
    POST /timeline/{id}/replay    — Replay a decision
    GET  /dashboard/overview      — Dashboard composition
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..deps import CurrentUser, SessionDep
from ..runtime import (
    AIEvent,
    InvokeRequest,
    InvokeResponse,
    Runtime,
    TimelineService,
    get_session_manager,
)
from prachar_shared.ai_gateway import AIGateway

log = logging.getLogger("prachar.api.runtime")

router = APIRouter(prefix="/runtime", tags=["runtime"])
timeline_router = APIRouter(prefix="/timeline", tags=["timeline"])
dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ─── Runtime singleton ──────────────────────────────────────────────────────


_runtime: Runtime | None = None
_timeline_service: TimelineService | None = None


def get_runtime() -> Runtime:
    global _runtime
    if _runtime is None:
        _runtime = Runtime(gateway=AIGateway())
    return _runtime


def get_timeline_service() -> TimelineService:
    global _timeline_service
    if _timeline_service is None:
        _timeline_service = TimelineService()
    return _timeline_service


# ─── POST /runtime/invoke ───────────────────────────────────────────────────


@router.post("/invoke", response_model=InvokeResponse)
async def invoke(
    user: CurrentUser,
    session: SessionDep,
    request: InvokeRequest,
) -> InvokeResponse:
    """Start a new AI session.

    This is the single entry point for all AI requests.
    Returns a session_id and stream_url for SSE subscription.
    """
    runtime = get_runtime()
    try:
        response = await runtime.invoke(session=session, user=user, request=request)
        return response
    except Exception as exc:
        log.exception("Runtime invoke failed: %s", exc)
        # Return a graceful error session instead of 500 — the Orb will
        # show the error message rather than hanging silently.
        import secrets as _secrets
        from ..runtime.events import EventBus, make_event, EventPhase, OrbState
        session_id = _secrets.token_hex(12)
        bus = EventBus(session_id=session_id)
        await bus.publish(make_event(
            session_id=session_id,
            type="runtime.session.error",
            phase=EventPhase.ERROR.value,
            orb_state=OrbState.ERROR.value,
            data={
                "error": "AI brain is unavailable right now. Please try again in a moment.",
                "detail": str(exc)[:300],
            },
        ))
        await bus.close()
        return InvokeResponse(
            session_id=session_id,
            decision_id=_secrets.token_hex(8),
            stream_url=f"/runtime/stream?session_id={session_id}",
            decision={},
        )


# ─── GET /runtime/stream ────────────────────────────────────────────────────


@router.get("/stream")
async def stream(
    user: CurrentUser,
    session_id: str = Query(..., description="Runtime session ID"),
) -> StreamingResponse:
    """SSE stream of events for a session.

    The frontend subscribes once and receives all events.
    Events follow the unified protocol (see V2_AI_ORCHESTRATOR_SPEC.md).
    """
    sm = get_session_manager()
    bus = await sm.get_bus(session_id)
    if bus is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")

    async def event_generator():
        # Send any buffered events first, then stream new ones
        for event in bus.get_all_events():
            yield event.to_sse()
        # Stream new events
        async for event in bus.stream():
            yield event.to_sse()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─── POST /runtime/approve ──────────────────────────────────────────────────


class ApproveRequest(BaseModel):
    decision_id: str = Field(..., description="Decision Contract ID")
    choice: str = Field(..., description='"approve" or "deny"')
    modifications: dict[str, Any] = Field(default_factory=dict)


@router.post("/approve")
async def approve(
    user: CurrentUser,
    session: SessionDep,
    request: ApproveRequest,
) -> dict[str, Any]:
    """Approve or deny a paused execution."""
    runtime = get_runtime()
    return await runtime.approve(session=session, user=user, request=request)


# ─── POST /runtime/cancel ───────────────────────────────────────────────────


class CancelRequest(BaseModel):
    session_id: str = Field(..., description="Session ID to cancel")


@router.post("/cancel")
async def cancel(
    user: CurrentUser,
    request: CancelRequest,
) -> dict[str, Any]:
    """Cancel a running session."""
    runtime = get_runtime()
    return await runtime.cancel(request)


# ─── GET /timeline ──────────────────────────────────────────────────────────


@timeline_router.get("")
async def list_timeline(
    user: CurrentUser,
    session: SessionDep,
    brand_id: uuid.UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None),
    entry_type: str | None = Query(None),
) -> dict[str, Any]:
    """List workspace timeline entries (newest first, cursor pagination)."""
    svc = get_timeline_service()
    entries, next_cursor = await svc.list(
        session=session,
        tenant_id=user.tenant_id,
        brand_id=brand_id,
        limit=limit,
        cursor=cursor,
        entry_type=entry_type,
    )
    return {
        "items": [e.to_dict() for e in entries],
        "next_cursor": next_cursor,
    }


# ─── GET /timeline/{id} ─────────────────────────────────────────────────────


@timeline_router.get("/{entry_id}")
async def get_timeline_entry(
    user: CurrentUser,
    session: SessionDep,
    entry_id: uuid.UUID,
) -> dict[str, Any]:
    """Get a single timeline entry."""
    svc = get_timeline_service()
    entry = await svc.get(session=session, tenant_id=user.tenant_id, entry_id=entry_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entry not found")
    return entry.to_dict()


# ─── POST /timeline/{id}/replay ─────────────────────────────────────────────


class ReplayRequest(BaseModel):
    input_overrides: dict[str, Any] = Field(default_factory=dict)


@timeline_router.post("/{entry_id}/replay")
async def replay_timeline_entry(
    user: CurrentUser,
    session: SessionDep,
    entry_id: uuid.UUID,
    request: ReplayRequest,
) -> dict[str, Any]:
    """Replay a timeline entry (re-execute with original or modified inputs).

    Constitution Rule 5: Every Timeline event is replayable. No exceptions.
    """
    svc = get_timeline_service()
    entry = await svc.get(session=session, tenant_id=user.tenant_id, entry_id=entry_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entry not found")
    if not entry.replayable:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "entry is not replayable")

    # Re-invoke the runtime with the original inputs (+ overrides)
    replay_inputs = entry.replay_inputs or {}
    context_snapshot = replay_inputs.get("context_snapshot", {})
    brand_id_str = context_snapshot.get("brand_id")
    if not brand_id_str:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot replay: no brand_id in snapshot")

    invoke_req = InvokeRequest(
        message=request.input_overrides.get("message", entry.title),
        brand_id=uuid.UUID(brand_id_str),
        modality="text",
        context={"replay_of": entry.id, **request.input_overrides},
    )
    runtime = get_runtime()
    response = await runtime.invoke(session=session, user=user, request=invoke_req)
    return {
        "session_id": response.session_id,
        "decision_id": response.decision_id,
        "stream_url": response.stream_url,
        "replay_of": entry.id,
    }


# ─── GET /runtime/sessions — list past chat sessions ─────────────────────────


@router.get("/sessions")
async def list_sessions(
    user: CurrentUser,
    session: SessionDep,
    brand_id: uuid.UUID | None = Query(None, description="Filter by brand"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """List past chat sessions (ChatGPT/Gemini-style history).

    Groups runtime_events by session_id, extracts the first user message
    as the title, and returns the most recent sessions.
    """
    from sqlalchemy import select, func, and_
    from ..models.tables import RuntimeEventRecord

    # Build query: group by session_id, get first + last event, event count
    base_filter = [RuntimeEventRecord.tenant_id == user.tenant_id]
    if brand_id:
        # Filter by brand_id stored in event data (invoke events carry it)
        base_filter.append(
            RuntimeEventRecord.data["brand_id"].astext == str(brand_id)
        )

    # Get distinct session_ids with their first event timestamp
    subq = (
        select(
            RuntimeEventRecord.session_id,
            func.min(RuntimeEventRecord.timestamp).label("first_ts"),
            func.max(RuntimeEventRecord.timestamp).label("last_ts"),
            func.count(RuntimeEventRecord.id).label("event_count"),
        )
        .where(and_(*base_filter))
        .group_by(RuntimeEventRecord.session_id)
        .order_by(func.max(RuntimeEventRecord.timestamp).desc())
        .limit(limit)
        .subquery()
    )

    res = await session.execute(select(subq))
    rows = res.all()

    sessions: list[dict[str, Any]] = []
    for row in rows:
        session_id = row.session_id
        first_ts = row.first_ts
        last_ts = row.last_ts
        event_count = row.event_count

        # Fetch the first user message (from the invoke event data)
        # and the AI reply (from the session.completed event)
        events_res = await session.execute(
            select(RuntimeEventRecord)
            .where(RuntimeEventRecord.session_id == session_id)
            .order_by(RuntimeEventRecord.timestamp.asc())
        )
        events = events_res.scalars().all()

        title = "New conversation"
        last_reply = ""
        has_artefacts = False

        for ev in events:
            # Extract user message from session.started OR session.completed
            if ev.type == "runtime.session.started" and ev.data:
                msg = ev.data.get("message") or ev.data.get("user_message")
                if msg:
                    title = msg[:80]
            if ev.type == "runtime.session.completed" and ev.data:
                # Fallback: user_message stored in completion event
                if title == "New conversation":
                    msg = ev.data.get("user_message")
                    if msg:
                        title = msg[:80]
                resp = ev.data.get("response") or {}
                last_reply = (resp.get("reply") or "")[:120]
            # Check for artefacts
            if ev.type and ev.type.startswith("artefact."):
                has_artefacts = True

        duration_s = 0
        if first_ts and last_ts:
            duration_s = int((last_ts - first_ts).total_seconds())

        sessions.append({
            "session_id": session_id,
            "title": title,
            "preview": last_reply,
            "timestamp": last_ts.isoformat() if last_ts else "",
            "created_at": first_ts.isoformat() if first_ts else "",
            "event_count": event_count,
            "duration_s": duration_s,
            "has_artefacts": has_artefacts,
        })

    return {"sessions": sessions, "count": len(sessions)}


# ─── GET /runtime/sessions/{id} — load a session's messages ──────────────────


@router.get("/sessions/{session_id}")
async def get_session_messages(
    user: CurrentUser,
    session: SessionDep,
    session_id: str,
) -> dict[str, Any]:
    """Load a past session's conversation messages (for replay/display).

    Reconstructs the user/AI message pairs from persisted runtime events.
    """
    from sqlalchemy import select
    from ..models.tables import RuntimeEventRecord

    res = await session.execute(
        select(RuntimeEventRecord)
        .where(
            RuntimeEventRecord.session_id == session_id,
            RuntimeEventRecord.tenant_id == user.tenant_id,
        )
        .order_by(RuntimeEventRecord.timestamp.asc())
    )
    events = res.scalars().all()

    if not events:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")

    messages: list[dict[str, Any]] = []
    artefacts: list[dict[str, Any]] = []
    title = "New conversation"
    created_at = ""
    user_msg_added = False

    for ev in events:
        # User message (from session.started event)
        if ev.type == "runtime.session.started" and ev.data:
            msg = ev.data.get("message") or ev.data.get("user_message")
            if msg:
                if not title or title == "New conversation":
                    title = msg[:80]
                if not created_at:
                    created_at = ev.timestamp.isoformat() if ev.timestamp else ""
                messages.append({
                    "role": "user",
                    "content": msg,
                    "timestamp": ev.timestamp.isoformat() if ev.timestamp else "",
                })
                user_msg_added = True

        # Planner explanation
        if ev.type == "planner.decision.created" and ev.data:
            explanation = ev.data.get("user_explanation")
            if explanation:
                messages.append({
                    "role": "ai",
                    "content": "",
                    "explanation": explanation,
                    "timestamp": ev.timestamp.isoformat() if ev.timestamp else "",
                })

        # Artefacts
        if ev.type and ev.type.startswith("artefact.") and ev.data:
            artefact = ev.data.get("artefact")
            if artefact:
                artefacts.append(artefact)

        # AI reply (from session.completed event)
        if ev.type == "runtime.session.completed" and ev.data:
            # Fallback: extract user message from completion event if not already added
            if not user_msg_added:
                msg = ev.data.get("user_message")
                if msg:
                    if not title or title == "New conversation":
                        title = msg[:80]
                    messages.append({
                        "role": "user",
                        "content": msg,
                        "timestamp": ev.timestamp.isoformat() if ev.timestamp else "",
                    })
                    user_msg_added = True

            resp = ev.data.get("response") or {}
            reply = resp.get("reply") or ""
            suggestions = resp.get("suggested_actions") or []
            if reply:
                messages.append({
                    "role": "ai",
                    "content": reply,
                    "suggestions": suggestions,
                    "artefacts": artefacts if artefacts else None,
                    "timestamp": ev.timestamp.isoformat() if ev.timestamp else "",
                })
                artefacts = []  # consumed

        # Error
        if ev.type == "runtime.session.error" and ev.data:
            messages.append({
                "role": "ai",
                "content": ev.data.get("error") or "Something went wrong.",
                "timestamp": ev.timestamp.isoformat() if ev.timestamp else "",
            })

    return {
        "session_id": session_id,
        "title": title,
        "created_at": created_at,
        "messages": messages,
    }


# ─── GET /dashboard/overview ────────────────────────────────────────────────


@dashboard_router.get("/overview")
async def dashboard_overview(
    user: CurrentUser,
    session: SessionDep,
    brand_id: uuid.UUID = Query(..., description="Active brand ID"),
) -> dict[str, Any]:
    """Dashboard composition — one endpoint, all sections.

    Returns: greeting, performance, campaigns, notifications, tasks, memory, orb, activity.
    Each section is composed from existing data sources. If any sub-query fails,
    that section returns null — the rest still renders.
    """
    from sqlalchemy import select, func
    from ..models import (
        Brand,
        CampaignPlanRecord,
        BusinessMemoryRecord,
        Connection,
        Billing,
        AuditEvent,
    )

    # Load brand
    brand_res = await session.execute(select(Brand).where(Brand.id == brand_id))
    brand = brand_res.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")

    # Parallel queries for dashboard sections
    import asyncio
    from ..runtime.context import (
        _load_memory,
        _load_billing,
        _load_connections,
    )

    memory_info, billing_info, connections = await asyncio.gather(
        _load_memory(session, brand_id),
        _load_billing(session, user.tenant_id),
        _load_connections(session, brand_id),
        return_exceptions=True,
    )

    # Campaigns
    campaigns_res = await session.execute(
        select(CampaignPlanRecord)
        .where(CampaignPlanRecord.brand_id == brand_id)
        .order_by(CampaignPlanRecord.created_at.desc())
        .limit(10)
    )
    campaigns = campaigns_res.scalars().all()

    active_campaigns = [c for c in campaigns if c.status == "active"]
    pending_campaigns = [c for c in campaigns if c.status in ("draft", "in_review")]

    # Recent timeline entries for activity feed
    timeline_svc = get_timeline_service()
    timeline_entries, _ = await timeline_svc.list(
        session=session,
        tenant_id=user.tenant_id,
        brand_id=brand_id,
        limit=10,
    )

    # Compose greeting
    import datetime
    now = datetime.datetime.now()
    hour = now.hour
    if hour < 12:
        greeting_text = f"Good morning, {brand.name}"
    elif hour < 17:
        greeting_text = f"Good afternoon, {brand.name}"
    else:
        greeting_text = f"Good evening, {brand.name}"

    pending_count = len(pending_campaigns)
    active_count = len(active_campaigns)

    greeting_suffix = ""
    if pending_count > 0:
        greeting_suffix = f". You have {pending_count} campaign{'s' if pending_count > 1 else ''} waiting for review"
    elif active_count > 0:
        greeting_suffix = f". {active_count} campaign{'s' if active_count > 1 else ''} running smoothly"

    # Memory reference
    memory_ref = ""
    if isinstance(memory_info, type(None)):
        memory_info = None
    if memory_info and hasattr(memory_info, "best_practices") and memory_info.best_practices:
        memory_ref = f" Last time, {memory_info.best_practices[0]}"

    # Compose KPIs
    visibility = brand.visibility_score or 0
    kpis = [
        {"label": "Active campaigns", "value": active_count, "trend": "Running" if active_count > 0 else "None", "trend_up": active_count > 0},
        {"label": "Pending review", "value": pending_count, "trend": "Waiting" if pending_count > 0 else "All clear", "trend_up": pending_count == 0},
        {"label": "Visibility", "value": int(visibility), "trend": f"{visibility:.0f}/100", "trend_up": visibility >= 50},
    ]

    # AI team status (static for now — will be wired to worker status)
    ai_team = [
        {"agent": "Marketing", "status": "idle", "detail": "Ready to create content", "icon": "📢"},
        {"agent": "Finance", "status": "idle", "detail": "Monitoring budget", "icon": "💰"},
        {"agent": "Researcher", "status": "idle", "detail": "Standing by", "icon": "📊"},
        {"agent": "Social", "status": "idle", "detail": "Ready to publish", "icon": "💬"},
    ]

    # Activity feed from timeline
    activity = [
        {
            "id": e.id,
            "entry_type": e.entry_type,
            "actor": e.actor,
            "title": e.title,
            "summary": e.summary,
            "created_at": e.created_at,
        }
        for e in timeline_entries
    ]

    # Memory section
    memory_section = {}
    if memory_info and hasattr(memory_info, "best_practices"):
        memory_section = {
            "recent_learnings": memory_info.best_practices[:5],
            "total_campaigns": memory_info.total_campaigns,
            "average_roi": memory_info.average_roi,
        }

    # Orb suggestions
    suggestions = ["Create a campaign", "How are my ads doing?", "Generate an image", "What needs attention?"]

    return {
        "greeting": {
            "text": greeting_text + greeting_suffix + memory_ref,
            "action_buttons": [
                {"label": "Create campaign", "intent": "campaign.create"},
                {"label": "Show analytics", "href": "/app/analytics"},
                {"label": f"Review ({pending_count})" if pending_count > 0 else "Review", "href": "/app/review"},
            ],
            "memory_reference": memory_ref,
        },
        "performance": {
            "kpis": kpis,
        },
        "campaigns": {
            "active": [
                {"id": str(c.id), "name": c.name, "goal": c.goal, "status": c.status}
                for c in active_campaigns[:5]
            ],
            "pending": [
                {"id": str(c.id), "name": c.name, "status": c.status}
                for c in pending_campaigns[:5]
            ],
        },
        "notifications": {
            "items": [],
            "count": 0,
        },
        "tasks": {
            "ai_team": ai_team,
        },
        "memory": memory_section,
        "orb": {
            "state": "idle",
            "suggestions": suggestions,
        },
        "activity": {
            "items": activity,
        },
    }
