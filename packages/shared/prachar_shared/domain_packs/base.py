"""Domain Pack Architecture — base contracts and registry.

A Domain Pack is a plug-in that defines the domain-specific behaviour for a
customer segment (Business, Creator, Restaurant, Clinic, etc.). The universal
pipeline (consult → campaign → presentation) never changes; only the Domain
Pack changes.

Adding a new domain:
  1. Create a folder under domain_packs/<domain>/
  2. Implement a DomainPack subclass
  3. Register it in domain_packs/__init__.py

Zero core modifications. No router changes, no dashboard changes, no pipeline
changes.

The contract is intentionally minimal — it captures ONLY what the audit found
to be domain-specific. Nothing more.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


# ─── Specs (small data classes describing domain-specific UI/data) ─────────


@dataclass(frozen=True)
class SubtypePreset:
    """A selectable subtype within a domain (e.g. Restaurant, Clinic, Retail)."""

    id: str                   # "restaurant", "clinic", "youtube_creator"
    label: str                # "Restaurant", "YouTube Creator"
    emoji: str                # "🍽️", "📹"
    blurb: str                # short description shown in onboarding
    category: str = ""        # maps to Brand.category (e.g. "restaurant", "youtube")


@dataclass(frozen=True)
class KpiCardSpec:
    """A KPI card on the dashboard. The shell renders it; the pack defines it."""

    key: str                  # "subscribers", "views", "customers", "revenue"
    label: str                # "Subscribers", "Views", "Customers"
    icon: str = "Users"       # lucide icon name (frontend maps to component)
    hint: str = ""            # "Connect YouTube to see" etc.


@dataclass(frozen=True)
class ActionCardSpec:
    """A quick-action card on the dashboard."""

    title: str
    description: str
    href: str                 # frontend route
    icon: str = "Zap"         # lucide icon name
    accent: str = "accent"    # "accent" | "info" | "success" | "warning"


@dataclass(frozen=True)
class WidgetSpec:
    """A domain-specific dashboard widget slot.

    The dashboard shell renders known widget kinds. The pack declares which
    widgets appear and in what order.
    """

    kind: str                 # "kpi_grid" | "quick_actions" | "trending" | "pipeline" | "promotions" | "appointments"
    title: str = ""
    props: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NavItemSpec:
    """A sidebar navigation item."""

    label: str
    path: str
    icon: str = "LayoutDashboard"  # lucide icon name


@dataclass(frozen=True)
class NavSectionSpec:
    """A sidebar navigation section."""

    section: str
    items: list[NavItemSpec] = field(default_factory=list)


@dataclass(frozen=True)
class ToolSpec:
    """A domain-specific tool (e.g. creator's Repurpose, YouTube Plan).

    Tools are invoked via the unified /consult/tool/{tool_id} endpoint.
    The pack supplies the prompt template; the engine handles the LLM call,
    JSON extraction, and response shaping.
    """

    id: str                   # "repurpose", "youtube_plan"
    label: str                # "Repurpose a video"
    description: str
    input_schema: dict[str, Any]   # JSON schema for the tool's input
    output_schema: dict[str, Any]  # JSON schema for the tool's output
    prompt_template: str      # prompt with {placeholders}
    task_name: str            # AIGateway task name, e.g. "creator_repurpose"
    prompt_version: str       # e.g. "creator_repurpose_v1.0"
    max_tokens: int = 2500
    temperature: float = 0.7
    tier: str = "medium"      # "small" | "medium" | "large"


# ─── The Domain Pack contract ──────────────────────────────────────────────


@runtime_checkable
class DomainPack(Protocol):
    """The contract every domain pack must implement.

    A pack defines ONLY domain-specific behaviour:
      - Discovery (subtypes, extraction schema)
      - Goals (default goal, goal options)
      - KPIs (dashboard KPI card specs)
      - Growth Opportunities (prompt fragment)
      - Planning (week schema, prompt fragment)
      - Campaign Templates (template name, prompt fragment, creative directions prompt, hooks prompt, audience psychology prompt, offers prompt, pricing psychology prompt, seasonal prompt, local prompt, differentiation prompt)
      - Recommendations (prompt fragment)
      - Dashboard Cards (widget specs)
      - Memory Extensions (brand_graph schema, memory namespace)
      - Conversation Behaviour (role, jargon, greeting)
      - Sidebar (nav sections)
      - Domain-specific tools (optional)

    A pack does NOT define:
      - Its own router
      - Its own persistence logic
      - Its own UI components
      - Its own orchestration pipeline
      - Its own audit logging
      - Its own auth
    """

    # ─── Identity ───
    id: str                          # "business", "creator", "restaurant", "clinic"
    label: str                       # "Business Growth", "Creator Growth"
    customer_type: str               # "business" | "creator" (maps to Brand.customer_type)
    emoji: str

    # ─── Discovery ───
    subtypes: list[SubtypePreset]
    extraction_schema: dict[str, Any]      # JSON schema for entity extraction
    extraction_prompt: str                 # domain-specific extraction prompt fragment

    # ─── Goals ───
    default_goal: str
    goal_options: list[str]

    # ─── KPIs ───
    kpi_cards: list[KpiCardSpec]

    # ─── Growth Opportunities ───
    opportunity_prompt: str                # domain-specific opportunity prompt fragment

    # ─── Planning ───
    week_schema: dict[str, Any]            # JSON schema for a week of the 30-day plan
    week_prompt: str                       # domain-specific week plan prompt fragment

    # ─── Campaign Templates ───
    campaign_template: str                 # "Promotion Campaign" | "Content Campaign"
    campaign_prompt: str                   # domain-specific campaign prompt fragment
    creative_directions_prompt: str        # domain-specific prompt fragment shaping 3 creative directions
    hooks_prompt: str                      # domain-specific prompt fragment shaping 5 hook patterns
    audience_psychology_prompt: str        # domain-specific prompt fragment shaping audience psychology
    offers_prompt: str                     # domain-specific prompt fragment shaping 3 engineered offers
    pricing_psychology_prompt: str         # domain-specific prompt fragment shaping 3 pricing presentations
    seasonal_prompt: str                   # domain-specific prompt fragment shaping seasonal marketing ideas
    local_prompt: str                      # domain-specific prompt fragment shaping local marketing ideas ("" for creators)
    differentiation_prompt: str            # domain-specific prompt fragment shaping competitor differentiation
    strategy_prompt: str                   # domain-specific prompt fragment shaping multi-strategy generation (primary/alternative/contrarian)

    # ─── Recommendations ───
    recommendations_prompt: str

    # ─── Dashboard ───
    dashboard_widgets: list[WidgetSpec]
    quick_actions: list[ActionCardSpec]

    # ─── Memory ───
    brand_graph_schema: dict[str, Any]     # schema for domain-specific brand_graph fields
    memory_namespace: str                  # "business" | "creator.youtube" etc.

    # ─── Conversation ───
    conversation_role: str                 # "marketing strategist" | "creator strategist"
    forbidden_jargon: list[str]
    greeting_template: str                 # CURV AI's opening message template

    # ─── Sidebar ───
    nav_sections: list[NavSectionSpec]

    # ─── Tools (optional) ───
    tools: list[ToolSpec]


# ─── Base implementation (helpers for pack authors) ────────────────────────


class BaseDomainPack:
    """Base class with sensible defaults. Pack authors override what they need.

    This is a concrete class (not a Protocol) so packs can inherit from it and
    only override the fields that matter. The Protocol above is the contract;
    this base class is the convenience.
    """

    id: str = ""
    label: str = ""
    customer_type: str = "business"
    emoji: str = "🏢"

    subtypes: list[SubtypePreset] = []
    extraction_schema: dict[str, Any] = {}
    extraction_prompt: str = ""

    default_goal: str = "grow"
    goal_options: list[str] = ["grow"]

    kpi_cards: list[KpiCardSpec] = []
    opportunity_prompt: str = ""

    week_schema: dict[str, Any] = {}
    week_prompt: str = ""

    campaign_template: str = "Campaign"
    campaign_prompt: str = ""
    creative_directions_prompt: str = ""
    hooks_prompt: str = ""
    audience_psychology_prompt: str = ""
    offers_prompt: str = ""
    pricing_psychology_prompt: str = ""
    seasonal_prompt: str = ""
    local_prompt: str = ""
    differentiation_prompt: str = ""
    strategy_prompt: str = ""

    recommendations_prompt: str = ""

    dashboard_widgets: list[WidgetSpec] = []
    quick_actions: list[ActionCardSpec] = []

    brand_graph_schema: dict[str, Any] = {}
    memory_namespace: str = "business"

    conversation_role: str = "marketing strategist"
    forbidden_jargon: list[str] = ["ROAS", "CPA", "CTR", "funnel", "TOFU"]
    greeting_template: str = (
        "Hey! I'm CURV AI — your {role}. Tell me about your {subject}. "
        "What do you do, where, and who do you serve? The more you share, "
        "the better I can help."
    )

    nav_sections: list[NavSectionSpec] = []
    tools: list[ToolSpec] = []

    def greeting(self, subtype_label: str = "") -> str:
        """Render the greeting message for a given subtype."""
        subject = subtype_label.lower() if subtype_label else "business"
        return self.greeting_template.format(role=self.conversation_role, subject=subject)

    def map_subtype_to_category(self, subtype_id: str) -> str:
        """Map a subtype id to a Brand.category value."""
        for st in self.subtypes:
            if st.id == subtype_id:
                return st.category or st.id
        return subtype_id

    def get_tool(self, tool_id: str) -> ToolSpec | None:
        """Look up a tool by id."""
        for t in self.tools:
            if t.id == tool_id:
                return t
        return None


# ─── Registry ──────────────────────────────────────────────────────────────


class DomainPackRegistry:
    """Registry of available domain packs. Singleton."""

    _instance: "DomainPackRegistry | None" = None

    def __init__(self) -> None:
        self._packs: dict[str, DomainPack] = {}

    @classmethod
    def instance(cls) -> "DomainPackRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, pack: DomainPack) -> None:
        if not pack.id:
            raise ValueError("DomainPack.id is required")
        self._packs[pack.id] = pack

    def get(self, pack_id: str) -> DomainPack | None:
        return self._packs.get(pack_id)

    def get_required(self, pack_id: str) -> DomainPack:
        pack = self._packs.get(pack_id)
        if pack is None:
            raise KeyError(f"Unknown domain pack: {pack_id!r}. Available: {list(self._packs)}")
        return pack

    def all(self) -> list[DomainPack]:
        return list(self._packs.values())

    def ids(self) -> list[str]:
        return list(self._packs.keys())

    def clear(self) -> None:
        """Clear all registered packs (for tests)."""
        self._packs.clear()


def get_registry() -> DomainPackRegistry:
    """Get the singleton registry."""
    return DomainPackRegistry.instance()


def register_all() -> None:
    """Register all built-in domain packs. Called at app startup."""
    from .business.pack import BusinessPack
    from .creator.pack import CreatorPack
    from .restaurant.pack import RestaurantPack
    from .clinic.pack import ClinicPack

    reg = get_registry()
    reg.clear()
    reg.register(BusinessPack())
    reg.register(CreatorPack())
    reg.register(RestaurantPack())
    reg.register(ClinicPack())
