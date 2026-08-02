"""Tool Registry — every AI capability registers here with a Tool Manifest.

Constitution Rule 6: Every tool must expose a Tool Manifest. No hidden behaviour.
Constitution Rule 7: The Planner reasons from manifests. Never hard-code intent→tool mappings.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Protocol, TYPE_CHECKING

from .memory_categories import MemoryCategory

if TYPE_CHECKING:
    from .context import AIContext

log = logging.getLogger("prachar.runtime.registry")


# ─── Enums ──────────────────────────────────────────────────────────────────


class ToolCategory(str, Enum):
    """Namespace a tool belongs to — matches event taxonomy."""

    CONVERSATION = "conversation"
    CAMPAIGN = "campaign"
    CREATIVE = "creative"
    REVIEW = "review"
    ANALYTICS = "analytics"
    NOTIFICATION = "notification"
    EXECUTION = "execution"
    MEMORY = "memory"
    ONBOARDING = "onboarding"
    AUTOMATION = "automation"
    WEBSITE = "website"
    SEO = "seo"
    LANDING_PAGE = "landing_page"
    CRM = "crm"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    CALENDAR = "calendar"
    COLLABORATION = "collaboration"
    RESEARCH = "research"
    ANALYSIS = "analysis"


class SideEffects(str, Enum):
    """What kind of side effects a tool has."""

    NONE = "none"        # pure read
    READS = "reads"       # reads from DB/external
    WRITES = "writes"     # writes to DB
    EXTERNAL = "external"  # calls external API (publish, OAuth, etc.)


class RetryPolicy(str, Enum):
    """Retry behaviour on tool failure."""

    NONE = "none"
    ONCE = "once"
    TWICE = "twice"
    EXPONENTIAL = "exponential"


# ─── Tool Manifest ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ToolManifest:
    """Metadata that the Planner reasons about.

    Every tool exposes this. The Planner reads manifests to decide which tools
    to invoke, in what order, and whether approval is needed.
    """

    # Identity
    name: str                            # "campaign_brain.analyse"
    display_name: str                    # "Business Intelligence Engine"
    description: str                     # human-readable summary
    category: ToolCategory               # matches event namespace

    # Schema (JSON Schema fragments — can be minimal for now)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)

    # Cost & time estimates
    estimated_cost_usd: float = 0.0
    estimated_time_ms: int = 1000
    estimated_tokens: int = 0

    # Phase E2.2: Cost-aware planning estimates
    estimated_latency_ms: int = 5000          # expected execution time in ms
    quality_score: float = 0.8                # 0.0 to 1.0, higher is better

    # Capabilities
    supports_streaming: bool = False       # emits progress events?
    supports_cancellation: bool = True
    supports_retry: bool = True

    # Requirements
    requires_brand: bool = True
    requires_user_approval: bool = False   # always needs approval? (e.g. publish)
    requires_active_subscription: bool = False

    # Behaviour
    retry_policy: RetryPolicy = RetryPolicy.ONCE
    timeout_ms: int = 120_000
    soft_timeout_ms: int = 60_000       # V3: soft timeout — tool gets a warning
    hard_timeout_ms: int = 120_000      # V3: hard timeout — tool is killed
    side_effects: SideEffects = SideEffects.READS

    # Versioning (V5)
    version: str = "1.0.0"              # semantic version of this tool
    deprecated: bool = False            # is this tool deprecated?
    successor: str | None = None        # name of replacement tool (if deprecated)
    min_runtime_version: str = "1.0.0"  # minimum runtime version required

    # Permissions
    required_role: str = "member"          # "owner", "admin", "member"
    required_permissions: tuple[str, ...] = ()

    # Memory — which memory categories this tool needs (E1.1)
    # Empty list means "all categories" (backward compatible)
    memory_categories: list[MemoryCategory] = field(default_factory=list)

    @property
    def cost_efficiency(self) -> float:
        """Quality per dollar — higher is better value (Phase E2.2).

        Computed as ``quality_score / max(estimated_cost_usd, 0.001)`` so a
        zero-cost tool does not blow up to infinity.
        """
        return self.quality_score / max(self.estimated_cost_usd, 0.001)

    def to_dict(self) -> dict[str, Any]:
        """Serialise for the Planner prompt and for API responses."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category.value,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "estimated_cost_usd": self.estimated_cost_usd,
            "estimated_time_ms": self.estimated_time_ms,
            "estimated_tokens": self.estimated_tokens,
            # Phase E2.2: cost-aware planning
            "estimated_latency_ms": self.estimated_latency_ms,
            "quality_score": self.quality_score,
            "cost_efficiency": self.cost_efficiency,
            "supports_streaming": self.supports_streaming,
            "supports_cancellation": self.supports_cancellation,
            "requires_brand": self.requires_brand,
            "requires_user_approval": self.requires_user_approval,
            "requires_active_subscription": self.requires_active_subscription,
            "side_effects": self.side_effects.value,
            "required_role": self.required_role,
            "required_permissions": list(self.required_permissions),
            # V3: Timeouts
            "timeout_ms": self.timeout_ms,
            "soft_timeout_ms": self.soft_timeout_ms,
            "hard_timeout_ms": self.hard_timeout_ms,
            # V5: Versioning
            "version": self.version,
            "deprecated": self.deprecated,
            "successor": self.successor,
            "min_runtime_version": self.min_runtime_version,
            # E1.1: Memory categories
            "memory_categories": [c.value for c in self.memory_categories],
        }


