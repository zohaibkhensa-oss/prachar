"""AI Context Object — assembled once, passed to every tool.

Constitution Rule: No tool re-queries everything. The Runtime assembles context
once (in parallel) and passes it to every tool in the execution graph.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from .registry import ToolRegistry

from ..models import (
    Billing,
    Brand,
    BusinessMemoryRecord,
    Connection,
    CampaignPlanRecord,
    User,
    Tenant,
)
from .memory_categories import MemoryCategory, MemoryEntry, MemoryStore

log = logging.getLogger("prachar.runtime.context")


# ─── Data classes ───────────────────────────────────────────────────────────


@dataclass
class BrandInfo:
    """Brand snapshot — loaded from Brand table."""

    id: uuid.UUID
    name: str
    website: str | None
    category: str | None
    customer_type: str
    locales: list[str]
    tone: dict[str, Any] | None
    visibility_score: float | None


@dataclass
class BillingInfo:
    """Billing snapshot — loaded from Billing + Tenant tables."""

    plan: str
    ai_tokens_used: int
    ai_budget: int
    videos_used: int = 0
    videos_limit: int = 5
    images_used: int = 0
    images_limit: int = 50


@dataclass
class ConnectionInfo:
    """Channel connection status."""

    channel: str
    status: str


@dataclass
class MemoryInfo:
    """Business memory snapshot — loaded from BusinessMemoryRecord."""

    best_practices: list[str] = field(default_factory=list)
    audience_insights: list[str] = field(default_factory=list)
    creative_insights: list[str] = field(default_factory=list)
    channel_insights: list[str] = field(default_factory=list)
    total_campaigns: int = 0
    average_roi: str = "—"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationMessage:
    """Single message in conversation history."""

    role: str  # "user" or "ai"
    content: str
    timestamp: str = ""


@dataclass
class ActiveTask:
    """Currently running background task."""

    task_id: str
    task_type: str
    status: str
    started_at: str = ""


@dataclass
class TimelineSummary:
    """Recent timeline entries (for context)."""

    recent: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class UserPreferences:
    """User preferences (defaults for now; persisted later)."""

    locale: str = "en-IN"
    voice_enabled: bool = True
    auto_approve_threshold: float = 8.0  # council score above which auto-approve
    notification_channels: list[str] = field(default_factory=lambda: ["in_app"])


@dataclass
class Permissions:
    """What the user can do."""

    role: str
    can_approve: bool = True
    can_publish: bool = True
    can_manage_billing: bool = False


@dataclass
class AIContext:
    """The single context object passed to every tool in a session.

    Assembled once at request start via ``assemble_context``.
    Stored in the Decision Contract as ``context_snapshot``.
    """

    # Identity
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    brand_id: uuid.UUID

    # Brand
    brand: BrandInfo | None = None

    # Active campaign (optional — set if user is viewing a specific campaign)
    campaign: dict[str, Any] | None = None

    # Workspace
    workspace: TimelineSummary = field(default_factory=TimelineSummary)
    active_tasks: list[ActiveTask] = field(default_factory=list)

    # Conversation
    conversation: list[ConversationMessage] = field(default_factory=list)

    # Memory (E1.1: categorised MemoryStore; MemoryInfo kept for compat)
    memory: MemoryStore = field(default_factory=MemoryStore)

    # Permissions
    permissions: Permissions = field(default_factory=lambda: Permissions(role="member"))

    # Billing
    billing: BillingInfo = field(default_factory=lambda: BillingInfo(plan="starter", ai_tokens_used=0, ai_budget=50000))

    # Connected channels
    connected_channels: list[ConnectionInfo] = field(default_factory=list)

    # User preferences
    user_preferences: UserPreferences = field(default_factory=UserPreferences)

    # Enriched context (from Context Builder — adaptive per-message)
    enriched: dict[str, Any] = field(default_factory=dict)
    capabilities: list[dict[str, Any]] = field(default_factory=list)
    knowledge_chunks: list[dict[str, Any]] = field(default_factory=list)
    # Ranked prompt context (from Context Ranking Layer — scored + trimmed by token budget)
    prompt_context: str = ""

    # DB session (for tools that need to query — most won't, context has what they need)
    session: AsyncSession | None = None

    def to_snapshot(self) -> dict[str, Any]:
        """Serialise for storage in Decision Contract (no session)."""
        return {
            "tenant_id": str(self.tenant_id),
            "user_id": str(self.user_id),
            "brand_id": str(self.brand_id),
            "brand": {
                "name": self.brand.name if self.brand else None,
                "category": self.brand.category if self.brand else None,
                "customer_type": self.brand.customer_type if self.brand else None,
                "visibility_score": self.brand.visibility_score if self.brand else None,
            } if self.brand else None,
            "memory": {
                "total_campaigns": self.memory.total_campaigns,
                "average_roi": self.memory.average_roi,
                "best_practices_count": len(self.memory.best_practices),
                "categories": self.memory.counts_by_category(),
            },
            "billing": {
                "plan": self.billing.plan,
                "ai_tokens_used": self.billing.ai_tokens_used,
                "ai_budget": self.billing.ai_budget,
            },
            "permissions": {
                "role": self.permissions.role,
                "can_approve": self.permissions.can_approve,
                "can_publish": self.permissions.can_publish,
            },
            "connected_channels": [
                {"channel": c.channel, "status": c.status} for c in self.connected_channels
            ],
            "conversation_length": len(self.conversation),
            "enriched": {
                "providers_used": list(self.enriched.keys()),
                "knowledge_chunk_count": len(self.knowledge_chunks),
                "capability_count": len(self.capabilities),
                "prompt_context_tokens": len(self.prompt_context) // 4,
            },
        }

    def get_memory_for_tool(
        self,
        tool_name: str,
        registry: ToolRegistry,
    ) -> list[MemoryEntry]:
        """Return only the memory entries relevant to a given tool.

        Looks up the tool's manifest and returns entries from the categories
        declared in ``manifest.memory_categories``. An empty list means
        "all categories" (backward compatible).
        """
        entry = registry.get(tool_name)
        if entry is None:
            # Unknown tool — return all memory (safe default)
            return self.memory.all()
        categories = entry.manifest.memory_categories
        return self.memory.get_for_categories(list(categories))


# ─── Assembler ──────────────────────────────────────────────────────────────


async def assemble_context(
    session: AsyncSession,
    user: User,
    brand_id: uuid.UUID,
    message: str = "",
    current_campaign_id: uuid.UUID | None = None,
) -> AIContext:
    """Assemble the AI Context in parallel — one round of queries.

    This is the ONLY place that queries brand, memory, billing, connections.
    Tools receive the assembled context and don't re-query.
    """
    ctx = AIContext(
        tenant_id=user.tenant_id,
        user_id=user.id,
        brand_id=brand_id,
        session=session,
    )

    # Run all queries in parallel
    brand_result, memory_result, billing_result, connections_result, tenant_result = await asyncio.gather(
        _load_brand(session, brand_id),
        _load_memory(session, brand_id),
        _load_billing(session, user.tenant_id),
        _load_connections(session, brand_id),
        _load_tenant(session, user.tenant_id),
        return_exceptions=True,
    )

    # Apply results (tolerate individual failures)
    if isinstance(brand_result, BrandInfo):
        ctx.brand = brand_result
    elif isinstance(brand_result, Exception):
        log.warning("failed to load brand %s: %s", brand_id, brand_result)

    if isinstance(memory_result, MemoryStore):
        ctx.memory = memory_result
    elif isinstance(memory_result, MemoryInfo):
        # Legacy loader returned a MemoryInfo — convert to MemoryStore
        ctx.memory = MemoryStore.from_memory_info(memory_result)
    elif isinstance(memory_result, Exception):
        log.warning("failed to load memory: %s", memory_result)

    if isinstance(billing_result, BillingInfo):
        ctx.billing = billing_result
    elif isinstance(billing_result, Exception):
        log.warning("failed to load billing: %s", billing_result)

    if isinstance(connections_result, list):
        ctx.connected_channels = connections_result
    elif isinstance(connections_result, Exception):
        log.warning("failed to load connections: %s", connections_result)

    # Permissions from tenant + user role
    plan = "starter"
    if isinstance(tenant_result, Tenant):
        plan = str(tenant_result.plan)
    ctx.billing.plan = plan
    ctx.permissions = Permissions(
        role=str(user.role),
        can_approve=str(user.role) in ("owner", "admin", "member"),
        can_publish=str(user.role) in ("owner", "admin"),
        can_manage_billing=str(user.role) in ("owner", "admin"),
    )

    # Current message goes into conversation
    if message:
        ctx.conversation.append(ConversationMessage(
            role="user",
            content=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

    # Load active campaign if specified
    if current_campaign_id:
        campaign = await _load_campaign(session, current_campaign_id)
        if campaign:
            ctx.campaign = campaign

    return ctx


# ─── Loaders (each runs in parallel) ────────────────────────────────────────


async def _load_brand(session: AsyncSession, brand_id: uuid.UUID) -> BrandInfo:
    res = await session.execute(select(Brand).where(Brand.id == brand_id))
    brand = res.scalar_one_or_none()
    if brand is None:
        raise ValueError(f"brand {brand_id} not found")
    return BrandInfo(
        id=brand.id,
        name=brand.name,
        website=brand.website,
        category=brand.category,
        customer_type=brand.customer_type,
        locales=list(brand.locales) if brand.locales else [],
        tone=brand.tone,
        visibility_score=brand.visibility_score,
    )


async def _load_memory(session: AsyncSession, brand_id: uuid.UUID) -> MemoryStore:
    """Load business memory and categorise it into the 7 memory classes.

    The legacy ``BusinessMemoryRecord.memory`` JSON stores flat lists
    (best_practices, audience_insights, creative_insights, channel_insights)
    plus a ``metadata`` block. These are mapped to the new categories:
      - best_practices   → CAMPAIGN
      - audience_insights → AUDIENCE
      - creative_insights → CREATIVE
      - channel_insights  → PERFORMANCE
    Scalar metadata (total_campaigns, average_roi) is preserved on the store.
    """
    res = await session.execute(
        select(BusinessMemoryRecord).where(BusinessMemoryRecord.brand_id == brand_id)
    )
    record = res.scalar_one_or_none()
    if record is None:
        return MemoryStore()
    memory = record.memory or {}
    return MemoryStore.from_raw_dict(memory)


async def _load_billing(session: AsyncSession, tenant_id: uuid.UUID) -> BillingInfo:
    res = await session.execute(select(Billing).where(Billing.tenant_id == tenant_id))
    billing = res.scalar_one_or_none()
    if billing is None:
        return BillingInfo(plan="starter", ai_tokens_used=0, ai_budget=50000)
    return BillingInfo(
        plan="starter",  # plan comes from tenant, not billing
        ai_tokens_used=int(billing.ai_tokens_used_month or 0),
        ai_budget=int(billing.ai_budget_month or 50000),
    )


async def _load_connections(session: AsyncSession, brand_id: uuid.UUID) -> list[ConnectionInfo]:
    res = await session.execute(
        select(Connection).where(Connection.brand_id == brand_id)
    )
    connections = res.scalars().all()
    return [
        ConnectionInfo(channel=str(c.channel), status=str(c.status))
        for c in connections
    ]


async def _load_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
    res = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    return res.scalar_one_or_none()


async def _load_campaign(session: AsyncSession, campaign_id: uuid.UUID) -> dict[str, Any] | None:
    res = await session.execute(
        select(CampaignPlanRecord).where(CampaignPlanRecord.id == campaign_id)
    )
    plan = res.scalar_one_or_none()
    if plan is None:
        return None
    return {
        "id": str(plan.id),
        "name": plan.name,
        "goal": plan.goal,
        "status": plan.status,
        "budget": plan.budget or "",
    }
