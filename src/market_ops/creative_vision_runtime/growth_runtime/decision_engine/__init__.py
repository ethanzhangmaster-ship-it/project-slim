"""E13.3 Growth Decision Engine — 增长决策引擎模块.

将 E13.2 的"事实数据"转换为可决策的信号、可执行的机会和具体执行动作.

核心组件:
  E13.3.1 Signal Engine:
    - GrowthSignalEngine: 信号引擎
    - GrowthSignal: 信号数据模型
    - SignalType: 信号类型枚举

  E13.3.2 Opportunity Engine:
    - GrowthOpportunityEngine: 机会引擎
    - GrowthOpportunity: 机会数据模型
    - OpportunityType: 机会类型枚举

  E13.3.3 Decision Executor:
    - GrowthDecisionExecutor: 决策执行器
    - ExecutionAction: 执行动作数据模型
    - ExecutionResult: 执行结果数据模型
"""

from .decision_executor import GrowthDecisionExecutor
from .models import (
    ApprovalLevel,
    ExecutionAction,
    ExecutionActionType,
    ExecutionBatch,
    ExecutionResult,
    ExecutionStatus,
    GrowthOpportunity,
    GrowthSignal,
    OpportunityBatch,
    OpportunityPriority,
    OpportunityStatus,
    OpportunityType,
    OPPORTUNITY_TO_ACTION_MAP,
    SignalBatch,
    SignalCategory,
    SignalContext,
    SignalSeverity,
    SignalType,
    SIGNAL_CATEGORY_MAP,
    SIGNAL_TO_OPPORTUNITY_MAP,
)
from .opportunity_engine import GrowthOpportunityEngine
from .signal_engine import GrowthSignalEngine

__all__ = [
    # Engines
    "GrowthSignalEngine",
    "GrowthOpportunityEngine",
    "GrowthDecisionExecutor",
    # Signal Models
    "GrowthSignal",
    "SignalBatch",
    "SignalContext",
    # Opportunity Models
    "GrowthOpportunity",
    "OpportunityBatch",
    # Execution Models
    "ExecutionAction",
    "ExecutionResult",
    "ExecutionBatch",
    # Signal Enums
    "SignalType",
    "SignalSeverity",
    "SignalCategory",
    # Opportunity Enums
    "OpportunityType",
    "OpportunityPriority",
    "OpportunityStatus",
    # Execution Enums
    "ExecutionActionType",
    "ExecutionStatus",
    "ApprovalLevel",
    # Mappings
    "SIGNAL_CATEGORY_MAP",
    "SIGNAL_TO_OPPORTUNITY_MAP",
    "OPPORTUNITY_TO_ACTION_MAP",
]