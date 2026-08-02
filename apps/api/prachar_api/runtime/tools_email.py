"""Phase L5 — Email Campaign Manager tool.

World-class email: sequence design, subject lines, body copy, segmentation.
Emits email_sequence artefact.
"""
from __future__ import annotations

import logging
from typing import Any

from .registry import (
    SideEffects,
    ToolCategory,
    ToolManifest,
    register_tool,
)
from .memory_categories import MemoryCategory
from .context import AIContext
from .artefacts import email_sequence

log = logging.getLogger("prachar.runtime.tools.email")


@register_tool(ToolManifest(
    name="email.sequence",
    display_name="Email Sequence Designer",
    description="Designs a complete email sequence (welcome, nurture, re-engagement, promotional) with subject lines, body copy, timing, and segmentation. Includes A/B subject line variants.",
    category=ToolCategory.EMAIL,
    input_schema={"sequence_type": "string", "product": "string", "audience": "string", "goal": "string"},
    output_schema={"sequence": "object"},
    estimated_cost_usd=0.10,
    estimated_time_ms=12000,
    estimated_tokens=2500,
    estimated_latency_ms=9000,
    quality_score=0.90,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.WRITES,
    memory_categories=[MemoryCategory.BRAND, MemoryCategory.CAMPAIGN],
))
async def email_sequence_design(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Design an email sequence."""
    from prachar_shared.ai_gateway import AIGateway, Tier
    from prachar_shared.ai_gateway.json_utils import extract_json

    gateway = AIGateway()
    seq_type = input.get("sequence_type", "welcome")
    product = input.get("product", "")
    audience = input.get("audience", "")
    goal = input.get("goal", "convert")

    prompt = f"""You are a world-class email marketing strategist and copywriter.
Design a {seq_type} email sequence for:

Product/Service: {product}
Audience: {audience}
Goal: {goal}

SEQUENCE DESIGN REQUIREMENTS:

1. STEPS (3-7 emails depending on sequence type):
   For each email provide:
   - step_number: 1, 2, 3...
   - name: descriptive name (e.g. "Welcome", "Value Drop", "Soft Pitch")
   - send_delay: when to send (e.g. "Day 0", "Day 2", "Day 5")
   - subject_line: compelling subject ≤50 chars
   - subject_variants: 2 A/B alternatives
   - preview_text: the preheader text (40-80 chars)
   - body: full email body in markdown (150-300 words)
   - cta: primary call-to-action
   - goal: what this email should achieve
   - psychology: the psychological principle used (e.g. reciprocity, scarcity, social proof)

2. SEGMENTATION:
   - target_segment: who receives this sequence
   - entry_trigger: what action starts the sequence
   - exit_trigger: what action stops the sequence

3. OPTIMISATION:
   - best_send_time: optimal day and time
   - personalisation_tokens: list of merge fields to use
   - success_metrics: KPIs to track (open rate, CTR, conversion)

QUALITY REQUIREMENTS:
- Subject lines must be compelling but not clickbait
- Each email must provide value before asking for action
- Sequence must have a clear narrative arc
- Body copy must be scannable (short paragraphs, bullet points)
- CTAs must be specific and singular (one per email)

Return JSON:
{{
  "steps": [...],
  "target_segment": "...",
  "entry_trigger": "...",
  "exit_trigger": "...",
  "best_send_time": "...",
  "personalisation_tokens": [...],
  "success_metrics": [...]
}}"""

    response = await gateway.async_complete(
        prompt=prompt, tier=Tier.large,
        tenant_id=str(ctx.tenant_id), max_tokens=2500,
    )
    result = extract_json(response.content) or {}
    steps = result.get("steps", [])

    return {
        "sequence": result,
        "artefacts": [email_sequence(
            steps=steps,
            total_duration=f"{len(steps)} emails over {sum(int(s.get('send_delay', '0').replace('Day ', '').split()[0]) for s in steps if 'send_delay' in s)} days",
            target_segment=result.get("target_segment", ""),
        ).to_dict()],
    }


@register_tool(ToolManifest(
    name="email.subject",
    display_name="Subject Line Optimiser",
    description="Generates 10 high-converting subject lines with A/B variants, predicted open rates, and psychology notes. Optimises for curiosity, urgency, and relevance.",
    category=ToolCategory.EMAIL,
    input_schema={"topic": "string", "audience": "string", "tone": "string"},
    output_schema={"subject_lines": "array"},
    estimated_cost_usd=0.04,
    estimated_time_ms=5000,
    estimated_tokens=800,
    estimated_latency_ms=4000,
    quality_score=0.86,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.BRAND],
))
async def email_subject(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Generate subject lines."""
    from prachar_shared.ai_gateway import AIGateway, Tier
    from prachar_shared.ai_gateway.json_utils import extract_json

    gateway = AIGateway()
    topic = input.get("topic", "")
    audience = input.get("audience", "")
    tone = input.get("tone", "friendly")

    prompt = f"""You are a world-class email subject line copywriter.
Generate 10 subject lines for:
Topic: {topic}
Audience: {audience}
Tone: {tone}

For each subject line provide:
- subject: the subject line (≤50 chars)
- psychology: the principle used (curiosity, urgency, benefit, personalisation, etc.)
- predicted_open_rate: estimated open rate % (30-60% range)
- best_for: "mobile" | "desktop" | "both"

Include a mix of:
- 3 curiosity-driven
- 3 benefit-driven
- 2 urgency-driven
- 2 personalisation-driven

Return JSON: {{"subject_lines": [...]}}"""

    response = await gateway.async_complete(
        prompt=prompt, tier=Tier.MEDIUM,
        tenant_id=str(ctx.tenant_id), max_tokens=800,
    )
    result = extract_json(response.content) or {}

    return {"subject_lines": result.get("subject_lines", [])}
