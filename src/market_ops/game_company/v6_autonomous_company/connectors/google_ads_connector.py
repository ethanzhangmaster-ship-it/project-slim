from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from ._base import BaseConnector, ConnectorResult, CampaignMetrics


class GoogleAdsConnector(BaseConnector):
    def __init__(self, developer_token: str = None, customer_id: str = None):
        super().__init__(developer_token, customer_id)
        self.platform = "google_ads"
        self._mock_campaigns = [
            {"id": "ggl_camp_001", "name": "Merge Cozy - US - Search", "status": "ENABLED"},
            {"id": "ggl_camp_002", "name": "Merge Cozy - US - UAC", "status": "ENABLED"},
        ]

    def get_campaigns(self, status: str = "ENABLED") -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        campaigns = [c for c in self._mock_campaigns if c["status"] == status or status == "ALL"]
        return self._make_result(True, {"campaigns": campaigns})

    def get_campaign_metrics(
        self,
        campaign_id: str,
        start_date: str = None,
        end_date: str = None,
    ) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        metrics = CampaignMetrics(
            campaign_id=campaign_id,
            campaign_name=f"Google Campaign {campaign_id}",
            spend=3420.80,
            impressions=890000,
            clicks=24500,
            installs=6280,
            ctr=0.0275,
            cvr=0.256,
            cpi=0.545,
            cpm=3.84,
            revenue=9150.20,
            roas=2.67,
            purchases=285,
            d1_revenue=3240.00,
            d7_revenue=6420.50,
            d30_revenue=9150.20,
            date=end_date,
        )
        return self._make_result(True, {"metrics": metrics.__dict__})

    def get_keywords(self, campaign_id: str) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        keywords = [
            {"keyword": "merge game", "search_volume": 50000, "cpc": 0.45, "ctr": 0.03, "conversions": 450},
            {"keyword": "puzzle game", "search_volume": 80000, "cpc": 0.38, "ctr": 0.025, "conversions": 380},
            {"keyword": "decorate game", "search_volume": 30000, "cpc": 0.52, "ctr": 0.035, "conversions": 320},
        ]
        return self._make_result(True, {"keywords": keywords})

    def update_bid(self, ad_group_id: str, new_bid: float) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        return self._make_result(True, {"ad_group_id": ad_group_id, "new_bid": new_bid, "status": "updated"})
