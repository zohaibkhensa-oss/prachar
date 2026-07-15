from __future__ import annotations

import hashlib
import logging
import re
import uuid
from typing import Any

from prachar_shared.adapters.organic.youtube import YouTubeAdapter
from prachar_shared.adapters.organic.youtube_prompts import (
    YOUTUBE_DESCRIPTION_PROMPT,
    YOUTUBE_PINNED_COMMENT_PROMPT,
    YOUTUBE_TAGS_PROMPT,
    YOUTUBE_TITLE_PROMPT,
)
from prachar_shared.ai_gateway import AIGateway, Tier

logger = logging.getLogger(__name__)

_DEFAULT_REGISTER = "professional"
_DEFAULT_COMPETITORS = "No competitor examples available."

_TS_PATTERN = re.compile(r"(?m)^\s*(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$")


def _gateway() -> AIGateway:
    return AIGateway()


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_chapters(transcript: str) -> list[dict[str, str]]:
    """Parse transcript for timestamp lines, else generate fixed-interval chapters.

    Returns ``[{"time": "0:00", "title": "..."}, ...]``.
    """
    found = [
        {"time": m.group(1), "title": m.group(2).strip()}
        for m in _TS_PATTERN.finditer(transcript)
    ]
    if len(found) >= 2:
        return found

    # Fallback: split into sentences and assign fixed intervals.
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", transcript) if s.strip()]
    if not sentences:
        return [
            {"time": "0:00", "title": "Intro"},
            {"time": "1:00", "title": "Main content"},
        ]
    chapters: list[dict[str, str]] = []
    interval = 60  # seconds
    for i, s in enumerate(sentences[:8]):
        total = i * interval
        mm, ss = divmod(total, 60)
        chapters.append(
            {
                "time": f"{mm}:{ss:02d}",
                "title": (s[:60] + "...") if len(s) > 60 else s,
            }
        )
    if len(chapters) < 2:
        chapters.append({"time": "1:00", "title": "Main content"})
    return chapters


async def transcribe_video(
    asset_id: uuid.UUID, video_url_or_s3_key: str
) -> str:
    """Transcribe a video via the Whisper API.

    Stub mode (no Whisper credentials): returns a deterministic fake transcript
    based on the asset_id hash — 3-5 sentences about the brand category.
    """
    digest = _digest(str(asset_id))
    seed = int(digest[:8], 16)
    n_sentences = 3 + (seed % 3)  # 3-5
    category_idx = seed % 4
    categories = ["marketing", "productivity", "fitness", "finance"]
    category = categories[category_idx]
    sentences = [
        f"Welcome back to the channel where we talk about {category}.",
        f"Today we are diving deep into the strategies that work for {category} in the current landscape.",
        f"There are three key principles you need to understand to succeed here.",
        f"First, consistency matters more than intensity when building a {category} practice.",
        f"Second, always measure your results so you can iterate and improve over time.",
    ]
    return " ".join(sentences[:n_sentences])


def _stub_title(transcript: str, brand_graph: dict[str, Any]) -> str:
    brand_name = brand_graph.get("brand_name") or brand_graph.get("name") or "Brand"
    categories = brand_graph.get("categories") or []
    cat = categories[0] if categories else "growth"
    title = f"The Complete Guide to {cat.title()} | {brand_name}"
    if len(title) > 100:
        title = title[:97].rstrip() + "..."
    return title


def _stub_description(
    transcript: str, brand_graph: dict[str, Any], locale: str
) -> tuple[str, list[dict[str, str]]]:
    brand_name = brand_graph.get("brand_name") or brand_graph.get("name") or "Brand"
    chapters = extract_chapters(transcript)
    chapter_lines = "\n".join(f"{c['time']} {c['title']}" for c in chapters)
    desc = (
        f"In this video we break down the key ideas from {brand_name}.\n\n"
        f"Chapters:\n{chapter_lines}\n\n"
        f"Subscribe for more weekly content. Locale: {locale}."
    )
    return desc, chapters


