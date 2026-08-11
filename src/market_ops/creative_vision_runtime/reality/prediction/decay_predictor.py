"""E12.3 Phase 2 — Decay Velocity Predictor。

预测各指标（CTR/ROAS/CVR/CPI）的衰减速度，
精确量化创意退化趋势。

与 Phase 1 的区别：
  - Phase 1: 整体疲劳评分（fatigue_score）
  - Phase 2: 逐指标衰减速度（CTR -0.05%/day, ROAS -0.03%/day）

支持：
  - 多指标独立衰减预测
  - 加速衰减检测
  - 基于衰减速度的精确 mutation timing
"""

from __future__ import annotations

from .models import (
    DecayPrediction,
    RealityHistoryPoint,
)


# ── Constants ──────────────────────────────────────────────

SUPPORTED_METRICS = ["ctr", "roas", "cvr", "cpi"]

# 加速检测窗口：对比最近 N 天 vs 全部历史
ACCELERATION_WINDOW = 3

# 加速阈值：最近速度 > 全部速度 × 1.5
ACCELERATION_THRESHOLD = 1.5

MIN_DATA_POINTS = 3


class DecayPredictor:
    """多指标衰减速度预测器。

    对每个指标独立计算衰减速度，检测加速衰减，
    生成精确的 DecayPrediction。

    Usage:
        >>> predictor = DecayPredictor()
        >>> decay = predictor.predict(history, metric="ctr", horizon_days=7)
        >>> print(decay.velocity, decay.predicted_value)
    """

    def predict(
        self,
        history: list[RealityHistoryPoint],
        metric: str = "ctr",
        horizon_days: int = 7,
    ) -> DecayPrediction | None:
        """预测单个指标的衰减速度。

        Args:
            history: 历史数据点
            metric: 指标名称（ctr/roas/cvr/cpi）
            horizon_days: 预测时间范围

        Returns:
            DecayPrediction 或 None
        """
        if len(history) < MIN_DATA_POINTS:
            return None

        if metric not in SUPPORTED_METRICS:
            return None

        sorted_history = sorted(history, key=lambda p: p.date)
        creative_id = sorted_history[-1].creative_id

        # 提取指标序列
        values = [getattr(p, metric) for p in sorted_history]

        # 计算线性回归斜率
        days = list(range(len(sorted_history)))
        slope, r_squared = self._linear_slope(days, values)

        current_value = values[-1]
        future_index = len(sorted_history) - 1 + horizon_days
        predicted_value = current_value + slope * horizon_days
        predicted_value = max(0.0, predicted_value)

        # 检测是否加速衰减
        is_accelerating = self._detect_acceleration(values, slope)

        # 置信度
        confidence = self._compute_confidence(
            slope, r_squared, len(history), sum(p.installs for p in history)
        )

        # 证据
        evidence = self._build_evidence(
            metric, current_value, predicted_value, slope, horizon_days, is_accelerating
        )

        return DecayPrediction(
            creative_id=creative_id,
            metric=metric,
            velocity=slope,
            current_value=current_value,
            predicted_value=predicted_value,
            horizon_days=horizon_days,
            confidence=confidence,
            is_accelerating=is_accelerating,
            evidence=evidence,
        )

    def predict_all_metrics(
        self,
        history: list[RealityHistoryPoint],
        horizon_days: int = 7,
    ) -> list[DecayPrediction]:
        """预测所有支持指标的衰减速度。

        Args:
            history: 历史数据点
            horizon_days: 预测时间范围

        Returns:
            所有指标的 DecayPrediction 列表
        """
        predictions: list[DecayPrediction] = []
        for metric in SUPPORTED_METRICS:
            pred = self.predict(history, metric, horizon_days)
            if pred is not None:
                predictions.append(pred)
        return sorted(predictions, key=lambda p: p.velocity)  # 最严重的先

    def predict_batch(
        self,
        history_grouped: dict[str, list[RealityHistoryPoint]],
        metric: str = "ctr",
        horizon_days: int = 7,
    ) -> list[DecayPrediction]:
        """批量预测多个创意的衰减速度。"""
        predictions: list[DecayPrediction] = []
        for creative_id, points in history_grouped.items():
            pred = self.predict(points, metric, horizon_days)
            if pred is not None:
                predictions.append(pred)
        return sorted(predictions, key=lambda p: p.velocity)

    def predict_all_metrics_batch(
        self,
        history_grouped: dict[str, list[RealityHistoryPoint]],
        horizon_days: int = 7,
    ) -> dict[str, list[DecayPrediction]]:
        """批量预测所有指标。"""
        result: dict[str, list[DecayPrediction]] = {}
        for creative_id, points in history_grouped.items():
            preds = self.predict_all_metrics(points, horizon_days)
            if preds:
                result[creative_id] = preds
        return result

    # ── Private methods ────────────────────────────────────

    @staticmethod
    def _linear_slope(
        x: list[int], y: list[float]
    ) -> tuple[float, float]:
        """最小二乘线性回归斜率。

        Returns:
            (slope, r_squared)
        """
        n = len(x)
        if n < 2:
            return 0.0, 0.0

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        cov_xy = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        var_x = sum((xi - mean_x) ** 2 for xi in x)

        if var_x == 0:
            return 0.0, 1.0

        slope = cov_xy / var_x
        intercept = mean_y - slope * mean_x

        # R²
        ss_res = sum((yi - (intercept + slope * xi)) ** 2 for xi, yi in zip(x, y))
        ss_tot = sum((yi - mean_y) ** 2 for yi in y)

        if ss_tot == 0:
            r_squared = 1.0
        else:
            r_squared = 1.0 - (ss_res / ss_tot)
            r_squared = max(0.0, min(1.0, r_squared))

        return slope, r_squared

    @staticmethod
    def _detect_acceleration(
        values: list[float],
        overall_slope: float,
    ) -> bool:
        """检测是否加速衰减。

        对比最近 N 天的速度 vs 全部历史速度。
        """
        if len(values) < ACCELERATION_WINDOW + 2:
            return False

        recent_values = values[-ACCELERATION_WINDOW - 1:]
        recent_days = list(range(len(recent_values)))
        recent_slope, _ = DecayPredictor._linear_slope(recent_days, recent_values)

        # 必须都是负值（都在下降）
        if overall_slope >= 0 or recent_slope >= 0:
            return False

        # 最近速度比整体速度快 1.5 倍以上 = 加速
        return abs(recent_slope) > abs(overall_slope) * ACCELERATION_THRESHOLD

    @staticmethod
    def _compute_confidence(
        slope: float,
        r_squared: float,
        data_points: int,
        total_installs: int,
    ) -> float:
        """计算衰减预测置信度。"""
        # 趋势强度
        if abs(slope) > 0.005:
            trend_strength = 1.0
        elif abs(slope) > 0.002:
            trend_strength = 0.8
        elif abs(slope) > 0.001:
            trend_strength = 0.6
        else:
            trend_strength = 0.3

        # 数据量
        if data_points >= 14 and total_installs >= 5000:
            data_volume = 1.0
        elif data_points >= 7 and total_installs >= 1000:
            data_volume = 0.8
        elif data_points >= 3 and total_installs >= 100:
            data_volume = 0.5
        else:
            data_volume = 0.3

        # 趋势一致性
        consistency = r_squared

        return trend_strength * 0.35 + data_volume * 0.35 + consistency * 0.30

    @staticmethod
    def _build_evidence(
        metric: str,
        current_value: float,
        predicted_value: float,
        slope: float,
        horizon_days: int,
        is_accelerating: bool,
    ) -> list[str]:
        """构建证据。"""
        evidence: list[str] = []

        direction = "declining" if slope < 0 else "improving" if slope > 0 else "stable"
        evidence.append(
            f"{metric.upper()} {direction} at {slope:.6f}/day"
        )

        if slope != 0 and current_value > 0:
            change_pct = (predicted_value - current_value) / current_value
            evidence.append(
                f"Predicted {metric.upper()} in {horizon_days} days: "
                f"{current_value:.4f} → {predicted_value:.4f} ({change_pct:+.1%})"
            )

        if is_accelerating:
            evidence.append(
                f"{metric.upper()} decay is accelerating — "
                f"recent velocity > {ACCELERATION_THRESHOLD}x overall"
            )

        return evidence

    def __repr__(self) -> str:
        return "DecayPredictor()"