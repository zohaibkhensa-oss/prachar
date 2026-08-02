"""Business Knowledge Hub — API endpoints.

First-class knowledge management:
- Upload documents (PDF, Word, Excel, CSV, images, URLs)
- Process and chunk documents
- Generate embeddings and index for search
- Semantic search across all knowledge
- Source attribution for AI outputs
- Knowledge governance (expiry, permissions, confidence)
- Workspace isolation

Endpoints:
- POST /knowledge/upload — upload a document
- POST /knowledge/url — add a URL as a knowledge source
- POST /knowledge/text — add text directly
- GET /knowledge/sources — list all knowledge sources
- GET /knowledge/sources/{id} — get a single source with chunks
- DELETE /knowledge/sources/{id} — delete a source
- POST /knowledge/search — semantic search across knowledge
- GET /knowledge/levels — get knowledge organized by level
- POST /knowledge/attribute — record source attribution for an AI output
- GET /knowledge/attributions/{output_type}/{output_id} — get attribution
- GET /knowledge/stats — knowledge hub statistics
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel, Field
from sqlalchemy import select, delete, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import CurrentUser, SessionDep
from ..models import (
    KnowledgeSourceRecord,
    KnowledgeChunkRecord,
    KnowledgeEmbeddingRecord,
    KnowledgeAttributionRecord,
)
from ..models.enums import (
    KnowledgeLevel,
    KnowledgeSourceStatus,
    KnowledgeSourceType,
    KnowledgeFileType,
)
from ..audit import log_audit

log = logging.getLogger("prachar.api.knowledge")
router = APIRouter(prefix="/knowledge", tags=["knowledge"])


# ─── Schemas ────────────────────────────────────────────────────────────────


class KnowledgeSourceOut(BaseModel):
    id: str
    workspace_id: str | None = None
    brand_id: str | None = None
    level: str
    source_type: str
    file_type: str | None = None
    title: str
    description: str | None = None
    status: str
    processing_error: str | None = None
    chunk_count: int = 0
    total_tokens: int | None = None
    # Governance
    version: int = 1
    owner_name: str | None = None
    confidence: float = 0.8
    permissions: str = "shared"
    expires_at: str | None = None
    tags: list[str] = Field(default_factory=list)
    integration_name: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_record(cls, r: KnowledgeSourceRecord) -> "KnowledgeSourceOut":
        return cls(
            id=str(r.id),
            workspace_id=str(r.workspace_id) if r.workspace_id else None,
            brand_id=str(r.brand_id) if r.brand_id else None,
            level=r.level,
            source_type=r.source_type,
            file_type=r.file_type,
            title=r.title,
            description=r.description,
            status=r.status,
            processing_error=r.processing_error,
            chunk_count=r.chunk_count,
            total_tokens=r.total_tokens,
            version=r.version,
            owner_name=r.owner_name,
            confidence=r.confidence,
            permissions=r.permissions,
            expires_at=r.expires_at.isoformat() if r.expires_at else None,
            tags=r.tags or [],
            integration_name=r.integration_name,
            created_at=r.created_at.isoformat() if r.created_at else "",
            updated_at=r.updated_at.isoformat() if r.updated_at else "",
        )


class KnowledgeChunkOut(BaseModel):
    id: str
    source_id: str
    chunk_index: int
    content: str
    page_number: int | None = None
    section: str | None = None
    token_count: int | None = None
    embedded: bool = False


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    level: str | None = None       # Filter by knowledge level
    workspace_id: str | None = None
    brand_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class SearchResultOut(BaseModel):
    chunk_id: str
    source_id: str
    title: str
    level: str
    score: float
    content: str
    section: str | None = None
    page_number: int | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultOut] = Field(default_factory=list)
    total: int = 0


class UrlSourceRequest(BaseModel):
    url: str = Field(min_length=1)
    title: str = ""
    level: str = KnowledgeLevel.business
    workspace_id: str | None = None
    brand_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class TextSourceRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1)
    level: str = KnowledgeLevel.business
    description: str = ""
    workspace_id: str | None = None
    brand_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0, le=1)


class AttributionRequest(BaseModel):
    output_type: str = Field(min_length=1)
    output_id: str = Field(min_length=1)
    engine: str = Field(min_length=1)
    query: str = ""
    source_ids: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    relevance_scores: dict[str, float] = Field(default_factory=dict)


class AttributionOut(BaseModel):
    id: str
    output_type: str
    output_id: str
    engine: str
    query: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    relevance_scores: dict[str, Any] | None = None
    created_at: str = ""


class KnowledgeStats(BaseModel):
    total_sources: int = 0
    total_chunks: int = 0
    total_embeddings: int = 0
    by_level: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_source_type: dict[str, int] = Field(default_factory=dict)


# ─── Helper: detect file type ───────────────────────────────────────────────


def _detect_file_type(filename: str, mime_type: str = "") -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mapping = {
        "pdf": KnowledgeFileType.pdf,
        "doc": KnowledgeFileType.word, "docx": KnowledgeFileType.word,
        "xls": KnowledgeFileType.excel, "xlsx": KnowledgeFileType.excel,
        "ppt": KnowledgeFileType.powerpoint, "pptx": KnowledgeFileType.powerpoint,
        "csv": KnowledgeFileType.csv,
        "txt": KnowledgeFileType.text, "md": KnowledgeFileType.text,
        "html": KnowledgeFileType.html, "htm": KnowledgeFileType.html,
        "json": KnowledgeFileType.json,
        "png": KnowledgeFileType.image, "jpg": KnowledgeFileType.image,
        "jpeg": KnowledgeFileType.image, "gif": KnowledgeFileType.image, "webp": KnowledgeFileType.image,
    }
    return mapping.get(ext, KnowledgeFileType.text).value


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/stats", response_model=KnowledgeStats)
async def knowledge_stats(user: CurrentUser, session: SessionDep) -> KnowledgeStats:
    """Get knowledge hub statistics."""
    # Total sources
    res = await session.execute(
        select(func.count()).select_from(KnowledgeSourceRecord)
        .where(KnowledgeSourceRecord.tenant_id == user.tenant_id)
    )
    total_sources = res.scalar() or 0

    # Total chunks
    res = await session.execute(
        select(func.count()).select_from(KnowledgeChunkRecord)
        .where(KnowledgeChunkRecord.tenant_id == user.tenant_id)
    )
    total_chunks = res.scalar() or 0

    # Total embeddings
    res = await session.execute(
        select(func.count()).select_from(KnowledgeEmbeddingRecord)
        .where(KnowledgeEmbeddingRecord.tenant_id == user.tenant_id)
    )
    total_embeddings = res.scalar() or 0

    # By level
    res = await session.execute(
        select(KnowledgeSourceRecord.level, func.count())
        .where(KnowledgeSourceRecord.tenant_id == user.tenant_id)
        .group_by(KnowledgeSourceRecord.level)
    )
    by_level = {row[0]: row[1] for row in res.all()}

    # By status
    res = await session.execute(
        select(KnowledgeSourceRecord.status, func.count())
        .where(KnowledgeSourceRecord.tenant_id == user.tenant_id)
        .group_by(KnowledgeSourceRecord.status)
    )
    by_status = {row[0]: row[1] for row in res.all()}

    # By source type
    res = await session.execute(
        select(KnowledgeSourceRecord.source_type, func.count())
        .where(KnowledgeSourceRecord.tenant_id == user.tenant_id)
        .group_by(KnowledgeSourceRecord.source_type)
    )
    by_source_type = {row[0]: row[1] for row in res.all()}

    return KnowledgeStats(
        total_sources=total_sources,
        total_chunks=total_chunks,
        total_embeddings=total_embeddings,
        by_level=by_level,
        by_status=by_status,
        by_source_type=by_source_type,
    )


@router.get("/sources", response_model=list[KnowledgeSourceOut])
async def list_sources(
    user: CurrentUser,
    session: SessionDep,
    level: str | None = None,
    workspace_id: str | None = None,
    brand_id: str | None = None,
    limit: int = 100,
) -> list[KnowledgeSourceOut]:
    """List all knowledge sources with optional filters."""
    query = select(KnowledgeSourceRecord).where(
        KnowledgeSourceRecord.tenant_id == user.tenant_id
    )
    if level:
        query = query.where(KnowledgeSourceRecord.level == level)
    if workspace_id:
        query = query.where(KnowledgeSourceRecord.workspace_id == uuid.UUID(workspace_id))
    if brand_id:
        query = query.where(KnowledgeSourceRecord.brand_id == uuid.UUID(brand_id))
    query = query.order_by(KnowledgeSourceRecord.created_at.desc()).limit(limit)

    res = await session.execute(query)
    return [KnowledgeSourceOut.from_record(r) for r in res.scalars().all()]


@router.get("/sources/{source_id}", response_model=dict)
async def get_source(
    source_id: str,
    user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Get a single knowledge source with its chunks."""
    res = await session.execute(
        select(KnowledgeSourceRecord).where(
            KnowledgeSourceRecord.id == uuid.UUID(source_id),
            KnowledgeSourceRecord.tenant_id == user.tenant_id,
        )
    )
    source = res.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")

    # Get chunks
    res = await session.execute(
        select(KnowledgeChunkRecord).where(
            KnowledgeChunkRecord.source_id == source.id,
        ).order_by(KnowledgeChunkRecord.chunk_index)
    )
    chunks = res.scalars().all()

    return {
        "source": KnowledgeSourceOut.from_record(source).model_dump(),
        "chunks": [
            KnowledgeChunkOut(
                id=str(c.id), source_id=str(c.source_id),
                chunk_index=c.chunk_index, content=c.content[:500] + "..." if len(c.content) > 500 else c.content,
                page_number=c.page_number, section=c.section,
                token_count=c.token_count, embedded=c.embedded,
            ).model_dump()
            for c in chunks
        ],
    }


