"""E13.7.4 Decision Learning Loop — 数据模型导出.

向后兼容:
  原 models.py 迁移至 models/_legacy.py，通过本 __init__.py 保持原有导出不变。

Day 7.4.3 新增模型 (通过 learning_models 子模块访问):
  - LearningOutcome       — 执行结果
  - LearningExperience    — 统一学习事件 (Day 7.4 版本)
  - RewardWeights         — 可配置奖励权重
  - LearningReward        — 统一奖励
  - AttributionEvidence   — 归因证据
  - AttributionResult     — 归因分解
  - LearningResult        — 学习闭环输出 (Day 7.4 版本)
  - create_learning_experience — 工厂函数

用法:
  # 旧模型 (E15.3.5)
  from growth_runtime.intelligence.learning.models import LearningExperience, LearningResult

  # 新模型 (Day 7.4)
  from growth_runtime.intelligence.learning.models.learning_models import (
      LearningExperience as Day74LearningExperience,
      LearningResult as Day74LearningResult,
      LearningReward,
      AttributionResult,
  )
"""

# ── 旧模型 (E15.3.5) — 保持向后兼容 ──
from ._legacy import (
    ExperienceQuality,
    ExperienceQualityLevel,
    InsightType,
    LearnedPattern,
    LearningExperience,
    LearningInsight,
    LearningResult,
    PatternEvolution,
    PatternStatus,
    StrategyRecommendation,
)

# ── 新模型 (Day 7.4) — 无冲突名称 ──
from .learning_models import (
    AttributionEvidence,
    AttributionResult,
    LearningOutcome,
    LearningReward,
    RewardWeights,
    create_learning_experience,
)

# ── 新模型 (Day 7.5) — 知识模型 ──
from .learning_models import (
    DecisionLearningResult,
    LearnedPattern as Day75LearnedPattern,
    LearningCycleResult,
    LearningKnowledge,
    PatternPrediction,
    RiskSignal,
    StrategyInsight,
)

# ── 新模型 (Day 7.7) — 学习策略控制平面 ──
from .learning_strategy_models import (
    AdjustmentSource,
    LearningAdjustment,
    LearningMode,
    LearningPolicyDecision,
    LearningStrategyState,
    PolicyAction,
    PolicyPriority,
)

# ── 新模型 (Day 7.7.3) — 自适应置信度 ──
from .adaptive_confidence_models import (
    AdaptiveConfidenceResult,
    ConfidenceDimension,
    ConfidenceRecord,
)

# ── 新模型 (Day 7.7.5) — 策略执行协议 ──
from .learning_execution_models import (
    LearningExecutionAction,
    LearningExecutionContext,
    LearningExecutionResult,
)

# ── 新模型 (Day 7.8) — 学习循环编排协议 ──
from .learning_orchestration_models import (
    CycleOrchestrationState,
    OrchestrationCycleResult,
    OrchestratorConfig,
)

# ── 新模型 (Day 7.8 Step 3) — 执行结果测量协议 ──
from .outcome_measurement_models import (
    MeasurementContext,
    OutcomeMeasurement,
)

# ── 新模型 (Day 7.8 Step 4) — 学习反馈协议 ──
from .learning_feedback_models import (
    FeedbackAction,
    FeedbackClassification,
    LearningFeedback,
)

__all__ = [
    # Legacy (E15.3.5)
    "PatternStatus",
    "InsightType",
    "ExperienceQualityLevel",
    "ExperienceQuality",
    "LearningExperience",
    "LearnedPattern",
    "PatternEvolution",
    "LearningInsight",
    "StrategyRecommendation",
    "LearningResult",
    # Day 7.4 (new, no name conflict)
    "LearningOutcome",
    "RewardWeights",
    "LearningReward",
    "AttributionEvidence",
    "AttributionResult",
    "create_learning_experience",
    # Day 7.5 (new, aliased to avoid conflict with legacy LearnedPattern)
    "Day75LearnedPattern",
    "LearningKnowledge",
    "RiskSignal",
    "StrategyInsight",
    # Day 7.5.2-7.5.4
    "PatternPrediction",
    "DecisionLearningResult",
    "LearningCycleResult",
    # Day 7.7 (Learning Strategy Control Plane)
    "LearningMode",
    "PolicyAction",
    "AdjustmentSource",
    "PolicyPriority",
    "LearningStrategyState",
    "LearningAdjustment",
    "LearningPolicyDecision",
    # Day 7.7.3 (Adaptive Confidence)
    "ConfidenceDimension",
    "ConfidenceRecord",
    "AdaptiveConfidenceResult",
    # Day 7.7.5 (Execution Protocol)
    "LearningExecutionAction",
    "LearningExecutionContext",
    "LearningExecutionResult",
    # Day 7.8 (Learning Orchestration)
    "CycleOrchestrationState",
    "OrchestratorConfig",
    "OrchestrationCycleResult",
    # Day 7.8 Step 3 (Outcome Measurement)
    "MeasurementContext",
    "OutcomeMeasurement",
    # Day 7.8 Step 4 (Feedback Protocol)
    "FeedbackClassification",
    "FeedbackAction",
    "LearningFeedback",
]