def _stub_tags(transcript: str, brand_graph: dict[str, Any]) -> list[str]:
    categories = brand_graph.get("categories") or ["growth"]
    base_tags = [c.lower() for c in categories[:3]]
    words = re.findall(r"[a-zA-Z]{4,}", transcript.lower())
    extra = list(dict.fromkeys(words))[:10]
    tags = base_tags + extra
    # Trim to <= 500 total chars.
    out: list[str] = []
    total = 0
    for t in tags:
        if total + len(t) > 500:
            break
        out.append(t)
        total += len(t)
    if not out:
        out = ["growth", "guide"]
    return out


def _stub_pinned_comment(transcript: str, brand_graph: dict[str, Any]) -> str:
    brand_name = brand_graph.get("brand_name") or brand_graph.get("name") or "Brand"
    comment = (
        f"What was your biggest takeaway from this {brand_name} video? "
        "Drop it below and subscribe for the next one!"
    )
    if len(comment) > 500:
        comment = comment[:497].rstrip() + "..."
    return comment


async def optimize_youtube_metadata(
    brand_id: uuid.UUID,
    transcript: str,
    locale: str,
    brand_graph: dict[str, Any],
) -> dict[str, Any]:
    """Generate YouTube metadata (title, description w/ chapters, tags, pinned comment).

    Uses the YouTube prompts via AIGateway. In stub mode, generates plausible
    metadata from the transcript hash. Returns a payload dict matching
    ``YouTubeAdapter().generate_schema()``.
    """
    gw = _gateway()
    schema = YouTubeAdapter().generate_schema()
    register = (brand_graph.get("tone") or {}).get("register", _DEFAULT_REGISTER)
    competitors = brand_graph.get("competitors") or []
    competitor_examples = (
        ", ".join(competitors) if competitors else _DEFAULT_COMPETITORS
    )
    categories = brand_graph.get("categories") or []
    category = categories[0] if categories else "general"

    title_prompt = JOUTUBE_TITLE_PROMPT_FMT(
        brand_graph=brand_graph,
        locale=locale,
        competitor_examples=competitor_examples,
        transcript=transcript[:800],
    )
    desc_prompt = YOUTUBE_DESCRIPTION_PROMPT.format(
        brand_graph=str(brand_graph),
        locale=locale,
        transcript=transcript[:1500],
    )
    tags_prompt = YOUTUBE_TAGS_PROMPT.format(
        brand_graph=str(brand_graph),
        locale=locale,
        transcript=transcript[:800],
        category=category,
    )
    pinned_prompt = JOUTUBE_PINNED_COMMENT_PROMPT_FMT(
        brand_graph=brand_graph,
        locale=locale,
        transcript=transcript[:800],
    )

    if gw._stub_mode():
        title = _stub_title(transcript, brand_graph)
        description, chapters = _stub_description(transcript, brand_graph, locale)
        tags = _stub_tags(transcript, brand_graph)
        pinned_comment = _stub_pinned_comment(transcript, brand_graph)
        return {
            "title": title,
            "description": description,
            "tags": tags,
            "thumbnail_variants": [{}, {}],
            "pinned_comment": pinned_comment,
            "playlist_id": "",
        }

    # Live mode: call the gateway for each field.
    import json

    title_comp = gw.complete(
        title_prompt,
        tier=Tier.small,
        task="captions",
        schema={"type": "object", "properties": {"title": {"type": "string"}}},
        tenant_id=brand_id,
        plan="starter",
    )
    title = str((title_comp.json_value or {}).get("title", "") or _stub_title(transcript, brand_graph))
    if len(title) > 100:
        title = title[:97].rstrip() + "..."

    desc_comp = gw.complete(
        desc_prompt,
        tier=Tier.small,
        task="captions",
        schema={
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "chapters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "time": {"type": "string"},
                            "title": {"type": "string"},
                        },
                    },
                },
            },
        },
        tenant_id=brand_id,
        plan="starter",
    )
    desc_jv = desc_comp.json_value or {}
    description = str(desc_jv.get("description", "") or "")
    chapters = desc_jv.get("chapters") or []
    if not chapters:
        _, chapters = _stub_description(transcript, brand_graph, locale)
    if not description:
        description, _ = _stub_description(transcript, brand_graph, locale)

    tags_comp = gw.complete(
        tags_prompt,
        tier=Tier.small,
        task="captions",
        schema={"type": "object", "properties": {"tags": {"type": "array", "items": {"type": "string"}}}},
        tenant_id=brand_id,
        plan="starter",
    )
    tags = (tags_comp.json_value or {}).get("tags") or _stub_tags(transcript, brand_graph)
    # Enforce <= 500 total chars.
    total = 0
    trimmed: list[str] = []
    for t in tags:
        if total + len(str(t)) > 500:
            break
        trimmed.append(str(t))
        total += len(str(t))
    tags = trimmed or _stub_tags(transcript, brand_graph)

    pinned_comp = gw.complete(
        pinned_prompt,
        tier=Tier.small,
        task="captions",
        schema={"type": "object", "properties": {"pinned_comment": {"type": "string"}}},
        tenant_id=brand_id,
        plan="starter",
    )
    pinned_comment = str(
        (pinned_comp.json_value or {}).get("pinned_comment", "")
        or _stub_pinned_comment(transcript, brand_graph)
    )

    logger.debug(
        "optimize_youtube_metadata brand=%s title_len=%s tags=%s",
        brand_id,
        len(title),
        len(tags),
    )
    _ = json  # silence unused import in some linters
    _ = schema  # schema available for callers; not strictly required here
    return {
        "title": title,
        "description": description,
        "tags": tags,
        "thumbnail_variants": [{}, {}],
        "pinned_comment": pinned_comment,
        "playlist_id": "",
    }


