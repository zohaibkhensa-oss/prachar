"""Business Domain Pack — the default domain for traditional businesses.

Extracted from the original consult.py prompts and logic. This pack defines
business-specific discovery, planning, campaign templates, KPIs, and
conversation behaviour. The universal pipeline (consult engine, campaign
generator, presentation) is shared.
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
)


class BusinessPack(BaseDomainPack):
    """The default domain pack for traditional businesses."""

    id = "business"
    label = "Business Growth"
    customer_type = "business"
    emoji = "🏢"

    # ─── Discovery: business subtypes ───
    subtypes = [
        SubtypePreset("restaurant", "Restaurant", "🍽️", "Get more customers walking in.", "restaurant"),
        SubtypePreset("clinic", "Clinic", "🏥", "Get more patient appointments.", "clinic"),
        SubtypePreset("retail", "Retail", "🛍️", "Get more foot traffic and sales.", "retail"),
        SubtypePreset("hotel", "Hotel", "🏨", "Get more bookings.", "hotel"),
        SubtypePreset("realestate", "Real Estate", "🏠", "Get more property enquiries.", "realestate"),
        SubtypePreset("education", "Education", "🎓", "Get more student enrolments.", "education"),
        SubtypePreset("professional", "Professional Services", "💼", "Get more client enquiries.", "professional"),
        SubtypePreset("manufacturing", "Manufacturing", "🏭", "Reach more B2B buyers.", "manufacturing"),
        SubtypePreset("startup", "Startup", "🚀", "Launch and grow your startup.", "startup"),
        SubtypePreset("agency", "Agency", "🏢", "Grow your agency's client base.", "agency"),
    ]

    # ─── Discovery: extraction ───
    extraction_schema = {
        "type": "object",
        "properties": {
            "business_name": {"type": "string"},
            "industry": {"type": "string", "enum": ["restaurant", "clinic", "retail", "realestate", "education", "gym", "salon", "hotel", "professional", "other"]},
            "location": {"type": "string"},
            "products": {"type": "array", "items": {"type": "string"}},
            "services": {"type": "array", "items": {"type": "string"}},
            "audience": {"type": "string"},
            "goals": {"type": "array", "items": {"type": "string"}},
            "website": {"type": "string"},
            "social_handles": {"type": "array", "items": {"type": "string"}},
            "additional_context": {"type": "string"},
        },
    }

    extraction_prompt = """\
You are a business analyst. Extract structured information from the user's \
description of their business.

User said: "{message}"

Extract:
- business_name: The name of the business (if mentioned). If not, leave empty.
- industry: One of these categories: restaurant, clinic, retail, realestate, \
education, gym, salon, hotel, professional, other. Pick the closest match.
- location: City or area (if mentioned).
- products: List of products mentioned (e.g. "biryani", "coffee").
- services: List of services mentioned (e.g. "catering", "dental checkups").
- audience: Who the target customers seem to be.
- goals: What the business owner wants to achieve (stated or inferred).
- website: Website URL (if mentioned).
- social_handles: Social media handles (if mentioned).
- additional_context: Anything else useful (years in business, seasonality, \
special features, current marketing efforts).

Respond as JSON only, no markdown:
{{
  "business_name": "...",
  "industry": "...",
  "location": "...",
  "products": ["..."],
  "services": ["..."],
  "audience": "...",
  "goals": ["..."],
  "website": "...",
  "social_handles": ["..."],
  "additional_context": "..."
}}
"""

    # ─── Goals ───
    default_goal = "grow the business"
    goal_options = [
        "get more customers",
        "grow the business",
        "launch a new product",
        "increase revenue",
        "build brand awareness",
    ]

    # ─── KPIs ───
    kpi_cards = [
        KpiCardSpec("customers", "Customers", "Users", "From your campaigns"),
        KpiCardSpec("revenue", "Revenue", "TrendingUp", "From your campaigns"),
        KpiCardSpec("enquiries", "Enquiries", "MessageSquare", "From your campaigns"),
        KpiCardSpec("reach", "Reach", "Eye", "People who saw your business"),
    ]

    # ─── Growth Opportunities ───
    opportunity_prompt = """\
3. **growth_opportunities**: Exactly 5 growth opportunities, each with:
   - title: Short, action-oriented title (e.g. "Launch weekday lunch combo")
   - description: 1-2 sentence description
   - business_impact: "High", "Medium", or "Low"
   - difficulty: "Easy", "Medium", or "Hard"
   - timeframe: e.g. "1-2 weeks", "1 month", "3 months"
"""

    # ─── Planning ───
    week_schema = {
        "type": "object",
        "properties": {
            "week": {"type": "integer"},
            "theme": {"type": "string"},
            "objectives": {"type": "array", "items": {"type": "string"}},
            "content": {"type": "array", "items": {"type": "string"}},
            "offers": {"type": "array", "items": {"type": "string"}},
            "channels": {"type": "array", "items": {"type": "string"}},
            "kpis": {"type": "array", "items": {"type": "string"}},
        },
    }

    week_prompt = """\
