"""Model Inference V3.2.1 — 带校准的推理"""
import pickle
import numpy as np
from pathlib import Path
from typing import Dict

from ..feature_schema import CreativeFeatureVector
from ..calibration import PredictionCalibrator
from ...config import MEMORY_DIR


class ModelInference:
    """加载训练好的模型进行推理，带预测校准"""

    def __init__(self, game_code: str = "P04"):
        self.game_code = game_code
        self.model_dir = MEMORY_DIR / "models"
        self.models: Dict[str, any] = {}
        self.calibrator = PredictionCalibrator()
        self._load_models()

    def _load_models(self):
        for name in ["ctr", "cvr", "roas"]:
            path = self.model_dir / f"{self.game_code}_{name}.pkl"
            if path.exists():
                try:
                    with open(path, "rb") as f:
                        data = pickle.load(f)
                    self.models[name] = data["model"]
                except Exception as e:
                    print(f"  加载模型 {name} 失败: {e}")

    def predict(self, feature: CreativeFeatureVector) -> Dict[str, float]:
        """预测并校准"""
        X = np.array([feature.to_model_input()])

        raw = {
            "expected_ctr": 0.02,
            "expected_cvr": 0.005,
            "expected_roas": 0.8,
        }

        if "ctr" in self.models:
            raw["expected_ctr"] = max(0, float(self._predict(self.models["ctr"], X)[0]))
        if "cvr" in self.models:
            raw["expected_cvr"] = max(0, float(self._predict(self.models["cvr"], X)[0]))
        if "roas" in self.models:
            raw["expected_roas"] = max(0, float(self._predict(self.models["roas"], X)[0]))

        # Phase 4: Calibration
        return self.calibrator.calibrate(raw)

    def _predict(self, model, X: np.ndarray):
        if hasattr(model, "predict"):
            return model.predict(X)
        elif isinstance(model, dict) and "coeffs" in model:
            X_bias = np.column_stack([np.ones(len(X)), X])
            return X_bias @ model["coeffs"]
        return np.zeros(len(X))

    def is_ready(self) -> bool:
        return len(self.models) >= 2
