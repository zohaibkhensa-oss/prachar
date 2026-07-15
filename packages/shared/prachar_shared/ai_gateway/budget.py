from __future__ import annotations

import logging
from datetime import UTC, datetime

import redis

from ..config import get_settings

logger = logging.getLogger(__name__)


def _month_key(tenant_id, dt: datetime | None = None) -> str:
    dt = dt or datetime.now(UTC)
    return f"budget:{tenant_id}:{dt.strftime('%Y-%m')}"


class BudgetGuard:
    def __init__(self, client: redis.Redis | None = None) -> None:
        self._client = client

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis.from_url(get_settings().redis_url, decode_responses=False)
        return self._client

    def _cap(self, plan: str) -> int:
        return get_settings().plan_budget(plan)

    def remaining(self, tenant_id, plan: str) -> int:
        used = int(self.client.get(_month_key(tenant_id)) or 0)
        return max(0, self._cap(plan) - used)

    def check_and_reserve(self, tenant_id, tokens: int, plan: str) -> bool:
        key = _month_key(tenant_id)
        used = int(self.client.get(key) or 0)
        if used + tokens > self._cap(plan):
            logger.info("budget exceeded for %s plan=%s used=%s tokens=%s", tenant_id, plan, used, tokens)
            return False
        return True

    def record_usage(self, tenant_id, tokens: int, plan: str) -> None:
        self.client.incrby(_month_key(tenant_id), int(tokens))
