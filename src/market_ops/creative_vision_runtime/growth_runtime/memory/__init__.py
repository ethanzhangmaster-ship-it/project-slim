"""E13.4 Growth Memory — 增长记忆模块.

将"决策→执行→结果"的经验闭环存储，从经验中挖掘可复用模式。

E13.4.1 Experience Store:
  - GrowthExperience: 经验数据模型
  - ExperienceStore: 经验存储与检索
  - MemoryRetriever: 记忆检索增强器

E13.4.2 Pattern Memory:
  - PatternMemory: 增长模式数据模型
  - PatternMiner: 模式挖掘器
  - PatternStore: 模式存储与检索

E13.4.3 Strategy Memory:
  - GrowthStrategyPattern: 增长策略数据模型
  - StrategyMemory: 策略提取、存储与推荐

E13.4.4 Failure Memory:
  - FailurePattern: 失败模式数据模型
  - FailureMemory: 失败记忆提取、风险检查与警告

E13.4.5 Memory Evolution:
  - MemoryEvolution: 记忆进化引擎 (合并、升级、衰减、知识图谱)
  - EvolutionEvent: 进化事件记录
  - KnowledgeGraph: 跨层知识图谱
  - EvolutionMetrics: 进化质量指标
  - EvolutionConfig: 进化参数配置

E13.6 Pattern Evolution:
  - PatternScorer: 多维度模式评分 (base + novelty + recency + quality + stability)
  - PatternDecayEngine: 时间衰减 + 市场条件敏感度
  - PatternReinforcer: 贝叶斯更新 + 重复验证增强
  - PatternConflictResolver: 冲突检测 + 上下文分裂
  - AdaptiveMemoryController: 进化编排 + 报告生成

E13.6 Pattern Feedback Loop:
  - PatternEvaluator: 模式有效性评估 (基于最近执行结果)
  - PatternRewardUpdater: 执行结果→奖励信号→更新模式性能
  - PatternLifecycleManager: 生命周期管理 (ACTIVE → DECAYING → ARCHIVED)

E13.6.5 Decision Memory Synchronization:
  - DecisionMemoryEvent: 决策执行结果→统一记忆事件
  - DecisionOutcomeBridge: 决策结果→记忆事件转换
  - PatternDecisionReconciler: 预测 vs 实际对齐
  - DecisionPatternSynchronizer: 双向同步编排
"""

from .experience_store import ExperienceStore
from .evolution_models import (
    ConsolidationResult,
    EvolutionConfig,
    EvolutionEvent,
    EvolutionEventType,
    EvolutionMetrics,
    EvolutionTarget,
    KnowledgeGraph,
)
from .failure_memory import FailureMemory
from .failure_models import (
    FailureCategory,
    FailureCondition,
    FailurePattern,
    FailureQuery,
    FailureSeverity,
    FailureStats,
    FailureWarning,
)
from .memory_retriever import MemoryRetriever
from .memory_evolution import MemoryEvolution
from .models import (
    ExperienceCategory,
    ExperienceContext,
    ExperienceOutcome,
    ExperienceOutcomeLevel,
    ExperienceQuery,
    ExperienceStats,
    GrowthExperience,
    PatternAction,
    PatternCondition,
    PatternMemory,
    PatternMiningDimension,
    PatternPerformance,
    PatternQuality,
    PatternQuery,
    PatternStats,
)
from .decision_sync import (
    BridgeResult,
    DecisionMemoryEvent,
    DecisionOutcomeBridge,
    DecisionPatternSynchronizer,
    PatternDecisionReconciler,
    PredictionGap,
    ReconciliationAction,
    ReconciliationResult,
    SyncEventType,
    SyncResult,
)
from .decision_pattern_sync import (
    DecisionPatternExtractor,
    DecisionPatternSync,
    ExtractionResult,
)
from .pattern_evolution import (
    AdaptiveMemoryController,
    ConflictPair,
    ConflictResolution,
    DecayResult,
    EvolutionReport,
    PatternConflictResolver,
    PatternDecayEngine,
    PatternReinforcer,
    PatternScore,
    PatternScorer,
    ReinforcementResult,
)
from .pattern_feedback import (
    EvaluationResult,
    LifecycleReport,
    LifecycleTransition,
    PatternEffectiveness,
    PatternEvaluator,
    PatternLifecycleManager,
    PatternLifecycleState,
    PatternRewardUpdater,
    RewardSignal,
    RewardUpdateResult,
)
from .pattern_miner import PatternMiner
from .pattern_store import PatternStore
from .strategy_memory import StrategyMemory
from .strategy_models import (
    GrowthStrategyPattern,
    StrategyCategory,
    StrategyPerformance,
    StrategyQuality,
    StrategyQuery,
    StrategyStats,
    StrategyStep,
    StrategyTriggerCondition,
)

