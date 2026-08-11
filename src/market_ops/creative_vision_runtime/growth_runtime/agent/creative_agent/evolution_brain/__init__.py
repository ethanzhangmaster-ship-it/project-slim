"""E14.5 Creative Evolution Brain — 自主创意进化大脑.

将 E14.4.4 Self-Learning Loop 的学习结果与 E11 Evolution Engine 的 Genome Population
连接起来，形成从「观察市场 → 分析群体 → 规划进化 → 自适应变异 → 预测筛选 → 进化记忆」
的完整自主进化闭环。

核心模块:
  1. genome_intelligence: GenomeIntelligence — 基因级别智能分析 (E14.5.1)
  2. population_analyzer: PopulationAnalyzer — 群体多样性+进化趋势 (E14.5.2)
  3. evolution_planner: EvolutionPlanner — 进化方向决策 (E14.5.3)
  4. adaptive_mutation: AdaptiveMutationSelector — 连接E11的自适应变异 (E14.5.4)
  5. fitness_predictor: FitnessPredictor — 预测试筛选 (E14.5.5)
  6. evolution_memory: EvolutionMemoryGraph — 进化知识图谱 (E14.5.6)

与已有模块的关系:
  - 建立在 E14.4.4 Learning Loop 之上 (RewardModel, PatternMiner, StrategyMemory, MutationLearning)
  - 连接到 E11 Evolution Engine (CreativeGenome, PopulationManager, MutationEngine)
  - 与 E14.4 Creative Agent 协同 (CreativeMemory, DNAEngine, CreativePolicy)

设计原则:
  - 确定性、可解释 — 所有进化决策有据可查
  - 基于历史数据 — 从 resolved 决策记录和 DNA 记忆中提取规律
  - 渐进式进化 — 不替代 E11，而是增强其决策能力
  - 所有进化结果可追溯 — 每个基因变异都有来源证据
"""

from .genome_intelligence import (
    GenomeIntelligence,
    GenePerformance,
    ContextAffinity,
    GeneIntelligence,
    GenomeIntelligenceReport,
    create_genome_intelligence,
)
from .population_analyzer import (
    PopulationAnalyzer,
    DiversityMetrics,
    TrendSignal,
    PopulationHealthReport,
    create_population_analyzer,
)
from .evolution_planner import (
    EvolutionPlanner,
    EvolutionGoal,
    GeneMutationPlan,
    EvolutionPlan,
    create_evolution_planner,
)
from .adaptive_mutation import (
    AdaptiveMutationSelector,
    AdaptiveMutation,
    AdaptiveMutationReport,
    create_adaptive_mutation_selector,
)
from .fitness_predictor import (
    FitnessPredictor,
    FitnessPrediction,
    FitnessPredictionReport,
    create_fitness_predictor,
)
from .evolution_memory import (
    EvolutionMemoryGraph,
    EvolutionNode,
    EvolutionEdge,
    EvolutionPath,
    EvolutionMemoryReport,
    NodeType,
    EdgeType,
    create_evolution_memory_graph,
)
from .decision_executor import (
    DecisionExecutor,
    EvolutionAction,
    ExecutionResult,
    ExecutionReport,
    ActionType,
    ActionStatus,
    create_decision_executor,
)
from .experiment_controller import (
    ExperimentController,
    Experiment,
    ExperimentGroup,
    ExperimentConfig,
    ExperimentResult,
    ExperimentReport,
    ExperimentStatus,
    GroupType,
    PlatformType,
    create_experiment_controller,
)
from .feedback_controller import (
    EvolutionFeedbackController,
    EvolutionFeedback,
    MemoryPattern,
    EvolutionSignal,
    FeedbackReport,
    FeedbackType,
    SignalAction,
    create_feedback_controller,
)
from .growth_action_router import (
    GrowthActionRouter,
    GrowthAction,
    GrowthActionType,
    ActionSource,
    ActionStatus,
    ActionPriority,
    RouteResult,
    SIGNAL_TO_ACTION,
    SIGNAL_TO_FALLBACK,
    ACTION_TO_EXECUTOR,
    create_growth_action_router,
)
from .growth_execution_engine import (
    GrowthExecutionEngine,
    ExecutionStatus,
    ExecutionOutcome,
    BaseExecutor,
    CreativeExecutor,
    MetaAdsExecutor,
    ExperimentExecutor,
    EvolutionExecutor,
    NoOpExecutor,
    create_growth_execution_engine,
)
from .execution_feedback import (
    ExecutionFeedbackCollector,
    ExecutionFeedback,
    RewardMetrics,
    RewardCalculator,
    FeedbackQuality,
    FeedbackPipeline,
    create_feedback_collector,
    create_feedback_pipeline,
)
from .strategy_optimizer import (
    GrowthStrategyOptimizer,
    StrategyScore,
    StrategyCluster,
    StrategyExtractor,
    StrategyEvaluator,
    create_strategy_optimizer,
)
from .goal_models import (
    GrowthGoal,
    GoalPriority,
    GoalStatus,
    GoalGap,
    GoalManager,
    create_goal_manager,
)
from .growth_state_analyzer import (
    GrowthState,
    StateAnalyzer,
    MetricStatus,
    CreativeHealth,
    UAScaleStatus,
    create_state_analyzer,
)
from .strategy_retriever import (
    StrategyMatch,
    StrategyRetriever,
    create_strategy_retriever,
)
from .growth_planner import (
    GrowthPlan,
    PlanStep,
    GrowthPlanner,
    create_growth_planner,
)
from .safety_guard import (
    GrowthSafetyGuard,
    SafetyDecision,
    SafetyDecisionType,
    BudgetLimit,
    FrequencyLimit,
    create_safety_guard,
)
from .autonomous_growth_agent import (
    AutonomousGrowthAgent,
    AgentState,
    CycleResult,
    create_autonomous_growth_agent,
)
from .media_buying_agent import (
    MediaBuyingAgent,
    ApprovalTier,
    ApprovalDecision,
    RollbackRecord,
    create_media_buying_agent,
)

