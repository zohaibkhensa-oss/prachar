"""Integration Event Bus — routes webhook events to handlers.

The event bus allows the Runtime to react to external events in real-time
instead of polling. When a webhook arrives (e.g. Shopify order_created,
HubSpot deal_won), the event bus dispatches it to all registered handlers.

Handlers are async callables that receive a WebhookEvent. They can:
- Update internal state (e.g. mark a campaign as converted)
- Trigger new workflows (e.g. send a thank-you email)
- Store the event for analytics
- Notify the user

This is the foundation of the "AI Marketing Operating System" — the
Runtime becomes an orchestrator that reacts to external system events.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

from .base import WebhookEvent

log = logging.getLogger("prachar.integrations.event_bus")

# Type for event handlers
EventHandler = Callable[[WebhookEvent], Awaitable[Any]]


class IntegrationEventBus:
    """Async event bus for routing webhook events to handlers.

    Events are routed by:
    1. Integration name (e.g. "shopify", "hubspot")
    2. Event type (e.g. "orders/create", "deal.creation")
    3. Wildcard "*" matches all events

    Handlers are async callables. Multiple handlers can subscribe to the
    same event. All handlers run concurrently.

    Usage:
        bus = IntegrationEventBus()

        @bus.on("shopify", "orders/create")
        async def handle_order(event: WebhookEvent):
            log.info("New order: %s", event.entity_id)

        @bus.on("hubspot", "deal.propertyChange")
        async def handle_deal_change(event: WebhookEvent):
            if event.payload.get("propertyName") == "dealstage":
                log.info("Deal stage changed: %s", event.entity_id)

        @bus.on("*", "*")
        async def log_all(event: WebhookEvent):
            log.info("Event: %s/%s", event.integration, event.event_type)
    """

    def __init__(self) -> None:
        # (integration, event_type) -> list of handlers
        self._handlers: dict[tuple[str, str], list[EventHandler]] = defaultdict(list)
        # Track event counts for observability
        self._event_counts: dict[str, int] = defaultdict(int)
        self._error_counts: dict[str, int] = defaultdict(int)

    def on(
        self,
        integration: str,
        event_type: str,
        handler: EventHandler | None = None,
    ) -> Callable[[EventHandler], EventHandler] | EventHandler:
        """Register a handler for a specific integration + event type.

        Can be used as a decorator or called directly:

            @bus.on("shopify", "orders/create")
            async def handler(event): ...

            bus.on("shopify", "orders/create", handler)

        Use "*" as a wildcard for integration or event_type to match all.
        """
        def decorator(h: EventHandler) -> EventHandler:
            self._handlers[(integration, event_type)].append(h)
            log.debug("Registered handler for %s/%s: %s", integration, event_type, h.__name__)
            return h

        if handler is not None:
            return decorator(handler)
        return decorator

    def off(self, integration: str, event_type: str, handler: EventHandler) -> None:
        """Remove a previously registered handler."""
        handlers = self._handlers.get((integration, event_type), [])
        if handler in handlers:
            handlers.remove(handler)
            log.debug("Removed handler for %s/%s", integration, event_type)

    async def publish(self, event: WebhookEvent) -> list[Any]:
        """Dispatch an event to all matching handlers.

        Handlers are matched by:
        1. Exact (integration, event_type)
        2. (integration, "*")
        3. ("*", event_type)
        4. ("*", "*")

        All matching handlers run concurrently. Errors in one handler
        don't affect others.

        Returns a list of results from all handlers (in match order).
        """
        key = (event.integration, event.event_type)
        self._event_counts[key[0]] += 1

        # Collect all matching handlers
        matching: list[EventHandler] = []
        matching.extend(self._handlers.get((event.integration, event.event_type), []))
        matching.extend(self._handlers.get((event.integration, "*"), []))
        matching.extend(self._handlers.get(("*", event.event_type), []))
        matching.extend(self._handlers.get(("*", "*"), []))

        if not matching:
            log.debug("No handlers for %s/%s", event.integration, event.event_type)
            return []

        log.info(
            "Dispatching %s/%s to %d handler(s)",
            event.integration, event.event_type, len(matching),
        )

        # Run all handlers concurrently
        results: list[Any] = []
        tasks = []
        for handler in matching:
            tasks.append(self._run_handler(handler, event))

        completed = await asyncio.gather(*tasks, return_exceptions=True)
        for result in completed:
            if isinstance(result, Exception):
                self._error_counts[key[0]] += 1
                log.error(
                    "Handler error for %s/%s: %s",
                    event.integration, event.event_type, result,
                    exc_info=result,
                )
            else:
                results.append(result)

        return results

    async def _run_handler(self, handler: EventHandler, event: WebhookEvent) -> Any:
        """Run a single handler with error isolation."""
        try:
            return await handler(event)
        except Exception as e:
            log.error("Handler %s failed: %s", handler.__name__, e, exc_info=True)
            raise

    def stats(self) -> dict[str, Any]:
        """Return event bus statistics for observability."""
        return {
            "registered_handlers": sum(len(hs) for hs in self._handlers.values()),
            "event_counts": dict(self._event_counts),
            "error_counts": dict(self._error_counts),
            "subscriptions": {
                f"{integ}/{evt}": len(hs)
                for (integ, evt), hs in self._handlers.items()
                if hs
            },
        }

    def clear(self) -> None:
        """Remove all handlers and reset stats."""
        self._handlers.clear()
        self._event_counts.clear()
        self._error_counts.clear()


# Singleton
_event_bus = IntegrationEventBus()


def get_event_bus() -> IntegrationEventBus:
    """Get the global event bus instance."""
    return _event_bus
