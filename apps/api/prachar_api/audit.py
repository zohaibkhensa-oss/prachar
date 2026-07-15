from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .models import Actor, AuditEvent


async def log_audit(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    actor: Actor | str,
    action: str,
    entity_type: str,
    entity_id: str | uuid.UUID,
    payload: dict[str, Any] | None = None,
) -> None:
    """Append an immutable audit event. No exception swallowing — caller's tx
    rolls back if this fails (audit is mandatory, not best-effort)."""
    event = AuditEvent(
        tenant_id=tenant_id or uuid.UUID(int=0),
        actor=actor if isinstance(actor, str) else actor.value,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        payload=payload,
    )
    session.add(event)
    await session.flush()
