"""Workspace Timeline — the single source of truth.

Constitution Rule 4: Every Decision creates Timeline entries. Nothing happens outside the Timeline.
Constitution Rule 5: Every Timeline event is replayable. No exceptions.
Constitution Rule 14: The Workspace Timeline is immutable. Never edit history. Only append. Like Git.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..models.base import Base, TenantScoped, UUIDPK, utcnow

log = logging.getLogger("prachar.runtime.timeline")


# ─── Timeline Table ─────────────────────────────────────────────────────────


class WorkspaceTimeline(Base, UUIDPK, TenantScoped):
    """Workspace Timeline — immutable, append-only.

    Every action, every output, every decision, every learning.
    This is the single source of truth for the workspace.
    """

    __tablename__ = "workspace_timeline"

    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), index=True, nullable=True
    )
    decision_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), index=True, nullable=True
    )
    entry_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    replayable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    replay_inputs: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = (
        Index("idx_timeline_brand_created", "brand_id", "created_at"),
        Index("idx_timeline_session", "session_id"),
        Index("idx_timeline_decision", "decision_id"),
        Index("idx_timeline_type", "entry_type"),
    )


# ─── Timeline Entry (DTO) ───────────────────────────────────────────────────


@dataclass
class TimelineEntry:
    """Data transfer object for timeline entries."""

    id: str = ""
    brand_id: str | None = None
    session_id: str | None = None
    decision_id: str | None = None
    entry_type: str = ""
    actor: str = ""
    title: str = ""
    summary: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    replayable: bool = False
    replay_inputs: dict[str, Any] | None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "brand_id": self.brand_id,
            "session_id": self.session_id,
            "decision_id": self.decision_id,
            "entry_type": self.entry_type,
            "actor": self.actor,
            "title": self.title,
            "summary": self.summary,
            "detail": self.detail,
            "replayable": self.replayable,
            "replay_inputs": self.replay_inputs,
            "created_at": self.created_at,
        }


# ─── Timeline Service ───────────────────────────────────────────────────────


class TimelineService:
    """Appends entries to the Workspace Timeline and queries them.

    Constitution Rule 14: Immutable. Only append. Never edit.
    """

    async def append(
        self,
        session: "AsyncSession",
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID | None,
        entry_type: str,
        actor: str,
        title: str,
        summary: str | None = None,
        detail: dict[str, Any] | None = None,
        session_id: uuid.UUID | None = None,
        decision_id: uuid.UUID | None = None,
        replayable: bool = False,
        replay_inputs: dict[str, Any] | None = None,
    ) -> TimelineEntry:
        """Append a new entry to the timeline. Never update existing entries."""
        entry = WorkspaceTimeline(
            tenant_id=tenant_id,
            brand_id=brand_id,
            session_id=session_id,
            decision_id=decision_id,
            entry_type=entry_type,
            actor=actor,
            title=title,
            summary=summary,
            detail=detail,
            replayable=replayable,
            replay_inputs=replay_inputs,
        )
        session.add(entry)
        await session.flush()
        return TimelineEntry(
            id=str(entry.id),
            brand_id=str(brand_id) if brand_id else None,
            session_id=str(session_id) if session_id else None,
            decision_id=str(decision_id) if decision_id else None,
            entry_type=entry_type,
            actor=actor,
            title=title,
            summary=summary,
            detail=detail or {},
            replayable=replayable,
            replay_inputs=replay_inputs,
            created_at=entry.created_at.isoformat() if entry.created_at else "",
        )

    async def list(
        self,
        session: "AsyncSession",
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID | None = None,
        limit: int = 50,
        cursor: str | None = None,
        entry_type: str | None = None,
    ) -> tuple[list[TimelineEntry], str | None]:
        """List timeline entries (newest first, cursor-based pagination)."""
        query = select(WorkspaceTimeline).where(
            WorkspaceTimeline.tenant_id == tenant_id
        )
        if brand_id:
            query = query.where(WorkspaceTimeline.brand_id == brand_id)
        if entry_type:
            query = query.where(WorkspaceTimeline.entry_type == entry_type)
        if cursor:
            try:
                cursor_uuid = uuid.UUID(cursor)
                query = query.where(WorkspaceTimeline.id < cursor_uuid)
            except ValueError:
                pass

        query = query.order_by(WorkspaceTimeline.created_at.desc()).limit(limit + 1)
        res = await session.execute(query)
        rows = res.scalars().all()

        next_cursor = None
        if len(rows) > limit:
            next_cursor = str(rows[limit - 1].id)
            rows = rows[:limit]

        entries = [
            TimelineEntry(
                id=str(r.id),
                brand_id=str(r.brand_id) if r.brand_id else None,
                session_id=str(r.session_id) if r.session_id else None,
                decision_id=str(r.decision_id) if r.decision_id else None,
                entry_type=r.entry_type,
                actor=r.actor,
                title=r.title,
                summary=r.summary,
                detail=r.detail or {},
                replayable=r.replayable,
                replay_inputs=r.replay_inputs,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in rows
        ]
        return entries, next_cursor

    async def get(
        self,
        session: "AsyncSession",
        tenant_id: uuid.UUID,
        entry_id: uuid.UUID,
    ) -> TimelineEntry | None:
        """Get a single timeline entry."""
        res = await session.execute(
            select(WorkspaceTimeline).where(
                WorkspaceTimeline.id == entry_id,
                WorkspaceTimeline.tenant_id == tenant_id,
            )
        )
        r = res.scalar_one_or_none()
        if r is None:
            return None
        return TimelineEntry(
            id=str(r.id),
            brand_id=str(r.brand_id) if r.brand_id else None,
            session_id=str(r.session_id) if r.session_id else None,
            decision_id=str(r.decision_id) if r.decision_id else None,
            entry_type=r.entry_type,
            actor=r.actor,
            title=r.title,
            summary=r.summary,
            detail=r.detail or {},
            replayable=r.replayable,
            replay_inputs=r.replay_inputs,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )


# ─── Type imports (avoid circular) ──────────────────────────────────────────

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402
