"""Adaptive Context Builder — decides what the Orb needs to know per conversation.

ARCHITECTURE
============

    User message
        ↓
    Context Builder
        ↓
    ┌──────────────────────────────────────┐
    │  ALWAYS LOADED (base context)        │
    │  • Brand info                        │
    │  • Business memory                   │
    │  • Billing + permissions             │
    │  • Connected channels                │
    │  • Capabilities (dynamic)            │
    └──────────────────────────────────────┘
        ↓
    ┌──────────────────────────────────────┐
    │  ADAPTIVE (loaded based on message)  │
    │  • Knowledge Hub search              │
    │  • Marketing Intelligence summaries  │
    │  • Agency Council memory             │
    │  • Integrations status               │
    │  • Performance + attribution         │
    │  • Review queue                      │
    │  • Domain pack                       │
    └──────────────────────────────────────┘
        ↓
    Enriched AIContext → Planner → Orb

The Context Builder keeps prompts focused and scalable. Instead of injecting
all 30+ database models into every conversation, it loads only what's relevant.

Example:
    User: "Create a Diwali campaign"
    → Context includes: Brand, Audience, Strategy, Products, Previous campaigns, Knowledge
    → No need for billing or webhook state.

    User: "Why did ROAS drop?"
    → Context includes: GA4, Attribution, CampaignPerformance, Council recommendations
    → No need for Brand Guidelines.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from .context import (
    AIContext,
    BrandInfo,
    BillingInfo,
    ConnectionInfo,
    MemoryStore,
    UserPreferences,
    Permissions,
    assemble_context,
)
from .context_ranking import (
    ContextItem,
    ContextItemExtractor,
    ContextRankingLayer,
    ContextTrace,
    ProviderTrace,
    RankedEnrichedContext,
    estimate_tokens,
    estimate_dict_tokens,
)

log = logging.getLogger("prachar.runtime.context_builder")


# ─── Context Provider Protocol ──────────────────────────────────────────────


@runtime_checkable
class ContextProvider(Protocol):
    """A provider that loads specific context data when relevant.

    Each provider:
    1. Declares what keywords/intents trigger it (is_relevant)
    2. Loads its data asynchronously (load)
    3. Returns a dict that gets merged into the AIContext's `enriched` field
    """

    name: str

    def is_relevant(self, message: str, intent: str = "") -> bool:
        """Should this provider's data be loaded for this message?"""
        ...

    async def load(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        message: str,
    ) -> dict[str, Any]:
        """Load the context data. Returns a dict to merge into enriched context."""
        ...


# ─── Enriched Context ───────────────────────────────────────────────────────


@dataclass
class EnrichedContext:
    """Wraps AIContext with adaptive enrichment from providers.

    The `enriched` dict holds data loaded by context providers.
    The `capabilities` list holds dynamically-discovered capabilities.
    The `knowledge_chunks` list holds retrieved knowledge for grounding.
    """

    base: AIContext
    enriched: dict[str, Any] = field(default_factory=dict)
    capabilities: list[dict[str, Any]] = field(default_factory=list)
    knowledge_chunks: list[dict[str, Any]] = field(default_factory=list)
    providers_used: list[str] = field(default_factory=list)

    @property
    def session(self) -> AsyncSession | None:
        return self.base.session

    def to_prompt_context(self) -> str:
        """Build a context string for injection into the LLM prompt.

        This is what makes the Orb "aware" of the user's business.
        Only includes data that was actually loaded (adaptive).
        """
        parts: list[str] = []

        # Brand info (always)
        if self.base.brand:
            parts.append(f"Brand: {self.base.brand.name} ({self.base.brand.category or 'unknown'})")

        # Capabilities (always — dynamic discovery)
        if self.capabilities:
            caps = [f"✓ {c['name']}" for c in self.capabilities if c.get("available")]
            if caps:
                parts.append(f"Available capabilities: {', '.join(caps)}")

        # Knowledge Hub results (if loaded)
        if self.knowledge_chunks:
            knowledge_text = "\n".join(
                f"  - [{c.get('title', 'Unknown')}]: {c.get('content', '')[:200]}"
                for c in self.knowledge_chunks[:5]
            )
            parts.append(f"Retrieved knowledge:\n{knowledge_text}")

        # Marketing Intelligence summaries (if loaded)
        mi = self.enriched.get("marketing_intelligence")
        if mi:
            if mi.get("business_profile"):
                bp = mi["business_profile"]
                parts.append(f"Business profile: {bp.get('summary', '')[:200]}")
            if mi.get("audience_profile"):
                ap = mi["audience_profile"]
                parts.append(f"Audience: {ap.get('summary', '')[:200]}")
            if mi.get("competitor_profile"):
                cp = mi["competitor_profile"]
                parts.append(f"Competitors: {cp.get('summary', '')[:200]}")
            if mi.get("strategy"):
                parts.append(f"Strategy: {mi['strategy'].get('summary', '')[:200]}")

        # Agency Council memory (if loaded)
        council = self.enriched.get("council_memory")
        if council:
            decisions = council.get("recent_decisions", [])
            if decisions:
                dec_text = "; ".join(
                    f"{d.get('campaign', 'unknown')}: {d.get('decision', '')}"
                    for d in decisions[:3]
                )
                parts.append(f"Recent council decisions: {dec_text}")

        # Integrations (if loaded)
        integrations = self.enriched.get("integrations")
        if integrations:
            connected = integrations.get("connected", [])
            if connected:
                int_text = ", ".join(f"{i['name']} ({i.get('status', 'unknown')})" for i in connected)
                parts.append(f"Connected integrations: {int_text}")
            # Integration data summaries
            for int_data in connected:
                if int_data.get("summary"):
                    parts.append(f"{int_data['name']} data: {int_data['summary'][:150]}")

        # Performance + attribution (if loaded)
        perf = self.enriched.get("performance")
        if perf:
            if perf.get("campaign_performance"):
                cp = perf["campaign_performance"]
                parts.append(f"Performance: {cp.get('summary', '')[:200]}")
            if perf.get("attribution"):
                attr = perf["attribution"]
                parts.append(f"Attribution: {attr.get('summary', '')[:200]}")

        # Review queue (if loaded)
        reviews = self.enriched.get("reviews")
        if reviews:
            pending = reviews.get("pending_count", 0)
            if pending > 0:
                parts.append(f"Pending reviews: {pending} campaign(s) awaiting approval")

        # Domain pack (if loaded)
        domain = self.enriched.get("domain_pack")
        if domain:
            parts.append(f"Industry expertise: {domain.get('name', '')} pack active")

        # Memory (always — but summarised)
        if self.base.memory.best_practices:
            parts.append(f"Past learnings: {', '.join(self.base.memory.best_practices[:3])}")

        return "\n".join(parts) if parts else ""

    def to_snapshot(self) -> dict[str, Any]:
        """Serialise for decision contract storage."""
        return {
            "base": self.base.to_snapshot(),
            "providers_used": self.providers_used,
            "capabilities": self.capabilities,
            "knowledge_chunk_count": len(self.knowledge_chunks),
            "enriched_keys": list(self.enriched.keys()),
        }


