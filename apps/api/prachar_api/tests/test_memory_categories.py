"""Tests for Memory Categories (Phase E1.1).

Verifies the 7 memory classes, MemoryStore categorisation, ToolManifest
memory_categories field, and AIContext.get_memory_for_tool filtering.
"""
from __future__ import annotations

import uuid

import pytest

from prachar_api.runtime.memory_categories import (
    ALL_CATEGORIES,
    MemoryCategory,
    MemoryEntry,
    MemoryStore,
)
from prachar_api.runtime.registry import ToolManifest, ToolRegistry, ToolCategory
from prachar_api.runtime.context import AIContext, MemoryInfo


# ─── MemoryCategory enum ────────────────────────────────────────────────────


class TestMemoryCategory:
    def test_seven_categories_exist(self):
        assert len(MemoryCategory) == 7
        assert MemoryCategory.BRAND in MemoryCategory
        assert MemoryCategory.CAMPAIGN in MemoryCategory
        assert MemoryCategory.AUDIENCE in MemoryCategory
        assert MemoryCategory.CREATIVE in MemoryCategory
        assert MemoryCategory.PERFORMANCE in MemoryCategory
        assert MemoryCategory.WORKSPACE in MemoryCategory
        assert MemoryCategory.USER_PREFERENCES in MemoryCategory

    def test_category_values_are_strings(self):
        for cat in MemoryCategory:
            assert isinstance(cat.value, str)
            assert cat.value  # non-empty

    def test_all_categories_tuple(self):
        assert len(ALL_CATEGORIES) == 7
        assert all(isinstance(c, MemoryCategory) for c in ALL_CATEGORIES)


# ─── MemoryEntry ────────────────────────────────────────────────────────────


class TestMemoryEntry:
    def test_creation_defaults(self):
        entry = MemoryEntry(
            category=MemoryCategory.BRAND,
            content="Acme is a D2C skincare brand",
        )
        assert entry.category == MemoryCategory.BRAND
        assert entry.content == "Acme is a D2C skincare brand"
        assert entry.confidence == 0.5
        assert entry.source == "system"
        assert entry.created_at  # auto-populated

    def test_creation_with_all_fields(self):
        entry = MemoryEntry(
            category=MemoryCategory.CAMPAIGN,
            content="Diwali sale campaign performed well",
            confidence=0.9,
            source="learning_engine",
            created_at="2025-01-01T00:00:00+00:00",
        )
        assert entry.confidence == 0.9
        assert entry.source == "learning_engine"

    def test_serialisation(self):
        entry = MemoryEntry(
            category=MemoryCategory.AUDIENCE,
            content="18-24 urban professionals",
            confidence=0.8,
            source="campaign",
            created_at="2025-01-01T00:00:00+00:00",
        )
        d = entry.to_dict()
        assert d["category"] == "audience"
        assert d["content"] == "18-24 urban professionals"
        assert d["confidence"] == 0.8
        assert d["source"] == "campaign"
        assert d["created_at"] == "2025-01-01T00:00:00+00:00"


# ─── MemoryStore ────────────────────────────────────────────────────────────


