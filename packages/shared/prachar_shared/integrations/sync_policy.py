"""Sync Policies — per-integration sync behaviour configuration.

Different businesses have different requirements. A high-volume Shopify store
needs real-time webhook sync, while a small blog might only need daily polling
for WordPress. Sync policies let users choose the behaviour per integration.

Sync Modes:
- REALTIME:   Webhook-driven, events processed as they arrive
- WEBHOOK:    Webhook-driven but batched (processed every N seconds)
- POLLING:    Pull data on a schedule (every 5 min, hourly, daily)
- MANUAL:     Only sync when user clicks "Sync" in the UI
- SCHEDULE:   Cron-like schedule (e.g. "0 2 * * *" = daily at 2am)
- DISABLED:   No sync, integration is dormant

Each mode has configurable parameters (interval, batch size, schedule expression).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SyncMode(str, Enum):
    """How an integration syncs data."""
    REALTIME = "realtime"     # Webhook-driven, immediate processing
    WEBHOOK = "webhook"       # Webhook-driven, batched processing
    POLLING = "polling"       # Pull on interval
    MANUAL = "manual"         # Only on user trigger
    SCHEDULE = "schedule"     # Cron expression
    DISABLED = "disabled"     # No sync


# Default sync mode by category
DEFAULT_SYNC_MODES: dict[str, SyncMode] = {
    "analytics": SyncMode.POLLING,      # GA4 — pull every hour
    "cms": SyncMode.MANUAL,             # WordPress — publish on demand
    "ecommerce": SyncMode.REALTIME,     # Shopify — webhook on order
    "crm": SyncMode.POLLING,            # HubSpot — pull every 15 min
    "email": SyncMode.POLLING,          # Mailchimp — pull every hour
    "ads": SyncMode.POLLING,            # Ad networks — pull every hour
}

# Default polling intervals by category (in seconds)
DEFAULT_POLL_INTERVALS: dict[str, int] = {
    "analytics": 3600,      # 1 hour
    "cms": 86400,           # 24 hours (manual anyway)
    "ecommerce": 300,       # 5 minutes (fallback if no webhooks)
    "crm": 900,             # 15 minutes
    "email": 3600,          # 1 hour
    "ads": 3600,            # 1 hour
}


@dataclass
class SyncPolicy:
    """Sync policy for a specific integration connection.

    Stored per-connection (not per-integration type) because different
    connections to the same integration may have different sync needs.
    """
    integration: str
    mode: SyncMode = SyncMode.MANUAL
    # For POLLING mode: interval in seconds
    poll_interval_seconds: int = 3600
    # For SCHEDULE mode: cron expression (e.g. "0 2 * * *" = daily at 2am)
    cron_expression: str = ""
    # For WEBHOOK mode: batch window in seconds (collect events, then process)
    batch_window_seconds: int = 30
    # Maximum events to process in one batch
    batch_size: int = 100
    # Whether to retry failed syncs
    retry_failed: bool = True
    # Maximum retry attempts
    max_retries: int = 3
    # Retry backoff in seconds (exponential: base * 2^attempt)
    retry_backoff_base: int = 60
    # Last sync timestamps
    last_sync_at: datetime | None = None
    last_successful_sync_at: datetime | None = None
    last_failed_sync_at: datetime | None = None
    last_error: str = ""
    # Sync statistics
    total_syncs: int = 0
    successful_syncs: int = 0
    failed_syncs: int = 0
    # Custom metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def default_for(cls, integration: str, category: str) -> "SyncPolicy":
        """Create a default sync policy for an integration based on its category."""
        mode = DEFAULT_SYNC_MODES.get(category, SyncMode.MANUAL)
        interval = DEFAULT_POLL_INTERVALS.get(category, 3600)
        return cls(
            integration=integration,
            mode=mode,
            poll_interval_seconds=interval,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "integration": self.integration,
            "mode": self.mode.value,
            "poll_interval_seconds": self.poll_interval_seconds,
            "cron_expression": self.cron_expression,
            "batch_window_seconds": self.batch_window_seconds,
            "batch_size": self.batch_size,
            "retry_failed": self.retry_failed,
            "max_retries": self.max_retries,
            "retry_backoff_base": self.retry_backoff_base,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "last_successful_sync_at": self.last_successful_sync_at.isoformat() if self.last_successful_sync_at else None,
            "last_failed_sync_at": self.last_failed_sync_at.isoformat() if self.last_failed_sync_at else None,
            "last_error": self.last_error,
            "total_syncs": self.total_syncs,
            "successful_syncs": self.successful_syncs,
            "failed_syncs": self.failed_syncs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SyncPolicy":
        """Reconstruct from a dict (e.g. from DB JSON column)."""
        def _parse_dt(v: str | None) -> datetime | None:
            if not v:
                return None
            try:
                return datetime.fromisoformat(v)
            except (ValueError, TypeError):
                return None

        return cls(
            integration=data.get("integration", ""),
            mode=SyncMode(data.get("mode", "manual")),
            poll_interval_seconds=data.get("poll_interval_seconds", 3600),
            cron_expression=data.get("cron_expression", ""),
            batch_window_seconds=data.get("batch_window_seconds", 30),
            batch_size=data.get("batch_size", 100),
            retry_failed=data.get("retry_failed", True),
            max_retries=data.get("max_retries", 3),
            retry_backoff_base=data.get("retry_backoff_base", 60),
            last_sync_at=_parse_dt(data.get("last_sync_at")),
            last_successful_sync_at=_parse_dt(data.get("last_successful_sync_at")),
            last_failed_sync_at=_parse_dt(data.get("last_failed_sync_at")),
            last_error=data.get("last_error", ""),
            total_syncs=data.get("total_syncs", 0),
            successful_syncs=data.get("successful_syncs", 0),
            failed_syncs=data.get("failed_syncs", 0),
            metadata=data.get("metadata", {}),
        )

    def record_success(self, synced_count: int = 0) -> None:
        """Record a successful sync."""
        now = datetime.now(timezone.utc)
        self.last_sync_at = now
        self.last_successful_sync_at = now
        self.last_error = ""
        self.total_syncs += 1
        self.successful_syncs += 1
        self.metadata["last_synced_count"] = synced_count

    def record_failure(self, error: str) -> None:
        """Record a failed sync."""
        now = datetime.now(timezone.utc)
        self.last_sync_at = now
        self.last_failed_sync_at = now
        self.last_error = error
        self.total_syncs += 1
        self.failed_syncs += 1

    def should_sync(self, now: datetime | None = None) -> bool:
        """Check if a sync should happen now based on the policy."""
        now = now or datetime.now(timezone.utc)

        if self.mode == SyncMode.DISABLED:
            return False

        if self.mode == SyncMode.MANUAL:
            return False  # Only triggered by user

        if self.mode == SyncMode.REALTIME:
            return True  # Always (webhook-driven)

        if self.mode == SyncMode.POLLING:
            if not self.last_sync_at:
                return True
            elapsed = (now - self.last_sync_at).total_seconds()
            return elapsed >= self.poll_interval_seconds

        if self.mode == SyncMode.SCHEDULE:
            # Cron evaluation is complex; for now just check if last sync was > 1 hour ago
            # In production, use a cron library like croniter
            if not self.last_sync_at:
                return True
            elapsed = (now - self.last_sync_at).total_seconds()
            return elapsed >= 3600  # Fallback: hourly

        if self.mode == SyncMode.WEBHOOK:
            return False  # Webhook-driven, not time-based

        return False

    def next_sync_at(self) -> datetime | None:
        """Estimate when the next sync should happen."""
        if self.mode in (SyncMode.DISABLED, SyncMode.MANUAL, SyncMode.REALTIME, SyncMode.WEBHOOK):
            return None

        if not self.last_sync_at:
            return datetime.now(timezone.utc)

        if self.mode == SyncMode.POLLING:
            return self.last_sync_at + timedelta(seconds=self.poll_interval_seconds)

        if self.mode == SyncMode.SCHEDULE:
            return self.last_sync_at + timedelta(hours=1)

        return None

    @property
    def success_rate(self) -> float:
        """Percentage of successful syncs."""
        if self.total_syncs == 0:
            return 100.0
        return (self.successful_syncs / self.total_syncs) * 100


# Need timedelta import
from datetime import timedelta  # noqa: E402
