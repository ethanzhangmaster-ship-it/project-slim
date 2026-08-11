"""P3.3 — Strategy Loop 包（Strategy Feedback Controller）。

薄层编排：只读既有链路产物 + 维护 strategy-level 经验 + 产出策略调整建议。
不重算、不决策、不调 Provider、不直改生产。
"""
from .guard import GuardVerdict, StrategyGuard
from .loop import StrategyLoop, write_strategy_outputs
from .memory import DEFAULT_STRATEGIES, StrategyMemoryAdapter
from .models import (
    BusinessOutcome,
    StrategyFeedback,
    StrategyInsight,
    StrategyLoopResult,
    StrategyProposal,
    StrategyState,
    StrategyStatus,
)
from .mutation import SAFER_VARIANT, StrategyMutationEngine
from .evaluator import OutcomeEvaluator, evaluate

__all__ = [
    "StrategyStatus",
    "StrategyState",
    "BusinessOutcome",
    "StrategyFeedback",
    "StrategyProposal",
    "StrategyInsight",
    "StrategyLoopResult",
    "OutcomeEvaluator",
    "evaluate",
    "StrategyMemoryAdapter",
    "DEFAULT_STRATEGIES",
    "StrategyMutationEngine",
    "SAFER_VARIANT",
    "StrategyGuard",
    "GuardVerdict",
    "StrategyLoop",
    "write_strategy_outputs",
]
