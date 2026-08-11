"""E15.2.3 Action Selection Engine — 动作选择引擎.

Autonomous Execution Intelligence 的决策中枢，在 Planner 生成多个候选动作、
Risk Engine 给出风险评估后，自动选择最优执行动作。

模块:
  - models.py:     核心数据模型
  - scoring.py:    加权评分引擎
  - selector.py:   动作选择器主类
  - explanation.py: 可解释性层
"""

from .explanation import DecisionExplainer
from .models import (
    ActionCandidate,
    ScoredCandidate,
    SelectedAction,
    SelectionResult,
    SelectionStatus,
)
from .scoring import ScoringEngine, ScoringWeights
from .selector import ActionSelector

__all__ = [
    # Models
    "SelectionStatus",
    "ActionCandidate",
    "ScoredCandidate",
    "SelectedAction",
    "SelectionResult",
    # Scoring
    "ScoringWeights",
    "ScoringEngine",
    # Selector
    "ActionSelector",
    # Explanation
    "DecisionExplainer",
]