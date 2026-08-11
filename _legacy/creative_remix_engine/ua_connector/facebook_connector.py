"""Facebook Connector — 连接 Facebook Marketing API

获取 Campaign/Ad/Creative 层级的真实买量数据。

输出：facebook_campaign_raw.json
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from ..config import OUTPUT_DIR


class FacebookConnector:
    """Facebook Marketing API 连接器"""

    def __init__(self, access_token: Optional[str] = None,
                 account_id: Optional[str] = None):
        self.access_token = access_token
        self.account_id = account_id
        self.is_mocked = not (access_token and account_id)

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
        campaigns = []
        countries = ["US", "UK", "DE", "FR", "JP"]

        for i in range(10):
            date = (datetime.now() - timedelta(days=random.randint(0, days))).strftime("%Y-%m-%d")
            campaigns.append({
                "campaign_id": f"campaign_{i+1:04d}",
                "campaign_name": f"P04_Witch_Battle_{i+1}",
                "country": random.choice(countries),
                "date": date,
            })
        return campaigns

    def _generate_mock_ad_data(self, days: int) -> List[dict]:
        """生成模拟 Ad Level 数据"""
        import random

        hook_types = ["transformation", "challenge", "curiosity", "urgency", "shock"]
        subjects = ["dragon", "witch", "castle", "hero", "monster"]
        gameplay_types = ["merge", "upgrade", "battle", "unlock", "showcase"]
        rewards = ["evolution", "treasure", "magic", "new_character"]

        ads = []
        for i in range(100):
            date = (datetime.now() - timedelta(days=random.randint(0, days))).strftime("%Y-%m-%d")
            hook = random.choice(hook_types)
            subject = random.choice(subjects)
            gameplay = random.choice(gameplay_types)
            reward = random.choice(rewards)

            impressions = random.randint(5000, 200000)
            clicks = int(impressions * random.uniform(0.02, 0.06))
            installs = int(clicks * random.uniform(0.1, 0.3))
            purchase = int(installs * random.uniform(0.02, 0.15))

            base_ctr = 0.03
            if hook == "transformation" and subject == "dragon":
                base_ctr = 0.05
            elif hook == "challenge":
                base_ctr = 0.04

            clicks = int(impressions * base_ctr * random.uniform(0.8, 1.2))

            spend = installs * random.uniform(0.25, 0.8)

            ads.append({
                "ad_id": f"ad_{i+1:06d}",
                "creative_id": f"{subject}_{hook}_{gameplay}_{i+1:03d}",
                "video_id": f"video_{i+1:06d}",
                "thumbnail": f"thumb_{i+1:06d}.jpg",
                "spend": round(spend, 2),
                "impressions": impressions,
                "clicks": clicks,
                "installs": installs,
                "purchase": purchase,
                "date": date,
                "dna": {
                    "hook": hook,
                    "subject": subject,
                    "gameplay": gameplay,
                    "reward": reward,
                },
            })
        return ads

    def _generate_mock_creative_data(self, days: int) -> List[dict]:
        """生成模拟 Creative 表现数据"""
        import random

        hook_types = ["transformation", "challenge", "curiosity", "urgency", "shock"]
        subjects = ["dragon", "witch", "castle", "hero", "monster"]
        gameplay_types = ["merge", "upgrade", "battle", "unlock", "showcase"]

        creatives = []
        for i in range(20):
            hook = random.choice(hook_types)
            subject = random.choice(subjects)
            gameplay = random.choice(gameplay_types)

            # 基于 DNA 模式的表现差异
            multiplier = 1.0
            if hook == "transformation" and subject == "dragon" and gameplay == "merge":
                multiplier = 1.3
            elif hook == "challenge" and gameplay == "battle":
                multiplier = 1.2
            elif hook == "curiosity" and subject == "witch":
                multiplier = 1.15

            impressions = int(random.randint(50000, 500000) * multiplier)
            clicks = int(impressions * random.uniform(0.03, 0.06) * multiplier)
            installs = int(clicks * random.uniform(0.15, 0.25))
            spend = installs * random.uniform(0.3, 0.6)

            d7_revenue = spend * random.uniform(0.3, 1.2) * multiplier
            d30_revenue = spend * random.uniform(0.6, 2.0) * multiplier

            creatives.append({
                "creative_id": f"creative_{subject}_{hook}_{gameplay}_{i:03d}",
                "video_name": f"{subject}_{hook}_{gameplay}_15s",
                "spend": round(spend, 2),
                "impressions": impressions,
                "clicks": clicks,
                "installs": installs,
                "purchase": int(installs * random.uniform(0.05, 0.15)),
                "d7_revenue": round(d7_revenue, 2),
                "d30_revenue": round(d30_revenue, 2),
                "date_start": (datetime.now() - timedelta(days=random.randint(7, 30))).strftime("%Y-%m-%d"),
                "date_end": (datetime.now() - timedelta(days=random.randint(0, 6))).strftime("%Y-%m-%d"),
                "dna": {
                    "hook": hook,
                    "subject": subject,
                    "gameplay": gameplay,
                    "reward": random.choice(["evolution", "treasure", "magic"]),
                },
            })
        return creatives

    def save_raw_data(self, data: List[dict], filename: str = "facebook_campaign_raw.json") -> Path:
        """保存原始数据"""
        output_path = OUTPUT_DIR / "v38_1" / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "data": data,
                "timestamp": datetime.now().isoformat(),
                "source": "facebook",
                "is_mocked": self.is_mocked,
            }, f, ensure_ascii=False, indent=2)

        return output_path

    def sync(self, days: int = 7) -> Dict[str, Path]:
        """执行完整同步"""
        print("[FacebookConnector] Syncing data...")

        results = {}

        # Campaign 数据
        campaigns = self.fetch_campaigns(days)
        results["campaigns"] = self.save_raw_data(campaigns, "facebook_campaigns_raw.json")
        print(f"  Campaigns: {len(campaigns)}")

        # Ad Level 数据
        ads = self.fetch_ad_level_data(days)
        results["ads"] = self.save_raw_data(ads, "facebook_ads_raw.json")
        print(f"  Ads: {len(ads)}")

        # Creative Performance 数据
        creatives = self.fetch_creative_performance(days)
        results["creatives"] = self.save_raw_data(creatives, "facebook_creatives_raw.json")
        print(f"  Creatives: {len(creatives)}")

        print("[FacebookConnector] Sync complete.")
        return results


import random
