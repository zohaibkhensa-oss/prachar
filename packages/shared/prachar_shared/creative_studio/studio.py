"""Creative Studio — generation engine.

Takes a campaign + creative_direction and generates all 10 creative formats
(poster, video_script, carousel, story, whatsapp, facebook, linkedin, email,
landing_page, sms) in parallel via the AI gateway.

Usage:
    from prachar_shared.ai_gateway import AIGateway
    from prachar_shared.creative_studio.studio import CreativeStudio

    studio = CreativeStudio(AIGateway())
    package = await studio.generate_all(
        campaign={...},           # campaign plan dict
        creative_direction={...}, # creative direction dict
        domain_context={...},     # domain pack context dict
    )
    package.formats["poster"]     # → {"headline": ..., "cta": ..., ...}

The studio is format-agnostic — it reads specs from ``CreativeFormatRegistry``
and fills each spec's ``prompt_template`` with the campaign, creative_direction,
and domain_context. One format failure does not break the package; the failed
format is marked ``{"error": "..."}``.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from prachar_shared.ai_gateway import AIGateway, Tier
from prachar_shared.ai_gateway.json_utils import extract_json
from prachar_shared.creative_studio import CreativeFormatRegistry
from prachar_shared.creative_studio.base import CreativeFormatSpec

logger = logging.getLogger(__name__)


# ─── Package result ────────────────────────────────────────────────────────


@dataclass
class CreativePackage:
    """The result of generating all 10 creative formats from one campaign.

    ``formats`` maps format id → generated content dict (or ``{"error": ...}``
    if that format failed).
    """

    id: str
    campaign_id: str
    creative_direction_id: str
    formats: dict[str, dict[str, Any]] = field(default_factory=dict)
    generated_at: str = ""
    total_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (for API responses / JSON storage)."""
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "creative_direction_id": self.creative_direction_id,
            "formats": self.formats,
            "generated_at": self.generated_at,
            "total_tokens": self.total_tokens,
        }


# ─── Studio ────────────────────────────────────────────────────────────────


