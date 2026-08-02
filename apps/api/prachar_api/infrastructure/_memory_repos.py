"""Infrastructure layer: Postgres implementation of MemoryRepository.

This module lives in the API app (infrastructure layer) and implements
the MemoryRepository protocol defined in the shared package. The shared
package depends on the protocol, not on this implementation — this is
dependency inversion (Phase 6: Architecture Stabilisation).

Architecture:
    Domain (shared/repository.py) defines MemoryRepository protocol
         ↑
    Infrastructure (this file) implements PostgresMemoryRepository
         ↑
    Application (routers, brain) uses BusinessMemoryStore(repository)
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from prachar_api.models.tables import BusinessMemoryRecord

logger = logging.getLogger(__name__)


class PostgresMemoryRepository:
    """Postgres-backed implementation of MemoryRepository.

    Stores business memory as JSONB on the `business_memories` table,
    keyed by (tenant_id, brand_id).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, tenant_id: uuid.UUID, brand_id: uuid.UUID) -> dict[str, Any]:
        """Read the business memory for a brand. Returns empty dict if not found."""
        res = await self._session.execute(
            select(BusinessMemoryRecord).where(
                BusinessMemoryRecord.tenant_id == tenant_id,
                BusinessMemoryRecord.brand_id == brand_id,
            )
        )
        record = res.scalar_one_or_none()
        if record is None:
            return {}
        return record.memory or {}

    async def save(
        self,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        memory: dict[str, Any],
    ) -> None:
        """Save (upsert) the business memory for a brand."""
        res = await self._session.execute(
            select(BusinessMemoryRecord).where(
                BusinessMemoryRecord.tenant_id == tenant_id,
                BusinessMemoryRecord.brand_id == brand_id,
            )
        )
        record = res.scalar_one_or_none()
        if record is None:
            record = BusinessMemoryRecord(
                tenant_id=tenant_id,
                brand_id=brand_id,
                memory=memory,
            )
            self._session.add(record)
        else:
            record.memory = memory
        await self._session.flush()


# ─── Agency Council: PostgresCouncilRepository ──────────────────────────────


