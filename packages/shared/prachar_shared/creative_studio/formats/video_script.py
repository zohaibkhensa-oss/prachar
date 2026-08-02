"""Video Script creative format spec + generator.

Part P2.5 of the PRACHAR roadmap. Declares the ``video_script`` format spec
(scenes, music_mood, total_duration) and a domain-specific generator that
calls the AIGateway to produce a scene-by-scene short-form video script.

The generator mirrors the pattern used by
``prachar_shared.marketing_intelligence.hooks.generate_hooks``: build a
prompt, call the gateway with ``Tier.large``, parse the response via
``extract_json``, and fall back to an empty dict on any failure so the
caller's preview still works.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from prachar_shared.ai_gateway import AIGateway, BudgetExceeded, Tier
from prachar_shared.ai_gateway.json_utils import extract_json

from ..base import CreativeFormatSpec

logger = logging.getLogger(__name__)


VIDEO_SCRIPT = CreativeFormatSpec(
    id="video_script",
    label="Video Script",
    description="A scene-by-scene video script with visuals, voiceover, on-screen text, and timing.",
    output_schema={
        "type": "object",
        "properties": {
            "scenes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "scene_no": {"type": "integer"},
                        "visual": {"type": "string"},
                        "voiceover": {"type": "string"},
                        "on_screen_text": {"type": "string"},
                        "duration": {"type": "number"},
                    },
                    "required": ["scene_no", "visual", "voiceover", "on_screen_text", "duration"],
                },
            },
            "music_mood": {"type": "string"},
            "total_duration": {"type": "number"},
        },
        "required": ["scenes", "music_mood", "total_duration"],
    },
    prompt_template=(
        "You are a professional video scriptwriter crafting a short-form video "
        "for the campaign below.\n\n"
        "Campaign:\n{campaign}\n\n"
        "Creative Direction:\n{creative_direction}\n\n"
        "Domain Context:\n{domain_context}\n\n"
        "Write a short-form video script (30-60 seconds total). Break it into 4-8 "
        "scenes. Each scene must include:\n"
        "  - scene_no:        integer, starting at 1\n"
        "  - visual:          a vivid description of what the viewer sees\n"
        "  - voiceover:       the narration line for this scene\n"
        "  - on_screen_text:  short text overlay shown on screen\n"
        "  - duration:        seconds this scene lasts (number)\n\n"
        "The scene durations should sum to the total_duration. Specify the "
        "music_mood (e.g. upbeat, inspirational, calm, energetic) that fits the "
        "campaign tone. Tailor the visuals and voiceover to the brand, the "
        "creative direction's hook/angle/tone, and the domain's customer type.\n\n"
        "AGENCY QUALITY REQUIREMENTS (Phase I2):\n"
        "- The FIRST 5 SECONDS are critical — the hook must grab attention "
        "immediately. Use a pattern interrupt, surprising stat, or question.\n"
        "- Structure: Hook (0-5s) → Problem (5-15s) → Solution (15-40s) → "
        "CTA (40-60s). Adjust proportions for shorter videos.\n"
        "- rationale: explain why this script structure will retain viewers "
        "and what emotion each act evokes.\n"
        "- brand_alignment: rate 1-10 and explain in one sentence.\n"
        "- hook_alternatives: provide 2 alternative opening hooks (different "
        "angles: emotional, curiosity, bold claim) for A/B testing.\n"
        "- platform_adaptations: how should this script be adapted for "
        "YouTube (longer, chapters), Reels (15-30s, trending audio), and "
        "WhatsApp status (30s, vertical)?\n\n"
        "Respond as JSON only, no markdown:\n"
        "{{\n"
        '  "scenes": [\n'
        '    {{"scene_no": 1, "visual": "...", "voiceover": "...", '
        '"on_screen_text": "...", "duration": 5}},\n'
        '    {{"scene_no": 2, "visual": "...", "voiceover": "...", '
        '"on_screen_text": "...", "duration": 7}}\n'
        "  ],\n"
        '  "music_mood": "upbeat",\n'
        '  "total_duration": 45,\n'
        '  "rationale": "Why this script works...",\n'
        '  "brand_alignment": {{"score": 8, "reason": "..."}},\n'
        '  "hook_alternatives": ["...", "..."],\n'
        '  "platform_adaptations": "..."}}'
    ),
    max_tokens=2500,
    tier="pro",
)


# ─── Generator ─────────────────────────────────────────────────────────────


def _build_prompt(
    campaign: dict[str, Any],
    creative_direction: dict[str, Any],
    domain_context: dict[str, Any],
) -> str:
    """Assemble the video-script prompt from the three context dicts."""
    domain_label = str(domain_context.get("label") or domain_context.get("id") or "business")
    template = VIDEO_SCRIPT.prompt_template
    # The shared template only has {campaign}/{creative_direction}/{domain_context}
    # placeholders (so studio.py's .format() works). Inject the domain label via
    # the domain_context JSON block instead of a template placeholder.
    enriched_context = {**domain_context, "label": domain_label}
    return template.format(
        campaign=json.dumps(campaign, ensure_ascii=False, default=str),
        creative_direction=json.dumps(creative_direction, ensure_ascii=False, default=str),
        domain_context=json.dumps(enriched_context, ensure_ascii=False, default=str),
    )


def _parse_video_script(raw: Any) -> dict[str, Any]:
    """Normalise the parsed JSON into the video_script output shape.

    Ensures ``scenes`` is a list of dicts each carrying the required fields
    (filling missing ones with sensible defaults), ``music_mood`` is a string,
    and ``total_duration`` is a number. Returns an empty dict if the input
    cannot be normalised.
    """
    if not isinstance(raw, dict):
        return {}

    scenes_raw = raw.get("scenes")
    if not isinstance(scenes_raw, list):
        scenes_raw = []

    scenes: list[dict[str, Any]] = []
    for idx, item in enumerate(scenes_raw, start=1):
        if not isinstance(item, dict):
            continue
        scene_no = item.get("scene_no", idx)
        try:
            scene_no = int(scene_no)
        except (TypeError, ValueError):
            scene_no = idx
        try:
            duration = float(item.get("duration", 0) or 0)
        except (TypeError, ValueError):
            duration = 0.0
        scenes.append(
            {
                "scene_no": scene_no,
                "visual": str(item.get("visual", "")),
                "voiceover": str(item.get("voiceover", "")),
                "on_screen_text": str(item.get("on_screen_text", "")),
                "duration": duration,
            }
        )

    music_mood = str(raw.get("music_mood", ""))

    total_duration: float
    try:
        total_duration = float(raw.get("total_duration", 0) or 0)
    except (TypeError, ValueError):
        total_duration = 0.0
    # If total_duration missing but scenes present, sum the scene durations.
    if not total_duration and scenes:
        total_duration = float(sum(s["duration"] for s in scenes))

    return {
        "scenes": scenes,
        "music_mood": music_mood,
        "total_duration": total_duration,
        "rationale": str(raw.get("rationale", "")),
        "brand_alignment": raw.get("brand_alignment") if isinstance(raw.get("brand_alignment"), dict) else {},
        "hook_alternatives": raw.get("hook_alternatives") if isinstance(raw.get("hook_alternatives"), list) else [],
        "platform_adaptations": str(raw.get("platform_adaptations", "")),
    }


def generate_video_script(
    campaign: dict[str, Any],
    creative_direction: dict[str, Any],
    domain_context: dict[str, Any],
    *,
    gateway: AIGateway | None = None,
    tenant_id: Any = None,
    plan: str = "agency",
) -> dict[str, Any]:
    """Generate a scene-by-scene video script for a campaign.

    Builds a prompt from the campaign, creative direction, and domain context,
    calls the AIGateway with ``Tier.large``, parses the JSON response via
    ``extract_json``, and returns a dict with ``scenes``, ``music_mood``, and
    ``total_duration``.

    Falls back to an empty dict on any failure (other than ``BudgetExceeded``,
    which re-raises) so the caller's preview still works without a script.

    Args:
        campaign:           campaign plan dict (id, name, goal, budget, ...).
        creative_direction: creative direction dict (hook, angle, tone, ...).
        domain_context:     domain pack context dict (id, label, customer_type).
        gateway:            optional AIGateway instance (a new one is created
                            if absent).
        tenant_id:          tenant UUID for budget tracking.
        plan:               tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        A dict with ``scenes`` (list of scene dicts), ``music_mood`` (str), and
        ``total_duration`` (number). Empty dict on failure.
    """
    gw = gateway or AIGateway()
    prompt = _build_prompt(campaign, creative_direction, domain_context)

    try:
        comp = gw.complete(
            prompt=prompt,
            tier=Tier.large,
            task="creative_studio_video_script",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=VIDEO_SCRIPT.max_tokens,
            temperature=0.7,
            user_input=str(campaign.get("goal", "")),
            prompt_version="creative_studio_video_script_v1.0",
        )
        try:
            raw = extract_json(comp.text) or {}
        except Exception:
            raw = {}
        return _parse_video_script(raw)
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.warning("video_script generation failed (continuing): %s", e)
        return {}
