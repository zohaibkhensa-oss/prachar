"""Creative Direction Engine.

Before any image/video is generated, determines visual style, mood, colour
palette, typography, photography style, motion style, brand consistency,
and creative references.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prachar_shared.ai_gateway import Completion, Tier

from .base import EngineOutput, IntelligenceEngine
from .domain_base import DomainModel


@dataclass
class CreativeDirection(DomainModel):
    """Creative direction for asset generation.

    Inherits from_dict()/validate()/schema_version() from DomainModel.
    Owned by CreativeDirectionEngine.
    """

    visual_style: str = ""
    mood: str = ""
    colour_palette: dict[str, Any] = field(default_factory=dict)
    typography: dict[str, Any] = field(default_factory=dict)
    photography_style: str = ""
    motion_style: str = ""
    brand_consistency_rules: list[str] = field(default_factory=list)
    creative_references: list[dict[str, Any]] = field(default_factory=list)
    do_list: list[str] = field(default_factory=list)
    dont_list: list[str] = field(default_factory=list)
    image_prompt_template: str = ""
    video_prompt_template: str = ""
    creative_rationale: str = ""
    brand_alignment: str = ""
    concept_alternatives: list[dict[str, Any]] = field(default_factory=list)
    platform_adaptation_notes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "visual_style": self.visual_style,
            "mood": self.mood,
            "colour_palette": self.colour_palette,
            "typography": self.typography,
            "photography_style": self.photography_style,
            "motion_style": self.motion_style,
            "brand_consistency_rules": self.brand_consistency_rules,
            "creative_references": self.creative_references,
            "do_list": self.do_list,
            "dont_list": self.dont_list,
            "image_prompt_template": self.image_prompt_template,
            "video_prompt_template": self.video_prompt_template,
            "creative_rationale": self.creative_rationale,
            "brand_alignment": self.brand_alignment,
            "concept_alternatives": self.concept_alternatives,
            "platform_adaptation_notes": self.platform_adaptation_notes,
        }


class CreativeDirectionEngine(IntelligenceEngine):
    """Determines creative direction BEFORE any assets are generated.

    This is the critical "think before create" gate. No image or video
    generation happens until this engine has defined the visual language.
    """

    ENGINE_NAME = "creative_direction"
    ENGINE_VERSION = "1.1.0"
    PROMPT_VERSION = "2.0.0"
    SCHEMA_VERSION = "1.1.0"
    TIER = Tier.large
    MAX_TOKENS = 3000
    TEMPERATURE = 0.4

    def _build_prompt(self, **kwargs: Any) -> str:
        business_profile = kwargs.get("business_profile", {})
        audience_profile = kwargs.get("audience_profile", {})
        campaign_strategy = kwargs.get("campaign_strategy", {})
        brand_colors = kwargs.get("brand_colors", [])
        brand_logo_url = kwargs.get("brand_logo_url", "")
        brand_fonts = kwargs.get("brand_fonts", [])
        additional_context = kwargs.get("additional_context", "")

        return f"""ROLE: You are an Executive Creative Director at a top global agency
(Wieden+Kennedy/Ogilvy/BBDO). You define the visual language for campaigns before
any creative assets are produced. You think like Apple's design team — every pixel
matters. You don't just pick a style — you explain WHY this concept, how it aligns
with the brand, and how it adapts across platforms. You always present 3 concept
alternatives because the best creative comes from creative tension, not the first idea.

TASK: Define the creative direction for this campaign. Provide a creative rationale,
brand alignment explanation, 3 concept alternatives, and platform-specific adaptation notes.

INPUTS:
- Business Profile: {business_profile}
- Audience Profile: {audience_profile}
- Campaign Strategy: {campaign_strategy}
- Brand Colors: {brand_colors}
- Brand Logo: {brand_logo_url}
- Brand Fonts: {brand_fonts}
{f"- Additional Context: {additional_context}" if additional_context else ""}

REASONING PROCESS (follow this chain-of-thought before producing your answer):
Step 1 — BRAND DNA: What is the brand's visual identity? What colours, fonts, and
  imagery does it already use? What is the brand personality (premium, playful, serious, etc.)?
Step 2 — AUDIENCE FIT: What visual language resonates with this audience?
  What do they save, share, and engage with? What aesthetic signals "this is for me"?
Step 3 — CONCEPT: What is the creative concept? Why THIS concept and not another?
  How does it translate the campaign strategy's core message into a visual world?
Step 4 — ALTERNATIVES: What are 2 other valid concepts? How do they differ from the
  primary? What are the trade-offs? (The primary should be the best, but the
  alternatives should be genuinely viable, not strawmen.)
Step 5 — ADAPTATION: How does this concept adapt across platforms? A Reel needs
  different treatment than a carousel, which needs different treatment than a YouTube
  long-form video. Specify the adaptation for each platform.
