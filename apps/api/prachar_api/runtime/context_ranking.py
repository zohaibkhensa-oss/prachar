"""Context Ranking Layer + Observability — scores context items and trims by token budget.

Two systems:

1. **Context Ranking Layer**
   Instead of every provider contributing equally, each context item gets a
   relevance score (0-1). The ranking layer:
   - Scores every item based on type, recency, confidence, and semantic relevance
   - Sorts items by score (descending)
   - Trims to stay within a target token budget
   - Keeps the highest-value items, drops the least relevant

   Example:
       Brand Guidelines     score = 0.98  ✓ kept
       Previous Campaign    score = 0.91  ✓ kept
       Pricing Catalogue    score = 0.87  ✓ kept
       Audience Profile     score = 0.72  ✓ kept
       Competitor Report    score = 0.44  ✗ trimmed (budget exceeded)

2. **Context Trace (Observability)**
   Every context build emits a trace showing:
   - Intent classified
   - Providers activated vs skipped
   - Items retrieved per provider
   - Estimated vs final prompt tokens
   - Items trimmed by ranking

   Example trace:
       Context Build
       ─────────────
       Intent: Campaign Creation
       Providers Activated: ✓ Knowledge, ✓ Marketing Intelligence, ✓ Domain Pack
       Skipped: ✗ Billing, ✗ Reviews, ✗ Performance
       Knowledge Retrieved: 5 chunks
       Estimated Prompt Tokens: 6,850
       Final Prompt Tokens: 7,420
       Items Trimmed: 2 (Competitor Report, Old FAQ)
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

log = logging.getLogger("prachar.runtime.context_ranking")


# ─── Token Estimation ───────────────────────────────────────────────────────


def estimate_tokens(text: str) -> int:
    """Estimate token count for a string.

    Uses the standard heuristic: ~4 characters per token.
    For more accuracy, use tiktoken in production.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_dict_tokens(data: dict[str, Any], max_depth: int = 3) -> int:
    """Estimate token count for a dict by serialising its values."""
    if not data:
        return 0
    total = 0
    for key, value in data.items():
        if isinstance(value, str):
            total += estimate_tokens(value)
        elif isinstance(value, list):
            for item in value[:10]:  # Sample first 10 items
                if isinstance(item, dict):
                    total += estimate_dict_tokens(item, max_depth - 1)
                elif isinstance(item, str):
                    total += estimate_tokens(item)
        elif isinstance(value, dict) and max_depth > 0:
            total += estimate_dict_tokens(value, max_depth - 1)
        elif value is not None:
            total += estimate_tokens(str(value))
    return total


# ─── Context Item ───────────────────────────────────────────────────────────


class ContextItemType(str, Enum):
    """Types of context items that can be ranked."""
    KNOWLEDGE_CHUNK = "knowledge_chunk"
    BUSINESS_PROFILE = "business_profile"
    AUDIENCE_PROFILE = "audience_profile"
    COMPETITOR_PROFILE = "competitor_profile"
    STRATEGY = "strategy"
    CREATIVE_DIRECTION = "creative_direction"
    MEDIA_PLAN = "media_plan"
    COUNCIL_DECISION = "council_decision"
    INTEGRATION_DATA = "integration_data"
    PERFORMANCE_DATA = "performance_data"
    ATTRIBUTION_DATA = "attribution_data"
    CAPABILITY = "capability"
    REVIEW_ITEM = "review_item"
    DOMAIN_PACK = "domain_pack"
    BRAND_INFO = "brand_info"
    MEMORY = "memory"
    BILLING = "billing"


# Base scores by type — how inherently valuable is this type of context?
# These are starting points; actual scores are adjusted by recency, confidence, etc.
BASE_SCORES: dict[ContextItemType, float] = {
    ContextItemType.KNOWLEDGE_CHUNK: 0.70,       # Adjusted by semantic relevance
    ContextItemType.BRAND_INFO: 0.95,            # Always high — brand is core
    ContextItemType.BUSINESS_PROFILE: 0.80,      # High — core business understanding
    ContextItemType.AUDIENCE_PROFILE: 0.75,      # High — needed for campaigns
    ContextItemType.STRATEGY: 0.78,             # High — strategic context
    ContextItemType.CREATIVE_DIRECTION: 0.65,    # Medium — creative guidance
    ContextItemType.MEDIA_PLAN: 0.60,            # Medium — channel allocation
    ContextItemType.COMPETITOR_PROFILE: 0.50,    # Medium — useful but not critical
    ContextItemType.COUNCIL_DECISION: 0.55,      # Medium — historical context
    ContextItemType.INTEGRATION_DATA: 0.45,      # Medium — operational context
    ContextItemType.PERFORMANCE_DATA: 0.65,      # Medium-high — needed for analysis
    ContextItemType.ATTRIBUTION_DATA: 0.60,      # Medium — conversion context
    ContextItemType.CAPABILITY: 0.40,            # Low-medium — awareness, not grounding
    ContextItemType.REVIEW_ITEM: 0.35,           # Low — operational, not strategic
    ContextItemType.DOMAIN_PACK: 0.50,           # Medium — industry context
    ContextItemType.MEMORY: 0.70,               # Medium-high — past learnings
    ContextItemType.BILLING: 0.20,              # Low — rarely needed for answers
}


@dataclass
class ContextItem:
    """A single item of context that can be scored and ranked.

    Each item has:
    - type: what kind of context (knowledge chunk, MI profile, etc.)
    - title: human-readable label for the trace
    - content: the actual text/data to inject into the prompt
    - score: relevance score 0-1 (computed by the ranking layer)
    - tokens: estimated token count
    - source: which provider loaded this item
    - metadata: additional info for scoring (recency, confidence, semantic relevance)
    """
    type: ContextItemType
    title: str
    content: str
    score: float = 0.0
    tokens: int = 0
    source: str = ""  # provider name
    metadata: dict[str, Any] = field(default_factory=dict)
    # Whether this item survived ranking (True) or was trimmed (False)
    kept: bool = True

    def __post_init__(self) -> None:
        if self.tokens == 0:
            self.tokens = estimate_tokens(self.content)


# ─── Context Ranking Layer ──────────────────────────────────────────────────


