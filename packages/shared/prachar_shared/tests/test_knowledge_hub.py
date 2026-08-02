"""Tests for the Business Knowledge Hub — document processing, embeddings,
governance, attribution, workspace isolation, and API endpoints."""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from prachar_shared.knowledge import (
    # Document processing
    DocumentProcessor, ParsedPage, ProcessingResult, TextChunk,
    # Vector store
    EmbeddingGenerator, KnowledgeSearcher, SearchResult, VectorStore, cosine_similarity,
    # Governance
    GovernanceChecker, GovernanceMetadata, KnowledgeLevel, KnowledgeLevelClassifier,
    # Attribution
    SourceCitation, AttributionRecord, AttributionTracker, WorkspaceKnowledgeFilter,
)


# ─── Document Processing Tests ──────────────────────────────────────────────


class TestDocumentProcessor:
    """Document processing pipeline — parse, clean, chunk."""

    def test_process_text(self):
        proc = DocumentProcessor()
        text = b"This is a test document. " * 100
        result = proc.process(file_bytes=text, file_type="text")
        assert result.success
        assert len(result.chunks) > 0
        assert result.total_tokens > 0

    def test_process_csv(self):
        proc = DocumentProcessor()
        csv = b"name,price,category\nWidget,9.99,gadgets\nGadget,19.99,tools\n"
        result = proc.process(file_bytes=csv, file_type="csv")
        assert result.success
        assert len(result.chunks) > 0

    def test_process_html(self):
        proc = DocumentProcessor()
        html = b"<html><body><h1>Title</h1><p>Content here.</p></body></html>"
        result = proc.process(file_bytes=html, file_type="html")
        assert result.success
        assert len(result.chunks) > 0
        # HTML tags should be stripped
        for chunk in result.chunks:
            assert "<html>" not in chunk.content
            assert "<body>" not in chunk.content

    def test_detect_file_type(self):
        proc = DocumentProcessor()
        assert proc.detect_file_type("report.pdf") == "pdf"
        assert proc.detect_file_type("doc.docx") == "word"
        assert proc.detect_file_type("data.xlsx") == "excel"
        assert proc.detect_file_type("slides.pptx") == "powerpoint"
        assert proc.detect_file_type("data.csv") == "csv"
        assert proc.detect_file_type("notes.txt") == "text"
        assert proc.detect_file_type("page.html") == "html"

    def test_clean_removes_noise(self):
        proc = DocumentProcessor()
        dirty = "  Hello   world  \n\n\n  With   extra  spaces  "
        clean = proc.clean(dirty)
        assert "  " not in clean  # No double spaces
        assert clean.strip() == clean  # No leading/trailing whitespace

    def test_chunk_overlap(self):
        proc = DocumentProcessor()
        page = ParsedPage(page_number=1, text="A" * 2000)
        chunks = proc.chunk([page], chunk_size=1000, overlap=200)
        assert len(chunks) >= 2
        # Second chunk should start with the last 200 chars of the first
        if len(chunks) >= 2:
            assert chunks[1].content[:200] == chunks[0].content[-200:]

    def test_chunk_token_count(self):
        proc = DocumentProcessor()
        page = ParsedPage(page_number=1, text="Hello world. " * 100)
        chunks = proc.chunk([page], chunk_size=500, overlap=50)
        for chunk in chunks:
            assert chunk.token_count > 0
            assert chunk.token_count == len(chunk.content) // 4

    def test_empty_input(self):
        proc = DocumentProcessor()
        result = proc.process(file_bytes=b"", file_type="text")
        assert not result.success or len(result.chunks) == 0

    def test_unsupported_file_type(self):
        proc = DocumentProcessor()
        result = proc.process(file_bytes=b"test", file_type="unknown")
        # Should not crash, should handle gracefully
        assert isinstance(result, ProcessingResult)


# ─── Embedding + Vector Store Tests ─────────────────────────────────────────


class TestEmbeddingGenerator:
    """Embedding generation with hash fallback."""

    def test_generate_returns_vector(self):
        gen = EmbeddingGenerator()
        emb = gen.generate("hello world")
        assert isinstance(emb, list)
        assert len(emb) > 0
        assert all(isinstance(v, float) for v in emb)

    def test_deterministic(self):
        gen = EmbeddingGenerator()
        emb1 = gen.generate("same text")
        emb2 = gen.generate("same text")
        assert emb1 == emb2

    def test_different_texts_different_embeddings(self):
        gen = EmbeddingGenerator()
        emb1 = gen.generate("hello world")
        emb2 = gen.generate("goodbye universe")
        assert emb1 != emb2

    def test_batch(self):
        gen = EmbeddingGenerator()
        texts = ["hello", "world", "test"]
        embeddings = gen.generate_batch(texts)
        assert len(embeddings) == 3
        assert all(len(e) == len(embeddings[0]) for e in embeddings)

    def test_caching(self):
        gen = EmbeddingGenerator()
        emb1 = gen.generate("cached text")
        emb2 = gen.generate("cached text")
        assert emb1 is emb2 or emb1 == emb2  # Same object or same value


