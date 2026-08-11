"""E11.8.2 — Execution Planner。

职责：EvolutionStrategy → MutationPlan。

流程：
  EvolutionStrategy → MutationMapper → MutationPlan
"""

from __future__ import annotations

import logging
from typing import Any

from ..models import (
    EvolutionStrategy,
    MutationFocus,
    StrategyType,
)
from .models import (
    MutationPlan,
    MutationOperation,
    MutationParameter,
)
from .mutation_mapper import MutationMapper

logger = logging.getLogger(__name__)

# 每个操作的预估成本
COST_PER_OPERATION: dict[MutationOperation, float] = {
    MutationOperation.MODIFY: 1.0,
    MutationOperation.CREATE: 3.0,
    MutationOperation.CROSSOVER: 2.0,
    MutationOperation.RETIRE: 0.5,
    MutationOperation.CLONE: 0.5,
}

# StrategyType → 基础优先级
STRATEGY_PRIORITY: dict[StrategyType, int] = {
    StrategyType.DIVERSIFY: 100,
    StrategyType.FIX_FAILURE: 90,
    StrategyType.SCALE_SUCCESS: 70,
    StrategyType.EXPLOIT_WINNER: 60,
    StrategyType.EXPLORE_NEW: 40,
}


class ExecutionPlanner:
    """执行计划器。

    将 EvolutionStrategy 转换为 MutationPlan。

    Attributes:
        mutation_mapper: 突变映射器
        cost_map:        操作成本映射
        priority_map:    策略优先级映射
    """

    def __init__(
        self,
        mutation_mapper: MutationMapper | None = None,
        cost_map: dict[MutationOperation, float] | None = None,
        priority_map: dict[StrategyType, int] | None = None,
    ) -> None:
        self._mapper = mutation_mapper or MutationMapper()
        self._cost_map = cost_map or COST_PER_OPERATION
        self._priority_map = priority_map or STRATEGY_PRIORITY

    # ── 主入口 ──────────────────────────────────────────

    def create_plan(self, strategy: EvolutionStrategy) -> MutationPlan:
        """将 EvolutionStrategy 转换为 MutationPlan。

        Args:
            strategy: EvolutionStrategy

        Returns:
            MutationPlan
        """
        # 1. 映射操作和参数
        mapped = self._mapper.map(strategy)
        operations = mapped["operations"]
        mutations = mapped["mutations"]

        # 2. 计算预估成本
        estimated_cost = self._estimate_cost(operations, mutations)

        # 3. 计算优先级
        priority = self._compute_priority(strategy, operations)

        # 4. 构建 MutationPlan
        plan = MutationPlan(
            strategy_id=strategy.strategy_id,
            genome_ids=list(strategy.target_genomes),
            operations=operations,
            mutations=mutations,
            estimated_cost=estimated_cost,
            priority=priority,
            metadata={
                "strategy_type": strategy.strategy_type.value,
                "mutation_focus": strategy.mutation_focus.value,
                "intensity": strategy.intensity.value,
                "confidence": strategy.confidence,
                "reason": strategy.reason,
            },
        )

        logger.info(
            f"Created plan {plan.plan_id}: "
            f"{plan.operation_count} ops, {plan.mutation_count} mutations, "
            f"cost={plan.estimated_cost}"
        )

        return plan

    def create_plans(
        self, strategies: list[EvolutionStrategy]
    ) -> list[MutationPlan]:
        """批量创建计划。

        Returns:
            MutationPlan 列表（与 strategies 一一对应）
        """
        return [self.create_plan(s) for s in strategies]

    # ── 内部方法 ─────────────────────────────────────────

    def _estimate_cost(
        self,
        operations: list[MutationOperation],
        mutations: list[MutationParameter],
    ) -> float:
        """估算资源消耗。

        cost = sum(每个操作的固定成本) + 0.1 * mutation_count
        """
        op_cost = sum(self._cost_map.get(op, 1.0) for op in operations)
        mutation_cost = len(mutations) * 0.1
        return round(op_cost + mutation_cost, 2)

    def _compute_priority(
        self,
        strategy: EvolutionStrategy,
        operations: list[MutationOperation],
    ) -> int:
        """计算执行优先级。

        priority = base_priority(strategy_type) * confidence
        """
        base = self._priority_map.get(strategy.strategy_type, 50)
        # 置信度调整
        adjusted = int(base * strategy.confidence)
        return max(1, min(100, adjusted))

    @property
    def mutation_mapper(self) -> MutationMapper:
        return self._mapper

    def __repr__(self) -> str:
        return f"ExecutionPlanner(mapper={self._mapper})"