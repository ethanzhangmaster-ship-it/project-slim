from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class PerformanceMetrics:
    campaign_id: str
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    conversions: int = 0
    ctr: float = 0.0
    cpc: float = 0.0
    cpa: float = 0.0
    quality_score: int = 0
    date_range: str = ""
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "spend": self.spend,
            "conversions": self.conversions,
            "ctr": self.ctr,
            "cpc": self.cpc,
            "cpa": self.cpa,
            "quality_score": self.quality_score,
            "date_range": self.date_range,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class SearchTerm:
    id: str
    campaign_id: str
    keyword: str
    impressions: int = 0
    clicks: int = 0
    cost: float = 0.0
    conversions: int = 0
    match_type: str = "broad"
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "keyword": self.keyword,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "cost": self.cost,
            "conversions": self.conversions,
            "match_type": self.match_type,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Keyword:
    id: str
    campaign_id: str
    ad_group_id: str
    text: str
    match_type: str = "broad"
    bid: float = 0.0
    status: str = "enabled"
    quality_score: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "ad_group_id": self.ad_group_id,
            "text": self.text,
            "match_type": self.match_type,
            "bid": self.bid,
            "status": self.status,
            "quality_score": self.quality_score,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class GoogleCampaign:
    id: str
    name: str
    status: str = "enabled"
    budget: float = 0.0
    bidding_strategy: str = ""
    start_date: datetime = field(default_factory=datetime.now)
    end_date: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "budget": self.budget,
            "bidding_strategy": self.bidding_strategy,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class GoogleAdsConnector:
    def __init__(self):
        self._connected = False
        self._campaigns: Dict[str, GoogleCampaign] = {}
        self._keywords: Dict[str, List[Keyword]] = {}
        self._search_terms: Dict[str, List[SearchTerm]] = {}
        self._sync_history: List[Dict[str, Any]] = []

    def connect(self) -> bool:
        self._connected = True
        return True

    def get_campaigns(self) -> List[GoogleCampaign]:
        if not self._connected:
            return []
        if not self._campaigns:
            self._mock_campaigns()
        return list(self._campaigns.values())

    def get_keywords(self, campaign_id: str) -> List[Keyword]:
        if not self._connected or campaign_id not in self._campaigns:
            return []
        if campaign_id not in self._keywords:
            self._keywords[campaign_id] = [
                Keyword(
                    id=f"keyword_{campaign_id}_1",
                    campaign_id=campaign_id,
                    ad_group_id=f"adgroup_{campaign_id}_1",
                    text="mobile game download",
                    match_type="exact",
                    bid=2.50,
                    status="enabled",
                    quality_score=8,
                ),
                Keyword(
                    id=f"keyword_{campaign_id}_2",
                    campaign_id=campaign_id,
                    ad_group_id=f"adgroup_{campaign_id}_1",
                    text="best strategy game",
                    match_type="phrase",
                    bid=1.80,
                    status="enabled",
                    quality_score=7,
                ),
                Keyword(
                    id=f"keyword_{campaign_id}_3",
                    campaign_id=campaign_id,
                    ad_group_id=f"adgroup_{campaign_id}_2",
                    text="free online game",
                    match_type="broad",
                    bid=1.20,
                    status="paused",
                    quality_score=6,
                ),
            ]
        return self._keywords[campaign_id]

    def get_search_terms(self, campaign_id: str) -> List[SearchTerm]:
        if not self._connected or campaign_id not in self._campaigns:
            return []
        if campaign_id not in self._search_terms:
            self._search_terms[campaign_id] = [
                SearchTerm(
                    id=f"searchterm_{campaign_id}_1",
                    campaign_id=campaign_id,
                    keyword="download mobile game free",
                    impressions=2500,
                    clicks=120,
                    cost=280.0,
                    conversions=8,
                    match_type="broad",
                ),
                SearchTerm(
                    id=f"searchterm_{campaign_id}_2",
                    campaign_id=campaign_id,
                    keyword="best strategy games 2024",
                    impressions=1800,
                    clicks=95,
                    cost=220.0,
                    conversions=12,
                    match_type="phrase",
                ),
                SearchTerm(
                    id=f"searchterm_{campaign_id}_3",
                    campaign_id=campaign_id,
                    keyword="mobile game download",
                    impressions=3200,
                    clicks=200,
                    cost=500.0,
                    conversions=15,
                    match_type="exact",
                ),
            ]
        return self._search_terms[campaign_id]

    def get_performance(self, campaign_id: str) -> Optional[PerformanceMetrics]:
        if not self._connected or campaign_id not in self._campaigns:
            return None
        return PerformanceMetrics(
            campaign_id=campaign_id,
            impressions=12500,
            clicks=680,
            spend=1850.0,
            conversions=32,
            ctr=5.44,
            cpc=2.72,
            cpa=57.81,
            quality_score=7,
            date_range="last_7_days",
        )

    def sync_data(self) -> Dict[str, Any]:
        if not self._connected:
            return {"success": False, "message": "Not connected"}
        self._mock_campaigns()
        sync_time = datetime.now()
        self._sync_history.append({
            "timestamp": sync_time.isoformat(),
            "campaign_count": len(self._campaigns),
            "success": True,
        })
        return {
            "success": True,
            "campaigns_synced": len(self._campaigns),
            "sync_time": sync_time.isoformat(),
        }

    def _mock_campaigns(self):
        self._campaigns = {
            "google_campaign_1": GoogleCampaign(
                id="google_campaign_1",
                name="Search - Game Downloads",
                status="enabled",
                budget=8000.0,
                bidding_strategy="MAXIMIZE_CONVERSIONS",
            ),
            "google_campaign_2": GoogleCampaign(
                id="google_campaign_2",
                name="Display - Brand Awareness",
                status="enabled",
                budget=4000.0,
                bidding_strategy="TARGET_CPA",
            ),
            "google_campaign_3": GoogleCampaign(
                id="google_campaign_3",
                name="Performance Max - UA",
                status="enabled",
                budget=12000.0,
                bidding_strategy="MAXIMIZE_CONVERSION_VALUE",
            ),
        }