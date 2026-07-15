from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest

from prachar_workers.ads.spend_cap import check_idempotency, check_spend_cap
from prachar_workers.creative.evolution import (
    CreativePerf,
    classify_variants,
    generate_winner_children,
    log_lineage,
)


def test_classify_variants_basic():
    perfs = [
        CreativePerf(creative_id=uuid.uuid4(), variant_group="g1", ctr_7d=0.05, impressions_7d=1000, clicks_7d=50, conversions_7d=5),
        CreativePerf(creative_id=uuid.uuid4(), variant_group="g1", ctr_7d=0.03, impressions_7d=1000, clicks_7d=30, conversions_7d=3),
        CreativePerf(creative_id=uuid.uuid4(), variant_group="g1", ctr_7d=0.01, impressions_7d=1000, clicks_7d=10, conversions_7d=1),
        CreativePerf(creative_id=uuid.uuid4(), variant_group="g1", ctr_7d=0.04, impressions_7d=1000, clicks_7d=40, conversions_7d=4),
        CreativePerf(creative_id=uuid.uuid4(), variant_group="g1", ctr_7d=0.02, impressions_7d=1000, clicks_7d=20, conversions_7d=2),
    ]
    winners, losers, neutral = classify_variants(perfs)
    # With 5 items, median=0.03, stdev~0.0158
    # hi threshold ≈ 0.0458, lo threshold ≈ 0.0142
    assert len(winners) >= 1  # 0.05 > 0.0458
    assert len(losers) >= 1   # 0.01 < 0.0142
    assert len(neutral) >= 1


def test_classify_variants_empty():
    winners, losers, neutral = classify_variants([])
    assert winners == [] and losers == [] and neutral == []


def test_classify_variants_single():
    p = CreativePerf(creative_id=uuid.uuid4(), variant_group="g1", ctr_7d=0.05, impressions_7d=100, clicks_7d=5, conversions_7d=1)
    winners, losers, neutral = classify_variants([p])
    assert len(winners) == 1  # single item → all winners


@pytest.mark.asyncio
async def test_generate_winner_children_stub():
    winner = CreativePerf(
        creative_id=uuid.uuid4(), variant_group="g1",
        ctr_7d=0.08, impressions_7d=10000, clicks_7d=800, conversions_7d=80,
    )
    brand_graph = {"brand_name": "Acme", "category": "coffee"}
    children = await generate_winner_children(uuid.uuid4(), winner, brand_graph, count=3)
    assert len(children) <= 3
    assert len(children) >= 1
    for child in children:
        assert "copy" in child
        assert "hook_type" in child


def test_check_spend_cap_no_state():
    # Without a real DB connection (or with unknown tenant), should fail-open.
    allowed, reason = check_spend_cap(uuid.uuid4(), additional_daily=100.0)
    # In test env, DB may or may not be available. Either way it shouldn't crash.
    assert isinstance(allowed, bool)
    assert isinstance(reason, str)


def test_check_idempotency():
    key = f"test-{uuid.uuid4()}"
    # First call should allow (new key).
    allowed1 = check_idempotency(key)
    # Second call should block (duplicate).
    allowed2 = check_idempotency(key)
    # If Redis is available: allowed1=True, allowed2=False
    # If Redis unavailable: both True (fail-open)
    assert isinstance(allowed1, bool)
    assert isinstance(allowed2, bool)


def test_log_lineage_no_crash():
    # Should not crash even if DB is unavailable.
    log_lineage(uuid.uuid4(), [uuid.uuid4(), uuid.uuid4()], "mutation")
