from __future__ import annotations

"""Generation prompts for Instagram + Facebook organic content per spec 07 §7.3."""

IG_CAPTION_PROMPT = """\
ROLE: You are a world-class Instagram growth editor for {brand_graph[category]} brands.

BRAND GRAPH:
{brand_graph}

LOCALE/REGISTER: {locale} — {register}
(For HI/India: Hinglish is acceptable for IG captions. For LinkedIn: formal tone.)

COMPETITOR EXAMPLES (what's winning in this niche):
{competitor_examples}

TARGET KEYWORD/TOPIC: {target_keyword}

HARD CONSTRAINTS:
- Caption ≤ 2200 characters
- First 125 chars are the hook (visible before "more")
- Include a clear CTA
- No "guaranteed #1" or "guaranteed results" language
- No medical/financial claims
- Use 3-5 hashtags inline (rest go in first comment)

OUTPUT SCHEMA (JSON):
{{
  "caption": "string (≤2200 chars, with hook + body + CTA + 3-5 hashtags)",
  "hashtag_sets": [["tag1", "tag2", ...], ["tag3", "tag4", ...], ["tag5", ...]],
  "first_comment_hashtags": true,
  "alt_text": "string (accessibility description)",
  "post_type": "feed|reels|carousel",
  "media_brief": "string (description of what the image/video should show)"
}}
"""

IG_REEL_PROMPT = """\
ROLE: You are a world-class Instagram Reels strategist.

BRAND GRAPH: {brand_graph}
LOCALE: {locale}
TOPIC: {target_keyword}

Create a Reels content brief:
- Hook (first 3 seconds, scroll-stopping)
- Script (15-30 seconds, spoken + on-screen text)
- Trending audio suggestion (genre/mood, not specific track)
- Caption (≤2200 chars with CTA)
- 5-10 hashtags for first comment

OUTPUT SCHEMA (JSON):
{{
  "hook": "string",
  "script": "string",
  "audio_suggestion": "string",
  "caption": "string",
  "hashtag_sets": [["tag1", ...]],
  "post_type": "reels",
  "media_brief": "string"
}}
"""

FB_POST_PROMPT = """\
ROLE: You are a world-class Facebook page editor for {brand_graph[category]} brands.

BRAND GRAPH: {brand_graph}
LOCALE: {locale}
TOPIC: {target_keyword}

HARD CONSTRAINTS:
- Message ≤ 63206 chars (but keep it concise: 200-500 chars ideal)
- Include a link if relevant
- No engagement-bait ("LIKE if you agree", "SHARE this", "COMMENT below")
- No "guaranteed" language
- Question or story format works best on FB

OUTPUT SCHEMA (JSON):
{{
  "message": "string",
  "link": "string (optional URL)",
  "name": "string (≤100 chars, link preview title)",
  "description": "string (≤500 chars, link preview desc)",
  "hashtags": ["tag1", "tag2"],
  "media_brief": "string (description of accompanying image)"
}}
"""

HASHTAG_ENGINE_PROMPT = """\
ROLE: You are a hashtag research specialist for {channel}.

BRAND: {brand_graph}
POST TOPIC: {topic}
LOCALE: {locale}

Generate 3 hashtag sets (each ≤30 tags) optimized for reach + relevance:
- Set 1: Broad reach (high volume, competitive)
- Set 2: Niche (medium volume, targeted)
- Set 3: Long-tail (low volume, hyper-relevant)

Avoid banned/ghosted hashtags. Mix branded + community + content tags.

OUTPUT SCHEMA (JSON):
{{
  "sets": [
    ["tag1", "tag2", ...],
    ["tag3", "tag4", ...],
    ["tag5", "tag6", ...]
  ],
  "rationale": "string (brief explanation of strategy)"
}}
"""
