"""Knowledge Level Classification & Governance for the Business Knowledge Hub.

The Business Knowledge Hub stores every document the AI engines consult — brand
guidelines, SOPs, campaign briefs, live analytics snapshots, etc. To decide
*which* documents to feed into a given prompt and *when* to refresh them, we
need two things:

1. **Knowledge Level Classification** — every document is bucketed into one of
   four levels that describe how frequently the information changes:

   ┌────────────┬──────────────────────────────────┬──────────────────────┐
   │ Level      │ Description                      │ Typical refresh      │
   ├────────────┼──────────────────────────────────┼──────────────────────┤
   │ brand      │ Identity, pricing, policies      │ Rarely / never       │
   │ business   │ SOPs, processes, team structure  │ ~yearly              │
   │ marketing  │ Campaigns, creatives, media plans│ ~6 months            │
   │ live       │ Integration data (GA, Shopify…)  │ Continuous (≤7 days) │
   └────────────┴──────────────────────────────────┴──────────────────────┘

2. **Knowledge Governance** — every document carries ``GovernanceMetadata``
   (source, version, owner, confidence, permissions, expiry). The
   ``GovernanceChecker`` answers the question *"should this document be used
   right now, for this user?"* by combining freshness, access, and confidence.

This module is dependency-free (stdlib only) so it can be imported by both the
shared package and the API/worker layers without creating cycles.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
#  Knowledge levels
# ─────────────────────────────────────────────────────────────────────────────


class KnowledgeLevel(StrEnum):
    """The four knowledge levels used by the Business Knowledge Hub.

    Ordered from most stable (``brand``) to most volatile (``live``). The
    string values are persisted in the database and surfaced to the frontend,
    so they must remain stable across releases.
    """

    brand = "brand"          # Level 1 — rarely changes
    business = "business"    # Level 2 — operational knowledge
    marketing = "marketing"  # Level 3 — marketing assets
    live = "live"            # Level 4 — continuously updated (integrations)


# ─────────────────────────────────────────────────────────────────────────────
#  Classifier
# ─────────────────────────────────────────────────────────────────────────────


class KnowledgeLevelClassifier:
    """Auto-classifies uploaded documents into the four knowledge levels.

    Classification is a cheap, deterministic heuristic — not an LLM call — so
    it can run synchronously on every upload without budget concerns. The
    signal priority is:

    1. **Integration name** — if the document came from a registered
       integration (Google Analytics, Shopify, …) it is unambiguously ``live``.
    2. **Title keywords** — the title is the highest-quality text signal
       because authors tend to label documents by their type
       ("Brand Guidelines", "Q3 Campaign Brief", …).
    3. **Content keywords** — the first 2000 characters of the body are
       scanned as a fallback when the title is generic.
    4. **Default** — if no signal matches, the document is classified as
       ``business`` because that is the most common bucket for ad-hoc uploads.
    """

    # Level 1 — Brand: things that rarely change
    BRAND_KEYWORDS: list[str] = [
        "brand guidelines", "logo", "colours", "colors", "tone of voice",
        "mission", "vision", "product catalogue", "pricing", "policies",
        "brand book", "style guide", "brand identity",
    ]

    # Level 2 — Business: operational knowledge
    BUSINESS_KEYWORDS: list[str] = [
        "sop", "standard operating procedure", "sales process", "crm",
        "faq", "frequently asked", "customer persona", "service description",
        "team structure", "workflow", "process", "procedure", "manual",
    ]

    # Level 3 — Marketing: marketing assets
    MARKETING_KEYWORDS: list[str] = [
        "campaign", "ad creative", "landing page", "email campaign",
        "blog post", "video script", "seo report", "social media post",
        "ad copy", "creative brief", "media plan",
    ]

    # Level 4 — Live: continuously updated (from integrations)
    LIVE_SOURCES: list[str] = [
        "google_analytics", "shopify", "hubspot", "mailchimp", "wordpress",
        "meta_ads", "google_ads", "search_console",
    ]

    # How much of the content body to scan. Keeps classification O(1)-ish
    # regardless of document size.
    _CONTENT_SCAN_LIMIT: int = 2000

    # ─── Public API ──────────────────────────────────────────────────────

    def classify(
        self,
        title: str,
        content: str = "",
        source_type: str = "",
        integration_name: str = "",
    ) -> KnowledgeLevel:
        """Classify a single document into a :class:`KnowledgeLevel`.

        Args:
            title: Document title — the strongest text signal.
            content: Full document body. Only the first ``2000`` characters
                are inspected; the rest is ignored for performance.
            source_type: How the document entered the hub
                (``upload``, ``url``, ``integration``, ``generated``,
                ``manual``). Currently informational only.
            integration_name: If the document originated from an integration,
                the canonical integration slug (e.g. ``"google_analytics"``).
                When non-empty and recognised, the document is classified as
                ``live`` regardless of title/content.

        Returns:
            A :class:`KnowledgeLevel` (never ``None``).
        """
        # 1. Integration signal — authoritative for "live".
        if integration_name and self._matches_any(integration_name, self.LIVE_SOURCES):
            return KnowledgeLevel.live

        # 2. Title signal — highest-quality text.
        title_l = (title or "").lower()
        if title_l:
            level = self._level_from_keywords(title_l)
            if level is not None:
                return level

        # 3. Content signal — fallback (first N chars only).
        content_slice = (content or "")[: self._CONTENT_SCAN_LIMIT].lower()
        if content_slice:
            level = self._level_from_keywords(content_slice)
            if level is not None:
                return level

        # 4. Default — operational knowledge is the most common bucket.
        return KnowledgeLevel.business

    def classify_batch(self, documents: list[dict]) -> list[KnowledgeLevel]:
        """Classify many documents at once.

        Each dict may contain the keys ``title``, ``content``,
        ``source_type`` and ``integration_name`` (all optional except
        ``title``). Missing keys are treated as empty strings.

        Args:
            documents: List of document dicts.

        Returns:
            A list of :class:`KnowledgeLevel` aligned 1:1 with the input
            order.
        """
        return [
            self.classify(
                title=doc.get("title", ""),
                content=doc.get("content", ""),
                source_type=doc.get("source_type", ""),
                integration_name=doc.get("integration_name", ""),
            )
            for doc in documents
        ]

    # ─── Internals ───────────────────────────────────────────────────────

    @staticmethod
    def _matches_any(haystack: str, needles: list[str]) -> bool:
        """Case-insensitive substring check: does ``haystack`` contain any needle?"""
        h = haystack.lower()
        return any(needle in h for needle in needles)

    def _level_from_keywords(self, text: str) -> KnowledgeLevel | None:
        """Return the first matching level for ``text`` or ``None``.

        Brand is checked first (most specific), then marketing, then
        business. We deliberately check business *last* so that more
        specific signals (e.g. "campaign") are not shadowed by the broad
        business keyword "process".
        """
        if self._matches_any(text, self.BRAND_KEYWORDS):
            return KnowledgeLevel.brand
        if self._matches_any(text, self.MARKETING_KEYWORDS):
            return KnowledgeLevel.marketing
        if self._matches_any(text, self.BUSINESS_KEYWORDS):
            return KnowledgeLevel.business
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Governance metadata
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class GovernanceMetadata:
    """Provenance, ownership and freshness metadata for a knowledge document.

    Every row in the knowledge hub carries one of these. It is the single
    source of truth for *who* can use a document, *whether* it is still
    current, and *how much* to trust it.

    Attributes:
        source: How the document entered the hub. One of
            ``upload``, ``url``, ``integration``, ``generated``, ``manual``.
        version: Monotonically increasing version number. Bumped on every
            edit so callers can detect stale caches.
        owner_id: ID of the user who owns the document (may be ``None`` for
            system-generated content).
        owner_name: Display name of the owner, denormalised for logs/UI.
        confidence: 0.0–1.0 — how confident we are in this source.
            Integrations are typically 0.9+, user uploads ~0.8, AI-generated
            content ~0.6.
        permissions: Visibility scope — ``private``, ``shared`` or ``public``.
        expires_at: When the document is considered stale. ``None`` means
            "never expires" (used for brand-level docs).
        tags: Free-form tags for search/filtering.
        workspace_id: The workspace the document belongs to. Required for
            ``shared`` permission enforcement.
        created_at: UTC creation timestamp.
        modified_at: UTC last-modified timestamp.
    """

    source: str = "upload"
    version: int = 1
    owner_id: str | None = None
    owner_name: str | None = None
    confidence: float = 0.8
    permissions: str = "shared"
    expires_at: datetime | None = None
    tags: list[str] = field(default_factory=list)
    workspace_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    modified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ─── Serialization ───────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict (for DB JSON columns / API responses)."""
        return {
            "source": self.source,
            "version": self.version,
            "owner_id": self.owner_id,
            "owner_name": self.owner_name,
            "confidence": self.confidence,
            "permissions": self.permissions,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "tags": list(self.tags),
            "workspace_id": self.workspace_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "GovernanceMetadata":
        """Reconstruct from a dict (e.g. a DB JSON column).

        Defensive: unknown keys are ignored, missing keys use defaults,
        and malformed datetimes fall back to ``None``.
        """
        if not data:
            return cls()

        def _parse_dt(v: Any) -> datetime | None:
            if not v:
                return None
            if isinstance(v, datetime):
                return v
            try:
                dt = datetime.fromisoformat(str(v))
                # Ensure timezone-aware (assume UTC if naive).
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, TypeError):
                return None

        return cls(
            source=data.get("source", "upload"),
            version=int(data.get("version", 1)),
            owner_id=data.get("owner_id"),
            owner_name=data.get("owner_name"),
            confidence=float(data.get("confidence", 0.8)),
            permissions=data.get("permissions", "shared"),
            expires_at=_parse_dt(data.get("expires_at")),
            tags=list(data.get("tags", [])),
            workspace_id=data.get("workspace_id"),
            created_at=_parse_dt(data.get("created_at")) or datetime.now(timezone.utc),
            modified_at=_parse_dt(data.get("modified_at")) or datetime.now(timezone.utc),
        )

    def touch(self) -> None:
        """Update ``modified_at`` to now (UTC). Call after any edit."""
        self.modified_at = datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
