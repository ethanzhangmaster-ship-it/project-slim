"""E11.2 Strategy Rules — 具体策略实现。

三个基础策略：

  WeakGeneEnhancementStrategy  — 弱基因增强（ENHANCE）
  StrongGenePreserveStrategy   — 强基因保护 + 弱元素替换（REPLACE）
  ExplorationMutationStrategy  — 探索性变异（REPLACE 随机基因）

所有策略保持 deterministic。
"""

from __future__ import annotations

from .mutation_schema import MutationType, MutationRule
from .mutation_strategy import StrategyContext, MutationStrategy


# ═══════════════════════════════════════════════════════════
# WeakGeneEnhancementStrategy — 弱基因增强
# ═══════════════════════════════════════════════════════════

class WeakGeneEnhancementStrategy(MutationStrategy):
    """弱基因增强策略。

    条件：存在 weak_genes（基因强度 < 阈值）
    动作：选择最弱的基因，执行 ENHANCE
    优先级：0.7 + 0.1 * len(weak_genes)（弱基因越多，优先级越高）

    例如：
      reward.intensity = 0.3 → ENHANCE boost=0.4 → 0.42
    """

    def __init__(self, boost: float = 0.4) -> None:
        super().__init__(name="WeakGeneEnhancement")
        self._boost = boost

    def evaluate(self, context: StrategyContext) -> MutationRule | None:
        if not context.weak_genes:
            return None

        # 选择第一个弱基因
        target_gene = context.weak_genes[0]

        # 优先级随弱基因数量增加
        priority = min(0.7 + 0.1 * len(context.weak_genes), 1.0)

        return MutationRule(
            target_gene=target_gene,
            mutation_type=MutationType.ENHANCE,
            strategy="weak_enhancement",
            priority=priority,
        )


# ═══════════════════════════════════════════════════════════
# StrongGenePreserveStrategy — 强基因保护
# ═══════════════════════════════════════════════════════════

class StrongGenePreserveStrategy(MutationStrategy):
    """强基因保护策略。

    条件：存在 strong_genes 且存在 weak_genes
    动作：保留强基因，对弱基因执行 REPLACE（不修改强基因本身）
    优先级：0.8（强基因保护优先级较高）

    策略逻辑：
      - 强基因是已验证的模式，不应被破坏
      - 弱基因需要被替换为更好的候选
      - 如果有弱基因，选择一个进行 REPLACE
    """

    def __init__(self) -> None:
        super().__init__(name="StrongGenePreserve")

    def evaluate(self, context: StrategyContext) -> MutationRule | None:
        if not context.strong_genes:
            return None

        # 如果有弱基因，替换弱基因
        if context.weak_genes:
            target_gene = context.weak_genes[0]
            return MutationRule(
                target_gene=target_gene,
                mutation_type=MutationType.REPLACE,
                strategy="strong_preserve_replace_weak",
                priority=0.8,
            )

        # 强基因存在但无弱基因 → 不需要变异
        return None


# ═══════════════════════════════════════════════════════════
# ExplorationMutationStrategy — 探索性变异
# ═══════════════════════════════════════════════════════════

class ExplorationMutationStrategy(MutationStrategy):
    """探索性变异策略。

    条件：无明显强弱基因（或所有基因都在中等水平）
    动作：选择中等基因执行 REPLACE，探索新方向
    优先级：0.5（探索优先级较低，不干扰明确策略）

    例如：
      hook.type = "rescue" → REPLACE → "discovery"
    """

    def __init__(self) -> None:
        super().__init__(name="ExplorationMutation")

    def evaluate(self, context: StrategyContext) -> MutationRule | None:
        # 确定哪些基因是"中等"的（既不强也不弱）
        all_genes = list(context.gene_details.keys())
        if not all_genes:
            return None

        middle_genes = [
            g for g in all_genes
            if g not in context.weak_genes and g not in context.strong_genes
        ]

        if not middle_genes:
            # 所有基因都是强或弱，选第一个弱基因探索
            if context.weak_genes:
                target_gene = context.weak_genes[0]
            else:
                target_gene = all_genes[0]
        else:
            # 选第一个中等基因
            target_gene = middle_genes[0]

        return MutationRule(
            target_gene=target_gene,
            mutation_type=MutationType.REPLACE,
            strategy="exploration_replace",
            priority=0.5,
        )