from __future__ import annotations

"""Attribution pixel — per spec 06 §"Attribution (pragmatic tier)":
UTM enforcement on all links + per-network click ids (gclid/fbclid/ttclid) →
landing pixel (1st-party js snippet tenant installs) → conversions table →
position-based model (40/20/40). Don't build MMM at MVP; expose per-network
CPA honestly labeled 'network-reported vs pixel-verified'."""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field

from ..deps import SessionDep

router = APIRouter(tags=["attribution"])


class ConversionEvent(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    tenant_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    conversion_type: str = Field(default="purchase", max_length=40)
    value: float = Field(default=0.0, ge=0)
    currency: str = Field(default="INR", max_length=8)
    # Attribution data captured by the pixel.
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None
    gclid: str | None = None  # Google click id
    fbclid: str | None = None  # Meta click id
    ttclid: str | None = None  # TikTok click id
    landing_url: str | None = None
    referrer: str | None = None


class ConversionOut(BaseModel):
    id: uuid.UUID
    attributed_network: str | None
    position_based_credit: dict[str, float]


# In-memory store for S6 (production: metric_events table or dedicated conversions table).
# Keyed by session_id for multi-touch attribution.
_touchpoints: dict[str, list[dict[str, Any]]] = {}


@router.post("/pixel/track")
async def track_event(body: dict[str, Any], request: Request) -> dict[str, Any]:
    """First-party pixel tracking endpoint. Receives page views + click data
    from the JS snippet. Stores touchpoints per session for attribution."""
    session_id = body.get("session_id", "")
    if not session_id:
        return {"status": "ignored", "reason": "no session_id"}
    touchpoint = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "url": body.get("url", ""),
        "referrer": body.get("referrer", ""),
        "utm_source": body.get("utm_source"),
        "utm_medium": body.get("utm_medium"),
        "utm_campaign": body.get("utm_campaign"),
        "gclid": body.get("gclid"),
        "fbclid": body.get("fbclid"),
        "ttclid": body.get("ttclid"),
    }
    _touchpoints.setdefault(session_id, []).append(touchpoint)
    return {"status": "tracked", "session_id": session_id, "touchpoints": len(_touchpoints[session_id])}


@router.post("/pixel/convert", response_model=ConversionOut, status_code=status.HTTP_201_CREATED)
async def record_conversion(body: ConversionEvent, request: Request) -> ConversionOut:
    """Record a conversion and attribute it using position-based model (40/20/40).
    First-touch gets 40%, last-touch gets 40%, middle touches share 20%.
    Per spec 06 §"Attribution"."""
    conv_id = uuid.uuid4()
    touchpoints = _touchpoints.get(body.session_id, [])

    # Determine which network to attribute to.
    attributed_network = None
    if body.gclid:
        attributed_network = "google_ads"
    elif body.fbclid:
        attributed_network = "meta_ads"
    elif body.ttclid:
        attributed_network = "tiktok_ads"
    elif body.utm_source:
        attributed_network = body.utm_source

    # Position-based attribution (40/20/40).
    credit: dict[str, float] = {}
    if touchpoints:
        networks = []
        for tp in touchpoints:
            n = None
            if tp.get("gclid"):
                n = "google_ads"
            elif tp.get("fbclid"):
                n = "meta_ads"
            elif tp.get("ttclid"):
                n = "tiktok_ads"
            elif tp.get("utm_source"):
                n = tp["utm_source"]
            if n:
                networks.append(n)
        if networks:
            if len(networks) == 1:
                credit[networks[0]] = 1.0
            elif len(networks) == 2:
                credit[networks[0]] = 0.4
                credit[networks[1]] = 0.6  # last touch gets more in 2-touch
            else:
                credit[networks[0]] = 0.4  # first
                credit[networks[-1]] = 0.4  # last
                mid_share = 0.2 / (len(networks) - 2)
                for n in networks[1:-1]:
                    credit[n] = credit.get(n, 0) + mid_share
    elif attributed_network:
        credit[attributed_network] = 1.0

    # Clear touchpoints for this session.
    _touchpoints.pop(body.session_id, None)

    return ConversionOut(
        id=conv_id,
        attributed_network=attributed_network,
        position_based_credit=credit,
    )


@router.get("/pixel.js")
async def pixel_js(request: Request) -> str:
    """Serve the first-party tracking pixel JS snippet.
    Tenants install this on their landing pages."""
    return """(function(){
  var P={track:function(e){var d={session_id:P.sid(),url:location.href,referrer:document.referrer};
    var p=new URLSearchParams(location.search);
    ['utm_source','utm_medium','utm_campaign','utm_content','utm_term','gclid','fbclid','ttclid'].forEach(function(k){var v=p.get(k);if(v)d[k]=v;});
    fetch('""" + str(request.base_url) + """pixel/track',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});},
  convert:function(t,v){var d={session_id:P.sid(),conversion_type:t||'purchase',value:v||0,currency:'INR'};
    var p=new URLSearchParams(location.search);
    ['utm_source','utm_medium','utm_campaign','gclid','fbclid','ttclid'].forEach(function(k){var v=p.get(k);if(v)d[k]=v;});
    fetch('""" + str(request.base_url) + """pixel/convert',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});},
  sid:function(){var s=sessionStorage.getItem('_pr_sid');if(!s){s=Math.random().toString(36).slice(2)+Date.now().toString(36);sessionStorage.setItem('_pr_sid',s);}return s;}
  };
  P.track();window.PracharPixel=P;
})();"""
