"""Audience Intelligence Engine.

Determines primary and secondary audiences with buying intent, pain points,
demographics, psychographics, language, platforms, content preferences,
and buying journey mapping.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prachar_shared.ai_gateway import Completion, Tier

from .base import EngineOutput, IntelligenceEngine
from .domain_base import DomainModel


@dataclass
class AudienceProfile(DomainModel):
    """Structured audience understanding.

    Inherits from_dict()/validate()/schema_version() from DomainModel.
    Owned by AudienceIntelligenceEngine.
    """

    primary_audience: dict[str, Any] = field(default_factory=dict)
    secondary_audience: dict[str, Any] = field(default_factory=dict)
    buying_intent: str = ""
    pain_points: list[str] = field(default_factory=list)
    demographics: dict[str, Any] = field(default_factory=dict)
    psychographics: dict[str, Any] = field(default_factory=dict)
    language_preference: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    content_preferences: list[str] = field(default_factory=list)
    buying_journey: list[dict[str, Any]] = field(default_factory=list)
    psychographic_segments: list[dict[str, Any]] = field(default_factory=list)
    platform_behaviour: list[dict[str, Any]] = field(default_factory=list)
    segment_objections: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_audience": self.primary_audience,
            "secondary_audience": self.secondary_audience,
            "buying_intent": self.buying_intent,
            "pain_points": self.pain_points,
            "demographics": self.demographics,
            "psychographics": self.psychographics,
            "language_preference": self.language_preference,
            "platforms": self.platforms,
            "content_preferences": self.content_preferences,
            "buying_journey": self.buying_journey,
            "psychographic_segments": self.psychographic_segments,
            "platform_behaviour": self.platform_behaviour,
            "segment_objections": self.segment_objections,
        }


class AudienceIntelligenceEngine(IntelligenceEngine):
    """Analyzes the target audience for a business/campaign.

    Reasons like a senior planner at a global ad agency — combining
    demographic data, psychographic insight, and behavioral analysis.
    """

    ENGINE_NAME = "audience_intelligence"
    ENGINE_VERSION = "1.1.0"
    PROMPT_VERSION = "2.0.0"
    SCHEMA_VERSION = "1.1.0"
    TIER = Tier.large
    MAX_TOKENS = 3000
    TEMPERATURE = 0.3

    def _build_prompt(self, **kwargs: Any) -> str:
        business_profile = kwargs.get("business_profile", {})
        business_name = kwargs.get("business_name", "")
        goal = kwargs.get("goal", "")
        locale = kwargs.get("locale", "en-IN")
        additional_context = kwargs.get("additional_context", "")

        return f"""ROLE: You are a senior audience planner at a global advertising agency (WPP/Publicis).
You combine demographic data, psychographic insight, and behavioral analysis to
define audiences with the precision of a data scientist and the empathy of a
consumer psychologist. You think in segments, motivations, objections, and
platform-native behaviours — not just age and gender.

TASK: Define the primary and secondary audiences for this business. Go beyond
demographics into psychographics, buyer journey mapping, and platform-specific
behaviour patterns. Think like you are writing the audience section of an
award-winning strategy brief.

BUSINESS CONTEXT:
- Name: {business_name}
- Goal: {goal}
- Locale: {locale}
- Business Profile: {business_profile}
{f"- Additional Context: {additional_context}" if additional_context else ""}

REASONING PROCESS (follow this chain-of-thought before producing your answer):
Step 1 — DEMOGRAPHICS: Who are they? Age, gender, location, income, education, occupation, family status.
Step 2 — PSYCHOGRAPHICS: What do they VALUE? What are their lifestyles, attitudes, beliefs, aspirations, fears?
  Go beyond "interests" — identify the core values that drive purchase decisions (status, security,
  self-expression, belonging, achievement, convenience, sustainability, authenticity).
Step 3 — SEGMENTATION: Break the primary audience into 2-3 psychographic segments. Each segment should
  have distinct values, motivations, and objections. Not everyone in the same demographic thinks alike.
Step 4 — JOURNEY: Map the buyer journey: awareness → consideration → decision → retention.
  At each stage, identify the touchpoints, content needs, emotional state, and potential drop-off points.
Step 5 — PLATFORM BEHAVIOUR: How does this audience behave on each platform? What do they do on Instagram
  vs YouTube vs LinkedIn? When are they active? What content format do they consume on each?
Write your reasoning in the "reasoning" field showing this step-by-step analysis.

