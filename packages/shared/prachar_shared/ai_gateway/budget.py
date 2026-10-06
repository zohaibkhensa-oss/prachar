from __future__ import annotations

import logging
from datetime import UTC, datetime

import redis

from prachar_shared.redis_utils import normalize_redis_url

from ..config import get_settings

logger = logging.getLogger(__name__)

# Atomically reserve `tokens` against the monthly cap: INCRBY only if the
# reservation fits, so concurrent requests can't both pass the check.
# ARGV: [1]=cap, [2]=tokens to reserve. Returns new usage, or -1 if over cap.
_RESERVE_LUA = """
local used = tonumber(redis.call('GET', KEYS[1]) or '0')
local cap = tonumber(ARGV[1])
local tokens = tonumber(ARGV[2])
if used + tokens > cap then
  return -1
end
local newv = redis.call('INCRBY', KEYS[1], tokens)
redis.call('PEXPIRE', KEYS[1], 4003200000)  -- ~46 days, past month rollover
return newv
"""

# Settle a reservation to actual usage: adjust by (actual - reserved),
# clamped at 0 so a released reservation on an expired key can't go negative.
# ARGV: [1]=delta (may be negative).
_SETTLE_LUA = """
local cur = tonumber(redis.call('GET', KEYS[1]) or '0')
local nextv = cur + tonumber(ARGV[1])
if nextv < 0 then nextv = 0 end
redis.call('SET', KEYS[1], nextv)
return nextv
"""


def _month_key(tenant_id, dt: datetime | None = None) -> str:
    dt = dt or datetime.now(UTC)
    return f"budget:{tenant_id}:{dt.strftime('%Y-%m')}"


class BudgetGuard:
    def __init__(self, client: redis.Redis | None = None) -> None:
        self._client = client

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis.from_url(normalize_redis_url(get_settings().redis_url), decode_responses=False)
        return self._client

    def _cap(self, plan: str) -> int:
        return get_settings().plan_budget(plan)

    def remaining(self, tenant_id, plan: str) -> int:
        used = int(self.client.get(_month_key(tenant_id)) or 0)
        return max(0, self._cap(plan) - used)

    def check_and_reserve(self, tenant_id, tokens: int, plan: str) -> bool:
        """Atomically reserve `tokens` against the monthly cap.

        Returns True and increments the counter if the reservation fits;
        returns False without touching the counter if it would exceed the cap.
        The reservation is settled to actual usage via record_usage(reserved=).
        """
        newv = self.client.eval(
            _RESERVE_LUA, 1, _month_key(tenant_id), self._cap(plan), int(tokens)
        )
        if int(newv) == -1:
            used = int(self.client.get(_month_key(tenant_id)) or 0)
            logger.info("budget exceeded for %s plan=%s used=%s tokens=%s", tenant_id, plan, used, tokens)
            return False
        return True

    def record_usage(self, tenant_id, tokens: int, plan: str, reserved: int = 0) -> None:
        """Settle actual usage against a prior reservation.

        `reserved` is what check_and_reserve booked up-front (typically
        max_tokens); the counter is adjusted by (actual - reserved). When
        called without `reserved` this is a plain increment.
        """
        self.client.eval(_SETTLE_LUA, 1, _month_key(tenant_id), int(tokens) - int(reserved))