Write your reasoning in the "reasoning" field showing this step-by-step analysis.

CREATIVE DIRECTION REQUIREMENTS:
1. Visual Style: Define the overall aesthetic (minimalist, bold, editorial, etc.)
2. Mood: The emotional tone of visuals (warm, energetic, serene, dramatic, etc.)
3. Colour Palette: 5-7 specific colours with hex codes and usage guidelines.
4. Typography: Font recommendations (primary, secondary, accent) with reasoning.
5. Photography Style: Type of imagery (lifestyle, product, documentary, etc.)
   with composition guidelines.
6. Motion Style: For video content — pacing, transitions, camera movement.
7. Brand Consistency Rules: 5-8 rules to maintain brand identity across assets.
8. Creative References: 3-5 reference campaigns/styles to emulate (describe, don't copy).
9. Do List: 5-8 things creatives MUST do.
10. Don't List: 5-8 things creatives MUST NOT do.
11. Image Prompt Template: A reusable template for AI image generation.
12. Video Prompt Template: A reusable template for AI video generation.
13. Creative Rationale: Why THIS creative concept? Explain the strategic logic:
    - What emotion does it evoke and why is that the right emotion for this audience?
    - What visual metaphor or device carries the message?
    - Why this concept over the obvious alternative? (e.g., "We chose 'farmer's hands'
      over 'coffee cup beauty shots' because the audience values authenticity over
      polish — the imperfection IS the message.")
    - How does the concept differentiate from competitors' visual language?
14. Brand Alignment: How does this creative direction align with the brand?
    - Which brand values does the visual language express?
    - How does it extend (not contradict) the existing brand identity?
    - What brand guardrails does it respect? (colours, logo usage, tone)
    - If the brand has no established visual identity, what are we establishing
      and why these choices?
15. Concept Alternatives: Provide 3 concept alternatives (including the primary):
    - concept_name: A memorable name (e.g., "The Farmer's Hands", "The Ritual",
      "The Gift Unboxed")
    - description: 2-3 sentences describing the visual world
    - visual_approach: How it looks (palette, photography style, mood)
    - why_it_works: Why this concept is effective for this audience + strategy
    - trade_offs: What this concept sacrifices (e.g., "sacrifices polish for authenticity",
      "sacrifices broad appeal for niche depth")
    - recommended: Is this the primary recommendation? (true for one, false for others)
    The 3 concepts should be genuinely different — not variations of the same idea.
16. Platform Adaptation Notes: For each major platform:
    - platform: Name (Instagram, YouTube, LinkedIn, WhatsApp, etc.)
    - format_adaptation: How the concept adapts to this platform's native format
      (e.g., "Instagram Reels: 9:16, 15-30s, trending audio, fast cuts of farmer
      hands → pour → cup. YouTube: 16:9, 8-15min, slow documentary pacing.")
    - visual_tweaks: Specific visual changes for this platform
      (e.g., "LinkedIn: desaturate by 10%, add text overlay for sound-off viewing")
    - copy_tone: Tone shift for this platform (e.g., "Instagram: poetic and sensory.
      LinkedIn: professional and impact-focused.")
    - asset_specs: Technical specs (dimensions, duration, file format)

FEW-SHOT EXAMPLE (D2C Coffee — use as quality benchmark, do NOT copy):
- Creative Rationale: "We chose 'The Farmer's Hands' — close-up photography of the
  farmers' hands holding beans, pouring, brewing — because the audience (The Ritualist)
  values craftsmanship and authenticity over polish. The imperfection of weathered hands
  IS the message: this coffee comes from real people, not a factory. This differentiates
  from Blue Tokai's polished studio shots and Sleepy Owl's playful illustrations.
  The visual metaphor: hands = craft, care, human connection."
- Brand Alignment: "Expresses the brand values of traceability, direct trade, and
  human connection. Extends the existing earthy palette (browns, creams) with richer
  skin tones and natural light. Respects brand guardrails: logo bottom-right, no
  competitor product shots, FSSAI compliance on all food imagery."
- Concept Alternatives:
  1. concept_name: "The Farmer's Hands" (recommended)
     description: "Intimate close-ups of farmers' hands through the coffee journey —
     harvesting, sorting, roasting, brewing. Natural light, documentary feel."
     visual_approach: "Warm, earthy, documentary photography. Shallow depth of field.
     Hands as the hero, coffee as the supporting character."
     why_it_works: "Authenticity resonates with The Ritualist segment. Differentiates
     from all competitors. Creates emotional connection through human presence."
     trade_offs: "Sacrifices product visibility for emotional impact. May feel too
     artisanal for The Gifter segment."
  2. concept_name: "The Ritual"
     description: "Slow-motion morning coffee rituals of real customers. Steam rising,
     first sip, eyes closing. Sensory and aspirational."
     visual_approach: "Cinematic, warm, golden hour lighting. Product as the hero of
     a daily ritual. People > product in framing."
     why_it_works: "Aspirational yet relatable. Shows the product in use, which aids
     purchase decision. Works well for gifting angle."
     trade_offs: "Less differentiated — every coffee brand shows rituals. Requires
     casting real customers, which is logistically harder."
  3. concept_name: "The Origin Map"
     description: "Visual journey from farm to cup using map graphics, distance markers,
     and time stamps. Data-meets-storytelling."
     visual_approach: "Editorial, infographic-meets-photography. Clean, modern,
     data-visualisation aesthetic with real farm photography."
     why_it_works: "Unique format no competitor uses. Appeals to The Conscious Connoisseur
     who values transparency. Highly shareable as educational content."
     trade_offs: "May feel too clinical for emotional buyers. Higher production complexity
     for map graphics. Less Instagram-native."
- Platform Adaptation:
  - platform: "Instagram"
    format_adaptation: "Reels: 9:16, 15-30s, trending audio, fast cuts (hands → beans →
      pour → cup → smile). Carousels: 1:1, 5-7 slides, educational swipe-through."
    visual_tweaks: "Reels: boost saturation +10% for feed stand-out. Carousels: add
      text overlay on each slide for sound-off viewing."
    copy_tone: "Poetic and sensory. 'Every cup starts with these hands.'"
    asset_specs: "Reels: 1080x1920, MP4, 15-30s. Carousels: 1080x1080, JPG/PNG, 5-7 slides."
  - platform: "YouTube"
    format_adaptation: "16:9, 8-15min, slow documentary pacing. Single farmer story per
      video. Interview + b-roll of farm and roastery."
    visual_tweaks: "Cinematic colour grade, letterbox optional. Lower third with farmer
      name and estate location."
    copy_tone: "Narrative documentary. 'Meet Raju. He's been growing coffee for 23 years.'"
    asset_specs: "1920x1080, MP4, 8-15min. Custom thumbnail with farmer portrait + brand logo."

QUALITY RULES:
- Colour palette must include hex codes
- Photography style must be specific enough to guide a photographer or AI
- Prompt templates must be immediately usable for AI generation
- Do/Don't lists must be specific to this brand, not generic
- Creative rationale must explain WHY this concept, not just describe it
- Brand alignment must reference specific brand values and guardrails
- 3 concept alternatives must be genuinely different approaches, not variations
- Platform adaptation must be specific to each platform's native format and audience behaviour
- Confidence 0.4-0.8
- 3-5 creative recommendations

OUTPUT: JSON matching the schema. Include "reasoning", "confidence", "recommendations".
"""

    def _build_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "visual_style": {"type": "string"},
                "mood": {"type": "string"},
                "colour_palette": {
                    "type": "object",
                    "properties": {
                        "primary": {"type": "string"},
                        "secondary": {"type": "string"},
                        "accent": {"type": "string"},
                        "background": {"type": "string"},
                        "text": {"type": "string"},
                        "colours": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "hex": {"type": "string"},
                                    "usage": {"type": "string"},
                                },
                            },
                        },
                    },
                },
                "typography": {
                    "type": "object",
                    "properties": {
                        "primary_font": {"type": "string"},
                        "secondary_font": {"type": "string"},
                        "accent_font": {"type": "string"},
                        "reasoning": {"type": "string"},
                    },
                },
                "photography_style": {"type": "string"},
                "motion_style": {"type": "string"},
                "brand_consistency_rules": {"type": "array", "items": {"type": "string"}},
                "creative_references": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "style": {"type": "string"},
                            "why_it_works": {"type": "string"},
                        },
                    },
                },
                "do_list": {"type": "array", "items": {"type": "string"}},
                "dont_list": {"type": "array", "items": {"type": "string"}},
                "image_prompt_template": {"type": "string"},
                "video_prompt_template": {"type": "string"},
                "creative_rationale": {"type": "string"},
                "brand_alignment": {"type": "string"},
                "concept_alternatives": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "concept_name": {"type": "string"},
                            "description": {"type": "string"},
                            "visual_approach": {"type": "string"},
                            "why_it_works": {"type": "string"},
                            "trade_offs": {"type": "string"},
                            "recommended": {"type": "boolean"},
                        },
                    },
                },
                "platform_adaptation_notes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "platform": {"type": "string"},
                            "format_adaptation": {"type": "string"},
                            "visual_tweaks": {"type": "string"},
                            "copy_tone": {"type": "string"},
                            "asset_specs": {"type": "string"},
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
            "required": ["visual_style", "mood", "colour_palette", "reasoning", "confidence"],
        }

    def to_direction(self, output: EngineOutput) -> CreativeDirection:
        """Convert an EngineOutput to a typed CreativeDirection.

        Delegates to CreativeDirection.from_dict() — the model owns parsing.
        """
        return CreativeDirection.from_dict(output.result)  # type: ignore[return-value]
