"""Base classes for the Marketing Intelligence Engine.

Every intelligence engine inherits from IntelligenceEngine and returns
an EngineResult containing structured recommendations with confidence,
rationale, risks, and expected outcomes.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from prachar_shared.ai_gateway import AIGateway, Completion, Tier

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    """Current UTC time as ISO 8601 string (e.g., '2026-07-25T12:00:00Z')."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Recommendation:
    """A single AI-generated recommendation with full reasoning chain.

    Every recommendation must include:
    - confidence: 0.0-1.0
    - business_rationale: why this makes sense for the business
    - marketing_rationale: why this makes sense for marketing
    - alternatives: other options considered
    - risks: what could go wrong
    - expected_outcome: what we expect to happen
    """

    title: str
    description: str
    confidence: float = 0.5
    business_rationale: str = ""
    marketing_rationale: str = ""
    alternatives: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    expected_outcome: str = ""
    evidence: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "confidence": self.confidence,
            "business_rationale": self.business_rationale,
            "marketing_rationale": self.marketing_rationale,
            "alternatives": self.alternatives,
            "risks": self.risks,
            "expected_outcome": self.expected_outcome,
            "evidence": self.evidence,
            "sources": self.sources,
        }


@dataclass
class EngineOutput:
    """The structured output of an intelligence engine.

    Contains the AI's reasoning, the parsed result, and full versioning +
    metadata about the AI call. Every output is versioned so old persisted
    results can be detected and migrated.

    Versioning:
    - schema_version: Version of the JSON schema the result conforms to.
    - engine_version: Version of the engine class that produced this output.
    - prompt_version: Version of the prompt template used.
    - model_version: The specific model + provider that generated the result.
    """

    result: dict[str, Any]
    confidence: float = 0.5
    reasoning: str = ""
    recommendations: list[Recommendation] = field(default_factory=list)
    # Versioning (Phase 2: Architecture Stabilisation)
    schema_version: str = ""
    engine_version: str = ""
    prompt_version: str = ""
    model_version: str = ""  # "provider:model" e.g. "groq:llama-3.3-70b"
    # AI metadata
    model: str = ""
    provider: str = ""
    tokens_used: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    cached: bool = False
    request_id: str = ""
    # Provenance
    generated_by: str = ""  # Engine name that produced this
    created_at: str = ""  # ISO timestamp

    def to_dict(self) -> dict[str, Any]:
        return {
            "result": self.result,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "schema_version": self.schema_version,
            "engine_version": self.engine_version,
            "prompt_version": self.prompt_version,
            "model_version": self.model_version,
            "model": self.model,
            "provider": self.provider,
            "tokens_used": self.tokens_used,
            "cost_usd": self.cost_usd,
            "latency_ms": self.latency_ms,
            "cached": self.cached,
            "request_id": self.request_id,
            "generated_by": self.generated_by,
            "created_at": self.created_at,
        }


class EngineResult(EngineOutput):
    """Alias for EngineOutput — the result of an engine invocation."""

    pass


