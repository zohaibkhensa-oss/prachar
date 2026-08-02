"""Tests for the Context Ranking Layer and Observability system.

Covers:
- Token estimation
- ContextItem scoring (base, semantic, recency, confidence, intent alignment)
- Token budget trimming
- Always-keep types
- Minimum items guarantee
- ContextTrace recording and formatting
- ContextItemExtractor for all provider types
- RankedEnrichedContext snapshot
- Integration with ContextBuilder (ranking applied, trace emitted)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from prachar_api.runtime.context_builder import ContextBuilder, ContextProvider
from prachar_api.runtime.context_ranking import (
    BASE_SCORES,
    AdaptiveContextRankingLayer,
    ChunkWeightAdjustment,
    ContextEvaluation,
    ContextEvaluator,
    ContextItem,
    ContextItemExtractor,
    ContextItemType,
    ContextRankingLayer,
    ContextTrace,
    FeedbackRecord,
    ItemEvaluation,
    OfflineModelVersion,
    ProviderTrace,
    RankedEnrichedContext,
    RankingFeedbackStore,
    RetrievalQuality,
    ScoringWeights,
    SourceWeightAdjustment,
    TypeWeightAdjustment,
    estimate_dict_tokens,
    estimate_tokens,
)


# ─── Token Estimation ───────────────────────────────────────────────────────


class TestTokenEstimation:
    def test_estimate_tokens_empty(self):
        assert estimate_tokens("") == 0

    def test_estimate_tokens_short(self):
        # 4 chars → 1 token
        assert estimate_tokens("abcd") == 1

    def test_estimate_tokens_longer(self):
        # 20 chars → 5 tokens
        assert estimate_tokens("a" * 20) == 5

    def test_estimate_tokens_min_one(self):
        # 1 char → at least 1 token
        assert estimate_tokens("a") == 1

    def test_estimate_dict_tokens_empty(self):
        assert estimate_dict_tokens({}) == 0

    def test_estimate_dict_tokens_flat(self):
        data = {"key": "a" * 20}  # 5 tokens
        assert estimate_dict_tokens(data) == 5

    def test_estimate_dict_tokens_nested(self):
        data = {"outer": {"inner": "a" * 20}}
        assert estimate_dict_tokens(data) == 5

    def test_estimate_dict_tokens_list(self):
        data = {"items": ["a" * 20, "b" * 20]}
        assert estimate_dict_tokens(data) == 10


# ─── Context Item ───────────────────────────────────────────────────────────


class TestContextItem:
    def test_item_auto_estimates_tokens(self):
        item = ContextItem(
            type=ContextItemType.KNOWLEDGE_CHUNK,
            title="Test",
            content="a" * 40,
        )
        assert item.tokens == 10

    def test_item_explicit_tokens(self):
        item = ContextItem(
            type=ContextItemType.KNOWLEDGE_CHUNK,
            title="Test",
            content="a" * 40,
            tokens=999,
        )
        assert item.tokens == 999

    def test_item_default_kept_true(self):
        item = ContextItem(
            type=ContextItemType.BRAND_INFO,
            title="Brand",
            content="Brand info",
        )
        assert item.kept is True


# ─── Context Ranking Layer — Scoring ────────────────────────────────────────


class TestScoring:
    def test_base_score_applied(self):
        ranking = ContextRankingLayer()
        item = ContextItem(
            type=ContextItemType.BRAND_INFO,
            title="Brand",
            content="Brand info",
        )
        score = ranking.score_item(item)
        # Brand info has base 0.95, no other metadata → 0.95 * 0.50 + 0.5*0.20 + 0.5*0.15 + 0.5*0.10 + 0.3*0.05
        # = 0.475 + 0.10 + 0.075 + 0.05 + 0.015 = 0.715
        assert 0.6 < score < 0.8

    def test_semantic_relevance_for_knowledge(self):
        ranking = ContextRankingLayer()
        high_sim = ContextItem(
            type=ContextItemType.KNOWLEDGE_CHUNK,
            title="High",
            content="x",
            metadata={"similarity_score": 0.95},
        )
        low_sim = ContextItem(
            type=ContextItemType.KNOWLEDGE_CHUNK,
            title="Low",
            content="x",
            metadata={"similarity_score": 0.20},
        )
        assert ranking.score_item(high_sim) > ranking.score_item(low_sim)

    def test_recency_boost_newer_items(self):
        ranking = ContextRankingLayer()
        recent = ContextItem(
            type=ContextItemType.COUNCIL_DECISION,
            title="Recent",
            content="x",
            metadata={"created_at": datetime.now(timezone.utc).isoformat()},
        )
        old = ContextItem(
            type=ContextItemType.COUNCIL_DECISION,
            title="Old",
            content="x",
            metadata={"created_at": (datetime.now(timezone.utc) - timedelta(days=300)).isoformat()},
        )
        assert ranking.score_item(recent) > ranking.score_item(old)

    def test_recency_score_string_format(self):
        ranking = ContextRankingLayer()
        score = ranking._recency_score(datetime.now(timezone.utc).isoformat())
        assert score == 1.0

    def test_recency_score_old(self):
        ranking = ContextRankingLayer()
        old = datetime.now(timezone.utc) - timedelta(days=400)
        score = ranking._recency_score(old.isoformat())
        assert score == 0.1

    def test_recency_score_naive_datetime(self):
        ranking = ContextRankingLayer()
        dt = datetime.utcnow() - timedelta(days=30)
        score = ranking._recency_score(dt)
        assert 0.1 < score < 1.0

    def test_recency_score_invalid(self):
        ranking = ContextRankingLayer()
        score = ranking._recency_score("not a date")
        assert score == 0.5

    def test_confidence_boost(self):
        ranking = ContextRankingLayer()
        high = ContextItem(
            type=ContextItemType.BUSINESS_PROFILE,
            title="High",
            content="x",
            metadata={"confidence": 0.95},
        )
        low = ContextItem(
            type=ContextItemType.BUSINESS_PROFILE,
            title="Low",
            content="x",
            metadata={"confidence": 0.10},
        )
        assert ranking.score_item(high) > ranking.score_item(low)

    def test_intent_alignment_campaign(self):
        ranking = ContextRankingLayer()
        audience = ContextItem(
            type=ContextItemType.AUDIENCE_PROFILE,
            title="Audience",
            content="x",
        )
        billing = ContextItem(
            type=ContextItemType.BILLING,
            title="Billing",
            content="x",
        )
        score_aud = ranking.score_item(audience, intent="campaign creation")
        score_bill = ranking.score_item(billing, intent="campaign creation")
        assert score_aud > score_bill

    def test_intent_alignment_performance(self):
        ranking = ContextRankingLayer()
        perf = ContextItem(
            type=ContextItemType.PERFORMANCE_DATA,
            title="Perf",
            content="x",
        )
        billing = ContextItem(
            type=ContextItemType.BILLING,
            title="Billing",
            content="x",
        )
        score_perf = ranking.score_item(perf, intent="performance analysis")
        score_bill = ranking.score_item(billing, intent="performance analysis")
        assert score_perf > score_bill

    def test_score_clamped_to_unit_interval(self):
        ranking = ContextRankingLayer()
        item = ContextItem(
            type=ContextItemType.BRAND_INFO,
            title="Test",
            content="x",
            metadata={"similarity_score": 1.0, "confidence": 1.0},
        )
        score = ranking.score_item(item)
        assert 0.0 <= score <= 1.0


# ─── Context Ranking Layer — Ranking & Trimming ─────────────────────────────


class TestRankingAndTrimming:
    def test_empty_items(self):
        ranking = ContextRankingLayer()
        result = ranking.rank([])
        assert result == []

    def test_all_items_kept_under_budget(self):
        ranking = ContextRankingLayer(token_budget=10000)
        items = [
            ContextItem(type=ContextItemType.BRAND_INFO, title="A", content="a" * 20),
            ContextItem(type=ContextItemType.MEMORY, title="B", content="b" * 20),
        ]
        result = ranking.rank(items)
        assert all(i.kept for i in result)
        assert len(result) == 2

    def test_items_trimmed_over_budget(self):
        ranking = ContextRankingLayer(token_budget=15)  # Very small budget (3 items max)
        items = [
            ContextItem(type=ContextItemType.BRAND_INFO, title="Brand", content="a" * 20),  # 5 tokens, always kept
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="K1", content="b" * 20,
                        metadata={"similarity_score": 0.9}),  # 5 tokens
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="K2", content="c" * 20,
                        metadata={"similarity_score": 0.5}),  # 5 tokens
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="K3", content="d" * 20,
                        metadata={"similarity_score": 0.3}),  # 5 tokens
        ]
        result = ranking.rank(items)
        kept = [i for i in result if i.kept]
        trimmed = [i for i in result if not i.kept]
        # Brand is always kept; some knowledge items should be trimmed
        assert any(i.title == "Brand" for i in kept)
        assert len(kept) < len(items)
        assert len(trimmed) > 0

    def test_always_keep_types_preserved(self):
        ranking = ContextRankingLayer(
            token_budget=10,  # Tiny budget
            always_keep_types={ContextItemType.BRAND_INFO},
        )
        items = [
            ContextItem(type=ContextItemType.BRAND_INFO, title="Brand", content="a" * 100),
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="K", content="b" * 100),
        ]
        result = ranking.rank(items)
        brand = next(i for i in result if i.title == "Brand")
        assert brand.kept is True

    def test_min_items_guarantee(self):
        ranking = ContextRankingLayer(token_budget=5, min_items=3)
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="A", content="a" * 100),
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="B", content="b" * 100),
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="C", content="c" * 100),
        ]
        result = ranking.rank(items)
        kept = [i for i in result if i.kept]
        assert len(kept) >= 3

    def test_sorted_by_score_descending(self):
        ranking = ContextRankingLayer(token_budget=10000)
        items = [
            ContextItem(type=ContextItemType.BILLING, title="Low", content="a" * 20),
            ContextItem(type=ContextItemType.BRAND_INFO, title="High", content="b" * 20),
            ContextItem(type=ContextItemType.MEMORY, title="Mid", content="c" * 20),
        ]
        result = ranking.rank(items)
        kept = [i for i in result if i.kept]
        scores = [i.score for i in kept]
        assert scores == sorted(scores, reverse=True)

    def test_rank_to_prompt_returns_string(self):
        ranking = ContextRankingLayer(token_budget=10000)
        items = [
            ContextItem(type=ContextItemType.BRAND_INFO, title="Brand", content="My Brand"),
        ]
        prompt = ranking.rank_to_prompt(items)
        assert "Brand" in prompt
        assert "My Brand" in prompt
        assert "score:" in prompt


# ─── Context Trace (Observability) ──────────────────────────────────────────


class TestContextTrace:
    def test_trace_starts_empty(self):
        trace = ContextTrace()
        assert trace.providers_activated == []
        assert trace.providers_skipped == []
        assert trace.total_items == 0

    def test_add_activated(self):
        trace = ContextTrace()
        trace.add_activated(ProviderTrace(name="knowledge", activated=True, items_loaded=5, tokens_estimated=1200))
        assert len(trace.providers_activated) == 1
        assert trace.total_items == 5
        assert trace.estimated_prompt_tokens == 1200

    def test_add_skipped(self):
        trace = ContextTrace()
        trace.add_skipped("billing", reason="not relevant")
        assert len(trace.providers_skipped) == 1
        assert trace.providers_skipped[0].name == "billing"

    def test_record_ranking(self):
        trace = ContextTrace()
        items = [
            ContextItem(type=ContextItemType.BRAND_INFO, title="Brand", content="x" * 20),
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="K1", content="y" * 20),
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="K2", content="z" * 20),
        ]
        items[0].kept = True
        items[1].kept = True
        items[2].kept = False
        trace.record_ranking(items, final_tokens=10)
        assert trace.ranking_applied is True
        assert trace.items_kept == 2
        assert trace.items_trimmed == 1
        assert "K2" in trace.trimmed_titles
        assert trace.final_prompt_tokens == 10
        assert len(trace.top_items) <= 5

    def test_to_dict(self):
        trace = ContextTrace(message="hello world this is a long message", intent="campaign")
        trace.add_activated(ProviderTrace(name="knowledge", activated=True, items_loaded=3, tokens_estimated=500))
        trace.add_skipped("billing", reason="not relevant")
        trace.record_ranking([], final_tokens=0)
        d = trace.to_dict()
        assert d["intent"] == "campaign"
        assert len(d["message"]) <= 200
        assert d["providers_activated"][0]["name"] == "knowledge"
        assert d["providers_skipped"][0]["name"] == "billing"
        assert d["ranking_applied"] is True

    def test_format_for_display(self):
        trace = ContextTrace(message="create campaign", intent="campaign creation")
        trace.add_activated(ProviderTrace(name="knowledge", activated=True, items_loaded=5, tokens_estimated=1200))
        trace.add_skipped("billing", reason="not relevant")
        trace.record_ranking([], final_tokens=0)
        text = trace.format_for_display()
        assert "Context Build" in text
        assert "knowledge" in text
        assert "billing" in text
        assert "Intent" in text

    def test_mark_start_end(self):
        trace = ContextTrace()
        trace.mark_start()
        trace.mark_end()
        assert trace.total_build_time_ms >= 0


# ─── Context Item Extractor ─────────────────────────────────────────────────


class TestContextItemExtractor:
    def test_extract_knowledge(self):
        data = {
            "chunks": [
                {"title": "Brand Guidelines", "content": "Use bold colors", "score": 0.92, "level": "brand"},
                {"title": "Pricing", "content": "Premium pricing", "score": 0.75, "level": "product"},
            ]
        }
        items = ContextItemExtractor.extract("knowledge", data)
        assert len(items) == 2
        assert items[0].type == ContextItemType.KNOWLEDGE_CHUNK
        assert items[0].metadata["similarity_score"] == 0.92

    def test_extract_mi(self):
        data = {
            "business_profile": {"summary": "Tech startup", "confidence": 0.8},
            "audience_profile": {"summary": "Young professionals", "confidence": 0.7},
        }
        items = ContextItemExtractor.extract("marketing_intelligence", data)
        assert len(items) == 2
        types = {i.type for i in items}
        assert ContextItemType.BUSINESS_PROFILE in types
        assert ContextItemType.AUDIENCE_PROFILE in types

    def test_extract_council(self):
        data = {
            "recent_decisions": [
                {"campaign": "Diwali 2024", "decision": "Approved", "reasoning": "Strong creative"},
            ]
        }
        items = ContextItemExtractor.extract("council_memory", data)
        assert len(items) == 1
        assert items[0].type == ContextItemType.COUNCIL_DECISION
        assert "Diwali 2024" in items[0].content

    def test_extract_integrations(self):
        data = {
            "connected": [
                {"name": "GA4", "status": "connected", "summary": "Tracking active"},
            ]
        }
        items = ContextItemExtractor.extract("integrations", data)
        assert len(items) == 1
        assert items[0].type == ContextItemType.INTEGRATION_DATA

    def test_extract_performance(self):
        data = {
            "campaign_performance": {"summary": "ROAS 3.5x"},
            "attribution": {"summary": "Last-click model"},
        }
        items = ContextItemExtractor.extract("performance", data)
        assert len(items) == 2
        types = {i.type for i in items}
        assert ContextItemType.PERFORMANCE_DATA in types
        assert ContextItemType.ATTRIBUTION_DATA in types

    def test_extract_reviews_with_pending(self):
        data = {"pending_count": 3}
        items = ContextItemExtractor.extract("reviews", data)
        assert len(items) == 1
        assert items[0].type == ContextItemType.REVIEW_ITEM

    def test_extract_reviews_no_pending(self):
        data = {"pending_count": 0}
        items = ContextItemExtractor.extract("reviews", data)
        assert len(items) == 0

    def test_extract_domain_pack(self):
        data = {"name": "SaaS", "category": "B2B"}
        items = ContextItemExtractor.extract("domain_pack", data)
        assert len(items) == 1
        assert items[0].type == ContextItemType.DOMAIN_PACK

    def test_extract_capabilities(self):
        data = {"capabilities": [{"name": "video_gen", "available": True}, {"name": "billing", "available": False}]}
        items = ContextItemExtractor.extract("capabilities", data)
        assert len(items) == 1
        assert "video_gen" in items[0].content

    def test_extract_unknown_provider(self):
        items = ContextItemExtractor.extract("unknown", {"foo": "bar"})
        assert items == []

    def test_extract_base_context_with_brand(self):
        brand = MagicMock()
        brand.name = "TestBrand"
        brand.category = "SaaS"
        brand.website = "https://example.com"
        brand.tone = "professional"
        memory = MagicMock()
        memory.best_practices = ["Always A/B test", "Use clear CTAs"]
        items = ContextItemExtractor.extract_base_context(brand, memory)
        assert len(items) == 2
        assert items[0].type == ContextItemType.BRAND_INFO
        assert items[1].type == ContextItemType.MEMORY

    def test_extract_base_context_no_brand(self):
        items = ContextItemExtractor.extract_base_context(None, None)
        assert items == []


# ─── RankedEnrichedContext ──────────────────────────────────────────────────


class TestRankedEnrichedContext:
    def test_to_snapshot_includes_trace(self):
        base = MagicMock()
        base.to_snapshot.return_value = {"brand_id": "123"}
        trace = ContextTrace(intent="campaign")
        ctx = RankedEnrichedContext(
            base=base,
            enriched={"knowledge": {"chunks": []}},
            providers_used=["knowledge"],
            trace=trace,
            prompt_context="some context",
        )
        snapshot = ctx.to_snapshot()
        assert "trace" in snapshot
        assert snapshot["trace"]["intent"] == "campaign"
        assert snapshot["providers_used"] == ["knowledge"]

    def test_to_prompt_context_returns_prompt(self):
        ctx = RankedEnrichedContext(
            base=MagicMock(),
            prompt_context="ranked context here",
        )
        assert ctx.to_prompt_context() == "ranked context here"


# ─── Integration with ContextBuilder ────────────────────────────────────────


class TestContextBuilderIntegration:
    @pytest.mark.asyncio
    async def test_build_emits_trace(self):
        """ContextBuilder.build() should return a RankedEnrichedContext with a trace."""
        # Mock provider that returns knowledge chunks
        class MockKnowledgeProvider:
            name = "knowledge"

            def is_relevant(self, message: str, intent: str = "") -> bool:
                return "campaign" in message.lower()

            async def load(self, session, tenant_id, brand_id, message):
                return {
                    "chunks": [
                        {"title": "Brand Guidelines", "content": "Use bold colors", "score": 0.92},
                    ]
                }

        # Mock provider that is not relevant
        class MockBillingProvider:
            name = "billing"

            def is_relevant(self, message: str, intent: str = "") -> bool:
                return False

            async def load(self, session, tenant_id, brand_id, message):
                return {"usage": 1000}

        builder = ContextBuilder(providers=[MockKnowledgeProvider(), MockBillingProvider()])

        # Mock the assemble_context function
        from prachar_api.runtime import context_builder as cb_module
        original_assemble = cb_module.assemble_context

        async def mock_assemble(**kwargs):
            ctx = MagicMock()
            ctx.brand = None
            ctx.memory = MagicMock()
            ctx.memory.best_practices = []
            ctx.session = None
            return ctx

        cb_module.assemble_context = mock_assemble
        try:
            result = await builder.build(
                session=None,
                user=MagicMock(tenant_id="t1"),
                brand_id="b1",
                message="create a diwali campaign",
                intent="campaign.creation",
            )
        finally:
            cb_module.assemble_context = original_assemble

        assert isinstance(result, RankedEnrichedContext)
        assert result.trace.intent == "campaign.creation"
        assert "knowledge" in result.providers_used
        # Billing should be skipped
        skipped_names = [p.name for p in result.trace.providers_skipped]
        assert "billing" in skipped_names
        # Should have ranked items
        assert len(result.ranked_items) > 0
        # Should have a prompt context
        assert result.prompt_context != ""

    @pytest.mark.asyncio
    async def test_build_with_no_relevant_providers(self):
        """If no providers are relevant, should still return a valid context."""
        builder = ContextBuilder(providers=[])

        from prachar_api.runtime import context_builder as cb_module
        original_assemble = cb_module.assemble_context

        async def mock_assemble(**kwargs):
            ctx = MagicMock()
            ctx.brand = None
            ctx.memory = MagicMock()
            ctx.memory.best_practices = []
            ctx.session = None
            return ctx

        cb_module.assemble_context = mock_assemble
        try:
            result = await builder.build(
                session=None,
                user=MagicMock(tenant_id="t1"),
                brand_id="b1",
                message="hello",
            )
        finally:
            cb_module.assemble_context = original_assemble

        assert isinstance(result, RankedEnrichedContext)
        assert result.providers_used == []
        assert result.trace.total_items == 0


# ─── Base Scores Sanity ─────────────────────────────────────────────────────


class TestBaseScores:
    def test_all_types_have_scores(self):
        for item_type in ContextItemType:
            assert item_type in BASE_SCORES, f"Missing base score for {item_type}"

    def test_scores_in_unit_interval(self):
        for item_type, score in BASE_SCORES.items():
            assert 0.0 <= score <= 1.0, f"Score for {item_type} out of range: {score}"

    def test_brand_info_is_highest(self):
        assert BASE_SCORES[ContextItemType.BRAND_INFO] >= 0.9

    def test_billing_is_lowest(self):
        assert BASE_SCORES[ContextItemType.BILLING] <= 0.3


# ─── Context Evaluation (Post-Hoc Metrics) ──────────────────────────────────


class TestContextEvaluation:
    def test_evaluation_defaults(self):
        ev = ContextEvaluation()
        assert ev.items_total == 0
        assert ev.items_kept == 0
        assert ev.answer_support_pct == 0.0

    def test_to_dict(self):
        ev = ContextEvaluation(items_total=10, items_kept=5, items_referenced=3)
        d = ev.to_dict()
        assert d["items_total"] == 10
        assert d["items_kept"] == 5
        assert d["items_referenced"] == 3

    def test_format_for_display(self):
        ev = ContextEvaluation(
            chunks_retrieved=12, chunks_used=5, chunks_referenced=3,
            answer_support_pct=94, unused_context_pct=58,
            avg_retrieval_score=0.87,
        )
        text = ev.format_for_display()
        assert "Context Build Evaluation" in text
        assert "12" in text  # chunks retrieved
        assert "94%" in text  # answer support


class TestContextEvaluator:
    def test_evaluate_empty_items(self):
        ev = ContextEvaluator.evaluate([], "some answer")
        assert ev.items_total == 0
        assert ev.items_kept == 0

    def test_evaluate_counts(self):
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="A", content="x" * 20,
                        metadata={"similarity_score": 0.9}),
            ContextItem(type=ContextItemType.BRAND_INFO, title="B", content="y" * 20),
            ContextItem(type=ContextItemType.BILLING, title="C", content="z" * 20),
        ]
        items[0].kept = True
        items[1].kept = True
        items[2].kept = False
        ev = ContextEvaluator.evaluate(items, "answer text")
        assert ev.items_total == 3
        assert ev.items_kept == 2
        assert ev.items_trimmed == 1

    def test_evaluate_chunks_retrieved(self):
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="K1", content="x",
                        metadata={"similarity_score": 0.9}),
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="K2", content="y",
                        metadata={"similarity_score": 0.8}),
        ]
        items[0].kept = True
        items[1].kept = False
        ev = ContextEvaluator.evaluate(items, "answer")
        assert ev.chunks_retrieved == 2
        assert ev.chunks_used == 1

    def test_avg_retrieval_score(self):
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="K1", content="x",
                        metadata={"similarity_score": 0.9}),
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="K2", content="y",
                        metadata={"similarity_score": 0.7}),
        ]
        ev = ContextEvaluator.evaluate(items, "answer")
        assert ev.avg_retrieval_score == pytest.approx(0.8, abs=0.01)

    def test_referenced_detection(self):
        """Items whose content words appear in the answer should be marked referenced."""
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="Brand Guidelines",
                        content="Use bold colors and modern typography for campaigns",
                        metadata={"similarity_score": 0.9}),
        ]
        items[0].kept = True
        answer = "Based on your brand guidelines, use bold colors and modern typography."
        ev = ContextEvaluator.evaluate(items, answer)
        assert ev.items_referenced == 1
        assert ev.item_evaluations[0].referenced is True

    def test_not_referenced_detection(self):
        """Items whose content doesn't appear in the answer should not be referenced."""
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="Pricing",
                        content="Premium pricing strategy for enterprise customers",
                        metadata={"similarity_score": 0.9}),
        ]
        items[0].kept = True
        answer = "Let's create a social media calendar for next month."
        ev = ContextEvaluator.evaluate(items, answer)
        assert ev.items_referenced == 0
        assert ev.item_evaluations[0].referenced is False

    def test_answer_support_pct(self):
        """Answer support should be > 0 when items are referenced."""
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="Strategy",
                        content="Focus on premium positioning and targeted advertising",
                        metadata={"similarity_score": 0.9}),
        ]
        items[0].kept = True
        answer = "Focus on premium positioning and targeted advertising for this campaign."
        ev = ContextEvaluator.evaluate(items, answer)
        assert ev.answer_support_pct > 0

    def test_unused_context_pct(self):
        """Unused context should be > 0 when kept items aren't referenced."""
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="Useful",
                        content="Focus on premium positioning and targeted advertising",
                        metadata={"similarity_score": 0.9}),
            ContextItem(type=ContextItemType.COMPETITOR_PROFILE, title="Useless",
                        content="Competitor launched something completely unrelated here",
                        source="marketing_intelligence"),
        ]
        items[0].kept = True
        items[1].kept = True
        answer = "Focus on premium positioning and targeted advertising."
        ev = ContextEvaluator.evaluate(items, answer)
        assert ev.unused_context_pct > 0

    def test_trimmed_items_not_evaluated_for_reference(self):
        """Trimmed items should not be checked for references."""
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="K",
                        content="Focus on premium positioning and targeted advertising",
                        metadata={"similarity_score": 0.9}),
        ]
        items[0].kept = False  # Trimmed
        answer = "Focus on premium positioning and targeted advertising."
        ev = ContextEvaluator.evaluate(items, answer)
        assert ev.items_referenced == 0

    def test_item_evaluations_populated(self):
        items = [
            ContextItem(type=ContextItemType.BRAND_INFO, title="Brand", content="My Brand"),
            ContextItem(type=ContextItemType.MEMORY, title="Memory", content="Past learning"),
        ]
        items[0].kept = True
        items[1].kept = True
        ev = ContextEvaluator.evaluate(items, "answer")
        assert len(ev.item_evaluations) == 2
        assert ev.item_evaluations[0].title == "Brand"
        assert ev.item_evaluations[0].kept is True


