from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..contracts import PolicyResult
from .claims_gate import claims_gate


class PolicyGate(ABC):
    """Base policy gate composing the global claims_gate with per-channel rules."""

    @abstractmethod
    def channel_rules(self, payload: dict[str, Any]) -> PolicyResult:
        """Per-channel ToS rules; override in concrete adapters."""
        ...

    def check(self, payload: dict[str, Any]) -> PolicyResult:
        text = self._extract_text(payload)
        base = claims_gate(text)
        ch = self.channel_rules(payload)
        blocked = list(base.blocked_reasons) + list(ch.blocked_reasons)
        warnings = list(base.warnings) + list(ch.warnings)
        return PolicyResult(passed=not blocked, blocked_reasons=blocked, warnings=warnings)

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        parts: list[str] = []
        for key in ("title", "headline", "body", "caption", "meta", "description", "text"):
            v = payload.get(key)
            if isinstance(v, str):
                parts.append(v)
        return " ".join(parts)
