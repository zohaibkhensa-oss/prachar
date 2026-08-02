"""AI observability and metrics collection.

Every AI request logs:
- request_id
- workspace (tenant_id)
- campaign (optional)
- prompt_version
- model
- provider
- latency
- token usage
- estimated cost
- retry count
- failure reason

Metrics are stored in Redis for real-time dashboards and can be
exported to Prometheus or other monitoring systems.

Usage:
    from prachar_shared.ai_gateway.observability import AIMetrics, log_ai_request

    metrics = AIMetrics()
    metrics.record(
        request_id="req-123",
        tenant_id="tenant-456",
        task="chat",
        model="llama-3.3-70b",
        provider="groq",
        latency_ms=1200,
        tokens_used=500,
        cost_usd=0.001,
        cached=False,
        success=True,
    )
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

import redis

from ..config import get_settings

logger = logging.getLogger(__name__)


# ─── Cost estimation tables (per 1M tokens) ───────────────────────────────────
# Updated 2026-07. These are approximate list prices.
COST_TABLE: dict[str, dict[str, float]] = {
    # Groq
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "llama-3.1-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    # Anthropic
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-20250514": {"input": 1.00, "output": 5.00},
    # Fallback
    "_default": {"input": 1.00, "output": 3.00},
}


def estimate_cost(model: str, tokens_used: int, *, input_ratio: float = 0.6) -> float:
    """Estimate the USD cost of an AI request.

    Args:
        model: The model name used.
        tokens_used: Total tokens (input + output).
        input_ratio: Fraction of tokens that are input (default 60%).

    Returns:
        Estimated cost in USD.
    """
    pricing = COST_TABLE.get(model, COST_TABLE["_default"])
    input_tokens = int(tokens_used * input_ratio)
    output_tokens = tokens_used - input_tokens
    cost = (input_tokens / 1_000_000 * pricing["input"]) + (output_tokens / 1_000_000 * pricing["output"])
    return round(cost, 6)


@dataclass
class AIRequestLog:
    """Structured log entry for an AI request."""

    request_id: str
    tenant_id: str
    task: str
    model: str
    provider: str
    latency_ms: float
    tokens_used: int
    cost_usd: float
    cached: bool = False
    success: bool = True
    retry_count: int = 0
    failure_reason: str = ""
    prompt_version: str = ""
    campaign_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_json(self) -> str:
        return json.dumps(asdict(self))


class AIMetrics:
    """Collects and stores AI metrics in Redis.

    Metrics are stored in two forms:
    1. Individual request logs (Redis list, capped at 10000 entries)
    2. Aggregated counters (Redis hashes for dashboard queries)
    """

    def __init__(self, client: redis.Redis | None = None) -> None:
        self._client = client

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
        return self._client

    def record(self, log: AIRequestLog) -> None:
        """Record an AI request log and update aggregated metrics."""
        try:
            # Store individual log (capped list)
            self.client.lpush("ai:logs", log.to_json())
            self.client.ltrim("ai:logs", 0, 9999)  # Keep last 10000

            # Update aggregated metrics
            date_key = datetime.now(UTC).strftime("%Y-%m-%d")
            prefix = f"ai:metrics:{date_key}"

            # Total counts
            self.client.hincrby(prefix, "total_requests", 1)
            if log.success:
                self.client.hincrby(prefix, "success_count", 1)
            else:
                self.client.hincrby(prefix, "failure_count", 1)

            if log.cached:
                self.client.hincrby(prefix, "cache_hit_count", 1)
            else:
                self.client.hincrby(prefix, "cache_miss_count", 1)

            # Latency (running sum for average)
            self.client.hincrbyfloat(prefix, "latency_sum_ms", log.latency_ms)
            self.client.hincrby(prefix, "latency_count", 1)

            # Token usage
            self.client.hincrby(prefix, "tokens_total", log.tokens_used)

            # Cost
            self.client.hincrbyfloat(prefix, "cost_total_usd", log.cost_usd)

            # Retry count
            if log.retry_count > 0:
                self.client.hincrby(prefix, "retry_count", 1)

            # Per-task metrics
            task_prefix = f"{prefix}:task:{log.task}"
            self.client.hincrby(task_prefix, "count", 1)
            self.client.hincrbyfloat(task_prefix, "latency_sum_ms", log.latency_ms)
            self.client.hincrby(task_prefix, "latency_count", 1)
            if not log.success:
                self.client.hincrby(task_prefix, "failure_count", 1)

            # Per-provider metrics
            provider_prefix = f"{prefix}:provider:{log.provider}"
            self.client.hincrby(provider_prefix, "count", 1)
            if not log.success:
                self.client.hincrby(provider_prefix, "failure_count", 1)

            # Per-model metrics
            model_prefix = f"{prefix}:model:{log.model}"
            self.client.hincrby(model_prefix, "count", 1)
            self.client.hincrby(model_prefix, "tokens_total", log.tokens_used)

            # Set TTL on daily keys (30 days)
            self.client.expire(prefix, 30 * 24 * 3600)
        except redis.RedisError:
            logger.warning("AI metrics record failed (Redis unavailable)", exc_info=True)

    def get_dashboard(self, date: str | None = None) -> dict[str, Any]:
        """Get aggregated metrics for dashboard display.

        Args:
            date: Date string YYYY-MM-DD. Defaults to today.

        Returns:
            Dict with all metrics for the date.
        """
        date = date or datetime.now(UTC).strftime("%Y-%m-%d")
        prefix = f"ai:metrics:{date}"

        try:
            data = self.client.hgetall(prefix)
            total = int(data.get("total_requests", 0))
            success = int(data.get("success_count", 0))
            failure = int(data.get("failure_count", 0))
            cache_hits = int(data.get("cache_hit_count", 0))
            cache_misses = int(data.get("cache_miss_count", 0))
            latency_sum = float(data.get("latency_sum_ms", 0))
            latency_count = int(data.get("latency_count", 0))
            tokens = int(data.get("tokens_total", 0))
            cost = float(data.get("cost_total_usd", 0))
            retries = int(data.get("retry_count", 0))

            avg_latency = latency_sum / latency_count if latency_count > 0 else 0
            success_rate = (success / total * 100) if total > 0 else 0
            failure_rate = (failure / total * 100) if total > 0 else 0
            cache_hit_rate = (cache_hits / total * 100) if total > 0 else 0

            # Get per-task breakdown
            task_keys = self.client.keys(f"{prefix}:task:*")
            tasks: dict[str, Any] = {}
            for key in task_keys:
                task_name = key.split(":task:")[-1]
                task_data = self.client.hgetall(key)
                t_count = int(task_data.get("count", 0))
                t_latency_sum = float(task_data.get("latency_sum_ms", 0))
                t_latency_count = int(task_data.get("latency_count", 0))
                t_failures = int(task_data.get("failure_count", 0))
                tasks[task_name] = {
                    "count": t_count,
                    "avg_latency_ms": t_latency_sum / t_latency_count if t_latency_count > 0 else 0,
                    "failure_rate": (t_failures / t_count * 100) if t_count > 0 else 0,
                }

            # Get per-provider breakdown
            provider_keys = self.client.keys(f"{prefix}:provider:*")
            providers: dict[str, Any] = {}
            for key in provider_keys:
                provider_name = key.split(":provider:")[-1]
                provider_data = self.client.hgetall(key)
                p_count = int(provider_data.get("count", 0))
                p_failures = int(provider_data.get("failure_count", 0))
                providers[provider_name] = {
                    "count": p_count,
                    "failure_rate": (p_failures / p_count * 100) if p_count > 0 else 0,
                }

            return {
                "date": date,
                "total_requests": total,
                "success_count": success,
                "failure_count": failure,
                "success_rate": round(success_rate, 2),
                "failure_rate": round(failure_rate, 2),
                "cache_hit_rate": round(cache_hit_rate, 2),
                "avg_latency_ms": round(avg_latency, 2),
                "total_tokens": tokens,
                "total_cost_usd": round(cost, 4),
                "retry_count": retries,
                "tasks": tasks,
                "providers": providers,
            }
        except redis.RedisError:
            logger.warning("AI metrics dashboard query failed", exc_info=True)
            return {"error": "metrics unavailable (redis down)"}

    def get_recent_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent AI request logs."""
        try:
            raw_logs = self.client.lrange("ai:logs", 0, limit - 1)
            return [json.loads(log) for log in raw_logs]
        except redis.RedisError:
            return []


