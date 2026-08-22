"""Clinic Domain Pack — for clinics, dental practices, medical practices.

This pack demonstrates that a new domain can be added by implementing ONE file
with ZERO core modifications. The universal pipeline is shared.

A clinic is a business subtype with domain-specific:
- KPIs (appointments, new patients, repeat patients, no-shows)
- Campaign template (Patient Acquisition Campaign)
- Dashboard widgets (today's appointments campaign, patient pipeline)
- Conversation behaviour (healthcare language, compliance-aware, no jargon)
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


class ClinicPack(BaseDomainPack):
    """The domain pack for clinics and medical practices."""

    id = "clinic"
    label = "Clinic Growth"
    customer_type = "business"
    emoji = "🏥"

    # ─── Discovery ───
    subtypes = [
        SubtypePreset("dental", "Dental Clinic", "🦷", "Get more patient appointments.", "dental"),
        SubtypePreset("dermatology", "Dermatology Clinic", "✨", "Get more skincare patients.", "dermatology"),
        SubtypePreset("general", "General Practice", "🩺", "Get more patients.", "general"),
        SubtypePreset("physiotherapy", "Physiotherapy", "💪", "Get more therapy bookings.", "physiotherapy"),
        SubtypePreset("vet", "Veterinary Clinic", "🐾", "Get more pet patients.", "vet"),
        SubtypePreset("ayurveda", "Ayurveda / Wellness", "🌿", "Get more wellness clients.", "ayurveda"),
    ]

    extraction_schema = {
        "type": "object",
        "properties": {
            "business_name": {"type": "string"},
            "specialty": {"type": "string"},
            "location": {"type": "string"},
            "services": {"type": "array", "items": {"type": "string"}},
            "audience": {"type": "string"},
            "goals": {"type": "array", "items": {"type": "string"}},
            "website": {"type": "string"},
            "social_handles": {"type": "array", "items": {"type": "string"}},
            "additional_context": {"type": "string"},
        },
    }

    extraction_prompt = """\
You are a clinic business analyst. Extract structured information from the \
owner's description of their clinic.

Owner said: "{message}"

Extract:
- business_name: The name of the clinic (if mentioned).
- specialty: Type of practice (e.g. "dental", "dermatology", "general", "physiotherapy").
- location: City or area.
- services: List of services offered (e.g. "dental checkups", "root canal", "teeth whitening").
- audience: Who the target patients are.
- goals: What the owner wants to achieve.
- website: Website URL (if mentioned).
- social_handles: Social media handles (if mentioned).
- additional_context: Anything else (years open, equipment, specialisations).

Respond as JSON only:
{{
  "business_name": "...",
  "specialty": "...",
  "location": "...",
  "services": ["..."],
  "audience": "...",
  "goals": ["..."],
  "website": "...",
  "social_handles": ["..."],
  "additional_context": "..."
}}
"""

    # ─── Goals ───
    default_goal = "get more patient appointments"
    goal_options = [
        "get more patient appointments",
        "promote a new treatment",
        "build trust and credibility",
        "reduce no-shows",
        "grow a specific service line",
    ]

    # ─── KPIs ───
    kpi_cards = [
        KpiCardSpec("appointments", "Appointments", "Calendar", "Booked this month"),
        KpiCardSpec("new_patients", "New patients", "UserPlus", "First-time visits"),
        KpiCardSpec("repeat_patients", "Repeat patients", "RefreshCw", "Returning patients"),
        KpiCardSpec("no_shows", "No-shows", "Clock", "Missed appointments"),
        KpiCardSpec("enquiries", "Enquiries", "MessageSquare", "Calls + WhatsApp + forms"),
        KpiCardSpec("reviews", "Reviews", "Star", "Google + Practo"),
    ]

    # ─── Growth Opportunities ───
    opportunity_prompt = """\
3. **growth_opportunities**: Exactly 5 growth opportunities, each with:
   - title: Short, action-oriented title (e.g. "Launch free first consultation")
   - description: 1-2 sentence description
   - business_impact: "High", "Medium", or "Low"
   - difficulty: "Easy", "Medium", or "Hard"
   - timeframe: e.g. "1-2 weeks", "1 month"
   Focus on clinic-specific opportunities: free first consultations, health camp \
   campaigns, patient education content, Google Business Profile, Practo/Justdial \
   listings, WhatsApp appointment reminders, referral programs, seasonal checkups.
   NEVER recommend guarantees of medical outcomes. Keep claims_gate in mind.
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
   - theme: A short theme (e.g. "Build your online presence")
   - objectives: 2-3 objectives
   - content: 2-3 content pieces (e.g. "5 Instagram posts on common dental myths", "Patient testimonial video")
   - offers: 1-2 offers (e.g. "Free first consultation", "20% off teeth cleaning this month")
   - channels: 2-3 channels (e.g. "Google", "Instagram", "WhatsApp")
   - kpis: 2-3 KPIs (e.g. "10 new Google reviews", "30 appointment bookings", "15 new patients")
   Use clinic language only. No marketing jargon. No medical claims or guarantees.