class ContextRankingLayer:
    """Scores and ranks context items, trimming to fit a token budget.

    Scoring factors:
    1. Base score by type (how inherently valuable is this kind of context?)
    2. Semantic relevance (for knowledge chunks — cosine similarity score)
    3. Recency boost (newer items score higher)
    4. Confidence boost (higher confidence = higher score)
    5. Intent alignment (items matching the user's intent score higher)

    Token budget:
    - Default: 4000 tokens (configurable)
    - Items are sorted by score (descending)
    - Items are added until budget is reached
    - Remaining items are trimmed (kept=False)
    - A minimum set of items is always kept (brand info, top knowledge chunk)
    """

    def __init__(
        self,
        token_budget: int = 4000,
        min_items: int = 3,
        always_keep_types: set[ContextItemType] | None = None,
    ) -> None:
        self.token_budget = token_budget
        self.min_items = min_items
        self.always_keep_types = always_keep_types or {
            ContextItemType.BRAND_INFO,
        }

    def score_item(
        self,
        item: ContextItem,
        message: str = "",
        intent: str = "",
    ) -> float:
        """Compute a relevance score (0-1) for a context item.

        The score combines:
        - Base type score (50% weight)
        - Semantic relevance (20% weight) — for knowledge chunks
        - Recency boost (15% weight)
        - Confidence boost (10% weight)
        - Intent alignment (5% weight)
        """
        # 1. Base score from type
        base = BASE_SCORES.get(item.type, 0.50)

        # 2. Semantic relevance (for knowledge chunks, use the similarity score)
        semantic = 0.5  # Default neutral
        if item.type == ContextItemType.KNOWLEDGE_CHUNK:
            semantic = item.metadata.get("similarity_score", 0.5)
        elif item.type == ContextItemType.MEMORY:
            # Memory items with higher relevance to the message score higher
            semantic = 0.6

        # 3. Recency boost — newer items score higher
        recency = 0.5  # Default neutral
        created_at = item.metadata.get("created_at")
        if created_at:
            recency = self._recency_score(created_at)
        elif item.metadata.get("age_days") is not None:
            age_days = item.metadata["age_days"]
            recency = max(0.1, 1.0 - (age_days / 365))  # Decay over a year

        # 4. Confidence boost
        confidence = item.metadata.get("confidence", 0.5)

        # 5. Intent alignment — does this item type match the intent?
        intent_alignment = self._intent_alignment(item.type, intent)

        # Weighted combination
        score = (
            base * 0.50
            + semantic * 0.20
            + recency * 0.15
            + confidence * 0.10
            + intent_alignment * 0.05
        )

        # Clamp to [0, 1]
        return max(0.0, min(1.0, score))

    def _recency_score(self, created_at: Any) -> float:
        """Score based on how recent the item is. 1.0 = just now, 0.1 = >1 year old."""
        try:
            if isinstance(created_at, str):
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            elif isinstance(created_at, datetime):
                dt = created_at
            else:
                return 0.5

            # Ensure timezone-aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            age_days = (datetime.now(timezone.utc) - dt).days
            # Full score if < 7 days, decays to 0.1 over 365 days
            if age_days <= 7:
                return 1.0
            elif age_days >= 365:
                return 0.1
            else:
                return 1.0 - (0.9 * (age_days - 7) / 358)
        except Exception:
            return 0.5

    def _intent_alignment(self, item_type: ContextItemType, intent: str) -> float:
        """How well does this item type align with the user's intent?"""
        intent_lower = intent.lower()

        alignment_map = {
            "campaign": {
                ContextItemType.BUSINESS_PROFILE: 0.9,
                ContextItemType.AUDIENCE_PROFILE: 0.9,
                ContextItemType.STRATEGY: 0.85,
                ContextItemType.KNOWLEDGE_CHUNK: 0.8,
                ContextItemType.CREATIVE_DIRECTION: 0.75,
                ContextItemType.MEDIA_PLAN: 0.7,
                ContextItemType.DOMAIN_PACK: 0.65,
                ContextItemType.COMPETITOR_PROFILE: 0.6,
            },
            "performance": {
                ContextItemType.PERFORMANCE_DATA: 0.95,
                ContextItemType.ATTRIBUTION_DATA: 0.9,
                ContextItemType.COUNCIL_DECISION: 0.7,
                ContextItemType.KNOWLEDGE_CHUNK: 0.5,
            },
            "review": {
                ContextItemType.REVIEW_ITEM: 0.95,
                ContextItemType.COUNCIL_DECISION: 0.85,
                ContextItemType.CREATIVE_DIRECTION: 0.6,
            },
            "conversation": {
                ContextItemType.BRAND_INFO: 0.8,
                ContextItemType.CAPABILITY: 0.7,
                ContextItemType.KNOWLEDGE_CHUNK: 0.6,
            },
            "research": {
                ContextItemType.PERFORMANCE_DATA: 0.8,
                ContextItemType.COUNCIL_DECISION: 0.7,
                ContextItemType.KNOWLEDGE_CHUNK: 0.65,
            },
        }

        # Find matching intent category
        for intent_key, type_scores in alignment_map.items():
            if intent_key in intent_lower:
                return type_scores.get(item_type, 0.3)

        return 0.3  # Default low alignment

    def rank(
        self,
        items: list[ContextItem],
        message: str = "",
        intent: str = "",
    ) -> list[ContextItem]:
        """Score, sort, and trim context items to fit the token budget.

        Returns the items list with:
        - score field populated
        - kept field set (True if in final context, False if trimmed)
        - Sorted by score (highest first)
        """
        if not items:
            return []

        # Step 1: Score all items
        for item in items:
            item.score = self.score_item(item, message, intent)

        # Step 2: Sort by score (descending)
        items.sort(key=lambda x: x.score, reverse=True)

        # Step 3: Allocate token budget
        # Reserve tokens for always-keep items first
        kept_items: list[ContextItem] = []
        trimmed_items: list[ContextItem] = []
        used_tokens = 0

        # Phase A: Always-keep items (regardless of budget)
        for item in items:
            if item.type in self.always_keep_types:
                kept_items.append(item)
                item.kept = True
                used_tokens += item.tokens

        # Phase B: Remaining items by score, until budget is reached
        remaining = [i for i in items if i not in kept_items]
        for item in remaining:
            if used_tokens + item.tokens <= self.token_budget:
                kept_items.append(item)
                item.kept = True
                used_tokens += item.tokens
            else:
                item.kept = False
                trimmed_items.append(item)

        # Phase C: Ensure minimum items
        if len(kept_items) < self.min_items and remaining:
            for item in remaining:
                if item in trimmed_items and len(kept_items) < self.min_items:
                    kept_items.append(item)
                    item.kept = True
                    used_tokens += item.tokens
                    trimmed_items.remove(item)

        # Re-sort kept items by score
        kept_items.sort(key=lambda x: x.score, reverse=True)

        # Return all items (kept first, then trimmed)
        return kept_items + trimmed_items

    def rank_to_prompt(self, items: list[ContextItem], message: str = "", intent: str = "") -> str:
        """Rank items and return the kept items as a prompt context string."""
        ranked = self.rank(items, message, intent)
        kept = [i for i in ranked if i.kept]

        parts: list[str] = []
        for item in kept:
            parts.append(f"[{item.title}] (score: {item.score:.2f})\n{item.content}")

        return "\n\n".join(parts) if parts else ""


# ─── Context Trace (Observability) ──────────────────────────────────────────


@dataclass
class ProviderTrace:
    """Trace for a single provider's execution."""
    name: str
    activated: bool = False
    reason: str = ""  # Why it was activated or skipped
    items_loaded: int = 0
    tokens_estimated: int = 0
    load_time_ms: float = 0.0
    error: str = ""


@dataclass
class ContextTrace:
    """Full trace of a context build — for debugging and observability.

    Emitted as an event so the frontend can display it in the Orb panel
    (or a debug view), and it's stored in the Decision Contract for replay.
    """

    # Input
    message: str = ""
    intent: str = ""

    # Provider execution
    providers_activated: list[ProviderTrace] = field(default_factory=list)
    providers_skipped: list[ProviderTrace] = field(default_factory=list)

    # Items
    total_items: int = 0
    items_kept: int = 0
    items_trimmed: int = 0
    trimmed_titles: list[str] = field(default_factory=list)

    # Token budget
    token_budget: int = 4000
    estimated_prompt_tokens: int = 0  # Before ranking
    final_prompt_tokens: int = 0     # After ranking (kept items only)

    # Timing
    build_start: float = 0.0
    build_end: float = 0.0
    total_build_time_ms: float = 0.0

    # Ranking details
    ranking_applied: bool = False
    top_items: list[dict[str, Any]] = field(default_factory=list)  # Top 5 by score

    def mark_start(self) -> None:
        self.build_start = time.time()

    def mark_end(self) -> None:
        self.build_end = time.time()
        self.total_build_time_ms = (self.build_end - self.build_start) * 1000

    def add_activated(self, trace: ProviderTrace) -> None:
        self.providers_activated.append(trace)
        self.total_items += trace.items_loaded
        self.estimated_prompt_tokens += trace.tokens_estimated

    def add_skipped(self, name: str, reason: str = "") -> None:
        self.providers_skipped.append(ProviderTrace(name=name, activated=False, reason=reason))

    def record_ranking(self, items: list[ContextItem], final_tokens: int) -> None:
        """Record ranking results after the ranking layer runs."""
        self.ranking_applied = True
        self.items_kept = sum(1 for i in items if i.kept)
        self.items_trimmed = sum(1 for i in items if not i.kept)
        self.trimmed_titles = [i.title for i in items if not i.kept]
        self.final_prompt_tokens = final_tokens

        # Record top 5 items by score
        kept = [i for i in items if i.kept]
        kept.sort(key=lambda x: x.score, reverse=True)
        self.top_items = [
            {
                "title": i.title,
                "type": i.type.value,
                "score": round(i.score, 4),
                "tokens": i.tokens,
                "source": i.source,
            }
            for i in kept[:5]
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message[:200],
            "intent": self.intent,
            "providers_activated": [
                {"name": p.name, "items": p.items_loaded, "tokens": p.tokens_estimated,
                 "time_ms": round(p.load_time_ms, 1), "error": p.error}
                for p in self.providers_activated
            ],
            "providers_skipped": [
                {"name": p.name, "reason": p.reason}
                for p in self.providers_skipped
            ],
            "total_items": self.total_items,
            "items_kept": self.items_kept,
            "items_trimmed": self.items_trimmed,
            "trimmed_titles": self.trimmed_titles,
            "token_budget": self.token_budget,
            "estimated_prompt_tokens": self.estimated_prompt_tokens,
            "final_prompt_tokens": self.final_prompt_tokens,
            "total_build_time_ms": round(self.total_build_time_ms, 1),
            "ranking_applied": self.ranking_applied,
            "top_items": self.top_items,
        }

    def format_for_display(self) -> str:
        """Format as a human-readable trace for debugging.

        Example:
            Context Build
            ─────────────
            Intent: Campaign Creation
            Providers Activated: ✓ Knowledge, ✓ Marketing Intelligence, ✓ Domain Pack
            Skipped: ✗ Billing, ✗ Reviews, ✗ Performance
            Knowledge Retrieved: 5 chunks
            Estimated Prompt Tokens: 6,850
            Final Prompt Tokens: 7,420
            Items Trimmed: 2 (Competitor Report, Old FAQ)
        """
        lines: list[str] = [
            "Context Build",
            "─────────────",
            f"Intent: {self.intent or 'unknown'}",
        ]

        # Providers activated
        activated_names = [p.name for p in self.providers_activated]
        if activated_names:
            lines.append(f"Providers Activated: {', '.join(f'✓ {n}' for n in activated_names)}")
        else:
            lines.append("Providers Activated: (none)")

        # Providers skipped
        skipped_names = [p.name for p in self.providers_skipped]
        if skipped_names:
            lines.append(f"Skipped: {', '.join(f'✗ {n}' for n in skipped_names)}")

        # Items
        lines.append(f"Total Items: {self.total_items}")
        lines.append(f"Items Kept: {self.items_kept}")
        if self.items_trimmed > 0:
            lines.append(f"Items Trimmed: {self.items_trimmed} ({', '.join(self.trimmed_titles[:5])})")

        # Tokens
        lines.append(f"Estimated Prompt Tokens: {self.estimated_prompt_tokens:,}")
        lines.append(f"Final Prompt Tokens: {self.final_prompt_tokens:,}")
        lines.append(f"Token Budget: {self.token_budget:,}")

        # Top items
        if self.top_items:
            lines.append("\nTop Items by Score:")
            for item in self.top_items:
                lines.append(f"  {item['title']}: {item['score']:.2f} ({item['tokens']} tokens)")

        # Timing
        lines.append(f"\nBuild Time: {self.total_build_time_ms:.1f}ms")

        return "\n".join(lines)


# ─── Item Extractor — converts provider data to ContextItems ────────────────


