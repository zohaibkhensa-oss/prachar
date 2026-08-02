"""Performance ingestion worker (P4.2).

Pulls daily performance metrics from each channel adapter for every active
campaign and upserts the aggregated numbers into ``CampaignPerformance``.

Design notes
------------
* One Celery task ``pull_daily_performance`` iterates over all active
  campaigns.  For each campaign it looks up the brand's *connected* channels
  (``Connection`` rows whose ``channel`` matches the campaign's network and
  whose ``status`` is ``active``) and calls the matching ``AdNetworkAdapter``
  to fetch canonical ``MetricEvent`` rows.
* Failures are isolated **per channel** — a single adapter blowing up is
  logged and the loop continues with the next channel / campaign.
* Derived metrics (``ctr``, ``cpa``, ``roas``) are computed with safe division
  so that zero denominators never raise.
* Upsert is keyed on ``(campaign_id, date, channel)`` — the unique constraint
  declared on ``CampaignPerformance``.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any, Callable, Iterable, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from prachar_workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Map canonical MetricEvent metric names -> CampaignPerformance columns.
METRIC_MAP: dict[str, str] = {
    "impressions": "impressions",
    "clicks": "clicks",
    "conversions": "conversions",
    "cost": "spend",
    "revenue": "revenue",
}

AGG_KEYS = ("impressions", "clicks", "conversions", "spend", "revenue")

# ─── Organic / Meta channel constants ─────────────────────────────────────────
GBP_CHANNEL = "gmb"

# Channels routed to the Meta ingestion helper (ads + organic).
META_CHANNELS: frozenset[str] = frozenset({"meta_ads", "facebook", "instagram"})

# Additional organic / paid channel constants (C.1.3–C.1.6).
LINKEDIN_CHANNEL = "linkedin"
WHATSAPP_CHANNEL = "whatsapp"
YOUTUBE_CHANNEL = "youtube"
GOOGLE_ADS_CHANNEL = "google_ads"

# Channels routed to the dedicated Google Ads ingestion helper.
GOOGLE_ADS_CHANNELS: frozenset[str] = frozenset({GOOGLE_ADS_CHANNEL})

# GBP Insights metric names -> CampaignPerformance columns.
# The CampaignPerformance table only exposes impressions/clicks/conversions/
# spend/revenue, so GBP-specific signals are mapped to the closest canonical
# bucket:
#   search_impressions  -> impressions  (discovery surface)
#   directions_requests -> clicks       (intent-rich engagement)
#   calls               -> conversions  (strongest offline conversion signal)
#   photo_views         -> revenue      (engagement depth proxy; spend=0 organic)
GBP_METRIC_MAP: dict[str, str] = {
    "search_impressions": "impressions",
    "directions_requests": "clicks",
    "calls": "conversions",
    "photo_views": "revenue",
}

# Organic Facebook/Instagram Insights metric names -> CampaignPerformance columns.
# Reach is intentionally not mapped to avoid double-counting with impressions.
META_ORGANIC_METRIC_MAP: dict[str, str] = {
    "fb_page_impressions": "impressions",
    "ig_impressions": "impressions",
    "fb_page_post_engagements": "clicks",
    "ig_profile_views": "clicks",
    "fb_page_fan_adds": "conversions",
}

# LinkedIn organic share statistics -> CampaignPerformance columns.
# The LinkedInAdapter emits impressions, clicks, likes and comments.  Likes are
# the strongest organic engagement signal (mapped to conversions) and comments
# represent deeper engagement (mapped to revenue as a depth proxy; spend=0).
LINKEDIN_METRIC_MAP: dict[str, str] = {
    "impressions": "impressions",
    "clicks": "clicks",
    "likes": "conversions",
    "comments": "revenue",
}

# WhatsApp Business message insights -> CampaignPerformance columns.
# The WhatsAppAdapter emits delivered / read / failed.  Delivered maps to
# impressions (reach), read to clicks (engagement).  ``sent`` and ``replied``
# are included for forward-compatibility if the adapter is later enhanced.
WHATSAPP_METRIC_MAP: dict[str, str] = {
    "sent": "impressions",
    "delivered": "impressions",
    "read": "clicks",
    "replied": "conversions",
}

# YouTube Analytics -> CampaignPerformance columns.
# The YouTubeAdapter emits views, impressions, ctr and watch_time_minutes.
# Thumbnail impressions are the discovery surface (-> impressions); views are
# the action of watching (-> clicks); watch time is the engagement-depth proxy
# (-> revenue; organic so spend=0).  ``ctr`` is intentionally not mapped — the
# derived ``ctr`` is recomputed in :func:`compute_derived` as views/impressions.
YOUTUBE_METRIC_MAP: dict[str, str] = {
    "impressions": "impressions",
    "views": "clicks",
    "watch_time_minutes": "revenue",
}


# ─── Small store abstraction (thin wrapper around the ORM session) ────────────


class PerformanceStore:
    """Read/write helper around ``CampaignPerformance`` rows.

    Wrapped in a class so the worker logic can be unit-tested with a fake
    store without standing up a real database.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def find(
        self, campaign_id: Any, target_date: date, channel: str
    ) -> Any | None:
        from prachar_api.models.tables import CampaignPerformance

        return self.session.execute(
            select(CampaignPerformance).where(
                CampaignPerformance.campaign_id == campaign_id,
                CampaignPerformance.date == target_date,
                CampaignPerformance.channel == channel,
            )
        ).first()

    def add(self, perf: Any) -> None:
        self.session.add(perf)

    def flush(self) -> None:
        self.session.flush()


