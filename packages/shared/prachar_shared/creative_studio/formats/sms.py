"""SMS creative format spec + generator.

Part P2.13 of the PRACHAR roadmap.

The SMS format produces exactly 2 message variants (each with a character
count) plus the standard opt-out language required for compliance. SMS is
the most tightly constrained creative format — every character counts, and
regulatory rules mandate a clear opt-out instruction on every message.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from prachar_shared.ai_gateway import AIGateway, BudgetExceeded, Tier
from prachar_shared.ai_gateway.json_utils import extract_json

from ..base import CreativeFormatSpec

logger = logging.getLogger(__name__)


# Default opt-out language used when the model omits it or generation fails.
DEFAULT_OPT_OUT_LANGUAGE = "Reply STOP to unsubscribe"

# Hard SMS length ceiling (GSM-7 single-segment). Variants may exceed this only
# if the model includes the opt-out line within the message body.
SMS_MAX_CHARS = 160


SMS = CreativeFormatSpec(
    id="sms",
    label="SMS",
    description="Two SMS variants with character counts and required opt-out language.",
    output_schema={
        "type": "object",
        "properties": {
            "variants": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "char_count": {"type": "integer"},
                        "message": {"type": "string"},
                    },
                    "required": ["char_count", "message"],
                },
                "minItems": 2,
                "maxItems": 2,
            },
            "opt_out_language": {"type": "string"},
        },
        "required": ["variants", "opt_out_language"],
    },
    prompt_template=(
        "You are an SMS marketing specialist and compliance expert.\n\n"
        "Campaign:\n{campaign}\n\n"
        "Creative Direction:\n{creative_direction}\n\n"
        "Domain Context:\n{domain_context}\n\n"
        "Write exactly 2 SMS variants for this campaign.\n\n"
        "Hard constraints:\n"
        "  - Each message must be 160 characters or fewer INCLUDING the opt-out "
        "line.\n"
        "  - Every variant MUST end with the standard opt-out language "
        "(e.g. 'Reply STOP to unsubscribe').\n"
        "  - No engagement bait, no ALL-CAPS shouting, no medical/financial "
        "guarantees.\n"
        "  - Be punchy and action-oriented; lead with the offer or hook.\n\n"
        "Return JSON only, no markdown, matching this schema:\n"
        "{{\n"
        '  "variants": [\n'
        '    {{"char_count": 123, "message": "..."}},\n'
        '    {{"char_count": 118, "message": "..."}}\n'
        "  ],\n"
        '  "opt_out_language": "Reply STOP to unsubscribe"\n'
        "}}\n"
        "The char_count must equal len(message) for each variant."
    ),
    max_tokens=800,
    tier="pro",
)


# ─── Generator ─────────────────────────────────────────────────────────────


def _build_prompt(
    campaign: dict[str, Any],
    creative_direction: dict[str, Any],
    domain_context: dict[str, Any],
) -> str:
    """Fill the SMS spec's prompt template with serialised context dicts."""
    return SMS.prompt_template.format(
        campaign=json.dumps(campaign, ensure_ascii=False, default=str),
        creative_direction=json.dumps(creative_direction, ensure_ascii=False, default=str),
        domain_context=json.dumps(domain_context, ensure_ascii=False, default=str),
    )


def _parse_sms(raw: Any) -> dict[str, Any]:
    """Normalise parsed JSON into the SMS output schema.

    Guarantees:
      - ``variants`` is a list of exactly 2 dicts, each with ``char_count``
        (int) and ``message`` (str). Missing variants are filled with
        empty-message placeholders so callers always receive 2 entries.
      - ``opt_out_language`` is always a non-empty string.
    """
    if not isinstance(raw, dict):
        raw = {}

    raw_variants = raw.get("variants") or []
    if not isinstance(raw_variants, list):
        raw_variants = []

    variants: list[dict[str, Any]] = []
    for item in raw_variants[:2]:
        if not isinstance(item, dict):
            continue
        message = str(item.get("message", "")).strip()
        char_count = item.get("char_count")
        if not isinstance(char_count, int) or char_count < 0:
            char_count = len(message)
        variants.append({"char_count": char_count, "message": message})

    # Pad to exactly 2 variants with empty placeholders.
    while len(variants) < 2:
        variants.append({"char_count": 0, "message": ""})

    opt_out = str(raw.get("opt_out_language") or "").strip()
    if not opt_out:
        opt_out = DEFAULT_OPT_OUT_LANGUAGE

    return {"variants": variants[:2], "opt_out_language": opt_out}


def generate_sms(
    campaign: dict[str, Any],
    creative_direction: dict[str, Any],
    domain_context: dict[str, Any],
    *,
    gateway: AIGateway | None = None,
    tenant_id: Any = None,
    plan: str = "agency",
) -> dict[str, Any]:
    """Generate 2 SMS variants + opt-out language for a campaign.

    Builds the SMS prompt from the spec's ``prompt_template``, calls the
    AIGateway at :data:`Tier.large`, parses the JSON response via
    :func:`extract_json`, and returns a dict matching the SMS output schema::

        {
            "variants": [
                {"char_count": 123, "message": "..."},
                {"char_count": 118, "message": "..."},
            ],
            "opt_out_language": "Reply STOP to unsubscribe",
        }

    Falls back to a dict with 2 empty-message variants and the default
    opt-out language on any non-budget failure so callers always receive a
    schema-compliant dict.

    Args:
        campaign: campaign plan dict.
        creative_direction: creative direction dict.
        domain_context: domain pack context dict.
        gateway: optional AIGateway instance (a new one is created if absent).
        tenant_id: tenant UUID for budget tracking.
        plan: tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        A dict with ``variants`` (list of 2) and ``opt_out_language``.

    Raises:
        BudgetExceeded: re-raised if the tenant has exhausted its AI budget.
    """
    gw = gateway or AIGateway()
    prompt = _build_prompt(campaign, creative_direction, domain_context)

    try:
        comp = gw.complete(
            prompt=prompt,
            tier=Tier.large,
            task="creative_studio_sms",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=SMS.max_tokens,
            temperature=0.4,
            prompt_version="creative_studio_sms_v1.0",
        )
        try:
            raw = extract_json(comp.text) or {}
        except Exception:
            raw = {}
        return _parse_sms(raw)
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.warning("SMS generation failed (continuing): %s", e)
        return _parse_sms({})