# ─── Feedback Record ────────────────────────────────────────────────────────


class TestFeedbackRecord:
    def test_outcome_score_not_kept(self):
        """Items not kept have no signal."""
        r = FeedbackRecord(item_type="knowledge_chunk", source="knowledge",
                           kept=False, referenced=False)
        assert r.outcome_score == 0.0

    def test_outcome_score_referenced_positive(self):
        """Referenced + accepted + positive → high positive score."""
        r = FeedbackRecord(item_type="knowledge_chunk", source="knowledge",
                           kept=True, referenced=True, user_accepted=True,
                           positive_outcome=True)
        assert r.outcome_score > 0.5
        assert r.outcome_score <= 1.0

    def test_outcome_score_not_referenced_negative(self):
        """Kept but not referenced + rejected → negative score."""
        r = FeedbackRecord(item_type="knowledge_chunk", source="knowledge",
                           kept=True, referenced=False, user_accepted=False,
                           positive_outcome=False)
        assert r.outcome_score < 0

    def test_outcome_score_clamped(self):
        """Outcome score should be clamped to [-1, 1]."""
        r = FeedbackRecord(item_type="knowledge_chunk", source="knowledge",
                           kept=True, referenced=True, user_accepted=True,
                           positive_outcome=True)
        assert -1.0 <= r.outcome_score <= 1.0