"""

    # ─── Campaign ───
    campaign_template = "Patient Acquisition Campaign"
    campaign_prompt = """\
You are a marketing strategist presenting a campaign recommendation to a clinic owner.

Clinic: {business_name}
Goal: {goal}
Budget: {budget}

Here is the full campaign analysis from our strategy team:
{campaign}

Create a campaign preview that feels like a presentation deck. Include:

1. **reply**: A 2-3 sentence conversational pitch for this campaign. Speak as "I". \
Make the owner excited but honest. Never use jargon. Never make medical claims.

2. **preview**: A campaign preview with:
   - title: A catchy campaign title (e.g. "Smile Brighter This Season")
   - hero_image_concept: Describe what the hero image should show (clinic/patient-focused, 1 sentence)
   - video_concept: Describe a 30-second video concept (patient experience or doctor intro)
   - post_ideas: 5 specific post ideas (e.g. "5 signs you need a dental checkup", "Patient testimonial: how root canal treatment went")
   - estimated_reach: e.g. "15,000-25,000 people in your area"
   - expected_enquiries: e.g. "30-50 appointment enquiries in the first month"
   - budget_estimate: e.g. "₹15,000/month (₹500/day)"
   - why_this_campaign: 2-3 sentences explaining why this works for a clinic
   - confidence: 0-100
   - expected_benefit: 1 sentence on what they'll get
   - risks: 2-3 risks (e.g. "Slow first week while ads learn your audience")
   - alternative: 1 sentence backup approach

