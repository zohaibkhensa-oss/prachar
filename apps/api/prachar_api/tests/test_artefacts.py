"""Phase D / Step 3 tests — Live Capability Rendering.

Tests artefact factories, artefact events, and executor artefact emission.
"""
from __future__ import annotations

import asyncio
import pytest
import uuid

from prachar_api.runtime.artefacts import (
    Artefact,
    campaign_card,
    kpi_widget,
    kpi_grid,
    image_artefact,
    chart,
    budget_table,
    copy_draft,
    review_feedback,
    review_summary,
    timeline_plan,
    opportunity_card,
    audience_card,
    competitor_card,
    creative_brief,
    media_plan,
    task_list,
    alert,
    memory_insight,
)
from prachar_api.runtime.events import make_artefact_event, SessionManager
from prachar_api.runtime.registry import ToolManifest, ToolRegistry, ToolCategory
from prachar_api.runtime.graph import ExecutionGraph, GraphNode
from prachar_api.runtime.context import AIContext
from prachar_api.runtime.executor import ExecutionEngine


class TestArtefactFactories:
    """All artefact factories produce valid Artefact objects."""

    def test_campaign_card(self):
        a = campaign_card("Diwali Sale", "Sales", "₹5000", ["Instagram", "Google"])
        assert a.kind == "campaign_card"
        assert a.payload["name"] == "Diwali Sale"
        assert a.payload["channels"] == ["Instagram", "Google"]
        d = a.to_dict()
        assert d["kind"] == "campaign_card"

    def test_kpi_widget(self):
        a = kpi_widget("Reach", "12.4K", "↑ 18%", True, [10, 12, 15, 14, 18])
        assert a.kind == "kpi_widget"
        assert a.payload["value"] == "12.4K"
        assert len(a.payload["sparkline"]) == 5

    def test_kpi_grid(self):
        a = kpi_grid([{"label": "A", "value": 1}, {"label": "B", "value": 2}])
        assert a.kind == "kpi_grid"
        assert len(a.payload["kpis"]) == 2

    def test_image_artefact(self):
        a = image_artefact("https://example.com/img.png", "Diwali ad", "festive sale")
        assert a.kind == "image"
        assert a.payload["url"] == "https://example.com/img.png"

    def test_chart(self):
        a = chart("bar", ["Jan", "Feb", "Mar"], [{"data": [10, 20, 30]}], "Monthly Sales")
        assert a.kind == "chart"
        assert a.payload["chart_type"] == "bar"
        assert len(a.payload["labels"]) == 3

    def test_budget_table(self):
        a = budget_table([{"channel": "Google", "amount": "₹2000"}], "₹5000")
        assert a.kind == "budget_table"
        assert a.payload["total"] == "₹5000"

    def test_copy_draft(self):
        a = copy_draft("Instagram", "Festive Sale!", "Get 20% off this Diwali", ["#diwali", "#sale"])
        assert a.kind == "copy_draft"
        assert a.payload["platform"] == "Instagram"
        assert a.payload["hashtags"] == ["#diwali", "#sale"]

    def test_review_feedback(self):
        a = review_feedback("CSO", "Good strategy", 0.9, score=8.5, risks=["Budget too high"])
        assert a.kind == "review_feedback"
        assert a.payload["director"] == "CSO"
        assert a.payload["score"] == 8.5

    def test_review_summary(self):
        a = review_summary(True, 8.5, ["Strong creative", "Good budget allocation"])
        assert a.kind == "review_summary"
        assert a.payload["approved"] is True

    def test_timeline_plan(self):
        a = timeline_plan([{"objective": "Awareness", "content": "Brand posts"}])
        assert a.kind == "timeline_plan"
        assert len(a.payload["weeks"]) == 1

    def test_opportunity_card(self):
        a = opportunity_card("Expand to YouTube", "high", "medium", "2 weeks")
        assert a.kind == "opportunity_card"
        assert a.payload["impact"] == "high"

    def test_audience_card(self):
        a = audience_card({"age": "25-34"}, ["food", "dining"], ["weekend diners"])
        assert a.kind == "audience_card"
        assert a.payload["interests"] == ["food", "dining"]

    def test_competitor_card(self):
        a = competitor_card("Competitor X", ["Strong SEO"], ["Weak social"])
        assert a.kind == "competitor_card"
        assert a.payload["strengths"] == ["Strong SEO"]

    def test_creative_brief(self):
        a = creative_brief("Festive joy", "Vibrant", "Warm", colors=["#FFD700", "#FF6B35"])
        assert a.kind == "creative_brief"
        assert len(a.payload["colors"]) == 2

    def test_media_plan(self):
        a = media_plan([{"channel": "Google", "budget": "₹2000"}], "₹5000")
        assert a.kind == "media_plan"
        assert a.payload["total_budget"] == "₹5000"

    def test_task_list(self):
        a = task_list([{"title": "Approve campaign", "priority": "high"}])
        assert a.kind == "task_list"
        assert len(a.payload["tasks"]) == 1

    def test_alert(self):
        a = alert("warning", "Budget 80% used", "You've spent ₹4000 of ₹5000")
        assert a.kind == "alert"
        assert a.payload["severity"] == "warning"

    def test_memory_insight(self):
        a = memory_insight("Creative", "Reels outperform carousels 3x", 0.85)
        assert a.kind == "memory_insight"
        assert a.payload["confidence"] == 0.85

    def test_artefact_from_dict(self):
        original = campaign_card("Test", "Goal", "₹100", ["IG"])
        d = original.to_dict()
        restored = Artefact.from_dict(d)
        assert restored.kind == original.kind
        assert restored.title == original.title
        assert restored.payload["name"] == "Test"


