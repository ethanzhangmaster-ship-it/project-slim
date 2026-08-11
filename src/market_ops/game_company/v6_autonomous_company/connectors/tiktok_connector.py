from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from ._base import BaseConnector, ConnectorResult, CampaignMetrics


class TikTokAdsConnector(BaseConnector):
    def __init__(self, access_token: str = None, advertiser_id: str = None):
        super().__init__(access_token, advertiser_id)
        self.platform = "tiktok"
        self.advertiser_id = advertiser_id
        self._mock_campaigns = [
            {"id": "tt_camp_001", "name": "Merge Cozy - US - Viral", "status": "ACTIVE"},
            {"id": "tt_camp_002", "name": "Merge Cozy - US - Spark", "status": "ACTIVE"},
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
            campaign_name=f"TikTok Campaign {campaign_id}",
            spend=4560.20,
            impressions=2100000,
            clicks=63000,
            installs=12600,
            ctr=0.03,
            cvr=0.20,
            cpi=0.362,
            cpm=2.17,
            revenue=8120.40,
            roas=1.78,
            purchases=295,
            d1_revenue=2980.60,
            d7_revenue=5760.20,
            d30_revenue=8120.40,
            date=datetime.now().strftime("%Y-%m-%d"),
        )
        return self._make_result(True, {"metrics": metrics.__dict__})

    def get_video_metrics(self, campaign_id: str) -> ConnectorResult:
        if not self._check_rate_limit():
            return self._make_result(False, error="Rate limit exceeded")
        videos = [
            {"video_id": "video_001", "name": "Trend A", "views": 500000, "likes": 25000, "shares": 5000, "ctr": 0.035, "cpi": 0.32},
            {"video_id": "video_002", "name": "Gameplay B", "views": 320000, "likes": 12800, "shares": 2100, "ctr": 0.028, "cpi": 0.38},
        ]
        return self._make_result(True, {"videos": videos})
