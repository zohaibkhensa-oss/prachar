"""HubSpot Integration — CRM contacts, deals, pipeline, marketing, webhooks.

World-class CRM integration:
- Authenticate via OAuth 2.0 (HubSpot)
- Sync contacts, companies, deals
- Update CRM pipeline (write back)
- Track deal revenue and conversion
- Webhook support for contact/deal events
- Feed CRM Assistant with real pipeline data

API: HubSpot CRM API v3
Docs: https://developers.hubspot.com/docs/api/crm
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from ..contracts import MetricEvent, TokenSet
from .base import (
    IntegrationCapability,
    IntegrationInfo,
    MarketingIntegration,
    WebhookEvent,
    WebhookSubscription,
    register_integration,
)

log = logging.getLogger("prachar.integrations.hubspot")

HUBSPOT_AUTH_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
HUBSPOT_API_BASE = "https://api.hubapi.com/crm/v3"
HUBSPOT_WEBHOOK_API = "https://api.hubapi.com/webhooks/v3/{app_id}/subscriptions"

HUBSPOT_SCOPES = [
    "crm.objects.contacts.read",
    "crm.objects.contacts.write",
    "crm.objects.companies.read",
    "crm.objects.deals.read",
    "crm.objects.deals.write",
    "crm.schemas.deals.read",
    "marketing.events.read",
]

HUBSPOT_WEBHOOK_EVENTS = [
    "contact.creation",
    "contact.propertyChange",
    "contact.deletion",
    "deal.creation",
    "deal.propertyChange",
    "deal.deletion",
    "company.creation",
    "company.propertyChange",
]


@register_integration
class HubSpot(MarketingIntegration):
    """HubSpot integration — CRM pipeline and contact management."""

    integration_name = "hubspot"
    integration_display_name = "HubSpot"

    @classmethod
    def info(cls) -> IntegrationInfo:
        return IntegrationInfo(
            name="hubspot",
            display_name="HubSpot",
            category="crm",
            icon="🎯",
            description="Connect HubSpot to sync contacts, companies, and deals. Update the CRM pipeline from PRACHAR campaigns. Track deal revenue and conversion. Webhooks for real-time CRM events.",
            capabilities=(
                IntegrationCapability.AUTHENTICATE
                | IntegrationCapability.READ_METRICS
                | IntegrationCapability.SYNC_ASSETS
                | IntegrationCapability.WRITE_BACK
                | IntegrationCapability.WEBHOOKS
                | IntegrationCapability.CRM
            ),
            auth_type="oauth",
            scopes=HUBSPOT_SCOPES,
            docs_url="https://developers.hubspot.com/docs/api/crm",
            setup_guide="1. Create a HubSpot Developer account. 2. Create an app. 3. Set OAuth redirect URI. 4. Configure scopes (contacts, deals, companies). 5. Install on your HubSpot portal.",
        )

    def auth_url(self, client_id: str, redirect_uri: str, state: str, scope: str = "") -> str:
        """Generate the HubSpot OAuth authorization URL."""
        from urllib.parse import urlencode

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope or " ".join(HUBSPOT_SCOPES),
            "state": state,
        }
        return f"{HUBSPOT_AUTH_URL}?{urlencode(params)}"

    def authenticate(self, **kwargs: Any) -> TokenSet:
        """Exchange OAuth code for tokens.

        Required kwargs:
            code: OAuth authorization code
            client_id: HubSpot app client ID
            client_secret: HubSpot app client secret
            redirect_uri: OAuth redirect URI
        """
        code = kwargs.get("code", "")
        client_id = kwargs.get("client_id", "")
        client_secret = kwargs.get("client_secret", "")
        redirect_uri = kwargs.get("redirect_uri", "")

        if not code:
            raise ValueError("OAuth code is required")

        resp = httpx.post(
            HUBSPOT_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600))
        return TokenSet(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=expires_at,
            scopes=HUBSPOT_SCOPES,
        )

    def refresh_token(self, refresh_token: str, client_id: str, client_secret: str) -> TokenSet:
        """Refresh an expired access token."""
        resp = httpx.post(
            HUBSPOT_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600))
        return TokenSet(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", refresh_token),
            expires_at=expires_at,
            scopes=HUBSPOT_SCOPES,
        )

    def _headers(self, tokens: TokenSet) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {tokens.access_token}",
            "Content-Type": "application/json",
        }

    def test_connection(self, tokens: TokenSet) -> bool:
        """Test if the connection is valid by fetching account info."""
        try:
            resp = httpx.get(
                "https://api.hubapi.com/account-info/v3/details",
                headers=self._headers(tokens),
                timeout=15.0,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def fetch_assets(
        self,
        tokens: TokenSet,
        asset_type: str = "contacts",
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Pull assets from HubSpot CRM.

        Args:
            asset_type: "contacts" | "companies" | "deals" | "pipelines"
        """
        base = HUBSPOT_API_BASE
        headers = self._headers(tokens)

        if asset_type == "contacts":
            resp = httpx.get(
                f"{base}/objects/contacts",
                headers=headers,
                params={"limit": 100, "properties": "firstname,lastname,email,phone,company,lifecyclestage,createdate"},
                timeout=30.0,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            return [
                {
                    "id": c.get("id"),
                    "email": c.get("properties", {}).get("email", ""),
                    "first_name": c.get("properties", {}).get("firstname", ""),
                    "last_name": c.get("properties", {}).get("lastname", ""),
                    "phone": c.get("properties", {}).get("phone", ""),
                    "company": c.get("properties", {}).get("company", ""),
                    "lifecycle_stage": c.get("properties", {}).get("lifecyclestage", ""),
                    "created_at": c.get("createdAt", ""),
                }
                for c in results
            ]

        elif asset_type == "companies":
            resp = httpx.get(
                f"{base}/objects/companies",
                headers=headers,
                params={"limit": 100, "properties": "name,domain,industry,city,country,annualrevenue"},
                timeout=30.0,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            return [
                {
                    "id": c.get("id"),
                    "name": c.get("properties", {}).get("name", ""),
                    "domain": c.get("properties", {}).get("domain", ""),
                    "industry": c.get("properties", {}).get("industry", ""),
                    "city": c.get("properties", {}).get("city", ""),
                    "country": c.get("properties", {}).get("country", ""),
                    "annual_revenue": c.get("properties", {}).get("annualrevenue", ""),
                }
                for c in results
            ]

        elif asset_type == "deals":
            resp = httpx.get(
                f"{base}/objects/deals",
                headers=headers,
                params={"limit": 100, "properties": "dealname,amount,dealstage,pipeline,closedate,hubspot_owner_id"},
                timeout=30.0,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            return [
                {
                    "id": d.get("id"),
                    "name": d.get("properties", {}).get("dealname", ""),
                    "amount": float(d.get("properties", {}).get("amount", 0) or 0),
                    "stage": d.get("properties", {}).get("dealstage", ""),
                    "pipeline": d.get("properties", {}).get("pipeline", ""),
                    "close_date": d.get("properties", {}).get("closedate", ""),
                    "owner_id": d.get("properties", {}).get("hubspot_owner_id", ""),
                }
                for d in results
            ]

        elif asset_type == "pipelines":
            resp = httpx.get(
                f"{base}/pipelines/deals",
                headers=headers,
                params={"limit": 50},
                timeout=15.0,
            )
            resp.raise_for_status()
            pipelines = resp.json().get("results", [])
            return [
                {
                    "id": p.get("id"),
                    "label": p.get("label", ""),
                    "stages": [
                        {
                            "id": s.get("id"),
                            "label": s.get("label", ""),
                            "display_order": s.get("displayOrder", 0),
                            "is_closed": s.get("metadata", {}).get("isClosed", False),
                        }
                        for s in p.get("stages", [])
                    ],
                }
                for p in pipelines
            ]

        return []

    def write_back(
        self,
        tokens: TokenSet,
        entity_id: str,
        updates: dict[str, Any],
        **kwargs: Any,
    ) -> bool:
        """Update a CRM entity (contact, deal, company).

        Args:
            entity_id: HubSpot object ID
            updates: Properties to update
            kwargs:
                object_type: "contact" (default) | "deal" | "company"
        """
        object_type = kwargs.get("object_type", "contact")
        base = HUBSPOT_API_BASE

        resp = httpx.patch(
            f"{base}/objects/{object_type}s/{entity_id}",
            headers=self._headers(tokens),
            json={"properties": updates},
            timeout=15.0,
        )
        return resp.status_code == 200

    def fetch_metrics(
        self,
        tokens: TokenSet,
        since: datetime,
        until: datetime | None = None,
        **kwargs: Any,
    ) -> list[MetricEvent]:
        """Pull CRM metrics: deals created, deal revenue, conversion rate."""
        base = HUBSPOT_API_BASE
        headers = self._headers(tokens)

        # Fetch deals created since the given date
        resp = httpx.get(
            f"{base}/objects/deals",
            headers=headers,
            params={
                "limit": 100,
                "properties": "dealname,amount,dealstage,closedate,createdate",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])

        # Aggregate by day
        daily: dict[str, dict[str, float]] = {}
        for deal in results:
            created = deal.get("createdAt", "")
            if not created:
                continue

            try:
                event_time = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                continue

            if event_time < since:
                continue

            date = created[:10]
            if date not in daily:
                daily[date] = {"deals": 0, "revenue": 0, "won": 0, "won_revenue": 0}

            daily[date]["deals"] += 1
            amount = float(deal.get("properties", {}).get("amount", 0) or 0)
            daily[date]["revenue"] += amount

            # Check if deal is won (closed won stage)
            stage = deal.get("properties", {}).get("dealstage", "")
            if "won" in stage.lower() or "closedwon" in stage.lower():
                daily[date]["won"] += 1
                daily[date]["won_revenue"] += amount

        metrics: list[MetricEvent] = []
        for date, data in daily.items():
            try:
                event_time = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            metrics.append(MetricEvent(
                channel="hubspot",
                metric="deals_created",
                value=data["deals"],
                timestamp=event_time,
            ))
            metrics.append(MetricEvent(
                channel="hubspot",
                metric="pipeline_revenue",
                value=data["revenue"],
                timestamp=event_time,
            ))
            metrics.append(MetricEvent(
                channel="hubspot",
                metric="deals_won",
                value=data["won"],
                timestamp=event_time,
            ))
            metrics.append(MetricEvent(
                channel="hubspot",
                metric="won_revenue",
                value=data["won_revenue"],
                timestamp=event_time,
            ))
            win_rate = data["won"] / data["deals"] * 100 if data["deals"] > 0 else 0
            metrics.append(MetricEvent(
                channel="hubspot",
                metric="win_rate",
                value=win_rate,
                timestamp=event_time,
            ))

        return metrics

    # ─── Webhook Support ──────────────────────────────────────────────────

    def supported_webhook_events(self) -> list[str]:
        return HUBSPOT_WEBHOOK_EVENTS

    def register_webhook(
        self,
        tokens: TokenSet,
        event_type: str,
        callback_url: str,
        **kwargs: Any,
    ) -> WebhookSubscription:
        """Register a webhook subscription with HubSpot.

        HubSpot webhooks are managed at the app level, not per-portal.
        The app_id is required.
        """
        app_id = kwargs.get("app_id", "")
        if not app_id:
            raise ValueError("app_id is required for HubSpot webhooks")

        # Parse event type into HubSpot format
        # HubSpot uses: contact.creation, contact.propertyChange, etc.
        resp = httpx.post(
            HUBSPOT_WEBHOOK_API.format(app_id=app_id),
            headers=self._headers(tokens),
            json={
                "event_type": event_type,
                "target_url": callback_url,
                "active": True,
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

        return WebhookSubscription(
            integration="hubspot",
            event_type=event_type,
            callback_url=callback_url,
            native_id=str(data.get("id", "")),
        )

    def list_webhooks(self, tokens: TokenSet, **kwargs: Any) -> list[WebhookSubscription]:
        """List all webhook subscriptions for the app."""
        app_id = kwargs.get("app_id", "")
        if not app_id:
            raise ValueError("app_id is required")

        resp = httpx.get(
            HUBSPOT_WEBHOOK_API.format(app_id=app_id),
            headers=self._headers(tokens),
            timeout=15.0,
        )
        resp.raise_for_status()
        subs = resp.json().get("results", [])

        return [
            WebhookSubscription(
                integration="hubspot",
                event_type=s.get("eventType", ""),
                callback_url=s.get("targetUrl", ""),
                is_active=s.get("active", False),
                native_id=str(s.get("id", "")),
            )
            for s in subs
        ]

    def unregister_webhook(self, tokens: TokenSet, subscription_id: str, **kwargs: Any) -> bool:
        """Remove a webhook subscription."""
        app_id = kwargs.get("app_id", "")
        if not app_id:
            raise ValueError("app_id is required")

        resp = httpx.delete(
            f"{HUBSPOT_WEBHOOK_API.format(app_id=app_id)}/{subscription_id}",
            headers=self._headers(tokens),
            timeout=15.0,
        )
        return resp.status_code == 204

    def parse_webhook(
        self,
        headers: dict[str, str],
        body: dict[str, Any],
        **kwargs: Any,
    ) -> WebhookEvent | None:
        """Parse a HubSpot webhook.

        HubSpot sends webhook events with a specific structure:
        - subscriptionId: the webhook subscription ID
        - eventId: unique event ID
        - eventType: e.g. "contact.creation"
        - objectId: the ID of the affected object
        - propertyName: (for propertyChange events)
        """
        event_type = body.get("eventType", "")
        object_id = str(body.get("objectId", ""))
        subscription_id = body.get("subscriptionId", "")

        # Determine entity type from event type
        entity_type = "unknown"
        if event_type.startswith("contact."):
            entity_type = "contact"
        elif event_type.startswith("deal."):
            entity_type = "deal"
        elif event_type.startswith("company."):
            entity_type = "company"

        return WebhookEvent(
            integration="hubspot",
            event_type=event_type,
            entity_id=object_id,
            entity_type=entity_type,
            payload={
                **body,
                "subscription_id": str(subscription_id),
            },
        )
