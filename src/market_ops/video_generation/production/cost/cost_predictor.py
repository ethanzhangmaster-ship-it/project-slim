"""Cost Predictor - 成本预测器"""
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class Prediction:
    generation_id: str = ""
    estimated_cost: float = 0.0
    actual_cost: float = 0.0
    platform: str = ""
    duration: float = 0.0


class CostPredictor:
    """成本预测器 - 基于历史数据预测成本"""

    _historical_data: Dict[str, List[Prediction]] = {}

    def predict(self, generation_id: str, platform: str, duration: float, resolution: str = "1080p") -> float:
        base_rates = {
            "veo": 0.20,
            "kling": 0.15,
            "runway": 0.25,
            "comfyui": 0.05,
        }
        resolution_factors = {
            "720p": 0.8,
            "1080p": 1.0,
            "2k": 1.5,
            "4k": 2.5,
        }

        base_rate = base_rates.get(platform, 0.1)
        factor = resolution_factors.get(resolution, 1.0)
        estimated = duration * base_rate * factor

        if platform in self._historical_data and len(self._historical_data[platform]) >= 10:
            historical_avg = sum(p.estimated_cost for p in self._historical_data[platform]) / len(self._historical_data[platform])
            actual_avg = sum(p.actual_cost for p in self._historical_data[platform] if p.actual_cost > 0) / len([p for p in self._historical_data[platform] if p.actual_cost > 0] or [1])
            adjustment = actual_avg / historical_avg if historical_avg > 0 else 1.0
            estimated *= adjustment

        return round(estimated, 2)

    def record_actual(self, generation_id: str, platform: str, estimated_cost: float, actual_cost: float, duration: float):
        if platform not in self._historical_data:
            self._historical_data[platform] = []
        self._historical_data[platform].append(Prediction(
            generation_id=generation_id,
            estimated_cost=estimated_cost,
            actual_cost=actual_cost,
            platform=platform,
            duration=duration,
        ))

    def get_accuracy(self, platform: str) -> float:
        if platform not in self._historical_data or len(self._historical_data[platform]) < 5:
            return 0.0
        predictions = [p for p in self._historical_data[platform] if p.actual_cost > 0]
        if not predictions:
            return 0.0
        errors = [abs(p.estimated_cost - p.actual_cost) / p.actual_cost for p in predictions]
        avg_error = sum(errors) / len(errors)
        return round(1.0 - avg_error, 2)

    def get_platform_stats(self) -> Dict[str, Any]:
        stats = {}
        for platform, predictions in self._historical_data.items():
            if predictions:
                stats[platform] = {
                    "total_generations": len(predictions),
                    "avg_estimated": round(sum(p.estimated_cost for p in predictions) / len(predictions), 2),
                    "avg_actual": round(sum(p.actual_cost for p in predictions if p.actual_cost > 0) / len([p for p in predictions if p.actual_cost > 0] or [1]), 2),
                    "accuracy": self.get_accuracy(platform),
                }
        return stats