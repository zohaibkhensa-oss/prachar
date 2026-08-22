"""Landing Page creative format spec + generator.

Part P2.12 of the CURV AI roadmap. Defines the ``landing_page`` creative
format — a high-converting landing page with a hero section, exactly 3
benefit points, a social proof section, an FAQ list, a primary CTA, and the
form fields to collect — plus a ``generate_landing_page`` function that
builds a prompt, calls the AIGateway, parses the JSON via ``extract_json``,
and returns the content dict.

On any failure the generator falls back to an empty dict (with normalised
empty defaults for the required list fields) so the campaign preview still
works without a landing page.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from prachar_shared.ai_gateway import AIGateway, BudgetExceeded, Tier
from prachar_shared.ai_gateway.json_utils import extract_json

from ..base import CreativeFormatSpec

logger = logging.getLogger(__name__)


LANDING_PAGE = CreativeFormatSpec(
    id="landing_page",
    label="Landing Page",
    description="A landing page with hero section, benefits, social proof, FAQ, CTA, and form fields.",
    output_schema={
        "type": "object",
        "properties": {
            "hero_headline": {"type": "string"},
            "hero_subhead": {"type": "string"},
            "benefits": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
            "social_proof_section": {"type": "string"},
            "faq": {"type": "array", "items": {"type": "string"}},
            "cta": {"type": "string"},
            "form_fields": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["hero_headline", "hero_subhead", "benefits", "social_proof_section", "faq", "cta", "form_fields"],
    },
    prompt_template=(
        "You are a conversion-focused landing page designer.\n\n"
        "Campaign:\n{campaign}\n\n"
        "Creative Direction:\n{creative_direction}\n\n"
        "Domain Context:\n{domain_context}\n\n"
        "Design a high-converting landing page for this campaign. Produce:\n"
        "  - hero_headline: a bold, benefit-driven headline (one line)\n"
        "  - hero_subhead: a supporting subheadline that clarifies the offer\n"
        "  - benefits: EXACTLY 3 concise benefit points, each a single string\n"
        "  - social_proof_section: a short description of the social proof to\n"
        "    display (testimonials, logos, stats, ratings)\n"
        "  - faq: a list of FAQ questions (strings) addressing common objections\n"
        "  - cta: the primary call-to-action button text\n"
        "  - form_fields: a list of form field labels to collect from visitors\n\n"
        "Return JSON only, no markdown fences, matching this shape:\n"
        "{{\n"
        '  "hero_headline": "...",\n'
        '  "hero_subhead": "...",\n'
        '  "benefits": ["...", "...", "..."],\n'
        '  "social_proof_section": "...",\n'
        '  "faq": ["...", "..."],\n'
        '  "cta": "...",\n'
        '  "form_fields": ["...", "..."]\n'
        "}}"
    ),
    max_tokens=2500,
    tier="enterprise",
)


# ─── Generator ──────────────────────────────────────────────────────────────


def _normalise(raw: Any) -> dict[str, Any]:
    """Normalise parsed JSON into a valid landing-page content dict.

    Ensures every required key exists with the correct type and that
    ``benefits`` always contains exactly 3 strings (padding / trimming as
    needed). Other list fields (``faq``, ``form_fields``) default to empty
    lists when missing or malformed.
    """
    if not isinstance(raw, dict):
        raw = {}

    def _str(key: str) -> str:
        val = raw.get(key)
        return val if isinstance(val, str) else ""

    def _str_list(key: str) -> list[str]:
        val = raw.get(key)
        if not isinstance(val, list):
            return []
        return [str(item) for item in val if item is not None]

    benefits = _str_list("benefits")
    # Pad / trim to exactly 3 benefit points.
    while len(benefits) < 3:
        benefits.append("")
    benefits = benefits[:3]

    return {
        "hero_headline": _str("hero_headline"),
        "hero_subhead": _str("hero_subhead"),
        "benefits": benefits,
        "social_proof_section": _str("social_proof_section"),
        "faq": _str_list("faq"),
        "cta": _str("cta"),
        "form_fields": _str_list("form_fields"),
    }


def generate_landing_page(
    campaign: dict[str, Any],
    creative_direction: dict[str, Any],
    domain_context: dict[str, Any],
    *,
    gateway: AIGateway,
    tenant_id: Any,
    plan: str,
) -> dict[str, Any]:
    """Generate a landing page for a campaign.

    Builds a prompt from the ``LANDING_PAGE`` spec's ``prompt_template``,
    calls the AIGateway with :attr:`Tier.large`, parses the JSON response via
    :func:`extract_json`, and returns a normalised dict containing
    ``hero_headline``, ``hero_subhead``, ``benefits`` (exactly 3 strings),
    ``social_proof_section``, ``faq`` (list), ``cta``, and ``form_fields``
    (list).

    Falls back to an empty-but-well-formed dict on any failure (other than
    :class:`BudgetExceeded`, which is re-raised) so the campaign preview
    still works without a landing page.

    Args:
        campaign: the campaign plan dict.
        creative_direction: the creative direction dict.
        domain_context: the domain pack context dict.
        gateway: an :class:`AIGateway` instance.
        tenant_id: tenant UUID for budget tracking.
        plan: tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        A dict with the landing page content (see module docstring).
    """
    prompt = LANDING_PAGE.prompt_template.format(
        campaign=json.dumps(campaign, ensure_ascii=False, default=str),
        creative_direction=json.dumps(creative_direction, ensure_ascii=False, default=str),
        domain_context=json.dumps(domain_context, ensure_ascii=False, default=str),
    )

    try:
        comp = gateway.complete(
            prompt=prompt,
            tier=Tier.large,
            schema=LANDING_PAGE.output_schema,
            task="creative_studio_landing_page",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=LANDING_PAGE.max_tokens,
            temperature=0.4,
            prompt_version="creative_studio_landing_page_v1.0",
        )
        # Prefer pre-parsed json_value from the gateway, fall back to extract_json.
        raw: Any = None
        if getattr(comp, "json_value", None) is not None and isinstance(comp.json_value, dict):
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
        logger.warning("landing_page generation failed (continuing): %s", exc)
        return _normalise({})
