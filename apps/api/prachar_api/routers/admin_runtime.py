"""Runtime Certification Dashboard — internal admin endpoints.

Phase A.1.5: Not a user feature. An internal page for debugging runtime
sessions. Shows: Decision, Graph, Events, Timeline, Memory, Tool Calls,
Costs, Latency, Tokens for every session.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ..deps import current_user
from .runtime import get_runtime

router = APIRouter(prefix="/admin/runtime", tags=["admin-runtime"])


@router.get("/sessions")
async def list_sessions(
    request: Request,
    user=Depends(current_user),
):
    """List all runtime sessions (summary view).

    For the Certification Dashboard. Shows session_id, decision, status,
    metrics, and node counts.
    """
    runtime = get_runtime()
    return {"sessions": runtime.list_sessions()}


@router.get("/sessions/{session_id}")
async def get_session_detail(
    session_id: str,
    request: Request,
    user=Depends(current_user),
):
    """Get full detail of a single runtime session.

    Shows: Decision Contract, Execution Graph, Metrics, Execution Result
    (per-node), and the composed response.
    """
    runtime = get_runtime()
    detail = runtime.get_session_detail(session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="session not found")
    return detail


@router.get("/sessions/{session_id}/events")
async def get_session_events(
    session_id: str,
    request: Request,
    user=Depends(current_user),
):
    """Get all events emitted by a session (for debugging).

    This is NOT the SSE stream — it's a snapshot of all events collected
    so far. Falls back to persisted events (Phase E2.1) when the in-memory
    bus is no longer available, so post-mortem debugging works even after
    the session has been evicted from memory.
    """
    from .events import get_session_manager
    from ..db import get_sessionmaker
    from ..runtime.event_replay import get_session_events as fetch_persisted

    manager = get_session_manager()
    bus = await manager.get_bus(session_id)

    events: list = []
    if bus is not None and hasattr(bus, "get_all_events"):
        events = bus.get_all_events()

    # Fall back to persisted events when the in-memory bus is gone or empty.
    if not events:
        sm = get_sessionmaker()
        tenant_id = getattr(request.state, "tenant_id", None)
        async with sm() as db_session:
            if tenant_id is not None:
                from sqlalchemy import text

                await db_session.execute(
                    text("SELECT set_config('app.tenant_id', :tid, true)"),
                    {"tid": str(tenant_id)},
                )
            events = await fetch_persisted(db_session, session_id)

    # Serialise events
    serialised = []
    for ev in events:
        serialised.append({
            "session_id": ev.session_id,
            "type": ev.type,
            "phase": ev.phase,
            "timestamp": ev.timestamp,
            "decision_id": ev.decision_id,
            "tool": ev.tool,
            "orb_state": ev.orb_state,
            "data": ev.data,
            "progress": ev.progress,
        })
    return {"session_id": session_id, "events": serialised, "count": len(serialised)}


@router.get("/sessions/{session_id}/replay")
async def replay_session(
    session_id: str,
    request: Request,
    user=Depends(current_user),
):
    """Replay a session from its persisted event stream (Phase E2.1).

    Returns the full event stream plus a ReplayResult containing orb state
    transitions, tool executions, duration, and event count. This enables
    debugging and visual replay without re-running the tools.
    """
    from ..runtime.event_replay import replay_session as do_replay

    tenant_id = getattr(request.state, "tenant_id", None)
    result = await do_replay(session_id, tenant_id=str(tenant_id) if tenant_id else None)
    if result.event_count == 0:
        raise HTTPException(status_code=404, detail="no persisted events for session")
    return result.to_dict()


@router.get("/tools")
async def list_tools(
    request: Request,
    user=Depends(current_user),
):
    """List all registered tools with their manifests (for debugging).

    Shows: name, version, deprecated, timeouts, cost, retry support.
    """
    from .registry import get_registry

    registry = get_registry()
    tools = [m.to_dict() for m in registry.list()]
    return {"tools": tools, "count": len(tools)}


@router.get("/health")
async def get_tool_health(
    request: Request,
    user=Depends(current_user),
):
    """Get health status of all tracked tools (Phase E1.2).

    Shows: tool_name, status (healthy/degraded/offline), error/success counts,
    latency, last check time, and any status message.
    """
    from ..runtime.health import get_health_registry

    registry = get_health_registry()
    health = [h.to_dict() for h in registry.list_all()]
    return {"tools": health, "count": len(health)}


# ─── Automation (Phase H) ────────────────────────────────────────────────────


@router.get("/automation/rules")
async def list_automation_rules(
    request: Request,
    user=Depends(current_user),
):
    """List all automation rules and their current status."""
    from ..runtime.automation import get_automation_engine

    engine = get_automation_engine()
    return {"rules": [r.to_dict() for r in engine.rules], "count": len(engine.rules)}


@router.get("/automation/tasks")
async def list_automation_tasks(
    request: Request,
    user=Depends(current_user),
    brand_id: str | None = None,
):
    """List automation tasks (optionally filtered by brand)."""
    from ..runtime.automation import get_automation_engine
    from uuid import UUID

    engine = get_automation_engine()
    if brand_id:
        try:
            tasks = engine.get_tasks_for_brand(UUID(brand_id))
        except ValueError:
            tasks = []
    else:
        tasks = engine.tasks
    return {"tasks": [t.to_dict() for t in tasks], "count": len(tasks)}


@router.post("/automation/evaluate")
async def evaluate_automation(
    request: Request,
    user=Depends(current_user),
    brand_id: str = "",
):
    """Evaluate automation rules for a brand and create tasks.

    This is the trigger for autonomous operations. It checks all rules
    against the brand's current state and creates AutomationTask objects
    for any rules whose conditions are met.
    """
    from ..runtime.automation import get_automation_engine, build_automation_context
    from ..db import get_sessionmaker
    from uuid import UUID

    engine = get_automation_engine()
    bid = UUID(brand_id) if brand_id else None
    if bid is None:
        raise HTTPException(status_code=400, detail="brand_id required")

    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="tenant context required")

    sm = get_sessionmaker()
    async with sm() as session:
        from sqlalchemy import text
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        context = await build_automation_context(session, tenant_id, bid)

    tasks = engine.evaluate(bid, tenant_id, context)
    return {
        "context": context,
        "tasks_created": len(tasks),
        "tasks": [t.to_dict() for t in tasks],
    }


@router.post("/automation/tasks/{task_id}/approve")
async def approve_automation_task(
    task_id: str,
    request: Request,
    user=Depends(current_user),
):
    """Approve an automation task that's awaiting approval."""
    from ..runtime.automation import get_automation_engine

    engine = get_automation_engine()
    success = engine.approve(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="task not found or not awaiting approval")
    return {"status": "approved", "task_id": task_id}


