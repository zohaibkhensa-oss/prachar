from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlparse

from .citation_probe import CitationResult, probe_citations
from .crawl import CrawlResult, crawl_site, crawl_url
from .serp import SerpResult, generate_seed_queries, serp_sample

logger = logging.getLogger(__name__)


def extract_domain(input_text: str) -> str | None:
    """Return the registrable domain for a URL input, or None for @handles."""
    text = (input_text or "").strip()
    if not text:
        return None
    if text.startswith("@"):
        return None
    candidate = text
    if "://" not in candidate:
        candidate = "https://" + candidate
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None
    host = (parsed.netloc or "").lower()
    if not host:
        return None
    return host.lstrip("www.")


def _brand_name_from_domain(domain: str) -> str:
    return domain.split(".")[0] or domain


# ---------- progress logging ----------

async def _push_progress(job_id: uuid.UUID, msg: str) -> None:
    try:
        import redis.asyncio as aioredis

        from prachar_shared.config import get_settings

        url = get_settings().redis_url
        client = aioredis.from_url(url, decode_responses=True)
        try:
            await client.rpush(f"audit:{job_id}:progress", msg)
            await client.expire(f"audit:{job_id}:progress", 7 * 24 * 3600)
        finally:
            await client.aclose()
    except Exception as e:
        logger.debug("progress push skipped: %s", e)


# ---------- DB updates ----------

def _update_job(job_id: uuid.UUID, **fields: Any) -> None:
    try:
        from sqlalchemy import bindparam, text
        from sqlalchemy.dialects.postgresql import JSONB

        from prachar_workers.db import session_scope

        sets: list[str] = []
        params: dict[str, Any] = {"jid": job_id}
        json_cols = {"score_snapshot", "findings"}
        bindparams = []
        for k, v in fields.items():
            params[k] = v
            sets.append(f"{k} = :{k}")
            if k in json_cols:
                bindparams.append(bindparam(k, type_=JSONB))
        if not sets:
            return
        sql = text(
            f"UPDATE audit_jobs SET {', '.join(sets)} WHERE id = :jid"
        ).bindparams(*bindparams)
        with session_scope() as s:
            s.execute(sql, params)
    except Exception as e:
        logger.warning("update_job failed job=%s err=%s", job_id, e)


# ---------- entity extraction ----------

ENTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "brand_name": {"type": "string"},
        "category": {"type": "string"},
        "usps": {"type": "array", "items": {"type": "string"}},
        "competitors": {"type": "array", "items": {"type": "string"}},
        "locales": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["brand_name", "category", "usps", "competitors"],
}


async def extract_entities(crawl_results: list[CrawlResult], domain: str) -> dict:
    """Extract category/USPs/competitors via the small model (stub-aware)."""
    import uuid as _uuid

    from prachar_shared.ai_gateway import AIGateway, Tier

    gw = AIGateway()
    page = crawl_results[0] if crawl_results else CrawlResult(url=domain)
    snippet = page.text_snippet or domain
    prompt = (
        "Extract brand entity signals from this homepage content.\n"
        f"Domain: {domain}\n"
        f"Title: {page.title}\n"
        f"H1: {page.h1}\n"
        f"Meta description: {page.meta_description}\n"
        f"Text snippet: {snippet[:1500]}\n\n"
        "Return JSON with brand_name, category, usps (list), competitors (list)."
    )
    if gw._stub_mode():
        return _stub_entities(snippet, domain)
    try:
        comp = gw.complete(
            prompt,
            tier=Tier.small,
            schema=ENTITY_SCHEMA,
            task="entity_extraction",
            tenant_id=_uuid.UUID(int=0),
            plan="starter",
        )
        jv = comp.json_value or {}
        return {
            "brand_name": jv.get("brand_name") or _brand_name_from_domain(domain),
            "category": jv.get("category") or "",
            "usps": jv.get("usps") or [],
            "competitors": jv.get("competitors") or [],
            "locales": jv.get("locales") or ["en-US"],
        }
    except Exception as e:
        logger.warning("entity extraction failed, using stub: %s", e)
        return _stub_entities(snippet, domain)


