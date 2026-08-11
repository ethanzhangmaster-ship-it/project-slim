"""E12.3 — Fatigue Predictor。

基于历史数据趋势预测创意未来的疲劳风险。

预测逻辑：
  1. 从 RealityHistoryPoint 序列中提取 CTR、ROAS、Frequency 趋势
  2. 计算 CTR 衰减率、ROAS 衰减率、频次压力
  3. 加权融合为 fatigue_score（0-1）
  4. 根据 fatigue_score 和趋势速度生成 RealityPrediction

与 E12.2 FatigueDetector 的区别：
  - E12.2: 诊断当前是否已疲劳（单快照）
  - E12.3: 预测未来是否会疲劳（多日趋势）
"""

from __future__ import annotations

from .models import (
    PredictionType,
    RealityHistoryPoint,
    RealityPrediction,
    RiskLevel,
)


# ── Constants ──────────────────────────────────────────────

# 权重配置
CTR_DECAY_WEIGHT = 0.4
ROAS_DECAY_WEIGHT = 0.4
FREQUENCY_PRESSURE_WEIGHT = 0.2

# 频次归一化：frequency_growth >= MAX_FREQUENCY_GROWTH 时 pressure = 1.0
MAX_FREQUENCY_GROWTH = 5.0

# 最小数据点数
MIN_DATA_POINTS = 2


