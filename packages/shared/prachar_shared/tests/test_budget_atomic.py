"""Atomic budget reservation tests — regression for the pre-check pattern
where check_and_reserve read-but-didn't-write, letting concurrent calls
both pass. Now INCRBY+compare happen in one Lua script.
"""
from __future__ import annotations

import uuid

import pytest
from prachar_shared.ai_gateway.budget import BudgetGuard


class _LuaFakeRedis:
    """Minimal in-memory Redis double that interprets budget.py's two Lua
    scripts (reserve: INCRBY-if-fits; settle: clamped delta apply)."""

    def __init__(self) -> None:
        self._d: dict[str, int] = {}

    def get(self, key: str):
        return self._d.get(key)

    def eval(self, script: str, numkeys: int, key: str, *args):
        if "INCRBY" in script:  # reservation script
            used = int(self._d.get(key, 0))
            cap, tokens = int(args[0]), int(args[1])
            if used + tokens > cap:
                return -1
            self._d[key] = used + tokens
            return self._d[key]
        # settle script
        cur = int(self._d.get(key, 0))
        nxt = max(0, cur + int(args[0]))
        self._d[key] = nxt
        return nxt


@pytest.fixture()
def guard(monkeypatch: pytest.MonkeyPatch) -> tuple[BudgetGuard, _LuaFakeRedis]:
    monkeypatch.setattr(
        "prachar_shared.ai_gateway.budget.get_settings",
        lambda: type("S", (), {"plan_budget": staticmethod(lambda p: 1000)})(),
    )
    client = _LuaFakeRedis()
    return BudgetGuard(client=client), client


def test_reserve_fits_increments_counter(guard) -> None:
    g, _ = guard
    tid = uuid.uuid4()
    assert g.check_and_reserve(tid, 400, "starter") is True


def test_reserve_over_cap_returns_false_and_does_not_write(guard) -> None:
    g, c = guard
    tid = uuid.uuid4()
    assert g.check_and_reserve(tid, 900, "starter") is True
    assert g.check_and_reserve(tid, 200, "starter") is False
    assert int(c.get(f"budget:{tid}:{__import__('datetime').datetime.now(__import__('datetime').UTC).strftime('%Y-%m')}") or 0) == 900


def test_settle_replaces_reservation_with_actual(guard) -> None:
    g, c = guard
    tid = uuid.uuid4()
    key = f"budget:{tid}:{__import__('datetime').datetime.now(__import__('datetime').UTC).strftime('%Y-%m')}"
    g.check_and_reserve(tid, 500, "starter")  # reserved 500
    assert int(c.get(key) or 0) == 500
    g.record_usage(tid, 120, "starter", reserved=500)  # actual was only 120
    assert int(c.get(key) or 0) == 120


def test_settle_release_on_failure_returns_to_zero(guard) -> None:
    g, c = guard
    tid = uuid.uuid4()
    key = f"budget:{tid}:{__import__('datetime').datetime.now(__import__('datetime').UTC).strftime('%Y-%m')}"
    g.check_and_reserve(tid, 500, "starter")
    g.record_usage(tid, 0, "starter", reserved=500)  # call failed — release
    assert int(c.get(key) or 0) == 0


def test_second_reserve_blocked_by_first_reservation(guard) -> None:
    """Concurrency: two requests reserving 700 each against a 1000 cap —
    the second must fail even though actual usage hasn't settled yet."""
    g, _ = guard
    tid = uuid.uuid4()
    assert g.check_and_reserve(tid, 700, "starter") is True
    assert g.check_and_reserve(tid, 700, "starter") is False


def test_remaining_reflects_reservation(guard) -> None:
    g, _ = guard
    tid = uuid.uuid4()
    g.check_and_reserve(tid, 300, "starter")
    assert g.remaining(tid, "starter") == 700