class ContextItemExtractor:
    """Extracts ContextItems from the raw data returned by providers.

    Each provider returns a dict. This class converts that dict into
    a list of ContextItem objects that can be scored and ranked.
    """

    @staticmethod
    def extract(provider_name: str, data: dict[str, Any]) -> list[ContextItem]:
        """Extract context items from a provider's data."""
        items: list[ContextItem] = []

        if provider_name == "knowledge":
            items.extend(ContextItemExtractor._extract_knowledge(data))
        elif provider_name == "marketing_intelligence":
            items.extend(ContextItemExtractor._extract_mi(data))
        elif provider_name == "council_memory":
            items.extend(ContextItemExtractor._extract_council(data))
        elif provider_name == "integrations":
            items.extend(ContextItemExtractor._extract_integrations(data))
        elif provider_name == "performance":
            items.extend(ContextItemExtractor._extract_performance(data))
        elif provider_name == "reviews":
            items.extend(ContextItemExtractor._extract_reviews(data))
        elif provider_name == "domain_pack":
            items.extend(ContextItemExtractor._extract_domain_pack(data))
        elif provider_name == "capabilities":
            items.extend(ContextItemExtractor._extract_capabilities(data))

        return items

    @staticmethod
    def _extract_knowledge(data: dict[str, Any]) -> list[ContextItem]:
        items: list[ContextItem] = []
        for chunk in data.get("chunks", []):
            items.append(ContextItem(
                type=ContextItemType.KNOWLEDGE_CHUNK,
                title=chunk.get("title", "Unknown"),
                content=chunk.get("content", ""),
                source="knowledge",
                metadata={
                    "similarity_score": chunk.get("score", 0.5),
                    "level": chunk.get("level", ""),
                    "source_id": chunk.get("source_id", ""),
                    "chunk_id": chunk.get("chunk_id", ""),
                    "section": chunk.get("section", ""),
                    "page_number": chunk.get("page_number"),
                },
            ))
        return items

    @staticmethod
    def _extract_mi(data: dict[str, Any]) -> list[ContextItem]:
        items: list[ContextItem] = []
        type_map = {
            "business_profile": ContextItemType.BUSINESS_PROFILE,
            "audience_profile": ContextItemType.AUDIENCE_PROFILE,
            "competitor_profile": ContextItemType.COMPETITOR_PROFILE,
            "strategy": ContextItemType.STRATEGY,
            "creative_direction": ContextItemType.CREATIVE_DIRECTION,
            "media_plan": ContextItemType.MEDIA_PLAN,
        }
        for key, item_type in type_map.items():
            entry = data.get(key)
            if entry and isinstance(entry, dict):
                items.append(ContextItem(
                    type=item_type,
                    title=key.replace("_", " ").title(),
                    content=entry.get("summary", ""),
                    source="marketing_intelligence",
                    metadata={
                        "confidence": entry.get("confidence", 0.5),
                        "created_at": entry.get("created_at"),
                    },
                ))
        return items

    @staticmethod
    def _extract_council(data: dict[str, Any]) -> list[ContextItem]:
        items: list[ContextItem] = []
        for decision in data.get("recent_decisions", []):
            content = f"{decision.get('campaign', 'unknown')}: {decision.get('decision', '')}"
            if decision.get("reasoning"):
                content += f" — {decision['reasoning']}"
            items.append(ContextItem(
                type=ContextItemType.COUNCIL_DECISION,
                title=f"Council: {decision.get('campaign', 'unknown')}",
                content=content,
                source="council_memory",
                metadata={
                    "created_at": decision.get("date"),
                    "score": decision.get("score", 0),
                },
            ))
        return items

    @staticmethod
    def _extract_integrations(data: dict[str, Any]) -> list[ContextItem]:
        items: list[ContextItem] = []
        for integ in data.get("connected", []):
            content = f"{integ['name']}: {integ.get('summary', 'connected')}"
            items.append(ContextItem(
                type=ContextItemType.INTEGRATION_DATA,
                title=f"Integration: {integ['name']}",
                content=content,
                source="integrations",
                metadata={"status": integ.get("status", "unknown")},
            ))
        return items

    @staticmethod
    def _extract_performance(data: dict[str, Any]) -> list[ContextItem]:
        items: list[ContextItem] = []
        if data.get("campaign_performance"):
            perf = data["campaign_performance"]
            items.append(ContextItem(
                type=ContextItemType.PERFORMANCE_DATA,
                title="Campaign Performance",
                content=perf.get("summary", ""),
                source="performance",
            ))
        if data.get("attribution"):
            attr = data["attribution"]
            items.append(ContextItem(
                type=ContextItemType.ATTRIBUTION_DATA,
                title="Attribution Data",
                content=attr.get("summary", ""),
                source="performance",
            ))
        return items

    @staticmethod
    def _extract_reviews(data: dict[str, Any]) -> list[ContextItem]:
        items: list[ContextItem] = []
        pending = data.get("pending_count", 0)
        if pending > 0:
            items.append(ContextItem(
                type=ContextItemType.REVIEW_ITEM,
                title="Pending Reviews",
                content=f"{pending} campaign(s) awaiting approval",
                source="reviews",
            ))
        return items

    @staticmethod
    def _extract_domain_pack(data: dict[str, Any]) -> list[ContextItem]:
        items: list[ContextItem] = []
        if data.get("name"):
            items.append(ContextItem(
                type=ContextItemType.DOMAIN_PACK,
                title=f"Domain Pack: {data['name']}",
                content=f"Industry expertise: {data.get('name', '')} pack active for {data.get('category', 'this business')}",
                source="domain_pack",
            ))
        return items

    @staticmethod
    def _extract_capabilities(data: dict[str, Any]) -> list[ContextItem]:
        items: list[ContextItem] = []
        caps = data.get("capabilities", [])
        if caps:
            avail = [c["name"] for c in caps if c.get("available")]
            if avail:
                items.append(ContextItem(
                    type=ContextItemType.CAPABILITY,
                    title="Available Capabilities",
                    content=f"Available: {', '.join(avail)}",
                    source="capabilities",
                ))
        return items

    @staticmethod
    def extract_base_context(brand: Any, memory: Any) -> list[ContextItem]:
        """Extract base context items (brand + memory) that are always present."""
        items: list[ContextItem] = []
        if brand:
            brand_content = f"Brand: {brand.name} ({brand.category or 'unknown'})"
            if brand.website:
                brand_content += f"\nWebsite: {brand.website}"
            if brand.tone:
                brand_content += f"\nTone: {brand.tone}"
            items.append(ContextItem(
                type=ContextItemType.BRAND_INFO,
                title="Brand Info",
                content=brand_content,
                source="base",
                metadata={"score_override": 0.95},
            ))
        if memory and memory.best_practices:
            items.append(ContextItem(
                type=ContextItemType.MEMORY,
                title="Business Memory",
                content=f"Past learnings: {', '.join(memory.best_practices[:5])}",
                source="base",
            ))
        return items


# ─── Ranked Enriched Context ────────────────────────────────────────────────


@dataclass
class RankedEnrichedContext:
    """Enriched context after ranking — includes trace and ranked items.

    This is the final output of the Context Builder with ranking applied.
    It contains:
    - base: the base AIContext (for tools)
    - enriched: provider data (same as before)
    - capabilities: dynamic capabilities
    - knowledge_chunks: retrieved knowledge
    - ranked_items: all context items with scores and kept/trimmed status
    - trace: full observability trace
    - prompt_context: the final ranked prompt context string
    """

    base: Any  # AIContext
    enriched: dict[str, Any] = field(default_factory=dict)
    capabilities: list[dict[str, Any]] = field(default_factory=list)
    knowledge_chunks: list[dict[str, Any]] = field(default_factory=list)
    providers_used: list[str] = field(default_factory=list)
    ranked_items: list[ContextItem] = field(default_factory=list)
    trace: ContextTrace = field(default_factory=ContextTrace)
    prompt_context: str = ""

    @property
    def session(self) -> Any:
        return self.base.session

    def to_prompt_context(self) -> str:
        """Return the ranked prompt context string."""
        return self.prompt_context

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "base": self.base.to_snapshot(),
            "providers_used": self.providers_used,
            "capabilities": self.capabilities,
            "knowledge_chunk_count": len(self.knowledge_chunks),
            "enriched_keys": list(self.enriched.keys()),
            "trace": self.trace.to_dict(),
            "ranked_items": [
                {"title": i.title, "type": i.type.value, "score": round(i.score, 4),
                 "tokens": i.tokens, "kept": i.kept, "source": i.source}
                for i in self.ranked_items
            ],
        }


# ─── Context Build Evaluation (Post-Hoc Metrics) ───────────────────────────
#
# After the LLM responds, we evaluate how well the context build performed:
#
#   Context Build
#   ─────────────
#   Knowledge Retrieved:       12 chunks
#   Chunks Used by Model:      5      (kept by ranking)
#   Chunks Referenced in Answer: 3    (cited/paraphrased in the LLM output)
#   Answer Supported by Sources: 94%  (how much of the answer traces to context)
#   Unused Context:            58%    (tokens wasted on items not referenced)
#   Average Retrieval Score:   0.87   (mean similarity of retrieved chunks)
#
# These metrics let you measure over time:
# - Whether retrieval quality is improving
# - Whether ranking is selecting the right information
# - Whether providers are adding value or just consuming tokens
#
# Additionally, we evaluate the RETRIEVAL itself (not just the answer):
#
#   Retrieval Quality
#   ────────────────
#   Recall:              0.82   (were all relevant chunks retrieved?)
#   Precision:           0.67   (were retrieved chunks actually relevant?)
#   Novel Information:   0.71   (how much unique info per chunk?)
#   Duplicate Chunks:    2      (chunks that repeat existing info)
#   Chunk Diversity:     0.65   (are chunks topically diverse?)
#   Provider Diversity:  3      (how many distinct providers contributed?)


