"""Tests for Sprint 2 integrations — Shopify, Mailchimp, HubSpot, event bus, webhooks."""
from __future__ import annotations

import asyncio
import pytest
from datetime import datetime, timedelta, timezone

from prachar_shared.integrations import (
    IntegrationCapability,
    IntegrationEventBus,
    WebhookEvent,
    WebhookSubscription,
    get_event_bus,
    get_integration_registry,
)
from prachar_shared.integrations.shopify import Shopify, SHOPIFY_WEBHOOK_EVENTS
from prachar_shared.integrations.mailchimp import Mailchimp, MAILCHIMP_WEBHOOK_EVENTS
from prachar_shared.integrations.hubspot import HubSpot, HUBSPOT_WEBHOOK_EVENTS
# Also import Sprint 1 integrations so they register
from prachar_shared.integrations.google_analytics import GoogleAnalytics4  # noqa: F401
from prachar_shared.integrations.wordpress import WordPress  # noqa: F401


# ─── Capability Discovery Tests ────────────────────────────────────────────


class TestCapabilityDiscovery:
    """Test the capabilities() and supports() methods."""

    def test_shopify_capabilities(self):
        s = Shopify()
        caps = s.capabilities()
        assert caps["read_metrics"] is True
        assert caps["sync_assets"] is True
        assert caps["attribution"] is True
        assert caps["webhooks"] is True
        assert caps["ecommerce"] is True
        assert caps["publish"] is False
        assert caps["crm"] is False
        assert caps["email_marketing"] is False

    def test_mailchimp_capabilities(self):
        m = Mailchimp()
        caps = m.capabilities()
        assert caps["publish"] is True
        assert caps["read_metrics"] is True
        assert caps["sync_assets"] is True
        assert caps["webhooks"] is True
        assert caps["email_marketing"] is True
        assert caps["ecommerce"] is False
        assert caps["crm"] is False
        assert caps["attribution"] is False

    def test_hubspot_capabilities(self):
        h = HubSpot()
        caps = h.capabilities()
        assert caps["read_metrics"] is True
        assert caps["sync_assets"] is True
        assert caps["write_back"] is True
        assert caps["webhooks"] is True
        assert caps["crm"] is True
        assert caps["publish"] is False
        assert caps["ecommerce"] is False
        assert caps["email_marketing"] is False

    def test_supports_method(self):
        s = Shopify()
        assert s.supports(IntegrationCapability.ECOMMERCE) is True
        assert s.supports(IntegrationCapability.WEBHOOKS) is True
        assert s.supports(IntegrationCapability.CRM) is False
        assert s.supports(IntegrationCapability.EMAIL_MARKETING) is False

    def test_planner_can_discover_without_hardcoding(self):
        """The Planner can ask 'who supports ecommerce?' without knowing provider names."""
        registry = get_integration_registry()
        ecommerce_integrations = [
            name for name, cls in registry._integrations.items()
            if cls.info().capabilities & IntegrationCapability.ECOMMERCE
        ]
        assert "shopify" in ecommerce_integrations
        assert "hubspot" not in ecommerce_integrations

        crm_integrations = [
            name for name, cls in registry._integrations.items()
            if cls.info().capabilities & IntegrationCapability.CRM
        ]
        assert "hubspot" in crm_integrations
        assert "shopify" not in crm_integrations

        email_integrations = [
            name for name, cls in registry._integrations.items()
            if cls.info().capabilities & IntegrationCapability.EMAIL_MARKETING
        ]
        assert "mailchimp" in email_integrations
        assert "shopify" not in email_integrations


# ─── Shopify Adapter Tests ─────────────────────────────────────────────────


