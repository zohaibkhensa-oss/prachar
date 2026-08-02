"""Pricing Psychology Generator — produces 3 pricing presentations per campaign.

Part P1.5 of the PRACHAR roadmap. Builds on the engineered offers (P1.4) by
generating 3 pricing presentations that leverage specific pricing-psychology
techniques: charm pricing, tiered pricing, bundling, anchoring, and loss-leader.

Each ``PricingPresentation`` carries:
  - technique:  the pricing technique used ("charm", "tier", "bundle",
                 "anchor", "loss_leader")
  - copy:        the pricing copy the audience sees
  - rationale:   a short explanation of why this presentation works
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


# ─── PricingPresentation dataclass ─────────────────────────────────────────


@dataclass
class PricingPresentation:
    """A single pricing presentation with a psychological technique and copy.

    Attributes:
        technique: the pricing technique used ("charm", "tier", "bundle",
            "anchor", "loss_leader").
        copy: the pricing copy the audience sees (1-2 sentences).
        rationale: a short explanation of why this presentation works.
    """

    technique: str
    copy: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─── Generator ─────────────────────────────────────────────────────────────


def _build_prompt(campaign_context: dict[str, Any], domain_pack: DomainPack) -> str:
    """Assemble the pricing-psychology prompt from campaign context + domain pack guidance."""
    brand_name = campaign_context.get("brand_name", "")
    goal = campaign_context.get("goal", "")
    budget = campaign_context.get("budget", "")
    campaign_analysis = campaign_context.get("campaign_analysis", "")
    domain_label = getattr(domain_pack, "label", "business")
    pricing_psychology_prompt = getattr(domain_pack, "pricing_psychology_prompt", "")

    return (
        f"You are a pricing psychologist specialising in "
        f"{domain_label.lower()} campaigns.\n\n"
        f"Brand: {brand_name}\n"
        f"Goal: {goal}\n"
        f"Budget: {budget}\n\n"
        f"Here is the campaign analysis from our strategy team:\n"
        f"{str(campaign_analysis)[:4000]}\n\n"
        f"{pricing_psychology_prompt}\n\n"
        "Generate exactly 3 pricing presentations for this campaign. Each must "
        "use a DIFFERENT pricing-psychology technique from: charm pricing "
        "(e.g. ₹99 instead of ₹100), tiered pricing (good/better/best), "
        "bundling (combine items for perceived value), anchoring (show a high "
        "reference price), and loss-leader (a low-margin item to draw people "
        "in). Do NOT produce variations of the same technique.\n\n"
        "For each presentation provide:\n"
        "- technique: one of \"charm\", \"tier\", \"bundle\", \"anchor\", "
        "\"loss_leader\"\n"
        "- copy: the pricing copy the audience sees (1-2 sentences)\n"
        "- rationale: one sentence explaining why this presentation works\n\n"
        "Respond as JSON only, no markdown:\n"
        "{\n"
        '  "pricing": [\n'
        '    {"technique": "charm", "copy": "...", "rationale": "..."},\n'
        '    {"technique": "tier", "copy": "...", "rationale": "..."},\n'
        '    {"technique": "bundle", "copy": "...", "rationale": "..."}\n'
        "  ]\n"
        "}"
    )


def _parse_pricing(raw: Any) -> list[PricingPresentation]:
    """Normalise the parsed JSON into a list of PricingPresentation dataclasses.

    Ensures exactly 3 presentations are returned. Missing or malformed entries
    are filled with empty-string placeholders so the caller always receives 3
    entries.
    """
    if not isinstance(raw, dict):
        raw = {}
    pricing_list = raw.get("pricing") or raw.get("pricing_presentations") or []
    if not isinstance(pricing_list, list):
        pricing_list = []

    result: list[PricingPresentation] = []
    for item in pricing_list[:3]:
        if not isinstance(item, dict):
            result.append(PricingPresentation(technique="", copy="", rationale=""))
            continue
        result.append(
            PricingPresentation(
                technique=str(item.get("technique", "") or "").strip(),
                copy=str(item.get("copy", "") or "").strip(),
                rationale=str(item.get("rationale", "") or "").strip(),
            )
        )

    # Pad to exactly 3 presentations with empty placeholders
    while len(result) < 3:
        result.append(PricingPresentation(technique="", copy="", rationale=""))

    return result


def generate_pricing_psychology(
    campaign_context: dict[str, Any],
    domain_pack: DomainPack,
    *,
    gateway: AIGateway | None = None,
    tenant_id: Any = None,
    plan: str = "agency",
) -> list[PricingPresentation]:
    """Generate 3 pricing presentations for a campaign.

    Builds a prompt using the domain pack's ``pricing_psychology_prompt``
    guidance plus the campaign context, calls the AIGateway, parses the JSON
    response via ``extract_json``, and returns exactly 3
    :class:`PricingPresentation` objects (each using a different pricing-
    psychology technique: charm, tier, bundle, anchor, or loss_leader).

    Falls back to 3 empty-copy presentations on any failure so the campaign
    preview still works without pricing presentations.

    Args:
        campaign_context: dict with keys ``brand_name``, ``goal``, ``budget``,
            and ``campaign_analysis``.
        domain_pack: the DomainPack for the campaign's domain.
        gateway: optional AIGateway instance (a new one is created if absent).
        tenant_id: tenant UUID for budget tracking.
        plan: tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        A list of 3 :class:`PricingPresentation` objects.
    """
    gw = gateway or AIGateway()
    prompt = _build_prompt(campaign_context, domain_pack)
    pack_id = getattr(domain_pack, "id", "generic")

    try:
        comp = gw.complete(
            prompt=prompt,
            tier=Tier.large,
            task=f"{pack_id}_pricing_psychology",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=1500,
            temperature=0.8,
            user_input=campaign_context.get("goal", ""),
            prompt_version=f"{pack_id}_pricing_psychology_v1.0",
        )
        try:
            raw = extract_json(comp.text) or {}
        except Exception:
            raw = {}
        return _parse_pricing(raw)
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.warning("%s pricing psychology generation failed (continuing): %s", pack_id, e)
        return _parse_pricing({})
