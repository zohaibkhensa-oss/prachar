"""Runtime — the single public AI entry point.

Constitution Rule 1: The Runtime is the only public AI entry point.
Never call CampaignBrain, Agency Council, Creative Studio, or Review directly from the frontend.

Lifecycle:
    Request → Context → Intent → Planner → Decision Contract → Execute → Events → Memory → Response
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from .context import AIContext, assemble_context
from .context_builder import get_context_builder, EnrichedContext
from .context_ranking import (
    ContextEvaluation, ContextEvaluator, ContextItem, RankingFeedbackStore,
)
from .decision import DecisionContract, DecisionStatus
from .events import EventBus, EventPhase, OrbState, get_session_manager, make_event
from .executor import ExecutionEngine, ExecutionResult
from .composer import ResponseComposer
from .graph import ExecutionGraph
from .metrics import RuntimeMetrics
from .planner import IntentEngine, Planner, RuntimeMode
from .registry import get_registry
from .timeline import TimelineService

log = logging.getLogger("prachar.runtime")


# ─── Request/Response Models ────────────────────────────────────────────────


class InvokeRequest(BaseModel):
    """The single entry point for all AI requests."""

    message: str = Field(..., description="User's message or voice transcript")
    brand_id: uuid.UUID = Field(..., description="Active brand ID")
    modality: str = Field(default="text", description='"text" or "voice"')
    context: dict[str, Any] = Field(
        default_factory=dict,
        description='Additional context: {"current_page": "/app", "active_campaign_id": "uuid"}',
    )


class InvokeResponse(BaseModel):
    """Response from POST /runtime/invoke."""

    session_id: str
    decision_id: str
    stream_url: str
    decision: dict[str, Any] = Field(default_factory=dict)


class ApproveRequest(BaseModel):
    """Human approval of a decision or execution pause."""

    decision_id: str
    choice: str = Field(..., description='"approve" or "deny"')
    modifications: dict[str, Any] = Field(default_factory=dict)


class CancelRequest(BaseModel):
    """Cancel a running session."""

    session_id: str


# ─── Global Feedback Store (singleton) ──────────────────────────────────────

_feedback_store: RankingFeedbackStore | None = None


def get_feedback_store() -> RankingFeedbackStore:
    """Get the global ranking feedback store (singleton)."""
    global _feedback_store
    if _feedback_store is None:
        _feedback_store = RankingFeedbackStore()
    return _feedback_store


# ─── Session State ──────────────────────────────────────────────────────────


@dataclass
class SessionState:
    """Tracks the state of a Runtime session (in-memory).

    V1: Each session owns its own:
    - EventBus (via session_manager)
    - AIContext
    - DecisionContract
    - ExecutionGraph
    - CancelEvent
    - Metrics (V6)
    No cross-session leakage.
    """

    session_id: str
    decision: DecisionContract
    ctx: AIContext
    graph: ExecutionGraph
    tenant_id: Any = None  # V1: stored for background DB session creation
    user_id: Any = None
    brand_id: Any = None
    execution_result: ExecutionResult | None = None
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    response: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    completed: bool = False
    metrics: RuntimeMetrics = field(default_factory=RuntimeMetrics)  # V6
    # Context ranking: store ranked items for post-hoc evaluation after LLM responds
    ranked_items: list[ContextItem] = field(default_factory=list)
    context_evaluation: ContextEvaluation | None = None


# ─── Runtime ────────────────────────────────────────────────────────────────


class Runtime:
    """The AI Runtime — orchestrates the entire lifecycle.

    This is the ONLY class the frontend interacts with (via the router).
    It coordinates: Context → Intent → Planner → Decision → Execute → Events → Memory → Response
    """

    def __init__(
        self,
        gateway: Any,  # AIGateway
        timeline: TimelineService | None = None,
        feedback_store: RankingFeedbackStore | None = None,
    ) -> None:
        self._gateway = gateway
        self._intent_engine = IntentEngine(gateway)
        self._planner = Planner(gateway)
        self._executor = ExecutionEngine()
        self._composer = ResponseComposer(gateway)
        self._timeline = timeline or TimelineService()
        self._session_manager = get_session_manager()
        self._sessions: dict[str, SessionState] = {}
        # Global feedback store for adaptive ranking (shared across sessions)
        self._feedback_store = feedback_store or get_feedback_store()

    async def invoke(
        self,
        session: Any,  # AsyncSession (DB)
        user: Any,     # User
        request: InvokeRequest,
    ) -> InvokeResponse:
        """Start a new AI session.

        1. Assemble AI Context (parallel queries)
        2. Classify intent
        3. Plan execution graph
        4. Create Decision Contract
        5. Store Decision in Timeline
        6. Begin execution (async — events stream via SSE)
        7. Return session_id + stream_url
        """
        # 1. Create session + event bus
        session_id, bus = await self._session_manager.create_session()

        # V6: Initialize metrics
        metrics = RuntimeMetrics(session_id=session_id)
        metrics.mark_request_started()

        # Capture user fields early — context builder queries may expire them
        user_tenant_id = user.tenant_id
        user_id = user.id

        # 2. Assemble context (adaptive — Context Builder decides what to load)
        current_campaign_id = None
        if "active_campaign_id" in request.context:
            try:
                current_campaign_id = uuid.UUID(request.context["active_campaign_id"])
            except (ValueError, TypeError):
                pass

        # Use the Context Builder for adaptive, enriched context with ranking
        builder = get_context_builder()
        enriched_ctx = await builder.build(
            session=session,
            user=user,
            brand_id=request.brand_id,
            message=request.message,
            current_campaign_id=current_campaign_id,
        )
        # If any context provider's query failed, the session transaction may be
        # poisoned. Rollback to a clean state before subsequent operations.
        # After rollback, re-set the RLS context (SET LOCAL is transaction-scoped).
        try:
            await session.rollback()
            if user_tenant_id is not None:
                from sqlalchemy import text as _text
                await session.execute(
                    _text("SELECT set_config('app.tenant_id', :tid, true)"),
                    {"tid": str(user_tenant_id)},
                )
        except Exception:
            pass
        ctx = enriched_ctx.base  # Base AIContext for tools
        # Inject enriched data into the base context so all tools can access it
        ctx.enriched = enriched_ctx.enriched
        ctx.capabilities = enriched_ctx.capabilities
        ctx.knowledge_chunks = enriched_ctx.knowledge_chunks
        ctx.prompt_context = enriched_ctx.prompt_context  # Ranked, token-budgeted
        metrics.mark_context_assembled()

        # Emit context build trace (observability)
        trace = enriched_ctx.trace
        await bus.publish(make_event(
            session_id=session_id,
            type="context.build.completed",
            phase=EventPhase.COMPLETED.value,
            orb_state=OrbState.UNDERSTANDING.value,
            data=trace.to_dict(),
        ))

        # Store ranked items for post-hoc evaluation after LLM responds
        # (will be evaluated in _execute after the response is composed)

        # 3. Emit session.started
        await bus.publish(make_event(
            session_id=session_id,
            type="runtime.session.started",
            phase=EventPhase.STARTED.value,
            orb_state=OrbState.UNDERSTANDING.value,
            data={"message": request.message, "modality": request.modality},
        ))

        # 4. Classify intent
        await bus.publish(make_event(
            session_id=session_id,
            type="planner.intent.classifying",
            phase=EventPhase.STARTED.value,
            orb_state=OrbState.UNDERSTANDING.value,
        ))
        intent = await self._intent_engine.classify(ctx, request.message)
        metrics.mark_intent_classified()

        # ─── Step 1: Confidence-based behaviour ─────────────────────────────
        # > 0.85: execute
        # 0.60–0.85: ask a clarifying question
        # < 0.60: stay conversational
        if intent.should_clarify and intent.clarifying_question:
            # Mid confidence — ask a clarifying question instead of executing
            await bus.publish(make_event(
                session_id=session_id,
                type="runtime.session.completed",
                phase=EventPhase.COMPLETED.value,
                orb_state=OrbState.COMPLETED.value,
                data={
                    "response": {
                        "reply": intent.clarifying_question,
                        "summary": "Clarifying question — confidence was below threshold",
                        "suggested_actions": intent.alternatives[:3] if intent.alternatives else [],
                    },
                    "intent": intent.to_dict(),
                    "clarifying": True,
                },
            ))
            await bus.close()
            state = SessionState(
                session_id=session_id,
                decision=DecisionContract.create(
                    session_id=session_id,
                    goal="Clarifying question",
                    reasoning=f"Confidence {intent.confidence:.2f} below execute threshold",
                    intent=intent.intent,
                    mode=RuntimeMode.CONVERSATION.value,
                    tools=[],
                    graph={},
                    risk_level="low",
                    requires_approval=False,
                    approval_reason=None,
                    estimated_duration="—",
                    estimated_cost_usd=0.0,
                    expected_outputs=[],
                ),
                ctx=ctx,
                graph=ExecutionGraph(),
                tenant_id=user_tenant_id,
                user_id=user_id,
                brand_id=request.brand_id,
                metrics=metrics,
            )
            state.completed = True
            self._sessions[session_id] = state
            return InvokeResponse(
                session_id=session_id,
                decision_id=state.decision.id,
                stream_url=f"/runtime/stream?session_id={session_id}",
                decision=state.decision.to_dict(),
            )

        if intent.should_stay_conversational:
            # Low confidence — switch to conversation mode
            intent.mode = RuntimeMode.CONVERSATION
            intent.intent = "conversation"
        await bus.publish(make_event(
            session_id=session_id,
            type="planner.intent.classified",
            phase=EventPhase.COMPLETED.value,
            orb_state=OrbState.PLANNING.value,
            data=intent.to_dict(),
        ))

        # 5. Plan
        await bus.publish(make_event(
            session_id=session_id,
            type="planner.plan.creating",
            phase=EventPhase.STARTED.value,
            orb_state=OrbState.PLANNING.value,
        ))
        plan = await self._planner.plan(ctx, request.message, intent)
        metrics.mark_plan_created()
        await bus.publish(make_event(
            session_id=session_id,
            type="planner.plan.created",
            phase=EventPhase.COMPLETED.value,
            orb_state=OrbState.PLANNING.value,
            data={
                "goal": plan.goal,
                "tools": plan.tools,
                "graph": plan.graph.to_dict(),
                "estimated_duration": plan.estimated_duration,
                "estimated_cost_usd": plan.estimated_cost_usd,
                "user_explanation": plan.user_explanation,
            },
        ))

        # 6. Create Decision Contract
        decision = DecisionContract.create(
            session_id=session_id,
            goal=plan.goal,
            reasoning=plan.reasoning,
            user_explanation=plan.user_explanation,
            intent=plan.intent,
            mode=plan.mode.value,
            tools=plan.tools,
            graph=plan.graph.to_dict(),
            risk_level=plan.risk_level,
            requires_approval=plan.requires_approval,
            approval_reason=plan.approval_reason,
            estimated_duration=plan.estimated_duration,
            estimated_cost_usd=plan.estimated_cost_usd,
            expected_outputs=plan.expected_outputs,
            context=ctx,
            health_warnings=plan.health_warnings,
            cost_breakdown=plan.cost_breakdown,
        )

        await bus.publish(make_event(
            session_id=session_id,
            type="planner.decision.created",
            phase=EventPhase.COMPLETED.value,
            decision_id=decision.id,
            orb_state=OrbState.PLANNING.value,
            data=decision.to_dict(),
        ))

        # 7. Store Decision in Timeline
        try:
            await self._timeline.append(
                session=session,
                tenant_id=user_tenant_id,
                brand_id=request.brand_id,
                entry_type="decision_contract",
                actor="ai",
                title=f"Plan: {decision.goal}",
                summary=decision.user_explanation[:200] if decision.user_explanation else (decision.goal[:200] if decision.goal else ""),
                detail=decision.to_dict(),
                session_id=uuid.UUID(session_id) if session_id else None,
                decision_id=uuid.UUID(decision.id) if decision.id else None,
                replayable=True,
                replay_inputs={
                    "intent": decision.intent,
                    "mode": decision.mode,
                    "context_snapshot": decision.context_snapshot,
                },
            )
        except Exception as exc:
            log.warning("failed to append decision to timeline: %s", exc)
            # Rollback the poisoned transaction so the session is usable again.
            # Re-set RLS context after rollback (SET LOCAL is transaction-scoped).
            try:
                await session.rollback()
                if user_tenant_id is not None:
                    from sqlalchemy import text as _text
                    await session.execute(
                        _text("SELECT set_config('app.tenant_id', :tid, true)"),
                        {"tid": str(user_tenant_id)},
                    )
            except Exception:
                pass

        # 8. Store session state
        # V1: Store tenant_id, user_id, brand_id so the background task can
        # create its own DB session (the request's session will be closed).
        state = SessionState(
            session_id=session_id,
            decision=decision,
            ctx=ctx,
            graph=plan.graph,
            tenant_id=user_tenant_id,
            user_id=user_id,
            brand_id=request.brand_id,
            metrics=metrics,
            ranked_items=enriched_ctx.ranked_items,
        )
        metrics.decision_id = decision.id
        metrics.mark_decision_created()
        self._sessions[session_id] = state

        # 9. If planning mode, don't execute — just return the plan for review
        if plan.mode == RuntimeMode.PLANNING:
            decision.status = DecisionStatus.PENDING.value
            await bus.publish(make_event(
                session_id=session_id,
                type="runtime.session.completed",
                phase=EventPhase.COMPLETED.value,
                decision_id=decision.id,
                orb_state=OrbState.COMPLETED.value,
                data={
                    "response": {
                        "reply": plan.user_explanation or f"I've planned this out: {plan.goal}. Review the plan and let me know if you want me to execute it.",
                        "summary": plan.user_explanation or plan.goal,
                        "suggested_actions": ["Execute the plan", "Modify the plan"],
                    },
                    "decision": decision.to_dict(),
                },
            ))
            await bus.close()
            state.completed = True
            return InvokeResponse(
                session_id=session_id,
                decision_id=decision.id,
                stream_url=f"/runtime/stream?session_id={session_id}",
                decision=decision.to_dict(),
            )

        # 10. Start execution in background
        # V1: The background task creates its OWN DB session — it does NOT
        # share the request's AsyncSession (which will be closed when the
        # request handler returns). This prevents ResourceClosedError and
        # ensures session isolation.
        decision.status = DecisionStatus.EXECUTING.value
        asyncio.create_task(
            self._run_execution_with_own_session(session_id, state, request.message)
        )

        return InvokeResponse(
            session_id=session_id,
            decision_id=decision.id,
            stream_url=f"/runtime/stream?session_id={session_id}",
            decision=decision.to_dict(),
        )

    async def _run_execution_with_own_session(
        self,
        session_id: str,
        state: SessionState,
        message: str,
    ) -> None:
        """V1: Run execution with a dedicated DB session.

        The request handler's AsyncSession is closed after invoke() returns.
        This background task creates its own session via session_scope(),
        sets RLS context, and closes it when done. No session leakage.
        """
        from ..db import session_scope

        try:
            async with session_scope(tenant_id=str(state.tenant_id)) as db_session:
                # V1: Replace ctx.session with our own session
                state.ctx.session = db_session
                await self._run_execution(session_id, state, db_session, message)
        except Exception as exc:
            log.exception("background execution failed for session %s", session_id)
            bus = await self._session_manager.get_bus(session_id)
            if bus:
                await bus.publish(make_event(
                    session_id=session_id,
                    type="runtime.session.error",
                    phase=EventPhase.ERROR.value,
                    decision_id=state.decision.id,
                    orb_state=OrbState.ERROR.value,
                    data={"error": str(exc)},
                ))
                await bus.close()
            state.completed = True

    async def _run_execution(
        self,
        session_id: str,
        state: SessionState,
        db_session: Any,
        message: str,
    ) -> None:
        """Run the execution graph in the background, emitting events."""
        bus = await self._session_manager.get_bus(session_id)
        if bus is None:
            return

        # Phase E2.1: wire the EventBus to persist every event to the DB.
        # Uses the background task's own DB session (V1 session isolation).
        if state.tenant_id is not None:
            from .event_replay import persist_event

            async def _persist(ev: AIEvent) -> None:
                await persist_event(db_session, state.tenant_id, ev)

            bus.set_persist_callback(_persist)

        metrics = state.metrics
        metrics.mark_execution_started()

        try:
            # Execute the graph
            result = await self._executor.execute(
                graph=state.graph,
                ctx=state.ctx,
                bus=bus,
                decision_id=state.decision.id,
                session_id=session_id,
                cancel_event=state.cancel_event,
                metrics=metrics,
            )
            state.execution_result = result
            metrics.mark_execution_completed()

            # If waiting for approval, pause here
            if result.waiting_for_approval:
                state.decision.status = DecisionStatus.PENDING.value
                return  # Runtime.resume_after_approval will be called externally

            if result.cancelled:
                state.decision.status = DecisionStatus.CANCELLED.value
                await bus.publish(make_event(
                    session_id=session_id,
                    type="runtime.session.cancelled",
                    phase=EventPhase.CANCELLED.value,
                    decision_id=state.decision.id,
                    orb_state=OrbState.CANCELLED.value,
                ))
                await bus.close()
                state.completed = True
                return

            if not result.success:
                state.decision.status = DecisionStatus.FAILED.value
                state.decision.error = result.error
                metrics.outcome = "failed"
                metrics.mark_session_completed()
                state.decision.metrics = metrics.to_dict()
                await bus.publish(make_event(
                    session_id=session_id,
                    type="runtime.session.error",
                    phase=EventPhase.ERROR.value,
                    decision_id=state.decision.id,
                    orb_state=OrbState.ERROR.value,
                    data={"error": result.error},
                ))
                await bus.close()
                state.completed = True
                return

            # V4: Check for partial failure (completed with warnings)
            if result.has_warnings:
                state.decision.status = DecisionStatus.COMPLETED_WITH_WARNINGS.value
                state.decision.warnings = result.warnings
                metrics.outcome = "completed_with_warnings"
            else:
                state.decision.status = DecisionStatus.COMPLETED.value
                metrics.outcome = "completed"

            # Compose response
            response = await self._composer.compose(state.ctx, message, result)
            state.response = response
            metrics.mark_response_composed()

            # ─── Context Build Evaluation (post-hoc) ───────────────────────
            # Evaluate how well the context build supported the LLM answer.
            # This closes the observability loop: build → rank → inject →
            # LLM responds → evaluate → emit trace → learn.
            if state.ranked_items and response.get("reply"):
                try:
                    evaluation = ContextEvaluator.evaluate(
                        ranked_items=state.ranked_items,
                        answer_text=response["reply"],
                        knowledge_chunks=state.ctx.knowledge_chunks,
                    )
                    state.context_evaluation = evaluation

                    # Record feedback for adaptive ranking (learning loop)
                    self._feedback_store.record_from_evaluation(evaluation)

                    # Emit evaluation event (observability)
                    await bus.publish(make_event(
                        session_id=session_id,
                        type="context.build.evaluated",
                        phase=EventPhase.COMPLETED.value,
                        decision_id=state.decision.id,
                        orb_state=OrbState.COMPLETED.value,
                        data=evaluation.to_dict(),
                    ))

                    log.info(
                        "Context evaluation: %d/%d items referenced, "
                        "%.0f%% answer support, %.0f%% unused, avg score %.2f",
                        evaluation.items_referenced,
                        evaluation.items_kept,
                        evaluation.answer_support_pct,
                        evaluation.unused_context_pct,
                        evaluation.avg_retrieval_score,
                    )
                except Exception as exc:
                    log.warning("Context evaluation failed: %s", exc)

            # Phase E1.2: Include health warnings in the response so PRACHAR AI
            # can say "Publishing is temporarily unavailable. I've prepared everything else."
            if state.decision.health_warnings:
                response["health_warnings"] = state.decision.health_warnings
                state.response = response

            # Update decision with metrics
            state.decision.actual_duration_ms = result.total_duration_ms
            state.decision.actual_cost_usd = result.total_cost_usd
            metrics.mark_session_completed()
            state.decision.metrics = metrics.to_dict()

            # Append to timeline
            try:
                await self._timeline.append(
                    session=db_session,
                    tenant_id=state.tenant_id,
                    brand_id=state.brand_id,
                    entry_type="session_completed",
                    actor="ai",
                    title=state.decision.goal,
                    summary=response.get("summary", ""),
                    detail={
                        "response": response,
                        "decision_id": state.decision.id,
                        "tools_executed": list(result.all_outputs().keys()),
                        "duration_ms": result.total_duration_ms,
                        "cost_usd": result.total_cost_usd,
                        "warnings": result.warnings if result.has_warnings else [],
                        "health_warnings": state.decision.health_warnings,
                        "metrics": metrics.to_dict(),
                    },
                    session_id=uuid.UUID(session_id),
                    decision_id=uuid.UUID(state.decision.id),
                )
            except Exception as exc:
                log.warning("failed to append completion to timeline: %s", exc)
                try:
                    await session.rollback()
                    if state.tenant_id is not None:
                        from sqlalchemy import text as _text
                        await session.execute(
                            _text("SELECT set_config('app.tenant_id', :tid, true)"),
                            {"tid": str(state.tenant_id)},
                        )
                except Exception:
                    pass

            # Emit session.completed
            await bus.publish(make_event(
                session_id=session_id,
                type="runtime.session.completed",
                phase=EventPhase.COMPLETED.value,
                decision_id=state.decision.id,
                orb_state=OrbState.COMPLETED.value,
                data={
                    "response": response,
                    "summary": response.get("summary", ""),
                    "duration_ms": result.total_duration_ms,
                    "cost_usd": result.total_cost_usd,
                    "warnings": result.warnings if result.has_warnings else [],
                    "health_warnings": state.decision.health_warnings,
                },
            ))
            await bus.close()
            state.completed = True

        except Exception as exc:
            log.exception("execution failed for session %s", session_id)
            state.decision.status = DecisionStatus.FAILED.value
            state.decision.error = str(exc)
            metrics.outcome = "failed"
            metrics.mark_session_completed()
            state.decision.metrics = metrics.to_dict()
            await bus.publish(make_event(
                session_id=session_id,
                type="runtime.session.error",
                phase=EventPhase.ERROR.value,
                decision_id=state.decision.id,
                orb_state=OrbState.ERROR.value,
                data={"error": str(exc)},
            ))
            await bus.close()
            state.completed = True

    async def approve(
        self,
        session: Any,
        user: Any,
        request: ApproveRequest,
    ) -> dict[str, Any]:
        """Approve or deny a paused execution."""
        state = self._sessions.get(request.decision_id)
        # Also check by session_id → decision mapping
        if state is None:
            for s in self._sessions.values():
                if s.decision.id == request.decision_id:
                    state = s
                    break

        if state is None:
            return {"status": "error", "message": "session not found"}

        if not state.execution_result or not state.execution_result.waiting_for_approval:
            return {"status": "error", "message": "session not waiting for approval"}

        approved = request.choice == "approve"
        state.decision.status = DecisionStatus.APPROVED.value if approved else DecisionStatus.CANCELLED.value
        state.decision.approved_by = str(user.id)

        # V6: Record approval timing
        if approved:
            state.metrics.mark_approval_granted()

        if not approved:
            # Deny — close the session
            bus = await self._session_manager.get_bus(state.session_id)
            if bus:
                await bus.publish(make_event(
                    session_id=state.session_id,
                    type="approval.denied",
                    phase=EventPhase.COMPLETED.value,
                    decision_id=state.decision.id,
                    orb_state=OrbState.COMPLETED.value,
                ))
                await bus.close()
            state.completed = True
            return {"status": "denied"}

        # Approve — resume execution
        # V1: Resume with its own DB session (same as initial execution)
        bus = await self._session_manager.get_bus(state.session_id)
        if bus is None:
            return {"status": "error", "message": "event bus not found"}

        asyncio.create_task(
            self._resume_execution_with_own_session(state)
        )
        return {"status": "approved", "session_id": state.session_id}

    async def _resume_execution_with_own_session(
        self,
        state: SessionState,
    ) -> None:
        """V1: Resume execution with a dedicated DB session."""
        from ..db import session_scope

        try:
            async with session_scope(tenant_id=str(state.tenant_id)) as db_session:
                state.ctx.session = db_session
                await self._resume_execution(state, db_session)
        except Exception as exc:
            log.exception("resume execution failed for session %s", state.session_id)
            bus = await self._session_manager.get_bus(state.session_id)
            if bus:
                await bus.publish(make_event(
                    session_id=state.session_id,
                    type="runtime.session.error",
                    phase=EventPhase.ERROR.value,
                    decision_id=state.decision.id,
                    orb_state=OrbState.ERROR.value,
                    data={"error": str(exc)},
                ))
                await bus.close()
            state.completed = True

    async def _resume_execution(
        self,
        state: SessionState,
        db_session: Any,
    ) -> None:
        """Resume execution after approval."""
        bus = await self._session_manager.get_bus(state.session_id)
        if bus is None:
            return

        # Phase E2.1: ensure resumed events are also persisted.
        if state.tenant_id is not None and bus._persist_callback is None:
            from .event_replay import persist_event

            async def _persist(ev: AIEvent) -> None:
                await persist_event(db_session, state.tenant_id, ev)

            bus.set_persist_callback(_persist)

        result = await self._executor.resume_after_approval(
            graph=state.graph,
            ctx=state.ctx,
            bus=bus,
            decision_id=state.decision.id,
            session_id=state.session_id,
            approval_node_id=state.execution_result.approval_node_id,
            approved=True,
            prev_result=state.execution_result,
            cancel_event=state.cancel_event,
            metrics=state.metrics,
        )
        state.execution_result = result
        state.metrics.mark_execution_completed()

        if result.waiting_for_approval:
            return  # Another approval needed

        if result.success and not result.cancelled:
            # V4: Check for partial failure
            if result.has_warnings:
                state.decision.status = DecisionStatus.COMPLETED_WITH_WARNINGS.value
                state.decision.warnings = result.warnings
                state.metrics.outcome = "completed_with_warnings"
            else:
                state.decision.status = DecisionStatus.COMPLETED.value
                state.metrics.outcome = "completed"

            # Compose response
            message = state.ctx.conversation[-1].content if state.ctx.conversation else ""
            response = await self._composer.compose(state.ctx, message, result)
            state.response = response
            state.metrics.mark_response_composed()
            state.metrics.mark_session_completed()
            state.decision.metrics = state.metrics.to_dict()

            await bus.publish(make_event(
                session_id=state.session_id,
                type="runtime.session.completed",
                phase=EventPhase.COMPLETED.value,
                decision_id=state.decision.id,
                orb_state=OrbState.COMPLETED.value,
                data={
                    "response": response,
                    "warnings": result.warnings if result.has_warnings else [],
                },
            ))

        await bus.close()
        state.completed = True

    async def cancel(self, request: CancelRequest) -> dict[str, Any]:
        """Cancel a running session."""
        state = self._sessions.get(request.session_id)
        if state is None:
            return {"status": "error", "message": "session not found"}

        state.cancel_event.set()
        state.decision.status = DecisionStatus.CANCELLED.value
        return {"status": "cancelled"}

    def get_session_state(self, session_id: str) -> SessionState | None:
        """Get the in-memory state of a session (for debugging)."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions for the Certification Dashboard (A.1.5).

        Returns a summary of each session — not the full state.
        """
        sessions = []
        for sid, state in self._sessions.items():
            sessions.append({
                "session_id": sid,
                "decision_id": state.decision.id,
                "goal": state.decision.goal,
                "status": state.decision.status,
                "intent": state.decision.intent,
                "mode": state.decision.mode,
                "started_at": state.started_at,
                "completed": state.completed,
                "tenant_id": str(state.tenant_id) if state.tenant_id else None,
                "brand_id": str(state.brand_id) if state.brand_id else None,
                "metrics": state.metrics.to_dict() if state.metrics else None,
                "warnings": state.decision.warnings,
                "health_warnings": state.decision.health_warnings,
                "error": state.decision.error,
                "node_count": len(state.graph.nodes),
                "completed_nodes": len(state.execution_result.node_results) if state.execution_result else 0,
            })
        # Sort by started_at descending (newest first)
        sessions.sort(key=lambda s: s["started_at"], reverse=True)
        return sessions

    def get_session_detail(self, session_id: str) -> dict[str, Any] | None:
        """Get full detail of a session for the Certification Dashboard."""
        state = self._sessions.get(session_id)
        if state is None:
            return None
        return {
            "session_id": session_id,
            "decision": state.decision.to_dict(),
            "cost_breakdown": state.decision.cost_breakdown,
            "graph": state.graph.to_dict(),
            "metrics": state.metrics.to_dict() if state.metrics else None,
            "execution_result": {
                "success": state.execution_result.success,
                "cancelled": state.execution_result.cancelled,
                "has_warnings": state.execution_result.has_warnings,
                "warnings": state.execution_result.warnings,
                "total_duration_ms": state.execution_result.total_duration_ms,
                "total_cost_usd": state.execution_result.total_cost_usd,
                "node_results": {
                    nid: {
                        "node_id": nr.node_id,
                        "tool": nr.tool,
                        "success": nr.success,
                        "error": nr.error,
                        "duration_ms": nr.duration_ms,
                        "cost_usd": nr.cost_usd,
                        "retries": nr.retries,
                        "cancelled": nr.cancelled,
                        "timed_out": nr.timed_out,
                    }
                    for nid, nr in state.execution_result.node_results.items()
                },
            } if state.execution_result else None,
            "response": state.response,
            "started_at": state.started_at,
            "completed": state.completed,
            "context_evaluation": state.context_evaluation.to_dict() if state.context_evaluation else None,
        }

    def record_feedback(
        self,
        session_id: str,
        user_accepted: bool | None = None,
        positive_outcome: bool | None = None,
    ) -> bool:
        """Record user feedback for a completed session.

        This updates the feedback records for all items in the session's
        context evaluation with the user's acceptance and outcome signals.
        This is the final step in the learning loop:

            Context Item → Selected? → Referenced? → User accepted? →
            Positive outcome? → Adjust future ranking weights

        Args:
            session_id: The session to record feedback for
            user_accepted: Did the user accept the answer (vs regenerate)?
            positive_outcome: Did the resulting action have a positive outcome?

        Returns:
            True if feedback was recorded, False if session not found
        """
        state = self._sessions.get(session_id)
        if state is None or state.context_evaluation is None:
            return False

        # Re-record with user feedback signals
        self._feedback_store.record_from_evaluation(
            state.context_evaluation,
            user_accepted=user_accepted,
            positive_outcome=positive_outcome,
        )
        return True

    def get_feedback_stats(self) -> dict[str, Any]:
        """Get ranking feedback statistics for observability."""
        return self._feedback_store.stats()
