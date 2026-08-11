"""Model Training V3.2.1 — 使用最佳可用ML库"""
import json
import pickle
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np

from ..feature_schema import CreativeFeatureVector, MODEL_FEATURES
from ..feature_validator import FeatureValidator
from .dependency_checker import get_best_model_class
from ...config import MEMORY_DIR


class ModelTrainer:
    """训练 CTR / CVR / ROAS 预测模型"""

    def __init__(self, game_code: str = "P04"):
        self.game_code = game_code
        self.model_dir = MEMORY_DIR / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.models: Dict[str, any] = {}
        self.validator = FeatureValidator()

    def train(self, features: List[CreativeFeatureVector]) -> Dict[str, dict]:
        """训练三个模型"""
        if len(features) < 10:
            print(f"  训练数据不足 ({len(features)} 条)，跳过模型训练")
            return {}

        # Phase 3: Feature Validation
        print("  [Phase 3] Feature Validation...")
        features, report = self.validator.validate(features)
        print(f"    Quality: {report['feature_quality']}, Missing: {report['missing']}, Status: {report['status']}")

        # 获取最佳模型类
        ModelClass, model_type = get_best_model_class()
        print(f"  使用模型: {model_type}")

        X = np.array([f.to_model_input() for f in features])

        results = {}

        # CTR Model
        y_ctr = np.array([f.ctr for f in features])
        results["ctr"] = self._train_model(X, y_ctr, "ctr", ModelClass, model_type)

        # CVR / Purchase Rate Model
        y_cvr = np.array([f.purchase_rate for f in features])
        results["cvr"] = self._train_model(X, y_cvr, "cvr", ModelClass, model_type)

        # ROAS Model
        y_roas = np.array([f.roas for f in features])
        results["roas"] = self._train_model(X, y_roas, "roas", ModelClass, model_type)

        return results

    def _train_model(self, X: np.ndarray, y: np.ndarray, name: str,
                     ModelClass, model_type: str) -> dict:
        """训练单个模型"""
        valid_mask = ~np.isnan(y) & (y >= 0)
        if valid_mask.sum() < 5:
            return {"status": "failed", "reason": "insufficient valid labels", "model": None}

        X_valid = X[valid_mask]
        y_valid = y[valid_mask]

        n = len(X_valid)
        split = int(n * 0.8)
        if split < 5:
            split = n

        X_train, X_val = X_valid[:split], X_valid[split:]
        y_train, y_val = y_valid[:split], y_valid[split:]

        model = None
        val_score = 0

        if ModelClass:
            try:
                if model_type == "xgboost":
                    model = ModelClass(n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42)
                else:
                    model = ModelClass(n_estimators=100, max_depth=4, random_state=42)
                model.fit(X_train, y_train)
                if len(X_val) > 0:
                    val_score = model.score(X_val, y_val)
                print(f"  [{name}] {model_type} | val_r2: {val_score:.3f} | samples: {len(X_valid)}")
            except Exception as e:
                print(f"  [{name}] {model_type} failed: {e}, fallback to numpy")
                model = None

        if model is None:
            # numpy fallback
            model = self._numpy_linear_regression(X_train, y_train)
            if len(X_val) > 0:
                y_pred = self._predict_numpy(model, X_val)
                val_score = self._r2_score(y_val, y_pred)
            print(f"  [{name}] numpy fallback | val_r2: {val_score:.3f}")

        # 保存
        model_path = self.model_dir / f"{self.game_code}_{name}.pkl"
        with open(model_path, "wb") as f:
            pickle.dump({"model": model, "type": model_type}, f)

        self.models[name] = model

        return {
            "status": "success" if val_score > 0 else "weak",
            "val_r2": round(float(val_score), 3),
            "model_path": str(model_path),
            "model_type": model_type,
            "samples": len(X_valid),
        }

    @staticmethod
    def _numpy_linear_regression(X: np.ndarray, y: np.ndarray) -> dict:
        X_bias = np.column_stack([np.ones(len(X)), X])
        try:
            coeffs = np.linalg.pinv(X_bias.T @ X_bias) @ X_bias.T @ y
        except:
            coeffs = np.zeros(X_bias.shape[1])
        return {"coeffs": coeffs, "type": "numpy_linear"}

    @staticmethod
    def _predict_numpy(model: dict, X: np.ndarray) -> np.ndarray:
        X_bias = np.column_stack([np.ones(len(X)), X])
        return X_bias @ model["coeffs"]

    @staticmethod
    def _r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        return 1 - ss_res / ss_tot if ss_tot > 0 else 0