def _stub_entities(snippet: str, domain: str) -> dict:
    digest = hashlib.sha256((snippet + domain).encode("utf-8")).hexdigest()
    cats = ["SaaS", "E-commerce", "D2C brand", "Agency", "Marketplace"]
    cat = cats[int(digest[:2], 16) % len(cats)]
    return {
        "brand_name": _brand_name_from_domain(domain),
        "category": cat,
        "usps": [f"USP {digest[:4]}", f"USP {digest[4:8]}"],
        "competitors": [f"competitor{digest[8:10]}.com", f"competitor{digest[10:12]}.com"],
        "locales": ["en-US"],
    }


# ---------- channel presence ----------

async def channel_scan(
    entities: dict, domain: str, serp: SerpResult
) -> dict[str, float]:
    """Aggregate channel-presence signals into sub-scores (0-100)."""
    brand = entities.get("brand_name") or _brand_name_from_domain(domain)
    category = entities.get("category") or ""
    citation_queries = [f"best {category}", f"top {category} brands", f"{category} recommendations"]
    citation: CitationResult = await probe_citations(brand, category, citation_queries)
    # organic rank index from SERP
    if serp.avg_position is not None and serp.avg_position > 0:
        organic = max(0.0, min(100.0, (11.0 - serp.avg_position) / 10.0 * 100.0))
    else:
        organic = (serp.brand_in_top10 / max(1, len(serp.queries))) * 100.0
    ai_rate = citation.citation_rate * 100.0
    # social reach: stubbed (no YT/IG keys in free audit)
    social = 10.0
    return {
        "organic_rank_index": round(organic, 2),
        "ai_citation_rate": round(ai_rate, 2),
        "social_reach_index": round(social, 2),
        "paid_efficiency": 0.0,
        "momentum": 0.0,
    }


# ---------- findings ----------

FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "impact": {"type": "integer"},
                    "effort": {"type": "integer"},
                    "category": {"type": "string"},
                    "fix_description": {"type": "string"},
                    "gated": {"type": "boolean"},
                },
                "required": ["title", "impact", "effort", "category", "fix_description"],
            },
        }
    },
    "required": ["findings"],
}


async def build_findings(
    crawl_results: list[CrawlResult], entities: dict, serp: SerpResult
) -> dict:
    """Generate top-10 findings via the large model (one call). Stub-aware."""
    import uuid as _uuid

    from prachar_shared.ai_gateway import AIGateway, Tier

    gw = AIGateway()
    page = crawl_results[0] if crawl_results else CrawlResult(url="")
    prompt = (
        "You are an SEO/visibility auditor. Produce the top 10 issues ranked by "
        "impact x effort. 5 are free (gated=false), 5 are gated (gated=true).\n"
        f"Brand: {entities.get('brand_name','')}\n"
        f"Category: {entities.get('category','')}\n"
        f"Homepage title: {page.title}\n"
        f"Meta description: {page.meta_description}\n"
        f"H1: {page.h1}\n"
        f"Schema.org types: {page.schema_org_types}\n"
        f"Word count: {page.word_count}\n"
        f"Internal links: {page.internal_links}\n"
        f"SERP brand_in_top10: {serp.brand_in_top10}, avg_position: {serp.avg_position}\n"
        "Return JSON {findings: [...]} with title, impact(1-5), effort(1-5), "
        "category, fix_description, gated."
    )
    if gw._stub_mode():
        return _stub_findings(page, serp)
    try:
        comp = gw.complete(
            prompt,
            tier=Tier.large,
            schema=FINDINGS_SCHEMA,
            task="audits",
            tenant_id=_uuid.UUID(int=0),
            plan="starter",
            max_tokens=2048,
        )
        jv = comp.json_value or {}
        findings = jv.get("findings") or []
        # ensure gated flags: first 5 free, rest gated
        for i, f in enumerate(findings):
            f["gated"] = i >= 5
        return {"findings": findings[:10]}
    except Exception as e:
        logger.warning("findings generation failed, using stub: %s", e)
        return _stub_findings(page, serp)