__all__ = [
    # E13.4.1 Core
    "ExperienceStore",
    "MemoryRetriever",
    # E13.4.1 Models
    "GrowthExperience",
    "ExperienceContext",
    "ExperienceOutcome",
    "ExperienceQuery",
    "ExperienceStats",
    # E13.4.1 Enums
    "ExperienceCategory",
    "ExperienceOutcomeLevel",
    # E13.4.2 Core
    "PatternMiner",
    "PatternStore",
    # E13.4.2 Models
    "PatternMemory",
    "PatternCondition",
    "PatternAction",
    "PatternPerformance",
    "PatternQuery",
    "PatternStats",
    # E13.4.2 Enums
    "PatternMiningDimension",
    "PatternQuality",
    # E13.4.3 Core
    "StrategyMemory",
    # E13.4.3 Models
    "GrowthStrategyPattern",
    "StrategyTriggerCondition",
    "StrategyStep",
    "StrategyPerformance",
    "StrategyQuery",
    "StrategyStats",
    # E13.4.3 Enums
    "StrategyCategory",
    "StrategyQuality",
    # E13.4.4 Core
    "FailureMemory",
    # E13.4.4 Models
    "FailurePattern",
    "FailureCondition",
    "FailureWarning",
    "FailureQuery",
    "FailureStats",
    # E13.4.4 Enums
    "FailureSeverity",
    "FailureCategory",
    # E13.4.5 Core
    "MemoryEvolution",
    # E13.4.5 Models
    "EvolutionEvent",
    "ConsolidationResult",
    "KnowledgeGraph",
    "EvolutionMetrics",
    "EvolutionConfig",
    # E13.4.5 Enums
    "EvolutionEventType",
    "EvolutionTarget",
    # E13.6 Core
    "PatternScorer",
    "PatternDecayEngine",
    "PatternReinforcer",
    "PatternConflictResolver",
    "AdaptiveMemoryController",
    # E13.6 Models
    "PatternScore",
    "DecayResult",
    "ReinforcementResult",
    "ConflictPair",
    "ConflictResolution",
    "EvolutionReport",
    # E13.6 Pattern Feedback
    "PatternEvaluator",
    "PatternRewardUpdater",
    "PatternLifecycleManager",
    # E13.6 Feedback Models
    "EvaluationResult",
    "RewardSignal",
    "RewardUpdateResult",
    "LifecycleTransition",
    "LifecycleReport",
    # E13.6 Feedback Enums
    "PatternEffectiveness",
    "PatternLifecycleState",
    # E13.6.5 Decision Memory Synchronization
    "DecisionMemoryEvent",
    "DecisionOutcomeBridge",
    "PatternDecisionReconciler",
    "DecisionPatternSynchronizer",
    # E13.6.5 Models
    "BridgeResult",
    "PredictionGap",
    "ReconciliationAction",
    "ReconciliationResult",
    "SyncResult",
    # E13.6.5 Enums
    "SyncEventType",
    # E13.6.5 Decision → Pattern
    "DecisionPatternExtractor",
    "DecisionPatternSync",
    "ExtractionResult",
]