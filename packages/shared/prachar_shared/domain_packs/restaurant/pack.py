"""Restaurant Domain Pack — for restaurants, cafes, cloud kitchens, food brands.

This pack demonstrates that a new domain can be added by implementing ONE file
with ZERO core modifications. The universal pipeline (consult engine, campaign
generator, dashboard shell, presentation components) is shared.

A restaurant is a business subtype with domain-specific:
- KPIs (covers, average order value, repeat visits)
- Campaign template (Promotion Campaign with food-specific examples)
- Dashboard widgets (today's promotion, reservations)
- Conversation behaviour (food language, no jargon)
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


class RestaurantPack(BaseDomainPack):
    """The domain pack for restaurants."""

    id = "restaurant"
    label = "Restaurant Growth"
    customer_type = "business"
    emoji = "🍽️"

    # ─── Discovery ───
    subtypes = [
        SubtypePreset("dine_in", "Dine-in Restaurant", "🍽️", "Get more people walking in.", "restaurant"),
        SubtypePreset("cafe", "Cafe", "☕", "Get more regulars and orders.", "cafe"),
        SubtypePreset("cloud_kitchen", "Cloud Kitchen", "🥡", "Get more delivery orders.", "cloud_kitchen"),
        SubtypePreset("food_brand", "Food Brand / QSR", "🍔", "Scale your food brand.", "food_brand"),
        SubtypePreset("catering", "Catering", "🍱", "Get more catering bookings.", "catering"),
    ]

    extraction_schema = {
        "type": "object",
        "properties": {
            "business_name": {"type": "string"},
            "cuisine": {"type": "string"},
            "location": {"type": "string"},
            "signature_dishes": {"type": "array", "items": {"type": "string"}},
            "service_style": {"type": "string", "enum": ["dine_in", "takeaway", "delivery", "cloud_kitchen", "catering"]},
            "price_range": {"type": "string", "enum": ["budget", "mid", "premium", "luxury"]},
            "seating_capacity": {"type": "integer"},
            "audience": {"type": "string"},
            "goals": {"type": "array", "items": {"type": "string"}},
            "website": {"type": "string"},
            "social_handles": {"type": "array", "items": {"type": "string"}},
            "additional_context": {"type": "string"},
        },
    }

    extraction_prompt = """\
You are a restaurant business analyst. Extract structured information from the \
owner's description of their restaurant.

Owner said: "{message}"

Extract:
- business_name: The name of the restaurant (if mentioned).
- cuisine: Type of cuisine (e.g. "Hyderabadi", "Italian", "South Indian").
- location: City or area.
- signature_dishes: List of signature/most popular dishes.
- service_style: dine_in, takeaway, delivery, cloud_kitchen, or catering.
- price_range: budget, mid, premium, or luxury.
- seating_capacity: Approximate seating (if mentioned).
- audience: Who the target customers are.
- goals: What the owner wants to achieve.
- website: Website URL (if mentioned).
- social_handles: Social media handles (if mentioned).
- additional_context: Anything else (years open, ratings, special features).

Respond as JSON only:
{{
  "business_name": "...",
  "cuisine": "...",
  "location": "...",
  "signature_dishes": ["..."],
  "service_style": "...",
  "price_range": "...",
  "seating_capacity": 0,
  "audience": "...",
  "goals": ["..."],
  "website": "...",
  "social_handles": ["..."],
  "additional_context": "..."
}}
"""

    # ─── Goals ───
    default_goal = "get more customers walking in"
    goal_options = [
        "get more customers walking in",
        "grow catering orders",
        "fill more tables on weekdays",
        "launch a new menu",
        "build a loyal regular base",
    ]

    # ─── KPIs ───
    kpi_cards = [
        KpiCardSpec("covers", "Covers (daily)", "Users", "People served"),
        KpiCardSpec("aov", "Avg. order value", "DollarSign", "Per bill"),
        KpiCardSpec("repeat", "Repeat visits", "RefreshCw", "Returning customers"),
        KpiCardSpec("reviews", "Reviews", "Star", "Google + Zomato + Swiggy"),
        KpiCardSpec("enquiries", "Enquiries", "MessageSquare", "Catering + reservations"),
        KpiCardSpec("reach", "Reach", "Eye", "People who saw your restaurant"),
    ]

    # ─── Growth Opportunities ───
    opportunity_prompt = """\
