from __future__ import annotations

from prachar_workers.ads.allocator import NetworkStats, reallocate


def _stats(cpas: list[float], budgets: list[float]) -> list[NetworkStats]:
    out: list[NetworkStats] = []
    for i, (cpa, b) in enumerate(zip(cpas, budgets, strict=True)):
        spend = b * 7.0
        conv = int(round(spend / cpa)) if cpa > 0 else 0
        out.append(
            NetworkStats(
                network=f"net{i}",
                spend_7d=spend,
                conversions_7d=conv,
                cpa=cpa,
                roas=0.0,
            )
        )
    return out


def test_reallocate_shifts_toward_lowest_cpa():
    stats = _stats([10.0, 20.0, 40.0], [100.0, 100.0, 100.0])
    result = reallocate(stats)
    assert set(result) == {"net0", "net1", "net2"}
    # lowest CPA network should get the largest share
    assert result["net0"] >= result["net1"] >= result["net2"]


def test_total_budget_unchanged():
    stats = _stats([10.0, 20.0, 40.0], [100.0, 100.0, 100.0])
    result = reallocate(stats)
    total_in = sum(s.spend_7d / 7.0 for s in stats)
    total_out = sum(result.values())
    assert abs(total_in - total_out) < 1e-6


def test_clamp_within_20_percent():
    stats = _stats([10.0, 20.0, 40.0], [100.0, 100.0, 100.0])
    result = reallocate(stats)
    for s in stats:
        cur = s.spend_7d / 7.0
        lo = cur * 0.80
        hi = cur * 1.20
        assert lo - 1e-6 <= result[s.network] <= hi + 1e-6, (
            f"{s.network} moved out of +-20%: {result[s.network]} vs [{lo},{hi}]"
        )
