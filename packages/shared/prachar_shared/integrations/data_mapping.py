"""Data Mapping — semantic mapping between external systems and CURV AI's internal model.

This prevents every module from needing provider-specific logic. Instead of
each engine knowing that HubSpot calls it "lifecyclestage" and Shopify calls
it "tags", they all work with CURV AI's canonical fields.

Example mappings:
    HubSpot "lifecyclestage" → CURV AI "lead_stage"
    Shopify "tags"           → CURV AI "audience_segments"
    GA4 "conversions"        → CURV AI "campaign_kpi.conversions"
    Mailchimp "open_rate"    → CURV AI "email_metrics.open_rate"

Mappings are:
1. Per-integration (each integration maps its fields to canonical fields)
2. Bidirectional (read: external → canonical, write: canonical → external)
3. Transformable (values can be converted, not just renamed)
4. User-overridable (users can add custom mappings)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


# ─── Canonical CURV AI Field Definitions ─────────────────────────────────────

# These are the canonical field names that CURV AI's engines and tools use.
# External systems map their fields to these.

CANONICAL_FIELDS: dict[str, dict[str, str]] = {
    # Lead/Contact fields
    "lead_stage": {
        "description": "Where a lead is in the funnel",
        "values": "lead, mql, sql, opportunity, customer, churned",
    },
    "lead_source": {
        "description": "Where the lead came from",
        "values": "organic, paid, referral, email, social, direct",
    },
    "lead_score": {
        "description": "Quality score 0-100",
        "values": "0-100",
    },

    # Customer/Audience fields
    "audience_segments": {
        "description": "Tags/segments a customer belongs to",
        "values": "list of strings",
    },
    "customer_lifetime_value": {
        "description": "Total revenue from this customer",
        "values": "float",
    },
    "customer_status": {
        "description": "active, inactive, churned",
        "values": "active, inactive, churned",
    },

    # E-commerce fields
    "order_value": {
        "description": "Total order value",
        "values": "float",
    },
    "order_status": {
        "description": "pending, paid, fulfilled, cancelled, refunded",
        "values": "pending, paid, fulfilled, cancelled, refunded",
    },
    "product_category": {
        "description": "Product category/type",
        "values": "string",
    },
    "product_price": {
        "description": "Product price",
        "values": "float",
    },
    "inventory_count": {
        "description": "Available inventory",
        "values": "int",
    },

    # Campaign/KPI fields
    "campaign_kpi.conversions": {
        "description": "Number of conversions",
        "values": "int",
    },
    "campaign_kpi.revenue": {
        "description": "Revenue attributed to campaign",
        "values": "float",
    },
    "campaign_kpi.roas": {
        "description": "Return on ad spend",
        "values": "float",
    },
    "campaign_kpi.cpa": {
        "description": "Cost per acquisition",
        "values": "float",
    },
    "campaign_kpi.ctr": {
        "description": "Click-through rate",
        "values": "float (0-1)",
    },

    # Email marketing fields
    "email_metrics.open_rate": {
        "description": "Email open rate",
        "values": "float (0-1)",
    },
    "email_metrics.click_rate": {
        "description": "Email click rate",
        "values": "float (0-1)",
    },
    "email_metrics.bounce_rate": {
        "description": "Email bounce rate",
        "values": "float (0-1)",
    },
    "email_metrics.unsubscribe_count": {
        "description": "Number of unsubscribes",
        "values": "int",
    },

    # Content/CMS fields
    "content.title": {
        "description": "Page or post title",
        "values": "string",
    },
    "content.slug": {
        "description": "URL slug",
        "values": "string",
    },
    "content.seo_title": {
        "description": "SEO meta title",
        "values": "string",
    },
    "content.seo_description": {
        "description": "SEO meta description",
        "values": "string",
    },
    "content.status": {
        "description": "draft, published, scheduled",
        "values": "draft, published, scheduled",
    },

    # Analytics fields
    "analytics.sessions": {
        "description": "Number of sessions",
        "values": "int",
    },
    "analytics.users": {
        "description": "Number of unique users",
        "values": "int",
    },
    "analytics.pageviews": {
        "description": "Number of page views",
        "values": "int",
    },
    "analytics.engagement_rate": {
        "description": "Engagement rate",
        "values": "float (0-1)",
    },
}


# ─── Field Mapping ──────────────────────────────────────────────────────────


# Type for transform functions: external_value -> canonical_value
TransformFn = Callable[[Any], Any]


@dataclass
class FieldMapping:
    """A single field mapping from an external field to a canonical field.

    Attributes:
        external_field: The field name in the external system (e.g. "lifecyclestage")
        canonical_field: The CURV AI canonical field name (e.g. "lead_stage")
        transform: Optional function to transform the value
        reverse_transform: Optional function for write-back (canonical → external)
        default: Default value if external field is missing
    """
    external_field: str
    canonical_field: str
    transform: TransformFn | None = None
    reverse_transform: TransformFn | None = None
    default: Any = None

    def to_canonical(self, external_value: Any) -> Any:
        """Convert an external value to the canonical format."""
        if external_value is None:
            return self.default
        if self.transform:
            return self.transform(external_value)
        return external_value

    def to_external(self, canonical_value: Any) -> Any:
        """Convert a canonical value to the external format (for write-back)."""
        if self.reverse_transform:
            return self.reverse_transform(canonical_value)
        return canonical_value


@dataclass
class DataMapping:
    """A collection of field mappings for a specific integration.

    Each integration defines its own DataMapping that translates between
    its field names and CURV AI's canonical fields. Users can override
    or add custom mappings.
    """
    integration: str
    mappings: dict[str, FieldMapping] = field(default_factory=dict)
    # Custom mappings added by the user (overrides defaults)
    custom_mappings: dict[str, FieldMapping] = field(default_factory=dict)

    def add(self, mapping: FieldMapping) -> None:
        """Add a field mapping."""
        self.mappings[mapping.external_field] = mapping

    def add_custom(self, mapping: FieldMapping) -> None:
        """Add a custom user mapping (overrides defaults)."""
        self.custom_mappings[mapping.external_field] = mapping

    def get_mapping(self, external_field: str) -> FieldMapping | None:
        """Get the mapping for an external field (custom takes priority)."""
        if external_field in self.custom_mappings:
            return self.custom_mappings[external_field]
        return self.mappings.get(external_field)

    def to_canonical(self, external_data: dict[str, Any]) -> dict[str, Any]:
        """Convert a dict of external data to canonical CURV AI format.

        Example:
            mapping.to_canonical({"lifecyclestage": "subscriber"})
            → {"lead_stage": "lead"}
        """
        result: dict[str, Any] = {}
        for ext_field, value in external_data.items():
            mapping = self.get_mapping(ext_field)
            if mapping:
                result[mapping.canonical_field] = mapping.to_canonical(value)
            else:
                # Pass through unmapped fields with a prefix
                result[f"_raw.{ext_field}"] = value
        return result

    def to_external(self, canonical_data: dict[str, Any]) -> dict[str, Any]:
        """Convert canonical CURV AI data to external format (for write-back).

        Example:
            mapping.to_external({"lead_stage": "customer"})
            → {"lifecyclestage": "customer"}
        """
        # Build reverse lookup: canonical_field → external_field
        reverse: dict[str, FieldMapping] = {}
        for mapping in {**self.mappings, **self.custom_mappings}.values():
            reverse[mapping.canonical_field] = mapping

        result: dict[str, Any] = {}
        for can_field, value in canonical_data.items():
            mapping = reverse.get(can_field)
            if mapping:
                result[mapping.external_field] = mapping.to_external(value)
            else:
                result[can_field] = value
        return result

    def list_mappings(self) -> list[dict[str, Any]]:
        """List all mappings for display in the UI."""
        all_mappings = {**self.mappings, **self.custom_mappings}
        return [
            {
                "external_field": m.external_field,
                "canonical_field": m.canonical_field,
                "has_transform": m.transform is not None,
                "is_custom": m.external_field in self.custom_mappings,
                "default": m.default,
            }
            for m in all_mappings.values()
        ]


# ─── Default Mappings Per Integration ───────────────────────────────────────


def _hubspot_lifecycle_to_lead_stage(v: str) -> str:
    """Map HubSpot lifecycle stages to CURV AI lead stages."""
    mapping = {
        "subscriber": "lead",
        "lead": "lead",
        "mql": "mql",
        "sql": "sql",
        "opportunity": "opportunity",
        "customer": "customer",
        "evangelist": "customer",
        "other": "lead",
    }
    return mapping.get(str(v).lower(), "lead")


def _shopify_tags_to_segments(v: str | list) -> list[str]:
    """Convert Shopify tags (comma-separated string or list) to segment list."""
    if isinstance(v, list):
        return [t.strip() for t in v if t.strip()]
    if isinstance(v, str):
        return [t.strip() for t in v.split(",") if t.strip()]
    return []


def _shopify_financial_to_order_status(v: str) -> str:
    """Map Shopify financial status to canonical order status."""
    mapping = {
        "pending": "pending",
        "authorized": "pending",
        "partially_paid": "pending",
        "paid": "paid",
        "partially_refunded": "paid",
        "refunded": "refunded",
        "voided": "cancelled",
    }
    return mapping.get(str(v).lower(), "pending")


def _ga4_metric_passthrough(v: Any) -> float:
    """GA4 metrics are already numeric, just ensure float."""
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def _mailchimp_rate_to_float(v: Any) -> float:
    """Mailchimp rates are already 0-1 floats, but ensure it."""
    try:
        val = float(v)
        # Mailchimp reports rates as 0-1, but sometimes as percentages
        if val > 1:
            return val / 100.0
        return val
    except (ValueError, TypeError):
        return 0.0


def _wordpress_status_to_canonical(v: str) -> str:
    """Map WordPress post status to canonical content status."""
    mapping = {
        "publish": "published",
        "draft": "draft",
        "pending": "draft",
        "private": "published",
        "future": "scheduled",
        "trash": "draft",
    }
    return mapping.get(str(v).lower(), "draft")


# ─── Default Data Mappings ──────────────────────────────────────────────────


def _default_hubspot_mapping() -> DataMapping:
    m = DataMapping(integration="hubspot")
    m.add(FieldMapping("lifecyclestage", "lead_stage", transform=_hubspot_lifecycle_to_lead_stage))
    m.add(FieldMapping("email", "contact.email", default=""))
    m.add(FieldMapping("firstname", "contact.first_name", default=""))
    m.add(FieldMapping("lastname", "contact.last_name", default=""))
    m.add(FieldMapping("company", "contact.company", default=""))
    m.add(FieldMapping("dealname", "deal.name", default=""))
    m.add(FieldMapping("amount", "deal.value", transform=lambda v: float(v or 0)))
    m.add(FieldMapping("dealstage", "deal.stage", default=""))
    m.add(FieldMapping("createdate", "contact.created_at", default=""))
    return m


def _default_shopify_mapping() -> DataMapping:
    m = DataMapping(integration="shopify")
    m.add(FieldMapping("tags", "audience_segments", transform=_shopify_tags_to_segments))
    m.add(FieldMapping("financial_status", "order_status", transform=_shopify_financial_to_order_status))
    m.add(FieldMapping("total_price", "order_value", transform=lambda v: float(v or 0)))
    m.add(FieldMapping("product_type", "product_category", default=""))
    m.add(FieldMapping("price", "product_price", transform=lambda v: float(v or 0)))
    m.add(FieldMapping("inventory_quantity", "inventory_count", transform=lambda v: int(v or 0)))
    m.add(FieldMapping("email", "contact.email", default=""))
    m.add(FieldMapping("name", "contact.name", default=""))
    m.add(FieldMapping("orders_count", "customer_order_count", transform=lambda v: int(v or 0)))
    m.add(FieldMapping("total_spent", "customer_lifetime_value", transform=lambda v: float(v or 0)))
    return m


def _default_ga4_mapping() -> DataMapping:
    m = DataMapping(integration="google_analytics")
    m.add(FieldMapping("sessions", "analytics.sessions", transform=_ga4_metric_passthrough))
    m.add(FieldMapping("totalUsers", "analytics.users", transform=_ga4_metric_passthrough))
    m.add(FieldMapping("screenPageViews", "analytics.pageviews", transform=_ga4_metric_passthrough))
    m.add(FieldMapping("engagementRate", "analytics.engagement_rate", transform=_ga4_metric_passthrough))
    m.add(FieldMapping("conversions", "campaign_kpi.conversions", transform=_ga4_metric_passthrough))
    m.add(FieldMapping("totalRevenue", "campaign_kpi.revenue", transform=_ga4_metric_passthrough))
    return m


def _default_mailchimp_mapping() -> DataMapping:
    m = DataMapping(integration="mailchimp")
    m.add(FieldMapping("open_rate", "email_metrics.open_rate", transform=_mailchimp_rate_to_float))
    m.add(FieldMapping("click_rate", "email_metrics.click_rate", transform=_mailchimp_rate_to_float))
    m.add(FieldMapping("bounce_rate", "email_metrics.bounce_rate", transform=_mailchimp_rate_to_float))
    m.add(FieldMapping("unsubscribe_count", "email_metrics.unsubscribe_count", transform=lambda v: int(v or 0)))
    m.add(FieldMapping("emails_sent", "email_metrics.emails_sent", transform=lambda v: int(v or 0)))
    m.add(FieldMapping("title", "campaign.name", default=""))
    m.add(FieldMapping("status", "campaign.status", default=""))
    return m


def _default_wordpress_mapping() -> DataMapping:
    m = DataMapping(integration="wordpress")
    m.add(FieldMapping("title", "content.title", default=""))
    m.add(FieldMapping("slug", "content.slug", default=""))
    m.add(FieldMapping("status", "content.status", transform=_wordpress_status_to_canonical))
    m.add(FieldMapping("yoast_head_json.title", "content.seo_title", default=""))
    m.add(FieldMapping("yoast_head_json.description", "content.seo_description", default=""))
    return m


# ─── Mapping Registry ───────────────────────────────────────────────────────


class DataMappingRegistry:
    """Registry of data mappings per integration.

    Provides default mappings and allows user overrides.
    """

    def __init__(self) -> None:
        self._defaults: dict[str, DataMapping] = {}
        self._user_overrides: dict[str, dict[str, DataMapping]] = {}  # tenant_id → {integration → mapping}

    def register_default(self, integration: str, mapping: DataMapping) -> None:
        """Register a default mapping for an integration."""
        self._defaults[integration] = mapping

    def get_default(self, integration: str) -> DataMapping | None:
        """Get the default mapping for an integration."""
        return self._defaults.get(integration)

    def get(self, integration: str, tenant_id: str | None = None) -> DataMapping | None:
        """Get the mapping for an integration, with optional tenant overrides."""
        if tenant_id and tenant_id in self._user_overrides:
            if integration in self._user_overrides[tenant_id]:
                return self._user_overrides[tenant_id][integration]
        return self._defaults.get(integration)

    def set_user_override(self, tenant_id: str, integration: str, mapping: DataMapping) -> None:
        """Set a user-specific mapping override."""
        if tenant_id not in self._user_overrides:
            self._user_overrides[tenant_id] = {}
        self._user_overrides[tenant_id][integration] = mapping

    def all_defaults(self) -> dict[str, DataMapping]:
        """Return all default mappings."""
        return dict(self._defaults)


# Singleton with pre-registered defaults
_mapping_registry = DataMappingRegistry()
_mapping_registry.register_default("hubspot", _default_hubspot_mapping())
_mapping_registry.register_default("shopify", _default_shopify_mapping())
_mapping_registry.register_default("google_analytics", _default_ga4_mapping())
_mapping_registry.register_default("mailchimp", _default_mailchimp_mapping())
_mapping_registry.register_default("wordpress", _default_wordpress_mapping())


def get_mapping_registry() -> DataMappingRegistry:
    """Get the global data mapping registry."""
    return _mapping_registry