ANALYSIS REQUIREMENTS:
1. Primary Audience: The core segment most likely to convert. Include:
   - Age range, gender, location, income bracket, education
   - Occupation, family status, lifestyle
   - Psychographics: values, interests, attitudes, personality
   - Buying intent level (high/medium/low) with reasoning
2. Secondary Audience: A supplementary segment worth targeting.
3. Pain Points: 3-5 specific problems the audience faces that the business solves.
   Each pain point must be phrased from the customer's perspective ("I can't find..." not "customers lack...").
4. Platforms: Where this audience spends time (Instagram, LinkedIn, YouTube, etc.)
   with time-of-day patterns.
5. Content Preferences: What content formats resonate (video, carousel, long-form, etc.)
6. Buying Journey: Map the journey from awareness → consideration → decision → retention
   with touchpoints, content needs, and emotional state at each stage.
7. Language Preference: Preferred languages for communication.
8. Psychographic Segments: Break the audience into 2-3 psychographic segments. For each:
   - segment_name: A memorable label (e.g., "The Conscious Connoisseur", "The Convenience Seeker")
   - values: 3-5 core values that drive their decisions
   - lifestyle: How they live day-to-day
   - attitudes: Their attitudes toward the product category
   - motivations: What drives them to buy (aspirational, functional, emotional, social)
   - objections: What holds them back from buying (price, trust, time, complexity, social proof)
   - estimated_percentage: Rough share of the total audience (should sum to ~100%)
9. Platform Behaviour: For each major platform the audience uses:
   - platform: Name (Instagram, YouTube, LinkedIn, WhatsApp, etc.)
   - usage_pattern: How they use it (scrolling, searching, sharing, saving, commenting)
   - peak_times: When they are most active (specific hours + days)
   - content_format: What format works best (reels, carousels, stories, long-form video, text posts)
   - engagement_style: Passive scroller vs active engager vs creator
   - purchase_influence: How much does this platform influence their purchase decision? (high/medium/low)

LOCALE-AWARE GUIDANCE:
- India (en-IN/hi-IN): WhatsApp is the #1 communication channel. Instagram dominates 18-35.
  YouTube is the second search engine. Regional language content is exploding (Hindi, Tamil, Telugu, Marathi, Bengali).
  Consider Tier-2/3 city behaviour: price-sensitive, trust-driven, word-of-mouth heavy, festival-driven purchasing.
- US (en-US): TikTok is the discovery engine for Gen Z. Instagram for millennials. LinkedIn for B2B.
  Consider podcast consumption, Reddit for niche communities, Pinterest for planning/inspiration.
- Global: Adapt platform mix to local preferences (WeChat in China, LINE in Japan/Thailand, VK in Russia, KakaoTalk in Korea).

FEW-SHOT EXAMPLE (D2C Coffee — use as quality benchmark, do NOT copy):
- Psychographic Segments:
  - segment_name: "The Ritualist" (40% of audience)
    values: ["craftsmanship", "mindfulness", "quality over quantity", "sustainability"]
    lifestyle: "Slow mornings, reads with coffee, values process as much as outcome"
    attitudes: "Coffee is a ritual, not a caffeine delivery mechanism"
    motivations: "Aspirational — wants to feel like a connoisseur; emotional — the story behind the cup"
    objections: ["₹800/250g feels steep vs Blue Tokai ₹650", "Is direct trade actually verified?",
      "Will I taste the difference?"]
  - segment_name: "The Gifter" (25% of audience)
    values: ["thoughtfulness", "status", "uniqueness", "convenience"]
    lifestyle: "Busy professional, buys gifts that signal good taste"
    attitudes: "Premium coffee as a gift shows I know good things"
    motivations: "Social — wants the recipient to be impressed; functional — easy to order and ship"
    objections: ["Will it arrive on time?", "Is the packaging gift-worthy?", "What if they don't like coffee?"]
- Platform Behaviour:
  - platform: "Instagram"
    usage_pattern: "Saves recipes and aesthetic shots, shares Stories of coffee rituals"
    peak_times: "7-9 AM (morning ritual), 8-11 PM (evening scroll)"
    content_format: "Reels (discovery), Carousels (education), Stories (daily ritual)"
    engagement_style: "Active saver and sharer, low commenter"
    purchase_influence: "high — Instagram is the primary discovery channel"
  - platform: "YouTube"
    usage_pattern: "Searches 'how to brew pour-over', watches 10-min craft videos"
    peak_times: "Weekends 10 AM-2 PM"
    content_format: "Long-form (8-15 min) brewing tutorials, origin story documentaries"
    engagement_style: "Active watcher, occasional commenter, high subscriber loyalty"
    purchase_influence: "medium — builds trust but conversion happens on Instagram/website"