# ─── Ranking Feedback Store ─────────────────────────────────────────────────


class TestRankingFeedbackStore:
    def test_empty_store(self):
        store = RankingFeedbackStore()
        assert store.stats()["total_records"] == 0
        assert store.compute_type_adjustments() == {}

    def test_record_and_stats(self):
        store = RankingFeedbackStore()
        store.record(FeedbackRecord(
            item_type="knowledge_chunk", source="knowledge",
            kept=True, referenced=True, user_accepted=True,
        ))
        stats = store.stats()
        assert stats["total_records"] == 1
        assert stats["types_tracked"] == 1

    def test_compute_adjustments_positive(self):
        """Positive feedback should produce positive adjustment."""
        store = RankingFeedbackStore()
        for _ in range(10):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                kept=True, referenced=True, user_accepted=True,
                positive_outcome=True,
            ))
        adjustments = store.compute_type_adjustments()
        assert "knowledge_chunk" in adjustments
        assert adjustments["knowledge_chunk"].adjustment > 0

    def test_compute_adjustments_negative(self):
        """Negative feedback should produce negative adjustment."""
        store = RankingFeedbackStore()
        for _ in range(10):
            store.record(FeedbackRecord(
                item_type="billing", source="billing",
                kept=True, referenced=False, user_accepted=False,
                positive_outcome=False,
            ))
        adjustments = store.compute_type_adjustments()
        assert "billing" in adjustments
        assert adjustments["billing"].adjustment < 0

    def test_adjustment_clamped(self):
        """Adjustments should be clamped to [-0.2, +0.2]."""
        store = RankingFeedbackStore(learning_rate=1.0)  # Very high rate
        for _ in range(100):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                kept=True, referenced=True, user_accepted=True,
                positive_outcome=True,
            ))
        adjustments = store.compute_type_adjustments()
        assert adjustments["knowledge_chunk"].adjustment <= 0.2
        assert adjustments["knowledge_chunk"].adjustment >= -0.2

    def test_record_from_evaluation(self):
        """Should record feedback for all items in an evaluation."""
        store = RankingFeedbackStore()
        ev = ContextEvaluation(
            item_evaluations=[
                ItemEvaluation(title="A", item_type="knowledge_chunk", source="knowledge",
                               score=0.9, tokens=10, kept=True, referenced=True),
                ItemEvaluation(title="B", item_type="brand_info", source="base",
                               score=0.95, tokens=5, kept=True, referenced=False),
            ]
        )
        store.record_from_evaluation(ev, user_accepted=True)
        assert store.stats()["total_records"] == 2

    def test_get_type_adjustment_no_data(self):
        """Should return 0 for types with no feedback."""
        store = RankingFeedbackStore()
        assert store.get_type_adjustment(ContextItemType.KNOWLEDGE_CHUNK) == 0.0

    def test_get_type_adjustment_with_data(self):
        """Should return non-zero for types with feedback."""
        store = RankingFeedbackStore()
        for _ in range(10):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                kept=True, referenced=True, user_accepted=True,
            ))
        adj = store.get_type_adjustment(ContextItemType.KNOWLEDGE_CHUNK)
        assert adj > 0

    def test_max_records_trim(self):
        """Old records should be trimmed when over capacity."""
        store = RankingFeedbackStore(max_records=5)
        for i in range(10):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                kept=True, referenced=True,
            ))
        assert store.stats()["total_records"] == 5

    def test_cache_invalidation(self):
        """Cache should be invalidated when new records are added."""
        store = RankingFeedbackStore()
        store.record(FeedbackRecord(
            item_type="knowledge_chunk", source="knowledge",
            kept=True, referenced=True,
        ))
        adj1 = store.compute_type_adjustments()
        # Add more records
        for _ in range(5):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                kept=True, referenced=False, user_accepted=False,
            ))
        adj2 = store.compute_type_adjustments()
        # The adjustment should change (more negative now)
        assert adj2["knowledge_chunk"].samples > adj1["knowledge_chunk"].samples


