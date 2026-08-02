from __future__ import annotations

"""Tests for the CampaignPerformance model (P4.1).

Run with: .venv/bin/python -m pytest apps/api/prachar_api/tests/test_campaign_performance_model.py -q
"""
import datetime as _dt
import uuid


def test_campaign_performance_importable():
    """The model can be imported from prachar_api.models.tables."""
    from prachar_api.models.tables import CampaignPerformance

    assert CampaignPerformance.__tablename__ == "campaign_performance"


def test_campaign_performance_instantiation_with_all_fields():
    """CampaignPerformance can be instantiated with all fields set."""
    from prachar_api.models.tables import CampaignPerformance

    campaign_id = uuid.uuid4()
    perf = CampaignPerformance(
        campaign_id=campaign_id,
        date=_dt.date(2026, 7, 25),
        impressions=10_000,
        clicks=500,
        conversions=25,
        spend=1500.00,
        revenue=4500.00,
        ctr=0.05,
        cpa=60.0,
        roas=3.0,
        channel="google_ads",
    )

    assert perf.campaign_id == campaign_id
    assert perf.date == _dt.date(2026, 7, 25)
    assert perf.impressions == 10_000
    assert perf.clicks == 500
    assert perf.conversions == 25
    assert float(perf.spend) == 1500.00
    assert float(perf.revenue) == 4500.00
    assert perf.ctr == 0.05
    assert perf.cpa == 60.0
    assert perf.roas == 3.0
    assert perf.channel == "google_ads"


def test_campaign_performance_defaults():
    """Defaults are declared correctly on the model columns.

    SQLAlchemy applies `default=` at flush/insert time, so we verify the
    column-level default callables/values rather than instance attributes
    (which are None until flushed).
    """
    from prachar_api.models.tables import CampaignPerformance

    table = CampaignPerformance.__table__

    def col_default(name):
        default = table.c[name].default
        if default is None:
            return None
        if default.is_scalar:
            return default.arg
        if default.is_callable:
            return default.arg(None)
        return default.arg

    assert col_default("impressions") == 0
    assert col_default("clicks") == 0
    assert col_default("conversions") == 0
    assert float(col_default("spend")) == 0
    assert float(col_default("revenue")) == 0
    assert col_default("ctr") == 0.0
    assert col_default("cpa") == 0.0
    assert col_default("roas") == 0.0
    # channel is optional (nullable, no default)
    assert table.c["channel"].nullable is True
