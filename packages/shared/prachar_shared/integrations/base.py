"""Marketing Integration — common interface for all platform integrations.

This is the unified abstraction that ALL integrations implement:
- Ad networks (Google Ads, Meta Ads, LinkedIn Ads)
- Organic channels (Instagram, YouTube, WordPress)
- Analytics (GA4, Search Console)
- E-commerce (Shopify, WooCommerce)
- CRM (HubSpot, Salesforce)
- Email (Mailchimp, Brevo)

The Planner and Runtime interact with this single abstraction rather than
provider-specific code. Each adapter implements only the methods it supports.

Capabilities declare what an integration can do:
- READ_METRICS: pull performance data
- PUBLISH: push content/posts
- SYNC_ASSETS: pull products/contacts/pages
- WRITE_BACK: update CRM/pipeline
- ATTRIBUTION: attribute conversions to campaigns
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Flag, auto
from typing import Any

from ..contracts import MetricEvent, TokenSet


# ─── Capabilities ───────────────────────────────────────────────────────────


class IntegrationCapability(Flag):
    """What an integration can do. Adapters declare their capabilities."""

    NONE = 0
    AUTHENTICATE = auto()       # OAuth or API key auth
    READ_METRICS = auto()       # Pull performance/analytics data
    PUBLISH = auto()            # Push content (posts, pages, emails)
    SYNC_ASSETS = auto()        # Pull assets (products, contacts, pages)
    WRITE_BACK = auto()         # Update external system (CRM pipeline, tags)
    ATTRIBUTION = auto()        # Attribute conversions to campaigns
    MANAGE_MEDIA = auto()       # Upload/manage media files
    SEO_MANAGEMENT = auto()     # Update SEO metadata (title, meta, schema)
    WEBHOOKS = auto()           # Supports webhook event notifications
    REALTIME = auto()           # Supports real-time data queries
    ECOMMERCE = auto()          # E-commerce data (products, orders, revenue)
    CRM = auto()                # CRM data (contacts, deals, pipeline)
    EMAIL_MARKETING = auto()    # Email marketing (campaigns, lists, automation)


# ─── Integration Status ─────────────────────────────────────────────────────


class IntegrationStatus(str):
    """Connection status for an integration."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    EXPIRED = "expired"       # token expired, needs reconnect
    PENDING = "pending"       # OAuth flow in progress


# ─── Integration Metadata ───────────────────────────────────────────────────


@dataclass
class IntegrationInfo:
    """Static metadata about an integration (doesn't change per-connection)."""

    name: str                           # "google_analytics", "wordpress", "shopify"
    display_name: str                   # "Google Analytics 4"
    category: str                       # "analytics", "cms", "ecommerce", "crm", "email", "ads"
    icon: str = ""                      # emoji or icon name
    description: str = ""
    capabilities: IntegrationCapability = IntegrationCapability.NONE
    auth_type: str = "oauth"            # "oauth" | "api_key" | "app_password"
    scopes: list[str] = field(default_factory=list)
    docs_url: str = ""
    setup_guide: str = ""


@dataclass
class IntegrationHealth:
    """Health status for a connected integration."""

    name: str
    status: str = IntegrationStatus.CONNECTED
    last_sync: datetime | None = None
    last_error: str = ""
    capabilities: IntegrationCapability = IntegrationCapability.NONE
    permission_scopes: list[str] = field(default_factory=list)
    sync_count: int = 0
    error_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "last_error": self.last_error,
            "capabilities": [c.name for c in IntegrationCapability if c != IntegrationCapability.NONE and self.capabilities & c],
            "permission_scopes": self.permission_scopes,
            "sync_count": self.sync_count,
            "error_count": self.error_count,
        }


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    synced_count: int = 0
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookEvent:
    """A webhook event received from an external platform.

    Webhooks allow real-time reaction to external events instead of polling.
    Examples: Shopify order_created, WordPress post_published, HubSpot deal_won,
    Mailchimp campaign_sent, GA4 conversion_event.
    """
    integration: str               # "shopify", "wordpress", "hubspot"
    event_type: str                # "order_created", "post_published", "deal_won"
    entity_id: str                 # ID of the entity in the external system
    entity_type: str               # "order", "post", "deal", "campaign"
    payload: dict[str, Any] = field(default_factory=dict)
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "integration": self.integration,
            "event_type": self.event_type,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "payload": self.payload,
            "received_at": self.received_at.isoformat(),
        }


@dataclass
class WebhookSubscription:
    """A webhook subscription registered with an external platform."""
    integration: str
    event_type: str
    callback_url: str
    is_active: bool = True
    native_id: str = ""            # ID returned by the platform for this subscription


# ─── Base Interface ─────────────────────────────────────────────────────────