class TestCosineSimilarity:
    """Pure Python cosine similarity."""

    def test_identical_vectors(self):
        a = [1.0, 0.0, 0.0]
        assert cosine_similarity(a, a) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_empty_vectors(self):
        assert cosine_similarity([], []) == 0.0

    def test_different_lengths(self):
        # Should handle gracefully (compare up to min length)
        result = cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0])
        assert isinstance(result, float)


class TestVectorStore:
    """In-memory vector store."""

    def test_add_and_search(self):
        store = VectorStore()
        emb1 = [1.0, 0.0, 0.0]
        emb2 = [0.0, 1.0, 0.0]
        store.add("chunk1", emb1, {"level": "brand"}, content="brand doc", source_id="s1")
        store.add("chunk2", emb2, {"level": "marketing"}, content="marketing doc", source_id="s2")

        results = store.search([1.0, 0.0, 0.0], top_k=2)
        assert len(results) == 2
        assert results[0].chunk_id == "chunk1"
        assert results[0].score > results[1].score

    def test_search_with_filter(self):
        store = VectorStore()
        store.add("c1", [1.0, 0.0], {"level": "brand"}, content="a", source_id="s1")
        store.add("c2", [0.9, 0.1], {"level": "marketing"}, content="b", source_id="s2")

        results = store.search([1.0, 0.0], top_k=5, filter={"level": "brand"})
        assert len(results) == 1
        assert results[0].chunk_id == "c1"

    def test_delete(self):
        store = VectorStore()
        store.add("c1", [1.0, 0.0], {}, content="a", source_id="s1")
        assert store.count() == 1
        store.delete("c1")
        assert store.count() == 0

    def test_count(self):
        store = VectorStore()
        assert store.count() == 0
        store.add("c1", [1.0], {}, content="a", source_id="s1")
        store.add("c2", [0.5], {}, content="b", source_id="s2")
        assert store.count() == 2


class TestKnowledgeSearcher:
    """High-level search facade."""

    def test_index_and_search(self):
        searcher = KnowledgeSearcher()
        searcher.index_chunk(
            chunk_id="c1", content="Brand guidelines for ACME Corp",
            source_id="s1", metadata={"level": "brand", "workspace_id": "ws1"},
        )
        searcher.index_chunk(
            chunk_id="c2", content="Marketing campaign for Diwali 2025",
            source_id="s2", metadata={"level": "marketing", "workspace_id": "ws1"},
        )

        results = searcher.search("brand guidelines", top_k=2)
        assert len(results) > 0

    def test_search_by_level(self):
        searcher = KnowledgeSearcher()
        searcher.index_chunk("c1", "brand content", "s1", {"level": "brand"})
        searcher.index_chunk("c2", "marketing content", "s2", {"level": "marketing"})

        results = searcher.search_by_level("brand", "brand", top_k=5)
        assert all(r.metadata.get("level") == "brand" for r in results)

    def test_search_by_workspace(self):
        searcher = KnowledgeSearcher()
        searcher.index_chunk("c1", "ws1 content", "s1", {"workspace_id": "ws1"})
        searcher.index_chunk("c2", "ws2 content", "s2", {"workspace_id": "ws2"})

        results = searcher.search_by_workspace("content", "ws1", top_k=5)
        assert all(r.metadata.get("workspace_id") == "ws1" for r in results)


# ─── Governance Tests ───────────────────────────────────────────────────────


