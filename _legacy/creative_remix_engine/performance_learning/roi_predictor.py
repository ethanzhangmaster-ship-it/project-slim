"""ROI Predictor — 预测 Return On Investment

输入：Video Feature
输出：d7_roi, d30_roi

支持：XGBoost / LightGBM / RandomForest
"""
import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

import numpy as np

from ..config import OUTPUT_DIR
from .performance_feature_builder import PerformanceFeatureBuilder


class ROIPredictor:
    """ROI 预测器"""

    MODELS = ["random_forest", "xgboost", "lightgbm"]

    def __init__(self, model_type: str = "random_forest"):
        self.model_type = model_type.lower()
        self.model_d7 = None
        self.model_d30 = None
        self.feature_builder = PerformanceFeatureBuilder()
        self.trained = False
        self.metrics = {"d7": {}, "d30": {}}

    def train(self, X: np.ndarray, y_d7: np.ndarray, y_d30: np.ndarray):
        """训练模型"""
        print(f"[ROIPredictor] Training {self.model_type}...")

        if self.model_type == "random_forest":
            self._train_random_forest(X, y_d7, y_d30)
        elif self.model_type == "xgboost":
            self._train_xgboost(X, y_d7, y_d30)
        elif self.model_type == "lightgbm":
            self._train_lightgbm(X, y_d7, y_d30)

        self.trained = True
        print(f"[ROIPredictor] Training complete.")

    def _train_random_forest(self, X: np.ndarray, y_d7: np.ndarray, y_d30: np.ndarray):
        """训练 Random Forest"""
        try:
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

            X_train, X_val, y_d7_train, y_d7_val = train_test_split(X, y_d7, test_size=0.2, random_state=42)
            _, _, y_d30_train, y_d30_val = train_test_split(X, y_d30, test_size=0.2, random_state=42)

            # D7 Model
            self.model_d7 = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
            self.model_d7.fit(X_train, y_d7_train)
            y_d7_pred = self.model_d7.predict(X_val)
            self.metrics["d7"] = {
                "mae": round(mean_absolute_error(y_d7_val, y_d7_pred), 4),
                "mse": round(mean_squared_error(y_d7_val, y_d7_pred), 4),
                "rmse": round(np.sqrt(mean_squared_error(y_d7_val, y_d7_pred)), 4),
                "r2": round(r2_score(y_d7_val, y_d7_pred), 4),
            }

            # D30 Model
            self.model_d30 = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
            self.model_d30.fit(X_train, y_d30_train)
            y_d30_pred = self.model_d30.predict(X_val)
            self.metrics["d30"] = {
                "mae": round(mean_absolute_error(y_d30_val, y_d30_pred), 4),
                "mse": round(mean_squared_error(y_d30_val, y_d30_pred), 4),
                "rmse": round(np.sqrt(mean_squared_error(y_d30_val, y_d30_pred)), 4),
                "r2": round(r2_score(y_d30_val, y_d30_pred), 4),
            }

            print(f"  D7 Metrics: MAE={self.metrics['d7']['mae']} R2={self.metrics['d7']['r2']}")
            print(f"  D30 Metrics: MAE={self.metrics['d30']['mae']} R2={self.metrics['d30']['r2']}")
        except ImportError:
            self.model_d7 = None
            self.model_d30 = None
            print("  sklearn not available, falling back to baseline")

    def _train_xgboost(self, X: np.ndarray, y_d7: np.ndarray, y_d30: np.ndarray):
        """训练 XGBoost"""
        try:
            import xgboost as xgb
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

            X_train, X_val, y_d7_train, y_d7_val = train_test_split(X, y_d7, test_size=0.2, random_state=42)
            _, _, y_d30_train, y_d30_val = train_test_split(X, y_d30, test_size=0.2, random_state=42)

            params = {"objective": "reg:squarederror", "max_depth": 6, "learning_rate": 0.1, "random_state": 42}

            # D7 Model
            dtrain_d7 = xgb.DMatrix(X_train, label=y_d7_train)
            dval_d7 = xgb.DMatrix(X_val, label=y_d7_val)
            self.model_d7 = xgb.train(params, dtrain_d7, num_boost_round=100,
                                      evals=[(dval_d7, "val")], verbose_eval=False)
            y_d7_pred = self.model_d7.predict(dval_d7)
            self.metrics["d7"] = {
                "mae": round(mean_absolute_error(y_d7_val, y_d7_pred), 4),
                "mse": round(mean_squared_error(y_d7_val, y_d7_pred), 4),
                "rmse": round(np.sqrt(mean_squared_error(y_d7_val, y_d7_pred)), 4),
                "r2": round(r2_score(y_d7_val, y_d7_pred), 4),
            }

            # D30 Model
            dtrain_d30 = xgb.DMatrix(X_train, label=y_d30_train)
            dval_d30 = xgb.DMatrix(X_val, label=y_d30_val)
            self.model_d30 = xgb.train(params, dtrain_d30, num_boost_round=100,
                                       evals=[(dval_d30, "val")], verbose_eval=False)
            y_d30_pred = self.model_d30.predict(dval_d30)
            self.metrics["d30"] = {
                "mae": round(mean_absolute_error(y_d30_val, y_d30_pred), 4),
                "mse": round(mean_squared_error(y_d30_val, y_d30_pred), 4),
                "rmse": round(np.sqrt(mean_squared_error(y_d30_val, y_d30_pred)), 4),
                "r2": round(r2_score(y_d30_val, y_d30_pred), 4),
            }

            print(f"  D7 Metrics: MAE={self.metrics['d7']['mae']} R2={self.metrics['d7']['r2']}")
            print(f"  D30 Metrics: MAE={self.metrics['d30']['mae']} R2={self.metrics['d30']['r2']}")
        except ImportError:
            self.model_d7 = None
            self.model_d30 = None
            print("  xgboost not available, falling back to baseline")

    def _train_lightgbm(self, X: np.ndarray, y_d7: np.ndarray, y_d30: np.ndarray):
        """训练 LightGBM"""
        try:
            import lightgbm as lgb
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

            X_train, X_val, y_d7_train, y_d7_val = train_test_split(X, y_d7, test_size=0.2, random_state=42)
            _, _, y_d30_train, y_d30_val = train_test_split(X, y_d30, test_size=0.2, random_state=42)

            params = {"objective": "regression", "max_depth": 6, "learning_rate": 0.1, "random_state": 42}

            # D7 Model
            self.model_d7 = lgb.LGBMRegressor(**params)
            self.model_d7.fit(X_train, y_d7_train, eval_set=[(X_val, y_d7_val)],
                              eval_metric="mae", verbose=False)
            y_d7_pred = self.model_d7.predict(X_val)
            self.metrics["d7"] = {
                "mae": round(mean_absolute_error(y_d7_val, y_d7_pred), 4),
                "mse": round(mean_squared_error(y_d7_val, y_d7_pred), 4),
                "rmse": round(np.sqrt(mean_squared_error(y_d7_val, y_d7_pred)), 4),
                "r2": round(r2_score(y_d7_val, y_d7_pred), 4),
            }

            # D30 Model
            self.model_d30 = lgb.LGBMRegressor(**params)
            self.model_d30.fit(X_train, y_d30_train, eval_set=[(X_val, y_d30_val)],
                               eval_metric="mae", verbose=False)
            y_d30_pred = self.model_d30.predict(X_val)
            self.metrics["d30"] = {
                "mae": round(mean_absolute_error(y_d30_val, y_d30_pred), 4),
                "mse": round(mean_squared_error(y_d30_val, y_d30_pred), 4),
                "rmse": round(np.sqrt(mean_squared_error(y_d30_val, y_d30_pred)), 4),
                "r2": round(r2_score(y_d30_val, y_d30_pred), 4),
            }

            print(f"  D7 Metrics: MAE={self.metrics['d7']['mae']} R2={self.metrics['d7']['r2']}")
            print(f"  D30 Metrics: MAE={self.metrics['d30']['mae']} R2={self.metrics['d30']['r2']}")
        except ImportError:
            self.model_d7 = None
            self.model_d30 = None
            print("  lightgbm not available, falling back to baseline")

    def predict(self, dna: Dict) -> dict:
        """预测 ROI"""
        if not self.trained or self.model_d7 is None:
            return self._baseline_predict(dna)

        features = self.feature_builder.encode_dna(dna)
        features = features.reshape(1, -1)

        d7_pred = self.model_d7.predict(features)[0] if hasattr(self.model_d7, 'predict') else 0
        d30_pred = self.model_d30.predict(features)[0] if hasattr(self.model_d30, 'predict') else 0

        return {
            "d7_roi": round(max(-0.5, min(2.0, d7_pred)), 3),
            "d30_roi": round(max(-0.5, min(3.0, d30_pred)), 3),
            "model_type": self.model_type,
            "confidence": self._estimate_confidence(),
        }

    def _baseline_predict(self, dna: Dict) -> dict:
        """基线预测（基于规则）"""
        base_d7 = 0.3

        hook_bonus = {
            "transformation": 1.5,
            "challenge": 1.2,
            "urgency": 1.3,
        }
        base_d7 *= hook_bonus.get(dna.get("hook", ""), 1.0)

        subject_bonus = {
            "dragon": 1.4,
            "witch": 1.2,
        }
        base_d7 *= subject_bonus.get(dna.get("subject", ""), 1.0)

        gameplay_bonus = {
            "merge": 1.3,
            "upgrade": 1.2,
        }
        base_d7 *= gameplay_bonus.get(dna.get("gameplay", ""), 1.0)

        return {
            "d7_roi": round(base_d7, 3),
            "d30_roi": round(base_d7 * 1.8, 3),
            "model_type": "baseline",
            "confidence": 50.0,
        }

    def _estimate_confidence(self) -> float:
        """估算置信度"""
        if not self.metrics["d7"]:
            return 50.0

        r2_avg = (self.metrics["d7"].get("r2", 0) + self.metrics["d30"].get("r2", 0)) / 2
        return min(95, 50 + r2_avg * 50)

    def get_feature_importance(self) -> list:
        """获取特征重要性"""
        if not self.trained or self.model_d7 is None:
            return []

        try:
            importances = self.model_d7.feature_importances_
            return self.feature_builder.analyze_feature_importance(importances)
        except AttributeError:
            return []

    def save_model(self, output_path: Optional[Path] = None) -> Path:
        """保存模型"""
        if output_path is None:
            output_path = OUTPUT_DIR / "v38_1" / f"roi_{self.model_type}_model.json"

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
