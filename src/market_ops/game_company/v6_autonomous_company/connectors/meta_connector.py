from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from ._base import BaseConnector, ConnectorResult, CampaignMetrics


class MetaAdsConnector(BaseConnector):
    def __init__(self, access_token: str = None, account_id: str = None):
        super().__init__(access_token, account_id)
        self.platform = "meta"
        self._mock_campaigns = [
            {"id": "meta_camp_001", "name": "Merge Cozy - US - Video", "status": "ACTIVE"},
            {"id": "meta_camp_002", "name": "Merge Cozy - US - Carousel", "status": "ACTIVE"},
            {"id": "meta_camp_003", "name": "Merge Cozy - EU - Broad", "status": "PAUSED"},
        ]

    def get_campaigns(self, status: str = "ACTIVE") -> ConnectorResult:
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
            campaign_name=f"Campaign {campaign_id}",
            spend=5234.56,
            impressions=1250000,
            clicks=37500,
            installs=8920,
            ctr=0.03,
            cvr=0.238,
            cpi=0.587,
            cpm=4.19,
            revenue=12560.30,
            roas=2.4,
            purchases=342,
            d1_revenue=4520.10,
            d7_revenue=8930.50,
            d30_revenue=12560.30,
            date=end_date,
        )
        return self._make_result(True, {"metrics": metrics.__dict__})

    def get_adset_metrics(self, campaign_id: str) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        adsets = [
            {"adset_id": "adset_001", "name": "Interest - Gaming", "spend": 1200, "installs": 2100, "cpi": 0.57},
            {"adset_id": "adset_002", "name": "Lookalike 1%", "spend": 2500, "installs": 4200, "cpi": 0.595},
            {"adset_id": "adset_003", "name": "Broad", "spend": 1534.56, "installs": 2620, "cpi": 0.586},
        ]
        return self._make_result(True, {"adsets": adsets})

    def get_creative_performance(self, campaign_id: str) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        creatives = [
            {"creative_id": "creative_001", "name": "Merge Video V1", "spend": 1500, "ctr": 0.035, "cpi": 0.52},
            {"creative_id": "creative_002", "name": "Merge Video V2", "spend": 2000, "ctr": 0.032, "cpi": 0.58},
            {"creative_id": "creative_003", "name": "Carousel A", "spend": 1734.56, "ctr": 0.028, "cpi": 0.65},
        ]
        return self._make_result(True, {"creatives": creatives})

    def update_budget(self, campaign_id: str, new_budget: float) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        return self._make_result(True, {"campaign_id": campaign_id, "new_budget": new_budget, "status": "updated"})

    def create_campaign(self, name: str, budget: float) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        campaign_id = f"meta_camp_{hash(name) % 100000:05d}"
        return self._make_result(True, {"campaign_id": campaign_id, "name": name, "budget": budget, "status": "ACTIVE"})

    def pause_campaign(self, campaign_id: str) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        return self._make_result(True, {"campaign_id": campaign_id, "status": "PAUSED"})
