from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(15.0, connect=10.0)


@dataclass
class SerpEntry:
    position: int
    title: str
    url: str
    domain: str


@dataclass
class QueryResult:
    query: str
    results: list[SerpEntry] = field(default_factory=list)
    brand_position: int | None = None


@dataclass
class SerpResult:
    queries: list[QueryResult] = field(default_factory=list)
    brand_in_top10: int = 0
    avg_position: float | None = None


def _domain_of(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().lstrip("www.")
    except ValueError:
        return ""


def _has_serp_key() -> bool:
    from prachar_shared.config import get_settings

    return bool(get_settings().serp_api_key.strip())


def generate_seed_queries(entities: dict, domain: str) -> list[str]:
    """Derive 5 seed queries from entity extraction output."""
    category = (entities.get("category") or "").strip()
    brand = (entities.get("brand_name") or domain.split(".")[0] or "").strip()
    usps = entities.get("usps") or []
    competitors = entities.get("competitors") or []
    queries: list[str] = []
    if category:
        queries.append(category)
        if brand:
            queries.append(f"{brand} {category}".strip())
        queries.append(f"best {category}")
        if usps:
            queries.append(f"{category} {str(usps[0]).lower()}")
        if competitors:
            queries.append(f"{category} vs {competitors[0]}")
    else:
        queries.append(domain)
        queries.append(f"{brand} review")
        queries.append(f"best {brand} alternatives")
        queries.append(f"top {brand} features")
        queries.append(f"{brand} pricing")
    # de-dup, keep order, pad to 5
    seen: set[str] = set()
    uniq = [q for q in queries if not (q in seen or seen.add(q))]
    while len(uniq) < 5:
        uniq.append(f"{brand or domain} {category or 'review'}".strip())
    return uniq[:5]


async def _serp_api_query(query: str) -> list[SerpEntry]:
    from prachar_shared.config import get_settings

    key = get_settings().serp_api_key.strip()
    params = {"engine": "google", "q": query, "api_key": key, "num": "10"}
    entries: list[SerpEntry] = []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get("https://serpapi.com/search", params=params)
        data = resp.json()
        for i, item in enumerate(data.get("organic_results") or [], start=1):
            link = item.get("link") or ""
            entries.append(
                SerpEntry(
                    position=i,
                    title=item.get("title") or "",
                    url=link,
                    domain=_domain_of(link),
                )
            )
    except Exception as e:
        logger.warning("serp api query failed q=%s err=%s", query, e)
    return entries


def _mock_entries(query: str) -> list[SerpEntry]:
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
    entries: list[SerpEntry] = []
    for i in range(10):
        d = f"site{int(digest[i : i + 4], 16) % 900 + 100}.com"
        entries.append(
            SerpEntry(
                position=i + 1,
                title=f"Result {i + 1} for {query}",
                url=f"https://{d}/{i}",
                domain=d,
            )
        )
    return entries


async def serp_sample(queries: list[str], domain: str) -> SerpResult:
    """Sample SERP results for the given queries; check brand presence."""
    brand = domain.lower().lstrip("www.")
    use_api = _has_serp_key()
    qresults: list[QueryResult] = []
    for q in queries:
        entries = await _serp_api_query(q) if use_api else _mock_entries(q)
        brand_pos: int | None = None
        for e in entries:
            if brand and (brand in e.domain or e.domain in brand):
                brand_pos = e.position
                break
        qresults.append(QueryResult(query=q, results=entries, brand_position=brand_pos))
    in_top10 = sum(1 for qr in qresults if qr.brand_position is not None)
    positions = [qr.brand_position for qr in qresults if qr.brand_position is not None]
    avg = round(sum(positions) / len(positions), 2) if positions else None
    return SerpResult(queries=qresults, brand_in_top10=in_top10, avg_position=avg)
