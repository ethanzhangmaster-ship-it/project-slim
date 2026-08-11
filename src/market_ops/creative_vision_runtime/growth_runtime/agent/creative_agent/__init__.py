"""E14.4 Creative Agent — 创意智能 Agent.

Creative Agent 是多 Agent 组织中的专业 Agent，负责 Creative Intelligence 的全链路决策:

核心模块:
  1. analyzer: CreativeAnalyzer — 创意表现分析 (疲劳/赢家/潜力)
  2. dna_engine: DNAEngine — Creative DNA 提取与理解 (7基因体系)
  3. memory: CreativeMemory — 创意经验记忆 (决策历史/DNA记忆)
  4. creative_agent: CreativeAgent — Agent 核心 (整合所有模块)

E14.4.2 策略模块:
  5. opportunity: CreativeOpportunityEngine — 创意机会识别 (UA Signal → Opportunity)
  6. strategy: CreativeStrategyEngine — 创意策略生成 (Opportunity → Strategy)
  7. planner: CreativePlanner — 创意执行规划 (Strategy → Plan)
  8. evaluator: CreativeEvaluator — 策略评估反馈 (Strategy → Outcome)

E14.4.3 执行模块:
  9. executor: CreativeExecutor — 执行层 (Plan → Action)
  10. generator_bridge: GeneratorBridge — 连接 E11 (Generate Variants)
  11. experiment: ExperimentManager — 实验管理 (Experiment Lifecycle)
  12. rollout: RolloutController — 自动放量 (Winner → Scale)

与 E11 的互补关系:
  - E14.4: 决策层 + 执行层 (大脑 + 双手)
  - E11: 进化层 (创意进化器) — Genome/Mutation/CLIP

典型用法:
    from creative_agent import (
        CreativeAgent, CreativeAnalyzer, DNAEngine, CreativeMemory,
        CreativeOpportunityEngine, CreativeStrategyEngine, CreativePlanner, CreativeEvaluator,
        CreativeExecutor, GeneratorBridge, ExperimentManager, RolloutController,
        CreativeMetrics, CreativeDiagnosis, CreativeDiagnosisType,
        CreativeDNAProfile, CreativeGene, DNAComparisonResult,
        create_creative_agent,
    )

    # 完整策略+执行管道
    agent = create_creative_agent()

    # 1. UA 信号 → 机会
    opportunities = agent.detect_opportunities([
        {"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.91}
    ])

    # 2. 机会 → 策略
    strategies = agent.generate_strategies(opportunities.opportunities)

    # 3. 策略 → 执行计划
    batch = agent.plan_creative_batch(strategies.strategies)

    # 4. Plan → Action
    actions = agent.create_actions_from_batch(batch.plans)

    # 5. Generate → Experiment → Rollout
    pipeline = agent.run_full_execution_pipeline(batch.plans, strategy_map, dna_map)
"""

from .analyzer import (
    CreativeAnalyzer,
    CreativeMetrics,
    CreativeDiagnosis,
    CreativeDiagnosisType,
    CreativeDiagnosisSeverity,
    CreativeAnalysisReport,
    CreativeThresholds,
    DEFAULT_CREATIVE_THRESHOLDS,
    create_creative_analyzer,
)

from .dna_engine import (
    DNAEngine,
    CreativeDNAProfile,
    CreativeGene,
    DNAComparisonResult,
    WinnerDNAReport,
    HookType,
    VisualStyle,
    EmotionType,
    GameplayFocus,
    MonetizationType,
    AudienceType,
    ContextType,
    create_dna_engine,
)

from .memory import (
    CreativeMemory,
    CreativeDecisionRecord,
    CreativeDecisionOutcome,
    CreativeActionType,
    CreativeExperienceEntry,
    CreativeDNAMemoryEntry,
    create_creative_memory,
)

from .creative_agent import (
    CreativeAgent,
    CreativeAgentState,
    CreativeRecommendation,
    CreativeReport,
    create_creative_agent,
)

from .opportunity import (
    CreativeOpportunityEngine,
    CreativeOpportunity,
    CreativeOpportunityType,
    CreativeSignal,
    OpportunityPriority,
    OpportunityReport,
    create_opportunity_engine,
)

from .strategy import (
    CreativeStrategyEngine,
    CreativeStrategy,
    CreativeStrategyType,
    GeneMutation,
    GeneMutationAction,
    StrategyReport,
    create_strategy_engine,
)