@router.post("/automation/tasks/{task_id}/reject")
async def reject_automation_task(
    task_id: str,
    request: Request,
    user=Depends(current_user),
):
    """Reject an automation task that's awaiting approval."""
    from ..runtime.automation import get_automation_engine

    engine = get_automation_engine()
    success = engine.reject(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="task not found or not awaiting approval")
    return {"status": "rejected", "task_id": task_id}


# ─── Evaluation Framework (Phase J) ──────────────────────────────────────────


@router.get("/evaluation/datasets")
async def list_evaluation_datasets(
    request: Request,
    user=Depends(current_user),
):
    """List all evaluation datasets and their cases."""
    from ..runtime.evaluation import get_regression_suite

    suite = get_regression_suite()
    datasets = {}
    for name, cases in suite.datasets.items():
        datasets[name] = {
            "count": len(cases),
            "cases": [c.to_dict() for c in cases],
        }
    return {"datasets": datasets, "total_cases": suite.total_cases}


@router.post("/evaluation/run")
async def run_regression_suite(
    request: Request,
    user=Depends(current_user),
):
    """Run the regression suite (static checks only — no AI calls).

    This verifies that all evaluation cases are well-formed and that
    the output structure checks pass. For AI-powered quality scoring,
    use the /evaluation/score endpoint with actual outputs.
    """
    from ..runtime.evaluation import get_regression_suite

    suite = get_regression_suite()
    result = suite.run_static()
    return result.to_dict()


@router.post("/evaluation/score")
async def score_outputs(
    request: Request,
    user=Depends(current_user),
):
    """Score a set of outputs against the evaluation suite.

    Request body: {"outputs": {"case_id": {...output...}, ...}}
    """
    from ..runtime.evaluation import get_regression_suite

    body = await request.json()
    outputs = body.get("outputs", {})
    suite = get_regression_suite()
    result = suite.run_with_outputs(outputs)
    return result.to_dict()
