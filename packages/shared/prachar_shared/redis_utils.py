"""Redis URL normalization shared by workers, api, and shared services.

Celery's redis backend requires ``ssl_cert_reqs=CERT_*`` inside ``rediss://``
URLs, while redis-py (sync and asyncio) accepts only the lowercase names
``none``/``optional``/``required`` or the ``ssl.CERT_*`` enum. REDIS_URL is a
single shared env var, so this normalizes the celery form into the redis-py
form at every ``from_url`` call site.
"""
from __future__ import annotations

import re

_CERT_PARAM = re.compile(r"ssl_cert_reqs=CERT_(\w+)")


def normalize_redis_url(url: str) -> str:
    """Rewrite celery-style ``ssl_cert_reqs=CERT_X`` to redis-py's ``x``."""
    return _CERT_PARAM.sub(lambda m: f"ssl_cert_reqs={m.group(1).lower()}", url)
