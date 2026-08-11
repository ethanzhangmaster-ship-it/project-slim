"""E12.6.5 — Allocation Engine。

预算分配引擎 —— 基于产品适应度进行加权预算分配。

算法:
  初版: Weighted Allocation — score_i / sum(score)
  后续: Bayesian Portfolio Optimization + Thompson Sampling
"""

from __future__ import annotations

from typing import Any

from .models import (
    BudgetAllocation,
    ProductFitness,
    ProductLifecycleStage,
)


# 默认乘数（纯适应度分配，不包含生命周期调整）
# 生命周期调整由 LifecycleAllocator 单独处理
_DEFAULT_MULTIPLIER: float = 1.0


class AllocationEngine:
    """预算分配引擎。

    基于加权适应度评分分配总预算。
    """

    def __init__(
        self,
        default_multiplier: float = 1.0,
    ) -> None:
        self._default_multiplier = default_multiplier

    def allocate(
        self,
        fitness_scores: list[ProductFitness],
        total_budget: float,
        previous_budgets: dict[str, float] | None = None,
        min_allocation: float = 0.0,
    ) -> list[BudgetAllocation]:
        """加权分配预算。

        Args:
            fitness_scores:    适应度评分列表（已排名）
            total_budget:      总预算
            previous_budgets:  之前预算 {product_id: amount}
            min_allocation:    最小分配金额

        Returns:
            BudgetAllocation 列表
        """
        if not fitness_scores or total_budget <= 0:
            return []

        previous_budgets = previous_budgets or {}

        # 计算加权分数：total_fitness × default_multiplier
        weighted_scores: list[tuple[str, float]] = []
        for f in fitness_scores:
            weighted = f.total_fitness * self._default_multiplier
            weighted_scores.append((f.product_id, weighted))

        # 归一化分配
        total_weight = sum(w for _, w in weighted_scores)
        if total_weight <= 0:
            return [
                BudgetAllocation(
                    product_id=pid,
                    allocated_budget=0.0,
                    allocation_pct=0.0,
                    previous_budget=previous_budgets.get(pid, 0.0),
                    reason="zero_weight",
                )
                for pid, _ in weighted_scores
            ]

        allocations: list[BudgetAllocation] = []
        for pid, weight in weighted_scores:
            share = weight / total_weight
            amount = round(share * total_budget, 2)

            if amount < min_allocation:
                amount = 0.0

            prev = previous_budgets.get(pid, 0.0)
            change_pct = _safe_change(amount, prev)

            reason = self._build_reason(share, amount, prev)

            allocations.append(
                BudgetAllocation(
                    product_id=pid,
                    allocated_budget=amount,
                    allocation_pct=round(share, 4),
                    previous_budget=round(prev, 2),
                    change_pct=round(change_pct, 4),
                    reason=reason,
                )
            )

        # 调整四舍五入误差
        allocations = self._adjust_rounding(allocations, total_budget)

        return allocations

    def allocate_evenly(
        self,
        product_ids: list[str],
        total_budget: float,
    ) -> list[BudgetAllocation]:
        """均匀分配预算（无适应度数据时 fallback）。

        Args:
            product_ids:  产品 ID 列表
            total_budget: 总预算

        Returns:
            BudgetAllocation 列表
        """
        if not product_ids or total_budget <= 0:
            return []

        n = len(product_ids)
        share = 1.0 / n
        amount = round(total_budget / n, 2)

        allocations = []
        for pid in product_ids:
            allocations.append(
                BudgetAllocation(
                    product_id=pid,
                    allocated_budget=amount,
                    allocation_pct=round(share, 4),
                    change_pct=0.0,
                    reason="even_allocation",
                )
            )

        return self._adjust_rounding(allocations, total_budget)

    def _adjust_rounding(
        self,
        allocations: list[BudgetAllocation],
        total_budget: float,
    ) -> list[BudgetAllocation]:
        """调整分配以匹配总预算。"""
        total_allocated = sum(a.allocated_budget for a in allocations)
        if total_allocated <= 0 or abs(total_allocated - total_budget) < 0.01:
            return allocations

        # 将差额加到分配最多的产品上
        diff = round(total_budget - total_allocated, 2)
        max_idx = max(
            range(len(allocations)),
            key=lambda i: allocations[i].allocated_budget,
        )
        a = allocations[max_idx]
        new_amount = round(a.allocated_budget + diff, 2)
        allocations[max_idx] = BudgetAllocation(
            product_id=a.product_id,
            allocated_budget=new_amount,
            allocation_pct=round(new_amount / total_budget, 4) if total_budget > 0 else 0.0,
            previous_budget=a.previous_budget,
            change_pct=round(_safe_change(new_amount, a.previous_budget), 4),
            reason=a.reason,
        )

        return allocations

    def _build_reason(
        self, share: float, amount: float, previous: float
    ) -> str:
        """构建分配理由。"""
        if amount <= 0:
            return "zero_allocation"
        if previous <= 0:
            return "new_allocation"
        if amount > previous:
            return "increased_due_to_fitness"
        if amount < previous:
            return "decreased_due_to_fitness"
        return "maintained"

    def get_default_multiplier(self) -> float:
        """获取默认乘数。"""
        return self._default_multiplier

    def __repr__(self) -> str:
        return f"AllocationEngine(multiplier={self._default_multiplier})"


def _safe_change(new_amount: float, previous: float) -> float:
    """安全计算变化百分比。"""
    if previous <= 0:
        return 0.0 if new_amount <= 0 else 1.0
    return (new_amount - previous) / previous