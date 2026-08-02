"""A/B Concept Generator — produces 6 A/B variants (3 directions × 2 variants).

Part P1.9 of the PRACHAR roadmap. For each creative direction (from P1.1),
generates an A/B variant with a different hook/angle. Variant A is the
original direction's angle; variant B is an alternative angle.

Each ``ABConcept`` carries:
  - direction_id:           the id of the parent creative direction
  - variant_label:          "A" or "B"
  - what_changed:           what was changed from the original direction
  - why:                    why this variant might perform better
  - expected_audience_segment: the audience segment this variant targets
  - hook:                   the hook for this variant
  - headline:               the sample headline for this variant
  - cta:                    the call-to-action for this variant
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Any

from prachar_shared.ai_gateway import AIGateway, BudgetExceeded, Tier
from prachar_shared.ai_gateway.json_utils import extract_json

logger = logging.getLogger(__name__)


# ─── ABConcept dataclass ──────────────────────────────────────────────────


@dataclass
class ABConcept:
    """A single A/B concept variant for a creative direction.

    Attributes:
        direction_id: the id of the parent creative direction.
        variant_label: "A" or "B".
        what_changed: what was changed from the original direction (1 sentence).
        why: why this variant might perform better (1 sentence).
        expected_audience_segment: the audience segment this variant targets
            (1 sentence).
        hook: the hook for this variant (1 sentence).
        headline: the sample headline for this variant (1 sentence).
        cta: the call-to-action for this variant (1 sentence).
    """

    direction_id: str
    variant_label: str
    what_changed: str
    why: str
    expected_audience_segment: str
    hook: str
    headline: str
    cta: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─── Generator ─────────────────────────────────────────────────────────────


def _build_prompt(
    creative_directions: list[dict[str, Any]],
    campaign_context: dict[str, Any],
) -> str:
    """Assemble the A/B concepts prompt from creative directions + campaign context."""
    brand_name = campaign_context.get("brand_name", "")
    goal = campaign_context.get("goal", "")
    budget = campaign_context.get("budget", "")
    campaign_analysis = campaign_context.get("campaign_analysis", "")

    # Serialise the creative directions for the prompt
    directions_text = ""
    for d in creative_directions[:3]:
        directions_text += (
            f"- id: {d.get('id', '')}\n"
            f"  hook: {d.get('hook', '')}\n"
            f"  angle: {d.get('angle', '')}\n"
            f"  tone: {d.get('tone', '')}\n"
            f"  sample_headline: {d.get('sample_headline', '')}\n"
            f"  sample_cta: {d.get('sample_cta', '')}\n\n"
        )

    return (
        f"You are a creative strategist specialising in A/B testing for "
        f"marketing campaigns.\n\n"
        f"Brand: {brand_name}\n"
        f"Goal: {goal}\n"
        f"Budget: {budget}\n\n"
        f"Here is the campaign analysis from our strategy team:\n"
        f"{str(campaign_analysis)[:3000]}\n\n"
        f"Here are the 3 creative directions we have developed:\n"
        f"{directions_text}\n"
        "For each creative direction, generate 2 A/B variants. "
        "Variant A should follow the original direction's angle closely "
        "(with minor refinements). Variant B should take a different "
        "hook/angle to test an alternative hypothesis.\n\n"
        "For each variant provide:\n"
        "- direction_id: the id of the parent creative direction\n"
        "- variant_label: \"A\" or \"B\"\n"
        "- what_changed: what was changed from the original direction "
        "(1 sentence)\n"
        "- why: why this variant might perform better (1 sentence)\n"
        "- expected_audience_segment: the audience segment this variant "
        "targets (1 sentence)\n"
        "- hook: the hook for this variant (1 sentence)\n"
        "- headline: the sample headline for this variant (1 sentence)\n"
        "- cta: the call-to-action for this variant (1 sentence)\n\n"
        "Respond as JSON only, no markdown:\n"
        "{\n"
        '  "ab_concepts": [\n'
        '    {"direction_id": "...", "variant_label": "A", '
        '"what_changed": "...", "why": "...", '
        '"expected_audience_segment": "...", "hook": "...", '
        '"headline": "...", "cta": "..."},\n'
        '    {"direction_id": "...", "variant_label": "B", '
        '"what_changed": "...", "why": "...", '
        '"expected_audience_segment": "...", "hook": "...", '
        '"headline": "...", "cta": "..."},\n'
        "    ... (6 total: 2 per direction)\n"
        "  ]\n"
        "}"
    )


def _parse_ab_concepts(
    raw: Any, creative_directions: list[dict[str, Any]]
) -> list[ABConcept]:
    """Normalise the parsed JSON into a list of ABConcept dataclasses.

    Ensures exactly 2 variants (A and B) per creative direction, for a
    total of up to 6 concepts.
    """
    if not isinstance(raw, dict):
        raw = {}
    concepts_list = raw.get("ab_concepts") or raw.get("concepts") or []
    if not isinstance(concepts_list, list):
        concepts_list = []

    # Group parsed concepts by direction_id
    by_direction: dict[str, list[dict[str, Any]]] = {}
    for item in concepts_list:
        if not isinstance(item, dict):
            continue
        dir_id = str(item.get("direction_id", "") or "").strip()
        if dir_id:
            by_direction.setdefault(dir_id, []).append(item)

    result: list[ABConcept] = []
    for direction in creative_directions[:3]:
        dir_id = str(direction.get("id", "") or "").strip()
        if not dir_id:
            continue
        items = by_direction.get(dir_id, [])
        # Ensure we have at most 2 variants, labelled A and B
        for idx in range(2):
            label = "A" if idx == 0 else "B"
            item = items[idx] if idx < len(items) else {}
            concept = ABConcept(
                direction_id=dir_id,
                variant_label=label,
                what_changed=str(item.get("what_changed", "") or "").strip(),
                why=str(item.get("why", "") or "").strip(),
                expected_audience_segment=str(
                    item.get("expected_audience_segment", "") or ""
                ).strip(),
                hook=str(item.get("hook", "") or "").strip(),
                headline=str(item.get("headline", "") or "").strip(),
                cta=str(item.get("cta", "") or "").strip(),
            )
            result.append(concept)

    return result


def generate_ab_concepts(
    creative_directions: list[dict[str, Any]],
    campaign_context: dict[str, Any],
    *,
    gateway: AIGateway | None = None,
    tenant_id: Any = None,
    plan: str = "agency",
) -> list[ABConcept]:
    """Generate 6 A/B concept variants (3 directions × 2 variants).

    Builds a prompt from the creative directions + campaign context, calls
    the AIGateway, parses the JSON response via ``extract_json``, and
    returns a list of :class:`ABConcept` objects.

    Falls back to an empty list on any failure so the campaign preview
    still works without A/B concepts.

    Args:
        creative_directions: list of 3 creative direction dicts (from P1.1),
            each with keys: id, hook, angle, tone, sample_headline,
            sample_cta.
        campaign_context: dict with keys ``brand_name``, ``goal``,
            ``budget``, and ``campaign_analysis``.
        gateway: optional AIGateway instance (a new one is created if absent).
        tenant_id: tenant UUID for budget tracking.
        plan: tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        A list of 6 :class:`ABConcept` objects (2 per direction).

    Raises:
        BudgetExceeded: if the AI gateway budget is exceeded.
    """
    if not creative_directions:
        return []

    gw = gateway or AIGateway()
    prompt = _build_prompt(creative_directions, campaign_context)

    try:
        comp = gw.complete(
            prompt=prompt,
            tier=Tier.large,
            task="ab_concepts",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=2000,
            temperature=0.8,
            user_input=campaign_context.get("goal", ""),
            prompt_version="ab_concepts_v1.0",
        )
        try:
            raw = extract_json(comp.text) or {}
        except Exception:
            raw = {}
        return _parse_ab_concepts(raw, creative_directions)
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.warning("A/B concepts generation failed (continuing): %s", e)
        return []
