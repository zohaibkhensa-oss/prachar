from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import redis

from ..config import get_settings

logger = logging.getLogger(__name__)

# TTL table by task type (seconds).
TTL_TABLE: dict[str, int] = {
    "generation": 7 * 24 * 3600,
    "captions": 7 * 24 * 3600,
    "tags": 7 * 24 * 3600,
    "metas": 7 * 24 * 3600,
    "creative_copy": 7 * 24 * 3600,
    "geo_probes": 7 * 24 * 3600,
    "audits": 7 * 24 * 3600,
    "diagnosis": 7 * 24 * 3600,  # per-week key handled by caller via task naming
}
DEFAULT_TTL = 24 * 3600


def ttl_for(task: str) -> int:
    return TTL_TABLE.get(task, DEFAULT_TTL)


class Cache:
    def __init__(self, client: redis.Redis | None = None) -> None:
        self._client = client

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
        return self._client

    def key(self, model: str, prompt: str, schema: dict[str, Any] | None) -> str:
        schema_str = json.dumps(schema, sort_keys=True) if schema else ""
        h = hashlib.sha256()
        h.update(model.encode("utf-8"))
        h.update(b"\x00")
        h.update(prompt.encode("utf-8"))
        h.update(b"\x00")
        h.update(schema_str.encode("utf-8"))
        return "ai:" + h.hexdigest()

    def get(self, key: str) -> str | None:
        try:
            return self.client.get(key)
        except redis.RedisError:
            logger.warning("cache get failed", exc_info=True)
            return None

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        try:
            self.client.set(key, value, ex=ttl_seconds)
        except redis.RedisError:
            logger.warning("cache set failed", exc_info=True)