class TestMemoryStore:
    def test_default_empty_store(self):
        store = MemoryStore()
        assert store.brand == []
        assert store.campaign == []
        assert store.audience == []
        assert store.creative == []
        assert store.performance == []
        assert store.workspace == []
        assert store.user_preferences == []
        assert store.total_campaigns == 0
        assert store.average_roi == "—"

    def test_get_for_categories_specific(self):
        store = MemoryStore()
        store.brand.append(MemoryEntry(MemoryCategory.BRAND, "Brand voice is playful"))
        store.campaign.append(MemoryEntry(MemoryCategory.CAMPAIGN, "Diwali worked"))
        store.creative.append(MemoryEntry(MemoryCategory.CREATIVE, "Reels win"))
        store.audience.append(MemoryEntry(MemoryCategory.AUDIENCE, "Gen Z"))

        result = store.get_for_categories([MemoryCategory.BRAND, MemoryCategory.AUDIENCE])
        assert len(result) == 2
        contents = [e.content for e in result]
        assert "Brand voice is playful" in contents
        assert "Gen Z" in contents
        # Creative and campaign should NOT be included
        assert "Reels win" not in contents
        assert "Diwali worked" not in contents

    def test_get_for_categories_empty_means_all(self):
        store = MemoryStore()
        store.brand.append(MemoryEntry(MemoryCategory.BRAND, "b1"))
        store.campaign.append(MemoryEntry(MemoryCategory.CAMPAIGN, "c1"))
        store.performance.append(MemoryEntry(MemoryCategory.PERFORMANCE, "p1"))

        result = store.get_for_categories([])
        assert len(result) == 3  # all categories

    def test_get_for_categories_single(self):
        store = MemoryStore()
        store.creative.append(MemoryEntry(MemoryCategory.CREATIVE, "style A"))
        store.creative.append(MemoryEntry(MemoryCategory.CREATIVE, "style B"))
        store.audience.append(MemoryEntry(MemoryCategory.AUDIENCE, "aud"))

        result = store.get_for_categories([MemoryCategory.CREATIVE])
        assert len(result) == 2
        assert all(e.category == MemoryCategory.CREATIVE for e in result)

    def test_all_returns_everything(self):
        store = MemoryStore()
        store.brand.append(MemoryEntry(MemoryCategory.BRAND, "b"))
        store.workspace.append(MemoryEntry(MemoryCategory.WORKSPACE, "w"))
        store.user_preferences.append(MemoryEntry(MemoryCategory.USER_PREFERENCES, "u"))
        assert len(store.all()) == 3

    def test_counts_by_category(self):
        store = MemoryStore()
        store.brand.append(MemoryEntry(MemoryCategory.BRAND, "b1"))
        store.brand.append(MemoryEntry(MemoryCategory.BRAND, "b2"))
        store.campaign.append(MemoryEntry(MemoryCategory.CAMPAIGN, "c1"))
        counts = store.counts_by_category()
        assert counts["brand"] == 2
        assert counts["campaign"] == 1
        assert counts["audience"] == 0
        assert counts["creative"] == 0
        assert counts["performance"] == 0
        assert counts["workspace"] == 0
        assert counts["user_preferences"] == 0

    def test_to_dict(self):
        store = MemoryStore(total_campaigns=5, average_roi="3.2x")
        store.brand.append(MemoryEntry(MemoryCategory.BRAND, "Acme", confidence=0.9))
        d = store.to_dict()
        assert d["total_campaigns"] == 5
        assert d["average_roi"] == "3.2x"
        assert len(d["brand"]) == 1
        assert d["brand"][0]["content"] == "Acme"
        assert d["brand"][0]["confidence"] == 0.9
        # All 7 categories present as keys
        for cat in MemoryCategory:
            assert cat.value in d

    def test_from_memory_info(self):
        info = MemoryInfo(
            best_practices=["Test BP"],
            audience_insights=["Gen Z"],
            creative_insights=["Reels win"],
            channel_insights=["Instagram top"],
            total_campaigns=3,
            average_roi="2.5x",
        )
        store = MemoryStore.from_memory_info(info)
        assert store.total_campaigns == 3
        assert store.average_roi == "2.5x"
        # best_practices -> CAMPAIGN
        assert any(e.content == "Test BP" for e in store.campaign)
        # audience_insights -> AUDIENCE
        assert any(e.content == "Gen Z" for e in store.audience)
        # creative_insights -> CREATIVE
        assert any(e.content == "Reels win" for e in store.creative)
        # channel_insights -> PERFORMANCE
        assert any(e.content == "Instagram top" for e in store.performance)

    def test_from_raw_dict(self):
        raw = {
            "best_practices": ["BP1", "BP2"],
            "audience_insights": ["Aud1"],
            "creative_insights": ["Cre1"],
            "channel_insights": ["Ch1"],
            "metadata": {"total_campaigns": 7, "average_roi": "4x"},
        }
        store = MemoryStore.from_raw_dict(raw)
        assert store.total_campaigns == 7
        assert store.average_roi == "4x"
        assert len(store.campaign) == 2
        assert len(store.audience) == 1
        assert len(store.creative) == 1
        assert len(store.performance) == 1

    def test_from_raw_dict_with_categorised_entries(self):
        raw = {
            "categories": {
                "brand": [{"content": "Brand X", "confidence": 0.9}],
                "workspace": [{"content": "User approved", "source": "user"}],
            },
        }
        store = MemoryStore.from_raw_dict(raw)
        assert len(store.brand) == 1
        assert store.brand[0].content == "Brand X"
        assert store.brand[0].confidence == 0.9
        assert len(store.workspace) == 1
        assert store.workspace[0].source == "user"

    # ─── Backward-compat properties ─────────────────────────────────────────

    def test_backward_compat_best_practices(self):
        store = MemoryStore()
        store.campaign.append(MemoryEntry(MemoryCategory.CAMPAIGN, "BP1", source="best_practice"))
        store.campaign.append(MemoryEntry(MemoryCategory.CAMPAIGN, "other", source="learning_engine"))
        assert store.best_practices == ["BP1"]

    def test_backward_compat_audience_insights(self):
        store = MemoryStore()
        store.audience.append(MemoryEntry(MemoryCategory.AUDIENCE, "Gen Z"))
        store.audience.append(MemoryEntry(MemoryCategory.AUDIENCE, "Millennials"))
        assert store.audience_insights == ["Gen Z", "Millennials"]

    def test_backward_compat_creative_insights(self):
        store = MemoryStore()
        store.creative.append(MemoryEntry(MemoryCategory.CREATIVE, "Reels win"))
        assert store.creative_insights == ["Reels win"]

    def test_backward_compat_channel_insights(self):
        store = MemoryStore()
        store.performance.append(MemoryEntry(MemoryCategory.PERFORMANCE, "IG top channel"))
        assert store.channel_insights == ["IG top channel"]


