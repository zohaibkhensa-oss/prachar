"""LinkedIn creative format spec + generator.

Part P2.10 of the PRACHAR roadmap. Declares the LinkedIn creative format spec
(hook, body ≤3000 chars, cta, hashtags) and a ``generate_linkedin`` generator
that builds a prompt, calls the AIGateway, parses the JSON response via
``extract_json``, and returns a dict. Falls back to an empty dict on failure.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from prachar_shared.ai_gateway import AIGateway, BudgetExceeded, Tier
from prachar_shared.ai_gateway.json_utils import extract_json

from ..base import CreativeFormatSpec

logger = logging.getLogger(__name__)


# ─── Spec ───────────────────────────────────────────────────────────────────

LINKEDIN = CreativeFormatSpec(
    id="linkedin",
    label="LinkedIn",
    description="A LinkedIn post with a hook, body (max 3000 chars), CTA, and hashtags.",
    output_schema={
        "type": "object",
        "properties": {
            "hook": {"type": "string"},
            "body": {"type": "string", "maxLength": 3000},
            "cta": {"type": "string"},
            "hashtags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["hook", "body", "cta", "hashtags"],
    },
    prompt_template=(
        "You are a LinkedIn content strategist crafting a high-impact post.\n\n"
        "Campaign:\n{campaign}\n\n"
        "Creative Direction:\n{creative_direction}\n\n"
        "Domain Context:\n{domain_context}\n\n"
        "Write a LinkedIn post with the following structure:\n"
        "  - hook: a strong opening line that stops the scroll (1-2 sentences).\n"
        "  - body: the main post content. Professional, value-driven, and\n"
        "    formatted with line breaks for readability. MUST be at most 3000\n"
        "    characters. Lead with insight, support with evidence or story.\n"
        "  - cta: a single clear call-to-action (e.g. comment, DM, share).\n"
        "  - hashtags: 3 to 5 relevant hashtags as a list of strings (without\n"
        "    the leading # symbol).\n\n"
        "Keep the tone professional and value-driven. Do not use engagement bait.\n\n"
        "AGENCY QUALITY REQUIREMENTS (Phase I2):\n"
        "- LinkedIn rewards thought leadership — lead with a contrarian insight "
        "or data point, not a product pitch.\n"
        "- Use the 'insight → evidence → implication → CTA' structure.\n"
        "- Format with line breaks every 1-2 sentences for mobile readability.\n"
        "- Include 1-2 specific data points or examples (not generic claims).\n"
        "- rationale: explain why this post will generate engagement from "
        "professionals in this industry.\n"
        "- brand_alignment: rate 1-10 and explain in one sentence.\n"
        "- ab_variants: provide 2 alternative hooks for A/B testing.\n"
        "- target_audience: which LinkedIn audience (job titles, industries) "
        "will this resonate with?\n\n"
        "Return JSON only, no markdown, matching this shape:\n"
        "{{\n"
        '  "hook": "...",\n'
        '  "body": "...",\n'
        '  "cta": "...",\n'
        '  "hashtags": ["...", "...", "..."],\n'
        '  "rationale": "...",\n'
        '  "brand_alignment": {{"score": 8, "reason": "..."}},\n'
        '  "ab_variants": ["...", "..."],\n'
        '  "target_audience": "..."}}'
    ),
    max_tokens=2000,
    tier="pro",
)


# ─── Generator ──────────────────────────────────────────────────────────────

#: Hard character limit for the LinkedIn post body.
LINKEDIN_BODY_MAX_CHARS = 3000


def _build_prompt(
    campaign: dict[str, Any],
    creative_direction: dict[str, Any],
    domain_context: dict[str, Any],
) -> str:
    """Fill the LINKEDIN prompt_template with JSON-serialised context dicts."""
    return LINKEDIN.prompt_template.format(
        campaign=json.dumps(campaign, ensure_ascii=False, default=str),
        creative_direction=json.dumps(creative_direction, ensure_ascii=False, default=str),
        domain_context=json.dumps(domain_context, ensure_ascii=False, default=str),
    )


def _parse_linkedin(raw: Any) -> dict[str, Any]:
    """Normalise parsed JSON into a LinkedIn content dict.

    Ensures the four required keys are present and that ``body`` does not
    exceed the 3000 character LinkedIn limit (truncated if necessary).
    Missing fields default to empty strings / empty list.
    """
    if not isinstance(raw, dict):
        raw = {}

    hook = str(raw.get("hook", "") or "")
    body = str(raw.get("body", "") or "")
    cta = str(raw.get("cta", "") or "")

    hashtags_raw = raw.get("hashtags", [])
    if not isinstance(hashtags_raw, list):
        hashtags_raw = []
    hashtags = [str(h).lstrip("#").strip() for h in hashtags_raw if str(h).strip()]

    # Enforce the 3000 char body limit.
    if len(body) > LINKEDIN_BODY_MAX_CHARS:
        body = body[:LINKEDIN_BODY_MAX_CHARS]

    return {
        "hook": hook,
        "body": body,
        "cta": cta,
        "hashtags": hashtags,
        "rationale": str(raw.get("rationale", "") or ""),
        "brand_alignment": raw.get("brand_alignment") if isinstance(raw.get("brand_alignment"), dict) else {},
        "ab_variants": raw.get("ab_variants") if isinstance(raw.get("ab_variants"), list) else [],
        "target_audience": str(raw.get("target_audience", "") or ""),
    }


def generate_linkedin(
    campaign: dict[str, Any],
    creative_direction: dict[str, Any],
    domain_context: dict[str, Any],
    *,
    gateway: AIGateway,
    tenant_id: Any,
    plan: str,
) -> dict[str, Any]:
    """Generate a LinkedIn post from a campaign + creative direction.

    Builds a prompt from the LINKEDIN spec's ``prompt_template``, calls the
    AIGateway with ``Tier.large``, parses the JSON response via
    ``extract_json``, and returns a dict with ``hook``, ``body`` (≤3000 chars),
    ``cta``, and ``hashtags`` (list of strings).

    Falls back to an empty dict (``{"hook": "", "body": "", "cta": "",
    "hashtags": []}``) on any failure so callers can continue without a
    LinkedIn post. ``BudgetExceeded`` is re-raised so budget enforcement is
    never silently swallowed.

    Args:
        campaign:           campaign plan dict.
        creative_direction: creative direction dict.
        domain_context:     domain pack context dict.
        gateway:            AIGateway instance (required).
        tenant_id:          tenant UUID for budget tracking.
        plan:               tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        A dict with keys ``hook``, ``body``, ``cta``, ``hashtags``.
    """
    prompt = _build_prompt(campaign, creative_direction, domain_context)

    try:
        comp = gateway.complete(
            prompt=prompt,
            tier=Tier.large,
            task="creative_studio_linkedin",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=LINKEDIN.max_tokens,
            temperature=0.4,
            prompt_version="creative_studio_linkedin_v1.0",
        )
        try:
            raw = extract_json(comp.text)
        except Exception:
            raw = None
        if raw is None:
            raw = {}
        return _parse_linkedin(raw)
    except BudgetExceeded:
        raise
    except Exception as exc:
        logger.warning("linkedin generation failed (continuing): %s", exc)
        return _parse_linkedin({})
