"""Memory Categories — categorised memory store for the Runtime.

Instead of a single generic memory blob, the Runtime keeps 7 distinct memory
classes so the Planner can provide only the relevant context to each tool.

Constitution Rule 10: The Runtime owns memory. Tools declare which categories
they need via ``ToolManifest.memory_categories``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MemoryCategory(str, Enum):
    """The 7 memory classes.

    Each tool declares which categories it needs. An empty list means
    "all categories" (backward compatible).
    """

    BRAND = "brand"                    # brand identity, voice, positioning, industry, history
    CAMPAIGN = "campaign"              # past campaigns, what worked/failed, campaign patterns
    AUDIENCE = "audience"              # audience profiles, demographics, behaviours, preferences
    CREATIVE = "creative"              # best-performing creatives, style preferences, brand guidelines
    PERFORMANCE = "performance"        # historical KPIs, benchmarks, trends, ROI data
    WORKSPACE = "workspace"            # user actions, decisions, approvals, timeline events
    USER_PREFERENCES = "user_preferences"  # communication style, approval thresholds, notification prefs


# All categories as a tuple (used for "all categories" semantics)
ALL_CATEGORIES: tuple[MemoryCategory, ...] = tuple(MemoryCategory)


@dataclass
class MemoryEntry:
    """A single piece of memory, belonging to one category."""

    category: MemoryCategory
    content: str
    confidence: float = 0.5
    source: str = "system"           # "learning_engine", "user", "campaign", etc.
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Serialise for the Decision Contract context_snapshot."""
        return {
            "category": self.category.value,
            "content": self.content,
            "confidence": self.confidence,
            "source": self.source,
            "created_at": self.created_at,
        }