# ─── Pure helpers ─────────────────────────────────────────────────────────────


def _safe_div(numerator: float, denominator: float) -> float:
    """Division that returns ``0.0`` when the denominator is zero."""
    if not denominator:
        return 0.0
    return numerator / denominator


def compute_derived(
    impressions: int, clicks: int, conversions: int, spend: float, revenue: float
) -> tuple[float, float, float]:
    """Return ``(ctr, cpa, roas)`` with division-by-zero protection."""
    ctr = _safe_div(clicks, impressions)
    cpa = _safe_div(spend, conversions)
    roas = _safe_div(revenue, spend)
    return round(ctr, 6), round(cpa, 6), round(roas, 6)


def _event_field(ev: Any, name: str) -> Any:
    if isinstance(ev, dict):
        return ev.get(name)
    return getattr(ev, name, None)


def aggregate_events(
    events: Iterable[Any],
    target_date: date,
    metric_map: dict[str, str] | None = None,
) -> dict[str, float]:
    """Sum canonical ``MetricEvent`` rows for ``target_date`` into a metric dict.

    Events whose ``ts`` does not fall on ``target_date`` are ignored.  Unknown
    metric names (not present in ``metric_map``) are ignored.  Returns a dict
    with the keys in ``AGG_KEYS``.

    ``metric_map`` defaults to :data:`METRIC_MAP` (the canonical ads mapping).
    Pass a channel-specific map (e.g. :data:`GBP_METRIC_MAP`) to translate
    organic insight metric names into CampaignPerformance columns.
    """
    if metric_map is None:
        metric_map = METRIC_MAP
    agg: dict[str, float] = {k: 0 for k in AGG_KEYS}
    for ev in events:
        metric = _event_field(ev, "metric")
        value = _event_field(ev, "value")
        ts = _event_field(ev, "ts")
        if metric is None or value is None or ts is None:
            continue
        # Normalise the timestamp to a date.
        if hasattr(ts, "date"):
            ev_date = ts.date()
        else:
            try:
                ev_date = date.fromisoformat(str(ts)[:10])
            except ValueError:
                continue
        if ev_date != target_date:
            continue
        key = metric_map.get(str(metric))
        if key is None:
            continue
        agg[key] += float(value)
    return agg


def _stub_tokens() -> Any:
    """Build a placeholder ``TokenSet`` (decryption of oauth_tokens_enc not yet wired)."""
    from prachar_shared.contracts import TokenSet

    return TokenSet(access_token="stub", expires_at=datetime.now(UTC) + timedelta(hours=1))


# ─── Upsert ───────────────────────────────────────────────────────────────────


