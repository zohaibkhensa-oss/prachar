"""Load decrypted OAuth tokens for a brand+channel as a ``TokenSet``.

Shared by publish/performance/ads/organic tasks. Reads the encrypted
``connections.oauth_tokens_enc`` bundle written by the OAuth callback and
rehydrates a real ``TokenSet`` (access token, expiry, scopes, metadata such as
Meta's ``ad_account_id``). Returns ``None`` when no usable connection exists —
callers must treat that as "channel not connected" rather than fabricate tokens.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def load_connection_tokens(brand_id: str, channel: str) -> Any | None:
    """Return a ``TokenSet`` for the brand's newest connection on ``channel``."""
    try:
        from prachar_shared.contracts import TokenSet
        from prachar_shared.security import decrypt_token
        from sqlalchemy import text

        from prachar_workers.db import session_scope

        with session_scope() as session:
            row = session.execute(
                text(
                    "SELECT oauth_tokens_enc, expires_at, scopes "
                    "FROM connections WHERE brand_id = :bid AND channel = :ch "
                    "AND status = 'active' "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"bid": brand_id, "ch": channel},
            ).first()
            if not row or not row[0]:
                return None
            data = json.loads(decrypt_token(row[0]))
            return TokenSet(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                expires_at=datetime.fromisoformat(data["expires_at"]),
                scopes=data.get("scopes", []),
                metadata=data.get("metadata", {}),
            )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("load_connection_tokens failed brand=%s channel=%s: %s", brand_id, channel, exc)
        return None


def tokens_expired(tokens: Any) -> bool:
    exp = getattr(tokens, "expires_at", None)
    return exp is not None and exp <= datetime.now(UTC)