# ─── Context Builder ────────────────────────────────────────────────────────


class ContextBuilder:
    """Adaptive context builder — the Orb's intelligence layer.

    Replaces the flat `assemble_context()` with an adaptive system that:
    1. Always loads base context (brand, memory, billing, connections, capabilities)
    2. Classifies what additional context is needed based on the message
    3. Loads relevant providers in parallel
    4. Returns an EnrichedContext with everything the Orb needs

    Usage:
        builder = ContextBuilder(providers=[...])
        ctx = await builder.build(session, user, brand_id, message="Create a Diwali campaign")
        prompt_context = ctx.to_prompt_context()  # Inject into LLM prompt
    """

    def __init__(
        self,
        providers: list[ContextProvider] | None = None,
        ranking_layer: ContextRankingLayer | None = None,
    ) -> None:
        self._providers: list[ContextProvider] = providers or []
        # Always-on providers (loaded for every message)
        self._always_on: set[str] = {"capabilities"}
        # Ranking layer (scores and trims context items by token budget)
        self._ranking = ranking_layer or ContextRankingLayer()

    def register(self, provider: ContextProvider) -> None:
        """Register a context provider."""
        self._providers.append(provider)
        log.debug("Registered context provider: %s", provider.name)

    def register_many(self, providers: list[ContextProvider]) -> None:
        """Register multiple providers."""
        for p in providers:
            self.register(p)

    async def build(
        self,
        session: AsyncSession,
        user: Any,  # User model
        brand_id: uuid.UUID,
        message: str = "",
        intent: str = "",
        current_campaign_id: uuid.UUID | None = None,
    ) -> RankedEnrichedContext:
        """Build enriched context for a conversation turn.

        Pipeline:
        1. Load base context (always — brand, memory, billing, connections)
        2. Determine which providers are relevant (adaptive)
        3. Load relevant providers in parallel
        4. Extract ContextItems from each provider's data
        5. Score and rank items (Context Ranking Layer)
        6. Trim to token budget (keep highest-value items)
        7. Build final prompt context string
        8. Emit trace (observability)

        Returns a RankedEnrichedContext with:
        - base AIContext (for tools)
        - enriched data (for tools that need raw provider data)
        - ranked_items (with scores and kept/trimmed status)
        - trace (full observability)
        - prompt_context (final ranked string for LLM prompt)
        """
        trace = ContextTrace(message=message, intent=intent, token_budget=self._ranking.token_budget)
        trace.mark_start()

        # Step 1: Load base context (existing assemble_context)
        base_ctx = await assemble_context(
            session=session,
            user=user,
            brand_id=brand_id,
            message=message,
            current_campaign_id=current_campaign_id,
        )

        # Step 2: Determine relevant providers
        relevant_providers: list[ContextProvider] = []
        for provider in self._providers:
            try:
                if provider.name in self._always_on or provider.is_relevant(message, intent):
                    relevant_providers.append(provider)
                else:
                    trace.add_skipped(provider.name, reason="not relevant to message")
            except Exception as e:
                log.warning("Provider %s.is_relevant failed: %s", provider.name, e)
                trace.add_skipped(provider.name, reason=f"error: {e}")

        # Step 3: Load all relevant providers in parallel
        async def _safe_load(provider: ContextProvider) -> tuple[str, dict[str, Any], float]:
            start = time.time()
            try:
                data = await provider.load(
                    session=session,
                    tenant_id=user.tenant_id,
                    brand_id=brand_id,
                    message=message,
                )
                elapsed = (time.time() - start) * 1000
                return provider.name, data, elapsed
            except Exception as e:
                elapsed = (time.time() - start) * 1000
                log.warning("Provider %s.load failed: %s", provider.name, e)
                return provider.name, {}, elapsed

        results = await asyncio.gather(
            *[_safe_load(p) for p in relevant_providers],
            return_exceptions=False,
        )

        # Step 4: Merge results and extract ContextItems
        all_items: list[ContextItem] = []
        enriched_data: dict[str, Any] = {}
        providers_used: list[str] = []
        capabilities: list[dict[str, Any]] = []
        knowledge_chunks: list[dict[str, Any]] = []

        for provider_name, data, load_time_ms in results:
            if not data:
                trace.add_skipped(provider_name, reason="no data returned")
                continue

            enriched_data[provider_name] = data
            providers_used.append(provider_name)

            # Route specific provider data to structured fields
            if provider_name == "knowledge":
                knowledge_chunks = data.get("chunks", [])
            elif provider_name == "capabilities":
                capabilities = data.get("capabilities", [])

            # Extract context items for ranking
            items = ContextItemExtractor.extract(provider_name, data)
            all_items.extend(items)

            # Record provider trace
            items_tokens = sum(i.tokens for i in items)
            trace.add_activated(ProviderTrace(
                name=provider_name,
                activated=True,
                items_loaded=len(items),
                tokens_estimated=items_tokens,
                load_time_ms=load_time_ms,
            ))

        # Step 5: Add base context items (brand + memory — always present)
        base_items = ContextItemExtractor.extract_base_context(base_ctx.brand, base_ctx.memory)
        all_items.extend(base_items)

        # Step 6: Score and rank items
        ranked_items = self._ranking.rank(all_items, message=message, intent=intent)

        # Step 7: Build final prompt context from kept items
        kept_items = [i for i in ranked_items if i.kept]
        prompt_parts: list[str] = []
        for item in kept_items:
            prompt_parts.append(f"[{item.title}] (score: {item.score:.2f})\n{item.content}")
        prompt_context = "\n\n".join(prompt_parts) if prompt_parts else ""

        # Calculate final token count
        final_tokens = sum(i.tokens for i in kept_items)
        trace.record_ranking(ranked_items, final_tokens)

        # Step 8: Build the result
        result = RankedEnrichedContext(
            base=base_ctx,
            enriched=enriched_data,
            capabilities=capabilities,
            knowledge_chunks=knowledge_chunks,
            providers_used=providers_used,
            ranked_items=ranked_items,
            trace=trace,
            prompt_context=prompt_context,
        )

        trace.mark_end()

        log.info(
            "Context built: %d providers, %d items (%d kept, %d trimmed), "
            "%d→%d tokens (budget %d), %.1fms",
            len(providers_used),
            len(ranked_items),
            len(kept_items),
            len(ranked_items) - len(kept_items),
            trace.estimated_prompt_tokens,
            final_tokens,
            self._ranking.token_budget,
            trace.total_build_time_ms,
        )

        return result