@dataclass
class RetrievalQuality:
    """Evaluates the quality of the retrieval itself (independent of the answer).

    Metrics:
    - recall: Were all relevant chunks retrieved? (referenced / all_kept)
    - precision: Were retrieved chunks actually relevant? (referenced / retrieved)
    - novelty: How much unique information per chunk? (1 - avg_overlap)
    - duplicate_count: Chunks that repeat existing info
    - duplicate_pct: Percentage of chunks that are duplicates
    - chunk_diversity: Are chunks topically diverse? (0-1, based on unique words)
    - provider_diversity: How many distinct providers contributed?
    - avg_chunk_length: Average chunk content length (tokens)
    """
    recall: float = 0.0
    precision: float = 0.0
    novelty: float = 0.0
    duplicate_count: int = 0
    duplicate_pct: float = 0.0
    chunk_diversity: float = 0.0
    provider_diversity: int = 0
    avg_chunk_length: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "recall": round(self.recall, 4),
            "precision": round(self.precision, 4),
            "novelty": round(self.novelty, 4),
            "duplicate_count": self.duplicate_count,
            "duplicate_pct": round(self.duplicate_pct, 2),
            "chunk_diversity": round(self.chunk_diversity, 4),
            "provider_diversity": self.provider_diversity,
            "avg_chunk_length": round(self.avg_chunk_length, 1),
        }

    def format_for_display(self) -> str:
        lines: list[str] = [
            "Retrieval Quality",
            "─────────────────",
            f"Recall:            {self.recall:.2f}",
            f"Precision:         {self.precision:.2f}",
            f"Novel Information: {self.novelty:.2f}",
            f"Duplicate Chunks:  {self.duplicate_count}",
            f"Chunk Diversity:   {self.chunk_diversity:.2f}",
            f"Provider Diversity: {self.provider_diversity}",
        ]
        return "\n".join(lines)


@dataclass
class ItemEvaluation:
    """Per-item evaluation after the LLM has responded."""
    title: str
    item_type: str
    source: str
    score: float
    tokens: int
    kept: bool               # Was it kept by ranking?
    referenced: bool = False  # Was it cited/paraphrased in the LLM answer?
    citation_count: int = 0   # How many times referenced
    user_accepted: bool | None = None  # Did the user accept the answer? (set later)
    positive_outcome: bool | None = None  # Did the campaign/action succeed? (set later)
    # Granular identity (for source-level and chunk-level learning)
    source_title: str = ""   # The item's title (for source-level adjustments)
    chunk_id: str = ""       # Unique chunk ID (for chunk-level adjustments)


@dataclass
class ContextEvaluation:
    """Post-hoc evaluation of a context build + LLM response.

    Computed after the LLM responds, by comparing the answer text against
    the context items that were provided. This closes the observability loop:
        build → rank → inject → LLM responds → evaluate → learn
    """

    # Counts
    items_total: int = 0          # All items extracted
    items_kept: int = 0           # Kept by ranking (in prompt)
    items_trimmed: int = 0        # Trimmed by ranking (out of prompt)
    items_referenced: int = 0     # Referenced in the LLM answer

    # Knowledge-specific
    chunks_retrieved: int = 0
    chunks_used: int = 0          # Kept by ranking
    chunks_referenced: int = 0    # Referenced in answer

    # Quality metrics
    answer_support_pct: float = 0.0     # % of answer supported by sources
    unused_context_pct: float = 0.0     # % of prompt tokens not referenced
    avg_retrieval_score: float = 0.0    # Mean similarity of retrieved chunks
    avg_kept_score: float = 0.0         # Mean ranking score of kept items

    # Per-item detail
    item_evaluations: list[ItemEvaluation] = field(default_factory=list)

    # Retrieval quality (independent of the answer)
    retrieval_quality: RetrievalQuality = field(default_factory=RetrievalQuality)

    # The LLM answer text (for reference)
    answer_text: str = ""
    answer_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "items_total": self.items_total,
            "items_kept": self.items_kept,
            "items_trimmed": self.items_trimmed,
            "items_referenced": self.items_referenced,
            "chunks_retrieved": self.chunks_retrieved,
            "chunks_used": self.chunks_used,
            "chunks_referenced": self.chunks_referenced,
            "answer_support_pct": round(self.answer_support_pct, 2),
            "unused_context_pct": round(self.unused_context_pct, 2),
            "avg_retrieval_score": round(self.avg_retrieval_score, 4),
            "avg_kept_score": round(self.avg_kept_score, 4),
            "answer_tokens": self.answer_tokens,
            "retrieval_quality": self.retrieval_quality.to_dict(),
            "item_evaluations": [
                {
                    "title": e.title,
                    "type": e.item_type,
                    "source": e.source,
                    "score": round(e.score, 4),
                    "tokens": e.tokens,
                    "kept": e.kept,
                    "referenced": e.referenced,
                    "citations": e.citation_count,
                }
                for e in self.item_evaluations
            ],
        }

    def format_for_display(self) -> str:
        """Format as a human-readable evaluation report.

        Example:
            Context Build Evaluation
            ────────────────────────
            Knowledge Retrieved:        12 chunks
            Chunks Used by Model:       5
            Chunks Referenced in Answer: 3
            Answer Supported by Sources: 94%
            Unused Context:             58%
            Average Retrieval Score:    0.87
        """
        lines: list[str] = [
            "Context Build Evaluation",
            "────────────────────────",
            f"Items Total:              {self.items_total}",
            f"Items Kept by Ranking:    {self.items_kept}",
            f"Items Trimmed:            {self.items_trimmed}",
            f"Items Referenced:         {self.items_referenced}",
            "",
            f"Knowledge Retrieved:        {self.chunks_retrieved} chunks",
            f"Chunks Used by Model:       {self.chunks_used}",
            f"Chunks Referenced in Answer: {self.chunks_referenced}",
            "",
            f"Answer Supported by Sources: {self.answer_support_pct:.0f}%",
            f"Unused Context:             {self.unused_context_pct:.0f}%",
            f"Average Retrieval Score:    {self.avg_retrieval_score:.2f}",
            f"Average Kept Item Score:    {self.avg_kept_score:.2f}",
            f"Answer Tokens:              {self.answer_tokens:,}",
        ]

        # Per-item breakdown (top 5 referenced, top 5 unused)
        referenced = [e for e in self.item_evaluations if e.referenced]
        unused = [e for e in self.item_evaluations if e.kept and not e.referenced]

        if referenced:
            lines.append("\nReferenced Items:")
            for e in sorted(referenced, key=lambda x: x.citation_count, reverse=True)[:5]:
                lines.append(f"  ✓ {e.title} ({e.item_type}, score={e.score:.2f}, {e.citation_count} citations)")

        if unused:
            lines.append("\nUnused (kept but not referenced):")
            for e in sorted(unused, key=lambda x: x.tokens, reverse=True)[:5]:
                lines.append(f"  ✗ {e.title} ({e.item_type}, {e.tokens} tokens wasted)")

        # Retrieval quality
        lines.append("")
        lines.append(self.retrieval_quality.format_for_display())

        return "\n".join(lines)


