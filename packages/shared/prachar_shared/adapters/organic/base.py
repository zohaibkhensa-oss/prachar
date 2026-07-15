from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from ...contracts import ChannelProfile, MetricEvent, PolicyResult, PublishedRef, TokenSet


class ChannelAdapter(ABC):
    """Organic channel adapter interface (spec 03)."""

    channel: str

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
