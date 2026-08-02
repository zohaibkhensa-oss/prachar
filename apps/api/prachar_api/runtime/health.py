"""Capability Health Registry — tracks the health of every registered tool.

Phase E1.2: The Planner uses health status to automatically avoid degraded
or offline tools. The Runtime gracefully handles tool unavailability by
skipping offline tools and noting degraded ones in the plan.

Health states:
    healthy  — tool is fully operational
    degraded — tool is experiencing issues (slow, partial failures)
    offline  — tool is completely unavailable

Health checks are optional — tools without checkers default to healthy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable


class HealthStatus(str, Enum):
    """Health status of a tool."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OFFLINE = "offline"


@dataclass
class ToolHealth:
    """Health record for a single tool."""

    tool_name: str
    status: HealthStatus = HealthStatus.HEALTHY
    last_check: str = ""
    error_count: int = 0
    success_count: int = 0
    latency_ms: int = 0
    message: str = ""

    @property
    def is_available(self) -> bool:
        """True if the tool is not offline."""
        return self.status != HealthStatus.OFFLINE

    @property
    def is_healthy(self) -> bool:
        """True only if the tool is fully healthy."""
        return self.status == HealthStatus.HEALTHY

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "status": self.status.value,
            "last_check": self.last_check,
            "error_count": self.error_count,
            "success_count": self.success_count,
            "latency_ms": self.latency_ms,
            "message": self.message,
        }


class HealthRegistry:
    """Tracks health of all registered tools."""

    def __init__(self) -> None:
        self._health: dict[str, ToolHealth] = {}
        self._checkers: dict[str, Callable[[], Awaitable[HealthStatus]]] = {}

    def register(
        self,
        tool_name: str,
        checker: Callable[[], Awaitable[HealthStatus]] | None = None,
    ) -> None:
        """Register a tool for health tracking. Optionally provide a health checker."""
        self._health[tool_name] = ToolHealth(tool_name=tool_name)
        if checker:
            self._checkers[tool_name] = checker

    def get(self, tool_name: str) -> ToolHealth:
        """Get the health record for a tool (defaults to healthy if unknown)."""
        return self._health.get(tool_name, ToolHealth(tool_name=tool_name))

    def update(self, tool_name: str, status: HealthStatus, message: str = "") -> None:
        """Update a tool's health status."""
        if tool_name not in self._health:
            self._health[tool_name] = ToolHealth(tool_name=tool_name)
        self._health[tool_name].status = status
        self._health[tool_name].message = message
        self._health[tool_name].last_check = datetime.now(timezone.utc).isoformat()

    def record_success(self, tool_name: str, latency_ms: int = 0) -> None:
        """Record a successful tool execution."""
        if tool_name not in self._health:
            self._health[tool_name] = ToolHealth(tool_name=tool_name)
        h = self._health[tool_name]
        h.success_count += 1
        h.latency_ms = latency_ms
        # Auto-recover from degraded if we get enough successes
        if h.status == HealthStatus.DEGRADED and h.success_count > h.error_count * 3:
            h.status = HealthStatus.HEALTHY
            h.message = ""

    def record_error(self, tool_name: str, error: str = "") -> None:
        """Record a tool execution failure."""
        if tool_name not in self._health:
            self._health[tool_name] = ToolHealth(tool_name=tool_name)
        h = self._health[tool_name]
        h.error_count += 1
        h.message = error
        h.last_check = datetime.now(timezone.utc).isoformat()
        # Auto-degrade after 3 consecutive errors
        if h.error_count >= 3 and h.status == HealthStatus.HEALTHY:
            h.status = HealthStatus.DEGRADED
        # Auto-offline after 10 errors
        if h.error_count >= 10:
            h.status = HealthStatus.OFFLINE

    def get_available_tools(self) -> list[str]:
        """Return names of all non-offline tools."""
        return [name for name, h in self._health.items() if h.is_available]

    def get_healthy_tools(self) -> list[str]:
        """Return names of all healthy tools."""
        return [name for name, h in self._health.items() if h.is_healthy]

    def list_all(self) -> list[ToolHealth]:
        """Return health status of all tracked tools."""
        return list(self._health.values())

    async def check_all(self) -> None:
        """Run all registered health checkers and update statuses."""
        for tool_name, checker in self._checkers.items():
            try:
                status = await checker()
                self.update(tool_name, status)
            except Exception:
                self.update(tool_name, HealthStatus.OFFLINE, "health check failed")


# ─── Singleton ──────────────────────────────────────────────────────────────


_health_registry: HealthRegistry | None = None


def get_health_registry() -> HealthRegistry:
    """Get the global health registry (lazy singleton)."""
    global _health_registry
    if _health_registry is None:
        _health_registry = HealthRegistry()
    return _health_registry
