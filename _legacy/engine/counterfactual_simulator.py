"""Counterfactual Simulator — 模拟结构改动后的 ROAS/CTR/CVR 变化。

核心逻辑：
  ΔROAS = Σ(feature_change × feature_weight)

feature_weight 来自 V3.6 PerformanceRegressor 的线性回归系数。
模型不需要很复杂 — linear counterfactual 已经足够做优化排序。

输入：
  - current_features: 25-dim feature dict
  - mutation: {name, feature, delta, ...}
  - model: PerformanceRegressor (trained, with linear coefs)

输出：
  - current_roas: current predicted ROAS
  - new_roas: predicted ROAS after mutation
  - delta_roas: difference
  - confidence: based on model R²
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import numpy as np


class CounterfactualSimulator:
    """Simulate ΔROAS/ΔCTR/ΔCVR from structural mutations.

    Uses the linear regression coefficients from V3.6 to compute
    counterfactual predictions: what WOULD happen if we change
    a specific visual feature.
    """

    def __init__(self):
        self.models = {}          # target → linear model
        self.feature_names = []
        self._loaded = False

    def load_model(self, regressor) -> None:
        """Load trained PerformanceRegressor."""
        self.feature_names = regressor.feature_names
        # Extract linear models for each target
        for target in ["roas", "ctr", "cvr"]:
            key = f"{target}_linear"
            model = regressor.models.get(key)
            if model is not None:
                self.models[target] = model
        self._loaded = True

    def simulate(self, current_features: Dict[str, float],
                 mutation: Dict[str, float],
                 target: str = "roas") -> Dict:
        """Simulate the effect of one mutation on a performance metric.

        Args:
            current_features: original 25-dim feature dict
            mutation: {name, feature, delta, ...} from structure_mutation_engine
            target: "roas", "ctr", or "cvr"

        Returns:
            {
                "mutation": mutation_name,
                "feature": feature_name,
                "current_value": original feature value,
                "new_value": mutated feature value,
                "feature_delta": change in feature,
                "current_prediction": ROAS/CTR/CVR before,
                "new_prediction": ROAS/CTR/CVR after,
                "delta": absolute change,
                "delta_pct": percent change,
                "dimension": hook/comprehension/reward/motion,
                "time_window": "0-1s" etc,
            }
        """
        if not self._loaded:
            return {"error": "No model loaded. Call load_model() first."}

        feat_name = mutation["feature"]
        current_val = mutation.get("current_value", current_features.get(feat_name, 0))
        new_val = mutation.get("target_value", current_val)
        delta_feat = new_val - current_val

        # Build feature vectors
        X_current = self._features_to_vector(current_features)
        X_new = self._features_to_vector(current_features)
        feat_idx = self._feature_index(feat_name)
        if feat_idx >= 0:
            X_new[feat_idx] = new_val

        # Predict
        model = self.models.get(target)
        if model is None:
            return {"error": f"No model for target '{target}'"}

        current_pred = float(model.predict(X_current.reshape(1, -1)).flatten()[0])
        new_pred = float(model.predict(X_new.reshape(1, -1)).flatten()[0])
        delta = new_pred - current_pred
        delta_pct = (delta / max(abs(current_pred), 1e-6)) * 100

        return {
            "mutation": mutation["name"],
            "feature": feat_name,
            "description": mutation.get("description", ""),
            "ae_instruction": mutation.get("ae_instruction", ""),
            "current_value": round(current_val, 4),
            "new_value": round(new_val, 4),
            "feature_delta": round(delta_feat, 4),
            "current_prediction": round(current_pred, 4),
            "new_prediction": round(new_pred, 4),
            "delta": round(delta, 4),
            "delta_pct": round(delta_pct, 2),
            "dimension": mutation.get("dimension", "unknown"),
            "time_window": mutation.get("time_window", "unknown"),
            "target": target,
        }

    def simulate_all(self, current_features: Dict[str, float],
                     mutations: List[Dict],
                     target: str = "roas") -> List[Dict]:
        """Simulate all mutations and return results sorted by delta."""
        results = []
        for m in mutations:
            result = self.simulate(current_features, m, target)
            if "error" not in result:
                results.append(result)

        results.sort(key=lambda x: x["delta"], reverse=True)
        return results

    # ═══════════════════════════════════════════════════════════
    # Internal
    # ═══════════════════════════════════════════════════════════

    def _features_to_vector(self, features: Dict[str, float]) -> np.ndarray:
        """Convert feature dict to ordered numpy array matching model."""
        vec = np.zeros(len(self.feature_names), dtype=np.float32)
        for i, name in enumerate(self.feature_names):
            vec[i] = features.get(name, 0)
        return vec

    def _feature_index(self, name: str) -> int:
        try:
            return self.feature_names.index(name)
        except ValueError:
            return -1
