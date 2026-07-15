from __future__ import annotations

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)

CLAMP = 0.20


@dataclass(frozen=True)
class NetworkStats:
    network: str
    spend_7d: float
    conversions_7d: int
    cpa: float
    roas: float


def _softmax(scores: list[float]) -> list[float]:
    m = max(scores) if scores else 0.0
    exps = [math.exp(s - m) for s in scores]
    total = sum(exps)
    if total <= 0:
        n = len(scores)
        return [1.0 / n] * n if n else []
    return [e / total for e in exps]


def reallocate(
    stats: list[NetworkStats],
    *,
    max_cpa: float | None = None,
) -> dict[str, float]:
    if not stats:
        return {}
    current_total = sum(s.spend_7d / 7.0 for s in stats)
    if current_total <= 0:
        equal = sum(s.spend_7d for s in stats) / 7.0 / len(stats) if stats else 0.0
        return {s.network: equal for s in stats}

    current_daily = {s.network: s.spend_7d / 7.0 for s in stats}

    # Score: lower CPA is better. Use inverse CPA (add epsilon to avoid div0).
    eps = 1e-6
    scores = []
    for s in stats:
        if max_cpa is not None and s.cpa > max_cpa and s.cpa > 0:
            scores.append(-1e9)  # effectively zero allocation
        else:
            scores.append(1.0 / (s.cpa + eps))

    weights = _softmax(scores)
    target_total = current_total
    target_daily = {s.network: w * target_total for s, w in zip(stats, weights, strict=True)}

    # Clamp ±20% of current daily budget; redistribute leftover iteratively.
    result: dict[str, float] = {}
    clamped: set[str] = set()
    remaining = target_total
    for s in stats:
        cur = current_daily[s.network]
        lo = cur * (1.0 - CLAMP)
        hi = cur * (1.0 + CLAMP)
        tgt = target_daily[s.network]
        if tgt < lo:
            result[s.network] = lo
            clamped.add(s.network)
            remaining -= lo
        elif tgt > hi:
            result[s.network] = hi
            clamped.add(s.network)
            remaining -= hi
        else:
            result[s.network] = tgt
            remaining -= tgt

    # Redistribute leftover among non-clamped networks, respecting clamps.
    for _ in range(10):
        if abs(remaining) < 1e-9:
            break
        free = [s for s in stats if s.network not in clamped]
        if not free:
            break
        per = remaining / len(free)
        progressed = False
        for s in free:
            cur = current_daily[s.network]
            lo = cur * (1.0 - CLAMP)
            hi = cur * (1.0 + CLAMP)
            new_val = result[s.network] + per
            if new_val < lo:
                result[s.network] = lo
                clamped.add(s.network)
                remaining -= lo - result[s.network]
                progressed = True
            elif new_val > hi:
                result[s.network] = hi
                clamped.add(s.network)
                remaining -= hi - result[s.network]
                progressed = True
            else:
                result[s.network] = new_val
                remaining -= per
                progressed = True
        if not progressed:
            break

    # Guardrail: pause networks exceeding max_cpa for 3 consecutive days.
    # S0: we only have a snapshot; if cpa > max_cpa, set budget to 0 and
    # redistribute the freed budget proportionally to remaining weights.
    if max_cpa is not None:
        paused = [s for s in stats if s.cpa > max_cpa]
        if paused:
            freed = sum(result[s.network] for s in paused)
            for s in paused:
                result[s.network] = 0.0
            active = [s for s in stats if s.network not in {p.network for p in paused}]
            if active and freed > 0:
                aw = _softmax([1.0 / (s.cpa + eps) for s in active])
                for s, w in zip(active, aw, strict=True):
                    result[s.network] += freed * w

    return result