#  Governance checker
# ─────────────────────────────────────────────────────────────────────────────


# Default expiry deltas per knowledge level. ``None`` means "never expires".
DEFAULT_EXPIRY_DAYS: dict[KnowledgeLevel, int | None] = {
    KnowledgeLevel.brand: None,       # Brand identity rarely changes.
    KnowledgeLevel.business: 365,     # Operational knowledge: refresh yearly.
    KnowledgeLevel.marketing: 180,    # Marketing assets: refresh every 6 months.
    KnowledgeLevel.live: 7,           # Integration snapshots: refresh weekly.
}

# Confidence thresholds for human-readable labels.
_CONFIDENCE_HIGH = 0.75
_CONFIDENCE_MEDIUM = 0.45
# Below _CONFIDENCE_MEDIUM is "low".

# Minimum confidence for a document to be considered usable at all.
# Documents below this are treated as untrustworthy and excluded from prompts.
MIN_USABLE_CONFIDENCE: float = 0.3


class GovernanceChecker:
    """Checks whether a knowledge source is current and should be used.

    The checker is stateless and side-effect free, so a single shared
    instance can be injected anywhere (API routers, Celery workers, AI
    engines). All time comparisons are timezone-aware UTC.
    """

    def is_current(
        self,
        governance: GovernanceMetadata,
        now: datetime | None = None,
    ) -> bool:
        """Return ``True`` if the document has not expired.

        A document is current when ``expires_at`` is ``None`` (never expires)
        or lies in the future relative to ``now``.

        Args:
            governance: The document's governance metadata.
            now: Override the current time (useful for tests). Defaults to
                UTC now.

        Returns:
            ``True`` if the document is still within its validity window.
        """
        if governance.expires_at is None:
            return True
        now = self._now(now)
        return self._aware(governance.expires_at) > now

    def is_expired(
        self,
        governance: GovernanceMetadata,
        now: datetime | None = None,
    ) -> bool:
        """Return ``True`` if the document has passed its expiry date.

        This is the exact inverse of :meth:`is_current`.
        """
        return not self.is_current(governance, now)

    def is_accessible(
        self,
        governance: GovernanceMetadata,
        user_id: str,
        workspace_id: str | None = None,
    ) -> bool:
        """Return ``True`` if ``user_id`` may access the document.

        Permission model:

        - ``private``: only the owner (``owner_id``) may access.
        - ``shared``: any user in the same ``workspace_id`` may access.
          If the document has no ``workspace_id``, access is denied to
          non-owners (defensive default).
        - ``public``: any user in the tenant may access — we return
          ``True`` for any authenticated ``user_id``.
        - Unknown permission strings default to **denied**.

        Args:
            governance: The document's governance metadata.
            user_id: The user attempting access.
            workspace_id: The workspace the request is scoped to.
        """
        perm = (governance.permissions or "").lower()

        if perm == "private":
            return governance.owner_id is not None and governance.owner_id == user_id

        if perm == "shared":
            # Owner always has access.
            if governance.owner_id is not None and governance.owner_id == user_id:
                return True
            # Otherwise the user must be in the same workspace.
            if governance.workspace_id is None or workspace_id is None:
                return False
            return governance.workspace_id == workspace_id

        if perm == "public":
            return bool(user_id)

        # Unknown permission — fail closed.
        return False

    def should_use(
        self,
        governance: GovernanceMetadata,
        user_id: str,
        workspace_id: str | None = None,
        now: datetime | None = None,
    ) -> bool:
        """Return ``True`` if the document should be fed into a prompt.

        Combines three gates:

        1. :meth:`is_current` — the document has not expired.
        2. :meth:`is_accessible` — the user may see it.
        3. ``confidence`` — the document's confidence is above
           :data:`MIN_USABLE_CONFIDENCE` (0.3). Below this we assume the
           source is too unreliable to ground an AI response on.

        Args:
            governance: The document's governance metadata.
            user_id: The user the prompt is being built for.
            workspace_id: The workspace scoping the request.
            now: Override the current time (useful for tests).
        """
        if not self.is_current(governance, now):
            return False
        if not self.is_accessible(governance, user_id, workspace_id):
            return False
        if governance.confidence <= MIN_USABLE_CONFIDENCE:
            return False
        return True

    def confidence_label(self, confidence: float) -> str:
        """Map a 0–1 confidence score to a human-readable label.

        Returns:
            ``"high"`` (≥ 0.75), ``"medium"`` (≥ 0.45) or ``"low"`` (< 0.45).
        """
        if confidence >= _CONFIDENCE_HIGH:
            return "high"
        if confidence >= _CONFIDENCE_MEDIUM:
            return "medium"
        return "low"

    def recommended_expiry(
        self,
        level: KnowledgeLevel,
        now: datetime | None = None,
    ) -> datetime | None:
        """Return the recommended ``expires_at`` for a knowledge level.

        - ``brand``     → ``None`` (never expires).
        - ``business``  → +365 days.
        - ``marketing`` → +180 days.
        - ``live``      → +7 days.

        Args:
            level: The knowledge level to compute expiry for.
            now: Anchor time (defaults to UTC now). The returned datetime
                is timezone-aware UTC.

        Returns:
            An expiry datetime, or ``None`` for levels that never expire.
        """
        days = DEFAULT_EXPIRY_DAYS.get(level)
        if days is None:
            return None
        return self._now(now) + timedelta(days=days)

    # ─── Internals ───────────────────────────────────────────────────────

    @staticmethod
    def _now(now: datetime | None) -> datetime:
        """Return ``now`` or UTC now, guaranteed timezone-aware."""
        if now is None:
            return datetime.now(timezone.utc)
        return GovernanceChecker._aware(now)

    @staticmethod
    def _aware(dt: datetime) -> datetime:
        """Ensure a datetime is timezone-aware (assume UTC if naive)."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt


__all__ = [
    "KnowledgeLevel",
    "KnowledgeLevelClassifier",
    "GovernanceMetadata",
    "GovernanceChecker",
    "DEFAULT_EXPIRY_DAYS",
    "MIN_USABLE_CONFIDENCE",
]