def upsert_performance(
    store: PerformanceStore,
    campaign_id: Any,
    target_date: date,
    channel: str,
    agg: dict[str, float],
) -> Any:
    """Insert or update a ``CampaignPerformance`` row for the given key.

    Returns the persisted row (existing or newly added).
    """
    from prachar_api.models.tables import CampaignPerformance

    impressions = int(agg.get("impressions", 0))
    clicks = int(agg.get("clicks", 0))
    conversions = int(agg.get("conversions", 0))
    spend = float(agg.get("spend", 0.0))
    revenue = float(agg.get("revenue", 0.0))
    ctr, cpa, roas = compute_derived(impressions, clicks, conversions, spend, revenue)

    existing = store.find(campaign_id, target_date, channel)
    if existing is not None:
        existing.impressions = impressions
        existing.clicks = clicks
        existing.conversions = conversions
        existing.spend = spend
        existing.revenue = revenue
        existing.ctr = ctr
        existing.cpa = cpa
        existing.roas = roas
        return existing

    perf = CampaignPerformance(
        campaign_id=campaign_id,
        date=target_date,
        impressions=impressions,
        clicks=clicks,
        conversions=conversions,
        spend=spend,
        revenue=revenue,
        ctr=ctr,
        cpa=cpa,
        roas=roas,
        channel=channel,
    )
    store.add(perf)
    store.flush()
    return perf


# ─── Adapter resolution ───────────────────────────────────────────────────────


def get_ads_adapter(network: str) -> Any:
    """Resolve an ``AdNetworkAdapter`` for ``network`` via the shared registry."""
    from prachar_shared.adapters.registry import get_ads

    return get_ads(network)


def _default_organic_factory(channel: str) -> Any:
    """Resolve an organic ``ChannelAdapter`` for ``channel`` via the registry."""
    from prachar_shared.adapters.registry import get_organic

    return get_organic(channel)


def _call_metrics(adapter: Any, tokens: Any, since: datetime) -> list[Any]:
    """Invoke ``adapter.metrics`` supporting both sync and async adapters.

    Organic adapters (Facebook/Instagram) expose an ``async def metrics`` while
    the GMB adapter is synchronous.  The Celery worker is synchronous, so any
    awaitable result is resolved with ``asyncio.run``.
    """
    result = adapter.metrics(tokens, since)
    if inspect.isawaitable(result):
        result = asyncio.run(result)
    return result


def _result_ok(channel: str, agg: dict[str, float]) -> dict[str, Any]:
    return {
        "channel": channel,
        "status": "ok",
        "impressions": agg["impressions"],
        "clicks": agg["clicks"],
        "conversions": agg["conversions"],
        "spend": agg["spend"],
        "revenue": agg["revenue"],
    }


# ─── Google Business Profile ingestion (C.1.1) ────────────────────────────────


def ingest_gbp_metrics(
    store: PerformanceStore,
    campaign: Any,
    connection: Any,
    target_date: date,
    adapter: Any | None = None,
    tokens: Any | None = None,
) -> dict[str, Any]:
    """Pull Google Business Profile insights for a campaign and upsert them.

    GBP is an *organic* channel surfaced through :class:`GMBAdapter.metrics`.
    The adapter emits ``MetricEvent`` rows for search impressions, directions
    requests, calls and photo views; these are mapped to CampaignPerformance
    columns via :data:`GBP_METRIC_MAP`.

    Graceful skip: when ``connection`` is ``None`` (GBP not connected for the
    brand) the function returns a ``skipped`` result without touching the
    adapter or DB, so the worker never crashes on a missing OAuth token.
    """
    campaign_id = getattr(campaign, "id", None)

    if connection is None:
        logger.info(
            "gbp ingest skipped: not connected (campaign=%s)", campaign_id
        )
        return {
            "channel": GBP_CHANNEL,
            "status": "skipped",
            "reason": "not_connected",
        }

    if adapter is None:
        try:
            adapter = _default_organic_factory(GBP_CHANNEL)
        except KeyError as exc:
            logger.warning("gbp adapter not registered: %s", exc)
            return {
                "channel": GBP_CHANNEL,
                "status": "skipped",
                "reason": "adapter_not_registered",
            }

    if tokens is None:
        tokens = _stub_tokens()

    since = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
    try:
        events = _call_metrics(adapter, tokens, since)
        agg = aggregate_events(events, target_date, GBP_METRIC_MAP)
        upsert_performance(store, campaign_id, target_date, GBP_CHANNEL, agg)
        logger.info(
            "gbp ingest ok campaign=%s impressions=%s clicks=%s conversions=%s",
            campaign_id,
            agg["impressions"],
            agg["clicks"],
            agg["conversions"],
        )
        return _result_ok(GBP_CHANNEL, agg)
    except Exception as exc:  # noqa: BLE001 - per-channel isolation
        logger.warning(
            "gbp ingest failed campaign=%s: %s", campaign_id, exc
        )
        return {
            "channel": GBP_CHANNEL,
            "status": "error",
            "error": str(exc),
        }


