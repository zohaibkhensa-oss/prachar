from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from ...config import get_settings
from ...contracts import ChannelProfile, MetricEvent, PolicyResult, PublishedRef, TokenSet


def redirect_uri_for(channel: str) -> str:
    """Build the OAuth redirect URI for a channel using the configured WEB_URL.

    Pattern: {WEB_URL}/app/connections/{channel}/callback
    This must match the redirect URI registered in each provider's developer console.
    """
    web_url = get_settings().web_url or "http://localhost:3002"
    return f"{web_url}/app/connections/{channel}/callback"


class ChannelAdapter(ABC):
    """Organic channel adapter interface (spec 03)."""

    channel: str

    @property
    def redirect_uri(self) -> str:
        """Configurable redirect URI for this channel."""
        return redirect_uri_for(self.channel)

    @abstractmethod
    def auth_url(self, state: str) -> str:
        """Return the OAuth authorization URL for the given state token."""
        ...

    @abstractmethod
    def exchange_code(self, code: str) -> TokenSet:
        """Exchange an OAuth authorization code for a TokenSet."""
        ...

    @abstractmethod
    def fetch_profile(self, tokens: TokenSet) -> ChannelProfile:
        """Fetch the connected account's public profile."""
        ...

    @abstractmethod
    def generate_schema(self) -> dict[str, Any]:
        """Return the JSON schema that a content payload must satisfy for this channel."""
        ...

    @abstractmethod
    def policy_gate(self, payload: dict[str, Any]) -> PolicyResult:
        """Run ToS + claims pre-check on a content payload before publishing."""
        ...

    @abstractmethod
    def publish(self, tokens: TokenSet, payload: dict[str, Any]) -> PublishedRef:
        """Publish a content payload to the channel; return a PublishedRef."""
        ...

    @abstractmethod
    def metrics(self, tokens: TokenSet, since: datetime) -> list[MetricEvent]:
        """Pull canonical MetricEvents for this channel since the given timestamp."""
        ...
