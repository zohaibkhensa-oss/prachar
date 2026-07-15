from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    impact: int = Field(ge=1, le=5)
    effort: int = Field(ge=1, le=5)
    category: str
    fix_description: str
    gated: bool = False


class AuditFindings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[Finding] = Field(default_factory=list)