# ─── Tool Protocol ──────────────────────────────────────────────────────────


class Tool(Protocol):
    """Every tool implements this protocol.

    A tool is an async callable that receives:
      - ctx: AIContext (assembled once, shared across all tools in a session)
      - input: dict[str, Any] (validated against manifest.input_schema)

    Returns:
      - dict[str, Any] (validated against manifest.output_schema)

    Tools must NOT:
      - Call other tools (Constitution Rule 2)
      - Ask for approval (Constitution Rule 11 — Runtime decides)
      - Write to memory directly (Constitution Rule 10 — Runtime owns memory)
      - Emit events directly (Constitution Rule 8 — Executor emits events on behalf)

    Tools MAY:
      - Read from DB via ctx.session
      - Call external APIs (adapters, AI gateway)
      - Raise exceptions (Executor handles retries)
    """

    manifest: ToolManifest

    async def __call__(
        self,
        ctx: "AIContext",
        input: dict[str, Any],
    ) -> dict[str, Any]:
        ...


# ─── Tool Wrapper (concrete implementation) ─────────────────────────────────


@dataclass
class ToolEntry:
    """Internal registry entry — wraps a callable with its manifest."""

    manifest: ToolManifest
    func: Callable[..., Awaitable[dict[str, Any]]]

    async def __call__(
        self,
        ctx: "AIContext",
        input: dict[str, Any],
    ) -> dict[str, Any]:
        return await self.func(ctx, input)


# ─── Tool Registry ──────────────────────────────────────────────────────────


class ToolRegistry:
    """Global registry of all available tools.

    The Planner queries this to discover capabilities.
    New tools are added via ``register_tool`` — no hardcoded mappings.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolEntry] = {}

    def register(
        self,
        manifest: ToolManifest,
        func: Callable[..., Awaitable[dict[str, Any]]],
    ) -> None:
        if manifest.name in self._tools:
            log.warning("overwriting existing tool: %s", manifest.name)
        self._tools[manifest.name] = ToolEntry(manifest=manifest, func=func)
        log.info("registered tool: %s (%s)", manifest.name, manifest.display_name)
        # Phase E1.2: also register with the health registry
        from .health import get_health_registry
        get_health_registry().register(manifest.name)

    def get(self, name: str) -> ToolEntry | None:
        return self._tools.get(name)

    def list(self) -> list[ToolManifest]:
        """All registered manifests — used by the Planner."""
        return [entry.manifest for entry in self._tools.values()]

    def list_healthy(self) -> list[ToolManifest]:
        """Return manifests for tools that are fully healthy (Phase E1.2)."""
        from .health import get_health_registry
        health = get_health_registry()
        return [
            entry.manifest for name, entry in self._tools.items()
            if health.get(name).is_healthy
        ]

    def list_available(self) -> list[ToolManifest]:
        """Return manifests for tools that are not offline (Phase E1.2)."""
        from .health import get_health_registry
        health = get_health_registry()
        return [
            entry.manifest for name, entry in self._tools.items()
            if health.get(name).is_available
        ]

    def list_for_prompt(self, only_healthy: bool = False) -> str:
        """Format manifests as a text block for the Planner LLM prompt.

        Phase E1.2: If ``only_healthy`` is True, exclude offline tools
        (and degraded tools, since the planner should prefer alternatives).
        """
        if only_healthy:
            manifests = self.list_healthy()
        else:
            manifests = self.list()
        lines: list[str] = []
        for m in manifests:
            latency_s = m.estimated_latency_ms / 1000.0
            lines.append(
                f"- {m.name}: {m.description} "
                f"(cost: ${m.estimated_cost_usd:.2f}, latency: {latency_s:.0f}s, "
                f"quality: {m.quality_score:.2f}, "
                f"category={m.category.value}, "
                f"approval={m.requires_user_approval}, "
                f"streaming={m.supports_streaming})"
            )
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


# ─── Global registry singleton ──────────────────────────────────────────────


_global_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """Get the global tool registry (lazy singleton)."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def register_tool(manifest: ToolManifest) -> Callable:
    """Decorator to register a function as a tool.

    Usage::

        @register_tool(ToolManifest(
            name="campaign_brain.analyse",
            display_name="Business Analysis",
            ...
        ))
        async def campaign_brain_analyse(ctx: AIContext, input: dict) -> dict:
            ...
    """

    def decorator(func: Callable[..., Awaitable[dict[str, Any]]]) -> Callable[..., Awaitable[dict[str, Any]]]:
        get_registry().register(manifest, func)
        return func

    return decorator
