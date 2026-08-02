"""Memory repository protocol for dependency inversion.

The shared package defines the protocol; the API app provides the
PostgresMemoryRepository implementation. This ensures the shared package
never imports from the API app (Phase 6: Architecture Stabilisation).

Architecture:
    Domain (shared) defines MemoryRepository protocol
         ↑
    Infrastructure (api) implements PostgresMemoryRepository
         ↑
    Application (brain) uses BusinessMemoryStore(repository)
"""
from __future__ import annotations

import uuid
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MemoryRepository(Protocol):
    """Protocol for reading and writing BusinessMemory.

    Implementations live in the infrastructure layer (e.g.,
    PostgresMemoryRepository in the API app). The shared package
    depends only on this protocol, never on the implementation.
    """

    async def get(self, tenant_id: uuid.UUID, brand_id: uuid.UUID) -> dict[str, Any]:
        """Read the business memory for a brand.

        Returns:
            The memory as a dict (empty dict if not found).
        """
        ...

    async def save(
        self,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        memory: dict[str, Any],
    ) -> None:
        """Save (upsert) the business memory for a brand."""
        ...


class InMemoryRepository:
    """Simple in-memory implementation of MemoryRepository.

    Useful for tests and stub mode. No persistence.
    """

    def __init__(self) -> None:
        self._store: dict[tuple[uuid.UUID, uuid.UUID], dict[str, Any]] = {}

    async def get(self, tenant_id: uuid.UUID, brand_id: uuid.UUID) -> dict[str, Any]:
        return self._store.get((tenant_id, brand_id), {})

    async def save(
        self,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        memory: dict[str, Any],
    ) -> None:
        self._store[(tenant_id, brand_id)] = dict(memory)
