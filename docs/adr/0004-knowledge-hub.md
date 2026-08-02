# ADR-0004: Knowledge Hub (RAG)

**Status:** Accepted
**Date:** 2026-08-02

## Context

The Orb needs to answer questions about the user's business using their uploaded documents (brand guidelines, product info, past campaigns). A RAG (Retrieval-Augmented Generation) system is needed to store, chunk, embed, and retrieve this knowledge.

## Decision

The Knowledge Hub consists of:

1. **KnowledgeSourceRecord** — represents an uploaded document/URL/text
2. **KnowledgeChunkRecord** — a chunk of a source (with token count, page number, section)
3. **KnowledgeEmbeddingRecord** — vector embedding of a chunk
4. **KnowledgeAttributionRecord** — tracks which chunks were used in which responses

Pipeline:
- Upload → detect file type → store → chunk → embed → mark ready
- Query → embed question → similarity search → return top-k chunks with scores

The Knowledge Hub is accessed by:
- `KnowledgeContextProvider` (always-on) — feeds relevant chunks to the Orb
- `knowledge.search` tool — explicit search by the Orb
- `/knowledge/*` REST API — frontend upload/list/delete/stats

## Consequences

- The Orb can cite specific documents when answering
- Attribution tracking shows which sources were used
- Chunking strategy affects retrieval quality (tunable, not architectural)
- Embedding model is swappable (abstraction, not frozen)

## Frozen

The Knowledge Hub architecture is frozen. New memory/knowledge features must extend this system, not create a parallel one. Business Memory (learnings, best practices) is a separate store but follows the same pattern.
