from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LocalePack:
    """Locale pack parameterizing content generation per spec 01 Multi-region.

    Attributes:
        code: BCP-47 locale code (e.g. "hi-IN").
        language: primary language subtag (e.g. "hi").
        region: region subtag (e.g. "IN").
        cultural_register: tone/register guidance for the locale (e.g. "formal-respectful").
        channels: which channels matter per region.
        posting_times: best posting hours (local, 24h).
        hashtag_style: hashtag convention for the locale (e.g. "mixed-bilingual").
    """

    code: str
    language: str
    region: str
    cultural_register: str
    channels: list[str] = field(default_factory=list)
    posting_times: list[int] = field(default_factory=list)
    hashtag_style: str = "standard"


# ---------------------------------------------------------------------------
# Supported locale packs (spec 01 Multi-region: EN(US/UK/IN/AU), HI, AR, ES,
# PT-BR, ID, JA, KO, DE, FR, RU).
# ---------------------------------------------------------------------------
SUPPORTED_LOCALES: dict[str, LocalePack] = {
    "en-US": LocalePack(
        code="en-US",
        language="en",
        region="US",
        cultural_register="casual-confident",
        channels=["google", "instagram", "youtube", "tiktok"],
        posting_times=[9, 12, 18, 21],
        hashtag_style="short-punchy",
    ),
    "en-GB": LocalePack(
        code="en-GB",
        language="en",
        region="GB",
        cultural_register="understated-witty",
        channels=["google", "instagram", "linkedin", "youtube"],
        posting_times=[8, 13, 17, 20],
        hashtag_style="minimal",
    ),
    "en-IN": LocalePack(
        code="en-IN",
        language="en",
        region="IN",
        cultural_register="warm-aspirational",
        channels=["whatsapp", "instagram", "youtube", "google"],
        posting_times=[10, 13, 19, 21],
        hashtag_style="mixed-bilingual",
    ),
    "en-AU": LocalePack(
        code="en-AU",
        language="en",
        region="AU",
        cultural_register="friendly-laidback",
        channels=["google", "instagram", "youtube", "tiktok"],
        posting_times=[8, 12, 18, 20],
        hashtag_style="short-punchy",
    ),
    "hi-IN": LocalePack(
        code="hi-IN",
        language="hi",
        region="IN",
        cultural_register="formal-respectful",
        channels=["whatsapp", "instagram", "youtube", "google"],
        posting_times=[10, 13, 19, 21],
        hashtag_style="devanagari-mixed",
    ),
    "ar-SA": LocalePack(
        code="ar-SA",
        language="ar",
        region="SA",
        cultural_register="formal-respectful-rtl",
        channels=["snapchat", "instagram", "google"],
        posting_times=[10, 14, 20, 22],
        hashtag_style="arabic",
    ),
    "es-ES": LocalePack(
        code="es-ES",
        language="es",
        region="ES",
        cultural_register="warm-expressive",
        channels=["google", "instagram", "youtube", "linkedin"],
        posting_times=[9, 13, 18, 21],
        hashtag_style="spanish",
    ),
    "pt-BR": LocalePack(
        code="pt-BR",
        language="pt",
        region="BR",
        cultural_register="energetic-friendly",
        channels=["google", "instagram", "youtube", "tiktok"],
        posting_times=[9, 12, 18, 21],
        hashtag_style="portuguese",
    ),
    "id-ID": LocalePack(
        code="id-ID",
        language="id",
        region="ID",
        cultural_register="friendly-community",
        channels=["google", "instagram", "youtube", "tiktok"],
        posting_times=[9, 12, 18, 20],
        hashtag_style="indonesian",
    ),
    "ja-JP": LocalePack(
        code="ja-JP",
        language="ja",
        region="JP",
        cultural_register="polite-formal-keigo",
        channels=["line", "youtube", "google"],
        posting_times=[8, 12, 19, 21],
        hashtag_style="japanese-minimal",
    ),
    "ko-KR": LocalePack(
        code="ko-KR",
        language="ko",
        region="KR",
        cultural_register="polite-hierarchical",
        channels=["naver", "kakao", "youtube"],
        posting_times=[8, 12, 18, 21],
        hashtag_style="korean",
    ),
    "de-DE": LocalePack(
        code="de-DE",
        language="de",
        region="DE",
        cultural_register="precise-professional",
        channels=["google", "instagram", "linkedin", "youtube"],
        posting_times=[8, 12, 17, 19],
        hashtag_style="minimal",
    ),
    "fr-FR": LocalePack(
        code="fr-FR",
        language="fr",
        region="FR",
        cultural_register="elegant-articulate",
        channels=["google", "instagram", "linkedin", "youtube"],
        posting_times=[9, 13, 18, 20],
        hashtag_style="french",
    ),
    "ru-RU": LocalePack(
        code="ru-RU",
        language="ru",
        region="RU",
        cultural_register="direct-formal",
        channels=["vk", "telegram", "yandex"],
        posting_times=[9, 13, 18, 21],
        hashtag_style="cyrillic",
    ),
}


# ---------------------------------------------------------------------------
# Region routing table (spec 01 Multi-region): which channels matter per region.
# ---------------------------------------------------------------------------
REGION_ROUTES: dict[str, list[str]] = {
    "IN": ["whatsapp", "instagram", "youtube", "google"],
    "KR": ["naver", "kakao", "youtube"],
    "RU": ["vk", "telegram", "yandex"],
    "CIS": ["vk", "telegram", "yandex"],
    "JP": ["line", "youtube"],
    "MENA": ["snapchat", "instagram"],
    "Americas": ["google", "instagram", "youtube", "tiktok"],
    "Europe": ["google", "instagram", "linkedin", "youtube"],
}


def get_locale_pack(code: str) -> LocalePack | None:
    """Return the LocalePack for a BCP-47 code, or None if unsupported."""
    pack = SUPPORTED_LOCALES.get(code)
    if pack is None:
        logger.debug("get_locale_pack: no pack for code=%s", code)
    return pack


def channels_for_region(region: str) -> list[str]:
    """Return the list of channels that matter for a region (spec 01 region routing).

    Falls back to the region subtag of any matching locale pack if the region
    is not directly in REGION_ROUTES.
    """
    routes = REGION_ROUTES.get(region)
    if routes is not None:
        return list(routes)
    # Fallback: search locale packs whose region matches.
    for pack in SUPPORTED_LOCALES.values():
        if pack.region == region:
            return list(pack.channels)
    logger.debug("channels_for_region: no routes for region=%s", region)
    return []