QUALITY RULES:
- Be specific, not generic. "Urban millennials aged 25-34 with disposable income"
  not "young people".
- Psychographic segments must be genuinely different — not the same persona with different labels.
- Pain points must be phrased from the customer's perspective.
- Platform behaviour must be specific to THIS audience, not platform-general.
- Every audience claim must have reasoning.
- Confidence 0.3-0.9 range.
- 3-5 recommendations for reaching this audience.

OUTPUT: JSON matching the schema. Include "reasoning", "confidence", and "recommendations".
"""

    def _build_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "primary_audience": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "age_range": {"type": "string"},
                        "gender": {"type": "string"},
                        "location": {"type": "string"},
                        "income_bracket": {"type": "string"},
                        "occupation": {"type": "string"},
                        "education": {"type": "string"},
                        "family_status": {"type": "string"},
                        "lifestyle": {"type": "string"},
                        "values": {"type": "array", "items": {"type": "string"}},
                        "interests": {"type": "array", "items": {"type": "string"}},
                        "buying_intent": {"type": "string"},
                    },
                },
                "secondary_audience": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "age_range": {"type": "string"},
                        "buying_intent": {"type": "string"},
                    },
                },
                "buying_intent": {"type": "string"},
                "pain_points": {"type": "array", "items": {"type": "string"}},
                "demographics": {
                    "type": "object",
                    "properties": {
                        "primary_age": {"type": "string"},
                        "primary_gender": {"type": "string"},
                        "primary_location": {"type": "string"},
                        "primary_income": {"type": "string"},
                    },
                },
                "psychographics": {
                    "type": "object",
                    "properties": {
                        "values": {"type": "array", "items": {"type": "string"}},
                        "attitudes": {"type": "array", "items": {"type": "string"}},
                        "lifestyle": {"type": "string"},
                    },
                },
                "language_preference": {"type": "array", "items": {"type": "string"}},
                "platforms": {"type": "array", "items": {"type": "string"}},
                "content_preferences": {"type": "array", "items": {"type": "string"}},
                "buying_journey": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "stage": {"type": "string"},
                            "description": {"type": "string"},
                            "touchpoints": {"type": "array", "items": {"type": "string"}},
                            "content_needs": {"type": "array", "items": {"type": "string"}},
                            "emotional_state": {"type": "string"},
                        },
                    },
                },
                "psychographic_segments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "segment_name": {"type": "string"},
                            "values": {"type": "array", "items": {"type": "string"}},
                            "lifestyle": {"type": "string"},
                            "attitudes": {"type": "string"},
                            "motivations": {"type": "string"},
                            "objections": {"type": "array", "items": {"type": "string"}},
                            "estimated_percentage": {"type": "number"},
                        },
                    },
                },
                "platform_behaviour": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "platform": {"type": "string"},
                            "usage_pattern": {"type": "string"},
                            "peak_times": {"type": "string"},
                            "content_format": {"type": "string"},
                            "engagement_style": {"type": "string"},
                            "purchase_influence": {"type": "string"},
                        },
                    },
                },
                "segment_objections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "segment": {"type": "string"},
                            "objection": {"type": "string"},
                            "counter_argument": {"type": "string"},
                        },
                    },
                },
                "reasoning": {"type": "string"},
                "confidence": {"type": "number"},
                "recommendations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "confidence": {"type": "number"},
                            "business_rationale": {"type": "string"},
                            "marketing_rationale": {"type": "string"},
                            "alternatives": {"type": "array", "items": {"type": "string"}},
                            "risks": {"type": "array", "items": {"type": "string"}},
                            "expected_outcome": {"type": "string"},
                            "evidence": {"type": "array", "items": {"type": "string"}},
                            "sources": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
            "required": ["primary_audience", "buying_intent", "reasoning", "confidence"],
        }

    def to_profile(self, output: EngineOutput) -> AudienceProfile:
        """Convert an EngineOutput to a typed AudienceProfile.

        Delegates to AudienceProfile.from_dict() — the model owns parsing.
        """
        return AudienceProfile.from_dict(output.result)  # type: ignore[return-value]