class FatiguePredictor:
    """创意疲劳预测器。

    基于历史 CTR、ROAS、Frequency 趋势，预测未来 N 天
    创意是否会进入疲劳状态。

    Usage:
        >>> predictor = FatiguePredictor()
        >>> prediction = predictor.predict(history, horizon_days=7)
        >>> print(prediction.probability, prediction.risk_level)
    """

    def predict(
        self,
        history: list[RealityHistoryPoint],
        horizon_days: int = 7,
    ) -> RealityPrediction | None:
        """预测单个创意的疲劳风险。

        Args:
            history: 历史数据点（按时间排序）
            horizon_days: 预测时间范围

        Returns:
            RealityPrediction 或 None（数据不足时）
        """
        if len(history) < MIN_DATA_POINTS:
            return None

        # 按日期排序
        sorted_history = sorted(history, key=lambda p: p.date)

        # 提取首尾
        first = sorted_history[0]
        last = sorted_history[-1]

        # 计算天数跨度
        days_span = self._compute_days_span(sorted_history)

        # 计算各项衰减
        ctr_decay = self._compute_ctr_decay(first, last)
        roas_decay = self._compute_roas_decay(first, last)
        frequency_pressure = self._compute_frequency_pressure(first, last)

        # 加权融合
        fatigue_score = self._compute_fatigue_score(
            ctr_decay, roas_decay, frequency_pressure
        )

        # 考虑趋势速度：衰减越快，未来疲劳概率越高
        velocity = self._compute_velocity(ctr_decay, roas_decay, days_span)

        # 预测未来的 fatigue_score
        predicted_score = self._project_forward(fatigue_score, velocity, horizon_days)

        # 概率 = 预测的 fatigue_score（已归一化 0-1）
        probability = min(1.0, max(0.0, predicted_score))

        # 构建证据
        evidence = self._build_evidence(
            ctr_decay, roas_decay, frequency_pressure, fatigue_score, velocity, horizon_days
        )

        # 确定风险等级
        risk_level = self._determine_risk_level(probability)

        # 推荐行动
        action = self._recommend_action(ctr_decay, roas_decay, probability)

        return RealityPrediction(
            prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
            target_id=last.creative_id,
            current_value=fatigue_score,
            predicted_value=predicted_score,
            horizon_days=horizon_days,
            probability=probability,
            risk_level=risk_level,
            evidence=evidence,
            recommended_action=action,
            metadata={
                "ctr_decay": round(ctr_decay, 4),
                "roas_decay": round(roas_decay, 4),
                "frequency_pressure": round(frequency_pressure, 4),
                "velocity": round(velocity, 4),
                "initial_ctr": round(first.ctr, 4),
                "current_ctr": round(last.ctr, 4),
                "initial_roas": round(first.roas, 4),
                "current_roas": round(last.roas, 4),
                "initial_frequency": round(first.frequency, 2),
                "current_frequency": round(last.frequency, 2),
                "days_span": days_span,
                "data_points": len(history),
            },
        )

    def predict_batch(
        self,
        history_grouped: dict[str, list[RealityHistoryPoint]],
        horizon_days: int = 7,
    ) -> list[RealityPrediction]:
        """批量预测多个创意的疲劳风险。

        Args:
            history_grouped: {creative_id: [history_points]} 映射
            horizon_days: 预测时间范围

        Returns:
            预测结果列表（按 probability 降序）
        """
        predictions: list[RealityPrediction] = []
        for creative_id, points in history_grouped.items():
            pred = self.predict(points, horizon_days)
            if pred is not None:
                predictions.append(pred)
        return sorted(predictions, key=lambda p: p.probability, reverse=True)

    # ── Private methods ────────────────────────────────────

    @staticmethod
    def _compute_days_span(history: list[RealityHistoryPoint]) -> int:
        """计算历史数据的天数跨度。"""
        if len(history) < 2:
            return 0
        # 简单估算：数据点数量作为天数代理
        # 实际使用中每个 point 代表一天
        return len(history) - 1

    @staticmethod
    def _compute_ctr_decay(
        first: RealityHistoryPoint, last: RealityHistoryPoint
    ) -> float:
        """计算 CTR 衰减率。

        ctr_decay = (initial_ctr - current_ctr) / initial_ctr

        正值表示 CTR 下降，负值表示上升。
        """
        if first.ctr <= 0:
            return 0.0
        return max(0.0, (first.ctr - last.ctr) / first.ctr)

    @staticmethod
    def _compute_roas_decay(
        first: RealityHistoryPoint, last: RealityHistoryPoint
    ) -> float:
        """计算 ROAS 衰减率。

        roas_decay = (initial_roas - current_roas) / initial_roas

        正值表示 ROAS 下降，负值表示上升。
        """
        if first.roas <= 0:
            return 0.0
        return max(0.0, (first.roas - last.roas) / first.roas)

    @staticmethod
    def _compute_frequency_pressure(
        first: RealityHistoryPoint, last: RealityHistoryPoint
    ) -> float:
        """计算频次压力。

        frequency_growth = current_frequency / initial_frequency
        归一化到 0-1：growth / MAX_FREQUENCY_GROWTH
        """
        if first.frequency <= 0:
            return 0.0
        growth = last.frequency / first.frequency
        return min(1.0, growth / MAX_FREQUENCY_GROWTH)

    @staticmethod
    def _compute_fatigue_score(
        ctr_decay: float,
        roas_decay: float,
        frequency_pressure: float,
    ) -> float:
        """加权融合疲劳评分。

        fatigue_score = ctr_decay × 0.4 + roas_decay × 0.4 + frequency_pressure × 0.2
        """
        score = (
            ctr_decay * CTR_DECAY_WEIGHT
            + roas_decay * ROAS_DECAY_WEIGHT
            + frequency_pressure * FREQUENCY_PRESSURE_WEIGHT
        )
        return min(1.0, max(0.0, score))

    @staticmethod
    def _compute_velocity(
        ctr_decay: float,
        roas_decay: float,
        days_span: int,
    ) -> float:
        """计算衰减速度（每天变化率）。

        速度越大，表示下降趋势越陡峭。
        """
        if days_span <= 0:
            return 0.0
        avg_decay = (ctr_decay + roas_decay) / 2.0
        return avg_decay / days_span

    @staticmethod
    def _project_forward(
        current_score: float,
        velocity: float,
        horizon_days: int,
    ) -> float:
        """线性外推未来的 fatigue_score。

        predicted = current + velocity × horizon_days
        """
        projected = current_score + velocity * horizon_days
        return min(1.0, max(0.0, projected))

    def _build_evidence(
        self,
        ctr_decay: float,
        roas_decay: float,
        frequency_pressure: float,
        fatigue_score: float,
        velocity: float,
        horizon_days: int,
    ) -> list[str]:
        """构建人类可读的证据列表。"""
        evidence: list[str] = []

        if ctr_decay > 0.1:
            evidence.append(f"CTR decreased {ctr_decay:.0%} over observation period")
        if roas_decay > 0.1:
            evidence.append(f"ROAS decreased {roas_decay:.0%} over observation period")
        if frequency_pressure > 0.3:
            evidence.append(f"Frequency pressure high ({frequency_pressure:.0%})")
        if velocity > 0.01:
            evidence.append(
                f"Fatigue accelerating at {velocity:.3f}/day, "
                f"projected {fatigue_score:.2f} → {fatigue_score + velocity * horizon_days:.2f} "
                f"in {horizon_days} days"
            )
        if fatigue_score > 0.6:
            evidence.append(f"Current fatigue score {fatigue_score:.2f} already elevated")

        if not evidence:
            evidence.append("No significant fatigue signals detected")

        return evidence

    @staticmethod
    def _determine_risk_level(probability: float) -> RiskLevel:
        """根据概率确定风险等级。"""
        if probability >= 0.9:
            return RiskLevel.CRITICAL
        elif probability >= 0.75:
            return RiskLevel.HIGH
        elif probability >= 0.5:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    @staticmethod
    def _recommend_action(
        ctr_decay: float,
        roas_decay: float,
        probability: float,
    ) -> str:
        """根据衰减模式推荐行动。"""
        if probability < 0.5:
            return "MONITOR"
        if ctr_decay > roas_decay:
            return "MUTATE_HOOK"
        elif roas_decay > 0.3:
            return "MUTATE_MONETIZATION"
        else:
            return "MUTATE_CREATIVE"

    def __repr__(self) -> str:
        return "FatiguePredictor()"