"""Poster creative format spec + generator.

Part P2.4 of the CURV AI roadmap. The spec (``POSTER``) describes the poster
format's output schema and prompt template. The ``generate_poster`` function
is the generation layer — it builds a domain-aware prompt from the spec,
calls the AIGateway, parses the JSON response via ``extract_json``, and
returns a poster dict with the seven required fields:

    headline, subheadline, body, cta, visual_brief,
    color_palette (list), layout_hint

A restaurant poster is NOT the same as a clinic poster — the prompt
instructs the model to adapt copy, visual brief, and palette to the domain
context (e.g. appetising food photography + warm colours for restaurants,
calm clinical imagery + trust-building blues for clinics).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from prachar_shared.ai_gateway import AIGateway, BudgetExceeded, Tier
from prachar_shared.ai_gateway.json_utils import extract_json

from ..base import CreativeFormatSpec

logger = logging.getLogger(__name__)


# ─── Spec ──────────────────────────────────────────────────────────────────


POSTER = CreativeFormatSpec(
    id="poster",
    label="Poster",
    description="A single-image poster with headline, subheadline, body copy, and CTA.",
    output_schema={
        "type": "object",
        "properties": {
            "headline": {"type": "string"},
            "subheadline": {"type": "string"},
            "body": {"type": "string"},
            "cta": {"type": "string"},
            "visual_brief": {"type": "string"},
            "color_palette": {"type": "array", "items": {"type": "string"}},
            "layout_hint": {"type": "string"},
        },
        "required": [
            "headline",
            "subheadline",
            "body",
            "cta",
            "visual_brief",
            "color_palette",
            "layout_hint",
        ],
    },
    prompt_template=(
        "You are a senior poster designer and copywriter art-directing a "
        "single-image poster for a real brand.\n\n"
        "Campaign:\n{campaign}\n\n"
        "Creative Direction:\n{creative_direction}\n\n"
        "Domain Context:\n{domain_context}\n\n"
        "DOMAIN-AWARENESS RULES (critical):\n"
        "- Read the Domain Context carefully. The poster MUST feel native to "
        "this domain — a restaurant poster is NOT the same as a clinic poster.\n"
        "- For food/restaurant domains: lead with appetite appeal, use warm "
        "colours (reds, oranges, amber), show the dish/ambience, sensory copy, "
        "urgency for offers.\n"
        "- For clinic/healthcare domains: lead with trust and reassurance, use "
        "calm colours (blues, teals, whites), show clean professional imagery, "
        "empathetic copy, clear next-step CTA (book/consult).\n"
        "- For retail/e-commerce domains: lead with the offer/product hero, "
        "bold colours, price-led copy, shop-now CTA.\n"
        "- For professional/B2B domains: lead with credibility and outcome, "
        "muted sophisticated palette, data-backed copy, lead-gen CTA.\n"
        "- Adapt tone, imagery, palette, and CTA to whatever domain context "
        "is provided above. Do NOT use a generic one-size-fits-all poster.\n\n"
        "POSTER STRUCTURE:\n"
        "- headline: a punchy 3-8 word headline that stops the scroll.\n"
        "- subheadline: a supporting line (under 15 words) that adds context.\n"
        "- body: 1-3 sentences of body copy expanding the value proposition.\n"
        "- cta: a single clear call-to-action (2-5 words).\n"
        "- visual_brief: a 1-2 sentence description of the hero image / visual "
        "concept for the designer, domain-appropriate.\n"
        "- color_palette: a list of 3-5 colours (hex codes or names) matching "
        "the domain mood.\n"
        "- layout_hint: a short description of the layout (e.g. 'hero image "
        "top 60%, copy bottom 40% left-aligned').\n\n"
        "AGENCY QUALITY REQUIREMENTS (Phase I2):\n"
        "- rationale: explain WHY you chose this concept — what emotion does "
        "it evoke, why will it stop the scroll, what makes it brand-aligned?\n"
        "- brand_alignment: rate 1-10 how well this poster matches the brand "
        "voice and explain the score in one sentence.\n"
        "- ab_variants: provide 2 alternative headlines with different angles "
        "(emotional, rational, urgency) for A/B testing.\n"
        "- cta_optimisation: explain why this CTA will drive action and suggest "
        "1 alternative CTA to test.\n"
        "- platform_notes: how should this poster be adapted for Instagram "
        "(square 1:1), Stories (9:16), and feed (4:5)?\n\n"
        "Return JSON only, no markdown fences, matching exactly this schema:\n"
        "{{\n"
        '  "headline": "...",\n'
        '  "subheadline": "...",\n'
        '  "body": "...",\n'
        '  "cta": "...",\n'
        '  "visual_brief": "...",\n'
        '  "color_palette": ["#...", "#...", "#..."],\n'
        '  "layout_hint": "...",\n'
        '  "rationale": "Why this concept works...",\n'
        '  "brand_alignment": {{"score": 8, "reason": "..."}},\n'
        '  "ab_variants": [{{"angle": "emotional", "headline": "..."}}, {{"angle": "rational", "headline": "..."}}],\n'
        '  "cta_optimisation": {{"primary": "...", "reason": "...", "alternative": "..."}},\n'
        '  "platform_notes": "..."}}'
    ),
    max_tokens=1200,
    tier="free",
)


# ─── Required output fields (used for fallback normalisation) ───────────────


_POSTER_FIELDS: tuple[str, ...] = (
    "headline",
    "subheadline",
    "body",
    "cta",
    "visual_brief",
    "color_palette",
    "layout_hint",
    "rationale",
    "brand_alignment",
    "ab_variants",
    "cta_optimisation",
    "platform_notes",
)


def _normalise(raw: Any) -> dict[str, Any]:
    """Coerce the parsed JSON into a poster dict with all required fields.

    Missing fields are filled with sensible empty defaults so callers always
    receive a dict with the full schema. ``color_palette`` is guaranteed to
    be a list.
    """
    if not isinstance(raw, dict):
        raw = {}
    poster: dict[str, Any] = {}
    for field in _POSTER_FIELDS:
        val = raw.get(field)
        if field == "color_palette":
            if isinstance(val, list):
                poster[field] = [str(c) for c in val]
            else:
                poster[field] = []
        elif field in ("brand_alignment", "cta_optimisation"):
            poster[field] = val if isinstance(val, dict) else {}
        elif field == "ab_variants":
            poster[field] = val if isinstance(val, list) else []
        else:
            poster[field] = str(val) if val is not None else ""
    return poster


# ─── Generator ──────────────────────────────────────────────────────────────


def generate_poster(
    campaign: dict[str, Any],
    creative_direction: dict[str, Any],
    domain_context: dict[str, Any],
    *,
    gateway: AIGateway,
    tenant_id: Any,
    plan: str,
) -> dict[str, Any]:
    """Generate a single poster for a campaign.

    Builds a domain-aware prompt from the ``POSTER`` spec's ``prompt_template``,
    calls ``AIGateway.complete`` (using ``Tier.large``), parses the JSON
    response via ``extract_json``, and returns a poster dict containing all
    seven required fields (headline, subheadline, body, cta, visual_brief,
    color_palette, layout_hint).

    Falls back to an empty-valued poster dict (all fields present but empty)
    on any failure other than ``BudgetExceeded`` (which re-raises), so the
    caller always receives a well-formed dict.

    Args:
        campaign: the campaign plan dict.
        creative_direction: the creative direction dict.
        domain_context: the domain pack context dict (drives domain-awareness).
        gateway: an :class:`AIGateway` instance.
        tenant_id: tenant UUID for budget tracking.
        plan: tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        A dict with keys headline, subheadline, body, cta, visual_brief,
        color_palette (list), layout_hint.
    """
    prompt = POSTER.prompt_template.format(
        campaign=json.dumps(campaign, ensure_ascii=False, default=str),
        creative_direction=json.dumps(creative_direction, ensure_ascii=False, default=str),
        domain_context=json.dumps(domain_context, ensure_ascii=False, default=str),
    )

    try:
        comp = gateway.complete(
            prompt=prompt,
            tier=Tier.large,
            schema=POSTER.output_schema,
            task="creative_studio_poster",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=POSTER.max_tokens,
            temperature=0.4,
            prompt_version="creative_studio_poster_v1.0",
        )
        # Prefer pre-parsed json_value from the gateway, fall back to extract_json
        raw: Any = None
        if comp.json_value is not None and isinstance(comp.json_value, dict):
            raw = comp.json_value
        else:
            try:
                raw = extract_json(comp.text)
            except Exception:
                raw = None
        return _normalise(raw)
    except BudgetExceeded:
        raise
    except Exception as exc:
        logger.warning("Poster generation failed (continuing): %s", exc)
        return _normalise({})