# ─── Adaptive Ranking Layer ─────────────────────────────────────────────────


class TestAdaptiveContextRankingLayer:
    def test_no_feedback_store_uses_base_scores(self):
        """Without a feedback store, should behave like the base layer."""
        layer = AdaptiveContextRankingLayer(feedback_store=None)
        item = ContextItem(type=ContextItemType.BRAND_INFO, title="Brand", content="x")
        score = layer.score_item(item)
        # Should be same as base layer
        base = ContextRankingLayer()
        assert score == base.score_item(item)

    def test_positive_feedback_boosts_score(self):
        """Positive feedback should increase the score above base."""
        store = RankingFeedbackStore()
        for _ in range(20):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                kept=True, referenced=True, user_accepted=True,
                positive_outcome=True,
            ))
        adaptive = AdaptiveContextRankingLayer(feedback_store=store)
        base = ContextRankingLayer()

        item = ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="K",
                           content="x", metadata={"similarity_score": 0.8})
        adaptive_score = adaptive.score_item(item)
        base_score = base.score_item(item)
        assert adaptive_score > base_score

    def test_negative_feedback_lowers_score(self):
        """Negative feedback should decrease the score below base."""
        store = RankingFeedbackStore()
        for _ in range(20):
            store.record(FeedbackRecord(
                item_type="billing", source="billing",
                kept=True, referenced=False, user_accepted=False,
                positive_outcome=False,
            ))
        adaptive = AdaptiveContextRankingLayer(feedback_store=store)
        base = ContextRankingLayer()

        item = ContextItem(type=ContextItemType.BILLING, title="B", content="x")
        adaptive_score = adaptive.score_item(item)
        base_score = base.score_item(item)
        assert adaptive_score < base_score

    def test_score_clamped_to_unit_interval(self):
        """Even with large adjustments, score should stay in [0, 1]."""
        store = RankingFeedbackStore(learning_rate=1.0)
        for _ in range(100):
            store.record(FeedbackRecord(
                item_type="brand_info", source="base",
                kept=True, referenced=True, user_accepted=True,
                positive_outcome=True,
            ))
        adaptive = AdaptiveContextRankingLayer(feedback_store=store)
        item = ContextItem(type=ContextItemType.BRAND_INFO, title="Brand", content="x")
        score = adaptive.score_item(item)
        assert 0.0 <= score <= 1.0

    def test_rank_with_adaptive_layer(self):
        """Ranking should still work with the adaptive layer."""
        store = RankingFeedbackStore()
        for _ in range(10):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                kept=True, referenced=True, user_accepted=True,
            ))
        adaptive = AdaptiveContextRankingLayer(feedback_store=store, token_budget=10000)
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="K", content="x" * 20,
                        metadata={"similarity_score": 0.8}),
            ContextItem(type=ContextItemType.BILLING, title="B", content="y" * 20),
        ]
        result = adaptive.rank(items)
        assert len(result) == 2
        assert all(i.kept for i in result)


