from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from prachar_workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="prachar_workers.ingest.run_audit",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def run_audit(job_id_str: str, input_text: str) -> dict[str, Any]:
    """Celery entry point: run the full audit pipeline for one AuditJob."""
    from .audit import run_audit_pipeline

    job_id = uuid.UUID(job_id_str)
    return asyncio.run(run_audit_pipeline(job_id, input_text))


@celery_app.task(
    name="prachar_workers.ingest.crawl",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def crawl(url: str) -> dict[str, Any]:
    logger.info("crawl url=%s", url)
    from .audit import extract_domain
    from .crawl import crawl_site

    domain = extract_domain(url) or url
    results = asyncio.run(crawl_site(domain, max_pages=5))
    pages = [
        {
            "url": r.url,
            "title": r.title,
            "meta_description": r.meta_description,
            "h1": r.h1,
            "schema_org_types": r.schema_org_types,
            "word_count": r.word_count,
            "internal_links": r.internal_links,
            "text_snippet": r.text_snippet,
            "status_code": r.status_code,
        }
        for r in results
    ]
    return {
        "url": url,
        "title": pages[0]["title"] if pages else "",
        "meta_description": pages[0]["meta_description"] if pages else "",
        "h1": pages[0]["h1"] if pages else "",
        "text_snippet": pages[0]["text_snippet"] if pages else "",
        "schema_org_types": pages[0]["schema_org_types"] if pages else [],
        "pages": pages,
    }


@celery_app.task(
    name="prachar_workers.ingest.transcribe",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def transcribe(asset_id: str) -> dict[str, Any]:
    logger.info("transcribe asset_id=%s", asset_id)
    # S0 stub: would call Whisper API via openai client.
    return {"asset_id": asset_id, "transcript": ""}


@celery_app.task(
    name="prachar_workers.ingest.extract_entities",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def extract_entities(text: str) -> dict[str, Any]:
    logger.info("extract_entities len=%d", len(text))
    from .audit import extract_entities as _extract

    from .crawl import CrawlResult

    page = CrawlResult(url="", text_snippet=text)
    entities = asyncio.run(_extract([page], "example.com"))
    return {
        "entities": entities.get("competitors", []),
        "categories": [entities.get("category", "")],
        "usps": entities.get("usps", []),
        "competitors": entities.get("competitors", []),
        "brand_name": entities.get("brand_name", ""),
    }


@celery_app.task(
    name="prachar_workers.ingest.build_brand_graph",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def build_brand_graph(brand_id: str) -> dict[str, Any]:
    logger.info("build_brand_graph brand_id=%s", brand_id)
    # S0 stub: minimal BrandGraph.
    return {
        "brand_id": brand_id,
        "brand_graph": {
            "entities": [],
            "categories": [],
            "usps": [],
            "competitors": [],
            "locales": ["en-US"],
            "tone": {},
            "brand_voice": "",
        },
    }
