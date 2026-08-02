"""Source attribution and workspace isolation for the Business Knowledge Hub.

Every important AI answer in PRACHAR must be traceable back to the source
documents that informed it. When CampaignBrain, Creative Studio, the SEO
engine, or any other AI engine retrieves knowledge from the hub, it records
an :class:`AttributionRecord` via :class:`AttributionTracker`. This creates
an audit trail of *why the AI said what it said* and lets every answer
display a human-readable "Based on:" section, for example::

    Based on:
      - Brand Guidelines v3 (relevance: 92%)
      - Pricing Catalogue 2026 (relevance: 87%)
      - Campaign 'Diwali 2025' (relevance: 75%)

The four knowledge levels (mirroring the ``knowledge_sources`` table) are:
``brand``, ``business``, ``marketing``, and ``live``.

Workspace isolation is enforced by :class:`WorkspaceKnowledgeFilter`, which
builds metadata filter dicts for the vector store and performs visibility
checks so that knowledge from one workspace is never accessible from
another. A source with no ``workspace_id`` is tenant-wide (visible to all
workspaces); a source with ``permissions == "public"`` overrides workspace
isolation.

Architecture rules:
- Domain models never import infrastructure (no SQLAlchemy, no FastAPI).
- All models are dataclasses with defaults for every field.
- This module is fully serialisable (``to_dict`` / ``from_dict``) so records
  can be persisted to the ``knowledge_attributions`` table or shipped over
  the wire.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ─── Constants ────────────────────────────────────────────────────────────────

#: The four canonical knowledge levels, matching the ``knowledge_sources``
#: table's ``level`` column and the migration in ``0013_knowledge_hub``.
KNOWLEDGE_LEVELS: tuple[str, ...] = ("brand", "business", "marketing", "live")

#: Permission values understood by :class:`WorkspaceKnowledgeFilter`.
#: - ``private``: only the owning workspace (and tenant admins).
#: - ``shared``: visible within the owning workspace (default).
#: - ``public``: visible to every workspace in the tenant.
PERMISSIONS: tuple[str, ...] = ("private", "shared", "public")


# ─── Source Citation ──────────────────────────────────────────────────────────


@dataclass
class SourceCitation:
    """A single source citation for an AI answer.

    Represents one knowledge source (or a specific chunk of it) that was
    retrieved and used to produce an AI output. Multiple citations are
    grouped into an :class:`AttributionRecord`.

    Attributes:
        source_id: Unique identifier of the knowledge source (UUID string).
        title: Human-readable title, e.g. ``"Brand Guidelines"``.
        version: Document version (users may upload v2, v3, ...).
        level: Knowledge level — one of :data:`KNOWLEDGE_LEVELS`.
        relevance_score: 0.0–1.0, how relevant this source was to the query.
        chunk_snippet: The specific text that was actually used (truncated
            for display; full chunk is stored separately).
        page_number: Page number within the source document, if applicable.
        retrieved_at: UTC timestamp when the source was retrieved.
    """

    source_id: str = ""
    title: str = ""
    version: int = 1
    level: str = ""  # brand, business, marketing, live
    relevance_score: float = 0.0  # 0-1, how relevant this source was
    chunk_snippet: str = ""  # The specific text that was used
    page_number: int | None = None
    retrieved_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this citation to a plain dict."""
        return {
            "source_id": self.source_id,
            "title": self.title,
            "version": self.version,
            "level": self.level,
            "relevance_score": self.relevance_score,
            "chunk_snippet": self.chunk_snippet,
            "page_number": self.page_number,
            "retrieved_at": self.retrieved_at.isoformat()
            if self.retrieved_at
            else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceCitation:
        """Reconstruct a citation from a plain dict.

        Unknown keys are ignored so the format can evolve without breaking
        older persisted records.
        """
        retrieved_raw = data.get("retrieved_at")
        retrieved_at: datetime
        if isinstance(retrieved_raw, datetime):
            retrieved_at = retrieved_raw
        elif isinstance(retrieved_raw, str) and retrieved_raw:
            retrieved_at = datetime.fromisoformat(retrieved_raw)
        else:
            retrieved_at = datetime.now(timezone.utc)
        return cls(
            source_id=data.get("source_id", ""),
            title=data.get("title", ""),
            version=int(data.get("version", 1) or 1),
            level=data.get("level", ""),
            relevance_score=float(data.get("relevance_score", 0.0) or 0.0),
            chunk_snippet=data.get("chunk_snippet", ""),
            page_number=data.get("page_number"),
            retrieved_at=retrieved_at,
        )

    def format_line(self) -> str:
        """Format this citation as a single ``- Title vN`` line.

        The version suffix is only appended when ``version > 1``. A
        relevance percentage is appended in parentheses when
        ``relevance_score > 0``.
        """
        label = self.title or self.source_id or "Unknown source"
        if self.version and self.version > 1:
            label = f"{label} v{self.version}"
        if self.relevance_score and self.relevance_score > 0.0:
            pct = round(self.relevance_score * 100)
            label = f"{label} (relevance: {pct}%)"
        return f"  - {label}"


# ─── Attribution Record ───────────────────────────────────────────────────────


@dataclass
class AttributionRecord:
    """Complete attribution for a single AI output.

    Groups every :class:`SourceCitation` that contributed to one AI output
    (a campaign, creative, chat message, SEO audit, etc.) so the answer can
    be traced back to its sources.

    Attributes:
        output_type: Kind of AI output, e.g. ``"campaign"``, ``"creative"``,
            ``"chat"``, ``"seo_audit"``.
        output_id: Identifier of the AI output (campaign_id, creative_id,
            chat_message_id, ...).
        engine: Which AI engine produced the output, e.g.
            ``"CampaignBrain"``, ``"Creative Studio"``.
        query: The retrieval query that was used to fetch knowledge.
        citations: Ordered list of source citations (most relevant first).
        created_at: UTC timestamp when the record was created.
    """

    output_type: str = ""  # "campaign", "creative", "chat", "seo_audit", etc.
    output_id: str = ""  # ID of the AI output
    engine: str = ""  # Which AI engine produced this (CampaignBrain, Creative Studio, etc.)
    query: str = ""  # The query that was used to retrieve knowledge
    citations: list[SourceCitation] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def format_for_display(self) -> str:
        """Format as a human-readable "Based on:" section.

        Citations are sorted by descending relevance score so the most
        influential sources appear first. Returns::

            Based on:
              - Brand Guidelines v3 (relevance: 92%)
              - Pricing Catalogue 2026 (relevance: 87%)
              - Campaign 'Diwali 2025' (relevance: 75%)

        If there are no citations, returns a graceful fallback noting that
        the output was generated without retrieved knowledge.
        """
        if not self.citations:
            return "Based on: (no specific sources retrieved)"
        ordered = sorted(
            self.citations,
            key=lambda c: c.relevance_score,
            reverse=True,
        )
        lines = ["Based on:"]
        lines.extend(c.format_line() for c in ordered)
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the record to a plain dict.

        The structure mirrors the ``knowledge_attributions`` table columns
        (``source_ids``, ``chunk_ids``, ``relevance_scores``) while also
        embedding the full citations for round-tripping.
        """
        return {
            "output_type": self.output_type,
            "output_id": self.output_id,
            "engine": self.engine,
            "query": self.query,
            "citations": [c.to_dict() for c in self.citations],
            "source_ids": [c.source_id for c in self.citations],
            "relevance_scores": {
                c.source_id: c.relevance_score for c in self.citations
            },
            "created_at": self.created_at.isoformat()
            if self.created_at
            else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AttributionRecord:
        """Reconstruct a record from a plain dict.

        Accepts both the rich ``citations`` list and the flat
        ``source_ids`` / ``relevance_scores`` shape stored in the database.
        Unknown keys are ignored for forward compatibility.
        """
        citations_raw = data.get("citations") or []
        citations: list[SourceCitation] = []
        if citations_raw:
            for item in citations_raw:
                if isinstance(item, SourceCitation):
                    citations.append(item)
                elif isinstance(item, dict):
                    citations.append(SourceCitation.from_dict(item))
        else:
            # Reconstruct minimal citations from the flat DB columns.
            source_ids = data.get("source_ids") or []
            relevance_scores = data.get("relevance_scores") or {}
            if isinstance(relevance_scores, dict):
                for sid in source_ids:
                    citations.append(
                        SourceCitation(
                            source_id=sid,
                            relevance_score=float(
                                relevance_scores.get(sid, 0.0) or 0.0
                            ),
                        )
                    )

        created_raw = data.get("created_at")
        created_at: datetime
        if isinstance(created_raw, datetime):
            created_at = created_raw
        elif isinstance(created_raw, str) and created_raw:
            created_at = datetime.fromisoformat(created_raw)
        else:
            created_at = datetime.now(timezone.utc)

        return cls(
            output_type=data.get("output_type", ""),
            output_id=data.get("output_id", ""),
            engine=data.get("engine", ""),
            query=data.get("query", ""),
            citations=citations,
            created_at=created_at,
        )


# ─── Attribution Tracker ──────────────────────────────────────────────────────


class AttributionTracker:
    """Tracks source attributions for AI outputs.

    When any AI engine (CampaignBrain, Creative Studio, SEO, etc.) uses
    knowledge from the hub, it calls the tracker to record what sources
    were used. This creates an audit trail of why the AI said what it said.

    The tracker is an in-process store keyed by
    ``"{output_type}:{output_id}"``. In production the records should also
    be persisted to the ``knowledge_attributions`` table (see migration
    ``0013_knowledge_hub``); this class provides the domain logic and a
    fast in-memory cache that mirrors the persisted state.

    Thread-safety: the underlying dict operations are atomic for the GIL,
    but if you share a single tracker across threads/async tasks you should
    wrap multi-step read-modify-write sequences in a lock. For typical
    request-scoped or engine-scoped trackers this is not required.
    """

    def __init__(self) -> None:
        self._attributions: dict[str, AttributionRecord] = {}  # output_key -> record

    @staticmethod
    def _key(output_type: str, output_id: str) -> str:
        """Build the internal lookup key for an output."""
        return f"{output_type}:{output_id}"

    def record(
        self,
        output_type: str,
        output_id: str,
        engine: str,
        query: str,
        citations: list[SourceCitation],
    ) -> AttributionRecord:
        """Record (or replace) the attribution for an AI output.

        Args:
            output_type: Kind of AI output (e.g. ``"campaign"``).
            output_id: Identifier of the AI output.
            engine: Which AI engine produced the output.
            query: The retrieval query used to fetch knowledge.
            citations: Source citations backing the output. The list is
                copied so later mutations by the caller don't affect the
                stored record.

        Returns:
            The stored :class:`AttributionRecord`.
        """
        record = AttributionRecord(
            output_type=output_type,
            output_id=output_id,
            engine=engine,
            query=query,
            citations=list(citations),
        )
        self._attributions[self._key(output_type, output_id)] = record
        return record

    def get(self, output_type: str, output_id: str) -> AttributionRecord | None:
        """Return the attribution for an output, or ``None`` if absent."""
        return self._attributions.get(self._key(output_type, output_id))

    def get_by_engine(self, engine: str) -> list[AttributionRecord]:
        """Return all attributions produced by a given engine.

        Results are ordered by creation time, most recent first.
        """
        records = [r for r in self._attributions.values() if r.engine == engine]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records

    def format_attribution(self, output_type: str, output_id: str) -> str:
        """Return the human-readable "Based on:" section for an output.

        If no attribution has been recorded for the output, returns a
        fallback string indicating the output had no tracked sources.
        """
        record = self.get(output_type, output_id)
        if record is None:
            return "Based on: (no attribution recorded for this output)"
        return record.format_for_display()

    def list_recent(self, limit: int = 20) -> list[AttributionRecord]:
        """Return the most recently created attributions.

        Args:
            limit: Maximum number of records to return (default 20).

        Returns:
            Records ordered by creation time, most recent first.
        """
        records = sorted(
            self._attributions.values(),
            key=lambda r: r.created_at,
            reverse=True,
        )
        return records[:limit]

    def __len__(self) -> int:
        """Number of attributions currently tracked."""
        return len(self._attributions)


# ─── Workspace Knowledge Filter ───────────────────────────────────────────────


class WorkspaceKnowledgeFilter:
    """Filters knowledge queries by workspace.

    Ensures that knowledge from one workspace is never accessible from
    another workspace. Works in concert with the vector store: the filter
    dict returned by :meth:`build_filter` is passed to
    ``VectorStore.search(filter=...)`` so that only embeddings belonging to
    the correct workspace (and matching any other criteria) are considered.

    Visibility rules (see :meth:`is_visible`):
    - A source with no ``workspace_id`` is tenant-wide → visible to all.
    - A source with a ``workspace_id`` is only visible within that workspace.
    - ``permissions == "public"`` overrides workspace isolation.
    - ``permissions == "private"`` restricts to the owning workspace only.
    """

    @staticmethod
    def build_filter(
        workspace_id: str | None = None,
        level: str | None = None,
        tags: list[str] | None = None,
        source_type: str | None = None,
    ) -> dict[str, Any]:
        """Build a metadata filter dict for the vector store.

        Returns a dict that can be passed to ``VectorStore.search(filter=...)``.
        Only non-``None`` criteria are included so callers can layer filters
        incrementally.

        Args:
            workspace_id: Restrict to this workspace. ``None`` means
                tenant-wide sources only (sources with no workspace_id),
                which preserves strict isolation — a query without a
                workspace context must never leak workspace-private data.
            level: Knowledge level (one of :data:`KNOWLEDGE_LEVELS`).
            tags: List of tags to match (source must contain *all* tags).
            source_type: Source type (``upload``, ``url``, ``integration``,
                ``generated``, ``manual``).

        Returns:
            A filter dict suitable for the vector store. The
            ``workspace_id`` key is always present: either the explicit
            workspace id, or ``None`` to match tenant-wide sources only.
        """
        flt: dict[str, Any] = {"workspace_id": workspace_id}
        if level is not None:
            flt["level"] = level
        if source_type is not None:
            flt["source_type"] = source_type
        if tags:
            flt["tags"] = {"$all": list(tags)}
        return flt

    @staticmethod
    def is_visible(
        source_workspace_id: str | None,
        query_workspace_id: str | None,
        permissions: str = "shared",
    ) -> bool:
        """Check if a source is visible from a given workspace.

        Rules:
        - If the source has no ``workspace_id``, it is tenant-wide and
          visible to every workspace.
        - If the source has a ``workspace_id``, it is only visible within
          that same workspace (``query_workspace_id`` must match).
        - ``permissions == "public"`` overrides workspace isolation: the
          source is visible to every workspace.
        - ``permissions == "private"`` is the strictest: the source is only
          visible when ``query_workspace_id`` exactly matches
          ``source_workspace_id`` (tenant-wide private sources are not
          visible to any workspace-scoped query).

        Args:
            source_workspace_id: The workspace that owns the source, or
                ``None`` for tenant-wide sources.
            query_workspace_id: The workspace issuing the query, or
                ``None`` for a tenant-wide (admin) context.
            permissions: One of :data:`PERMISSIONS` (default ``"shared"``).

        Returns:
            ``True`` if the source is visible from the querying workspace.
        """
        permissions = (permissions or "shared").lower()

        # Public sources override workspace isolation entirely.
        if permissions == "public":
            return True

        # Tenant-wide sources (no owning workspace) are visible to all,
        # unless they are explicitly private.
        if source_workspace_id is None:
            if permissions == "private":
                # A private tenant-wide source is only visible to a
                # tenant-wide (admin) context.
                return query_workspace_id is None
            return True

        # Source belongs to a specific workspace.
        if permissions == "private":
            # Strict: exact workspace match only.
            return (
                query_workspace_id is not None
                and query_workspace_id == source_workspace_id
            )

        # Default "shared": visible within the owning workspace, or from a
        # tenant-wide (admin) context.
        if query_workspace_id is None:
            return True
        return query_workspace_id == source_workspace_id


__all__ = [
    "KNOWLEDGE_LEVELS",
    "PERMISSIONS",
    "SourceCitation",
    "AttributionRecord",
    "AttributionTracker",
    "WorkspaceKnowledgeFilter",
]
