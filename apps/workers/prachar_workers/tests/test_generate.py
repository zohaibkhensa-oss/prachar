from __future__ import annotations

import asyncio
import uuid

import pytest

from prachar_workers.organic.generate import (
    generate_faq_block,
    generate_meta_variants,
    generate_page_content,
)


@pytest.fixture(autouse=True)
def _no_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from prachar_shared.config import get_settings

    get_settings.cache_clear()


def test_generate_page_content_stub_returns_valid_payload() -> None:
    brand_id = uuid.uuid4()
    brand_graph = {"brand_name": "Acme", "entities": ["running shoes"]}
    result = asyncio.run(
        generate_page_content(brand_id, "running shoes", "en-US", brand_graph)
    )
    assert isinstance(result, dict)
    for key in ("title", "meta", "h_structure", "schema_org", "internal_links", "faq"):
        assert key in result, f"missing key: {key}"
    assert len(result["title"]) <= 60
    assert len(result["meta"]) <= 155


def test_generate_meta_variants_returns_n_variants() -> None:
    brand_id = uuid.uuid4()
    variants = asyncio.run(generate_meta_variants(brand_id, "running shoes", count=3))
    assert isinstance(variants, list)
    assert len(variants) == 3
    for v in variants:
        assert "title" in v and "meta" in v


def test_generate_faq_block_returns_at_least_three_pairs() -> None:
    brand_id = uuid.uuid4()
    faq = asyncio.run(generate_faq_block(brand_id, "running shoes", "en-US"))
    assert isinstance(faq, list)
    assert len(faq) >= 3
    for pair in faq:
        assert "question" in pair and "answer" in pair
