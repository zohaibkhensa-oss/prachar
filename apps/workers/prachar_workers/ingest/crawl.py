from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "PracharAuditBot/1.0 (+https://prachar.app/bot)"
_TIMEOUT = httpx.Timeout(15.0, connect=10.0)


@dataclass
class CrawlResult:
    url: str
    title: str = ""
    meta_description: str = ""
    h1: str = ""
    schema_org_types: list[str] = field(default_factory=list)
    word_count: int = 0
    internal_links: int = 0
    text_snippet: str = ""
    status_code: int = 0


_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)
_STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
_TITLE_RE = re.compile(r"<title\b[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_META_DESC_RE = re.compile(
    r'<meta\b[^>]+name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_META_DESC_RE_REV = re.compile(
    r'<meta\b[^>]+content=["\']([^"\']*)["\'][^>]*name=["\']description["\']',
    re.IGNORECASE,
)
_H1_RE = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_A_HREF_RE = re.compile(r'<a\b[^>]+href=["\']([^"\']+)["\']', re.IGNORECASE)
_JSONLD_RE = re.compile(
    r'<script\b[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_SPACE_RE = re.compile(r"\s+")


def _strip_tags(html: str) -> str:
    no_style = _STYLE_RE.sub(" ", html)
    no_scripts = _SCRIPT_RE.sub(" ", no_style)
    text = _TAG_RE.sub(" ", no_scripts)
    return _SPACE_RE.sub(" ", text).strip()


def _extract_schema_org_types(html: str) -> list[str]:
    types: list[str] = []
    for m in _JSONLD_RE.finditer(html):
        blob = m.group(1).strip()
        if not blob:
            continue
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        for node in _iter_jsonld_nodes(data):
            t = node.get("@type")
            if isinstance(t, list):
                types.extend(str(x) for x in t)
            elif isinstance(t, str):
                types.append(t)
    return types


def _iter_jsonld_nodes(data: object):
    if isinstance(data, list):
        for item in data:
            yield from _iter_jsonld_nodes(item)
    elif isinstance(data, dict):
        if "@graph" in data and isinstance(data["@graph"], list):
            for item in data["@graph"]:
                yield from _iter_jsonld_nodes(item)
        elif "@type" in data:
            yield data


def _same_domain(href: str, base: str) -> bool:
    try:
        h = urlparse(href)
        b = urlparse(base)
    except ValueError:
        return False
    if not h.netloc:
        return True
    return h.netloc.lower() == b.netloc.lower()


def parse_html(html: str, url: str) -> CrawlResult:
    title_m = _TITLE_RE.search(html)
    title = _strip_tags(title_m.group(1)) if title_m else ""
    desc = ""
    m = _META_DESC_RE.search(html) or _META_DESC_RE_REV.search(html)
    if m:
        desc = m.group(1).strip()
    h1_m = _H1_RE.search(html)
    h1 = _strip_tags(h1_m.group(1)) if h1_m else ""
    text = _strip_tags(html)
    word_count = len(text.split()) if text else 0
    internal = sum(
        1 for hm in _A_HREF_RE.finditer(html) if _same_domain(hm.group(1), url)
    )
    schema_types = _extract_schema_org_types(html)
    snippet = text[:500]
    return CrawlResult(
        url=url,
        title=title,
        meta_description=desc,
        h1=h1,
        schema_org_types=schema_types,
        word_count=word_count,
        internal_links=internal,
        text_snippet=snippet,
        status_code=200,
    )


async def crawl_url(url: str) -> CrawlResult:
    """Fetch a single URL with httpx and extract on-page signals."""
    logger.info("crawl_url url=%s", url)
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=_TIMEOUT, headers={"User-Agent": USER_AGENT}
        ) as client:
            resp = await client.get(url)
        result = parse_html(resp.text, str(resp.url))
        result.status_code = resp.status_code
        result.url = str(resp.url)
        return result
    except Exception as e:
        logger.warning("crawl_url failed url=%s err=%s", url, e)
        return CrawlResult(url=url, status_code=0)


async def crawl_site(domain: str, max_pages: int = 5) -> list[CrawlResult]:
    """Crawl the homepage plus up to (max_pages - 1) internal links."""
    if not domain.startswith(("http://", "https://")):
        domain = "https://" + domain
    homepage = await crawl_url(domain)
    results = [homepage]
    if homepage.status_code == 0 or max_pages <= 1:
        return results
    seen: set[str] = {homepage.url}
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=_TIMEOUT, headers={"User-Agent": USER_AGENT}
        ) as client:
            html = (await client.get(domain)).text
        for m in _A_HREF_RE.finditer(html):
            href = urljoin(domain, m.group(1))
            if not _same_domain(href, domain):
                continue
            if href in seen or href.rstrip("/") == homepage.url.rstrip("/"):
                continue
            if href.startswith(("mailto:", "tel:", "javascript:")):
                continue
            seen.add(href)
            if len(results) >= max_pages:
                break
            results.append(await crawl_url(href))
    except Exception as e:
        logger.warning("crawl_site extra pages failed domain=%s err=%s", domain, e)
    return results