class ContextEvaluator:
    """Evaluates a context build against an LLM answer.

    After the LLM responds, call `evaluate()` with:
    - The ranked items from the context build
    - The LLM's answer text

    It analyses which items were referenced in the answer and computes
    the post-hoc metrics.
    """

    # Minimum overlap to consider an item "referenced" in the answer
    MIN_REFERENCE_OVERLAP = 0.15  # 15% of item's key phrases appear in answer

    @classmethod
    def evaluate(
        cls,
        ranked_items: list[ContextItem],
        answer_text: str,
        knowledge_chunks: list[dict[str, Any]] | None = None,
    ) -> ContextEvaluation:
        """Evaluate how well the context build supported the LLM answer.

        Args:
            ranked_items: All context items (with kept/trimmed status and scores)
            answer_text: The LLM's response text
            knowledge_chunks: Raw knowledge chunks (for retrieval score metadata)

        Returns:
            ContextEvaluation with all metrics computed
        """
        eval_result = ContextEvaluation()
        eval_result.answer_text = answer_text
        eval_result.answer_tokens = estimate_tokens(answer_text)

        answer_lower = answer_text.lower()
        answer_words = set(answer_lower.split())

        kept_items = [i for i in ranked_items if i.kept]
        trimmed_items = [i for i in ranked_items if not i.kept]

        eval_result.items_total = len(ranked_items)
        eval_result.items_kept = len(kept_items)
        eval_result.items_trimmed = len(trimmed_items)

        # Knowledge chunk counts
        knowledge_items = [i for i in ranked_items if i.type == ContextItemType.KNOWLEDGE_CHUNK]
        eval_result.chunks_retrieved = len(knowledge_items)
        eval_result.chunks_used = len([i for i in knowledge_items if i.kept])

        # Average retrieval score (from knowledge chunk similarity)
        if knowledge_items:
            scores = [i.metadata.get("similarity_score", 0.5) for i in knowledge_items]
            eval_result.avg_retrieval_score = sum(scores) / len(scores)

        # Average kept item score
        if kept_items:
            eval_result.avg_kept_score = sum(i.score for i in kept_items) / len(kept_items)

        # Per-item evaluation: detect references
        referenced_count = 0
        chunks_referenced = 0
        referenced_tokens = 0
        total_kept_tokens = sum(i.tokens for i in kept_items)

        for item in ranked_items:
            item_eval = ItemEvaluation(
                title=item.title,
                item_type=item.type.value,
                source=item.source,
                score=item.score,
                tokens=item.tokens,
                kept=item.kept,
                source_title=item.title,  # For source-level learning
                chunk_id=item.metadata.get("chunk_id", ""),  # For chunk-level learning
            )

            if item.kept:
                # Check if this item was referenced in the answer
                overlap = cls._reference_overlap(item, answer_lower, answer_words)
                if overlap >= cls.MIN_REFERENCE_OVERLAP:
                    item_eval.referenced = True
                    item_eval.citation_count = cls._count_citations(item, answer_lower)
                    referenced_count += 1
                    referenced_tokens += item.tokens
                    if item.type == ContextItemType.KNOWLEDGE_CHUNK:
                        chunks_referenced += 1

            eval_result.item_evaluations.append(item_eval)

        eval_result.items_referenced = referenced_count
        eval_result.chunks_referenced = chunks_referenced

        # Answer support: what % of the answer is supported by referenced context?
        # Heuristic: ratio of referenced tokens to answer tokens (capped at 100%)
        if eval_result.answer_tokens > 0:
            eval_result.answer_support_pct = min(
                100.0,
                (referenced_tokens / eval_result.answer_tokens) * 100.0,
            )

        # Unused context: what % of kept tokens were NOT referenced?
        if total_kept_tokens > 0:
            unused_tokens = total_kept_tokens - referenced_tokens
            eval_result.unused_context_pct = (unused_tokens / total_kept_tokens) * 100.0

        # Retrieval quality metrics (independent of the answer)
        eval_result.retrieval_quality = cls._evaluate_retrieval(ranked_items, referenced_count)

        return eval_result

    @classmethod
    def _evaluate_retrieval(
        cls,
        ranked_items: list[ContextItem],
        referenced_count: int,
    ) -> RetrievalQuality:
        """Evaluate the quality of the retrieval itself.

        Metrics:
        - recall: Of the items we kept, how many were actually referenced?
          (High recall = we retrieved the right things)
        - precision: Of all items retrieved, how many were kept and useful?
          (High precision = we didn't retrieve junk)
        - novelty: How much unique information per chunk?
          (Low novelty = chunks are repetitive)
        - duplicate_count: Chunks that repeat existing info
        - chunk_diversity: Are chunks topically diverse?
        - provider_diversity: How many distinct providers contributed?
        """
        rq = RetrievalQuality()

        kept_items = [i for i in ranked_items if i.kept]
        if not kept_items:
            return rq

        # Recall: referenced / kept (were the kept items actually useful?)
        rq.recall = referenced_count / len(kept_items) if kept_items else 0.0

        # Precision: kept / total (did we trim well, or keep too much?)
        rq.precision = len(kept_items) / len(ranked_items) if ranked_items else 0.0

        # Novelty: 1 - average pairwise overlap between chunks
        # If chunks share a lot of words, novelty is low
        knowledge_items = [i for i in kept_items if i.type == ContextItemType.KNOWLEDGE_CHUNK]
        if len(knowledge_items) >= 2:
            overlaps: list[float] = []
            for i in range(len(knowledge_items)):
                for j in range(i + 1, len(knowledge_items)):
                    overlap = cls._content_overlap(knowledge_items[i], knowledge_items[j])
                    overlaps.append(overlap)
            avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0.0
            rq.novelty = max(0.0, 1.0 - avg_overlap)

            # Duplicate count: chunks with very high overlap (> 0.7)
            rq.duplicate_count = sum(1 for o in overlaps if o > 0.7)
            rq.duplicate_pct = (rq.duplicate_count / len(overlaps) * 100.0) if overlaps else 0.0
        else:
            rq.novelty = 1.0  # Single chunk = fully novel
            rq.duplicate_count = 0
            rq.duplicate_pct = 0.0

        # Chunk diversity: based on unique significant words across all chunks
        if knowledge_items:
            all_words: set[str] = set()
            per_chunk_words: list[set[str]] = []
            for item in knowledge_items:
                words = cls._extract_significant_words(item.content)
                per_chunk_words.append(words)
                all_words.update(words)
            # Diversity = unique words / total words (higher = more diverse)
            total_words = sum(len(w) for w in per_chunk_words)
            if total_words > 0:
                rq.chunk_diversity = len(all_words) / total_words
            else:
                rq.chunk_diversity = 0.0
        else:
            rq.chunk_diversity = 0.0

        # Provider diversity: how many distinct providers contributed?
        providers = set(i.source for i in kept_items if i.source)
        rq.provider_diversity = len(providers)

        # Average chunk length
        if kept_items:
            rq.avg_chunk_length = sum(i.tokens for i in kept_items) / len(kept_items)

        return rq

    @staticmethod
    def _reference_overlap(item: ContextItem, answer_lower: str, answer_words: set[str]) -> float:
        """Compute how much of an item's content appears in the answer.

        Uses a key-phrase matching approach:
        - Extract significant words from the item (length > 4, not stopwords)
        - Check how many appear in the answer
        - Return the overlap ratio (0.0 to 1.0)
        """
        if not item.content:
            return 0.0

        # Simple stopword set
        stopwords = {
            "the", "and", "for", "are", "but", "not", "you", "all", "any",
            "can", "had", "her", "was", "one", "our", "out", "has", "have",
            "from", "this", "that", "with", "will", "your", "they", "them",
            "been", "were", "what", "when", "which", "their", "would",
            "about", "there", "could", "other", "more", "such", "only",
            "some", "than", "very", "into", "also", "just", "like",
        }

        item_words = set()
        for word in item.content.lower().split():
            # Strip punctuation
            clean = word.strip(".,;:!?\"'()[]{}-—_/")
            if len(clean) > 4 and clean not in stopwords:
                item_words.add(clean)

        if not item_words:
            # Fall back to short words if no significant words
            for word in item.content.lower().split():
                clean = word.strip(".,;:!?\"'()[]{}-—_/")
                if len(clean) > 2 and clean not in stopwords:
                    item_words.add(clean)

        if not item_words:
            return 0.0

        # Check overlap
        matched = sum(1 for w in item_words if w in answer_words)
        return matched / len(item_words)

    @staticmethod
    def _count_citations(item: ContextItem, answer_lower: str) -> int:
        """Count how many times the item's title or key phrases appear in the answer."""
        if not item.title:
            return 0
        title_lower = item.title.lower()
        count = answer_lower.count(title_lower)
        # Also check for the first few significant words
        words = [w for w in item.content.lower().split() if len(w) > 6]
        for word in words[:3]:
            count += answer_lower.count(word)
        return count

    @staticmethod
    def _extract_significant_words(text: str) -> set[str]:
        """Extract significant words from text (for diversity/novelty metrics)."""
        stopwords = {
            "the", "and", "for", "are", "but", "not", "you", "all", "any",
            "can", "had", "her", "was", "one", "our", "out", "has", "have",
            "from", "this", "that", "with", "will", "your", "they", "them",
            "been", "were", "what", "when", "which", "their", "would",
            "about", "there", "could", "other", "more", "such", "only",
            "some", "than", "very", "into", "also", "just", "like",
        }
        words: set[str] = set()
        for word in text.lower().split():
            clean = word.strip(".,;:!?\"'()[]{}-—_/")
            if len(clean) > 3 and clean not in stopwords:
                words.add(clean)
        return words

    @staticmethod
    def _content_overlap(item_a: ContextItem, item_b: ContextItem) -> float:
        """Compute content overlap between two items (Jaccard similarity).

        Returns 0.0 to 1.0 — 1.0 means identical content, 0.0 means no overlap.
        Used to detect duplicate chunks and measure novelty.
        """
        words_a = ContextEvaluator._extract_significant_words(item_a.content)
        words_b = ContextEvaluator._extract_significant_words(item_b.content)
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union) if union else 0.0


# ─── Learning Feedback Loop (Adaptive Ranking Weights) ──────────────────────
#
# The ranking layer starts with fixed BASE_SCORES, but over time it should
# learn which context types and providers actually add value.
#
# Feedback pipeline:
#
#   Context Item
#       ↓
#   Selected? (kept by ranking)
#       ↓
#   Referenced in final answer?
#       ↓
#   User accepted?
#       ↓
#   Positive outcome?
#       ↓
#   Increase future ranking weight
#
# This is an EXTENSION of the existing ranking layer — not a separate
# architectural pillar. The ContextRankingLayer accepts optional
# LearnedWeights that adjust the base scores.


@dataclass
class FeedbackRecord:
    """A single feedback record for one context item.

    Supports granular identity at three levels:
    1. item_type — "knowledge_chunk" (coarsest, always present)
    2. source_title — "Brand Guidelines" (medium, the item's title)
    3. chunk_id — "chunk_abc123" (finest, unique per chunk)

    The feedback store computes adjustments at all three levels and
    combines them: total_adjustment = type_adj + source_adj + chunk_adj.
    """
    item_type: str
    source: str          # provider name (e.g., "knowledge")
    kept: bool           # Was it kept by ranking?
    referenced: bool     # Was it referenced in the answer?
    user_accepted: bool | None = None
    positive_outcome: bool | None = None
    score: float = 0.0   # The ranking score it had
    timestamp: float = 0.0
    # Granular identity (for source-level and chunk-level learning)
    source_title: str = ""   # e.g., "Brand Guidelines", "Pricing Catalogue"
    chunk_id: str = ""       # Unique chunk identifier (for knowledge chunks)

    @property
    def outcome_score(self) -> float:
        """Compute a -1.0 to +1.0 outcome score for this feedback.

        Positive outcomes increase future weight; negative decrease it.
        """
        if not self.kept:
            return 0.0  # No signal — wasn't in the prompt

        score = 0.0
        if self.referenced:
            score += 0.3  # Referenced is good
        else:
            score -= 0.1  # Kept but not referenced is mildly bad (wasted tokens)

        if self.user_accepted is True:
            score += 0.3
        elif self.user_accepted is False:
            score -= 0.3

        if self.positive_outcome is True:
            score += 0.4
        elif self.positive_outcome is False:
            score -= 0.4

        return max(-1.0, min(1.0, score))


@dataclass
class TypeWeightAdjustment:
    """Learned weight adjustment for a context item type."""
    item_type: str
    adjustment: float = 0.0       # Additive adjustment to base score
    samples: int = 0              # Number of feedback samples
    avg_outcome: float = 0.0      # Average outcome score

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_type": self.item_type,
            "adjustment": round(self.adjustment, 4),
            "samples": self.samples,
            "avg_outcome": round(self.avg_outcome, 4),
        }


