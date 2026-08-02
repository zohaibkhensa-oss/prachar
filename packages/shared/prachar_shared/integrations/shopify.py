"""Shopify Integration — e-commerce data, product sync, order tracking, webhooks.

World-class e-commerce integration:
- Authenticate via OAuth 2.0 (Shopify App)
- Pull products, collections, inventory, orders, customers
- Track revenue and conversion data
- Webhook support for real-time order/customer events
- Feed CampaignBrain with real product data for campaign generation

API: Shopify Admin REST API + GraphQL
Docs: https://shopify.dev/docs/api/admin-rest
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone
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

log = logging.getLogger("prachar.integrations.shopify")

SHOPIFY_AUTH_URL = "https://{shop}.myshopify.com/admin/oauth/authorize"
SHOPIFY_TOKEN_URL = "https://{shop}.myshopify.com/admin/oauth/access_token"
SHOPIFY_API_BASE = "https://{shop}.myshopify.com/admin/api/2024-01"

SHOPIFY_SCOPES = [
    "read_products",
    "read_orders",
    "read_customers",
    "read_inventory",
    "read_analytics",
    "write_products",
]

# Webhook events Shopify supports
SHOPIFY_WEBHOOK_EVENTS = [
    "orders/create",
    "orders/paid",
    "orders/fulfilled",
    "orders/cancelled",
    "customers/create",
    "customers/update",
    "products/create",
    "products/update",
    "inventory_levels/update",
    "app/uninstalled",
]


@register_integration
class Shopify(MarketingIntegration):
    """Shopify integration — e-commerce data and webhooks."""

    integration_name = "shopify"
    integration_display_name = "Shopify"

    @classmethod
    def info(cls) -> IntegrationInfo:
        return IntegrationInfo(
            name="shopify",
            display_name="Shopify",
            category="ecommerce",
            icon="🛍️",
            description="Connect Shopify to pull products, orders, customers, and revenue data. Generate campaigns from real products. Track sales and calculate ROAS. Webhooks for real-time order events.",
            capabilities=(
                IntegrationCapability.AUTHENTICATE
                | IntegrationCapability.READ_METRICS
                | IntegrationCapability.SYNC_ASSETS
                | IntegrationCapability.ATTRIBUTION
                | IntegrationCapability.WEBHOOKS
                | IntegrationCapability.ECOMMERCE
            ),
            auth_type="oauth",
            scopes=SHOPIFY_SCOPES,
            docs_url="https://shopify.dev/docs/api/admin-rest",
            setup_guide="1. Create a Shopify Partner account. 2. Create a custom app. 3. Set the callback URL. 4. Configure scopes (read_products, read_orders, read_customers). 5. Install the app on your store.",
        )

    def auth_url(self, shop: str, client_id: str, redirect_uri: str, state: str) -> str:
        """Generate the Shopify OAuth authorization URL."""
        from urllib.parse import urlencode

        shop = shop.replace(".myshopify.com", "")
        params = {
            "client_id": client_id,
            "scope": ",".join(SHOPIFY_SCOPES),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }
        return SHOPIFY_AUTH_URL.format(shop=shop) + "?" + urlencode(params)

    def authenticate(self, **kwargs: Any) -> TokenSet:
        """Exchange OAuth code for a permanent access token.

        Required kwargs:
            code: OAuth authorization code
            shop: Shop domain (e.g. "mystore" or "mystore.myshopify.com")
            client_id: Shopify App API key
            client_secret: Shopify App API secret
        """
        code = kwargs.get("code", "")
        shop = kwargs.get("shop", "").replace(".myshopify.com", "")
        client_id = kwargs.get("client_id", "")
        client_secret = kwargs.get("client_secret", "")

        if not code or not shop:
            raise ValueError("code and shop are required for Shopify authentication")

        resp = httpx.post(
            SHOPIFY_TOKEN_URL.format(shop=shop),
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

        # Shopify tokens don't expire (permanent access tokens)
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(days=365 * 10)
        return TokenSet(
            access_token=data["access_token"],
            refresh_token=None,
            expires_at=expires_at,
            scopes=SHOPIFY_SCOPES,
        )

    def _api_base(self, shop: str) -> str:
        shop = shop.replace(".myshopify.com", "")
        return SHOPIFY_API_BASE.format(shop=shop)

    def _headers(self, tokens: TokenSet) -> dict[str, str]:
        return {
            "X-Shopify-Access-Token": tokens.access_token,
            "Content-Type": "application/json",
        }

    def test_connection(self, tokens: TokenSet) -> bool:
        """Test if the connection is valid by fetching the shop info."""
        try:
            shop = getattr(tokens, "_shop", "")
            if not shop:
                return False
            resp = httpx.get(
                f"{self._api_base(shop)}/shop.json",
                headers=self._headers(tokens),
                timeout=15.0,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def fetch_assets(
        self,
        tokens: TokenSet,
        asset_type: str = "products",
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Pull assets from Shopify.

        Args:
            asset_type: "products" | "orders" | "customers" | "collections" | "inventory"
        """
        shop = kwargs.get("shop", getattr(tokens, "_shop", ""))
        if not shop:
            raise ValueError("shop domain is required")

        base = self._api_base(shop)
        headers = self._headers(tokens)

        if asset_type == "products":
            resp = httpx.get(
                f"{base}/products.json",
                headers=headers,
                params={"limit": 250, "fields": "id,title,handle,product_type,vendor,tags,variants,images,status"},
                timeout=30.0,
            )
            resp.raise_for_status()
            products = resp.json().get("products", [])
            return [
                {
                    "id": p.get("id"),
                    "title": p.get("title", ""),
                    "handle": p.get("handle", ""),
                    "product_type": p.get("product_type", ""),
                    "vendor": p.get("vendor", ""),
                    "tags": [t.strip() for t in p.get("tags", "").split(",") if t.strip()],
                    "status": p.get("status", ""),
                    "price": float(p.get("variants", [{}])[0].get("price", 0)) if p.get("variants") else 0,
                    "inventory": sum(int(v.get("inventory_quantity", 0)) for v in p.get("variants", [])),
                    "image_url": p.get("images", [{}])[0].get("src", "") if p.get("images") else "",
                    "url": f"https://{shop}.myshopify.com/products/{p.get('handle', '')}",
                }
                for p in products
            ]

        elif asset_type == "orders":
            resp = httpx.get(
                f"{base}/orders.json",
                headers=headers,
                params={"limit": 250, "status": "any", "fields": "id,name,email,total_price,currency,financial_status,fulfillment_status,created_at,customer,line_items"},
                timeout=30.0,
            )
            resp.raise_for_status()
            orders = resp.json().get("orders", [])
            return [
                {
                    "id": o.get("id"),
                    "order_number": o.get("name", ""),
                    "email": o.get("email", ""),
                    "total": float(o.get("total_price", 0)),
                    "currency": o.get("currency", "USD"),
                    "financial_status": o.get("financial_status", ""),
                    "fulfillment_status": o.get("fulfillment_status", ""),
                    "created_at": o.get("created_at", ""),
                    "customer_name": o.get("customer", {}).get("name", "") if o.get("customer") else "",
                    "item_count": sum(len(li) for li in [o.get("line_items", [])]),
                    "items": [
                        {
                            "title": li.get("title", ""),
                            "quantity": li.get("quantity", 0),
                            "price": float(li.get("price", 0)),
                        }
                        for li in o.get("line_items", [])
                    ],
                }
                for o in orders
            ]

        elif asset_type == "customers":
            resp = httpx.get(
                f"{base}/customers.json",
                headers=headers,
                params={"limit": 250, "fields": "id,email,first_name,last_name,orders_count,total_spent,created_at"},
                timeout=30.0,
            )
            resp.raise_for_status()
            customers = resp.json().get("customers", [])
            return [
                {
                    "id": c.get("id"),
                    "email": c.get("email", ""),
                    "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
                    "orders_count": c.get("orders_count", 0),
                    "total_spent": float(c.get("total_spent", 0)),
                    "created_at": c.get("created_at", ""),
                }
                for c in customers
            ]

        elif asset_type == "collections":
            resp = httpx.get(
                f"{base}/custom_collections.json",
                headers=headers,
                params={"limit": 250},
                timeout=30.0,
            )
            resp.raise_for_status()
            collections = resp.json().get("custom_collections", [])
            return [
                {
                    "id": c.get("id"),
                    "title": c.get("title", ""),
                    "handle": c.get("handle", ""),
                    "products_count": c.get("products_count", 0),
                }
                for c in collections
            ]

        elif asset_type == "inventory":
            resp = httpx.get(
                f"{base}/inventory_levels.json",
                headers=headers,
                params={"limit": 250},
                timeout=30.0,
            )
            resp.raise_for_status()
            levels = resp.json().get("inventory_levels", [])
            return [
                {
                    "inventory_item_id": lv.get("inventory_item_id"),
                    "location_id": lv.get("location_id"),
                    "available": lv.get("available", 0),
                }
                for lv in levels
            ]

        return []

    def fetch_metrics(
        self,
        tokens: TokenSet,
        since: datetime,
        until: datetime | None = None,
        **kwargs: Any,
    ) -> list[MetricEvent]:
        """Pull e-commerce metrics: revenue, orders, AOV, conversion rate."""
        shop = kwargs.get("shop", getattr(tokens, "_shop", ""))
        if not shop:
            raise ValueError("shop domain is required")

        until = until or datetime.now(timezone.utc)
        base = self._api_base(shop)
        headers = self._headers(tokens)

        # Fetch orders in date range
        resp = httpx.get(
            f"{base}/orders.json",
            headers=headers,
            params={
                "limit": 250,
                "status": "any",
                "created_at_min": since.isoformat(),
                "created_at_max": until.isoformat(),
                "fields": "id,total_price,currency,created_at,financial_status",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        orders = resp.json().get("orders", [])

        # Aggregate by day
        daily: dict[str, dict[str, float]] = {}
        for order in orders:
            date = order.get("created_at", "")[:10]
            if date not in daily:
                daily[date] = {"revenue": 0, "orders": 0}
            daily[date]["revenue"] += float(order.get("total_price", 0))
            daily[date]["orders"] += 1

        metrics: list[MetricEvent] = []
        for date, data in daily.items():
            try:
                event_time = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            metrics.append(MetricEvent(
                channel="shopify",
                metric="revenue",
                value=data["revenue"],
                timestamp=event_time,
                metadata={"shop": shop},
            ))
            metrics.append(MetricEvent(
                channel="shopify",
                metric="orders",
                value=data["orders"],
                timestamp=event_time,
                metadata={"shop": shop},
            ))
            aov = data["revenue"] / data["orders"] if data["orders"] > 0 else 0
            metrics.append(MetricEvent(
                channel="shopify",
                metric="average_order_value",
                value=aov,
                timestamp=event_time,
                metadata={"shop": shop},
            ))

        return metrics

    def attribute_conversions(
        self,
        tokens: TokenSet,
        since: datetime,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Attribute Shopify orders to marketing campaigns via UTM/referral data."""
        shop = kwargs.get("shop", getattr(tokens, "_shop", ""))
        if not shop:
            raise ValueError("shop domain is required")

        base = self._api_base(shop)
        headers = self._headers(tokens)

        resp = httpx.get(
            f"{base}/orders.json",
            headers=headers,
            params={
                "limit": 250,
                "status": "any",
                "created_at_min": since.isoformat(),
                "fields": "id,total_price,currency,created_at,customer,referrals,note_attributes",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        orders = resp.json().get("orders", [])

        conversions: list[dict[str, Any]] = []
        for order in orders:
            # Extract UTM/referral data from note_attributes or referrals
            utm_source = ""
            utm_medium = ""
            utm_campaign = ""
            for attr in order.get("note_attributes", []):
                name = attr.get("name", "").lower()
                if name == "utm_source":
                    utm_source = attr.get("value", "")
                elif name == "utm_medium":
                    utm_medium = attr.get("value", "")
                elif name == "utm_campaign":
                    utm_campaign = attr.get("value", "")

            referrals = order.get("referrals", [])
            if referrals and not utm_source:
                utm_source = referrals[0].get("source", "")

            conversions.append({
                "order_id": order.get("id"),
                "revenue": float(order.get("total_price", 0)),
                "currency": order.get("currency", "USD"),
                "created_at": order.get("created_at", ""),
                "utm_source": utm_source,
                "utm_medium": utm_medium,
                "utm_campaign": utm_campaign,
                "customer_email": order.get("customer", {}).get("email", "") if order.get("customer") else "",
            })

        return conversions

    # ─── Webhook Support ──────────────────────────────────────────────────

    def supported_webhook_events(self) -> list[str]:
        return SHOPIFY_WEBHOOK_EVENTS

    def register_webhook(
        self,
        tokens: TokenSet,
        event_type: str,
        callback_url: str,
        **kwargs: Any,
    ) -> WebhookSubscription:
        """Register a webhook subscription with Shopify."""
        shop = kwargs.get("shop", getattr(tokens, "_shop", ""))
        if not shop:
            raise ValueError("shop domain is required")

        base = self._api_base(shop)
        resp = httpx.post(
            f"{base}/webhooks.json",
            headers=self._headers(tokens),
            json={
                "webhook": {
                    "topic": event_type,
                    "address": callback_url,
                    "format": "json",
                }
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json().get("webhook", {})

        return WebhookSubscription(
            integration="shopify",
            event_type=event_type,
            callback_url=callback_url,
            native_id=str(data.get("id", "")),
        )

    def list_webhooks(self, tokens: TokenSet, **kwargs: Any) -> list[WebhookSubscription]:
        """List all webhook subscriptions."""
        shop = kwargs.get("shop", getattr(tokens, "_shop", ""))
        if not shop:
            raise ValueError("shop domain is required")

        base = self._api_base(shop)
        resp = httpx.get(
            f"{base}/webhooks.json",
            headers=self._headers(tokens),
            timeout=15.0,
        )
        resp.raise_for_status()
        webhooks = resp.json().get("webhooks", [])

        return [
            WebhookSubscription(
                integration="shopify",
                event_type=wh.get("topic", ""),
                callback_url=wh.get("address", ""),
                is_active=wh.get("status") == "active",
                native_id=str(wh.get("id", "")),
            )
            for wh in webhooks
        ]

    def unregister_webhook(self, tokens: TokenSet, subscription_id: str, **kwargs: Any) -> bool:
        """Remove a webhook subscription."""
        shop = kwargs.get("shop", getattr(tokens, "_shop", ""))
        if not shop:
            raise ValueError("shop domain is required")

        base = self._api_base(shop)
        resp = httpx.delete(
            f"{base}/webhooks/{subscription_id}.json",
            headers=self._headers(tokens),
            timeout=15.0,
        )
        return resp.status_code == 200

    def parse_webhook(
        self,
        headers: dict[str, str],
        body: dict[str, Any],
        **kwargs: Any,
    ) -> WebhookEvent | None:
        """Parse and verify a Shopify webhook.

        Shopify sends an X-Shopify-Hmac-Sha256 header that is the HMAC-SHA256
        of the raw request body using the app's API secret key.
        """
        api_secret = kwargs.get("api_secret", "")
        raw_body = kwargs.get("raw_body", b"")

        # Verify HMAC signature
        if api_secret and raw_body:
            received_hmac = headers.get("X-Shopify-Hmac-Sha256", "") or headers.get("x-shopify-hmac-sha256", "")
            computed_hmac = hmac.new(
                api_secret.encode(),
                raw_body if isinstance(raw_body, bytes) else raw_body.encode(),
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(received_hmac, computed_hmac):
                log.warning("Shopify webhook HMAC verification failed")
                return None

        topic = headers.get("X-Shopify-Topic", "") or headers.get("x-shopify-topic", "")
        shop = headers.get("X-Shopify-Shop-Domain", "") or headers.get("x-shopify-shop-domain", "")

        # Determine entity type and ID from the topic and body
        event_type = topic
        entity_type = "unknown"
        entity_id = ""

        if topic.startswith("orders/"):
            entity_type = "order"
            entity_id = str(body.get("id", ""))
        elif topic.startswith("customers/"):
            entity_type = "customer"
            entity_id = str(body.get("id", ""))
        elif topic.startswith("products/"):
            entity_type = "product"
            entity_id = str(body.get("id", ""))
        elif topic.startswith("inventory_levels/"):
            entity_type = "inventory_level"
            entity_id = str(body.get("inventory_item_id", ""))
        elif topic == "app/uninstalled":
            entity_type = "app"
            entity_id = shop

        return WebhookEvent(
            integration="shopify",
            event_type=event_type,
            entity_id=entity_id,
            entity_type=entity_type,
            payload={**body, "_shop": shop},
        )
