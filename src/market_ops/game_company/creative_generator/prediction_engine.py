from typing import Dict, List, Any, Optional
from .variant_engine import CreativeAsset


class PredictionEngine:
    def __init__(self):
        self._benchmarks = {
            "hook_type": {"collection": 1.2, "reward": 1.1, "curiosity": 0.8, "comparison": 0.7, "crisis": 0.6},
            "palette_bonus": {"warm": 1.15, "neutral": 1.0, "cool": 0.85},
            "hero_boost": 1.1,
            "reward_boost": 1.05,
        }

    def predict(self, asset: CreativeAsset) -> Dict[str, Any]:
        base_roas = 0.17
        base_ctr = 0.012
        base_ipm = 8.0
        base_cvr = 0.05
        base_cpp = 2.50

        hook_mult = self._benchmarks["hook_type"].get(asset.hook_type, 1.0)
        palette = asset.hero.get("palette", "neutral")
        if "gold" in palette or "warm" in palette or "golden" in palette:
            pal_mult = self._benchmarks["palette_bonus"]["warm"]
        elif "ice" in palette or "blue" in palette or "cold" in palette:
            pal_mult = self._benchmarks["palette_bonus"]["cool"]
        else:
            pal_mult = self._benchmarks["palette_bonus"]["neutral"]

        hero_mult = self._benchmarks["hero_boost"] if asset.hero else 1.0
        reward_mult = self._benchmarks["reward_boost"] if asset.reward else 1.0

        composite = hook_mult * pal_mult * hero_mult * reward_mult

        predicted_roas = base_roas * composite
        predicted_ctr = base_ctr * composite
        predicted_ipm = base_ipm * composite
        predicted_cvr = base_cvr * (composite / 1.1)
        predicted_cpp = base_cpp / (composite / 1.1)

        confidence = min(0.95, 0.65 + (composite - 0.8) * 0.15)

        reasons = []
        reasons.append(f"Hook type '{asset.hook_type}': multiplier {hook_mult:.2f}")
        reasons.append(f"Palette '{asset.hero.get('palette')}': multiplier {pal_mult:.2f}")
        reasons.append(f"Hero '{asset.hero.get('name')}': present (+{self._benchmarks['hero_boost']:.0%})")
        if asset.reward:
            reasons.append(f"Reward '{asset.reward.get('name')}': present (+{self._benchmarks['reward_boost']:.0%})")

        return {
            "predicted_ctr": round(predicted_ctr, 4),
            "predicted_ipm": round(predicted_ipm, 2),
            "predicted_cvr": round(predicted_cvr, 4),
            "predicted_cpp": round(predicted_cpp, 2),
            "predicted_roas": round(predicted_roas, 3),
            "confidence": round(confidence, 2),
            "composite_multiplier": round(composite, 2),
            "reasons": reasons,
            "grade": self._get_grade(predicted_roas),
        }

    def _get_grade(self, roas: float) -> str:
        if roas >= 0.50:
            return "S"
        elif roas >= 0.35:
            return "A"
        elif roas >= 0.20:
            return "B"
        elif roas >= 0.10:
            return "C"
        else:
            return "D"

    def batch_predict(self, assets: List[CreativeAsset]) -> List[Dict[str, Any]]:
        return [self.predict(a) for a in assets]

    def get_stats(self) -> Dict[str, Any]:
        return {"benchmark_categories": list(self._benchmarks.keys())}
