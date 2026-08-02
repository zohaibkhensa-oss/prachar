"""Story creative format spec + generator.

Part P2.7 of the PRACHAR roadmap. Defines the Instagram Story format spec
and a ``generate_story`` function that produces a sequence of interactive
frames (poll / question / quiz / text) via the AIGateway.
"""
from __future__ import annotations

import logging
from typing import Any

from prachar_shared.ai_gateway import AIGateway, BudgetExceeded, Tier
from prachar_shared.ai_gateway.json_utils import extract_json

from ..base import CreativeFormatSpec

logger = logging.getLogger(__name__)

STORY = CreativeFormatSpec(
    id="story",
    label="Story",
    description="Interactive story frames with polls, questions, quizzes, text, and stickers.",
    output_schema={
        "type": "object",
        "properties": {
            "frames": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "frame_no": {"type": "integer"},
                        "type": {"type": "string", "enum": ["poll", "question", "quiz", "text"]},
                        "copy": {"type": "string"},
                        "visual_brief": {"type": "string"},
                        "sticker": {"type": "string"},
                    },
                    "required": ["frame_no", "type", "copy", "visual_brief", "sticker"],
                },
            },
        },
        "required": ["frames"],
    },
    prompt_template=(
        "You are a social media story designer specialising in engagement.\n\n"
        "Campaign:\n{campaign}\n\n"
        "Creative Direction:\n{creative_direction}\n\n"
        "Domain Context:\n{domain_context}\n\n"
        "Create a 4-6 frame story sequence. Use interactive frame types "
        "(poll, question, quiz, text) to maximise engagement. Each frame "
        "needs copy, a visual brief, and a sticker suggestion. Return JSON "
        "matching the story output schema."
    ),
    max_tokens=1800,
    tier="free",
)


# ─── Generator ─────────────────────────────────────────────────────────────


_VALID_FRAME_TYPES = {"poll", "question", "quiz", "text"}


def _build_prompt(campaign: dict[str, Any], creative_direction: dict[str, Any], domain_context: dict[str, Any]) -> str:
    """Assemble the story prompt from campaign, creative direction, and domain context."""
    return STORY.prompt_template.format(
        campaign=campaign,
        creative_direction=creative_direction,
        domain_context=domain_context,
    )


def _parse_frames(raw: Any) -> list[dict[str, Any]]:
    """Normalise the parsed JSON into a list of frame dicts.

    Each frame is validated to contain the required fields
    (frame_no, type, copy, visual_brief, sticker). Frames with an invalid
    ``type`` are coerced to ``text``. Malformed entries are dropped.
    """
    if not isinstance(raw, dict):
        return []
    frames = raw.get("frames") or []
    if not isinstance(frames, list):
        return []

    result: list[dict[str, Any]] = []
    for i, item in enumerate(frames):
        if not isinstance(item, dict):
            continue
        frame_type = str(item.get("type", "text")).strip().lower()
        if frame_type not in _VALID_FRAME_TYPES:
            frame_type = "text"
        frame_no = item.get("frame_no", i + 1)
        try:
            frame_no = int(frame_no)
        except (TypeError, ValueError):
            frame_no = i + 1
        result.append(
            {
                "frame_no": frame_no,
                "type": frame_type,
                "copy": str(item.get("copy", "")),
                "visual_brief": str(item.get("visual_brief", "")),
                "sticker": str(item.get("sticker", "")),
            }
        )
    return result


def generate_story(
    campaign: dict[str, Any],
    creative_direction: dict[str, Any],
    domain_context: dict[str, Any],
    *,
    gateway: AIGateway | None = None,
    tenant_id: Any = None,
    plan: str = "agency",
) -> dict[str, Any]:
    """Generate an interactive Instagram Story (frames) for a campaign.

    Builds a prompt from the campaign, creative direction, and domain
    context, calls the AIGateway with :attr:`Tier.large`, parses the JSON
    response via :func:`extract_json`, and returns a dict with a ``frames``
    list. Each frame has ``frame_no``, ``type`` (poll/question/quiz/text),
    ``copy``, ``visual_brief``, and ``sticker``.

    Falls back to ``{"frames": []}`` on any failure so the caller can
    continue without a story.

    Args:
        campaign: campaign dict (brand, goal, audience, etc.).
        creative_direction: creative direction dict (tone, themes, hooks).
        domain_context: domain-specific context dict.
        gateway: optional AIGateway instance (a new one is created if absent).
        tenant_id: tenant UUID for budget tracking.
        plan: tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        A dict with a ``frames`` key containing a list of frame dicts.
    """
    gw = gateway or AIGateway()
    prompt = _build_prompt(campaign, creative_direction, domain_context)

    try:
        comp = gw.complete(
            prompt=prompt,
            tier=Tier.large,
            task="story",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=STORY.max_tokens,
            temperature=0.8,
            user_input=str(campaign.get("goal", "")),
            prompt_version="story_v1.0",
        )
        try:
            raw = extract_json(comp.text) or {}
        except Exception:
            raw = {}
        return {"frames": _parse_frames(raw)}
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.warning("story generation failed (continuing): %s", e)
        return {"frames": []}
