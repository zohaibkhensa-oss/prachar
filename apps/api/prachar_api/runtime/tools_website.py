"""Phase L1 — AI Website Builder tool.

World-class website generation: site structure, page content, SEO meta,
responsive design system. Emits website_blueprint + page_content artefacts.
"""
from __future__ import annotations

import logging
from typing import Any

from .registry import (
    SideEffects,
    ToolCategory,
    ToolManifest,
    register_tool,
)
from .memory_categories import MemoryCategory
from .context import AIContext
from .artefacts import website_blueprint, page_content

log = logging.getLogger("prachar.runtime.tools.website")


@register_tool(ToolManifest(
    name="website.build",
    display_name="AI Website Builder",
    description="Generates a complete website blueprint: page structure, navigation, design system, SEO foundation, and content for each page. World-class output with conversion-optimised copy, responsive design, and search engine optimisation.",
    category=ToolCategory.WEBSITE,
    input_schema={"business_name": "string", "industry": "string", "goal": "string", "pages": "array"},
    output_schema={"blueprint": "object", "pages": "array"},
    estimated_cost_usd=0.15,
    estimated_time_ms=20000,
    estimated_tokens=4000,
    estimated_latency_ms=15000,
    quality_score=0.92,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.WRITES,
    memory_categories=[MemoryCategory.BRAND, MemoryCategory.CAMPAIGN],
))
async def website_build(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Generate a complete website blueprint with all pages."""
    from prachar_shared.ai_gateway import AIGateway, Tier

    gateway = AIGateway()
    business_name = input.get("business_name", "Your Business")
    industry = input.get("industry", "general")
    goal = input.get("goal", "generate leads")
    requested_pages = input.get("pages", ["home", "about", "services", "contact"])

    prompt = f"""You are a world-class web architect and conversion specialist. Design a complete website for:

Business: {business_name}
Industry: {industry}
Primary Goal: {goal}
Requested Pages: {', '.join(requested_pages)}

DELIVERABLES (all in one JSON response):

1. BLUEPRINT — site structure:
   - pages: list of {{slug, title, purpose, target_audience, primary_cta}}
   - navigation: main nav items with order and dropdown structure
   - design_system: {{colors (3-5 hex), typography (heading + body font), spacing_scale, button_styles, card_styles}}
   - seo_foundation: {{target_keywords, meta_template, url_structure, schema_markup_types}}

2. PAGES — full content for each page:
   For each page provide:
   - slug, title (≤60 chars for SEO), meta_description (≤155 chars)
   - headings: list of {{level, text}} (H1, H2, H3 structure)
   - body: the full page copy (markdown, 200-500 words per page)
   - cta: primary call-to-action for this page
   - seo_keywords: 3-5 target keywords for this page

QUALITY REQUIREMENTS:
- Every page must have a clear conversion goal and CTA
- Copy must be benefit-driven (not feature-driven)
- Meta descriptions must be compelling and include primary keyword
- Design system must be cohesive and industry-appropriate
- Navigation must be intuitive (max 7 top-level items)
- Mobile-first responsive design considerations
- Include accessibility notes (alt text, contrast, semantic HTML)

Return JSON only:
{{
  "blueprint": {{
    "pages": [...],
    "navigation": [...],
    "design_system": {{...}},
    "seo_foundation": {{...}}
  }},
  "pages": [...]
}}"""

    response = await gateway.async_complete(
        prompt=prompt,
        tier=Tier.large,
        tenant_id=str(ctx.tenant_id),
        max_tokens=4000,
    )

    from prachar_shared.ai_gateway.json_utils import extract_json
    result = extract_json(response.content) or {}

    blueprint = result.get("blueprint", {})
    pages = result.get("pages", [])

    artefacts = [
        website_blueprint(
            pages=blueprint.get("pages", []),
            navigation=blueprint.get("navigation", []),
            design_system=blueprint.get("design_system", {}),
            seo_foundation=blueprint.get("seo_foundation", {}),
        ).to_dict()
    ]
    for page in pages[:5]:
        artefacts.append(page_content(
            title=page.get("title", ""),
            meta_description=page.get("meta_description", ""),
            headings=page.get("headings", []),
            body=page.get("body", ""),
            cta=page.get("cta", ""),
            seo_keywords=page.get("seo_keywords", []),
        ).to_dict())

    return {"blueprint": blueprint, "pages": pages, "artefacts": artefacts}


@register_tool(ToolManifest(
    name="website.page",
    display_name="Web Page Generator",
    description="Generates a single web page with SEO-optimised content, conversion-focused copy, and structured headings.",
    category=ToolCategory.WEBSITE,
    input_schema={"page_type": "string", "business_name": "string", "topic": "string", "keywords": "array"},
    output_schema={"page": "object"},
    estimated_cost_usd=0.05,
    estimated_time_ms=8000,
    estimated_tokens=1500,
    estimated_latency_ms=6000,
    quality_score=0.88,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.BRAND],
))
async def website_page(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Generate a single web page."""
    from prachar_shared.ai_gateway import AIGateway, Tier
    from prachar_shared.ai_gateway.json_utils import extract_json

    gateway = AIGateway()
    page_type = input.get("page_type", "home")
    business_name = input.get("business_name", "Your Business")
    topic = input.get("topic", "")
    keywords = input.get("keywords", [])

    prompt = f"""You are a world-class SEO copywriter and conversion specialist.
Generate a single {page_type} page for {business_name} about: {topic}.
Target keywords: {', '.join(keywords) if keywords else 'infer from topic'}.

Return JSON:
{{
  "title": "SEO title ≤60 chars",
  "meta_description": "Compelling meta ≤155 chars with primary keyword",
  "headings": [{{"level": 1, "text": "H1"}}, {{"level": 2, "text": "H2"}}],
  "body": "Full page copy in markdown, 300-500 words, benefit-driven",
  "cta": "Primary call-to-action",
  "seo_keywords": ["keyword1", "keyword2"],
  "internal_links": [{{"anchor": "text", "target": "/page"}}],
  "image_suggestions": [{{"alt": "description", "placement": "hero|inline"}}]
}}"""

    response = await gateway.async_complete(
        prompt=prompt,
        tier=Tier.MEDIUM,
        tenant_id=str(ctx.tenant_id),
        max_tokens=1500,
    )
    page = extract_json(response.content) or {}

    return {
        "page": page,
        "artefacts": [page_content(
            title=page.get("title", ""),
            meta_description=page.get("meta_description", ""),
            headings=page.get("headings", []),
            body=page.get("body", ""),
            cta=page.get("cta", ""),
            seo_keywords=page.get("seo_keywords", []),
        ).to_dict()],
    }
