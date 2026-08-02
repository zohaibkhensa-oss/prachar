"""All creative format specs, registered on import."""
from __future__ import annotations

from ..base import CreativeFormatSpec
from .carousel import CAROUSEL
from .email import EMAIL
from .facebook import FACEBOOK
from .landing_page import LANDING_PAGE
from .linkedin import LINKEDIN
from .poster import POSTER
from .sms import SMS
from .story import STORY
from .video_script import VIDEO_SCRIPT
from .whatsapp import WHATSAPP

ALL_FORMATS: list[CreativeFormatSpec] = [
    POSTER,
    VIDEO_SCRIPT,
    CAROUSEL,
    STORY,
    WHATSAPP,
    FACEBOOK,
    LINKEDIN,
    EMAIL,
    LANDING_PAGE,
    SMS,
]

__all__ = [
    "ALL_FORMATS",
    "POSTER",
    "VIDEO_SCRIPT",
    "CAROUSEL",
    "STORY",
    "WHATSAPP",
    "FACEBOOK",
    "LINKEDIN",
    "EMAIL",
    "LANDING_PAGE",
    "SMS",
]
