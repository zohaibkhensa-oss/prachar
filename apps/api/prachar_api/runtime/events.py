"""Event Bus — unified event protocol for the AI Runtime.

Constitution Rule 8: Everything emits Runtime Events. No silent execution.
Constitution Rule 13: Streaming belongs to the Event Bus. Never build individual streaming logic.

Every event has the same envelope. The frontend renders events; it doesn't
care whether they came from Chat, CampaignBrain, Agency Council, or Creative.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Awaitable, Callable

log = logging.getLogger("prachar.runtime.events")

# Type alias for the optional persistence callback.
# When set on an EventBus, every published event is also passed to this
# coroutine. The Runtime sets it to persist events to the database.
# (AIEvent is defined below; use a string forward reference to avoid a
# NameError at import time.)
PersistCallback = Callable[["AIEvent"], Awaitable[None]]


# ─── Orb State Machine (13 states, frozen) ──────────────────────────────────


class OrbState(str, Enum):
    """The 13 orb states. Every event carries an orb_state.

    The frontend simply sets the orb to whatever state an event carries.
    State transitions are enforced by the Runtime, not the frontend.
    """

    IDLE = "idle"
    WAKE = "wake"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    REASONING = "reasoning"
    EXECUTING = "executing"
    GENERATING = "generating"
    WAITING_APPROVAL = "waiting_approval"
    SPEAKING = "speaking"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


# ─── Event Phase ────────────────────────────────────────────────────────────


class EventPhase(str, Enum):
    """Lifecycle phase of an event."""

    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


# ─── Event Envelope ─────────────────────────────────────────────────────────


@dataclass
class AIEvent:
    """Every event across all capabilities has this shape.

    The frontend implements ONE event handler that switches on ``type``.
    """

    session_id: str
    type: str                        # e.g. "campaign.analysis.completed"
    phase: str                       # "started" | "progress" | "completed" | ...
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    decision_id: str | None = None   # links to Decision Contract
    tool: str | None = None          # which tool emitted this
    data: dict[str, Any] = field(default_factory=dict)
    orb_state: str = OrbState.IDLE.value
    progress: dict[str, Any] | None = None   # {completed, total, label}

    def to_sse(self) -> str:
        """Serialise as an SSE data line."""
        payload = {
            "session_id": self.session_id,
            "type": self.type,
            "phase": self.phase,
            "timestamp": self.timestamp,
            "decision_id": self.decision_id,
            "tool": self.tool,
            "data": self.data,
            "orb_state": self.orb_state,
            "progress": self.progress,
        }
        return f"data: {json.dumps(payload, default=str)}\n\n"

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "type": self.type,
            "phase": self.phase,
            "timestamp": self.timestamp,
            "decision_id": self.decision_id,
            "tool": self.tool,
            "data": self.data,
            "orb_state": self.orb_state,
            "progress": self.progress,
        }


# ─── Event Bus ──────────────────────────────────────────────────────────────


class EventBus:
    """In-memory event bus per session.

    Each Runtime session has its own EventBus. The frontend subscribes
    via SSE to ``GET /runtime/stream?session_id=xxx``.

    Events are:
    1. Published by the Execution Engine as tools run
    2. Buffered in an asyncio.Queue
    3. Consumed by the SSE endpoint

    Events are also persisted to the Workspace Timeline (by the Runtime).
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._queue: asyncio.Queue[AIEvent | None] = asyncio.Queue()
        self._closed = False
        self._all_events: list[AIEvent] = []  # for replay/debugging
        self._persist_callback: PersistCallback | None = None

    def set_persist_callback(self, callback: PersistCallback | None) -> None:
        """Set (or clear) the persistence callback.

        When set, every published event is also passed to this coroutine so it
        can be persisted to the database. The Runtime sets this to wire the
        EventBus to the Event Replay Service.
        """
        self._persist_callback = callback

    async def publish(self, event: AIEvent) -> None:
        """Publish an event. Also stores it for replay and persists it."""
        if self._closed:
            return
        # Ensure session_id is set
        if not event.session_id:
            event.session_id = self.session_id
        self._all_events.append(event)
        await self._queue.put(event)
        # Persist to the database if a callback is wired (Phase E2.1).
        if self._persist_callback is not None:
            try:
                await self._persist_callback(event)
            except Exception as exc:  # noqa: BLE001
                log.warning("persist callback failed for %s: %s", event.type, exc)
        log.debug("event published: %s (session=%s)", event.type, self.session_id)

    async def stream(self) -> AsyncIterator[AIEvent]:
        """Stream events as they arrive. Ends when close() is called."""
        while True:
            event = await self._queue.get()
            if event is None:  # sentinel — stream ended
                break
            yield event

    async def close(self) -> None:
        """Signal that the stream should end."""
        self._closed = True
        await self._queue.put(None)

    def get_all_events(self) -> list[AIEvent]:
        """All events published to this bus (for debugging/replay)."""
        return list(self._all_events)

    @property
    def is_closed(self) -> bool:
        return self._closed


# ─── Event Factory Helpers ──────────────────────────────────────────────────


def make_artefact_event(
    session_id: str,
    artefact: Any,  # Artefact
    decision_id: str | None = None,
    tool: str | None = None,
) -> AIEvent:
    """Create an artefact event for live capability rendering (Phase D).

    Artefact events have type "artefact.<kind>" and carry the artefact
    in data.artefact. The frontend renders these as rich UI components.
    Note: This is a sync function (returns AIEvent directly, not a coroutine).
    """
    return AIEvent(
        session_id=session_id,
        type=f"artefact.{artefact.kind}",
        phase=EventPhase.COMPLETED.value,
        timestamp=datetime.now(timezone.utc).isoformat(),
        decision_id=decision_id,
        tool=tool,
        orb_state=OrbState.GENERATING.value,
        data={"artefact": artefact.to_dict()},
        progress=None,
    )


def make_event(
    session_id: str,
    type: str,
    phase: str = EventPhase.COMPLETED.value,
    decision_id: str | None = None,
    tool: str | None = None,
    data: dict[str, Any] | None = None,
    orb_state: str = OrbState.IDLE.value,
    progress: dict[str, Any] | None = None,
) -> AIEvent:
    """Convenience factory for creating events."""
    return AIEvent(
        session_id=session_id,
        type=type,
        phase=phase,
        decision_id=decision_id,
        tool=tool,
        data=data or {},
        orb_state=orb_state,
        progress=progress,
    )


# ─── Session Manager ────────────────────────────────────────────────────────


class SessionManager:
    """Manages active Runtime sessions and their event buses.

    A session is created when POST /runtime/invoke is called.
    It lives until the session completes, is cancelled, or times out.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, EventBus] = {}
        self._lock = asyncio.Lock()

    async def create_session(self) -> tuple[str, EventBus]:
        """Create a new session and return (session_id, event_bus)."""
        session_id = str(uuid.uuid4())
        bus = EventBus(session_id)
        async with self._lock:
            self._sessions[session_id] = bus
        return session_id, bus

    async def get_bus(self, session_id: str) -> EventBus | None:
        async with self._lock:
            return self._sessions.get(session_id)

    async def close_session(self, session_id: str) -> None:
        async with self._lock:
            bus = self._sessions.get(session_id)
            if bus:
                await bus.close()
                # Keep the bus around for a bit so late subscribers can read buffered events
                # In production, this would have a TTL cleanup

    async def remove_session(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)


# Global session manager
_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
