"""Event Replay Tests — Phase E2.1.

Verifies:
- RuntimeEventRecord model exists and maps to runtime_events
- persist_event saves events to the DB
- get_session_events returns events in timestamp order
- replay_session reconstructs orb state transitions
- replay_session reconstructs tool executions
- EventBus persist_callback is called on publish
- ReplayResult has the correct fields
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "packages", "shared"))

# Ensure env is loaded before settings is cached.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://prachar:prachar@localhost:5432/prachar")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-jwt-xxxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-secret-refresh-xxxxxxxxxxxxxxxxx")
os.environ.setdefault("TOKEN_ENC_KEY", "a" * 64)

from prachar_shared.config import get_settings  # noqa: E402

get_settings.cache_clear()

from sqlalchemy import text  # noqa: E402

from prachar_api.db import get_sessionmaker  # noqa: E402
from prachar_api.models import Tenant  # noqa: E402
from prachar_api.models.tables import RuntimeEventRecord  # noqa: E402
from prachar_api.runtime.events import AIEvent, EventBus, OrbState  # noqa: E402
from prachar_api.runtime.event_replay import (  # noqa: E402
    ReplayResult,
    get_session_events,
    persist_event,
    replay_session,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_session():
    """A real AsyncSession with RLS context set to a real test tenant.

    Creates a Tenant row so the runtime_events FK constraint is satisfied.
    Cleans up the tenant afterwards.
    """
    import prachar_api.db as dbmod

    if dbmod._engine is not None:
        await dbmod._engine.dispose()
        dbmod._engine = None
        dbmod._sessionmaker = None

    sm = get_sessionmaker()
    tenant_id = uuid.uuid4()
    # Create the tenant outside RLS (no tenant_id set yet).
    async with sm() as setup_session:
        setup_session.add(Tenant(id=tenant_id, name="Event Replay Test Tenant"))
        await setup_session.commit()

    async with sm() as session:
        # Use is_local=false so the RLS context survives across commits
        # within this session (persist_event + commit + get_session_events).
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, false)"), {"tid": str(tenant_id)}
        )
        yield session, tenant_id
        await session.rollback()

    # Clean up the tenant and any events (set RLS context for the DELETE).
    async with sm() as cleanup_session:
        await cleanup_session.execute(
            text("SELECT set_config('app.tenant_id', :tid, false)"), {"tid": str(tenant_id)}
        )
        await cleanup_session.execute(
            text("DELETE FROM runtime_events WHERE tenant_id = :tid"),
            {"tid": str(tenant_id)},
        )
        await cleanup_session.commit()
    # Tenants table has no RLS, so delete outside RLS context.
    async with sm() as cleanup_session:
        await cleanup_session.execute(
            text("DELETE FROM tenants WHERE id = :tid"), {"tid": str(tenant_id)}
        )
        await cleanup_session.commit()

    if dbmod._engine is not None:
        await dbmod._engine.dispose()
        dbmod._engine = None
        dbmod._sessionmaker = None


def _make_event(
    session_id: str,
    type: str = "tool.started",
    phase: str = "started",
    orb_state: str = OrbState.EXECUTING.value,
    tool: str | None = "campaign_brain.analyse",
    decision_id: str | None = None,
    timestamp: str | None = None,
) -> AIEvent:
    return AIEvent(
        session_id=session_id,
        type=type,
        phase=phase,
        orb_state=orb_state,
        tool=tool,
        decision_id=decision_id,
        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
        data={"key": "value"},
    )


# ─── Model Tests ─────────────────────────────────────────────────────────────


class TestRuntimeEventRecordModel:
    def test_model_exists(self):
        """RuntimeEventRecord model exists and maps to runtime_events."""
        assert RuntimeEventRecord.__tablename__ == "runtime_events"

    def test_model_has_required_columns(self):
        """The model has all the columns specified in the migration."""
        cols = {c.name for c in RuntimeEventRecord.__table__.columns}
        expected = {
            "id",
            "tenant_id",
            "session_id",
            "decision_id",
            "type",
            "phase",
            "tool",
            "orb_state",
            "data",
            "progress",
            "timestamp",
        }
        assert expected.issubset(cols), f"missing columns: {expected - cols}"

    def test_model_has_indexes(self):
        """The model has indexes on session_id, type, and timestamp."""
        index_cols = set()
        for idx in RuntimeEventRecord.__table__.indexes:
            for col in idx.columns:
                index_cols.add(col.name)
        assert "session_id" in index_cols
        assert "type" in index_cols
        assert "timestamp" in index_cols


# ─── Persistence Tests ───────────────────────────────────────────────────────


class TestPersistEvent:
    @pytest.mark.asyncio
    async def test_persist_event_saves_to_db(self, db_session):
        """persist_event saves an event to the DB."""
        session, tenant_id = db_session
        sid = f"test-{uuid.uuid4().hex[:8]}"
        event = _make_event(sid, type="runtime.session.started", tool=None)
        await persist_event(session, tenant_id, event)
        await session.commit()

        events = await get_session_events(session, sid)
        assert len(events) == 1
        assert events[0].type == "runtime.session.started"
        assert events[0].session_id == sid

    @pytest.mark.asyncio
    async def test_persist_event_with_tool_and_progress(self, db_session):
        """persist_event saves tool and progress fields."""
        session, tenant_id = db_session
        sid = f"test-{uuid.uuid4().hex[:8]}"
        event = AIEvent(
            session_id=sid,
            type="tool.progress",
            phase="progress",
            tool="campaign_brain.analyse",
            orb_state=OrbState.EXECUTING.value,
            data={"step": 2},
            progress={"completed": 2, "total": 5, "label": "analysing"},
        )
        await persist_event(session, tenant_id, event)
        await session.commit()

        events = await get_session_events(session, sid)
        assert len(events) == 1
        assert events[0].tool == "campaign_brain.analyse"
        assert events[0].progress == {"completed": 2, "total": 5, "label": "analysing"}


# ─── Query Tests ─────────────────────────────────────────────────────────────


class TestGetSessionEvents:
    @pytest.mark.asyncio
    async def test_returns_events_in_order(self, db_session):
        """get_session_events returns events ordered by timestamp."""
        session, tenant_id = db_session
        sid = f"order-{uuid.uuid4().hex[:8]}"
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            _make_event(sid, type="e.first", timestamp=base.isoformat()),
            _make_event(sid, type="e.second", timestamp=base.replace(second=5).isoformat()),
            _make_event(sid, type="e.third", timestamp=base.replace(second=10).isoformat()),
        ]
        for ev in events:
            await persist_event(session, tenant_id, ev)
        await session.commit()

        result = await get_session_events(session, sid)
        assert len(result) == 3
        assert result[0].type == "e.first"
        assert result[1].type == "e.second"
        assert result[2].type == "e.third"

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_session(self, db_session):
        """get_session_events returns [] for an unknown session."""
        session, _ = db_session
        result = await get_session_events(session, "nonexistent-session")
        assert result == []


# ─── Replay Tests ────────────────────────────────────────────────────────────


class TestReplaySession:
    @pytest.mark.asyncio
    async def test_reconstructs_orb_state_transitions(self, db_session):
        """replay_session reconstructs orb state transitions."""
        session, tenant_id = db_session
        sid = f"orb-{uuid.uuid4().hex[:8]}"
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            _make_event(sid, type="s.started", orb_state=OrbState.UNDERSTANDING.value,
                        tool=None, timestamp=base.isoformat()),
            _make_event(sid, type="s.planning", orb_state=OrbState.PLANNING.value,
                        tool=None, timestamp=base.replace(second=2).isoformat()),
            _make_event(sid, type="s.executing", orb_state=OrbState.EXECUTING.value,
                        tool="campaign_brain.analyse",
                        timestamp=base.replace(second=4).isoformat()),
            _make_event(sid, type="s.completed", orb_state=OrbState.COMPLETED.value,
                        tool=None, timestamp=base.replace(second=8).isoformat()),
        ]
        for ev in events:
            await persist_event(session, tenant_id, ev)
        await session.commit()

        result = await replay_session(sid)
        assert result.session_id == sid
        assert result.event_count == 4
        # Orb state transitions: understanding -> planning -> executing -> completed
        states = [t["to"] for t in result.orb_state_transitions]
        assert states == [
            OrbState.UNDERSTANDING.value,
            OrbState.PLANNING.value,
            OrbState.EXECUTING.value,
            OrbState.COMPLETED.value,
        ]
        # First transition has no "from"
        assert result.orb_state_transitions[0]["from"] is None
        assert result.orb_state_transitions[1]["from"] == OrbState.UNDERSTANDING.value

    @pytest.mark.asyncio
    async def test_reconstructs_tool_executions(self, db_session):
        """replay_session reconstructs tool executions."""
        session, tenant_id = db_session
        sid = f"tools-{uuid.uuid4().hex[:8]}"
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            _make_event(sid, type="tool.started", phase="started",
                        tool="campaign_brain.analyse",
                        timestamp=base.isoformat()),
            _make_event(sid, type="tool.completed", phase="completed",
                        tool="campaign_brain.analyse",
                        timestamp=base.replace(second=3).isoformat()),
            _make_event(sid, type="tool.started", phase="started",
                        tool="creative_studio.generate",
                        timestamp=base.replace(second=5).isoformat()),
        ]
        for ev in events:
            await persist_event(session, tenant_id, ev)
        await session.commit()

        result = await replay_session(sid)
        assert len(result.tool_executions) == 3
        assert result.tool_executions[0]["tool"] == "campaign_brain.analyse"
        assert result.tool_executions[0]["phase"] == "started"
        assert result.tool_executions[1]["tool"] == "campaign_brain.analyse"
        assert result.tool_executions[1]["phase"] == "completed"
        assert result.tool_executions[2]["tool"] == "creative_studio.generate"

    @pytest.mark.asyncio
    async def test_duration_ms(self, db_session):
        """replay_session computes duration between first and last event."""
        session, tenant_id = db_session
        sid = f"dur-{uuid.uuid4().hex[:8]}"
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        await persist_event(session, tenant_id,
            _make_event(sid, timestamp=base.isoformat()))
        await persist_event(session, tenant_id,
            _make_event(sid, timestamp=base.replace(second=5).isoformat()))
        await session.commit()

        result = await replay_session(sid)
        assert result.duration_ms == 5000

    @pytest.mark.asyncio
    async def test_empty_session(self, db_session):
        """replay_session returns an empty result for an unknown session."""
        _, tenant_id = db_session
        result = await replay_session("no-such-session-replay", tenant_id=str(tenant_id))
        assert result.event_count == 0
        assert result.events == []
        assert result.orb_state_transitions == []
        assert result.tool_executions == []


# ─── EventBus Persist Callback Tests ─────────────────────────────────────────


class TestEventBusPersistCallback:
    def test_persist_callback_called_on_publish(self):
        """EventBus persist_callback is called when an event is published."""
        async def run():
            bus = EventBus("cb-session")
            callback = AsyncMock()
            bus.set_persist_callback(callback)

            event = AIEvent(
                session_id="cb-session",
                type="tool.started",
                phase="started",
                orb_state=OrbState.EXECUTING.value,
            )
            await bus.publish(event)

            callback.assert_awaited_once_with(event)

        asyncio.run(run())

    def test_persist_callback_not_required(self):
        """EventBus works fine without a persist callback."""
        async def run():
            bus = EventBus("no-cb-session")
            await bus.publish(AIEvent(
                session_id="no-cb-session",
                type="test.event",
                phase="started",
            ))
            events = bus.get_all_events()
            assert len(events) == 1

        asyncio.run(run())

    def test_persist_callback_failure_does_not_break_publish(self):
        """A failing persist callback does not break the event stream."""
        async def run():
            bus = EventBus("fail-cb-session")
            bad_callback = AsyncMock(side_effect=RuntimeError("db down"))
            bus.set_persist_callback(bad_callback)

            event = AIEvent(
                session_id="fail-cb-session",
                type="tool.started",
                phase="started",
            )
            await bus.publish(event)
            # Event is still buffered despite the callback failure
            assert len(bus.get_all_events()) == 1

        asyncio.run(run())

    def test_set_and_clear_persist_callback(self):
        """set_persist_callback can set and clear the callback."""
        async def run():
            bus = EventBus("toggle-cb")
            assert bus._persist_callback is None

            callback = AsyncMock()
            bus.set_persist_callback(callback)
            assert bus._persist_callback is callback

            bus.set_persist_callback(None)
            assert bus._persist_callback is None

        asyncio.run(run())


# ─── ReplayResult Dataclass Tests ────────────────────────────────────────────


class TestReplayResult:
    def test_has_correct_fields(self):
        """ReplayResult has the correct fields with defaults."""
        result = ReplayResult(session_id="test-session")
        assert result.session_id == "test-session"
        assert result.events == []
        assert result.orb_state_transitions == []
        assert result.tool_executions == []
        assert result.duration_ms == 0
        assert result.event_count == 0

    def test_to_dict(self):
        """ReplayResult.to_dict serialises correctly."""
        result = ReplayResult(
            session_id="s1",
            events=[AIEvent(session_id="s1", type="t", phase="p")],
            orb_state_transitions=[{"from": None, "to": "idle"}],
            tool_executions=[{"tool": "x", "phase": "started"}],
            duration_ms=1500,
            event_count=1,
        )
        d = result.to_dict()
        assert d["session_id"] == "s1"
        assert d["duration_ms"] == 1500
        assert d["event_count"] == 1
        assert len(d["events"]) == 1
        assert d["orb_state_transitions"] == [{"from": None, "to": "idle"}]
        assert d["tool_executions"] == [{"tool": "x", "phase": "started"}]
