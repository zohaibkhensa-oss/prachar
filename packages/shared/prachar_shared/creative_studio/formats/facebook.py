"""Facebook creative format spec + generator.

Part P2.9 of the PRACHAR roadmap. Defines the Facebook format spec (copy ≤500
chars, image_brief, link_description) and a ``generate_facebook`` function that
builds a prompt, calls the AIGateway with ``Tier.large``, parses the response via
``extract_json``, and returns a dict. Falls back to an empty dict on any failure
so callers can degrade gracefully.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from prachar_shared.ai_gateway import AIGateway, BudgetExceeded, Tier
from prachar_shared.ai_gateway.json_utils import extract_json

from ..base import CreativeFormatSpec

logger = logging.getLogger(__name__)

# Maximum length of the Facebook post copy (characters).
MAX_COPY_CHARS = 500

FACEBOOK = CreativeFormatSpec(
    id="facebook",
    label="Facebook",
    description="A Facebook post with copy (max 500 chars), image brief, and link description.",
    output_schema={
        "type": "object",
        "properties": {
            "copy": {"type": "string", "maxLength": MAX_COPY_CHARS},
            "image_brief": {"type": "string"},
            "link_description": {"type": "string"},
        },
        "required": ["copy", "image_brief", "link_description"],
    },
    prompt_template=(
        "You are a Facebook ads copywriter crafting a scroll-stopping post.\n\n"
        "Campaign:\n{campaign}\n\n"
        "Creative Direction:\n{creative_direction}\n\n"
        "Domain Context:\n{domain_context}\n\n"
        "Write a Facebook post with three fields:\n"
        "  - copy: the post text, max 500 characters, engaging and platform-native.\n"
        "  - image_brief: a concise visual brief for the accompanying image (subject, mood, style).\n"
        "  - link_description: a short description shown under the link preview.\n\n"
        "Keep the copy under 500 characters. Be authentic — no engagement bait.\n\n"
        "AGENCY QUALITY REQUIREMENTS (Phase I2):\n"
        "- Facebook rewards storytelling — start with a relatable hook, build "
        "with social proof, end with a clear CTA.\n"
        "- Use the first 3 lines as the 'see more' hook — they're what shows "
        "before the fold.\n"
        "- Include social proof where possible (customer count, ratings, testimonials).\n"
        "- rationale: explain why this copy will stop the scroll and drive action.\n"
        "- brand_alignment: rate 1-10 and explain in one sentence.\n"
        "- ab_variants: provide 2 alternative opening hooks for A/B testing.\n"
        "- audience_targeting: which audience segment will this resonate with most?\n\n"
        "Respond as JSON only, no markdown:\n"
        "{{\n"
        '  "copy": "...",\n'
        '  "image_brief": "...",\n'
        '  "link_description": "...",\n'
        '  "rationale": "...",\n'
        '  "brand_alignment": {{"score": 8, "reason": "..."}},\n'
        '  "ab_variants": ["...", "..."],\n'
        '  "audience_targeting": "..."}}'
    ),
    max_tokens=1000,
    tier="free",
)


def _build_prompt(campaign: dict[str, Any], creative_direction: dict[str, Any], domain_context: dict[str, Any]) -> str:
    """Fill the FACEBOOK prompt template with JSON-serialised context dicts."""
    return FACEBOOK.prompt_template.format(
        campaign=json.dumps(campaign, ensure_ascii=False, default=str),
        creative_direction=json.dumps(creative_direction, ensure_ascii=False, default=str),
        domain_context=json.dumps(domain_context, ensure_ascii=False, default=str),
    )


def _parse_facebook(raw: Any) -> dict[str, Any]:
    """Normalise the parsed JSON into a facebook output dict.

    Ensures the three required keys (copy, image_brief, link_description) are
    present as strings and that ``copy`` does not exceed ``MAX_COPY_CHARS``.
    """
    if not isinstance(raw, dict):
        return {}

    copy = str(raw.get("copy", "") or "")
    if len(copy) > MAX_COPY_CHARS:
        copy = copy[:MAX_COPY_CHARS]

    image_brief = str(raw.get("image_brief", "") or "")
    link_description = str(raw.get("link_description", "") or "")

    return {
        "copy": copy,
        "image_brief": image_brief,
        "link_description": link_description,
        "rationale": str(raw.get("rationale", "") or ""),
        "brand_alignment": raw.get("brand_alignment") if isinstance(raw.get("brand_alignment"), dict) else {},
        "ab_variants": raw.get("ab_variants") if isinstance(raw.get("ab_variants"), list) else [],
        "audience_targeting": str(raw.get("audience_targeting", "") or ""),
    }


def generate_facebook(
    campaign: dict[str, Any],
    creative_direction: dict[str, Any],
    domain_context: dict[str, Any],
    *,
    gateway: AIGateway,
    tenant_id: Any,
    plan: str,
) -> dict[str, Any]:
    """Generate a Facebook post (copy, image_brief, link_description).

    Builds a prompt from the campaign, creative direction, and domain context,
    calls the AIGateway with ``Tier.large``, parses the JSON response via
    ``extract_json``, and returns a dict with the three required fields. The
    ``copy`` field is truncated to 500 characters if the model exceeds the limit.

    Falls back to an empty dict on any failure (except ``BudgetExceeded`` which
    is re-raised) so callers can degrade gracefully.

    Args:
        campaign: the campaign plan dict.
        creative_direction: the creative direction dict.
        domain_context: the domain pack context dict.
        gateway: an AIGateway instance used for the LLM call.
        tenant_id: tenant identifier for budget tracking.
        plan: tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        A dict with keys ``copy`` (≤500 chars), ``image_brief``, and
        ``link_description``. Returns ``{}`` on failure.
    """
    prompt = _build_prompt(campaign, creative_direction, domain_context)

    try:
        comp = gateway.complete(
            prompt=prompt,
            tier=Tier.large,
            schema=FACEBOOK.output_schema,
            task="creative_studio_facebook",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=FACEBOOK.max_tokens,
            temperature=0.4,
            prompt_version="creative_studio_facebook_v1.0",
        )
        try:
            raw = extract_json(comp.text)
        except Exception:
            raw = None
        return _parse_facebook(raw)
    except BudgetExceeded:
        raise
    except Exception as exc:
        logger.warning("facebook generation failed (continuing): %s", exc)
        return {}
