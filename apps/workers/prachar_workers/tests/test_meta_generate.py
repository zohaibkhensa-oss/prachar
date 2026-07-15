from __future__ import annotations

import uuid

import pytest

from prachar_workers.organic.meta_generate import (
    compute_posting_windows,
    generate_fb_post,
    generate_hashtag_sets,
    generate_ig_caption,
)


@pytest.mark.asyncio
async def test_generate_ig_caption_stub():
    brand_id = uuid.uuid4()
    brand_graph = {"brand_name": "Acme", "category": "coffee", "website": "https://acme.com"}
    result = await generate_ig_caption(brand_id, "specialty coffee", "en-IN", brand_graph)
    assert "caption" in result
    assert len(result["caption"]) <= 2200
    assert "hashtag_sets" in result
    assert len(result["hashtag_sets"]) >= 2
    assert result["post_type"] in ("feed", "reels", "carousel")


@pytest.mark.asyncio
async def test_generate_fb_post_stub():
    brand_id = uuid.uuid4()
    brand_graph = {"brand_name": "Acme", "category": "coffee", "website": "https://acme.com"}
    result = await generate_fb_post(brand_id, "cold brew", "en-US", brand_graph)
    assert "message" in result
    assert len(result["message"]) <= 63206
    assert "hashtags" in result


@pytest.mark.asyncio
async def test_generate_hashtag_sets_stub():
    brand_graph = {"brand_name": "Acme", "category": "coffee"}
    result = await generate_hashtag_sets("instagram", "cold brew", "en-US", brand_graph)
    assert "sets" in result
    assert len(result["sets"]) == 3
    for s in result["sets"]:
        assert len(s) <= 30


def test_compute_posting_windows():
    windows = compute_posting_windows(["Asia/Kolkata"], "instagram")
    assert len(windows) >= 1
    assert len(windows) <= 7
