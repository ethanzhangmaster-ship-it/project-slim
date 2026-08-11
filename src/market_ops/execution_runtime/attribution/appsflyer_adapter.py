"""E10.2 Phase 4 — AppsFlyer Attribution Adapter.

Implements AttributionTracker for AppsFlyer's reporting API.
In sandbox mode (default), returns deterministic mock data
without making real API calls.

AppsFlyer data mapping:
    cost         → spend
    impressions  → impressions
    clicks       → clicks
    installs     → installs
    af_revenue   → revenue_d1/d7/d30
    roi          → roi_d7/roi_d30
"""

from __future__ import annotations

from market_ops.execution_runtime.attribution.base_tracker import (
    AttributionTracker,
    AttributionMetrics,
)


class AppsFlyerConfig:
    """AppsFlyer API configuration.

    Args:
        dev_key: AppsFlyer dev key.
        api_key: AppsFlyer API key (V2.0).
        app_id: AppsFlyer app ID (e.g., 'id123456789').
        sandbox: If True, returns mock data. Default: True.
    """

    def __init__(
        self,
        dev_key: str = "",
        api_key: str = "",
        app_id: str = "",
        sandbox: bool = True,
    ) -> None:
        self.dev_key = dev_key
        self.api_key = api_key
        self.app_id = app_id
        self.sandbox = sandbox


class AppsFlyerTracker(AttributionTracker):
    """AppsFlyer reporting API adapter.

    Fetches campaign-level attribution metrics from AppsFlyer.
    Sandbox mode returns mock data for CI and development.

    Usage:
        config = AppsFlyerConfig(dev_key="xxx", api_key="yyy", sandbox=True)
        tracker = AppsFlyerTracker(config)
        metrics = tracker.get_campaign_metrics("camp_001", "2024-01-01", "2024-01-07")
    """

    def __init__(self, config: AppsFlyerConfig | None = None) -> None:
        self._config = config or AppsFlyerConfig()

    @property
    def source_name(self) -> str:
        return "appsflyer"

    def get_campaign_metrics(
        self,
        campaign_id: str,
        start_date: str,
        end_date: str,
    ) -> AttributionMetrics:
        """Fetch campaign metrics from AppsFlyer.

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
        mock metrics for testing. AppsFlyer data tends to have
        slightly different patterns than Adjust.
        """
        seed = sum(ord(c) for c in campaign_id) % 100
        spend = 400.0 + seed * 8.0
        installs = 180 + seed * 4
        impressions = installs * 45 + seed * 80
        clicks = int(impressions * 0.035)
        revenue_d7 = spend * (0.9 + seed * 0.025)
        revenue_d30 = revenue_d7 * 1.6

        return AttributionMetrics(
            campaign_id=campaign_id,
            spend=spend,
            impressions=impressions,
            clicks=clicks,
            installs=installs,
            conversions=installs,
            revenue_d1=revenue_d7 * 0.25,
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