from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from prachar_shared.contracts import AudienceSpec, VisibilityScore


def test_visibility_score_compute_weighted_sum() -> None:
    score = VisibilityScore.compute(
        organic_rank_index=80.0,
        ai_citation_rate=60.0,
        social_reach_index=40.0,
        paid_efficiency=50.0,
        momentum=30.0,
        week=date(2024, 1, 1),
    )
    expected = 80 * 0.35 + 60 * 0.15 + 40 * 0.25 + 50 * 0.15 + 30 * 0.10
    assert score.overall == pytest.approx(expected, rel=1e-3)
    assert score.breakdown["organic_rank_index"] == 80.0
    assert 0.0 <= score.overall <= 100.0


def test_audience_spec_rejects_bad_geo() -> None:
    with pytest.raises(ValidationError):
        AudienceSpec(geo=["bad-code"])


def test_audience_spec_accepts_good_geo() -> None:
    spec = AudienceSpec(geo=["US-NY", "IN-MH"])
    assert spec.geo == ["US-NY", "IN-MH"]
