"""Universal Consult Engine — ONE pipeline for ALL domains.

Replaces the duplicated orchestration in consult.py and creator.py. The pipeline
never changes; only the Domain Pack changes.

Pipeline:
  1. Entity Extraction      ← pack.extraction_prompt + pack.extraction_schema
  2. Business Memory        ← shared brand creation/update
  3. Domain Detection       ← (caller passes pack_id)
  4. Load Domain Pack       ← from registry
  5. Marketing Intelligence ← CampaignBrain.analyse() (ALWAYS — no bypassing)
  6. Understanding          ← assembled from pack prompt fragments
  7. Plan                   ← assembled from pack prompt fragments
  8. Return unified response

This module is domain-agnostic. It imports nothing from any specific domain pack.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from prachar_shared.ai_gateway import AIGateway, BudgetExceeded, Tier
from prachar_shared.ai_gateway.json_utils import extract_json
from prachar_shared.domain_packs import DomainPack, get_registry
from prachar_shared.domain_packs.base import ToolSpec

from ..audit import log_audit
from ..models.tables import Brand, CampaignPlanRecord

logger = logging.getLogger(__name__)


# ─── Unified response shapes (domain-agnostic) ────────────────────────────


@dataclass
class ConsultResult:
    """The universal consult response. Domain-specific data lives in `domain`."""

    reply: str
    understanding: dict[str, Any]        # {summary, strengths, weaknesses, ...}
    opportunities: list[dict[str, Any]]  # [{title, description, impact, difficulty, timeframe}]
    plan: list[dict[str, Any]]           # [{week, theme, ...domain-specific fields}]
    extracted: dict[str, Any]            # extracted entity info
    brand_id: str
    brand_name: str
    confidence: float
    tokens_used: int
    model: str
    domain: str                          # pack id


@dataclass
class CampaignResult:
    """The universal campaign response. Domain-specific data lives in `domain`."""

    reply: str
    preview: dict[str, Any]              # {title, ...domain-specific preview fields}
    campaign_plan_id: str
    confidence: float
    tokens_used: int
    model: str
    domain: str


@dataclass
class ToolResult:
    """The universal tool response."""

    reply: str
    output: dict[str, Any]               # tool-specific output
    tokens_used: int
    model: str
    tool_id: str


# ─── The engine ────────────────────────────────────────────────────────────


class ConsultEngine:
    """Universal consult engine. Works for ANY domain pack.

    This class is domain-agnostic. It receives a DomainPack and uses its
    prompt fragments, schemas, and metadata to run the universal pipeline.
    """

    def __init__(self, gateway: AIGateway | None = None) -> None:
        self._gw = gateway or AIGateway()

    # ─── Consult ───────────────────────────────────────────────────────

    async def consult(
        self,
        *,
        message: str,
        pack_id: str,
        subtype_id: str = "",
        user,                              # CurrentUser
        session: AsyncSession,
        brand_id: UUID | None = None,
    ) -> ConsultResult:
        """Run the universal consult pipeline for any domain."""
        pack = get_registry().get_required(pack_id)
        plan = str(user.tenant.plan) if hasattr(user.tenant, "plan") else "agency"

        # ─── Step 1: Extract structured info ──────────────────────────
        extracted_dict, extract_tokens = await self._extract(
            message=message, pack=pack, user=user, plan=plan,
        )

        # ─── Step 2: Create or get brand ──────────────────────────────
        brand = await self._get_or_create_brand(
            session=session, user=user, pack=pack, subtype_id=subtype_id,
            extracted=extracted_dict, message=message, brand_id=brand_id,
        )

        # ─── Step 3: Run Marketing Intelligence (ALWAYS) ──────────────
        analysis_text, engine_tokens = await self._run_intelligence(
            pack=pack, brand=brand, extracted=extracted_dict,
            message=message, user=user, plan=plan,
        )

        # ─── Step 4: Generate understanding + opportunities + plan ────
        resp_dict, understanding_tokens, model, confidence = await self._generate_understanding(
            message=message, pack=pack, analysis_text=analysis_text,
            user=user, plan=plan,
        )

        # ─── Step 5: Update brand memory ──────────────────────────────
        await self._update_brand_memory(
            session=session, brand=brand, pack=pack,
            extracted=extracted_dict, understanding=resp_dict,
        )

        return ConsultResult(
            reply=resp_dict.get("reply", f"Thanks for telling me about {brand.name}!"),
            understanding=resp_dict.get("business") or resp_dict.get("profile") or {},
            opportunities=resp_dict.get("growth_opportunities", []),
            plan=resp_dict.get("plan", [])[:4],
            extracted=extracted_dict,
            brand_id=str(brand.id),
            brand_name=brand.name,
            confidence=confidence,
            tokens_used=engine_tokens + extract_tokens + understanding_tokens,
            model=model,
            domain=pack.id,
        )

    # ─── Campaign ──────────────────────────────────────────────────────

    async def campaign(
        self,
        *,
        pack_id: str,
        brand_id: UUID,
        goal: str,
        budget: str,
        user,
        session: AsyncSession,
    ) -> CampaignResult:
        """Run the universal campaign generation pipeline for any domain."""
        pack = get_registry().get_required(pack_id)
        plan = str(user.tenant.plan) if hasattr(user.tenant, "plan") else "agency"

        # Get the brand
        res = await session.execute(
            select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
        )
        brand = res.scalar_one_or_none()
        if brand is None:
            from fastapi import HTTPException, status
            raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")

        # ─── Step 1: Run CampaignBrain.generate_campaign() (ALWAYS) ───
        campaign_analysis, engine_tokens = await self._run_campaign_brain(
            pack=pack, brand=brand, goal=goal, budget=budget, user=user, plan=plan,
        )

        # ─── Step 1b: Generate 3 strategies + "why A not B" explanation ─
        strategies, strategy_explanation, strat_tokens = await self._generate_strategies(
            pack=pack, brand=brand, goal=goal, budget=budget,
            campaign_analysis=campaign_analysis, user=user, plan=plan,
        )

        # ─── Step 2: Generate campaign preview using pack prompt ──────
        resp_dict, preview_tokens, model, confidence = await self._generate_campaign_preview(
            pack=pack, brand=brand, goal=goal, budget=budget,
            campaign_analysis=campaign_analysis, user=user, plan=plan,
        )

        # ─── Step 2b: Generate 3 creative directions using pack prompt ─
        directions, dir_tokens = await self._generate_creative_directions(
            pack=pack, brand=brand, goal=goal, budget=budget,
            campaign_analysis=campaign_analysis, user=user, plan=plan,
        )

        # ─── Step 2c: Generate 5 hook patterns using pack prompt ──────
        hooks, hook_tokens = await self._generate_hooks(
            pack=pack, brand=brand, goal=goal, budget=budget,
            campaign_analysis=campaign_analysis, user=user, plan=plan,
        )

        # ─── Step 2d: Generate audience psychology using pack prompt ──
        audience_psychology, psych_tokens = await self._generate_audience_psychology(
            pack=pack, brand=brand, goal=goal, budget=budget,
            campaign_analysis=campaign_analysis, user=user, plan=plan,
        )

        # ─── Step 2e: Generate 3 engineered offers using pack prompt ──
        offers, offer_tokens = await self._generate_offers(
            pack=pack, brand=brand, goal=goal, budget=budget,
            campaign_analysis=campaign_analysis, user=user, plan=plan,
        )

        # ─── Step 2f: Generate 3 pricing presentations using pack prompt ─
        pricing_presentations, pricing_tokens = await self._generate_pricing_psychology(
            pack=pack, brand=brand, goal=goal, budget=budget,
            campaign_analysis=campaign_analysis, user=user, plan=plan,
        )

        # ─── Step 2g: Generate seasonal ideas using pack prompt ─────────
        seasonal_ideas, seasonal_tokens = await self._generate_seasonal_ideas(
            pack=pack, brand=brand, goal=goal, budget=budget,
            campaign_analysis=campaign_analysis, user=user, plan=plan,
        )

        # ─── Step 2h: Generate local marketing ideas using pack prompt ──
        local_ideas, local_tokens = await self._generate_local_ideas(
            pack=pack, brand=brand, goal=goal, budget=budget,
            campaign_analysis=campaign_analysis, user=user, plan=plan,
        )

        # ─── Step 2i: Generate competitor differentiation using pack prompt ─
        differentiation, diff_tokens = await self._generate_differentiation(
            pack=pack, brand=brand, goal=goal, budget=budget,
            campaign_analysis=campaign_analysis, user=user, plan=plan,
        )

        # ─── Step 2j: Generate A/B concepts (6 variants) using pack prompt ─
        ab_concepts, ab_tokens = await self._generate_ab_concepts(
            pack=pack, brand=brand, goal=goal, budget=budget,
            campaign_analysis=campaign_analysis, user=user, plan=plan,
            creative_directions=directions,
        )

        # ─── Step 3: Persist the campaign plan ────────────────────────
        campaign_plan_id = await self._persist_campaign_plan(
            session=session, user=user, pack=pack, brand=brand,
            goal=goal, budget=budget, resp_dict=resp_dict,
            analysis=campaign_analysis,
            tokens_used=engine_tokens + preview_tokens,
        )

        preview = resp_dict.get("preview") or {
            "title": resp_dict.get("title", ""),
            "content_plan": resp_dict.get("content_plan", []),
            "publishing_schedule": resp_dict.get("publishing_schedule", ""),
            "expected_growth": resp_dict.get("expected_growth", ""),
        }
        # Attach the 3 creative directions to the preview output
        preview["creative_directions"] = directions
        # Attach the 5 hook patterns to the preview output
        preview["hooks"] = hooks
        # Attach the audience psychology to the preview output
        preview["audience_psychology"] = audience_psychology
        # Attach the 3 engineered offers to the preview output
        preview["offers"] = offers
        # Attach the 3 pricing presentations to the preview output
        preview["pricing_psychology"] = pricing_presentations
        # Attach the seasonal ideas to the preview output
        preview["seasonal_ideas"] = seasonal_ideas
        # Attach the local marketing ideas to the preview output
        preview["local_ideas"] = local_ideas
        # Attach the competitor differentiation entries to the preview output
        preview["differentiation"] = differentiation
        # Attach the A/B concepts to the preview output
        preview["ab_concepts"] = ab_concepts
        # Attach the 3 strategies (primary/alternative/contrarian) to the preview
        preview["strategies"] = [s.to_dict() for s in strategies]
        # Attach the "why A not B" strategy explanation to the preview
        preview["strategy_explanation"] = strategy_explanation

        return CampaignResult(
            reply=resp_dict.get("reply", ""),
            preview=preview,
            campaign_plan_id=campaign_plan_id,
            confidence=confidence,
            tokens_used=engine_tokens + strat_tokens + preview_tokens + dir_tokens + hook_tokens + psych_tokens + offer_tokens + pricing_tokens + seasonal_tokens + local_tokens + diff_tokens + ab_tokens,
            model=model,
            domain=pack.id,
        )

    # ─── Tool (domain-specific tools like Repurpose, YouTube Plan) ─────

    async def tool(
        self,
        *,
        pack_id: str,
        tool_id: str,
        inputs: dict[str, Any],
        user,
    ) -> ToolResult:
        """Invoke a domain-specific tool. The pack supplies the prompt template."""
        pack = get_registry().get_required(pack_id)
        tool = pack.get_tool(tool_id)
        if tool is None:
            from fastapi import HTTPException, status
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Tool {tool_id!r} not found in pack {pack_id!r}",
            )
        plan = str(user.tenant.plan) if hasattr(user.tenant, "plan") else "agency"

        # Render the prompt with the supplied inputs
        prompt = self._render_tool_prompt(tool, inputs)

        comp = self._gw.complete(
            prompt=prompt,
            tier=Tier(tool.tier) if hasattr(Tier, tool.tier) else Tier.small,
            task=tool.task_name,
            tenant_id=user.tenant_id,
            plan=plan,
            max_tokens=tool.max_tokens,
            temperature=tool.temperature,
            user_input=json.dumps(inputs)[:1000],
            prompt_version=tool.prompt_version,
        )

        try:
            resp_dict = extract_json(comp.text) or {}
        except Exception:
            resp_dict = {"reply": comp.text[:500]}

        return ToolResult(
            reply=resp_dict.get("reply", ""),
            output=resp_dict,
            tokens_used=comp.tokens_used,
            model=comp.model,
            tool_id=tool_id,
        )

    # ─── Internal: extraction ──────────────────────────────────────────

    async def _extract(
        self, *, message: str, pack: DomainPack, user, plan: str,
    ) -> tuple[dict[str, Any], int]:
        """Step 1: Extract structured info from free text using pack prompt."""
        try:
            comp = self._gw.complete(
                prompt=pack.extraction_prompt.format(message=message[:1000]),
                tier=Tier.small,
                task=f"{pack.id}_extract",
                tenant_id=user.tenant_id,
                plan=plan,
                max_tokens=400,
                temperature=0.1,
                user_input=message,
                prompt_version=f"{pack.id}_extract_v1.0",
            )
            try:
                extracted = extract_json(comp.text) or {}
            except Exception:
                extracted = {}
            return extracted, comp.tokens_used
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.warning("%s extraction failed: %s", pack.id, e)
            return {}, 0

    # ─── Internal: brand creation (shared, domain-aware) ───────────────

    async def _get_or_create_brand(
        self, *, session: AsyncSession, user, pack: DomainPack,
        subtype_id: str, extracted: dict[str, Any], message: str,
        brand_id: UUID | None,
    ) -> Brand:
        """Get an existing brand or create a new one. Domain-aware via pack."""
        if brand_id is not None:
            res = await session.execute(
                select(Brand).where(Brand.id == brand_id, Brand.tenant_id == user.tenant_id)
            )
            brand = res.scalar_one_or_none()
            if brand is not None:
                return brand

        # Build brand_graph from pack schema + extracted info
        brand_graph = self._build_brand_graph(pack=pack, extracted=extracted, message=message)

        # Determine name
        name = (
            extracted.get("business_name")
            or extracted.get("channel_name")
            or self._infer_name_from_message(message)
            or f"New {pack.label}"
        )

        # Determine category from subtype or extracted
        category = (
            pack.map_subtype_to_category(subtype_id)
            if subtype_id
            else extracted.get("industry")
            or extracted.get("specialty")
            or extracted.get("niche")
            or pack.id
        )

        brand = Brand(
            tenant_id=user.tenant_id,
            name=name[:200],
            website=extracted.get("website") or None,
            category=category,
            customer_type=pack.customer_type,
            locales=["en-IN"],
            tone="friendly",
            brand_graph=brand_graph,
        )
        session.add(brand)
        await session.commit()
        await session.refresh(brand)

        await log_audit(
            session=session,
            tenant_id=user.tenant_id,
            user_id=user.id,
            action=f"{pack.id}.brand_created",
            entity_type="brand",
            entity_id=str(brand.id),
            payload={
                "name": brand.name,
                "category": category,
                "customer_type": pack.customer_type,
                "source": "conversational_onboarding",
            },
        )
        return brand

    # ─── Internal: marketing intelligence (ALWAYS runs) ────────────────

    async def _run_intelligence(
        self, *, pack: DomainPack, brand: Brand, extracted: dict[str, Any],
        message: str, user, plan: str,
    ) -> tuple[str, int]:
        """Step 3: Run CampaignBrain.analyse(). Always — no bypassing."""
        try:
            from prachar_shared.marketing_intelligence import CampaignBrain

            brain = CampaignBrain()
            result = await brain.analyse(
                tenant_id=user.tenant_id,
                plan=plan,
                business_name=brand.name,
                website=brand.website or "",
                category=brand.category or "",
                description=extracted.get("additional_context") or extracted.get("description") or "",
                goal=self._extract_goal(extracted, pack),
                locale="en-IN",
                brand_id=brand.id,
                additional_context=message,
            )
            biz = result.get("business_profile", {})
            aud = result.get("audience_profile", {})
            comp = result.get("competitor_profile", {})
            analysis_text = (
                f"Business Profile: {json.dumps(biz, indent=2)}\n\n"
                f"Audience Profile: {json.dumps(aud, indent=2)}\n\n"
                f"Competitor Profile: {json.dumps(comp, indent=2)}"
            )
            tokens = sum(
                eo.get("tokens_used", 0) for eo in result.get("engine_outputs", {}).values()
            )
            return analysis_text, tokens
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.warning("%s intelligence failed (continuing): %s", pack.id, e)
            return f"Extracted info: {json.dumps(extracted)}", 0

    # ─── Internal: understanding + plan generation ─────────────────────

    async def _generate_understanding(
        self, *, message: str, pack: DomainPack, analysis_text: str,
        user, plan: str,
    ) -> tuple[dict[str, Any], int, str, float]:
        """Step 4: Generate understanding + opportunities + plan via LLM."""
        prompt = self._assemble_understanding_prompt(
            message=message, pack=pack, analysis_text=analysis_text,
        )
        try:
            comp = self._gw.complete(
                prompt=prompt,
                tier=Tier.small,
                task=f"{pack.id}_understanding",
                tenant_id=user.tenant_id,
                plan=plan,
                max_tokens=2500,
                temperature=0.7,
                user_input=message,
                prompt_version=f"{pack.id}_understanding_v1.0",
            )
            try:
                resp = extract_json(comp.text) or {}
            except Exception:
                resp = {"reply": comp.text[:500]}
            return resp, comp.tokens_used, comp.model, comp.confidence
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.error("%s understanding failed: %s", pack.id, e)
            return {"reply": f"Thanks for telling me about your {pack.label.lower()}!"}, 0, "", 0.0

    # ─── Internal: campaign brain (ALWAYS runs) ────────────────────────

    async def _run_campaign_brain(
        self, *, pack: DomainPack, brand: Brand, goal: str, budget: str,
        user, plan: str,
    ) -> tuple[str, int]:
        """Run CampaignBrain.generate_campaign(). Always — no bypassing."""
        try:
            from prachar_shared.marketing_intelligence import CampaignBrain

            brain = CampaignBrain()
            result = await brain.generate_campaign(
                tenant_id=user.tenant_id,
                plan=plan,
                business_name=brand.name,
                website=brand.website or "",
                category=brand.category or "",
                description="",
                goal=goal,
                budget=budget,
                locale="en-IN",
                brand_id=brand.id,
            )
            tokens = sum(
                eo.get("tokens_used", 0) for eo in result.get("engine_outputs", {}).values()
            )
            return json.dumps(result, indent=2, default=str), tokens
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.warning("%s campaign brain failed (continuing): %s", pack.id, e)
            return "{}", 0

    # ─── Internal: multi-strategy generation (B.1.1 + B.1.2) ───────────

    async def _generate_strategies(
        self, *, pack: DomainPack, brand: Brand, goal: str, budget: str,
        campaign_analysis: str, user, plan: str,
    ) -> tuple[list[Any], dict[str, Any], int]:
        """Generate 3 strategies (primary/alternative/contrarian) + explanation.

        Uses the StrategyEngine to produce 3 genuinely different strategies and
        a "why A not B" explanation. The domain pack's ``strategy_prompt`` shapes
        what makes a good strategy for this domain.

        Falls back to default strategies + empty explanation on failure so the
        campaign preview still works without the strategy layer.

        Returns:
            A tuple of (strategies list, explanation dict, tokens_used).
        """
        from prachar_shared.marketing_intelligence.strategy_engine import (
            Strategy,
            StrategyEngine,
        )

        try:
            # Parse the campaign analysis JSON to extract context for the engine
            try:
                analysis_dict = json.loads(campaign_analysis) if campaign_analysis else {}
            except Exception:
                analysis_dict = {}

            business_context = analysis_dict.get("business_profile") or {
                "name": brand.name,
                "category": brand.category or "",
                "domain": pack.id,
            }
            audience_context = analysis_dict.get("audience_profile") or {}
            competitor_context = analysis_dict.get("competitor_profile") or {}

            # Enrich business context with domain-specific strategy guidance
            strategy_guidance = getattr(pack, "strategy_prompt", "")
            if strategy_guidance:
                business_context = dict(business_context)
                business_context["strategy_guidance"] = strategy_guidance

            engine = StrategyEngine(
                gateway=self._gw,
                tenant_id=user.tenant_id,
                plan=plan,
            )
            strategies = await engine.generate_strategies(
                business_context=business_context,
                audience_context=audience_context,
                competitor_context=competitor_context,
                budget=budget,
                goal=goal,
            )
            explanation = await engine.explain_choice(
                strategies=strategies,
                business_context=business_context,
                audience_context=audience_context,
                budget=budget,
                goal=goal,
            )
            return strategies, explanation, 0
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.warning("%s strategy generation failed (continuing): %s", pack.id, e)
            from prachar_shared.marketing_intelligence.strategy_engine import (
                Strategy as _S,
            )
            return [], {}, 0

    # ─── Internal: campaign preview generation ─────────────────────────

    async def _generate_campaign_preview(
        self, *, pack: DomainPack, brand: Brand, goal: str, budget: str,
        campaign_analysis: str, user, plan: str,
    ) -> tuple[dict[str, Any], int, str, float]:
        """Generate campaign preview using pack campaign_prompt."""
        prompt = pack.campaign_prompt.format(
            business_name=brand.name,
            creator_name=brand.name,
            goal=goal,
            budget=budget,
            campaign=campaign_analysis[:6000],
            analysis=campaign_analysis[:6000],
        )
        try:
            comp = self._gw.complete(
                prompt=prompt,
                tier=Tier.small,
                task=f"{pack.id}_campaign_preview",
                tenant_id=user.tenant_id,
                plan=plan,
                max_tokens=2500,
                temperature=0.7,
                user_input=goal,
                prompt_version=f"{pack.id}_campaign_preview_v1.0",
            )
            try:
                resp = extract_json(comp.text) or {}
            except Exception:
                resp = {"reply": comp.text[:500]}
            return resp, comp.tokens_used, comp.model, comp.confidence
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.error("%s campaign preview failed: %s", pack.id, e)
            return {"reply": f"Here's your campaign for {brand.name}!"}, 0, "", 0.0

    # ─── Internal: creative directions generation ──────────────────────

    async def _generate_creative_directions(
        self, *, pack: DomainPack, brand: Brand, goal: str, budget: str,
        campaign_analysis: str, user, plan: str,
    ) -> tuple[list[dict[str, Any]], int]:
        """Generate 3 creative directions using the pack's creative_directions_prompt.

        Returns a list of dicts, each with: id, hook, angle, tone,
        sample_headline, sample_cta. Falls back to an empty list on failure
        so the campaign preview still works without directions.
        """
        prompt = (
            f"You are a creative director for a {pack.label.lower()} campaign.\n\n"
            f"Brand: {brand.name}\n"
            f"Goal: {goal}\n"
            f"Budget: {budget}\n\n"
            f"Here is the campaign analysis from our strategy team:\n"
            f"{campaign_analysis[:4000]}\n\n"
            f"{pack.creative_directions_prompt}\n\n"
            "Respond as JSON only, no markdown:\n"
            "{\n"
            '  "creative_directions": [\n'
            '    {"id": "...", "hook": "...", "angle": "...", '
            '"tone": "...", "sample_headline": "...", "sample_cta": "..."},\n'
            '    {"id": "...", "hook": "...", "angle": "...", '
            '"tone": "...", "sample_headline": "...", "sample_cta": "..."},\n'
            '    {"id": "...", "hook": "...", "angle": "...", '
            '"tone": "...", "sample_headline": "...", "sample_cta": "..."}\n'
            "  ]\n"
            "}"
        )
        try:
            comp = self._gw.complete(
                prompt=prompt,
                tier=Tier.large,
                task=f"{pack.id}_creative_directions",
                tenant_id=user.tenant_id,
                plan=plan,
                max_tokens=1500,
                temperature=0.8,
                user_input=goal,
                prompt_version=f"{pack.id}_creative_directions_v1.0",
            )
            try:
                resp = extract_json(comp.text) or {}
            except Exception:
                resp = {}
            directions = resp.get("creative_directions") or []
            # Normalise: ensure each direction has the required keys
            normalised = []
            for d in directions[:3]:
                if not isinstance(d, dict):
                    continue
                normalised.append({
                    "id": d.get("id") or f"direction_{len(normalised) + 1}",
                    "hook": d.get("hook", ""),
                    "angle": d.get("angle", ""),
                    "tone": d.get("tone", ""),
                    "sample_headline": d.get("sample_headline", ""),
                    "sample_cta": d.get("sample_cta", ""),
                })
            return normalised, comp.tokens_used
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.warning("%s creative directions failed (continuing): %s", pack.id, e)
            return [], 0

    # ─── Internal: hook patterns generation ─────────────────────────────

    async def _generate_hooks(
        self, *, pack: DomainPack, brand: Brand, goal: str, budget: str,
        campaign_analysis: str, user, plan: str,
    ) -> tuple[list[dict[str, Any]], int]:
        """Generate 5 hook patterns using the pack's hooks_prompt.

        Returns a list of dicts, each with: pattern, copy, why_it_works.
        Falls back to an empty list on failure so the campaign preview still
        works without hooks.
        """
        from prachar_shared.marketing_intelligence.hooks import generate_hooks

        try:
            campaign_context = {
                "brand_name": brand.name,
                "goal": goal,
                "budget": budget,
                "campaign_analysis": campaign_analysis,
            }
            hooks = generate_hooks(
                campaign_context=campaign_context,
                domain_pack=pack,
                gateway=self._gw,
                tenant_id=user.tenant_id,
                plan=plan,
            )
            # Serialise Hook dataclasses to dicts for the preview payload
            return [h.to_dict() for h in hooks], 0
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.warning("%s hooks failed (continuing): %s", pack.id, e)
            return [], 0

    # ─── Internal: audience psychology generation ──────────────────────

    async def _generate_audience_psychology(
        self, *, pack: DomainPack, brand: Brand, goal: str, budget: str,
        campaign_analysis: str, user, plan: str,
    ) -> tuple[dict[str, Any], int]:
        """Generate the audience psychology profile using the pack's
        audience_psychology_prompt.

        Returns a dict with: motivations, objections, emotional_triggers,
        decision_style. Falls back to empty defaults on failure so the
        campaign preview still works without the psychology layer.
        """
        from prachar_shared.marketing_intelligence.audience_psychology import (
            generate_audience_psychology,
        )

        try:
            campaign_context = {
                "brand_name": brand.name,
                "goal": goal,
                "budget": budget,
                "campaign_analysis": campaign_analysis,
            }
            psychology = generate_audience_psychology(
                campaign_context=campaign_context,
                domain_pack=pack,
                gateway=self._gw,
                tenant_id=user.tenant_id,
                plan=plan,
            )
            # Serialise AudiencePsychology dataclass to dict for the preview payload
            return psychology.to_dict(), 0
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.warning("%s audience psychology failed (continuing): %s", pack.id, e)
            return {
                "motivations": [],
                "objections": [],
                "emotional_triggers": [],
                "decision_style": "",
            }, 0

    # ─── Internal: offer engineering generation ───────────────────────

    async def _generate_offers(
        self, *, pack: DomainPack, brand: Brand, goal: str, budget: str,
        campaign_analysis: str, user, plan: str,
    ) -> tuple[list[dict[str, Any]], int]:
        """Generate 3 engineered offers using the pack's offers_prompt.

        Returns a list of dicts, each with: structure, copy, psychology_lever,
        expected_conversion_lift. Falls back to an empty list on failure so the
        campaign preview still works without offers.
        """
        from prachar_shared.marketing_intelligence.offer_engine import generate_offers

        try:
            campaign_context = {
                "brand_name": brand.name,
                "goal": goal,
                "budget": budget,
                "campaign_analysis": campaign_analysis,
            }
            offers = generate_offers(
                campaign_context=campaign_context,
                domain_pack=pack,
                gateway=self._gw,
                tenant_id=user.tenant_id,
                plan=plan,
            )
            # Serialise Offer dataclasses to dicts for the preview payload
            return [o.to_dict() for o in offers], 0
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.warning("%s offers failed (continuing): %s", pack.id, e)
            return [], 0

    # ─── Internal: pricing psychology generation ──────────────────────

    async def _generate_pricing_psychology(
        self, *, pack: DomainPack, brand: Brand, goal: str, budget: str,
        campaign_analysis: str, user, plan: str,
    ) -> tuple[list[dict[str, Any]], int]:
        """Generate 3 pricing presentations using the pack's pricing_psychology_prompt.

        Returns a list of dicts, each with: technique, copy, rationale.
        Falls back to an empty list on failure so the campaign preview still
        works without pricing presentations.
        """
        from prachar_shared.marketing_intelligence.pricing_psychology import (
            generate_pricing_psychology,
        )

        try:
            campaign_context = {
                "brand_name": brand.name,
                "goal": goal,
                "budget": budget,
                "campaign_analysis": campaign_analysis,
            }
            presentations = generate_pricing_psychology(
                campaign_context=campaign_context,
                domain_pack=pack,
                gateway=self._gw,
                tenant_id=user.tenant_id,
                plan=plan,
            )
            # Serialise PricingPresentation dataclasses to dicts for the preview payload
            return [p.to_dict() for p in presentations], 0
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.warning("%s pricing psychology failed (continuing): %s", pack.id, e)
            return [], 0

    # ─── Internal: seasonal ideas generation ──────────────────────────

    async def _generate_seasonal_ideas(
        self, *, pack: DomainPack, brand: Brand, goal: str, budget: str,
        campaign_analysis: str, user, plan: str,
    ) -> tuple[list[dict[str, Any]], int]:
        """Generate seasonal marketing ideas using the pack's seasonal_prompt.

        Returns a list of dicts, each with: month, occasion, idea, copy.
        Falls back to an empty list on failure so the campaign preview still
        works without seasonal ideas.
        """
        from prachar_shared.marketing_intelligence.seasonal_engine import (
            generate_seasonal_ideas,
        )

        try:
            campaign_context = {
                "brand_name": brand.name,
                "goal": goal,
                "budget": budget,
                "campaign_analysis": campaign_analysis,
            }
            ideas = generate_seasonal_ideas(
                campaign_context=campaign_context,
                domain_pack=pack,
                gateway=self._gw,
                tenant_id=user.tenant_id,
                plan=plan,
            )
            # Serialise SeasonalIdea dataclasses to dicts for the preview payload
            return [i.to_dict() for i in ideas], 0
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.warning("%s seasonal ideas failed (continuing): %s", pack.id, e)
            return [], 0

    # ─── Internal: local marketing ideas generation ───────────────────

    async def _generate_local_ideas(
        self, *, pack: DomainPack, brand: Brand, goal: str, budget: str,
        campaign_analysis: str, user, plan: str,
    ) -> tuple[list[dict[str, Any]], int]:
        """Generate local marketing ideas using the pack's local_prompt.

        Returns a list of dicts, each with: type, idea, copy. Returns [] for
        the creator pack (no local marketing). Falls back to an empty list on
        failure so the campaign preview still works without local ideas.
        """
        from prachar_shared.marketing_intelligence.local_engine import (
            generate_local_ideas,
        )

        try:
            campaign_context = {
                "brand_name": brand.name,
                "goal": goal,
                "budget": budget,
                "campaign_analysis": campaign_analysis,
            }
            ideas = generate_local_ideas(
                campaign_context=campaign_context,
                domain_pack=pack,
                gateway=self._gw,
                tenant_id=user.tenant_id,
                plan=plan,
            )
            # Serialise LocalIdea dataclasses to dicts for the preview payload
            return [i.to_dict() for i in ideas], 0
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.warning("%s local ideas failed (continuing): %s", pack.id, e)
            return [], 0

    # ─── Internal: competitor differentiation generation ──────────────

    async def _generate_differentiation(
        self, *, pack: DomainPack, brand: Brand, goal: str, budget: str,
        campaign_analysis: str, user, plan: str,
    ) -> tuple[list[dict[str, Any]], int]:
        """Generate competitor differentiation entries using the pack's
        differentiation_prompt.

        Returns a list of dicts, each with: competitor_claim, our_counter,
        evidence. Falls back to an empty list on failure so the campaign
        preview still works without differentiation entries.
        """
        from prachar_shared.marketing_intelligence.differentiation_engine import (
            generate_differentiation,
        )

        try:
            campaign_context = {
                "brand_name": brand.name,
                "goal": goal,
                "budget": budget,
                "campaign_analysis": campaign_analysis,
            }
            entries = generate_differentiation(
                campaign_context=campaign_context,
                domain_pack=pack,
                gateway=self._gw,
                tenant_id=user.tenant_id,
                plan=plan,
            )
            # Serialise DifferentiationEntry dataclasses to dicts for the preview payload
            return [e.to_dict() for e in entries], 0
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.warning("%s differentiation failed (continuing): %s", pack.id, e)
            return [], 0

    # ─── Internal: A/B concepts generation ─────────────────────────────

    async def _generate_ab_concepts(
        self, *, pack: DomainPack, brand: Brand, goal: str, budget: str,
        campaign_analysis: str, user, plan: str,
        creative_directions: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], int]:
        """Generate 6 A/B concept variants (3 directions × 2 variants).

        Returns a list of dicts, each with: direction_id, variant_label,
        what_changed, why, expected_audience_segment, hook, headline, cta.
        Falls back to an empty list on failure so the campaign preview
        still works without A/B concepts.
        """
        from prachar_shared.marketing_intelligence.ab_concepts import (
            generate_ab_concepts,
        )

        try:
            campaign_context = {
                "brand_name": brand.name,
                "goal": goal,
                "budget": budget,
                "campaign_analysis": campaign_analysis,
            }
            concepts = generate_ab_concepts(
                creative_directions=creative_directions,
                campaign_context=campaign_context,
                gateway=self._gw,
                tenant_id=user.tenant_id,
                plan=plan,
            )
            # Serialise ABConcept dataclasses to dicts for the preview payload
            return [c.to_dict() for c in concepts], 0
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.warning("%s A/B concepts failed (continuing): %s", pack.id, e)
            return [], 0

    # ─── Internal: persistence (shared) ────────────────────────────────

    async def _persist_campaign_plan(
        self, *, session: AsyncSession, user, pack: DomainPack, brand: Brand,
        goal: str, budget: str, resp_dict: dict[str, Any], analysis: str,
        tokens_used: int,
    ) -> str:
        """Persist a campaign plan. Shared across all domains."""
        import uuid as _uuid

        record = CampaignPlanRecord(
            id=_uuid.uuid4(),
            tenant_id=user.tenant_id,
            brand_id=brand.id,
            name=resp_dict.get("title") or resp_dict.get("preview", {}).get("title") or f"{pack.campaign_template}",
            goal=goal,
            budget=budget,
            locale="en-IN",
            campaign={
                "preview": resp_dict.get("preview", resp_dict),
                "analysis": analysis[:8000],
                "domain": pack.id,
                "template": pack.campaign_template,
            },
            overall_confidence=float(resp_dict.get("confidence") or resp_dict.get("preview", {}).get("confidence") or 0),
            total_cost_usd=0.0,
            total_tokens=tokens_used,
            status="draft",
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)

        await log_audit(
            session=session,
            tenant_id=user.tenant_id,
            user_id=user.id,
            action=f"{pack.id}.campaign_created",
            entity_type="campaign_plan",
            entity_id=str(record.id),
            payload={
                "name": record.name,
                "goal": goal,
                "domain": pack.id,
                "template": pack.campaign_template,
            },
        )
        return str(record.id)

    # ─── Internal: brand memory update ─────────────────────────────────

    async def _update_brand_memory(
        self, *, session: AsyncSession, brand: Brand, pack: DomainPack,
        extracted: dict[str, Any], understanding: dict[str, Any],
    ) -> None:
        """Update brand_graph with extracted info + understanding."""
        graph = dict(brand.brand_graph or {})
        # Domain-specific extracted fields
        for k, v in extracted.items():
            if v:
                graph[k] = v
        # Understanding (profile/position/business)
        if "business" in understanding:
            graph["business"] = understanding["business"]
        if "profile" in understanding:
            graph["profile"] = understanding["profile"]
        if "position" in understanding:
            graph["position"] = understanding["position"]
        graph["domain"] = pack.id
        graph["memory_namespace"] = pack.memory_namespace

        brand.brand_graph = graph
        await session.commit()

    # ─── Internal: prompt assembly ─────────────────────────────────────

    def _assemble_understanding_prompt(
        self, *, message: str, pack: DomainPack, analysis_text: str,
    ) -> str:
        """Assemble the understanding prompt from pack fragments.

        The skeleton is universal; the domain-specific parts come from the pack.
        """
        # Build the "business" or "profile" section based on pack
        if pack.id == "creator":
            understanding_section = """\
