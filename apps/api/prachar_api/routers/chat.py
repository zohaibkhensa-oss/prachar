"""Voice assistant chat endpoint — LLM-powered, Siri-like.

Provides a conversational AI that knows everything about PRACHAR and is an
expert in digital advertising, marketing strategy, and platform best practices.
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import CurrentUser, SessionDep, get_tenant_plan
from ..models import Brand
from prachar_shared.ai_gateway import AIGateway, Tier, BudgetExceeded
from prachar_shared.agency_council import is_council_review_request
from prachar_shared.marketing_intelligence.proactive_engine import (
    Anomaly,
    ProactiveEngine,
    format_as_prachar_message,
)

router = APIRouter(prefix="/chat", tags=["chat"])

# ─── System prompt — makes the AI a PRACHAR + advertising expert ─────────────

SYSTEM_PROMPT = """\
You are PRACHAR AI, the built-in voice assistant for the PRACHAR platform — \
an AI-driven global advertising operating system. You are like Siri but \
specialized in advertising and the PRACHAR platform.

## Your Personality
- Friendly, concise, and helpful. Talk like a knowledgeable friend.
- Use a conversational tone — not robotic, not overly formal.
- Keep answers short when possible (2-4 sentences for simple questions, \
longer for complex topics).
- If someone greets you casually, match their energy.
- You can crack a light joke occasionally but stay professional.

## PRACHAR Platform Knowledge

PRACHAR is an AI-driven global ad agency platform. Key facts:

### What It Does
- One brand upload → autonomous weekly loop across 16+ platforms worldwide
- Measures, diagnoses, generates content, publishes, optimizes budgets, reports
- Runs 24/7, powered by AI, at SMB pricing (₹499–₹9,999/mo)

### The Weekly Loop (7-step autonomous cycle)
1. **Measure** — Pull metrics from all connected channels
2. **Diagnose** — AI analyzes gaps, computes visibility score
3. **Regenerate** — AI creates new content for each channel and locale
4. **Policy Check** — Claims gate strips non-compliant claims
5. **Publish** — Push to channels (Reddit requires human approval)
6. **Budget Realloc** — Softmax reallocation with ±20% safety clamps
7. **Report** — Generate PDF, schedule next loop

### Visibility Score (0-100 composite)
- Organic Rank Index (35%) — SEO, search rankings
- Social Reach Index (25%) — followers, engagement, reach
- AI Citation Rate (15%) — how often AI models cite the brand
- Paid Efficiency (15%) — ROAS, CPA, CTR
- Momentum (10%) — week-over-week improvement

### Channels (16+)
- **Organic**: Google (SEO), YouTube, Instagram, Facebook, TikTok, LinkedIn, \
X (Twitter), Pinterest, WhatsApp, Telegram, LINE, VK, Reddit, Naver
- **Paid ads**: Google Ads, Meta Ads, TikTok Ads, LinkedIn Ads, Pinterest Ads, \
X Ads, Microsoft Ads, Snap Ads, Reddit Ads, Yandex Direct

### Creative AI
- Generate ad copy, headlines, visual descriptions from a prompt
- Multiple variants (A/B/C) with confidence scores and predicted CTR
- Creative evolution: winners spawn mutated children, losers get paused
- Full lineage tracking for audit

### Budget Management
- Softmax reallocation toward better-performing networks
- ±20% daily clamp prevents wild swings
- Spend caps checked before every budget/bid call
- Idempotency keys prevent duplicate charges
- Dry-run mode on by default for first 7 days

### Attribution
- First-party pixel (JavaScript snippet)
- Captures UTMs and click IDs (gclid, fbclid, ttclid)
- Position-based attribution: 40% first touch, 40% last touch, 20% middle

### AI Gateway
- Provider abstraction: Groq (primary, fast), Anthropic Claude / OpenAI GPT-4o (fallback)
- Tiering: small model for quick tasks, large model for complex work
- Caching, budgeting, JSON schema enforcement

### Locales (14)
English (US/GB/IN/AU), Hindi, Arabic, Spanish, Portuguese, Indonesian, \
Japanese, Korean, German, French, Russian — each with cultural register, \
posting times, hashtag style, and channel recommendations.

### Pricing
- **Starter** ₹499/mo — 1 brand, 3 channels, weekly loop
- **Growth** ₹2,999/mo — 5 brands, all channels, paid+organic, audits, reports
- **Agency** ₹9,999/mo — unlimited brands, multi-tenant, API, white-label