class IntelligenceEngine:
    """Base class for all marketing intelligence engines.

    Each engine:
    1. Builds a structured prompt from inputs
    2. Calls the AI Gateway with a JSON schema
    3. Parses the response into typed recommendations
    4. Returns an EngineOutput with full metadata

    Subclasses must implement:
    - _build_prompt(**kwargs) -> str
    - _build_schema() -> dict
    - _parse_result(comp: Completion) -> EngineOutput
    - _engine_name() -> str  (for task labeling)
    - _prompt_version() -> str
    """

    # Subclasses override these
    ENGINE_NAME: str = "base"
    ENGINE_VERSION: str = "1.0.0"  # Version of the engine class itself
    PROMPT_VERSION: str = "1.0.0"  # Version of the prompt template
    SCHEMA_VERSION: str = "1.0.0"  # Version of the output JSON schema
    TIER: Tier = Tier.large
    MAX_TOKENS: int = 2048
    TEMPERATURE: float = 0.3

    def __init__(self, gateway: AIGateway | None = None) -> None:
        self._gateway = gateway

    @property
    def gateway(self) -> AIGateway:
        if self._gateway is None:
            self._gateway = AIGateway()
        return self._gateway

    def run(self, *, tenant_id: uuid.UUID, plan: str = "agency", **kwargs: Any) -> EngineOutput:
        """Execute the engine and return structured output.

        Args:
            tenant_id: The workspace/tenant ID for budget tracking.
            plan: The tenant's plan for budget allocation.
            **kwargs: Engine-specific inputs (e.g., business_name, website, goal).

        Returns:
            EngineOutput with the AI's structured analysis.
        """
        t0 = time.monotonic()
        prompt = self._build_prompt(**kwargs)
        schema = self._build_schema()

        try:
            comp = self.gateway.complete(
                prompt=prompt,
                tier=self.TIER,
                schema=schema,
                task=self.ENGINE_NAME,
                tenant_id=tenant_id,
                plan=plan,
                max_tokens=self.MAX_TOKENS,
                temperature=self.TEMPERATURE,
                prompt_version=f"{self.ENGINE_NAME}_v{self.PROMPT_VERSION}",
            )
        except Exception as exc:
            logger.error("engine %s failed: %s", self.ENGINE_NAME, exc)
            return EngineOutput(
                result={},
                confidence=0.0,
                reasoning=f"Engine failed: {exc}",
                model="error",
                provider="error",
                latency_ms=round((time.monotonic() - t0) * 1000, 2),
                schema_version=self.SCHEMA_VERSION,
                engine_version=self.ENGINE_VERSION,
                prompt_version=f"{self.ENGINE_NAME}_v{self.PROMPT_VERSION}",
                generated_by=self.ENGINE_NAME,
                created_at=_utcnow_iso(),
            )

        output = self._parse_result(comp)
        output.latency_ms = round((time.monotonic() - t0) * 1000, 2)
        output.model = comp.model
        output.provider = comp.provider
        output.tokens_used = comp.tokens_used
        output.cost_usd = comp.cost_usd
        output.cached = comp.cached
        # Versioning (Phase 2)
        output.schema_version = self.SCHEMA_VERSION
        output.engine_version = self.ENGINE_VERSION
        output.prompt_version = f"{self.ENGINE_NAME}_v{self.PROMPT_VERSION}"
        output.model_version = f"{comp.provider}:{comp.model}" if comp.provider and comp.model else ""
        output.generated_by = self.ENGINE_NAME
        output.created_at = _utcnow_iso()
        output.request_id = comp.request_id
        return output

    # ─── Subclass hooks ─────────────────────────────────────────────────────

    def _build_prompt(self, **kwargs: Any) -> str:
        raise NotImplementedError

    def _build_schema(self) -> dict[str, Any]:
        raise NotImplementedError

    def _parse_result(self, comp: Completion) -> EngineOutput:
        """Parse the AI completion into an EngineOutput.

        Default implementation uses the json_value from the completion
        and extracts recommendations.
        """
        result = comp.json_value or {}
        recommendations = self._extract_recommendations(result)
        confidence = float(result.get("confidence", comp.confidence or 0.5))
        reasoning = result.get("reasoning", "")

        return EngineOutput(
            result=result,
            confidence=confidence,
            reasoning=reasoning,
            recommendations=recommendations,
        )

    def _extract_recommendations(self, result: dict[str, Any]) -> list[Recommendation]:
        """Extract recommendations from the AI result."""
        recs: list[Recommendation] = []
        raw_recs = result.get("recommendations", [])
        if not isinstance(raw_recs, list):
            return recs
        for raw in raw_recs:
            if not isinstance(raw, dict):
                continue
            recs.append(
                Recommendation(
                    title=raw.get("title", ""),
                    description=raw.get("description", ""),
                    confidence=float(raw.get("confidence", 0.5)),
                    business_rationale=raw.get("business_rationale", ""),
                    marketing_rationale=raw.get("marketing_rationale", ""),
                    alternatives=raw.get("alternatives", []),
                    risks=raw.get("risks", []),
                    expected_outcome=raw.get("expected_outcome", ""),
                    evidence=raw.get("evidence", []),
                    sources=raw.get("sources", []),
                )
            )
        return recs

    @staticmethod
    def _format_input_summary(**kwargs: Any) -> str:
        """Format input kwargs into a readable summary for the prompt."""
        parts: list[str] = []
        for key, val in kwargs.items():
            if val is None or val == "":
                continue
            if isinstance(val, dict):
                parts.append(f"{key}: {val}")
            elif isinstance(val, list):
                parts.append(f"{key}: {', '.join(str(v) for v in val)}")
            else:
                parts.append(f"{key}: {val}")
        return "\n".join(parts)
