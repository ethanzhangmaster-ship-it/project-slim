"""E13.7.8 Policy Adjuster — 策略参数调整引擎.

Day 7.8 Step 6:
  将 Feedback + Gate + Effectiveness 三路信号融合为具体的
  策略参数调整建议，实现从 "感知" 到 "行动" 的最后一步。

核心流程:
  LearningFeedback
        +
  CycleGateResult
        +
  LearningEffectiveness
        +
  LearningStrategyState (current params)
        |
        v
  PolicyAdjuster.adjust()
        |
        v
  PolicyAdjustmentSet
        |
        +-- exploration_rate 调整
        +-- confidence_threshold 调整
        +-- pattern_weight 调整
        +-- memory_weight 调整
        +-- learning_mode 调整

调整策略 (四类反馈 → 参数调整):

  GOOD_LEARNING:
    - exploration_rate  ↓ (更多利用)
    - confidence_threshold ↑ (更严格)
    - pattern_weight  ↑ (更信任模式)

  BAD_LEARNING:
    - exploration_rate  ↑ (更多探索)
    - confidence_threshold ↓ (更宽松)
    - pattern_weight  ↓ (更保守)

  STAGNANT:
    - exploration_rate  ↑ (打破停滞)
    - pattern_weight  ~ (微调权重)
    - memory_weight  ~

  INSUFFICIENT_DATA:
    - 维持当前参数不变
    - 仅记录 "需要更多数据"

设计原则:
  - 确定性: 相同输入 → 相同调整
  - 渐进式: 每次调整幅度有限 (max 0.1 per step)
  - 可审计: 每次调整记录 reason + confidence
  - 不侵入已有模块: 通过 PolicyAdjustment 数据模型桥接

用法:
  from growth_runtime.intelligence.learning.learning_policy_adjuster import (
      PolicyAdjuster,
  )

  adjuster = PolicyAdjuster()
  adjustment_set = adjuster.adjust(
      feedback=feedback,
      gate_result=gate_result,
      effectiveness=effectiveness,
      current_state=strategy_state,
  )
"""

from __future__ import annotations

from typing import Any

from .models.learning_policy_models import (
    AdjustmentDirection,
    PolicyAdjustment,
    PolicyAdjustmentSet,
)


# ═══════════════════════════════════════════════════════════════
# Adjustment Constants
# ═══════════════════════════════════════════════════════════════

# 单次调整最大幅度
_MAX_DELTA = 0.10

# 调整系数 (基于 learning_gain 缩放)
_ADJUST_SCALE = 0.5

# 可调整的策略参数列表
_ADJUSTABLE_POLICIES = [
    "exploration_rate",
    "confidence_threshold",
    "pattern_weight",
    "memory_weight",
]


# ═══════════════════════════════════════════════════════════════
# PolicyAdjuster
# ═══════════════════════════════════════════════════════════════