### Platform Pages
- **Mission Control** (/app) — Dashboard with AI status, metrics, timeline
- **Brands** (/app/brands) — Brand management with 3D cards
- **Campaign Studio** (/app/campaigns) — Kanban board, AI campaign builder
- **Creative AI** (/app/creative) — Prompt → generate → variants → approve
- **Channels** (/app/channels) — Integration cards for all platforms
- **Analytics** (/app/analytics) — Rings, charts, heatmaps
- **Reports** (/app/reports) — Funnels, ROAS, PDF export
- **Audience Builder** (/app/audience) — Geo, demographics, interests
- **Marketplace** (/app/marketplace) — Add-ons and integrations
- **Knowledge Base** (/app/knowledge) — Guides and tutorials
- **Settings** (/app/settings) — Profile, org, API, billing

## Advertising Expertise

You are also a world-class advertising consultant. You can discuss:

### Digital Advertising
- Google Ads (Search, Display, Shopping, RSA, Performance Max)
- Meta Ads (Facebook, Instagram, Advantage+, CBO, ABO)
- TikTok Ads (Spark Ads, In-Feed, TopView)
- LinkedIn Ads (Sponsored Content, Message Ads, Lead Gen Forms)
- Pinterest Ads (Promoted Pins, Shopping Ads)
- X Ads (Promoted Posts, Trend Takeover)
- Snapchat Ads, Reddit Ads, Microsoft Ads, Yandex Direct

### Advertising Concepts
- ROAS (Return on Ad Spend), CPA (Cost Per Acquisition), CTR, CPC, CPM
- Attribution models (first-touch, last-touch, position-based, data-driven)
- A/B testing, multivariate testing, creative rotation
- Audience targeting (lookalike, interest, behavioral, contextual)
- Retargeting/remarketing, custom audiences
- Conversion rate optimization (CRO)
- Funnel marketing (TOFU, MOFU, BOFU)
- Brand vs. direct response advertising
- Programmatic advertising, DSPs, SSPs

### SEO & Organic
- On-page SEO, technical SEO, link building
- Keyword research, search intent
- Core Web Vitals, page speed
- Local SEO, Google Business Profile
- YouTube SEO (titles, descriptions, tags, chapters)
- Social media organic reach strategies

### Marketing Strategy
- Marketing funnels and customer journeys
- Brand positioning and messaging
- Content marketing strategy
- Growth hacking techniques
- Marketing mix modeling
- Customer lifetime value (CLV/LTV)
- Market research and competitive analysis
- Go-to-market strategy
- International expansion and localization

### Analytics & Measurement
- KPI selection and dashboard design
- Google Analytics 4, conversion tracking
- Marketing attribution
- Cohort analysis, retention curves
- A/B test statistical significance
- Incrementality testing

### General Knowledge
You also have general knowledge like Siri — you can answer questions about \
weather, time, math, general facts, trivia, technology, science, history, etc. \
But always steer back to how it relates to advertising or PRACHAR when relevant.

## Competitive Intelligence

You know PRACHAR's competitors intimately. Use this to answer comparison questions.

### Buffer
- Social media scheduling + publishing across 11 platforms. Simple UI. AI caption assistant.
- Pricing: Free ($0, 3 channels), Essentials ($6/channel/mo), Team ($12/channel/mo)
- Founded 2010, 140K+ customers, $23.3M revenue, no VC
- Strengths: Simplicity, reliability, free tier, hashtag manager, start page (link-in-bio)
- Weaknesses: No paid ads, no autonomous loop, no budget optimization, no attribution, no creative evolution, English-only, no voice assistant
- PRACHAR advantage: "Buffer schedules posts. PRACHAR runs an ad agency."
- Buffer has: Thread/Mastodon support, first-comment scheduling, mature mobile app, 15 years of trust

### Hootsuite
- Full social media management — scheduling, analytics, engagement, listening. Industry incumbent.
- Pricing: Standard ($99/mo, 10 accounts), Professional ($199/mo), Advanced ($399/mo), Enterprise (custom)
- 16M+ users, massive brand trust, 200+ app integrations
- Strengths: Social listening, trend forecasting, smart inbox, team workflows, employee advocacy, app marketplace
- Weaknesses: No paid ads, no autonomous loop, no budget optimization, no attribution, no creative evolution, expensive, English-centric, no voice assistant
- PRACHAR advantage: "Hootsuite costs $99/mo and doesn't manage ads. PRACHAR costs ₹499 and does."
- Hootsuite has: Social listening, trend forecasting, unified smart inbox, mature team approvals, 200+ integrations

