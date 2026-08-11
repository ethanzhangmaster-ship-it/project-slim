"""E10.2 Platform Adapter Base — Abstract interface for external platforms.

All concrete adapters (Facebook, Google, TikTok, AppLovin, etc.)
must implement this interface. E10.1 ExecutionEngine interacts
only with this abstraction, never with platform-specific SDKs.

No real platform SDK imports here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AdapterResult:
    """Unified response from any platform adapter.

    All concrete adapters must return this structure so
    ExecutionEngine can process results uniformly.
    """
    success: bool = True
    platform: str = ""
    external_id: str = ""
    operation: str = ""
    raw_response: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "platform": self.platform,
            "external_id": self.external_id,
            "operation": self.operation,
            "raw_response": self.raw_response,
            "error_message": self.error_message,
            "timestamp": self.timestamp,
        }


class PlatformAdapter(ABC):
    """Abstract base for all external platform adapters.

    Concrete implementations:
      - MockPlatformAdapter (testing)
      - FacebookAdsAdapter (future)
      - GoogleAdsAdapter (future)
      - TikTokAdsAdapter (future)
      - AppLovinAdapter (future)

    Usage:
        adapter = registry.get("facebook")
        result = adapter.update_budget("campaign_001", 200.0)
        assert isinstance(result, AdapterResult)
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Human-readable platform identifier.

        Examples: 'facebook', 'google_ads', 'tiktok', 'applovin'
        """
        ...

    @abstractmethod
    def create_campaign(self, config: dict[str, Any]) -> AdapterResult:
        """Create a new campaign on the platform.

        Maps to E10.1 ActionType.RETEST.

        Args:
            config: Campaign configuration (name, budget, targeting, etc.)

        Returns:
            AdapterResult with external campaign ID.
        """
        ...

    @abstractmethod
    def update_budget(self, campaign_id: str, amount: float) -> AdapterResult:
        """Update campaign budget.

        Maps to E10.1 ActionType.SCALE.

        Args:
            campaign_id: Platform-specific campaign identifier.
            amount: New daily budget in platform currency.

        Returns:
            AdapterResult confirming the change.
        """
        ...

    @abstractmethod
    def pause_campaign(self, campaign_id: str) -> AdapterResult:
        """Pause or stop a campaign.

        Maps to E10.1 ActionType.KILL.

        Args:
            campaign_id: Platform-specific campaign identifier.

        Returns:
            AdapterResult confirming the pause.
        """
        ...

    @abstractmethod
    def get_metrics(
        self,
        campaign_id: str,
        date_range: dict[str, str] | None = None,
    ) -> AdapterResult:
        """Retrieve performance metrics for a campaign.

        Maps to E10.1 ActionType.WATCH.

        Args:
            campaign_id: Platform-specific campaign identifier.
            date_range: Optional {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}.

        Returns:
            AdapterResult with metrics in raw_response["metrics"].
        """
        ...
