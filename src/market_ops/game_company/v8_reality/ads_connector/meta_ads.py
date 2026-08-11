from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class CampaignMetrics:
    campaign_id: str
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    conversions: int = 0
    cpm: float = 0.0
    cpc: float = 0.0
    cpa: float = 0.0
    date_range: str = ""
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "spend": self.spend,
            "conversions": self.conversions,
            "cpm": self.cpm,
            "cpc": self.cpc,
            "cpa": self.cpa,
            "date_range": self.date_range,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class AdSet:
    id: str
    name: str
    campaign_id: str
    budget: float = 0.0
    bid_strategy: str = ""
    targeting: Dict[str, Any] = field(default_factory=dict)
    status: str = "active"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "campaign_id": self.campaign_id,
            "budget": self.budget,
            "bid_strategy": self.bid_strategy,
            "targeting": self.targeting,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Creative:
    id: str
    ad_set_id: str
    name: str
    image_url: str = ""
    video_url: str = ""
    headline: str = ""
    description: str = ""
    call_to_action: str = ""
    status: str = "active"
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "ad_set_id": self.ad_set_id,
            "name": self.name,
            "image_url": self.image_url,
            "video_url": self.video_url,
            "headline": self.headline,
            "description": self.description,
            "call_to_action": self.call_to_action,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Campaign:
    id: str
    name: str
    objective: str = ""
    budget: float = 0.0
    status: str = "active"
    start_date: datetime = field(default_factory=datetime.now)
    end_date: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "objective": self.objective,
            "budget": self.budget,
            "status": self.status,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class MetaAdsConnector:
    def __init__(self):
        self._connected = False
        self._campaigns: Dict[str, Campaign] = {}
        self._ad_sets: Dict[str, List[AdSet]] = {}
        self._creatives: Dict[str, List[Creative]] = {}
        self._sync_history: List[Dict[str, Any]] = []

    def connect(self) -> bool:
        self._connected = True
        return True

    def get_campaigns(self) -> List[Campaign]:
        if not self._connected:
            return []
        if not self._campaigns:
            self._mock_campaigns()
        return list(self._campaigns.values())

    def get_campaign_metrics(self, campaign_id: str) -> Optional[CampaignMetrics]:
        if not self._connected or campaign_id not in self._campaigns:
            return None
        return CampaignMetrics(
            campaign_id=campaign_id,
            impressions=15000,
            clicks=850,
            spend=2500.0,
            conversions=45,
            cpm=16.67,
            cpc=2.94,
            cpa=55.56,
            date_range="last_7_days",
        )

    def get_ad_sets(self, campaign_id: str) -> List[AdSet]:
        if not self._connected or campaign_id not in self._campaigns:
            return []
        if campaign_id not in self._ad_sets:
            self._ad_sets[campaign_id] = [
                AdSet(
                    id=f"adset_{campaign_id}_1",
                    name=f"Ad Set 1 for {campaign_id}",
                    campaign_id=campaign_id,
                    budget=1000.0,
                    bid_strategy="LOWEST_COST_WITHOUT_CAP",
                    targeting={"age_min": 18, "age_max": 35, "interests": ["gaming", "mobile"]},
                    status="active",
                ),
                AdSet(
                    id=f"adset_{campaign_id}_2",
                    name=f"Ad Set 2 for {campaign_id}",
                    campaign_id=campaign_id,
                    budget=1500.0,
                    bid_strategy="TARGET_COST",
                    targeting={"age_min": 25, "age_max": 45, "interests": ["strategy games"]},
                    status="active",
                ),
            ]
        return self._ad_sets[campaign_id]

    def get_creatives(self, ad_set_id: str) -> List[Creative]:
        if not self._connected:
            return []
        if ad_set_id not in self._creatives:
            self._creatives[ad_set_id] = [
                Creative(
                    id=f"creative_{ad_set_id}_1",
                    ad_set_id=ad_set_id,
                    name=f"Creative 1 for {ad_set_id}",
                    image_url="https://example.com/image1.jpg",
                    headline="New Game Launch!",
                    description="Experience the ultimate gaming adventure",
                    call_to_action="Install Now",
                    status="active",
                ),
                Creative(
                    id=f"creative_{ad_set_id}_2",
                    ad_set_id=ad_set_id,
                    name=f"Video Creative for {ad_set_id}",
                    video_url="https://example.com/video1.mp4",
                    headline="Play Now!",
                    description="Join millions of players worldwide",
                    call_to_action="Download",
                    status="active",
                ),
            ]
        return self._creatives[ad_set_id]

    def update_campaign_budget(self, campaign_id: str, budget: float) -> bool:
        if not self._connected or campaign_id not in self._campaigns:
            return False
        self._campaigns[campaign_id].budget = budget
        self._campaigns[campaign_id].updated_at = datetime.now()
        return True

    def create_campaign(self, data: Dict[str, Any]) -> Optional[Campaign]:
        if not self._connected:
            return None
        campaign = Campaign(
            id=f"meta_campaign_{len(self._campaigns) + 1}",
            name=data.get("name", "New Campaign"),
            objective=data.get("objective", "APP_INSTALLS"),
            budget=data.get("budget", 0.0),
            status=data.get("status", "active"),
        )
        self._campaigns[campaign.id] = campaign
        return campaign

    def sync_campaigns(self) -> Dict[str, Any]:
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
            "meta_campaign_1": Campaign(
                id="meta_campaign_1",
                name="Summer Launch Campaign",
                objective="APP_INSTALLS",
                budget=5000.0,
                status="active",
            ),
            "meta_campaign_2": Campaign(
                id="meta_campaign_2",
                name="User Acquisition Q3",
                objective="LINK_CLICKS",
                budget=10000.0,
                status="active",
            ),
            "meta_campaign_3": Campaign(
                id="meta_campaign_3",
                name="Brand Awareness",
                objective="BRAND_AWARENESS",
                budget=3000.0,
                status="paused",
            ),
        }