class TestArtefactEvents:
    """Artefact events are properly created and published."""

    async def test_make_artefact_event(self):
        a = campaign_card("Test", "Goal", "₹100", ["IG"])
        event = make_artefact_event("session-1", a, decision_id="dec-1", tool="campaign_brain.analyse")
        assert event.type == "artefact.campaign_card"
        assert event.data["artefact"]["kind"] == "campaign_card"
        assert event.decision_id == "dec-1"
        assert event.tool == "campaign_brain.analyse"

    async def test_artefact_event_published_to_bus(self):
        manager = SessionManager()
        sid, bus = await manager.create_session()
        a = kpi_widget("Reach", "12.4K", "↑ 18%")
        event = make_artefact_event(sid, a)
        await bus.publish(event)
        events = bus.get_all_events()
        assert len(events) == 1
        assert events[0].type == "artefact.kpi_widget"


class TestExecutorArtefactEmission:
    """The executor emits artefact events when tools return artefacts."""

    async def test_tool_with_artefacts_emits_event(self):
        registry = ToolRegistry()

        async def tool_with_artefacts(ctx, inp):
            return {
                "result": "ok",
                "artefacts": [
                    campaign_card("Test Campaign", "Sales", "₹5000", ["Instagram"]).to_dict(),
                    kpi_widget("Reach", "10K", "↑ 20%").to_dict(),
                ],
            }

        registry.register(ToolManifest(
            name="test.artefact_tool", display_name="Artefact Tool",
            category=ToolCategory.ANALYTICS, description="Returns artefacts",
            estimated_cost_usd=0.0, supports_retry=False,
        ), tool_with_artefacts)

        engine = ExecutionEngine(registry)
        graph = ExecutionGraph()
        graph.add_node(GraphNode(id="n1", tool="test.artefact_tool", input={}))

        ctx = AIContext(
            user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), brand_id=uuid.uuid4(),
            conversation=[],
        )

        manager = SessionManager()
        sid, bus = await manager.create_session()

        await engine.execute(
            graph=graph, ctx=ctx, bus=bus,
            decision_id="test", session_id=sid,
        )

        events = bus.get_all_events()
        artefact_events = [e for e in events if e.type.startswith("artefact.")]
        assert len(artefact_events) == 2
        assert artefact_events[0].type == "artefact.campaign_card"
        assert artefact_events[1].type == "artefact.kpi_widget"

    async def test_tool_without_artefacts_doesnt_emit(self):
        registry = ToolRegistry()

        async def plain_tool(ctx, inp):
            return {"result": "no artefacts here"}

        registry.register(ToolManifest(
            name="test.plain_tool", display_name="Plain Tool",
            category=ToolCategory.ANALYTICS, description="No artefacts",
            estimated_cost_usd=0.0, supports_retry=False,
        ), plain_tool)

        engine = ExecutionEngine(registry)
        graph = ExecutionGraph()
        graph.add_node(GraphNode(id="n1", tool="test.plain_tool", input={}))

        ctx = AIContext(
            user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), brand_id=uuid.uuid4(),
            conversation=[],
        )

        manager = SessionManager()
        sid, bus = await manager.create_session()

        await engine.execute(
            graph=graph, ctx=ctx, bus=bus,
            decision_id="test", session_id=sid,
        )

        events = bus.get_all_events()
        artefact_events = [e for e in events if e.type.startswith("artefact.")]
        assert len(artefact_events) == 0