3. **growth_opportunities**: Exactly 5 growth opportunities, each with:
   - title: Short, action-oriented title (e.g. "Launch weekday lunch thali")
   - description: 1-2 sentence description
   - business_impact: "High", "Medium", or "Low"
   - difficulty: "Easy", "Medium", or "Hard"
   - timeframe: e.g. "1-2 weeks", "1 month"
   Focus on restaurant-specific opportunities: menu engineering, weekday promotions, \
   catering, delivery apps, reviews, Google Business Profile, Instagram food content, \
   local SEO, partnerships with offices/events.
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
   - theme: A short theme (e.g. "Build your Instagram presence")
   - objectives: 2-3 objectives
   - content: 2-3 content pieces (e.g. "5 Instagram reels of signature dishes being prepared")
   - offers: 1-2 offers (e.g. "Weekday lunch thali at ₹199", "Free dessert on reviews above 4.5")
   - channels: 2-3 channels (e.g. "Instagram", "Google Business Profile", "WhatsApp")
   - kpis: 2-3 KPIs (e.g. "10 new Google reviews", "30 catering enquiries", "200 covers on weekdays")
   Use restaurant language only. No marketing jargon.
"""

    # ─── Campaign ───
    campaign_template = "Promotion Campaign"
    campaign_prompt = """\
You are a marketing strategist presenting a campaign recommendation to a restaurant owner.

Restaurant: {business_name}
Goal: {goal}
Budget: {budget}

Here is the full campaign analysis from our strategy team:
{campaign}

Create a campaign preview that feels like a presentation deck. Include:

1. **reply**: A 2-3 sentence conversational pitch for this campaign. Speak as "I". \
Make the owner excited but honest. Never use jargon.

2. **preview**: A campaign preview with:
   - title: A catchy campaign title (e.g. "Hyderabad's Best Biryani Tour")
   - hero_image_concept: Describe what the hero image should show (food-focused, 1 sentence)
   - video_concept: Describe a 30-second video concept (food prep or customer reaction)
   - post_ideas: 5 specific post ideas (e.g. "Behind-the-scenes: how we marinate the chicken for 12 hours")
   - estimated_reach: e.g. "15,000-25,000 people in your area"
   - expected_enquiries: e.g. "30-50 catering enquiries in the first month"
   - budget_estimate: e.g. "₹15,000/month (₹500/day)"
   - why_this_campaign: 2-3 sentences explaining why this works for a restaurant
   - confidence: 0-100
   - expected_benefit: 1 sentence on what they'll get
   - risks: 2-3 risks (e.g. "Slow first week while ads learn your audience")
   - alternative: 1 sentence backup approach

