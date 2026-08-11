"""E12.4 — Reality Feedback Layer。

将 E12.3 Prediction 输出接入 E11 Evolution Loop，
建立 Reality → Decision → Action → Experiment → Learning 的完整闭环。

模块:
  Phase 1:
    - models:              反馈数据模型
    - trigger_rules:       安全阈值引擎
    - action_mapper:       信号 → E11 行动映射
    - feedback_controller: 核心编排器
    - learning_feedback:   闭环学习（预测 vs 实际）

  Phase 2:
    - mutation_request_builder: 信号 → MutationIntent → MutationRequest
    - experiment_trigger:       confidence/spend/cooldown 安全检查
    - experiment_monitor:       6 阶段实验生命周期
    - result_evaluator:         旧 vs 新对比，赢家检测
    - learning_feedback:        EvolutionLearningRecord 升级
"""

from .models import (
    # Phase 1
    FeedbackSignalType,
    PredictionOutcome,
    RealityFeedbackSignal,
    # Phase 2
    EvolutionLearningRecord,
    ExperimentEvaluation,
    ExperimentRun,
    ExperimentStatus,
    MutationIntent,
    MutationRequest,
)
from .trigger_rules import TriggerRules, TriggerThresholds
from .action_mapper import ActionMapper
from .feedback_controller import FeedbackController, FeedbackResult
from .learning_feedback import LearningFeedback, PredictionAccuracy
from .mutation_request_builder import MutationRequestBuilder
from .experiment_trigger import ExperimentTrigger, ExperimentTriggerResult
from .experiment_monitor import ExperimentMonitor
from .result_evaluator import ResultEvaluator

__all__ = [
    # Phase 1
    "FeedbackSignalType",
    "RealityFeedbackSignal",
    "PredictionOutcome",
    "TriggerThresholds",
    "TriggerRules",
    "ActionMapper",
    "FeedbackController",
    "FeedbackResult",
    "LearningFeedback",
    "PredictionAccuracy",
    # Phase 2
    "MutationIntent",
    "MutationRequest",
    "EvolutionLearningRecord",
    "ExperimentStatus",
    "ExperimentRun",
    "ExperimentEvaluation",
    "MutationRequestBuilder",
    "ExperimentTrigger",
    "ExperimentTriggerResult",
    "ExperimentMonitor",
    "ResultEvaluator",
]