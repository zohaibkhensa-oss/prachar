from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from prachar_shared.adapters.organic.gsc import GSCAdapter
from prachar_shared.adapters.organic.prompts import (
    FAQ_BLOCK_PROMPT,
    META_TAGS_PROMPT,
    PAGE_CONTENT_PROMPT,
)
from prachar_shared.ai_gateway import AIGateway, Tier

logger = logging.getLogger(__name__)

_DEFAULT_REGISTER = "professional"
_DEFAULT_COMPETITORS = "No competitor examples available."


def _gateway() -> AIGateway:
    return AIGateway()


def _stub_page_content(target_keyword: str, brand_graph: dict[str, Any]) -> dict[str, Any]:
    """Generate plausible page content in stub mode (no AI keys)."""
    brand_name = (brand_graph.get("brand_name") or brand_graph.get("name") or "Brand")
    title = f"{target_keyword.title()} | {brand_name}"
    if len(title) > 60:
        title = title[:57].rstrip() + "..."
    meta = f"Learn about {target_keyword} with {brand_name}. Expert insights, guides, and resources tailored for you."
    if len(meta) > 155:
        meta = meta[:152].rstrip() + "..."
    h_structure = [
        f"H1: {title}",
        f"H2: What is {target_keyword}?",
        f"H2: Why {target_keyword} matters",
        "H3: Key benefits",
        "H2: Frequently asked questions",
    ]
    schema_org = {
        "@type": "Article",
        "headline": title,
        "description": meta,
        "keywords": target_keyword,
    }
    internal_links = [
        f"/guide/{target_keyword.replace(' ', '-')}",
        f"/blog/{target_keyword.replace(' ', '-')}-tips",
        "/about",
    ]
    faq = [
        {
            "question": f"What is {target_keyword}?",
            "answer": f"{target_keyword.capitalize()} refers to a key area of focus for {brand_name}. "
            f"It involves strategies and practices that deliver measurable results.",
        },
        {
            "question": f"How does {target_keyword} work?",
            "answer": f"{target_keyword.capitalize()} works through a structured approach combining "
            "research, execution, and measurement to achieve outcomes.",
        },
        {
            "question": f"Why choose {brand_name} for {target_keyword}?",
            "answer": f"{brand_name} brings deep expertise in {target_keyword}, with proven "
            "methodologies and dedicated support.",
        },
    ]
    return {
        "title": title,
        "meta": meta,
        "h_structure": h_structure,
        "schema_org": schema_org,
        "internal_links": internal_links,
        "faq": faq,
    }


async def generate_page_content(
    brand_id: uuid.UUID,
    target_keyword: str,
    locale: str,
    brand_graph: dict[str, Any],
) -> dict[str, Any]:
    """Generate a full page content payload via the AI gateway.

    Uses PAGE_CONTENT_PROMPT, tier=small, task='captions' (batch-eligible),
    JSON schema from GSCAdapter().generate_schema(). In stub mode, generates
    plausible content from the keyword + brand_graph.
    """
    gw = _gateway()
    schema = GSCAdapter().generate_schema()
    register = (brand_graph.get("tone") or {}).get("register", _DEFAULT_REGISTER)
    competitors = brand_graph.get("competitors") or []
    competitor_examples = ", ".join(competitors) if competitors else _DEFAULT_COMPETITORS
    prompt = PAGE_CONTENT_PROMPT.format(
        brand_graph=json.dumps(brand_graph, default=str),
        locale=locale,
        register=register,
        competitor_examples=competitor_examples,
        target_keyword=target_keyword,
    )
    if gw._stub_mode():
        return _stub_page_content(target_keyword, brand_graph)
    comp = gw.complete(
        prompt,
        tier=Tier.small,
        task="captions",
        schema=schema,
        tenant_id=brand_id,
        plan="starter",
    )
    jv = comp.json_value or {}
    # Ensure all required keys exist.
    return {
        "title": jv.get("title", ""),
        "meta": jv.get("meta", ""),
        "h_structure": jv.get("h_structure", []),
        "schema_org": jv.get("schema_org", {}),
        "internal_links": jv.get("internal_links", []),
        "faq": jv.get("faq", []),
    }


def _stub_meta_variants(keyword: str, count: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in range(count):
        title = f"{keyword.title()} - Guide {i + 1}"
        if len(title) > 60:
            title = title[:57].rstrip() + "..."
        meta = f"Discover {keyword} with our guide {i + 1}. Tips, best practices, and expert insights."
        if len(meta) > 155:
            meta = meta[:152].rstrip() + "..."
        out.append({"title": title, "meta": meta})
    return out


async def generate_meta_variants(
    brand_id: uuid.UUID,
    keyword: str,
    count: int = 3,
) -> list[dict[str, Any]]:
    """Generate N title + meta description variants. Small model, batch."""
    gw = _gateway()
    schema = {
        "type": "object",
        "properties": {
            "variants": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "meta": {"type": "string"},
                    },
                },
            },
        },
    }
    prompt = META_TAGS_PROMPT.format(
        brand_graph="{}",
        locale="en-US",
        register=_DEFAULT_REGISTER,
        competitor_examples=_DEFAULT_COMPETITORS,
        target_keyword=keyword,
        count=count,
    )
    if gw._stub_mode():
        return _stub_meta_variants(keyword, count)
    comp = gw.complete(
        prompt,
        tier=Tier.small,
        task="metas",
        schema=schema,
        tenant_id=brand_id,
        plan="starter",
    )
    jv = comp.json_value or {}
    variants = jv.get("variants", [])
    if not variants:
        return _stub_meta_variants(keyword, count)
    return variants[:count]


def _stub_faq_block(topic: str, locale: str) -> list[dict[str, Any]]:
    return [
        {
            "question": f"What is {topic}?",
            "answer": f"{topic.capitalize()} is a key topic worth understanding in depth for best results.",
        },
        {
            "question": f"Why is {topic} important?",
            "answer": f"{topic.capitalize()} matters because it directly impacts outcomes and performance.",
        },
        {
            "question": f"How to get started with {topic}?",
            "answer": f"Start with {topic} by reviewing fundamentals, then apply best practices step by step.",
        },
        {
            "question": f"What are common mistakes in {topic}?",
            "answer": "Common mistakes include skipping research, ignoring measurement, and over-optimizing.",
        },
    ]


async def generate_faq_block(
    brand_id: uuid.UUID,
    topic: str,
    locale: str,
) -> list[dict[str, Any]]:
    """Generate FAQ Q&A pairs for schema.org FAQPage. Small model, batch."""
    gw = _gateway()
    schema = {
        "type": "object",
        "properties": {
            "faq": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "answer": {"type": "string"},
                    },
                },
            },
        },
    }
    prompt = FAQ_BLOCK_PROMPT.format(
        brand_graph="{}",
        locale=locale,
        register=_DEFAULT_REGISTER,
        competitor_examples=_DEFAULT_COMPETITORS,
        target_keyword=topic,
    )
    if gw._stub_mode():
        return _stub_faq_block(topic, locale)
    comp = gw.complete(
        prompt,
        tier=Tier.small,
        task="captions",
        schema=schema,
        tenant_id=brand_id,
        plan="starter",
    )
    jv = comp.json_value or {}
    faq = jv.get("faq", [])
    if not faq or len(faq) < 3:
        return _stub_faq_block(topic, locale)
    return faq
