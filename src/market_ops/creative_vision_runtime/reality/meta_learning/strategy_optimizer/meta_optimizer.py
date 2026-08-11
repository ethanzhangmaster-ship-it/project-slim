"""E12.5.4 — Meta Optimizer。

核心编排器，将 Pattern Mining + Knowledge Graph 的经验
转化为 E11 Evolution Orchestrator 可执行的战略。

流程:
  Patterns + Knowledge
        ↓
  StrategyGenerator.generate()
        ↓
  StrategyRanker.rank()
        ↓
  ExplorationController.select()
        ↓
  OptimizationResult → E11.9
"""

from __future__ import annotations

from ..knowledge_graph.models import KnowledgeEdge, KnowledgeNode
from ..pattern_miner.models import MetaPattern
from .exploration_controller import ExplorationController
from .models import (
    ExplorationPolicy,
    MetaStrategy,
    OptimizationGoal,
    OptimizationResult,
    StrategyRanking,
)
from .strategy_generator import StrategyGenerator
from .strategy_ranker import StrategyRanker


class MetaOptimizer:
    """元优化器 —— E12.5.4 核心编排器。

    将 Pattern / Knowledge 转化为可执行的进化策略。

    Usage:
        >>> optimizer = MetaOptimizer()
        >>> result = optimizer.optimize(patterns, nodes, edges, product="Merge Dragon")
        >>> # 输出给 E11
        >>> for s in result.strategies:
        ...     evolution_strategy = s.to_evolution_strategy()
    """

    def __init__(
        self,
        generator: StrategyGenerator | None = None,
        ranker: StrategyRanker | None = None,
        exploration: ExplorationController | None = None,
        exploit_ratio: float = 0.7,
        explore_ratio: float = 0.3,
    ) -> None:
        self.generator = generator or StrategyGenerator()
        self.ranker = ranker or StrategyRanker()
        self.exploration = exploration or ExplorationController(
            policy=ExplorationPolicy(
                exploit_ratio=exploit_ratio,
                explore_ratio=explore_ratio,
            )
        )

    # ── Main Optimize Method ───────────────────────────────

    def optimize(
        self,
        patterns: list[MetaPattern] | None = None,
        knowledge_nodes: list[KnowledgeNode] | None = None,
        knowledge_edges: list[KnowledgeEdge] | None = None,
        target_product: str = "",
        total_count: int = 10,
        goal: OptimizationGoal | None = None,
        include_exploration: bool = True,
        fatigue_level: float = 0.0,
    ) -> OptimizationResult:
        """执行完整优化流程。

        Patterns → Generate → Rank → Select → Result

        Args:
            patterns:           MetaPattern 列表
            knowledge_nodes:    KnowledgeNode 列表
            knowledge_edges:    KnowledgeEdge 列表
            target_product:     目标产品
            total_count:        最终策略数
            goal:               优化目标
            include_exploration: 是否包含探索策略
            fatigue_level:      疲劳度

        Returns:
            OptimizationResult
        """
        patterns = patterns or []
        knowledge_nodes = knowledge_nodes or []
        knowledge_edges = knowledge_edges or []

        all_strategies: list[MetaStrategy] = []

        # Step 1: 从 Pattern 生成策略
        if patterns:
            pattern_strategies = self.generator.generate_from_patterns(
                patterns, target_product
            )
            all_strategies.extend(pattern_strategies)

        # Step 2: 从 Knowledge Graph 生成策略
        if knowledge_nodes and knowledge_edges:
            kg_strategies = self.generator.generate_from_knowledge(
                knowledge_nodes, knowledge_edges, target_product
            )
            all_strategies.extend(kg_strategies)

        # Step 3: 生成探索策略
        if include_exploration and patterns:
            explore_strategies = self.generator.generate_exploration(
                patterns, target_product, count=3
            )
            all_strategies.extend(explore_strategies)

        # Step 4: 调整疲劳度
        if fatigue_level > 0:
            self.exploration.adjust_fatigue(fatigue_level)

        # Step 5: 排序
        if goal:
            ranking = self.ranker.rank_by_goal(all_strategies, goal)
        else:
            ranking = self.ranker.rank(all_strategies)

        # Step 6: 选择
        selected = self.exploration.select(ranking, total_count)

        # Step 7: 构建结果
        result = OptimizationResult(
            strategies=selected,
            ranking=ranking,
            exploration_policy=self.exploration.policy,
            total_patterns=len(patterns),
            total_knowledge=len(knowledge_nodes),
        )

        return result

    # ── Convenience Methods ─────────────────────────────────

    def optimize_from_patterns(
        self,
        patterns: list[MetaPattern],
        target_product: str = "",
        total_count: int = 10,
    ) -> OptimizationResult:
        """仅从 Pattern 优化（快捷方法）。"""
        return self.optimize(
            patterns=patterns,
            target_product=target_product,
            total_count=total_count,
        )

    def optimize_from_knowledge(
        self,
        nodes: list[KnowledgeNode],
        edges: list[KnowledgeEdge],
        target_product: str = "",
        total_count: int = 10,
    ) -> OptimizationResult:
        """仅从 Knowledge Graph 优化（快捷方法）。"""
        return self.optimize(
            knowledge_nodes=nodes,
            knowledge_edges=edges,
            target_product=target_product,
            total_count=total_count,
        )

    def optimize_full(
        self,
        patterns: list[MetaPattern],
        nodes: list[KnowledgeNode],
        edges: list[KnowledgeEdge],
        target_product: str = "",
        total_count: int = 10,
        goal: OptimizationGoal | None = None,
    ) -> OptimizationResult:
        """完整优化（Pattern + Knowledge Graph）。"""
        return self.optimize(
            patterns=patterns,
            knowledge_nodes=nodes,
            knowledge_edges=edges,
            target_product=target_product,
            total_count=total_count,
            goal=goal,
        )

    def get_evolution_strategies(
        self,
        result: OptimizationResult,
    ) -> list[dict]:
        """获取 E11 兼容的进化策略列表。"""
        return [s.to_evolution_strategy() for s in result.strategies]

    def __repr__(self) -> str:
        return (
            f"MetaOptimizer(exploit={self.exploration.policy.exploit_ratio:.0%}, "
            f"explore={self.exploration.policy.explore_ratio:.0%})"
        )