class TestKnowledgeLevelClassifier:
    """4-level knowledge classification."""

    def test_brand_keywords(self):
        clf = KnowledgeLevelClassifier()
        assert clf.classify(title="Brand Guidelines 2026") == KnowledgeLevel.brand
        assert clf.classify(title="Logo and Colour Palette") == KnowledgeLevel.brand
        assert clf.classify(title="Our Mission and Vision") == KnowledgeLevel.brand

    def test_business_keywords(self):
        clf = KnowledgeLevelClassifier()
        assert clf.classify(title="Sales Process SOP") == KnowledgeLevel.business
        assert clf.classify(title="Customer FAQ") == KnowledgeLevel.business
        assert clf.classify(title="Team Structure Manual") == KnowledgeLevel.business

    def test_marketing_keywords(self):
        clf = KnowledgeLevelClassifier()
        assert clf.classify(title="Diwali Campaign 2025") == KnowledgeLevel.marketing
        assert clf.classify(title="Ad Creative for Instagram") == KnowledgeLevel.marketing
        assert clf.classify(title="SEO Report November") == KnowledgeLevel.marketing

    def test_live_from_integration(self):
        clf = KnowledgeLevelClassifier()
        assert clf.classify(
            title="Analytics Data", integration_name="google_analytics"
        ) == KnowledgeLevel.live
        assert clf.classify(
            title="Orders", integration_name="shopify"
        ) == KnowledgeLevel.live

    def test_default_to_business(self):
        clf = KnowledgeLevelClassifier()
        assert clf.classify(title="Random Document") == KnowledgeLevel.business

    def test_classify_batch(self):
        clf = KnowledgeLevelClassifier()
        docs = [
            {"title": "Brand Book"},
            {"title": "Campaign Report"},
            {"title": "Sales SOP"},
        ]
        levels = clf.classify_batch(docs)
        assert len(levels) == 3
        assert levels[0] == KnowledgeLevel.brand
        assert levels[1] == KnowledgeLevel.marketing
        assert levels[2] == KnowledgeLevel.business