@dataclass
class MemoryStore:
    """Categorised memory store — holds memories split across 7 classes.

    The Planner and tools request only the categories they need via
    :meth:`get_for_categories`. An empty ``categories`` list returns every
    category (backward compatible with tools that don't declare categories).
    """

    brand: list[MemoryEntry] = field(default_factory=list)
    campaign: list[MemoryEntry] = field(default_factory=list)
    audience: list[MemoryEntry] = field(default_factory=list)
    creative: list[MemoryEntry] = field(default_factory=list)
    performance: list[MemoryEntry] = field(default_factory=list)
    workspace: list[MemoryEntry] = field(default_factory=list)
    user_preferences: list[MemoryEntry] = field(default_factory=list)

    # Legacy scalar metadata (not category-specific) — kept for backward compat
    total_campaigns: int = 0
    average_roi: str = "—"

    # ─── Category access ────────────────────────────────────────────────────

    def _list_for(self, category: MemoryCategory) -> list[MemoryEntry]:
        """Return the list backing a single category."""
        return {
            MemoryCategory.BRAND: self.brand,
            MemoryCategory.CAMPAIGN: self.campaign,
            MemoryCategory.AUDIENCE: self.audience,
            MemoryCategory.CREATIVE: self.creative,
            MemoryCategory.PERFORMANCE: self.performance,
            MemoryCategory.WORKSPACE: self.workspace,
            MemoryCategory.USER_PREFERENCES: self.user_preferences,
        }[category]

    def get_for_categories(self, categories: list[MemoryCategory]) -> list[MemoryEntry]:
        """Return only memories from the specified categories.

        An empty ``categories`` list means "all categories" (backward compatible).
        """
        if not categories:
            return self.all()
        result: list[MemoryEntry] = []
        for cat in categories:
            result.extend(self._list_for(cat))
        return result

    def all(self) -> list[MemoryEntry]:
        """Return every memory entry across all categories."""
        return (
            self.brand
            + self.campaign
            + self.audience
            + self.creative
            + self.performance
            + self.workspace
            + self.user_preferences
        )

    def counts_by_category(self) -> dict[str, int]:
        """Return a mapping of category name → entry count (for summaries)."""
        return {
            MemoryCategory.BRAND.value: len(self.brand),
            MemoryCategory.CAMPAIGN.value: len(self.campaign),
            MemoryCategory.AUDIENCE.value: len(self.audience),
            MemoryCategory.CREATIVE.value: len(self.creative),
            MemoryCategory.PERFORMANCE.value: len(self.performance),
            MemoryCategory.WORKSPACE.value: len(self.workspace),
            MemoryCategory.USER_PREFERENCES.value: len(self.user_preferences),
        }

    # ─── Serialisation ──────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialise for the Decision Contract context_snapshot."""
        return {
            "brand": [e.to_dict() for e in self.brand],
            "campaign": [e.to_dict() for e in self.campaign],
            "audience": [e.to_dict() for e in self.audience],
            "creative": [e.to_dict() for e in self.creative],
            "performance": [e.to_dict() for e in self.performance],
            "workspace": [e.to_dict() for e in self.workspace],
            "user_preferences": [e.to_dict() for e in self.user_preferences],
            "total_campaigns": self.total_campaigns,
            "average_roi": self.average_roi,
        }

    # ─── Backward compatibility with MemoryInfo ─────────────────────────────
    #
    # The legacy ``MemoryInfo`` dataclass exposed flat lists (best_practices,
    # audience_insights, creative_insights, channel_insights) plus scalar
    # metadata. These properties let existing tools/planner code keep working
    # while the new categorised store is the primary structure.

    @property
    def best_practices(self) -> list[str]:
        """Campaign best-practice learnings (legacy flat list)."""
        return [e.content for e in self.campaign if e.source == "best_practice"]

    @property
    def audience_insights(self) -> list[str]:
        """Audience insights (legacy flat list)."""
        return [e.content for e in self.audience]

    @property
    def creative_insights(self) -> list[str]:
        """Creative insights (legacy flat list)."""
        return [e.content for e in self.creative]

    @property
    def channel_insights(self) -> list[str]:
        """Channel/performance insights (legacy flat list)."""
        return [e.content for e in self.performance]

    @property
    def raw(self) -> dict[str, Any]:
        """Best-effort legacy ``raw`` dict (for tools that read it)."""
        return self.to_dict()

    # ─── Construction helpers ───────────────────────────────────────────────

    @classmethod
    def from_memory_info(cls, info: Any) -> MemoryStore:
        """Build a :class:`MemoryStore` from a legacy ``MemoryInfo`` instance.

        Maps the old flat fields to the new categories:
          - best_practices  → CAMPAIGN
          - audience_insights → AUDIENCE
          - creative_insights → CREATIVE
          - channel_insights  → PERFORMANCE
        Scalar metadata (total_campaigns, average_roi) is preserved.
        """
        store = cls(
            total_campaigns=getattr(info, "total_campaigns", 0),
            average_roi=getattr(info, "average_roi", "—"),
        )
        for bp in getattr(info, "best_practices", []) or []:
            store.campaign.append(MemoryEntry(
                category=MemoryCategory.CAMPAIGN,
                content=bp,
                source="best_practice",
            ))
        for ai in getattr(info, "audience_insights", []) or []:
            store.audience.append(MemoryEntry(
                category=MemoryCategory.AUDIENCE,
                content=ai,
                source="learning_engine",
            ))
        for ci in getattr(info, "creative_insights", []) or []:
            store.creative.append(MemoryEntry(
                category=MemoryCategory.CREATIVE,
                content=ci,
                source="learning_engine",
            ))
        for chi in getattr(info, "channel_insights", []) or []:
            store.performance.append(MemoryEntry(
                category=MemoryCategory.PERFORMANCE,
                content=chi,
                source="learning_engine",
            ))
        return store

    @classmethod
    def from_raw_dict(cls, raw: dict[str, Any]) -> MemoryStore:
        """Build a :class:`MemoryStore` from a raw ``BusinessMemoryRecord.memory`` dict.

        The legacy memory JSON has keys: ``best_practices``, ``audience_insights``,
        ``creative_insights``, ``channel_insights``, ``metadata``. Each may also
        carry an optional ``category`` field per entry which maps directly.
        """
        store = cls()
        meta = raw.get("metadata", {}) or {}
        store.total_campaigns = meta.get("total_campaigns", 0)
        store.average_roi = meta.get("average_roi", "—")

        def _entries(items: Any, default_cat: MemoryCategory, source: str) -> list[MemoryEntry]:
            entries: list[MemoryEntry] = []
            if not items:
                return entries
            for item in items:
                if isinstance(item, dict):
                    cat_str = item.get("category")
                    try:
                        cat = MemoryCategory(cat_str) if cat_str else default_cat
                    except ValueError:
                        cat = default_cat
                    entries.append(MemoryEntry(
                        category=cat,
                        content=str(item.get("content", item.get("text", ""))),
                        confidence=float(item.get("confidence", 0.5)),
                        source=str(item.get("source", source)),
                        created_at=str(item.get("created_at", "")) or datetime.now(timezone.utc).isoformat(),
                    ))
                else:
                    entries.append(MemoryEntry(
                        category=default_cat,
                        content=str(item),
                        source=source,
                    ))
            return entries

        store.campaign.extend(_entries(raw.get("best_practices"), MemoryCategory.CAMPAIGN, "best_practice"))
        store.audience.extend(_entries(raw.get("audience_insights"), MemoryCategory.AUDIENCE, "learning_engine"))
        store.creative.extend(_entries(raw.get("creative_insights"), MemoryCategory.CREATIVE, "learning_engine"))
        store.performance.extend(_entries(raw.get("channel_insights"), MemoryCategory.PERFORMANCE, "learning_engine"))

        # Categorised entries stored under a top-level "categories" key (future-proof)
        categories = raw.get("categories", {}) or {}
        for cat in ALL_CATEGORIES:
            store._list_for(cat).extend(_entries(categories.get(cat.value), cat, "system"))

        return store
