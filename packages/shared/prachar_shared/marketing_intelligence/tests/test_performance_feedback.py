"""Tests for the Performance Feedback Loop (P4.6).

Verifies that:
  1. ``CampaignBrain.generate_campaign`` includes past performance in the
     generation context when performance learnings are available.
  2. Performance learnings are stored and retrieved via
     ``BusinessMemoryStore.store_performance_learning`` /
     ``get_performance_learnings``.
  3. The feedback loop is graceful when there is no past data — campaign
     generation proceeds normally.

The DB session and PerformanceEngine are mocked; the AI gateway is stubbed
so no real LLM calls are made.

Run with:
    .venv/bin/python -m pytest \
        packages/shared/prachar_shared/marketing_intelligence/tests/test_performance_feedback.py -q
"""
from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from prachar_shared.marketing_intelligence.brain import CampaignBrain
from prachar_shared.marketing_intelligence.memory import (
    BusinessMemory,
    BusinessMemoryStore,
)
from prachar_shared.marketing_intelligence.repository import InMemoryRepository


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _learning(
    campaign_id: str,
    *,
    roas: float = 3.0,
    ctr: float = 0.02,
    hook: str = "emotional hooks",
    insight: str = "Emotion drives conversions",
    summary: str = "Strong performance",
) -> dict[str, Any]:
    return {
        "campaign_id": campaign_id,
        "summary": summary,
        "top_performing_hook": hook,
        "roas": roas,
        "ctr": ctr,
        "key_insight": insight,
    }


def _stub_gateway() -> MagicMock:
    """A stub AIGateway whose complete() returns minimal valid JSON.

    Each engine parses the JSON payload; we return empty dicts/lists which
    the engines tolerate (they default missing keys). This avoids needing
    real API keys while still exercising the full pipeline.
    """
    gw = MagicMock()
    from prachar_shared.ai_gateway import Completion

    completion = Completion(
        text="{}",
        model="stub",
        provider="stub",
        tokens_used=0,
        cost_usd=0.0,
        latency_ms=1.0,
    )
    gw.complete = MagicMock(return_value=completion)
    gw.extract_json = MagicMock(return_value={})
    return gw


def _brain_with_memory(repo: InMemoryRepository) -> CampaignBrain:
    """Build a CampaignBrain backed by an in-memory repository."""
    store = BusinessMemoryStore(repository=repo)
    return CampaignBrain(gateway=_stub_gateway(), memory_store=store)


# ─── BusinessMemoryStore: store / retrieve performance learnings ──────────────


@pytest.mark.asyncio
async def test_store_and_retrieve_performance_learning():
    repo = InMemoryRepository()
    store = BusinessMemoryStore(repository=repo)
    tenant = uuid.uuid4()
    brand = uuid.uuid4()

    await store.store_performance_learning(
        tenant, brand, "camp-1", _learning("camp-1", roas=3.0, hook="emotional hooks")
    )
    await store.store_performance_learning(
        tenant, brand, "camp-2", _learning("camp-2", roas=1.5, hook="discount offers")
    )

    learnings = await store.get_performance_learnings(tenant, brand, limit=5)
    assert len(learnings) == 2
    # Most-recent first → camp-2 then camp-1
    assert learnings[0]["campaign_id"] == "camp-2"
    assert learnings[1]["campaign_id"] == "camp-1"
    assert learnings[0]["roas"] == 1.5


@pytest.mark.asyncio
async def test_get_performance_learnings_respects_limit():
    repo = InMemoryRepository()
    store = BusinessMemoryStore(repository=repo)
    tenant = uuid.uuid4()
    brand = uuid.uuid4()

    for i in range(6):
        await store.store_performance_learning(
            tenant, brand, f"camp-{i}", _learning(f"camp-{i}")
        )

    learnings = await store.get_performance_learnings(tenant, brand, limit=3)
    assert len(learnings) == 3
    # Most recent three: camp-5, camp-4, camp-3
    assert [lg["campaign_id"] for lg in learnings] == ["camp-5", "camp-4", "camp-3"]


