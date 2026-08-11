from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class TikTokMetrics:
    campaign_id: str
    impressions: int = 0
    views: int = 0
    clicks: int = 0
    spend: float = 0.0
    conversions: int = 0
    ctr: float = 0.0
    cpc: float = 0.0
    cpm: float = 0.0
    video_play_rate: float = 0.0
    complete_play_rate: float = 0.0
    date_range: str = ""
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "impressions": self.impressions,
            "views": self.views,
            "clicks": self.clicks,
            "spend": self.spend,
            "conversions": self.conversions,
            "ctr": self.ctr,
            "cpc": self.cpc,
            "cpm": self.cpm,
            "video_play_rate": self.video_play_rate,
            "complete_play_rate": self.complete_play_rate,
            "date_range": self.date_range,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class TikTokCreative:
    id: str
    name: str
    video_id: str = ""
    video_url: str = ""
    image_url: str = ""
    title: str = ""
    description: str = ""
    call_to_action: str = ""
    status: str = "active"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "video_id": self.video_id,
            "video_url": self.video_url,
            "image_url": self.image_url,
            "title": self.title,
            "description": self.description,
            "call_to_action": self.call_to_action,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class TikTokAdsConnector:
    def __init__(self):
        self._connected = False
        self._creatives: Dict[str, TikTokCreative] = {}
        self._sync_history: List[Dict[str, Any]] = []

    def connect(self) -> bool:
        self._connected = True
        return True

    def get_creatives(self) -> List[TikTokCreative]:
        if not self._connected:
            return []
        if not self._creatives:
            self._mock_creatives()
        return list(self._creatives.values())

    def get_campaign_metrics(self, campaign_id: str) -> Optional[TikTokMetrics]:
        if not self._connected:
            return None
        return TikTokMetrics(
            campaign_id=campaign_id,
            impressions=25000,
            views=18000,
            clicks=1200,
            spend=3200.0,
            conversions=55,
            ctr=4.8,
            cpc=2.67,
            cpm=12.8,
            video_play_rate=72.0,
            complete_play_rate=45.0,
            date_range="last_7_days",
        )

    def get_video_metrics(self, video_id: str) -> Dict[str, Any]:
        if not self._connected:
            return {"error": "Not connected"}
        return {
            "video_id": video_id,
            "views": 45000,
            "likes": 8500,
            "comments": 1200,
            "shares": 3200,
            "followers": 850,
            "watch_time": 125000,
            "avg_watch_time": 2.78,
            "video_play_rate": 78.5,
            "complete_play_rate": 52.3,
            "date_range": "last_7_days",
        }

    def sync_data(self) -> Dict[str, Any]:
        if not self._connected:
            return {"success": False, "message": "Not connected"}
        self._mock_creatives()
        sync_time = datetime.now()
        self._sync_history.append({
            "timestamp": sync_time.isoformat(),
            "creative_count": len(self._creatives),
            "success": True,
        })
        return {
            "success": True,
            "creatives_synced": len(self._creatives),
            "sync_time": sync_time.isoformat(),
        }

    def _mock_creatives(self):
        self._creatives = {
            "tiktok_creative_1": TikTokCreative(
                id="tiktok_creative_1",
                name="Game Trailer - Launch",
                video_id="vid_001",
                video_url="https://example.com/tiktok_video1.mp4",
                title="New Game Alert!",
                description="Check out our new game trailer! #gaming #mobilegame",
                call_to_action="Download Now",
                status="active",
            ),
            "tiktok_creative_2": TikTokCreative(
                id="tiktok_creative_2",
                name="Gameplay Highlights",
                video_id="vid_002",
                video_url="https://example.com/tiktok_video2.mp4",
                title="Epic Gameplay!",
                description="Watch this epic gameplay! #gamer #fyp",
                call_to_action="Play Now",
                status="active",
            ),
            "tiktok_creative_3": TikTokCreative(
                id="tiktok_creative_3",
                name="Character Spotlight",
                video_id="vid_003",
                video_url="https://example.com/tiktok_video3.mp4",
                title="Meet Our Heroes!",
                description="Introducing our game characters! #gamecharacter",
                call_to_action="Learn More",
                status="active",
            ),
        }