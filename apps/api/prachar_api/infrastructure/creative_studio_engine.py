"""Creative Studio Engine — API-layer wrapper around ``CreativeStudio``.

Similar to how ``consult_engine.py`` wraps the consult flow for the API layer,
this module wraps the shared ``CreativeStudio`` for use in API routes.

It handles:
  - Loading the campaign plan from the database
  - Loading the creative direction from the database
  - Building the domain context from the domain pack
  - Calling ``CreativeStudio.generate_all()``
  - Returning a serialisable dict for the API response

API endpoints (P2.3) will call ``generate_package()``.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from prachar_shared.ai_gateway import AIGateway
from prachar_shared.creative_studio.studio import CreativePackage, CreativeStudio
from prachar_shared.domain_packs import get_registry as get_domain_pack_registry

from ..models.tables import CampaignPlanRecord, CreativeDirectionRecord

logger = logging.getLogger(__name__)


class CreativeStudioEngine:
    """API-layer wrapper around ``CreativeStudio``.

    Loads campaign + creative direction from the database, builds the domain
    context from the domain pack, and delegates generation to ``CreativeStudio``.
    """

    def __init__(self, gateway: AIGateway | None = None) -> None:
        self._gw = gateway or AIGateway()
        self._studio = CreativeStudio(self._gw)

    async def generate_package(
        self,
        *,
        campaign_id: UUID,
        creative_direction_id: UUID,
        domain: str,
        session: AsyncSession,
        brand_id: UUID | None = None,
        tenant_id: UUID | None = None,
        plan: str = "agency",
    ) -> dict[str, Any]:
        """Load campaign + creative direction from DB, generate all formats.

        Returns a serialisable dict (the ``CreativePackage.to_dict()`` output).
        """
        campaign_dict, creative_direction_dict, domain_context, resolved_tenant = (
            await self._load_inputs(
                campaign_id=campaign_id,
                creative_direction_id=creative_direction_id,
                domain=domain,
                session=session,
                tenant_id=tenant_id,
            )
        )

        # ─── 4. Generate all 10 formats ────────────────────────────────
        package: CreativePackage = await self._studio.generate_all(
            campaign=campaign_dict,
            creative_direction=creative_direction_dict,
            domain_context=domain_context,
            tenant_id=resolved_tenant,
            plan=plan,
        )

        return package.to_dict()

    async def generate_one(
        self,
        format_id: str,
        *,
        campaign_id: UUID,
        creative_direction_id: UUID,
        domain: str,
        session: AsyncSession,
        brand_id: UUID | None = None,
        tenant_id: UUID | None = None,
        plan: str = "agency",
    ) -> dict[str, Any]:
        """Load campaign + creative direction from DB, generate one format.

        Returns the single format's content dict. Raises ``KeyError`` (surfaced
        as a 404 by the router) if ``format_id`` is unknown.
        """
        campaign_dict, creative_direction_dict, domain_context, resolved_tenant = (
            await self._load_inputs(
                campaign_id=campaign_id,
                creative_direction_id=creative_direction_id,
                domain=domain,
                session=session,
                tenant_id=tenant_id,
            )
        )

        return await self._studio.generate_one(
            format_id,
            campaign=campaign_dict,
            creative_direction=creative_direction_dict,
            domain_context=domain_context,
            tenant_id=resolved_tenant,
            plan=plan,
        )

    async def regenerate_field(
        self,
        format_id: str,
        field_name: str,
        current_content: dict[str, Any],
        *,
        campaign_id: UUID,
        creative_direction_id: UUID,
        domain: str,
        session: AsyncSession,
        brand_id: UUID | None = None,
        tenant_id: UUID | None = None,
        plan: str = "agency",
    ) -> dict[str, Any]:
        """Load campaign + creative direction from DB, regenerate one field.

        Returns ``{"field_name": ..., "new_value": ...}``. Raises ``KeyError``
        (surfaced as a 404 by the router) if ``format_id`` or ``field_name`` is
        unknown.
        """
        campaign_dict, creative_direction_dict, domain_context, resolved_tenant = (
            await self._load_inputs(
                campaign_id=campaign_id,
                creative_direction_id=creative_direction_id,
                domain=domain,
                session=session,
                tenant_id=tenant_id,
            )
        )

        return await self._studio.regenerate_field(
            format_id,
            field_name,
            current_content,
            campaign=campaign_dict,
            creative_direction=creative_direction_dict,
            domain_context=domain_context,
            tenant_id=resolved_tenant,
            plan=plan,
        )

    # ─── Internal ───────────────────────────────────────────────────────

    async def _load_inputs(
        self,
        *,
        campaign_id: UUID,
        creative_direction_id: UUID,
        domain: str,
        session: AsyncSession,
        tenant_id: UUID | None,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], UUID | str]:
        """Load campaign plan + creative direction from DB, build domain context.

        Returns ``(campaign_dict, creative_direction_dict, domain_context,
        resolved_tenant_id)``.
        """
        # ─── 1. Load campaign plan ─────────────────────────────────────
        stmt = select(CampaignPlanRecord).where(
            CampaignPlanRecord.id == campaign_id,
        )
        if tenant_id is not None:
            stmt = stmt.where(CampaignPlanRecord.tenant_id == tenant_id)
        res = await session.execute(stmt)
        campaign_record = res.scalar_one_or_none()
        if campaign_record is None:
            from fastapi import HTTPException, status
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"campaign plan {campaign_id} not found",
            )

        campaign_dict: dict[str, Any] = dict(campaign_record.campaign or {})
        campaign_dict.setdefault("id", str(campaign_record.id))
        campaign_dict.setdefault("name", campaign_record.name)
        campaign_dict.setdefault("goal", campaign_record.goal)
        campaign_dict.setdefault("budget", campaign_record.budget)

        # ─── 2. Load creative direction ────────────────────────────────
        cd_stmt = select(CreativeDirectionRecord).where(
            CreativeDirectionRecord.id == creative_direction_id,
        )
        if tenant_id is not None:
            cd_stmt = cd_stmt.where(CreativeDirectionRecord.tenant_id == tenant_id)
        cd_res = await session.execute(cd_stmt)
        cd_record = cd_res.scalar_one_or_none()
        if cd_record is None:
            from fastapi import HTTPException, status
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"creative direction {creative_direction_id} not found",
            )

        creative_direction_dict: dict[str, Any] = dict(cd_record.direction or {})
        creative_direction_dict.setdefault("id", str(cd_record.id))

        # ─── 3. Build domain context from domain pack ──────────────────
        domain_context = self._build_domain_context(domain)

        resolved_tenant = tenant_id or campaign_record.tenant_id
        return campaign_dict, creative_direction_dict, domain_context, resolved_tenant

    @staticmethod
    def _build_domain_context(domain: str) -> dict[str, Any]:
        """Build a domain context dict from the domain pack registry.

        Falls back to a minimal context if the pack is not found.
        """
        reg = get_domain_pack_registry()
        pack = reg.get(domain)
        if pack is None:
            return {"id": domain, "label": domain}

        return {
            "id": pack.id,
            "label": pack.label,
            "customer_type": pack.customer_type,
            "campaign_template": pack.campaign_template,
            "conversation_role": pack.conversation_role,
            "default_goal": pack.default_goal,
        }