@dataclass
class SourceWeightAdjustment:
    """Learned weight adjustment for a specific source (e.g., "Brand Guidelines").

    More granular than TypeWeightAdjustment — learns that some sources
    are consistently more valuable than others, even within the same type.

    Example:
        Knowledge Source          Adjustment
        Brand Guidelines          +0.08
        Pricing Catalogue         +0.15
        Campaign Archive          -0.02
    """
    source_title: str
    item_type: str
    adjustment: float = 0.0
    samples: int = 0
    avg_outcome: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_title": self.source_title,
            "item_type": self.item_type,
            "adjustment": round(self.adjustment, 4),
            "samples": self.samples,
            "avg_outcome": round(self.avg_outcome, 4),
        }


@dataclass
class ChunkWeightAdjustment:
    """Learned weight adjustment for a specific chunk (finest granularity).

    Example:
        Chunk ID                  Adjustment
        chunk_abc123              +0.12
        chunk_def456              -0.05
    """
    chunk_id: str
    adjustment: float = 0.0
    samples: int = 0
    avg_outcome: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "adjustment": round(self.adjustment, 4),
            "samples": self.samples,
            "avg_outcome": round(self.avg_outcome, 4),
        }


# ─── Online vs Offline Learning ─────────────────────────────────────────────
#
# Two learning modes:
#
# ONLINE (during normal usage):
#   - Small adjustments applied immediately after each interaction
#   - Bounded to [-0.05, +0.05] per interaction to keep behaviour stable
#   - Uses a low learning rate (0.01-0.05)
#   - Runs automatically in the feedback store
#
# OFFLINE (periodic retraining):
#   - Runs weekly, monthly, or every N interactions
#   - Can safely experiment with larger changes
#   - Recomputes the relative importance (weights) of scoring factors:
#       semantic relevance, recency, confidence, intent alignment, type priors
#   - Can change BASE_SCORES themselves (not just adjustments)
#   - Results are committed as a new "model version"


@dataclass
class ScoringWeights:
    """The weights used by the ranking layer to combine scoring factors.

    These are the relative importances of each factor:
    - type_base: how much weight to give the item type's base score
    - semantic: how much weight to give semantic relevance
    - recency: how much weight to give recency
    - confidence: how much weight to give confidence
    - intent: how much weight to give intent alignment

    Default weights (matching the original ContextRankingLayer):
        type_base=0.50, semantic=0.20, recency=0.15, confidence=0.10, intent=0.05

    Offline training can adjust these. For example, if analysis shows
    recency matters more than confidence for a particular tenant, the
    offline trainer might produce:
        type_base=0.45, semantic=0.25, recency=0.20, confidence=0.05, intent=0.05
    """
    type_base: float = 0.50
    semantic: float = 0.20
    recency: float = 0.15
    confidence: float = 0.10
    intent: float = 0.05

    def normalised(self) -> "ScoringWeights":
        """Return a copy with weights normalised to sum to 1.0."""
        total = self.type_base + self.semantic + self.recency + self.confidence + self.intent
        if total == 0:
            return ScoringWeights()
        return ScoringWeights(
            type_base=self.type_base / total,
            semantic=self.semantic / total,
            recency=self.recency / total,
            confidence=self.confidence / total,
            intent=self.intent / total,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type_base": round(self.type_base, 4),
            "semantic": round(self.semantic, 4),
            "recency": round(self.recency, 4),
            "confidence": round(self.confidence, 4),
            "intent": round(self.intent, 4),
        }


@dataclass
class OfflineModelVersion:
    """A versioned snapshot of learned ranking parameters.

    Produced by the offline trainer. Contains:
    - Scoring weights (relative importance of each factor)
    - Base score overrides (adjusted BASE_SCORES)
    - Type/source/chunk adjustments
    - Metadata about the training run
    """
    version: str
    created_at: float = 0.0
    scoring_weights: ScoringWeights = field(default_factory=ScoringWeights)
    base_score_overrides: dict[str, float] = field(default_factory=dict)
    type_adjustments: dict[str, TypeWeightAdjustment] = field(default_factory=dict)
    source_adjustments: dict[str, SourceWeightAdjustment] = field(default_factory=dict)
    chunk_adjustments: dict[str, ChunkWeightAdjustment] = field(default_factory=dict)
    training_samples: int = 0
    avg_outcome: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "scoring_weights": self.scoring_weights.to_dict(),
            "base_score_overrides": {k: round(v, 4) for k, v in self.base_score_overrides.items()},
            "type_adjustments": [a.to_dict() for a in self.type_adjustments.values()],
            "source_adjustments": [a.to_dict() for a in self.source_adjustments.values()],
            "chunk_adjustments": [a.to_dict() for a in self.chunk_adjustments.values()],
            "training_samples": self.training_samples,
            "avg_outcome": round(self.avg_outcome, 4),
        }


