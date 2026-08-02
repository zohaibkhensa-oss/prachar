"""Business Knowledge Hub — document processing, embeddings, governance, and
source attribution.

Exports:
- :class:`DocumentProcessor` — ingest uploaded documents into searchable chunks.
- :class:`EmbeddingGenerator` / :class:`VectorStore` / :class:`KnowledgeSearcher`
  — embedding generation and similarity search.
- :class:`KnowledgeLevelClassifier` / :class:`GovernanceChecker` / :class:`GovernanceMetadata`
  — 4-level classification and knowledge governance.
- :class:`SourceCitation` / :class:`AttributionRecord` / :class:`AttributionTracker`
  — trace AI answers back to the source documents that informed them.
- :class:`WorkspaceKnowledgeFilter` — workspace-isolated knowledge filters.

Example
-------
>>> from prachar_shared.knowledge import DocumentProcessor
>>> processor = DocumentProcessor()
>>> result = processor.process(file_path="report.pdf")
>>> [c.content[:80] for c in result.chunks][:2]
"""

from __future__ import annotations

from .attribution import (
    KNOWLEDGE_LEVELS,
    PERMISSIONS,
    AttributionRecord,
    AttributionTracker,
    SourceCitation,
    WorkspaceKnowledgeFilter,
)
from .document_processor import (
    DocumentProcessor,
    ParsedPage,
    ProcessingResult,
    TextChunk,
)
from .governance import (
    DEFAULT_EXPIRY_DAYS,
    MIN_USABLE_CONFIDENCE,
    GovernanceChecker,
    GovernanceMetadata,
    KnowledgeLevel,
    KnowledgeLevelClassifier,
)
from .vector_store import (
    EmbeddingGenerator,
    KnowledgeSearcher,
    SearchResult,
    VectorStore,
    cosine_similarity,
)

__all__ = [
    # Document processing
    "DocumentProcessor",
    "ParsedPage",
    "ProcessingResult",
    "TextChunk",
    # Vector store + embeddings
    "EmbeddingGenerator",
    "KnowledgeSearcher",
    "SearchResult",
    "VectorStore",
    "cosine_similarity",
    # Governance
    "DEFAULT_EXPIRY_DAYS",
    "MIN_USABLE_CONFIDENCE",
    "GovernanceChecker",
    "GovernanceMetadata",
    "KnowledgeLevel",
    "KnowledgeLevelClassifier",
    # Attribution
    "KNOWLEDGE_LEVELS",
    "PERMISSIONS",
    "SourceCitation",
    "AttributionRecord",
    "AttributionTracker",
    "WorkspaceKnowledgeFilter",
]
