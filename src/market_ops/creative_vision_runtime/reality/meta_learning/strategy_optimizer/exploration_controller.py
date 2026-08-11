"""E12.5.4 — Exploration Controller。

控制 Exploitation vs Exploration 的平衡。

核心逻辑:
  - 70% 利用已验证策略（Exploit）
  - 30% 探索新组合（Explore）
  - 根据疲劳度动态调整比例
  - 支持探索衰减

选择策略:
  - 从排名结果中按 exploit_ratio 选择利用策略
  - 按 explore_ratio 选择探索策略
  - 不足时从对方池补充
"""

from __future__ import annotations

import random

from .models import (
    ExplorationPolicy,
    MetaStrategy,
    StrategyRanking,
    StrategyStatus,
)


class ExplorationController:
    """探索控制器 —— 控制 Exploit/Explore 平衡。

    Usage:
        >>> controller = ExplorationController()
        >>> selected = controller.select(ranking, total_count=20)
        >>> # 调整疲劳度
        >>> controller.adjust_fatigue(0.85)
    """

    def __init__(
        self,
        policy: ExplorationPolicy | None = None,
        seed: int | None = None,
    ) -> None:
        self.policy = policy or ExplorationPolicy()
        self._rng = random.Random(seed)

    # ── Selection ──────────────────────────────────────────

    def select(
        self,
        ranking: StrategyRanking,
        total_count: int = 10,
    ) -> list[MetaStrategy]:
        """从排名中选择策略，按 exploit/explore 比例。

        Args:
            ranking:      排序结果
            total_count:  总选择数

        Returns:
            选中的策略列表
        """
        if not ranking.strategies:
            return []

        exploit_count = max(1, int(total_count * self.policy.exploit_ratio))
        explore_count = total_count - exploit_count

        exploit_pool = [s for s in ranking.strategies if not s.exploration]
        explore_pool = [s for s in ranking.strategies if s.exploration]

        selected: list[MetaStrategy] = []

        # 选择利用策略
        selected_exploit = exploit_pool[:exploit_count]
        selected.extend(selected_exploit)

        # 如果利用策略不足，从探索池补充
        shortfall = exploit_count - len(selected_exploit)
        if shortfall > 0 and explore_pool:
            remaining = [s for s in explore_pool if s not in selected]
            selected.extend(remaining[:shortfall])

        # 选择探索策略
        explore_remaining = [s for s in explore_pool if s not in selected]
        selected_explore = explore_remaining[:explore_count]
        selected.extend(selected_explore)

        # 如果探索策略不足，从利用池补充
        shortfall_explore = explore_count - len(selected_explore)
        if shortfall_explore > 0 and exploit_pool:
            remaining = [s for s in exploit_pool if s not in selected]
            selected.extend(remaining[:shortfall_explore])

        # 标记状态
        for s in selected:
            s.status = StrategyStatus.SELECTED

        return selected

    def select_with_exploration(
        self,
        ranking: StrategyRanking,
        exploit_strategies: list[MetaStrategy],
        total_count: int = 10,
        mutation_strength: float | None = None,
    ) -> list[MetaStrategy]:
        """选择策略并生成探索变体。

        Args:
            ranking:            排序结果
            exploit_strategies: 利用策略（已验证）
            total_count:        总选择数
            mutation_strength:  突变强度（None = 使用 policy 默认值）

        Returns:
            选中的策略列表（含探索变体）
        """
        strength = mutation_strength or self.policy.mutation_strength
        exploit_count = max(1, int(total_count * self.policy.exploit_ratio))
        explore_count = total_count - exploit_count

        selected: list[MetaStrategy] = []

        # 选择利用策略
        selected_exploit = exploit_strategies[:exploit_count]
        selected.extend(selected_exploit)

        # 生成探索策略
        explore_strategies = [s for s in ranking.strategies if s.exploration]
        selected_explore = explore_strategies[:explore_count]

        # 如果探索策略不足，用利用策略生成变体
        if len(selected_explore) < explore_count and selected_exploit:
            variants = self._generate_explore_variants(
                selected_exploit,
                explore_count - len(selected_explore),
                strength,
            )
            selected_explore.extend(variants)

        selected.extend(selected_explore)

        for s in selected:
            s.status = StrategyStatus.SELECTED

        return selected

    def _generate_explore_variants(
        self,
        exploit_strategies: list[MetaStrategy],
        count: int,
        strength: float,
    ) -> list[MetaStrategy]:
        """从利用策略生成探索变体。

        Args:
            exploit_strategies: 利用策略
            count:              生成数量
            strength:           突变强度

        Returns:
            探索变体策略列表
        """
        variants: list[MetaStrategy] = []
        for i in range(count):
            source = exploit_strategies[i % len(exploit_strategies)]
            variant = MetaStrategy(
                name=f"Explore variant of {source.name}",
                target_product=source.target_product,
                optimization_goal=source.optimization_goal,
                dna_mutations=dict(source.dna_mutations),
                dna_amplify=[],
                dna_suppress=[],
                dna_explore=list(source.dna_mutations.keys()),
                source_patterns=list(source.source_patterns),
                expected_ctr_delta=source.expected_ctr_delta * strength,
                expected_roas_delta=source.expected_roas_delta * strength,
                expected_cvr_delta=source.expected_cvr_delta * strength,
                confidence=source.confidence * 0.5,
                risk_score=min(source.risk_score + 0.15, 1.0),
                exploration=True,
                strategy_source=source.strategy_source,
                evidence_count=0,
                markets=list(source.markets),
                platforms=list(source.platforms),
                audiences=list(source.audiences),
                insight=f"Exploration variant of {source.name}",
                recommendation=f"Test variant of {source.name} with strength={strength}",
            )
            variants.append(variant)
        return variants

    # ── Fatigue Adjustment ──────────────────────────────────

    def adjust_fatigue(self, fatigue_level: float) -> None:
        """根据疲劳度调整探索比例。

        Args:
            fatigue_level: 疲劳度 [0, 1]
        """
        self.policy.adjust_for_fatigue(fatigue_level)

    def get_ratio(self) -> tuple[float, float]:
        """获取当前 exploit/explore 比例。"""
        return self.policy.exploit_ratio, self.policy.explore_ratio

    def reset(self) -> None:
        """重置为默认策略。"""
        self.policy = ExplorationPolicy()

    def to_dict(self) -> dict:
        return {
            "policy": self.policy.to_dict(),
            "current_ratio": {
                "exploit": round(self.policy.exploit_ratio, 4),
                "explore": round(self.policy.explore_ratio, 4),
            },
        }

    def __repr__(self) -> str:
        return (
            f"ExplorationController(exploit={self.policy.exploit_ratio:.0%}, "
            f"explore={self.policy.explore_ratio:.0%})"
        )