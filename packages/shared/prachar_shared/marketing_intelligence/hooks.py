"""Hook Pattern Generator — produces 5 hook patterns per campaign.

Part P1.2 of the CURV AI roadmap. Builds on the creative directions module
(P1.1) by generating 5 psychologically-grounded hook patterns that can be
used across ad copy, video intros, and post openers.

The 5 canonical hook patterns:
  - QUESTION     — asks the audience a provocative question
  - STAT         — leads with a surprising statistic
  - STORY        — opens with a relatable narrative
  - CONTRARIAN   — challenges a commonly-held belief
  - ASPIRATION   — paints the desired future state

Each hook carries:
  - pattern:       the hook type (one of the 5 above)
  - copy:          the actual hook text
  - why_it_works:  the psychology behind why it grabs attention
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from prachar_shared.ai_gateway import AIGateway, BudgetExceeded, Tier
from prachar_shared.ai_gateway.json_utils import extract_json

if TYPE_CHECKING:
    from prachar_shared.domain_packs.base import DomainPack

logger = logging.getLogger(__name__)


# ─── Hook pattern types ────────────────────────────────────────────────────


class HookPattern(StrEnum):
    """The 5 canonical hook patterns."""

    QUESTION = "question"
    STAT = "stat"
    STORY = "story"
    CONTRARIAN = "contrarian"
    ASPIRATION = "aspiration"


# Ordered list — the prompt asks the LLM to produce hooks in this order.
HOOK_PATTERNS: list[str] = [
    HookPattern.QUESTION.value,
    HookPattern.STAT.value,
    HookPattern.STORY.value,
    HookPattern.CONTRARIAN.value,
    HookPattern.ASPIRATION.value,
]


# ─── Hook dataclass ────────────────────────────────────────────────────────


@dataclass
class Hook:
    """A single hook pattern with copy and psychology explanation.

    Attributes:
        pattern:       the hook type (question, stat, story, contrarian, aspiration)
        copy:          the actual hook text the audience sees
        why_it_works:  a short explanation of the psychology behind the hook
    """

    pattern: str
    copy: str
    why_it_works: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─── Generator ─────────────────────────────────────────────────────────────


def _build_prompt(campaign_context: dict[str, Any], domain_pack: DomainPack) -> str:
    """Assemble the hooks prompt from campaign context + domain pack guidance."""
    brand_name = campaign_context.get("brand_name", "")
    goal = campaign_context.get("goal", "")
    budget = campaign_context.get("budget", "")
    campaign_analysis = campaign_context.get("campaign_analysis", "")
    domain_label = getattr(domain_pack, "label", "business")
    hooks_prompt = getattr(domain_pack, "hooks_prompt", "")

    patterns_block = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(HOOK_PATTERNS))

    return (
        f"You are a master copywriter specialising in attention hooks for a "
        f"{domain_label.lower()} campaign.\n\n"
        f"Brand: {brand_name}\n"
        f"Goal: {goal}\n"
        f"Budget: {budget}\n\n"
        f"Here is the campaign analysis from our strategy team:\n"
        f"{str(campaign_analysis)[:4000]}\n\n"
        f"{hooks_prompt}\n\n"
        f"Generate exactly 5 hook patterns — one for each of these types, in order:\n"
        f"{patterns_block}\n\n"
        "Each hook must be genuinely different and tailored to this brand. "
        "Do NOT produce variations of the same idea.\n\n"
        "Respond as JSON only, no markdown:\n"
        "{\n"
        '  "hooks": [\n'
        '    {"pattern": "question", "copy": "...", "why_it_works": "..."},\n'
        '    {"pattern": "stat", "copy": "...", "why_it_works": "..."},\n'
        '    {"pattern": "story", "copy": "...", "why_it_works": "..."},\n'
        '    {"pattern": "contrarian", "copy": "...", "why_it_works": "..."},\n'
        '    {"pattern": "aspiration", "copy": "...", "why_it_works": "..."}\n'
        "  ]\n"
        "}"
    )


def _parse_hooks(raw: Any) -> list[Hook]:
    """Normalise the parsed JSON into a list of Hook dataclasses.

    Ensures exactly 5 hooks are returned, one per pattern type, in canonical
    order. Missing or malformed hooks are filled with empty-string placeholders
    so the caller always receives 5 entries.
    """
    if not isinstance(raw, dict):
        raw = {}
    hooks_list = raw.get("hooks") or []
    if not isinstance(hooks_list, list):
        hooks_list = []

    # Index parsed hooks by their pattern for quick lookup.
    by_pattern: dict[str, Hook] = {}
    for item in hooks_list:
        if not isinstance(item, dict):
            continue
        pattern = str(item.get("pattern", "")).strip().lower()
        if not pattern:
            continue
        by_pattern[pattern] = Hook(
            pattern=pattern,
            copy=str(item.get("copy", "")),
            why_it_works=str(item.get("why_it_works", "")),
        )

    # Build the canonical 5 hooks in order, filling gaps with placeholders.
    result: list[Hook] = []
    for p in HOOK_PATTERNS:
        hook = by_pattern.get(p)
        if hook is None:
            hook = Hook(pattern=p, copy="", why_it_works="")
        result.append(hook)
    return result


def generate_hooks(
    campaign_context: dict[str, Any],
    domain_pack: DomainPack,
    *,
    gateway: AIGateway | None = None,
    tenant_id: Any = None,
    plan: str = "agency",
) -> list[Hook]:
    """Generate 5 hook patterns for a campaign.

    Builds a prompt using the domain pack's ``hooks_prompt`` guidance plus the
    campaign context, calls the AIGateway, parses the JSON response via
    ``extract_json``, and returns exactly 5 :class:`Hook` objects (one per
    pattern type: question, stat, story, contrarian, aspiration).

    Falls back to 5 empty-copy hooks on any failure so the campaign preview
    still works without hooks.

    Args:
        campaign_context: dict with keys ``brand_name``, ``goal``, ``budget``,
            and ``campaign_analysis``.
        domain_pack: the DomainPack for the campaign's domain.
        gateway: optional AIGateway instance (a new one is created if absent).
        tenant_id: tenant UUID for budget tracking.
        plan: tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        A list of 5 :class:`Hook` objects in canonical pattern order.
    """
    gw = gateway or AIGateway()
    prompt = _build_prompt(campaign_context, domain_pack)
    pack_id = getattr(domain_pack, "id", "generic")

    try:
        comp = gw.complete(
            prompt=prompt,
            tier=Tier.large,
            task=f"{pack_id}_hooks",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=1500,
            temperature=0.8,
            user_input=campaign_context.get("goal", ""),
            prompt_version=f"{pack_id}_hooks_v1.0",
        )
        try:
            raw = extract_json(comp.text) or {}
        except Exception:
            raw = {}
        return _parse_hooks(raw)
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.warning("%s hooks generation failed (continuing): %s", pack_id, e)
        return _parse_hooks({})