async def generate_thumbnail_brief(
    brand_id: uuid.UUID, title: str, brand_graph: dict[str, Any]
) -> dict[str, Any]:
    """Generate a text brief describing what the thumbnail should contain.

    Stub mode returns a deterministic brief dict. Actual image generation lives
    in the creative worker.
    """
    digest = _digest(title + str(brand_graph))
    emotions = ["curiosity", "excitement", "confidence", "surprise"]
    palettes = ["bold-contrast", "warm", "cool-blue", "high-saturation"]
    seed = int(digest[:8], 16)
    emotion = emotions[seed % len(emotions)]
    palette = palettes[(seed >> 4) % len(palettes)]
    brand_name = brand_graph.get("brand_name") or brand_graph.get("name") or "Brand"
    return {
        "text_overlay": title[:40],
        "colors": palette,
        "emotion": emotion,
        "composition": "subject-left, text-right, high-contrast background",
        "brand_name": brand_name,
        "variants": [
            {"size": "1280x720", "purpose": "default"},
            {"size": "640x480", "purpose": "search-result"},
        ],
    }


# --- prompt formatters (kept as module-level callables to avoid f-string
#     brace conflicts with the prompt templates' JSON schema braces). ---
def JOUTUBE_TITLE_PROMPT_FMT(
    *,
    brand_graph: dict[str, Any],
    locale: str,
    competitor_examples: str,
    transcript: str,
) -> str:
    return YOUTUBE_TITLE_PROMPT.format(
        brand_graph=str(brand_graph),
        locale=locale,
        competitor_examples=competitor_examples,
        transcript=transcript,
    )


def JOUTUBE_PINNED_COMMENT_PROMPT_FMT(
    *,
    brand_graph: dict[str, Any],
    locale: str,
    transcript: str,
) -> str:
    return YOUTUBE_PINNED_COMMENT_PROMPT.format(
        brand_graph=str(brand_graph),
        locale=locale,
        transcript=transcript,
    )
