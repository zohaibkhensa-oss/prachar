"""Creative Studio API router (P2.3).

Endpoints:
  POST /creative-studio/generate          — generate all 10 formats
  POST /creative-studio/generate/{format_id} — generate one format
  POST /creative-studio/regenerate-field  — regenerate a single field of a format
  GET  /creative-studio/{package_id}      — retrieve a saved package (stub)

The generate endpoints return the package / format inline. Package persistence
(a DB table) is a future part — for now GET returns 404.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..deps import CurrentUser, SessionDep
from ..infrastructure.creative_studio_engine import CreativeStudioEngine

router = APIRouter(prefix="/creative-studio", tags=["creative-studio"])


class GenerateIn(BaseModel):
    """Request body for both generate endpoints."""

    campaign_id: str = Field(min_length=1)
    creative_direction_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)


class RegenerateFieldIn(BaseModel):
    """Request body for the regenerate-field endpoint."""

    campaign_id: str = Field(min_length=1)
    creative_direction_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    format_id: str = Field(min_length=1)
    field_name: str = Field(min_length=1)
    current_content: dict[str, Any] = Field(default_factory=dict)


@router.post("/generate")
async def generate_package(
    body: GenerateIn,
    user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Generate all 10 creative formats for a campaign + creative direction."""
    engine = CreativeStudioEngine()
    return await engine.generate_package(
        campaign_id=body.campaign_id,
        creative_direction_id=body.creative_direction_id,
        domain=body.domain,
        session=session,
        tenant_id=user.tenant_id,
    )


@router.post("/generate/{format_id}")
async def generate_one_format(
    format_id: str,
    body: GenerateIn,
    user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Generate a single creative format by id."""
    engine = CreativeStudioEngine()
    try:
        return await engine.generate_one(
            format_id,
            campaign_id=body.campaign_id,
            creative_direction_id=body.creative_direction_id,
            domain=body.domain,
            session=session,
            tenant_id=user.tenant_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"unknown creative format: {format_id!r}",
        ) from exc


@router.post("/regenerate-field")
async def regenerate_field(
    body: RegenerateFieldIn,
    user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Regenerate a single field of an already-generated creative format.

    Returns ``{"field_name": ..., "new_value": ...}``. Uses ``Tier.small``
    (it's a small task, not a full generation).
    """
    engine = CreativeStudioEngine()
    try:
        return await engine.regenerate_field(
            format_id=body.format_id,
            field_name=body.field_name,
            current_content=body.current_content,
            campaign_id=body.campaign_id,
            creative_direction_id=body.creative_direction_id,
            domain=body.domain,
            session=session,
            tenant_id=user.tenant_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            str(exc),
        ) from exc


@router.get("/{package_id}")
async def get_package(
    package_id: str,
    user: CurrentUser,  # noqa: ARG001 — auth required even though unused
    session: SessionDep,  # noqa: ARG001 — reserved for future DB lookup
) -> dict:
    """Retrieve a saved creative package by id.

    Package persistence (a DB table) is coming in a future part. For now we
    return 404 — the generate endpoints return the package inline.
    """
    raise HTTPException(
        status.HTTP_404_NOT_FOUND,
        "Package persistence coming in a future part. "
        "Use POST /creative-studio/generate to produce a package inline.",
    )
