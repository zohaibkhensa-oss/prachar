from __future__ import annotations

from prachar_shared.policy.claims_gate import claims_gate


def test_guaranteed_number_one_blocked() -> None:
    result = claims_gate("We will get you guaranteed #1 ranking on Google")
    assert not result.passed
    assert any("guarantee" in r for r in result.blocked_reasons)


def test_benign_copy_passes() -> None:
    result = claims_gate("we help businesses grow with data-driven marketing")
    assert result.passed
    assert result.blocked_reasons == []


def test_risk_free_investment_blocked() -> None:
    result = claims_gate("Put your money in our risk-free investment plan")
    assert not result.passed
    assert any("risk-free investment" in r for r in result.blocked_reasons)


def test_medical_soft_warning_only() -> None:
    result = claims_gate("This supplement cures fatigue and treats joint pain")
    assert result.passed
    assert any("cure" in w for w in result.warnings)
    assert any("treat" in w for w in result.warnings)
