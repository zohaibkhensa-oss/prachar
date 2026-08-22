"""Offer Engineering Generator — produces 3 engineered offers per campaign.

Part P1.4 of the CURV AI roadmap. Builds on the creative directions (P1.1),
hook patterns (P1.2), and audience psychology (P1.3) by generating 3
psychologically-engineered offers that leverage pricing psychology techniques
such as anchoring, scarcity, bundling, loss-aversion, and decoy pricing.

Each ``Offer`` carries:
  - structure:                the psychological technique used (e.g. "anchoring",
                              "scarcity", "bundling", "loss-aversion", "decoy pricing")
  - copy:                     the offer text the audience sees
  - psychology_lever:         a short explanation of why this offer works
  - expected_conversion_lift: "high" | "medium" | "low" or a percentage range string
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


# ─── Offer dataclass ───────────────────────────────────────────────────────


@dataclass
class Offer:
    """A single engineered offer with psychological structure and copy.

    Attributes:
        structure: the psychological technique used (e.g. "anchoring",
            "scarcity", "bundling", "loss-aversion", "decoy pricing").
        copy: the offer text the audience sees.
        psychology_lever: a short explanation of why this offer works.
        expected_conversion_lift: "high" | "medium" | "low" or a percentage
            range string (e.g. "15-25%").
    """

    structure: str
    copy: str
    psychology_lever: str
    expected_conversion_lift: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─── Generator ─────────────────────────────────────────────────────────────


def _build_prompt(campaign_context: dict[str, Any], domain_pack: DomainPack) -> str:
    """Assemble the offers prompt from campaign context + domain pack guidance."""
    brand_name = campaign_context.get("brand_name", "")
    goal = campaign_context.get("goal", "")
    budget = campaign_context.get("budget", "")
    campaign_analysis = campaign_context.get("campaign_analysis", "")
    domain_label = getattr(domain_pack, "label", "business")
    offers_prompt = getattr(domain_pack, "offers_prompt", "")

    return (
        f"You are a pricing psychologist and offer engineer specialising in "
        f"{domain_label.lower()} campaigns.\n\n"
        f"Brand: {brand_name}\n"
        f"Goal: {goal}\n"
        f"Budget: {budget}\n\n"
        f"Here is the campaign analysis from our strategy team:\n"
        f"{str(campaign_analysis)[:4000]}\n\n"
        f"{offers_prompt}\n\n"
        "Generate exactly 3 engineered offers for this campaign. Each offer must "
        "use a DIFFERENT psychological pricing technique from: anchoring, "
        "scarcity, bundling, loss-aversion, decoy pricing. Do NOT produce "
        "variations of the same technique.\n\n"
        "For each offer provide:\n"
        "- structure: the psychological technique name (one word or hyphenated)\n"
        "- copy: the offer text the audience sees (1-2 sentences)\n"
        "- psychology_lever: one sentence explaining why this offer works\n"
        "- expected_conversion_lift: \"high\", \"medium\", \"low\", or a "
        "percentage range like \"15-25%\"\n\n"
        "Respond as JSON only, no markdown:\n"
        "{\n"
        '  "offers": [\n'
        '    {"structure": "anchoring", "copy": "...", "psychology_lever": "...", "expected_conversion_lift": "high"},\n'
        '    {"structure": "scarcity", "copy": "...", "psychology_lever": "...", "expected_conversion_lift": "medium"},\n'
        '    {"structure": "bundling", "copy": "...", "psychology_lever": "...", "expected_conversion_lift": "low"}\n'
        "  ]\n"
        "}"
    )


def _parse_offers(raw: Any) -> list[Offer]:
    """Normalise the parsed JSON into a list of Offer dataclasses.

    Ensures exactly 3 offers are returned. Missing or malformed offers are
    filled with empty-string placeholders so the caller always receives 3
    entries.
    """
    if not isinstance(raw, dict):
        raw = {}
    offers_list = raw.get("offers") or []
    if not isinstance(offers_list, list):
        offers_list = []

    result: list[Offer] = []
    for item in offers_list[:3]:
        if not isinstance(item, dict):
            result.append(Offer(structure="", copy="", psychology_lever="", expected_conversion_lift=""))
            continue
        result.append(
            Offer(
                structure=str(item.get("structure", "") or "").strip(),
                copy=str(item.get("copy", "") or "").strip(),
                psychology_lever=str(item.get("psychology_lever", "") or "").strip(),
                expected_conversion_lift=str(item.get("expected_conversion_lift", "") or "").strip(),
            )
        )

    # Pad to exactly 3 offers with empty placeholders
    while len(result) < 3:
        result.append(Offer(structure="", copy="", psychology_lever="", expected_conversion_lift=""))

    return result


def generate_offers(
    campaign_context: dict[str, Any],
    domain_pack: DomainPack,
    *,
    gateway: AIGateway | None = None,
    tenant_id: Any = None,
    plan: str = "agency",
) -> list[Offer]:
    """Generate 3 engineered offers for a campaign.

    Builds a prompt using the domain pack's ``offers_prompt`` guidance plus the
    campaign context, calls the AIGateway, parses the JSON response via
    ``extract_json``, and returns exactly 3 :class:`Offer` objects (each using
    a different psychological pricing technique: anchoring, scarcity, bundling,
    loss-aversion, or decoy pricing).

    Falls back to 3 empty-copy offers on any failure so the campaign preview
    still works without offers.

    Args:
        campaign_context: dict with keys ``brand_name``, ``goal``, ``budget``,
            and ``campaign_analysis``.
        domain_pack: the DomainPack for the campaign's domain.
        gateway: optional AIGateway instance (a new one is created if absent).
        tenant_id: tenant UUID for budget tracking.
        plan: tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        A list of 3 :class:`Offer` objects.
    """
    gw = gateway or AIGateway()
    prompt = _build_prompt(campaign_context, domain_pack)
    pack_id = getattr(domain_pack, "id", "generic")

    try:
        comp = gw.complete(
            prompt=prompt,
            tier=Tier.large,
            task=f"{pack_id}_offers",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=1500,
            temperature=0.8,
            user_input=campaign_context.get("goal", ""),
            prompt_version=f"{pack_id}_offers_v1.0",
        )
        try:
            raw = extract_json(comp.text) or {}
        except Exception:
            raw = {}
        return _parse_offers(raw)
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.warning("%s offers generation failed (continuing): %s", pack_id, e)
        return _parse_offers({})
