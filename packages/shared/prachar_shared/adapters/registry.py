from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ads.base import AdNetworkAdapter
    from .organic.base import ChannelAdapter

logger = logging.getLogger(__name__)

_ORGANIC: dict[str, type[ChannelAdapter]] = {}
_ADS: dict[str, type[AdNetworkAdapter]] = {}

# Channels considered "launch" channels — enabled by default unless explicitly disabled.
LAUNCH_CHANNELS = frozenset({"google", "gsc", "gmb", "youtube", "instagram", "facebook", "meta_ads", "google_ads"})


def register_organic(adapter_cls: type[ChannelAdapter]) -> type[ChannelAdapter]:
    channel = adapter_cls.channel
    if not channel:
        raise ValueError(f"adapter {adapter_cls} has no channel attribute")
    _ORGANIC[channel] = adapter_cls
    logger.debug("registered organic adapter: %s", channel)
    return adapter_cls


def get_organic(channel: str) -> ChannelAdapter:
    try:
        cls = _ORGANIC[channel]
    except KeyError as e:
        raise KeyError(f"no organic adapter registered for channel={channel!r}") from e
    return cls()


def register_ads(adapter_cls: type[AdNetworkAdapter]) -> type[AdNetworkAdapter]:
    network = adapter_cls.network
    if not network:
        raise ValueError(f"adapter {adapter_cls} has no network attribute")
    _ADS[network] = adapter_cls
    logger.debug("registered ads adapter: %s", network)
    return adapter_cls


def get_ads(network: str) -> AdNetworkAdapter:
    try:
        cls = _ADS[network]
    except KeyError as e:
        raise KeyError(f"no ads adapter registered for network={network!r}") from e
    return cls()


def is_enabled(channel: str) -> bool:
    """Feature-flag aware: reads FEATURE_<CHANNEL> env. Launch channels default on; others off."""
    env_val = os.environ.get(f"FEATURE_{channel.upper()}", "").strip().lower()
    if env_val in ("on", "1", "true", "yes"):
        return True
    if env_val in ("off", "0", "false", "no"):
        return False
    return channel in LAUNCH_CHANNELS
