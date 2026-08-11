"""E12.3 Phase 2 — Lifecycle Predictor。

预测创意生命周期阶段及过渡时间。

7 阶段模型：
  Launch → Learning → Peak → Stable → FatigueWarning → Fatigued → Dead

检测逻辑：
  1. 根据 CTR/ROAS/Frequency 趋势判断当前阶段
  2. 根据衰减速度预测过渡到下一个阶段的天数
  3. 输出 LifecyclePrediction 包含阶段 + 时间 + 置信度
"""

from __future__ import annotations

import math

from .models import (
    CreativeLifecycleStage,
    LIFECYCLE_SEVERITY,
    LifecyclePrediction,
    RealityHistoryPoint,
    VALID_LIFECYCLE_TRANSITIONS,
)


# ── Stage detection thresholds ─────────────────────────────

# 最小数据点用于阶段判断
MIN_DATA_POINTS = 2

# 启动期：数据少于 3 天
LAUNCH_MAX_DAYS = 3

# 学习期：CTR 波动 > 20%
LEARNING_CTR_VOLATILITY = 0.20

# 峰值期：CTR 在历史最高 10% 以内
PEAK_CTR_RATIO = 0.90

# 疲劳预警：CTR 相对峰值下降 > 15%
FATIGUE_WARNING_CTR_DROP = 0.15

# 已疲劳：CTR 相对峰值下降 > 30% 或 ROAS 下降 > 35%
FATIGUED_CTR_DROP = 0.30
FATIGUED_ROAS_DROP = 0.35

# 死亡：ROAS < 0.3
DEAD_ROAS_THRESHOLD = 0.3


