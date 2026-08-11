"""TikTok Connector — 连接 TikTok Ads API

获取 Campaign/Ad/Creative 层级的真实买量数据。

输出：tiktok_campaign_raw.json
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from ..config import OUTPUT_DIR


class TikTokConnector:
    """TikTok Ads API 连接器"""

    def __init__(self, access_token: Optional[str] = None,
                 advertiser_id: Optional[str] = None):
        self.access_token = access_token
        self.advertiser_id = advertiser_id
        self.is_mocked = not (access_token and advertiser_id)

    def fetch_campaigns(self, days: int = 7) -> List[dict]:
        """获取 Campaign 数据"""
        if self.is_mocked:
            return self._generate_mock_campaigns(days)
        return []

    def fetch_ad_level_data(self, days: int = 7) -> List[dict]:
        """获取 Ad Level 数据"""
        if self.is_mocked:
            return self._generate_mock_ad_data(days)
        return []

    def fetch_creative_performance(self, days: int = 7) -> List[dict]:
        """获取 Creative 层级表现数据"""
        if self.is_mocked:
            return self._generate_mock_creative_data(days)
        return []

    def _generate_mock_campaigns(self, days: int) -> List[dict]:
        """生成模拟 Campaign 数据"""
        import random
        countries = ["US", "CN", "KR", "JP", "TH"]

        campaigns = []
        for i in range(8):
            date = (datetime.now() - timedelta(days=random.randint(0, days))).strftime("%Y-%m-%d")
            campaigns.append({
                "campaign_id": f"tt_campaign_{i+1:04d}",
                "campaign_name": f"P04_TikTok_Push_{i+1}",
                "country": random.choice(countries),
                "date": date,
            })
        return campaigns

    def _generate_mock_ad_data(self, days: int) -> List[dict]:
        """生成模拟 Ad Level 数据"""
        import random

        hook_types = ["shock", "challenge", "curiosity", "urgency", "transformation"]
        subjects = ["dragon", "witch", "hero", "monster"]
        gameplay_types = ["merge", "battle", "upgrade", "unlock"]

        ads = []
        for i in range(80):
            date = (datetime.now() - timedelta(days=random.randint(0, days))).strftime("%Y-%m-%d")
            hook = random.choice(hook_types)
            subject = random.choice(subjects)
            gameplay = random.choice(gameplay_types)

            impressions = random.randint(10000, 150000)
            clicks = int(impressions * random.uniform(0.025, 0.07))
            installs = int(clicks * random.uniform(0.08, 0.25))
            spend = installs * random.uniform(0.2, 0.6)

            ads.append({
                "ad_id": f"tt_ad_{i+1:06d}",
                "creative_id": f"tt_{subject}_{hook}_{i+1:03d}",
                "video_id": f"tt_video_{i+1:06d}",
                "thumbnail": f"tt_thumb_{i+1:06d}.jpg",
                "spend": round(spend, 2),
                "impressions": impressions,
                "clicks": clicks,
                "installs": installs,
                "purchase": int(installs * random.uniform(0.02, 0.12)),
                "date": date,
                "dna": {
                    "hook": hook,
                    "subject": subject,
                    "gameplay": gameplay,
                },
            })
        return ads

    def _generate_mock_creative_data(self, days: int) -> List[dict]:
        """生成模拟 Creative 表现数据"""
        import random

        hook_types = ["shock", "challenge", "curiosity"]
        subjects = ["dragon", "witch", "hero"]
        gameplay_types = ["merge", "battle", "upgrade"]

        creatives = []
        for i in range(15):
            hook = random.choice(hook_types)
            subject = random.choice(subjects)
            gameplay = random.choice(gameplay_types)

            multiplier = 1.0
            if hook == "shock" and subject == "dragon":
                multiplier = 1.25
            elif hook == "challenge" and gameplay == "battle":
                multiplier = 1.15

            impressions = int(random.randint(30000, 300000) * multiplier)
            clicks = int(impressions * random.uniform(0.035, 0.075) * multiplier)
            installs = int(clicks * random.uniform(0.12, 0.22))
            spend = installs * random.uniform(0.25, 0.5)

            d7_revenue = spend * random.uniform(0.25, 1.0) * multiplier
            d30_revenue = spend * random.uniform(0.5, 1.8) * multiplier

            creatives.append({
                "creative_id": f"tt_creative_{subject}_{hook}_{i:03d}",
                "video_name": f"{subject}_{hook}_{gameplay}_10s",
                "spend": round(spend, 2),
                "impressions": impressions,
                "clicks": clicks,
                "installs": installs,
                "purchase": int(installs * random.uniform(0.04, 0.12)),
                "d7_revenue": round(d7_revenue, 2),
                "d30_revenue": round(d30_revenue, 2),
                "date_start": (datetime.now() - timedelta(days=random.randint(7, 30))).strftime("%Y-%m-%d"),
                "date_end": (datetime.now() - timedelta(days=random.randint(0, 6))).strftime("%Y-%m-%d"),
                "dna": {
                    "hook": hook,
                    "subject": subject,
                    "gameplay": gameplay,
                },
            })
        return creatives

    def save_raw_data(self, data: List[dict], filename: str = "tiktok_campaign_raw.json") -> Path:
        """保存原始数据"""
        output_path = OUTPUT_DIR / "v38_1" / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "data": data,
                "timestamp": datetime.now().isoformat(),
                "source": "tiktok",
                "is_mocked": self.is_mocked,
            }, f, ensure_ascii=False, indent=2)

        return output_path

    def sync(self, days: int = 7) -> Dict[str, Path]:
        """执行完整同步"""
        print("[TikTokConnector] Syncing data...")

        results = {}
        campaigns = self.fetch_campaigns(days)
        results["campaigns"] = self.save_raw_data(campaigns, "tiktok_campaigns_raw.json")
        print(f"  Campaigns: {len(campaigns)}")

        ads = self.fetch_ad_level_data(days)
        results["ads"] = self.save_raw_data(ads, "tiktok_ads_raw.json")
        print(f"  Ads: {len(ads)}")

        creatives = self.fetch_creative_performance(days)
        results["creatives"] = self.save_raw_data(creatives, "tiktok_creatives_raw.json")
        print(f"  Creatives: {len(creatives)}")

        print("[TikTokConnector] Sync complete.")
        return results
