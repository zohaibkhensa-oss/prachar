"""Rate limiting for auth endpoints — in-memory sliding window.

Prevents brute-force attacks on /auth/login, /auth/register, and password
reset endpoints. Uses a simple in-memory dict keyed by IP address.

For production at scale, swap this for Redis-backed rate limiting
(`redis://` sliding window). The interface stays the same.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status


# Module-level flag — tests can toggle this directly without polluting the
# settings cache. Production reads from Settings.rate_limit_enabled once at
# startup. Tests set _enabled = False to disable, True to re-enable.
_enabled: bool | None = None

# Max entries in _store before we force a global sweep. Prevents the store
# from growing unboundedly as new IPs arrive. At 10K unique IPs this is
# ~1MB of memory — negligible. Sweep drops empty buckets.
_MAX_STORE_SIZE = 50_000
_last_sweep: float = 0.0
_SWEEP_INTERVAL_SEC = 300  # sweep at most every 5 minutes


def _is_enabled() -> bool:
    """Lazily read the setting once, then cache in _enabled."""
    global _enabled
    if _enabled is None:
        from prachar_shared.config import get_settings
        _enabled = get_settings().rate_limit_enabled
    return _enabled


@dataclass
class _Bucket:
    timestamps: list[float] = field(default_factory=list)


# In-memory store: { "ip:endpoint": _Bucket }
_store: dict[str, _Bucket] = defaultdict(_Bucket)


def _get_client_ip(request: Request) -> str:
    """Extract client IP, accounting for proxy headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return "unknown"


def _cleanup_bucket(bucket: _Bucket, window_sec: int) -> None:
    cutoff = time.time() - window_sec
    bucket.timestamps = [t for t in bucket.timestamps if t > cutoff]


def _sweep_store() -> None:
    """Remove empty buckets from _store to prevent unbounded memory growth.

    Called lazily: either when _store exceeds _MAX_STORE_SIZE, or every
    _SWEEP_INTERVAL_SEC seconds (whichever comes first). This bounds the
    store size to ~_MAX_STORE_SIZE entries regardless of how many unique
    IPs hit the service over the app's lifetime.
    """
    global _last_sweep
    now = time.time()
    # Always sweep if we're over the hard cap
    over_cap = len(_store) > _MAX_STORE_SIZE
    # Otherwise sweep at most every _SWEEP_INTERVAL_SEC
    time_for_sweep = (now - _last_sweep) > _SWEEP_INTERVAL_SEC
    if not (over_cap or time_for_sweep):
        return
    # Drop buckets with no recent timestamps (use 1 hour as the longest
    # possible window — anything older than that is definitely expired)
    cutoff = now - 3600
    empty_keys = [
        key for key, bucket in _store.items()
        if not bucket.timestamps or bucket.timestamps[-1] < cutoff
    ]
    for key in empty_keys:
        del _store[key]
    _last_sweep = now


def check_rate_limit(
    request: Request,
    endpoint: str,
    max_requests: int,
    window_sec: int,
) -> None:
    """Check if the request should be rate-limited.

    Raises HTTPException(429) if the IP has exceeded max_requests in window_sec.
    """
    if not _is_enabled():
        return

    ip = _get_client_ip(request)
    key = f"{ip}:{endpoint}"
    bucket = _store[key]
    now = time.time()
    _cleanup_bucket(bucket, window_sec)

    if len(bucket.timestamps) >= max_requests:
        retry_after = int(window_sec - (now - bucket.timestamps[0]))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Try again in {max(retry_after, 1)} seconds.",
            headers={"Retry-After": str(max(retry_after, 1))},
        )

    bucket.timestamps.append(now)
    # Periodically sweep empty buckets to bound memory
    _sweep_store()


def reset_rate_limit(ip: str, endpoint: str) -> None:
    """Clear rate limit for a specific IP+endpoint (e.g. after successful login)."""
    key = f"{ip}:{endpoint}"
    if key in _store:
        del _store[key]
