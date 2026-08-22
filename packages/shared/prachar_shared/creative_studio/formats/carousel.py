"""Carousel creative format spec + domain-specific generator.

Part P2.6 of the CURV AI roadmap. The carousel format produces a multi-slide
carousel post: a list of slides (each with slide_no, headline, body, and a
visual_brief) plus a final CTA slide string.

The spec (``CAROUSEL``) remains a declarative ``CreativeFormatSpec`` consumed
by the generic ``CreativeStudio``. The ``generate_carousel`` function is the
domain-specific generator that builds a richer prompt, calls the AIGateway
with ``Tier.large``, parses the response via ``extract_json``, and returns a
dict ``{"slides": [...], "cta_slide": "..."}``. On any failure it falls back
to an empty dict so callers can degrade gracefully.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from prachar_shared.ai_gateway import AIGateway, BudgetExceeded, Tier
from prachar_shared.ai_gateway.json_utils import extract_json

from ..base import CreativeFormatSpec

logger = logging.getLogger(__name__)


CAROUSEL = CreativeFormatSpec(
    id="carousel",
    label="Carousel",
    description="A multi-slide carousel post with headlines, body copy, and a final CTA slide.",
    output_schema={
        "type": "object",
        "properties": {
            "slides": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "slide_no": {"type": "integer"},
                        "headline": {"type": "string"},
                        "body": {"type": "string"},
                        "visual_brief": {"type": "string"},
                    },
                    "required": ["slide_no", "headline", "body", "visual_brief"],
                },
            },
            "cta_slide": {"type": "string"},
        },
        "required": ["slides", "cta_slide"],
    },
    prompt_template=(
        "You are a social media carousel designer.\n\n"
        "Campaign:\n{campaign}\n\n"
        "Creative Direction:\n{creative_direction}\n\n"
        "Domain Context:\n{domain_context}\n\n"
        "Design a 5-8 slide carousel that tells a story or teaches a mini-lesson. "
        "Each slide has a headline, body copy, and a visual brief. End with a "
        "strong CTA slide. Return JSON matching the carousel output schema."
    ),
    max_tokens=2000,
    tier="free",
)


# ─── Domain-specific generator ──────────────────────────────────────────────


def _build_prompt(
    campaign: dict[str, Any],
    creative_direction: dict[str, Any],
    domain_context: dict[str, Any],
) -> str:
    """Assemble a rich, domain-aware carousel prompt.

    Pulls the domain label and any carousel-specific guidance from the domain
    context so the generated slides reflect the domain's voice and constraints.
    """
    domain_label = str(domain_context.get("label") or domain_context.get("id") or "business")
    domain_guidance = str(domain_context.get("carousel_prompt") or "")
    brand_name = str(campaign.get("brand_name") or campaign.get("name") or "")
    goal = str(campaign.get("goal") or "")
    hook = str(creative_direction.get("hook") or "")
    angle = str(creative_direction.get("angle") or "")
    tone = str(creative_direction.get("tone") or "")
    sample_cta = str(creative_direction.get("sample_cta") or "")

    guidance_block = f"\n{domain_guidance}\n" if domain_guidance else ""

    return (
        f"You are a master social media carousel designer for a "
        f"{domain_label.lower()} campaign.\n\n"
        f"Brand: {brand_name}\n"
        f"Goal: {goal}\n"
        f"Creative hook: {hook}\n"
        f"Angle: {angle}\n"
        f"Tone: {tone}\n"
        f"Suggested CTA: {sample_cta}\n\n"
        f"Campaign:\n{json.dumps(campaign, ensure_ascii=False, default=str)[:4000]}\n\n"
        f"Creative Direction:\n"
        f"{json.dumps(creative_direction, ensure_ascii=False, default=str)[:2000]}\n\n"
        f"{guidance_block}"
        "Design a 5-8 slide carousel that tells a story or teaches a mini-lesson "
        "tailored to this domain. Each slide must have:\n"
        "  - slide_no: integer position starting at 1\n"
        "  - headline: a punchy slide title (under 60 chars)\n"
        "  - body: 1-3 sentences of slide copy\n"
        "  - visual_brief: a short description of the slide's visual\n\n"
        "The final slide is the CTA slide — include its copy in the top-level "
        '"cta_slide" field as a strong call-to-action string.\n\n'
        "Respond as JSON only, no markdown:\n"
        "{\n"
        '  "slides": [\n'
        '    {"slide_no": 1, "headline": "...", "body": "...", "visual_brief": "..."},\n'
        '    {"slide_no": 2, "headline": "...", "body": "...", "visual_brief": "..."}\n'
        "  ],\n"
        '  "cta_slide": "..."  // the final slide\'s CTA copy\n'
        "}"
    )


def _parse_carousel(raw: Any) -> dict[str, Any]:
    """Normalise parsed JSON into the carousel output shape.

    Ensures ``slides`` is a list of dicts each carrying the four required
    fields (slide_no, headline, body, visual_brief) and ``cta_slide`` is a
    string. Malformed entries are coerced rather than dropped so the structure
    stays predictable for callers.
    """
    if not isinstance(raw, dict):
        return {}

    slides_raw = raw.get("slides")
    if not isinstance(slides_raw, list):
        slides_raw = []

    slides: list[dict[str, Any]] = []
    for idx, item in enumerate(slides_raw, start=1):
        if not isinstance(item, dict):
            continue
        slide_no = item.get("slide_no", idx)
        try:
            slide_no = int(slide_no)
        except (TypeError, ValueError):
            slide_no = idx
        slides.append(
            {
                "slide_no": slide_no,
                "headline": str(item.get("headline", "")),
                "body": str(item.get("body", "")),
                "visual_brief": str(item.get("visual_brief", "")),
            }
        )

    cta_slide = raw.get("cta_slide", "")
    if not isinstance(cta_slide, str):
        cta_slide = str(cta_slide)

    return {"slides": slides, "cta_slide": cta_slide}


def generate_carousel(
    campaign: dict[str, Any],
    creative_direction: dict[str, Any],
    domain_context: dict[str, Any],
    *,
    gateway: AIGateway,
    tenant_id: Any = None,
    plan: str = "agency",
) -> dict[str, Any]:
    """Generate a carousel (slides + cta_slide) for a campaign.

    Builds a domain-aware prompt, calls the AIGateway with ``Tier.large``,
    parses the JSON response via ``extract_json``, and returns a dict of shape
    ``{"slides": [...], "cta_slide": "..."}``.

    Falls back to an empty dict on any failure (other than ``BudgetExceeded``,
    which re-raises) so callers can degrade gracefully.

    Args:
        campaign: campaign plan dict (brand_name/name, goal, ...).
        creative_direction: creative direction dict (hook, angle, tone, ...).
        domain_context: domain pack context dict (label/id, carousel_prompt, ...).
        gateway: AIGateway instance used for the LLM call.
        tenant_id: tenant identifier for budget tracking.
        plan: tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        A dict with ``slides`` (list of slide dicts) and ``cta_slide`` (str),
        or an empty dict on failure.
    """
    prompt = _build_prompt(campaign, creative_direction, domain_context)

    try:
        comp = gateway.complete(
            prompt=prompt,
            tier=Tier.large,
            task="creative_studio_carousel",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=CAROUSEL.max_tokens,
            temperature=0.7,
            prompt_version="creative_studio_carousel_v1.0",
        )
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.warning("carousel generation failed (continuing): %s", e)
        return {}

    try:
        raw = extract_json(comp.text)
    except Exception:
        raw = None

    if raw is None:
        return {}

    return _parse_carousel(raw)
