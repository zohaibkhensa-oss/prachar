from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models.enums import (
    CampaignObjective,
    CampaignStatus,
    Channel,
    Plan,
    Role,
)


def _cfg(**kw: Any) -> ConfigDict:
    return ConfigDict(from_attributes=True, **kw)


# ─── auth ────────────────────────────────────────────────────────────────────
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    tenant_name: str = Field(min_length=1, max_length=120)
    plan: Plan = Plan.starter


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserOut"


class RefreshIn(BaseModel):
    refresh_token: str


class VerifyEmailIn(BaseModel):
    token: str


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class ResendVerificationIn(BaseModel):
    email: EmailStr


# ─── user/tenant ─────────────────────────────────────────────────────────────
class UserOut(BaseModel):
    model_config = _cfg()
    id: uuid.UUID
    email: EmailStr
    role: Role
    tenant_id: uuid.UUID


class TenantOut(BaseModel):
    model_config = _cfg()
    id: uuid.UUID
    name: str
    plan: Plan
    region: str | None


# ─── brand ───────────────────────────────────────────────────────────────────
class BrandIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    website: str | None = None
    category: str | None = None
    customer_type: str = Field("business", pattern="^(business|creator)$")
    locales: list[str] | None = None
    tone: dict[str, Any] | None = None


class BrandOut(BaseModel):
    model_config = _cfg()
    id: uuid.UUID
    name: str
    website: str | None
    category: str | None
    customer_type: str = "business"
    locales: list[str] | None
    tone: dict[str, Any] | None
    visibility_score: float | None
    created_at: datetime


class AuditRequestIn(BaseModel):
    input: str = Field(min_length=3, max_length=2048, description="url or @handle")


# ─── connection ──────────────────────────────────────────────────────────────
class ConnectionOut(BaseModel):
    model_config = _cfg()
    id: uuid.UUID
    brand_id: uuid.UUID
    channel: str
    status: str
    expires_at: datetime | None


# ─── campaign ────────────────────────────────────────────────────────────────
class CampaignIn(BaseModel):
    brand_id: uuid.UUID
    network: str
    objective: CampaignObjective
    audience_spec: dict[str, Any]
    budget_daily: float = Field(gt=0)
    currency: str = "INR"
    guardrails: dict[str, Any] | None = None
    dry_run: bool = True


class CampaignOut(BaseModel):
    model_config = _cfg()
    id: uuid.UUID
    brand_id: uuid.UUID
    network: str
    objective: CampaignObjective
    budget_daily: float
    currency: str
    status: CampaignStatus
    dry_run: bool
    guardrails: dict[str, Any] | None


# ─── visibility score ────────────────────────────────────────────────────────
class VisibilityScoreOut(BaseModel):
    overall: float
    organic_rank_index: float
    ai_citation_rate: float
    social_reach_index: float
    paid_efficiency: float
    momentum: float
    week: str
    breakdown: dict[str, float]


# ─── audit funnel ────────────────────────────────────────────────────────────
class AuditJobOut(BaseModel):
    model_config = _cfg()
    id: uuid.UUID
    status: str
    score_snapshot: dict[str, Any] | None
    findings: dict[str, Any] | None
    error: str | None
    created_at: datetime
    completed_at: datetime | None


TokenOut.model_rebuild()