# ─── Keyword matching helper ────────────────────────────────────────────────


def matches_keywords(message: str, keywords: list[str]) -> bool:
    """Check if a message contains any of the keywords (case-insensitive word match)."""
    msg_lower = message.lower()
    for kw in keywords:
        kw_lower = kw.lower()
        # Word boundary match to avoid false positives
        if re.search(r'\b' + re.escape(kw_lower) + r'\b', msg_lower):
            return True
    return False


# ─── Default Provider Implementations ───────────────────────────────────────


class CapabilityProvider:
    """Always-on provider — dynamically discovers available capabilities.

    Instead of hardcoding capabilities in the system prompt, this provider
    checks what's actually connected and available, then reports it.
    """

    name = "capabilities"

    def is_relevant(self, message: str, intent: str = "") -> bool:
        return True  # Always loaded

    async def load(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        message: str,
    ) -> dict[str, Any]:
        """Discover available capabilities dynamically."""
        from sqlalchemy import select, func
        from ..models import Connection, KnowledgeSourceRecord
        from ..models.enums import KnowledgeSourceStatus, ConnectionStatus

        capabilities: list[dict[str, Any]] = []

        # Check connected channels
        try:
            res = await session.execute(
                select(Connection.channel, Connection.status).where(
                    Connection.tenant_id == tenant_id,
                    Connection.status == ConnectionStatus.active,
                )
            )
            for channel, status in res.all():
                capabilities.append({
                    "name": f"{channel} connected",
                    "available": True,
                    "category": "channel",
                })
        except Exception as e:
            log.debug("Failed to check connections: %s", e)

        # Check integrations (from knowledge_sources with source_type=integration)
        try:
            res = await session.execute(
                select(func.count()).select_from(KnowledgeSourceRecord).where(
                    KnowledgeSourceRecord.tenant_id == tenant_id,
                    KnowledgeSourceRecord.source_type == "integration",
                    KnowledgeSourceRecord.status == KnowledgeSourceStatus.ready,
                )
            )
            integration_count = res.scalar() or 0
            if integration_count > 0:
                capabilities.append({
                    "name": "Integrations connected",
                    "available": True,
                    "category": "integration",
                    "count": integration_count,
                })
        except Exception:
            pass

        # Check knowledge hub
        try:
            res = await session.execute(
                select(func.count()).select_from(KnowledgeSourceRecord).where(
                    KnowledgeSourceRecord.tenant_id == tenant_id,
                    KnowledgeSourceRecord.status == KnowledgeSourceStatus.ready,
                )
            )
            knowledge_count = res.scalar() or 0
            if knowledge_count > 0:
                capabilities.append({
                    "name": "Knowledge Hub",
                    "available": True,
                    "category": "knowledge",
                    "count": knowledge_count,
                })
        except Exception:
            pass

        # Static capabilities (always available)
        capabilities.extend([
            {"name": "Campaign Brain", "available": True, "category": "campaign"},
            {"name": "Creative Studio", "available": True, "category": "creative"},
            {"name": "Agency Council", "available": True, "category": "review"},
            {"name": "Website Builder", "available": True, "category": "tool"},
            {"name": "SEO Audit", "available": True, "category": "tool"},
            {"name": "Email Campaigns", "available": True, "category": "tool"},
            {"name": "WhatsApp Campaigns", "available": True, "category": "tool"},
            {"name": "Landing Page Builder", "available": True, "category": "tool"},
            {"name": "CRM Pipeline", "available": True, "category": "tool"},
            {"name": "Marketing Calendar", "available": True, "category": "tool"},
            {"name": "Performance Analysis", "available": True, "category": "tool"},
            {"name": "Video Generation", "available": True, "category": "tool"},
            {"name": "Brand Audit", "available": True, "category": "tool"},
        ])

        return {"capabilities": capabilities}


