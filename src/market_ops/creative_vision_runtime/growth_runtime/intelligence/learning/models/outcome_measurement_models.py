"""E13.7.8 Outcome Measurement Models — 执行结果测量协议.

Day 7.8 Step 3:
  定义 LearningExecutionResult → OutcomeMeasurement 的桥接层，
  将执行结果转化为可量化的学习指标，填补 Execution → Evaluation 的缺口。

核心模型:
  1. OutcomeMeasurement  — 执行结果测量 (reward_delta, confidence_delta, success_delta, learning_gain)
  2. MeasurementContext   — 测量上下文 (before/after snapshots)

设计原则:
  - 纯数据模型，不包含执行逻辑
  - 所有 delta 计算在 Measurement 层完成，评估层只消费
  - 可序列化 (to_dict)，支持审计
  - 不修改已有模块 (LearningExecutionResult, LearningEvaluator, DecisionImpactTracker)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ═══════════════════════════════════════════════════════════════
# 1. MeasurementContext
# ═══════════════════════════════════════════════════════════════


@dataclass
class MeasurementContext:
    """测量上下文 — 执行前后的状态快照.

    Attributes:
        execution_action: 执行的动作类型
        execution_success: 执行是否成功
        metrics_before: 执行前业务指标 (ROAS, CTR, CVR, CPI, spend, ...)
        metrics_after: 执行后业务指标
        strategy_state_before: 执行前策略状态
        strategy_state_after: 执行后策略状态
        policy_decision_type: 触发的策略决策类型
        cycle_number: 编排周期编号
        metadata: 扩展元数据
    """

    execution_action: str = ""
    execution_success: bool = False
    metrics_before: dict[str, float] = field(default_factory=dict)
    metrics_after: dict[str, float] = field(default_factory=dict)
    strategy_state_before: dict[str, Any] | None = None
    strategy_state_after: dict[str, Any] | None = None
    policy_decision_type: str = ""
    cycle_number: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_metrics(self) -> bool:
        """是否有完整的业务指标."""
        return len(self.metrics_before) > 0 and len(self.metrics_after) > 0

    @property
    def has_strategy_state(self) -> bool:
        """是否有策略状态快照."""
        return (
            self.strategy_state_before is not None
            and self.strategy_state_after is not None
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_action": self.execution_action,
            "execution_success": self.execution_success,
            "metrics_before": self.metrics_before,
            "metrics_after": self.metrics_after,
            "strategy_state_before": self.strategy_state_before,
            "strategy_state_after": self.strategy_state_after,
            "policy_decision_type": self.policy_decision_type,
            "cycle_number": self.cycle_number,
            "has_metrics": self.has_metrics,
            "has_strategy_state": self.has_strategy_state,
        }


# ═══════════════════════════════════════════════════════════════
# 2. OutcomeMeasurement
# ═══════════════════════════════════════════════════════════════


@dataclass
class OutcomeMeasurement:
    """执行结果测量 — 一次执行后的量化学习指标.

    Day 7.8 Step 3:
      桥接 ExecutionResult → LearningEvaluator，将执行结果
      转化为可量化的学习指标。

    核心指标:
      - reward_delta: 奖励变化
      - confidence_delta: 置信度变化
      - success_delta: 成功率变化
      - learning_gain: 综合学习增益

    Attributes:
        measurement_id: 测量唯一标识
        cycle_number: 编排周期编号
        execution_action: 执行的动作类型
        execution_success: 执行是否成功
        reward_delta: 奖励变化 [-1, 1]
        confidence_delta: 置信度变化 [-1, 1]
        success_delta: 成功率变化 [-1, 1]
        learning_gain: 综合学习增益 [-1, 1]
        is_measurable: 是否有足够数据进行测量
        metrics_before: 执行前业务指标
        metrics_after: 执行后业务指标
        metrics_delta: 指标变化率
        strategy_change_detected: 策略状态是否发生变化
        measurement_confidence: 测量置信度 [0, 1]
        recommendations: 基于测量的建议
        created_at: 测量时间
        metadata: 扩展元数据
    """

    measurement_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cycle_number: int = 0
    execution_action: str = ""
    execution_success: bool = False
    reward_delta: float = 0.0
    confidence_delta: float = 0.0
    success_delta: float = 0.0
    learning_gain: float = 0.0
    is_measurable: bool = False
    metrics_before: dict[str, float] = field(default_factory=dict)
    metrics_after: dict[str, float] = field(default_factory=dict)
    metrics_delta: dict[str, float] = field(default_factory=dict)
    strategy_change_detected: bool = False
    measurement_confidence: float = 0.0
    recommendations: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_positive(self) -> bool:
        """学习增益是否为正."""
        return self.learning_gain > 0.0

    @property
    def is_negative(self) -> bool:
        """学习增益是否为负."""
        return self.learning_gain < 0.0

    @property
    def is_significant(self) -> bool:
        """学习增益是否显著 (>0.05)."""
        return abs(self.learning_gain) > 0.05

    @property
    def is_high_confidence(self) -> bool:
        """测量置信度是否高."""
        return self.measurement_confidence >= 0.7

    @property
    def has_metric_data(self) -> bool:
        """是否有业务指标数据."""
        return len(self.metrics_delta) > 0

    # ── Factory Methods ────────────────────────────────────────

    @classmethod
    def not_measurable(
        cls,
        cycle_number: int = 0,
        reason: str = "",
    ) -> OutcomeMeasurement:
        """创建不可测量的结果."""
        return cls(
            cycle_number=cycle_number,
            is_measurable=False,
            measurement_confidence=0.0,
            recommendations=[reason or "No previous execution result to measure"],
        )

    @classmethod
    def from_execution(
        cls,
        cycle_number: int,
        execution_action: str,
        execution_success: bool,
        metrics_before: dict[str, float] | None = None,
        metrics_after: dict[str, float] | None = None,
        strategy_state_before: dict[str, Any] | None = None,
        strategy_state_after: dict[str, Any] | None = None,
        measurement_confidence: float = 0.5,
    ) -> OutcomeMeasurement:
        """从执行结果创建测量.

        Args:
            cycle_number: 周期编号
            execution_action: 执行动作
            execution_success: 执行是否成功
            metrics_before: 执行前指标
            metrics_after: 执行后指标
            strategy_state_before: 执行前策略状态
            strategy_state_after: 执行后策略状态
            measurement_confidence: 测量置信度

        Returns:
            OutcomeMeasurement
        """
        before = metrics_before or {}
        after = metrics_after or {}

        # 计算指标变化
        metrics_delta = cls._compute_metrics_delta(before, after)

        # 计算奖励变化 (基于 ROAS/key metrics)
        reward_delta = cls._compute_reward_delta(before, after, metrics_delta)

        # 计算置信度变化 (基于策略状态)
        confidence_delta = cls._compute_confidence_delta(
            strategy_state_before, strategy_state_after
        )

        # 计算成功率变化
        success_delta = cls._compute_success_delta(execution_success)

        # 计算综合学习增益
        learning_gain = cls._compute_learning_gain(
            reward_delta, confidence_delta, success_delta
        )

        # 是否可测量
        is_measurable = len(before) > 0 or len(after) > 0 or execution_action != ""

        # 策略变化检测
        strategy_change = cls._detect_strategy_change(
            strategy_state_before, strategy_state_after
        )

        # 生成建议
        recommendations = cls._generate_recommendations(
            learning_gain, reward_delta, confidence_delta
        )

        return cls(
            cycle_number=cycle_number,
            execution_action=execution_action,
            execution_success=execution_success,
            reward_delta=round(reward_delta, 4),
            confidence_delta=round(confidence_delta, 4),
            success_delta=round(success_delta, 4),
            learning_gain=round(learning_gain, 4),
            is_measurable=is_measurable,
            metrics_before=before,
            metrics_after=after,
            metrics_delta=metrics_delta,
            strategy_change_detected=strategy_change,
            measurement_confidence=round(measurement_confidence, 4),
            recommendations=recommendations,
        )

    # ── Static Computation Methods ──────────────────────────────

    @staticmethod
    def _compute_metrics_delta(
        before: dict[str, float],
        after: dict[str, float],
    ) -> dict[str, float]:
        """计算指标变化率."""
        delta: dict[str, float] = {}
        all_keys = set(before.keys()) | set(after.keys())
        for key in all_keys:
            b = before.get(key, 0.0)
            a = after.get(key, 0.0)
            if b != 0.0:
                delta[key] = round((a - b) / abs(b), 4)
            elif a != 0.0:
                delta[key] = 1.0
            else:
                delta[key] = 0.0
        return delta

    @staticmethod
    def _compute_reward_delta(
        before: dict[str, float],
        after: dict[str, float],
        metrics_delta: dict[str, float],
    ) -> float:
        """计算奖励变化.

        基于 ROAS, CTR, CVR 变化加权:
          reward_delta = tanh(roas_delta*5)*0.5 + tanh(ctr_delta*5)*0.25 + tanh(cvr_delta*5)*0.25
        """
        import math

        roas_delta = metrics_delta.get("roas", 0.0)
        ctr_delta = metrics_delta.get("ctr", 0.0)
        cvr_delta = metrics_delta.get("cvr", 0.0)

        if roas_delta == 0.0 and ctr_delta == 0.0 and cvr_delta == 0.0:
            # 无业务指标，基于执行成功/失败
            return 0.0

        reward = (
            math.tanh(roas_delta * 5.0) * 0.5
            + math.tanh(ctr_delta * 5.0) * 0.25
            + math.tanh(cvr_delta * 5.0) * 0.25
        )
        return round(max(-1.0, min(1.0, reward)), 4)

    @staticmethod
    def _compute_confidence_delta(
        strategy_before: dict[str, Any] | None,
        strategy_after: dict[str, Any] | None,
    ) -> float:
        """计算置信度变化.

        基于策略状态变化:
          - 如果 strategy_mode 变化，delta 反映模式切换的置信度
          - 如果 exploration_rate 降低，置信度提升
        """
        if strategy_before is None or strategy_after is None:
            return 0.0

        before_mode = strategy_before.get("learning_mode", "")
        after_mode = strategy_after.get("learning_mode", "")

        before_explore = strategy_before.get("exploration_rate", 0.2)
        after_explore = strategy_after.get("exploration_rate", 0.2)

        # 模式切换变化
        mode_delta = 0.0
        if before_mode != after_mode:
            if after_mode == "aggressive":
                mode_delta = -0.1  # 激进模式置信度相对低
            elif after_mode == "conservative":
                mode_delta = 0.1  # 保守模式置信度更高
            else:
                mode_delta = 0.05

        # 探索率变化 (探索率越低，置信度越高)
        explore_delta = (before_explore - after_explore) * 0.5

        return round(max(-1.0, min(1.0, mode_delta + explore_delta)), 4)

    @staticmethod
    def _compute_success_delta(execution_success: bool) -> float:
        """计算成功率变化."""
        return 1.0 if execution_success else -1.0

    @staticmethod
    def _compute_learning_gain(
        reward_delta: float,
        confidence_delta: float,
        success_delta: float,
    ) -> float:
        """计算综合学习增益.

        learning_gain = reward_delta × 0.50 + confidence_delta × 0.20 + success_delta × 0.30
        """
        gain = reward_delta * 0.50 + confidence_delta * 0.20 + success_delta * 0.30
        return round(max(-1.0, min(1.0, gain)), 4)

    @staticmethod
    def _detect_strategy_change(
        strategy_before: dict[str, Any] | None,
        strategy_after: dict[str, Any] | None,
    ) -> bool:
        """检测策略状态是否发生变化."""
        if strategy_before is None or strategy_after is None:
            return False
        return strategy_before != strategy_after

    @staticmethod
    def _generate_recommendations(
        learning_gain: float,
        reward_delta: float,
        confidence_delta: float,
    ) -> list[str]:
        """基于测量结果生成建议."""
        recs: list[str] = []

        if learning_gain > 0.3:
            recs.append("Strong positive learning gain — reinforce current strategy")
        elif learning_gain > 0.05:
            recs.append("Moderate positive learning gain — continue monitoring")
        elif learning_gain > -0.05:
            recs.append("Neutral learning gain — increase sample size")
        elif learning_gain > -0.3:
            recs.append("Negative learning gain — review strategy parameters")
        else:
            recs.append("Strong negative learning gain — consider strategy change")

        if reward_delta > 0.2:
            recs.append("Business metrics improving — scale up")
        elif reward_delta < -0.2:
            recs.append("Business metrics declining — investigate root cause")

        if confidence_delta > 0.1:
            recs.append("Decision confidence increasing — learning is effective")
        elif confidence_delta < -0.1:
            recs.append("Decision confidence decreasing — review learning quality")

        return recs

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "measurement_id": self.measurement_id,
            "cycle_number": self.cycle_number,
            "execution_action": self.execution_action,
            "execution_success": self.execution_success,
            "reward_delta": self.reward_delta,
            "confidence_delta": self.confidence_delta,
            "success_delta": self.success_delta,
            "learning_gain": self.learning_gain,
            "is_measurable": self.is_measurable,
            "metrics_before": self.metrics_before,
            "metrics_after": self.metrics_after,
            "metrics_delta": self.metrics_delta,
            "strategy_change_detected": self.strategy_change_detected,
            "measurement_confidence": self.measurement_confidence,
            "recommendations": self.recommendations,
            "is_positive": self.is_positive,
            "is_negative": self.is_negative,
            "is_significant": self.is_significant,
            "is_high_confidence": self.is_high_confidence,
            "has_metric_data": self.has_metric_data,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "MeasurementContext",
    "OutcomeMeasurement",
]