# ─── Full Learning Loop Integration ─────────────────────────────────────────


class TestLearningLoopIntegration:
    def test_full_loop_evaluate_record_adjust(self):
        """Full loop: evaluate → record feedback → adjust weights → next build scores differently."""
        # Step 1: Create items and a fake answer
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="Brand Guidelines",
                        content="Use bold colors and modern typography for all campaigns",
                        metadata={"similarity_score": 0.85}, source="knowledge"),
            ContextItem(type=ContextItemType.COMPETITOR_PROFILE, title="Competitor",
                        content="Competitor X launched a new premium product line",
                        source="marketing_intelligence"),
        ]
        items[0].kept = True
        items[1].kept = True

        answer = "Use bold colors and modern typography for the campaign."

        # Step 2: Evaluate
        evaluation = ContextEvaluator.evaluate(items, answer)
        assert evaluation.items_referenced >= 1

        # Step 3: Record feedback (user accepted, positive outcome)
        store = RankingFeedbackStore()
        store.record_from_evaluation(evaluation, user_accepted=True, positive_outcome=True)

        # Step 4: Create adaptive ranking layer
        adaptive = AdaptiveContextRankingLayer(feedback_store=store)
        base = ContextRankingLayer()

        # Step 5: Knowledge chunks (referenced + positive) should score higher
        k_item = ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="K",
                             content="x", metadata={"similarity_score": 0.85})
        assert adaptive.score_item(k_item) > base.score_item(k_item)

        # Competitor (not referenced) should get a smaller boost than knowledge chunks
        # (both get positive signal from user_accepted, but knowledge gets more for being referenced)
        c_item = ContextItem(type=ContextItemType.COMPETITOR_PROFILE, title="C",
                             content="x")
        k_boost = adaptive.score_item(k_item) - base.score_item(k_item)
        c_boost = adaptive.score_item(c_item) - base.score_item(c_item)
        assert k_boost > c_boost  # Referenced item gets bigger boost

    def test_loop_with_multiple_sessions(self):
        """Multiple rounds of feedback should compound the adjustment."""
        store = RankingFeedbackStore()

        # Simulate 5 sessions, all positive for knowledge chunks
        for _ in range(5):
            items = [
                ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="K",
                            content="Use bold colors and modern typography",
                            metadata={"similarity_score": 0.85}, source="knowledge"),
            ]
            items[0].kept = True
            answer = "Use bold colors and modern typography."
            ev = ContextEvaluator.evaluate(items, answer)
            store.record_from_evaluation(ev, user_accepted=True, positive_outcome=True)

        # After 5 sessions, adjustment should be positive
        adjustments = store.compute_type_adjustments()
        assert adjustments["knowledge_chunk"].adjustment > 0
        assert adjustments["knowledge_chunk"].samples == 5


# ─── Granular Feedback (Source + Chunk Level) ──────────────────────────────


