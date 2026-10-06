"""Marketing Intelligence Engine — the strategic brain of CURV AI.

This package implements the "think before create" principle. Every campaign
begins with strategy, not creative assets. The engine reasons like a senior
advertising agency (McKinsey + WPP + OpenAI + Apple).

Architecture:
    CURV AI (chat)
      ↓
    CampaignBrain (orchestrator)
      ↓
    ┌─────────────────────────────────────────────────────┐
    │  Business Intelligence Engine                       │
    │  Audience Intelligence Engine                       │
    │  Competitor Intelligence Engine                     │
    │  Marketing Objective Engine                         │
    │  Campaign Strategy Engine                           │
    │  Creative Direction Engine                          │
    │  Media Planning Engine                              │
    │  Budget Intelligence Engine                         │
    │  Execution Planner                                  │
    │  Learning Engine                                    │
    └─────────────────────────────────────────────────────┘
      ↓
    AI Workers (creative generation)
      ↓
    Publishing → Analytics → Continuous Learning

Every engine output includes:
    - confidence (0.0-1.0)
    - business_rationale
    - marketing_rationale
    - alternatives
    - risks
    - expected_outcome
    - evidence
    - reasoning
    - sources
    - cost_usd
    - latency_ms
"""
from __future__ import annotations

from .audience_engine import AudienceIntelligenceEngine, AudienceProfile
from .base import (
    EngineOutput,
    EngineResult,
    IntelligenceEngine,
    Recommendation,
)
from .brain import CampaignBrain, FullCampaign
from .budget_engine import BudgetEstimate, BudgetIntelligenceEngine
from .business_engine import BusinessIntelligenceEngine, BusinessProfile
from .competitor_engine import CompetitorIntelligenceEngine, CompetitorProfile
from .creative_engine import CreativeDirection, CreativeDirectionEngine
from .domain_base import DomainModel, VersionMismatchError
from .events import (
    AudienceIdentified,
    BudgetCalculated,
    BusinessAnalysed,
    CampaignCompleted,
    CompetitorsAnalysed,
    CreativeDirectionReady,
    DomainEvent,
    EventBus,
    ExecutionPlanned,
    LearningStored,
    MediaPlanReady,
    ObjectiveDerived,
    StrategyGenerated,
)
from .execution_engine import ExecutionPlan, ExecutionPlanner
from .learning_engine import LearningEngine, LearningReport
from .media_engine import MediaPlan, MediaPlanningEngine
from .memory import BusinessMemory, BusinessMemoryStore
from .objective_engine import MarketingObjective, MarketingObjectiveEngine
from .registry import EngineInfo, EngineRegistry, create_default_registry
from .repository import InMemoryRepository, MemoryRepository
from .strategy_engine import CampaignStrategy, CampaignStrategyEngine, Strategy, StrategyEngine

__all__ = [
    # Base
    "EngineOutput",
    "EngineResult",
    "IntelligenceEngine",
    "Recommendation",
    # Domain base (Phase 3: Architecture Stabilisation)
    "DomainModel",
    "VersionMismatchError",
    # Engines
    "BusinessIntelligenceEngine",
    "BusinessProfile",
    "AudienceIntelligenceEngine",
    "AudienceProfile",
    "CompetitorIntelligenceEngine",
    "CompetitorProfile",
    "MarketingObjectiveEngine",
    "MarketingObjective",
    "CampaignStrategyEngine",
    "CampaignStrategy",
    "Strategy",
    "StrategyEngine",
    "CreativeDirectionEngine",
    "CreativeDirection",
    "MediaPlanningEngine",
    "MediaPlan",
    "BudgetIntelligenceEngine",
    "BudgetEstimate",
    "ExecutionPlanner",
    "ExecutionPlan",
    "LearningEngine",
    "LearningReport",
    # Memory & Brain
    "BusinessMemory",
    "BusinessMemoryStore",
    "InMemoryRepository",
    "MemoryRepository",
    "EngineInfo",
    "EngineRegistry",
    "create_default_registry",
    "CampaignBrain",
    "FullCampaign",
    # Events (Phase 8: Architecture Stabilisation)
    "DomainEvent",
    "EventBus",
    "BusinessAnalysed",
    "AudienceIdentified",
    "CompetitorsAnalysed",
    "ObjectiveDerived",
    "StrategyGenerated",
    "CreativeDirectionReady",
    "MediaPlanReady",
    "BudgetCalculated",
    "ExecutionPlanned",
    "CampaignCompleted",
    "LearningStored",
]
