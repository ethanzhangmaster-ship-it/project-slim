"""E13.7.8 Learning Feedback Router — 学习反馈路由器.

Day 7.8 Step 4:
  将 OutcomeMeasurement 和 LearningEffectiveness 自动分类并路由到
  对应的处理动作，实现从 "测量" 到 "行动" 的自动反馈闭环。

核心流程:
  OutcomeMeasurement
          |
          v
  FeedbackRouter.route()
          |
          +--> 分类: GOOD_LEARNING / BAD_LEARNING / INSUFFICIENT_DATA / STAGNANT
          |
          +--> 路由: increase_confidence / scale_up / reduce_exploration / rollback / ...
          |
          v
  LearningFeedback
          |
          v
  LearningPolicyController (置信度调整, 探索率调整)
          |
          v
  LearningExecutionAdapter

设计原则:
  - 确定性路由: 基于 learning_gain, reward_delta, confidence_delta 的明确阈值
  - 分层路由: 先分类 → 再选动作 → 再执行
  - 可审计: 每次路由决策记录 classification + actions + reasoning
  - 不侵入已有模块: 通过 LearningFeedback 数据模型桥接

用法:
  from growth_runtime.intelligence.learning.learning_feedback_router import (
      LearningFeedbackRouter,
  )

  router = LearningFeedbackRouter()
  feedback = router.route(
      outcome_measurement=measurement,
      effectiveness=effectiveness,
      cycle_number=3,
  )
"""

from __future__ import annotations

from typing import Any

from .models.learning_feedback_models import (
    FeedbackAction,
    FeedbackClassification,
    LearningFeedback,
)


# ═══════════════════════════════════════════════════════════════
# LearningFeedbackRouter
# ═══════════════════════════════════════════════════════════════


class LearningFeedbackRouter:
    """学习反馈路由器 — 自动分类并路由反馈.

    用法:
        router = LearningFeedbackRouter()
        feedback = router.route(
            outcome_measurement=measurement,
            cycle_number=3,
        )
    """

    def __init__(self) -> None:
        self._route_count: int = 0
        self._route_history: list[LearningFeedback] = []

    @property
    def route_count(self) -> int:
        return self._route_count

    # ── Public API ───────────────────────────────────────────────

    def route(
        self,
        outcome_measurement: Any,  # OutcomeMeasurement
        cycle_number: int = 0,
        effectiveness: Any = None,  # LearningEffectiveness
    ) -> LearningFeedback:
        """路由反馈 — 主入口.

        Args:
            outcome_measurement: OutcomeMeasurement 实例
            cycle_number: 编排周期编号
            effectiveness: LearningEffectiveness (可选)

        Returns:
            LearningFeedback
        """
        self._route_count += 1

        feedback = LearningFeedback.from_measurement(
            outcome=outcome_measurement,
            cycle_number=cycle_number,
            effectiveness=effectiveness,
        )

        self._route_history.append(feedback)
        return feedback

    def route_batch(
        self,
        measurements: list[tuple[Any, int]],  # [(OutcomeMeasurement, cycle_number)]
        effectiveness: Any = None,
    ) -> list[LearningFeedback]:
        """批量路由.

        Args:
            measurements: (OutcomeMeasurement, cycle_number) 列表
            effectiveness: LearningEffectiveness

        Returns:
            list[LearningFeedback]
        """
        return [
            self.route(outcome_measurement=om, cycle_number=cn, effectiveness=effectiveness)
            for om, cn in measurements
        ]

    # ── Query ────────────────────────────────────────────────────

    def get_history(self) -> list[LearningFeedback]:
        """获取路由历史."""
        return list(self._route_history)

    def get_latest(self) -> LearningFeedback | None:
        """获取最近一次路由."""
        if not self._route_history:
            return None
        return self._route_history[-1]

    def get_stats(self) -> dict[str, Any]:
        """获取路由统计."""
        if not self._route_history:
            return {
                "route_count": self._route_count,
                "good_count": 0,
                "bad_count": 0,
                "insufficient_count": 0,
                "stagnant_count": 0,
                "actionable_rate": 0.0,
            }

        good = sum(1 for f in self._route_history if f.is_good)
        bad = sum(1 for f in self._route_history if f.is_bad)
        insufficient = sum(1 for f in self._route_history if f.is_insufficient)
        stagnant = sum(1 for f in self._route_history if f.is_stagnant)
        actionable = sum(1 for f in self._route_history if f.is_actionable)

        return {
            "route_count": self._route_count,
            "good_count": good,
            "bad_count": bad,
            "insufficient_count": insufficient,
            "stagnant_count": stagnant,
            "actionable_rate": round(actionable / len(self._route_history), 4),
        }

    def reset(self) -> None:
        """重置路由器."""
        self._route_count = 0
        self._route_history = []

    def __repr__(self) -> str:
        return (
            f"LearningFeedbackRouter("
            f"routes={self._route_count})"
        )


__all__ = [
    "LearningFeedbackRouter",
]