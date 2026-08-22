"""Creator Domain Pack — for content creators (YouTubers, podcasters, etc.).

Extracted from the original creator.py prompts and logic. This pack defines
creator-specific discovery, planning, campaign templates, KPIs, conversation
behaviour, and two domain-specific tools (Repurpose, YouTube Plan).

The universal pipeline (consult engine, campaign generator, presentation) is
shared with all other domains.
"""
from __future__ import annotations

from ..base import (
    BaseDomainPack,
    SubtypePreset,
    KpiCardSpec,
    ActionCardSpec,
    WidgetSpec,
    NavItemSpec,
    NavSectionSpec,
    ToolSpec,
)


# ─── Creator tools (domain-specific, invoked via /consult/tool/{tool_id}) ──


_REPURPOSE_PROMPT = """\
You are a content repurposing expert. Given one YouTube video, create 11 \
repurposed assets — each optimised for its platform.

Video title: "{title}"
Video description/transcript: "{description}"
Creator niche: {niche}

Create these 11 assets:

1. **YouTube Shorts** — 3 short scripts (30-60 seconds each), each with a \
strong hook in the first 3 seconds. Format: "Short 1: [script]"

2. **Instagram Reels** — 2 reel concepts with visual descriptions and captions. \
Format: "Reel 1: [concept + caption]"

3. **Facebook Reel** — 1 reel adapted for Facebook audience (slightly longer, \
more context). Format: "[concept + script]"

4. **LinkedIn Post** — 1 professional post extracting the key insight. \
150-300 words. No hashtags in the body.

5. **X Thread** — 1 thread of 5-7 tweets. First tweet is the hook. \
Each tweet standalone-readable.

6. **Blog Article** — 1 blog post outline with 5-7 sections, each with a \
1-sentence summary. Include suggested title and meta description.

7. **Newsletter** — 1 newsletter section (200-400 words) summarising the video \
for email subscribers. Include subject line.

8. **Email** — 1 short email (100-150 words) promoting the video to a list. \
Include subject line.

9. **Community Post** — 1 YouTube community post (poll or text) to drive \
engagement before/after the video.

10. **Podcast Summary** — If the video were a podcast episode, a 100-word \
summary for podcast directories.

11. **Sponsor Pitch** — A 100-word pitch to a relevant brand explaining why \
they should sponsor this content.

Respond as JSON only:
{{
  "reply": "A 1-2 sentence conversational summary of what you created.",
  "assets": [
    {{"asset_type": "YouTube Shorts", "content": "...", "notes": "..."}},
    {{"asset_type": "Instagram Reels", "content": "...", "notes": "..."}},
    {{"asset_type": "Facebook Reel", "content": "...", "notes": "..."}},
    {{"asset_type": "LinkedIn Post", "content": "...", "notes": "..."}},
    {{"asset_type": "X Thread", "content": "...", "notes": "..."}},
    {{"asset_type": "Blog Article", "content": "...", "notes": "..."}},
    {{"asset_type": "Newsletter", "content": "...", "notes": "..."}},
    {{"asset_type": "Email", "content": "...", "notes": "..."}},
    {{"asset_type": "Community Post", "content": "...", "notes": "..."}},
    {{"asset_type": "Podcast Summary", "content": "...", "notes": "..."}},
    {{"asset_type": "Sponsor Pitch", "content": "...", "notes": "..."}}
  ]
}}
"""

_YOUTUBE_PLAN_PROMPT = """\
You are a YouTube growth expert. Create a complete video plan for one video.

Video concept: "{concept}"
Creator niche: {niche}
Target audience: {audience}

Create:

1. **title_options**: 5 title options. Each must be:
   - Under 70 characters
   - Clickable but not clickbait
   - Optimised for search and CTR

2. **thumbnail_concepts**: 3 thumbnail concepts. Each describes:
   - The main visual
   - Text overlay (max 5 words)
   - Emotion/expression

3. **opening_hook**: The first 10 seconds of the video — the script that \
keeps viewers from clicking away.

4. **retention_improvements**: 3-5 techniques to keep viewers watching \
(e.g. "Tease the best part at 0:30", "Use pattern interrupts every 60 seconds").

5. **description**: A full video description (200-400 words) with:
   - First 2 lines are the hook (visible before "Show more")
   - Key points
   - Timestamps
   - Call to action
   - Links to social

6. **seo_keywords**: 10 SEO keywords for this video.

7. **tags**: 15 tags (mix of broad and specific).

8. **chapters**: Chapter markers with timestamps (e.g. "0:00 Intro", "1:30 The problem").

9. **pinned_comment**: A pinned comment that drives engagement \
(asks a question, offers a resource, or teases the next video).

10. **community_post**: A community post to promote the video 24 hours before launch.

11. **end_screen_suggestions**: 3 end screen video suggestions \
(describe which videos to link and why).

Respond as JSON only:
{{
  "reply": "A 1-2 sentence conversational summary.",
  "plan": {{
    "title_options": ["..."],
    "thumbnail_concepts": ["..."],
    "opening_hook": "...",
    "retention_improvements": ["..."],
    "description": "...",
    "seo_keywords": ["..."],
    "tags": ["..."],
    "chapters": ["..."],
    "pinned_comment": "...",
    "community_post": "...",
    "end_screen_suggestions": ["..."]
  }}
}}
"""


