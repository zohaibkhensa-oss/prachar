"""Architecture validation tests (Phase 10: Architecture Stabilisation).

These tests verify the architectural invariants of the Marketing Intelligence
Engine. They fail if any rule is violated, preventing architectural drift.

Rules enforced:
1. No shared→api imports (dependency inversion)
2. No circular imports within the marketing_intelligence package
3. No duplicate responsibility ownership (each concept has one owner)
4. Version compatibility (every engine has version constants)
5. Repository abstraction (BusinessMemoryStore depends on protocol)
6. Campaign Brain orchestration only (no manual engine chaining in routers)
7. Dependency inversion (domain models don't import infrastructure)
8. Engine independence (engines don't import each other)
"""
from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path
from typing import Any

import pytest

# ─── Paths ──────────────────────────────────────────────────────────────────

MI_PACKAGE_DIR = Path(__file__).resolve().parent.parent / "marketing_intelligence"
SHARED_PACKAGE_DIR = Path(__file__).resolve().parent.parent
API_ROUTERS_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "apps" / "api" / "prachar_api" / "routers"


# ─── 1. No shared→api imports ───────────────────────────────────────────────


class TestNoSharedToApiImports:
    """The shared package must never import from the API app."""

    def test_no_prachar_api_imports_in_shared(self) -> None:
        violations: list[str] = []
        for py_file in SHARED_PACKAGE_DIR.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                content = py_file.read_text()
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and "prachar_api" in node.module:
                    violations.append(f"{py_file}: from {node.module} import ...")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if "prachar_api" in alias.name:
                            violations.append(f"{py_file}: import {alias.name}")
        assert not violations, f"shared package imports from API app:\n{chr(10).join(violations)}"

    def test_no_sqlalchemy_imports_in_mi_domain(self) -> None:
        """Domain files must not import SQLAlchemy (infrastructure concern)."""
        domain_files = [
            "domain_base.py", "business_engine.py", "audience_engine.py",
            "competitor_engine.py", "objective_engine.py", "strategy_engine.py",
            "creative_engine.py", "media_engine.py", "budget_engine.py",
            "execution_engine.py", "learning_engine.py", "repository.py",
            "events.py", "registry.py",
        ]
        violations: list[str] = []
        for fname in domain_files:
            fpath = MI_PACKAGE_DIR / fname
            if not fpath.exists():
                continue
            content = fpath.read_text()
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and "sqlalchemy" in node.module:
                    violations.append(f"{fname}: from {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if "sqlalchemy" in alias.name:
                            violations.append(f"{fname}: import {alias.name}")
        assert not violations, f"domain files import SQLAlchemy:\n{chr(10).join(violations)}"


# ─── 2. No circular imports ─────────────────────────────────────────────────


class TestNoCircularImports:
    """All modules in the marketing_intelligence package must import cleanly."""

    @pytest.mark.parametrize("module_name", [
        "prachar_shared.marketing_intelligence",
        "prachar_shared.marketing_intelligence.base",
        "prachar_shared.marketing_intelligence.domain_base",
        "prachar_shared.marketing_intelligence.repository",
        "prachar_shared.marketing_intelligence.memory",
        "prachar_shared.marketing_intelligence.events",
        "prachar_shared.marketing_intelligence.registry",
        "prachar_shared.marketing_intelligence.brain",
        "prachar_shared.marketing_intelligence.business_engine",
        "prachar_shared.marketing_intelligence.audience_engine",
        "prachar_shared.marketing_intelligence.competitor_engine",
        "prachar_shared.marketing_intelligence.objective_engine",
        "prachar_shared.marketing_intelligence.strategy_engine",
        "prachar_shared.marketing_intelligence.creative_engine",
        "prachar_shared.marketing_intelligence.media_engine",
        "prachar_shared.marketing_intelligence.budget_engine",
        "prachar_shared.marketing_intelligence.execution_engine",
        "prachar_shared.marketing_intelligence.learning_engine",
    ])
    def test_module_imports_without_error(self, module_name: str) -> None:
        """Each module should be importable without raising."""
        try:
            importlib.import_module(module_name)
        except ImportError as e:
            pytest.fail(f"Circular import or missing dependency in {module_name}: {e}")


# ─── 3. No duplicate responsibility ownership ───────────────────────────────


class TestNoDuplicateOwnership:
    """Each concept must have exactly one owner engine."""

    def test_strategy_does_not_own_media_mix(self) -> None:
        """Strategy Engine must NOT have media_mix (owned by Media Planning)."""
        from prachar_shared.marketing_intelligence import CampaignStrategy
        from dataclasses import fields
        field_names = {f.name for f in fields(CampaignStrategy)}
        assert "media_mix" not in field_names, "CampaignStrategy must not have media_mix field"

    def test_strategy_does_not_own_budget_allocation(self) -> None:
        """Strategy Engine must NOT have budget_allocation (owned by Budget)."""
        from prachar_shared.marketing_intelligence import CampaignStrategy
        from dataclasses import fields
        field_names = {f.name for f in fields(CampaignStrategy)}
        assert "budget_allocation" not in field_names
        assert "media_mix" not in field_names
        assert "success_metrics" not in field_names  # owned by Objective Engine

    def test_strategy_owns_channel_intent(self) -> None:
        """Strategy Engine owns channel_intent (strategic, not tactical)."""
        from prachar_shared.marketing_intelligence import CampaignStrategy
        from dataclasses import fields
        field_names = {f.name for f in fields(CampaignStrategy)}
        assert "channel_intent" in field_names

    def test_media_owns_recommended_channels(self) -> None:
        """Media Planning Engine owns recommended_channels."""
        from prachar_shared.marketing_intelligence import MediaPlan
        from dataclasses import fields
        field_names = {f.name for f in fields(MediaPlan)}
        assert "recommended_channels" in field_names

    def test_budget_owns_total_cost(self) -> None:
        """Budget Engine owns total_cost and roi_projection."""
        from prachar_shared.marketing_intelligence import BudgetEstimate
        from dataclasses import fields
        field_names = {f.name for f in fields(BudgetEstimate)}
        assert "total_cost" in field_names
        assert "roi_projection" in field_names

    def test_objective_owns_kpis(self) -> None:
        """Objective Engine owns kpis and success_criteria."""
        from prachar_shared.marketing_intelligence import MarketingObjective
        from dataclasses import fields
        field_names = {f.name for f in fields(MarketingObjective)}
        assert "kpis" in field_names
        assert "success_criteria" in field_names


# ─── 4. Version compatibility ──────────────────────────────────────────────


class TestVersionCompatibility:
    """Every engine must have version constants."""

    def test_all_engines_have_version_constants(self) -> None:
        from prachar_shared.marketing_intelligence import (
            AudienceIntelligenceEngine,
            BudgetIntelligenceEngine,
            BusinessIntelligenceEngine,
            CampaignStrategyEngine,
            CompetitorIntelligenceEngine,
            CreativeDirectionEngine,
            ExecutionPlanner,
            LearningEngine,
            MarketingObjectiveEngine,
            MediaPlanningEngine,
        )
        engines = [
            BusinessIntelligenceEngine, AudienceIntelligenceEngine,
            CompetitorIntelligenceEngine, MarketingObjectiveEngine,
            CampaignStrategyEngine, CreativeDirectionEngine,
            MediaPlanningEngine, BudgetIntelligenceEngine,
            ExecutionPlanner, LearningEngine,
        ]
        for engine in engines:
            assert hasattr(engine, "ENGINE_VERSION"), f"{engine.__name__} missing ENGINE_VERSION"
            assert hasattr(engine, "PROMPT_VERSION"), f"{engine.__name__} missing PROMPT_VERSION"
            assert hasattr(engine, "SCHEMA_VERSION"), f"{engine.__name__} missing SCHEMA_VERSION"
            assert engine.ENGINE_VERSION, f"{engine.__name__} has empty ENGINE_VERSION"

    def test_engine_output_has_versioning_fields(self) -> None:
        from prachar_shared.marketing_intelligence import EngineOutput
        out = EngineOutput(result={})
        assert hasattr(out, "schema_version")
        assert hasattr(out, "engine_version")
        assert hasattr(out, "prompt_version")
        assert hasattr(out, "model_version")
        assert hasattr(out, "generated_by")
        assert hasattr(out, "created_at")

    def test_strategy_schema_is_v2(self) -> None:
        """Phase 1 bumped strategy schema to 2.0.0; Phase I1 bumped to 2.1.0."""
        from prachar_shared.marketing_intelligence import CampaignStrategyEngine
        assert CampaignStrategyEngine.SCHEMA_VERSION.startswith("2.")


# ─── 5. Repository abstraction ──────────────────────────────────────────────


class TestRepositoryAbstraction:
    """BusinessMemoryStore must depend on the protocol, not on SQLAlchemy."""

    def test_memory_store_accepts_protocol(self) -> None:
        from prachar_shared.marketing_intelligence import BusinessMemoryStore, InMemoryRepository
        store = BusinessMemoryStore(repository=InMemoryRepository())
        assert store._repository is not None

    def test_memory_store_defaults_to_in_memory(self) -> None:
        from prachar_shared.marketing_intelligence import BusinessMemoryStore, InMemoryRepository
        store = BusinessMemoryStore()
        assert isinstance(store._repository, InMemoryRepository)

    def test_memory_store_does_not_import_sqlalchemy(self) -> None:
        """memory.py must not import sqlalchemy at module level."""
        fpath = MI_PACKAGE_DIR / "memory.py"
        content = fpath.read_text()
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "sqlalchemy" in node.module:
                pytest.fail(f"memory.py imports sqlalchemy: from {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "sqlalchemy" in alias.name:
                        pytest.fail(f"memory.py imports sqlalchemy: import {alias.name}")


# ─── 6. Campaign Brain orchestration only ───────────────────────────────────


class TestCampaignBrainOrchestration:
    """Routers must not manually chain engines — they delegate to CampaignBrain."""

    def test_chat_router_uses_brain_consult(self) -> None:
        """chat.py should call brain.consult(), not chain engines manually."""
        fpath = API_ROUTERS_DIR / "chat.py"
        if not fpath.exists():
            pytest.skip("chat.py not found")
        content = fpath.read_text()
        # Should use brain.consult (the public API)
        assert "brain.consult(" in content, "chat.py should use brain.consult()"
        # Should NOT manually chain engines
        assert "brain.analyse_business(" not in content, \
            "chat.py should not call brain.analyse_business() directly — use brain.consult()"
        assert "brain.analyse_audience(" not in content
        assert "brain.derive_objective(" not in content
        assert "brain.create_strategy(" not in content

    def test_campaign_brain_router_uses_public_api(self) -> None:
        """campaign_brain.py should use public API methods where possible."""
        fpath = API_ROUTERS_DIR / "campaign_brain.py"
        if not fpath.exists():
            pytest.skip("campaign_brain.py not found")
        content = fpath.read_text()
        # Should use at least one public API method
        public_methods = ["brain.analyse(", "brain.consult(", "brain.generate_strategy(",
                         "brain.generate_campaign(", "brain.generate_media_plan(", "brain.learn("]
        assert any(m in content for m in public_methods), \
            "campaign_brain.py should use at least one CampaignBrain public API method"


# ─── 7. Dependency inversion ────────────────────────────────────────────────


class TestDependencyInversion:
    """Domain models must not import infrastructure."""

    def test_domain_models_inherit_from_domain_model(self) -> None:
        from prachar_shared.marketing_intelligence import (
            AudienceProfile, BudgetEstimate, BusinessProfile, CampaignStrategy,
            CompetitorProfile, CreativeDirection, DomainModel, ExecutionPlan,
            LearningReport, MarketingObjective, MediaPlan,
        )
        models = [
            BusinessProfile, AudienceProfile, CompetitorProfile,
            MarketingObjective, CampaignStrategy, CreativeDirection,
            MediaPlan, BudgetEstimate, ExecutionPlan, LearningReport,
        ]
        for model in models:
            assert issubclass(model, DomainModel), f"{model.__name__} is not a DomainModel"

    def test_domain_models_have_from_dict(self) -> None:
        from prachar_shared.marketing_intelligence import BusinessProfile
        profile = BusinessProfile.from_dict({"industry": "Coffee"})
        assert profile.industry == "Coffee"

    def test_domain_models_have_validate(self) -> None:
        from prachar_shared.marketing_intelligence import BusinessProfile
        profile = BusinessProfile()
        assert isinstance(profile.validate(), list)

    def test_domain_models_have_schema_version(self) -> None:
        from prachar_shared.marketing_intelligence import BusinessProfile, CampaignStrategy
        assert BusinessProfile.schema_version() == "1.0.0"
        assert CampaignStrategy.schema_version() == "2.0.0"


# ─── 8. Engine independence ─────────────────────────────────────────────────


class TestEngineIndependence:
    """Engines must not import each other — they communicate via outputs only."""

    ENGINE_FILES = [
        "business_engine.py", "audience_engine.py", "competitor_engine.py",
        "objective_engine.py", "strategy_engine.py", "creative_engine.py",
        "media_engine.py", "budget_engine.py", "execution_engine.py",
        "learning_engine.py",
    ]

    @pytest.mark.parametrize("engine_file", ENGINE_FILES)
    def test_engine_does_not_import_other_engines(self, engine_file: str) -> None:
        fpath = MI_PACKAGE_DIR / engine_file
        content = fpath.read_text()
        tree = ast.parse(content)
        other_engines = [f for f in self.ENGINE_FILES if f != engine_file]
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                # Check if importing from another engine module
                for other in other_engines:
                    other_module = other.replace(".py", "")
                    if other_module in node.module:
                        pytest.fail(f"{engine_file} imports from {other_module}")
