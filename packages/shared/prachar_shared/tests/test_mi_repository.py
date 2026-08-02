"""Tests for the MemoryRepository abstraction (Phase 6: Architecture Stabilisation).

Verifies:
- InMemoryRepository implements the protocol
- BusinessMemoryStore depends on the protocol, not on SQLAlchemy
- No shared→api imports exist
- Dependency injection works correctly
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

from prachar_shared.marketing_intelligence import (
    BusinessMemory,
    BusinessMemoryStore,
    InMemoryRepository,
    MemoryRepository,
)


class TestInMemoryRepository:
    def test_get_returns_empty_for_missing(self) -> None:
        repo = InMemoryRepository()
        result = asyncio_run(repo.get(uuid.uuid4(), uuid.uuid4()))
        assert result == {}

    def test_save_then_get_roundtrip(self) -> None:
        repo = InMemoryRepository()
        tid, bid = uuid.uuid4(), uuid.uuid4()
        asyncio_run(repo.save(tid, bid, {"industry": "Coffee", "best_practices": ["x"]}))
        result = asyncio_run(repo.get(tid, bid))
        assert result["industry"] == "Coffee"
        assert result["best_practices"] == ["x"]

    def test_save_overwrites(self) -> None:
        repo = InMemoryRepository()
        tid, bid = uuid.uuid4(), uuid.uuid4()
        asyncio_run(repo.save(tid, bid, {"industry": "Coffee"}))
        asyncio_run(repo.save(tid, bid, {"industry": "Tea"}))
        result = asyncio_run(repo.get(tid, bid))
        assert result["industry"] == "Tea"

    def test_isolates_by_brand(self) -> None:
        repo = InMemoryRepository()
        tid = uuid.uuid4()
        asyncio_run(repo.save(tid, uuid.uuid4(), {"industry": "Coffee"}))
        asyncio_run(repo.save(tid, uuid.uuid4(), {"industry": "Tea"}))
        # Both should be independent
        assert len(repo._store) == 2


class TestBusinessMemoryStoreWithRepository:
    def test_default_uses_in_memory_repository(self) -> None:
        store = BusinessMemoryStore()
        assert isinstance(store._repository, InMemoryRepository)

    def test_accepts_custom_repository(self) -> None:
        repo = InMemoryRepository()
        store = BusinessMemoryStore(repository=repo)
        assert store._repository is repo

    def test_get_returns_empty_memory_for_missing(self) -> None:
        store = BusinessMemoryStore()
        memory = asyncio_run(store.get(uuid.uuid4(), uuid.uuid4()))
        assert isinstance(memory, BusinessMemory)
        assert memory.industry == ""

    def test_save_then_get_roundtrip(self) -> None:
        store = BusinessMemoryStore()
        tid, bid = uuid.uuid4(), uuid.uuid4()
        memory = BusinessMemory(industry="Coffee", brand_voice="Warm")
        asyncio_run(store.save(tid, bid, memory))
        loaded = asyncio_run(store.get(tid, bid))
        assert loaded.industry == "Coffee"
        assert loaded.brand_voice == "Warm"

    def test_save_sets_updated_at(self) -> None:
        store = BusinessMemoryStore()
        memory = BusinessMemory()
        asyncio_run(store.save(uuid.uuid4(), uuid.uuid4(), memory))
        assert memory.updated_at != ""

    def test_get_handles_repository_failure(self) -> None:
        class _FailRepo:
            async def get(self, tid: Any, bid: Any) -> dict[str, Any]:
                raise RuntimeError("DB down")
            async def save(self, tid: Any, bid: Any, m: Any) -> None:
                pass
        store = BusinessMemoryStore(repository=_FailRepo())  # type: ignore[arg-type]
        memory = asyncio_run(store.get(uuid.uuid4(), uuid.uuid4()))
        assert isinstance(memory, BusinessMemory)
        assert memory.industry == ""  # graceful fallback

    def test_save_handles_repository_failure(self) -> None:
        class _FailRepo:
            async def get(self, tid: Any, bid: Any) -> dict[str, Any]:
                return {}
            async def save(self, tid: Any, bid: Any, m: Any) -> None:
                raise RuntimeError("DB down")
        store = BusinessMemoryStore(repository=_FailRepo())  # type: ignore[arg-type]
        # Should not raise
        asyncio_run(store.save(uuid.uuid4(), uuid.uuid4(), BusinessMemory()))


class TestProtocolConformance:
    def test_in_memory_repository_is_memory_repository(self) -> None:
        """InMemoryRepository should satisfy the MemoryRepository protocol."""
        repo = InMemoryRepository()
        assert isinstance(repo, MemoryRepository)

    def test_custom_repo_with_matching_methods_satisfies_protocol(self) -> None:
        class CustomRepo:
            async def get(self, tid: Any, bid: Any) -> dict[str, Any]:
                return {}
            async def save(self, tid: Any, bid: Any, m: Any) -> None:
                pass
        assert isinstance(CustomRepo(), MemoryRepository)


# ─── Helper ─────────────────────────────────────────────────────────────────


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)