4. **plan**: A 30-day marketing plan with 4 weeks, each with:
   - week: 1, 2, 3, or 4
   - theme: A short theme for the week (e.g. "Build your foundation")
   - objectives: 2-3 objectives for the week
   - content: 2-3 content pieces to create (e.g. "5 Instagram posts showing your best dishes")
   - offers: 1-2 offers or promotions (e.g. "Weekday lunch combo at ₹199")
   - channels: 2-3 channels to focus on (use friendly names: "Google", "Instagram", "WhatsApp")
   - kpis: 2-3 KPIs to track (in business language, e.g. "10 new reviews", "50 enquiries")
"""

    # ─── Campaign ───
    campaign_template = "Promotion Campaign"
    campaign_prompt = """\
You are a marketing strategist presenting a campaign recommendation to a business owner.

Business: {business_name}
Goal: {goal}
Budget: {budget}

Here is the full campaign analysis from our strategy team:
{campaign}

Create a campaign preview that feels like a presentation deck. Include:

1. **reply**: A 2-3 sentence conversational pitch for this campaign. Speak as "I". \
Make the owner excited but honest. Never use jargon.

2. **preview**: A campaign preview with:
   - title: A catchy campaign title (e.g. "Hyderabad's Best Biryani Tour")
   - hero_image_concept: Describe what the hero image should show (1 sentence)
   - video_concept: Describe a 30-second video concept (1-2 sentences)
   - post_ideas: 5 specific post ideas (e.g. "Behind-the-scenes: how we marinate the chicken for 12 hours")
   - estimated_reach: e.g. "15,000-25,000 people in Hyderabad"
   - expected_enquiries: e.g. "30-50 catering enquiries in the first month"
   - budget_estimate: e.g. "₹15,000/month (₹500/day)"
   - why_this_campaign: 2-3 sentences explaining why this campaign makes sense for their business
   - confidence: 0-100, how confident you are this will work
   - expected_benefit: 1 sentence on what they'll get out of it
   - risks: 2-3 risks (e.g. "Slow first week while ads learn your audience")
   - alternative: 1 sentence on a backup approach if this doesn't work

Use business language only. No jargon.

Respond as JSON only:
{{
  "reply": "...",
  "preview": {{
    "title": "...",
    "hero_image_concept": "...",
    "video_concept": "...",
    "post_ideas": ["..."],
    "estimated_reach": "...",
    "expected_enquiries": "...",
    "budget_estimate": "...",
    "why_this_campaign": "...",
    "confidence": 85,
    "expected_benefit": "...",
    "risks": ["..."],
    "alternative": "..."
  }}
}}
"""

    # ─── Recommendations ───
    recommendations_prompt = "Be specific to their business. A biryani restaurant's plan should look different from a dental clinic's plan."

    # ─── Creative Directions ───
    creative_directions_prompt = """\
Generate exactly 3 distinct creative directions for this business campaign. \
Each direction must take a genuinely different angle — do NOT produce three \
variants of the same idea. Use business language only. No jargon.

For each direction provide:
- id: A short slug (e.g. "trust_builder", "offer_lead", "story_behind")
- hook: A 1-sentence attention-grabber the audience can't scroll past
- angle: 1 sentence describing the strategic angle (what makes this direction different)
- tone: 2-3 words describing the tone (e.g. "Warm and confident", "Bold and playful")
- sample_headline: One sample ad headline for this direction
- sample_cta: One sample call-to-action for this direction
"""

    # ─── Hook Patterns ───
    hooks_prompt = """\
Generate 5 hook patterns for this business campaign — one each for: question, \
stat, story, contrarian, aspiration. Each hook must be a single sentence that \
stops the scroll. Use plain business language — no jargon, no hype. The \
"why_it_works" field should explain the psychological trigger in one sentence \
(e.g. curiosity gap, social proof, loss aversion, identity appeal).
"""

    # ─── Audience Psychology ───
    audience_psychology_prompt = """\
Analyse the psychology of this business's target audience. Focus on growth, \
efficiency, ROI, and risk reduction. Motivations should centre on saving time, \
making money, or gaining a competitive edge. Objections often involve cost, \
trust, and switching effort. Emotional triggers include security, pride, fear \
of missing out, and ambition. The decision style is typically rational and \
comparison-driven.
"""

    # ─── Offers ───
    offers_prompt = """\
Generate 3 engineered offers for this business campaign using pricing \
psychology. Use business-appropriate techniques: anchoring (show a premium \
tier to make the standard look affordable), bundling (combine services for \
perceived value), loss-aversion (frame what they lose by not acting), scarcity \
(limited-time or limited-seat), and decoy pricing (a third option that makes \
the target look best). Offers should feel professional and credible — no hype. \
Focus on value, ROI, and risk reduction.
"""

    # ─── Pricing Psychology ───
    pricing_psychology_prompt = """\