# ─── Meta (Facebook + Instagram) ingestion (C.1.2) ────────────────────────────


def ingest_meta_metrics(
    store: PerformanceStore,
    campaign: Any,
    connection: Any,
    target_date: date,
    ads_adapter_factory: Callable[[str], Any] = get_ads_adapter,
    organic_adapter_factory: Callable[[str], Any] | None = None,
    tokens: Any | None = None,
) -> dict[str, Any]:
    """Pull Meta (Facebook + Instagram) metrics for a campaign and upsert them.

    Handles three Meta surfaces, each upserted as its own CampaignPerformance
    row keyed by channel:

    * ``meta_ads``   — paid ads via :class:`MetaAdsAdapter.stats` (impressions,
      clicks, conversions, cost/spend).  Requires ``network_campaign_id``.
    * ``facebook``   — organic page insights via :class:`FacebookAdapter.metrics`
      (page impressions, engagements, fan adds).
    * ``instagram``  — organic profile insights via :class:`InstagramAdapter.metrics`
      (impressions, profile views).

    Graceful skip: when ``connection`` is ``None`` (Meta not connected) the
    function returns a ``skipped`` result without touching any adapter, so a
    missing OAuth token never crashes the worker.
    """
    campaign_id = getattr(campaign, "id", None)
    channel = getattr(connection, "channel", None) if connection is not None else None

    if connection is None or channel is None:
        logger.info(
            "meta ingest skipped: not connected (campaign=%s)", campaign_id
        )
        return {
            "channel": "meta",
            "status": "skipped",
            "reason": "not_connected",
        }

    if organic_adapter_factory is None:
        organic_adapter_factory = _default_organic_factory

    if tokens is None:
        tokens = _stub_tokens()

    since = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
    ncid = getattr(campaign, "network_campaign_id", None)

    try:
        if channel == "meta_ads":
            if not ncid:
                return {
                    "channel": "meta_ads",
                    "status": "skipped",
                    "reason": "no_network_campaign_id",
                }
            adapter = ads_adapter_factory("meta_ads")
            events = adapter.stats(tokens, str(ncid), since)
            agg = aggregate_events(events, target_date, METRIC_MAP)
            upsert_performance(store, campaign_id, target_date, "meta_ads", agg)
            logger.info(
                "meta_ads ingest ok campaign=%s impressions=%s spend=%s",
                campaign_id,
                agg["impressions"],
                agg["spend"],
            )
            return _result_ok("meta_ads", agg)

        if channel in ("facebook", "instagram"):
            adapter = organic_adapter_factory(str(channel))
            events = _call_metrics(adapter, tokens, since)
            agg = aggregate_events(events, target_date, META_ORGANIC_METRIC_MAP)
            upsert_performance(
                store, campaign_id, target_date, str(channel), agg
            )
            logger.info(
                "%s ingest ok campaign=%s impressions=%s clicks=%s",
                channel,
                campaign_id,
                agg["impressions"],
                agg["clicks"],
            )
            return _result_ok(str(channel), agg)

        return {
            "channel": str(channel),
            "status": "skipped",
            "reason": "not_meta_channel",
        }
    except Exception as exc:  # noqa: BLE001 - per-channel isolation
        logger.warning(
            "meta ingest failed campaign=%s channel=%s: %s",
            campaign_id,
            channel,
            exc,
        )
        return {
            "channel": str(channel),
            "status": "error",
            "error": str(exc),
        }


# ─── LinkedIn ingestion (C.1.3) ───────────────────────────────────────────────


