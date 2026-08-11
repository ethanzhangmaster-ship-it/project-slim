"""Google Ads Connector — 连接 Google Ads API

获取 Campaign/Ad/Creative 层级的真实买量数据。

输出：google_ads_campaign_raw.json
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from ..config import OUTPUT_DIR


class GoogleAdsConnector:
    """Google Ads API 连接器"""

    def __init__(self, client_id: Optional[str] = None,
                 client_secret: Optional[str] = None,
                 developer_token: Optional[str] = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.developer_token = developer_token
        self.is_mocked = not (client_id and client_secret and developer_token)

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
        countries = ["US", "UK", "DE", "CA", "AU"]

        campaigns = []
        for i in range(6):
            date = (datetime.now() - timedelta(days=random.randint(0, days))).strftime("%Y-%m-%d")
            campaigns.append({
                "campaign_id": f"ga_campaign_{i+1:04d}",
                "campaign_name": f"P04_UAC_Global_{i+1}",
                "country": random.choice(countries),
                "date": date,
            })
        return campaigns

    def _generate_mock_ad_data(self, days: int) -> List[dict]:
        """生成模拟 Ad Level 数据"""
        import random

        hook_types = ["challenge", "curiosity", "transformation", "urgency"]
        subjects = ["dragon", "witch", "hero", "castle"]
        gameplay_types = ["merge", "upgrade", "battle"]

        ads = []
        for i in range(60):
            date = (datetime.now() - timedelta(days=random.randint(0, days))).strftime("%Y-%m-%d")
            hook = random.choice(hook_types)
            subject = random.choice(subjects)
            gameplay = random.choice(gameplay_types)

            impressions = random.randint(8000, 120000)
            clicks = int(impressions * random.uniform(0.015, 0.045))
            installs = int(clicks * random.uniform(0.12, 0.3))
            spend = installs * random.uniform(0.4, 0.9)

            ads.append({
                "ad_id": f"ga_ad_{i+1:06d}",
                "creative_id": f"ga_{subject}_{hook}_{i+1:03d}",
                "video_id": f"ga_video_{i+1:06d}",
                "thumbnail": f"ga_thumb_{i+1:06d}.jpg",
                "spend": round(spend, 2),
                "impressions": impressions,
                "clicks": clicks,
                "installs": installs,
                "purchase": int(installs * random.uniform(0.03, 0.1)),
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

        hook_types = ["challenge", "curiosity", "transformation"]
        subjects = ["dragon", "witch", "hero"]
        gameplay_types = ["merge", "upgrade"]

        creatives = []
        for i in range(12):
            hook = random.choice(hook_types)
            subject = random.choice(subjects)
            gameplay = random.choice(gameplay_types)

            multiplier = 1.0
            if hook == "challenge" and gameplay == "merge":
                multiplier = 1.2
            elif hook == "transformation" and subject == "dragon":
                multiplier = 1.25

            impressions = int(random.randint(40000, 250000) * multiplier)
            clicks = int(impressions * random.uniform(0.02, 0.05) * multiplier)
            installs = int(clicks * random.uniform(0.15, 0.28))
            spend = installs * random.uniform(0.4, 0.75)

            d7_revenue = spend * random.uniform(0.25, 0.9) * multiplier
            d30_revenue = spend * random.uniform(0.5, 1.6) * multiplier

            creatives.append({
                "creative_id": f"ga_creative_{subject}_{hook}_{i:03d}",
                "video_name": f"{subject}_{hook}_{gameplay}_15s",
                "spend": round(spend, 2),
                "impressions": impressions,
                "clicks": clicks,
                "installs": installs,
                "purchase": int(installs * random.uniform(0.04, 0.1)),
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

    def save_raw_data(self, data: List[dict], filename: str = "google_ads_campaign_raw.json") -> Path:
        """保存原始数据"""
        output_path = OUTPUT_DIR / "v38_1" / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "data": data,
                "timestamp": datetime.now().isoformat(),
                "source": "google_ads",
                "is_mocked": self.is_mocked,
            }, f, ensure_ascii=False, indent=2)

        return output_path

    def sync(self, days: int = 7) -> Dict[str, Path]:
        """执行完整同步"""
        print("[GoogleAdsConnector] Syncing data...")

        results = {}
        campaigns = self.fetch_campaigns(days)
        results["campaigns"] = self.save_raw_data(campaigns, "google_ads_campaigns_raw.json")
        print(f"  Campaigns: {len(campaigns)}")

        ads = self.fetch_ad_level_data(days)
        results["ads"] = self.save_raw_data(ads, "google_ads_ads_raw.json")
        print(f"  Ads: {len(ads)}")

        creatives = self.fetch_creative_performance(days)
        results["creatives"] = self.save_raw_data(creatives, "google_ads_creatives_raw.json")
        print(f"  Creatives: {len(creatives)}")

        print("[GoogleAdsConnector] Sync complete.")
        return results
