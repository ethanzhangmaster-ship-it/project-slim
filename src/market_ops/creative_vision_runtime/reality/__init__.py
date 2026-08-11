"""E12 Reality Integration Layer。

将 E11 Autonomous Evolution Controller 接入真实 UA 数据、真实收入、
真实广告资产、真实市场反馈。

分层架构：
  RealityDataHub (统一入口)
       │
  ┌────┴────┐
  ▼         ▼
MetaAdsReality   AdjustReality
(门面层)         (门面层)
  │              │
  ▼              ▼
FacebookAdsAdapter  AdjustTracker
(execution_runtime)  (execution_runtime)

核心模块：
  - models:             统一现实数据模型
  - meta_ads_reality:   Meta Ads 门面层
  - adjust_reality:     Adjust 门面层
  - reality_data_hub:   统一入口（E11 消费端）
  - feedback_bridge:    Reality → E11 Feedback 转换器
"""

from .models import (
    AdPerformanceRecord,
    CampaignReality,
    CreativeReality,
    ProductBehaviorRecord,
    RealitySnapshot,
    RealitySource,
    RevenuePerformance,
)
from .meta_ads_reality import MetaAdsReality
from .adjust_reality import AdjustReality
from .thinkingdata_reality import ThinkingDataReality
from .reality_data_hub import RealityDataHub
from .feedback_bridge import RealityFeedbackBridge

# E12.2 Intelligence
from .analyzers import (
    AnomalyDetector,
    FatigueDetector,
    PerformanceAnalyzer,
)
from .intelligence import (
    AnomalyInsight,
    CombinedInsight,
    ConfidenceEngine,
    FatigueInsight,
    InsightEngine,
    InsightType,
    PerformanceInsight,
    RealityInsight,
    RecommendationEngine,
    SeverityLevel,
    TrendInsight,
)
from .insight_bridge import InsightBridge

# E12.3 Prediction
from .prediction import (
    CreativeLifecycleStage,
    DecayPrediction,
    DecayPredictor,
    ExplanationEngine,
    FatiguePredictor,
    LifecyclePrediction,
    LifecyclePredictor,
    PredictionConfidence,
    PredictionConfidenceEngine,
    PredictionEngine,
    PredictionExplanation,
    PredictionResult,
    PredictionType,
    RealityHistoryPoint,
    RealityPrediction,
    RiskLevel,
    ROASPredictor,
)

# E12.4 Feedback
from .feedback import (
    ActionMapper,
    EvolutionLearningRecord,
    ExperimentEvaluation,
    ExperimentMonitor,
    ExperimentRun,
    ExperimentStatus,
    ExperimentTrigger,
    ExperimentTriggerResult,
    FeedbackController,
    FeedbackResult,
    FeedbackSignalType,
    LearningFeedback,
    MutationIntent,
    MutationRequest,
    MutationRequestBuilder,
    PredictionAccuracy,
    PredictionOutcome,
    RealityFeedbackSignal,
    ResultEvaluator,
    TriggerRules,
    TriggerThresholds,
)

# E12.5 Meta Learning
from .meta_learning import (
    ContextDetail,
    ExperienceCollector,
    ExperienceOutcome,
    ExperiencePattern,
    ExperienceQuery,
    ExperienceRecord,
    ExperienceResult,
    ExperienceStats,
    ExperienceStore,
    ExperimentDetail,
    GeneCategory,
    MutationDetail,
    MutationType,
)

__all__ = [
    # E12.1 Models
    "RealitySource",
    "AdPerformanceRecord",
    "RevenuePerformance",
    "ProductBehaviorRecord",
    "CampaignReality",
    "CreativeReality",
    "RealitySnapshot",
    # E12.1 Engines
    "MetaAdsReality",
    "AdjustReality",
    "ThinkingDataReality",
    "RealityDataHub",
    "RealityFeedbackBridge",
    # E12.2 Models
    "InsightType",
    "SeverityLevel",
    "RealityInsight",
    "PerformanceInsight",
    "FatigueInsight",
    "AnomalyInsight",
    "TrendInsight",
    "CombinedInsight",
    # E12.2 Analyzers
    "PerformanceAnalyzer",
    "FatigueDetector",
    "AnomalyDetector",
    # E12.2 Intelligence
    "ConfidenceEngine",
    "RecommendationEngine",
    "InsightEngine",
    # E12.2 Bridge
    "InsightBridge",
    # E12.3 Prediction
    "PredictionType",
    "RiskLevel",
    "RealityHistoryPoint",
    "RealityPrediction",
    "FatiguePredictor",
    "ROASPredictor",
    "PredictionEngine",
    "PredictionResult",
    # E12.3 Phase 2
    "CreativeLifecycleStage",
    "LifecyclePrediction",
    "DecayPrediction",
    "PredictionConfidence",
    "PredictionExplanation",
    "LifecyclePredictor",
    "DecayPredictor",
    "PredictionConfidenceEngine",
    "ExplanationEngine",
    # E12.4 Feedback
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
    # E12.4 Phase 2
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
    # E12.5 Meta Learning
    "ExperienceOutcome",
    "GeneCategory",
    "MutationType",
    "MutationDetail",
    "ExperimentDetail",
    "ContextDetail",
    "ExperienceResult",
    "ExperienceRecord",
    "ExperienceQuery",
    "ExperienceStats",
    "ExperiencePattern",
    "ExperienceStore",
    "ExperienceCollector",
]