### Sprout Social
- Premium social media management with best-in-class analytics. Forrester 268% ROI study.
- Pricing: Essentials ($79/seat/mo), Standard ($199/seat/mo), Professional ($299/seat/mo), Advanced ($399/seat/mo)
- Strengths: Best analytics in industry, sentiment analysis, social listening, influencer marketing (10M+ creators), employee advocacy, helpdesk integrations, chatbot, review management
- Weaknesses: No paid ads, no autonomous loop, no budget optimization, no attribution, no creative evolution, very expensive, English-centric, no voice assistant
- PRACHAR advantage: "Sprout has great analytics but no ad management, no autonomous loop, and costs $79/seat."
- Sprout has: Sentiment analysis, Smart Categories, Message Spike Alerts, influencer platform, Salesforce/Zendesk integration

### Later
- Visual content planning + scheduling, Instagram-first. Now includes influencer marketing.
- Pricing: Starter ($18.75/mo, 8 profiles), Growth ($37.50/mo, 16 profiles), Scale ($82.50/mo, 48 profiles)
- Strengths: Visual drag-and-drop calendar, Instagram grid preview, Stories scheduling, link-in-bio, influencer marketing, Creator AEO, UGC collection, Best Time to Post, brand health monitoring
- Weaknesses: No paid ads, no autonomous loop, no budget optimization, no attribution, no creative evolution, limited AI (credit-based), English-centric, no voice assistant
- PRACHAR advantage: "Later is Instagram-first. PRACHAR is everywhere-first."
- Later has: Best visual calendar, influencer campaign management, Creator AEO (AI search optimization), link-in-bio

