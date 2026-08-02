from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from prachar_shared.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        s = get_settings()
        # Pool sizing: defaults are tuned for production (25 base + 50 overflow
        # = 75 max connections). For local dev / tests, the defaults are fine.
        # When using PgBouncer in transaction-pooling mode, set pool_size lower
        # (e.g. 10) since PgBouncer multiplexes — the app pool just needs to
        # cover concurrent requests, not concurrent DB sessions.
        pool_size = s.db_pool_size
        max_overflow = s.db_max_overflow
        # pool_recycle prevents "stale connection" errors when the DB or a
        # proxy (PgBouncer, RDS proxy) drops idle connections after a timeout.
        # 1800s (30 min) is safe for most managed DBs which default to 1h.
        _engine = create_async_engine(
            s.database_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=30,  # seconds to wait for a connection before giving up
            future=True,
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _sessionmaker


async def get_session(request: Request):
    """FastAPI dependency. Yields a session with RLS context bound to the
    request's tenant_id (set by TenantMiddleware). Public endpoints have no
    tenant_id and must only touch RLS-exempt tables."""
    sm = get_sessionmaker()
    async with sm() as session:
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id is not None:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)}
            )
        yield session


@asynccontextmanager
async def session_scope(tenant_id: str | None = None) -> AsyncIterator[AsyncSession]:
    """Imperative context for workers/scripts. Optionally sets RLS context."""
    sm = get_sessionmaker()
    async with sm() as session:
        if tenant_id is not None:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)}
            )
        yield session
