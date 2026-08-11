"""E12.6.2 — Priority Allocator。

多产品竞争资源时的优先级分配器。

使用 Softmax 算法将预算在多个产品之间进行分配，
确保不会完全赌博单一赢家。
"""

from __future__ import annotations

from typing import Any

from .models import (
    ProductResourceState,
    ResourceAllocation,
    ResourceRequest,
    ResourceType,
    calculate_priority_score,
    softmax_allocate,
)


class PriorityAllocator:
    """优先级分配器。

    负责:
      1. 计算每个产品的优先级评分
      2. 使用 softmax 分配预算
      3. 生成 ResourceAllocation 结果
    """

    def __init__(
        self,
        temperature: float = 1.0,
        min_allocation: float = 0.0,
    ) -> None:
        """初始化。

        Args:
            temperature:    softmax 温度参数（越大越均匀，越小越极化）
            min_allocation: 最小分配金额阈值
        """
        self.temperature = temperature
        self.min_allocation = min_allocation

    def calculate_scores(
        self,
        states: list[ProductResourceState],
        requests: list[ResourceRequest] | None = None,
    ) -> list[tuple[str, float]]:
        """计算所有产品的优先级评分。

        Args:
            states:   产品资源状态列表
            requests: 资源请求列表（可选）

        Returns:
            [(product_id, priority_score), ...]
        """
        scores: list[tuple[str, float]] = []

        for state in states:
            score = self._score_state(state)
            scores.append((state.product_id, score))

        return scores

    def _score_state(self, state: ProductResourceState) -> float:
        """为单个产品状态计算优先级评分。

        公式:
          priority_score = normalized_roi × learning_value × urgency × confidence

        其中:
          - normalized_roi = min(1.0, ROAS / 3.0)
          - learning_value = 1.0 - fatigue (疲劳越高，学习价值越低)
          - urgency = fatigue (疲劳越高，越紧急)
          - confidence = prediction_confidence
        """
        normalized_roi = max(0.0, min(1.0, state.recent_roas / 3.0))
        learning_value = max(0.0, min(1.0, 1.0 - state.fatigue_score))
        urgency = max(0.0, min(1.0, state.fatigue_score))
        confidence = max(0.0, min(1.0, state.prediction_confidence))

        return calculate_priority_score(
            expected_roi=state.recent_roas,
            learning_value=learning_value,
            urgency=urgency,
            confidence=confidence,
        )

    def allocate(
        self,
        states: list[ProductResourceState],
        total_budget: float,
        resource_type: ResourceType = ResourceType.EXPERIMENT_BUDGET,
        requests: list[ResourceRequest] | None = None,
    ) -> list[ResourceAllocation]:
        """分配资源。

        Args:
            states:         产品资源状态列表
            total_budget:   总预算
            resource_type:  资源类型
            requests:       资源请求列表（可选）

        Returns:
            ResourceAllocation 列表
        """
        if not states:
            return []

        scores = self.calculate_scores(states, requests)

        # 应用温度
        if self.temperature != 1.0:
            scores = [(pid, s / self.temperature) for pid, s in scores]

        # Softmax 分配
        allocations = softmax_allocate(
            scores=scores,
            total_budget=total_budget,
            min_allocation=self.min_allocation,
        )

        # 构建 ResourceAllocation 对象
        result: list[ResourceAllocation] = []
        for (pid, amount), (_, score) in zip(allocations, scores):
            reasons = self._build_reasons(pid, score, amount, total_budget)

            allocation = ResourceAllocation(
                product_id=pid,
                resource_type=resource_type,
                allocated_amount=amount,
                allocation_score=score,
                priority=round(score * 100),
                reasons=reasons,
                expected_roi=self._find_state_roas(states, pid),
                confidence=score,
            )
            result.append(allocation)

        return result

    def _build_reasons(
        self,
        product_id: str,
        score: float,
        amount: float,
        total_budget: float,
    ) -> list[str]:
        """构建分配理由。"""
        reasons: list[str] = []
        share = amount / total_budget if total_budget > 0 else 0.0

        if score >= 0.70:
            reasons.append(f"High priority (score={score:.2f})")
        elif score >= 0.40:
            reasons.append(f"Medium priority (score={score:.2f})")
        else:
            reasons.append(f"Low priority (score={score:.2f})")

        if amount > 0:
            reasons.append(f"Allocated {share:.1%} of budget")
        else:
            reasons.append("Below minimum allocation threshold")

        return reasons

    def _find_state_roas(
        self,
        states: list[ProductResourceState],
        product_id: str,
    ) -> float:
        for s in states:
            if s.product_id == product_id:
                return s.recent_roas
        return 0.0

    def allocate_budget_split(
        self,
        states: list[ProductResourceState],
        total_budget: float,
        split_ratio: dict[ResourceType, float] | None = None,
    ) -> list[ResourceAllocation]:
        """按资源类型拆分预算分配。

        例如:
          - 60% 实验预算
          - 30% 突变预算
          - 10% 探索预算

        Args:
            states:       产品状态列表
            total_budget: 总预算
            split_ratio:  各资源类型占比（默认 60/30/10）

        Returns:
            ResourceAllocation 列表
        """
        if split_ratio is None:
            split_ratio = {
                ResourceType.EXPERIMENT_BUDGET: 0.60,
                ResourceType.MUTATION_BUDGET: 0.30,
                ResourceType.GENERATION_CAPACITY: 0.10,
            }

        all_allocations: list[ResourceAllocation] = []
        for resource_type, ratio in split_ratio.items():
            budget = round(total_budget * ratio, 2)
            if budget <= 0:
                continue
            allocations = self.allocate(states, budget, resource_type=resource_type)
            all_allocations.extend(allocations)

        return all_allocations

    def __repr__(self) -> str:
        return (
            f"PriorityAllocator(temperature={self.temperature}, "
            f"min_allocation={self.min_allocation})"
        )