# ─── ToolManifest memory_categories field ───────────────────────────────────


class TestToolManifestMemoryCategories:
    def test_default_empty_memory_categories(self):
        manifest = ToolManifest(
            name="test.tool",
            display_name="Test",
            category=ToolCategory.ANALYTICS,
            description="Test",
            estimated_cost_usd=0.0,
        )
        assert manifest.memory_categories == []

    def test_memory_categories_in_to_dict(self):
        manifest = ToolManifest(
            name="test.tool",
            display_name="Test",
            category=ToolCategory.ANALYTICS,
            description="Test",
            estimated_cost_usd=0.0,
            memory_categories=[MemoryCategory.BRAND, MemoryCategory.CAMPAIGN],
        )
        d = manifest.to_dict()
        assert d["memory_categories"] == ["brand", "campaign"]

    def test_memory_categories_empty_in_to_dict(self):
        manifest = ToolManifest(
            name="test.tool",
            display_name="Test",
            category=ToolCategory.ANALYTICS,
            description="Test",
            estimated_cost_usd=0.0,
        )
        d = manifest.to_dict()
        assert d["memory_categories"] == []


# ─── AIContext.get_memory_for_tool ──────────────────────────────────────────


def _make_ctx_with_memory() -> AIContext:
    """Build an AIContext with memories spread across categories."""
    ctx = AIContext(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        brand_id=uuid.uuid4(),
    )
    ctx.memory.brand.append(MemoryEntry(MemoryCategory.BRAND, "Brand identity"))
    ctx.memory.audience.append(MemoryEntry(MemoryCategory.AUDIENCE, "Gen Z"))
    ctx.memory.campaign.append(MemoryEntry(MemoryCategory.CAMPAIGN, "Diwali worked"))
    ctx.memory.creative.append(MemoryEntry(MemoryCategory.CREATIVE, "Reels win"))
    ctx.memory.performance.append(MemoryEntry(MemoryCategory.PERFORMANCE, "ROAS 3x"))
    ctx.memory.workspace.append(MemoryEntry(MemoryCategory.WORKSPACE, "User approved"))
    ctx.memory.user_preferences.append(MemoryEntry(MemoryCategory.USER_PREFERENCES, "prefers Hindi"))
    return ctx


def _make_registry_with_tools() -> ToolRegistry:
    """Build a registry with a few tools declaring memory categories."""
    registry = ToolRegistry()

    async def noop(ctx, inp):
        return {}

    registry.register(ToolManifest(
        name="campaign_brain.analyse",
        display_name="Analyse",
        category=ToolCategory.CAMPAIGN,
        description="Analyse",
        estimated_cost_usd=0.0,
        memory_categories=[MemoryCategory.BRAND, MemoryCategory.AUDIENCE, MemoryCategory.CAMPAIGN],
    ), noop)

    registry.register(ToolManifest(
        name="creative_studio.generate",
        display_name="Creative",
        category=ToolCategory.CREATIVE,
        description="Creative",
        estimated_cost_usd=0.0,
        memory_categories=[MemoryCategory.BRAND, MemoryCategory.CREATIVE, MemoryCategory.AUDIENCE],
    ), noop)

    registry.register(ToolManifest(
        name="performance.check",
        display_name="Perf",
        category=ToolCategory.ANALYTICS,
        description="Perf",
        estimated_cost_usd=0.0,
        memory_categories=[MemoryCategory.PERFORMANCE, MemoryCategory.CAMPAIGN],
    ), noop)

    registry.register(ToolManifest(
        name="memory.recall",
        display_name="Recall",
        category=ToolCategory.MEMORY,
        description="Recall",
        estimated_cost_usd=0.0,
        memory_categories=[],  # all categories
    ), noop)

    return registry