__all__ = [
    # E14.5.1
    "GenomeIntelligence",
    "GenePerformance",
    "ContextAffinity",
    "GeneIntelligence",
    "GenomeIntelligenceReport",
    "create_genome_intelligence",
    # E14.5.2
    "PopulationAnalyzer",
    "DiversityMetrics",
    "TrendSignal",
    "PopulationHealthReport",
    "create_population_analyzer",
    # E14.5.3
    "EvolutionPlanner",
    "EvolutionGoal",
    "GeneMutationPlan",
    "EvolutionPlan",
    "create_evolution_planner",
    # E14.5.4
    "AdaptiveMutationSelector",
    "AdaptiveMutation",
    "AdaptiveMutationReport",
    "create_adaptive_mutation_selector",
    # E14.5.5
    "FitnessPredictor",
    "FitnessPrediction",
    "FitnessPredictionReport",
    "create_fitness_predictor",
    # E14.5.6
    "EvolutionMemoryGraph",
    "EvolutionNode",
    "EvolutionEdge",
    "EvolutionPath",
    "EvolutionMemoryReport",
    "NodeType",
    "EdgeType",
    "create_evolution_memory_graph",
    # E14.6.1
    "DecisionExecutor",
    "EvolutionAction",
    "ExecutionResult",
    "ExecutionReport",
    "ActionType",
    "ActionStatus",
    "create_decision_executor",
    # E14.6.2
    "ExperimentController",
    "Experiment",
    "ExperimentGroup",
    "ExperimentConfig",
    "ExperimentResult",
    "ExperimentReport",
    "ExperimentStatus",
    "GroupType",
    "PlatformType",
    "create_experiment_controller",
    # E14.6.3
    "EvolutionFeedbackController",
    "EvolutionFeedback",
    "MemoryPattern",
    "EvolutionSignal",
    "FeedbackReport",
    "FeedbackType",
    "SignalAction",
    "create_feedback_controller",
    # E14.7.1
    "GrowthActionRouter",
    "GrowthAction",
    "GrowthActionType",
    "ActionSource",
    "ActionStatus",
    "ActionPriority",
    "RouteResult",
    "SIGNAL_TO_ACTION",
    "SIGNAL_TO_FALLBACK",
    "ACTION_TO_EXECUTOR",
    "create_growth_action_router",
    # E14.7.2
    "GrowthExecutionEngine",
    "ExecutionStatus",
    "ExecutionOutcome",
    "BaseExecutor",
    "CreativeExecutor",
    "MetaAdsExecutor",
    "ExperimentExecutor",
    "EvolutionExecutor",
    "NoOpExecutor",
    "create_growth_execution_engine",
    # E14.7.3
    "ExecutionFeedbackCollector",
    "ExecutionFeedback",
    "RewardMetrics",
    "RewardCalculator",
    "FeedbackQuality",
    "FeedbackPipeline",
    "create_feedback_collector",
    "create_feedback_pipeline",
    # E14.7.4
    "GrowthStrategyOptimizer",
    "StrategyScore",
    "StrategyCluster",
    "StrategyExtractor",
    "StrategyEvaluator",
    "create_strategy_optimizer",
    # E14.8.1
    "GrowthGoal",
    "GoalPriority",
    "GoalStatus",
    "GoalGap",
    "GoalManager",
    "create_goal_manager",
    # E14.8.2
    "GrowthState",
    "StateAnalyzer",
    "MetricStatus",
    "CreativeHealth",
    "UAScaleStatus",
    "create_state_analyzer",
    # E14.8.3
    "StrategyMatch",
    "StrategyRetriever",
    "create_strategy_retriever",
    # E14.8.4
    "GrowthPlan",
    "PlanStep",
    "GrowthPlanner",
    "create_growth_planner",
    # E14.8.5
    "GrowthSafetyGuard",
    "SafetyDecision",
    "SafetyDecisionType",
    "BudgetLimit",
    "FrequencyLimit",
    "create_safety_guard",
    # E14.8
    "AutonomousGrowthAgent",
    "AgentState",
    "CycleResult",
    "create_autonomous_growth_agent",
    # E14.8.1 Media Buying Agent
    "MediaBuyingAgent",
    "ApprovalTier",
    "ApprovalDecision",
    "RollbackRecord",
    "create_media_buying_agent",
]