class LifecyclePredictor:
    """创意生命周期预测器。

    基于历史 CTR/ROAS 趋势判断创意当前处于哪个生命周期阶段，
    并预测过渡到下一个阶段的时间。

    Usage:
        >>> predictor = LifecyclePredictor()
        >>> pred = predictor.predict(history)
        >>> print(pred.current_stage, pred.days_to_transition)
    """

    def predict(
        self,
        history: list[RealityHistoryPoint],
    ) -> LifecyclePrediction | None:
        """预测单个创意的生命周期。

        Args:
            history: 历史数据点（按时间排序）

        Returns:
            LifecyclePrediction 或 None（数据不足时）
        """
        if len(history) < MIN_DATA_POINTS:
            return None

        sorted_history = sorted(history, key=lambda p: p.date)
        creative_id = sorted_history[-1].creative_id

        # 1. 检测当前阶段
        current_stage, stage_scores = self._detect_stage(sorted_history)

        # 2. 预测下一个阶段
        predicted_stage = self._predict_next_stage(current_stage, sorted_history)

        # 3. 计算过渡天数
        days_to_transition = self._estimate_days_to_transition(
            current_stage, predicted_stage, sorted_history
        )

        # 4. 计算置信度
        confidence = self._compute_confidence(
            sorted_history, current_stage, predicted_stage
        )

        # 5. 构建证据
        evidence = self._build_evidence(
            sorted_history, current_stage, predicted_stage, days_to_transition
        )

        # 6. 推荐行动
        action = self._recommend_action(current_stage, predicted_stage)

        return LifecyclePrediction(
            creative_id=creative_id,
            current_stage=current_stage,
            predicted_stage=predicted_stage,
            days_to_transition=days_to_transition,
            confidence=confidence,
            stage_scores=stage_scores,
            evidence=evidence,
            recommended_action=action,
        )

    def predict_batch(
        self,
        history_grouped: dict[str, list[RealityHistoryPoint]],
    ) -> list[LifecyclePrediction]:
        """批量预测多个创意的生命周期。"""
        predictions: list[LifecyclePrediction] = []
        for creative_id, points in history_grouped.items():
            pred = self.predict(points)
            if pred is not None:
                predictions.append(pred)
        return sorted(
            predictions,
            key=lambda p: (
                LIFECYCLE_SEVERITY.get(p.predicted_stage, 0),
                p.days_to_transition if p.days_to_transition > 0 else 999,
            ),
            reverse=True,
        )

    # ── Stage Detection ────────────────────────────────────

    def _detect_stage(
        self, history: list[RealityHistoryPoint]
    ) -> tuple[CreativeLifecycleStage, dict[str, float]]:
        """检测当前生命周期阶段。

        使用多指标评分，选择得分最高的阶段。
        """
        days = len(history)
        first = history[0]
        last = history[-1]

        # 提取指标序列
        ctr_values = [p.ctr for p in history]
        roas_values = [p.roas for p in history]
        freq_values = [p.frequency for p in history]

        max_ctr = max(ctr_values) if ctr_values else 0
        max_roas = max(roas_values) if roas_values else 0
        avg_ctr = sum(ctr_values) / len(ctr_values) if ctr_values else 0
        avg_roas = sum(roas_values) / len(roas_values) if roas_values else 0

        scores: dict[str, float] = {}

        # Launch: 数据少于 3 天
        scores["launch"] = 1.0 if days <= LAUNCH_MAX_DAYS else 0.0

        # Learning: CTR 波动大，但不是单调下降
        ctr_volatility = self._compute_volatility(ctr_values)
        ctr_is_monotonic_decline = self._is_monotonic_decline(ctr_values)
        if ctr_is_monotonic_decline:
            scores["learning"] = 0.0  # 单调下降不算是学习期
        else:
            scores["learning"] = min(1.0, ctr_volatility / LEARNING_CTR_VOLATILITY)

        # Peak: CTR 接近历史最高
        if max_ctr > 0:
            scores["peak"] = min(1.0, last.ctr / max_ctr) if last.ctr >= max_ctr * PEAK_CTR_RATIO else 0.0
        else:
            scores["peak"] = 0.0

        # Stable: 指标平稳，CTR 在峰值 70%-90% 之间
        if max_ctr > 0:
            ctr_ratio = last.ctr / max_ctr
            if 0.7 <= ctr_ratio < PEAK_CTR_RATIO and ctr_volatility < 0.15:
                scores["stable"] = 1.0 - ctr_volatility
            else:
                scores["stable"] = 0.0
        else:
            scores["stable"] = 0.0

        # Fatigue Warning: CTR 下降 15%-30%
        if max_ctr > 0:
            ctr_drop = (max_ctr - last.ctr) / max_ctr
            if FATIGUE_WARNING_CTR_DROP <= ctr_drop < FATIGUED_CTR_DROP:
                scores["fatigue_warning"] = min(1.0, ctr_drop / FATIGUED_CTR_DROP)
            else:
                scores["fatigue_warning"] = 0.0
        else:
            scores["fatigue_warning"] = 0.0

        # Fatigued: CTR 下降 > 30% 或 ROAS 下降 > 35%
        if max_ctr > 0 and max_roas > 0:
            ctr_drop = (max_ctr - last.ctr) / max_ctr
            roas_drop = (max_roas - last.roas) / max_roas
            if ctr_drop >= FATIGUED_CTR_DROP or roas_drop >= FATIGUED_ROAS_DROP:
                scores["fatigued"] = min(1.0, max(ctr_drop, roas_drop))
            else:
                scores["fatigued"] = 0.0
        else:
            scores["fatigued"] = 0.0

        # Dead: ROAS < 0.3
        if last.roas > 0:
            scores["dead"] = 1.0 if last.roas < DEAD_ROAS_THRESHOLD else 0.0
        else:
            scores["dead"] = 0.0

        # 选择得分最高的阶段
        best_stage_name = max(scores, key=lambda k: scores[k])
        best_stage = CreativeLifecycleStage(best_stage_name)

        return best_stage, scores

    def _predict_next_stage(
        self,
        current_stage: CreativeLifecycleStage,
        history: list[RealityHistoryPoint],
    ) -> CreativeLifecycleStage:
        """预测下一个阶段。"""
        valid_next = VALID_LIFECYCLE_TRANSITIONS.get(current_stage, [])

        if not valid_next:
            return current_stage

        last = history[-1]
        first = history[0]

        # 计算趋势方向
        ctr_decay = (first.ctr - last.ctr) / first.ctr if first.ctr > 0 else 0
        roas_decay = (first.roas - last.roas) / first.roas if first.roas > 0 else 0

        # 如果正在退化，选择更严重的下一个阶段
        if ctr_decay > 0.05 or roas_decay > 0.05:
            degrading_stages = [
                s for s in valid_next
                if LIFECYCLE_SEVERITY.get(s, 0) > LIFECYCLE_SEVERITY.get(current_stage, 0)
            ]
            if degrading_stages:
                return degrading_stages[0]  # 最近的退化阶段

        # 如果正在改善，选择不太严重的阶段
        if ctr_decay < -0.05 or roas_decay < -0.05:
            improving_stages = [
                s for s in valid_next
                if LIFECYCLE_SEVERITY.get(s, 0) < LIFECYCLE_SEVERITY.get(current_stage, 0)
            ]
            if improving_stages:
                return improving_stages[0]

        # 默认：选择严重程度最接近的下一个阶段
        return valid_next[0]

    def _estimate_days_to_transition(
        self,
        current_stage: CreativeLifecycleStage,
        predicted_stage: CreativeLifecycleStage,
        history: list[RealityHistoryPoint],
    ) -> int:
        """估算过渡到下一个阶段的天数。"""
        if current_stage == predicted_stage:
            return -1

        if len(history) < 2:
            return -1

        # 计算 CTR 衰减速度
        ctr_values = [p.ctr for p in history]
        if len(ctr_values) < 2:
            return -1

        first_ctr = ctr_values[0]
        last_ctr = ctr_values[-1]
        days = len(history) - 1

        if days == 0:
            return -1

        # 每天衰减率
        if first_ctr > 0:
            daily_decay = (first_ctr - last_ctr) / first_ctr / days
        else:
            daily_decay = 0

        if daily_decay <= 0:
            return -1  # 没有衰减，无法预测

        # 需要多少衰减才能过渡
        current_severity = LIFECYCLE_SEVERITY.get(current_stage, 0)
        predicted_severity = LIFECYCLE_SEVERITY.get(predicted_stage, 0)
        severity_gap = predicted_severity - current_severity

        if severity_gap <= 0:
            return -1

        # 每级严重度大约需要 15% CTR 衰减
        decay_needed = severity_gap * 0.15
        estimated_days = int(math.ceil(decay_needed / daily_decay))

        return max(1, estimated_days)

    # ── Helpers ────────────────────────────────────────────

    @staticmethod
    def _compute_volatility(values: list[float]) -> float:
        """计算序列波动率（变异系数）。"""
        if not values or len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        if mean == 0:
            return 0.0
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return math.sqrt(variance) / mean

    @staticmethod
    def _compute_confidence(
        history: list[RealityHistoryPoint],
        current_stage: CreativeLifecycleStage,
        predicted_stage: CreativeLifecycleStage,
    ) -> float:
        """计算置信度。"""
        days = len(history)
        total_installs = sum(p.installs for p in history)

        # 数据量因子
        if days >= 14 and total_installs >= 5000:
            data_factor = 1.0
        elif days >= 7 and total_installs >= 1000:
            data_factor = 0.8
        elif days >= 3 and total_installs >= 100:
            data_factor = 0.5
        else:
            data_factor = 0.3

        # 阶段确定性因子
        if current_stage == predicted_stage:
            stage_factor = 0.5
        else:
            stage_factor = 0.8

        # 趋势一致性
        ctr_values = [p.ctr for p in history]
        consistent = LifecyclePredictor._is_trend_consistent(ctr_values)
        trend_factor = 0.9 if consistent else 0.5

        return data_factor * 0.4 + stage_factor * 0.3 + trend_factor * 0.3

    @staticmethod
    def _is_trend_consistent(values: list[float]) -> bool:
        """检查趋势是否一致（单调）。"""
        if len(values) < 3:
            return True
        increasing = all(values[i] <= values[i + 1] for i in range(len(values) - 1))
        decreasing = all(values[i] >= values[i + 1] for i in range(len(values) - 1))
        return increasing or decreasing

    @staticmethod
    def _is_monotonic_decline(values: list[float]) -> bool:
        """检查是否单调下降。"""
        if len(values) < 3:
            return False
        return all(values[i] >= values[i + 1] for i in range(len(values) - 1))

    @staticmethod
    def _build_evidence(
        history: list[RealityHistoryPoint],
        current_stage: CreativeLifecycleStage,
        predicted_stage: CreativeLifecycleStage,
        days_to_transition: int,
    ) -> list[str]:
        """构建证据列表。"""
        evidence: list[str] = []
        first = history[0]
        last = history[-1]

        evidence.append(
            f"Creative in {current_stage.value} stage "
            f"({len(history)} days of data)"
        )

        if first.ctr > 0:
            ctr_change = (last.ctr - first.ctr) / first.ctr
            evidence.append(f"CTR changed {ctr_change:+.0%} over observation period")

        if first.roas > 0:
            roas_change = (last.roas - first.roas) / first.roas
            evidence.append(f"ROAS changed {roas_change:+.0%} over observation period")

        if current_stage != predicted_stage:
            evidence.append(
                f"Predicted transition to {predicted_stage.value} "
                f"in {days_to_transition} days"
            )

        return evidence

    @staticmethod
    def _recommend_action(
        current_stage: CreativeLifecycleStage,
        predicted_stage: CreativeLifecycleStage,
    ) -> str:
        """根据阶段推荐行动。"""
        if predicted_stage == CreativeLifecycleStage.DEAD:
            return "RETIRE_AND_REGENERATE"
        elif predicted_stage == CreativeLifecycleStage.FATIGUED:
            return "MUTATE_CREATIVE"
        elif predicted_stage == CreativeLifecycleStage.FATIGUE_WARNING:
            return "PREPARE_MUTATION"
        elif current_stage == CreativeLifecycleStage.PEAK:
            return "SCALE_BUDGET"
        elif current_stage == CreativeLifecycleStage.LAUNCH:
            return "COLLECT_DATA"
        else:
            return "MONITOR"

    def __repr__(self) -> str:
        return "LifecyclePredictor()"