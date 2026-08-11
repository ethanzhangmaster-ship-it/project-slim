from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from ._base import BaseConnector, ConnectorResult


class AdjustConnector(BaseConnector):
    def __init__(self, app_token: str = None, api_token: str = None):
        super().__init__(api_token, app_token)
        self.platform = "adjust"
        self.app_token = app_token

    def get_installs(
        self,
        start_date: str = None,
        end_date: str = None,
        attribution_source: str = None,
    ) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        installs = {
            "total_installs": 32500,
            "organic": 8200,
            "paid": 24300,
            "by_network": {
                "Facebook Ads": 12500,
                "Google Ads": 6800,
                "Apple Search Ads": 3100,
                "TikTok Ads": 1900,
            },
            "by_country": {"US": 15800, "GB": 3200, "DE": 2800, "JP": 2100},
            "start_date": start_date,
            "end_date": end_date,
        }
        return self._make_result(True, installs)

    def get_retention(self, cohort_date: str) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        retention = {
            "cohort_date": cohort_date,
            "installs": 4500,
            "d1": 0.38,
            "d3": 0.25,
            "d7": 0.18,
            "d14": 0.12,
            "d30": 0.08,
            "by_network": {
                "Facebook Ads": {"d1": 0.42, "d7": 0.20, "d30": 0.09},
                "Google Ads": {"d1": 0.40, "d7": 0.19, "d30": 0.085},
                "Apple Search Ads": {"d1": 0.45, "d7": 0.22, "d30": 0.10},
                "TikTok Ads": {"d1": 0.35, "d7": 0.15, "d30": 0.06},
            },
        }
        return self._make_result(True, retention)

    def get_revenue(self, start_date: str = None, end_date: str = None) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        revenue = {
            "total_revenue": 89500.50,
            "ad_revenue": 52300.25,
            "iap_revenue": 37200.25,
            "arpdau": 0.15,
            "ltv_d30": 3.25,
            "by_network": {
                "Facebook Ads": {"revenue": 35600, "ltv": 2.85},
                "Google Ads": {"revenue": 22800, "ltv": 3.35},
                "Apple Search Ads": {"revenue": 18900, "ltv": 6.10},
                "TikTok Ads": {"revenue": 12200, "ltv": 6.42},
            },
        }
        return self._make_result(True, revenue)

    def get_events(self, event_name: str = None) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        events = {
            "total_events": 2450000,
            "event_counts": {
                "session_start": 890000,
                "tutorial_complete": 28000,
                "level_complete": 1560000,
                "purchase": 12500,
                "ad_impression": 820000,
            },
        }
        return self._make_result(True, events)