class MarketingIntegration(ABC):
    """Common interface for all platform integrations.

    Every integration (GA4, WordPress, Shopify, HubSpot, Mailchimp, etc.)
    implements this interface. The Planner discovers capabilities via
    `info()` and calls only the methods the integration supports.

    Adapters implement only the methods they support — unsupported methods
    raise NotImplementedError by default.
    """

    # Subclasses must set these
    integration_name: str = ""
    integration_display_name: str = ""

    @classmethod
    @abstractmethod
    def info(cls) -> IntegrationInfo:
        """Return static metadata about this integration."""
        ...

    @abstractmethod
    def authenticate(self, **kwargs: Any) -> TokenSet:
        """Authenticate with the platform (OAuth code exchange or API key validation).

        Args:
            **kwargs: OAuth code, API key, or other credentials depending on auth_type.

        Returns:
            TokenSet with access token and scopes.
        """
        ...

    @abstractmethod
    def test_connection(self, tokens: TokenSet) -> bool:
        """Test if the connection is valid. Returns True if healthy."""
        ...

    def capabilities(self) -> dict[str, bool]:
        """Return a human-readable capability map for the Planner.

        The Planner uses this to decide which integration to use for a task
        without hard-coded provider knowledge.

        Example:
            {
                "publish": True,
                "read_metrics": True,
                "sync_assets": True,
                "write_back": False,
                "attribution": True,
                "manage_media": False,
                "seo_management": False,
                "webhooks": True,
                "realtime": True,
                "ecommerce": False,
                "crm": False,
                "email_marketing": False,
            }
        """
        caps = self.info().capabilities
        return {
            "publish": bool(caps & IntegrationCapability.PUBLISH),
            "read_metrics": bool(caps & IntegrationCapability.READ_METRICS),
            "sync_assets": bool(caps & IntegrationCapability.SYNC_ASSETS),
            "write_back": bool(caps & IntegrationCapability.WRITE_BACK),
            "attribution": bool(caps & IntegrationCapability.ATTRIBUTION),
            "manage_media": bool(caps & IntegrationCapability.MANAGE_MEDIA),
            "seo_management": bool(caps & IntegrationCapability.SEO_MANAGEMENT),
            "webhooks": bool(caps & IntegrationCapability.WEBHOOKS),
            "realtime": bool(caps & IntegrationCapability.REALTIME),
            "ecommerce": bool(caps & IntegrationCapability.ECOMMERCE),
            "crm": bool(caps & IntegrationCapability.CRM),
            "email_marketing": bool(caps & IntegrationCapability.EMAIL_MARKETING),
        }

    def supports(self, capability: IntegrationCapability) -> bool:
        """Check if this integration supports a specific capability."""
        return bool(self.info().capabilities & capability)

    def fetch_metrics(
        self,
        tokens: TokenSet,
        since: datetime,
        until: datetime | None = None,
        **kwargs: Any,
    ) -> list[MetricEvent]:
        """Pull performance metrics since the given timestamp."""
        raise NotImplementedError(f"{self.integration_name} does not support READ_METRICS")

    def fetch_realtime(
        self,
        tokens: TokenSet,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Pull real-time data (active users, live conversions)."""
        raise NotImplementedError(f"{self.integration_name} does not support realtime metrics")

    def fetch_assets(
        self,
        tokens: TokenSet,
        asset_type: str = "all",
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Pull assets (products, contacts, pages, lists) from the platform."""
        raise NotImplementedError(f"{self.integration_name} does not support SYNC_ASSETS")

    def publish(
        self,
        tokens: TokenSet,
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Publish content (post, page, email, campaign) to the platform.

        Returns:
            dict with native_id, url, and published_at.
        """
        raise NotImplementedError(f"{self.integration_name} does not support PUBLISH")

    def write_back(
        self,
        tokens: TokenSet,
        entity_id: str,
        updates: dict[str, Any],
        **kwargs: Any,
    ) -> bool:
        """Write data back to the external system (update CRM contact, add tag, etc.)."""
        raise NotImplementedError(f"{self.integration_name} does not support WRITE_BACK")

    def attribute_conversions(
        self,
        tokens: TokenSet,
        since: datetime,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Attribute conversions to campaigns/channels.

        Returns list of conversion events with attribution data.
        """
        raise NotImplementedError(f"{self.integration_name} does not support ATTRIBUTION")

    def manage_media(
        self,
        tokens: TokenSet,
        action: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Upload, list, or delete media files.

        Args:
            action: "upload" | "list" | "delete"
        """
        raise NotImplementedError(f"{self.integration_name} does not support MANAGE_MEDIA")

    def update_seo(
        self,
        tokens: TokenSet,
        page_id: str,
        seo_data: dict[str, Any],
        **kwargs: Any,
    ) -> bool:
        """Update SEO metadata for a page (title, meta description, schema)."""
        raise NotImplementedError(f"{self.integration_name} does not support SEO_MANAGEMENT")

    def sync(self, tokens: TokenSet, **kwargs: Any) -> SyncResult:
        """Full sync — pull all data from the platform.

        Override in subclasses for custom sync logic.
        Default implementation calls fetch_metrics and fetch_assets.
        """
        start = datetime.now(timezone.utc)
        errors: list[str] = []
        synced = 0

        info = self.info()
        if info.capabilities & IntegrationCapability.READ_METRICS:
            try:
                metrics = self.fetch_metrics(tokens, since=datetime.min.replace(tzinfo=timezone.utc))
                synced += len(metrics)
            except Exception as e:
                errors.append(f"metrics: {e}")

        if info.capabilities & IntegrationCapability.SYNC_ASSETS:
            try:
                assets = self.fetch_assets(tokens)
                synced += len(assets)
            except Exception as e:
                errors.append(f"assets: {e}")

        duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        return SyncResult(
            success=len(errors) == 0,
            synced_count=synced,
            errors=errors,
            duration_ms=duration,
        )

    def health(self, tokens: TokenSet) -> IntegrationHealth:
        """Check the health of this integration connection."""
        info = self.info()
        try:
            connected = self.test_connection(tokens)
            return IntegrationHealth(
                name=self.integration_name,
                status=IntegrationStatus.CONNECTED if connected else IntegrationStatus.ERROR,
                capabilities=info.capabilities,
                permission_scopes=tokens.scopes,
            )
        except Exception as e:
            return IntegrationHealth(
                name=self.integration_name,
                status=IntegrationStatus.ERROR,
                last_error=str(e),
                capabilities=info.capabilities,
            )

    # ─── Webhook Support ──────────────────────────────────────────────────

    def register_webhook(
        self,
        tokens: TokenSet,
        event_type: str,
        callback_url: str,
        **kwargs: Any,
    ) -> WebhookSubscription:
        """Register a webhook subscription with the external platform.

        The platform will send HTTP POST requests to callback_url when
        events of the given type occur.

        Args:
            event_type: Platform-specific event (e.g. "orders/create",
                        "post_published", "deal.won")
            callback_url: The URL the platform should POST to.

        Returns:
            WebhookSubscription with the native subscription ID.
        """
        raise NotImplementedError(f"{self.integration_name} does not support WEBHOOKS")

    def list_webhooks(self, tokens: TokenSet) -> list[WebhookSubscription]:
        """List all webhook subscriptions registered with the platform."""
        raise NotImplementedError(f"{self.integration_name} does not support WEBHOOKS")

    def unregister_webhook(self, tokens: TokenSet, subscription_id: str) -> bool:
        """Remove a webhook subscription from the platform."""
        raise NotImplementedError(f"{self.integration_name} does not support WEBHOOKS")

    def parse_webhook(
        self,
        headers: dict[str, str],
        body: dict[str, Any],
        **kwargs: Any,
    ) -> WebhookEvent | None:
        """Parse and verify an incoming webhook from the platform.

        This method:
        1. Verifies the webhook signature (HMAC, etc.)
        2. Extracts the event type, entity ID, and payload
        3. Returns a normalised WebhookEvent

        Returns None if the webhook is invalid or cannot be parsed.
        """
        raise NotImplementedError(f"{self.integration_name} does not support WEBHOOKS")

    def supported_webhook_events(self) -> list[str]:
        """Return the list of webhook event types this integration supports.

        Override in subclasses to list platform-specific events.
        """
        return []


# ─── Integration Registry ───────────────────────────────────────────────────


class IntegrationRegistry:
    """Registry of all available integrations.

    Integrations register themselves at import time. The Integration Centre
    discovers them via this registry.
    """

    def __init__(self) -> None:
        self._integrations: dict[str, type[MarketingIntegration]] = {}

    def register(self, cls: type[MarketingIntegration]) -> type[MarketingIntegration]:
        """Register an integration class. Used as decorator."""
        name = cls.integration_name
        if not name:
            raise ValueError(f"{cls.__name__} must set integration_name")
        self._integrations[name] = cls
        return cls

    def get(self, name: str) -> type[MarketingIntegration] | None:
        return self._integrations.get(name)

    def all_integrations(self) -> dict[str, IntegrationInfo]:
        """Return info for all registered integrations."""
        return {name: cls.info() for name, cls in self._integrations.items()}

    def available(self) -> list[str]:
        """Return names of all registered integrations."""
        return list(self._integrations.keys())


# Singleton
_registry = IntegrationRegistry()


def get_integration_registry() -> IntegrationRegistry:
    return _registry


def register_integration(cls: type[MarketingIntegration]) -> type[MarketingIntegration]:
    """Decorator to register an integration."""
    return _registry.register(cls)
