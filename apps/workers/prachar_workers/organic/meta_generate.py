from __future__ import annotations

"""Instagram + Facebook content generation + hashtag engine + scheduler."""

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _stub_seed(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(h[:8], 16)


async def generate_ig_caption(
    brand_id: uuid.UUID,
    target_keyword: str,
    locale: str,
    brand_graph: dict[str, Any],
) -> dict[str, Any]:
    """Generate an Instagram caption + hashtag sets via AIGateway (stub mode
    returns deterministic plausible content)."""
    try:
        from prachar_shared.ai_gateway import AIGateway, Tier
        from prachar_shared.adapters.organic.meta_prompts import IG_CAPTION_PROMPT

        gw = AIGateway()
        prompt = IG_CAPTION_PROMPT.format(
            brand_graph=brand_graph,
            locale=locale,
            register="casual" if locale.startswith("hi") else "professional",
            competitor_examples="N/A (stub mode)",
            target_keyword=target_keyword,
        )
        result = await gw.complete(
            prompt=prompt,
            tier=Tier.small,
            task="captions",
            tenant_id=brand_id,
            plan="starter",
        )
        if result.json_value:
            return result.json_value
    except Exception as exc:
        logger.warning("IG caption AI call failed, using stub: %s", exc)

    # Stub: deterministic plausible caption.
    seed = _stub_seed(str(brand_id), target_keyword, locale)
    brand_name = brand_graph.get("brand_name", "Your Brand")
    category = brand_graph.get("category", "business")
    hooks = [
        f"Stop scrolling! Here's how {brand_name} is redefining {category} 👀",
        f"Nobody talks about this {category} secret... but we will 🧵",
        f"POV: You just discovered the best {category} brand in {locale.upper()} ✨",
        f"The {category} industry needs a shake-up. Here's our take 💪",
    ]
    ctas = [
        "Link in bio to learn more!",
        "DM us for a free consultation.",
        "Save this post for later!",
        "Follow for daily {category} tips.",
    ]
    hook = hooks[seed % len(hooks)]
    cta = ctas[(seed >> 4) % len(ctas)]
    caption = f"{hook}\n\nWe believe {target_keyword} should be accessible to everyone. That's why {brand_name} has been perfecting our approach for years.\n\n{cta}\n\n#{category.replace(' ', '')} #{brand_name.replace(' ', '')} #{target_keyword.replace(' ', '')} #{locale} {category}tips"
    hashtag_sets = [
        [f"#{category.replace(' ', '')}", f"#{brand_name.replace(' ', '')}", f"#{target_keyword.replace(' ', '')}"],
        [f"#{locale}", f"#{category}life", f"#{category}lover", f"#{category}community"],
        [f"#{target_keyword.replace(' ', '')}tips", f"#{brand_name.replace(' ', '')}story", f"#{locale}{category}"],
    ]
    return {
        "caption": caption[:2200],
        "hashtag_sets": hashtag_sets,
        "first_comment_hashtags": True,
        "alt_text": f"{brand_name} post about {target_keyword}",
        "post_type": "feed",
        "media_brief": f"High-quality image of {brand_name} product/service related to {target_keyword}, warm lighting, brand colors",
    }


async def generate_fb_post(
    brand_id: uuid.UUID,
    target_keyword: str,
    locale: str,
    brand_graph: dict[str, Any],
) -> dict[str, Any]:
    """Generate a Facebook page post via AIGateway (stub mode fallback)."""
    try:
        from prachar_shared.ai_gateway import AIGateway, Tier
        from prachar_shared.adapters.organic.meta_prompts import FB_POST_PROMPT

        gw = AIGateway()
        prompt = FB_POST_PROMPT.format(
            brand_graph=brand_graph,
            locale=locale,
            target_keyword=target_keyword,
        )
        result = await gw.complete(
            prompt=prompt, tier=Tier.small, task="captions",
            tenant_id=brand_id, plan="starter",
        )
        if result.json_value:
            return result.json_value
    except Exception as exc:
        logger.warning("FB post AI call failed, using stub: %s", exc)

    seed = _stub_seed(str(brand_id), target_keyword, "fb")
    brand_name = brand_graph.get("brand_name", "Your Brand")
    category = brand_graph.get("category", "business")
    messages = [
        f"Did you know? {target_keyword} is one of the fastest-growing trends in {category}. Here's how {brand_name} is leading the way.",
        f"We get asked about {target_keyword} all the time. Here's our take — and why it matters for your {category} journey.",
        f"Story time! Last week, a customer asked us about {target_keyword}. What happened next surprised everyone...",
    ]
    msg = messages[seed % len(messages)]
    return {
        "message": msg[:500],
        "link": brand_graph.get("website", ""),
        "name": f"{brand_name} | {target_keyword}",
        "description": f"Learn more about {target_keyword} from {brand_name}.",
        "hashtags": [f"#{category.replace(' ', '')}", f"#{target_keyword.replace(' ', '')}"],
        "media_brief": f"Professional image related to {target_keyword}, {brand_name} branding",
    }


async def generate_hashtag_sets(
    channel: str,
    topic: str,
    locale: str,
    brand_graph: dict[str, Any],
) -> dict[str, Any]:
    """Generate optimized hashtag sets via the hashtag engine (stub fallback)."""
    try:
        from prachar_shared.ai_gateway import AIGateway, Tier
        from prachar_shared.adapters.organic.meta_prompts import HASHTAG_ENGINE_PROMPT

        gw = AIGateway()
        prompt = HASHTAG_ENGINE_PROMPT.format(
            channel=channel, brand_graph=brand_graph, topic=topic, locale=locale,
        )
        result = await gw.complete(
            prompt=prompt, tier=Tier.small, task="captions",
            tenant_id=uuid.UUID(int=0), plan="starter",
        )
        if result.json_value:
            return result.json_value
    except Exception as exc:
        logger.warning("hashtag engine AI call failed, using stub: %s", exc)

    seed = _stub_seed(channel, topic, locale)
    base = topic.replace(" ", "").lower()
    cat = brand_graph.get("category", "business").replace(" ", "").lower()
    return {
        "sets": [
            [f"#{base}", f"#{cat}", f"#{locale}", f"#trending", f"#{base}tips"],
            [f"#{base}community", f"#{cat}life", f"#{base}lover", f"#{locale}{cat}"],
            [f"#{base}expert", f"#{cat}daily", f"#{base}guide", f"#{locale}business"],
        ],
        "rationale": "Broad + niche + long-tail mix for balanced reach (stub)",
    }


def compute_posting_windows(
    audience_timezones: list[str],
    channel: str,
) -> list[datetime]:
    """Compute optimal posting windows per audience timezone (not tenant tz).
    Returns a list of UTC datetimes for the next 7 days."""
    # Stub: post at 9am, 1pm, 7pm audience-local time.
    # For now, assume single timezone.
    windows = []
    now = datetime.now(timezone.utc)
    for day_offset in range(7):
        for hour_local in (9, 13, 19):
            # Simplified: assume audience is in UTC+5:30 (India) for stub.
            utc_hour = (hour_local - 5) % 24
            target = now.replace(hour=utc_hour, minute=30, second=0, microsecond=0)
            target += timedelta(days=day_offset)
            if target > now:
                windows.append(target)
    return windows[:7]  # max 1 post/day