def ingest_linkedin_metrics(
    store: PerformanceStore,
    campaign: Any,
    connection: Any,
    target_date: date,
    adapter: Any | None = None,
    tokens: Any | None = None,
) -> dict[str, Any]:
    """Pull LinkedIn organic share statistics for a campaign and upsert them.

    LinkedIn is an *organic* channel surfaced through
    :class:`LinkedInAdapter.metrics`.  The adapter emits ``MetricEvent`` rows
    for impressions, clicks, likes and comments; these are mapped to
    CampaignPerformance columns via :data:`LINKEDIN_METRIC_MAP`.

    Graceful skip: when ``connection`` is ``None`` (LinkedIn not connected for
    the brand) the function returns a ``skipped`` result without touching the
    adapter or DB, so the worker never crashes on a missing OAuth token.
    """
    campaign_id = getattr(campaign, "id", None)

    if connection is None:
        logger.info(
            "linkedin ingest skipped: not connected (campaign=%s)", campaign_id
        )
        return {
            "channel": LINKEDIN_CHANNEL,
            "status": "skipped",
            "reason": "not_connected",
        }

    if adapter is None:
        try:
            adapter = _default_organic_factory(LINKEDIN_CHANNEL)
        except KeyError as exc:
            logger.warning("linkedin adapter not registered: %s", exc)
            return {
                "channel": LINKEDIN_CHANNEL,
                "status": "skipped",
                "reason": "adapter_not_registered",
            }

    if tokens is None:
        tokens = _stub_tokens()

    since = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
    try:
        events = _call_metrics(adapter, tokens, since)
        agg = aggregate_events(events, target_date, LINKEDIN_METRIC_MAP)
        upsert_performance(store, campaign_id, target_date, LINKEDIN_CHANNEL, agg)
        logger.info(
            "linkedin ingest ok campaign=%s impressions=%s clicks=%s conversions=%s",
            campaign_id,
            agg["impressions"],
            agg["clicks"],
            agg["conversions"],
        )
        return _result_ok(LINKEDIN_CHANNEL, agg)
    except Exception as exc:  # noqa: BLE001 - per-channel isolation
        logger.warning(
            "linkedin ingest failed campaign=%s: %s", campaign_id, exc
        )
        return {
            "channel": LINKEDIN_CHANNEL,
            "status": "error",
            "error": str(exc),
        }


# ─── WhatsApp Business ingestion (C.1.4) ─────────────────────────────────────


def ingest_whatsapp_metrics(
    store: PerformanceStore,
    campaign: Any,
    connection: Any,
    target_date: date,
    adapter: Any | None = None,
    tokens: Any | None = None,
) -> dict[str, Any]:
    """Pull WhatsApp Business message insights for a campaign and upsert them.

    WhatsApp is an *organic* channel surfaced through
    :class:`WhatsAppAdapter.metrics`.  The adapter emits ``MetricEvent`` rows
    for delivered, read and failed messages; these are mapped to
    CampaignPerformance columns via :data:`WHATSAPP_METRIC_MAP`
    (delivered -> impressions, read -> clicks).

    Graceful skip: when ``connection`` is ``None`` (WhatsApp not connected for
    the brand) the function returns a ``skipped`` result without touching the
    adapter or DB, so the worker never crashes on a missing token.
    """
    campaign_id = getattr(campaign, "id", None)

    if connection is None:
        logger.info(
            "whatsapp ingest skipped: not connected (campaign=%s)", campaign_id
        )
        return {
            "channel": WHATSAPP_CHANNEL,
            "status": "skipped",
            "reason": "not_connected",
        }

    if adapter is None:
        try:
            adapter = _default_organic_factory(WHATSAPP_CHANNEL)
        except KeyError as exc:
            logger.warning("whatsapp adapter not registered: %s", exc)
            return {
                "channel": WHATSAPP_CHANNEL,
                "status": "skipped",
                "reason": "adapter_not_registered",
            }

    if tokens is None:
        tokens = _stub_tokens()

    since = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
    try:
        events = _call_metrics(adapter, tokens, since)
        agg = aggregate_events(events, target_date, WHATSAPP_METRIC_MAP)
        upsert_performance(store, campaign_id, target_date, WHATSAPP_CHANNEL, agg)
        logger.info(
            "whatsapp ingest ok campaign=%s impressions=%s clicks=%s",
            campaign_id,
            agg["impressions"],
            agg["clicks"],
        )
        return _result_ok(WHATSAPP_CHANNEL, agg)
    except Exception as exc:  # noqa: BLE001 - per-channel isolation
        logger.warning(
            "whatsapp ingest failed campaign=%s: %s", campaign_id, exc
        )
        return {
            "channel": WHATSAPP_CHANNEL,
            "status": "error",
            "error": str(exc),
        }


# ─── Google Ads ingestion (C.1.5) ────────────────────────────────────────────