@router.delete("/sources/{source_id}", response_model=dict)
async def delete_source(
    source_id: str,
    user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Delete a knowledge source and all its chunks and embeddings."""
    res = await session.execute(
        select(KnowledgeSourceRecord).where(
            KnowledgeSourceRecord.id == uuid.UUID(source_id),
            KnowledgeSourceRecord.tenant_id == user.tenant_id,
        )
    )
    source = res.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")

    title = source.title
    # Chunks and embeddings cascade-delete via FK
    await session.delete(source)
    await session.commit()

    await log_audit(
        session, tenant_id=user.tenant_id, actor=str(user.id),
        action="knowledge.source_deleted",
        entity_type="knowledge_source", entity_id=source_id,
        payload={"title": title},
    )
    await session.commit()

    return {"status": "deleted", "source_id": source_id}


@router.post("/upload", response_model=KnowledgeSourceOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    user: CurrentUser,
    session: SessionDep,
    file: UploadFile = File(...),
    title: str = Form(""),
    level: str = Form(KnowledgeLevel.business),
    description: str = Form(""),
    workspace_id: str = Form(""),
    brand_id: str = Form(""),
    tags: str = Form(""),  # comma-separated
) -> KnowledgeSourceOut:
    """Upload a document to the knowledge hub.

    Supported file types: PDF, Word, Excel, PowerPoint, CSV, images, text, HTML, JSON.
    The document is processed, chunked, and indexed for semantic search.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required")

    file_type = _detect_file_type(file.filename, file.content_type or "")
    file_bytes = await file.read()
    file_size = len(file_bytes)

    # Content hash for deduplication
    content_hash = hashlib.sha256(file_bytes).hexdigest()

    # Check for duplicate
    existing = await session.execute(
        select(KnowledgeSourceRecord).where(
            KnowledgeSourceRecord.tenant_id == user.tenant_id,
            KnowledgeSourceRecord.content_hash == content_hash,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This document has already been uploaded")

    # Create source record
    ws_id = uuid.UUID(workspace_id) if workspace_id else None
    br_id = uuid.UUID(brand_id) if brand_id else None
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    source = KnowledgeSourceRecord(
        tenant_id=user.tenant_id,
        workspace_id=ws_id,
        brand_id=br_id,
        level=level,
        source_type=KnowledgeSourceType.upload,
        file_type=file_type,
        title=title or file.filename,
        description=description,
        file_name=file.filename,
        file_size=file_size,
        mime_type=file.content_type,
        status=KnowledgeSourceStatus.processing,
        owner_id=user.id,
        owner_name=getattr(user, "name", str(user.id)),
        tags=tag_list,
        content_hash=content_hash,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)

    # Process the document (inline for now; in production this would be a Celery task)
    try:
        from prachar_shared.knowledge.document_processor import DocumentProcessor
        from prachar_shared.knowledge.governance import KnowledgeLevelClassifier

        processor = DocumentProcessor()
        result = processor.process(file_bytes=file_bytes, file_type=file_type)

        if not result.success:
            source.status = KnowledgeSourceStatus.failed
            source.processing_error = result.error
            await session.commit()
            return KnowledgeSourceOut.from_record(source)

        # Auto-classify level if not explicitly set or if it's "business" (default)
        if level == KnowledgeLevel.business and result.chunks:
            classifier = KnowledgeLevelClassifier()
            auto_level = classifier.classify(
                title=source.title,
                content=result.chunks[0].content if result.chunks else "",
            )
            source.level = auto_level

        # Store chunks
        total_tokens = 0
        for chunk in result.chunks:
            chunk_record = KnowledgeChunkRecord(
                tenant_id=user.tenant_id,
                source_id=source.id,
                workspace_id=ws_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                token_count=chunk.token_count,
                page_number=chunk.page_number,
                section=chunk.section,
                chunk_metadata=chunk.metadata,
            )
            session.add(chunk_record)
            total_tokens += chunk.token_count

        source.status = KnowledgeSourceStatus.ready
        source.chunk_count = len(result.chunks)
        source.total_tokens = total_tokens
        source.processed_at = datetime.now(timezone.utc)
        await session.commit()

        # Generate embeddings (best effort — don't fail if embedding fails)
        try:
            from prachar_shared.knowledge.vector_store import KnowledgeSearcher

            searcher = KnowledgeSearcher()
            # Get the chunks we just saved
            res = await session.execute(
                select(KnowledgeChunkRecord).where(
                    KnowledgeChunkRecord.source_id == source.id
                ).order_by(KnowledgeChunkRecord.chunk_index)
            )
            for chunk_record in res.scalars().all():
                embedding = searcher.embedding_generator.generate(chunk_record.content)
                emb_record = KnowledgeEmbeddingRecord(
                    tenant_id=user.tenant_id,
                    chunk_id=chunk_record.id,
                    source_id=source.id,
                    workspace_id=ws_id,
                    embedding=embedding,
                    embedding_dim=len(embedding),
                    embedding_model=searcher.embedding_generator.model,
                )
                session.add(emb_record)
                chunk_record.embedded = True
                chunk_record.embedding_model = searcher.embedding_generator.model

            await session.commit()
        except Exception as e:
            log.warning("Embedding generation failed for source %s: %s", source.id, e)

        await log_audit(
            session, tenant_id=user.tenant_id, actor=str(user.id),
            action="knowledge.source_uploaded",
            entity_type="knowledge_source", entity_id=str(source.id),
            payload={"title": source.title, "file_type": file_type, "chunks": source.chunk_count},
        )
        await session.commit()

    except Exception as e:
        log.error("Document processing failed: %s", e, exc_info=True)
        source.status = KnowledgeSourceStatus.failed
        source.processing_error = str(e)
        await session.commit()

    await session.refresh(source)
    return KnowledgeSourceOut.from_record(source)


@router.post("/url", response_model=KnowledgeSourceOut, status_code=status.HTTP_201_CREATED)
async def add_url_source(
    body: UrlSourceRequest,
    user: CurrentUser,
    session: SessionDep,
) -> KnowledgeSourceOut:
    """Add a URL as a knowledge source. The page content is fetched and processed."""
    source = KnowledgeSourceRecord(
        tenant_id=user.tenant_id,
        workspace_id=uuid.UUID(body.workspace_id) if body.workspace_id else None,
        brand_id=uuid.UUID(body.brand_id) if body.brand_id else None,
        level=body.level,
        source_type=KnowledgeSourceType.url,
        file_type=KnowledgeFileType.url,
        title=body.title or body.url,
        status=KnowledgeSourceStatus.processing,
        owner_id=user.id,
        owner_name=getattr(user, "name", str(user.id)),
        tags=body.tags,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)

    try:
        from prachar_shared.knowledge.document_processor import DocumentProcessor

        processor = DocumentProcessor()
        result = processor.process(url=body.url, file_type=KnowledgeFileType.url)

        if not result.success:
            source.status = KnowledgeSourceStatus.failed
            source.processing_error = result.error
            await session.commit()
            return KnowledgeSourceOut.from_record(source)

        total_tokens = 0
        for chunk in result.chunks:
            chunk_record = KnowledgeChunkRecord(
                tenant_id=user.tenant_id,
                source_id=source.id,
                workspace_id=source.workspace_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                token_count=chunk.token_count,
                section=chunk.section,
                chunk_metadata=chunk.metadata,
            )
            session.add(chunk_record)
            total_tokens += chunk.token_count

        source.status = KnowledgeSourceStatus.ready
        source.chunk_count = len(result.chunks)
        source.total_tokens = total_tokens
        source.processed_at = datetime.now(timezone.utc)
        await session.commit()

    except Exception as e:
        log.error("URL processing failed: %s", e, exc_info=True)
        source.status = KnowledgeSourceStatus.failed
        source.processing_error = str(e)
        await session.commit()

    await session.refresh(source)
    return KnowledgeSourceOut.from_record(source)


@router.post("/text", response_model=KnowledgeSourceOut, status_code=status.HTTP_201_CREATED)
async def add_text_source(
    body: TextSourceRequest,
    user: CurrentUser,
    session: SessionDep,
) -> KnowledgeSourceOut:
    """Add text directly as a knowledge source."""
    content_hash = hashlib.sha256(body.content.encode()).hexdigest()

    # Check for duplicate
    existing = await session.execute(
        select(KnowledgeSourceRecord).where(
            KnowledgeSourceRecord.tenant_id == user.tenant_id,
            KnowledgeSourceRecord.content_hash == content_hash,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This content has already been added")

    source = KnowledgeSourceRecord(
        tenant_id=user.tenant_id,
        workspace_id=uuid.UUID(body.workspace_id) if body.workspace_id else None,
        brand_id=uuid.UUID(body.brand_id) if body.brand_id else None,
        level=body.level,
        source_type=KnowledgeSourceType.manual,
        file_type=KnowledgeFileType.text,
        title=body.title,
        description=body.description,
        status=KnowledgeSourceStatus.processing,
        owner_id=user.id,
        owner_name=getattr(user, "name", str(user.id)),
        confidence=body.confidence,
        tags=body.tags,
        content_hash=content_hash,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)

    try:
        from prachar_shared.knowledge.document_processor import DocumentProcessor

        processor = DocumentProcessor()
        result = processor.process(file_bytes=body.content.encode(), file_type=KnowledgeFileType.text)

        if not result.success:
            source.status = KnowledgeSourceStatus.failed
            source.processing_error = result.error
            await session.commit()
            return KnowledgeSourceOut.from_record(source)

        total_tokens = 0
        for chunk in result.chunks:
            chunk_record = KnowledgeChunkRecord(
                tenant_id=user.tenant_id,
                source_id=source.id,
                workspace_id=source.workspace_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                token_count=chunk.token_count,
                chunk_metadata=chunk.metadata,
            )
            session.add(chunk_record)
            total_tokens += chunk.token_count

        source.status = KnowledgeSourceStatus.ready
        source.chunk_count = len(result.chunks)
        source.total_tokens = total_tokens
        source.processed_at = datetime.now(timezone.utc)
        await session.commit()

        # Generate embeddings
        try:
            from prachar_shared.knowledge.vector_store import KnowledgeSearcher

            searcher = KnowledgeSearcher()
            res = await session.execute(
                select(KnowledgeChunkRecord).where(
                    KnowledgeChunkRecord.source_id == source.id
                ).order_by(KnowledgeChunkRecord.chunk_index)
            )
            for chunk_record in res.scalars().all():
                embedding = searcher.embedding_generator.generate(chunk_record.content)
                emb_record = KnowledgeEmbeddingRecord(
                    tenant_id=user.tenant_id,
                    chunk_id=chunk_record.id,
                    source_id=source.id,
                    workspace_id=source.workspace_id,
                    embedding=embedding,
                    embedding_dim=len(embedding),
                    embedding_model=searcher.embedding_generator.model,
                )
                session.add(emb_record)
                chunk_record.embedded = True
                chunk_record.embedding_model = searcher.embedding_generator.model

            await session.commit()
        except Exception as e:
            log.warning("Embedding generation failed: %s", e)

        await log_audit(
            session, tenant_id=user.tenant_id, actor=str(user.id),
            action="knowledge.source_added_text",
            entity_type="knowledge_source", entity_id=str(source.id),
            payload={"title": source.title, "chunks": source.chunk_count},
        )
        await session.commit()

    except Exception as e:
        log.error("Text processing failed: %s", e, exc_info=True)
        source.status = KnowledgeSourceStatus.failed
        source.processing_error = str(e)
        await session.commit()

    await session.refresh(source)
    return KnowledgeSourceOut.from_record(source)


@router.post("/search", response_model=SearchResponse)
async def search_knowledge(
    body: SearchRequest,
    user: CurrentUser,
    session: SessionDep,
) -> SearchResponse:
    """Semantic search across all knowledge in the hub.

    Searches are workspace-isolated and can be filtered by level, tags, etc.
    """
    from prachar_shared.knowledge.vector_store import KnowledgeSearcher, EmbeddingGenerator

    # Generate query embedding
    gen = EmbeddingGenerator()
    query_embedding = gen.generate(body.query)

    # Build query for chunks
    query = select(
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
        KnowledgeChunkRecord.tenant_id == user.tenant_id,
        KnowledgeSourceRecord.status == KnowledgeSourceStatus.ready,
    )

    if body.level:
        query = query.where(KnowledgeSourceRecord.level == body.level)
    if body.workspace_id:
        query = query.where(
            (KnowledgeChunkRecord.workspace_id == uuid.UUID(body.workspace_id)) |
            (KnowledgeChunkRecord.workspace_id.is_(None))
        )
    if body.brand_id:
        query = query.where(
            (KnowledgeSourceRecord.brand_id == uuid.UUID(body.brand_id)) |
            (KnowledgeSourceRecord.brand_id.is_(None))
        )

    res = await session.execute(query)
    rows = res.all()

    if not rows:
        return SearchResponse(query=body.query, results=[], total=0)

    # Compute cosine similarity for each chunk
    from prachar_shared.knowledge.vector_store import cosine_similarity

    scored: list[tuple[float, KnowledgeChunkRecord, KnowledgeSourceRecord]] = []
    for chunk, source, embedding_rec in rows:
        if embedding_rec and embedding_rec.embedding:
            score = cosine_similarity(query_embedding, embedding_rec.embedding)
        else:
            # Fallback: simple text matching score
            query_lower = body.query.lower()
            content_lower = chunk.content.lower()
            overlap = sum(1 for word in query_lower.split() if word in content_lower)
            score = overlap / max(len(query_lower.split()), 1) * 0.5

        scored.append((score, chunk, source))

    # Sort by score and take top_k
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:body.top_k]

    results = [
        SearchResultOut(
            chunk_id=str(chunk.id),
            source_id=str(source.id),
            title=source.title,
            level=source.level,
            score=round(score, 4),
            content=chunk.content[:500],
            section=chunk.section,
            page_number=chunk.page_number,
        )
        for score, chunk, source in top
        if score > 0.01  # Filter out irrelevant results
    ]

    return SearchResponse(query=body.query, results=results, total=len(results))


@router.get("/levels", response_model=dict)
async def knowledge_by_level(
    user: CurrentUser,
    session: SessionDep,
    workspace_id: str | None = None,
) -> dict:
    """Get knowledge sources organized by level."""
    query = select(KnowledgeSourceRecord).where(
        KnowledgeSourceRecord.tenant_id == user.tenant_id,
        KnowledgeSourceRecord.status == KnowledgeSourceStatus.ready,
    )
    if workspace_id:
        query = query.where(
            (KnowledgeSourceRecord.workspace_id == uuid.UUID(workspace_id)) |
            (KnowledgeSourceRecord.workspace_id.is_(None))
        )

    res = await session.execute(query)
    sources = res.scalars().all()

    by_level: dict[str, list[dict]] = {
        KnowledgeLevel.brand: [],
        KnowledgeLevel.business: [],
        KnowledgeLevel.marketing: [],
        KnowledgeLevel.live: [],
    }

    for source in sources:
        by_level.setdefault(source.level, []).append(
            KnowledgeSourceOut.from_record(source).model_dump()
        )

    return {
        "levels": by_level,
        "counts": {level: len(items) for level, items in by_level.items()},
        "total": len(sources),
    }


@router.post("/attribute", response_model=AttributionOut, status_code=status.HTTP_201_CREATED)
async def record_attribution(
    body: AttributionRequest,
    user: CurrentUser,
    session: SessionDep,
) -> AttributionOut:
    """Record source attribution for an AI output.

    When CampaignBrain, Creative Studio, or any AI engine uses knowledge
    from the hub, this endpoint records which sources were used.
    """
    attr = KnowledgeAttributionRecord(
        tenant_id=user.tenant_id,
        output_type=body.output_type,
        output_id=body.output_id,
        source_ids=body.source_ids,
        chunk_ids=body.chunk_ids,
        query=body.query,
        relevance_scores=body.relevance_scores,
        engine=body.engine,
    )
    session.add(attr)
    await session.commit()
    await session.refresh(attr)

    return AttributionOut(
        id=str(attr.id),
        output_type=attr.output_type,
        output_id=attr.output_id,
        engine=attr.engine,
        query=attr.query,
        source_ids=attr.source_ids or [],
        chunk_ids=attr.chunk_ids or [],
        relevance_scores=attr.relevance_scores,
        created_at=attr.created_at.isoformat() if attr.created_at else "",
    )


@router.get("/attributions/{output_type}/{output_id}", response_model=list[AttributionOut])
async def get_attribution(
    output_type: str,
    output_id: str,
    user: CurrentUser,
    session: SessionDep,
) -> list[AttributionOut]:
    """Get source attribution for a specific AI output."""
    res = await session.execute(
        select(KnowledgeAttributionRecord).where(
            KnowledgeAttributionRecord.tenant_id == user.tenant_id,
            KnowledgeAttributionRecord.output_type == output_type,
            KnowledgeAttributionRecord.output_id == output_id,
        ).order_by(KnowledgeAttributionRecord.created_at.desc())
    )
    return [
        AttributionOut(
            id=str(a.id),
            output_type=a.output_type,
            output_id=a.output_id,
            engine=a.engine,
            query=a.query,
            source_ids=a.source_ids or [],
            chunk_ids=a.chunk_ids or [],
            relevance_scores=a.relevance_scores,
            created_at=a.created_at.isoformat() if a.created_at else "",
        )
        for a in res.scalars().all()
    ]
