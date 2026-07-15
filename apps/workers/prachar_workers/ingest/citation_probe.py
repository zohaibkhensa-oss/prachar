from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CitationResult:
    queries_tested: int = 0
    brand_mentioned: int = 0
    citation_rate: float = 0.0


def _stub_mode() -> bool:
    from prachar_shared.config import get_settings

    s = get_settings()
    return not (s.anthropic_api_key.strip() or s.openai_api_key.strip())


async def probe_citations(
    brand_name: str, category: str, queries: list[str]
) -> CitationResult:
    """Probe AI answer engines for brand mentions in category questions.

    Uses the ai_gateway small model when keys are available; otherwise returns
    a deterministic stub derived from the brand name hash.
    """
    if not queries:
        return CitationResult()
    if _stub_mode():
        return _stub_probe(brand_name, category, queries)
    return await _live_probe(brand_name, category, queries)


def _stub_probe(brand_name: str, category: str, queries: list[str]) -> CitationResult:
    import hashlib

    digest = hashlib.sha256((brand_name + category).encode("utf-8")).hexdigest()
    mentioned = int(digest[:2], 16) % (len(queries) + 1)
    rate = round(mentioned / len(queries), 4) if queries else 0.0
    return CitationResult(
        queries_tested=len(queries),
        brand_mentioned=mentioned,
        citation_rate=rate,
    )


async def _live_probe(
    brand_name: str, category: str, queries: list[str]
) -> CitationResult:
    import uuid

    from prachar_shared.ai_gateway import AIGateway, Tier

    gw = AIGateway()
    schema = {
        "type": "object",
        "properties": {
            "mentions_brand": {"type": "boolean"},
            "answer": {"type": "string"},
        },
        "required": ["mentions_brand", "answer"],
    }
    mentioned = 0
    for q in queries:
        prompt = (
            f"Answer this question as an AI answer engine would: '{q}'. "
            f"Then state whether the brand '{brand_name}' (category: {category}) "
            "is mentioned in your answer."
        )
        try:
            comp = gw.complete(
                prompt,
                tier=Tier.small,
                schema=schema,
                task="geo_probes",
                tenant_id=uuid.UUID(int=0),
                plan="starter",
            )
            jv = comp.json_value or {}
            if jv.get("mentions_brand"):
                mentioned += 1
        except Exception as e:
            logger.warning("citation probe query failed q=%s err=%s", q, e)
    rate = round(mentioned / len(queries), 4) if queries else 0.0
    return CitationResult(
        queries_tested=len(queries),
        brand_mentioned=mentioned,
        citation_rate=rate,
    )