class TestGranularFeedback:
    def test_source_level_adjustment_positive(self):
        """Positive feedback for a specific source should produce positive adjustment."""
        store = RankingFeedbackStore()
        for _ in range(20):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                source_title="Brand Guidelines",
                kept=True, referenced=True, user_accepted=True,
                positive_outcome=True,
            ))
        adjustments = store.compute_source_adjustments()
        assert len(adjustments) == 1
        adj = list(adjustments.values())[0]
        assert adj.source_title == "Brand Guidelines"
        assert adj.adjustment > 0

    def test_source_level_adjustment_negative(self):
        """Negative feedback for a specific source should produce negative adjustment."""
        store = RankingFeedbackStore()
        for _ in range(20):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                source_title="Campaign Archive",
                kept=True, referenced=False, user_accepted=False,
                positive_outcome=False,
            ))
        adjustments = store.compute_source_adjustments()
        adj = list(adjustments.values())[0]
        assert adj.adjustment < 0

    def test_different_sources_same_type_different_adjustments(self):
        """Two sources of the same type should get different adjustments."""
        store = RankingFeedbackStore()
        # Brand Guidelines: positive
        for _ in range(20):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                source_title="Brand Guidelines",
                kept=True, referenced=True, user_accepted=True,
            ))
        # Campaign Archive: negative
        for _ in range(20):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                source_title="Campaign Archive",
                kept=True, referenced=False, user_accepted=False,
            ))
        adjustments = store.compute_source_adjustments()
        bg_adj = next(a for a in adjustments.values() if a.source_title == "Brand Guidelines")
        ca_adj = next(a for a in adjustments.values() if a.source_title == "Campaign Archive")
        assert bg_adj.adjustment > 0
        assert ca_adj.adjustment < 0
        assert bg_adj.adjustment > ca_adj.adjustment

    def test_chunk_level_adjustment(self):
        """Chunk-level feedback should produce chunk-specific adjustments."""
        store = RankingFeedbackStore()
        for _ in range(10):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                source_title="Brand Guidelines", chunk_id="chunk_abc123",
                kept=True, referenced=True, user_accepted=True,
            ))
        adjustments = store.compute_chunk_adjustments()
        assert "chunk_abc123" in adjustments
        assert adjustments["chunk_abc123"].adjustment > 0

    def test_combined_adjustment_type_plus_source_plus_chunk(self):
        """Combined adjustment should include all three levels."""
        store = RankingFeedbackStore()
        for _ in range(20):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                source_title="Brand Guidelines", chunk_id="chunk_001",
                kept=True, referenced=True, user_accepted=True,
                positive_outcome=True,
            ))

        item = ContextItem(
            type=ContextItemType.KNOWLEDGE_CHUNK,
            title="Brand Guidelines",
            content="x",
            metadata={"chunk_id": "chunk_001"},
        )
        combined = store.get_adjustment(item)
        type_adj = store.get_type_adjustment(ContextItemType.KNOWLEDGE_CHUNK)
        source_adj = store.get_source_adjustment("Brand Guidelines", ContextItemType.KNOWLEDGE_CHUNK)
        chunk_adj = store.get_chunk_adjustment("chunk_001")

        # Combined should be approximately type + source + chunk
        assert combined == pytest.approx(type_adj + source_adj + chunk_adj, abs=0.001)
        assert combined > 0

    def test_combined_adjustment_no_chunk_id(self):
        """Items without chunk_id should still get type + source adjustments."""
        store = RankingFeedbackStore()
        for _ in range(20):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                source_title="Brand Guidelines",
                kept=True, referenced=True, user_accepted=True,
            ))
        item = ContextItem(
            type=ContextItemType.KNOWLEDGE_CHUNK,
            title="Brand Guidelines",
            content="x",
        )
        combined = store.get_adjustment(item)
        assert combined > 0  # Should still get type + source

    def test_combined_adjustment_no_source_title(self):
        """Items without title should only get type adjustment."""
        store = RankingFeedbackStore()
        for _ in range(20):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                kept=True, referenced=True, user_accepted=True,
            ))
        item = ContextItem(
            type=ContextItemType.KNOWLEDGE_CHUNK,
            title="",
            content="x",
        )
        combined = store.get_adjustment(item)
        type_adj = store.get_type_adjustment(ContextItemType.KNOWLEDGE_CHUNK)
        assert combined == pytest.approx(type_adj, abs=0.001)

    def test_source_adjustment_clamped(self):
        """Source adjustments should be clamped."""
        store = RankingFeedbackStore(learning_rate=1.0)
        for _ in range(100):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                source_title="Brand Guidelines",
                kept=True, referenced=True, user_accepted=True,
                positive_outcome=True,
            ))
        adjustments = store.compute_source_adjustments()
        for adj in adjustments.values():
            assert -0.15 <= adj.adjustment <= 0.15

    def test_chunk_adjustment_clamped(self):
        """Chunk adjustments should be clamped."""
        store = RankingFeedbackStore(learning_rate=1.0)
        for _ in range(100):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                source_title="X", chunk_id="c1",
                kept=True, referenced=True, user_accepted=True,
                positive_outcome=True,
            ))
        adjustments = store.compute_chunk_adjustments()
        for adj in adjustments.values():
            assert -0.10 <= adj.adjustment <= 0.10

    def test_no_source_adjustment_without_source_title(self):
        """Records without source_title should not produce source adjustments."""
        store = RankingFeedbackStore()
        for _ in range(10):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                kept=True, referenced=True,
            ))
        assert store.compute_source_adjustments() == {}

    def test_no_chunk_adjustment_without_chunk_id(self):
        """Records without chunk_id should not produce chunk adjustments."""
        store = RankingFeedbackStore()
        for _ in range(10):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                source_title="X",
                kept=True, referenced=True,
            ))
        assert store.compute_chunk_adjustments() == {}

    def test_stats_include_granular_counts(self):
        """Stats should include source and chunk tracking counts."""
        store = RankingFeedbackStore()
        for _ in range(5):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                source_title="Brand Guidelines", chunk_id="c1",
                kept=True, referenced=True,
            ))
        stats = store.stats()
        assert "sources_tracked" in stats
        assert "chunks_tracked" in stats
        assert stats["sources_tracked"] == 1
        assert stats["chunks_tracked"] == 1


# ─── Offline Training ───────────────────────────────────────────────────────


class TestOfflineTraining:
    def test_run_offline_training_returns_model(self):
        """Offline training should return an OfflineModelVersion."""
        store = RankingFeedbackStore()
        for _ in range(20):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                source_title="Brand Guidelines",
                kept=True, referenced=True, user_accepted=True,
            ))
        model = store.run_offline_training(version="v1.0")
        assert isinstance(model, OfflineModelVersion)
        assert model.version == "v1.0"
        assert model.training_samples > 0

    def test_offline_model_has_scoring_weights(self):
        """Offline model should include scoring weights."""
        store = RankingFeedbackStore()
        for _ in range(20):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                kept=True, referenced=True, user_accepted=True,
            ))
        model = store.run_offline_training()
        assert isinstance(model.scoring_weights, ScoringWeights)
        # Weights should sum to approximately 1.0
        w = model.scoring_weights
        total = w.type_base + w.semantic + w.recency + w.confidence + w.intent
        assert 0.9 <= total <= 1.1

    def test_offline_model_has_base_score_overrides(self):
        """Offline model should include base score overrides."""
        store = RankingFeedbackStore()
        for _ in range(20):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                kept=True, referenced=True, user_accepted=True,
                positive_outcome=True,
            ))
        model = store.run_offline_training()
        assert len(model.base_score_overrides) > 0
        assert "knowledge_chunk" in model.base_score_overrides

    def test_offline_model_has_adjustments(self):
        """Offline model should include type, source, and chunk adjustments."""
        store = RankingFeedbackStore()
        for _ in range(20):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                source_title="Brand Guidelines", chunk_id="c1",
                kept=True, referenced=True, user_accepted=True,
            ))
        model = store.run_offline_training()
        assert len(model.type_adjustments) > 0
        assert len(model.source_adjustments) > 0
        assert len(model.chunk_adjustments) > 0

    def test_offline_resets_interaction_counter(self):
        """Offline training should reset the interaction counter."""
        store = RankingFeedbackStore()
        for _ in range(20):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                kept=True, referenced=True,
            ))
        assert store._interactions_since_offline == 20
        store.run_offline_training()
        assert store._interactions_since_offline == 0

    def test_should_run_offline(self):
        """should_run_offline should return True when threshold is met."""
        store = RankingFeedbackStore()
        for _ in range(15):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                kept=True, referenced=True,
            ))
        assert store.should_run_offline(threshold=10) is True
        assert store.should_run_offline(threshold=20) is False

    def test_get_offline_model_none_initially(self):
        """get_offline_model should return None before any training."""
        store = RankingFeedbackStore()
        assert store.get_offline_model() is None

    def test_get_offline_model_after_training(self):
        """get_offline_model should return the model after training."""
        store = RankingFeedbackStore()
        for _ in range(10):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                kept=True, referenced=True,
            ))
        model = store.run_offline_training()
        assert store.get_offline_model() is model

    def test_offline_model_to_dict(self):
        """Offline model should serialise to dict."""
        store = RankingFeedbackStore()
        for _ in range(10):
            store.record(FeedbackRecord(
                item_type="knowledge_chunk", source="knowledge",
                source_title="X", chunk_id="c1",
                kept=True, referenced=True,
            ))
        model = store.run_offline_training()
        d = model.to_dict()
        assert "version" in d
        assert "scoring_weights" in d
        assert "base_score_overrides" in d
        assert "type_adjustments" in d

    def test_scoring_weights_normalised(self):
        """ScoringWeights.normalised() should sum to 1.0."""
        w = ScoringWeights(type_base=0.6, semantic=0.3, recency=0.2, confidence=0.1, intent=0.1)
        normalised = w.normalised()
        total = normalised.type_base + normalised.semantic + normalised.recency + normalised.confidence + normalised.intent
        assert total == pytest.approx(1.0, abs=0.001)


