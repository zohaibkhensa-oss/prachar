from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(UTC)


class BrandGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    usps: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    locales: list[str] = Field(default_factory=list)
    tone: dict[str, Any] = Field(default_factory=dict)
    brand_voice: str = ""


class Gender(StrEnum):
    any = "any"
    male = "male"
    female = "female"
    non_binary = "non_binary"


class AudienceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geo: list[str] = Field(default_factory=list)
    age: tuple[int, int] = (18, 65)
    gender: Gender = Gender.any
    interests: list[str] = Field(default_factory=list)
    intents: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    lookalike_seed: str | None = None

    @field_validator("geo")
    @classmethod
    def _validate_geo(cls, v: list[str]) -> list[str]:
        import re

        pat = re.compile(r"^[A-Z]{2}-[A-Z0-9]{1,3}$")
        for code in v:
            if not pat.match(code):
                raise ValueError(f"geo code must match [A-Z]{{2}}-[A-Z0-9]{{1,3}}: {code!r}")
        return v

    @field_validator("age")
    @classmethod
    def _validate_age(cls, v: tuple[int, int]) -> tuple[int, int]:
        lo, hi = v
        if lo < 0 or hi < lo or hi > 130:
            raise ValueError(f"invalid age range: {v}")
        return v


class CreativeType(StrEnum):
    copy = "copy"
    image = "image"
    video = "video"
    thumbnail = "thumbnail"


class PolicyStatus(StrEnum):
    pending = "pending"
    passed = "passed"
    blocked = "blocked"


class CreativeAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: CreativeType
    locale: str
    channel: str
    variant_group: str
    policy_status: PolicyStatus = PolicyStatus.pending
    payload: dict[str, Any] = Field(default_factory=dict)
    s3_key: str | None = None


class MetricEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    entity_type: str
    entity_id: str
    metric: str
    value: float
    ts: datetime = Field(default_factory=_utcnow)

    @field_validator("ts")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("ts must be timezone-aware UTC")
        return v.astimezone(UTC)


class VisibilityScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall: float = Field(ge=0.0, le=100.0)
    organic_rank_index: float = Field(ge=0.0, le=100.0)
    ai_citation_rate: float = Field(ge=0.0, le=100.0)
    social_reach_index: float = Field(ge=0.0, le=100.0)
    paid_efficiency: float = Field(ge=0.0, le=100.0)
    momentum: float = Field(ge=0.0, le=100.0)
    week: date
    breakdown: dict[str, float] = Field(default_factory=dict)

    @classmethod
    def compute(
        cls,
        *,
        organic_rank_index: float,
        ai_citation_rate: float,
        social_reach_index: float,
        paid_efficiency: float,
        momentum: float,
        week: date,
    ) -> "VisibilityScore":
        weights = {
            "organic_rank_index": 0.35,
            "ai_citation_rate": 0.15,
            "social_reach_index": 0.25,
            "paid_efficiency": 0.15,
            "momentum": 0.10,
        }
        subs = {
            "organic_rank_index": organic_rank_index,
            "ai_citation_rate": ai_citation_rate,
            "social_reach_index": social_reach_index,
            "paid_efficiency": paid_efficiency,
            "momentum": momentum,
        }
        overall = sum(subs[k] * weights[k] for k in weights)
        return cls(
            overall=round(overall, 4),
            organic_rank_index=organic_rank_index,
            ai_citation_rate=ai_citation_rate,
            social_reach_index=social_reach_index,
            paid_efficiency=paid_efficiency,
            momentum=momentum,
            week=week,
            breakdown={k: round(v, 4) for k, v in subs.items()},
        )


class PolicyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool = True
    blocked_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TokenSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str | None = None
    expires_at: datetime
    scopes: list[str] = Field(default_factory=list)

    @field_validator("expires_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware UTC")
        return v.astimezone(UTC)


class ChannelProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    handle: str
    display_name: str
    follower_count: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PublishedRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    native_id: str
    url: str | None = None
    published_at: datetime

    @field_validator("published_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("published_at must be timezone-aware UTC")
        return v.astimezone(UTC)


class NativeTargeting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    network: str
    payload: dict[str, Any] = Field(default_factory=dict)
