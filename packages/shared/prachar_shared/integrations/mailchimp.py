"""Mailchimp Integration — email campaigns, audiences, automation, webhooks.

World-class email marketing integration:
- Authenticate via OAuth 2.0 (Mailchimp)
- Create and send email campaigns
- Manage audiences and segments
- Track opens, clicks, conversions
- Webhook support for campaign events
- Feed Email Campaign Manager with real audience data

API: Mailchimp Marketing API
Docs: https://mailchimp.com/developer/marketing/api/
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

log = logging.getLogger("prachar.integrations.mailchimp")

MAILCHIMP_AUTH_URL = "https://login.mailchimp.com/oauth2/authorize"
MAILCHIMP_TOKEN_URL = "https://login.mailchimp.com/oauth2/token"
MAILCHIMP_METADATA_URL = "https://login.mailchimp.com/oauth2/metadata"
MAILCHIMP_API_BASE = "https://{dc}.api.mailchimp.com/3.0"

MAILCHIMP_SCOPES = [
    "campaigns:read",
    "campaigns:write",
    "lists:read",
    "lists:write",
    "members:read",
    "members:write",
    "reports:read",
    "automations:read",
]

MAILCHIMP_WEBHOOK_EVENTS = [
    "subscribe",
    "unsubscribe",
    "profile",
    "upemail",
    "cleaned",
    "campaign",
    "abuse",
]


@register_integration
class Mailchimp(MarketingIntegration):
    """Mailchimp integration — email campaigns and audience management."""

    integration_name = "mailchimp"
    integration_display_name = "Mailchimp"

    @classmethod
    def info(cls) -> IntegrationInfo:
        return IntegrationInfo(
            name="mailchimp",
            display_name="Mailchimp",
            category="email",
            icon="📧",
            description="Connect Mailchimp to send email campaigns, manage audiences, track opens/clicks/conversions, and set up automations. Webhooks for real-time subscriber events.",
            capabilities=(
                IntegrationCapability.AUTHENTICATE
                | IntegrationCapability.READ_METRICS
                | IntegrationCapability.PUBLISH
                | IntegrationCapability.SYNC_ASSETS
                | IntegrationCapability.WEBHOOKS
                | IntegrationCapability.EMAIL_MARKETING
            ),
            auth_type="oauth",
            scopes=MAILCHIMP_SCOPES,
            docs_url="https://mailchimp.com/developer/marketing/api/",
            setup_guide="1. Register a Mailchimp app at https://mailchimp.com/developer/. 2. Set OAuth redirect URI. 3. Configure scopes. 4. Connect your Mailchimp account.",
        )

    def auth_url(self, client_id: str, redirect_uri: str, state: str) -> str:
        """Generate the Mailchimp OAuth authorization URL."""
        from urllib.parse import urlencode

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }
        return f"{MAILCHIMP_AUTH_URL}?{urlencode(params)}"

    def authenticate(self, **kwargs: Any) -> TokenSet:
        """Exchange OAuth code for an access token.

        Required kwargs:
            code: OAuth authorization code
            client_id: Mailchimp app client ID
            client_secret: Mailchimp app client secret
            redirect_uri: OAuth redirect URI
        """
        code = kwargs.get("code", "")
        client_id = kwargs.get("client_id", "")
        client_secret = kwargs.get("client_secret", "")
        redirect_uri = kwargs.get("redirect_uri", "")

        if not code:
            raise ValueError("OAuth code is required")

        resp = httpx.post(
            MAILCHIMP_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

        access_token = data["access_token"]

        # Get the data center (dc) from metadata
        meta_resp = httpx.get(
            MAILCHIMP_METADATA_URL,
            headers={"Authorization": f"OAuth {access_token}"},
            timeout=15.0,
        )
        meta_resp.raise_for_status()
        meta = meta_resp.json()
        dc = meta.get("dc", "us1")

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600))
        return TokenSet(
            access_token=access_token,
            refresh_token=data.get("refresh_token"),
            expires_at=expires_at,
            scopes=MAILCHIMP_SCOPES + [f"_dc:{dc}"],  # Store dc in scopes for convenience
        )

    def _api_base(self, tokens: TokenSet) -> str:
        """Get the API base URL from the data center."""
        dc = "us1"
        for scope in tokens.scopes:
            if scope.startswith("_dc:"):
                dc = scope.split(":")[1]
                break
        return MAILCHIMP_API_BASE.format(dc=dc)

    def _headers(self, tokens: TokenSet) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {tokens.access_token}",
            "Content-Type": "application/json",
        }

    def test_connection(self, tokens: TokenSet) -> bool:
        """Test if the connection is valid by fetching the root API resource."""
        try:
            resp = httpx.get(
                f"{self._api_base(tokens)}/",
                headers=self._headers(tokens),
                timeout=15.0,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def fetch_assets(
        self,
        tokens: TokenSet,
        asset_type: str = "lists",
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Pull assets from Mailchimp.

        Args:
            asset_type: "lists" | "campaigns" | "templates" | "automations"
        """
        base = self._api_base(tokens)
        headers = self._headers(tokens)

        if asset_type == "lists":
            resp = httpx.get(
                f"{base}/lists",
                headers=headers,
                params={"count": 100, "fields": "lists.id,name,stats.member_count,stats.unsubscribe_count,stats.clean_count"},
                timeout=30.0,
            )
            resp.raise_for_status()
            lists = resp.json().get("lists", [])
            return [
                {
                    "id": lst.get("id"),
                    "name": lst.get("name", ""),
                    "member_count": lst.get("stats", {}).get("member_count", 0),
                    "unsubscribe_count": lst.get("stats", {}).get("unsubscribe_count", 0),
                    "clean_count": lst.get("stats", {}).get("clean_count", 0),
                }
                for lst in lists
            ]

        elif asset_type == "campaigns":
            resp = httpx.get(
                f"{base}/campaigns",
                headers=headers,
                params={"count": 100, "fields": "campaigns.id,title,status,type,emails_sent,send_time,recipients.list_id"},
                timeout=30.0,
            )
            resp.raise_for_status()
            campaigns = resp.json().get("campaigns", [])
            return [
                {
                    "id": c.get("id"),
                    "title": c.get("title", ""),
                    "status": c.get("status", ""),
                    "type": c.get("type", ""),
                    "emails_sent": c.get("emails_sent", 0),
                    "send_time": c.get("send_time", ""),
                    "list_id": c.get("recipients", {}).get("list_id", ""),
                }
                for c in campaigns
            ]

        elif asset_type == "automations":
            resp = httpx.get(
                f"{base}/automations",
                headers=headers,
                params={"count": 50},
                timeout=30.0,
            )
            resp.raise_for_status()
            automations = resp.json().get("automations", [])
            return [
                {
                    "id": a.get("id"),
                    "title": a.get("title", ""),
                    "status": a.get("status", ""),
                    "emails_sent": a.get("emails_sent", 0),
                    "recipients": a.get("recipients", {}).get("count", 0),
                }
                for a in automations
            ]

        elif asset_type == "templates":
            resp = httpx.get(
                f"{base}/templates",
                headers=headers,
                params={"count": 50},
                timeout=30.0,
            )
            resp.raise_for_status()
            templates = resp.json().get("templates", [])
            return [
                {
                    "id": t.get("id"),
                    "name": t.get("name", ""),
                    "type": t.get("type", ""),
                    "category": t.get("category", ""),
                }
                for t in templates
            ]

        return []

    def publish(
        self,
        tokens: TokenSet,
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create and optionally send an email campaign.

        Required payload:
            subject: Email subject line
            list_id: Audience/list ID to send to
            html_content: HTML email body

        Optional payload:
            from_name: From name (defaults to account default)
            reply_to: Reply-to email
            preview_text: Preview/preheader text
            send: If True, send immediately after creation
            schedule_for: ISO datetime to schedule the send
        """
        base = self._api_base(tokens)
        headers = self._headers(tokens)

        # Step 1: Create the campaign
        campaign_data: dict[str, Any] = {
            "type": "regular",
            "recipients": {"list_id": payload.get("list_id", "")},
            "settings": {
                "subject_line": payload.get("subject", ""),
                "preview_text": payload.get("preview_text", ""),
                "from_name": payload.get("from_name", "PRACHAR"),
                "reply_to": payload.get("reply_to", ""),
            },
        }

        resp = httpx.post(
            f"{base}/campaigns",
            headers=headers,
            json=campaign_data,
            timeout=30.0,
        )
        resp.raise_for_status()
        campaign = resp.json()
        campaign_id = campaign.get("id", "")

        if not campaign_id:
            raise ValueError("Failed to create campaign — no ID returned")

        # Step 2: Set the content
        content_data = {
            "html": payload.get("html_content", ""),
        }
        resp = httpx.put(
            f"{base}/campaigns/{campaign_id}/content",
            headers=headers,
            json=content_data,
            timeout=30.0,
        )
        resp.raise_for_status()

        # Step 3: Send or schedule
        if payload.get("send"):
            resp = httpx.post(
                f"{base}/campaigns/{campaign_id}/actions/send",
                headers=headers,
                timeout=15.0,
            )
            resp.raise_for_status()
            status = "sent"
        elif payload.get("schedule_for"):
            resp = httpx.post(
                f"{base}/campaigns/{campaign_id}/actions/schedule",
                headers=headers,
                json={"schedule_time": payload["schedule_for"]},
                timeout=15.0,
            )
            resp.raise_for_status()
            status = "scheduled"
        else:
            status = "draft"

        return {
            "native_id": campaign_id,
            "url": campaign.get("archive_url", ""),
            "published_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "title": campaign.get("settings", {}).get("title", ""),
        }

    def fetch_metrics(
        self,
        tokens: TokenSet,
        since: datetime,
        until: datetime | None = None,
        **kwargs: Any,
    ) -> list[MetricEvent]:
        """Pull email campaign metrics: opens, clicks, bounces, unsubscribes."""
        base = self._api_base(tokens)
        headers = self._headers(tokens)

        # Get campaigns sent since the given date
        resp = httpx.get(
            f"{base}/campaigns",
            headers=headers,
            params={
                "count": 100,
                "since_send_time": since.isoformat(),
                "fields": "campaigns.id,title,emails_sent,send_time,report_summary",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        campaigns = resp.json().get("campaigns", [])

        metrics: list[MetricEvent] = []
        for c in campaigns:
            send_time = c.get("send_time", "")
            if not send_time:
                continue

            try:
                event_time = datetime.fromisoformat(send_time.replace("Z", "+00:00"))
            except ValueError:
                continue

            summary = c.get("report_summary", {})
            campaign_id = c.get("id", "")

            metrics.append(MetricEvent(
                channel="mailchimp",
                metric="emails_sent",
                value=float(c.get("emails_sent", 0)),
                timestamp=event_time,
                metadata={"campaign_id": campaign_id, "title": c.get("title", "")},
            ))
            metrics.append(MetricEvent(
                channel="mailchimp",
                metric="open_rate",
                value=float(summary.get("open_rate", 0)),
                timestamp=event_time,
                metadata={"campaign_id": campaign_id},
            ))
            metrics.append(MetricEvent(
                channel="mailchimp",
                metric="click_rate",
                value=float(summary.get("click_rate", 0)),
                timestamp=event_time,
                metadata={"campaign_id": campaign_id},
            ))
            metrics.append(MetricEvent(
                channel="mailchimp",
                metric="bounce_rate",
                value=float(summary.get("bounce_rate", 0)),
                timestamp=event_time,
                metadata={"campaign_id": campaign_id},
            ))
            metrics.append(MetricEvent(
                channel="mailchimp",
                metric="unsubscribe_count",
                value=float(summary.get("unsubscribe_count", 0)),
                timestamp=event_time,
                metadata={"campaign_id": campaign_id},
            ))

        return metrics

    # ─── Webhook Support ──────────────────────────────────────────────────

    def supported_webhook_events(self) -> list[str]:
        return MAILCHIMP_WEBHOOK_EVENTS

    def register_webhook(
        self,
        tokens: TokenSet,
        event_type: str,
        callback_url: str,
        **kwargs: Any,
    ) -> WebhookSubscription:
        """Register a webhook on a Mailchimp list.

        Mailchimp webhooks are per-list, not per-event. All events for a list
        go to the same URL. The event_type is used for filtering on our side.
        """
        list_id = kwargs.get("list_id", "")
        if not list_id:
            raise ValueError("list_id is required for Mailchimp webhooks")

        base = self._api_base(tokens)
        resp = httpx.post(
            f"{base}/lists/{list_id}/webhooks",
            headers=self._headers(tokens),
            json={
                "url": callback_url,
                "events": {
                    "subscribe": True,
                    "unsubscribe": True,
                    "profile": True,
                    "upemail": True,
                    "cleaned": True,
                    "campaign": True,
                },
                "sources": {"user": True, "admin": True, "api": True},
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

        return WebhookSubscription(
            integration="mailchimp",
            event_type=event_type,
            callback_url=callback_url,
            native_id=str(data.get("id", "")),
        )

    def list_webhooks(self, tokens: TokenSet, **kwargs: Any) -> list[WebhookSubscription]:
        """List all webhooks for a list."""
        list_id = kwargs.get("list_id", "")
        if not list_id:
            raise ValueError("list_id is required")

        base = self._api_base(tokens)
        resp = httpx.get(
            f"{base}/lists/{list_id}/webhooks",
            headers=self._headers(tokens),
            timeout=15.0,
        )
        resp.raise_for_status()
        webhooks = resp.json().get("webhooks", [])

        return [
            WebhookSubscription(
                integration="mailchimp",
                event_type="all",
                callback_url=wh.get("url", ""),
                is_active=True,
                native_id=str(wh.get("id", "")),
            )
            for wh in webhooks
        ]

    def unregister_webhook(self, tokens: TokenSet, subscription_id: str, **kwargs: Any) -> bool:
        """Remove a webhook from a list."""
        list_id = kwargs.get("list_id", "")
        if not list_id:
            raise ValueError("list_id is required")

        base = self._api_base(tokens)
        resp = httpx.delete(
            f"{base}/lists/{list_id}/webhooks/{subscription_id}",
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
        """Parse a Mailchimp webhook.

        Mailchimp webhook events have a 'type' field in the body.
        """
        event_type = body.get("type", "")
        data = body.get("data", {})

        entity_type = "subscriber"
        entity_id = data.get("id", data.get("email", ""))

        if event_type == "campaign":
            entity_type = "campaign"
            entity_id = data.get("id", "")

        return WebhookEvent(
            integration="mailchimp",
            event_type=event_type,
            entity_id=str(entity_id),
            entity_type=entity_type,
            payload=body,
        )