class TestAdaptiveRankingWithOfflineModel:
    def test_apply_offline_model(self):
        """Applying an offline model should update scoring weights."""
        store = RankingFeedbackStore()
        layer = AdaptiveContextRankingLayer(feedback_store=store)

        # Default weights
        assert layer._scoring_weights.type_base == 0.50

        # Apply offline model with custom weights
        model = OfflineModelVersion(
            version="v1.0",
            scoring_weights=ScoringWeights(type_base=0.40, semantic=0.30),
            base_score_overrides={"knowledge_chunk": 0.85},
        )
        layer.apply_offline_model(model)

        assert layer._scoring_weights.type_base == 0.40
        assert layer._scoring_weights.semantic == 0.30
        assert layer._base_score_overrides["knowledge_chunk"] == 0.85

    def test_score_item_with_offline_weights(self):
        """Score should use offline-trained weights when applied."""
        store = RankingFeedbackStore()
        layer_default = AdaptiveContextRankingLayer(feedback_store=store)
        layer_offline = AdaptiveContextRankingLayer(feedback_store=store)

        # Apply offline model with higher semantic weight
        model = OfflineModelVersion(
            version="v1.0",
            scoring_weights=ScoringWeights(type_base=0.30, semantic=0.40, recency=0.15, confidence=0.10, intent=0.05),
        )
        layer_offline.apply_offline_model(model)

        # Item with high semantic score
        item = ContextItem(
            type=ContextItemType.KNOWLEDGE_CHUNK,
            title="K",
            content="x",
            metadata={"similarity_score": 0.95},
        )
        score_default = layer_default.score_item(item)
        score_offline = layer_offline.score_item(item)

        # With higher semantic weight, the high-similarity item should score higher
        assert score_offline > score_default

    def test_score_item_with_base_score_override(self):
        """Score should use overridden base score when available."""
        store = RankingFeedbackStore()
        layer = AdaptiveContextRankingLayer(feedback_store=store)

        model = OfflineModelVersion(
            version="v1.0",
            base_score_overrides={"knowledge_chunk": 0.95},  # Higher than default 0.70
        )
        layer.apply_offline_model(model)

        item = ContextItem(
            type=ContextItemType.KNOWLEDGE_CHUNK,
            title="K",
            content="x",
            metadata={"similarity_score": 0.5},
        )
        score = layer.score_item(item)
        # Should be higher than with default base score (0.70)
        layer_no_override = AdaptiveContextRankingLayer(feedback_store=store)
        score_no_override = layer_no_override.score_item(item)
        assert score > score_no_override


# ─── Retrieval Quality Metrics ──────────────────────────────────────────────