# ─── Convenience functions ─────────────────────────────────────────────────────

_metrics: AIMetrics | None = None


def get_metrics() -> AIMetrics:
    """Get the global AIMetrics singleton."""
    global _metrics
    if _metrics is None:
        _metrics = AIMetrics()
    return _metrics


def new_request_id() -> str:
    """Generate a unique request ID."""
    return f"ai-{uuid.uuid4().hex[:12]}"


def log_ai_request(
    *,
    tenant_id: str,
    task: str,
    model: str,
    provider: str,
    latency_ms: float,
    tokens_used: int,
    cost_usd: float | None = None,
    cached: bool = False,
    success: bool = True,
    retry_count: int = 0,
    failure_reason: str = "",
    prompt_version: str = "",
    campaign_id: str = "",
    request_id: str | None = None,
) -> None:
    """Log an AI request with full observability data."""
    log = AIRequestLog(
        request_id=request_id or new_request_id(),
        tenant_id=str(tenant_id),
        task=task,
        model=model,
        provider=provider,
        latency_ms=latency_ms,
        tokens_used=tokens_used,
        cost_usd=cost_usd if cost_usd is not None else estimate_cost(model, tokens_used),
        cached=cached,
        success=success,
        retry_count=retry_count,
        failure_reason=failure_reason,
        prompt_version=prompt_version,
        campaign_id=campaign_id,
    )
    get_metrics().record(log)
    # Also log to structured logger
    logger.info(
        "ai_request id=%s task=%s model=%s provider=%s latency=%dms tokens=%d cost=$%.6f cached=%s success=%s",
        log.request_id,
        log.task,
        log.model,
        log.provider,
        log.latency_ms,
        log.tokens_used,
        log.cost_usd,
        log.cached,
        log.success,
    )
