"""Tests for the Engine Registry (Phase 9: Architecture Stabilisation)."""
from __future__ import annotations

from typing import Any

import pytest

from prachar_shared.marketing_intelligence import (
    BusinessIntelligenceEngine,
    CampaignStrategyEngine,
    EngineInfo,
    EngineRegistry,
    create_default_registry,
)
from prachar_shared.marketing_intelligence.base import IntelligenceEngine


class _DummyEngine(IntelligenceEngine):
    ENGINE_NAME = "dummy"
    ENGINE_VERSION = "1.0.0"
    PROMPT_VERSION = "1.0.0"
    SCHEMA_VERSION = "1.0.0"

    def _build_prompt(self, **kw: Any) -> str:
        return "dummy"

    def _build_schema(self) -> dict[str, Any]:
        return {"type": "object"}


class _DummyEngineV2(IntelligenceEngine):
    ENGINE_NAME = "dummy"  # Same name, different version
    ENGINE_VERSION = "2.0.0"
    PROMPT_VERSION = "2.0.0"
    SCHEMA_VERSION = "2.0.0"

    def _build_prompt(self, **kw: Any) -> str:
        return "dummy v2"

    def _build_schema(self) -> dict[str, Any]:
        return {"type": "object"}


class TestEngineRegistry:
    def test_register_and_get(self) -> None:
        registry = EngineRegistry()
        registry.register(_DummyEngine)
        assert registry.has("dummy")
        engine = registry.get("dummy")
        assert engine is not None
        assert isinstance(engine, _DummyEngine)

    def test_get_unknown_returns_none(self) -> None:
        registry = EngineRegistry()
        assert registry.get("nonexistent") is None
        assert not registry.has("nonexistent")

    def test_unregister(self) -> None:
        registry = EngineRegistry()
        registry.register(_DummyEngine)
        assert registry.unregister("dummy") is True
        assert not registry.has("dummy")
        assert registry.unregister("dummy") is False  # already removed

    def test_list_returns_engine_info(self) -> None:
        registry = EngineRegistry()
        registry.register(_DummyEngine, description="A dummy engine", capabilities=["test"])
        infos = registry.list()
        assert len(infos) == 1
        info = infos[0]
        assert isinstance(info, EngineInfo)
        assert info.name == "dummy"
        assert info.engine_version == "1.0.0"
        assert info.description == "A dummy engine"
        assert info.capabilities == ["test"]

    def test_names(self) -> None:
        registry = EngineRegistry()
        registry.register(_DummyEngine)
        assert registry.names() == ["dummy"]

    def test_health_all_healthy(self) -> None:
        registry = EngineRegistry()
        registry.register(_DummyEngine)
        health = registry.health()
        assert health["dummy"] == "healthy"

    def test_overwrite_replaces_engine(self) -> None:
        registry = EngineRegistry()
        registry.register(_DummyEngine)
        registry.register(_DummyEngineV2)  # same name, different version
        infos = registry.list()
        assert infos[0].engine_version == "2.0.0"

    def test_clear(self) -> None:
        registry = EngineRegistry()
        registry.register(_DummyEngine)
        registry.clear()
        assert registry.names() == []

    def test_engine_info_to_dict(self) -> None:
        info = EngineInfo(
            name="test", engine_version="1.0.0", prompt_version="1.0.0",
            schema_version="1.0.0", tier="large", max_tokens=2048,
            temperature=0.3, description="test", capabilities=["a"],
        )
        d = info.to_dict()
        assert d["name"] == "test"
        assert d["capabilities"] == ["a"]


class TestDefaultRegistry:
    def test_has_all_10_engines(self) -> None:
        registry = create_default_registry()
        names = set(registry.names())
        expected = {
            "business_intelligence", "audience_intelligence",
            "competitor_intelligence", "marketing_objective",
            "campaign_strategy", "creative_direction",
            "media_planning", "budget_intelligence",
            "execution_planner", "learning_engine",
        }
        assert names == expected

    def test_all_engines_healthy(self) -> None:
        registry = create_default_registry()
        health = registry.health()
        assert all(status == "healthy" for status in health.values())

    def test_list_has_metadata(self) -> None:
        registry = create_default_registry()
        infos = registry.list()
        assert len(infos) == 10
        # Each should have a description
        for info in infos:
            assert info.description != ""
            assert len(info.capabilities) > 0

    def test_get_returns_correct_type(self) -> None:
        registry = create_default_registry()
        engine = registry.get("business_intelligence")
        assert isinstance(engine, BusinessIntelligenceEngine)
        engine = registry.get("campaign_strategy")
        assert isinstance(engine, CampaignStrategyEngine)

    def test_strategy_engine_is_v2(self) -> None:
        """Phase 1 bumped strategy to v2.x — verify registry reflects this."""
        registry = create_default_registry()
        engine = registry.get("campaign_strategy")
        assert engine is not None
        assert engine.SCHEMA_VERSION.startswith("2.")
        infos = {i.name: i for i in registry.list()}
        assert infos["campaign_strategy"].schema_version.startswith("2.")
