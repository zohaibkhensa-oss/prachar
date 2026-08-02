"""Local Marketing Generator — produces 3-5 local marketing ideas per campaign.

Part P1.7 of the PRACHAR roadmap. Generates local marketing ideas for
location-based businesses (business, restaurant, clinic). Creators don't have
a local presence, so the creator pack's ``local_prompt`` is empty and this
generator returns [] for creators.

Each ``LocalIdea`` carries:
  - type:  the idea type ("event", "partnership", "geo_target", "seo")
  - idea:  a short description of the local marketing idea
  - copy:  ready-to-use copy for the local marketing initiative
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


# ─── LocalIdea dataclass ───────────────────────────────────────────────────


@dataclass
class LocalIdea:
    """A single local marketing idea.

    Attributes:
        type: the idea type ("event", "partnership", "geo_target", "seo").
        idea: a short description of the local marketing idea (1 sentence).
        copy: ready-to-use copy for the local marketing initiative (1-2
            sentences).
    """

    type: str
    idea: str
    copy: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─── Generator ─────────────────────────────────────────────────────────────


def _build_prompt(campaign_context: dict[str, Any], domain_pack: DomainPack) -> str:
    """Assemble the local-marketing prompt from campaign context + domain pack guidance."""
    brand_name = campaign_context.get("brand_name", "")
    goal = campaign_context.get("goal", "")
    budget = campaign_context.get("budget", "")
    campaign_analysis = campaign_context.get("campaign_analysis", "")
    domain_label = getattr(domain_pack, "label", "business")
    local_prompt = getattr(domain_pack, "local_prompt", "")
    location = campaign_context.get("location", "")

    return (
        f"You are a local marketing strategist specialising in "
        f"{domain_label.lower()} campaigns.\n\n"
        f"Brand: {brand_name}\n"
        f"Goal: {goal}\n"
        f"Budget: {budget}\n"
        f"Location: {location}\n\n"
        f"Here is the campaign analysis from our strategy team:\n"
        f"{str(campaign_analysis)[:4000]}\n\n"
        f"{local_prompt}\n\n"
        "Generate 3-5 local marketing ideas for this campaign. Use a mix of "
        "these idea types: event (host or sponsor a local event), partnership "
        "(collaborate with a nearby complementary business), geo_target "
        "(hyper-local ad targeting), and seo (local SEO / Google Business "
        "Profile optimisation). Do NOT produce variations of the same idea.\n\n"
        "For each idea provide:\n"
        "- type: one of \"event\", \"partnership\", \"geo_target\", \"seo\"\n"
        "- idea: a short description of the local marketing idea (1 sentence)\n"
        "- copy: ready-to-use copy for the initiative (1-2 sentences)\n\n"
        "Respond as JSON only, no markdown:\n"
        "{\n"
        '  "local_ideas": [\n'
        '    {"type": "event", "idea": "...", "copy": "..."},\n'
        '    {"type": "partnership", "idea": "...", "copy": "..."},\n'
        '    {"type": "geo_target", "idea": "...", "copy": "..."}\n'
        "  ]\n"
        "}"
    )


def _parse_local(raw: Any) -> list[LocalIdea]:
    """Normalise the parsed JSON into a list of LocalIdea dataclasses."""
    if not isinstance(raw, dict):
        raw = {}
    ideas_list = raw.get("local_ideas") or raw.get("ideas") or []
    if not isinstance(ideas_list, list):
        ideas_list = []

    result: list[LocalIdea] = []
    for item in ideas_list[:5]:
        if not isinstance(item, dict):
            continue
        idea = LocalIdea(
            type=str(item.get("type", "") or "").strip(),
            idea=str(item.get("idea", "") or "").strip(),
            copy=str(item.get("copy", "") or "").strip(),
        )
        if idea.type or idea.idea or idea.copy:
            result.append(idea)

    return result


def generate_local_ideas(
    campaign_context: dict[str, Any],
    domain_pack: DomainPack,
    *,
    gateway: AIGateway | None = None,
    tenant_id: Any = None,
    plan: str = "agency",
) -> list[LocalIdea]:
    """Generate 3-5 local marketing ideas for a campaign.

    Builds a prompt using the domain pack's ``local_prompt`` guidance plus the
    campaign context, calls the AIGateway, parses the JSON response via
    ``extract_json``, and returns a list of :class:`LocalIdea` objects.

    For the creator pack (which has no local presence and an empty
    ``local_prompt``), returns an empty list immediately without calling the
    AI gateway.

    Falls back to an empty list on any failure so the campaign preview still
    works without local ideas.

    Args:
        campaign_context: dict with keys ``brand_name``, ``goal``, ``budget``,
            ``campaign_analysis``, and optionally ``location``.
        domain_pack: the DomainPack for the campaign's domain.
        gateway: optional AIGateway instance (a new one is created if absent).
        tenant_id: tenant UUID for budget tracking.
        plan: tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        A list of 3-5 :class:`LocalIdea` objects, or [] for creators.
    """
    # Creators don't have local marketing — skip the AI call entirely
    local_prompt = getattr(domain_pack, "local_prompt", "")
    if not local_prompt:
        return []

    gw = gateway or AIGateway()
    prompt = _build_prompt(campaign_context, domain_pack)
    pack_id = getattr(domain_pack, "id", "generic")

    try:
        comp = gw.complete(
            prompt=prompt,
            tier=Tier.large,
            task=f"{pack_id}_local_ideas",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=1500,
            temperature=0.8,
            user_input=campaign_context.get("goal", ""),
            prompt_version=f"{pack_id}_local_ideas_v1.0",
        )
        try:
            raw = extract_json(comp.text) or {}
        except Exception:
            raw = {}
        return _parse_local(raw)
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.warning("%s local ideas generation failed (continuing): %s", pack_id, e)
        return _parse_local({})
