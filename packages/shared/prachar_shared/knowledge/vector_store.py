"""Vector store and embedding system for the Business Knowledge Hub.

Generates embeddings for text chunks and provides cosine-similarity search.
Works WITHOUT requiring an embedding API — a deterministic hash-based
pseudo-embedding is used as a fallback for development/testing.

Production would back this with pgvector; this module provides an in-memory
implementation that is API-compatible so callers can be swapped later.

Usage::

    from prachar_shared.knowledge.vector_store import KnowledgeSearcher

    searcher = KnowledgeSearcher()
    searcher.index_chunk("chunk-1", "Brand voice: bold and confident", "src-1",
                         {"level": "brand", "workspace_id": "ws-1"})
    results = searcher.search("confident tone", top_k=5)
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import threading
from dataclasses import dataclass, field
from typing import Any

from ..config import get_settings

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────
# OpenAI text-embedding-3-small produces 1536-dimensional vectors.
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_EMBEDDING_DIM = 1536
# The hash-based fallback produces 384-dimensional vectors (compact, fast,
# good enough for dev/testing where semantic quality is not required).
FALLBACK_EMBEDDING_DIM = 384


# ─── Cosine similarity (pure Python, no numpy) ──────────────────────────────

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors.

    Returns a float in ``[-1, 1]``. For search scoring we clamp to ``[0, 1]``
    at the call site because embeddings are unit-normalised and negative
    similarities are not meaningful for ranking knowledge chunks.

    Vectors of differing length are compared over the shared prefix — this
    should not happen in practice (all vectors from one generator share a
    dimension), but we guard against it rather than raising.
    """
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for i in range(n):
        av = a[i]
        bv = b[i]
        dot += av * bv
        norm_a += av * av
        norm_b += bv * bv
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


# ─── Hash-based fallback embedding ──────────────────────────────────────────

def _hash_embedding(text: str, dim: int = FALLBACK_EMBEDDING_DIM) -> list[float]:
    """Deterministic pseudo-embedding from a hash of the text.

    Uses SHA-256 over the UTF-8 bytes of the text, then expands the digest
    into ``dim`` floats in ``[-1, 1]`` and normalises to unit length.

    Properties:
    - Deterministic: the same text always yields the same vector.
    - Different texts produce different vectors (SHA-256 collisions are
      infeasible; even single-character changes alter the entire digest).
    - Unit-normalised so cosine similarity is well-defined.

    This is NOT semantically meaningful — it only lets the vector store and
    search machinery work end-to-end without an embedding API. Real semantic
    search requires the OpenAI path (or another embedding model).
    """
    if not text:
        # Zero vector for empty input; normalising would divide by zero so we
        # return a tiny uniform vector instead.
        return [0.0] * dim

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    # Expand the 32-byte digest into `dim` bytes by repeatedly hashing with
    # a counter salt. This gives us enough entropy for any dimension.
    bytes_needed = dim
    salt = 0
    buf = bytearray()
    while len(buf) < bytes_needed:
        buf.extend(hashlib.sha256(digest + salt.to_bytes(4, "big")).digest())
        salt += 1

    vec = [(b - 128) / 128.0 for b in buf[:dim]]  # each in [-1, 1]

    # Normalise to unit length.
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        # Extremely unlikely, but guard anyway.
        vec = [1.0 / math.sqrt(dim)] * dim
    else:
        vec = [v / norm for v in vec]
    return vec


# ─── Embedding generator ────────────────────────────────────────────────────

