"""Phase L7 — Marketing Calendar tool.

World-class content calendar: content planning, scheduling, seasonal hooks,
cross-channel coordination. Emits calendar_grid artefact.
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
from .artefacts import calendar_grid

log = logging.getLogger("prachar.runtime.tools.calendar")


@register_tool(ToolManifest(
    name="calendar.plan",
    display_name="Marketing Calendar Planner",
    description="Generates a 4-12 week marketing calendar with content themes, channel assignments, seasonal hooks, and cross-channel coordination. Includes content pillars and posting cadence.",
    category=ToolCategory.CALENDAR,
    input_schema={"weeks": "number", "industry": "string", "channels": "array", "goal": "string", "season": "string"},
    output_schema={"calendar": "object"},
    estimated_cost_usd=0.08,
    estimated_time_ms=10000,
    estimated_tokens=2000,
    estimated_latency_ms=8000,
    quality_score=0.89,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.WRITES,
    memory_categories=[MemoryCategory.BRAND, MemoryCategory.CAMPAIGN],
))
async def calendar_plan(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Generate a marketing calendar."""
    from prachar_shared.ai_gateway import AIGateway, Tier
    from prachar_shared.ai_gateway.json_utils import extract_json

    gateway = AIGateway()
    weeks = input.get("weeks", 4)
    industry = input.get("industry", "general")
    channels = input.get("channels", ["instagram", "facebook", "email"])
    goal = input.get("goal", "brand awareness")
    season = input.get("season", "")

    prompt = f"""You are a world-class content marketing strategist.
Create a {weeks}-week marketing calendar for:

Industry: {industry}
Channels: {', '.join(channels)}
Goal: {goal}
Season: {season or 'current season'}

CALENDAR REQUIREMENTS:

1. CONTENT PILLARS (3-5 themes):
   - name: pillar name
   - description: what this pillar covers
   - percentage: what % of content should be this pillar (must total 100%)

2. WEEKLY PLAN (for each of {weeks} weeks):
   For each week provide:
   - week_number: 1, 2, 3...
   - theme: weekly theme or focus
   - content_pieces: list of {{
       day: "Mon" | "Tue" | "Wed" | "Thu" | "Fri" | "Sat" | "Sun",
       channel: which channel,
       content_type: "post" | "story" | "reel" | "email" | "blog" | "video",
       topic: what the content is about,
       angle: the creative angle,
       cta: call-to-action,
       pillar: which content pillar this belongs to
     }}
   - seasonal_hook: any seasonal event or trend to leverage this week
   - cross_channel_synergy: how this week's content works across channels
   - kpi_focus: what metric to prioritise this week

3. POSTING CADENCE:
   - per_channel_frequency: how many posts per week per channel
   - best_posting_times: optimal times per channel
   - content_mix: ratio of educational/promotional/engagement/entertainment

QUALITY REQUIREMENTS:
- Each week must have a clear theme (not random posts)
- Content must be varied (not repetitive across weeks)
- Cross-channel synergy — same theme adapted per channel, not copy-pasted
- Seasonal hooks must be relevant and timely
- Cadence must be sustainable (not overwhelming)
- Include engagement-focused content (not just promotional)

Return JSON:
{{
  "content_pillars": [...],
  "weeks": [...],
  "posting_cadence": {{
    "per_channel_frequency": {{...}},
    "best_posting_times": {{...}},
    "content_mix": {{"educational": 40, "promotional": 20, "engagement": 25, "entertainment": 15}}
  }}
}}"""

    response = await gateway.async_complete(
        prompt=prompt, tier=Tier.large,
        tenant_id=str(ctx.tenant_id), max_tokens=2000,
    )
    result = extract_json(response.content) or {}
    week_list = result.get("weeks", [])

    return {
        "calendar": result,
        "artefacts": [calendar_grid(
            weeks=week_list,
            theme=season or "marketing calendar",
        ).to_dict()],
    }


@register_tool(ToolManifest(
    name="calendar.seasonal",
    display_name="Seasonal Content Planner",
    description="Identifies upcoming seasonal events, holidays, and trends relevant to the business. Generates content ideas for each with timing and channel recommendations.",
    category=ToolCategory.CALENDAR,
    input_schema={"industry": "string", "location": "string", "months_ahead": "number"},
    output_schema={"events": "array"},
    estimated_cost_usd=0.05,
    estimated_time_ms=6000,
    estimated_tokens=1000,
    estimated_latency_ms=5000,
    quality_score=0.86,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.BRAND],
))
async def calendar_seasonal(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Identify seasonal content opportunities."""
    from prachar_shared.ai_gateway import AIGateway, Tier
    from prachar_shared.ai_gateway.json_utils import extract_json

    gateway = AIGateway()
    industry = input.get("industry", "general")
    location = input.get("location", "global")
    months_ahead = input.get("months_ahead", 3)

    prompt = f"""You are a world-class seasonal marketing strategist.
Identify {months_ahead} months of seasonal opportunities for:

Industry: {industry}
Location: {location}

For each event/opportunity provide:
- event: name of the event/holiday/trend
- date: when it occurs (or date range)
- relevance: "high" | "medium" | "low" for this industry
- content_ideas: 2-3 specific content ideas
- channels: recommended channels for this event
- lead_time: how many days before to start posting
- angle: the creative angle for this event
- offer_idea: optional promotional offer tied to this event

Include a mix of:
- Major holidays (Diwali, Christmas, Eid, etc. — location-appropriate)
- Industry-specific events (awareness days, trade shows, seasonal peaks)
- Cultural moments (sports events, viral trends, memes)
- Shopping events (Black Friday, end-of-season sales, payday timing)

Return JSON: {{"events": [...]}}"""

    response = await gateway.async_complete(
        prompt=prompt, tier=Tier.MEDIUM,
        tenant_id=str(ctx.tenant_id), max_tokens=1000,
    )
    result = extract_json(response.content) or {}

    return {"events": result.get("events", [])}
