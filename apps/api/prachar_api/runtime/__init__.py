"""PRACHAR AI Runtime — the single public AI entry point.

Architecture Freeze v2.0 — see V2_AI_ORCHESTRATOR_SPEC.md and RUNTIME_CONSTITUTION.md.

The Runtime is the only way the frontend invokes AI capabilities.
Tools never know about each other; only the Planner coordinates them.
Every execution creates a Decision Contract, emits Events, and writes to the Timeline.
"""
from __future__ import annotations

from .context import AIContext, assemble_context
from .context_builder import ContextBuilder, EnrichedContext, get_context_builder, create_default_context_builder
from .context_ranking import (
    AdaptiveContextRankingLayer,
    ChunkWeightAdjustment,
    ContextEvaluation, ContextEvaluator, ContextItem, ContextItemExtractor,
    ContextItemType, ContextRankingLayer, ContextTrace, FeedbackRecord,
    ItemEvaluation, OfflineModelVersion, ProviderTrace, RankedEnrichedContext,
    RankingFeedbackStore, RetrievalQuality, ScoringWeights,
    SourceWeightAdjustment, TypeWeightAdjustment, estimate_tokens,
)
from .events import AIEvent, EventBus, EventPhase, OrbState, get_session_manager, SessionManager
from .registry import Tool, ToolManifest, ToolRegistry, get_registry, register_tool
from .memory_categories import MemoryCategory, MemoryEntry, MemoryStore
from .decision import DecisionContract, RiskLevel
from .graph import ExecutionGraph, GraphNode, GraphEdge
from .planner import IntentEngine, IntentResult, RuntimeMode, Planner, ExecutionPlan
from .executor import ExecutionEngine, ExecutionResult
from .composer import ResponseComposer
from .runtime import Runtime, InvokeRequest, InvokeResponse
from .timeline import TimelineEntry, TimelineService
from .metrics import RuntimeMetrics, ToolMetrics

# Import tools to register them in the Tool Registry
from . import tools  # noqa: F401 — side effect: registers all tools
from . import tools_phase2  # noqa: F401 — side effect: registers Phase 2 tools

__all__ = [
    # Context
    "AIContext",
    "assemble_context",
    # Context Builder
    "ContextBuilder",
    "EnrichedContext",
    "get_context_builder",
    "create_default_context_builder",
    # Context Ranking
    "AdaptiveContextRankingLayer",
    "ChunkWeightAdjustment",
    "ContextEvaluation",
    "ContextEvaluator",
    "ContextItem",
    "ContextItemExtractor",
    "ContextItemType",
    "ContextRankingLayer",
    "ContextTrace",
    "FeedbackRecord",
    "ItemEvaluation",
    "OfflineModelVersion",
    "ProviderTrace",
    "RankedEnrichedContext",
    "RankingFeedbackStore",
    "RetrievalQuality",
    "ScoringWeights",
    "SourceWeightAdjustment",
    "TypeWeightAdjustment",
    "estimate_tokens",
    # Events
    "AIEvent",
    "EventBus",
    "EventPhase",
    "OrbState",
    # Registry
    "Tool",
    "ToolManifest",
    "ToolRegistry",
    "get_registry",
    "register_tool",
    # Memory (E1.1)
    "MemoryCategory",
    "MemoryEntry",
    "MemoryStore",
    # Decision
    "DecisionContract",
    "RiskLevel",
    # Graph
    "ExecutionGraph",
    "GraphNode",
    "GraphEdge",
    # Planner
    "IntentEngine",
    "IntentResult",
    "RuntimeMode",
    "Planner",
    "ExecutionPlan",
    # Executor
    "ExecutionEngine",
    "ExecutionResult",
    # Composer
    "ResponseComposer",
    # Runtime
    "Runtime",
    "InvokeRequest",
    "InvokeResponse",
    # Timeline
    "TimelineEntry",
    "TimelineService",
]