class EmbeddingGenerator:
    """Generates embeddings for text, with caching and an API-free fallback.

    Primary path: OpenAI ``text-embedding-3-small`` (1536 dims) when
    ``OPENAI_API_KEY`` is set.
    Fallback path: deterministic hash-based pseudo-embedding (384 dims) for
    development and testing.

    Embeddings are cached in-process keyed by text so repeated indexing of
    the same chunk (e.g. across re-index runs) does not call the API twice.
    """

    def __init__(
        self,
        *,
        model: str = OPENAI_EMBEDDING_MODEL,
        force_fallback: bool = False,
        cache_size: int | None = None,
    ) -> None:
        self.model = model
        self._force_fallback = force_fallback
        self._cache: dict[str, list[float]] = {}
        self._cache_size = cache_size
        self._lock = threading.Lock()

    # ── Mode selection ──────────────────────────────────────────────────
    def _use_openai(self) -> bool:
        if self._force_fallback:
            return False
        s = get_settings()
        return bool(s.openai_api_key.strip())

    @property
    def dimension(self) -> int:
        """Dimensionality of vectors produced by this generator."""
        return OPENAI_EMBEDDING_DIM if self._use_openai() else FALLBACK_EMBEDDING_DIM

    @property
    def provider(self) -> str:
        return "openai" if self._use_openai() else "hash-fallback"

    # ── Cache ───────────────────────────────────────────────────────────
    def _cache_get(self, text: str) -> list[float] | None:
        with self._lock:
            return self._cache.get(text)

    def _cache_put(self, text: str, vec: list[float]) -> None:
        with self._lock:
            if self._cache_size is not None and len(self._cache) >= self._cache_size:
                # Simple eviction: drop an arbitrary entry. LRU would be nicer
                # but the cache is small and this is dev-grade machinery.
                self._cache.pop(next(iter(self._cache)))
            self._cache[text] = vec

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    # ── Public API ──────────────────────────────────────────────────────
    def generate(self, text: str) -> list[float]:
        """Generate an embedding for a single text."""
        cached = self._cache_get(text)
        if cached is not None:
            return cached
        if self._use_openai():
            vec = self._openai_embed([text])[0]
        else:
            vec = _hash_embedding(text, FALLBACK_EMBEDDING_DIM)
        self._cache_put(text, vec)
        return vec

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        OpenAI supports native batching (one API call for many inputs). The
        fallback path simply hashes each text independently. Results are
        cached per-text.
        """
        if not texts:
            return []
        results: list[list[float] | None] = [None] * len(texts)
        missing: list[int] = []
        missing_texts: list[str] = []
        for i, t in enumerate(texts):
            cached = self._cache_get(t)
            if cached is not None:
                results[i] = cached
            else:
                missing.append(i)
                missing_texts.append(t)

        if missing_texts:
            if self._use_openai():
                vecs = self._openai_embed(missing_texts)
            else:
                vecs = [_hash_embedding(t, FALLBACK_EMBEDDING_DIM) for t in missing_texts]
            for idx, vec in zip(missing, vecs):
                results[idx] = vec
                self._cache_put(texts[idx], vec)

        # All slots are filled by this point.
        return [r for r in results if r is not None]

    # ── OpenAI call ─────────────────────────────────────────────────────
    def _openai_embed(self, texts: list[str]) -> list[list[float]]:
        """Call the OpenAI embeddings API for a batch of texts."""
        import openai as openai_lib

        s = get_settings()
        client = openai_lib.OpenAI(
            api_key=s.openai_api_key,
            timeout=60.0,
        )
        try:
            resp = client.embeddings.create(model=self.model, input=texts)
        except Exception:
            logger.warning(
                "OpenAI embeddings call failed; falling back to hash embedding",
                exc_info=True,
            )
            return [_hash_embedding(t, FALLBACK_EMBEDDING_DIM) for t in texts]

        # OpenAI returns embeddings in input order.
        out: list[list[float]] = []
        for item in resp.data:
            out.append(list(item.embedding))
        return out


# ─── Search result ──────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    """A single similarity-search hit."""

    chunk_id: str
    score: float  # cosine similarity, clamped to [0, 1]
    content: str = ""
    source_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ─── Vector store (in-memory) ───────────────────────────────────────────────

@dataclass
class _StoredVector:
    chunk_id: str
    embedding: list[float]
    content: str
    source_id: str
    metadata: dict[str, Any]


class VectorStore:
    """In-memory vector store with cosine-similarity search.

    Production would use pgvector; this implementation keeps everything in
    memory and is suitable for development, testing, and small workspaces.
    All public methods are thread-safe.
    """

    def __init__(self) -> None:
        self._vectors: dict[str, _StoredVector] = {}
        self._lock = threading.RLock()

    # ── Mutation ────────────────────────────────────────────────────────
    def add(
        self,
        chunk_id: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
        *,
        content: str = "",
        source_id: str = "",
    ) -> None:
        """Add or replace a vector keyed by ``chunk_id``."""
        meta = dict(metadata) if metadata else {}
        vec = _StoredVector(
            chunk_id=chunk_id,
            embedding=list(embedding),
            content=content,
            source_id=source_id,
            metadata=meta,
        )
        with self._lock:
            self._vectors[chunk_id] = vec

    def delete(self, chunk_id: str) -> bool:
        """Remove a vector. Returns True if it existed."""
        with self._lock:
            return self._vectors.pop(chunk_id, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._vectors.clear()

    def count(self) -> int:
        with self._lock:
            return len(self._vectors)

    # ── Search ──────────────────────────────────────────────────────────
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Cosine-similarity search.

        Args:
            query_embedding: The query vector.
            top_k: Maximum number of results to return.
            filter: Optional metadata filter. A stored vector matches the
                filter when, for every key in ``filter``, the stored
                metadata either has an equal value or — if the stored value
                is a list — contains the filter value. This supports the
                ``tags`` field (list membership) and scalar fields like
                ``workspace_id`` / ``level`` / ``source_id``.
        """
        with self._lock:
            candidates = list(self._vectors.values())

        scored: list[tuple[float, _StoredVector]] = []
        for v in candidates:
            if filter and not _matches_filter(v.metadata, filter):
                continue
            score = cosine_similarity(query_embedding, v.embedding)
            # Clamp to [0, 1] for ranking/scoring consistency.
            if score < 0.0:
                score = 0.0
            elif score > 1.0:
                score = 1.0
            scored.append((score, v))

        # Sort by score descending; break ties by chunk_id for determinism.
        scored.sort(key=lambda item: (-item[0], item[1].chunk_id))

        results: list[SearchResult] = []
        for score, v in scored[:top_k]:
            results.append(
                SearchResult(
                    chunk_id=v.chunk_id,
                    score=score,
                    content=v.content,
                    source_id=v.source_id,
                    metadata=dict(v.metadata),
                )
            )
        return results