class RankingFeedbackStore:
    """Stores feedback records and computes learned weight adjustments.

    Supports three levels of granularity:
    1. Type-level: "knowledge_chunk" → +0.06 (coarsest, always available)
    2. Source-level: "Brand Guidelines" → +0.08 (medium, uses source_title)
    3. Chunk-level: "chunk_abc123" → +0.12 (finest, uses chunk_id)

    Supports two learning modes:
    - ONLINE: small adjustments during normal usage (bounded, stable)
    - OFFLINE: periodic retraining that can change scoring weights

    In production, this would be backed by a database table. For now,
    it's in-memory with a clean interface for swapping in a DB-backed store.

    Usage:
        store = RankingFeedbackStore()
        store.record(FeedbackRecord(item_type="knowledge_chunk", source="knowledge",
                                     source_title="Brand Guidelines",
                                     kept=True, referenced=True, user_accepted=True))
        # Type-level adjustment
        store.get_type_adjustment(ContextItemType.KNOWLEDGE_CHUNK)  # → +0.06
        # Source-level adjustment
        store.get_source_adjustment("Brand Guidelines")  # → +0.08
        # Combined adjustment
        store.get_adjustment(item)  # → +0.14 (type + source)

        # Offline retraining
        model = store.run_offline_training()
        # model.scoring_weights might now be different
    """

    # Online adjustment bounds (small, stable)
    ONLINE_TYPE_ADJ_MAX = 0.20
    ONLINE_SOURCE_ADJ_MAX = 0.15
    ONLINE_CHUNK_ADJ_MAX = 0.10

    # Offline adjustment bounds (larger, can retrain more aggressively)
    OFFLINE_TYPE_ADJ_MAX = 0.30
    OFFLINE_SOURCE_ADJ_MAX = 0.25
    OFFLINE_CHUNK_ADJ_MAX = 0.20

    # Sample thresholds for confidence
    TYPE_CONFIDENCE_SAMPLES = 50
    SOURCE_CONFIDENCE_SAMPLES = 20
    CHUNK_CONFIDENCE_SAMPLES = 5

    def __init__(
        self,
        max_records: int = 10000,
        learning_rate: float = 0.05,
        online_learning_rate: float = 0.02,
    ) -> None:
        self._records: list[FeedbackRecord] = []
        self._max_records = max_records
        self._learning_rate = learning_rate
        self._online_learning_rate = online_learning_rate
        # Cached adjustments (invalidated on new records)
        self._type_cache: dict[str, TypeWeightAdjustment] | None = None
        self._source_cache: dict[str, SourceWeightAdjustment] | None = None
        self._chunk_cache: dict[str, ChunkWeightAdjustment] | None = None
        # Offline model (the latest offline-trained model version)
        self._offline_model: OfflineModelVersion | None = None
        # Interaction counter for offline training triggers
        self._interactions_since_offline = 0

    def record(self, feedback: FeedbackRecord) -> None:
        """Record a feedback event."""
        if not feedback.timestamp:
            feedback.timestamp = time.time()

        self._records.append(feedback)
        self._interactions_since_offline += 1

        # Trim if over capacity (keep most recent)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records:]

        # Invalidate caches
        self._type_cache = None
        self._source_cache = None
        self._chunk_cache = None

    def record_from_evaluation(
        self,
        evaluation: ContextEvaluation,
        user_accepted: bool | None = None,
        positive_outcome: bool | None = None,
    ) -> None:
        """Record feedback for all items in a context evaluation.

        Args:
            evaluation: The post-hoc evaluation of a context build
            user_accepted: Did the user accept/regenerate the answer?
            positive_outcome: Did the resulting action have a positive outcome?
        """
        for item_eval in evaluation.item_evaluations:
            self.record(FeedbackRecord(
                item_type=item_eval.item_type,
                source=item_eval.source,
                kept=item_eval.kept,
                referenced=item_eval.referenced,
                user_accepted=user_accepted,
                positive_outcome=positive_outcome,
                score=item_eval.score,
                source_title=item_eval.source_title if hasattr(item_eval, "source_title") else "",
                chunk_id=item_eval.chunk_id if hasattr(item_eval, "chunk_id") else "",
            ))

    # ─── Type-Level Adjustments (coarsest) ──────────────────────────────

    def compute_type_adjustments(self) -> dict[str, TypeWeightAdjustment]:
        """Compute weight adjustments per item type from feedback history."""
        if self._type_cache is not None:
            return self._type_cache

        by_type: dict[str, list[FeedbackRecord]] = {}
        for record in self._records:
            by_type.setdefault(record.item_type, []).append(record)

        adjustments: dict[str, TypeWeightAdjustment] = {}
        for item_type, records in by_type.items():
            kept_records = [r for r in records if r.kept]
            if not kept_records:
                continue

            outcomes = [r.outcome_score for r in kept_records]
            avg_outcome = sum(outcomes) / len(outcomes)
            confidence = min(1.0, len(kept_records) / self.TYPE_CONFIDENCE_SAMPLES)
            adjustment = self._online_learning_rate * avg_outcome * confidence * 4.0
            adjustment = max(-self.ONLINE_TYPE_ADJ_MAX, min(self.ONLINE_TYPE_ADJ_MAX, adjustment))

            adjustments[item_type] = TypeWeightAdjustment(
                item_type=item_type,
                adjustment=adjustment,
                samples=len(kept_records),
                avg_outcome=avg_outcome,
            )

        self._type_cache = adjustments
        return adjustments

    # ─── Source-Level Adjustments (medium granularity) ───────────────────

    def compute_source_adjustments(self) -> dict[str, SourceWeightAdjustment]:
        """Compute weight adjustments per source title from feedback history.

        This is more granular than type-level: it learns that "Brand Guidelines"
        is more valuable than "Campaign Archive", even though both are knowledge chunks.
        """
        if self._source_cache is not None:
            return self._source_cache

        by_source: dict[str, list[FeedbackRecord]] = {}
        for record in self._records:
            if not record.source_title:
                continue
            key = f"{record.item_type}:{record.source_title}"
            by_source.setdefault(key, []).append(record)

        adjustments: dict[str, SourceWeightAdjustment] = {}
        for key, records in by_source.items():
            kept_records = [r for r in records if r.kept]
            if not kept_records:
                continue

            outcomes = [r.outcome_score for r in kept_records]
            avg_outcome = sum(outcomes) / len(outcomes)
            confidence = min(1.0, len(kept_records) / self.SOURCE_CONFIDENCE_SAMPLES)
            adjustment = self._online_learning_rate * avg_outcome * confidence * 3.0
            adjustment = max(-self.ONLINE_SOURCE_ADJ_MAX, min(self.ONLINE_SOURCE_ADJ_MAX, adjustment))

            # Use the source_title from the first record
            source_title = kept_records[0].source_title
            item_type = kept_records[0].item_type

            adjustments[key] = SourceWeightAdjustment(
                source_title=source_title,
                item_type=item_type,
                adjustment=adjustment,
                samples=len(kept_records),
                avg_outcome=avg_outcome,
            )

        self._source_cache = adjustments
        return adjustments

    # ─── Chunk-Level Adjustments (finest granularity) ────────────────────

    def compute_chunk_adjustments(self) -> dict[str, ChunkWeightAdjustment]:
        """Compute weight adjustments per chunk ID from feedback history.

        This is the finest granularity: each individual chunk gets its own
        adjustment based on how often it's referenced and accepted.
        """
        if self._chunk_cache is not None:
            return self._chunk_cache

        by_chunk: dict[str, list[FeedbackRecord]] = {}
        for record in self._records:
            if not record.chunk_id:
                continue
            by_chunk.setdefault(record.chunk_id, []).append(record)

        adjustments: dict[str, ChunkWeightAdjustment] = {}
        for chunk_id, records in by_chunk.items():
            kept_records = [r for r in records if r.kept]
            if not kept_records:
                continue

            outcomes = [r.outcome_score for r in kept_records]
            avg_outcome = sum(outcomes) / len(outcomes)
            confidence = min(1.0, len(kept_records) / self.CHUNK_CONFIDENCE_SAMPLES)
            adjustment = self._online_learning_rate * avg_outcome * confidence * 2.0
            adjustment = max(-self.ONLINE_CHUNK_ADJ_MAX, min(self.ONLINE_CHUNK_ADJ_MAX, adjustment))

            adjustments[chunk_id] = ChunkWeightAdjustment(
                chunk_id=chunk_id,
                adjustment=adjustment,
                samples=len(kept_records),
                avg_outcome=avg_outcome,
            )

        self._chunk_cache = adjustments
        return adjustments

    # ─── Combined Adjustment (all three levels) ──────────────────────────

    def get_adjustment(self, item: ContextItem) -> float:
        """Get the combined learned adjustment for a context item.

        Combines type-level + source-level + chunk-level adjustments:
            total = type_adj + source_adj + chunk_adj

        This lets the system discover that some sources are consistently
        more valuable than others, and some specific chunks are gold.
        """
        total = 0.0

        # Type-level
        type_adj = self.get_type_adjustment(item.type)
        total += type_adj

        # Source-level (if the item has a title)
        if item.title:
            source_adj = self.get_source_adjustment(item.title, item.type)
            total += source_adj

        # Chunk-level (if the item has a chunk_id)
        chunk_id = item.metadata.get("chunk_id", "")
        if chunk_id:
            chunk_adj = self.get_chunk_adjustment(chunk_id)
            total += chunk_adj

        return total

    def get_type_adjustment(self, item_type: ContextItemType) -> float:
        """Get the type-level learned adjustment."""
        adjustments = self.compute_type_adjustments()
        adj = adjustments.get(item_type.value)
        return adj.adjustment if adj else 0.0

    def get_source_adjustment(self, source_title: str, item_type: ContextItemType | None = None) -> float:
        """Get the source-level learned adjustment for a specific source title."""
        adjustments = self.compute_source_adjustments()
        # Try with type prefix first, then without
        if item_type:
            key = f"{item_type.value}:{source_title}"
            adj = adjustments.get(key)
            if adj:
                return adj.adjustment
        # Fallback: search by source_title
        for adj in adjustments.values():
            if adj.source_title == source_title:
                return adj.adjustment
        return 0.0

    def get_chunk_adjustment(self, chunk_id: str) -> float:
        """Get the chunk-level learned adjustment for a specific chunk."""
        adjustments = self.compute_chunk_adjustments()
        adj = adjustments.get(chunk_id)
        return adj.adjustment if adj else 0.0

    # ─── Offline Training ────────────────────────────────────────────────

    def run_offline_training(self, version: str = "") -> OfflineModelVersion:
        """Run offline training to produce a new model version.

        Offline training can:
        1. Recompute scoring weights (relative importance of factors)
        2. Adjust BASE_SCORES themselves (not just adjustments)
        3. Use larger adjustment bounds than online learning
        4. Experiment with different weight configurations

        This should be called periodically (weekly/monthly/every 10K interactions).
        The resulting model version can be inspected, A/B tested, and
        rolled back if it degrades performance.

        Returns:
            OfflineModelVersion with the new learned parameters
        """
        if not version:
            version = f"v{int(time.time())}"

        # Compute adjustments with offline bounds (larger)
        type_adjustments = self._compute_type_adjustments(offline=True)
        source_adjustments = self._compute_source_adjustments(offline=True)
        chunk_adjustments = self._compute_chunk_adjustments(offline=True)

        # Recompute scoring weights based on which factors correlated with
        # positive outcomes. This is a simplified heuristic:
        # - If referenced items had high semantic scores → increase semantic weight
        # - If recent items were more often referenced → increase recency weight
        # - If high-confidence items were more often referenced → increase confidence weight
        scoring_weights = self._optimise_scoring_weights()

        # Compute base score overrides (adjust BASE_SCORES based on outcomes)
        base_score_overrides = self._compute_base_score_overrides()

        # Compute overall stats
        all_kept = [r for r in self._records if r.kept]
        avg_outcome = (
            sum(r.outcome_score for r in all_kept) / len(all_kept)
            if all_kept else 0.0
        )

        model = OfflineModelVersion(
            version=version,
            created_at=time.time(),
            scoring_weights=scoring_weights,
            base_score_overrides=base_score_overrides,
            type_adjustments=type_adjustments,
            source_adjustments=source_adjustments,
            chunk_adjustments=chunk_adjustments,
            training_samples=len(all_kept),
            avg_outcome=avg_outcome,
        )

        self._offline_model = model
        self._interactions_since_offline = 0
        return model

    def _compute_type_adjustments(self, offline: bool = False) -> dict[str, TypeWeightAdjustment]:
        """Compute type adjustments (shared logic for online/offline)."""
        adj_max = self.OFFLINE_TYPE_ADJ_MAX if offline else self.ONLINE_TYPE_ADJ_MAX
        rate = self._learning_rate if offline else self._online_learning_rate

        by_type: dict[str, list[FeedbackRecord]] = {}
        for record in self._records:
            by_type.setdefault(record.item_type, []).append(record)

        adjustments: dict[str, TypeWeightAdjustment] = {}
        for item_type, records in by_type.items():
            kept_records = [r for r in records if r.kept]
            if not kept_records:
                continue
            outcomes = [r.outcome_score for r in kept_records]
            avg_outcome = sum(outcomes) / len(outcomes)
            confidence = min(1.0, len(kept_records) / self.TYPE_CONFIDENCE_SAMPLES)
            adjustment = rate * avg_outcome * confidence * 4.0
            adjustment = max(-adj_max, min(adj_max, adjustment))
            adjustments[item_type] = TypeWeightAdjustment(
                item_type=item_type, adjustment=adjustment,
                samples=len(kept_records), avg_outcome=avg_outcome,
            )
        return adjustments

    def _compute_source_adjustments(self, offline: bool = False) -> dict[str, SourceWeightAdjustment]:
        """Compute source adjustments (shared logic for online/offline)."""
        adj_max = self.OFFLINE_SOURCE_ADJ_MAX if offline else self.ONLINE_SOURCE_ADJ_MAX
        rate = self._learning_rate if offline else self._online_learning_rate

        by_source: dict[str, list[FeedbackRecord]] = {}
        for record in self._records:
            if not record.source_title:
                continue
            key = f"{record.item_type}:{record.source_title}"
            by_source.setdefault(key, []).append(record)

        adjustments: dict[str, SourceWeightAdjustment] = {}
        for key, records in by_source.items():
            kept_records = [r for r in records if r.kept]
            if not kept_records:
                continue
            outcomes = [r.outcome_score for r in kept_records]
            avg_outcome = sum(outcomes) / len(outcomes)
            confidence = min(1.0, len(kept_records) / self.SOURCE_CONFIDENCE_SAMPLES)
            adjustment = rate * avg_outcome * confidence * 3.0
            adjustment = max(-adj_max, min(adj_max, adjustment))
            source_title = kept_records[0].source_title
            item_type = kept_records[0].item_type
            adjustments[key] = SourceWeightAdjustment(
                source_title=source_title, item_type=item_type,
                adjustment=adjustment, samples=len(kept_records),
                avg_outcome=avg_outcome,
            )
        return adjustments

    def _compute_chunk_adjustments(self, offline: bool = False) -> dict[str, ChunkWeightAdjustment]:
        """Compute chunk adjustments (shared logic for online/offline)."""
        adj_max = self.OFFLINE_CHUNK_ADJ_MAX if offline else self.ONLINE_CHUNK_ADJ_MAX
        rate = self._learning_rate if offline else self._online_learning_rate

        by_chunk: dict[str, list[FeedbackRecord]] = {}
        for record in self._records:
            if not record.chunk_id:
                continue
            by_chunk.setdefault(record.chunk_id, []).append(record)

        adjustments: dict[str, ChunkWeightAdjustment] = {}
        for chunk_id, records in by_chunk.items():
            kept_records = [r for r in records if r.kept]
            if not kept_records:
                continue
            outcomes = [r.outcome_score for r in kept_records]
            avg_outcome = sum(outcomes) / len(outcomes)
            confidence = min(1.0, len(kept_records) / self.CHUNK_CONFIDENCE_SAMPLES)
            adjustment = rate * avg_outcome * confidence * 2.0
            adjustment = max(-adj_max, min(adj_max, adjustment))
            adjustments[chunk_id] = ChunkWeightAdjustment(
                chunk_id=chunk_id, adjustment=adjustment,
                samples=len(kept_records), avg_outcome=avg_outcome,
            )
        return adjustments

    def _optimise_scoring_weights(self) -> ScoringWeights:
        """Optimise scoring weights based on feedback correlations.

        Heuristic approach:
        - Look at items that were referenced (positive signal)
        - Check which scoring factors were high for those items
        - Increase weights for factors that correlate with positive outcomes

        In production, this would use proper optimisation (gradient descent,
        Bayesian optimisation, or bandit algorithms). Here we use a simple
        correlation heuristic.
        """
        kept_records = [r for r in self._records if r.kept]
        if len(kept_records) < 20:
            return ScoringWeights()  # Not enough data

        # Split into positive (referenced + accepted) and negative (not referenced)
        positive = [r for r in kept_records if r.referenced and r.user_accepted is not False]
        negative = [r for r in kept_records if not r.referenced]

        if not positive or not negative:
            return ScoringWeights()

        # The score field tells us the ranking score the item had.
        # Higher scores for positive items → current weights are good.
        # Lower scores for positive items → weights need adjustment.
        avg_positive_score = sum(r.score for r in positive) / len(positive)
        avg_negative_score = sum(r.score for r in negative) / len(negative)

        # If positive items had lower scores than negative, we need to
        # shift weight toward factors that would have ranked them higher.
        # Since we don't have per-factor breakdowns in the record, we use
        # a simple heuristic: if the model is underperforming, slightly
        # increase semantic and recency weights (the most adaptive factors).
        weights = ScoringWeights()

        if avg_positive_score < avg_negative_score:
            # Model is underperforming — shift weight toward adaptive factors
            weights.semantic = 0.25
            weights.recency = 0.20
            weights.type_base = 0.40
            weights.confidence = 0.10
            weights.intent = 0.05
        else:
            # Model is performing well — keep weights close to default
            weights = ScoringWeights()

        return weights.normalised()

    def _compute_base_score_overrides(self) -> dict[str, float]:
        """Compute adjustments to BASE_SCORES based on feedback.

        If a type consistently has positive outcomes, increase its base score.
        If consistently negative, decrease it.
        """
        overrides: dict[str, float] = {}
        type_adjs = self._compute_type_adjustments(offline=True)
        for item_type, adj in type_adjs.items():
            # Apply a fraction of the adjustment to the base score itself
            base = BASE_SCORES.get(ContextItemType(item_type), 0.5)
            new_base = base + (adj.adjustment * 0.5)  # Half the adjustment goes to base
            new_base = max(0.05, min(1.0, new_base))
            overrides[item_type] = new_base
        return overrides

    def get_offline_model(self) -> OfflineModelVersion | None:
        """Get the current offline model version (or None if not yet trained)."""
        return self._offline_model

    def should_run_offline(self, threshold: int = 10000) -> bool:
        """Check if offline training should run (based on interaction count)."""
        return self._interactions_since_offline >= threshold

    # ─── Stats & Observability ───────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return summary statistics for observability."""
        type_adjs = self.compute_type_adjustments()
        source_adjs = self.compute_source_adjustments()
        chunk_adjs = self.compute_chunk_adjustments()
        return {
            "total_records": len(self._records),
            "types_tracked": len(type_adjs),
            "sources_tracked": len(source_adjs),
            "chunks_tracked": len(chunk_adjs),
            "type_adjustments": [a.to_dict() for a in type_adjs.values()],
            "source_adjustments": [a.to_dict() for a in source_adjs.values()],
            "chunk_adjustments": [a.to_dict() for a in chunk_adjs.values()],
            "learning_rate": self._learning_rate,
            "online_learning_rate": self._online_learning_rate,
            "interactions_since_offline": self._interactions_since_offline,
            "offline_model": self._offline_model.to_dict() if self._offline_model else None,
        }


