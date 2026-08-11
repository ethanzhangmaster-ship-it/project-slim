"""E13.7.8 Learning Feedback Models — 学习反馈协议.

Day 7.8 Step 4:
  定义 OutcomeMeasurement → LearningEvaluator → PolicyController 的
  自动反馈桥接层，将测量结果转化为可执行的反馈信号。

核心模型:
  1. FeedbackClassification  — 反馈分类枚举
  2. LearningFeedback        — 学习反馈 (含分类、建议、策略调整)
  3. FeedbackAction          — 反馈动作 (具体操作指令)

设计原则:
  - 纯数据模型，不包含执行逻辑
  - 反馈分类基于确定性规则，不是 AI 猜测
  - 可序列化 (to_dict)，支持审计
  - 不修改已有模块 (OutcomeMeasurement, LearningEvaluator, PolicyController)

用法:
  from growth_runtime.intelligence.learning.models.learning_feedback_models import (
      FeedbackClassification,
      LearningFeedback,
  )
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# 1. FeedbackClassification
# ═══════════════════════════════════════════════════════════════


class FeedbackClassification(str, Enum):
    """反馈分类 — 学习效果的四级分类.

    | 分类                   | 含义                          | 触发条件                  |
    |-----------------------|------------------------------|--------------------------|
    | GOOD_LEARNING         | 学习有效，策略在改善            | learning_gain > 0.05     |
    | BAD_LEARNING          | 学习无效，策略在恶化            | learning_gain < -0.05    |
    | INSUFFICIENT_DATA     | 数据不足，无法判断              | 指标不完整                |
    | STAGNANT              | 停滞，学习无变化                | |learning_gain| <= 0.05 |
    """

    GOOD_LEARNING = "good_learning"
    BAD_LEARNING = "bad_learning"
    INSUFFICIENT_DATA = "insufficient_data"
    STAGNANT = "stagnant"


# ═══════════════════════════════════════════════════════════════
# 2. FeedbackAction
# ═══════════════════════════════════════════════════════════════


class FeedbackAction(str, Enum):
    """反馈动作 — 基于分类的具体操作指令.

    | 动作                  | 含义                          | 适用分类              |
    |----------------------|------------------------------|----------------------|
    | INCREASE_CONFIDENCE  | 提升决策置信度                 | GOOD_LEARNING        |
    | SCALE_UP             | 扩大学习规模                   | GOOD_LEARNING        |
    | REDUCE_EXPLORATION   | 降低探索率，提高利用            | BAD_LEARNING         |
    | ROLLBACK_STRATEGY    | 回滚策略到上一版本              | BAD_LEARNING         |
    | CONTINUE_SAMPLING    | 继续采样，积累数据              | INSUFFICIENT_DATA    |
    | INVESTIGATE          | 人工审查异常                   | STAGNANT / BAD_LEARNING |
    | MAINTAIN             | 保持当前策略不变                | STAGNANT             |
    | ADJUST_WEIGHTS       | 调整学习权重                   | STAGNANT             |
    """

    INCREASE_CONFIDENCE = "increase_confidence"
    SCALE_UP = "scale_up"
    REDUCE_EXPLORATION = "reduce_exploration"
    ROLLBACK_STRATEGY = "rollback_strategy"
    CONTINUE_SAMPLING = "continue_sampling"
    INVESTIGATE = "investigate"
    MAINTAIN = "maintain"
    ADJUST_WEIGHTS = "adjust_weights"


# ═══════════════════════════════════════════════════════════════
# 3. LearningFeedback
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearningFeedback:
    """学习反馈 — OutcomeMeasurement 到 PolicyController 的桥接.

    Day 7.8 Step 4:
      将 OutcomeMeasurement 和 LearningEffectiveness 综合为
      可执行的反馈信号，驱动策略调整。

    Attributes:
        feedback_id: 反馈唯一标识
        cycle_number: 编排周期编号
        classification: 反馈分类 (GOOD/BAD/INSUFFICIENT/STAGNANT)
        actions: 建议执行的动作列表
        outcome_measurement: 来源 OutcomeMeasurement
        effectiveness: 来源 LearningEffectiveness (可选)
        confidence_adjustment: 建议的置信度调整量 [-1, 1]
        exploration_adjustment: 建议的探索率调整量 [-1, 1]
        recommendation: 自然语言建议
        is_actionable: 是否有可执行的动作
        created_at: 创建时间
        metadata: 扩展元数据
    """

    feedback_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cycle_number: int = 0
    classification: str = FeedbackClassification.INSUFFICIENT_DATA.value
    actions: list[str] = field(default_factory=list)
    outcome_measurement: Any = None  # OutcomeMeasurement
    effectiveness: Any = None  # LearningEffectiveness
    confidence_adjustment: float = 0.0
    exploration_adjustment: float = 0.0
    recommendation: str = ""
    is_actionable: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_good(self) -> bool:
        return self.classification == FeedbackClassification.GOOD_LEARNING.value

    @property
    def is_bad(self) -> bool:
        return self.classification == FeedbackClassification.BAD_LEARNING.value

    @property
    def is_insufficient(self) -> bool:
        return self.classification == FeedbackClassification.INSUFFICIENT_DATA.value

    @property
    def is_stagnant(self) -> bool:
        return self.classification == FeedbackClassification.STAGNANT.value

    @property
    def has_effectiveness(self) -> bool:
        return self.effectiveness is not None

    @property
    def has_outcome(self) -> bool:
        return self.outcome_measurement is not None

    # ── Factory Methods ────────────────────────────────────────

    @classmethod
    def from_measurement(
        cls,
        outcome: Any,  # OutcomeMeasurement
        cycle_number: int = 0,
        effectiveness: Any = None,  # LearningEffectiveness
    ) -> LearningFeedback:
        """从 OutcomeMeasurement 创建反馈.

        Args:
            outcome: OutcomeMeasurement 实例
            cycle_number: 周期编号
            effectiveness: LearningEffectiveness (可选)

        Returns:
            LearningFeedback
        """
        classification, actions, conf_adj, expl_adj, recommendation = (
            cls._classify(outcome, effectiveness)
        )

        return cls(
            cycle_number=cycle_number,
            classification=classification.value,
            actions=[a.value for a in actions],
            outcome_measurement=outcome,
            effectiveness=effectiveness,
            confidence_adjustment=round(conf_adj, 4),
            exploration_adjustment=round(expl_adj, 4),
            recommendation=recommendation,
            is_actionable=len(actions) > 0
            and classification != FeedbackClassification.INSUFFICIENT_DATA,
        )

    @classmethod
    def insufficient(
        cls,
        cycle_number: int = 0,
        reason: str = "",
    ) -> LearningFeedback:
        """创建 INSUFFICIENT_DATA 反馈."""
        return cls(
            cycle_number=cycle_number,
            classification=FeedbackClassification.INSUFFICIENT_DATA.value,
            actions=[FeedbackAction.CONTINUE_SAMPLING.value],
            recommendation=reason or "Insufficient data for feedback",
            is_actionable=False,
        )

    # ── Static Classification Logic ─────────────────────────────

    @staticmethod
    def _classify(
        outcome: Any,
        effectiveness: Any,
    ) -> tuple[
        FeedbackClassification,
        list[FeedbackAction],
        float,
        float,
        str,
    ]:
        """分类反馈.

        Args:
            outcome: OutcomeMeasurement
            effectiveness: LearningEffectiveness (可选)

        Returns:
            (classification, actions, confidence_adjustment, exploration_adjustment, recommendation)
        """
        # ── 不可测量 → INSUFFICIENT_DATA ──
        if outcome is None or not getattr(outcome, "is_measurable", False):
            return (
                FeedbackClassification.INSUFFICIENT_DATA,
                [FeedbackAction.CONTINUE_SAMPLING],
                0.0,
                0.0,
                "Insufficient measurement data — continue sampling",
            )

        learning_gain = getattr(outcome, "learning_gain", 0.0)
        reward_delta = getattr(outcome, "reward_delta", 0.0)
        confidence_delta = getattr(outcome, "confidence_delta", 0.0)
        success_delta = getattr(outcome, "success_delta", 0.0)

        # ── GOOD_LEARNING ──
        if learning_gain > 0.05:
            actions = [FeedbackAction.INCREASE_CONFIDENCE]
            conf_adj = min(0.2, learning_gain * 0.3)
            expl_adj = -0.05  # 减少探索，更多利用

            recommendation = "Learning is effective — increasing confidence"
            if learning_gain > 0.3:
                actions.append(FeedbackAction.SCALE_UP)
                recommendation = (
                    "Strong learning gain — scaling up and increasing confidence"
                )

            return (
                FeedbackClassification.GOOD_LEARNING,
                actions,
                conf_adj,
                expl_adj,
                recommendation,
            )

        # ── BAD_LEARNING ──
        if learning_gain < -0.05:
            actions = [FeedbackAction.REDUCE_EXPLORATION]
            conf_adj = max(-0.2, learning_gain * 0.3)
            expl_adj = -0.1  # 显著减少探索

            recommendation = "Learning is ineffective — reducing exploration"
            if learning_gain < -0.3:
                actions.append(FeedbackAction.ROLLBACK_STRATEGY)
                actions.append(FeedbackAction.INVESTIGATE)
                recommendation = (
                    "Strong negative learning — rollback and investigate"
                )
            elif learning_gain < -0.15:
                actions.append(FeedbackAction.INVESTIGATE)

            return (
                FeedbackClassification.BAD_LEARNING,
                actions,
                conf_adj,
                expl_adj,
                recommendation,
            )

        # ── STAGNANT (|learning_gain| <= 0.05) ──
        actions = [FeedbackAction.MAINTAIN]
        conf_adj = 0.0
        expl_adj = 0.0
        recommendation = "Learning is stagnant — maintaining current strategy"

        if abs(reward_delta) < 0.02 and abs(confidence_delta) < 0.02:
            # 真正停滞，尝试调整权重
            actions.append(FeedbackAction.ADJUST_WEIGHTS)
            recommendation = (
                "Learning has plateaued — adjusting weights to break through"
            )
        elif success_delta < 0:
            actions.append(FeedbackAction.INVESTIGATE)
            recommendation = "Stagnant with failures — investigate root cause"

        return (
            FeedbackClassification.STAGNANT,
            actions,
            conf_adj,
            expl_adj,
            recommendation,
        )

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "cycle_number": self.cycle_number,
            "classification": self.classification,
            "actions": self.actions,
            "outcome_measurement": (
                self.outcome_measurement.to_dict()
                if hasattr(self.outcome_measurement, "to_dict")
                else None
            ),
            "effectiveness": (
                self.effectiveness.to_dict()
                if hasattr(self.effectiveness, "to_dict")
                else None
            ),
            "confidence_adjustment": self.confidence_adjustment,
            "exploration_adjustment": self.exploration_adjustment,
            "recommendation": self.recommendation,
            "is_actionable": self.is_actionable,
            "is_good": self.is_good,
            "is_bad": self.is_bad,
            "is_insufficient": self.is_insufficient,
            "is_stagnant": self.is_stagnant,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "FeedbackClassification",
    "FeedbackAction",
    "LearningFeedback",
]