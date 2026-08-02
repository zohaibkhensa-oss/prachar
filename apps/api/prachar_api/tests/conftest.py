"""Global test configuration — sets test env vars before settings are cached.

Disables rate limiting globally so multiple tests can register users from
127.0.0.1 without hitting 429 errors. Tests that need rate limiting
(test_auth_hardening.py) re-enable it via the rate_limit._enabled module flag.
"""
import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://prachar:prachar@localhost:5432/prachar")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-jwt-xxxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-secret-refresh-xxxxxxxxxxxxxxxxx")
os.environ.setdefault("TOKEN_ENC_KEY", "a" * 64)

# Disable rate limiting at the module level (read once, no settings cache pollution)
from prachar_api import rate_limit  # noqa: E402

rate_limit._enabled = False
