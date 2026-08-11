"""CPI Predictor — 预测 Cost Per Install

输入：Video Feature
输出：predicted_cpi

支持：XGBoost / LightGBM / RandomForest
"""
import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

import numpy as np

from ..config import OUTPUT_DIR
from .performance_feature_builder import PerformanceFeatureBuilder


class CPIPredictor:
    """CPI 预测器"""

    MODELS = ["random_forest", "xgboost", "lightgbm"]

    def __init__(self, model_type: str = "random_forest"):
        self.model_type = model_type.lower()
        self.model = None
        self.feature_builder = PerformanceFeatureBuilder()
        self.trained = False
        self.metrics = {}

    def train(self, X: np.ndarray, y: np.ndarray):
        """训练模型"""
        print(f"[CPIPredictor] Training {self.model_type}...")

        if self.model_type == "random_forest":
            self._train_random_forest(X, y)
        elif self.model_type == "xgboost":
            self._train_xgboost(X, y)
        elif self.model_type == "lightgbm":
            self._train_lightgbm(X, y)

        self.trained = True
        print(f"[CPIPredictor] Training complete.")

    def _train_random_forest(self, X: np.ndarray, y: np.ndarray):
        """训练 Random Forest"""
        try:
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

            X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

            self.model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1,
            )
            self.model.fit(X_train, y_train)

            y_pred = self.model.predict(X_val)
            self.metrics = {
                "mae": round(mean_absolute_error(y_val, y_pred), 4),
                "mse": round(mean_squared_error(y_val, y_pred), 4),
                "rmse": round(np.sqrt(mean_squared_error(y_val, y_pred)), 4),
                "r2": round(r2_score(y_val, y_pred), 4),
            }
            print(f"  Metrics: MAE={self.metrics['mae']} R2={self.metrics['r2']}")
        except ImportError:
            self.model = None
            print("  sklearn not available, falling back to baseline")

    def _train_xgboost(self, X: np.ndarray, y: np.ndarray):
        """训练 XGBoost"""
        try:
            import xgboost as xgb
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

            X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

            dtrain = xgb.DMatrix(X_train, label=y_train)
            dval = xgb.DMatrix(X_val, label=y_val)

            params = {
                "objective": "reg:squarederror",
                "max_depth": 6,
                "learning_rate": 0.1,
                "n_estimators": 100,
                "random_state": 42,
            }

            self.model = xgb.train(params, dtrain, num_boost_round=100,
                                   evals=[(dval, "val")], verbose_eval=False)

            y_pred = self.model.predict(dval)
            self.metrics = {
                "mae": round(mean_absolute_error(y_val, y_pred), 4),
                "mse": round(mean_squared_error(y_val, y_pred), 4),
                "rmse": round(np.sqrt(mean_squared_error(y_val, y_pred)), 4),
                "r2": round(r2_score(y_val, y_pred), 4),
            }
            print(f"  Metrics: MAE={self.metrics['mae']} R2={self.metrics['r2']}")
        except ImportError:
            self.model = None
            print("  xgboost not available, falling back to baseline")

    def _train_lightgbm(self, X: np.ndarray, y: np.ndarray):
        """训练 LightGBM"""
        try:
            import lightgbm as lgb
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

            X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

            params = {
                "objective": "regression",
                "max_depth": 6,
                "learning_rate": 0.1,
                "n_estimators": 100,
                "random_state": 42,
            }

            self.model = lgb.LGBMRegressor(**params)
            self.model.fit(X_train, y_train, eval_set=[(X_val, y_val)],
                          eval_metric="mae", verbose=False)

            y_pred = self.model.predict(X_val)
            self.metrics = {
                "mae": round(mean_absolute_error(y_val, y_pred), 4),
                "mse": round(mean_squared_error(y_val, y_pred), 4),
                "rmse": round(np.sqrt(mean_squared_error(y_val, y_pred)), 4),
                "r2": round(r2_score(y_val, y_pred), 4),
            }
            print(f"  Metrics: MAE={self.metrics['mae']} R2={self.metrics['r2']}")
        except ImportError:
            self.model = None
            print("  lightgbm not available, falling back to baseline")

    def predict(self, dna: Dict) -> dict:
        """预测 CPI"""
        if not self.trained or self.model is None:
            return self._baseline_predict(dna)

        features = self.feature_builder.encode_dna(dna)
        features = features.reshape(1, -1)

        if hasattr(self.model, 'predict'):
            pred_cpi = self.model.predict(features)[0]
        else:
            pred_cpi = self._baseline_predict(dna)["predicted_cpi"]

        return {
            "predicted_cpi": round(max(0.15, min(1.5, pred_cpi)), 2),
            "model_type": self.model_type,
            "confidence": self._estimate_confidence(),
        }

    def _baseline_predict(self, dna: Dict) -> dict:
        """基线预测（基于规则）"""
        base_cpi = 0.6

        hook_penalty = {
            "transformation": 0.8,
            "challenge": 0.85,
            "curiosity": 1.0,
            "urgency": 0.88,
            "shock": 0.82,
        }
        base_cpi *= hook_penalty.get(dna.get("hook", ""), 1.0)

        subject_penalty = {
            "dragon": 0.85,
            "witch": 0.9,
        }
        base_cpi *= subject_penalty.get(dna.get("subject", ""), 1.0)

        return {
            "predicted_cpi": round(base_cpi, 2),
            "model_type": "baseline",
            "confidence": 50.0,
        }

    def _estimate_confidence(self) -> float:
        """估算置信度"""
        if not self.metrics:
            return 50.0

        r2 = self.metrics.get("r2", 0)
        return min(95, 50 + r2 * 50)

    def get_feature_importance(self) -> list:
        """获取特征重要性"""
        if not self.trained or self.model is None:
            return []

        try:
            importances = self.model.feature_importances_
            return self.feature_builder.analyze_feature_importance(importances)
        except AttributeError:
            return []

    def save_model(self, output_path: Optional[Path] = None) -> Path:
        """保存模型"""
        if output_path is None:
            output_path = OUTPUT_DIR / "v38_1" / f"cpi_{self.model_type}_model.json"

        data = {
            "model_type": self.model_type,
            "trained": self.trained,
            "metrics": self.metrics,
            "feature_names": self.feature_builder.get_feature_names(),
            "feature_importance": self.get_feature_importance(),
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return output_path