Generate 3 pricing presentations for this business campaign. Use charm pricing \
(prices ending in 9 or 99 to feel lower), tiered pricing (good/better/best \
options), bundling (combine products or services for perceived value), \
anchoring (show a high reference price to make the actual price look \
reasonable), and loss-leader (a low-margin item to draw customers in). \
Presentations should feel professional and credible — focus on value, ROI, \
and clear pricing logic.
"""

    # ─── Seasonal ───
    seasonal_prompt = """\
Generate seasonal marketing ideas for this business tied to the target months. \
Consider seasonal sales cycles, holidays, financial year milestones, and \
industry-specific seasonal trends. Ideas should leverage seasonal demand \
patterns, end-of-season clearances, festive promotions, and \
back-to-school/back-to-work moments. Focus on driving sales during peak \
seasonal windows.
"""

    # ─── Local ───
    local_prompt = """\
Generate local marketing ideas for this business. Consider hosting or \
sponsoring local events, partnering with nearby complementary businesses, \
hyper-local ad targeting (within a few km radius), and local SEO / Google \
Business Profile optimisation. Ideas should drive foot traffic and local \
awareness. Focus on the neighbourhood and community around the business.
"""

    # ─── Differentiation ───
    differentiation_prompt = """\
Generate competitor differentiation entries for this business. Identify common \
claims competitors make (e.g. "lowest prices", "fastest service", "biggest \
selection") and how this business counters them with genuine evidence. Focus \
on what makes this business uniquely valuable — quality, expertise, customer \
service, or specialisation. Avoid naming specific competitors; use generic \
competitor claims instead.
"""

    # ─── Strategy ───
    strategy_prompt = """\
A good strategy for a business balances measurable growth with brand trust. \
The primary strategy should be the highest-probability path to the goal given \
the budget — typically a direct-response or lead-generation approach. The \
alternative should pursue the same goal via a different lever (e.g. brand \
awareness instead of direct response, or a different audience segment). The \
contrarian should take an unconventional angle that most competitors would \
ignore but that could win big (e.g. community-building, polarising positioning, \
or a counter-cyclical timing play). Strategies must be genuinely different in \
approach — not three variations of the same tactic. Consider ROI, sales cycle \
length, and competitive saturation when choosing the primary.
"""

    # ─── Dashboard ───
    dashboard_widgets = [
        WidgetSpec("kpi_grid", "Your business at a glance"),
        WidgetSpec("quick_actions", "Grow your business"),
        WidgetSpec("approvals", "Waiting for your approval"),
        WidgetSpec("pipeline", "Your campaigns"),
    ]

    quick_actions = [
        ActionCardSpec("Create My Campaign", "We'll build your marketing campaign — tailored for your business. Takes 30 seconds.", "/app/brands/{brand_id}/campaigns/new", "Zap", "accent"),
    ]

    # ─── Memory ───
    brand_graph_schema = {
        "type": "object",
        "properties": {
            "location": {"type": "string"},
            "products": {"type": "array", "items": {"type": "string"}},
            "services": {"type": "array", "items": {"type": "string"}},
            "audience": {"type": "string"},
            "goals": {"type": "array", "items": {"type": "string"}},
            "social_handles": {"type": "array", "items": {"type": "string"}},
            "additional_context": {"type": "string"},
        },
    }
    memory_namespace = "business"

    # ─── Conversation ───
    conversation_role = "marketing strategist"
    forbidden_jargon = ["ROAS", "CPA", "CTR", "funnel", "TOFU"]
    greeting_template = (
        "Hey! I'm PRACHAR AI — your marketing strategist. Tell me about your {subject} business. "
        "What do you do, where, and who do you serve? The more you share, "
        "the better I can help."
    )

    # ─── Sidebar ───
    nav_sections = [
        NavSectionSpec("Main", [
            NavItemSpec("Home", "/app", "LayoutDashboard"),
            NavItemSpec("Campaigns", "/app/campaigns", "Megaphone"),
            NavItemSpec("Review", "/app/review", "CircleCheckBig"),
            NavItemSpec("Performance", "/app/performance", "TrendingUp"),
        ]),
        NavSectionSpec("Creative AI", [
            NavItemSpec("Creative AI", "/app/creative", "Sparkles"),
            NavItemSpec("AI Video", "/app/video", "Video"),
            NavItemSpec("Studio AI", "/app/creative-studio", "Wand2"),
            NavItemSpec("AI Image Studio", "/app/images", "Image"),
            NavItemSpec("Design AI", "/app/design", "Palette"),
        ]),
        NavSectionSpec("Brand", [
            NavItemSpec("My Brand", "/app/brands", "Building2"),
            NavItemSpec("Channels", "/app/channels", "Share2"),
            NavItemSpec("Content Calendar", "/app/calendar", "Calendar"),
            NavItemSpec("Customer Reviews", "/app/reviews", "Star"),
        ]),
        NavSectionSpec("Settings", [
            NavItemSpec("Settings", "/app/settings", "Settings"),
            NavItemSpec("Upgrade", "/app/pricing", "Crown"),
        ]),
    ]

    # ─── Tools ───
    tools = []  # Business has no domain-specific tools (yet)
