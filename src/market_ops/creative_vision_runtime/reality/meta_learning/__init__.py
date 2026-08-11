"""E12.5 — Meta Learning Layer。

将 E12.4 实验闭环沉淀为长期经验记忆，实现跨产品、
跨市场、跨生命周期的知识积累与迁移。

Phase 1 (E12.5.1): Experience Memory Layer
  - models:              经验记忆数据模型
  - experience_store:    持久化存储 + 多维度查询
  - experience_collector: E12.4 数据 → ExperienceRecord

Phase 2 (E12.5.2): Pattern Mining Engine
  - pattern_miner/models:              Pattern 数据模型
  - pattern_miner/gene_analyzer:       基因分析器
  - pattern_miner/pattern_miner:       模式提取引擎
  - pattern_miner/correlation_engine:  相关性引擎
  - pattern_miner/pattern_ranker:      模式排序器

Phase 3 (E12.5.3): Meta Knowledge Graph
  - knowledge_graph/models:              Graph 数据模型
  - knowledge_graph/graph_store:         图存储引擎
  - knowledge_graph/node_builder:        Pattern → Node 转换
  - knowledge_graph/relationship_engine: 自动关系发现
  - knowledge_graph/graph_query:         图查询引擎

Phase 4 (E12.5.4): Meta Strategy Optimizer
  - strategy_optimizer/models:                 MetaStrategy, ExplorationPolicy
  - strategy_optimizer/strategy_generator:     Pattern/Knowledge → Strategy
  - strategy_optimizer/strategy_ranker:        策略评分与排序
  - strategy_optimizer/exploration_controller: Exploit/Explore 平衡
  - strategy_optimizer/meta_optimizer:         核心编排器

Phase 5 (E12.5.5): Autonomous Meta Learning Loop
  - autonomous_loop/models:                    MetaLearningCycle, LearningSchedule
  - autonomous_loop/cycle_manager:             学习周期生命周期管理
  - autonomous_loop/learning_scheduler:        学习触发条件判断
  - autonomous_loop/knowledge_updater:         Bayesian 知识更新
  - autonomous_loop/strategy_feedback:         策略反馈收集与评分更新
  - autonomous_loop/meta_learning_controller:  核心编排器
"""

from .models import (
    ContextDetail,
    ExperienceOutcome,
    ExperiencePattern,
    ExperienceQuery,
    ExperienceRecord,
    ExperienceResult,
    ExperienceStats,
    ExperimentDetail,
    GeneCategory,
    MutationDetail,
    MutationType,
)
from .experience_store import ExperienceStore
from .experience_collector import ExperienceCollector

# E12.5.2 Pattern Mining
from .pattern_miner import (
    CorrelationEngine,
    ExtractedGene,
    GeneAnalyzer,
    GeneCluster,
    GeneImpactScore,
    MetaPattern,
    PatternExtractor,
    PatternMiningResult,
    PatternRanker,
    PatternType,
)

# E12.5.3 Knowledge Graph
from .knowledge_graph import (
    GraphQuery,
    GraphQueryEngine,
    GraphQueryResult,
    GraphStats,
    GraphStore,
    KnowledgeEdge,
    KnowledgeNode,
    NodeBuilder,
    NodeType,
    RelationType,
    RelationshipEngine,
)

# E12.5.4 Meta Strategy Optimizer
from .strategy_optimizer import (
    ExplorationController,
    ExplorationPolicy,
    MetaOptimizer,
    MetaStrategy,
    OptimizationGoal,
    OptimizationResult,
    StrategyGenerator,
    StrategyRanker,
    StrategyRanking,
    StrategySource,
    StrategyStatus,
)

# E12.5.5 Autonomous Meta Learning Loop
from .autonomous_loop import (
    CycleManager,
    KnowledgeUpdate,
    KnowledgeUpdater,
    LearningSchedule,
    LearningScheduler,
    LearningSummary,
    LearningTrigger,
    LoopMetrics,
    MetaCycleStatus,
    MetaLearningController,
    MetaLearningCycle,
    MetaLearningResult,
    StrategyFeedback,
    StrategyFeedbackCollector,
    TriggerReason,
)

__all__ = [
    # Models
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
    # Engines (E12.5.1)
    "ExperienceStore",
    "ExperienceCollector",
    # E12.5.2 Pattern Mining
    "PatternType",
    "ExtractedGene",
    "GeneCluster",
    "MetaPattern",
    "GeneImpactScore",
    "PatternMiningResult",
    "GeneAnalyzer",
    "PatternExtractor",
    "CorrelationEngine",
    "PatternRanker",
    # E12.5.3 Knowledge Graph
    "NodeType",
    "RelationType",
    "KnowledgeNode",
    "KnowledgeEdge",
    "GraphQuery",
    "GraphQueryResult",
    "GraphStats",
    "GraphStore",
    "NodeBuilder",
    "RelationshipEngine",
    "GraphQueryEngine",
    # E12.5.4 Meta Strategy Optimizer
    "OptimizationGoal",
    "StrategyStatus",
    "StrategySource",
    "MetaStrategy",
    "ExplorationPolicy",
    "StrategyRanking",
    "OptimizationResult",
    "StrategyGenerator",
    "StrategyRanker",
    "ExplorationController",
    "MetaOptimizer",
    # E12.5.5 Autonomous Meta Learning Loop
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
    "CycleManager",
    "LearningScheduler",
    "KnowledgeUpdater",
    "StrategyFeedbackCollector",
    "MetaLearningController",
]