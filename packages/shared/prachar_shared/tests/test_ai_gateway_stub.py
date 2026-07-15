from __future__ import annotations

import os
import uuid
from typing import Any

import pytest

from prachar_shared.ai_gateway import AIGateway, Completion, Tier
from prachar_shared.ai_gateway.budget import BudgetGuard
from prachar_shared.ai_gateway.cache import Cache


class _FakeCache(Cache):
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._store[key] = value


class _FakeBudget(BudgetGuard):
    def __init__(self) -> None:
        self.used = 0

    def check_and_reserve(self, tenant_id, tokens: int, plan: str) -> bool:
        return True

    def record_usage(self, tenant_id, tokens: int, plan: str) -> None:
        self.used += tokens

    def remaining(self, tenant_id, plan: str) -> int:
        return 10**9


@pytest.fixture(autouse=True)
def _no_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    # reset cached settings
    from prachar_shared.config import get_settings

    get_settings.cache_clear()


def _gateway() -> AIGateway:
    return AIGateway(cache=_FakeCache(), budget=_FakeBudget())


def test_stub_mode_returns_stub_model() -> None:
    gw = _gateway()
    comp = gw.complete(
        "write a caption about shoes",
        tier=Tier.small,
        tenant_id=uuid.uuid4(),
        plan="starter",
    )
    assert isinstance(comp, Completion)
    assert comp.model == "stub"
    assert comp.text.startswith("[stub]")


def test_stub_deterministic_for_same_prompt() -> None:
    gw = _gateway()
    c1 = gw.complete("same prompt here", tenant_id=uuid.uuid4(), plan="starter")
    c2 = gw.complete("same prompt here", tenant_id=uuid.uuid4(), plan="starter")
    assert c1.text == c2.text


def test_second_call_is_cached() -> None:
    gw = _gateway()
    first = gw.complete("cached prompt xyz", tenant_id=uuid.uuid4(), plan="starter")
    second = gw.complete("cached prompt xyz", tenant_id=uuid.uuid4(), plan="starter")
    assert not first.cached
    assert second.cached
    assert first.text == second.text