class TestShopify:
    """Shopify integration adapter."""

    def test_info(self):
        info = Shopify.info()
        assert info.name == "shopify"
        assert info.display_name == "Shopify"
        assert info.category == "ecommerce"
        assert info.auth_type == "oauth"
        assert IntegrationCapability.ECOMMERCE in info.capabilities
        assert IntegrationCapability.WEBHOOKS in info.capabilities

    def test_auth_url(self):
        s = Shopify()
        url = s.auth_url(
            shop="mystore",
            client_id="test_id",
            redirect_uri="http://localhost:3000/callback",
            state="abc123",
        )
        assert "mystore.myshopify.com" in url
        assert "test_id" in url
        assert "abc123" in url
        assert "read_products" in url

    def test_authenticate_requires_code(self):
        s = Shopify()
        with pytest.raises(ValueError, match="code and shop are required"):
            s.authenticate(code="", shop="mystore")

    def test_authenticate_requires_shop(self):
        s = Shopify()
        with pytest.raises(ValueError, match="code and shop are required"):
            s.authenticate(code="abc", shop="")

    def test_fetch_assets_requires_shop(self):
        s = Shopify()
        from prachar_shared.contracts import TokenSet
        tokens = TokenSet(
            access_token="fake",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        with pytest.raises(ValueError, match="shop domain is required"):
            s.fetch_assets(tokens, asset_type="products")

    def test_fetch_metrics_requires_shop(self):
        s = Shopify()
        from prachar_shared.contracts import TokenSet
        tokens = TokenSet(
            access_token="fake",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        with pytest.raises(ValueError, match="shop domain is required"):
            s.fetch_metrics(tokens, since=datetime.now(timezone.utc))

    def test_unsupported_methods_raise(self):
        s = Shopify()
        from prachar_shared.contracts import TokenSet
        tokens = TokenSet(
            access_token="fake",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        with pytest.raises(NotImplementedError, match="does not support PUBLISH"):
            s.publish(tokens, payload={})
        with pytest.raises(NotImplementedError, match="does not support MANAGE_MEDIA"):
            s.manage_media(tokens, action="list")
        with pytest.raises(NotImplementedError, match="does not support SEO_MANAGEMENT"):
            s.update_seo(tokens, page_id="1", seo_data={})

    def test_supported_webhook_events(self):
        s = Shopify()
        events = s.supported_webhook_events()
        assert "orders/create" in events
        assert "orders/paid" in events
        assert "customers/create" in events
        assert "products/create" in events
        assert len(events) == len(SHOPIFY_WEBHOOK_EVENTS)

    def test_register_webhook_requires_shop(self):
        s = Shopify()
        from prachar_shared.contracts import TokenSet
        tokens = TokenSet(
            access_token="fake",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        with pytest.raises(ValueError, match="shop domain is required"):
            s.register_webhook(tokens, event_type="orders/create", callback_url="https://example.com/hook")

    def test_parse_webhook_order_created(self):
        s = Shopify()
        event = s.parse_webhook(
            headers={"x-shopify-topic": "orders/create", "x-shopify-shop-domain": "mystore.myshopify.com"},
            body={"id": 12345, "total_price": "99.00", "email": "customer@example.com"},
        )
        assert event is not None
        assert event.integration == "shopify"
        assert event.event_type == "orders/create"
        assert event.entity_id == "12345"
        assert event.entity_type == "order"
        assert event.payload["total_price"] == "99.00"

    def test_parse_webhook_customer_created(self):
        s = Shopify()
        event = s.parse_webhook(
            headers={"x-shopify-topic": "customers/create", "x-shopify-shop-domain": "mystore.myshopify.com"},
            body={"id": 67890, "email": "new@example.com"},
        )
        assert event is not None
        assert event.entity_type == "customer"
        assert event.entity_id == "67890"

    def test_parse_webhook_product_updated(self):
        s = Shopify()
        event = s.parse_webhook(
            headers={"x-shopify-topic": "products/update", "x-shopify-shop-domain": "mystore.myshopify.com"},
            body={"id": 11111, "title": "Updated Product"},
        )
        assert event is not None
        assert event.entity_type == "product"

    def test_parse_webhook_invalid_hmac_returns_none(self):
        s = Shopify()
        event = s.parse_webhook(
            headers={"x-shopify-topic": "orders/create", "x-shopify-hmac-sha256": "wrong_signature"},
            body={"id": 12345},
            api_secret="secret",
            raw_body=b'{"id": 12345}',
        )
        assert event is None


# ─── Mailchimp Adapter Tests ───────────────────────────────────────────────


class TestMailchimp:
    """Mailchimp integration adapter."""

    def test_info(self):
        info = Mailchimp.info()
        assert info.name == "mailchimp"
        assert info.display_name == "Mailchimp"
        assert info.category == "email"
        assert IntegrationCapability.PUBLISH in info.capabilities
        assert IntegrationCapability.EMAIL_MARKETING in info.capabilities
        assert IntegrationCapability.WEBHOOKS in info.capabilities

    def test_auth_url(self):
        m = Mailchimp()
        url = m.auth_url(
            client_id="test_id",
            redirect_uri="http://localhost:3000/callback",
            state="abc123",
        )
        assert "login.mailchimp.com" in url
        assert "test_id" in url
        assert "abc123" in url

    def test_authenticate_requires_code(self):
        m = Mailchimp()
        with pytest.raises(ValueError, match="OAuth code is required"):
            m.authenticate(code="")

    def test_unsupported_methods_raise(self):
        m = Mailchimp()
        from prachar_shared.contracts import TokenSet
        tokens = TokenSet(
            access_token="fake",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scopes=["_dc:us1"],
        )
        with pytest.raises(NotImplementedError, match="does not support WRITE_BACK"):
            m.write_back(tokens, entity_id="1", updates={})
        with pytest.raises(NotImplementedError, match="does not support ATTRIBUTION"):
            m.attribute_conversions(tokens, since=datetime.now(timezone.utc))
        with pytest.raises(NotImplementedError, match="does not support MANAGE_MEDIA"):
            m.manage_media(tokens, action="list")
        with pytest.raises(NotImplementedError, match="does not support SEO_MANAGEMENT"):
            m.update_seo(tokens, page_id="1", seo_data={})

    def test_supported_webhook_events(self):
        m = Mailchimp()
        events = m.supported_webhook_events()
        assert "subscribe" in events
        assert "unsubscribe" in events
        assert "campaign" in events
        assert len(events) == len(MAILCHIMP_WEBHOOK_EVENTS)

    def test_register_webhook_requires_list_id(self):
        m = Mailchimp()
        from prachar_shared.contracts import TokenSet
        tokens = TokenSet(
            access_token="fake",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        with pytest.raises(ValueError, match="list_id is required"):
            m.register_webhook(tokens, event_type="subscribe", callback_url="https://example.com/hook")

    def test_parse_webhook_subscribe(self):
        m = Mailchimp()
        event = m.parse_webhook(
            headers={},
            body={
                "type": "subscribe",
                "data": {"id": "abc123", "email": "new@example.com", "list_id": "list1"},
            },
        )
        assert event is not None
        assert event.integration == "mailchimp"
        assert event.event_type == "subscribe"
        assert event.entity_id == "abc123"
        assert event.entity_type == "subscriber"

    def test_parse_webhook_campaign_event(self):
        m = Mailchimp()
        event = m.parse_webhook(
            headers={},
            body={
                "type": "campaign",
                "data": {"id": "camp1", "subject": "Summer Sale"},
            },
        )
        assert event is not None
        assert event.event_type == "campaign"
        assert event.entity_type == "campaign"
        assert event.entity_id == "camp1"


# ─── HubSpot Adapter Tests ─────────────────────────────────────────────────


class TestHubSpot:
    """HubSpot integration adapter."""

    def test_info(self):
        info = HubSpot.info()
        assert info.name == "hubspot"
        assert info.display_name == "HubSpot"
        assert info.category == "crm"
        assert IntegrationCapability.CRM in info.capabilities
        assert IntegrationCapability.WRITE_BACK in info.capabilities
        assert IntegrationCapability.WEBHOOKS in info.capabilities

    def test_auth_url(self):
        h = HubSpot()
        url = h.auth_url(
            client_id="test_id",
            redirect_uri="http://localhost:3000/callback",
            state="abc123",
        )
        assert "app.hubspot.com" in url
        assert "test_id" in url
        assert "abc123" in url

    def test_authenticate_requires_code(self):
        h = HubSpot()
        with pytest.raises(ValueError, match="OAuth code is required"):
            h.authenticate(code="")

    def test_unsupported_methods_raise(self):
        h = HubSpot()
        from prachar_shared.contracts import TokenSet
        tokens = TokenSet(
            access_token="fake",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        with pytest.raises(NotImplementedError, match="does not support PUBLISH"):
            h.publish(tokens, payload={})
        with pytest.raises(NotImplementedError, match="does not support ATTRIBUTION"):
            h.attribute_conversions(tokens, since=datetime.now(timezone.utc))
        with pytest.raises(NotImplementedError, match="does not support MANAGE_MEDIA"):
            h.manage_media(tokens, action="list")
        with pytest.raises(NotImplementedError, match="does not support SEO_MANAGEMENT"):
            h.update_seo(tokens, page_id="1", seo_data={})

    def test_supported_webhook_events(self):
        h = HubSpot()
        events = h.supported_webhook_events()
        assert "contact.creation" in events
        assert "deal.creation" in events
        assert "deal.propertyChange" in events
        assert len(events) == len(HUBSPOT_WEBHOOK_EVENTS)

    def test_register_webhook_requires_app_id(self):
        h = HubSpot()
        from prachar_shared.contracts import TokenSet
        tokens = TokenSet(
            access_token="fake",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        with pytest.raises(ValueError, match="app_id is required"):
            h.register_webhook(tokens, event_type="contact.creation", callback_url="https://example.com/hook")

    def test_parse_webhook_contact_creation(self):
        h = HubSpot()
        event = h.parse_webhook(
            headers={},
            body={
                "eventType": "contact.creation",
                "objectId": 12345,
                "subscriptionId": 99,
            },
        )
        assert event is not None
        assert event.integration == "hubspot"
        assert event.event_type == "contact.creation"
        assert event.entity_id == "12345"
        assert event.entity_type == "contact"

    def test_parse_webhook_deal_property_change(self):
        h = HubSpot()
        event = h.parse_webhook(
            headers={},
            body={
                "eventType": "deal.propertyChange",
                "objectId": 67890,
                "propertyName": "dealstage",
                "propertyValue": "closedwon",
            },
        )
        assert event is not None
        assert event.entity_type == "deal"
        assert event.entity_id == "67890"
        assert event.payload["propertyName"] == "dealstage"


# ─── Event Bus Tests ───────────────────────────────────────────────────────


class TestEventBus:
    """Integration event bus for webhook events."""

    def test_register_and_publish(self):
        bus = IntegrationEventBus()
        received: list[WebhookEvent] = []

        @bus.on("shopify", "orders/create")
        async def handler(event: WebhookEvent):
            received.append(event)

        event = WebhookEvent(
            integration="shopify",
            event_type="orders/create",
            entity_id="123",
            entity_type="order",
        )
        asyncio.run(bus.publish(event))
        assert len(received) == 1
        assert received[0].entity_id == "123"

    def test_wildcard_integration(self):
        bus = IntegrationEventBus()
        received: list[WebhookEvent] = []

        @bus.on("*", "orders/create")
        async def handler(event: WebhookEvent):
            received.append(event)

        event = WebhookEvent(
            integration="shopify",
            event_type="orders/create",
            entity_id="123",
            entity_type="order",
        )
        asyncio.run(bus.publish(event))
        assert len(received) == 1

    def test_wildcard_event_type(self):
        bus = IntegrationEventBus()
        received: list[WebhookEvent] = []

        @bus.on("shopify", "*")
        async def handler(event: WebhookEvent):
            received.append(event)

        event1 = WebhookEvent("shopify", "orders/create", "1", "order")
        event2 = WebhookEvent("shopify", "customers/create", "2", "customer")
        asyncio.run(bus.publish(event1))
        asyncio.run(bus.publish(event2))
        assert len(received) == 2

    def test_global_wildcard(self):
        bus = IntegrationEventBus()
        received: list[WebhookEvent] = []

        @bus.on("*", "*")
        async def handler(event: WebhookEvent):
            received.append(event)

        asyncio.run(bus.publish(WebhookEvent("shopify", "orders/create", "1", "order")))
        asyncio.run(bus.publish(WebhookEvent("hubspot", "deal.creation", "2", "deal")))
        asyncio.run(bus.publish(WebhookEvent("mailchimp", "subscribe", "3", "subscriber")))
        assert len(received) == 3

    def test_multiple_handlers_same_event(self):
        bus = IntegrationEventBus()
        results_a: list[str] = []
        results_b: list[str] = []

        @bus.on("shopify", "orders/create")
        async def handler_a(event: WebhookEvent):
            results_a.append(event.entity_id)

        @bus.on("shopify", "orders/create")
        async def handler_b(event: WebhookEvent):
            results_b.append(event.entity_id)

        asyncio.run(bus.publish(WebhookEvent("shopify", "orders/create", "999", "order")))
        assert results_a == ["999"]
        assert results_b == ["999"]

    def test_handler_error_isolation(self):
        """An error in one handler doesn't affect others."""
        bus = IntegrationEventBus()
        received: list[str] = []

        @bus.on("shopify", "orders/create")
        async def failing_handler(event: WebhookEvent):
            raise ValueError("Handler failed")

        @bus.on("shopify", "orders/create")
        async def good_handler(event: WebhookEvent):
            received.append(event.entity_id)

        asyncio.run(bus.publish(WebhookEvent("shopify", "orders/create", "42", "order")))
        assert received == ["42"]  # Good handler still ran

    def test_no_handlers_returns_empty(self):
        bus = IntegrationEventBus()
        event = WebhookEvent("unknown", "unknown", "1", "test")
        results = asyncio.run(bus.publish(event))
        assert results == []

    def test_stats(self):
        bus = IntegrationEventBus()

        @bus.on("shopify", "orders/create")
        async def handler(event: WebhookEvent):
            pass

        asyncio.run(bus.publish(WebhookEvent("shopify", "orders/create", "1", "order")))
        stats = bus.stats()
        assert stats["registered_handlers"] == 1
        assert stats["event_counts"]["shopify"] == 1

    def test_off_removes_handler(self):
        bus = IntegrationEventBus()
        received: list[WebhookEvent] = []

        @bus.on("shopify", "orders/create")
        async def handler(event: WebhookEvent):
            received.append(event)

        asyncio.run(bus.publish(WebhookEvent("shopify", "orders/create", "1", "order")))
        assert len(received) == 1

        bus.off("shopify", "orders/create", handler)
        asyncio.run(bus.publish(WebhookEvent("shopify", "orders/create", "2", "order")))
        assert len(received) == 1  # No new events received

    def test_clear(self):
        bus = IntegrationEventBus()

        @bus.on("*", "*")
        async def handler(event: WebhookEvent):
            pass

        asyncio.run(bus.publish(WebhookEvent("shopify", "orders/create", "1", "order")))
        bus.clear()
        stats = bus.stats()
        assert stats["registered_handlers"] == 0
        assert stats["event_counts"] == {}


# ─── Registry Tests ────────────────────────────────────────────────────────


class TestSprint2Registry:
    """All Sprint 2 integrations are registered."""

    def test_all_five_integrations_registered(self):
        registry = get_integration_registry()
        available = registry.available()
        assert "google_analytics" in available
        assert "wordpress" in available
        assert "shopify" in available
        assert "mailchimp" in available
        assert "hubspot" in available

    def test_all_integration_info(self):
        registry = get_integration_registry()
        all_info = registry.all_integrations()
        assert all_info["shopify"].category == "ecommerce"
        assert all_info["mailchimp"].category == "email"
        assert all_info["hubspot"].category == "crm"
        assert all_info["google_analytics"].category == "analytics"
        assert all_info["wordpress"].category == "cms"

    def test_categories_are_diverse(self):
        """We have integrations across 5 different categories."""
        registry = get_integration_registry()
        all_info = registry.all_integrations()
        categories = {info.category for info in all_info.values()}
        assert "analytics" in categories
        assert "cms" in categories
        assert "ecommerce" in categories
        assert "email" in categories
        assert "crm" in categories
