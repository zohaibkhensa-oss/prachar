"""Webhook receiver — receives webhooks from external platforms and dispatches to the event bus.

This endpoint is the entry point for all platform webhooks:
- POST /webhooks/{integration} — receives a webhook from a platform

The endpoint:
1. Identifies the integration by URL path
2. Looks up the adapter in the integration registry
3. Calls adapter.parse_webhook() to verify signature and parse the event
4. Publishes the normalised WebhookEvent to the event bus
5. Returns 200 OK quickly (platforms expect fast acknowledgement)

Handlers on the event bus process the event asynchronously.

Security:
- Each adapter verifies the webhook signature (HMAC, etc.)
- Invalid signatures return 401
- Unknown integrations return 404
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from prachar_shared.integrations import get_integration_registry, get_event_bus
from prachar_shared.integrations.google_analytics import GoogleAnalytics4
from prachar_shared.integrations.wordpress import WordPress
from prachar_shared.integrations.shopify import Shopify
from prachar_shared.integrations.mailchimp import Mailchimp
from prachar_shared.integrations.hubspot import HubSpot

log = logging.getLogger("prachar.api.webhooks")
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/{integration}")
async def receive_webhook(
    integration: str,
    request: Request,
) -> JSONResponse:
    """Receive a webhook from an external platform.

    The platform sends a POST to /webhooks/{integration} with:
    - Platform-specific headers (for signature verification)
    - JSON body with the event data

    The endpoint verifies the signature, normalises the event, and
    dispatches it to the event bus for async processing.
    """
    registry = get_integration_registry()
    integration_cls = registry.get(integration)

    if integration_cls is None:
        log.warning("Webhook received for unknown integration: %s", integration)
        raise HTTPException(status_code=404, detail=f"Unknown integration: {integration}")

    # Read the raw body (needed for HMAC verification)
    raw_body = await request.body()

    # Parse the body as JSON
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}

    # Collect headers (case-insensitive)
    headers = {k.lower(): v for k, v in request.headers.items()}

    # Get the adapter and parse the webhook
    adapter = integration_cls()

    try:
        # Pass the raw body for HMAC verification
        # The adapter's parse_webhook method handles signature verification
        event = adapter.parse_webhook(
            headers=headers,
            body=body,
            raw_body=raw_body,
        )
    except NotImplementedError:
        log.warning("Integration %s does not support webhooks", integration)
        raise HTTPException(status_code=501, detail="Webhooks not supported for this integration")
    except Exception as e:
        log.error("Webhook parsing failed for %s: %s", integration, e, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Webhook parsing failed: {e}")

    if event is None:
        # Signature verification failed or event could not be parsed
        log.warning("Webhook from %s rejected (invalid signature or unparseable)", integration)
        raise HTTPException(status_code=401, detail="Webhook verification failed")

    # Publish to the event bus
    bus = get_event_bus()
    await bus.publish(event)

    log.info(
        "Webhook received: %s/%s (entity: %s/%s)",
        event.integration, event.event_type, event.entity_type, event.entity_id,
    )

    # Return 200 quickly — platforms expect fast acknowledgement
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "received", "event_type": event.event_type},
    )


@router.get("/stats")
async def webhook_stats() -> dict[str, Any]:
    """Return event bus statistics for observability."""
    bus = get_event_bus()
    return bus.stats()