# ─── Extended Ranking Layer with Learned Weights ────────────────────────────


class AdaptiveContextRankingLayer(ContextRankingLayer):
    """Ranking layer that uses learned weights from feedback.

    Extends ContextRankingLayer — same interface, but scores are adjusted
    based on real usage outcomes recorded in the feedback store.

    Three levels of granularity:
    1. Type-level: "knowledge_chunk" → +0.06
    2. Source-level: "Brand Guidelines" → +0.08
    3. Chunk-level: "chunk_abc123" → +0.12
    Total adjustment = type + source + chunk

    Two learning modes:
    - ONLINE: small adjustments during normal usage (automatic)
    - OFFLINE: periodic retraining that can change scoring weights

    Usage:
        feedback_store = RankingFeedbackStore()
        ranking = AdaptiveContextRankingLayer(feedback_store=feedback_store)

        # ... after LLM responds ...
        evaluation = ContextEvaluator.evaluate(ranked_items, answer_text)
        feedback_store.record_from_evaluation(evaluation, user_accepted=True)

        # Periodically (e.g., weekly):
        model = feedback_store.run_offline_training()
        ranking.apply_offline_model(model)

        # Next build will use adjusted weights + offline scoring weights
    """

    def __init__(
        self,
        feedback_store: RankingFeedbackStore | None = None,
        token_budget: int = 4000,
        min_items: int = 3,
        always_keep_types: set[ContextItemType] | None = None,
    ) -> None:
        super().__init__(
            token_budget=token_budget,
            min_items=min_items,
            always_keep_types=always_keep_types,
        )
        self._feedback_store = feedback_store
        # Offline model (applied when available)
        self._offline_model: OfflineModelVersion | None = None
        # Scoring weights (can be overridden by offline training)
        self._scoring_weights: ScoringWeights = ScoringWeights()
        # Base score overrides (from offline training)
        self._base_score_overrides: dict[str, float] = {}

    def apply_offline_model(self, model: OfflineModelVersion) -> None:
        """Apply an offline-trained model version.

        This updates:
        - Scoring weights (relative importance of each factor)
        - Base score overrides (adjusted BASE_SCORES)
        """
        self._offline_model = model
        self._scoring_weights = model.scoring_weights
        self._base_score_overrides = model.base_score_overrides
        log.info(
            "Applied offline model %s: weights=%s, %d base overrides",
            model.version,
            model.scoring_weights.to_dict(),
            len(model.base_score_overrides),
        )

    def score_item(
        self,
        item: ContextItem,
        message: str = "",
        intent: str = "",
    ) -> float:
        """Score an item, applying learned adjustments on top of the base score.

        Uses the offline-trained scoring weights (if available) instead of
        the hardcoded weights, and applies granular adjustments:
            total_adjustment = type_adj + source_adj + chunk_adj
        """
        # 1. Get the base type score (possibly overridden by offline training)
        base = self._base_score_overrides.get(
            item.type.value,
            BASE_SCORES.get(item.type, 0.50),
        )

        # 2. Compute individual factor scores (same as parent)
        semantic = 0.5
        if item.type == ContextItemType.KNOWLEDGE_CHUNK:
            semantic = item.metadata.get("similarity_score", 0.5)
        elif item.type == ContextItemType.MEMORY:
            semantic = 0.6

        recency = 0.5
        created_at = item.metadata.get("created_at")
        if created_at:
            recency = self._recency_score(created_at)
        elif item.metadata.get("age_days") is not None:
            age_days = item.metadata["age_days"]
            recency = max(0.1, 1.0 - (age_days / 365))

        confidence = item.metadata.get("confidence", 0.5)
        intent_alignment = self._intent_alignment(item.type, intent)

        # 3. Combine using offline-trained weights (or defaults)
        w = self._scoring_weights
        score = (
            base * w.type_base
            + semantic * w.semantic
            + recency * w.recency
            + confidence * w.confidence
            + intent_alignment * w.intent
        )

        # 4. Apply learned adjustments (granular: type + source + chunk)
        if self._feedback_store:
            adjustment = self._feedback_store.get_adjustment(item)
            score += adjustment

        # 5. Clamp to [0, 1]
        return max(0.0, min(1.0, score))