class CreativeStudio:
    """Generate all 10 creative formats from a campaign + creative direction.

    The studio is domain-agnostic and format-agnostic. It reads specs from the
    ``CreativeFormatRegistry``, fills each spec's prompt template, calls the AI
    gateway, and parses the JSON response.
    """

    def __init__(self, gateway: AIGateway) -> None:
        self._gw = gateway
        self._registry = CreativeFormatRegistry()

    # ─── Public API ─────────────────────────────────────────────────────

    async def generate_all(
        self,
        campaign: dict[str, Any],
        creative_direction: dict[str, Any],
        domain_context: dict[str, Any],
        *,
        tenant_id: str | uuid.UUID = "",
        plan: str = "agency",
    ) -> CreativePackage:
        """Generate all 10 creative formats in parallel.

        One format failure does not break the package — the failed format is
        marked ``{"error": "..."}`` and the remaining formats still generate.
        """
        specs = self._registry.all()
        # Run all formats in parallel. Each _generate is wrapped to never raise
        # so that asyncio.gather returns all results (errors become dict values).
        tasks = [
            self._generate_safe(spec, campaign, creative_direction, domain_context,
                                tenant_id=tenant_id, plan=plan)
            for spec in specs
        ]
        results = await asyncio.gather(*tasks)

        formats: dict[str, dict[str, Any]] = {}
        total_tokens = 0
        for spec, result in zip(specs, results):
            formats[spec.id] = result
            total_tokens += result.get("_tokens", 0)
            # Clean up internal bookkeeping keys from the output
            result.pop("_tokens", None)

        campaign_id = str(campaign.get("id") or campaign.get("campaign_id") or "")
        cd_id = str(
            creative_direction.get("id")
            or creative_direction.get("creative_direction_id")
            or ""
        )

        return CreativePackage(
            id=str(uuid.uuid4()),
            campaign_id=campaign_id,
            creative_direction_id=cd_id,
            formats=formats,
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_tokens=total_tokens,
        )

    async def generate_one(
        self,
        format_id: str,
        campaign: dict[str, Any],
        creative_direction: dict[str, Any],
        domain_context: dict[str, Any],
        *,
        tenant_id: str | uuid.UUID = "",
        plan: str = "agency",
    ) -> dict[str, Any]:
        """Generate a single creative format by id.

        Raises ``KeyError`` if the format id is unknown.
        """
        spec = self._registry.get_required(format_id)
        result = await self._generate_safe(
            spec, campaign, creative_direction, domain_context,
            tenant_id=tenant_id, plan=plan,
        )
        result.pop("_tokens", None)
        return result

    async def regenerate_field(
        self,
        format_id: str,
        field_name: str,
        current_content: dict[str, Any],
        campaign: dict[str, Any],
        creative_direction: dict[str, Any],
        domain_context: dict[str, Any],
        *,
        tenant_id: str | uuid.UUID = "",
        plan: str = "agency",
    ) -> dict[str, Any]:
        """Regenerate a single field of an already-generated creative format.

        Builds a focused prompt that asks the AI to rewrite ONLY ``field_name``
        while keeping the rest of the creative consistent. Uses ``Tier.small``
        (it's a small task, not a full generation).

        Returns ``{"field_name": field_name, "new_value": <regenerated value>}``.

        Raises ``KeyError`` if ``format_id`` is unknown.
        """
        spec = self._registry.get_required(format_id)

        # Build a dynamic output schema containing only the target field.
        field_schema = spec.output_schema.get("properties", {}).get(field_name)
        if field_schema is None:
            raise KeyError(
                f"Field {field_name!r} is not a known field of format {format_id!r}. "
                f"Available: {list(spec.output_schema.get('properties', {}))}"
            )

        output_schema = {
            "type": "object",
            "properties": {field_name: field_schema},
            "required": [field_name],
        }

        prompt = self._build_regenerate_prompt(
            spec, field_name, current_content,
            campaign, creative_direction, domain_context,
        )

        comp = await asyncio.to_thread(
            self._gw.complete,
            prompt,
            tier=Tier.small,
            schema=output_schema,
            task=f"creative_studio_regenerate_{format_id}_{field_name}",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=800,
            temperature=0.5,
            prompt_version=f"creative_studio_regenerate_v1.0",
        )

        # Parse the response — expect {field_name: new_value}
        content: dict[str, Any] | None = None
        if comp.json_value is not None and isinstance(comp.json_value, dict):
            content = comp.json_value
        else:
            extracted = extract_json(comp.text)
            if extracted is not None and isinstance(extracted, dict):
                content = extracted

        if content is None or field_name not in content:
            # Fallback: return the original value unchanged
            return {"field_name": field_name, "new_value": current_content.get(field_name)}

        return {"field_name": field_name, "new_value": content[field_name]}

    # ─── Internal ───────────────────────────────────────────────────────

    @staticmethod
    def _build_regenerate_prompt(
        spec: CreativeFormatSpec,
        field_name: str,
        current_content: dict[str, Any],
        campaign: dict[str, Any],
        creative_direction: dict[str, Any],
        domain_context: dict[str, Any],
    ) -> str:
        """Build a focused prompt to regenerate a single field."""
        return (
            f"You are a senior creative director. A {spec.label} creative has already "
            f"been generated for a campaign. The user wants to regenerate ONLY the "
            f"'{field_name}' field — keep everything else exactly as-is.\n\n"
            f"Campaign:\n{json.dumps(campaign, ensure_ascii=False, default=str)}\n\n"
            f"Creative Direction:\n{json.dumps(creative_direction, ensure_ascii=False, default=str)}\n\n"
            f"Domain Context:\n{json.dumps(domain_context, ensure_ascii=False, default=str)}\n\n"
            f"Current full creative content:\n{json.dumps(current_content, ensure_ascii=False, default=str)}\n\n"
            f"TASK: Regenerate ONLY the '{field_name}' field. Make it fresh, compelling, "
            f"and consistent with the rest of the creative and the campaign's tone. "
            f"Do NOT change any other field.\n\n"
            f"Return JSON only, no markdown fences, with exactly this shape:\n"
            f'{{"{field_name}": <new value>}}'
        )

    async def _generate_safe(
        self,
        spec: CreativeFormatSpec,
        campaign: dict[str, Any],
        creative_direction: dict[str, Any],
        domain_context: dict[str, Any],
        *,
        tenant_id: str | uuid.UUID,
        plan: str,
    ) -> dict[str, Any]:
        """Wrapper that never raises — converts exceptions to error dicts."""
        try:
            return await self._generate(
                spec, campaign, creative_direction, domain_context,
                tenant_id=tenant_id, plan=plan,
            )
        except Exception as exc:
            logger.warning("Creative format %s failed: %s", spec.id, exc)
            return {"error": str(exc)}

    async def _generate(
        self,
        spec: CreativeFormatSpec,
        campaign: dict[str, Any],
        creative_direction: dict[str, Any],
        domain_context: dict[str, Any],
        *,
        tenant_id: str | uuid.UUID,
        plan: str,
    ) -> dict[str, Any]:
        """Fill the spec's prompt template, call the gateway, parse JSON.

        Returns the parsed content dict plus an internal ``_tokens`` key for
        token accounting (stripped before returning to callers).
        """
        prompt = spec.prompt_template.format(
            campaign=json.dumps(campaign, ensure_ascii=False, default=str),
            creative_direction=json.dumps(creative_direction, ensure_ascii=False, default=str),
            domain_context=json.dumps(domain_context, ensure_ascii=False, default=str),
        )

        tier = Tier.large if spec.tier in ("pro", "enterprise") else Tier.small

        # The gateway's complete() is synchronous (may do blocking I/O).
        # Run it in a thread so asyncio.gather parallelises across formats.
        comp = await asyncio.to_thread(
            self._gw.complete,
            prompt,
            tier=tier,
            schema=spec.output_schema,
            task=f"creative_studio_{spec.id}",
            tenant_id=tenant_id,
            plan=plan,
            max_tokens=spec.max_tokens,
            temperature=0.4,
            prompt_version=f"creative_studio_{spec.id}_v1.0",
        )

        # Prefer pre-parsed json_value from the gateway, fall back to extract_json
        content: dict[str, Any] | None = None
        if comp.json_value is not None and isinstance(comp.json_value, dict):
            content = comp.json_value
        else:
            extracted = extract_json(comp.text)
            if extracted is not None and isinstance(extracted, dict):
                content = extracted

        if content is None:
            content = {"error": f"failed to parse JSON for {spec.id}", "raw": comp.text[:500]}

        content["_tokens"] = comp.tokens_used
        return content