def ingest_google_ads_metrics(
    store: PerformanceStore,
    campaign: Any,
    connection: Any,
    target_date: date,
    ads_adapter_factory: Callable[[str], Any] = get_ads_adapter,
    tokens: Any | None = None,
) -> dict[str, Any]:
    """Pull Google Ads performance for a campaign and upsert them.

    Google Ads is a *paid* channel surfaced through
    :class:`GoogleAdsAdapter.stats`.  The adapter emits canonical
    ``MetricEvent`` rows (impressions, clicks, cost, conversions) which are
    mapped via the default :data:`METRIC_MAP` (cost -> spend).  ROAS is derived
    in :func:`compute_derived`.

    Graceful skip: when ``connection`` is ``None`` (Google Ads not connected)
    the function returns a ``skipped`` result without touching the adapter, so
    a missing OAuth token never crashes the worker.  A campaign without a
    ``network_campaign_id`` is also skipped (no ad to query).
    """
    campaign_id = getattr(campaign, "id", None)

    if connection is None:
        logger.info(
            "google_ads ingest skipped: not connected (campaign=%s)", campaign_id
        )
        return {
            "channel": GOOGLE_ADS_CHANNEL,
            "status": "skipped",
            "reason": "not_connected",
        }

    ncid = getattr(campaign, "network_campaign_id", None)
    if not ncid:
        return {
            "channel": GOOGLE_ADS_CHANNEL,
            "status": "skipped",
            "reason": "no_network_campaign_id",
        }

    if tokens is None:
        tokens = _stub_tokens()

    since = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
    try:
        adapter = ads_adapter_factory(GOOGLE_ADS_CHANNEL)
        events = adapter.stats(tokens, str(ncid), since)
        agg = aggregate_events(events, target_date, METRIC_MAP)
        upsert_performance(store, campaign_id, target_date, GOOGLE_ADS_CHANNEL, agg)
        logger.info(
            "google_ads ingest ok campaign=%s impressions=%s spend=%s",
            campaign_id,
            agg["impressions"],
            agg["spend"],
        )
        return _result_ok(GOOGLE_ADS_CHANNEL, agg)
    except Exception as exc:  # noqa: BLE001 - per-channel isolation
        logger.warning(
            "google_ads ingest failed campaign=%s: %s", campaign_id, exc
        )
        return {
            "channel": GOOGLE_ADS_CHANNEL,
            "status": "error",
            "error": str(exc),
        }


# ─── YouTube ingestion (C.1.6) ───────────────────────────────────────────────


def ingest_youtube_metrics(
    store: PerformanceStore,
    campaign: Any,
    connection: Any,
    target_date: date,
    adapter: Any | None = None,
    tokens: Any | None = None,
) -> dict[str, Any]:
    """Pull YouTube Analytics for a campaign and upsert them.

    YouTube is an *organic* channel surfaced through
    :class:`YouTubeAdapter.metrics`.  The adapter emits ``MetricEvent`` rows
    for views, impressions, ctr and watch time; these are mapped to
    CampaignPerformance columns via :data:`YOUTUBE_METRIC_MAP`
    (thumbnail impressions -> impressions, views -> clicks, watch time ->
    revenue).  The derived ``ctr`` is recomputed as views/impressions.

    Graceful skip: when ``connection`` is ``None`` (YouTube not connected for
    the brand) the function returns a ``skipped`` result without touching the
    adapter or DB, so the worker never crashes on a missing OAuth token.
    """
    campaign_id = getattr(campaign, "id", None)

    if connection is None:
        logger.info(
            "youtube ingest skipped: not connected (campaign=%s)", campaign_id
        )
        return {
            "channel": YOUTUBE_CHANNEL,
            "status": "skipped",
            "reason": "not_connected",
        }

    if adapter is None:
        try:
            adapter = _default_organic_factory(YOUTUBE_CHANNEL)
        except KeyError as exc:
            logger.warning("youtube adapter not registered: %s", exc)
            return {
                "channel": YOUTUBE_CHANNEL,
                "status": "skipped",
                "reason": "adapter_not_registered",
            }

    if tokens is None:
        tokens = _stub_tokens()

    since = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
    try:
        events = _call_metrics(adapter, tokens, since)
        agg = aggregate_events(events, target_date, YOUTUBE_METRIC_MAP)
        upsert_performance(store, campaign_id, target_date, YOUTUBE_CHANNEL, agg)
        logger.info(
            "youtube ingest ok campaign=%s impressions=%s clicks=%s",
            campaign_id,
            agg["impressions"],
            agg["clicks"],
        )
        return _result_ok(YOUTUBE_CHANNEL, agg)
    except Exception as exc:  # noqa: BLE001 - per-channel isolation
        logger.warning(
            "youtube ingest failed campaign=%s: %s", campaign_id, exc
        )
        return {
            "channel": YOUTUBE_CHANNEL,
            "status": "error",
            "error": str(exc),
        }


