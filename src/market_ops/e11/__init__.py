"""E11 Creative Growth Evolution Layer — 创意增长进化层。

E11 建立在 E10.2 执行基础设施之上，提供创意进化的核心能力：

E11.1 — Creative Genome Foundation
  - CreativeGenome: 可进化创意遗传单位
  - GenomeManager: 生命周期管理
  - DNAMapper: DNA → Genome 转换
  - GenomeRepository: 持久化存储

E11.2 — Mutation Engine
  - MutationType: REPLACE/COMBINE/ENHANCE/REMOVE
  - MutationOperator: 四种变异操作
  - StrategyLayer: 自动策略选择

E11.3 — Evolution
  - Fitness & Evaluation Foundation
  - Population Manager
  - Selection Layer

E11.4 — Evolution Orchestrator
  - EvolutionOrchestrator: 单代/多代循环调度
  - Convergence Detector: 收敛检测
  - Checkpoint: 断点保存/恢复

E11.5 — Market Feedback
  - PerformanceFeedback: IAP 产品统一反馈
  - UA / IAP / Analytics Adapters
  - FeedbackRepository
  - MarketSignal: 市场信号
  - MarketSignalProcessor: 信号处理器
  - FeedbackLoop: 闭环进化控制器

E11.6 — IAP Reality Integration
  - RevenueEvent: 单笔收入事件
  - UserValueProfile: 用户生命周期价值
  - RevenueSummary: Genome 聚合收入
  - AttributionSource: 归因来源

与 E10.2 接口：
  E11 输出 ExecutionTask → E10.2 执行
  E10.2 返回 LearningSignal → E11 学习
"""

from .genome.schema import (
    CreativeGenome,
    Gene,
    GenomeLineage,
    GENE_SLOTS,
)
from .genome.genome_manager import GenomeManager
from .genome.dna_mapper import DNAMapper
from .genome.exceptions import (
    GenomeError,
    GenomeNotFoundError,
    GenomeDuplicateError,
    GenomeValidationError,
    DNAMappingError,
    GenomeRepositoryError,
)
from .storage.genome_repository import GenomeRepository
from .mutation import (
    MutationType,
    MutationTarget,
    MutationRule,
    MutationResult,
    MutationHistory,
)
from .evolution import (
    FitnessDirection,
    FitnessMetric,
    FitnessScore,
    FitnessSnapshot,
    EvaluationResult,
    # E11.4
    EvolutionStatus,
    EvolutionConfig,
    EvolutionRun,
    GenerationResult,
    EvolutionResult,
    EvolutionOrchestrator,
    # E11.4.2
    GenerationStatus,
    GenerationRecord,
    EvolutionHistory,
    GenerationManager,
    EvolutionHistoryRecorder,
    ConvergenceConfig,
    ConvergenceDetector,
    CheckpointRecord,
    CheckpointManager,
)
from .market import (
    UAMetrics,
    EngagementMetrics,
    IAPMetrics,
    PerformanceFeedback,
    PerformanceAdapter,
    UAPerformanceAdapter,
    IAPPerformanceAdapter,
    AnalyticsPerformanceAdapter,
    FeedbackRepository,
    MarketError,
    MarketAdapterError,
    InvalidMetricsError,
    RepositoryError,
    SignalType,
    SignalStrength,
    MarketSignal,
    MarketSignalProcessor,
    GenomeFitness,
    FitnessHistoryEntry,
    FitnessHistory,
    FitnessCalculator,
    FitnessEngine,
    LoopStatus,
    EvolutionFeedbackEvent,
    FeedbackLoopState,
    EvolutionEventStore,
    EvolutionBridge,
    FeedbackLoopController,
)
from .reality import (
    AttributionSource,
    PayerType,
    RevenueEvent,
    UserValueProfile,
    RevenueSummary,
    AdjustRawEvent,
    RevenueType,
    AdjustAdapter,
    AdjustCreativeMapper,
    CreativeRevenueAttribution,
    GeneRevenueImpact,
    GenomeAttributionResult,
    GenomeAttributor,
    DNARevenueAnalyzer,
    AttributionRepository,
    ROASProfile,
    RetentionProfile,
    RevenueFitnessProfile,
    CalibratedFitness,
    FitnessWeights,
    RevenueFitnessCalculator,
    FitnessCalibrator,
)

__all__ = [
    # Schema
    "CreativeGenome",
    "Gene",
    "GenomeLineage",
    "GENE_SLOTS",
    # Manager
    "GenomeManager",
    # Mapper
    "DNAMapper",
    # Repository
    "GenomeRepository",
    # Exceptions
    "GenomeError",
    "GenomeNotFoundError",
    "GenomeDuplicateError",
    "GenomeValidationError",
    "DNAMappingError",
    "GenomeRepositoryError",
    # E11.2 Mutation
    "MutationType",
    "MutationTarget",
    "MutationRule",
    "MutationResult",
    "MutationHistory",
    # E11.3 Evolution
    "FitnessDirection",
    "FitnessMetric",
    "FitnessScore",
    "FitnessSnapshot",
    "EvaluationResult",
    # E11.4 Orchestrator
    "EvolutionStatus",
    "EvolutionConfig",
    "EvolutionRun",
    "GenerationResult",
    "EvolutionResult",
    "EvolutionOrchestrator",
    # E11.4.2 Multi Generation
    "GenerationStatus",
    "GenerationRecord",
    "EvolutionHistory",
    "GenerationManager",
    "EvolutionHistoryRecorder",
    "ConvergenceConfig",
    "ConvergenceDetector",
    "CheckpointRecord",
    "CheckpointManager",
    # E11.5 Market
    "UAMetrics",
    "EngagementMetrics",
    "IAPMetrics",
    "PerformanceFeedback",
    "PerformanceAdapter",
    "UAPerformanceAdapter",
    "IAPPerformanceAdapter",
    "AnalyticsPerformanceAdapter",
    "FeedbackRepository",
    "MarketError",
    "MarketAdapterError",
    "InvalidMetricsError",
    "RepositoryError",
    # E11.5.2 Signal
    "SignalType",
    "SignalStrength",
    "MarketSignal",
    "MarketSignalProcessor",
    # E11.5.3 Fitness
    "GenomeFitness",
    "FitnessHistoryEntry",
    "FitnessHistory",
    "FitnessCalculator",
    "FitnessEngine",
    # E11.5.4 Feedback Loop
    "LoopStatus",
    "EvolutionFeedbackEvent",
    "FeedbackLoopState",
    "EvolutionEventStore",
    "EvolutionBridge",
    "FeedbackLoopController",
    # E11.6 Reality
    "AttributionSource",
    "PayerType",
    "RevenueEvent",
    "UserValueProfile",
    "RevenueSummary",
    # E11.6.2 Adjust
    "AdjustRawEvent",
    "RevenueType",
    "AdjustAdapter",
    "AdjustCreativeMapper",
    # E11.6.3 Attribution
    "CreativeRevenueAttribution",
    "GeneRevenueImpact",
    "GenomeAttributionResult",
    "GenomeAttributor",
    "DNARevenueAnalyzer",
    "AttributionRepository",
    # E11.6.4 Fitness Calibration
    "ROASProfile",
    "RetentionProfile",
    "RevenueFitnessProfile",
    "CalibratedFitness",
    "FitnessWeights",
    "RevenueFitnessCalculator",
    "FitnessCalibrator",
]