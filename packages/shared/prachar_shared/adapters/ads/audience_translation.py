from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any

from ...ai_gateway import AIGateway, Tier

logger = logging.getLogger(__name__)

# Stub ISO-3166-1 country code -> Google Ads geo target resource id (constant).
# A small representative subset; production would load the full canonical table.
GEO_CODE_MAP: dict[str, int] = {
    "US": 2840,
    "IN": 2356,
    "GB": 2826,
    "CA": 2124,
    "AU": 2036,
    "DE": 2276,
    "FR": 2250,
    "AE": 2784,
    "SG": 2086,
    "JP": 2392,
}

# Meta location targeting key shape: {"countries": [...], "regions": [...]}.
# Stub ISO-3166-1 -> Meta country code (ISO-2 used by Meta).
_META_COUNTRY_CODES: dict[str, str] = {
    "US": "US",
    "IN": "IN",
    "GB": "GB",
    "CA": "CA",
    "AU": "AU",
    "DE": "DE",
    "FR": "FR",
    "AE": "AE",
    "SG": "SG",
    "JP": "JP",
}


def google_geo_target(iso_code: str) -> int:
    """Return the Google Ads geo target constant id for a country ISO-2 code."""
    code = iso_code.upper()
    if code not in GEO_CODE_MAP:
        logger.warning("google_geo_target: unmapped iso_code=%s, defaulting to US", code)
        return GEO_CODE_MAP["US"]
    return GEO_CODE_MAP[code]


def meta_location_target(iso_code: str) -> dict[str, Any]:
    """Return a Meta Marketing API location targeting dict for a country ISO-2 code."""
    code = iso_code.upper()
    meta_code = _META_COUNTRY_CODES.get(code, code)
    return {
        "geo_locations": {
            "countries": [meta_code],
            "location_types": ["home", "recent"],
        },
    }


def _spec_hash(items: list[str], source_type: str, target_network: str) -> str:
    raw = f"{target_network}|{source_type}|" + ",".join(sorted(items))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def translate_taxonomy(
    items: list[str],
    source_type: str,
    target_network: str,
) -> list[str]:
    """Translate canonical interest/intent taxonomy terms to a network-native taxonomy.

    Uses the AIGateway small model with a per-(network,type,items)-hash cache key.
    In stub mode (no provider keys) returns items prefixed with the network + type
    so callers get a deterministic, non-empty mapping.
    """
    if not items:
        return []
    gw = AIGateway()
    digest = _spec_hash(items, source_type, target_network)
    if gw._stub_mode():
        # Deterministic stub mapping: prefix each item with network + type tag.
        return [f"{target_network}:{source_type}:{it}#{digest[:6]}" for it in items]

    schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "mapped": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
    }
    prompt = (
        f"Translate the following {source_type} terms into {target_network} native "
        f"targeting taxonomy names. Return one mapped term per input, preserving order.\n"
        f"Terms: {items}\n"
    )
    import uuid

    comp = gw.complete(
        prompt,
        tier=Tier.small,
        task="creative_copy",
        schema=schema,
        tenant_id=uuid.UUID(int=0),
        plan="starter",
    )
    mapped = (comp.json_value or {}).get("mapped", []) if comp.json_value else []
    if not isinstance(mapped, list) or not mapped:
        return [f"{target_network}:{source_type}:{it}" for it in items]
    return [str(m) for m in mapped]


def translate_taxonomy_sync(
    items: list[str],
    source_type: str,
    target_network: str,
) -> list[str]:
    """Synchronous wrapper around :func:`translate_taxonomy` for adapter use."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Inside a running loop (e.g. async test) fall back to stub mapping.
            gw = AIGateway()
            if gw._stub_mode():
                digest = _spec_hash(items, source_type, target_network)
                return [f"{target_network}:{source_type}:{it}#{digest[:6]}" for it in items]
            return [f"{target_network}:{source_type}:{it}" for it in items]
    except RuntimeError:
        pass
    return asyncio.run(translate_taxonomy(items, source_type, target_network))