class KnowledgeContextProvider:
    """Searches the Knowledge Hub for relevant documents.

    Triggered when the user asks about brand, products, pricing, campaigns,
    SOPs, FAQs, or any business-specific question.
    """

    name = "knowledge"

    KNOWLEDGE_KEYWORDS = [
        "brand", "guidelines", "pricing", "price", "product", "catalogue",
        "campaign", "diwali", "festival", "sop", "process", "faq", "question",
        "policy", "policies", "logo", "colour", "color", "tone", "voice",
        "mission", "vision", "audience", "persona", "customer", "competitor",
        "strategy", "creative", "asset", "document", "knowledge", "report",
        "previous", "last year", "history", "reference", "guide", "manual",
    ]

    def is_relevant(self, message: str, intent: str = "") -> bool:
        # Always search knowledge for campaign/strategy/creative intents
        if intent in ("campaign.create", "campaign.strategy", "creative.generate",
                       "consult", "planning"):
            return True
        return matches_keywords(message, self.KNOWLEDGE_KEYWORDS)

    async def load(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        message: str,
    ) -> dict[str, Any]:
        """Search the Knowledge Hub for chunks relevant to the message."""
        from sqlalchemy import select
        from ..models import KnowledgeSourceRecord, KnowledgeChunkRecord, KnowledgeEmbeddingRecord
        from ..models.enums import KnowledgeSourceStatus
        from prachar_shared.knowledge import EmbeddingGenerator, cosine_similarity

        # Generate query embedding
        gen = EmbeddingGenerator()
        query_embedding = gen.generate(message)

        # Query chunks with embeddings
        res = await session.execute(
            select(
                KnowledgeChunkRecord,
                KnowledgeSourceRecord,
                KnowledgeEmbeddingRecord,
            ).join(
                KnowledgeSourceRecord,
                KnowledgeChunkRecord.source_id == KnowledgeSourceRecord.id,
            ).outerjoin(
                KnowledgeEmbeddingRecord,
                KnowledgeChunkRecord.id == KnowledgeEmbeddingRecord.chunk_id,
            ).where(
                KnowledgeChunkRecord.tenant_id == tenant_id,
                KnowledgeSourceRecord.status == KnowledgeSourceStatus.ready,
            ).limit(100)  # Limit to avoid loading too many
        )
        rows = res.all()

        if not rows:
            return {"chunks": []}

        # Score by cosine similarity
        scored: list[tuple[float, dict[str, Any]]] = []
        for chunk, source, embedding_rec in rows:
            if embedding_rec and embedding_rec.embedding:
                score = cosine_similarity(query_embedding, embedding_rec.embedding)
            else:
                # Fallback: simple text overlap
                msg_words = set(message.lower().split())
                chunk_words = set(chunk.content.lower().split())
                overlap = len(msg_words & chunk_words)
                score = overlap / max(len(msg_words), 1) * 0.3

            scored.append((score, {
                "chunk_id": str(chunk.id),
                "source_id": str(source.id),
                "title": source.title,
                "level": source.level,
                "content": chunk.content[:500],
                "section": chunk.section,
                "page_number": chunk.page_number,
                "score": round(score, 4),
            }))

        # Sort and take top 5
        scored.sort(key=lambda x: x[0], reverse=True)
        top_chunks = [c for s, c in scored[:5] if s > 0.01]

        return {"chunks": top_chunks}


class MarketingIntelligenceProvider:
    """Loads Marketing Intelligence engine output summaries.

    Triggered when the user asks about strategy, audience, competitors,
    or campaign planning.
    """

    name = "marketing_intelligence"

    MI_KEYWORDS = [
        "strategy", "audience", "competitor", "campaign", "plan",
        "media", "budget", "objective", "positioning", "target",
        "segment", "market", "analysis", "intelligence", "insight",
    ]

    def is_relevant(self, message: str, intent: str = "") -> bool:
        if intent in ("campaign.create", "campaign.strategy", "planning", "consult"):
            return True
        return matches_keywords(message, self.MI_KEYWORDS)

    async def load(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        message: str,
    ) -> dict[str, Any]:
        """Load recent MI engine outputs as concise summaries."""
        from sqlalchemy import select
        from ..models import (
            BusinessProfileRecord, AudienceProfileRecord,
            CompetitorProfileRecord, MarketingStrategyRecord,
            CreativeDirectionRecord, MediaPlanRecord,
        )

        result: dict[str, Any] = {}

        # Load most recent of each type
        async def _load_latest(model, label: str) -> tuple[str, dict | None]:
            try:
                res = await session.execute(
                    select(model).where(
                        model.tenant_id == tenant_id,
                        model.brand_id == brand_id,
                    ).order_by(model.created_at.desc()).limit(1)
                )
                record = res.scalar_one_or_none()
                if record:
                    return label, _summarise_mi_record(label, record)
                return label, None
            except Exception as e:
                log.debug("Failed to load %s: %s", label, e)
                return label, None

        labels = [
            ("business_profile", BusinessProfileRecord),
            ("audience_profile", AudienceProfileRecord),
            ("competitor_profile", CompetitorProfileRecord),
            ("strategy", MarketingStrategyRecord),
            ("creative_direction", CreativeDirectionRecord),
            ("media_plan", MediaPlanRecord),
        ]

        tasks = [_load_latest(model, label) for label, model in labels]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        for outcome in outcomes:
            if isinstance(outcome, tuple):
                label, data = outcome
                if data:
                    result[label] = data

        return result


