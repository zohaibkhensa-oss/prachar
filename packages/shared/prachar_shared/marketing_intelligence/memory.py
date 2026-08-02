"""Business Memory Store.

Every workspace stores accumulated knowledge: industry, brand voice, tone,
fonts, logo, colours, campaign history, successful/failed campaigns,
preferred platforms, budget preference, language preference, seasonal events.

This memory persists across campaigns and informs future strategy.
The Learning Engine updates this memory after each campaign.

Phase 6: Architecture Stabilisation — the store now depends on the
MemoryRepository protocol (defined in repository.py), not on the API app's
SQLAlchemy models. This inverts the dependency: the shared package defines
the interface, the API app provides the implementation.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from .repository import InMemoryRepository, MemoryRepository

logger = logging.getLogger(__name__)


@dataclass
class BusinessMemory:
    """Persistent business memory for a workspace.

    Stored in the `business_memory` table as a JSONB column. Updated
    after every campaign via the Learning Engine.
    """

    # Brand identity
    industry: str = ""
    brand_voice: str = ""
    tone: str = ""
    fonts: list[str] = field(default_factory=list)
    logo_url: str = ""
    colours: list[dict[str, str]] = field(default_factory=list)

    # Campaign history (summary references)
    campaign_history: list[dict[str, Any]] = field(default_factory=list)
    successful_campaigns: list[dict[str, Any]] = field(default_factory=list)
    failed_campaigns: list[dict[str, Any]] = field(default_factory=list)

    # Preferences learned over time
    preferred_platforms: list[str] = field(default_factory=list)
    budget_preference: str = ""
    language_preference: list[str] = field(default_factory=list)
    seasonal_events: list[dict[str, Any]] = field(default_factory=list)

    # Accumulated best practices (from Learning Engine)
    best_practices: list[str] = field(default_factory=list)
    audience_insights: list[str] = field(default_factory=list)
    creative_insights: list[str] = field(default_factory=list)
    channel_insights: list[str] = field(default_factory=list)

    # Performance learnings (P4.6 feedback loop) — one entry per past campaign.
    # Each entry is a dict: {campaign_id, summary, top_performing_hook, roas,
    # ctr, key_insight}. Used by CampaignBrain to inform future generation.
    performance_learnings: list[dict[str, Any]] = field(default_factory=list)

    # Metadata
    last_campaign_at: str = ""
    total_campaigns: int = 0
    average_roi: float = 0.0
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> BusinessMemory:
        if not data:
            return cls()
        # Filter to known fields to avoid errors on schema evolution
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


class BusinessMemoryStore:
    """Reads and writes BusinessMemory via a MemoryRepository.

    Phase 6: Depends on the MemoryRepository protocol, not on SQLAlchemy
    models. The repository implementation is injected via the constructor.
    This ensures the shared package never imports from the API app.

    Usage:
        # In the API app (infrastructure layer):
        from prachar_api.infrastructure import PostgresMemoryRepository
        store = BusinessMemoryStore(repository=PostgresMemoryRepository(session))

        # In tests / stub mode:
        store = BusinessMemoryStore()  # uses InMemoryRepository
    """

    def __init__(self, repository: MemoryRepository | None = None) -> None:
        """Initialize with an optional MemoryRepository.

        If no repository is provided, an InMemoryRepository is used
        (useful for tests and stub mode).
        """
        self._repository = repository or InMemoryRepository()

    async def get(self, tenant_id: uuid.UUID, brand_id: uuid.UUID) -> BusinessMemory:
        """Read the business memory for a brand. Returns empty memory if not found."""
        try:
            data = await self._repository.get(tenant_id, brand_id)
            return BusinessMemory.from_dict(data)
        except Exception as exc:
            logger.warning("failed to read business memory: %s", exc)
            return BusinessMemory()

    async def save(
        self,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        memory: BusinessMemory,
    ) -> None:
        """Save (upsert) the business memory for a brand."""
        memory.updated_at = datetime.now(UTC).isoformat()
        try:
            await self._repository.save(tenant_id, brand_id, memory.to_dict())
        except Exception as exc:
            logger.warning("failed to save business memory: %s", exc)

    def update_from_learning(self, memory: BusinessMemory, report: Any) -> BusinessMemory:
        """Update memory in-place from a LearningReport.

        Args:
            memory: The current memory (mutated in place).
            report: A LearningReport dataclass or dict.

        Returns:
            The updated memory (same object, mutated).
        """
        # Accept either a LearningReport dataclass or a dict
        if hasattr(report, "to_dict"):
            report_data = report.to_dict()
        elif isinstance(report, dict):
            report_data = report
        else:
            return memory

        # Update best practices
        new_practices = report_data.get("updated_best_practices", [])
        for practice in new_practices:
            if practice and practice not in memory.best_practices:
                memory.best_practices.append(practice)
        # Cap at 50 to prevent unbounded growth
        memory.best_practices = memory.best_practices[-50:]

        # Update insights
        for insight in report_data.get("audience_insights", {}).get("surprising_findings", []):
            if insight and insight not in memory.audience_insights:
                memory.audience_insights.append(insight)
        memory.audience_insights = memory.audience_insights[-30:]

        for pattern in report_data.get("creative_insights", {}).get("patterns", []):
            if pattern and pattern not in memory.creative_insights:
                memory.creative_insights.append(pattern)
        memory.creative_insights = memory.creative_insights[-30:]

        for ch in report_data.get("channel_insights", {}).get("best_roi_channels", []):
            if ch and ch not in memory.channel_insights:
                memory.channel_insights.append(ch)
        memory.channel_insights = memory.channel_insights[-20:]

        # Update campaign counters
        memory.total_campaigns += 1
        memory.last_campaign_at = datetime.now(UTC).isoformat()

        # Update average ROI if available
        perf = report_data.get("performance_summary", {})
        grade = perf.get("overall_grade", "")
        if grade and grade not in memory.campaign_history[-1:] if memory.campaign_history else True:
            memory.campaign_history.append(
                {
                    "grade": grade,
                    "headline": perf.get("headline_finding", ""),
                    "timestamp": memory.last_campaign_at,
                }
            )
        memory.campaign_history = memory.campaign_history[-20:]

        return memory

    def to_prompt_context(self, memory: BusinessMemory) -> str:
        """Serialize memory into a prompt context string for engines."""
        if not memory.industry and not memory.best_practices:
            return ""
        parts: list[str] = []
        if memory.industry:
            parts.append(f"Industry: {memory.industry}")
        if memory.brand_voice:
            parts.append(f"Brand Voice: {memory.brand_voice}")
        if memory.tone:
            parts.append(f"Tone: {memory.tone}")
        if memory.preferred_platforms:
            parts.append(f"Preferred Platforms: {', '.join(memory.preferred_platforms)}")
        if memory.best_practices:
            parts.append("Best Practices Learned:")
            for bp in memory.best_practices[-10:]:
                parts.append(f"  - {bp}")
        if memory.audience_insights:
            parts.append("Audience Insights:")
            for ai in memory.audience_insights[-5:]:
                parts.append(f"  - {ai}")
        if memory.creative_insights:
            parts.append("Creative Insights:")
            for ci in memory.creative_insights[-5:]:
                parts.append(f"  - {ci}")
        if memory.successful_campaigns:
            parts.append(f"Successful Campaigns: {len(memory.successful_campaigns)}")
        if memory.failed_campaigns:
            parts.append(f"Failed Campaigns: {len(memory.failed_campaigns)}")
        return "\n".join(parts)

    # ─── Performance learnings (P4.6 feedback loop) ─────────────────────────

    async def store_performance_learning(
        self,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        campaign_id: str,
        learning: dict[str, Any],
    ) -> None:
        """Store a performance learning for a brand's past campaign.

        A learning is a dict with keys: {campaign_id, summary,
        top_performing_hook, roas, ctr, key_insight}. The learning is
        appended to the brand's ``performance_learnings`` list (capped at
        20 entries) and persisted via the repository.

        Args:
            tenant_id: Workspace ID.
            brand_id: Brand ID.
            campaign_id: The campaign these learnings come from.
            learning: The learning dict. ``campaign_id`` is set/overridden
                from the ``campaign_id`` argument if missing.
        """
        entry = dict(learning)
        entry["campaign_id"] = entry.get("campaign_id") or str(campaign_id)
        try:
            memory = await self.get(tenant_id, brand_id)
            memory.performance_learnings.append(entry)
            # Cap at 20 most-recent entries to keep prompts concise.
            memory.performance_learnings = memory.performance_learnings[-20:]
            await self.save(tenant_id, brand_id, memory)
        except Exception as exc:
            logger.warning("failed to store performance learning: %s", exc)

    async def get_performance_learnings(
        self,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve the most recent performance learnings for a brand.

        Returns an empty list if no learnings are stored or on error —
        callers (CampaignBrain) should proceed gracefully when empty.
        """
        try:
            memory = await self.get(tenant_id, brand_id)
            learnings = memory.performance_learnings or []
            # Most-recent first.
            return list(reversed(learnings))[:limit]
        except Exception as exc:
            logger.warning("failed to read performance learnings: %s", exc)
            return []

    @staticmethod
    def to_performance_context(learnings: list[dict[str, Any]]) -> str:
        """Format performance learnings into a concise prompt context string.

        Returns an empty string when there are no learnings so that
        CampaignBrain can append it unconditionally.
        """
        if not learnings:
            return ""
        lines: list[str] = ["Past campaign performance:"]
        for i, lg in enumerate(learnings, start=1):
            label = f"Campaign {chr(ord('A') + i - 1)}"
            roas = lg.get("roas")
            hook = lg.get("top_performing_hook") or lg.get("summary") or ""
            insight = lg.get("key_insight") or ""
            roas_str = f"{roas}x ROAS" if roas else "unknown ROAS"
            hook_str = f" with {hook}" if hook else ""
            line = f"{label} achieved {roas_str}{hook_str}."
            if insight:
                line += f" Key insight: {insight}."
            lines.append(f"  - {line}")
        lines.append("Learn from this.")
        return "\n".join(lines)
