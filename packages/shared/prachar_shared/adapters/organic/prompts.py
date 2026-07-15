from __future__ import annotations

# Generation prompts per spec 07 §7.3.
# Structure every prompt: ROLE + BRAND GRAPH + LOCALE/REGISTER + COMPETITOR
# EXAMPLES + HARD CONSTRAINTS (char limits, claims_gate) + OUTPUT SCHEMA.
# Placeholders: {brand_graph}, {locale}, {register}, {competitor_examples},
# {target_keyword}.

PAGE_CONTENT_PROMPT = """\
ROLE: You are a world-class Google Search / SEO growth editor. You write
on-page content that ranks and converts.

BRAND GRAPH:
{brand_graph}

LOCALE / REGISTER:
locale={locale}
register={register}

COMPETITOR EXAMPLES (what is winning in this SERP):
{competitor_examples}

TARGET KEYWORD:
{target_keyword}

HARD CONSTRAINTS:
- title: <= 60 characters. Must contain the target keyword near the front.
- meta: <= 155 characters. Must be an accurate, non-misleading summary.
- h_structure: ordered list of heading tags (H1, H2, H3...) that structure the page.
- schema_org: a schema.org JSON-LD object (Article, FAQPage, Product, or
  HowTo as appropriate). Must match the page content — no misleading metadata.
- internal_links: list of suggested internal link anchor texts / paths.
- faq: list of {{question, answer}} pairs for FAQPage schema. 3-6 pairs.
- claims_gate: NEVER use "guaranteed #1", "guaranteed results", "100% guaranteed",
  "guaranteed return", "risk-free investment". NEVER make medical claims
  (cure, treat, diagnose). NEVER make financial guarantees.
- Regenerate natively per locale — do NOT translate. Use the cultural register
  notes above.

OUTPUT SCHEMA (return JSON only, no prose):
{{
  "title": string,
  "meta": string,
  "h_structure": [string, ...],
  "schema_org": {{...}},
  "internal_links": [string, ...],
  "faq": [{{"question": string, "answer": string}}, ...]
}}
"""

META_TAGS_PROMPT = """\
ROLE: You are a world-class SEO title + meta description writer.

BRAND GRAPH:
{brand_graph}

LOCALE / REGISTER:
locale={locale}
register={register}

COMPETITOR EXAMPLES (top-ranking title/meta pairs):
{competitor_examples}

TARGET KEYWORD:
{target_keyword}

HARD CONSTRAINTS:
- title: <= 60 characters. Keyword near the front. No clickbait.
- meta: <= 155 characters. Accurate, compelling, non-misleading summary.
- claims_gate: no "guaranteed #1", "guaranteed results", "100% guaranteed",
  medical/financial claims.
- Regenerate natively per locale (no translation).

OUTPUT SCHEMA (return JSON array of {count} variants):
[
  {{"title": string, "meta": string}},
  ...
]
"""

FAQ_BLOCK_PROMPT = """\
ROLE: You are a world-class SEO FAQ schema writer. You produce FAQPage
schema.org Q&A pairs that earn rich results.

BRAND GRAPH:
{brand_graph}

LOCALE / REGISTER:
locale={locale}
register={register}

COMPETITOR EXAMPLES (People Also Ask / competitor FAQ blocks):
{competitor_examples}

TARGET TOPIC / KEYWORD:
{target_keyword}

HARD CONSTRAINTS:
- 3 to 6 question/answer pairs.
- Each answer: 40-60 words, direct, factual, no fluff.
- questions must be natural-language queries a user would type.
- claims_gate: no guarantees, no medical/financial claims.
- Regenerate natively per locale.

OUTPUT SCHEMA (return JSON array):
[
  {{"question": string, "answer": string}},
  ...
]
"""