def _summarise_mi_record(label: str, record: Any) -> dict[str, Any]:
    """Distil a MI engine output into a concise summary for context."""
    # All MI records have a JSONB `profile` or similar field
    raw = {}
    for attr in ("profile", "strategy", "direction", "plan", "data"):
        if hasattr(record, attr):
            raw = getattr(record, attr) or {}
            break

    summary = ""
    if label == "business_profile":
        strengths = raw.get("strengths", [])
        summary = f"Strengths: {', '.join(strengths[:3])}" if strengths else "No profile data"
    elif label == "audience_profile":
        demographics = raw.get("demographics", {})
        interests = raw.get("interests", [])
        summary = f"Demographics: {demographics}; Interests: {', '.join(interests[:3])}"
    elif label == "competitor_profile":
        competitors = raw.get("competitors", [])
        if isinstance(competitors, list) and competitors:
            summary = f"Top competitor: {competitors[0].get('name', 'unknown')}"
        else:
            summary = raw.get("summary", "No competitor data")
    elif label == "strategy":
        summary = raw.get("summary", raw.get("objective", "No strategy data"))
    elif label == "creative_direction":
        summary = raw.get("summary", raw.get("direction", "No creative direction"))
    elif label == "media_plan":
        channels = raw.get("channels", [])
        summary = f"Channels: {', '.join(channels[:5])}" if channels else "No media plan"

    return {
        "summary": summary[:300],
        "confidence": getattr(record, "confidence", 0.5),
        "created_at": record.created_at.isoformat() if hasattr(record, "created_at") else "",
    }


class CouncilMemoryProvider:
    """Loads recent Agency Council decisions and reasoning.

    Triggered when the user asks about past decisions, rejections, or
    council reviews.
    """

    name = "council_memory"

    COUNCIL_KEYWORDS = [
        "council", "director", "review", "reject", "approved", "decision",
        "why did", "last week", "previous", "score", "consensus", "opinion",
        "feedback", "critique", "evaluation",
    ]

    def is_relevant(self, message: str, intent: str = "") -> bool:
        if intent == "campaign.review":
            return True
        return matches_keywords(message, self.COUNCIL_KEYWORDS)

    async def load(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        message: str,
    ) -> dict[str, Any]:
        """Load recent council decisions."""
        from sqlalchemy import select
        from ..models import CouncilSessionRecord, ConsensusDecisionRecord

        try:
            res = await session.execute(
                select(CouncilSessionRecord, ConsensusDecisionRecord)
                .join(ConsensusDecisionRecord,
                      ConsensusDecisionRecord.session_id == CouncilSessionRecord.id)
                .where(CouncilSessionRecord.tenant_id == tenant_id)
                .order_by(CouncilSessionRecord.created_at.desc())
                .limit(5)
            )
            rows = res.all()

            decisions = []
            for session, decision in rows:
                decisions.append({
                    "session_id": str(session.id),
                    "campaign": session.campaign_name if hasattr(session, "campaign_name") else "unknown",
                    "decision": decision.decision if hasattr(decision, "decision") else "unknown",
                    "reasoning": (decision.reasoning or "")[:200] if hasattr(decision, "reasoning") else "",
                    "score": decision.score if hasattr(decision, "score") else 0,
                    "date": session.created_at.isoformat() if hasattr(session, "created_at") else "",
                })

            return {"recent_decisions": decisions}
        except Exception as e:
            log.debug("Failed to load council memory: %s", e)
            return {"recent_decisions": []}


class IntegrationsProvider:
    """Loads connected integrations and their data summaries.

    Triggered when the user asks about Shopify, GA4, WordPress, Mailchimp,
    HubSpot, or integration-related questions.
    """

    name = "integrations"

    INTEGRATION_KEYWORDS = [
        "shopify", "wordpress", "google analytics", "ga4", "mailchimp",
        "hubspot", "integration", "connected", "store", "website",
        "email list", "crm", "analytics", "traffic", "revenue", "orders",
        "products", "contact", "sync",
    ]

    def is_relevant(self, message: str, intent: str = "") -> bool:
        return matches_keywords(message, self.INTEGRATION_KEYWORDS)

    async def load(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        message: str,
    ) -> dict[str, Any]:
        """Load integration status and data summaries."""
        from sqlalchemy import select, func
        from ..models import KnowledgeSourceRecord
        from ..models.enums import KnowledgeSourceStatus

        connected: list[dict[str, Any]] = []

        try:
            # Integration data comes through the Knowledge Hub as "live" level sources
            res = await session.execute(
                select(
                    KnowledgeSourceRecord.integration_name,
                    func.count().label("source_count"),
                ).where(
                    KnowledgeSourceRecord.tenant_id == tenant_id,
                    KnowledgeSourceRecord.source_type == "integration",
                    KnowledgeSourceRecord.status == KnowledgeSourceStatus.ready,
                ).group_by(KnowledgeSourceRecord.integration_name)
            )
            for integration_name, count in res.all():
                if integration_name:
                    connected.append({
                        "name": integration_name,
                        "status": "active",
                        "source_count": count,
                        "summary": f"{count} data source(s) synced",
                    })
        except Exception as e:
            log.debug("Failed to load integrations: %s", e)

        return {"connected": connected}


