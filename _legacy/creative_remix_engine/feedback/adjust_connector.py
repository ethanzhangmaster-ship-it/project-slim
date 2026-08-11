"""Adjust Connector — Adjust 数据反馈接口"""
import csv
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from ..config import DATA_ROOT
from ..models import PerformanceData


class AdjustConnector:
    """读取 Adjust 投放数据并更新创意记忆"""

    def __init__(self, game_code: str = "P04"):
        self.game_code = game_code

    def fetch_performance(self, days: int = 7) -> List[PerformanceData]:
        """
        读取最近 N 天的 Adjust 数据
        （简化版：直接读取已有的 final_adjust_material_report.csv）
        """
        csv_path = DATA_ROOT / "final_adjust_material_report.csv"
        if not csv_path.exists():
            return []

        data = []
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(PerformanceData(
                    creative_id=row.get("creative_id", ""),
                    v_num=row.get("v_num", ""),
                    spend=float(row.get("spend", 0) or 0),
                    revenue=float(row.get("revenue", 0) or 0),
                    roas=float(row.get("roas", 0) or 0),
                    purchase=int(float(row.get("purchase", 0) or 0)),
                    ctr=float(row.get("ctr", 0) or 0),
                    cvr=float(row.get("cvr", 0) or 0),
                    cost=float(row.get("cost", 0) or 0),
                    installs=int(float(row.get("installs", 0) or 0)),
                    content_type=row.get("content", ""),
                    duration=row.get("duration", ""),
                    ratio=row.get("ratio", ""),
                ))
        return data

    def get_creative_performance(self, creative_id: str) -> Optional[Dict]:
        """获取单个创意的表现"""
        all_perf = self.fetch_performance()
        matches = [p for p in all_perf if p.creative_id == creative_id or p.v_num in creative_id]
        if not matches:
            return None

        total_spend = sum(p.spend for p in matches)
        total_revenue = sum(p.revenue for p in matches)
        total_purchase = sum(p.purchase for p in matches)

        return {
            "creative_id": creative_id,
            "spend": total_spend,
            "revenue": total_revenue,
            "roas": total_revenue / max(total_spend, 1),
            "purchase": total_purchase,
            "purchase_rate": total_purchase / max(total_spend, 1) * 1000,
            "samples": len(matches),
        }