class TestRetrievalQuality:
    def test_retrieval_quality_defaults(self):
        rq = RetrievalQuality()
        assert rq.recall == 0.0
        assert rq.precision == 0.0
        assert rq.duplicate_count == 0

    def test_retrieval_quality_to_dict(self):
        rq = RetrievalQuality(recall=0.8, precision=0.6, novelty=0.7, duplicate_count=2)
        d = rq.to_dict()
        assert d["recall"] == 0.8
        assert d["precision"] == 0.6
        assert d["novelty"] == 0.7
        assert d["duplicate_count"] == 2

    def test_retrieval_quality_format_for_display(self):
        rq = RetrievalQuality(recall=0.82, precision=0.67, novelty=0.71)
        text = rq.format_for_display()
        assert "Retrieval Quality" in text
        assert "Recall" in text
        assert "0.82" in text

    def test_evaluation_includes_retrieval_quality(self):
        """ContextEvaluation should include retrieval quality."""
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="K",
                        content="Use bold colors and modern typography",
                        metadata={"similarity_score": 0.9}),
        ]
        items[0].kept = True
        ev = ContextEvaluator.evaluate(items, "Use bold colors.")
        assert ev.retrieval_quality is not None
        assert isinstance(ev.retrieval_quality, RetrievalQuality)

    def test_recall_all_referenced(self):
        """If all kept items are referenced, recall should be 1.0."""
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="A",
                        content="Use bold colors and modern typography",
                        metadata={"similarity_score": 0.9}),
        ]
        items[0].kept = True
        ev = ContextEvaluator.evaluate(items, "Use bold colors and modern typography.")
        assert ev.retrieval_quality.recall == 1.0

    def test_recall_none_referenced(self):
        """If no kept items are referenced, recall should be 0.0."""
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="A",
                        content="Completely different content about pricing",
                        metadata={"similarity_score": 0.9}),
        ]
        items[0].kept = True
        ev = ContextEvaluator.evaluate(items, "Let's talk about social media.")
        assert ev.retrieval_quality.recall == 0.0

    def test_precision(self):
        """Precision = kept / total."""
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="A", content="x" * 20,
                        metadata={"similarity_score": 0.9}),
            ContextItem(type=ContextItemType.BILLING, title="B", content="y" * 20),
        ]
        items[0].kept = True
        items[1].kept = False
        ev = ContextEvaluator.evaluate(items, "answer")
        assert ev.retrieval_quality.precision == 0.5

    def test_novelty_single_chunk(self):
        """Single chunk should have novelty = 1.0 (fully novel)."""
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="A",
                        content="Unique content here about branding",
                        metadata={"similarity_score": 0.9}),
        ]
        items[0].kept = True
        ev = ContextEvaluator.evaluate(items, "answer")
        assert ev.retrieval_quality.novelty == 1.0

    def test_novelty_duplicate_chunks(self):
        """Duplicate chunks should have low novelty."""
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="A",
                        content="Use bold colors and modern typography for campaigns",
                        metadata={"similarity_score": 0.9}),
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="B",
                        content="Use bold colors and modern typography for campaigns",
                        metadata={"similarity_score": 0.85}),
        ]
        items[0].kept = True
        items[1].kept = True
        ev = ContextEvaluator.evaluate(items, "answer")
        assert ev.retrieval_quality.novelty < 0.5  # Low novelty (duplicates)
        assert ev.retrieval_quality.duplicate_count >= 1

    def test_novelty_distinct_chunks(self):
        """Distinct chunks should have high novelty."""
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="A",
                        content="Premium pricing strategy for enterprise customers",
                        metadata={"similarity_score": 0.9}),
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="B",
                        content="Social media calendar planning for next quarter",
                        metadata={"similarity_score": 0.85}),
        ]
        items[0].kept = True
        items[1].kept = True
        ev = ContextEvaluator.evaluate(items, "answer")
        assert ev.retrieval_quality.novelty > 0.7  # High novelty (distinct)

    def test_duplicate_count(self):
        """Duplicate chunks should be counted."""
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="A",
                        content="Use bold colors and modern typography for campaigns",
                        metadata={"similarity_score": 0.9}),
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="B",
                        content="Use bold colors and modern typography for campaigns",
                        metadata={"similarity_score": 0.85}),
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="C",
                        content="Premium pricing strategy for enterprise customers",
                        metadata={"similarity_score": 0.8}),
        ]
        for i in items:
            i.kept = True
        ev = ContextEvaluator.evaluate(items, "answer")
        assert ev.retrieval_quality.duplicate_count >= 1

    def test_chunk_diversity(self):
        """Chunk diversity should be > 0 for diverse chunks."""
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="A",
                        content="Premium pricing strategy for enterprise customers",
                        metadata={"similarity_score": 0.9}),
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="B",
                        content="Social media calendar planning for next quarter",
                        metadata={"similarity_score": 0.85}),
        ]
        for i in items:
            i.kept = True
        ev = ContextEvaluator.evaluate(items, "answer")
        assert ev.retrieval_quality.chunk_diversity > 0.3

    def test_chunk_diversity_low_for_duplicates(self):
        """Chunk diversity should be low for duplicate chunks."""
        content = "Use bold colors and modern typography for campaigns"
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="A",
                        content=content, metadata={"similarity_score": 0.9}),
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="B",
                        content=content, metadata={"similarity_score": 0.85}),
        ]
        for i in items:
            i.kept = True
        ev = ContextEvaluator.evaluate(items, "answer")
        assert ev.retrieval_quality.chunk_diversity <= 0.5

    def test_provider_diversity(self):
        """Provider diversity should count distinct providers."""
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="A",
                        content="x" * 20, source="knowledge",
                        metadata={"similarity_score": 0.9}),
            ContextItem(type=ContextItemType.BUSINESS_PROFILE, title="B",
                        content="y" * 20, source="marketing_intelligence"),
            ContextItem(type=ContextItemType.COUNCIL_DECISION, title="C",
                        content="z" * 20, source="council_memory"),
        ]
        for i in items:
            i.kept = True
        ev = ContextEvaluator.evaluate(items, "answer")
        assert ev.retrieval_quality.provider_diversity == 3

    def test_provider_diversity_single_provider(self):
        """Provider diversity should be 1 when all items from same provider."""
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="A",
                        content="x" * 20, source="knowledge",
                        metadata={"similarity_score": 0.9}),
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="B",
                        content="y" * 20, source="knowledge",
                        metadata={"similarity_score": 0.8}),
        ]
        for i in items:
            i.kept = True
        ev = ContextEvaluator.evaluate(items, "answer")
        assert ev.retrieval_quality.provider_diversity == 1

    def test_retrieval_quality_in_evaluation_to_dict(self):
        """Retrieval quality should be included in evaluation.to_dict()."""
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="A",
                        content="x" * 20, source="knowledge",
                        metadata={"similarity_score": 0.9}),
        ]
        items[0].kept = True
        ev = ContextEvaluator.evaluate(items, "answer")
        d = ev.to_dict()
        assert "retrieval_quality" in d
        assert "recall" in d["retrieval_quality"]
        assert "precision" in d["retrieval_quality"]
        assert "novelty" in d["retrieval_quality"]

    def test_retrieval_quality_in_format_for_display(self):
        """Retrieval quality should appear in format_for_display()."""
        items = [
            ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="A",
                        content="x" * 20, source="knowledge",
                        metadata={"similarity_score": 0.9}),
        ]
        items[0].kept = True
        ev = ContextEvaluator.evaluate(items, "answer")
        text = ev.format_for_display()
        assert "Retrieval Quality" in text
        assert "Recall" in text
        assert "Precision" in text


# ─── Full Granular Learning Loop Integration ────────────────────────────────


class TestGranularLearningLoop:
    def test_granular_loop_discovers_valuable_sources(self):
        """The system should discover that some sources are more valuable than others."""
        store = RankingFeedbackStore()

        # Simulate 10 sessions where Brand Guidelines is always referenced
        # and Campaign Archive is never referenced
        for _ in range(10):
            items = [
                ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="Brand Guidelines",
                            content="Use bold colors and modern typography for campaigns",
                            metadata={"similarity_score": 0.85, "chunk_id": "bg_001"},
                            source="knowledge"),
                ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="Campaign Archive",
                            content="Previous campaign results and metrics from last quarter",
                            metadata={"similarity_score": 0.80, "chunk_id": "ca_001"},
                            source="knowledge"),
            ]
            for i in items:
                i.kept = True
            answer = "Use bold colors and modern typography for the new campaign."
            ev = ContextEvaluator.evaluate(items, answer)
            store.record_from_evaluation(ev, user_accepted=True, positive_outcome=True)

        # Source-level adjustments should differ
        source_adjs = store.compute_source_adjustments()
        bg_adj = next(a for a in source_adjs.values() if a.source_title == "Brand Guidelines")
        ca_adj = next(a for a in source_adjs.values() if a.source_title == "Campaign Archive")

        # Brand Guidelines (referenced) should get positive adjustment
        assert bg_adj.adjustment > 0
        # Campaign Archive (not referenced) should get lower adjustment
        assert ca_adj.adjustment < bg_adj.adjustment

        # Adaptive ranking should score Brand Guidelines higher
        adaptive = AdaptiveContextRankingLayer(feedback_store=store)
        bg_item = ContextItem(
            type=ContextItemType.KNOWLEDGE_CHUNK, title="Brand Guidelines",
            content="x", metadata={"similarity_score": 0.85, "chunk_id": "bg_001"},
        )
        ca_item = ContextItem(
            type=ContextItemType.KNOWLEDGE_CHUNK, title="Campaign Archive",
            content="x", metadata={"similarity_score": 0.85, "chunk_id": "ca_001"},
        )
        assert adaptive.score_item(bg_item) > adaptive.score_item(ca_item)

    def test_offline_training_improves_ranking(self):
        """Offline training should produce weights that improve ranking."""
        store = RankingFeedbackStore()

        # Simulate sessions where high-semantic items are more often referenced
        for _ in range(30):
            items = [
                ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="High Sim",
                            content="Premium pricing strategy for enterprise customers",
                            metadata={"similarity_score": 0.95, "chunk_id": "h1"},
                            source="knowledge"),
                ContextItem(type=ContextItemType.KNOWLEDGE_CHUNK, title="Low Sim",
                            content="General marketing tips and best practices guide",
                            metadata={"similarity_score": 0.50, "chunk_id": "l1"},
                            source="knowledge"),
            ]
            for i in items:
                i.kept = True
            answer = "Premium pricing strategy for enterprise customers."
            ev = ContextEvaluator.evaluate(items, answer)
            store.record_from_evaluation(ev, user_accepted=True, positive_outcome=True)

        # Run offline training
        model = store.run_offline_training()
        assert model.training_samples == 60  # 30 sessions × 2 items

        # Apply to adaptive layer
        adaptive = AdaptiveContextRankingLayer(feedback_store=store)
        adaptive.apply_offline_model(model)

        # High-similarity item should still score higher
        high_item = ContextItem(
            type=ContextItemType.KNOWLEDGE_CHUNK, title="High Sim",
            content="x", metadata={"similarity_score": 0.95, "chunk_id": "h1"},
        )
        low_item = ContextItem(
            type=ContextItemType.KNOWLEDGE_CHUNK, title="Low Sim",
            content="x", metadata={"similarity_score": 0.50, "chunk_id": "l1"},
        )
        assert adaptive.score_item(high_item) > adaptive.score_item(low_item)
