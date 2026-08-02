"""Council Memory — persists council decisions, minority opinions, and learnings.

Uses the same dependency-inversion pattern as BusinessMemoryStore:
- CouncilMemoryRepository Protocol defined here (domain)
- PostgresCouncilRepository implemented in the API app (infrastructure)
- CouncilMemoryStore depends on the protocol, not on SQLAlchemy

Architecture:
    Domain (this file) defines CouncilMemoryRepository protocol
         ↑
    Infrastructure (api) implements PostgresCouncilRepository
         ↑
    Application (council) uses CouncilMemoryStore(repository)
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Protocol, runtime_checkable

from .models import CouncilLearning, CouncilSession

logger = logging.getLogger(__name__)


@runtime_checkable
class CouncilMemoryRepository(Protocol):
    """Protocol for reading and writing council memory."""

    async def save_session(self, session: dict[str, Any]) -> None:
        """Persist a council session (with all opinions and decision)."""
        ...

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Load a council session by ID. Returns None if not found."""
        ...

    async def list_sessions(
        self,
        tenant_id: str,
        brand_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List council sessions for a tenant, optionally filtered by brand."""
        ...

    async def get_session_by_campaign(
        self, tenant_id: str, campaign_id: str
    ) -> dict[str, Any] | None:
        """Get the most recent council session for a campaign."""
        ...

    async def save_learning(self, learning: dict[str, Any]) -> None:
        """Persist a council learning."""
        ...

    async def list_learnings(
        self,
        tenant_id: str,
        brand_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List council learnings for a tenant."""
        ...

    async def update_learning_outcome(
        self, learning_id: str, outcome: str
    ) -> None:
        """Update the outcome of a learning (success/failure) after the campaign runs."""
        ...


class InMemoryCouncilRepository:
    """Simple in-memory implementation of CouncilMemoryRepository.

    Useful for tests and stub mode. No persistence.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}
        self._learnings: dict[str, dict[str, Any]] = {}
        self._learning_counter = 0

    async def save_session(self, session: dict[str, Any]) -> None:
        sid = session.get("session_id", "")
        if not sid:
            sid = str(uuid.uuid4())
            session["session_id"] = sid
        self._sessions[sid] = dict(session)

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        s = self._sessions.get(session_id)
        return dict(s) if s else None

    async def list_sessions(
        self,
        tenant_id: str,
        brand_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        results = []
        for s in self._sessions.values():
            if s.get("tenant_id") != tenant_id:
                continue
            if brand_id and s.get("brand_id") != brand_id:
                continue
            results.append(dict(s))
        return results[:limit]

    async def get_session_by_campaign(
        self, tenant_id: str, campaign_id: str
    ) -> dict[str, Any] | None:
        for s in self._sessions.values():
            if (s.get("tenant_id") == tenant_id
                    and s.get("campaign_id") == campaign_id):
                return dict(s)
        return None

    async def save_learning(self, learning: dict[str, Any]) -> None:
        self._learning_counter += 1
        lid = learning.get("learning_id") or f"learning-{self._learning_counter}"
        learning["learning_id"] = lid
        self._learnings[lid] = dict(learning)

    async def list_learnings(
        self,
        tenant_id: str,
        brand_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        results = []
        for l in self._learnings.values():
            if l.get("tenant_id") != tenant_id:
                continue
            if brand_id and l.get("brand_id") != brand_id:
                continue
            results.append(dict(l))
        return results[:limit]

    async def update_learning_outcome(
        self, learning_id: str, outcome: str
    ) -> None:
        if learning_id in self._learnings:
            self._learnings[learning_id]["outcome"] = outcome


class CouncilMemoryStore:
    """Reads and writes council memory via a CouncilMemoryRepository.

    Phase 6 pattern: depends on the protocol, not on SQLAlchemy.
    """

    def __init__(self, repository: CouncilMemoryRepository | None = None) -> None:
        self._repository = repository or InMemoryCouncilRepository()

    async def save_session(self, session: CouncilSession) -> str:
        """Persist a council session. Returns the session ID."""
        try:
            d = session.to_dict()
            await self._repository.save_session(d)
            return d.get("session_id", "")
        except Exception as exc:
            logger.warning("failed to save council session: %s", exc)
            return ""

    async def get_session(self, session_id: str) -> CouncilSession | None:
        """Load a council session by ID."""
        try:
            data = await self._repository.get_session(session_id)
            if data is None:
                return None
            return CouncilSession.from_dict(data)  # type: ignore[return-value]
        except Exception as exc:
            logger.warning("failed to load council session: %s", exc)
            return None

    async def list_sessions(
        self,
        tenant_id: str | uuid.UUID,
        brand_id: str | uuid.UUID | None = None,
        limit: int = 20,
    ) -> list[CouncilSession]:
        """List council sessions."""
        try:
            sessions = await self._repository.list_sessions(
                str(tenant_id),
                str(brand_id) if brand_id else None,
                limit,
            )
            return [CouncilSession.from_dict(s) for s in sessions]  # type: ignore[arg-type]
        except Exception as exc:
            logger.warning("failed to list council sessions: %s", exc)
            return []

    async def get_session_by_campaign(
        self,
        tenant_id: str | uuid.UUID,
        campaign_id: str | uuid.UUID,
    ) -> CouncilSession | None:
        """Get the most recent council session for a campaign."""
        try:
            data = await self._repository.get_session_by_campaign(
                str(tenant_id), str(campaign_id)
            )
            if data is None:
                return None
            return CouncilSession.from_dict(data)  # type: ignore[return-value]
        except Exception as exc:
            logger.warning("failed to load council session by campaign: %s", exc)
            return None

    async def save_learning(self, learning: CouncilLearning) -> str:
        """Persist a council learning. Returns the learning ID."""
        try:
            d = learning.to_dict()
            await self._repository.save_learning(d)
            return d.get("learning_id", "")
        except Exception as exc:
            logger.warning("failed to save council learning: %s", exc)
            return ""

    async def list_learnings(
        self,
        tenant_id: str | uuid.UUID,
        brand_id: str | uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[CouncilLearning]:
        """List council learnings."""
        try:
            learnings = await self._repository.list_learnings(
                str(tenant_id),
                str(brand_id) if brand_id else None,
                limit,
            )
            return [CouncilLearning.from_dict(l) for l in learnings]  # type: ignore[arg-type]
        except Exception as exc:
            logger.warning("failed to list council learnings: %s", exc)
            return []

    async def update_learning_outcome(
        self, learning_id: str, outcome: str
    ) -> None:
        """Update the outcome of a learning."""
        try:
            await self._repository.update_learning_outcome(learning_id, outcome)
        except Exception as exc:
            logger.warning("failed to update learning outcome: %s", exc)

    def to_prompt_context(self, learnings: list[CouncilLearning]) -> str:
        """Serialize learnings into a prompt context string for directors."""
        if not learnings:
            return ""
        parts: list[str] = []
        for l in learnings[-5:]:  # Last 5 learnings
            parts.append(f"- Decision: {l.decision}, Outcome: {l.outcome}")
            if l.lessons:
                parts.append(f"  Lessons: {'; '.join(l.lessons[:2])}")
            if l.successful_recommendations:
                parts.append(f"  What worked: {'; '.join(l.successful_recommendations[:2])}")
            if l.failed_recommendations:
                parts.append(f"  What failed: {'; '.join(l.failed_recommendations[:2])}")
        return "\n".join(parts)