@pytest.mark.asyncio
async def test_get_performance_learnings_empty_when_none():
    repo = InMemoryRepository()
    store = BusinessMemoryStore(repository=repo)

    learnings = await store.get_performance_learnings(uuid.uuid4(), uuid.uuid4())
    assert learnings == []


@pytest.mark.asyncio
async def test_store_performance_learning_sets_campaign_id():
    repo = InMemoryRepository()
    store = BusinessMemoryStore(repository=repo)
    tenant = uuid.uuid4()
    brand = uuid.uuid4()

    # learning dict without campaign_id — should be filled from arg
    partial = {"roas": 2.0, "summary": "ok"}
    await store.store_performance_learning(tenant, brand, "camp-x", partial)

    learnings = await store.get_performance_learnings(tenant, brand)
    assert learnings[0]["campaign_id"] == "camp-x"


def test_to_performance_context_formats_concisely():
    learnings = [
        _learning("a", roas=3.0, hook="emotional hooks", insight="Emotion wins"),
        _learning("b", roas=1.5, hook="discount offers", insight=""),
    ]
    ctx = BusinessMemoryStore.to_performance_context(learnings)
    assert "Past campaign performance:" in ctx
    assert "3.0x ROAS" in ctx
    assert "1.5x ROAS" in ctx
    assert "emotional hooks" in ctx
    assert "discount offers" in ctx
    assert "Learn from this." in ctx
    assert "Emotion wins" in ctx


def test_to_performance_context_empty_returns_empty_string():
    assert BusinessMemoryStore.to_performance_context([]) == ""


# ─── CampaignBrain feedback loop ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_campaign_includes_past_performance_in_context(monkeypatch):
    """When past learnings exist, the performance context is injected into
    the additional_context passed to every engine."""
    repo = InMemoryRepository()
    tenant = uuid.uuid4()
    brand = uuid.uuid4()

    # Pre-seed two performance learnings for the brand.
    store = BusinessMemoryStore(repository=repo)
    await store.store_performance_learning(
        tenant, brand, "camp-a", _learning("camp-a", roas=3.0, hook="emotional hooks")
    )
    await store.store_performance_learning(
        tenant, brand, "camp-b", _learning("camp-b", roas=1.5, hook="discount offers")
    )

    brain = _brain_with_memory(repo)

    # Capture the additional_context passed to the business engine so we can
    # assert the performance context was merged in.
    captured: list[str] = []
    original_run = brain.business_engine.run

    def _spy_run(*, tenant_id, plan, **kw):
        captured.append(kw.get("additional_context", ""))
        return original_run(tenant_id=tenant_id, plan=plan, **kw)

    brain.business_engine.run = _spy_run  # type: ignore[assignment]

    await brain.generate_campaign(
        tenant_id=tenant,
        plan="starter",
        business_name="Acme",
        goal="increase sales",
        brand_id=brand,
    )

    assert captured, "business engine should have been called"
    ctx = captured[0]
    assert "PAST CAMPAIGN PERFORMANCE" in ctx
    assert "Past campaign performance:" in ctx
    assert "3.0x ROAS" in ctx
    assert "1.5x ROAS" in ctx
    assert "emotional hooks" in ctx
    assert "discount offers" in ctx
    assert "Learn from this." in ctx


@pytest.mark.asyncio
async def test_generate_campaign_graceful_with_no_past_data():
    """With no past performance data, generation proceeds and no
    performance context block is added."""
    repo = InMemoryRepository()
    tenant = uuid.uuid4()
    brand = uuid.uuid4()

    brain = _brain_with_memory(repo)

    captured: list[str] = []
    original_run = brain.business_engine.run

    def _spy_run(*, tenant_id, plan, **kw):
        captured.append(kw.get("additional_context", ""))
        return original_run(tenant_id=tenant_id, plan=plan, **kw)

    brain.business_engine.run = _spy_run  # type: ignore[assignment]

    campaign = await brain.generate_campaign(
        tenant_id=tenant,
        plan="starter",
        business_name="Acme",
        goal="increase sales",
        brand_id=brand,
    )

    assert campaign is not None
    assert captured, "business engine should have been called"
    ctx = captured[0]
    assert "PAST CAMPAIGN PERFORMANCE" not in ctx
    assert "Past campaign performance:" not in ctx


