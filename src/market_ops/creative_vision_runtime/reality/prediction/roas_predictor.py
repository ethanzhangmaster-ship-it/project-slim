"""E12.3 — ROAS Predictor。

基于历史 ROAS 数据，使用线性趋势回归预测未来 ROAS。

预测逻辑：
  1. 从 RealityHistoryPoint 序列中提取 ROAS 时间序列
  2. 计算线性回归斜率（最小二乘法）
  3. 外推未来 N 天的 ROAS 值
  4. 根据趋势方向和强度生成 RealityPrediction

与 E12.2 PerformanceAnalyzer 的区别：
  - E12.2: 诊断当前 ROAS 是否下降（单快照对比）
  - E12.3: 预测未来 ROAS 会变成多少（多日趋势外推）
"""

from __future__ import annotations

from .models import (
    PredictionType,
    RealityHistoryPoint,
    RealityPrediction,
    RiskLevel,
)


# ── Constants ──────────────────────────────────────────────

MIN_DATA_POINTS = 2
MIN_DATA_POINTS_RELIABLE = 5  # 至少 5 个点才认为可靠

# 趋势阈值
SLOPE_FLAT_THRESHOLD = 0.005  # |slope| < 此值视为平稳
SIGNIFICANT_DECLINE = -0.01  # slope < 此值视为显著下降
SIGNIFICANT_GROWTH = 0.01    # slope > 此值视为显著增长