# ─── Core per-campaign pull ───────────────────────────────────────────────────


def pull_for_campaign(
    store: PerformanceStore,
    campaign: Any,
    connections: Iterable[Any],
    target_date: date,
    adapter_factory: Callable[[str], Any] = get_ads_adapter,
    gbp_adapter: Any | None = None,
    meta_organic_adapter_factory: Callable[[str], Any] | None = None,
    linkedin_adapter: Any | None = None,
    whatsapp_adapter: Any | None = None,
    youtube_adapter: Any | None = None,
) -> dict[str, Any]:
    """Pull metrics for a single campaign across its connected channels.

    ``campaign`` is expected to expose ``id``, ``network`` and
    ``network_campaign_id``.  ``connections`` are ``Connection``-like objects
    with a ``channel`` attribute.

    Channels are routed to the appropriate ingestion path:

    * ``gmb``                       -> :func:`ingest_gbp_metrics` (organic GBP)
    * ``meta_ads``/``facebook``/
      ``instagram``                 -> :func:`ingest_meta_metrics` (Meta ads + organic)
    * ``google_ads``                -> :func:`ingest_google_ads_metrics` (paid)
    * ``linkedin``                  -> :func:`ingest_linkedin_metrics` (organic)
    * ``whatsapp``                  -> :func:`ingest_whatsapp_metrics` (organic)
    * ``youtube``                   -> :func:`ingest_youtube_metrics` (organic)
    * any other ads network         -> the generic ads ``stats`` path

    Per-channel errors are caught and reported — one failure never blocks the
    other channels for the same campaign.
    """
    channels_result: dict[str, Any] = {}
    ncid = getattr(campaign, "network_campaign_id", None)
    network = getattr(campaign, "network", None)
    campaign_id = getattr(campaign, "id", None)

    for conn in connections:
        channel = getattr(conn, "channel", None)
        if channel is None:
            continue

        # ── Google Business Profile (organic) ────────────────────────────────
        if channel == GBP_CHANNEL:
            channels_result[str(channel)] = ingest_gbp_metrics(
                store, campaign, conn, target_date, adapter=gbp_adapter
            )
            continue

        # ── Meta (Facebook + Instagram, ads + organic) ───────────────────────
        if channel in META_CHANNELS:
            channels_result[str(channel)] = ingest_meta_metrics(
                store,
                campaign,
                conn,
                target_date,
                ads_adapter_factory=adapter_factory,
                organic_adapter_factory=meta_organic_adapter_factory,
            )
            continue

        # ── Google Ads (paid) ────────────────────────────────────────────────
        if channel in GOOGLE_ADS_CHANNELS:
            channels_result[str(channel)] = ingest_google_ads_metrics(
                store,
                campaign,
                conn,
                target_date,
                ads_adapter_factory=adapter_factory,
            )
            continue

        # ── LinkedIn (organic) ───────────────────────────────────────────────
        if channel == LINKEDIN_CHANNEL:
            channels_result[str(channel)] = ingest_linkedin_metrics(
                store, campaign, conn, target_date, adapter=linkedin_adapter
            )
            continue

        # ── WhatsApp Business (organic) ──────────────────────────────────────
        if channel == WHATSAPP_CHANNEL:
            channels_result[str(channel)] = ingest_whatsapp_metrics(
                store, campaign, conn, target_date, adapter=whatsapp_adapter
            )
            continue

        # ── YouTube (organic) ────────────────────────────────────────────────
        if channel == YOUTUBE_CHANNEL:
            channels_result[str(channel)] = ingest_youtube_metrics(
                store, campaign, conn, target_date, adapter=youtube_adapter
            )
            continue

        # ── Generic ads networks ─────────────────────────────────────────────
        if not ncid:
            channels_result[str(channel)] = {
                "status": "skipped",
                "reason": "no_network_campaign_id",
            }
            continue
        try:
            adapter = adapter_factory(str(channel))
            since = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
            events = adapter.stats(_stub_tokens(), str(ncid), since)
            agg = aggregate_events(events, target_date)
            upsert_performance(store, campaign_id, target_date, str(channel), agg)
            channels_result[str(channel)] = {
                "status": "ok",
                "impressions": agg["impressions"],
                "clicks": agg["clicks"],
                "conversions": agg["conversions"],
                "spend": agg["spend"],
                "revenue": agg["revenue"],
            }
        except Exception as exc:  # noqa: BLE001 - per-channel isolation
            logger.warning(
                "performance pull failed campaign=%s channel=%s: %s",
                campaign_id,
                channel,
                exc,
            )
            channels_result[str(channel)] = {
                "status": "error",
                "error": str(exc),
            }

    return {
        "campaign_id": str(campaign_id) if campaign_id is not None else None,
        "network": str(network) if network is not None else None,
        "channels": channels_result,
    }


