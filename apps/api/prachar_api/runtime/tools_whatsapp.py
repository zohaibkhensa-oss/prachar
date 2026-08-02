"""Phase L6 — WhatsApp Campaign Manager tool.

World-class WhatsApp: broadcast templates, status strategy, contact segmentation.
Emits whatsapp_campaign artefact.
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
from .artefacts import whatsapp_campaign

log = logging.getLogger("prachar.runtime.tools.whatsapp")


@register_tool(ToolManifest(
    name="whatsapp.campaign",
    display_name="WhatsApp Campaign Designer",
    description="Designs a WhatsApp campaign with broadcast templates, status strategy, contact segmentation, and compliance notes. Optimised for WhatsApp's conversational format and 24-hour rule.",
    category=ToolCategory.WHATSAPP,
    input_schema={"product": "string", "audience": "string", "goal": "string", "budget": "string"},
    output_schema={"campaign": "object"},
    estimated_cost_usd=0.08,
    estimated_time_ms=10000,
    estimated_tokens=2000,
    estimated_latency_ms=8000,
    quality_score=0.88,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.WRITES,
    memory_categories=[MemoryCategory.BRAND, MemoryCategory.CAMPAIGN],
))
async def whatsapp_campaign_design(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Design a WhatsApp campaign."""
    from prachar_shared.ai_gateway import AIGateway, Tier
    from prachar_shared.ai_gateway.json_utils import extract_json

    gateway = AIGateway()
    product = input.get("product", "")
    audience = input.get("audience", "")
    goal = input.get("goal", "engagement")
    budget = input.get("budget", "")

    prompt = f"""You are a world-class WhatsApp marketing strategist.
Design a WhatsApp campaign for:

Product/Service: {product}
Audience: {audience}
Goal: {goal}
Budget: {budget}

WHATSAPP CAMPAIGN REQUIREMENTS:

1. BROADCAST TEMPLATES (2-3 message templates):
   For each template:
   - name: template name
   - message: the broadcast message (≤1000 chars, conversational, no spam)
   - cta: call-to-action (button text or reply keyword)
   - media: optional image/video description
   - personalisation: merge fields to use
   - compliance: must comply with WhatsApp Business policy (opt-in required, no spam)

2. STATUS STRATEGY (5-7 status updates over a week):
   For each status:
   - day: which day to post
   - type: "text" | "image" | "video"
   - content: the status text or visual description
   - duration: how long to keep (24h max)
   - goal: awareness | engagement | conversion

3. CONTACT SEGMENTATION:
   - segments: 2-3 audience segments based on engagement level
   - segment_criteria: how to define each segment
   - segment_message: tailored message angle for each segment

4. SCHEDULE:
   - best_send_times: optimal days and times for this audience
   - frequency: how often to message (avoid over-messaging)
   - cooldown: minimum days between broadcasts

5. COMPLIANCE NOTES:
   - opt_in_requirements: how to get consent
   - opt_out_mechanism: how users can unsubscribe
   - 24_hour_rule: how to handle the 24-hour customer service window

QUALITY REQUIREMENTS:
- Messages must be conversational, not promotional-speak
- No spam tactics — WhatsApp bans accounts for spam
- Status updates must be engaging, not just ads
- Respect frequency limits (max 1 broadcast per 24h per segment)

Return JSON:
{{
  "templates": [...],
  "status_strategy": [...],
  "segments": [...],
  "schedule": {{"best_send_times": "...", "frequency": "...", "cooldown": "..."}},
  "compliance_notes": "..."
}}"""

    response = await gateway.async_complete(
        prompt=prompt, tier=Tier.large,
        tenant_id=str(ctx.tenant_id), max_tokens=2000,
    )
    result = extract_json(response.content) or {}

    return {
        "campaign": result,
        "artefacts": [whatsapp_campaign(
            templates=result.get("templates", []),
            segments=result.get("segments", []),
            schedule=result.get("schedule", {}).get("best_send_times", ""),
            compliance_notes=result.get("compliance_notes", ""),
        ).to_dict()],
    }


@register_tool(ToolManifest(
    name="whatsapp.broadcast",
    display_name="WhatsApp Broadcast Composer",
    description="Composes a single WhatsApp broadcast message with personalisation tokens, CTA, and compliance check. Includes 2 A/B variants.",
    category=ToolCategory.WHATSAPP,
    input_schema={"topic": "string", "audience": "string", "goal": "string"},
    output_schema={"broadcast": "object"},
    estimated_cost_usd=0.04,
    estimated_time_ms=5000,
    estimated_tokens=800,
    estimated_latency_ms=4000,
    quality_score=0.85,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.WRITES,
    memory_categories=[MemoryCategory.BRAND],
))
async def whatsapp_broadcast(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Compose a WhatsApp broadcast message."""
    from prachar_shared.ai_gateway import AIGateway, Tier
    from prachar_shared.ai_gateway.json_utils import extract_json

    gateway = AIGateway()
    topic = input.get("topic", "")
    audience = input.get("audience", "")
    goal = input.get("goal", "engagement")

    prompt = f"""You are a world-class WhatsApp marketing copywriter.
Compose a broadcast message for:
Topic: {topic}
Audience: {audience}
Goal: {goal}

Return JSON:
{{
  "message": "Conversational message ≤1000 chars, friendly tone, no spam words",
  "cta": "Reply keyword or button text",
  "media": "Optional image description or null",
  "personalisation_tokens": ["first_name", "last_purchase"],
  "variants": [
    {{"angle": "benefit", "message": "Alternative version focusing on benefit"}},
    {{"angle": "curiosity", "message": "Alternative version with curiosity hook"}}
  ],
  "compliance_check": "Confirms opt-in requirement and no spam language",
  "best_send_time": "Recommended day and time"
}}"""

    response = await gateway.async_complete(
        prompt=prompt, tier=Tier.MEDIUM,
        tenant_id=str(ctx.tenant_id), max_tokens=800,
    )
    result = extract_json(response.content) or {}

    return {"broadcast": result}