from .planner import (
    CreativePlanner,
    CreativePlan,
    MutationConfig,
    ExperimentConfig,
    ExperimentType,
    PlanStatus,
    BatchPlan,
    create_planner,
)

from .evaluator import (
    CreativeEvaluator,
    CreativeStrategyOutcome,
    CreativeMetricsSnapshot,
    StrategyEvaluation,
    StrategyOutcomeType,
    EvaluationReport,
    create_evaluator,
)

from .executor import (
    CreativeExecutor,
    CreativeExecutionAction,
    ExecutionActionType,
    ExecutionStatus,
    ExecutionParameters,
    ExecutionBatch,
    create_executor,
)

from .generator_bridge import (
    GeneratorBridge,
    CreativeVariant,
    GenerationResult,
    VariantStatus,
    GeneratorType,
    create_generator_bridge,
)

from .experiment import (
    ExperimentManager,
    CreativeExperiment,
    ExperimentStatus,
    ExperimentResult,
    VariantMetrics,
    VariantGroupType,
    ExperimentReport,
    create_experiment_manager,
)

from .rollout import (
    RolloutController,
    RolloutDecision,
    RolloutStrategy,
    RolloutStatus,
    RolloutTrigger,
    RolloutReport,
    create_rollout_controller,
)

__all__ = [
    # analyzer
    "CreativeAnalyzer",
    "CreativeMetrics",
    "CreativeDiagnosis",
    "CreativeDiagnosisType",
    "CreativeDiagnosisSeverity",
    "CreativeAnalysisReport",
    "CreativeThresholds",
    "DEFAULT_CREATIVE_THRESHOLDS",
    "create_creative_analyzer",
    # dna_engine
    "DNAEngine",
    "CreativeDNAProfile",
    "CreativeGene",
    "DNAComparisonResult",
    "WinnerDNAReport",
    "HookType",
    "VisualStyle",
    "EmotionType",
    "GameplayFocus",
    "MonetizationType",
    "AudienceType",
    "ContextType",
    "create_dna_engine",
    # memory
    "CreativeMemory",
    "CreativeDecisionRecord",
    "CreativeDecisionOutcome",
    "CreativeActionType",
    "CreativeExperienceEntry",
    "CreativeDNAMemoryEntry",
    "create_creative_memory",
    # creative_agent
    "CreativeAgent",
    "CreativeAgentState",
    "CreativeRecommendation",
    "CreativeReport",
    "create_creative_agent",
    # opportunity (E14.4.2.1)
    "CreativeOpportunityEngine",
    "CreativeOpportunity",
    "CreativeOpportunityType",
    "CreativeSignal",
    "OpportunityPriority",
    "OpportunityReport",
    "create_opportunity_engine",
    # strategy (E14.4.2.2)
    "CreativeStrategyEngine",
    "CreativeStrategy",
    "CreativeStrategyType",
    "GeneMutation",
    "GeneMutationAction",
    "StrategyReport",
    "create_strategy_engine",
    # planner (E14.4.2.3)
    "CreativePlanner",
    "CreativePlan",
    "MutationConfig",
    "ExperimentConfig",
    "ExperimentType",
    "PlanStatus",
    "BatchPlan",
    "create_planner",
    # evaluator (E14.4.2.4)
    "CreativeEvaluator",
    "CreativeStrategyOutcome",
    "CreativeMetricsSnapshot",
    "StrategyEvaluation",
    "StrategyOutcomeType",
    "EvaluationReport",
    "create_evaluator",
    # executor (E14.4.3.1)
    "CreativeExecutor",
    "CreativeExecutionAction",
    "ExecutionActionType",
    "ExecutionStatus",
    "ExecutionParameters",
    "ExecutionBatch",
    "create_executor",
    # generator_bridge (E14.4.3.2)
    "GeneratorBridge",
    "CreativeVariant",
    "GenerationResult",
    "VariantStatus",
    "GeneratorType",
    "create_generator_bridge",
    # experiment (E14.4.3.3)
    "ExperimentManager",
    "CreativeExperiment",
    "ExperimentStatus",
    "ExperimentResult",
    "VariantMetrics",
    "VariantGroupType",
    "ExperimentReport",
    "create_experiment_manager",
    # rollout (E14.4.3.4)
    "RolloutController",
    "RolloutDecision",
    "RolloutStrategy",
    "RolloutStatus",
    "RolloutTrigger",
    "RolloutReport",
    "create_rollout_controller",
]