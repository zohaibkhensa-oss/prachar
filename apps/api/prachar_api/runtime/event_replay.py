"""Event Replay Service — persists and replays runtime event streams.

Every event published to the EventBus is also persisted to the database.
This enables:
- debugging: see exactly what happened in a session
- visual replay: reconstruct the orb state transitions
- deterministic testing: replay events without re-running tools
- session reconstruction: rebuild the full session state
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.tables import RuntimeEventRecord
from .events import AIEvent

log = logging.getLogger("prachar.runtime.event_replay")


# ─── Replay Result ───────────────────────────────────────────────────────────


@dataclass
class ReplayResult:
    """The reconstructed result of replaying a session's event stream."""

    session_id: str
    events: list[AIEvent] = field(default_factory=list)
    orb_state_transitions: list[dict[str, Any]] = field(default_factory=list)
    tool_executions: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: int = 0
    event_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "events": [e.to_dict() for e in self.events],
            "orb_state_transitions": self.orb_state_transitions,
            "tool_executions": self.tool_executions,
            "duration_ms": self.duration_ms,
            "event_count": self.event_count,
        }


# ─── Persistence ─────────────────────────────────────────────────────────────


async def persist_event(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    event: AIEvent,
) -> None:
    """Save a single event to the database.

    Called by the EventBus persist callback (set by the Runtime). Failures are
    logged but never raised — persistence must not break the event stream.
    """
    try:
        # Parse the ISO-8601 timestamp string back into a datetime.
        ts = _parse_timestamp(event.timestamp)
        record = RuntimeEventRecord(
            tenant_id=tenant_id,
            session_id=event.session_id,
            decision_id=event.decision_id,
            type=event.type,
            phase=event.phase,
            tool=event.tool,
            orb_state=event.orb_state,
            data=event.data or {},
            progress=event.progress,
            timestamp=ts,
        )
        session.add(record)
        await session.flush()
    except Exception as exc:  # noqa: BLE001
        log.warning("failed to persist event %s: %s", event.type, exc)


async def get_session_events(
    session: AsyncSession,
    session_id: str,
) -> list[AIEvent]:
    """Return all persisted events for a session, ordered by timestamp."""
    query = (
        select(RuntimeEventRecord)
        .where(RuntimeEventRecord.session_id == session_id)
        .order_by(RuntimeEventRecord.timestamp.asc())
    )
    res = await session.execute(query)
    rows = res.scalars().all()
    return [_record_to_event(r) for r in rows]


async def replay_session(
    session_id: str,
    tenant_id: str | None = None,
) -> ReplayResult:
    """Reconstruct a session from its persisted events.

    Opens its own DB session (the caller may not have one). When ``tenant_id``
    is provided, the RLS context is set so tenant-scoped rows are visible.
    Returns a ReplayResult containing the full event stream, orb state
    transitions, and tool executions extracted from the events.
    """
    from ..db import session_scope

    async with session_scope(tenant_id=tenant_id) as db_session:
        events = await get_session_events(db_session, session_id)

    orb_state_transitions: list[dict[str, Any]] = []
    tool_executions: list[dict[str, Any]] = []
    seen_orb_states: set[str] = set()
    first_ts: datetime | None = None
    last_ts: datetime | None = None

    for ev in events:
        ts = _parse_timestamp(ev.timestamp)
        if first_ts is None:
            first_ts = ts
        last_ts = ts

        # Orb state transitions — record each new state in order.
        if ev.orb_state and ev.orb_state not in seen_orb_states:
            orb_state_transitions.append({
                "from": list(seen_orb_states)[-1] if seen_orb_states else None,
                "to": ev.orb_state,
                "timestamp": ev.timestamp,
                "event_type": ev.type,
            })
            seen_orb_states.add(ev.orb_state)

        # Tool executions — events that carry a tool name.
        if ev.tool:
            tool_executions.append({
                "tool": ev.tool,
                "type": ev.type,
                "phase": ev.phase,
                "timestamp": ev.timestamp,
                "decision_id": ev.decision_id,
                "data": ev.data,
            })

    duration_ms = 0
    if first_ts is not None and last_ts is not None:
        duration_ms = int((last_ts - first_ts).total_seconds() * 1000)

    return ReplayResult(
        session_id=session_id,
        events=events,
        orb_state_transitions=orb_state_transitions,
        tool_executions=tool_executions,
        duration_ms=duration_ms,
        event_count=len(events),
    )


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _parse_timestamp(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp string into a timezone-aware datetime."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.utcnow()


def _record_to_event(r: RuntimeEventRecord) -> AIEvent:
    """Convert a persisted RuntimeEventRecord back into an AIEvent."""
    return AIEvent(
        session_id=r.session_id,
        type=r.type,
        phase=r.phase,
        timestamp=r.timestamp.isoformat() if r.timestamp else "",
        decision_id=r.decision_id,
        tool=r.tool,
        orb_state=r.orb_state,
        data=r.data or {},
        progress=r.progress,
    )