@pytest.mark.asyncio
async def test_generate_campaign_graceful_without_brand_id():
    """When brand_id is None, no performance lookup is attempted and
    generation still works."""
    repo = InMemoryRepository()
    tenant = uuid.uuid4()

    brain = _brain_with_memory(repo)
    campaign = await brain.generate_campaign(
        tenant_id=tenant,
        plan="starter",
        business_name="Acme",
        goal="grow",
        brand_id=None,
    )
    assert campaign is not None


@pytest.mark.asyncio
async def test_learn_from_campaign_stores_performance_learning():
    """learn_from_campaign should persist a performance learning that a
    subsequent generate_campaign can pick up."""
    repo = InMemoryRepository()
    tenant = uuid.uuid4()
    brand = uuid.uuid4()

    brain = _brain_with_memory(repo)

    campaign_plan = {"id": "camp-learn", "name": "Learned Campaign"}
    performance_data = {
        "roas": 4.2,
        "ctr": 0.03,
        "top_performing_hook": "storytelling",
        "summary": "Great campaign",
    }

    await brain.learn_from_campaign(
        tenant_id=tenant,
        brand_id=brand,
        campaign_plan=campaign_plan,
        performance_data=performance_data,
        plan="starter",
    )

    store = BusinessMemoryStore(repository=repo)
    learnings = await store.get_performance_learnings(tenant, brand)
    assert len(learnings) == 1
    lg = learnings[0]
    assert lg["campaign_id"] == "camp-learn"
    assert lg["roas"] == 4.2
    assert lg["top_performing_hook"] == "storytelling"


@pytest.mark.asyncio
async def test_full_feedback_loop_learn_then_generate():
    """End-to-end: store a learning via learn(), then generate_campaign()
    picks it up and injects it into the context."""
    repo = InMemoryRepository()
    tenant = uuid.uuid4()
    brand = uuid.uuid4()

    brain = _brain_with_memory(repo)

    # First campaign: learn from it.
    await brain.learn_from_campaign(
        tenant_id=tenant,
        brand_id=brand,
        campaign_plan={"id": "camp-1"},
        performance_data={"roas": 2.5, "top_performing_hook": "urgency"},
        plan="starter",
    )

    # Second campaign generation should include the past performance.
    captured: list[str] = []
    original_run = brain.business_engine.run

    def _spy_run(*, tenant_id, plan, **kw):
        captured.append(kw.get("additional_context", ""))
        return original_run(tenant_id=tenant_id, plan=plan, **kw)

    brain.business_engine.run = _spy_run  # type: ignore[assignment]

    await brain.generate_campaign(
        tenant_id=tenant,
        plan="starter",
        business_name="Acme",
        goal="grow more",
        brand_id=brand,
    )

    assert captured
    ctx = captured[0]
    assert "PAST CAMPAIGN PERFORMANCE" in ctx
    assert "2.5x ROAS" in ctx
    assert "urgency" in ctx


# ─── C.2.1: Live performance data in generate_campaign ───────────────────────


class _FakeLiveSession:
    """Async session that returns pre-seeded campaigns and performance rows
    for the live data context queries."""

    def __init__(
        self,
        campaigns: list[Any] | None = None,
        perf_rows: list[Any] | None = None,
    ) -> None:
        self._campaigns = campaigns or []
        self._perf_rows = perf_rows or []
        from unittest.mock import AsyncMock, MagicMock

        self.execute = AsyncMock(side_effect=self._execute)

    async def _execute(self, stmt: Any) -> Any:
        from unittest.mock import MagicMock

        stmt_str = str(stmt)
        # Campaign ID query: select(Campaign.id) — returns tuples.
        if "campaigns" in stmt_str and "campaign_performance" not in stmt_str:
            return MagicMock(
                all=MagicMock(
                    return_value=[(c["id"],) for c in self._campaigns]
                )
            )
        # CampaignPerformance query — returns scalar rows.
        return MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(all=MagicMock(return_value=self._perf_rows))
            )
        )