class PerformanceProvider:
    """Loads campaign performance and attribution data.

    Triggered when the user asks about ROAS, revenue, conversions,
    performance, or why something changed.
    """

    name = "performance"

    PERFORMANCE_KEYWORDS = [
        "roas", "roi", "revenue", "conversion", "performance", "result",
        "metric", "ctr", "cpc", "cpa", "spend", "budget", "cost",
        "why did", "drop", "increase", "decrease", "improve", "decline",
        "attribution", "pixel", "track",
    ]

    def is_relevant(self, message: str, intent: str = "") -> bool:
        if intent in ("performance.query", "research"):
            return True
        return matches_keywords(message, self.PERFORMANCE_KEYWORDS)

    async def load(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        message: str,
    ) -> dict[str, Any]:
        """Load performance and attribution summaries."""
        from sqlalchemy import select, func
        from ..models import MetricEvent, Campaign

        result: dict[str, Any] = {}

        try:
            # Recent campaign performance
            res = await session.execute(
                select(Campaign).where(
                    Campaign.tenant_id == tenant_id,
                    Campaign.brand_id == brand_id,
                ).order_by(Campaign.created_at.desc()).limit(5)
            )
            campaigns = res.scalars().all()
            if campaigns:
                result["campaign_performance"] = {
                    "summary": f"{len(campaigns)} recent campaign(s). Latest: {campaigns[0].name}",
                    "campaigns": [
                        {"name": c.name, "status": c.status, "budget": str(c.budget) if hasattr(c, "budget") else ""}
                        for c in campaigns[:3]
                    ],
                }
        except Exception as e:
            log.debug("Failed to load performance: %s", e)

        try:
            # Recent metrics
            res = await session.execute(
                select(func.count()).select_from(MetricEvent).where(
                    MetricEvent.tenant_id == tenant_id,
                )
            )
            metric_count = res.scalar() or 0
            if metric_count > 0:
                result["attribution"] = {
                    "summary": f"{metric_count} tracked events",
                    "event_count": metric_count,
                }
        except Exception as e:
            log.debug("Failed to load attribution: %s", e)

        return result


class ReviewProvider:
    """Loads pending review queue.

    Triggered when the user asks about approvals, reviews, or pending items.
    """

    name = "reviews"

    REVIEW_KEYWORDS = [
        "review", "approve", "approval", "pending", "waiting", "queue",
        "reject", "changes", "feedback",
    ]

    def is_relevant(self, message: str, intent: str = "") -> bool:
        if intent == "campaign.review":
            return True
        return matches_keywords(message, self.REVIEW_KEYWORDS)

    async def load(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        message: str,
    ) -> dict[str, Any]:
        """Load pending reviews."""
        from sqlalchemy import select, func
        from ..models import Campaign
        from ..models.enums import CampaignStatus

        try:
            res = await session.execute(
                select(func.count()).select_from(Campaign).where(
                    Campaign.tenant_id == tenant_id,
                    Campaign.brand_id == brand_id,
                    Campaign.status.in_([CampaignStatus.in_review, CampaignStatus.changes_requested]),
                )
            )
            pending = res.scalar() or 0
            return {"pending_count": pending}
        except Exception as e:
            log.debug("Failed to load reviews: %s", e)
            return {"pending_count": 0}


class DomainPackProvider:
    """Loads the active domain pack for the brand's industry.

    Triggered when industry-specific knowledge would be helpful.
    """

    name = "domain_pack"

    def is_relevant(self, message: str, intent: str = "") -> bool:
        # Load for campaign/strategy/creative intents
        if intent in ("campaign.create", "campaign.strategy", "creative.generate", "consult"):
            return True
        return False

    async def load(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        message: str,
    ) -> dict[str, Any]:
        """Load domain pack info for the brand's industry."""
        from sqlalchemy import select
        from ..models import Brand

        try:
            res = await session.execute(
                select(Brand.category).where(Brand.id == brand_id)
            )
            category = res.scalar_one_or_none()
            if category:
                # Map category to domain pack
                pack_map = {
                    "restaurant": "restaurant",
                    "clinic": "clinic",
                    "healthcare": "clinic",
                    "creator": "creator",
                    "influencer": "creator",
                }
                pack_name = pack_map.get(category.lower(), "business")
                return {"name": pack_name, "category": category}
        except Exception as e:
            log.debug("Failed to load domain pack: %s", e)
        return {"name": "business"}


# ─── Audit Context Provider ──────────────────────────────────────────────────


class AuditContextProvider:
    """Loads the latest brand audit results (visibility score, findings).

    Triggered when the user asks about visibility, SEO, audit, or brand health.
    """

    name = "audit"

    _KEYWORDS = (
        "audit", "visibility", "score", "seo", "findings", "health",
        "how am i doing", "where do i rank", "online presence",
    )

    def is_relevant(self, message: str, intent: str = "") -> bool:
        msg = message.lower()
        if intent in ("audit", "brand.health", "performance.diagnose"):
            return True
        return any(kw in msg for kw in self._KEYWORDS)

    async def load(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        message: str,
    ) -> dict[str, Any]:
        from sqlalchemy import select, desc
        from ..models import Brand, AuditJob

        try:
            # Get the brand's website to match audit jobs
            res = await session.execute(
                select(Brand.website).where(Brand.id == brand_id)
            )
            website = res.scalar_one_or_none()
            if not website:
                return {"latest_audit": None}

            # Extract domain from website
            domain = website.replace("https://", "").replace("http://", "").split("/")[0]

            # Get the latest completed audit for this domain
            res = await session.execute(
                select(AuditJob)
                .where(AuditJob.domain == domain, AuditJob.status == "completed")
                .order_by(desc(AuditJob.created_at))
                .limit(1)
            )
            audit = res.scalar_one_or_none()
            if audit is None:
                return {"latest_audit": None}

            return {
                "latest_audit": {
                    "score": audit.score_snapshot or {},
                    "findings_count": len(audit.findings or []),
                    "top_findings": (audit.findings or [])[:5],
                    "completed_at": audit.completed_at.isoformat() if audit.completed_at else None,
                }
            }
        except Exception as e:
            log.debug("Failed to load audit context: %s", e)
        return {"latest_audit": None}


# ─── Attribution Context Provider ────────────────────────────────────────────


