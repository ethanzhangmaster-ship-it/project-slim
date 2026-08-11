"""Quality Predictor - 质量预测器"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class QualityPrediction:
    """质量预测"""
    score: float = 0.0
    predicted_ctr: float = 0.0
    predicted_ipm: float = 0.0
    predicted_roas: float = 0.0
    factors: Dict[str, float] = field(default_factory=dict)


class QualityPredictor:
    """质量预测器"""

    def predict(self, blueprint: Dict[str, Any], consistency_score: float) -> QualityPrediction:
        """预测视频质量"""
        prediction = QualityPrediction()

        factors = {}

        shot_list = blueprint.get("shot_list", {}).get("shots", [])
        creative_review = blueprint.get("creative_review", {})
        camera_specs = blueprint.get("camera_spec", {}).get("specs", [])

        factors["consistency"] = consistency_score

        if shot_list:
            avg_duration = sum(s.get("duration", 0) for s in shot_list) / len(shot_list)
            factors["shot_count"] = min(len(shot_list) / 10, 1.0)
            factors["avg_duration"] = min(avg_duration / 5, 1.0)

        if camera_specs:
            dynamic_shots = sum(1 for c in camera_specs if c.get("move") != "static")
            factors["camera_dynamics"] = dynamic_shots / len(camera_specs) if camera_specs else 0.5

        fb_score = creative_review.get("facebook_score", 0)
        if fb_score:
            factors["facebook_score"] = min(fb_score / 100, 1.0)

        factors["complexity"] = self._calculate_complexity(shot_list)

        weights = {
            "consistency": 0.3,
            "shot_count": 0.15,
            "avg_duration": 0.1,
            "camera_dynamics": 0.15,
            "facebook_score": 0.15,
            "complexity": 0.15,
        }

        total_score = sum(factors.get(k, 0) * weights.get(k, 0) for k in weights)
        prediction.score = round(total_score * 100, 2)

        prediction.predicted_ctr = round(min(total_score * 3.5, 15), 2)
        prediction.predicted_ipm = round(min(total_score * 20, 80), 2)
        prediction.predicted_roas = round(min(total_score * 8, 30), 2)

        prediction.factors = factors

        return prediction

    def _calculate_complexity(self, shots: List[Dict[str, Any]]) -> float:
        """计算视频复杂度"""
        if not shots:
            return 0.5

        complex_elements = 0
        total_elements = 0

        for shot in shots:
            if shot.get("fx") and isinstance(shot["fx"], list) and len(shot["fx"]) > 0:
                complex_elements += 1
            total_elements += 1

            if shot.get("motion") and shot["motion"] != "static":
                complex_elements += 1
            total_elements += 1

        return complex_elements / total_elements if total_elements > 0 else 0.5

    def save_prediction(self, prediction: QualityPrediction, path: str) -> None:
        """保存质量预测"""
        data = {
            "score": prediction.score,
            "predicted_ctr": prediction.predicted_ctr,
            "predicted_ipm": prediction.predicted_ipm,
            "predicted_roas": prediction.predicted_roas,
            "factors": prediction.factors,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)