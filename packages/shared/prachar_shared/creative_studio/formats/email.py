"""Email creative format spec + generator.

Part P2.11 of the PRACHAR roadmap. The Email format produces:
  - subject_lines:   exactly 3 A/B/n subject line variants
  - preview_text:    the preheader / preview text line
  - body_html_brief: a description of the email layout and key sections
  - cta:             the primary call-to-action
  - ps_line:         the postscript line

The spec (``EMAIL``) is the declarative contract used by the format-agnostic
``CreativeStudio`` engine. The ``generate_email`` function is a domain-specific
generator that builds a richer prompt, calls the AIGateway, parses the JSON
response via ``extract_json``, and returns a dict with exactly 3 subject lines.
On any failure it falls back to an empty dict so callers can continue.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from prachar_shared.ai_gateway import AIGateway, BudgetExceeded, Tier
from prachar_shared.ai_gateway.json_utils import extract_json
from prachar_shared.creative_studio.base import CreativeFormatSpec

logger = logging.getLogger(__name__)


EMAIL = CreativeFormatSpec(
    id="email",
    label="Email",
    description="An email campaign with 3 subject line variants, preview text, body brief, CTA, and PS line.",
    output_schema={
        "type": "object",
        "properties": {
            "subject_lines": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
            "preview_text": {"type": "string"},
            "body_html_brief": {"type": "string"},
            "cta": {"type": "string"},
            "ps_line": {"type": "string"},
        },
        "required": ["subject_lines", "preview_text", "body_html_brief", "cta", "ps_line"],
    },
    prompt_template=(
        "You are an expert email marketing copywriter crafting a high-converting "
        "email campaign.\n\n"
        "Campaign:\n{campaign}\n\n"
        "Creative Direction:\n{creative_direction}\n\n"
        "Domain Context:\n{domain_context}\n\n"
        "Write an email campaign with these elements:\n"
        "  - subject_lines: exactly 3 distinct subject line variants for A/B/n "
        "testing (each ≤ 60 characters, different angles/hooks)\n"
        "  - preview_text: a preheader line that complements the subject (≤ 90 "
        "characters)\n"
        "  - body_html_brief: a concise description of the email layout and key "
        "sections (hero, benefits, proof, CTA block)\n"
        "  - cta: the primary call-to-action button text\n"
        "  - ps_line: a postscript line that reinforces the offer or adds urgency\n\n"
        "Tailor the tone, offer framing, and language to the domain context. "
        "Do NOT use engagement-bait or make guaranteed-results claims.\n\n"
        "Respond as JSON only, no markdown:\n"
        "{{\n"
        '  "subject_lines": ["...", "...", "..."],\n'
        '  "preview_text": "...",\n'
        '  "body_html_brief": "...",\n'
        '  "cta": "...",\n'
        '  "ps_line": "..."\n'
        "}}"
    ),
    max_tokens=2000,
    tier="pro",
)


# ─── Generator ──────────────────────────────────────────────────────────────


def _build_prompt(
    campaign: dict[str, Any],
    creative_direction: dict[str, Any],
    domain_context: dict[str, Any],
) -> str:
    """Assemble the email generation prompt from the three context dicts."""
    campaign_json = json.dumps(campaign, ensure_ascii=False, default=str)
    cd_json = json.dumps(creative_direction, ensure_ascii=False, default=str)
    domain_json = json.dumps(domain_context, ensure_ascii=False, default=str)
    return EMAIL.prompt_template.format(
        campaign=campaign_json,
        creative_direction=cd_json,
        domain_context=domain_json,
    )


def _normalise(raw: Any) -> dict[str, Any]:
    """Normalise parsed JSON into the email output dict.

    Ensures exactly 3 subject lines are present (padding/truncating as needed)
    and that all required keys exist as strings.
    """
    if not isinstance(raw, dict):
        raw = {}

    subject_lines = raw.get("subject_lines")
    if not isinstance(subject_lines, list):
        subject_lines = []
    # Coerce every entry to a string and drop non-string junk.
    subject_lines = [str(s) for s in subject_lines if s is not None]
    # Pad to exactly 3 with empty strings if the model returned fewer.
    while len(subject_lines) < 3:
        subject_lines.append("")
    # Truncate to exactly 3 if the model returned more.
    subject_lines = subject_lines[:3]

    return {
        "subject_lines": subject_lines,
        "preview_text": str(raw.get("preview_text", "")),
        "body_html_brief": str(raw.get("body_html_brief", "")),
        "cta": str(raw.get("cta", "")),
        "ps_line": str(raw.get("ps_line", "")),
    }


def generate_email(
    campaign: dict[str, Any],
    creative_direction: dict[str, Any],
    domain_context: dict[str, Any],
    *,
    gateway: AIGateway | None = None,
    tenant_id: Any = None,
    plan: str = "agency",
) -> dict[str, Any]:
    """Generate an email campaign creative.

    Builds a prompt from the campaign, creative direction, and domain context,
    calls the AIGateway with :attr:`Tier.large`, parses the JSON response via
    ``extract_json``, and returns a dict with the keys ``subject_lines`` (a
    list of exactly 3 strings), ``preview_text``, ``body_html_brief``,
    ``cta``, and ``ps_line``.

    Falls back to an empty-valued dict (3 empty subject lines) on any failure
    so callers can continue without the email creative.

    Args:
        campaign: the campaign plan dict.
        creative_direction: the creative direction dict.
        domain_context: the domain pack context dict.
        gateway: optional AIGateway instance (a new one is created if absent).
        tenant_id: tenant identifier for budget tracking.
        plan: tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        A dict with ``subject_lines`` (exactly 3 strings), ``preview_text``,
        ``body_html_brief``, ``cta``, and ``ps_line``.
    """
    gw = gateway or AIGateway()
    prompt = _build_prompt(campaign, creative_direction, domain_context)

    try:
        comp = gw.complete(
            prompt=prompt,
            tier=Tier.large,
            task="creative_studio_email",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=EMAIL.max_tokens,
            temperature=0.7,
            prompt_version="creative_studio_email_v1.0",
        )
        try:
            raw = extract_json(comp.text)
        except Exception:
            raw = None
        return _normalise(raw)
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.warning("email generation failed (continuing): %s", e)
        return _normalise({})
