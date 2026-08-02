"""Base class for all Agency Council Directors.

Every Director inherits from Director and returns a DirectorOpinion.
Directors are independent — no Director may call another Director.

Architecture:
- Directors depend only on the AI Gateway and the campaign brief.
- Directors do NOT depend on each other.
- Directors do NOT depend on the Consensus Engine.
- Directors do NOT import infrastructure (no SQLAlchemy, no FastAPI).

The Director contract is enforced: every opinion must have all 9 fields.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from prachar_shared.ai_gateway import AIGateway, Completion, Tier

from .models import DirectorOpinion

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Director:
    """Base class for all Agency Council Directors.

    Each Director:
    1. Receives a campaign brief (dict with business/audience/strategy/etc.)
    2. Builds a focused prompt from its area of expertise
    3. Calls the AI Gateway with a strict JSON schema
    4. Returns a DirectorOpinion with all 9 contract fields

    Subclasses must implement:
    - DIRECTOR_NAME: str (e.g., "chief_strategy_officer")
    - DIRECTOR_ROLE: str (e.g., "Chief Strategy Officer")
    - RESPONSIBILITY: str (one-line description)
    - _build_prompt(brief, context) -> str
    - _build_schema() -> dict
    """

    # Subclass overrides
    DIRECTOR_NAME: ClassVar[str] = "base_director"
    DIRECTOR_ROLE: ClassVar[str] = "Base Director"
    RESPONSIBILITY: ClassVar[str] = ""
    ENGINE_VERSION: ClassVar[str] = "1.0.0"
    PROMPT_VERSION: ClassVar[str] = "1.0.0"
    SCHEMA_VERSION: ClassVar[str] = "1.0.0"
    TIER: ClassVar[Tier] = Tier.large
    MAX_TOKENS: ClassVar[int] = 2048
    TEMPERATURE: ClassVar[float] = 0.4

    def __init__(self, gateway: AIGateway | None = None) -> None:
        self._gateway = gateway

    @property
    def gateway(self) -> AIGateway:
        if self._gateway is None:
            self._gateway = AIGateway()
        return self._gateway

    def review(
        self,
        *,
        tenant_id: uuid.UUID,
        plan: str = "agency",
        campaign_brief: dict[str, Any],
        round_number: int = 1,
        previous_opinions: list[dict[str, Any]] | None = None,
        additional_context: str = "",
    ) -> DirectorOpinion:
        """Review a campaign and return a DirectorOpinion.

        Args:
            tenant_id: For budget tracking.
            plan: Tenant's plan tier.
            campaign_brief: The campaign being reviewed (business, audience,
                strategy, creative, media, budget, objective, etc.).
            round_number: Which review round (1, 2, or 3). Later rounds get
                previous opinions for context (but directors still work
                independently — they see the *summary* of disagreements,
                not other directors' full reasoning).
            previous_opinions: Opinions from the previous round (for rounds 2+).
                Only the disagreements and risks are shared, not full reasoning.
            additional_context: Extra context (e.g., business memory).

        Returns:
            DirectorOpinion with all 9 contract fields populated.
        """
        t0 = time.monotonic()
        prompt = self._build_prompt(
            campaign_brief=campaign_brief,
            round_number=round_number,
            previous_opinions=previous_opinions or [],
            additional_context=additional_context,
        )
        schema = self._build_schema()

        try:
            comp = self.gateway.complete(
                prompt=prompt,
                tier=self.TIER,
                schema=schema,
                task=self.DIRECTOR_NAME,
                tenant_id=tenant_id,
                plan=plan,
                max_tokens=self.MAX_TOKENS,
                temperature=self.TEMPERATURE,
                prompt_version=f"{self.DIRECTOR_NAME}_v{self.PROMPT_VERSION}",
            )
        except Exception as exc:
            logger.error("director %s failed: %s", self.DIRECTOR_NAME, exc)
            return DirectorOpinion(
                director=self.DIRECTOR_NAME,
                role=self.DIRECTOR_ROLE,
                opinion=f"Director failed to review: {exc}",
                confidence=0.0,
                reasoning="Director invocation failed",
                priority="high",
                approval=False,
                latency_ms=round((time.monotonic() - t0) * 1000, 2),
                round_number=round_number,
            )

        opinion = self._parse_opinion(comp)
        opinion.director = self.DIRECTOR_NAME
        opinion.role = self.DIRECTOR_ROLE
        opinion.latency_ms = round((time.monotonic() - t0) * 1000, 2)
        opinion.tokens_used = comp.tokens_used
        opinion.cost_usd = comp.cost_usd
        opinion.model = comp.model
        opinion.provider = comp.provider
        opinion.round_number = round_number
        return opinion

    # ─── Subclass hooks ─────────────────────────────────────────────────────

    def _build_prompt(
        self,
        *,
        campaign_brief: dict[str, Any],
        round_number: int,
        previous_opinions: list[dict[str, Any]],
        additional_context: str,
    ) -> str:
        raise NotImplementedError(f"{self.DIRECTOR_NAME} must implement _build_prompt")

    def _build_schema(self) -> dict[str, Any]:
        """JSON schema for the director's opinion. Subclasses can override."""
        return {
            "type": "object",
            "properties": {
                "opinion": {"type": "string", "description": "Your main opinion (1-3 sentences)"},
                "reasoning": {"type": "string", "description": "Detailed reasoning"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "risks": {"type": "array", "items": {"type": "string"}},
                "alternatives": {"type": "array", "items": {"type": "string"}},
                "recommendations": {"type": "array", "items": {"type": "string"}},
                "evidence": {"type": "array", "items": {"type": "string"},
                             "description": "Internal evidence cited (from the brief)"},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                "approval": {"type": "boolean"},
                "evidence_cited": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Specific sections quoted from the campaign brief",
                },
                "alternatives_considered": {
                    "type": "array", "items": {"type": "string"},
                    "description": "At least 2 alternative approaches evaluated before recommending",
                },
            },
            "required": ["opinion", "reasoning", "confidence", "risks",
                         "alternatives", "recommendations", "evidence",
                         "priority", "approval"],
            "additionalProperties": False,
        }

    def _parse_opinion(self, comp: Completion) -> DirectorOpinion:
        """Parse the AI completion into a DirectorOpinion."""
        data = comp.json_value if comp.json_value else {}
        return DirectorOpinion(
            opinion=data.get("opinion", ""),
            reasoning=data.get("reasoning", ""),
            confidence=float(data.get("confidence", 0.5)),
            risks=list(data.get("risks", [])),
            alternatives=list(data.get("alternatives", [])),
            recommendations=list(data.get("recommendations", [])),
            evidence=list(data.get("evidence", [])),
            priority=data.get("priority", "medium"),
            approval=bool(data.get("approval", False)),
            evidence_cited=list(data.get("evidence_cited", [])),
            alternatives_considered=list(data.get("alternatives_considered", [])),
        )

    # ─── Helpers for subclasses ─────────────────────────────────────────────

    def _format_brief(self, brief: dict[str, Any]) -> str:
        """Format a campaign brief into a readable string for the prompt."""
        parts: list[str] = []
        for key, value in brief.items():
            if isinstance(value, dict):
                parts.append(f"\n{key.upper()}:")
                for k, v in value.items():
                    parts.append(f"  {k}: {v}")
            elif isinstance(value, list):
                parts.append(f"\n{key.upper()}: {', '.join(str(v) for v in value)}")
            elif value:
                parts.append(f"{key}: {value}")
        return "\n".join(parts)

    def _format_previous_disagreements(
        self, previous_opinions: list[dict[str, Any]]
    ) -> str:
        """Format the disagreements/risks from previous round for round 2+ directors.

        Phase I3: Directors who disagreed in round 1 now see the full opinions
        (opinion + reasoning + confidence + approval) of the directors who
        disagreed with them, so they can explicitly revise their position.
        Directors who agreed see only the risks raised — they stay independent
        but can still converge.
        """
        if not previous_opinions:
            return ""
        parts: list[str] = ["Previous round opinions — review and REVISE your position:"]
        for op in previous_opinions:
            role = op.get("role", op.get("director", "unknown"))
            approval = op.get("approval")
            confidence = op.get("confidence", 0.5)
            opinion_text = op.get("opinion", "")
            risks = op.get("risks", [])
            stance = "APPROVES" if approval else "REJECTS"
            parts.append(
                f"\n{role} ({stance}, confidence={confidence}):\n"
                f"  Opinion: {opinion_text}"
            )
            if risks:
                parts.append(f"  Risks raised:")
                for r in risks[:3]:  # Top 3 risks per director
                    parts.append(f"    - {r}")
        parts.append(
            "\nINSTRUCTION: If you previously disagreed, you MUST explicitly "
            "state whether you maintain or revise your position after seeing "
            "the above opinions, and WHY."
        )
        return "\n".join(parts)

    def _safety_preamble(self) -> str:
        """AI safety preamble — every director must avoid hallucinations."""
        return (
            "You are a senior advertising agency executive. "
            "You are reviewing a campaign for a client.\n\n"
            "SAFETY RULES:\n"
            "- Only cite evidence from the campaign brief provided.\n"
            "- Never invent features, integrations, or capabilities.\n"
            "- Never fabricate statistics, benchmarks, or case studies.\n"
            "- If you lack information, say so explicitly.\n"
            "- Be honest about risks and weaknesses.\n"
            "- Do not use engagement-bait or make guaranteed-results claims.\n"
            "- Strip any medical/financial guarantees from recommendations.\n"
        )