def _stub_findings(page: CrawlResult, serp: SerpResult) -> dict:
    base: list[dict] = []
    if not page.meta_description:
        base.append({
            "title": "Missing meta description",
            "impact": 4, "effort": 1, "category": "onpage",
            "fix_description": "Add a concise meta description (under 160 chars).",
        })
    if not page.schema_org_types:
        base.append({
            "title": "No schema.org markup detected",
            "impact": 3, "effort": 2, "category": "technical",
            "fix_description": "Add Organization/WebSite JSON-LD structured data.",
        })
    if page.word_count < 300:
        base.append({
            "title": "Low word count on homepage",
            "impact": 3, "effort": 3, "category": "content",
            "fix_description": "Expand homepage content to at least 500 words.",
        })
    if page.internal_links < 5:
        base.append({
            "title": "Few internal links",
            "impact": 2, "effort": 2, "category": "onpage",
            "fix_description": "Add more internal links to key pages.",
        })
    if not page.h1:
        base.append({
            "title": "Missing H1 heading",
            "impact": 3, "effort": 1, "category": "onpage",
            "fix_description": "Add a single descriptive H1 to the homepage.",
        })
    if serp.brand_in_top10 == 0:
        base.append({
            "title": "Brand absent from top-10 SERP results",
            "impact": 5, "effort": 4, "category": "organic",
            "fix_description": "Improve topical authority and on-page SEO for seed queries.",
        })
    # pad to 10
    pad = [
        ("Improve page load speed (CWV)", "technical", 4, 3),
        ("Build topical content clusters", "content", 4, 4),
        ("Earn backlinks from relevant sites", "organic", 5, 5),
        ("Add FAQ schema for answer engines", "geo", 3, 2),
        ("Set up Google Business Profile", "local", 2, 1),
    ]
    i = 0
    while len(base) < 10 and i < len(pad):
        t, cat, imp, eff = pad[i]
        i += 1
        if any(f["title"] == t for f in base):
            continue
        base.append({
            "title": t, "impact": imp, "effort": eff, "category": cat,
            "fix_description": f"Recommended action for {t.lower()}.",
        })
    base = base[:10]
    for idx, f in enumerate(base):
        f["gated"] = idx >= 5
    return {"findings": base}


# ---------- main pipeline ----------

async def run_audit_pipeline(job_id: uuid.UUID, input_text: str) -> dict:
    """Run the full audit pipeline and update the AuditJob row as it progresses."""
    from prachar_shared.contracts import VisibilityScore

    domain = extract_domain(input_text)
    await _push_progress(job_id, f"start: input={input_text} domain={domain}")
    _update_job(job_id, status="running", domain=domain)

    try:
        # 1. crawl
        await _push_progress(job_id, "step:crawl")
        if domain:
            crawl_results = await crawl_site(domain, max_pages=5)
        else:
            crawl_results = [CrawlResult(url=input_text)]
        await _push_progress(
            job_id, f"step:crawl:done pages={len(crawl_results)}"
        )

        # 2. entity extraction
        await _push_progress(job_id, "step:extract_entities")
        entities = await extract_entities(crawl_results, domain or input_text)
        await _push_progress(
            job_id, f"step:extract_entities:done category={entities.get('category')}"
        )

        # 3. SERP sampling
        await _push_progress(job_id, "step:serp_sample")
        queries = generate_seed_queries(entities, domain or input_text)
        serp = await serp_sample(queries, domain or input_text)
        await _push_progress(
            job_id,
            f"step:serp_sample:done in_top10={serp.brand_in_top10} avg={serp.avg_position}",
        )

        # 4. channel presence scan
        await _push_progress(job_id, "step:channel_scan")
        signals = await channel_scan(entities, domain or input_text, serp)
        await _push_progress(job_id, f"step:channel_scan:done signals={signals}")

        # 5. score
        await _push_progress(job_id, "step:score")
        score = VisibilityScore.compute(
            organic_rank_index=signals["organic_rank_index"],
            ai_citation_rate=signals["ai_citation_rate"],
            social_reach_index=signals["social_reach_index"],
            paid_efficiency=signals["paid_efficiency"],
            momentum=signals["momentum"],
            week=date.today(),
        )
        await _push_progress(job_id, f"step:score:done overall={score.overall}")

        # 6. findings
        await _push_progress(job_id, "step:findings")
        findings = await build_findings(crawl_results, entities, serp)
        await _push_progress(
            job_id, f"step:findings:done count={len(findings.get('findings', []))}"
        )

        score_dict = score.model_dump(mode="json")
        _update_job(
            job_id,
            status="completed",
            score_snapshot=score_dict,
            findings=findings,
            completed_at=datetime.now(timezone.utc),
        )
        await _push_progress(job_id, "completed")
        return {"score": score_dict, "findings": findings}
    except Exception as e:
        logger.exception("audit pipeline failed job=%s", job_id)
        _update_job(job_id, status="failed", error=str(e))
        await _push_progress(job_id, f"failed: {e}")
        raise
