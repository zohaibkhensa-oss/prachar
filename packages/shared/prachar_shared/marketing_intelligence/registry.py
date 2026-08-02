"""Engine Registry for the Marketing Intelligence Engine.

Replaces hardcoded engine references with a dynamic registry. The Campaign
Brain requests engines by name from the registry, enabling:

- Dynamic registration of new engines (plugins)
- Discovery of available engines
- Health checks
- Version introspection
- Capability declaration
- Future: hot-swap engines without restarting the brain

Usage:
    from prachar_shared.marketing_intelligence import EngineRegistry, BusinessIntelligenceEngine

    registry = EngineRegistry()
    registry.register(BusinessIntelligenceEngine)
    registry.register(AudienceIntelligenceEngine)

    # Discover
    engines = registry.list()
    # → [{"name": "business_intelligence", "version": "1.0.0", ...}, ...]

    # Get
    engine = registry.get("business_intelligence")
    # → BusinessIntelligenceEngine instance

    # Health check
    health = registry.health()
    # → {"business_intelligence": "healthy", ...}

The registry is the single source of truth for which engines exist.
The Campaign Brain uses the registry to instantiate engines, making it
trivial to add new engines without modifying the brain.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .base import IntelligenceEngine

logger = logging.getLogger(__name__)


@dataclass
class EngineInfo:
    """Metadata about a registered engine."""

    name: str
    engine_version: str
    prompt_version: str
    schema_version: str
    tier: str
    max_tokens: int
    temperature: float
    description: str = ""
    capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "engine_version": self.engine_version,
            "prompt_version": self.prompt_version,
            "schema_version": self.schema_version,
            "tier": self.tier,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "description": self.description,
            "capabilities": self.capabilities,
        }


class EngineRegistry:
    """Dynamic registry of intelligence engines.

    Engines are registered by class. The registry instantiates them on
    demand (lazy) with the appropriate gateway. This decouples the Campaign
    Brain from specific engine classes — the brain asks the registry for
    an engine by name, and the registry provides it.
    """

    def __init__(self) -> None:
        self._engines: dict[str, type[IntelligenceEngine]] = {}
        self._instances: dict[str, IntelligenceEngine] = {}
        self._descriptions: dict[str, str] = {}
        self._capabilities: dict[str, list[str]] = {}

    def register(
        self,
        engine_class: type[IntelligenceEngine],
        *,
        description: str = "",
        capabilities: list[str] | None = None,
    ) -> None:
        """Register an engine class.

        Args:
            engine_class: The engine class (subclass of IntelligenceEngine).
            description: Human-readable description of what the engine does.
            capabilities: List of capability strings (e.g., ["analysis", "strategy"]).
        """
        name = engine_class.ENGINE_NAME
        if name in self._engines:
            logger.warning("overwriting registered engine: %s", name)
        self._engines[name] = engine_class
        self._descriptions[name] = description
        self._capabilities[name] = capabilities or []
        # Clear any cached instance
        self._instances.pop(name, None)

    def unregister(self, name: str) -> bool:
        """Unregister an engine by name. Returns True if it was registered."""
        if name not in self._engines:
            return False
        del self._engines[name]
        self._instances.pop(name, None)
        self._descriptions.pop(name, None)
        self._capabilities.pop(name, None)
        return True

    def get(self, name: str, gateway: Any = None) -> IntelligenceEngine | None:
        """Get an engine instance by name.

        Engines are instantiated lazily and cached. If a gateway is provided,
        it's passed to the engine constructor.

        Returns None if the engine is not registered.
        """
        if name not in self._engines:
            return None
        # Re-instantiate if gateway changed or not yet instantiated
        if name not in self._instances:
            engine_class = self._engines[name]
            self._instances[name] = engine_class(gateway=gateway)
        return self._instances[name]

    def has(self, name: str) -> bool:
        """Check if an engine is registered."""
        return name in self._engines

    def list(self) -> list[EngineInfo]:
        """List all registered engines with their metadata."""
        result: list[EngineInfo] = []
        for name, engine_class in self._engines.items():
            result.append(EngineInfo(
                name=name,
                engine_version=engine_class.ENGINE_VERSION,
                prompt_version=engine_class.PROMPT_VERSION,
                schema_version=engine_class.SCHEMA_VERSION,
                tier=engine_class.TIER.value if hasattr(engine_class.TIER, "value") else str(engine_class.TIER),
                max_tokens=engine_class.MAX_TOKENS,
                temperature=engine_class.TEMPERATURE,
                description=self._descriptions.get(name, ""),
                capabilities=self._capabilities.get(name, []),
            ))
        return result

    def names(self) -> list[str]:
        """List just the engine names."""
        return list(self._engines.keys())

    def health(self) -> dict[str, str]:
        """Check the health of all registered engines.

        Returns a dict mapping engine name to health status:
        - "healthy": engine is registered and can be instantiated
        - "unhealthy": engine failed to instantiate
        """
        result: dict[str, str] = {}
        for name in self._engines:
            try:
                engine = self.get(name)
                if engine is not None:
                    result[name] = "healthy"
                else:
                    result[name] = "unhealthy"
            except Exception as exc:
                logger.warning("engine %s health check failed: %s", name, exc)
                result[name] = "unhealthy"
        return result

    def clear(self) -> None:
        """Remove all registered engines."""
        self._engines.clear()
        self._instances.clear()
        self._descriptions.clear()
        self._capabilities.clear()


# ─── Default registry with all 10 engines ──────────────────────────────────


def create_default_registry() -> EngineRegistry:
    """Create a registry pre-populated with all 10 default engines.

    This is the standard registry used by CampaignBrain. Custom registries
    can be created by instantiating EngineRegistry() and registering
    only the engines needed (e.g., for testing or for a lightweight service).
    """
    from .audience_engine import AudienceIntelligenceEngine
    from .budget_engine import BudgetIntelligenceEngine
    from .business_engine import BusinessIntelligenceEngine
    from .competitor_engine import CompetitorIntelligenceEngine
    from .creative_engine import CreativeDirectionEngine
    from .execution_engine import ExecutionPlanner
    from .learning_engine import LearningEngine
    from .media_engine import MediaPlanningEngine
    from .objective_engine import MarketingObjectiveEngine
    from .strategy_engine import CampaignStrategyEngine

    registry = EngineRegistry()
    registry.register(
        BusinessIntelligenceEngine,
        description="Understands the business: industry, USP, SWOT, market position.",
        capabilities=["analysis", "business"],
    )
    registry.register(
        AudienceIntelligenceEngine,
        description="Defines primary/secondary audiences with buying intent and journey.",
        capabilities=["analysis", "audience"],
    )
    registry.register(
        CompetitorIntelligenceEngine,
        description="Analyzes competitors: messaging, positioning, market gaps.",
        capabilities=["analysis", "competitor"],
    )
    registry.register(
        MarketingObjectiveEngine,
        description="Converts user goals into SMART KPIs and measurable objectives.",
        capabilities=["objective", "kpi"],
    )
    registry.register(
        CampaignStrategyEngine,
        description="Creates campaign strategy: core message, funnel, content pillars.",
        capabilities=["strategy", "creative-direction"],
    )
    registry.register(
        CreativeDirectionEngine,
        description="Determines visual style, colours, typography before asset generation.",
        capabilities=["creative", "visual-direction"],
    )
    registry.register(
        MediaPlanningEngine,
        description="Selects channels, allocates budget, schedules publishing.",
        capabilities=["media", "channel-selection", "budget-allocation"],
    )
    registry.register(
        BudgetIntelligenceEngine,
        description="Estimates costs, ROI, CAC, break-even analysis.",
        capabilities=["budget", "financial", "roi"],
    )
    registry.register(
        ExecutionPlanner,
        description="Breaks campaign into tasks with timeline, dependencies, approvals.",
        capabilities=["execution", "planning", "task-breakdown"],
    )
    registry.register(
        LearningEngine,
        description="Extracts learnings post-campaign and updates business memory.",
        capabilities=["learning", "continuous-improvement"],
    )
    return registry
