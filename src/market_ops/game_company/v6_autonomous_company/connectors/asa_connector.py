from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from ._base import BaseConnector, ConnectorResult, CampaignMetrics


class AppleSearchAdsConnector(BaseConnector):
    def __init__(self, org_id: str = None, access_token: str = None):
        super().__init__(access_token, org_id)
        self.platform = "apple_search_ads"
        self.org_id = org_id
        self._mock_campaigns = [
            {"id": "asa_camp_001", "name": "Merge Cozy - Brand", "status": "ENABLED"},
            {"id": "asa_camp_002", "name": "Merge Cozy - Generic", "status": "ENABLED"},
            {"id": "asa_camp_003", "name": "Merge Cozy - Competitor", "status": "ENABLED"},
        ]

    def get_campaigns(self) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        return self._make_result(True, {"campaigns": self._mock_campaigns})

    def get_campaign_metrics(self, campaign_id: str) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        metrics = CampaignMetrics(
            campaign_id=campaign_id,
            campaign_name=f"ASA Campaign {campaign_id}",
            spend=2180.50,
            impressions=420000,
            clicks=18900,
            installs=4150,
            ctr=0.045,
            cvr=0.22,
            cpi=0.525,
            cpm=5.19,
            revenue=5840.70,
            roas=2.68,
            purchases=185,
            d1_revenue=2100.30,
            d7_revenue=4120.80,
            d30_revenue=5840.70,
            date=datetime.now().strftime("%Y-%m-%d"),
        )
        return self._make_result(True, {"metrics": metrics.__dict__})

    def get_search_terms(self, campaign_id: str) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        search_terms = [
            {"term": "merge cozy game", "impressions": 15000, "taps": 675, "installs": 180, "cpi": 1.2},
            {"term": "merge mansion", "impressions": 25000, "taps": 1125, "installs": 280, "cpi": 0.95},
            {"term": "puzzle merge", "impressions": 8000, "taps": 360, "installs": 95, "cpi": 1.05},
        ]
        return self._make_result(True, {"search_terms": search_terms})