class AttributionContextProvider:
    """Loads attribution and conversion data for the brand.

    Triggered when the user asks about conversions, ROI, attribution,
    or which channels are driving results.
    """

    name = "attribution"

    _KEYWORDS = (
        "conversion", "conversions", "attribut", "roi", "roas",
        "which channel", "driving results", "revenue", "leads from",
        "customer journey", "touchpoint", "first touch", "last touch",
    )

    def is_relevant(self, message: str, intent: str = "") -> bool:
        msg = message.lower()
        if intent in ("performance.analyze", "attribution.query", "performance.why"):
            return True
        return any(kw in msg for kw in self._KEYWORDS)

    async def load(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        message: str,
    ) -> dict[str, Any]:
        from sqlalchemy import select, desc, func
        from ..models import CampaignPerformance, Campaign

        try:
            # CampaignPerformance has campaign_id, not brand_id — join through Campaign
            res = await session.execute(
                select(CampaignPerformance)
                .join(Campaign, CampaignPerformance.campaign_id == Campaign.id)
                .where(Campaign.brand_id == brand_id)
                .order_by(desc(CampaignPerformance.created_at))
                .limit(20)
            )
            records = res.scalars().all()
            if not records:
                return {"attribution_summary": None}

            # Summarise channel-level performance
            channels = {}
            for r in records:
                ch = r.channel or "unknown"
                if ch not in channels:
                    channels[ch] = {"conversions": 0, "spend": 0, "revenue": 0, "clicks": 0}
                channels[ch]["conversions"] += getattr(r, "conversions", 0) or 0
                channels[ch]["spend"] += float(getattr(r, "spend", 0) or 0)
                channels[ch]["revenue"] += float(getattr(r, "revenue", 0) or 0)
                channels[ch]["clicks"] += getattr(r, "clicks", 0) or 0

            return {
                "attribution_summary": {
                    "channels": channels,
                    "total_conversions": sum(c["conversions"] for c in channels.values()),
                    "total_spend": sum(c["spend"] for c in channels.values()),
                    "total_revenue": sum(c["revenue"] for c in channels.values()),
                }
            }
        except Exception as e:
            log.debug("Failed to load attribution context: %s", e)
        return {"attribution_summary": None}


# ─── Timeline Context Provider ───────────────────────────────────────────────


class TimelineContextProvider:
    """Loads recent timeline entries so the Orb knows what happened recently.

    Triggered when the user asks about history, recent actions, what the AI did,
    or references past events.
    """

    name = "timeline"

    _KEYWORDS = (
        "what did you do", "what happened", "recently", "history",
        "last week", "yesterday", "show me", "what have you been",
        "log", "activity", "actions", "timeline",
    )

    def is_relevant(self, message: str, intent: str = "") -> bool:
        msg = message.lower()
        if intent in ("history.query", "timeline.view"):
            return True
        return any(kw in msg for kw in self._KEYWORDS)

    async def load(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        message: str,
    ) -> dict[str, Any]:
        from .timeline import TimelineService

        try:
            svc = TimelineService()
            entries, _ = await svc.list(
                session=session,
                tenant_id=tenant_id,
                brand_id=brand_id,
                limit=10,
            )
            if not entries:
                return {"recent_actions": []}

            # Summarise — don't send full detail, just titles + types + timestamps
            summary = [
                {
                    "title": e.title,
                    "type": e.entry_type,
                    "actor": e.actor,
                    "when": e.created_at,
                }
                for e in entries
            ]
            return {"recent_actions": summary}
        except Exception as e:
            log.debug("Failed to load timeline context: %s", e)
        return {"recent_actions": []}


# ─── Workflow Context Provider ───────────────────────────────────────────────


class WorkflowContextProvider:
    """Loads automation/workflow state so the Orb knows what's automated.

    Triggered when the user asks about automation, workflows, rules,
    or scheduled tasks.
    """

    name = "workflow"

    _KEYWORDS = (
        "automat", "workflow", "rule", "rules", "schedule",
        "trigger", "task", "tasks", "recurring", "loop",
        "weekly loop", "auto", "hands-free",
    )

    def is_relevant(self, message: str, intent: str = "") -> bool:
        msg = message.lower()
        if intent in ("workflow.view", "automation.manage"):
            return True
        return any(kw in msg for kw in self._KEYWORDS)

    async def load(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        message: str,
    ) -> dict[str, Any]:
        from .automation import get_automation_engine, build_automation_context

        try:
            engine = get_automation_engine()
            rules = engine.rules
            tasks = engine.tasks

            active_rules = [r for r in rules if r.enabled]
            pending_tasks = engine.get_pending_tasks()
            brand_tasks = engine.get_tasks_for_brand(brand_id)

            # Also build live context (active campaigns, days since audit, etc.)
            live_ctx = await build_automation_context(session, tenant_id, brand_id)

            return {
                "workflow_state": {
                    "total_rules": len(rules),
                    "active_rules": len(active_rules),
                    "rules_summary": [
                        {"name": r.name, "type": r.type.value, "frequency": r.frequency.value}
                        for r in active_rules[:5]
                    ],
                    "pending_tasks": len(pending_tasks),
                    "brand_tasks": len(brand_tasks),
                    "recent_tasks": [
                        {"type": t.type.value, "status": t.status.value, "frequency": t.frequency.value}
                        for t in brand_tasks[:5]
                    ],
                    "live_context": live_ctx,
                }
            }
        except Exception as e:
            log.debug("Failed to load workflow context: %s", e)
        return {"workflow_state": None}


# ─── Reports Context Provider ───────────────────────────────────────────────


class ReportsContextProvider:
    """Loads the latest report summary for the brand.

    Triggered when the user asks about reports, summaries, weekly results,
    or performance overviews.
    """

    name = "reports"

    _KEYWORDS = (
        "report", "reports", "weekly summary", "summary",
        "results overview", "performance report",
    )

    def is_relevant(self, message: str, intent: str = "") -> bool:
        msg = message.lower()
        if intent in ("reports", "performance.report"):
            return True
        return any(kw in msg for kw in self._KEYWORDS)

    async def load(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        message: str,
    ) -> dict[str, Any]:
        from sqlalchemy import select, desc, func

        try:
            from ..models import Report

            res = await session.execute(
                select(Report)
                .where(Report.brand_id == brand_id)
                .order_by(desc(Report.created_at))
                .limit(3)
            )
            reports = res.scalars().all()
            if not reports:
                return {"recent_reports": []}

            return {
                "recent_reports": [
                    {
                        "id": str(r.id),
                        "week": r.week,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                        "score_snapshot": r.score_snapshot,
                    }
                    for r in reports
                ]
            }
        except Exception as e:
            log.debug("Failed to load reports context: %s", e)
        return {"recent_reports": []}


