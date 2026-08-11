from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class SearchPopularity:
    keyword: str
    popularity: int = 0
    competition: str = "low"
    competition_index: int = 0
    avg_cpc: float = 0.0
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "popularity": self.popularity,
            "competition": self.competition,
            "competition_index": self.competition_index,
            "avg_cpc": self.avg_cpc,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class ASAKeyword:
    id: str
    campaign_id: str
    ad_group_id: str
    text: str
    match_type: str = "broad"
    bid_amount: float = 0.0
    status: str = "enabled"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "ad_group_id": self.ad_group_id,
            "text": self.text,
            "match_type": self.match_type,
            "bid_amount": self.bid_amount,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class ASACampaign:
    id: str
    name: str
    status: str = "active"
    budget: float = 0.0
    budget_type: str = "daily"
    country_or_region: str = "US"
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
            "budget_type": self.budget_type,
            "country_or_region": self.country_or_region,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class ASAConnector:
    def __init__(self):
        self._connected = False
        self._campaigns: Dict[str, ASACampaign] = {}
        self._keywords: Dict[str, List[ASAKeyword]] = {}
        self._sync_history: List[Dict[str, Any]] = []

    def connect(self) -> bool:
        self._connected = True
        return True

    def get_campaigns(self) -> List[ASACampaign]:
        if not self._connected:
            return []
        if not self._campaigns:
            self._mock_campaigns()
        return list(self._campaigns.values())

    def get_keywords(self, campaign_id: str) -> List[ASAKeyword]:
        if not self._connected or campaign_id not in self._campaigns:
            return []
        if campaign_id not in self._keywords:
            self._keywords[campaign_id] = [
                ASAKeyword(
                    id=f"asa_keyword_{campaign_id}_1",
                    campaign_id=campaign_id,
                    ad_group_id=f"asa_adgroup_{campaign_id}_1",
                    text="strategy game",
                    match_type="broad",
                    bid_amount=3.00,
                    status="enabled",
                ),
                ASAKeyword(
                    id=f"asa_keyword_{campaign_id}_2",
                    campaign_id=campaign_id,
                    ad_group_id=f"asa_adgroup_{campaign_id}_1",
                    text="tower defense",
                    match_type="exact",
                    bid_amount=4.50,
                    status="enabled",
                ),
                ASAKeyword(
                    id=f"asa_keyword_{campaign_id}_3",
                    campaign_id=campaign_id,
                    ad_group_id=f"asa_adgroup_{campaign_id}_2",
                    text="free games",
                    match_type="broad",
                    bid_amount=2.00,
                    status="paused",
                ),
            ]
        return self._keywords[campaign_id]

    def get_search_popularity(self, keyword: str) -> Optional[SearchPopularity]:
        if not self._connected:
            return None
        return SearchPopularity(
            keyword=keyword,
            popularity=85,
            competition="high",
            competition_index=9,
            avg_cpc=3.20,
        )

    def get_tap_data(self, campaign_id: str) -> Dict[str, Any]:
        if not self._connected or campaign_id not in self._campaigns:
            return {"error": "Campaign not found"}
        return {
            "campaign_id": campaign_id,
            "taps": 1200,
            "installs": 350,
            "tap_to_install_rate": 29.17,
            "avg_tap_position": 2.5,
            "date_range": "last_7_days",
        }

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
            "asa_campaign_1": ASACampaign(
                id="asa_campaign_1",
                name="App Store - Game Launch",
                status="active",
                budget=6000.0,
                budget_type="daily",
                country_or_region="US",
            ),
            "asa_campaign_2": ASACampaign(
                id="asa_campaign_2",
                name="App Store - Global UA",
                status="active",
                budget=15000.0,
                budget_type="total",
                country_or_region="GB",
            ),
            "asa_campaign_3": ASACampaign(
                id="asa_campaign_3",
                name="App Store - Brand",
                status="active",
                budget=4000.0,
                budget_type="daily",
                country_or_region="JP",
            ),
        }