from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Action(StrEnum):
    rewrite = "rewrite"
    new_content = "new_content"
    budget_shift = "budget_shift"
    schedule_change = "schedule_change"


class DiagnosisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    finding: str
    evidence_metric: str
    action: Action
    target_entity_id: str
    priority: int = Field(ge=1, le=5)