class ROASPredictor:
    """ROAS 趋势预测器。

    使用线性回归分析历史 ROAS 趋势，预测未来 D7/D14/D30 的 ROAS。

    Usage:
        >>> predictor = ROASPredictor()
        >>> prediction = predictor.predict(history, horizon_days=7)
        >>> print(prediction.predicted_value, prediction.risk_level)
    """

    def predict(
        self,
        history: list[RealityHistoryPoint],
        horizon_days: int = 7,
    ) -> RealityPrediction | None:
        """预测未来 ROAS。

        Args:
            history: 历史数据点（按时间排序）
            horizon_days: 预测时间范围（7/14/30）

        Returns:
            RealityPrediction 或 None（数据不足时）
        """
        if len(history) < MIN_DATA_POINTS:
            return None

        sorted_history = sorted(history, key=lambda p: p.date)

        # 提取 ROAS 序列和对应的时间索引
        roas_values = [p.roas for p in sorted_history]
        days = list(range(len(sorted_history)))

        # 线性回归
        slope, intercept, r_squared = self._linear_regression(days, roas_values)

        # 当前 ROAS（最后一个数据点）
        current_roas = roas_values[-1]

        # 预测未来 ROAS
        future_index = len(sorted_history) - 1 + horizon_days
        predicted_roas = intercept + slope * future_index
        predicted_roas = max(0.0, predicted_roas)  # ROAS 不能为负

        # 确定预测类型
        prediction_type = self._determine_type(slope)

        # 计算概率（基于 r_squared 和趋势强度）
        probability = self._compute_probability(slope, r_squared, len(history))

        # 确定风险等级
        risk_level = self._determine_risk_level(slope, predicted_roas, current_roas)

        # 证据
        evidence = self._build_evidence(
            slope, current_roas, predicted_roas, horizon_days, r_squared
        )

        # 推荐行动
        action = self._recommend_action(prediction_type, slope, predicted_roas)

        return RealityPrediction(
            prediction_type=prediction_type,
            target_id=sorted_history[-1].creative_id,
            current_value=current_roas,
            predicted_value=predicted_roas,
            horizon_days=horizon_days,
            probability=probability,
            risk_level=risk_level,
            evidence=evidence,
            recommended_action=action,
            metadata={
                "slope": round(slope, 6),
                "intercept": round(intercept, 4),
                "r_squared": round(r_squared, 4),
                "data_points": len(history),
                "slope_per_day": round(slope, 6),
            },
        )

    def predict_batch(
        self,
        history_grouped: dict[str, list[RealityHistoryPoint]],
        horizon_days: int = 7,
    ) -> list[RealityPrediction]:
        """批量预测多个创意的 ROAS 趋势。

        Args:
            history_grouped: {creative_id: [history_points]} 映射
            horizon_days: 预测时间范围

        Returns:
            预测结果列表（按 risk 降序）
        """
        predictions: list[RealityPrediction] = []
        for creative_id, points in history_grouped.items():
            pred = self.predict(points, horizon_days)
            if pred is not None:
                predictions.append(pred)
        return sorted(
            predictions,
            key=lambda p: (p.risk_level == RiskLevel.CRITICAL,
                           p.risk_level == RiskLevel.HIGH,
                           p.probability),
            reverse=True,
        )

    # ── Private methods ────────────────────────────────────

    @staticmethod
    def _linear_regression(
        x: list[int],
        y: list[float],
    ) -> tuple[float, float, float]:
        """最小二乘线性回归。

        Args:
            x: 自变量（时间索引）
            y: 因变量（ROAS 值）

        Returns:
            (slope, intercept, r_squared)
        """
        n = len(x)
        if n < 2:
            return 0.0, y[0] if y else 0.0, 0.0

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        # 协方差和方差
        cov_xy = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        var_x = sum((xi - mean_x) ** 2 for xi in x)

        if var_x == 0:
            return 0.0, mean_y, 0.0

        slope = cov_xy / var_x
        intercept = mean_y - slope * mean_x

        # R² 计算
        ss_res = sum((yi - (intercept + slope * xi)) ** 2 for xi, yi in zip(x, y))
        ss_tot = sum((yi - mean_y) ** 2 for yi in y)

        if ss_tot == 0:
            r_squared = 1.0
        else:
            r_squared = 1.0 - (ss_res / ss_tot)
            r_squared = max(0.0, min(1.0, r_squared))

        return slope, intercept, r_squared

    @staticmethod
    def _determine_type(slope: float) -> PredictionType:
        """根据斜率确定预测类型。"""
        if slope > SIGNIFICANT_GROWTH:
            return PredictionType.SCALE_OPPORTUNITY
        elif slope < SIGNIFICANT_DECLINE:
            return PredictionType.ROAS_DECAY_RISK
        else:
            return PredictionType.ROAS_DECAY_RISK  # 默认关注衰减风险

    @staticmethod
    def _compute_probability(
        slope: float,
        r_squared: float,
        data_points: int,
    ) -> float:
        """计算预测概率。

        概率 = 趋势强度 × 数据可靠性 × 样本量因子

        - 趋势强度：基于 slope 的绝对值
        - 数据可靠性：基于 R²
        - 样本量因子：数据点越多越可靠
        """
        # 趋势强度（slope 越大，趋势越明显）
        if slope > 0:
            trend_strength = min(1.0, abs(slope) / 0.05)  # 5% daily change → 1.0
        else:
            trend_strength = min(1.0, abs(slope) / 0.05)

        # 数据可靠性（R² 越高越好）
        reliability = r_squared

        # 样本量因子（5 points = 0.7, 10+ = 1.0）
        if data_points >= 10:
            sample_factor = 1.0
        elif data_points >= MIN_DATA_POINTS_RELIABLE:
            sample_factor = 0.7 + 0.06 * (data_points - MIN_DATA_POINTS_RELIABLE)
        else:
            sample_factor = 0.3 + 0.13 * (data_points - 2)

        probability = trend_strength * 0.5 + reliability * 0.3 + sample_factor * 0.2
        return min(1.0, max(0.0, probability))

    @staticmethod
    def _determine_risk_level(
        slope: float,
        predicted_roas: float,
        current_roas: float,
    ) -> RiskLevel:
        """根据斜率和预测值确定风险等级。"""
        if slope < -0.02:
            return RiskLevel.CRITICAL
        elif slope < -0.01:
            return RiskLevel.HIGH
        elif slope < -0.005:
            return RiskLevel.MEDIUM
        elif predicted_roas < current_roas * 0.5:
            return RiskLevel.HIGH
        else:
            return RiskLevel.LOW

    @staticmethod
    def _build_evidence(
        slope: float,
        current_roas: float,
        predicted_roas: float,
        horizon_days: int,
        r_squared: float,
    ) -> list[str]:
        """构建证据列表。"""
        evidence: list[str] = []

        change_pct = (predicted_roas - current_roas) / current_roas if current_roas > 0 else 0

        if slope < -0.005:
            evidence.append(
                f"ROAS declining at {slope:.4f}/day "
                f"(R²={r_squared:.2f})"
            )
        elif slope > 0.005:
            evidence.append(
                f"ROAS improving at {slope:.4f}/day "
                f"(R²={r_squared:.2f})"
            )
        else:
            evidence.append(f"ROAS stable (slope={slope:.4f}, R²={r_squared:.2f})")

        evidence.append(
            f"Predicted ROAS in {horizon_days} days: "
            f"{current_roas:.2f} → {predicted_roas:.2f} "
            f"({change_pct:+.0%})"
        )

        if r_squared < 0.5:
            evidence.append(f"Low data consistency (R²={r_squared:.2f})")

        return evidence

    @staticmethod
    def _recommend_action(
        prediction_type: PredictionType,
        slope: float,
        predicted_roas: float,
    ) -> str:
        """根据预测类型和趋势推荐行动。"""
        if prediction_type == PredictionType.SCALE_OPPORTUNITY:
            return "INCREASE_BUDGET"
        elif slope < -0.02:
            return "PAUSE_AND_MUTATE"
        elif slope < -0.01:
            return "MUTATE_CREATIVE"
        elif predicted_roas < 0.5:
            return "EVALUATE_AND_MUTATE"
        else:
            return "MONITOR"

    def __repr__(self) -> str:
        return "ROASPredictor()"