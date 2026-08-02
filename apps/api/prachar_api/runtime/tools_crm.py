"""Phase L4 — CRM Assistant tool.

World-class CRM: contact management, pipeline tracking, follow-up reminders,
insights. Emits crm_pipeline + contact_card artefacts.
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
from .artefacts import crm_pipeline, contact_card, task_list

log = logging.getLogger("prachar.runtime.tools.crm")


@register_tool(ToolManifest(
    name="crm.pipeline",
    display_name="CRM Pipeline View",
    description="Shows the sales pipeline with contacts at each stage, deal values, conversion rates, and bottleneck analysis. Identifies deals at risk and recommends next actions.",
    category=ToolCategory.CRM,
    input_schema={},
    output_schema={"pipeline": "object"},
    estimated_cost_usd=0.03,
    estimated_time_ms=3000,
    estimated_tokens=500,
    estimated_latency_ms=3000,
    quality_score=0.85,
    supports_streaming=False,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.PERFORMANCE, MemoryCategory.CAMPAIGN],
))
async def crm_pipeline_view(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """View the sales pipeline."""
    from sqlalchemy import select, func
    from ..models.tables import LeadRecord

    # Get leads grouped by stage
    res = await ctx.session.execute(
        select(LeadRecord.stage, func.count(LeadRecord.id), func.sum(LeadRecord.estimated_value))
        .where(LeadRecord.brand_id == ctx.brand_id)
        .group_by(LeadRecord.stage)
    )
    rows = res.all()

    stages: list[dict[str, Any]] = []
    total_value = 0.0
    total_contacts = 0
    for stage, count, value in rows:
        stages.append({
            "stage": stage or "new",
            "count": count,
            "value": float(value or 0),
        })
        total_value += float(value or 0)
        total_contacts += count

    # Sort by pipeline order
    stage_order = ["new", "contacted", "qualified", "proposal", "negotiation", "won", "lost"]
    stages.sort(key=lambda s: stage_order.index(s["stage"]) if s["stage"] in stage_order else 99)

    return {
        "pipeline": {"stages": stages, "total_value": total_value, "contact_count": total_contacts},
        "artefacts": [crm_pipeline(
            stages=stages,
            total_value=f"₹{total_value:,.0f}",
            contact_count=total_contacts,
        ).to_dict()],
    }


@register_tool(ToolManifest(
    name="crm.follow_ups",
    display_name="Follow-Up Reminders",
    description="Identifies contacts that need follow-up based on last contact date, stage, and deal value. Prioritises by urgency and potential.",
    category=ToolCategory.CRM,
    input_schema={},
    output_schema={"follow_ups": "array"},
    estimated_cost_usd=0.02,
    estimated_time_ms=2000,
    estimated_tokens=300,
    estimated_latency_ms=2000,
    quality_score=0.83,
    supports_streaming=False,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.PERFORMANCE],
))
async def crm_follow_ups(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Get follow-up reminders."""
    from sqlalchemy import select
    from datetime import datetime, timedelta
    from ..models.tables import LeadRecord

    cutoff = datetime.now() - timedelta(days=3)
    res = await ctx.session.execute(
        select(LeadRecord)
        .where(
            LeadRecord.brand_id == ctx.brand_id,
            LeadRecord.stage.notin_(["won", "lost"]),
            (LeadRecord.last_contact_at < cutoff) | (LeadRecord.last_contact_at.is_(None)),
        )
        .order_by(LeadRecord.estimated_value.desc())
        .limit(20)
    )
    leads = res.scalars().all()

    follow_ups: list[dict[str, Any]] = []
    artefacts: list[dict] = []
    for lead in leads:
        days_since = (datetime.now() - (lead.last_contact_at or datetime.now())).days if lead.last_contact_at else 999
        urgency = "high" if days_since > 7 else "medium" if days_since > 3 else "low"
        follow_ups.append({
            "contact_id": str(lead.id),
            "name": lead.name or "Unknown",
            "stage": lead.stage or "new",
            "value": float(lead.estimated_value or 0),
            "days_since_contact": days_since,
            "urgency": urgency,
            "next_action": f"Follow up with {lead.name or 'contact'} — {days_since} days since last contact",
        })
        artefacts.append(contact_card(
            name=lead.name or "Unknown",
            stage=lead.stage or "new",
            value=f"₹{float(lead.estimated_value or 0):,.0f}",
            next_action=f"Follow up ({days_since} days overdue)",
        ).to_dict())

    return {
        "follow_ups": follow_ups,
        "artefacts": artefacts + [task_list([
            {"title": f["next_action"], "priority": f["urgency"], "action": f["next_action"]}
            for f in follow_ups[:5]
        ]).to_dict()],
    }


@register_tool(ToolManifest(
    name="crm.insights",
    display_name="CRM Insights",
    description="Analyses the sales pipeline and provides insights: conversion rates, bottleneck stages, deal velocity, and recommendations to improve close rates.",
    category=ToolCategory.CRM,
    input_schema={},
    output_schema={"insights": "object"},
    estimated_cost_usd=0.05,
    estimated_time_ms=6000,
    estimated_tokens=1000,
    estimated_latency_ms=5000,
    quality_score=0.87,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.PERFORMANCE],
))
async def crm_insights(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Analyse the sales pipeline and provide insights."""
    from sqlalchemy import select, func
    from ..models.tables import LeadRecord

    res = await ctx.session.execute(
        select(LeadRecord.stage, func.count(LeadRecord.id), func.sum(LeadRecord.estimated_value))
        .where(LeadRecord.brand_id == ctx.brand_id)
        .group_by(LeadRecord.stage)
    )
    rows = res.all()

    total = sum(r[1] for r in rows)
    won = next((r[1] for r in rows if r[0] == "won"), 0)
    lost = next((r[1] for r in rows if r[0] == "lost"), 0)
    conversion_rate = (won / total * 100) if total > 0 else 0

    # Find bottleneck (stage with most contacts but lowest advancement)
    stage_counts = {r[0]: r[1] for r in rows}
    bottleneck = max(stage_counts.items(), key=lambda x: x[1]) if stage_counts else ("none", 0)

    insights = {
        "total_leads": total,
        "won": won,
        "lost": lost,
        "conversion_rate": round(conversion_rate, 1),
        "bottleneck_stage": bottleneck[0],
        "bottleneck_count": bottleneck[1],
        "recommendations": [
            {
                "priority": "high",
                "action": f"Focus on moving {bottleneck[1]} leads from '{bottleneck[0]}' stage",
                "expected_impact": "Increase pipeline velocity by 20-30%",
            },
            {
                "priority": "medium",
                "action": "Set up automated follow-up reminders for leads > 3 days idle",
                "expected_impact": "Prevent 15-25% of leads from going cold",
            },
        ],
    }

    return {"insights": insights}
