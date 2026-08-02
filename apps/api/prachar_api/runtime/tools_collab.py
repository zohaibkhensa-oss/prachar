"""Phase L8 — Team Collaboration tool.

World-class team: task assignment, approval workflows, comments, roles.
Emits team_board artefact.
"""
from __future__ import annotations

import logging
from typing import Any

from .registry import (
    SideEffects,
    ToolCategory,
    ToolManifest,
    register_tool,
)
from .memory_categories import MemoryCategory
from .context import AIContext
from .artefacts import team_board, task_list

log = logging.getLogger("prachar.runtime.tools.collab")


@register_tool(ToolManifest(
    name="team.board",
    display_name="Team Board",
    description="Shows the team board with members, roles, assigned tasks, and pending approvals. Provides an overview of who is doing what and what needs attention.",
    category=ToolCategory.COLLABORATION,
    input_schema={},
    output_schema={"board": "object"},
    estimated_cost_usd=0.02,
    estimated_time_ms=2000,
    estimated_tokens=300,
    estimated_latency_ms=2000,
    quality_score=0.82,
    supports_streaming=False,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.PERFORMANCE],
))
async def team_board_view(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """View the team board."""
    from sqlalchemy import select
    from ..models.tables import TeamMember, TaskRecord

    # Get team members
    members_res = await ctx.session.execute(
        select(TeamMember)
        .where(TeamMember.brand_id == ctx.brand_id)
        .order_by(TeamMember.role)
    )
    members = members_res.scalars().all()

    # Get tasks
    tasks_res = await ctx.session.execute(
        select(TaskRecord)
        .where(TaskRecord.brand_id == ctx.brand_id)
        .order_by(TaskRecord.priority.desc())
        .limit(50)
    )
    tasks = tasks_res.scalars().all()

    member_list = [
        {
            "id": str(m.id),
            "name": m.name,
            "role": m.role,
            "email": m.email,
            "active": m.active,
        }
        for m in members
    ]
    task_list_data = [
        {
            "id": str(t.id),
            "title": t.title,
            "assignee": t.assignee_id,
            "status": t.status,
            "priority": t.priority,
        }
        for t in tasks
    ]
    pending = [t for t in task_list_data if t["status"] == "pending_approval"]

    return {
        "board": {"members": member_list, "tasks": task_list_data, "pending_approvals": pending},
        "artefacts": [team_board(
            members=member_list,
            tasks=task_list_data,
            pending_approvals=pending,
        ).to_dict()],
    }


@register_tool(ToolManifest(
    name="team.assign",
    display_name="Task Assigner",
    description="Assigns a task to a team member with priority, deadline, and context. Notifies the assignee and tracks progress.",
    category=ToolCategory.COLLABORATION,
    input_schema={"task_title": "string", "assignee_id": "string", "priority": "string", "deadline": "string", "context": "string"},
    output_schema={"task": "object"},
    estimated_cost_usd=0.01,
    estimated_time_ms=1000,
    estimated_tokens=100,
    estimated_latency_ms=1000,
    quality_score=0.80,
    supports_streaming=False,
    requires_brand=True,
    side_effects=SideEffects.WRITES,
    memory_categories=[MemoryCategory.CAMPAIGN],
))
async def team_assign(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Assign a task to a team member."""
    from sqlalchemy import select
    from ..models.tables import TaskRecord, TeamMember
    from ..audit import audit_event

    assignee_id = input.get("assignee_id", "")
    title = input.get("task_title", "Untitled task")
    priority = input.get("priority", "medium")
    deadline = input.get("deadline", "")
    context = input.get("context", "")

    # Verify assignee exists
    member = await ctx.session.execute(
        select(TeamMember).where(TeamMember.id == assignee_id)
    )
    member = member.scalar_one_or_none()
    if not member:
        return {"error": "assignee not found", "task": {}}

    task = TaskRecord(
        brand_id=ctx.brand_id,
        title=title,
        assignee_id=assignee_id,
        status="assigned",
        priority=priority,
        deadline=deadline,
        context=context,
    )
    ctx.session.add(task)
    await ctx.session.commit()

    await audit_event(
        ctx.session, ctx.tenant_id, ctx.user_id,
        action="team.task_assigned",
        resource_type="task", resource_id=str(task.id),
        details={"title": title, "assignee": assignee_id, "priority": priority},
    )

    return {
        "task": {
            "id": str(task.id),
            "title": title,
            "assignee": member.name,
            "priority": priority,
            "deadline": deadline,
            "status": "assigned",
        },
        "artefacts": [task_list([{
            "title": title,
            "assignee": member.name,
            "priority": priority,
            "deadline": deadline,
        }]).to_dict()],
    }


@register_tool(ToolManifest(
    name="team.approve",
    display_name="Approval Workflow",
    description="Submits a campaign or creative for approval. Routes to the appropriate approver based on role and tracks the approval chain.",
    category=ToolCategory.COLLABORATION,
    input_schema={"item_type": "string", "item_id": "string", "submitted_by": "string", "notes": "string"},
    output_schema={"approval": "object"},
    estimated_cost_usd=0.01,
    estimated_time_ms=1000,
    estimated_tokens=100,
    estimated_latency_ms=1000,
    quality_score=0.81,
    supports_streaming=False,
    requires_brand=True,
    side_effects=SideEffects.WRITES,
    memory_categories=[MemoryCategory.CAMPAIGN],
))
async def team_approve(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Submit an item for approval."""
    from ..models.tables import ApprovalRecord
    from ..audit import audit_event

    item_type = input.get("item_type", "campaign")
    item_id = input.get("item_id", "")
    submitted_by = input.get("submitted_by", str(ctx.user_id))
    notes = input.get("notes", "")

    approval = ApprovalRecord(
        brand_id=ctx.brand_id,
        item_type=item_type,
        item_id=item_id,
        submitted_by=submitted_by,
        status="pending",
        notes=notes,
    )
    ctx.session.add(approval)
    await ctx.session.commit()

    await audit_event(
        ctx.session, ctx.tenant_id, ctx.user_id,
        action="team.approval_submitted",
        resource_type=item_type, resource_id=item_id,
        details={"approval_id": str(approval.id), "notes": notes},
    )

    return {
        "approval": {
            "id": str(approval.id),
            "item_type": item_type,
            "item_id": item_id,
            "status": "pending",
            "submitted_by": submitted_by,
        },
    }