Use clinic language only. No jargon. No medical claims or guarantees of outcomes.

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
    recommendations_prompt = "Be specific to their specialty. A dental clinic's plan should look different from a dermatology clinic's plan. Never recommend guarantees of medical outcomes."

    # ─── Creative Directions ───
    creative_directions_prompt = """\
Generate exactly 3 distinct creative directions for this clinic campaign. \
Each direction must take a genuinely different angle — do NOT produce three \
variants of the same idea. Use clinic language only. No jargon. No medical \
claims or guarantees of outcomes. Focus on trust, education, and care.

For each direction provide:
- id: A short slug (e.g. "trust_and_testimonials", "health_education", "first_visit_offer")
- hook: A 1-sentence attention-grabber (never fear-mongering, never medical claims)
- angle: 1 sentence describing the strategic angle (what makes this direction different)
- tone: 2-3 words describing the tone (e.g. "Caring and reassuring", "Informative and calm")
- sample_headline: One sample ad headline for this direction
- sample_cta: One sample call-to-action for this direction (e.g. "Book your free consultation")
"""

    # ─── Hook Patterns ───
    hooks_prompt = """\
Generate 5 hook patterns for this clinic campaign — one each for: question, \
stat, story, contrarian, aspiration. Each hook must be a single sentence that \
stops the scroll. Use clinic language only — no jargon, no medical claims or \
guarantees of outcomes. Focus on trust, education, and care. The \
"why_it_works" field should explain the psychological trigger in one sentence \
(e.g. health curiosity, empathy, authority, loss aversion).
"""

    # ─── Audience Psychology ───
    audience_psychology_prompt = """\
Analyse the psychology of this clinic's patients. Focus on trust, expertise, \
and convenience. Motivations should centre on health, relief, safety, and peace \
of mind. Objections often involve cost, fear, trust in the provider, and wait \
times. Emotional triggers include reassurance, empathy, authority, and hope. \
The decision style is typically cautious and research-driven. Never imply \
guaranteed outcomes or make medical claims.
"""

    # ─── Offers ───
    offers_prompt = """\
Generate 3 engineered offers for this clinic campaign using pricing \
psychology. Use clinic-appropriate techniques: first-visit discount (anchoring \
to make ongoing care feel accessible), package of sessions (bundling 3-5 \
sessions at a per-session discount), family checkup package (bundling for \
households), loss-aversion (\"early checkup saves costly treatment later\"), \
and decoy pricing (a comprehensive health package that makes the basic \
consult look affordable). Offers must feel trustworthy and caring — never \
fear-monger, never guarantee medical outcomes, never make medical claims. \
Focus on peace of mind, accessibility, and preventive care.
"""

    # ─── Pricing Psychology ───
    pricing_psychology_prompt = """\
Generate 3 pricing presentations for this clinic campaign. Use charm pricing \
(₹499 instead of ₹500 on consultations), tiered pricing (basic/standard/\
comprehensive checkup packages), bundling (3-5 session packages at a \
per-session discount), anchoring (a comprehensive health package that makes \
the basic consult look affordable), and loss-leader (a free or low-cost \
first consultation to draw patients in). Presentations must feel trustworthy \
and caring — never fear-monger, never guarantee medical outcomes, never make \
medical claims. Focus on peace of mind, accessibility, and preventive care.
"""

    # ─── Seasonal ───
    seasonal_prompt = """\
Generate seasonal marketing ideas for this clinic tied to the target months. \
Consider seasonal health checkups (monsoon immunity checks, winter flu \
prevention, summer hydration, back-to-school health screenings), festive \
season health packages, and seasonal health awareness campaigns. Ideas should \
leverage seasonal health concerns and preventive care moments. Never imply \
guaranteed outcomes or make medical claims. Focus on preventive care and \
seasonal health awareness.
"""

    # ─── Local ───
    local_prompt = """\
Generate local marketing ideas for this clinic. Consider hosting free health \
checkup camps in the community, partnering with nearby pharmacies or gyms, \
hyper-local ad targeting (within 5 km radius), and local SEO / Google \
Business Profile optimisation for "clinic near me" and "doctor near me" \
searches. Ideas should drive patient appointments and local awareness. Focus \
on the neighbourhood and community around the clinic. Never make medical \
claims or guarantee outcomes.
"""

    # ─── Differentiation ───
    differentiation_prompt = """\
Generate competitor differentiation entries for this clinic. Identify common \
claims competing clinics make (e.g. "most advanced equipment", "cheapest \
consultations", "fastest appointments", "most experienced") and how this \
clinic counters them with genuine evidence. Focus on what makes this clinic \
uniquely valuable — patient care, expertise, trust, technology, or \
convenience. Avoid naming specific competitors; use generic competitor claims \
instead. Never imply guaranteed outcomes or make medical claims. Focus on \
trust, care, and patient outcomes.
"""

    # ─── Strategy ───
    strategy_prompt = """\
A good strategy for a clinic builds trust and drives appointment bookings — \
never through fear or guaranteed outcomes. The primary strategy should be the \
most reliable way to attract new patients within the budget (e.g. a free first \
consultation offer paired with patient-testimonial content and local SEO). \
The alternative should pursue the same goal via a different lever (e.g. a \
health-education content series on Instagram instead of a direct offer, or a \
community health-camp instead of digital ads). The contrarian should take an \
unconventional angle most competing clinics would ignore (e.g. a membership / \
preventive-care subscription model, a polarising "why we don't discount" \
transparency campaign, or a referral-only growth play). Strategies must be \
genuinely different — not three variations of the same offer. Consider trust \
cycle length, patient lifetime value, and local competition density when \
choosing the primary. Never recommend strategies that guarantee medical \
outcomes or use fear-based messaging.
"""

    # ─── Dashboard ───
    dashboard_widgets = [
        WidgetSpec("kpi_grid", "Your clinic at a glance"),
        WidgetSpec("quick_actions", "Grow your clinic"),
        WidgetSpec("approvals", "Waiting for your approval"),
        WidgetSpec("appointments", "Today's appointments campaign"),
        WidgetSpec("pipeline", "Your campaigns"),
    ]

    quick_actions = [
        ActionCardSpec("Create My Campaign", "We'll build your patient acquisition campaign — tailored for your clinic. Takes 30 seconds.", "/app/brands/{brand_id}/campaigns/new", "Zap", "accent"),
    ]

    # ─── Memory ───
    brand_graph_schema = {
        "type": "object",
        "properties": {
            "specialty": {"type": "string"},
            "location": {"type": "string"},
            "services": {"type": "array", "items": {"type": "string"}},
            "audience": {"type": "string"},
            "goals": {"type": "array", "items": {"type": "string"}},
            "additional_context": {"type": "string"},
        },
    }
    memory_namespace = "business.clinic"

    # ─── Conversation ───
    conversation_role = "marketing strategist"
    forbidden_jargon = ["ROAS", "CPA", "CTR", "funnel", "TOFU"]
    greeting_template = (
        "Hey! I'm CURV AI — your marketing strategist. Tell me about your clinic. "
        "What's your specialty, where are you located, and what do you want to "
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
            NavItemSpec("My Clinic", "/app/brands", "Stethoscope"),
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
