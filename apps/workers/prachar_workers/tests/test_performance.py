"""Tests for the performance ingestion worker (P4.2).

Run with:
    .venv/bin/python -m pytest apps/workers/prachar_workers/tests/test_performance.py -q
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from prachar_workers import performance
from prachar_workers.performance import (
    PerformanceStore,
    aggregate_events,
    compute_derived,
    pull_for_campaign,
    run_pull,
    upsert_performance,
)

# ─── Fakes ───────────────────────────────────────────────────────────────────