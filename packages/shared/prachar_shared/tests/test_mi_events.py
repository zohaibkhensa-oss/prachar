"""Tests for the domain event model (Phase 8: Architecture Stabilisation)."""
from __future__ import annotations

import uuid
from typing import Any

import pytest

from prachar_shared.marketing_intelligence import (
    AudienceIdentified,
    BudgetCalculated,
    BusinessAnalysed,
    CampaignBrain,
    CampaignCompleted,
    CompetitorsAnalysed,
    CreativeDirectionReady,
    DomainEvent,
    EventBus,
    ExecutionPlanned,
    LearningStored,
    MediaPlanReady,
    ObjectiveDerived,
    StrategyGenerated,
)
from prachar_shared.ai_gateway import Completion


class _StubGateway:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def complete(self, **kw: Any) -> Completion:
        self.calls.append(kw)
        task = kw.get("task", "generic")
        results: dict[str, dict[str, Any]] = {
            "business_intelligence": {"industry": "Coffee", "confidence": 0.8, "reasoning": "r"},
            "audience_intelligence": {"buying_intent": "high", "confidence": 0.75, "reasoning": "r"},
            "competitor_intelligence": {"competitors": [{"name": "X"}], "confidence": 0.6, "reasoning": "r"},
            "marketing_objective": {"objective_type": "sales", "confidence": 0.85, "reasoning": "r"},
            "campaign_strategy": {"core_message": "test", "confidence": 0.7, "reasoning": "r"},
            "creative_direction": {"visual_style": "Editorial", "confidence": 0.75, "reasoning": "r"},
            "media_planning": {"recommended_channels": [{"channel": "IG"}], "confidence": 0.65, "reasoning": "r"},
            "budget_intelligence": {"total_cost": {"amount": "₹1L"}, "confidence": 0.6, "reasoning": "r"},
            "execution_planner": {"phases": [{"phase": "1"}], "confidence": 0.8, "reasoning": "r"},
            "learning_engine": {"performance_summary": {"overall_grade": "B"}, "updated_best_practices": ["x"], "confidence": 0.75, "reasoning": "r"},
        }
        result = results.get(task, {"confidence": 0.5, "reasoning": "stub"})
        return Completion(
            text="[stub]", json_value=result, tokens_used=100,
            model="stub", provider="stub", latency_ms=5.0,
            cost_usd=0.001, request_id=f"req-{task}",
            confidence=result.get("confidence", 0.7),
        )


# ─── Event basics ───────────────────────────────────────────────────────────


class TestDomainEvent:
    def test_event_has_id_and_timestamp(self) -> None:
        event = BusinessAnalysed()
        assert event.event_id != ""
        assert event.timestamp != ""
        assert "T" in event.timestamp

    def test_event_type_property(self) -> None:
        event = BusinessAnalysed()
        assert event.event_type == "BusinessAnalysed"

    def test_event_carries_data(self) -> None:
        event = BusinessAnalysed(industry="Coffee", confidence=0.8)
        assert event.industry == "Coffee"
        assert event.confidence == 0.8


# ─── Event bus ──────────────────────────────────────────────────────────────


