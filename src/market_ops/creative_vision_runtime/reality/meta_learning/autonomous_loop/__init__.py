"""E12.5.5 — Autonomous Meta Learning Loop。

E12 Meta Learning Layer 的最终闭环层，实现自我学习循环。

模块:
  - models:                   MetaLearningCycle, LearningSchedule, StrategyFeedback
  - cycle_manager:            学习周期生命周期管理
  - learning_scheduler:       学习触发条件判断
  - knowledge_updater:        Bayesian 知识更新
  - strategy_feedback:        策略反馈收集与评分更新
  - meta_learning_controller: 核心编排器
"""

from .models import (
    KnowledgeUpdate,
    LearningSchedule,
    LearningSummary,
    LearningTrigger,
    LoopMetrics,
    MetaCycleStatus,
    MetaLearningCycle,
    MetaLearningResult,
    StrategyFeedback,
    TriggerReason,
)
from .cycle_manager import CycleManager
from .learning_scheduler import LearningScheduler
from .knowledge_updater import KnowledgeUpdater
from .strategy_feedback import StrategyFeedbackCollector
from .meta_learning_controller import MetaLearningController

__all__ = [
    # Models
    "MetaCycleStatus",
    "TriggerReason",
    "MetaLearningCycle",
    "LearningSchedule",
    "LearningTrigger",
    "StrategyFeedback",
    "KnowledgeUpdate",
    "LearningSummary",
    "LoopMetrics",
    "MetaLearningResult",
    # Engines
    "CycleManager",
    "LearningScheduler",
    "KnowledgeUpdater",
    "StrategyFeedbackCollector",
    "MetaLearningController",
]