def _matches_filter(metadata: dict[str, Any], filter: dict[str, Any]) -> bool:
    """Check whether ``metadata`` satisfies ``filter``.

    For each key/value in ``filter``:
    - If the stored metadata value is a list, the filter value must be a
      member of that list (supports ``tags``).
    - Otherwise the stored value must equal the filter value.
    - If the key is absent from metadata, the filter does not match.
    """
    for key, want in filter.items():
        have = metadata.get(key)
        if have is None:
            return False
        if isinstance(have, list):
            if want not in have:
                return False
        elif have != want:
            return False
    return True


# ─── Knowledge searcher (embedding + vector store combined) ────────────────

class KnowledgeSearcher:
    """Combines embedding generation and vector search for the Knowledge Hub.

    This is the high-level facade used by the Business Knowledge Hub: index
    chunks as they are extracted from sources, then run semantic searches
    scoped by knowledge level or workspace.
    """

    def __init__(
        self,
        *,
        embedder: EmbeddingGenerator | None = None,
        store: VectorStore | None = None,
    ) -> None:
        self.embedder = embedder if embedder is not None else EmbeddingGenerator()
        self.store = store if store is not None else VectorStore()

    # ── Indexing ────────────────────────────────────────────────────────
    def index_chunk(
        self,
        chunk_id: str,
        content: str,
        source_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> list[float]:
        """Generate an embedding for ``content`` and add it to the store.

        Returns the generated embedding (useful for callers that also
        persist it to the database).
        """
        embedding = self.embedder.generate(content)
        meta = dict(metadata) if metadata else {}
        # Ensure source_id is mirrored into metadata for filtering convenience.
        meta.setdefault("source_id", source_id)
        self.store.add(
            chunk_id=chunk_id,
            embedding=embedding,
            metadata=meta,
            content=content,
            source_id=source_id,
        )
        return embedding

    def index_chunks(
        self,
        chunks: list[dict[str, Any]],
    ) -> list[list[float]]:
        """Batch-index many chunks.

        Each chunk dict should contain ``chunk_id`` and ``content`` and may
        include ``source_id`` and ``metadata``. Uses batched embedding
        generation to minimise API calls.
        """
        if not chunks:
            return []
        texts = [c.get("content", "") for c in chunks]
        embeddings = self.embedder.generate_batch(texts)
        for c, emb in zip(chunks, embeddings):
            cid = c["chunk_id"]
            content = c.get("content", "")
            source_id = c.get("source_id", "")
            meta = dict(c.get("metadata") or {})
            meta.setdefault("source_id", source_id)
            self.store.add(
                chunk_id=cid,
                embedding=emb,
                metadata=meta,
                content=content,
                source_id=source_id,
            )
        return embeddings

    def remove_chunk(self, chunk_id: str) -> bool:
        """Remove a chunk from the index. Returns True if it existed."""
        return self.store.delete(chunk_id)

    def count(self) -> int:
        return self.store.count()

    # ── Search ──────────────────────────────────────────────────────────
    def search(
        self,
        query: str,
        top_k: int = 5,
        level: str | None = None,
        workspace_id: str | None = None,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Semantic search over indexed chunks.

        Args:
            query: Free-text query.
            top_k: Maximum results.
            level: Optional knowledge level filter (brand, business,
                marketing, live).
            workspace_id: Optional workspace isolation filter.
            filter: Additional raw metadata filters merged with the above.
        """
        query_embedding = self.embedder.generate(query)
        combined_filter: dict[str, Any] = dict(filter) if filter else {}
        if level is not None:
            combined_filter["level"] = level
        if workspace_id is not None:
            combined_filter["workspace_id"] = workspace_id
        return self.store.search(
            query_embedding,
            top_k=top_k,
            filter=combined_filter or None,
        )

    def search_by_level(
        self,
        query: str,
        level: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Search restricted to a single knowledge level."""
        return self.search(query, top_k=top_k, level=level)

    def search_by_workspace(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 5,
        level: str | None = None,
    ) -> list[SearchResult]:
        """Search restricted to a single workspace (with optional level)."""
        return self.search(
            query,
            top_k=top_k,
            workspace_id=workspace_id,
            level=level,
        )

    def search_by_source(
        self,
        query: str,
        source_id: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Search restricted to chunks from a single source document."""
        return self.search(query, top_k=top_k, filter={"source_id": source_id})

    def search_by_tags(
        self,
        query: str,
        tags: list[str],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Search restricted to chunks tagged with ALL of ``tags``.

        Uses the list-membership semantics of the metadata filter: a chunk
        matches when its ``tags`` list contains every requested tag.
        """
        filter = {"tags": t for t in tags}
        return self.search(query, top_k=top_k, filter=filter)


__all__ = [
    "OPENAI_EMBEDDING_MODEL",
    "OPENAI_EMBEDDING_DIM",
    "FALLBACK_EMBEDDING_DIM",
    "cosine_similarity",
    "EmbeddingGenerator",
    "SearchResult",
    "VectorStore",
    "KnowledgeSearcher",
]
