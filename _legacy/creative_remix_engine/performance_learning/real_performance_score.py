"""Real Performance Score — 基于真实数据的创意评分

公式：
Performance Score = 真实CTR × 30% + 真实CPI × 25% + 真实ROI × 35% + Retention × 10%

从 V3.8 的"人工公式 Buying Score"升级为"真实数据驱动的 Performance Score"。
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import numpy as np

from ..config import OUTPUT_DIR
from ..performance_learning import CTRPredictor, CPIPredictor, ROIPredictor


class RealPerformanceScore:
    """真实表现评分引擎"""

    WEIGHTS = {
        "ctr": 0.30,
        "cpi": 0.25,
        "roi": 0.35,
        "retention": 0.10,
    }

    def __init__(self, ctr_predictor: Optional[CTRPredictor] = None,
                 cpi_predictor: Optional[CPIPredictor] = None,
                 roi_predictor: Optional[ROIPredictor] = None):
        self.ctr_predictor = ctr_predictor or CTRPredictor()
        self.cpi_predictor = cpi_predictor or CPIPredictor()
        self.roi_predictor = roi_predictor or ROIPredictor()

    def calculate(self, dna: Dict, real_performance: Optional[Dict] = None) -> Dict:
        """计算真实表现评分"""
        if real_performance:
            return self._calculate_from_real_data(dna, real_performance)
        else:
            return self._calculate_from_prediction(dna)

    def _calculate_from_real_data(self, dna: Dict, real_performance: Dict) -> Dict:
        """基于真实数据计算"""
        ctr = real_performance.get("ctr", 0)
        cpi = real_performance.get("cpi", float('inf'))
        d7_roi = real_performance.get("d7_roi", 0)
        d30_roi = real_performance.get("d30_roi", 0)
        ltv_d7 = real_performance.get("ltv_d7", 0)
        ltv_d30 = real_performance.get("ltv_d30", 0)

        # 标准化各项指标
        ctr_score = min(100, ctr * 15)
        cpi_score = max(0, 100 - cpi * 80)
        roi_score = min(100, d7_roi * 150)
        retention_score = self._calculate_retention_score(ltv_d7, ltv_d30)

        # 综合评分
        performance_score = (
            ctr_score * self.WEIGHTS["ctr"] +
            cpi_score * self.WEIGHTS["cpi"] +
            roi_score * self.WEIGHTS["roi"] +
            retention_score * self.WEIGHTS["retention"]
        )

        performance_score = min(100, max(0, performance_score))

        # 计算综合 Ad Value
        ad_value = self._calculate_ad_value(ctr, cpi, d7_roi)

        return {
            "performance_score": round(performance_score, 1),
            "breakdown": {
                "ctr_score": round(ctr_score, 1),
                "cpi_score": round(cpi_score, 1),
                "roi_score": round(roi_score, 1),
                "retention_score": round(retention_score, 1),
            },
            "weights": self.WEIGHTS,
            "real_metrics": {
                "ctr": ctr,
                "cpi": cpi,
                "d7_roi": d7_roi,
                "d30_roi": d30_roi,
            },
            "ad_value": round(ad_value, 2),
            "grade": self._determine_grade(performance_score),
        }

    def _calculate_from_prediction(self, dna: Dict) -> Dict:
        """基于预测数据计算"""
        ctr_pred = self.ctr_predictor.predict(dna)
        cpi_pred = self.cpi_predictor.predict(dna)
        roi_pred = self.roi_predictor.predict(dna)

        ctr = ctr_pred["predicted_ctr"]
        cpi = cpi_pred["predicted_cpi"]
        d7_roi = roi_pred["d7_roi"]
        d30_roi = roi_pred["d30_roi"]

        ctr_score = min(100, ctr * 15)
        cpi_score = max(0, 100 - cpi * 80)
        roi_score = min(100, d7_roi * 150)
        retention_score = self._calculate_retention_score_from_roi(d7_roi, d30_roi)

        performance_score = (
            ctr_score * self.WEIGHTS["ctr"] +
            cpi_score * self.WEIGHTS["cpi"] +
            roi_score * self.WEIGHTS["roi"] +
            retention_score * self.WEIGHTS["retention"]
        )

        performance_score = min(100, max(0, performance_score))

        ad_value = self._calculate_ad_value(ctr, cpi, d7_roi)

        return {
            "performance_score": round(performance_score, 1),
            "breakdown": {
                "ctr_score": round(ctr_score, 1),
                "cpi_score": round(cpi_score, 1),
                "roi_score": round(roi_score, 1),
                "retention_score": round(retention_score, 1),
            },
            "weights": self.WEIGHTS,
            "predicted_metrics": {
                "ctr": ctr,
                "cpi": cpi,
                "d7_roi": d7_roi,
                "d30_roi": d30_roi,
            },
            "ad_value": round(ad_value, 2),
            "grade": self._determine_grade(performance_score),
        }

    def _calculate_retention_score(self, ltv_d7: float, ltv_d30: float) -> float:
        """计算留存评分"""
        if ltv_d30 > 0:
            retention_ratio = ltv_d7 / ltv_d30
        else:
            retention_ratio = 0.5

        return min(100, 50 + retention_ratio * 50)

    def _calculate_retention_score_from_roi(self, d7_roi: float, d30_roi: float) -> float:
        """从 ROI 估算留存评分"""
        if d30_roi > 0:
            retention_ratio = d7_roi / d30_roi
        else:
            retention_ratio = 0.5

        return min(100, 50 + retention_ratio * 50)

    def _calculate_ad_value(self, ctr: float, cpi: float, roi: float) -> float:
        """计算综合 Ad Value"""
        return (
            ctr * 15 +
            (1.0 / max(cpi, 0.01)) * 10 +
            roi * 100 * 3
        )

    def _determine_grade(self, score: float) -> str:
        """确定等级"""
        if score >= 85:
            return "S+"
        elif score >= 75:
            return "S"
        elif score >= 60:
            return "A"
        elif score >= 45:
            return "B"
        else:
            return "Reject"

    def batch_calculate(self, data: List[Dict]) -> List[Dict]:
        """批量计算"""
        results = []
        for item in data:
            dna = item.get("dna", {})
            real_performance = item.get("performance")
            result = self.calculate(dna, real_performance)
            result["creative_id"] = item.get("creative_id", "")
            result["video_name"] = item.get("video_name", "")
            results.append(result)
        return results

    def save_scores(self, scores: List[Dict], filename: str = "creative_performance_score.json") -> Path:
        """保存评分结果"""
        output_path = OUTPUT_DIR / "v38_1" / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        summary = self._generate_summary(scores)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "data": scores,
                "timestamp": datetime.now().isoformat(),
                "total": len(scores),
                "summary": summary,
            }, f, ensure_ascii=False, indent=2)

        return output_path

    def _generate_summary(self, scores: List[Dict]) -> dict:
        """生成汇总"""
        if not scores:
            return {}

        scores_list = [s["performance_score"] for s in scores]
        ad_values = [s["ad_value"] for s in scores]

        grade_dist = {"S+": 0, "S": 0, "A": 0, "B": 0, "Reject": 0}
        for s in scores:
            grade_dist[s["grade"]] += 1

        return {
            "avg_performance_score": round(np.mean(scores_list), 1),
            "median_performance_score": round(np.median(scores_list), 1),
            "avg_ad_value": round(np.mean(ad_values), 2),
            "grade_distribution": grade_dist,
        }
