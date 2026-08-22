"""WhatsApp creative format spec + generator.

Part P2.8 of the CURV AI roadmap. Defines the declarative WhatsApp
``CreativeFormatSpec`` (status text, status image brief, compliance-aware
broadcast message) and a standalone ``generate_whatsapp`` generator that
builds the prompt, calls the AIGateway, parses the JSON response via
``extract_json``, and returns a dict.

The broadcast message is compliance-aware: it must include opt-in language
and opt-out guidance, avoid spam language, and respect WhatsApp Business
policy. On any failure the generator falls back to an empty dict so the
caller can continue without a WhatsApp creative.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from prachar_shared.ai_gateway import AIGateway, BudgetExceeded, Tier
from prachar_shared.ai_gateway.json_utils import extract_json

from ..base import CreativeFormatSpec

logger = logging.getLogger(__name__)


WHATSAPP = CreativeFormatSpec(
    id="whatsapp",
    label="WhatsApp",
    description="WhatsApp status text, status image brief, and a compliance-aware broadcast message.",
    output_schema={
        "type": "object",
        "properties": {
            "status_text": {"type": "string", "maxLength": 139},
            "status_image_brief": {"type": "string"},
            "broadcast_message": {"type": "string"},
        },
        "required": ["status_text", "status_image_brief", "broadcast_message"],
    },
    prompt_template=(
        "You are a WhatsApp marketing specialist for the Indian market.\n\n"
        "Campaign:\n{campaign}\n\n"
        "Creative Direction:\n{creative_direction}\n\n"
        "Domain Context:\n{domain_context}\n\n"
        "Produce three WhatsApp assets:\n"
        "1. status_text — a short, punchy WhatsApp status update (max 139 "
        "characters). No emojis-only, no hashtags spam. Should feel personal "
        "and conversational, like a friend's status.\n"
        "2. status_image_brief — a concise art-direction brief for the status "
        "image (subject, mood, colours, text overlay if any).\n"
        "3. broadcast_message — a compliance-aware broadcast message. It MUST:\n"
        "   - be sent only to users who have opted in (state the opt-in "
        "expectation in a short note),\n"
        "   - avoid spam language (no ALL-CAPS urgency, no 'GUARANTEED', no "
        "medical/financial claims),\n"
        "   - include clear opt-out guidance (e.g. 'Reply STOP to opt out'),\n"
        "   - respect WhatsApp Business policy (no promotional content to users "
        "outside the 24-hour session window without an approved template),\n"
        "   - stay under 1024 characters.\n\n"
        "AGENCY QUALITY REQUIREMENTS (Phase I2):\n"
        "- WhatsApp is conversational — write like you're texting a friend, "
        "not writing an ad. Use casual Hindi-English mix if appropriate.\n"
        "- Use 1-2 emojis max (not spammy). Use them to convey emotion, not "
        "decoration.\n"
        "- Create urgency without being pushy — 'Limited seats' not 'HURRY UP!!!'\n"
        "- rationale: explain why this messaging will feel native to WhatsApp "
        "and not like spam.\n"
        "- brand_alignment: rate 1-10 and explain in one sentence.\n"
        "- ab_variants: provide 2 alternative status texts with different "
        "tones (playful, informative, urgent) for A/B testing.\n"
        "- best_send_time: when is the best time to send the broadcast "
        "(e.g. '7-9 PM when users are relaxing')?\n\n"
        "Return JSON only, no markdown, matching this shape:\n"
        "{{\n"
        '  "status_text": "...",\n'
        '  "status_image_brief": "...",\n'
        '  "broadcast_message": "...",\n'
        '  "rationale": "...",\n'
        '  "brand_alignment": {{"score": 8, "reason": "..."}},\n'
        '  "ab_variants": ["...", "..."],\n'
        '  "best_send_time": "..."}}'
    ),
    max_tokens=1000,
    tier="free",
)


def _build_prompt(
    campaign: dict[str, Any],
    creative_direction: dict[str, Any],
    domain_context: dict[str, Any],
) -> str:
    """Assemble the WhatsApp prompt from the spec template + context dicts."""
    return WHATSAPP.prompt_template.format(
        campaign=json.dumps(campaign, ensure_ascii=False, default=str),
        creative_direction=json.dumps(
            creative_direction, ensure_ascii=False, default=str
        ),
        domain_context=json.dumps(
            domain_context, ensure_ascii=False, default=str
        ),
    )


def _normalise(raw: Any) -> dict[str, Any]:
    """Normalise parsed JSON into the canonical WhatsApp output dict.

    Ensures the three required keys are always present as strings. Missing or
    malformed values become empty strings so the caller always receives a
    well-shaped dict.
    """
    if not isinstance(raw, dict):
        raw = {}
    return {
        "status_text": str(raw.get("status_text", "") or ""),
        "status_image_brief": str(raw.get("status_image_brief", "") or ""),
        "broadcast_message": str(raw.get("broadcast_message", "") or ""),
        "rationale": str(raw.get("rationale", "") or ""),
        "brand_alignment": raw.get("brand_alignment") if isinstance(raw.get("brand_alignment"), dict) else {},
        "ab_variants": raw.get("ab_variants") if isinstance(raw.get("ab_variants"), list) else [],
        "best_send_time": str(raw.get("best_send_time", "") or ""),
    }


def generate_whatsapp(
    campaign: dict[str, Any],
    creative_direction: dict[str, Any],
    domain_context: dict[str, Any],
    *,
    gateway: AIGateway | None = None,
    tenant_id: Any = None,
    plan: str = "agency",
) -> dict[str, Any]:
    """Generate WhatsApp creative content for a campaign.

    Builds the WhatsApp prompt from the spec template, calls the AIGateway
    with :attr:`Tier.large`, parses the JSON response via ``extract_json``,
    and returns a dict with ``status_text``, ``status_image_brief``, and
    ``broadcast_message`` keys.

    The broadcast message is compliance-aware (opt-in expectation, opt-out
    guidance, no spam language, WhatsApp Business policy compliant).

    Falls back to an empty-shaped dict (all three keys present but empty) on
    any failure so the caller can continue without a WhatsApp creative.
    ``BudgetExceeded`` is re-raised so budget enforcement is not swallowed.

    Args:
        campaign: campaign plan dict (id, name, goal, budget, ...).
        creative_direction: creative direction dict (hook, angle, tone, ...).
        domain_context: domain pack context dict (id, label, ...).
        gateway: optional AIGateway instance (a new one is created if absent).
        tenant_id: tenant UUID for budget tracking.
        plan: tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        A dict with ``status_text``, ``status_image_brief``, and
        ``broadcast_message`` string values.
    """
    gw = gateway or AIGateway()
    prompt = _build_prompt(campaign, creative_direction, domain_context)

    try:
        comp = gw.complete(
            prompt=prompt,
            tier=Tier.large,
            task="creative_studio_whatsapp",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=WHATSAPP.max_tokens,
            temperature=0.4,
            user_input=str(campaign.get("goal", "")),
            prompt_version="creative_studio_whatsapp_v1.0",
        )
        try:
            raw = extract_json(comp.text)
        except Exception:
            raw = None
        if raw is None:
            raw = {}
        return _normalise(raw)
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.warning("whatsapp generation failed (continuing): %s", e)
        return _normalise({})
