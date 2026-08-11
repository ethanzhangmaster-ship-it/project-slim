"""E14.4.4 Creative Self-Learning Loop — 创意自主进化学习系统.

核心模块:
  1. reward_model: RewardModel — 量化「什么有价值」
  2. pattern_miner: PatternMiner — 从历史赢家中挖掘创意模式
  3. strategy_memory: StrategyMemory — 长期策略记忆
  4. mutation_learning: MutationLearning — 学习哪些变异有效
  5. creative_policy: CreativePolicy — 上下文感知决策策略

与已有模块的关系:
  - 建立在 CreativeMemory (E14.4.1) 之上
  - 与 CreativeEvaluator (E14.4.2) 互补
  - 为 CreativeStrategyEngine (E14.4.2) 提供学习后的参数
  - 为 RolloutController (E14.4.3) 提供风险参考

设计原则:
  - 确定性、可解释 — 不依赖 AI/随机搜索
  - 基于历史数据的学习 — 从 resolved 决策记录中提取规律
  - 所有学习结果可追溯 — 每个模式/策略都有来源证据
"""

from .reward_model import (
    RewardModel,
    CreativeReward,
    DNAReward,
    MutationReward,
    RewardConfig,
    create_reward_model,
)

from .pattern_miner import (
    PatternMiner,
    CreativePattern,
    DNAPattern,
    PatternCategory,
    PatternConfidence,
    MiningReport,
    create_pattern_miner,
)

from .strategy_memory import (
    StrategyMemory,
    StrategyRecord,
    ContextProfile,
    StrategyEffectiveness,
    StrategyMemoryReport,
    create_strategy_memory,
)

from .mutation_learning import (
    MutationLearning,
    MutationRecord,
    GeneCategory,
    MutationEffectiveness,
    MutationPriority,
    MutationLearningReport,
    create_mutation_learning,
)

from .creative_policy import (
    CreativePolicy,
    PolicyDecision,
    PolicyContext,
    PolicyConfidence,
    PolicyAction,
    PolicyReport,
    create_creative_policy,
)

__all__ = [
    # reward_model
    "RewardModel",
    "CreativeReward",
    "DNAReward",
    "MutationReward",
    "RewardConfig",
    "create_reward_model",
    # pattern_miner
    "PatternMiner",
    "CreativePattern",
    "DNAPattern",
    "PatternCategory",
    "PatternConfidence",
    "MiningReport",
    "create_pattern_miner",
    # strategy_memory
    "StrategyMemory",
    "StrategyRecord",
    "ContextProfile",
    "StrategyEffectiveness",
    "StrategyMemoryReport",
    "create_strategy_memory",
    # mutation_learning
    "MutationLearning",
    "MutationRecord",
    "GeneCategory",
    "MutationEffectiveness",
    "MutationPriority",
    "MutationLearningReport",
    "create_mutation_learning",
    # creative_policy
    "CreativePolicy",
    "PolicyDecision",
    "PolicyContext",
    "PolicyConfidence",
    "PolicyAction",
    "PolicyReport",
    "create_creative_policy",
]