class TestEventBus:
    def test_subscribe_and_publish(self) -> None:
        bus = EventBus()
        received: list[DomainEvent] = []
        bus.subscribe(BusinessAnalysed, lambda e: received.append(e))
        bus.publish(BusinessAnalysed(industry="Coffee"))
        assert len(received) == 1
        assert received[0].industry == "Coffee"

    def test_unsubscribe(self) -> None:
        bus = EventBus()
        received: list[DomainEvent] = []
        handler = lambda e: received.append(e)
        bus.subscribe(BusinessAnalysed, handler)
        bus.unsubscribe(BusinessAnalysed, handler)
        bus.publish(BusinessAnalysed())
        assert len(received) == 0

    def test_only_matching_handlers_called(self) -> None:
        bus = EventBus()
        business_events: list[DomainEvent] = []
        strategy_events: list[DomainEvent] = []
        bus.subscribe(BusinessAnalysed, lambda e: business_events.append(e))
        bus.subscribe(StrategyGenerated, lambda e: strategy_events.append(e))
        bus.publish(BusinessAnalysed())
        assert len(business_events) == 1
        assert len(strategy_events) == 0

    def test_handler_exception_does_not_break_bus(self) -> None:
        bus = EventBus()
        received: list[DomainEvent] = []
        def bad_handler(e: DomainEvent) -> None:
            raise RuntimeError("boom")
        bus.subscribe(BusinessAnalysed, bad_handler)
        bus.subscribe(BusinessAnalysed, lambda e: received.append(e))
        bus.publish(BusinessAnalysed())  # should not raise
        assert len(received) == 1  # second handler still called

    def test_clear(self) -> None:
        bus = EventBus()
        received: list[DomainEvent] = []
        bus.subscribe(BusinessAnalysed, lambda e: received.append(e))
        bus.clear()
        bus.publish(BusinessAnalysed())
        assert len(received) == 0

    def test_publish_no_subscribers(self) -> None:
        bus = EventBus()
        bus.publish(BusinessAnalysed())  # should not raise


# ─── Brain publishes events ─────────────────────────────────────────────────


class TestBrainPublishesEvents:
    @pytest.mark.asyncio
    async def test_full_campaign_publishes_all_events(self) -> None:
        bus = EventBus()
        received: list[DomainEvent] = []
        for event_type in [
            BusinessAnalysed, AudienceIdentified, CompetitorsAnalysed,
            ObjectiveDerived, StrategyGenerated, CreativeDirectionReady,
            MediaPlanReady, BudgetCalculated, ExecutionPlanned, CampaignCompleted,
        ]:
            bus.subscribe(event_type, lambda e: received.append(e))

        brain = CampaignBrain(gateway=_StubGateway(), event_bus=bus)
        await brain.generate_campaign(
            tenant_id=uuid.uuid4(), plan="agency",
            business_name="Acme", goal="grow",
        )
        # All 10 event types should have been published
        event_types = {type(e) for e in received}
        assert BusinessAnalysed in event_types
        assert AudienceIdentified in event_types
        assert CompetitorsAnalysed in event_types
        assert ObjectiveDerived in event_types
        assert StrategyGenerated in event_types
        assert CreativeDirectionReady in event_types
        assert MediaPlanReady in event_types
        assert BudgetCalculated in event_types
        assert ExecutionPlanned in event_types
        assert CampaignCompleted in event_types

    @pytest.mark.asyncio
    async def test_campaign_completed_has_metadata(self) -> None:
        bus = EventBus()
        completed: list[CampaignCompleted] = []
        bus.subscribe(CampaignCompleted, lambda e: completed.append(e))  # type: ignore[arg-type]

        brain = CampaignBrain(gateway=_StubGateway(), event_bus=bus)
        await brain.generate_campaign(
            tenant_id=uuid.uuid4(), plan="agency",
            business_name="Acme", goal="grow",
        )
        assert len(completed) == 1
        assert completed[0].overall_confidence > 0
        assert completed[0].total_tokens > 0

    @pytest.mark.asyncio
    async def test_learn_publishes_learning_stored(self) -> None:
        from prachar_shared.marketing_intelligence import BusinessMemoryStore
        bus = EventBus()
        stored: list[LearningStored] = []
        bus.subscribe(LearningStored, lambda e: stored.append(e))  # type: ignore[arg-type]

        brain = CampaignBrain(gateway=_StubGateway(), memory_store=BusinessMemoryStore(), event_bus=bus)
        await brain.learn(
            tenant_id=uuid.uuid4(), brand_id=uuid.uuid4(),
            campaign_plan={}, performance_data={},
        )
        assert len(stored) == 1
        assert stored[0].overall_grade == "B"

    @pytest.mark.asyncio
    async def test_no_event_bus_does_not_crash(self) -> None:
        """Brain should work fine without an event bus."""
        brain = CampaignBrain(gateway=_StubGateway())  # no event_bus
        campaign = await brain.generate_campaign(
            tenant_id=uuid.uuid4(), plan="agency",
            business_name="Acme", goal="grow",
        )
        assert campaign.business_profile.industry == "Coffee"
