"""E12.6.2 — Resource Controller。

核心资源控制器。

整合:
  - PriorityAllocator:  多产品优先级分配
  - BudgetOptimizer:    动态预算调整
  - ResourcePolicy:     资源策略规则

流程:
  Product States → 计算优先级 → 分配预算 → 优化调整 → ResourceAllocations
"""

from __future__ import annotations

from typing import Any

from .models import (
    BudgetAdjustment,
    ProductResourceState,
    ResourceAllocation,
    ResourceRequest,
    ResourceType,
    calculate_priority_score,
)
from .resource_policy import (
    DEFAULT_RESOURCE_POLICIES,
    ResourcePolicy,
)
from .priority_allocator import PriorityAllocator
from .budget_optimizer import BudgetOptimizer


class ResourceController:
    """资源控制器 —— E12.6.2 核心。

    负责:
      1. 评估产品资源状态
      2. 计算优先级评分
      3. 分配预算
      4. 动态调整预算
      5. 输出 ResourceAllocation
    """

    def __init__(
        self,
        policies: list[ResourcePolicy] | None = None,
        allocator: PriorityAllocator | None = None,
        optimizer: BudgetOptimizer | None = None,
        total_budget: float = 10000.0,
        default_split_ratio: dict[ResourceType, float] | None = None,
    ) -> None:
        """初始化 Resource Controller。

        Args:
            policies:            资源策略列表
            allocator:           优先级分配器
            optimizer:           预算优化器
            total_budget:        总预算
            default_split_ratio: 默认资源类型预算拆分比例
        """
        self.policies = policies or list(DEFAULT_RESOURCE_POLICIES)
        self.allocator = allocator or PriorityAllocator()
        self.optimizer = optimizer or BudgetOptimizer()
        self.total_budget = total_budget

        if default_split_ratio is None:
            default_split_ratio = {
                ResourceType.EXPERIMENT_BUDGET: 0.60,
                ResourceType.MUTATION_BUDGET: 0.30,
                ResourceType.GENERATION_CAPACITY: 0.10,
            }
        self.default_split_ratio = default_split_ratio

    def allocate(
        self,
        states: list[ProductResourceState],
        total_budget: float | None = None,
        requests: list[ResourceRequest] | None = None,
    ) -> list[ResourceAllocation]:
        """核心分配接口。

        流程:
          1. 评估策略 → 预算调整
          2. 应用调整到 state
          3. 计算优先级 → 分配预算

        Args:
            states:       产品资源状态列表
            total_budget: 总预算（不传则使用初始化时的值）
            requests:     资源请求列表

        Returns:
            ResourceAllocation 列表
        """
        budget = total_budget if total_budget is not None else self.total_budget

        if not states:
            return []

        # 1. 评估策略，生成调整
        adjustments = self._evaluate_policies(states)

        # 2. 应用调整为 updated states
        updated_states = self._apply_adjustments(states, adjustments)

        # 3. 分配预算
        allocations = self.allocator.allocate_budget_split(
            states=updated_states,
            total_budget=budget,
            split_ratio=self.default_split_ratio,
        )

        return allocations

    def allocate_single(
        self,
        state: ProductResourceState,
        total_budget: float | None = None,
        resource_type: ResourceType = ResourceType.EXPERIMENT_BUDGET,
    ) -> ResourceAllocation:
        """为单个产品分配资源。

        Args:
            state:         产品资源状态
            total_budget:  总预算
            resource_type: 资源类型

        Returns:
            ResourceAllocation
        """
        budget = total_budget if total_budget is not None else self.total_budget

        # 评估策略
        adjustments = self._evaluate_policies([state])
        if adjustments:
            state = self._apply_adjustments([state], adjustments)[0]

        # 计算优先级评分
        score = self.allocator._score_state(state)

        # 生成分配
        reasons = self._build_allocation_reasons(state, score)

        return ResourceAllocation(
            product_id=state.product_id,
            resource_type=resource_type,
            allocated_amount=round(budget * score, 2) if score > 0 else 0.0,
            allocation_score=score,
            priority=round(score * 100),
            reasons=reasons,
            expected_roi=state.recent_roas,
            confidence=score,
        )

    def _evaluate_policies(
        self,
        states: list[ProductResourceState],
    ) -> list[BudgetAdjustment]:
        """评估所有策略，生成调整列表。"""
        adjustments: list[BudgetAdjustment] = []
        for state in states:
            for policy in self.policies:
                adj = policy.evaluate(state)
                if adj is not None:
                    adjustments.append(adj)
        return adjustments

    def _apply_adjustments(
        self,
        states: list[ProductResourceState],
        adjustments: list[BudgetAdjustment],
    ) -> list[ProductResourceState]:
        """将预算调整应用到产品状态。"""
        # 按 product_id 索引调整
        adj_map: dict[str, list[BudgetAdjustment]] = {}
        for adj in adjustments:
            adj_map.setdefault(adj.product_id, []).append(adj)

        updated: list[ProductResourceState] = []
        for state in states:
            new_state = ProductResourceState(
                product_id=state.product_id,
                total_budget=state.total_budget,
                allocated_budget=state.allocated_budget,
                spent_budget=state.spent_budget,
                active_experiments=state.active_experiments,
                active_mutations=state.active_mutations,
                generation_queue_size=state.generation_queue_size,
                recent_roas=state.recent_roas,
                fatigue_score=state.fatigue_score,
                prediction_confidence=state.prediction_confidence,
                population_diversity=state.population_diversity,
                last_allocation_time=state.last_allocation_time,
            )

            if state.product_id in adj_map:
                for adj in adj_map[state.product_id]:
                    if adj.resource_type == ResourceType.EXPERIMENT_BUDGET:
                        new_state.allocated_budget = adj.new_amount
                    elif adj.resource_type == ResourceType.MUTATION_BUDGET:
                        new_state.active_mutations = max(0, int(adj.new_amount / 10))
                    elif adj.resource_type == ResourceType.GENERATION_CAPACITY:
                        new_state.generation_queue_size = max(0, int(adj.new_amount / 5))

            updated.append(new_state)

        return updated

    def _build_allocation_reasons(
        self,
        state: ProductResourceState,
        score: float,
    ) -> list[str]:
        """构建分配理由。"""
        reasons: list[str] = []

        if score >= 0.70:
            reasons.append(f"High priority allocation for {state.product_id}")
        elif score >= 0.40:
            reasons.append(f"Medium priority allocation for {state.product_id}")
        else:
            reasons.append(f"Low priority allocation for {state.product_id}")

        if state.recent_roas >= 1.50:
            reasons.append(f"Strong ROAS performance ({state.recent_roas:.2f})")
        elif state.recent_roas < 0.50:
            reasons.append(f"Low ROAS warning ({state.recent_roas:.2f})")

        if state.fatigue_score >= 0.80:
            reasons.append(f"High fatigue detected ({state.fatigue_score:.2f})")

        if state.population_diversity >= 0.70:
            reasons.append(f"High diversity — exploration opportunity")
        elif state.population_diversity < 0.20:
            reasons.append(f"Low diversity — population at risk")

        return reasons

    def optimize_budgets(
        self,
        states: list[ProductResourceState],
    ) -> list[BudgetAdjustment]:
        """使用 BudgetOptimizer 优化所有产品预算。

        Args:
            states: 产品资源状态列表

        Returns:
            BudgetAdjustment 列表
        """
        return self.optimizer.optimize_all(states)

    def calculate_priority(
        self,
        state: ProductResourceState,
    ) -> float:
        """计算单个产品的优先级评分。

        Args:
            state: 产品资源状态

        Returns:
            优先级评分 [0, 1]
        """
        return self.allocator._score_state(state)

    def get_summary(
        self,
        allocations: list[ResourceAllocation],
    ) -> dict[str, Any]:
        """生成分配摘要。

        Args:
            allocations: 分配结果列表

        Returns:
            摘要字典
        """
        total_allocated = sum(a.allocated_amount for a in allocations)
        funded_count = sum(1 for a in allocations if a.is_funded)
        unfunded_count = len(allocations) - funded_count

        by_product: dict[str, float] = {}
        for a in allocations:
            by_product[a.product_id] = by_product.get(a.product_id, 0.0) + a.allocated_amount

        by_resource: dict[str, float] = {}
        for a in allocations:
            key = a.resource_type.value
            by_resource[key] = by_resource.get(key, 0.0) + a.allocated_amount

        top_products = sorted(by_product.items(), key=lambda x: x[1], reverse=True)[:3]

        return {
            "total_budget": self.total_budget,
            "total_allocated": round(total_allocated, 2),
            "allocation_rate": round(total_allocated / self.total_budget, 4) if self.total_budget > 0 else 0.0,
            "funded_products": funded_count,
            "unfunded_products": unfunded_count,
            "by_product": {k: round(v, 2) for k, v in by_product.items()},
            "by_resource_type": {k: round(v, 2) for k, v in by_resource.items()},
            "top_products": [{"product_id": pid, "amount": round(amt, 2)} for pid, amt in top_products],
        }

    def __repr__(self) -> str:
        return (
            f"ResourceController(budget={self.total_budget:.0f}, "
            f"policies={len(self.policies)}, "
            f"allocator={self.allocator!r})"
        )