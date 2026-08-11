"""Performance Regressor — 视觉特征 → ROAS/CTR/CVR 建模引擎。

支持按优先级:
  1. Linear Regression (必须有)
  2. XGBoost/LightGBM (如果可用)
  3. Rank-based model (必须有)

输出: Feature Importance Ranking (TOP DRIVERS + NEGATIVE DRIVERS)
"""
from __future__ import annotations
import json, warnings
from pathlib import Path
from typing import List, Optional, Tuple, Callable
import numpy as np

warnings.filterwarnings("ignore")


class PerformanceRegressor:
    """Train regression/ranking models on visual features → performance labels."""

    def __init__(self):
        self.models = {}          # target → trained model
        self.feature_names = []
        self.feature_importance = {}  # target → {name: importance}
        self.r2_scores = {}
        self._is_fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray,
            feature_names: List[str], targets: List[str] = None):
        """Fit regression models for each target (ROAS, CTR, CVR).

        Priority:
          1. Linear regression (always available)
          2. XGBoost (if installed)
          3. Rank model (pairwise comparison)

        Args:
            X: (N, D) feature matrix
            y: (N, T) label matrix
            feature_names: list of D feature names
            targets: list of T target names (default: ROAS, CTR, CVR)
        """
        if targets is None:
            targets = ["roas", "ctr", "cvr"]

        self.feature_names = feature_names
        n_features = X.shape[1]

        for t_idx, t_name in enumerate(targets):
            y_target = y[:, t_idx]

            # ── Always train Linear Regression as baseline ──
            lr = self._train_linear(X, y_target)
            lr_importance = self._linear_importance(lr, feature_names)
            self.models[f"{t_name}_linear"] = lr
            self.feature_importance[f"{t_name}_linear"] = lr_importance

            # ── Try XGBoost ──
            try:
                import xgboost as xgb
                xgb_model = xgb.XGBRegressor(
                    n_estimators=100, max_depth=4,
                    learning_rate=0.1, random_state=42,
                    verbosity=0,
                )
                xgb_model.fit(X, y_target)
                imp = dict(zip(feature_names, xgb_model.feature_importances_))
                self.models[f"{t_name}_xgb"] = xgb_model
                self.feature_importance[f"{t_name}_xgb"] = imp
            except ImportError:
                pass

            # ── Train rank model (pairwise: margin-based) ──
            rank_imp = self._train_ranking(X, y_target, feature_names)
            self.feature_importance[f"{t_name}_rank"] = rank_imp

            # ── Compute R² ──
            try:
                from sklearn.metrics import r2_score
                pred_lr = lr.predict(X)
                self.r2_scores[f"{t_name}_linear"] = float(r2_score(y_target, pred_lr))
            except:
                pass

        self._is_fitted = True

    def predict(self, X: np.ndarray, target: str = "roas",
                method: str = "linear") -> np.ndarray:
        """Predict performance for new feature vectors."""
        key = f"{target}_{method}"
        if key not in self.models:
            # Fallback to linear
            key = f"{target}_linear"
        model = self.models.get(key)
        if model is None:
            return np.zeros(X.shape[0])
        return model.predict(X)

    def get_impact_report(self, target: str = "roas") -> dict:
        """Get structured feature → performance impact report.

        Returns:
            {
                "target": "roas",
                "top_drivers": [(name, impact), ...],
                "negative_drivers": [(name, impact), ...],
                "method": "linear | xgb | rank"
            }
        """
        # Prefer XGBoost, fallback to linear
        for method in ["xgb", "linear", "rank"]:
            key = f"{target}_{method}"
            if key in self.feature_importance:
                imp = self.feature_importance[key]
                break
        else:
            return {"target": target, "error": "no model trained"}

        # Separate positive and negative
        sorted_imp = sorted(imp.items(), key=lambda x: -abs(x[1]))
        pos = [(n, round(v, 4)) for n, v in sorted_imp if v > 0]
        neg = [(n, round(v, 4)) for n, v in sorted_imp if v < 0]

        return {
            "target": target,
            "method": method,
            "r2": self.r2_scores.get(f"{target}_{method}", None),
            "top_drivers": pos[:8],
            "negative_drivers": neg[:5],
        }

    def export_report(self) -> str:
        """Generate human-readable feature importance report."""
        lines = []
        lines.append("📊 Feature → Performance Impact Report")
        lines.append("=" * 55)
        lines.append("")

        for target in ["roas", "ctr", "cvr"]:
            report = self.get_impact_report(target)
            if "error" in report:
                continue

            lines.append(f"🎯 {target.upper()} DRIVERS:")
            lines.append(f"   R² = {report.get('r2', 'N/A')}")
            if report["top_drivers"]:
                lines.append("   TOP POSITIVE:")
                for name, val in report["top_drivers"][:5]:
                    lines.append(f"     +{val:+.4f}  {name}")
            if report["negative_drivers"]:
                lines.append("   NEGATIVE:")
                for name, val in report["negative_drivers"][:5]:
                    lines.append(f"     {val:+.4f}  {name}")
            lines.append("")

        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════
    # Internal
    # ═══════════════════════════════════════════════════════════

    def _train_linear(self, X: np.ndarray, y: np.ndarray):
        """Fit linear regression with pure numpy (scikit-learn optional)."""
        n_features = X.shape[1]
        if n_features == 0:
            return None

        try:
            from sklearn.linear_model import Ridge
            lr = Ridge(alpha=1.0, random_state=42)
            lr.fit(X, y)
            return lr
        except ImportError:
            pass

        # Pure numpy OLS with simple L2 regularization
        # (X^T X + λI)^{-1} X^T y
        lam = 1.0
        XtX = X.T @ X + lam * np.eye(n_features)
        Xty = X.T @ y
        try:
            coef = np.linalg.solve(XtX, Xty)
        except np.linalg.LinAlgError:
            coef = np.zeros(n_features)
        return _NumpyLinearModel(coef)

    def _linear_importance(self, model, feature_names: List[str]) -> dict:
        if model is None:
            return {n: 0.0 for n in feature_names}
        importances = model.coef_.flatten()
        return dict(zip(feature_names, [float(v) for v in importances]))

    def _train_ranking(self, X: np.ndarray, y: np.ndarray,
                       feature_names: List[str]) -> dict:
        """Train a simple pairwise ranking model.

        Uses difference-based ranking: for each pair (high vs low),
        learn which features explain the difference.
        """
        n = X.shape[0]
        if n < 10:
            return {n: 0.0 for n in feature_names}

        # Create pairwise comparisons: high vs low ROAS
        median = np.median(y)
        high_idx = np.where(y >= median)[0]
        low_idx = np.where(y < median)[0]

        if len(high_idx) < 2 or len(low_idx) < 2:
            return {n: 0.0 for n in feature_names}

        # Compute mean feature difference between high and low groups
        high_mean = X[high_idx].mean(axis=0)
        low_mean = X[low_idx].mean(axis=0)
        diff = high_mean - low_mean

        # Normalize by pool standard deviation
        pool_std = np.sqrt(
            (X[high_idx].var(axis=0) + X[low_idx].var(axis=0)) / 2
        )
        pool_std = np.where(pool_std > 1e-8, pool_std, 1.0)
        effect_size = diff / pool_std

        return dict(zip(feature_names, [float(v) for v in effect_size]))


def train_test_split(X: np.ndarray, y: np.ndarray, test_ratio: float = 0.2):
    """Simple train/test split."""
    n = X.shape[0]
    n_test = max(1, int(n * test_ratio))
    indices = np.random.RandomState(42).permutation(n)
    test_idx = indices[:n_test]
    train_idx = indices[n_test:]
    return X[train_idx], X[test_idx], y[train_idx], y[test_idx]


class _NumpyLinearModel:
    """Minimal linear model wrapper for pure numpy coefficients."""
    def __init__(self, coef_):
        self.coef_ = coef_
    def predict(self, X):
        return X @ self.coef_
