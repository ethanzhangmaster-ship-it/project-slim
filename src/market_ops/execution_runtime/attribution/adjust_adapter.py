"""E10.2 Phase 4 — Adjust Attribution Adapter.

Implements AttributionTracker for Adjust's reporting API.
In sandbox mode (default), returns deterministic mock data
without making real API calls.

Adjust data mapping:
    cost        → spend
    impressions → impressions
    clicks      → clicks
    installs    → installs
    revenue     → revenue_d1/d7/d30
    roi         → roi_d7/roi_d30
"""

from __future__ import annotations

from market_ops.execution_runtime.attribution.base_tracker import (
    AttributionTracker,
    AttributionMetrics,
)


class AdjustConfig:
    """Adjust API configuration.

    Args:
        app_token: Adjust app token.
        api_token: Adjust API token for authentication.
        sandbox: If True, returns mock data. Default: True.
    """

    def __init__(
        self,
        app_token: str = "",
        api_token: str = "",
        sandbox: bool = True,
    ) -> None:
        self.app_token = app_token
        self.api_token = api_token
        self.sandbox = sandbox


class AdjustTracker(AttributionTracker):
    """Adjust reporting API adapter.

    Fetches campaign-level attribution metrics from Adjust.
    Sandbox mode returns mock data for CI and development.

    Usage:
        config = AdjustConfig(app_token="xxx", api_token="yyy", sandbox=True)
        tracker = AdjustTracker(config)
        metrics = tracker.get_campaign_metrics("camp_001", "2024-01-01", "2024-01-07")
    """

    def __init__(self, config: AdjustConfig | None = None) -> None:
        self._config = config or AdjustConfig()

    @property
    def source_name(self) -> str:
        return "adjust"

    def get_campaign_metrics(
        self,
        campaign_id: str,
        start_date: str,
        end_date: str,
    ) -> AttributionMetrics:
        """Fetch campaign metrics from Adjust.

        In sandbox mode, returns deterministic mock data.
        """
        if self._config.sandbox:
            return self._mock_metrics(campaign_id, start_date, end_date)
        return self._fetch_metrics(campaign_id, start_date, end_date)

    def _fetch_metrics(
        self,
        campaign_id: str,
        start_date: str,
        end_date: str,
    ) -> AttributionMetrics:
        """Real API call — not implemented in Phase 4."""
        return AttributionMetrics(
            campaign_id=campaign_id,
            source=self.source_name,
            date_range={"start": start_date, "end": end_date},
        )

    def _mock_metrics(
        self,
        campaign_id: str,
        start_date: str,
        end_date: str,
    ) -> AttributionMetrics:
        """Generate deterministic mock attribution data.

        Uses campaign_id hash to produce consistent but varied
        mock metrics for testing.
        """
        seed = sum(ord(c) for c in campaign_id) % 100
        spend = 500.0 + seed * 10.0
        installs = 200 + seed * 5
        impressions = installs * 50 + seed * 100
        clicks = int(impressions * 0.03)
        revenue_d7 = spend * (1.0 + seed * 0.02)
        revenue_d30 = revenue_d7 * 1.5

        return AttributionMetrics(
            campaign_id=campaign_id,
            spend=spend,
            impressions=impressions,
            clicks=clicks,
            installs=installs,
            conversions=installs,
            revenue_d1=revenue_d7 * 0.3,
            revenue_d7=revenue_d7,
            revenue_d30=revenue_d30,
            roi_d7=round(revenue_d7 / spend, 4) if spend > 0 else 0.0,
            roi_d30=round(revenue_d30 / spend, 4) if spend > 0 else 0.0,
            cpi=round(spend / installs, 2) if installs > 0 else 0.0,
            ctr=round(clicks / impressions, 4) if impressions > 0 else 0.0,
            cvr=round(installs / clicks, 4) if clicks > 0 else 0.0,
            source=self.source_name,
            date_range={"start": start_date, "end": end_date},
        )