2. **profile**: A structured creator profile with:
   - niche: Their content niche (specific)
   - platforms: List of platforms they're on
   - upload_frequency: Their posting cadence
   - content_pillars: 3-4 main content themes
   - audience: Who watches/follows them
   - audience_size: Estimated size (if inferrable)
   - growth_stage: "Emerging", "Growing", "Established", or "Pro"
   - monetisation: Current monetisation methods
   - brand_partnerships: Notable brand deals (or empty)
   - competitors: 2-3 similar creators

3. **position**: A structured position analysis with:
   - strengths: 3-4 strengths
   - weaknesses: 2-3 weaknesses or gaps
"""
            opportunity_section = pack.opportunity_prompt
            plan_section = pack.week_prompt
            response_shape = """\
{{
  "reply": "...",
  "profile": {{
    "niche": "...",
    "platforms": ["..."],
    "upload_frequency": "...",
    "content_pillars": ["..."],
    "audience": "...",
    "audience_size": "...",
    "growth_stage": "...",
    "monetisation": "...",
    "brand_partnerships": ["..."],
    "competitors": ["..."]
  }},
  "position": {{
    "strengths": ["..."],
    "weaknesses": ["..."],
    "growth_opportunities": ["..."],
    "content_gaps": ["..."],
    "monetisation_opportunities": ["..."]
  }},
  "plan": [
    {{"week": 1, "theme": "...", "videos": ["..."], "shorts": ["..."], "community_posts": ["..."], "collaborations": ["..."], "seo": ["..."], "newsletter": "...", "live_sessions": "...", "kpis": ["..."]}}
  ]
}}
"""
        else:
            understanding_section = """\