def run_pull(
    store: PerformanceStore,
    campaigns: Iterable[Any],
    connections_by_brand: Callable[[Any], Iterable[Any]] | None,
    target_date: date,
    adapter_factory: Callable[[str], Any] = get_ads_adapter,
    gbp_adapter: Any | None = None,
    meta_organic_adapter_factory: Callable[[str], Any] | None = None,
    linkedin_adapter: Any | None = None,
    whatsapp_adapter: Any | None = None,
    youtube_adapter: Any | None = None,
) -> list[dict[str, Any]]:
    """Run the pull across every campaign.

    ``connections_by_brand`` resolves the list of connections for a given
    brand id.  Per-campaign failures are isolated.
    """
    results: list[dict[str, Any]] = []
    for campaign in campaigns:
        try:
            brand_id = getattr(campaign, "brand_id", None)
            connections: Iterable[Any] = []
            if connections_by_brand is not None and brand_id is not None:
                connections = connections_by_brand(brand_id)
            results.append(
                pull_for_campaign(
                    store,
                    campaign,
                    connections,
                    target_date,
                    adapter_factory,
                    gbp_adapter=gbp_adapter,
                    meta_organic_adapter_factory=meta_organic_adapter_factory,
                    linkedin_adapter=linkedin_adapter,
                    whatsapp_adapter=whatsapp_adapter,
                    youtube_adapter=youtube_adapter,
                )
            )
        except Exception as exc:  # noqa: BLE001 - per-campaign isolation
            logger.warning(
                "performance pull crashed for campaign=%s: %s",
                getattr(campaign, "id", None),
                exc,
            )
            results.append(
                {
                    "campaign_id": str(getattr(campaign, "id", None)),
                    "status": "error",
                    "error": str(exc),
                }
            )
    return results


# ─── DB loaders ───────────────────────────────────────────────────────────────


def _load_active_campaigns(session: Session) -> list[Any]:
    from prachar_api.models.tables import Campaign
    from prachar_api.models.enums import CampaignStatus

    return list(
        session.execute(
            select(Campaign).where(Campaign.status == CampaignStatus.active)
        ).scalars().all()
    )


def _load_active_connections(session: Session, brand_id: Any) -> list[Any]:
    from prachar_api.models.enums import ConnectionStatus
    from prachar_api.models.tables import Connection

    return list(
        session.execute(
            select(Connection).where(
                Connection.brand_id == brand_id,
                Connection.status == ConnectionStatus.active,
            )
        ).scalars().all()
    )


# ─── Celery task ──────────────────────────────────────────────────────────────


@celery_app.task(
    name="prachar_workers.performance.pull_daily_performance",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def pull_daily_performance(
    target_date: str | None = None,
) -> dict[str, Any]:
    """Pull yesterday's (or ``target_date``'s) performance for all active campaigns.

    ``target_date`` is an ISO ``YYYY-MM-DD`` string; defaults to today.
    """
    target = date.fromisoformat(target_date) if target_date else date.today()
    logger.info("pull_daily_performance target=%s", target)

    from prachar_workers.db import session_scope

    try:
        with session_scope() as session:
            store = PerformanceStore(session)
            campaigns = _load_active_campaigns(session)

            def connections_by_brand(brand_id: Any) -> list[Any]:
                return _load_active_connections(session, brand_id)

            results = run_pull(
                store,
                campaigns,
                connections_by_brand,
                target,
                get_ads_adapter,
            )
    except Exception as exc:  # pragma: no cover - DB optional
        logger.warning("pull_daily_performance DB failed: %s", exc)
        return {"date": str(target), "status": "error", "error": str(exc), "results": []}

    ok = sum(1 for r in results if all(v.get("status") == "ok" for v in r.get("channels", {}).values()))
    logger.info("pull_daily_performance done campaigns=%d ok=%d", len(results), ok)
    return {"date": str(target), "status": "ok", "results": results}
