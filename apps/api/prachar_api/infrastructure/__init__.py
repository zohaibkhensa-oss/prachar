"""Infrastructure layer — implementations of shared protocols.

This package contains:
  - consult_engine: Universal Consult Engine (replaces duplicated /consult + /creator orchestration)
  - _memory_repos: Postgres implementations of MemoryRepository and CouncilMemoryRepository

Backward compatibility: PostgresMemoryRepository and PostgresCouncilRepository
are re-exported here so existing imports (`from ..infrastructure import ...`)
continue to work.
"""
from .consult_engine import ConsultEngine, ConsultResult, CampaignResult, ToolResult
from ._memory_repos import PostgresMemoryRepository, PostgresCouncilRepository

__all__ = [
    "ConsultEngine",
    "ConsultResult",
    "CampaignResult",
    "ToolResult",
    "PostgresMemoryRepository",
    "PostgresCouncilRepository",
]