class PolicyAdjuster:
    """策略参数调整引擎 — 反馈驱动的参数调速器.

    用法:
        adjuster = PolicyAdjuster()
        adjustment_set = adjuster.adjust(
            feedback=feedback,
            gate_result=gate_result,
            effectiveness=effectiveness,
            current_state=strategy_state,
        )
    """

    def __init__(self) -> None:
        self._adjust_count: int = 0
        self._adjustment_history: list[PolicyAdjustmentSet] = []

    @property
    def adjust_count(self) -> int:
        return self._adjust_count

    # ── Public API ───────────────────────────────────────────────

    def adjust(
        self,
        feedback: Any = None,  # LearningFeedback
        gate_result: Any = None,  # CycleGateResult
        effectiveness: Any = None,  # LearningEffectiveness
        current_state: Any = None,  # LearningStrategyState
        cycle_number: int = 0,
    ) -> PolicyAdjustmentSet:
        """执行策略调整 — 主入口.

        Args:
            feedback: LearningFeedback 实例
            gate_result: CycleGateResult 实例
            effectiveness: LearningEffectiveness 实例
            current_state: LearningStrategyState 实例

        Returns:
            PolicyAdjustmentSet
        """
        self._adjust_count += 1

        # 提取当前参数值
        params = self._extract_current_params(current_state)

        # 提取分类和门控信号
        classification = getattr(feedback, "classification", "") if feedback else ""
        gate_decision = getattr(gate_result, "decision", "") if gate_result else ""
        learning_gain = self._extract_learning_gain(feedback, effectiveness)

        # 根据分类选择调整策略
        adjustments = self._apply_adjustment_strategy(
            classification=classification,
            gate_decision=gate_decision,
            learning_gain=learning_gain,
            params=params,
            cycle_number=cycle_number,
        )

        adjustment_set = PolicyAdjustmentSet.from_adjustments(
            adjustments=adjustments,
            cycle_number=cycle_number,
            source_feedback=classification,
            source_gate=gate_decision,
        )

        self._adjustment_history.append(adjustment_set)
        return adjustment_set

    # ── Adjustment Strategy ─────────────────────────────────────

    def _apply_adjustment_strategy(
        self,
        classification: str,
        gate_decision: str,
        learning_gain: float,
        params: dict[str, float],
        cycle_number: int,
    ) -> list[PolicyAdjustment]:
        """根据分类选择调整策略."""
        if classification == "good_learning":
            return self._adjust_good_learning(learning_gain, params, cycle_number)
        elif classification == "bad_learning":
            return self._adjust_bad_learning(learning_gain, params, cycle_number, gate_decision)
        elif classification == "stagnant":
            return self._adjust_stagnant(learning_gain, params, cycle_number)
        elif classification == "insufficient_data":
            return self._adjust_insufficient(params, cycle_number)
        else:
            return self._adjust_default(params, cycle_number)

    # ── GOOD_LEARNING ───────────────────────────────────────────

    def _adjust_good_learning(
        self,
        learning_gain: float,
        params: dict[str, float],
        cycle_number: int,
    ) -> list[PolicyAdjustment]:
        """正向学习 → 提高利用，降低探索，增强信心.

        - exploration_rate   ↓ (减少探索，更多利用)
        - confidence_threshold ↑ (提高门槛，更严格)
        - pattern_weight     ↑ (更信任模式)
        """
        scale = min(_MAX_DELTA, abs(learning_gain) * _ADJUST_SCALE)
        confidence = min(0.95, 0.5 + abs(learning_gain))
        source = "good_learning"

        adjustments = []

        # exploration_rate: 下调
        exp_delta = min(scale, params["exploration_rate"] * 0.2)
        if exp_delta > 0.005:
            adjustments.append(PolicyAdjustment.decrease(
                target_policy="exploration_rate",
                current_value=params["exploration_rate"],
                delta=exp_delta,
                reason=f"Good learning (gain={learning_gain:.4f}) — reducing exploration",
                confidence=confidence,
                cycle_number=cycle_number,
                source=source,
            ))

        # confidence_threshold: 上调
        conf_delta = min(scale * 0.5, 0.05)
        if conf_delta > 0.001:
            adjustments.append(PolicyAdjustment.increase(
                target_policy="confidence_threshold",
                current_value=params["confidence_threshold"],
                delta=conf_delta,
                reason=f"Good learning — raising confidence threshold",
                confidence=confidence,
                cycle_number=cycle_number,
                source=source,
            ))

        # pattern_weight: 上调
        pw_delta = min(scale * 0.3, 0.05)
        if pw_delta > 0.001:
            adjustments.append(PolicyAdjustment.increase(
                target_policy="pattern_weight",
                current_value=params["pattern_weight"],
                delta=pw_delta,
                reason=f"Good learning — trusting patterns more",
                confidence=confidence,
                cycle_number=cycle_number,
                source=source,
            ))

        # memory_weight: 随 pattern_weight 调整 (保持 sum=1.0)
        if pw_delta > 0.001:
            new_memory = round(max(0.0, params["memory_weight"] - pw_delta), 4)
            adjustments.append(PolicyAdjustment(
                cycle_number=cycle_number,
                target_policy="memory_weight",
                current_value=params["memory_weight"],
                recommended_value=new_memory,
                adjustment_delta=round(new_memory - params["memory_weight"], 4),
                direction=AdjustmentDirection.DECREASE.value,
                reason="Rebalancing memory_weight to match pattern_weight increase",
                confidence=confidence,
                source=source,
            ))

        return adjustments

    # ── BAD_LEARNING ────────────────────────────────────────────

    def _adjust_bad_learning(
        self,
        learning_gain: float,
        params: dict[str, float],
        cycle_number: int,
        gate_decision: str,
    ) -> list[PolicyAdjustment]:
        """负向学习 → 提高探索，降低信心，回滚策略.

        - exploration_rate   ↑ (增加探索，寻找新方向)
        - confidence_threshold ↓ (降低门槛，允许更多尝试)
        - pattern_weight     ↓ (减少对旧模式的依赖)
        """
        scale = min(_MAX_DELTA, abs(learning_gain) * _ADJUST_SCALE)
        confidence = min(0.9, 0.5 + abs(learning_gain))
        source = "bad_learning"

        # ROLLBACK gate → 更激进的调整
        if gate_decision == "rollback":
            scale = min(_MAX_DELTA * 1.5, scale * 2.0)
            confidence = min(0.95, confidence + 0.1)

        adjustments = []

        # exploration_rate: 上调
        exp_delta = min(scale, 0.15)
        if exp_delta > 0.005:
            adjustments.append(PolicyAdjustment.increase(
                target_policy="exploration_rate",
                current_value=params["exploration_rate"],
                delta=exp_delta,
                reason=f"Bad learning (gain={learning_gain:.4f}) — increasing exploration",
                confidence=confidence,
                cycle_number=cycle_number,
                source=source,
            ))

        # confidence_threshold: 下调
        conf_delta = min(scale * 0.5, 0.05)
        if conf_delta > 0.001:
            adjustments.append(PolicyAdjustment.decrease(
                target_policy="confidence_threshold",
                current_value=params["confidence_threshold"],
                delta=conf_delta,
                reason=f"Bad learning — lowering confidence threshold",
                confidence=confidence,
                cycle_number=cycle_number,
                source=source,
            ))

        # pattern_weight: 下调
        pw_delta = min(scale * 0.3, 0.05)
        if pw_delta > 0.001:
            adjustments.append(PolicyAdjustment.decrease(
                target_policy="pattern_weight",
                current_value=params["pattern_weight"],
                delta=pw_delta,
                reason=f"Bad learning — reducing trust in patterns",
                confidence=confidence,
                cycle_number=cycle_number,
                source=source,
            ))

        # memory_weight: 随 pattern_weight 调整
        if pw_delta > 0.001:
            new_memory = round(min(1.0, params["memory_weight"] + pw_delta), 4)
            adjustments.append(PolicyAdjustment(
                cycle_number=cycle_number,
                target_policy="memory_weight",
                current_value=params["memory_weight"],
                recommended_value=new_memory,
                adjustment_delta=round(new_memory - params["memory_weight"], 4),
                direction=AdjustmentDirection.INCREASE.value,
                reason="Rebalancing memory_weight to match pattern_weight decrease",
                confidence=confidence,
                source=source,
            ))

        return adjustments

    # ── STAGNANT ────────────────────────────────────────────────

    def _adjust_stagnant(
        self,
        learning_gain: float,
        params: dict[str, float],
        cycle_number: int,
    ) -> list[PolicyAdjustment]:
        """停滞 → 微调权重，增加探索扰动.

        - exploration_rate  ↑ (轻微增加探索以打破停滞)
        - pattern_weight    ~ (微调)
        """
        source = "stagnant"
        confidence = 0.6

        adjustments = []

        # exploration_rate: 微上调
        exp_delta = 0.02
        if params["exploration_rate"] < 0.5:
            adjustments.append(PolicyAdjustment.increase(
                target_policy="exploration_rate",
                current_value=params["exploration_rate"],
                delta=exp_delta,
                reason="Stagnant learning — slight exploration increase to break plateau",
                confidence=confidence,
                cycle_number=cycle_number,
                source=source,
            ))

        # 如果 pattern_weight 和 memory_weight 严重失衡，调整
        if abs(params["pattern_weight"] - params["memory_weight"]) > 0.5:
            target = 0.5
            adjustments.append(PolicyAdjustment(
                cycle_number=cycle_number,
                target_policy="pattern_weight",
                current_value=params["pattern_weight"],
                recommended_value=target,
                adjustment_delta=round(target - params["pattern_weight"], 4),
                direction=(
                    AdjustmentDirection.INCREASE.value
                    if params["pattern_weight"] < target
                    else AdjustmentDirection.DECREASE.value
                ),
                reason="Rebalancing weights to break stagnation",
                confidence=confidence,
                source=source,
            ))
            adjustments.append(PolicyAdjustment(
                cycle_number=cycle_number,
                target_policy="memory_weight",
                current_value=params["memory_weight"],
                recommended_value=target,
                adjustment_delta=round(target - params["memory_weight"], 4),
                direction=(
                    AdjustmentDirection.INCREASE.value
                    if params["memory_weight"] < target
                    else AdjustmentDirection.DECREASE.value
                ),
                reason="Rebalancing weights to break stagnation",
                confidence=confidence,
                source=source,
            ))

        return adjustments

    # ── INSUFFICIENT_DATA ───────────────────────────────────────

    def _adjust_insufficient(
        self,
        params: dict[str, float],
        cycle_number: int,
    ) -> list[PolicyAdjustment]:
        """数据不足 → 维持所有参数不变."""
        source = "insufficient_data"
        adjustments = []

        for policy in _ADJUSTABLE_POLICIES:
            val = params.get(policy, 0.0)
            adjustments.append(PolicyAdjustment.maintain(
                target_policy=policy,
                current_value=val,
                reason="Insufficient data — maintaining current policy",
                cycle_number=cycle_number,
                source=source,
            ))

        return adjustments

    # ── DEFAULT ─────────────────────────────────────────────────

    def _adjust_default(
        self,
        params: dict[str, float],
        cycle_number: int,
    ) -> list[PolicyAdjustment]:
        """默认 (无分类) → 维持不变."""
        source = "unknown"
        adjustments = []

        for policy in _ADJUSTABLE_POLICIES:
            val = params.get(policy, 0.0)
            adjustments.append(PolicyAdjustment.maintain(
                target_policy=policy,
                current_value=val,
                reason="No feedback classification — maintaining current policy",
                cycle_number=cycle_number,
                source=source,
            ))

        return adjustments

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _extract_learning_gain(
        feedback: Any,
        effectiveness: Any,
    ) -> float:
        """从 feedback 或 effectiveness 提取 learning_gain."""
        if feedback is not None:
            outcome = getattr(feedback, "outcome_measurement", None)
            if outcome is not None:
                gain = getattr(outcome, "learning_gain", 0.0)
                if gain != 0.0:
                    return gain or 0.0
        if effectiveness is not None:
            gain = getattr(effectiveness, "learning_gain", 0.0)
            if gain is not None:
                return gain
        return 0.0

    @staticmethod
    def _extract_current_params(current_state: Any) -> dict[str, float]:
        """从 LearningStrategyState 提取当前参数值."""
        default_params = {
            "exploration_rate": 0.3,
            "confidence_threshold": 0.5,
            "pattern_weight": 0.7,
            "memory_weight": 0.3,
        }

        if current_state is None:
            return default_params

        params = {}
        for policy in _ADJUSTABLE_POLICIES:
            val = getattr(current_state, policy, None)
            params[policy] = float(val) if val is not None else default_params[policy]

        return params

    # ── Query ────────────────────────────────────────────────────

    def get_history(self) -> list[PolicyAdjustmentSet]:
        return list(self._adjustment_history)

    def get_latest(self) -> PolicyAdjustmentSet | None:
        if not self._adjustment_history:
            return None
        return self._adjustment_history[-1]

    def get_stats(self) -> dict[str, Any]:
        if not self._adjustment_history:
            return {
                "adjust_count": self._adjust_count,
                "total_adjustments": 0,
                "significant_total": 0,
                "recent_direction": "none",
            }

        total_adjustments = sum(s.total_adjustments for s in self._adjustment_history)
        total_significant = sum(s.significant_count for s in self._adjustment_history)

        # 最近一次调整方向
        latest = self._adjustment_history[-1]
        if latest.is_empty:
            recent_direction = "none"
        else:
            directions = [a.direction for a in latest.adjustments if a.is_significant]
            if not directions:
                recent_direction = "maintain"
            elif all(d == "increase" for d in directions):
                recent_direction = "increase"
            elif all(d == "decrease" for d in directions):
                recent_direction = "decrease"
            else:
                recent_direction = "mixed"

        return {
            "adjust_count": self._adjust_count,
            "total_adjustments": total_adjustments,
            "significant_total": total_significant,
            "recent_direction": recent_direction,
        }

    def reset(self) -> None:
        self._adjust_count = 0
        self._adjustment_history = []

    def __repr__(self) -> str:
        return (
            f"PolicyAdjuster("
            f"adjustments={self._adjust_count})"
        )


__all__ = [
    "PolicyAdjuster",
]