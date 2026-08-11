"""Performance Fuser — 三源数据融合

Facebook Excel (花费) + Facebook API (creative 元数据) + Adjust (归因收入)
→ creative_performance_raw.json

匹配链路:
1. Excel 广告编号 (ad_id) == Adjust creative_id_network → revenue/installs
2. Excel 广告编号 (ad_id) == API ad_id → thumbnail_url, creative_type
3. 合并计算 ROAS / CPI / image_score
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from ..config import OUTPUT_DIR, IMAGE_KEYWORDS, IMAGE_SCORE_THRESHOLD, ensure_dirs
from .facebook_loader import FacebookDataLoader
from .adjust_loader import AdjustDataLoader


class PerformanceFuser:
    """三源数据融合器"""

    def __init__(self,
                 fb_loader: Optional[FacebookDataLoader] = None,
                 adjust_loader: Optional[AdjustDataLoader] = None):
        self.fb_loader = fb_loader or FacebookDataLoader()
        self.adjust_loader = adjust_loader or AdjustDataLoader()

    def fuse(self) -> List[dict]:
        """执行三源融合, 输出 creative_performance_raw.json"""
        ensure_dirs()

        # 1. 加载 Facebook 数据
        fb_data = self.fb_loader.load()

        # 2. 加载 Adjust 数据 (限定 FB ad_id 范围)
        adjust_data = self.adjust_loader.load(fb_ad_ids=set(fb_data.keys()))

        # 3. 融合
        fused = self._fuse(fb_data, adjust_data)

        # 4. 保存
        output_path = OUTPUT_DIR / "creative_performance_raw.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "version": "2.1.8",
                "total": len(fused),
                "records": fused,
                "stats": self._compute_stats(fused),
            }, f, ensure_ascii=False, indent=2)

        print(f"\n[PerformanceFuser] 输出: {output_path}")
        print(f"[PerformanceFuser] 总记录: {len(fused)}")
        self._print_stats(fused)

        return fused

    def _fuse(self, fb_data: Dict[str, dict], adjust_data: Dict[str, dict]) -> List[dict]:
        """融合 FB + Adjust"""
        results = []

        for ad_id, fb_info in fb_data.items():
            adj = adjust_data.get(ad_id, {})

            spend = fb_info["spend"]
            iap_revenue = adj.get("revenue", 0)
            ad_revenue = adj.get("ad_revenue", 0)
            all_revenue = adj.get("all_revenue", 0)
            installs = adj.get("installs", 0)
            data_days = adj.get("data_days", 0)

            # 计算指标
            iap_roas = iap_revenue / spend if spend > 0 else 0
            total_roas = all_revenue / spend if spend > 0 else 0
            cpi = spend / installs if installs > 0 else 0

            # 图片检测评分
            image_score = self._calculate_image_score(fb_info)

            # 平台识别
            platform = self._detect_platform(fb_info["ad_name"])

            record = {
                "ad_id": ad_id,
                "ad_name": fb_info["ad_name"],
                "platform": platform,
                "creative_id": fb_info.get("creative_id", ""),
                "creative_type": fb_info.get("creative_type", ""),
                "thumbnail_url": fb_info.get("thumbnail_url", ""),
                "video_id": fb_info.get("video_id", ""),
                "has_api_data": fb_info.get("has_api_data", False),

                # Facebook 指标 (Excel 为准)
                "spend": round(spend, 2),
                "impressions": fb_info["impressions"],

                # Adjust 归因指标
                "iap_revenue": round(iap_revenue, 2),
                "ad_revenue": round(ad_revenue, 2),
                "all_revenue": round(all_revenue, 2),
                "installs": installs,
                "data_days": data_days,
                "has_adjust_data": ad_id in adjust_data,

                # 计算指标
                "iap_roas": round(iap_roas, 4),
                "total_roas": round(total_roas, 4),
                "cpi": round(cpi, 2),

                # 分类
                "image_score": round(image_score, 2),
                "is_image": image_score >= IMAGE_SCORE_THRESHOLD,
            }

            results.append(record)

        return results

    @staticmethod
    def _calculate_image_score(fb_info: dict) -> float:
        """计算 Image Detection Score

        ImageScore = 0.5 * meta_type + 0.3 * thumbnail_exists + 0.2 * keyword
        """
        creative_type = fb_info.get("creative_type", "")
        video_id = fb_info.get("video_id", "")
        thumbnail_url = fb_info.get("thumbnail_url", "")
        ad_name = fb_info.get("ad_name", "").lower()

        # Meta creative type score
        if creative_type == "image":
            meta_score = 1.0
        elif not video_id:
            meta_score = 0.5
        else:
            meta_score = 0.0

        # Thumbnail exists score
        thumb_score = 1.0 if thumbnail_url else 0.0

        # Keyword score
        keyword_score = 1.0 if any(kw in ad_name for kw in IMAGE_KEYWORDS) else 0.0

        return 0.5 * meta_score + 0.3 * thumb_score + 0.2 * keyword_score

    @staticmethod
    def _detect_platform(ad_name: str) -> str:
        """从广告名识别平台"""
        name_upper = ad_name.upper()
        if "-IOS-" in name_upper:
            return "ios"
        elif "-AND-" in name_upper:
            return "android"
        return "unknown"

    @staticmethod
    def _compute_stats(fused: List[dict]) -> dict:
        """计算汇总统计"""
        total = len(fused)
        image_ads = [r for r in fused if r["is_image"]]
        with_adjust = [r for r in fused if r["has_adjust_data"]]
        image_with_adjust = [r for r in image_ads if r["has_adjust_data"]]

        return {
            "total_ads": total,
            "total_spend": round(sum(r["spend"] for r in fused), 2),
            "image_ads": len(image_ads),
            "image_spend": round(sum(r["spend"] for r in image_ads), 2),
            "adjust_match_rate": round(len(with_adjust) / total, 3) if total else 0,
            "image_adjust_match_rate": round(
                len(image_with_adjust) / len(image_ads), 3
            ) if image_ads else 0,
        }

    @staticmethod
    def _print_stats(fused: List[dict]):
        """打印汇总统计"""
        image_ads = [r for r in fused if r["is_image"]]
        with_adj = [r for r in image_ads if r["has_adjust_data"]]

        total_spend = sum(r["spend"] for r in fused)
        img_spend = sum(r["spend"] for r in image_ads)
        img_revenue = sum(r["all_revenue"] for r in image_ads)

        print(f"\n=== 汇总 ===")
        print(f"总广告: {len(fused)}, 总花费: ${total_spend:,.0f}")
        print(f"图片广告: {len(image_ads)} ({len(image_ads)/len(fused)*100:.0f}%), "
              f"花费: ${img_spend:,.0f}")
        print(f"图片 Adjust 匹配: {len(with_adj)}/{len(image_ads)} "
              f"({len(with_adj)/len(image_ads)*100:.1f}%)")
        print(f"图片总收入: ${img_revenue:,.0f}, 整体 ROAS: "
              f"{img_revenue/img_spend*100:.0f}%" if img_spend > 0 else "N/A")