class PostgresCouncilRepository:
    """Postgres-backed implementation of CouncilMemoryRepository.

    Stores council sessions, director opinions, consensus decisions,
    campaign scores, and learnings across 5 tables.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_session(self, session: dict[str, Any]) -> None:
        from .models import (
            CampaignScoreRecord,
            ConsensusDecisionRecord,
            CouncilSessionRecord,
            DirectorOpinionRecord,
        )
        import uuid as _uuid

        sid = _uuid.UUID(session["session_id"]) if "session_id" in session and session["session_id"] else _uuid.uuid4()
        tenant_id = _uuid.UUID(session["tenant_id"]) if session.get("tenant_id") else None
        brand_id = _uuid.UUID(session["brand_id"]) if session.get("brand_id") else None
        campaign_plan_id = _uuid.UUID(session["campaign_id"]) if session.get("campaign_id") else None

        record = CouncilSessionRecord(
            id=sid,
            tenant_id=tenant_id,
            brand_id=brand_id,
            campaign_plan_id=campaign_plan_id,
            campaign_brief=session.get("campaign_brief", {}),
            opinions_by_round=session.get("opinions_by_round", {}),
            consensus_decision=session.get("consensus_decision", {}),
            status=session.get("status", "pending"),
            rounds_completed=session.get("rounds_completed", 0),
            total_tokens=session.get("total_tokens", 0),
            total_cost_usd=session.get("total_cost_usd", 0.0),
            total_latency_ms=session.get("total_latency_ms", 0.0),
        )
        self._session.add(record)

        # Save individual director opinions
        opinions_by_round = session.get("opinions_by_round", {})
        for round_str, opinions in opinions_by_round.items():
            round_num = int(round_str)
            for op in opinions:
                op_record = DirectorOpinionRecord(
                    tenant_id=tenant_id,
                    council_session_id=sid,
                    director=op.get("director", ""),
                    role=op.get("role", ""),
                    opinion=op,
                    round_number=round_num,
                    confidence=op.get("confidence", 0.5),
                    approval=op.get("approval", False),
                    priority=op.get("priority", "medium"),
                    tokens_used=op.get("tokens_used", 0),
                    cost_usd=op.get("cost_usd", 0.0),
                    latency_ms=op.get("latency_ms", 0.0),
                    model_used=op.get("model", ""),
                )
                self._session.add(op_record)

        # Save consensus decision
        decision = session.get("consensus_decision", {})
        if decision:
            score = decision.get("campaign_score", {})
            dec_record = ConsensusDecisionRecord(
                tenant_id=tenant_id,
                council_session_id=sid,
                decision=decision,
                campaign_score=score,
                approval_status=decision.get("approval_status", "pending"),
                confidence=decision.get("confidence", 0.5),
                overall_score=score.get("overall_score", 0.0),
                rounds_completed=decision.get("rounds_completed", 1),
                total_tokens=decision.get("total_tokens", 0),
                total_cost_usd=decision.get("total_cost_usd", 0.0),
            )
            self._session.add(dec_record)

            # Save campaign score
            score_record = CampaignScoreRecord(
                tenant_id=tenant_id,
                council_session_id=sid,
                campaign_plan_id=campaign_plan_id,
                strategy_score=score.get("strategy_score", 0.0),
                creative_score=score.get("creative_score", 0.0),
                media_score=score.get("media_score", 0.0),
                brand_score=score.get("brand_score", 0.0),
                performance_score=score.get("performance_score", 0.0),
                risk_score=score.get("risk_score", 0.0),
                compliance_score=score.get("compliance_score", 0.0),
                overall_score=score.get("overall_score", 0.0),
                weights_used=score.get("weights_used", {}),
            )
            self._session.add(score_record)

        await self._session.flush()

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        from .models import CouncilSessionRecord
        import uuid as _uuid

        res = await self._session.execute(
            select(CouncilSessionRecord).where(
                CouncilSessionRecord.id == _uuid.UUID(session_id)
            )
        )
        record = res.scalar_one_or_none()
        if record is None:
            return None
        return self._session_record_to_dict(record)

    async def list_sessions(
        self,
        tenant_id: str,
        brand_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        from .models import CouncilSessionRecord
        import uuid as _uuid

        stmt = select(CouncilSessionRecord).where(
            CouncilSessionRecord.tenant_id == _uuid.UUID(tenant_id)
        )
        if brand_id:
            stmt = stmt.where(CouncilSessionRecord.brand_id == _uuid.UUID(brand_id))
        stmt = stmt.order_by(CouncilSessionRecord.created_at.desc()).limit(limit)
        res = await self._session.execute(stmt)
        return [self._session_record_to_dict(r) for r in res.scalars()]

    async def get_session_by_campaign(
        self, tenant_id: str, campaign_id: str
    ) -> dict[str, Any] | None:
        from .models import CouncilSessionRecord
        import uuid as _uuid

        stmt = (
            select(CouncilSessionRecord)
            .where(
                CouncilSessionRecord.tenant_id == _uuid.UUID(tenant_id),
                CouncilSessionRecord.campaign_plan_id == _uuid.UUID(campaign_id),
            )
            .order_by(CouncilSessionRecord.created_at.desc())
            .limit(1)
        )
        res = await self._session.execute(stmt)
        record = res.scalar_one_or_none()
        if record is None:
            return None
        return self._session_record_to_dict(record)

    async def save_learning(self, learning: dict[str, Any]) -> None:
        from .models import CouncilLearningRecord
        import uuid as _uuid

        tenant_id = _uuid.UUID(learning["tenant_id"]) if learning.get("tenant_id") else None
        brand_id = _uuid.UUID(learning["brand_id"]) if learning.get("brand_id") else None
        session_id = _uuid.UUID(learning["session_id"]) if learning.get("session_id") else None
        campaign_id = _uuid.UUID(learning["campaign_id"]) if learning.get("campaign_id") else None

        record = CouncilLearningRecord(
            tenant_id=tenant_id,
            brand_id=brand_id,
            council_session_id=session_id,
            campaign_plan_id=campaign_id,
            decision=learning.get("decision", ""),
            outcome=learning.get("outcome", "pending"),
            minority_opinions=learning.get("minority_opinions", []),
            rejected_ideas=learning.get("rejected_ideas", []),
            successful_recommendations=learning.get("successful_recommendations", []),
            failed_recommendations=learning.get("failed_recommendations", []),
            lessons=learning.get("lessons", []),
            overall_score=learning.get("overall_score", 0.0),
        )
        self._session.add(record)
        await self._session.flush()

    async def list_learnings(
        self,
        tenant_id: str,
        brand_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        from .models import CouncilLearningRecord
        import uuid as _uuid

        stmt = select(CouncilLearningRecord).where(
            CouncilLearningRecord.tenant_id == _uuid.UUID(tenant_id)
        )
        if brand_id:
            stmt = stmt.where(CouncilLearningRecord.brand_id == _uuid.UUID(brand_id))
        stmt = stmt.order_by(CouncilLearningRecord.created_at.desc()).limit(limit)
        res = await self._session.execute(stmt)
        return [
            {
                "learning_id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "brand_id": str(r.brand_id) if r.brand_id else "",
                "session_id": str(r.council_session_id) if r.council_session_id else "",
                "campaign_id": str(r.campaign_plan_id) if r.campaign_plan_id else "",
                "decision": r.decision,
                "outcome": r.outcome,
                "minority_opinions": r.minority_opinions,
                "rejected_ideas": r.rejected_ideas,
                "successful_recommendations": r.successful_recommendations,
                "failed_recommendations": r.failed_recommendations,
                "lessons": r.lessons,
                "overall_score": r.overall_score,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in res.scalars()
        ]

    async def update_learning_outcome(
        self, learning_id: str, outcome: str
    ) -> None:
        from .models import CouncilLearningRecord
        import uuid as _uuid

        res = await self._session.execute(
            select(CouncilLearningRecord).where(
                CouncilLearningRecord.id == _uuid.UUID(learning_id)
            )
        )
        record = res.scalar_one_or_none()
        if record is not None:
            record.outcome = outcome
            await self._session.flush()

    def _session_record_to_dict(self, record: Any) -> dict[str, Any]:
        return {
            "session_id": str(record.id),
            "tenant_id": str(record.tenant_id),
            "brand_id": str(record.brand_id) if record.brand_id else "",
            "campaign_id": str(record.campaign_plan_id) if record.campaign_plan_id else "",
            "campaign_brief": record.campaign_brief,
            "opinions_by_round": record.opinions_by_round,
            "consensus_decision": record.consensus_decision,
            "status": record.status,
            "rounds_completed": record.rounds_completed,
            "total_tokens": record.total_tokens,
            "total_cost_usd": record.total_cost_usd,
            "total_latency_ms": record.total_latency_ms,
            "created_at": record.created_at.isoformat() if record.created_at else "",
            "completed_at": record.completed_at.isoformat() if record.completed_at else "",
        }
