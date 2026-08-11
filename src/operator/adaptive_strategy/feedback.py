"""P3.3.3 — Adaptive Strategy Feedback（薄封装 P3.3 反馈闭环）。

职责：
- 用 OutcomeEvaluator 把 SafeExecutionOutcome 折成 StrategyFeedback
- 折进 StrategyMemoryAdapter（apply_feedback + save）

零重算；不触碰 Provider。这是闭环的最后一环（Outcome → Memory → Strategy Update）。
"""
from __future__ import annotations

from typing import Any, Optional

from src.operator.strategy.evaluator import OutcomeEvaluator
from src.operator.strategy.memory import StrategyMemoryAdapter
from src.operator.strategy.models import StrategyFeedback, StrategyState


class AdaptiveStrategyFeedback:
    """执行结果 → 策略经验（闭环最后一环）。"""

    def __init__(
        self,
        memory: StrategyMemoryAdapter,
        evaluator: Optional[OutcomeEvaluator] = None,
    ) -> None:
        self.memory = memory
        self.evaluator = evaluator or OutcomeEvaluator()

    def evaluate(
        self,
        strategy_id: str,
        execution_outcome: Any,
        action_id: str = "",
    ) -> StrategyFeedback:
        """把一次 SafeExecutionOutcome 折成 StrategyFeedback（零重算）。"""
        return self.evaluator.evaluate(
            None,
            execution_result=execution_outcome,
            strategy_id=str(strategy_id),
            action_id=action_id or str(strategy_id),
        )

    def record(self, fb: StrategyFeedback) -> StrategyState:
        """折进策略经验并落盘。"""
        st = self.memory.apply_feedback(fb)
        self.memory.save()
        return st

    def process(
        self,
        strategy_id: str,
        execution_outcome: Any,
        action_id: str = "",
    ) -> StrategyFeedback:
        """evaluate + record 一步完成。"""
        fb = self.evaluate(strategy_id, execution_outcome, action_id=action_id)
        self.record(fb)
        return fb


__all__ = ["AdaptiveStrategyFeedback"]
