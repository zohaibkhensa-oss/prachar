"""Domain events for the Marketing Intelligence Engine.

Events are published by the Campaign Brain as it runs engines. Subscribers
can observe these events without the brain knowing about them — this is
the observer pattern, enabling loose coupling.

Events:
- BusinessAnalysed
- AudienceIdentified
- CompetitorsAnalysed
- ObjectiveDerived
- StrategyGenerated
- CreativeDirectionReady
- MediaPlanReady
- BudgetCalculated
- ExecutionPlanned
- CampaignCompleted
- LearningStored

Usage:
    from prachar_shared.marketing_intelligence import EventBus, BusinessAnalysed

    bus = EventBus()
    bus.subscribe(BusinessAnalysed, lambda e: print(f"Business analysed: {e.industry}"))
    brain = CampaignBrain(event_bus=bus)
    # When brain.analyse_business() completes, it publishes BusinessAnalysed

The event bus is in-process (no external broker). For cross-service events,
a future adapter can forward to Redis/SQS.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Protocol, runtime_checkable


def _utcnow_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─── Event base ─────────────────────────────────────────────────────────────


@dataclass
class DomainEvent:
    """Base class for all domain events."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=_utcnow_iso)
    tenant_id: str = ""
    brand_id: str = ""

    @property
    def event_type(self) -> str:
        return self.__class__.__name__


# ─── Engine events ──────────────────────────────────────────────────────────


@dataclass
class BusinessAnalysed(DomainEvent):
    industry: str = ""
    confidence: float = 0.0


@dataclass
class AudienceIdentified(DomainEvent):
    buying_intent: str = ""
    confidence: float = 0.0


@dataclass
class CompetitorsAnalysed(DomainEvent):
    competitor_count: int = 0
    confidence: float = 0.0


@dataclass
class ObjectiveDerived(DomainEvent):
    objective_type: str = ""
    confidence: float = 0.0


@dataclass
class StrategyGenerated(DomainEvent):
    core_message: str = ""
    confidence: float = 0.0


@dataclass
class CreativeDirectionReady(DomainEvent):
    visual_style: str = ""
    confidence: float = 0.0


@dataclass
class MediaPlanReady(DomainEvent):
    channel_count: int = 0
    confidence: float = 0.0


@dataclass
class BudgetCalculated(DomainEvent):
    total_cost: str = ""
    confidence: float = 0.0


@dataclass
class ExecutionPlanned(DomainEvent):
    phase_count: int = 0
    confidence: float = 0.0


@dataclass
class CampaignCompleted(DomainEvent):
    overall_confidence: float = 0.0
    total_cost_usd: float = 0.0
    total_tokens: int = 0


@dataclass
class LearningStored(DomainEvent):
    overall_grade: str = ""
    best_practices_count: int = 0


# ─── Event handler protocol ─────────────────────────────────────────────────


@runtime_checkable
class EventHandler(Protocol):
    def __call__(self, event: DomainEvent) -> None: ...


# ─── Event bus ──────────────────────────────────────────────────────────────


class EventBus:
    """In-process event bus for domain events.

    Subscribers register for specific event types. When an event is published,
    all subscribers for that type are called synchronously.

    This is intentionally simple — no async, no external broker. For
    cross-service events, wrap this bus with an adapter that forwards
    to Redis/SQS.
    """

    def __init__(self) -> None:
        self._subscribers: dict[type[DomainEvent], list[EventHandler]] = {}

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        """Subscribe to a specific event type."""
        self._subscribers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        """Unsubscribe from a specific event type."""
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def publish(self, event: DomainEvent) -> None:
        """Publish an event to all subscribers of its type."""
        handlers = self._subscribers.get(type(event), [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:  # noqa: BLE001
                import logging
                logging.getLogger(__name__).warning(
                    "event handler failed for %s: %s",
                    type(event).__name__,
                    exc,
                )

    def clear(self) -> None:
        """Remove all subscribers."""
        self._subscribers.clear()
