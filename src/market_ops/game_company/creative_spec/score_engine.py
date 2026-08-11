from typing import Dict, List, Any, Optional
import random


class ScoreEngine:
    def __init__(self):
        self._benchmarks = {
            "ctr": {"top": 0.025, "average": 0.012, "poor": 0.005},
            "ipm": {"top": 15.0, "average": 8.0, "poor": 3.0},
            "roas": {"top": 0.50, "average": 0.17, "poor": 0.05},
        }

    def score(
        self, subject_center: float = 0.5, contrast: float = 0.15, saturation: float = 0.45,
        text_density: float = 0.015, motion_change: float = 0.10, reward_surge: float = 0.05,
        has_cta: bool = True, aspect_ratio: str = "9:16", palette: str = "warm"
    ) -> Dict[str, Any]:
        dimensions = {}

        d_subject = min(100, subject_center / 0.40 * 100) if subject_center < 0.40 else 100
        dimensions["subject_center"] = d_subject

        d_contrast = min(100, contrast / 0.15 * 100) if contrast < 0.15 else 100
        dimensions["contrast"] = d_contrast

        d_saturation = min(100, saturation / 0.45 * 100) if saturation < 0.45 else 100
        dimensions["saturation"] = d_saturation

        d_text = max(0, 100 - (text_density / 0.015 * 100)) if text_density > 0.015 else 100
        dimensions["text_density"] = d_text

        d_motion = min(100, motion_change / 0.10 * 100) if motion_change < 0.10 else 100
        dimensions["motion"] = d_motion

        d_reward = min(100, reward_surge / 0.05 * 100) if reward_surge < 0.05 else 100
        dimensions["reward"] = d_reward

        d_cta = 100 if has_cta else 0
        dimensions["cta"] = d_cta

        d_ratio = 100 if aspect_ratio == "9:16" else 60
        dimensions["aspect_ratio"] = d_ratio

        d_palette = 100 if palette == "warm" else (70 if palette == "neutral" else 50)
        dimensions["palette"] = d_palette

        weights = {
            "subject_center": 0.15, "contrast": 0.15, "saturation": 0.12,
            "text_density": 0.12, "motion": 0.10, "reward": 0.12,
            "cta": 0.08, "aspect_ratio": 0.06, "palette": 0.10,
        }

        overall = sum(dimensions[k] * weights[k] for k in weights)
        overall = max(0, min(100, overall))

        predicted_ctr = self._predict_ctr(overall)
        predicted_ipm = self._predict_ipm(overall)
        predicted_roas = self._predict_roas(overall)

        return {
            "overall_score": round(overall, 1),
            "dimensions": {k: round(v, 1) for k, v in dimensions.items()},
            "predictions": {
                "expected_ctr": round(predicted_ctr, 4),
                "expected_ipm": round(predicted_ipm, 2),
                "expected_roas": round(predicted_roas, 3),
            },
            "grade": self._get_grade(overall),
        }

    def _predict_ctr(self, score: float) -> float:
        bench = self._benchmarks["ctr"]
        return bench["poor"] + (bench["top"] - bench["poor"]) * (score / 100)

    def _predict_ipm(self, score: float) -> float:
        bench = self._benchmarks["ipm"]
        return bench["poor"] + (bench["top"] - bench["poor"]) * (score / 100)

    def _predict_roas(self, score: float) -> float:
        bench = self._benchmarks["roas"]
        return bench["poor"] + (bench["top"] - bench["poor"]) * (score / 100)

    def _get_grade(self, score: float) -> str:
        if score >= 90:
            return "S"
        elif score >= 80:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 60:
            return "C"
        else:
            return "D"

    def get_stats(self) -> Dict[str, Any]:
        return {
            "metrics": list(self._benchmarks.keys()),
            "benchmarks": self._benchmarks,
        }
