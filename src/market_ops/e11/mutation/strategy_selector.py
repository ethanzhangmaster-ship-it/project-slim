"""E11.2 Strategy Selector — 策略选择器。

根据 StrategyContext 自动选择最优变异策略。

优先级规则：
  1. 有强基因 + 弱基因 → StrongGenePreserve（保护强者，替换弱者）
  2. 有弱基因（无强基因）→ WeakGeneEnhancement（增强弱者）
  3. 其他情况 → ExplorationMutation（探索新方向）

数据流：
  StrategyContext → StrategySelector.select() → MutationStrategy → MutationRule
"""

from __future__ import annotations

from .mutation_strategy import StrategyContext, MutationStrategy
from .strategy_rules import (
    WeakGeneEnhancementStrategy,
    StrongGenePreserveStrategy,
    ExplorationMutationStrategy,
)


class StrategySelector:
    """策略选择器。

    根据上下文自动选择最优策略，按优先级依次尝试：
      1. StrongGenePreserveStrategy（保护强基因）
      2. WeakGeneEnhancementStrategy（增强弱基因）
      3. ExplorationMutationStrategy（探索变异）

    Usage:
        selector = StrategySelector()
        strategy = selector.select(context)
        rule = strategy.evaluate(context)
    """

    def __init__(self) -> None:
        self._strategies: list[MutationStrategy] = [
            StrongGenePreserveStrategy(),
            WeakGeneEnhancementStrategy(),
            ExplorationMutationStrategy(),
        ]
        self._selection_count: int = 0

    def select(self, context: StrategyContext) -> MutationStrategy:
        """根据上下文选择策略。

        按优先级依次尝试每个策略，返回第一个能产生有效规则的策略。

        Args:
            context: 当前 Genome 状态

        Returns:
            选中的 MutationStrategy（保证返回一个策略）
        """
        for strategy in self._strategies:
            rule = strategy.evaluate(context)
            if rule is not None:
                self._selection_count += 1
                return strategy

        # 兜底：返回探索策略
        self._selection_count += 1
        return self._strategies[-1]

    def select_with_rule(
        self, context: StrategyContext
    ) -> tuple[MutationStrategy, MutationRule | None]:
        """选择策略并返回对应的规则。

        Returns:
            (strategy, rule) — rule 可能为 None
        """
        strategy = self.select(context)
        rule = strategy.evaluate(context)
        return strategy, rule

    @property
    def selection_count(self) -> int:
        """已执行的策略选择次数。"""
        return self._selection_count