def _live_perf_row(
    d, *, channel="instagram", impressions=12_000, clicks=360,
    conversions=15, spend=500.0, revenue=1000.0,
):
    """Build a CampaignPerformance-like row for live data tests."""
    from types import SimpleNamespace

    return SimpleNamespace(
        date=d,
        impressions=impressions,
        clicks=clicks,
        conversions=conversions,
        spend=spend,
        revenue=revenue,
        channel=channel,
    )


@pytest.mark.asyncio
async def test_generate_campaign_includes_live_performance_data_in_context():
    """When live CampaignPerformance data exists, it is injected into the
    additional_context passed to every engine (C.2.1)."""
    from datetime import date, timedelta

    repo = InMemoryRepository()
    tenant = uuid.uuid4()
    brand = uuid.uuid4()

    today = date.today()
    perf_rows = [
        _live_perf_row(today - timedelta(days=1), channel="instagram",
                       impressions=12_000, clicks=360, conversions=15),
        _live_perf_row(today - timedelta(days=2), channel="whatsapp",
                       impressions=0, clicks=50, conversions=6),
        _live_perf_row(today - timedelta(days=3), channel="google_ads",
                       impressions=8_000, clicks=160, conversions=4,
                       spend=5000.0, revenue=10000.0),
    ]
    campaigns = [{"id": str(uuid.uuid4())}]
    session = _FakeLiveSession(campaigns=campaigns, perf_rows=perf_rows)

    brain = CampaignBrain(
        gateway=_stub_gateway(),
        memory_store=BusinessMemoryStore(repository=repo),
        session_factory=lambda: session,
    )

    captured: list[str] = []
    original_run = brain.business_engine.run

    def _spy_run(*, tenant_id, plan, **kw):
        captured.append(kw.get("additional_context", ""))
        return original_run(tenant_id=tenant_id, plan=plan, **kw)

    brain.business_engine.run = _spy_run  # type: ignore[assignment]

    await brain.generate_campaign(
        tenant_id=tenant,
        plan="starter",
        business_name="Acme",
        goal="increase sales",
        brand_id=brand,
    )

    assert captured, "business engine should have been called"
    ctx = captured[0]
    assert "LIVE PERFORMANCE DATA" in ctx
    assert "Instagram" in ctx
    assert "reach" in ctx.lower()
    assert "WhatsApp" in ctx
    assert "Google Ads" in ctx


@pytest.mark.asyncio
async def test_generate_campaign_graceful_with_no_live_data():
    """When no live CampaignPerformance data exists, generation proceeds
    normally and no LIVE PERFORMANCE DATA block is added."""
    repo = InMemoryRepository()
    tenant = uuid.uuid4()
    brand = uuid.uuid4()

    # Session with campaigns but no performance rows.
    campaigns = [{"id": str(uuid.uuid4())}]
    session = _FakeLiveSession(campaigns=campaigns, perf_rows=[])

    brain = CampaignBrain(
        gateway=_stub_gateway(),
        memory_store=BusinessMemoryStore(repository=repo),
        session_factory=lambda: session,
    )

    captured: list[str] = []
    original_run = brain.business_engine.run

    def _spy_run(*, tenant_id, plan, **kw):
        captured.append(kw.get("additional_context", ""))
        return original_run(tenant_id=tenant_id, plan=plan, **kw)

    brain.business_engine.run = _spy_run  # type: ignore[assignment]

    campaign = await brain.generate_campaign(
        tenant_id=tenant,
        plan="starter",
        business_name="Acme",
        goal="increase sales",
        brand_id=brand,
    )

    assert campaign is not None
    assert captured, "business engine should have been called"
    ctx = captured[0]
    assert "LIVE PERFORMANCE DATA" not in ctx


@pytest.mark.asyncio
async def test_generate_campaign_graceful_without_session_factory():
    """When no session_factory is provided, live data is skipped gracefully
    and generation proceeds normally."""
    repo = InMemoryRepository()
    tenant = uuid.uuid4()
    brand = uuid.uuid4()

    brain = CampaignBrain(
        gateway=_stub_gateway(),
        memory_store=BusinessMemoryStore(repository=repo),
        session_factory=None,
    )

    campaign = await brain.generate_campaign(
        tenant_id=tenant,
        plan="starter",
        business_name="Acme",
        goal="increase sales",
        brand_id=brand,
    )
    assert campaign is not None
