"""E12.6.2 — Budget Optimizer。

动态预算调整器。

负责根据历史 ROI 表现动态调整预算：
  - Increase: ROI 超额 → 增加预算
  - Decrease: ROI 不足 → 减少预算
  - Freeze:   高风险 → 冻结预算
"""

from __future__ import annotations

from typing import Any

from .models import (
    BudgetAdjustment,
    ProductResourceState,
    ResourceType,
)


class BudgetOptimizer:
    """预算优化器。

    根据产品 ROI 表现动态调整预算分配。
    """

    # 默认参数
    ROI_TARGET = 1.2  # 目标 ROI
    ROI_EXCEED_THRESHOLD = 1.50  # 超过此值触发增加
    ROI_DEFICIT_THRESHOLD = 0.80  # 低于此值触发减少
    CONFIDENCE_MIN = 0.60  # 最低置信度要求
    HIGH_RISK_FATIGUE = 0.85  # 高风险疲劳阈值
    HIGH_RISK_DIVERSITY = 0.15  # 高风险多样性阈值

    INCREASE_RATIO = 0.30  # 增加 30%
    DECREASE_RATIO = 0.50  # 减少 50%
    MAX_INCREASE = 3.0  # 最大倍率
    MIN_BUDGET = 0.0  # 最低预算

    def __init__(
        self,
        roi_target: float | None = None,
        increase_ratio: float | None = None,
        decrease_ratio: float | None = None,
        max_increase: float | None = None,
    ) -> None:
        self.roi_target = roi_target or self.ROI_TARGET
        self.increase_ratio = increase_ratio or self.INCREASE_RATIO
        self.decrease_ratio = decrease_ratio or self.DECREASE_RATIO
        self.max_increase = max_increase or self.MAX_INCREASE

    def optimize(
        self,
        state: ProductResourceState,
        current_budget: float | None = None,
    ) -> BudgetAdjustment | None:
        """优化单个产品的预算。

        Args:
            state:          产品资源状态
            current_budget: 当前预算（不传则使用 state.allocated_budget）

        Returns:
            BudgetAdjustment 或 None（无需调整）
        """
        budget = current_budget if current_budget is not None else state.allocated_budget

        # 检查是否需要冻结
        freeze = self._check_freeze(state)
        if freeze:
            return freeze

        # 检查是否需要增加
        increase = self._check_increase(state, budget)
        if increase:
            return increase

        # 检查是否需要减少
        decrease = self._check_decrease(state, budget)
        if decrease:
            return decrease

        return None

    def _check_freeze(self, state: ProductResourceState) -> BudgetAdjustment | None:
        """检查是否需要冻结预算。

        条件:
          - fatigue > 0.85 且 diversity < 0.15
          - 或 ROAS < 0.3
        """
        if state.fatigue_score >= self.HIGH_RISK_FATIGUE and state.population_diversity <= self.HIGH_RISK_DIVERSITY:
            return BudgetAdjustment(
                product_id=state.product_id,
                resource_type=ResourceType.EXPERIMENT_BUDGET,
                previous_amount=state.allocated_budget,
                new_amount=0.0,
                reason=f"Freeze: extreme fatigue ({state.fatigue_score:.2f}) "
                f"and low diversity ({state.population_diversity:.2f})",
            )

        if state.recent_roas < 0.30 and state.allocated_budget > 0:
            return BudgetAdjustment(
                product_id=state.product_id,
                resource_type=ResourceType.EXPERIMENT_BUDGET,
                previous_amount=state.allocated_budget,
                new_amount=0.0,
                reason=f"Freeze: critically low ROAS ({state.recent_roas:.2f})",
            )

        return None

    def _check_increase(
        self,
        state: ProductResourceState,
        current_budget: float,
    ) -> BudgetAdjustment | None:
        """检查是否需要增加预算。

        条件:
          - ROI > 1.5x target
          - confidence > 0.6
          - 不处于高风险状态
        """
        if state.recent_roas < self.roi_target * 1.5:
            return None
        if state.prediction_confidence < self.CONFIDENCE_MIN:
            return None
        if state.fatigue_score >= self.HIGH_RISK_FATIGUE:
            return None

        previous = current_budget if current_budget > 0 else state.total_budget * 0.10
        new_amount = round(min(previous * (1.0 + self.increase_ratio), previous * self.max_increase), 2)

        return BudgetAdjustment(
            product_id=state.product_id,
            resource_type=ResourceType.EXPERIMENT_BUDGET,
            previous_amount=previous,
            new_amount=new_amount,
            reason=f"Increase: ROAS={state.recent_roas:.2f} exceeds target={self.roi_target:.2f}, "
            f"confidence={state.prediction_confidence:.2f}",
        )

    def _check_decrease(
        self,
        state: ProductResourceState,
        current_budget: float,
    ) -> BudgetAdjustment | None:
        """检查是否需要减少预算。

        条件:
          - ROI < target
          - 预算 > 0
        """
        if state.recent_roas >= self.roi_target:
            return None
        if current_budget <= 0:
            return None

        new_amount = round(max(current_budget * (1.0 - self.decrease_ratio), self.MIN_BUDGET), 2)

        return BudgetAdjustment(
            product_id=state.product_id,
            resource_type=ResourceType.EXPERIMENT_BUDGET,
            previous_amount=current_budget,
            new_amount=new_amount,
            reason=f"Decrease: ROAS={state.recent_roas:.2f} below target={self.roi_target:.2f}",
        )

    def optimize_all(
        self,
        states: list[ProductResourceState],
    ) -> list[BudgetAdjustment]:
        """批量优化所有产品。

        Returns:
            BudgetAdjustment 列表（仅包含需要调整的）
        """
        adjustments: list[BudgetAdjustment] = []
        for state in states:
            adj = self.optimize(state)
            if adj is not None:
                adjustments.append(adj)
        return adjustments

    def __repr__(self) -> str:
        return (
            f"BudgetOptimizer(roi_target={self.roi_target}, "
            f"increase={self.increase_ratio:.0%}, "
            f"decrease={self.decrease_ratio:.0%})"
        )