class CreatorPack(BaseDomainPack):
    """The domain pack for content creators."""

    id = "creator"
    label = "Creator Growth"
    customer_type = "creator"
    emoji = "🎨"

    # ─── Discovery: creator subtypes ───
    subtypes = [
        SubtypePreset("youtube_creator", "YouTube Creator", "📹", "Grow your channel with better titles, thumbnails, and content.", "youtube"),
        SubtypePreset("instagram_creator", "Instagram Creator", "📸", "Build your Instagram presence with reels, posts, and stories.", "instagram"),
        SubtypePreset("podcaster", "Podcaster", "🎙️", "Grow your podcast audience and find sponsors.", "podcast"),
        SubtypePreset("influencer", "Influencer", "✨", "Grow your following and land brand deals.", "influencer"),
        SubtypePreset("gaming_creator", "Gaming Creator", "🎮", "Grow your gaming channel and community.", "gaming"),
        SubtypePreset("educator", "Educator", "🎓", "Teach your audience and grow your educational channel.", "education"),
        SubtypePreset("media_company", "Media Company", "📰", "Scale your media brand across platforms.", "media"),
        SubtypePreset("production_studio", "Production Studio", "🎬", "Produce content that gets noticed.", "production"),
        SubtypePreset("musician", "Musician", "🎵", "Grow your music career and audience.", "music"),
        SubtypePreset("personal_brand", "Personal Brand", "🚀", "Build your personal brand and authority.", "personal"),
    ]

    # ─── Discovery: extraction ───
    extraction_schema = {
        "type": "object",
        "properties": {
            "niche": {"type": "string"},
            "platforms": {"type": "array", "items": {"type": "string"}},
            "upload_frequency": {"type": "string"},
            "content_pillars": {"type": "array", "items": {"type": "string"}},
            "audience": {"type": "string"},
            "audience_size": {"type": "string"},
            "growth_stage": {"type": "string", "enum": ["Emerging", "Growing", "Established", "Pro"]},
            "monetisation": {"type": "string"},
            "brand_partnerships": {"type": "array", "items": {"type": "string"}},
            "competitors": {"type": "array", "items": {"type": "string"}},
        },
    }

    extraction_prompt = """\
You are a creator analyst. Extract structured information from the creator's \
description of their channel.

Creator said: "{message}"

Extract:
- niche: Their content niche (be specific, e.g. "tech reviews for Indian audiences")
- platforms: Primary platforms (e.g. ["YouTube", "Instagram"])
- upload_frequency: Their posting cadence (e.g. "2 videos/week, 3 shorts/week")
- content_pillars: 3-4 main content themes
- audience: Who watches/follows them
- audience_size: Estimated audience size if inferrable
- growth_stage: "Emerging" (<10K), "Growing" (10K-100K), "Established" (100K-1M), or "Pro" (1M+)
- monetisation: Current monetisation methods (or "Not yet monetised")
- brand_partnerships: Any notable brand deals mentioned
- competitors: 2-3 similar creators in the niche

Respond as JSON only, no markdown:
{{
  "niche": "...",
  "platforms": ["..."],
  "upload_frequency": "...",
  "content_pillars": ["..."],
  "audience": "...",
  "audience_size": "...",
  "growth_stage": "...",
  "monetisation": "...",
  "brand_partnerships": ["..."],
  "competitors": ["..."]
}}
"""

    # ─── Goals ───
    default_goal = "grow the channel"
    goal_options = [
        "grow the channel",
        "reach 10K subscribers",
        "monetise the channel",
        "land brand deals",
        "launch merchandise",
    ]

    # ─── KPIs ───
    kpi_cards = [
        KpiCardSpec("subscribers", "Subscribers", "Users", "Connect YouTube to see"),
        KpiCardSpec("views", "Views (28d)", "Eye", "Connect YouTube to see"),
        KpiCardSpec("watch_time", "Watch time", "Clock", "Connect YouTube to see"),
        KpiCardSpec("retention", "Avg. retention", "Target", "Connect YouTube to see"),
        KpiCardSpec("ctr", "CTR", "TrendingUp", "Connect YouTube to see"),
        KpiCardSpec("uploads", "Uploads (30d)", "Video", "From your plans"),
        KpiCardSpec("revenue", "Est. revenue", "DollarSign", "Connect YouTube to see"),
        KpiCardSpec("brand_deals", "Brand deals", "Handshake", "Track in Brand Deals"),
    ]

    # ─── Growth Opportunities ───
    opportunity_prompt = """\
3. **growth_opportunities**: 3-4 growth opportunities specific to their channel.
4. **content_gaps**: 2-3 content types they're missing.
5. **monetisation_opportunities**: 2-3 monetisation opportunities.
"""

    # ─── Planning ───
    week_schema = {
        "type": "object",
        "properties": {
            "week": {"type": "integer"},
            "theme": {"type": "string"},
            "videos": {"type": "array", "items": {"type": "string"}},
            "shorts": {"type": "array", "items": {"type": "string"}},
            "community_posts": {"type": "array", "items": {"type": "string"}},
            "collaborations": {"type": "array", "items": {"type": "string"}},
            "seo": {"type": "array", "items": {"type": "string"}},
            "newsletter": {"type": "string"},
            "live_sessions": {"type": "string"},
            "kpis": {"type": "array", "items": {"type": "string"}},
        },
    }

    week_prompt = """\
6. **plan**: A 30-day growth plan with 4 weeks, each with:
   - week: 1, 2, 3, or 4
   - theme: Short theme (e.g. "Double down on shorts")
   - videos: 1-2 long-form video ideas
   - shorts: 3-5 shorts/reels ideas
   - community_posts: 2-3 community post ideas
   - collaborations: 1-2 collaboration ideas
   - seo: 1-2 SEO/optimisation tasks
   - newsletter: Newsletter content for the week (or "" if no newsletter)
   - live_sessions: Live session plan (or "" if not applicable)
   - kpis: 2-3 KPIs to track (e.g. "5K new subscribers", "10% CTR")
"""

    # ─── Campaign ───
    campaign_template = "Content Campaign"
    campaign_prompt = """\
You are a creator growth strategist. Create a 30-day content campaign for a creator.

Creator: {creator_name}
Goal: {goal}
Budget: {budget}

Here is the creator's profile and analysis:
{analysis}

Create a content campaign that includes:

1. **reply**: A 2-3 sentence conversational pitch for this campaign.

2. **title**: A catchy campaign title (e.g. "Tech Tuesday Marathon" or \
"Road to 10K Subscribers").

3. **content_plan**: A 4-week content plan (reuse the weekly structure with \
videos, shorts, community_posts, collaborations, seo, newsletter, \
live_sessions, kpis).

4. **publishing_schedule**: A summary of the publishing cadence \
(e.g. "2 long-form videos/week on Tue+Fri, 3 shorts/week, 1 community post/week").

5. **expected_growth**: What they can expect in 30 days \
(e.g. "2,000-3,000 new subscribers if execution is consistent").

6. **confidence**: 0-100, how confident you are this plan will work.

Use creator language only. No business jargon.

Respond as JSON only:
{{
  "reply": "...",
  "title": "...",
  "content_plan": [
    {{
      "week": 1,
      "theme": "...",
      "videos": ["..."],
      "shorts": ["..."],
      "community_posts": ["..."],
      "collaborations": ["..."],
      "seo": ["..."],
      "newsletter": "...",
      "live_sessions": "...",
      "kpis": ["..."]
    }}
  ],
  "publishing_schedule": "...",
  "expected_growth": "...",
  "confidence": 85
}}
"""

    # ─── Recommendations ───
    recommendations_prompt = "Be specific to their niche. A tech reviewer's plan should look different from a gaming creator's plan. Use creator language — never use business jargon like 'ROAS', 'CPA', 'conversions', 'customers'."

    # ─── Creative Directions ───
    creative_directions_prompt = """\
Generate exactly 3 distinct creative directions for this creator content campaign. \
Each direction must take a genuinely different angle — do NOT produce three \
variants of the same idea. Use creator language only. No business jargon.

For each direction provide:
- id: A short slug (e.g. "behind_the_scenes", "hot_takes", "value_bombs")
- hook: A 1-sentence attention-grabber viewers can't scroll past
- angle: 1 sentence describing the strategic angle (what makes this direction different)
- tone: 2-3 words describing the tone (e.g. "Energetic and raw", "Calm and authoritative")
- sample_headline: One sample video title / post headline for this direction
- sample_cta: One sample call-to-action for this direction (e.g. "Subscribe for more")
"""

    # ─── Hook Patterns ───
    hooks_prompt = """\
Generate 5 hook patterns for this creator content campaign — one each for: \
question, stat, story, contrarian, aspiration. Each hook must be a single \
sentence that stops the scroll. Use creator language only — never use business \
jargon like "ROAS", "CPA", "conversions". The "why_it_works" field should \
explain the psychological trigger in one sentence (e.g. curiosity gap, pattern \
interrupt, relatability, identity appeal).
"""

    # ─── Audience Psychology ───
    audience_psychology_prompt = """\
Analyse the psychology of this creator's audience. Focus on entertainment, \
learning, belonging, and identity. Motivations should centre on curiosity, \
inspiration, self-improvement, and community. Objections often involve time, \
relevance, and content saturation. Emotional triggers include inspiration, \
FOMO, relatability, and aspiration. The decision style is typically impulse \
and emotionally driven.
"""

    # ─── Offers ───
    offers_prompt = """\
Generate 3 engineered offers for this creator content campaign using pricing \
psychology. Use creator-appropriate techniques: exclusive content bundle \
(bundling premium videos, community access, and resources), scarcity (limited- \
spot mentorship or a one-time workshop), anchoring (a premium 1-on-1 tier \
that makes the community subscription look like a steal), loss-aversion \
(\"don't miss this month's exclusive drop\"), and decoy pricing (a high-ticket \
coaching package that makes the standard membership look like the obvious \
choice). Offers should feel exciting and community-driven — never use business \
jargon like \"ROAS\", \"CPA\", \"conversions\". Focus on access, belonging, \
and exclusivity.
"""

    # ─── Pricing Psychology ───
    pricing_psychology_prompt = """\
Generate 3 pricing presentations for this creator content campaign. Use charm \
pricing (membership at ₹99/month instead of ₹100), tiered pricing \
(free/community/premium tiers), bundling (combine courses + community + \
resources for perceived value), anchoring (a premium 1-on-1 coaching price \
that makes the subscription look like a steal), and loss-leader (a free \
resource or mini-course to draw viewers into the funnel). Presentations \
should feel exciting and community-driven — never use business jargon like \
\"ROAS\", \"CPA\", \"conversions\". Focus on access, belonging, and value.
"""

    # ─── Seasonal ───
    seasonal_prompt = """\
Generate seasonal marketing ideas for this creator tied to the target months. \
Consider trending topics, seasonal content themes (New Year goals, summer \
projects, back-to-school, holiday gift guides), and platform-specific seasonal \
trends. Ideas should leverage what's trending and what audiences are searching \
for during each month. Focus on riding seasonal content waves and trending \
topics to maximise reach.
"""

    # ─── Local ───
    local_prompt = ""  # Creators don't have local marketing — they're online

    # ─── Differentiation ───
    differentiation_prompt = """\
Generate competitor differentiation entries for this creator. Identify common \
claims other creators make (e.g. "most in-depth tutorials", "fastest growing \
channel", "exclusive industry access") and how this creator counters them with \
genuine evidence. Focus on what makes this creator uniquely valuable — \
perspective, expertise, personality, or content quality. Avoid naming specific \
creators; use generic competitor claims instead. Never use business jargon.
"""

    # ─── Strategy ───
    strategy_prompt = """\
A good strategy for a creator grows audience, engagement, or monetisation — \
not vanity metrics. The primary strategy should be the highest-probability \
path to the goal given the budget (e.g. a short-form-first content sprint \
across Shorts and Reels to maximise reach, paired with a community funnel). \
The alternative should pursue the same goal via a different lever (e.g. long-\
form YouTube SEO instead of short-form virality, or a collaboration / cross-\
promotion blitz instead of solo content). The contrarian should take an \
unconventional angle most creators in the niche would ignore (e.g. a polarising \
hot-takes series, a slow-burn documentary style, or a paid newsletter pivot \
that trades reach for depth). Strategies must be genuinely different — not \
three variations of the same content format. Consider niche saturation, \
audience loyalty, and platform algorithm trends when choosing the primary. \
Never use business jargon like "ROAS", "CPA", "conversions".
"""

    # ─── Dashboard ───
    dashboard_widgets = [
        WidgetSpec("kpi_grid", "Your channel"),
        WidgetSpec("quick_actions", "Create content"),
        WidgetSpec("approvals", "Waiting for your approval"),
        WidgetSpec("trending", "Trending in your niche"),
        WidgetSpec("pipeline", "Content pipeline"),
    ]

    quick_actions = [
        ActionCardSpec("Repurpose a video", "Turn one YouTube video into 11 assets — Shorts, Reels, posts, blog, newsletter.", "/app/repurpose", "RefreshCw", "accent"),
        ActionCardSpec("Plan a YouTube video", "Get titles, thumbnails, hooks, SEO, tags, chapters — everything you need to post.", "/app/youtube-plan", "Video", "info"),
        ActionCardSpec("Build content campaign", "Get a 30-day content plan tailored to your channel and goals.", "/app/brands/{brand_id}/campaigns/new", "Calendar", "success"),
    ]

    # ─── Memory ───
    brand_graph_schema = {
        "type": "object",
        "properties": {
            "creator_type": {"type": "string"},
            "description": {"type": "string"},
            "profile": {"type": "object"},
            "position": {"type": "object"},
        },
    }
    memory_namespace = "creator"

    # ─── Conversation ───
    conversation_role = "creator strategist"
    forbidden_jargon = ["ROAS", "CPA", "conversions", "customers", "funnel"]
    greeting_template = (
        "Hey! I'm CURV AI — your strategist for {subject} growth. Tell me about your channel. "
        "What's your niche, where do you post, who's your audience, and where do you "
        "want to be in 6 months? The more you share, the better I can help."
    )

    # ─── Sidebar ───
    nav_sections = [
        NavSectionSpec("Main", [
            NavItemSpec("Home", "/app", "LayoutDashboard"),
            NavItemSpec("Content", "/app/campaigns", "Megaphone"),
            NavItemSpec("Review", "/app/review", "CircleCheckBig"),
            NavItemSpec("Performance", "/app/performance", "TrendingUp"),
            NavItemSpec("Repurpose video", "/app/repurpose", "RefreshCw"),
            NavItemSpec("Plan YouTube video", "/app/youtube-plan", "Video"),
        ]),
        NavSectionSpec("Creative AI", [
            NavItemSpec("Creative AI", "/app/creative", "Sparkles"),
            NavItemSpec("AI Video", "/app/video", "Video"),
            NavItemSpec("Studio AI", "/app/creative-studio", "Wand2"),
            NavItemSpec("AI Image Studio", "/app/images", "Image"),
            NavItemSpec("Design AI", "/app/design", "Palette"),
        ]),
        NavSectionSpec("Channel", [
            NavItemSpec("My Channel", "/app/brands", "Video"),
            NavItemSpec("Channels", "/app/channels", "Share2"),
            NavItemSpec("Content Calendar", "/app/calendar", "Calendar"),
            NavItemSpec("Audience", "/app/analytics", "Users"),
        ]),
        NavSectionSpec("Settings", [
            NavItemSpec("Settings", "/app/settings", "Settings"),
            NavItemSpec("Upgrade", "/app/pricing", "Crown"),
        ]),
    ]

    # ─── Tools ───
    tools = [
        ToolSpec(
            id="repurpose",
            label="Repurpose a video",
            description="Turn one YouTube video into 11 assets — Shorts, Reels, posts, blog, newsletter.",
            input_schema={
                "type": "object",
                "properties": {
                    "video_title": {"type": "string"},
                    "video_description": {"type": "string", "minLength": 10, "maxLength": 5000},
                    "niche": {"type": "string"},
                },
                "required": ["video_description"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "reply": {"type": "string"},
                    "assets": {"type": "array", "items": {"type": "object"}},
                },
            },
            prompt_template=_REPURPOSE_PROMPT,
            task_name="creator_repurpose",
            prompt_version="creator_repurpose_v1.0",
            max_tokens=3000,
            temperature=0.7,
            tier="medium",
        ),
        ToolSpec(
            id="youtube_plan",
            label="Plan a YouTube video",
            description="Get titles, thumbnails, hooks, SEO, tags, chapters — everything you need to post.",
            input_schema={
                "type": "object",
                "properties": {
                    "video_concept": {"type": "string", "minLength": 5, "maxLength": 1000},
                    "niche": {"type": "string"},
                    "audience": {"type": "string"},
                },
                "required": ["video_concept"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "reply": {"type": "string"},
                    "plan": {"type": "object"},
                },
            },
            prompt_template=_YOUTUBE_PLAN_PROMPT,
            task_name="creator_youtube_plan",
            prompt_version="creator_youtube_plan_v1.0",
            max_tokens=2500,
            temperature=0.7,
            tier="medium",
        ),
    ]
