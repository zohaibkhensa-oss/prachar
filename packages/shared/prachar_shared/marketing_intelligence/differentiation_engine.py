"""Competitor Differentiation Generator — produces 3-5 differentiation entries.

Part P1.8 of the PRACHAR roadmap. Generates a differentiation matrix that
identifies what competitors claim and how this brand can counter those claims
with evidence-backed positioning.

Each ``DifferentiationEntry`` carries:
  - competitor_claim:  what a competitor typically claims
  - our_counter:       how this brand counters that claim
  - evidence:          the evidence or proof point that supports the counter
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


# ─── DifferentiationEntry dataclass ────────────────────────────────────────


@dataclass
class DifferentiationEntry:
    """A single competitor differentiation entry.

    Attributes:
        competitor_claim: what a competitor typically claims (1 sentence).
        our_counter: how this brand counters that claim (1 sentence).
        evidence: the evidence or proof point that supports the counter
            (1 sentence).
    """

    competitor_claim: str
    our_counter: str
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─── Generator ─────────────────────────────────────────────────────────────


def _build_prompt(campaign_context: dict[str, Any], domain_pack: DomainPack) -> str:
    """Assemble the differentiation prompt from campaign context + domain pack guidance."""
    brand_name = campaign_context.get("brand_name", "")
    goal = campaign_context.get("goal", "")
    budget = campaign_context.get("budget", "")
    campaign_analysis = campaign_context.get("campaign_analysis", "")
    domain_label = getattr(domain_pack, "label", "business")
    differentiation_prompt = getattr(domain_pack, "differentiation_prompt", "")

    return (
        f"You are a competitive positioning strategist specialising in "
        f"{domain_label.lower()} campaigns.\n\n"
        f"Brand: {brand_name}\n"
        f"Goal: {goal}\n"
        f"Budget: {budget}\n\n"
        f"Here is the campaign analysis from our strategy team:\n"
        f"{str(campaign_analysis)[:4000]}\n\n"
        f"{differentiation_prompt}\n\n"
        "Generate 3-5 competitor differentiation entries for this campaign. "
        "Each entry identifies a common competitor claim, how this brand "
        "counters it, and the evidence that supports the counter. Use "
        "realistic, generic competitor claims (not specific competitor "
        "names) and focus on what makes this brand genuinely different.\n\n"
        "For each entry provide:\n"
        "- competitor_claim: what a competitor typically claims (1 sentence)\n"
        "- our_counter: how this brand counters that claim (1 sentence)\n"
        "- evidence: the evidence or proof point that supports the counter "
        "(1 sentence)\n\n"
        "Respond as JSON only, no markdown:\n"
        "{\n"
        '  "differentiation": [\n'
        '    {"competitor_claim": "...", "our_counter": "...", "evidence": "..."},\n'
        '    {"competitor_claim": "...", "our_counter": "...", "evidence": "..."},\n'
        '    {"competitor_claim": "...", "our_counter": "...", "evidence": "..."}\n'
        "  ]\n"
        "}"
    )


def _parse_differentiation(raw: Any) -> list[DifferentiationEntry]:
    """Normalise the parsed JSON into a list of DifferentiationEntry dataclasses."""
    if not isinstance(raw, dict):
        raw = {}
    entries_list = raw.get("differentiation") or raw.get("entries") or []
    if not isinstance(entries_list, list):
        entries_list = []

    result: list[DifferentiationEntry] = []
    for item in entries_list[:5]:
        if not isinstance(item, dict):
            continue
        entry = DifferentiationEntry(
            competitor_claim=str(item.get("competitor_claim", "") or "").strip(),
            our_counter=str(item.get("our_counter", "") or "").strip(),
            evidence=str(item.get("evidence", "") or "").strip(),
        )
        if entry.competitor_claim or entry.our_counter or entry.evidence:
            result.append(entry)

    return result


def generate_differentiation(
    campaign_context: dict[str, Any],
    domain_pack: DomainPack,
    *,
    gateway: AIGateway | None = None,
    tenant_id: Any = None,
    plan: str = "agency",
) -> list[DifferentiationEntry]:
    """Generate 3-5 competitor differentiation entries for a campaign.

    Builds a prompt using the domain pack's ``differentiation_prompt`` guidance
    plus the campaign context, calls the AIGateway, parses the JSON response
    via ``extract_json``, and returns a list of :class:`DifferentiationEntry`
    objects.

    Falls back to an empty list on any failure so the campaign preview still
    works without differentiation entries.

    Args:
        campaign_context: dict with keys ``brand_name``, ``goal``, ``budget``,
            and ``campaign_analysis``.
        domain_pack: the DomainPack for the campaign's domain.
        gateway: optional AIGateway instance (a new one is created if absent).
        tenant_id: tenant UUID for budget tracking.
        plan: tenant plan string (e.g. "starter", "growth", "agency").

    Returns:
        A list of 3-5 :class:`DifferentiationEntry` objects.
    """
    gw = gateway or AIGateway()
    prompt = _build_prompt(campaign_context, domain_pack)
    pack_id = getattr(domain_pack, "id", "generic")

    try:
        comp = gw.complete(
            prompt=prompt,
            tier=Tier.large,
            task=f"{pack_id}_differentiation",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=1500,
            temperature=0.8,
            user_input=campaign_context.get("goal", ""),
            prompt_version=f"{pack_id}_differentiation_v1.0",
        )
        try:
            raw = extract_json(comp.text) or {}
        except Exception:
            raw = {}
        return _parse_differentiation(raw)
    except BudgetExceeded:
        raise
    except Exception as e:
        logger.warning("%s differentiation generation failed (continuing): %s", pack_id, e)
        return _parse_differentiation({})
