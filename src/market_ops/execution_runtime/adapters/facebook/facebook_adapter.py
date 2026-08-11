"""E10.2 Facebook Ads Adapter — Implements PlatformAdapter for Facebook.

Wires together FacebookClient and FacebookMapper to translate
E10.1 ExecutionTasks into Facebook Graph API calls.

Flow:
    ExecutionTask
        │
        ▼
    FacebookAdsAdapter
        │
        ├── FacebookMapper  (action → API params)
        │
        └── FacebookClient  (HTTP → Graph API)
        │
        ▼
    AdapterResult

In sandbox mode (default), no real API calls are made.
"""

from __future__ import annotations

from typing import Any

from market_ops.execution_runtime.adapters.base_adapter import PlatformAdapter, AdapterResult
from market_ops.execution_runtime.adapters.facebook.facebook_client import FacebookClient
from market_ops.execution_runtime.adapters.facebook.facebook_config import FacebookConfig
from market_ops.execution_runtime.adapters.facebook.facebook_mapper import FacebookMapper
from market_ops.execution_runtime.adapters.facebook.exceptions import (
    FacebookAdapterError,
    FacebookAPIError,
)


class FacebookAdsAdapter(PlatformAdapter):
    """Facebook Ads platform adapter.

    Implements PlatformAdapter ABC. In sandbox mode (default),
    uses mock responses. Set sandbox=False in config to make
    real Graph API calls.

    Args:
        config: FacebookConfig. If None, loads from env with sandbox=True.
        client: Optional pre-configured FacebookClient (for testing).

    Usage:
        adapter = FacebookAdsAdapter()
        result = adapter.update_budget("23842567890012345", 500.0)
    """

    def __init__(
        self,
        config: FacebookConfig | None = None,
        client: FacebookClient | None = None,
    ) -> None:
        self._config = config or FacebookConfig()
        self._client = client or FacebookClient(self._config)
        self._mapper = FacebookMapper()

    # ───────────────────────────────────────────────────────
    # PlatformAdapter interface
    # ───────────────────────────────────────────────────────

    @property
    def platform_name(self) -> str:
        return "facebook"

    def create_campaign(self, config: dict[str, Any]) -> AdapterResult:
        """Create a new campaign via duplication. Maps to RETEST.

        Args:
            config: Must contain 'source_campaign_id' and optionally 'budget'.

        Returns:
            AdapterResult with new campaign ID.
        """
        source_id = config.get("source_campaign_id", "")
        try:
            response = self._client.duplicate_campaign(source_id)
            return AdapterResult(
                success=True,
                platform=self.platform_name,
                external_id=response.get("data", {}).get("id", source_id),
                operation="create_campaign",
                raw_response=response,
            )
        except FacebookAdapterError as exc:
            return AdapterResult(
                success=False,
                platform=self.platform_name,
                operation="create_campaign",
                error_message=str(exc),
                raw_response=exc.raw_response,
            )

    def update_budget(self, campaign_id: str, amount: float) -> AdapterResult:
        """Update campaign daily budget. Maps to SCALE.

        Args:
            campaign_id: Facebook campaign ID.
            amount: New daily budget in dollars (e.g., 500.0).

        Returns:
            AdapterResult confirming budget change.
        """
        try:
            daily_budget = int(round(amount * 100))
            response = self._client.update_campaign_budget(campaign_id, daily_budget)
            return AdapterResult(
                success=True,
                platform=self.platform_name,
                external_id=campaign_id,
                operation="update_budget",
                raw_response={
                    **response,
                    "budget_applied": amount,
                    "daily_budget_cents": daily_budget,
                },
            )
        except FacebookAdapterError as exc:
            return AdapterResult(
                success=False,
                platform=self.platform_name,
                external_id=campaign_id,
                operation="update_budget",
                error_message=str(exc),
                raw_response=exc.raw_response,
            )

    def pause_campaign(self, campaign_id: str) -> AdapterResult:
        """Pause a campaign. Maps to KILL.

        Args:
            campaign_id: Facebook campaign ID.

        Returns:
            AdapterResult confirming pause.
        """
        try:
            response = self._client.pause_campaign(campaign_id)
            return AdapterResult(
                success=True,
                platform=self.platform_name,
                external_id=campaign_id,
                operation="pause_campaign",
                raw_response={
                    **response,
                    "effective_status": "PAUSED",
                },
            )
        except FacebookAdapterError as exc:
            return AdapterResult(
                success=False,
                platform=self.platform_name,
                external_id=campaign_id,
                operation="pause_campaign",
                error_message=str(exc),
                raw_response=exc.raw_response,
            )

    def get_metrics(
        self,
        campaign_id: str,
        date_range: dict[str, str] | None = None,
    ) -> AdapterResult:
        """Get campaign performance metrics. Maps to WATCH.

        Args:
            campaign_id: Facebook campaign ID.
            date_range: Optional date range filter.

        Returns:
            AdapterResult with metrics in raw_response.
        """
        try:
            response = self._client.get_campaign(campaign_id)
            data = response.get("data", {})
            insights = data.get("insights", {}).get("data", [{}])[0] if data.get("insights") else {}

            return AdapterResult(
                success=True,
                platform=self.platform_name,
                external_id=campaign_id,
                operation="get_metrics",
                raw_response={
                    **response,
                    "metrics": {
                        "impressions": int(insights.get("impressions", 0)),
                        "clicks": int(insights.get("clicks", 0)),
                        "spend": float(insights.get("spend", 0)),
                        "cpm": float(insights.get("cpm", 0)),
                        "cpc": float(insights.get("cpc", 0)),
                        "ctr": float(insights.get("ctr", 0)),
                    },
                    "campaign_status": data.get("status", "UNKNOWN"),
                },
            )
        except FacebookAdapterError as exc:
            return AdapterResult(
                success=False,
                platform=self.platform_name,
                external_id=campaign_id,
                operation="get_metrics",
                error_message=str(exc),
                raw_response=exc.raw_response,
            )

    # ───────────────────────────────────────────────────────
    # Properties
    # ───────────────────────────────────────────────────────

    @property
    def config(self) -> FacebookConfig:
        return self._config

    @property
    def client(self) -> FacebookClient:
        return self._client

    @property
    def mapper(self) -> FacebookMapper:
        return self._mapper