from __future__ import annotations

from enum import StrEnum

from ..config import get_settings


class Tier(StrEnum):
    small = "small"
    large = "large"


def pick_model(tier: Tier) -> str:
    settings = get_settings()
    if tier is Tier.small:
        return settings.ai_small_model
    return settings.ai_large_model


_BATCH_TASKS = frozenset(
    {
        "captions",
        "tags",
        "metas",
        "geo_probes",
        "creative_copy",
        "generation",
    }
)


def is_batch_task(task: str) -> bool:
    return task in _BATCH_TASKS
