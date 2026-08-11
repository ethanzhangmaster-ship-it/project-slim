"""Adjust Data Loader — 加载 Adjust MMP 归因数据

数据源: adjust_creative_data.json
字段: creative_id_network, creative_network, cost, revenue, ad_revenue, installs, day

输出: {ad_id: {cost, revenue, ad_revenue, all_revenue, installs, data_days}}
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

from ..config import ADJUST_JSON


class AdjustDataLoader:
    """Adjust 归因数据加载器"""

    def __init__(self, adjust_path: Optional[Path] = None):
        self.adjust_path = adjust_path or ADJUST_JSON

    def load(self, fb_ad_ids: Optional[set] = None) -> Dict[str, dict]:
        """加载 Adjust 数据并按 ad_id 聚合

        Args:
            fb_ad_ids: Facebook ad_id 集合, 用于限定匹配范围

        Returns:
            {ad_id: {cost, revenue, ad_revenue, all_revenue, installs, data_days}}
        """
        if not self.adjust_path.exists():
            raise FileNotFoundError(f"Adjust 文件不存在: {self.adjust_path}")

        with open(self.adjust_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        rows = data.get("rows", [])
        print(f"[AdjustLoader] 总行数: {len(rows)}")

        # 筛选 P04 Facebook 行
        fb_p04_rows = [r for r in rows if self._is_p04_facebook(r)]
        print(f"[AdjustLoader] P04 Facebook 行: {len(fb_p04_rows)}")

        # 按 creative_id_network (= Facebook ad_id) 聚合
        by_ad_id: Dict[str, dict] = defaultdict(lambda: {
            "cost": 0.0,
            "revenue": 0.0,        # IAP revenue
            "ad_revenue": 0.0,
            "all_revenue": 0.0,
            "installs": 0,
            "days": set(),         # 有数据的天数
        })

        matched_rows = 0
        for row in fb_p04_rows:
            cid = str(row.get("creative_id_network", "") or "").strip()

            # 如果提供了 fb_ad_ids, 只匹配在范围内的
            if fb_ad_ids and cid not in fb_ad_ids:
                continue

            matched_rows += 1
            entry = by_ad_id[cid]
            entry["cost"] += float(row.get("cost", 0) or 0)
            entry["revenue"] += float(row.get("revenue", 0) or 0)
            entry["ad_revenue"] += float(row.get("ad_revenue", 0) or 0)
            entry["all_revenue"] += float(row.get("all_revenue", 0) or 0)
            entry["installs"] += int(float(row.get("installs", 0) or 0))
            day = row.get("day", "")
            if day:
                entry["days"].add(day)

        # 转换 days set → data_days count
        result: Dict[str, dict] = {}
        for ad_id, entry in by_ad_id.items():
            result[ad_id] = {
                "cost": round(entry["cost"], 2),
                "revenue": round(entry["revenue"], 2),
                "ad_revenue": round(entry["ad_revenue"], 2),
                "all_revenue": round(entry["all_revenue"], 2),
                "installs": entry["installs"],
                "data_days": len(entry["days"]),
            }

        print(f"[AdjustLoader] 匹配行数: {matched_rows} ({matched_rows/len(fb_p04_rows)*100:.1f}%)")
        print(f"[AdjustLoader] 唯一 ad_id: {len(result)}")

        return result

    @staticmethod
    def _is_p04_facebook(row: dict) -> bool:
        """判断是否为 P04 Facebook 行"""
        partner = (row.get("partner_name", "") or "").lower()
        if "facebook" not in partner:
            return False
        text = (
            (row.get("campaign_network", "") or "") + " " +
            (row.get("creative_network", "") or "")
        ).upper()
        return "P4" in text or "P04" in text
