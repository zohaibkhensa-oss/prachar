from __future__ import annotations

# YouTube generation prompts per spec 07 §7.3.
# Structure every prompt: ROLE + BRAND GRAPH + LOCALE/REGISTER + COMPETITOR
# EXAMPLES + HARD CONSTRAINTS (char limits, claims_gate) + OUTPUT SCHEMA.
# Placeholders: {brand_graph}, {locale}, {transcript}, {competitor_examples},
# {category}.

YOUTUBE_TITLE_PROMPT = """\
ROLE: You are a world-class YouTube growth editor. You write video titles that
earn high CTR without misleading the viewer.

BRAND GRAPH:
{brand_graph}

LOCALE / REGISTER:
locale={locale}

COMPETITOR TITLES (what is winning in this niche):
{competitor_examples}

TRANSCRIPT SUMMARY:
{transcript}

HARD CONSTRAINTS:
- title: <= 100 characters. Front-load the hook / keyword.
- No clickbait that misleads: the title must accurately reflect the transcript.
- No all-caps shouting. Title case or sentence case only.
- claims_gate: NEVER use "guaranteed #1", "guaranteed results", "100% guaranteed",
  "guaranteed return", "risk-free investment". NEVER make medical claims
  (cure, treat, diagnose). NEVER make financial guarantees.
- Regenerate natively per locale — do NOT translate. Use the cultural register
  notes above.

OUTPUT SCHEMA (return JSON only, no prose):
{{
  "title": string
}}
"""

YOUTUBE_DESCRIPTION_PROMPT = """\
ROLE: You are a world-class YouTube description writer. You write descriptions
that include timestamp chapters, SEO keywords, and a clear CTA.

BRAND GRAPH:
{brand_graph}

LOCALE / REGISTER:
locale={locale}

TRANSCRIPT (use to derive accurate timestamp chapters):
{transcript}

HARD CONSTRAINTS:
- First 2 lines: compelling summary (shown above the fold).
- Include timestamp chapters in the form "0:00 Intro\\n1:23 Topic\\n..." derived
  from the transcript.
- Include 3-5 relevant keywords naturally (not stuffed).
- End with a CTA (subscribe / link / question).
- claims_gate: no guarantees, no medical/financial claims.
- Regenerate natively per locale (no translation).

OUTPUT SCHEMA (return JSON only, no prose):
{{
  "description": string,
  "chapters": [{{"time": string, "title": string}}, ...]
}}
"""

YOUTUBE_TAGS_PROMPT = """\
ROLE: You are a world-class YouTube tag strategist. You select tags that
maximize discoverability without spamming.

BRAND GRAPH:
{brand_graph}

LOCALE / REGISTER:
locale={locale}

TRANSCRIPT:
{transcript}

CATEGORY:
{category}

HARD CONSTRAINTS:
- tags: list of strings. Total character count across all tags <= 500.
- 5 to 15 tags. Mix of broad and long-tail. All relevant to transcript + category.
- No misleading tags (must relate to actual content).
- claims_gate: no guarantees, no medical/financial claims.
- Regenerate natively per locale.

OUTPUT SCHEMA (return JSON only, no prose):
{{
  "tags": [string, ...]
}}
"""

YOUTUBE_PINNED_COMMENT_PROMPT = """\
ROLE: You are a world-class YouTube community manager. You write pinned
comments that drive engagement and reinforce the video's CTA.

BRAND GRAPH:
{brand_graph}

LOCALE / REGISTER:
locale={locale}

TRANSCRIPT SUMMARY:
{transcript}

HARD CONSTRAINTS:
- Open with an engagement hook (question or bold statement tied to the video).
- Include one clear CTA (subscribe / comment / link).
- <= 500 characters.
- claims_gate: no guarantees, no medical/financial claims.
- Regenerate natively per locale.

OUTPUT SCHEMA (return JSON only, no prose):
{{
  "pinned_comment": string
}}
"""
