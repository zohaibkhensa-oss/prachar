from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from ...contracts import AudienceSpec, CreativeAsset, MetricEvent, NativeTargeting, PolicyResult, TokenSet


class AdNetworkAdapter(ABC):
    """Paid ad network adapter interface (spec 03)."""

    network: str

    @abstractmethod
    def translate_audience(self, spec: AudienceSpec) -> NativeTargeting:
        """Translate a canonical AudienceSpec into this network's native targeting payload."""
        ...

    @abstractmethod
    def create_campaign(self, tokens: TokenSet, campaign: dict[str, Any]) -> str:
        """Create a campaign on the network; return the native campaign id."""
        ...

    @abstractmethod
    def upload_creative(self, tokens: TokenSet, creative: CreativeAsset) -> str:
        """Upload a creative asset to the network; return the native creative id."""
        ...

    @abstractmethod
    def set_budget_bid(self, tokens: TokenSet, campaign_id: str, budget: float, bid: dict[str, Any]) -> None:
        """Update the daily budget and bid strategy for a campaign."""
        ...

    @abstractmethod
    def pause(self, tokens: TokenSet, campaign_id: str) -> None:
        """Pause a campaign on the network."""
        ...

    @abstractmethod
    def stats(self, tokens: TokenSet, campaign_id: str, since: datetime) -> list[MetricEvent]:
        """Pull canonical MetricEvents for a campaign since the given timestamp."""
        ...

    @abstractmethod
    def policy_precheck(self, creative: CreativeAsset) -> PolicyResult:
        """Run network-specific policy pre-check on a creative before submission."""
        ...