2. **business**: A structured business understanding with:
   - summary: 2-3 sentence plain-language summary
   - strengths: 3-4 strengths
   - weaknesses: 2-3 weaknesses or gaps
   - likely_customers: 3-4 customer types
   - likely_competitors: 2-3 competitor types
   - marketing_opportunities: 3-4 marketing opportunities
   - seasonal_opportunities: 2-3 seasonal opportunities (or empty)
   - marketing_maturity: "Beginner", "Intermediate", or "Advanced"
   - potential_risks: 2-3 risks
"""
            opportunity_section = pack.opportunity_prompt
            plan_section = pack.week_prompt
            response_shape = """\
{{
  "reply": "...",
  "business": {{
    "summary": "...",
    "strengths": ["..."],
    "weaknesses": ["..."],
    "likely_customers": ["..."],
    "likely_competitors": ["..."],
    "marketing_opportunities": ["..."],
    "seasonal_opportunities": ["..."],
    "marketing_maturity": "...",
    "potential_risks": ["..."]
  }},
  "growth_opportunities": [
    {{"title": "...", "description": "...", "business_impact": "...", "difficulty": "...", "timeframe": "..."}}
  ],
  "plan": [
    {{"week": 1, "theme": "...", "objectives": ["..."], "content": ["..."], "offers": ["..."], "channels": ["..."], "kpis": ["..."]}}
  ]
}}
"""

        jargon_list = ", ".join(f'"{j}"' for j in pack.forbidden_jargon)
        return f"""\
