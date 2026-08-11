"""P3.3.3 — Adaptive Strategy（Strategy Proposal 的生产级落地闭环）。

把 P3.3 的 StrategyProposal 真正闭环成：
    Proposal → Simulation → Approval → Execution → Outcome → Memory → Strategy Update

全部薄层复用 E17.3 / E17.8 / P2.1 / P2.2 / P2.3 / P2.4 / P3.3，不重写执行链。
"""
from __future__ import annotations

from .controller import (
    AdaptiveStrategyController,
    build_adaptive_strategy_engine,
)
from .feedback import AdaptiveStrategyFeedback
from .models import (
    AdaptiveAction,
    AdaptiveStrategyRequest,
    AdaptiveStrategyResult,
    AdaptiveStrategyTemplate,
    FinalStatus,
    Stage,
)
from .planner import (
    AdaptiveStrategyPlanner,
    DEFAULT_TEMPLATES,
    PlannedAction,
    UnknownStrategyError,
)
from .simulator import AdaptiveStrategySimulator


__all__ = [
    # models
    "AdaptiveAction",
    "Stage",
    "FinalStatus",
    "AdaptiveStrategyTemplate",
    "AdaptiveStrategyRequest",
    "AdaptiveStrategyResult",
    # planner
    "AdaptiveStrategyPlanner",
    "DEFAULT_TEMPLATES",
    "PlannedAction",
    "UnknownStrategyError",
    # simulator
    "AdaptiveStrategySimulator",
    # feedback
    "AdaptiveStrategyFeedback",
    # controller
    "AdaptiveStrategyController",
    "build_adaptive_strategy_engine",
]
