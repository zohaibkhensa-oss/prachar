"""CURV AI Runtime — the single public AI entry point.

Architecture Freeze v2.0 — see V2_AI_ORCHESTRATOR_SPEC.md and RUNTIME_CONSTITUTION.md.

The Runtime is the only way the frontend invokes AI capabilities.
Tools never know about each other; only the Planner coordinates them.
Every execution creates a Decision Contract, emits Events, and writes to the Timeline.
"""
from __future__ import annotations

# Import tools to register them in the Tool Registry
# L1–L8 capability tools (were only imported in tests; now auto-registered)
# New wiring tools — connect channel adapters, loop, knowledge CRUD, integrations
from . import (
    tools,  # noqa: F401 — side effect: registers all tools
    tools_admin,  # noqa: F401
    tools_ads,  # noqa: F401
    tools_calendar,  # noqa: F401
    tools_channels,  # noqa: F401
    tools_collab,  # noqa: F401
    tools_crm,  # noqa: F401
    tools_email,  # noqa: F401
    tools_integrations,  # noqa: F401
    tools_knowledge,  # noqa: F401
    tools_landing,  # noqa: F401
    tools_loop,  # noqa: F401
    tools_phase2,  # noqa: F401 — side effect: registers Phase 2 tools
    tools_seo,  # noqa: F401
    tools_website,  # noqa: F401
    tools_whatsapp,  # noqa: F401
)
from .composer import ResponseComposer
from .context import AIContext, assemble_context
from .context_builder import (
    ContextBuilder,
    EnrichedContext,
    create_default_context_builder,
    get_context_builder,
)
from .context_ranking import (
    AdaptiveContextRankingLayer,
    ChunkWeightAdjustment,
    ContextEvaluation,
    ContextEvaluator,
    ContextItem,
    ContextItemExtractor,
    ContextItemType,
    ContextRankingLayer,
    ContextTrace,
    FeedbackRecord,
    ItemEvaluation,
    OfflineModelVersion,
    ProviderTrace,
    RankedEnrichedContext,
    RankingFeedbackStore,
    RetrievalQuality,
    ScoringWeights,
    SourceWeightAdjustment,
    TypeWeightAdjustment,
    estimate_tokens,
)
from .decision import DecisionContract, RiskLevel
from .events import AIEvent, EventBus, EventPhase, OrbState, SessionManager, get_session_manager
from .executor import ExecutionEngine, ExecutionResult
from .graph import ExecutionGraph, GraphEdge, GraphNode
from .memory_categories import MemoryCategory, MemoryEntry, MemoryStore
from .metrics import RuntimeMetrics, ToolMetrics
from .planner import ExecutionPlan, IntentEngine, IntentResult, Planner, RuntimeMode
from .registry import Tool, ToolManifest, ToolRegistry, get_registry, register_tool
from .runtime import InvokeRequest, InvokeResponse, Runtime
from .timeline import TimelineEntry, TimelineService

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
    "SessionManager",
    "get_session_manager",
    "RuntimeMetrics",
    "ToolMetrics",
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