class TestGetMemoryForTool:
    def test_campaign_brain_gets_brand_audience_campaign_not_creative(self):
        ctx = _make_ctx_with_memory()
        registry = _make_registry_with_tools()
        entries = ctx.get_memory_for_tool("campaign_brain.analyse", registry)
        contents = [e.content for e in entries]
        assert "Brand identity" in contents
        assert "Gen Z" in contents
        assert "Diwali worked" in contents
        # Creative and performance should NOT be present
        assert "Reels win" not in contents
        assert "ROAS 3x" not in contents
        assert "User approved" not in contents

    def test_creative_studio_gets_brand_creative_audience_not_performance(self):
        ctx = _make_ctx_with_memory()
        registry = _make_registry_with_tools()
        entries = ctx.get_memory_for_tool("creative_studio.generate", registry)
        contents = [e.content for e in entries]
        assert "Brand identity" in contents
        assert "Reels win" in contents
        assert "Gen Z" in contents
        # Performance and campaign should NOT be present
        assert "ROAS 3x" not in contents
        assert "Diwali worked" not in contents

    def test_performance_gets_performance_and_campaign(self):
        ctx = _make_ctx_with_memory()
        registry = _make_registry_with_tools()
        entries = ctx.get_memory_for_tool("performance.check", registry)
        contents = [e.content for e in entries]
        assert "ROAS 3x" in contents
        assert "Diwali worked" in contents
        assert "Brand identity" not in contents
        assert "Reels win" not in contents

    def test_empty_categories_returns_all(self):
        ctx = _make_ctx_with_memory()
        registry = _make_registry_with_tools()
        entries = ctx.get_memory_for_tool("memory.recall", registry)
        # All 7 entries returned
        assert len(entries) == 7

    def test_unknown_tool_returns_all(self):
        ctx = _make_ctx_with_memory()
        registry = _make_registry_with_tools()
        entries = ctx.get_memory_for_tool("does.not.exist", registry)
        # Safe default: all memory
        assert len(entries) == 7

    def test_backward_compatible_empty_memory_categories(self):
        """A tool with no memory_categories declared gets all memory."""
        ctx = _make_ctx_with_memory()
        registry = ToolRegistry()

        async def noop(ctx, inp):
            return {}

        registry.register(ToolManifest(
            name="legacy.tool",
            display_name="Legacy",
            category=ToolCategory.ANALYTICS,
            description="Legacy tool with no memory_categories",
            estimated_cost_usd=0.0,
        ), noop)

        entries = ctx.get_memory_for_tool("legacy.tool", registry)
        assert len(entries) == 7  # all categories


# ─── Registered tools have memory_categories ────────────────────────────────


class TestRegisteredToolsMemoryCategories:
    """Verify the real tool registrations declare memory categories."""

    def test_campaign_brain_analyse_categories(self):
        from prachar_api.runtime import get_registry
        # Ensure tools are imported/registered
        from prachar_api.runtime import tools  # noqa: F401
        registry = get_registry()
        manifest = registry.get("campaign_brain.analyse").manifest
        cats = set(manifest.memory_categories)
        assert MemoryCategory.BRAND in cats
        assert MemoryCategory.AUDIENCE in cats
        assert MemoryCategory.CAMPAIGN in cats
        # Should NOT include creative
        assert MemoryCategory.CREATIVE not in cats

    def test_creative_studio_generate_categories(self):
        from prachar_api.runtime import get_registry
        from prachar_api.runtime import tools  # noqa: F401
        registry = get_registry()
        manifest = registry.get("creative_studio.generate").manifest
        cats = set(manifest.memory_categories)
        assert MemoryCategory.BRAND in cats
        assert MemoryCategory.CREATIVE in cats
        assert MemoryCategory.AUDIENCE in cats
        # Should NOT include performance
        assert MemoryCategory.PERFORMANCE not in cats

    def test_performance_story_categories(self):
        from prachar_api.runtime import get_registry
        from prachar_api.runtime import tools  # noqa: F401
        registry = get_registry()
        manifest = registry.get("performance.story").manifest
        cats = set(manifest.memory_categories)
        assert MemoryCategory.PERFORMANCE in cats
        assert MemoryCategory.CAMPAIGN in cats

    def test_memory_retrieve_empty_categories(self):
        from prachar_api.runtime import get_registry
        from prachar_api.runtime import tools  # noqa: F401
        registry = get_registry()
        manifest = registry.get("memory.retrieve").manifest
        assert manifest.memory_categories == []  # all categories

    def test_review_publish_categories(self):
        from prachar_api.runtime import get_registry
        from prachar_api.runtime import tools  # noqa: F401
        registry = get_registry()
        manifest = registry.get("review.publish").manifest
        cats = set(manifest.memory_categories)
        assert MemoryCategory.CAMPAIGN in cats
        assert MemoryCategory.WORKSPACE in cats

    def test_chat_respond_categories(self):
        from prachar_api.runtime import get_registry
        from prachar_api.runtime import tools  # noqa: F401
        registry = get_registry()
        manifest = registry.get("chat.respond").manifest
        cats = set(manifest.memory_categories)
        assert MemoryCategory.BRAND in cats
        assert MemoryCategory.USER_PREFERENCES in cats
