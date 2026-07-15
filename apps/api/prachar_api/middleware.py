from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .security import decode_token


class TenantMiddleware(BaseHTTPMiddleware):
    """Extracts the tenant_id from the JWT and stashes it on request.state.
    The actual Postgres RLS context (SET LOCAL app.tenant_id) is applied inside
    the get_session dependency on the same connection used by the handler."""

    async def dispatch(self, request: Request, call_next) -> Response:
        auth = request.headers.get("authorization")
        tenant_id: uuid.UUID | None = None
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            try:
                payload = decode_token(token, kind="access")
                tid = payload.get("tenant_id")
                if tid:
                    tenant_id = uuid.UUID(str(tid))
            except (ValueError, KeyError):
                pass
        request.state.tenant_id = tenant_id
        return await call_next(request)
