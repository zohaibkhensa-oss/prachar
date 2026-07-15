from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt as _bcrypt
from jose import JWTError, jwt

from prachar_shared.config import get_settings


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:72]
    return _bcrypt.hashpw(pw, _bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, pw_hash: str) -> bool:
    pw = password.encode("utf-8")[:72]
    try:
        return _bcrypt.checkpw(pw, pw_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _secret(kind: str) -> str:
    s = get_settings()
    return s.jwt_secret if kind == "access" else s.jwt_refresh_secret


def _ttl(kind: str) -> timedelta:
    s = get_settings()
    if kind == "access":
        return timedelta(minutes=s.jwt_ttl_min)
    return timedelta(days=s.jwt_refresh_ttl_days)


def create_token(sub: str | uuid.UUID, kind: str = "access", extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(sub),
        "iat": int(now.timestamp()),
        "exp": int((now + _ttl(kind)).timestamp()),
        "typ": kind,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _secret(kind), algorithm="HS256")


def decode_token(token: str, kind: str = "access") -> dict[str, Any]:
    try:
        payload = jwt.decode(token, _secret(kind), algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError(f"invalid token: {exc}") from exc
    if payload.get("typ") != kind:
        raise ValueError("wrong token type")
    return payload


def hash_ip(ip: str) -> str:
    s = get_settings()
    return hashlib.sha256(f"{s.jwt_secret}:{ip}".encode()).hexdigest()
