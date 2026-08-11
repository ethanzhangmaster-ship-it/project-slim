"""E12.6.5 — Experiment Allocator。

实验槽位分配器 —— 基于产品适应度和生命周期分配实验机会。

实验槽位分配策略:
  1. 基于适应度加权分配
  2. 生命周期阶段调整（LAUNCH/FATIGUE 获得更多实验）
  3. 跨产品知识迁移加分（高相似度产品获得额外实验）
"""

from __future__ import annotations

from .models import (
    ExperimentAllocation,
    ProductFitness,
    ProductLifecycleStage,
)


# 生命周期实验调整因子
_LIFECYCLE_EXPERIMENT_FACTOR: dict[ProductLifecycleStage, float] = {
    ProductLifecycleStage.LAUNCH: 2.0,
    ProductLifecycleStage.GROWTH: 1.2,
    ProductLifecycleStage.PEAK: 1.0,
    ProductLifecycleStage.PLATEAU: 1.5,
    ProductLifecycleStage.FATIGUE: 1.8,
    ProductLifecycleStage.DECAY: 0.3,
    ProductLifecycleStage.DEATH: 0.0,
}


class ExperimentAllocator:
    """实验槽位分配器。

    分配实验机会给不同产品。
    """

    def __init__(
        self,
        lifecycle_factors: dict[ProductLifecycleStage, float] | None = None,
    ) -> None:
        self._factors = dict(
            lifecycle_factors or _LIFECYCLE_EXPERIMENT_FACTOR
        )

    def allocate(
        self,
        fitness_scores: list[ProductFitness],
        total_slots: int,
        previous_slots: dict[str, int] | None = None,
        transfer_bonus: dict[str, float] | None = None,
    ) -> list[ExperimentAllocation]:
        """分配实验槽位。

        Args:
            fitness_scores:  适应度评分列表
            total_slots:     总实验槽位
            previous_slots:  之前槽位 {product_id: slots}
            transfer_bonus:  跨产品迁移加分 {product_id: bonus}

        Returns:
            ExperimentAllocation 列表
        """
        if not fitness_scores or total_slots <= 0:
            return []

        previous_slots = previous_slots or {}
        transfer_bonus = transfer_bonus or {}

        # 计算加权分数：total_fitness × lifecycle_factor × (1 + transfer_bonus)
        weighted_scores: list[tuple[str, float]] = []
        for f in fitness_scores:
            factor = self._factors.get(f.lifecycle_stage, 1.0)
            bonus = transfer_bonus.get(f.product_id, 0.0)
            weighted = f.total_fitness * factor * (1.0 + bonus)
            weighted_scores.append((f.product_id, weighted))

        # 归一化分配
        total_weight = sum(w for _, w in weighted_scores)
        if total_weight <= 0:
            return [
                ExperimentAllocation(
                    product_id=pid,
                    allocated_slots=0,
                    allocation_pct=0.0,
                    previous_slots=previous_slots.get(pid, 0),
                    reason="zero_weight",
                )
                for pid, _ in weighted_scores
            ]

        allocations: list[ExperimentAllocation] = []
        assigned = 0
        raw_allocations: list[tuple[str, float, int]] = []

        for pid, weight in weighted_scores:
            share = weight / total_weight
            raw_slots = share * total_slots
            slots = max(1, round(raw_slots)) if raw_slots >= 0.5 else 0
            raw_allocations.append((pid, share, slots))

        # 调整分配使总和匹配 total_slots
        total_assigned = sum(s for _, _, s in raw_allocations)
        if total_assigned != total_slots:
            raw_allocations = self._adjust_slots(
                raw_allocations, total_slots, total_assigned
            )

        for pid, share, slots in raw_allocations:
            prev = previous_slots.get(pid, 0)
            change_pct = _safe_change(slots, prev)

            reason = self._build_reason(slots, prev, transfer_bonus.get(pid, 0.0))

            allocations.append(
                ExperimentAllocation(
                    product_id=pid,
                    allocated_slots=slots,
                    allocation_pct=round(share, 4),
                    previous_slots=prev,
                    change_pct=round(change_pct, 4),
                    reason=reason,
                )
            )

        return allocations

    def _adjust_slots(
        self,
        allocations: list[tuple[str, float, int]],
        target: int,
        current: int,
    ) -> list[tuple[str, float, int]]:
        """调整槽位分配以匹配目标值。"""
        diff = target - current
        if diff == 0:
            return allocations

        # 按份额从大到小排序，从份额最大的开始调整
        sorted_indices = sorted(
            range(len(allocations)),
            key=lambda i: allocations[i][1],
            reverse=True,
        )

        result = list(allocations)
        for i in sorted_indices:
            if diff == 0:
                break
            pid, share, slots = result[i]
            if diff > 0:
                result[i] = (pid, share, slots + 1)
                diff -= 1
            elif diff < 0 and slots > 0:
                result[i] = (pid, share, slots - 1)
                diff += 1

        return result

    def _build_reason(
        self, slots: int, previous: int, transfer_bonus: float
    ) -> str:
        """构建分配理由。"""
        if slots <= 0:
            return "zero_slots"
        if previous <= 0:
            return "new_allocation"
        if slots > previous:
            base = "increased"
            if transfer_bonus > 0:
                return f"{base}_with_transfer_bonus"
            return base
        if slots < previous:
            return "decreased"
        return "maintained"

    def get_lifecycle_factor(self, stage: ProductLifecycleStage) -> float:
        return self._factors.get(stage, 1.0)

    def __repr__(self) -> str:
        return f"ExperimentAllocator(stages={len(self._factors)})"


def _safe_change(new_val: int, previous: int) -> float:
    """安全计算变化百分比。"""
    if previous <= 0:
        return 0.0 if new_val <= 0 else 1.0
    return (new_val - previous) / previous