Use restaurant language only. No jargon.

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
    recommendations_prompt = "Be specific to their cuisine and service style. A Hyderabadi biryani restaurant's plan should look different from a Mumbai cafe's plan."

    # ─── Creative Directions ───
    creative_directions_prompt = """\
Generate exactly 3 distinct creative directions for this restaurant campaign. \
Each direction must take a genuinely different angle — do NOT produce three \
variants of the same idea. Use restaurant language only. No jargon. Focus on \
food, appetite appeal, local pride, and the dining experience.

For each direction provide:
- id: A short slug (e.g. "signature_dish_hero", "local_pride", "value_combo")
- hook: A 1-sentence attention-grabber that makes people hungry
- angle: 1 sentence describing the strategic angle (what makes this direction different)
- tone: 2-3 words describing the tone (e.g. "Mouth-watering and warm", "Bold and festive")
- sample_headline: One sample ad headline for this direction
- sample_cta: One sample call-to-action for this direction (e.g. "Order now on Swiggy")
"""

    # ─── Hook Patterns ───
    hooks_prompt = """\
Generate 5 hook patterns for this restaurant campaign — one each for: question, \
stat, story, contrarian, aspiration. Each hook must be a single sentence that \
makes people hungry and stops the scroll. Use restaurant language only — no \
jargon. Focus on food, appetite appeal, local pride, and the dining experience. \
The "why_it_works" field should explain the psychological trigger in one \
sentence (e.g. sensory craving, nostalgia, social proof, FOMO).
"""

    # ─── Audience Psychology ───
    audience_psychology_prompt = """\
Analyse the psychology of this restaurant's diners. Focus on taste, value, and \
the social experience of dining. Motivations should centre on flavour, \
convenience, socialising, and treating oneself. Objections often involve price, \
wait times, hygiene, and distance. Emotional triggers include craving, \
nostalgia, social belonging, and indulgence. The decision style is typically \
spontaneous and socially influenced.
"""

    # ─── Offers ───
    offers_prompt = """\
Generate 3 engineered offers for this restaurant campaign using pricing \
psychology. Use restaurant-appropriate techniques: combo meals (bundling a \
main + side + drink for perceived value), happy hour (scarcity with a \
time-limited discount), family bundle (bundling for groups at a price anchor), \
loss-aversion (\"don't miss our weekend special\"), and decoy pricing (a \
premium thali that makes the standard combo look like a great deal). Offers \
should make people hungry and feel like a smart choice — focus on appetite \
appeal, value, and the dining experience.
"""

    # ─── Pricing Psychology ───
    pricing_psychology_prompt = """\
Generate 3 pricing presentations for this restaurant campaign. Use charm \
pricing (₹99 instead of ₹100 on menu items), tiered pricing \
(solo/duo/family combo meals), bundling (main + side + drink combos for \
perceived value), anchoring (a premium thali that makes the standard combo \
look like a great deal), and loss-leader (a low-margin starter or drink to \
draw diners in). Presentations should make people hungry and feel like a \
smart choice — focus on appetite appeal, value, and the dining experience.
"""

    # ─── Seasonal ───
    seasonal_prompt = """\
Generate seasonal marketing ideas for this restaurant tied to the target \
months. Consider festive menus for major festivals (Diwali, Eid, Christmas, \
Pongal, etc.), seasonal ingredients and dishes (monsoon comfort food, winter \
warmers, summer coolers), and seasonal dining occasions (Valentine's Day \
couples dinner, Mother's Day brunch, New Year feast). Ideas should leverage \
festive menus and seasonal cravings to drive footfall and orders.
"""

    # ─── Local ───
    local_prompt = """\
Generate local marketing ideas for this restaurant. Consider hosting or \
sponsoring local food events, partnering with nearby complementary businesses \
(ice cream shop, cinema, gym), hyper-local ad targeting (within 3-5 km \
radius), and local SEO / Google Business Profile optimisation for "restaurants \
near me" searches. Ideas should drive footfall and dine-in visits. Focus on \
the neighbourhood and community around the restaurant.
"""

    # ─── Differentiation ───
    differentiation_prompt = """\
Generate competitor differentiation entries for this restaurant. Identify \
common claims competing restaurants make (e.g. "biggest portions", "fastest \
delivery", "cheapest prices", "most authentic") and how this restaurant \
counters them with genuine evidence. Focus on what makes this restaurant \
uniquely valuable — recipe authenticity, ingredient quality, cooking method, \
or dining experience. Avoid naming specific competitors; use generic \
competitor claims instead. Focus on taste, quality, and food.
"""

    # ─── Strategy ───
    strategy_prompt = """\
A good strategy for a restaurant drives covers, orders, or repeat visits — \
not just awareness. The primary strategy should be the most reliable way to \
fill tables or boost orders within the budget (e.g. a signature-dish-led \
Instagram campaign with a time-limited combo offer). The alternative should \
pursue the same goal via a different lever (e.g. local SEO + Google Business \
Profile optimisation instead of paid social, or a catering/ bulk-order push \
instead of dine-in). The contrarian should take an unconventional angle most \
competing restaurants would ignore (e.g. a loyalty-first community play, a \
polarising "only our worst dish is on discount" campaign, or a counter-\
seasonal menu launch). Strategies must be genuinely different — not three \
variations of the same promo. Consider footfall vs delivery mix, cuisine \
saturation, and weekday vs weekend demand when choosing the primary.
"""

    # ─── Dashboard ───
    dashboard_widgets = [
        WidgetSpec("kpi_grid", "Your restaurant at a glance"),
        WidgetSpec("quick_actions", "Grow your restaurant"),
        WidgetSpec("approvals", "Waiting for your approval"),
        WidgetSpec("promotions", "Today's promotion"),
        WidgetSpec("pipeline", "Your campaigns"),
    ]

    quick_actions = [
        ActionCardSpec("Create My Campaign", "We'll build your marketing campaign — tailored for your restaurant. Takes 30 seconds.", "/app/brands/{brand_id}/campaigns/new", "Zap", "accent"),
    ]

    # ─── Memory ───
    brand_graph_schema = {
        "type": "object",
        "properties": {
            "cuisine": {"type": "string"},
            "location": {"type": "string"},
            "signature_dishes": {"type": "array", "items": {"type": "string"}},
            "service_style": {"type": "string"},
            "price_range": {"type": "string"},
            "audience": {"type": "string"},
            "goals": {"type": "array", "items": {"type": "string"}},
            "additional_context": {"type": "string"},
        },
    }
    memory_namespace = "business.restaurant"

    # ─── Conversation ───
    conversation_role = "marketing strategist"
    forbidden_jargon = ["ROAS", "CPA", "CTR", "funnel", "TOFU"]
    greeting_template = (
        "Hey! I'm CURV AI — your marketing strategist. Tell me about your restaurant. "
        "What cuisine do you serve, where are you located, and what do you want to "
        "achieve? The more you share, the better I can help."
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
            NavItemSpec("My Restaurant", "/app/brands", "UtensilsCrossed"),
            NavItemSpec("Channels", "/app/channels", "Share2"),
            NavItemSpec("Content Calendar", "/app/calendar", "Calendar"),
            NavItemSpec("Customer Reviews", "/app/reviews", "Star"),
        ]),
        NavSectionSpec("Settings", [
            NavItemSpec("Settings", "/app/settings", "Settings"),
            NavItemSpec("Upgrade", "/app/pricing", "Crown"),
        ]),
    ]

    tools = []
