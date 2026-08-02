"""Clean Architecture boundaries for the Marketing Intelligence Engine.

This module documents and enforces the dependency rules of the
Marketing Intelligence Engine. The architecture follows Clean Architecture
+ DDD + Hexagonal Architecture principles.

LAYERS (dependencies point inward only):

    Presentation (apps/api/prachar_api/routers/)
        ↓ depends on
    Application (packages/shared/.../marketing_intelligence/brain.py)
        ↓ depends on
    Domain (packages/shared/.../marketing_intelligence/{domain_base,*_engine,repository}.py)
        ↑ depends on
    Infrastructure (apps/api/prachar_api/infrastructure.py)

RULES:
1. Domain never imports infrastructure (no SQLAlchemy, no FastAPI, no API models).
2. Domain never imports application (no brain.py, no engine run() methods).
3. Application imports domain only (engines, models, repository protocol).
4. Presentation imports application (CampaignBrain) and infrastructure (repos).
5. Infrastructure implements domain protocols (MemoryRepository).

The dependency inversion is achieved via Protocols:
- Domain defines MemoryRepository (protocol)
- Infrastructure implements PostgresMemoryRepository
- Application uses BusinessMemoryStore(repository: MemoryRepository)

This allows the shared package to be used without the API app installed
(e.g., in tests, in workers, in future services).
"""
from __future__ import annotations

# ─── Layer markers (for documentation and architecture tests) ──────────────

DOMAIN_LAYER = "domain"
APPLICATION_LAYER = "application"
INFRASTRUCTURE_LAYER = "infrastructure"
PRESENTATION_LAYER = "presentation"

# Files that belong to each layer (relative to marketing_intelligence/)
DOMAIN_FILES = {
    "domain_base.py",
    "business_engine.py",  # dataclass + engine (domain logic)
    "audience_engine.py",
    "competitor_engine.py",
    "objective_engine.py",
    "strategy_engine.py",
    "creative_engine.py",
    "media_engine.py",
    "budget_engine.py",
    "execution_engine.py",
    "learning_engine.py",
    "repository.py",  # protocol (domain defines the interface)
    "memory.py",  # BusinessMemory dataclass (domain) + BusinessMemoryStore (application)
}

APPLICATION_FILES = {
    "brain.py",  # orchestrator (application layer)
    "memory.py",  # BusinessMemoryStore is application (uses repository)
}

INFRASTRUCTURE_FILES = {
    # apps/api/prachar_api/infrastructure.py (outside this package)
}

PRESENTATION_FILES = {
    # apps/api/prachar_api/routers/campaign_brain.py (outside this package)
}

# Forbidden imports in domain files
FORBIDDEN_IN_DOMAIN = [
    "sqlalchemy",
    "fastapi",
    "pydantic",
    "prachar_api",
]
