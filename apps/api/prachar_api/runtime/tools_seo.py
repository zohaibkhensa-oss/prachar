"""Phase L2 — SEO Optimiser tool.

World-class SEO: keyword research, on-page SEO, technical audit, SERP tracking.
Emits seo_audit + keyword_grid artefacts.
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
from .artefacts import seo_audit, keyword_grid

log = logging.getLogger("prachar.runtime.tools.seo")


@register_tool(ToolManifest(
    name="seo.keywords",
    display_name="Keyword Research",
    description="Discovers high-value keywords with search volume, difficulty, intent, and ranking potential. Includes long-tail variations and question keywords for featured snippets.",
    category=ToolCategory.SEO,
    input_schema={"topic": "string", "industry": "string", "location": "string", "limit": "number"},
    output_schema={"keywords": "array", "total_volume": "number"},
    estimated_cost_usd=0.08,
    estimated_time_ms=10000,
    estimated_tokens=2000,
    estimated_latency_ms=8000,
    quality_score=0.90,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.BRAND, MemoryCategory.PERFORMANCE],
))
async def seo_keywords(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Research keywords for a topic."""
    from prachar_shared.ai_gateway import AIGateway, Tier
    from prachar_shared.ai_gateway.json_utils import extract_json

    gateway = AIGateway()
    topic = input.get("topic", "")
    industry = input.get("industry", "general")
    location = input.get("location", "global")
    limit = input.get("limit", 20)

    prompt = f"""You are a world-class SEO strategist. Research keywords for:
Topic: {topic}
Industry: {industry}
Location: {location}

Provide {limit} keywords with:
- keyword: the search term
- search_volume: estimated monthly searches (number)
- difficulty: 1-100 (higher = harder to rank)
- intent: "informational" | "commercial" | "transactional" | "navigational"
- opportunity: "high" | "medium" | "low" (based on volume vs difficulty)
- serp_features: list of features present (featured_snippet, people_also_ask, local_pack, etc.)
- recommended_page: what page type to create for this keyword
- long_tail_variations: 2-3 related long-tail keywords

Include a mix of:
- 30% head terms (high volume, high difficulty)
- 40% mid-tail (medium volume, medium difficulty)
- 30% long-tail (lower volume, lower difficulty, higher conversion intent)

Return JSON: {{"keywords": [...], "total_volume": 12345}}"""

    response = await gateway.async_complete(
        prompt=prompt, tier=Tier.large,
        tenant_id=str(ctx.tenant_id), max_tokens=2000,
    )
    result = extract_json(response.content) or {}
    keywords = result.get("keywords", [])

    return {
        "keywords": keywords,
        "total_volume": result.get("total_volume", 0),
        "artefacts": [keyword_grid(
            keywords=keywords,
            total_volume=result.get("total_volume", 0),
        ).to_dict()],
    }


@register_tool(ToolManifest(
    name="seo.audit",
    display_name="SEO Audit",
    description="Audits a website or page for SEO issues: meta tags, headings, content quality, technical SEO, mobile-friendliness, page speed, and structured data. Provides prioritised recommendations.",
    category=ToolCategory.SEO,
    input_schema={"url": "string", "target_keyword": "string"},
    output_schema={"score": "number", "issues": "array", "recommendations": "array"},
    estimated_cost_usd=0.06,
    estimated_time_ms=8000,
    estimated_tokens=1500,
    estimated_latency_ms=6000,
    quality_score=0.88,
    supports_streaming=False,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.PERFORMANCE],
))
async def seo_audit_tool(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Audit a URL for SEO issues."""
    from prachar_shared.ai_gateway import AIGateway, Tier
    from prachar_shared.ai_gateway.json_utils import extract_json

    gateway = AIGateway()
    url = input.get("url", "")
    keyword = input.get("target_keyword", "")

    prompt = f"""You are a world-class technical SEO auditor. Audit this page:
URL: {url}
Target Keyword: {keyword}

Evaluate across these dimensions (score each 0-100):
1. On-Page SEO (title, meta description, H1, content relevance)
2. Technical SEO (page speed, mobile-friendly, crawlability, indexability)
3. Content Quality (word count, keyword density, LSI keywords, readability)
4. Structured Data (schema markup, rich snippet eligibility)
5. User Experience (CTR optimization, bounce rate factors, core web vitals)

Return JSON:
{{
  "score": 75,
  "issues": [
    {{"category": "On-Page", "severity": "high", "issue": "Missing meta description", "fix": "Add a 155-char meta description with the primary keyword"}},
    {{"category": "Technical", "severity": "medium", "issue": "No schema markup", "fix": "Add Organization schema markup"}}
  ],
  "recommendations": [
    {{"priority": "high", "action": "Optimize title tag", "expected_impact": "+15% CTR", "effort": "quick win"}},
    {{"priority": "medium", "action": "Add FAQ schema", "expected_impact": "Featured snippet eligibility", "effort": "1 hour"}}
  ],
  "passed": ["H1 present", "Mobile-responsive", "SSL enabled"]
}}"""

    response = await gateway.async_complete(
        prompt=prompt, tier=Tier.MEDIUM,
        tenant_id=str(ctx.tenant_id), max_tokens=1500,
    )
    result = extract_json(response.content) or {}

    return {
        "score": result.get("score", 0),
        "issues": result.get("issues", []),
        "recommendations": result.get("recommendations", []),
        "passed": result.get("passed", []),
        "artefacts": [seo_audit(
            score=result.get("score", 0),
            issues=result.get("issues", []),
            recommendations=result.get("recommendations", []),
            passed=result.get("passed", []),
        ).to_dict()],
    }


@register_tool(ToolManifest(
    name="seo.optimise",
    display_name="On-Page SEO Optimiser",
    description="Optimises page content for a target keyword: title tag, meta description, headings, content structure, internal links, and schema markup suggestions.",
    category=ToolCategory.SEO,
    input_schema={"content": "string", "target_keyword": "string", "page_type": "string"},
    output_schema={"optimised": "object"},
    estimated_cost_usd=0.05,
    estimated_time_ms=6000,
    estimated_tokens=1200,
    estimated_latency_ms=5000,
    quality_score=0.87,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.BRAND],
))
async def seo_optimise(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Optimise page content for a target keyword."""
    from prachar_shared.ai_gateway import AIGateway, Tier
    from prachar_shared.ai_gateway.json_utils import extract_json

    gateway = AIGateway()
    content = input.get("content", "")
    keyword = input.get("target_keyword", "")
    page_type = input.get("page_type", "blog")

    prompt = f"""You are a world-class on-page SEO optimiser.
Optimise this {page_type} page content for the keyword: "{keyword}"

Current content:
{content[:3000]}

Return JSON with:
{{
  "title_tag": "Optimised title ≤60 chars with keyword near front",
  "meta_description": "Compelling meta ≤155 chars with keyword",
  "h1": "Optimised H1 with keyword",
  "headings": [{{"level": 2, "text": "H2 with related keyword"}}],
  "content_suggestions": "Specific changes to improve keyword relevance",
  "internal_link_opportunities": [{{"anchor": "text", "target": "/page"}}],
  "schema_markup": "Recommended schema type and key properties",
  "keyword_density": "Recommended density % and placement strategy",
  "lsi_keywords": ["related keyword 1", "related keyword 2"]
}}"""

    response = await gateway.async_complete(
        prompt=prompt, tier=Tier.MEDIUM,
        tenant_id=str(ctx.tenant_id), max_tokens=1200,
    )
    result = extract_json(response.content) or {}

    return {"optimised": result}
