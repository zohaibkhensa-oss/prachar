from __future__ import annotations

import re

from ..contracts import PolicyResult

# Hard guarantees — block.
_HARD_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"guaranteed\s*#?\s*1", re.IGNORECASE), "guaranteed #1"),
    (re.compile(r"guaranteed\s+results?", re.IGNORECASE), "guaranteed results"),
    (re.compile(r"100\s*%\s*guaranteed", re.IGNORECASE), "100% guaranteed"),
    (re.compile(r"guaranteed\s+return", re.IGNORECASE), "guaranteed return"),
    (re.compile(r"risk[-\s]?free\s+investment", re.IGNORECASE), "risk-free investment"),
]

# Soft medical claims — warn.
_SOFT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bcures?\b", re.IGNORECASE), "medical claim: 'cure'"),
    (re.compile(r"\btreats?\b", re.IGNORECASE), "medical claim: 'treat'"),
    (re.compile(r"\bdiagnos(e|es|ed|ing)\b", re.IGNORECASE), "medical claim: 'diagnose'"),
]


def claims_gate(text: str) -> PolicyResult:
    """Flag forbidden phrases per spec compliance guardrails.

    Hard guarantees (guaranteed #1 / guaranteed results / 100% guaranteed) → blocked.
    Medical/financial claims (cure, treat, diagnose, guaranteed return, risk-free investment) → warnings.
    """
    blocked: list[str] = []
    warnings: list[str] = []

    for pat, label in _HARD_PATTERNS:
        if pat.search(text):
            blocked.append(f"forbidden guarantee: {label}")

    for pat, label in _SOFT_PATTERNS:
        if pat.search(text):
            warnings.append(label)

    return PolicyResult(
        passed=not blocked,
        blocked_reasons=blocked,
        warnings=warnings,
    )
