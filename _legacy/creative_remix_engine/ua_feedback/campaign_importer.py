"""Campaign Importer — 导入多平台 UA 数据

从 Facebook/TikTok/Google Ads 导入 Campaign 数据，统一格式。
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from ..config import OUTPUT_DIR
from ..ua_connector import FacebookConnector, TikTokConnector, GoogleAdsConnector


class CampaignImporter:
    """Campaign 数据导入器"""

    def __init__(self):
        self.facebook = FacebookConnector()
        self.tiktok = TikTokConnector()
        self.google_ads = GoogleAdsConnector()

    def import_all_platforms(self, days: int = 7) -> Dict[str, List[dict]]:
        """导入所有平台数据"""
        print("[CampaignImporter] Importing data from all platforms...")

        all_data = {}

        # Facebook
        fb_results = self.facebook.sync(days)
        with open(fb_results["creatives"], "r", encoding="utf-8") as f:
            fb_data = json.load(f)
        all_data["facebook"] = fb_data.get("data", [])
        print(f"  Facebook: {len(all_data['facebook'])} creatives")

        # TikTok
        tt_results = self.tiktok.sync(days)
        with open(tt_results["creatives"], "r", encoding="utf-8") as f:
            tt_data = json.load(f)
        all_data["tiktok"] = tt_data.get("data", [])
        print(f"  TikTok: {len(all_data['tiktok'])} creatives")

        # Google Ads
        ga_results = self.google_ads.sync(days)
        with open(ga_results["creatives"], "r", encoding="utf-8") as f:
            ga_data = json.load(f)
        all_data["google_ads"] = ga_data.get("data", [])
        print(f"  Google Ads: {len(all_data['google_ads'])} creatives")

        # 合并数据
        merged = self._merge_creatives(all_data)
        print(f"\n[CampaignImporter] Total merged: {len(merged)} creatives")

        # 保存合并数据
        merged_path = self._save_merged_data(merged)
        print(f"  Saved to: {merged_path}")

        return {
            "platforms": all_data,
            "merged": merged,
            "merged_path": str(merged_path),
        }

    def _merge_creatives(self, platform_data: Dict[str, List[dict]]) -> List[dict]:
        """合并多平台 Creative 数据"""
        merged = []
        seen_ids = set()

        for platform, creatives in platform_data.items():
            for creative in creatives:
                creative_id = creative.get("creative_id", "")
                if creative_id and creative_id in seen_ids:
                    continue
                seen_ids.add(creative_id)

                merged.append({
                    "creative_id": creative_id,
                    "video_name": creative.get("video_name", ""),
                    "platform": platform,
                    "spend": creative.get("spend", 0),
                    "impressions": creative.get("impressions", 0),
                    "clicks": creative.get("clicks", 0),
                    "installs": creative.get("installs", 0),
                    "purchase": creative.get("purchase", 0),
                    "d7_revenue": creative.get("d7_revenue", 0),
                    "d30_revenue": creative.get("d30_revenue", 0),
                    "date_start": creative.get("date_start", ""),
                    "date_end": creative.get("date_end", ""),
                    "dna": creative.get("dna", {}),
                })

        return merged

    def _save_merged_data(self, data: List[dict]) -> Path:
        """保存合并数据"""
        output_path = OUTPUT_DIR / "v38_1" / "merged_creatives_raw.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "data": data,
                "timestamp": datetime.now().isoformat(),
                "total": len(data),
            }, f, ensure_ascii=False, indent=2)

        return output_path

    def load_merged_data(self) -> List[dict]:
        """加载已合并的数据"""
        merged_path = OUTPUT_DIR / "v38_1" / "merged_creatives_raw.json"
        if merged_path.exists():
            with open(merged_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("data", [])
        return []
