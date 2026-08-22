"""Review Suggestion Engine — produces 3-5 AI-powered improvement suggestions.

Part P3.3 of the CURV AI roadmap. Given a draft campaign/creative, the engine
asks the AI to review it and suggest concrete improvements. Each suggestion
tells the human reviewer:

  - what_to_change:       the specific element to modify (headline, CTA, etc.)
  - why:                  the reasoning behind the suggestion
  - suggested_replacement: a concrete replacement or revised version

The engine mirrors the pattern established by ``hooks.py``: build a prompt,
call ``AIGateway``, parse the JSON via ``extract_json``, and fall back to an
empty list on any failure so the review workflow still works without AI.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Any

from prachar_shared.ai_gateway import AIGateway, BudgetExceeded, Tier
from prachar_shared.ai_gateway.json_utils import extract_json

logger = logging.getLogger(__name__)


# ─── Suggestion dataclass ──────────────────────────────────────────────────


@dataclass
class Suggestion:
    """A single AI-generated improvement suggestion for a draft campaign.

    Attributes:
        what_to_change:        the specific element to modify (e.g. "headline",
                               "call-to-action", "targeting").
        why:                   the reasoning behind the suggestion.
        suggested_replacement: a concrete replacement or revised version.
    """

    what_to_change: str
    why: str
    suggested_replacement: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─── Prompt builder ────────────────────────────────────────────────────────


def _build_prompt(campaign_context: dict[str, Any]) -> str:
    """Assemble the review-suggestions prompt from the campaign context."""
    brand_name = campaign_context.get("brand_name", "")
    goal = campaign_context.get("goal", "")
    budget = campaign_context.get("budget", "")
    network = campaign_context.get("network", "")
    objective = campaign_context.get("objective", "")
    audience = campaign_context.get("audience", "")
    campaign_analysis = campaign_context.get("campaign_analysis", "")

    return (
        "You are a senior marketing reviewer evaluating a draft campaign before "
        "it goes live. Your job is to identify concrete improvements.\n\n"
        f"Brand: {brand_name}\n"
        f"Goal: {goal}\n"
        f"Budget: {budget}\n"
        f"Network: {network}\n"
        f"Objective: {objective}\n"
        f"Audience: {audience}\n\n"
        "Here is the campaign analysis from our strategy team:\n"
        f"{str(campaign_analysis)[:4000]}\n\n"
        "Review this campaign and suggest 3 to 5 specific improvements. "
        "Each suggestion must be actionable and tailored to this campaign. "
        "Do NOT produce generic advice.\n\n"
        "Respond as JSON only, no markdown:\n"
        "{\n"
        '  "suggestions": [\n'
        '    {"what_to_change": "...", "why": "...", "suggested_replacement": "..."},\n'
        '    {"what_to_change": "...", "why": "...", "suggested_replacement": "..."}\n'
        "  ]\n"
        "}"
    )


# ─── Parser ────────────────────────────────────────────────────────────────


def _parse_suggestions(raw: Any) -> list[Suggestion]:
    """Normalise the parsed JSON into a list of Suggestion dataclasses."""
    if not isinstance(raw, dict):
        return []
    suggestions = raw.get("suggestions") or []
    if not isinstance(suggestions, list):
        return []

    result: list[Suggestion] = []
    for item in suggestions:
        if not isinstance(item, dict):
            continue
        result.append(
            Suggestion(
                what_to_change=str(item.get("what_to_change", "")),
                why=str(item.get("why", "")),
                suggested_replacement=str(item.get("suggested_replacement", "")),
            )
        )
    return result


# ─── Generator ─────────────────────────────────────────────────────────────


def generate_suggestions(
    campaign_context: dict[str, Any],
    *,
    gateway: AIGateway | None = None,
    tenant_id: Any = None,
    plan: str = "agency",
) -> list[Suggestion]:
    """Generate 3-5 AI-powered improvement suggestions for a draft campaign.

    Builds a prompt from the campaign context, calls the AIGateway, parses the
    JSON response via ``extract_json``, and returns a list of
    :class:`Suggestion` objects.

    Falls back to an empty list on any failure so the review workflow still
    works without AI.

    Args:
        campaign_context: dict with keys such as ``brand_name``, ``goal``,
            ``budget``, ``network``, ``objective``, ``audience``, and
            ``campaign_analysis``.
        gateway: optional AIGateway instance (a new one is created if absent).
        tenant_id: tenant UUID for budget tracking.
        plan: tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        A list of 3-5 :class:`Suggestion` objects, or ``[]`` on failure.
    """
    gw = gateway or AIGateway()
    prompt = _build_prompt(campaign_context)

    try:
        comp = gw.complete(
            prompt=prompt,
            tier=Tier.large,
            task="review_suggestions",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=1500,
            temperature=0.7,
            user_input=campaign_context.get("goal", ""),
            prompt_version="review_suggestions_v1.0",
        )
        try:
            raw = extract_json(comp.text) or {}
        except Exception:
            raw = {}
        return _parse_suggestions(raw)
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.warning("review suggestions generation failed (continuing): %s", e)
        return []