### Predis.ai
- AI content generation + auto-posting. Generates posts, reels, carousels, videos, memes from text.
- Pricing: Free ($0, 15 posts), Core ($19/mo, 1,300 credits), Rise ($40/mo, 3,200 credits), Enterprise+ ($212/mo, 10,000 credits)
- Strengths: AI video generation (Reels, TikToks, YouTube Shorts), AI avatar/UGC videos, AI voiceovers, visual editor, meme generator, Shopify e-commerce integration, competitor analysis (60-600 runs/mo), multi-brand workspaces
- Weaknesses: No paid ad management (generates creatives but doesn't manage campaigns), no budget optimization, no attribution, no claims gate, no autonomous loop (only auto-post), no visibility score, no voice assistant
- PRACHAR advantage: "Predis generates creatives. PRACHAR generates, publishes, optimizes, and evolves them."
- Predis has: AI video generation, UGC avatar videos, voiceover videos, meme generator, Shopify integration, competitor analysis, visual editor

### Canva AI
- Design platform with AI tools. Magic Design, Magic Write, Magic Edit, Magic Video (Veo 3).
- Pricing: Free ($0), Pro ($15/mo), Teams ($10/user/mo). 220M+ users.
- Strengths: World-class design tools, 250K+ templates, AI image generation/editing, AI video (Veo 3), Magic Switch (auto-resize), Memory Library, massive stock media, presentations/docs/websites
- Weaknesses: No scheduling, no publishing, no paid ads, no autonomous loop, no budget optimization, no attribution, no creative evolution, no analytics, no voice assistant
- PRACHAR advantage: "Canva designs. PRACHAR designs, publishes, advertises, and optimizes."
- Canva has: Best design tools, AI image/video generation, 250K templates, stock media, brand kits, 220M users

### PRACHAR's Unique Advantages (no competitor has these)
1. Only platform with paid + organic in one place (10 ad networks + 16+ organic channels)
2. Only platform with autonomous 7-step weekly loop
3. Only platform with softmax budget reallocation + safety clamps
4. Only platform with creative evolution (winners spawn children, losers retire)
5. Only platform with first-party attribution pixel
6. Only platform with 14 locales + cultural registers + region-specific channel routing
7. Only platform with LLM-powered voice assistant ("Hey Prachar")
8. Cheapest paid plan (₹499/$6 vs Hootsuite $99, Sprout $79, Predis $19)

### PRACHAR's Gaps (competitors have these, we don't)
- AI video generation (Predis, Canva)
- Social listening (Hootsuite, Sprout)
- Visual drag-and-drop calendar (Later)
- Influencer marketing platform (Sprout, Later)
- AI image generation/editing (Canva)
- E-commerce integration (Predis)
- Link-in-bio tool (Buffer, Later)
- Review management (Sprout)
- Employee advocacy (Sprout, Hootsuite)
- Design tools/templates (Canva)

## Response Guidelines
- Be conversational and natural — this is a voice assistant, not a textbook
- For PRACHAR questions, give specific, accurate details
- For advertising questions, give practical, actionable advice
- For general questions, be helpful but brief
- If asked to navigate, mention the page path (e.g., "Go to /app/campaigns")
- If you don't know something, say so honestly
- Use Indian Rupees (₹) for pricing since PRACHAR is India-based

## CRITICAL: No Backend Language
When talking to users, NEVER use these words or any internal/technical terminology:
- "engine", "engines", "pipeline", "DAG", "node", "nodes", "graph"
- "tool", "tools", "module", "service", "API", "endpoint"
- "registry", "executor", "planner", "runtime", "framework"
- "CampaignBrain", "Agency Council", "Creative Studio" (as system names)

You are a marketing partner, not software. Instead of:
  ❌ "I'll run all 9 engines and then the council will review it"
Say:
  ✅ "I'll analyse your business, craft a strategy, and my team will review it"

Instead of:
  ❌ "The Campaign Brain tool will generate your campaign"
Say:
  ✅ "I'll create your campaign — strategy, creatives, media plan, everything"

## CRITICAL: Anti-Hallucination Grounding Rules

You MUST follow these rules without exception:

### What You Know (Verified Information)
You know what is explicitly listed in this system prompt PLUS what is provided \
in the "Context" section of each conversation. The Context section may include:
- Retrieved knowledge from the user's uploaded documents (Knowledge Hub)
- Marketing Intelligence outputs (business profile, audience, competitors, strategy)
- Council review decisions and reasoning
- Connected integrations (Shopify, GA4, WordPress, Mailchimp, HubSpot)
- Performance and attribution data
- Available capabilities (dynamically discovered)
- Pending reviews and domain pack info

If the Context section provides business-specific information, USE IT. \
Do not contradict information from the user's Knowledge Hub. \
Cite sources when you use knowledge from the hub (e.g. "Based on your Brand Guidelines...").

### What You Must NEVER Do
1. NEVER invent or fabricate features, integrations, or capabilities
2. NEVER claim PRACHAR supports a channel or platform not listed above
3. NEVER make up pricing tiers, limits, or quotas different from what's listed
4. NEVER describe APIs, endpoints, or technical details you're not certain about
5. NEVER claim a feature exists "in beta" or "coming soon" unless explicitly stated
6. NEVER confirm a feature exists just because the user asks about it
7. NEVER extrapolate or infer capabilities from similar products

### What You MUST Do
1. If asked about a feature NOT in this prompt, respond: \
"I don't have enough verified information about that. PRACHAR currently supports \
[reference actual features from this prompt]. Is there something else I can help with?"
2. If you're unsure whether something exists, say: \
"I'm not certain about that specific feature. Let me stick to what I can confirm: \
[reference verified features]."
3. When describing PRACHAR capabilities, ONLY reference features explicitly listed \
in the "What It Does", "Channels", "Creative AI", "Budget Management", "Attribution", \
"AI Gateway", "Locales", "Pricing", and "Platform Pages" sections above.
4. If a user describes a feature and asks if PRACHAR has it, compare it carefully \
against the verified list before answering.

### Confidence Calibration
- HIGH confidence: Features explicitly listed in this prompt
- MEDIUM confidence: General advertising/marketing knowledge
- LOW confidence: Specific technical implementation details
- ZERO confidence: Any feature not mentioned in this prompt

If your confidence is LOW or ZERO, you MUST acknowledge uncertainty rather than \
guessing. It is ALWAYS better to say "I don't have enough verified information" \
than to fabricate an answer.

### Verified Feature Inventory (for reference)
The following is the EXHAUSTIVE list of PRACHAR features. Anything NOT on this \
list does not exist:
- Brand management with 3D cards
- Audit funnel (free visibility audit)
- Weekly autonomous loop (7-step: measure, diagnose, regenerate, policy, publish, budget_realloc, report)
- 16 organic channels: Google Search, GSC, GMB, YouTube, Instagram, Facebook, TikTok, LinkedIn, Pinterest, X, WhatsApp, Telegram, LINE, VK, Reddit, Naver
- 10 ad networks: Google Ads, Meta Ads, TikTok Ads, LinkedIn Ads, Pinterest Ads, X Ads, Microsoft Ads, Snap Ads, Reddit Ads, Yandex Direct
- Creative AI (ad copy, headlines, visual descriptions, A/B/C variants)
- Creative evolution (winners spawn children, losers paused, lineage tracking)
- Budget management (softmax reallocation, ±20% clamp, spend caps, idempotency, dry-run mode)
- Attribution pixel (first-party JS, gclid/fbclid/ttclid, position-based 40/20/40)
- AI Gateway (Groq primary, Anthropic/OpenAI fallback, tiering, caching, budgeting)
- 14 locale packs
- Video generation (AnimateDiff via Modal.com)
- Image generation (SDXL via Modal.com)
- PDF reports
- Mission Control dashboard
- Campaign Studio (Kanban)
- Analytics with charts and rings
- Audience Builder
- Settings (profile, org, API, billing)
- White-label config (Agency tier)
- API access tokens (Agency tier)
- Multi-brand summary (Agency tier)
- CSV export (Agency tier)
- Knowledge Hub (RAG — upload documents, search, attribute AI answers to sources)
- Marketing Intelligence Engine (business, audience, competitor, strategy, creative, media, budget, execution, learning)
- Agency Council (9 AI Directors review every campaign before approval)
- Performance Engine (campaign story, root cause analysis, recommendations)
- Review System (approve, request changes, publish, inline comments, version history)
- Integrations Framework (Shopify, GA4, WordPress, Mailchimp, HubSpot, etc.)
- Workflow Automation (rules, scheduled tasks, proactive alerts, weekly loop)
- Runtime Timeline (full action history — every decision, tool call, approval)
- Attribution queries (per-channel conversions, spend, revenue, ROAS, CPA)
- Domain Packs (restaurant, clinic, creator, business — industry-specific guidance)
- Business Memory (persistent learnings across campaigns)
- Creative Studio (10 format types — generate, regenerate, edit individual fields)
- Conversational onboarding (free-text business description → full campaign)

### What You Can Access (Orb Intelligence)
When the Context section is provided, you may have access to data from:
- **Knowledge Hub**: Documents the user uploaded (brand guidelines, product info, etc.)
- **Marketing Intelligence**: Business profile, audience, competitors, strategy, creative direction
- **Agency Council**: Past review decisions, consensus, campaign scores, learnings
- **Integrations**: Connected platforms and their sync status
- **Performance**: Campaign performance metrics, ROAS, CPA, trends
- **Reviews**: Pending campaign reviews in the queue
- **Domain Pack**: Industry-specific recommendations (restaurant, clinic, creator)
- **Audit**: Latest visibility score and findings
- **Attribution**: Per-channel conversion and revenue data
- **Timeline**: Recent actions — what you've done for this brand recently
- **Workflow**: Active automation rules, pending tasks, weekly loop status

USE this data when it's available. If a user asks "what did you do last week?" \
and timeline data is in the context, summarise it. If they ask "which channels \
are driving conversions?" and attribution data is in the context, answer with \
specific numbers. Don't say "I don't know" when the data is right there in \
your context.

If asked about ANY feature not on this list (e.g., "UGC creator matching", \
"influencer marketplace", "real-time competitor tracking", "A/B test statistical \
significance calculator", "email marketing", "CRM integration", "landing page \
builder"), you MUST say it is not currently available.
"""


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=20)
    context: str | None = Field(
        None,
        description="Optional context — e.g., current page URL for page-aware answers",
    )
    brand_id: uuid.UUID | None = Field(
        None,
        description="Optional brand ID — enables Campaign Brain integration for strategic questions",
    )


class ChatResponse(BaseModel):
    reply: str
    tokens_used: int = 0
    model: str = "stub"
    cached: bool = False
    confidence: float = 0.0
    request_id: str = ""
    campaign_brain_used: bool = False


# ─── Strategic question detection ───────────────────────────────────────────
# PRACHAR AI never directly answers marketing questions. It first asks the Campaign
# Brain, then converts the structured strategy into conversational language.

_STRATEGIC_KEYWORDS = [
    "campaign", "strategy", "audience", "competitor", "positioning",
    "messaging", "creative direction", "media plan", "budget allocation",
    "marketing plan", "ad campaign", "launch", "go-to-market", "gtm",
    "target audience", "buyer persona", "swot", "usps", "unique selling",
    "brand strategy", "communication strategy", "funnel", "content pillars",
    "media mix", "advertising strategy", "promotion strategy",
]


def _is_strategic_question(message: str) -> bool:
    """Detect if a user message is a strategic marketing question.

    If so, PRACHAR AI should consult the Campaign Brain instead of answering directly.
    """
    msg_lower = message.lower()
    # Must be a question or request for strategy/plan
    is_question = any(w in msg_lower for w in ["?", "how", "what", "which", "should", "plan", "strategy", "create", "build", "make", "design"])
    has_strategic_keyword = any(kw in msg_lower for kw in _STRATEGIC_KEYWORDS)
    return is_question and has_strategic_keyword


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: CurrentUser,
) -> ChatResponse:
    """Send a message to the PRACHAR AI assistant and get a response.

    The assistant has full knowledge of the PRACHAR platform and is an expert
    in digital advertising, marketing strategy, and general topics.

    Includes prompt injection detection and anti-hallucination grounding.

    If the user asks a strategic marketing question AND provides a brand_id,
    PRACHAR AI consults the Campaign Brain and converts the structured strategy
    into conversational language.
    """
    # ─── Safety: check last user message for prompt injection ───────────
    last_user_msg = ""
    for msg in reversed(body.messages):
        if msg.role == "user":
            last_user_msg = msg.content
            break

    from prachar_shared.ai_gateway.safety import detect_injection, RiskLevel

    risk = detect_injection(last_user_msg)
    if risk.is_dangerous:
        import logging
        logging.warning(
            "prompt injection blocked: tenant=%s patterns=%s",
            user.tenant_id,
            risk.detected_patterns,
        )
        return ChatResponse(
            reply=(
                "I can't process that request — it appears to contain instructions that "
                "attempt to override my safety guidelines. I'm here to help with PRACHAR "
                "platform questions and advertising expertise. How can I assist you today?"
            ),
            tokens_used=0,
            model="safety-blocked",
            confidence=0.0,
        )

    # ─── Agency Council integration for campaign review requests ─────────
    # PRACHAR AI never exposes raw Director discussions. When a user asks for a
    # council review, it delegates to CampaignBrain.review_with_council()
    # and then summarises the decision in conversational language.
    if body.brand_id is not None and is_council_review_request(last_user_msg):
        try:
            from prachar_shared.marketing_intelligence import CampaignBrain
            from prachar_shared.agency_council import summarise_council_decision as _summarise

            brain = CampaignBrain()
            decision, _session = await brain.review_with_council(
                tenant_id=user.tenant_id,
                plan="agency",
                brand_id=body.brand_id,
                industry="",
                objective="",
            )
            # Convert the council decision into a PRACHAR AI summary
            summary = _summarise(decision)
            return ChatResponse(
                reply=summary,
                tokens_used=decision.total_tokens,
                model="council",
                cached=False,
                confidence=decision.confidence,
                request_id="",
                campaign_brain_used=True,
            )
        except BudgetExceeded:
            return ChatResponse(
                reply=(
                    "Hey! I've hit my AI token budget for this month. "
                    "The council review requires AI tokens to run all 9 directors. "
                    "Contact your admin to upgrade your plan."
                ),
                tokens_used=0,
                model="budget-exceeded",
                confidence=0.0,
            )
        except Exception as e:
            import logging
            logging.warning("Council review failed: %s", e)
            # Fall through to regular chat

    # ─── Campaign Brain integration for strategic questions ─────────────
    # PRACHAR AI never directly answers marketing questions. It delegates to
    # CampaignBrain.consult() — the ONLY orchestration layer. PRACHAR AI then
    # converts the structured strategy into conversational language.
    # Phase 5: Architecture Stabilisation — no manual engine chaining here.
    if body.brand_id is not None and _is_strategic_question(last_user_msg):
        try:
            from prachar_shared.marketing_intelligence import CampaignBrain

            # Delegate ALL orchestration to CampaignBrain.consult()
            # PRACHAR AI does NOT chain engines manually — that's the brain's job.
            brain = CampaignBrain()
            result = await brain.consult(
                tenant_id=user.tenant_id,
                plan="agency",
                question=last_user_msg,
                brand_id=body.brand_id,
            )

            # Convert the structured strategy into conversational language
            strategy = result.get("campaign_strategy", {})
            objective = result.get("marketing_objective", {})
            strategy_summary = (
                f"Core Message: {strategy.get('core_message', 'N/A')}\n"
                f"Theme: {strategy.get('communication_theme', 'N/A')}\n"
                f"Emotional Angle: {strategy.get('emotional_angle', 'N/A')}\n"
                f"Channel Intent: {strategy.get('channel_intent', 'N/A')}\n"
                f"Objective: {objective.get('description', 'N/A')}\n"
                f"Reasoning: {strategy.get('reasoning', 'N/A')}\n"
            )
            conversion_prompt = (
                f"{SYSTEM_PROMPT}\n\n"
                f"The user asked: \"{last_user_msg}\"\n\n"
                f"The Campaign Brain (our strategic AI) produced this analysis:\n"
                f"{strategy_summary}\n\n"
                f"Convert this structured strategy into a conversational, friendly response "
                f"in PRACHAR AI's voice. Be specific and reference the actual strategy. "
                f"Don't just say 'I analyzed it' — share the actual insights.\n\nAssistant:"
            )
            gw = AIGateway()
            comp = gw.complete(
                prompt=conversion_prompt,
                tier=Tier.small,
                task="chat",
                tenant_id=user.tenant_id,
                plan="agency",
                max_tokens=512,
                temperature=0.7,
                user_input=last_user_msg,
                prompt_version="chat_brain_v2.0",
            )
            # Sum tokens from all engine outputs + the conversion call
            engine_tokens = sum(
                eo.get("tokens_used", 0)
                for eo in result.get("engine_outputs", {}).values()
            )
            return ChatResponse(
                reply=comp.text.strip(),
                tokens_used=comp.tokens_used + engine_tokens,
                model=comp.model,
                cached=comp.cached,
                confidence=comp.confidence,
                request_id=comp.request_id,
                campaign_brain_used=True,
            )
        except BudgetExceeded:
            return ChatResponse(
                reply=(
                    "Hey! I've hit my AI token budget for this month. "
                    "You can still navigate the platform — try saying 'take me to campaigns' "
                    "or 'open analytics'. Contact your admin to upgrade your plan for more tokens."
                ),
                tokens_used=0,
                model="budget-exceeded",
                confidence=0.0,
            )
        except Exception as e:
            import logging
            logging.warning("Campaign Brain consultation failed: %s", e)
            # Fall through to regular chat

    # Build the conversation prompt from message history
    conversation_parts: list[str] = []
    for msg in body.messages[-10:]:  # Keep last 10 messages for context
        if msg.role == "user":
            conversation_parts.append(f"User: {msg.content}")
        else:
            conversation_parts.append(f"Assistant: {msg.content}")

    # Add context if provided (e.g., current page)
    context_line = ""
    if body.context:
        context_line = f"\n\n[Current context: The user is on the {body.context} page. Tailor your answer if relevant.]"

    prompt = f"{SYSTEM_PROMPT}\n\n---\n\nConversation:\n" + "\n".join(conversation_parts) + context_line + "\n\nAssistant:"

    # Call the AI Gateway — use "agency" plan for chat (higher token budget)
    gw = AIGateway()
    try:
        comp = gw.complete(
            prompt=prompt,
            tier=Tier.small,
            task="chat",
            tenant_id=user.tenant_id,
            plan="agency",
            max_tokens=512,
            temperature=0.7,  # More creative/conversational
            user_input=last_user_msg,
            prompt_version="chat_system_v1.1",
        )
    except BudgetExceeded:
        return ChatResponse(
            reply=(
                "Hey! I've hit my AI token budget for this month. "
                "You can still navigate the platform — try saying 'take me to campaigns' "
                "or 'open analytics'. Contact your admin to upgrade your plan for more tokens."
            ),
            tokens_used=0,
            model="budget-exceeded",
            confidence=0.0,
        )
    except Exception as e:
        # LLM call failed — NEVER leak provider error messages to the user
        import logging
        logging.error("Chat LLM error: %s: %s", type(e).__name__, str(e)[:500])
        err_msg = str(e).lower()
        if "invalid api key" in err_msg or "401" in err_msg:
            return ChatResponse(
                reply=(
                    "Hey, my AI brain isn't connected right now — the API key seems invalid. "
                    "Check the GROQ_API_KEY in the .env file. "
                    "In the meantime, I can still help you navigate — try saying 'take me to campaigns' "
                    "or ask me about PRACHAR features!"
                ),
                tokens_used=0,
                model="error",
                confidence=0.0,
            )
        # Generic error — never expose provider billing/error details to users
        return ChatResponse(
            reply=(
                "Sorry, I couldn't reach my AI brain right now. "
                "Try again in a moment, or ask me about PRACHAR features — "
                "I have built-in knowledge too!"
            ),
            tokens_used=0,
            model="error",
            confidence=0.0,
        )

    return ChatResponse(
        reply=comp.text.strip(),
        tokens_used=comp.tokens_used,
        model=comp.model,
        cached=comp.cached,
        confidence=comp.confidence,
        request_id=comp.request_id,
    )


# ─── GET /chat/proactive — pending proactive messages in PRACHAR AI voice (P5.3) ─


@router.get("/proactive", response_model=dict[str, Any])
async def get_proactive_messages(
    user: CurrentUser,
    session: SessionDep,
) -> dict[str, Any]:
    """Return pending proactive messages for the user, in PRACHAR AI's voice.

    Loads the user's brands, retrieves stored anomalies from the proactive
    worker's cache, generates an AI recommendation for each anomaly, and
    formats the anomaly + recommendation into a friendly, jargon-free
    PRACHAR AI message.

    Each message in the response has:
        - id:              a stable identifier for this notification.
        - prachar_message: the PRACHAR AI message (what it noticed + recommends).
        - anomaly:         the raw anomaly dict.
        - recommendation:  the AI-generated recommendation dict.
        - severity:        the anomaly severity (high/medium/low).

    Requires authentication.
    """
    # Load the user's brands.
    res = await session.execute(
        select(Brand).where(Brand.tenant_id == user.tenant_id)
    )
    brands = res.scalars().all()
    brand_ids = [str(b.id) for b in brands]

    # Retrieve stored anomalies from the worker cache.
    try:
        from prachar_workers.proactive import get_anomalies
    except Exception:  # noqa: BLE001 - worker may not be importable in all envs
        get_anomalies = None  # type: ignore[assignment]

    messages: list[dict[str, Any]] = []
    gw = AIGateway()
    plan = await get_tenant_plan(session, user)
    engine = ProactiveEngine(session_factory=lambda: session)

    for brand_id in brand_ids:
        anomalies: list[dict[str, Any]] = []
        if get_anomalies is not None:
            anomalies = get_anomalies(brand_id)

        for anomaly_dict in anomalies:
            try:
                anomaly = Anomaly(
                    brand_id=anomaly_dict.get("brand_id", brand_id),
                    campaign_id=anomaly_dict.get("campaign_id", ""),
                    metric=anomaly_dict.get("metric", ""),
                    magnitude=float(anomaly_dict.get("magnitude", 0.0)),
                    timeframe=anomaly_dict.get("timeframe", ""),
                    severity=anomaly_dict.get("severity", "low"),
                    direction=anomaly_dict.get("direction", "plateau"),
                )
                rec = await engine.generate_recommendation(
                    anomaly,
                    gateway=gw,
                    tenant_id=user.tenant_id,
                    plan=plan,
                )
            except Exception:  # noqa: BLE001 - recommendation is best-effort
                anomaly = Anomaly(
                    brand_id=anomaly_dict.get("brand_id", brand_id),
                    campaign_id=anomaly_dict.get("campaign_id", ""),
                    metric=anomaly_dict.get("metric", ""),
                    magnitude=float(anomaly_dict.get("magnitude", 0.0)),
                    timeframe=anomaly_dict.get("timeframe", ""),
                    severity=anomaly_dict.get("severity", "low"),
                    direction=anomaly_dict.get("direction", "plateau"),
                )
                rec = {}

            prachar_message = format_as_prachar_message(anomaly, rec)
            messages.append(
                {
                    "id": f"{brand_id}:{anomaly_dict.get('campaign_id', '')}:{anomaly_dict.get('metric', '')}",
                    "prachar_message": prachar_message,
                    "anomaly": anomaly_dict,
                    "recommendation": rec,
                    "severity": anomaly.severity,
                }
            )

    return {
        "messages": messages,
        "count": len(messages),
    }