You are a world-class {pack.conversation_role} having a conversation with a {pack.label.lower()} owner.

The owner said: "{message[:1000]}"

Here is what we extracted and analyzed:
{analysis_text[:6000]}

Write a response that makes the owner feel understood. Include:

1. **reply**: A warm, conversational 2-3 sentence opening that shows you get \
their {pack.label.lower()}. Speak like a knowledgeable friend ("bro" energy), \
not a robot. Never use the words "AI", "engine", "algorithm", or "data". \
Speak as "I". Never use marketing jargon like {jargon_list}.

{understanding_section}
{opportunity_section}
{plan_section}

{pack.recommendations_prompt}

Respond as JSON only:
{response_shape}
"""

    # ─── Internal: helpers ─────────────────────────────────────────────

    def _build_brand_graph(
        self, *, pack: DomainPack, extracted: dict[str, Any], message: str,
    ) -> dict[str, Any]:
        """Build the initial brand_graph from pack schema + extracted info."""
        graph: dict[str, Any] = {"domain": pack.id, "memory_namespace": pack.memory_namespace}
        # Include any extracted field that's in the pack's schema
        schema_props = pack.brand_graph_schema.get("properties", {})
        for k in schema_props:
            if k in extracted and extracted[k]:
                graph[k] = extracted[k]
        # Always store the original message
        graph["description"] = message[:2000]
        return graph

    def _extract_goal(self, extracted: dict[str, Any], pack: DomainPack) -> str:
        goals = extracted.get("goals") or []
        if isinstance(goals, list) and goals:
            return "; ".join(str(g) for g in goals)
        return pack.default_goal

    def _infer_name_from_message(self, message: str) -> str:
        """Heuristic: look for 'called X', 'named X', 'channel X', '@x'."""
        import re
        for pattern in [
            r"called\s+([A-Z][\w&'-]+(?:\s+[A-Z][\w&'-]+)?)",
            r"named\s+([A-Z][\w&'-]+(?:\s+[A-Z][\w&'-]+)?)",
            r"channel\s+([A-Z][\w&'-]+(?:\s+[A-Z][\w&'-]+)?)",
            r"@([A-Za-z0-9_]+)",
        ]:
            m = re.search(pattern, message)
            if m:
                return m.group(1)
        return ""

    def _render_tool_prompt(self, tool: ToolSpec, inputs: dict[str, Any]) -> str:
        """Render a tool prompt template with the supplied inputs."""
        # Provide common placeholders
        safe_inputs = {k: str(v) for k, v in inputs.items()}
        try:
            return tool.prompt_template.format(**safe_inputs)
        except KeyError:
            # If a placeholder is missing, fall back to a generic render
            return tool.prompt_template.replace("{title}", safe_inputs.get("video_title", "")).replace(
                "{description}", safe_inputs.get("video_description", "")
            ).replace("{niche}", safe_inputs.get("niche", "")).replace(
                "{concept}", safe_inputs.get("video_concept", "")
            ).replace("{audience}", safe_inputs.get("audience", ""))
