"""Seasonal Ideas Generator — produces campaign ideas for the current + next 2 months.

Part P1.6 of the CURV AI roadmap. Generates seasonal marketing ideas tied to
the current month and the following two months, leveraging festivals, holidays,
weather shifts, and domain-specific seasonal moments.

Each ``SeasonalIdea`` carries:
  - month:     the month name (e.g. "October", "November", "December")
  - occasion:  the seasonal occasion or event (e.g. "Diwali", "Monsoon onset")
  - idea:      a short description of the campaign idea
  - copy:      ready-to-use copy for the seasonal campaign
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import TYPE_CHECKING, Any

from prachar_shared.ai_gateway import AIGateway, BudgetExceeded, Tier
from prachar_shared.ai_gateway.json_utils import extract_json

if TYPE_CHECKING:
    from prachar_shared.domain_packs.base import DomainPack

logger = logging.getLogger(__name__)


_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


# ─── SeasonalIdea dataclass ────────────────────────────────────────────────


@dataclass
class SeasonalIdea:
    """A single seasonal marketing idea tied to a specific month and occasion.

    Attributes:
        month: the month name (e.g. "October", "November", "December").
        occasion: the seasonal occasion or event (e.g. "Diwali", "Monsoon").
        idea: a short description of the campaign idea.
        copy: ready-to-use copy for the seasonal campaign (1-2 sentences).
    """

    month: str
    occasion: str
    idea: str
    copy: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─── Generator ─────────────────────────────────────────────────────────────


def _get_target_months(now: datetime | None = None) -> list[str]:
    """Return the current month + next 2 months as full month names."""
    now = now or datetime.now()
    months: list[str] = []
    for offset in range(3):
        idx = (now.month - 1 + offset) % 12
        months.append(_MONTH_NAMES[idx])
    return months


def _build_prompt(
    campaign_context: dict[str, Any],
    domain_pack: DomainPack,
    target_months: list[str],
) -> str:
    """Assemble the seasonal-ideas prompt from campaign context + domain pack guidance."""
    brand_name = campaign_context.get("brand_name", "")
    goal = campaign_context.get("goal", "")
    budget = campaign_context.get("budget", "")
    campaign_analysis = campaign_context.get("campaign_analysis", "")
    domain_label = getattr(domain_pack, "label", "business")
    seasonal_prompt = getattr(domain_pack, "seasonal_prompt", "")
    months_str = ", ".join(target_months)

    return (
        f"You are a seasonal marketing strategist specialising in "
        f"{domain_label.lower()} campaigns.\n\n"
        f"Brand: {brand_name}\n"
        f"Goal: {goal}\n"
        f"Budget: {budget}\n"
        f"Target months: {months_str}\n\n"
        f"Here is the campaign analysis from our strategy team:\n"
        f"{str(campaign_analysis)[:4000]}\n\n"
        f"{seasonal_prompt}\n\n"
        f"Generate seasonal marketing ideas for each of these months: "
        f"{months_str}. For each month, identify the most relevant seasonal "
        f"occasion, festival, holiday, or trend and create a campaign idea.\n\n"
        "For each idea provide:\n"
        "- month: the month name (e.g. \"October\")\n"
        "- occasion: the seasonal occasion or event (e.g. \"Diwali\", "
        "\"Monsoon onset\", \"Back to school\")\n"
        "- idea: a short description of the campaign idea (1 sentence)\n"
        "- copy: ready-to-use copy for the seasonal campaign (1-2 sentences)\n\n"
        "Respond as JSON only, no markdown:\n"
        "{\n"
        '  "seasonal_ideas": [\n'
        f'    {{"month": "{target_months[0]}", "occasion": "...", "idea": "...", "copy": "..."}},\n'
        f'    {{"month": "{target_months[1]}", "occasion": "...", "idea": "...", "copy": "..."}},\n'
        f'    {{"month": "{target_months[2]}", "occasion": "...", "idea": "...", "copy": "..."}}\n'
        "  ]\n"
        "}"
    )


def _parse_seasonal(raw: Any) -> list[SeasonalIdea]:
    """Normalise the parsed JSON into a list of SeasonalIdea dataclasses."""
    if not isinstance(raw, dict):
        raw = {}
    ideas_list = raw.get("seasonal_ideas") or raw.get("ideas") or []
    if not isinstance(ideas_list, list):
        ideas_list = []

    result: list[SeasonalIdea] = []
    for item in ideas_list[:5]:
        if not isinstance(item, dict):
            continue
        idea = SeasonalIdea(
            month=str(item.get("month", "") or "").strip(),
            occasion=str(item.get("occasion", "") or "").strip(),
            idea=str(item.get("idea", "") or "").strip(),
            copy=str(item.get("copy", "") or "").strip(),
        )
        # Only keep entries that have at least some content
        if idea.month or idea.idea or idea.copy:
            result.append(idea)

    return result


def generate_seasonal_ideas(
    campaign_context: dict[str, Any],
    domain_pack: DomainPack,
    *,
    gateway: AIGateway | None = None,
    tenant_id: Any = None,
    plan: str = "agency",
) -> list[SeasonalIdea]:
    """Generate seasonal marketing ideas for the current month + next 2 months.

    Builds a prompt using the domain pack's ``seasonal_prompt`` guidance plus
    the campaign context, calls the AIGateway, parses the JSON response via
    ``extract_json``, and returns a list of :class:`SeasonalIdea` objects —
    one per target month (current + next 2).

    Falls back to an empty list on any failure so the campaign preview still
    works without seasonal ideas.

    Args:
        campaign_context: dict with keys ``brand_name``, ``goal``, ``budget``,
            and ``campaign_analysis``.
        domain_pack: the DomainPack for the campaign's domain.
        gateway: optional AIGateway instance (a new one is created if absent).
        tenant_id: tenant UUID for budget tracking.
        plan: tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        A list of :class:`SeasonalIdea` objects (typically 3, one per month).
    """
    gw = gateway or AIGateway()
    target_months = _get_target_months()
    prompt = _build_prompt(campaign_context, domain_pack, target_months)
    pack_id = getattr(domain_pack, "id", "generic")

    try:
        comp = gw.complete(
            prompt=prompt,
            tier=Tier.large,
            task=f"{pack_id}_seasonal_ideas",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=1500,
            temperature=0.8,
            user_input=campaign_context.get("goal", ""),
            prompt_version=f"{pack_id}_seasonal_ideas_v1.0",
        )
        try:
            raw = extract_json(comp.text) or {}
        except Exception:
            raw = {}
        return _parse_seasonal(raw)
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.warning("%s seasonal ideas generation failed (continuing): %s", pack_id, e)
        return _parse_seasonal({})
