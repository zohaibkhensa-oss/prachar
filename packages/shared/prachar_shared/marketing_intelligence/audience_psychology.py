"""Audience Psychology Generator — produces the psychology layer per campaign.

Part P1.3 of the CURV AI roadmap. Builds on the creative directions (P1.1) and
hook patterns (P1.2) by generating an audience psychology profile that
captures *why* the target audience acts (motivations), *why* they might
hesitate (objections), the emotional levers that move them (emotional
triggers), and how they make decisions (decision style).

Each ``AudiencePsychology`` carries:
  - motivations:        top 3 reasons the audience wants the outcome
  - objections:         top 3 reasons the audience might hesitate
  - emotional_triggers: list of emotional levers that resonate
  - decision_style:     a short string describing how they decide
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import TYPE_CHECKING, Any

from prachar_shared.ai_gateway import AIGateway, BudgetExceeded, Tier
from prachar_shared.ai_gateway.json_utils import extract_json

if TYPE_CHECKING:
    from prachar_shared.domain_packs.base import DomainPack

logger = logging.getLogger(__name__)


# ─── AudiencePsychology dataclass ──────────────────────────────────────────


@dataclass
class AudiencePsychology:
    """The psychology profile of a campaign's target audience.

    Attributes:
        motivations:        the top 3 motivations driving the audience.
        objections:         the top 3 objections that might hold them back.
        emotional_triggers: a list of emotional levers that resonate.
        decision_style:     a short string describing how they decide.
    """

    motivations: list[str]
    objections: list[str]
    emotional_triggers: list[str]
    decision_style: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─── Defaults ──────────────────────────────────────────────────────────────


def _empty() -> AudiencePsychology:
    """Return an AudiencePsychology with empty defaults (graceful fallback)."""
    return AudiencePsychology(
        motivations=[],
        objections=[],
        emotional_triggers=[],
        decision_style="",
    )


# ─── Generator ─────────────────────────────────────────────────────────────


def _build_prompt(campaign_context: dict[str, Any], domain_pack: DomainPack) -> str:
    """Assemble the audience psychology prompt from context + domain pack guidance."""
    brand_name = campaign_context.get("brand_name", "")
    goal = campaign_context.get("goal", "")
    budget = campaign_context.get("budget", "")
    campaign_analysis = campaign_context.get("campaign_analysis", "")
    domain_label = getattr(domain_pack, "label", "business")
    psychology_prompt = getattr(domain_pack, "audience_psychology_prompt", "")

    return (
        f"You are a consumer psychologist specialising in audience behaviour for a "
        f"{domain_label.lower()} campaign.\n\n"
        f"Brand: {brand_name}\n"
        f"Goal: {goal}\n"
        f"Budget: {budget}\n\n"
        f"Here is the campaign analysis from our strategy team:\n"
        f"{str(campaign_analysis)[:4000]}\n\n"
        f"{psychology_prompt}\n\n"
        "Analyse the target audience's psychology for this campaign. "
        "Identify the top 3 motivations, top 3 objections, the emotional "
        "triggers that resonate, and a one-phrase decision style.\n\n"
        "Respond as JSON only, no markdown:\n"
        "{\n"
        '  "motivations": ["...", "...", "..."],\n'
        '  "objections": ["...", "...", "..."],\n'
        '  "emotional_triggers": ["...", "...", "..."],\n'
        '  "decision_style": "..."\n'
        "}"
    )


def _parse_psychology(raw: Any) -> AudiencePsychology:
    """Normalise the parsed JSON into an AudiencePsychology dataclass.

    Ensures motivations and objections are capped at 3 entries and all
    fields are strings. Missing or malformed data falls back to empty
    defaults so the caller always receives a valid object.
    """
    if not isinstance(raw, dict):
        raw = {}

    def _str_list(key: str) -> list[str]:
        items = raw.get(key) or []
        if not isinstance(items, list):
            items = []
        return [str(x).strip() for x in items if str(x).strip()]

    motivations = _str_list("motivations")[:3]
    objections = _str_list("objections")[:3]
    emotional_triggers = _str_list("emotional_triggers")
    decision_style = str(raw.get("decision_style", "") or "").strip()

    return AudiencePsychology(
        motivations=motivations,
        objections=objections,
        emotional_triggers=emotional_triggers,
        decision_style=decision_style,
    )


def generate_audience_psychology(
    campaign_context: dict[str, Any],
    domain_pack: DomainPack,
    *,
    gateway: AIGateway | None = None,
    tenant_id: Any = None,
    plan: str = "agency",
) -> AudiencePsychology:
    """Generate the audience psychology profile for a campaign.

    Builds a prompt using the domain pack's ``audience_psychology_prompt``
    guidance plus the campaign context, calls the AIGateway, parses the JSON
    response via ``extract_json``, and returns an :class:`AudiencePsychology`
    object with the top 3 motivations, top 3 objections, emotional triggers,
    and a decision-style string.

    Falls back to an empty :class:`AudiencePsychology` on any failure so the
    campaign preview still works without the psychology layer.

    Args:
        campaign_context: dict with keys ``brand_name``, ``goal``, ``budget``,
            and ``campaign_analysis``.
        domain_pack: the DomainPack for the campaign's domain.
        gateway: optional AIGateway instance (a new one is created if absent).
        tenant_id: tenant UUID for budget tracking.
        plan: tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        An :class:`AudiencePsychology` object.
    """
    gw = gateway or AIGateway()
    prompt = _build_prompt(campaign_context, domain_pack)
    pack_id = getattr(domain_pack, "id", "generic")

    try:
        comp = gw.complete(
            prompt=prompt,
            tier=Tier.large,
            task=f"{pack_id}_audience_psychology",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=1500,
            temperature=0.8,
            user_input=campaign_context.get("goal", ""),
            prompt_version=f"{pack_id}_audience_psychology_v1.0",
        )
        try:
            raw = extract_json(comp.text) or {}
        except Exception:
            raw = {}
        return _parse_psychology(raw)
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.warning(
            "%s audience psychology generation failed (continuing): %s",
            pack_id,
            e,
        )
        return _empty()
