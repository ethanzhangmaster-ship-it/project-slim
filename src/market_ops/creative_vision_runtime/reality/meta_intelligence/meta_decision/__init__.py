"""E12.6.1 — Meta Decision Engine。

Meta Decision Engine 是 Growth Intelligence 的决策大脑。

模块:
  - models:             MetaDecisionType, DecisionContext, MetaDecision
  - decision_policy:    7 条决策规则
  - decision_engine:    核心决策引擎（评估 + 排序 + 风险检查）
  - decision_explainer: 决策解释生成器
"""

from .models import (
    DecisionContext,
    MetaDecision,
    MetaDecisionType,
    get_decision_priority,
)
from .decision_policy import (
    ContinueEvolutionRule,
    DecisionPolicy,
    ExperimentFailureRule,
    FatigueRule,
    InsufficientDataRule,
    PopulationDegradationRule,
    RoasGrowthRule,
    RollbackRule,
    DEFAULT_POLICIES,
)
from .decision_engine import MetaDecisionEngine
from .decision_explainer import DecisionExplainer

__all__ = [
    # Models
    "MetaDecisionType",
    "DecisionContext",
    "MetaDecision",
    "get_decision_priority",
    # Policies
    "DecisionPolicy",
    "FatigueRule",
    "RoasGrowthRule",
    "ExperimentFailureRule",
    "InsufficientDataRule",
    "PopulationDegradationRule",
    "ContinueEvolutionRule",
    "RollbackRule",
    "DEFAULT_POLICIES",
    # Engine
    "MetaDecisionEngine",
    "DecisionExplainer",
]