class TestGovernanceChecker:
    """Knowledge governance — expiry, permissions, confidence."""

    def test_is_current_no_expiry(self):
        checker = GovernanceChecker()
        gm = GovernanceMetadata(source="upload")
        assert checker.is_current(gm) is True

    def test_is_current_future_expiry(self):
        checker = GovernanceChecker()
        gm = GovernanceMetadata(
            source="upload",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        assert checker.is_current(gm) is True

    def test_is_expired_past(self):
        checker = GovernanceChecker()
        gm = GovernanceMetadata(
            source="upload",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        assert checker.is_expired(gm) is True
        assert checker.is_current(gm) is False

    def test_should_use_current_and_accessible(self):
        checker = GovernanceChecker()
        gm = GovernanceMetadata(source="upload", confidence=0.8, permissions="shared", workspace_id="ws1")
        assert checker.should_use(gm, user_id="user1", workspace_id="ws1") is True

    def test_should_not_use_low_confidence(self):
        checker = GovernanceChecker()
        gm = GovernanceMetadata(source="upload", confidence=0.1)
        assert checker.should_use(gm, user_id="user1") is False

    def test_should_not_use_expired(self):
        checker = GovernanceChecker()
        gm = GovernanceMetadata(
            source="upload", confidence=0.9,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        assert checker.should_use(gm, user_id="user1") is False

    def test_confidence_labels(self):
        checker = GovernanceChecker()
        assert checker.confidence_label(0.9) == "high"
        assert checker.confidence_label(0.5) == "medium"
        assert checker.confidence_label(0.2) == "low"

    def test_recommended_expiry_brand(self):
        checker = GovernanceChecker()
        expiry = checker.recommended_expiry(KnowledgeLevel.brand)
        assert expiry is None  # Brand never expires

    def test_recommended_expiry_business(self):
        checker = GovernanceChecker()
        expiry = checker.recommended_expiry(KnowledgeLevel.business)
        assert expiry is not None
        # Should be about 365 days from now
        delta = expiry - datetime.now(timezone.utc)
        assert 360 < delta.days < 370

    def test_recommended_expiry_live(self):
        checker = GovernanceChecker()
        expiry = checker.recommended_expiry(KnowledgeLevel.live)
        assert expiry is not None
        delta = expiry - datetime.now(timezone.utc)
        assert 5 < delta.days < 10

    def test_private_permissions_owner_only(self):
        checker = GovernanceChecker()
        gm = GovernanceMetadata(source="upload", permissions="private", owner_id="owner1")
        assert checker.is_accessible(gm, user_id="owner1") is True
        assert checker.is_accessible(gm, user_id="other") is False

    def test_public_permissions(self):
        checker = GovernanceChecker()
        gm = GovernanceMetadata(source="upload", permissions="public")
        assert checker.is_accessible(gm, user_id="anyone") is True


# ─── Attribution Tests ──────────────────────────────────────────────────────


class TestSourceCitation:
    """Source citation for AI answers."""

    def test_creation(self):
        cite = SourceCitation(
            source_id="src1", title="Brand Guidelines", version=3,
            level="brand", relevance_score=0.92,
        )
        assert cite.source_id == "src1"
        assert cite.title == "Brand Guidelines"
        assert cite.version == 3

    def test_format_line(self):
        cite = SourceCitation(
            source_id="src1", title="Brand Guidelines", version=3,
            relevance_score=0.92,
        )
        line = cite.format_line()
        assert "Brand Guidelines" in line
        assert "v3" in line
        assert "92%" in line

    def test_format_line_no_version(self):
        cite = SourceCitation(source_id="src1", title="Pricing", relevance_score=0.8)
        line = cite.format_line()
        assert "Pricing" in line
        assert "v" not in line or "v1" not in line  # No version suffix for v1

    def test_to_dict_and_from_dict(self):
        cite = SourceCitation(source_id="s1", title="Test", version=2, level="brand")
        d = cite.to_dict()
        restored = SourceCitation.from_dict(d)
        assert restored.source_id == "s1"
        assert restored.title == "Test"
        assert restored.version == 2


class TestAttributionRecord:
    """Complete attribution for an AI output."""

    def test_format_for_display(self):
        record = AttributionRecord(
            output_type="campaign",
            output_id="camp1",
            engine="CampaignBrain",
            query="brand colours and pricing",
            citations=[
                SourceCitation(source_id="s1", title="Brand Guidelines", version=3, relevance_score=0.92),
                SourceCitation(source_id="s2", title="Pricing Catalogue 2026", relevance_score=0.87),
                SourceCitation(source_id="s3", title="Campaign 'Diwali 2025'", relevance_score=0.75),
            ],
        )
        text = record.format_for_display()
        assert "Based on:" in text
        assert "Brand Guidelines" in text
        assert "Pricing Catalogue" in text
        assert "Diwali" in text
        # Should be sorted by relevance (descending)
        assert text.index("Brand Guidelines") < text.index("Pricing Catalogue")

    def test_to_dict_and_from_dict(self):
        record = AttributionRecord(
            output_type="creative", output_id="cr1",
            engine="CreativeStudio", query="test",
            citations=[SourceCitation(source_id="s1", title="Test")],
        )
        d = record.to_dict()
        restored = AttributionRecord.from_dict(d)
        assert restored.output_type == "creative"
        assert restored.engine == "CreativeStudio"
        assert len(restored.citations) == 1


class TestAttributionTracker:
    """Tracks attributions across AI outputs."""

    def test_record_and_get(self):
        tracker = AttributionTracker()
        tracker.record(
            output_type="campaign", output_id="c1",
            engine="CampaignBrain", query="test",
            citations=[SourceCitation(source_id="s1", title="Brand Guide")],
        )
        retrieved = tracker.get("campaign", "c1")
        assert retrieved is not None
        assert retrieved.engine == "CampaignBrain"

    def test_get_nonexistent(self):
        tracker = AttributionTracker()
        assert tracker.get("campaign", "nonexistent") is None

    def test_get_by_engine(self):
        tracker = AttributionTracker()
        tracker.record("campaign", "c1", "CampaignBrain", "", [])
        tracker.record("creative", "cr1", "CreativeStudio", "", [])
        brain_records = tracker.get_by_engine("CampaignBrain")
        assert len(brain_records) == 1
        assert brain_records[0].output_type == "campaign"

    def test_format_attribution(self):
        tracker = AttributionTracker()
        tracker.record(
            "campaign", "c1", "CampaignBrain", "test",
            [SourceCitation(source_id="s1", title="Brand Guide", relevance_score=0.9)],
        )
        text = tracker.format_attribution("campaign", "c1")
        assert "Brand Guide" in text

    def test_list_recent(self):
        tracker = AttributionTracker()
        for i in range(5):
            tracker.record("campaign", f"c{i}", "CampaignBrain", "", [])
        recent = tracker.list_recent(limit=3)
        assert len(recent) == 3


# ─── Workspace Isolation Tests ──────────────────────────────────────────────


class TestWorkspaceKnowledgeFilter:
    """Workspace isolation for knowledge queries."""

    def test_build_filter_with_workspace(self):
        f = WorkspaceKnowledgeFilter.build_filter(workspace_id="ws1", level="brand")
        assert f["workspace_id"] == "ws1"
        assert f["level"] == "brand"

    def test_build_filter_with_tags(self):
        f = WorkspaceKnowledgeFilter.build_filter(tags=["vip", "premium"])
        assert "tags" in f

    def test_is_visible_same_workspace(self):
        assert WorkspaceKnowledgeFilter.is_visible("ws1", "ws1") is True

    def test_is_visible_different_workspace(self):
        assert WorkspaceKnowledgeFilter.is_visible("ws1", "ws2") is False

    def test_is_visible_tenant_wide(self):
        # Source with no workspace is visible to all
        assert WorkspaceKnowledgeFilter.is_visible(None, "ws1") is True

    def test_is_visible_public_overrides(self):
        assert WorkspaceKnowledgeFilter.is_visible("ws1", "ws2", permissions="public") is True

    def test_is_visible_private_different_workspace(self):
        assert WorkspaceKnowledgeFilter.is_visible("ws1", "ws2", permissions="private") is False

    def test_is_visible_private_same_workspace(self):
        assert WorkspaceKnowledgeFilter.is_visible("ws1", "ws1", permissions="private") is True


# ─── DB Model Tests ─────────────────────────────────────────────────────────


class TestKnowledgeModels:
    """Verify the SQLAlchemy models are correctly defined."""

    def test_knowledge_source_table(self):
        from prachar_api.models import KnowledgeSourceRecord
        assert KnowledgeSourceRecord.__tablename__ == "knowledge_sources"
        # Check key columns exist
        cols = {c.name for c in KnowledgeSourceRecord.__table__.columns}
        assert "level" in cols
        assert "source_type" in cols
        assert "status" in cols
        assert "version" in cols
        assert "owner_id" in cols
        assert "confidence" in cols
        assert "permissions" in cols
        assert "expires_at" in cols
        assert "tags" in cols
        assert "workspace_id" in cols
        assert "content_hash" in cols

    def test_knowledge_chunk_table(self):
        from prachar_api.models import KnowledgeChunkRecord
        assert KnowledgeChunkRecord.__tablename__ == "knowledge_chunks"
        cols = {c.name for c in KnowledgeChunkRecord.__table__.columns}
        assert "source_id" in cols
        assert "chunk_index" in cols
        assert "content" in cols
        assert "embedded" in cols
        assert "workspace_id" in cols

    def test_knowledge_embedding_table(self):
        from prachar_api.models import KnowledgeEmbeddingRecord
        assert KnowledgeEmbeddingRecord.__tablename__ == "knowledge_embeddings"
        cols = {c.name for c in KnowledgeEmbeddingRecord.__table__.columns}
        assert "chunk_id" in cols
        assert "embedding" in cols
        assert "embedding_dim" in cols

    def test_knowledge_attribution_table(self):
        from prachar_api.models import KnowledgeAttributionRecord
        assert KnowledgeAttributionRecord.__tablename__ == "knowledge_attributions"
        cols = {c.name for c in KnowledgeAttributionRecord.__table__.columns}
        assert "output_type" in cols
        assert "output_id" in cols
        assert "source_ids" in cols
        assert "engine" in cols


class TestKnowledgeEnums:
    """Verify the knowledge enums are correctly defined."""

    def test_knowledge_level_values(self):
        from prachar_api.models.enums import KnowledgeLevel
        assert KnowledgeLevel.brand.value == "brand"
        assert KnowledgeLevel.business.value == "business"
        assert KnowledgeLevel.marketing.value == "marketing"
        assert KnowledgeLevel.live.value == "live"

    def test_knowledge_source_status_values(self):
        from prachar_api.models.enums import KnowledgeSourceStatus
        assert KnowledgeSourceStatus.pending.value == "pending"
        assert KnowledgeSourceStatus.processing.value == "processing"
        assert KnowledgeSourceStatus.ready.value == "ready"
        assert KnowledgeSourceStatus.failed.value == "failed"

    def test_knowledge_source_type_values(self):
        from prachar_api.models.enums import KnowledgeSourceType
        assert KnowledgeSourceType.upload.value == "upload"
        assert KnowledgeSourceType.url.value == "url"
        assert KnowledgeSourceType.integration.value == "integration"
        assert KnowledgeSourceType.generated.value == "generated"
        assert KnowledgeSourceType.manual.value == "manual"

    def test_knowledge_file_type_values(self):
        from prachar_api.models.enums import KnowledgeFileType
        assert KnowledgeFileType.pdf.value == "pdf"
        assert KnowledgeFileType.word.value == "word"
        assert KnowledgeFileType.excel.value == "excel"
        assert KnowledgeFileType.csv.value == "csv"
        assert KnowledgeFileType.image.value == "image"
