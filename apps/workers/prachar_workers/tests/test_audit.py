from __future__ import annotations

import asyncio
import os
import uuid

import pytest

from prachar_workers.ingest.audit import extract_domain, run_audit_pipeline


def test_extract_domain_url():
    assert extract_domain("https://example.com/page") == "example.com"


def test_extract_domain_bare_domain():
    assert extract_domain("example.com") == "example.com"


def test_extract_domain_handle_returns_none():
    assert extract_domain("@brandname") is None


def test_extract_domain_empty():
    assert extract_domain("") is None


def test_extract_domain_www_stripped():
    assert extract_domain("https://www.example.co.in/path?q=1") == "example.co.in"


def _redis_available() -> bool:
    try:
        import redis

        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        r = redis.Redis.from_url(url, socket_connect_timeout=1)
        r.ping()
        return True
    except Exception:
        return False


def test_run_audit_pipeline_stub_mode(monkeypatch):
    """End-to-end pipeline in stub mode (no AI keys, mock DB writes)."""
    # Force stub mode: clear any AI keys via env.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SERP_API_KEY", raising=False)

    # Avoid real DB writes: patch _update_job to a no-op.
    import prachar_workers.ingest.audit as audit_mod

    calls: list[dict] = []

    def fake_update(job_id, **fields):
        calls.append({"job_id": job_id, **fields})

    monkeypatch.setattr(audit_mod, "_update_job", fake_update)

    # Use a domain that will not actually be fetched over the network:
    # patch crawl_site to return a deterministic page so the test is offline.
    from prachar_workers.ingest.crawl import CrawlResult

    async def fake_crawl_site(domain, max_pages=5):
        return [
            CrawlResult(
                url=f"https://{domain}",
                title="Example Brand - Best SaaS Tools",
                meta_description="",
                h1="Welcome to Example",
                schema_org_types=[],
                word_count=120,
                internal_links=2,
                text_snippet="Example brand offers the best SaaS tools for teams.",
                status_code=200,
            )
        ]

    monkeypatch.setattr(audit_mod, "crawl_site", fake_crawl_site)

    job_id = uuid.uuid4()
    result = asyncio.run(run_audit_pipeline(job_id, "https://example.com"))

    assert "score" in result
    assert "findings" in result
    score = result["score"]
    assert 0.0 <= score["overall"] <= 100.0
    findings = result["findings"]["findings"]
    assert isinstance(findings, list)
    assert len(findings) >= 5
    # first 5 free, rest gated
    assert all(f["gated"] is False for f in findings[:5])
    assert all(f["gated"] is True for f in findings[5:])

    # DB update calls happened: at least running + completed.
    statuses = [c.get("status") for c in calls if "status" in c]
    assert "running" in statuses
    assert "completed" in statuses


def test_run_audit_pipeline_failed_sets_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SERP_API_KEY", raising=False)

    import prachar_workers.ingest.audit as audit_mod

    calls: list[dict] = []

    def fake_update(job_id, **fields):
        calls.append({"job_id": job_id, **fields})

    monkeypatch.setattr(audit_mod, "_update_job", fake_update)

    async def boom(domain, max_pages=5):
        raise RuntimeError("network down")

    monkeypatch.setattr(audit_mod, "crawl_site", boom)

    job_id = uuid.uuid4()
    with pytest.raises(RuntimeError):
        asyncio.run(run_audit_pipeline(job_id, "https://example.com"))

    statuses = [c.get("status") for c in calls if "status" in c]
    assert "failed" in statuses
    assert any("error" in c for c in calls)


def test_progress_messages_pushed_or_skipped(monkeypatch):
    """Progress is pushed to Redis when available, else skipped gracefully."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SERP_API_KEY", raising=False)

    import prachar_workers.ingest.audit as audit_mod

    monkeypatch.setattr(audit_mod, "_update_job", lambda *a, **k: None)

    from prachar_workers.ingest.crawl import CrawlResult

    async def fake_crawl_site(domain, max_pages=5):
        return [CrawlResult(url=f"https://{domain}", text_snippet="x", status_code=200)]

    monkeypatch.setattr(audit_mod, "crawl_site", fake_crawl_site)

    job_id = uuid.uuid4()
    # Should not raise regardless of Redis availability.
    asyncio.run(run_audit_pipeline(job_id, "https://example.com"))

    if _redis_available():
        import redis

        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        r = redis.Redis.from_url(url, decode_responses=True)
        key = f"audit:{job_id}:progress"
        msgs = r.lrange(key, 0, -1)
        assert isinstance(msgs, list)
        assert len(msgs) >= 1
        r.delete(key)
