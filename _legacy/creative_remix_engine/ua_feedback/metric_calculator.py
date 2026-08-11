"""Metric Calculator — 统一指标计算

计算：
- CTR = click / impression
- CPI = spend / install
- CVR = install / click
- ROAS = revenue / spend
- Payback (D1, D7, D30)

输出：{creative_id}_performance.json
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from ..config import OUTPUT_DIR


class MetricCalculator:
    """统一指标计算器"""

    def calculate(self, raw_data: List[dict]) -> List[dict]:
        """计算所有创意的指标"""
        results = []

        for item in raw_data:
            performance = self._calculate_single(item)
            if performance:
                results.append({
                    "creative_id": item.get("creative_id", ""),
                    "video_name": item.get("video_name", ""),
                    "platform": item.get("platform", ""),
                    "raw": item,
                    "performance": performance,
                })

        return results

    def _calculate_single(self, item: dict) -> Optional[dict]:
        """计算单个创意的指标"""
        spend = item.get("spend", 0)
        impressions = item.get("impressions", 0)
        clicks = item.get("clicks", 0)
        installs = item.get("installs", 0)
        purchase = item.get("purchase", 0)
        d7_revenue = item.get("d7_revenue", 0)
        d30_revenue = item.get("d30_revenue", 0)

        # 数据有效性检查
        if impressions <= 0 or spend <= 0:
            return None

        # CTR: Click Through Rate
        ctr = clicks / impressions if impressions > 0 else 0

        # CPI: Cost Per Install
        cpi = spend / installs if installs > 0 else float('inf')

        # CVR: Conversion Rate
        cvr = installs / clicks if clicks > 0 else 0

        # ROAS: Return On Ad Spend
        d7_roas = d7_revenue / spend if spend > 0 else 0
        d30_roas = d30_revenue / spend if spend > 0 else 0

        # ROI (基于 ROAS)
        d7_roi = d7_roas - 1 if d7_roas > 0 else 0
        d30_roi = d30_roas - 1 if d30_roas > 0 else 0

        # Payback Period 估算
        payback_d7 = self._calculate_payback(spend, d7_revenue)
        payback_d30 = self._calculate_payback(spend, d30_revenue)

        # LTV 估算
        ltv_d7 = self._estimate_ltv(d7_revenue, installs)
        ltv_d30 = self._estimate_ltv(d30_revenue, installs)

        return {
            "ctr": round(ctr * 100, 2),
            "cpi": round(cpi, 2),
            "cvr": round(cvr * 100, 2),
            "d7_roas": round(d7_roas, 2),
            "d30_roas": round(d30_roas, 2),
            "d7_roi": round(d7_roi, 3),
            "d30_roi": round(d30_roi, 3),
            "payback_d7": payback_d7,
            "payback_d30": payback_d30,
            "ltv_d7": round(ltv_d7, 2),
            "ltv_d30": round(ltv_d30, 2),
            "efficiency_score": self._calculate_efficiency_score(ctr, cpi, d7_roi),
            "quality_flag": self._determine_quality_flag(ctr, cpi, d7_roi),
        }

    @staticmethod
    def _calculate_payback(spend: float, revenue: float) -> Optional[int]:
        """计算回本周期（天数）"""
        if spend <= 0 or revenue <= 0:
            return None

        daily_revenue = revenue / 7
        if daily_revenue <= 0:
            return None

        payback_days = int(spend / daily_revenue)
        return min(payback_days, 30)

    @staticmethod
    def _estimate_ltv(revenue: float, installs: int) -> float:
        """估算 LTV"""
        if installs <= 0:
            return 0.0
        return revenue / installs

    @staticmethod
    def _calculate_efficiency_score(ctr: float, cpi: float, roi: float) -> float:
        """计算效率评分"""
        score = 0.0

        # CTR 评分 (目标 > 3%)
        ctr_score = min(100, ctr * 20)
        score += ctr_score * 0.3

        # CPI 评分 (目标 < $0.5)
        cpi_score = max(0, 100 - cpi * 100)
        score += cpi_score * 0.25

        # ROI 评分 (目标 > 0.3)
        roi_score = min(100, roi * 200)
        score += roi_score * 0.35

        # 基础分
        score += 10

        return round(min(100, score), 1)

    @staticmethod
    def _determine_quality_flag(ctr: float, cpi: float, roi: float) -> str:
        """确定质量标记"""
        if ctr >= 4.0 and cpi <= 0.4 and roi >= 0.5:
            return "winner"
        elif ctr >= 3.0 and cpi <= 0.6 and roi >= 0.2:
            return "good"
        elif ctr >= 2.0 and cpi <= 0.8:
            return "acceptable"
        else:
            return "poor"

    def save_calculated(self, results: List[dict], filename: str = "calculated_metrics.json") -> Path:
        """保存计算结果"""
        output_path = OUTPUT_DIR / "v38_1" / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "data": results,
                "timestamp": datetime.now().isoformat(),
                "total": len(results),
                "summary": self._generate_summary(results),
            }, f, ensure_ascii=False, indent=2)

        return output_path

    def _generate_summary(self, results: List[dict]) -> dict:
        """生成汇总统计"""
        if not results:
            return {}

        ctrs = [r["performance"]["ctr"] for r in results]
        cpis = [r["performance"]["cpi"] for r in results if r["performance"]["cpi"] < 10]
        d7_rois = [r["performance"]["d7_roi"] for r in results]
        d30_rois = [r["performance"]["d30_roi"] for r in results]

        import numpy as np
        return {
            "avg_ctr": round(np.mean(ctrs), 2),
            "median_ctr": round(np.median(ctrs), 2),
            "avg_cpi": round(np.mean(cpis), 2),
            "median_cpi": round(np.median(cpis), 2),
            "avg_d7_roi": round(np.mean(d7_rois), 3),
            "avg_d30_roi": round(np.mean(d30_rois), 3),
            "winner_count": sum(1 for r in results if r["performance"]["quality_flag"] == "winner"),
            "good_count": sum(1 for r in results if r["performance"]["quality_flag"] == "good"),
            "acceptable_count": sum(1 for r in results if r["performance"]["quality_flag"] == "acceptable"),
            "poor_count": sum(1 for r in results if r["performance"]["quality_flag"] == "poor"),
        }

    def calculate_from_file(self, input_path: Path) -> List[dict]:
        """从文件计算指标"""
        if not input_path.exists():
            return []

        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_data = data.get("data", [])
        return self.calculate(raw_data)