# ─── Billing Context Provider ───────────────────────────────────────────────


class BillingContextProvider:
    """Loads the tenant's billing/subscription state.

    Triggered when the user asks about billing, plans, usage, costs,
    or subscription status.
    """

    name = "billing"

    _KEYWORDS = (
        "billing", "plan", "subscription", "usage", "cost",
        "how much", "quota", "tokens", "limit", "upgrade",
    )

    def is_relevant(self, message: str, intent: str = "") -> bool:
        msg = message.lower()
        if intent in ("billing", "subscription", "usage"):
            return True
        return any(kw in msg for kw in self._KEYWORDS)

    async def load(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        message: str,
    ) -> dict[str, Any]:
        from sqlalchemy import select

        try:
            from ..models import Billing

            res = await session.execute(
                select(Billing).where(Billing.tenant_id == tenant_id)
            )
            billing = res.scalar_one_or_none()
            if billing is None:
                return {"subscription": None}

            return {
                "subscription": {
                    "provider": billing.provider,
                    "status": billing.status,
                    "ai_tokens_used": billing.ai_tokens_used_month,
                    "ai_budget": billing.ai_budget_month,
                }
            }
        except Exception as e:
            log.debug("Failed to load billing context: %s", e)
        return {"subscription": None}


# ─── Creative Studio Context Provider ───────────────────────────────────────


class CreativeStudioContextProvider:
    """Loads recent creative packages for the brand.

    Triggered when the user asks about creatives, ad copy, headlines,
    or generated content variants.
    """

    name = "creative_studio"

    _KEYWORDS = (
        "creative", "creatives", "ad copy", "headline", "headlines",
        "copy", "variant", "variants", "generated content", "ad text",
    )

    def is_relevant(self, message: str, intent: str = "") -> bool:
        msg = message.lower()
        if intent in ("creative", "content.generate"):
            return True
        return any(kw in msg for kw in self._KEYWORDS)

    async def load(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        message: str,
    ) -> dict[str, Any]:
        from sqlalchemy import select, desc

        try:
            from ..models import Creative, Campaign

            # Creative has no brand_id — join through Campaign
            res = await session.execute(
                select(Creative)
                .join(Campaign, Creative.campaign_id == Campaign.id)
                .where(Campaign.brand_id == brand_id)
                .order_by(desc(Creative.created_at))
                .limit(5)
            )
            creatives = res.scalars().all()
            if not creatives:
                return {"recent_creatives": []}

            return {
                "recent_creatives": [
                    {
                        "id": str(c.id),
                        "type": c.type,
                        "policy_status": c.policy_status,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                    }
                    for c in creatives
                ]
            }
        except Exception as e:
            log.debug("Failed to load creative studio context: %s", e)
        return {"recent_creatives": []}


# ─── Video Gen Context Provider ─────────────────────────────────────────────


class VideoGenContextProvider:
    """Loads recent video/image generations for the brand.

    Triggered when the user asks about videos, reels, image generation,
    or AI-generated media.
    """

    name = "video_gen"

    _KEYWORDS = (
        "video", "videos", "reel", "reels", "image", "images",
        "generate", "generated", "thumbnail", "visual", "media",
    )

    def is_relevant(self, message: str, intent: str = "") -> bool:
        msg = message.lower()
        if intent in ("video", "image", "media.generate"):
            return True
        return any(kw in msg for kw in self._KEYWORDS)

    async def load(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        message: str,
    ) -> dict[str, Any]:
        from sqlalchemy import select, desc

        try:
            from ..models import Asset

            res = await session.execute(
                select(Asset)
                .where(Asset.brand_id == brand_id, Asset.type.in_(["video", "image"]))
                .order_by(desc(Asset.created_at))
                .limit(5)
            )
            assets = res.scalars().all()
            if not assets:
                return {"recent_generations": []}

            return {
                "recent_generations": [
                    {
                        "id": str(a.id),
                        "type": a.type,
                        "source_url": a.source_url,
                        "created_at": a.created_at.isoformat() if a.created_at else None,
                    }
                    for a in assets
                ]
            }
        except Exception as e:
            log.debug("Failed to load video gen context: %s", e)
        return {"recent_generations": []}


# ─── Factory ────────────────────────────────────────────────────────────────


def create_default_context_builder() -> ContextBuilder:
    """Create a ContextBuilder with all default providers registered."""
    builder = ContextBuilder()
    builder.register(CapabilityProvider())
    builder.register(KnowledgeContextProvider())
    builder.register(MarketingIntelligenceProvider())
    builder.register(CouncilMemoryProvider())
    builder.register(IntegrationsProvider())
    builder.register(PerformanceProvider())
    builder.register(ReviewProvider())
    builder.register(DomainPackProvider())
    # New providers — complete Orb awareness
    builder.register(AuditContextProvider())
    builder.register(AttributionContextProvider())
    builder.register(TimelineContextProvider())
    builder.register(WorkflowContextProvider())
    builder.register(ReportsContextProvider())
    builder.register(BillingContextProvider())
    builder.register(CreativeStudioContextProvider())
    builder.register(VideoGenContextProvider())
    return builder


# Singleton
_builder: ContextBuilder | None = None


def get_context_builder() -> ContextBuilder:
    """Get the global ContextBuilder instance."""
    global _builder
    if _builder is None:
        _builder = create_default_context_builder()
    return _builder
