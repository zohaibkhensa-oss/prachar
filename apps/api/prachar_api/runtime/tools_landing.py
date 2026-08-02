"""Phase L3 — Landing Page Generator tool.

World-class landing pages: hero, benefits, social proof, CTA, A/B variants.
Emits landing_page artefact.
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
from .artefacts import landing_page

log = logging.getLogger("prachar.runtime.tools.landing")


@register_tool(ToolManifest(
    name="landing_page.generate",
    display_name="Landing Page Generator",
    description="Generates a conversion-optimised landing page with hero section, benefits, social proof, CTA, and 2 A/B test variants. Includes copy, layout, and design direction.",
    category=ToolCategory.LANDING_PAGE,
    input_schema={"product": "string", "audience": "string", "goal": "string", "offer": "string"},
    output_schema={"page": "object"},
    estimated_cost_usd=0.10,
    estimated_time_ms=12000,
    estimated_tokens=2500,
    estimated_latency_ms=9000,
    quality_score=0.91,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.WRITES,
    memory_categories=[MemoryCategory.BRAND, MemoryCategory.CAMPAIGN],
))
async def landing_page_generate(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Generate a conversion-optimised landing page."""
    from prachar_shared.ai_gateway import AIGateway, Tier
    from prachar_shared.ai_gateway.json_utils import extract_json

    gateway = AIGateway()
    product = input.get("product", "")
    audience = input.get("audience", "")
    goal = input.get("goal", "sign up")
    offer = input.get("offer", "")

    prompt = f"""You are a world-class landing page designer and conversion copywriter.
Create a high-converting landing page for:

Product/Service: {product}
Target Audience: {audience}
Conversion Goal: {goal}
Offer: {offer}

LANDING PAGE STRUCTURE (all sections must be conversion-optimised):

1. HERO SECTION:
   - headline: 5-10 words that communicate the core value proposition
   - subheadline: 10-20 words expanding on the headline
   - cta: 2-4 word action button text
   - hero_visual: description of the hero image/video
   - trust_indicators: badges, ratings, or social proof for hero

2. BENEFITS (3-5 benefit blocks):
   - Each: {{icon, title (3-5 words), description (1-2 sentences)}}
   - Benefits NOT features — focus on what the user gets, not what the product does

3. SOCIAL PROOF:
   - testimonials: 2-3 short testimonials with name, role, company, quote
   - metrics: 2-3 trust metrics (customers served, rating, results)
   - logos: description of logo placement

4. CTA SECTION:
   - cta_text: final push CTA copy
   - cta_button: button text
   - urgency: optional urgency element (limited time, spots left)

5. A/B VARIANTS (2 alternative versions):
   - Each variant changes the headline + hero angle
   - variant_a: emotional angle (fear of missing out, aspiration)
   - variant_b: rational angle (data, efficiency, ROI)

QUALITY REQUIREMENTS:
- Copy must be benefit-driven and audience-specific
- CTA must be specific and action-oriented
- Social proof must feel authentic (not generic)
- Mobile-first layout considerations
- Page load speed considerations (minimal heavy elements above the fold)

Return JSON:
{{
  "hero": {{"headline": "...", "subheadline": "...", "cta": "...", "hero_visual": "...", "trust_indicators": [...]}},
  "benefits": [...],
  "social_proof": {{"testimonials": [...], "metrics": [...], "logos": "..."}},
  "cta": {{"text": "...", "button": "...", "urgency": "..."}},
  "variants": [{{"angle": "emotional", "headline": "...", "subheadline": "..."}}, {{"angle": "rational", "headline": "...", "subheadline": "..."}}],
  "design_notes": "Layout, colors, typography guidance",
  "conversion_tips": "3-5 tips to maximise conversion rate"
}}"""

    response = await gateway.async_complete(
        prompt=prompt, tier=Tier.large,
        tenant_id=str(ctx.tenant_id), max_tokens=2500,
    )
    page = extract_json(response.content) or {}

    return {
        "page": page,
        "artefacts": [landing_page(
            hero=page.get("hero", {}),
            benefits=page.get("benefits", []),
            social_proof=page.get("social_proof", {}).get("testimonials", []),
            cta=page.get("cta", {}).get("button", ""),
            variants=page.get("variants", []),
        ).to_dict()],
    }
