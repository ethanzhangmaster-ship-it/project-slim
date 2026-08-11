"""E12.6.5 — Lifecycle Allocator。

产品生命周期分配器 —— 根据产品所处阶段调整预算和实验策略。

生命周期策略:
  LAUNCH:   Explore —— 高实验、低预算（探索）
  GROWTH:   Increase —— 高预算、维持实验（放量）
  PEAK:     Maintain —— 维持预算、中等实验（效率最大化）
  PLATEAU:  Explore —— 中等预算、增加实验（重新激活）
  FATIGUE:  Decrease —— 减少预算、高实验（寻找新赢家）
  DECAY:    Harvest —— 最低预算、最少实验（收割）
  DEATH:    Sunset —— 零预算、零实验（退出）
"""

from __future__ import annotations

from .models import (
    BudgetAllocation,
    ExperimentAllocation,
    PortfolioAction,
    ProductFitness,
    ProductLifecycleStage,
    get_default_action,
)


# 生命周期预算调整因子
_LIFECYCLE_BUDGET_FACTOR: dict[ProductLifecycleStage, float] = {
    ProductLifecycleStage.LAUNCH: 0.5,
    ProductLifecycleStage.GROWTH: 1.5,
    ProductLifecycleStage.PEAK: 1.2,
    ProductLifecycleStage.PLATEAU: 0.8,
    ProductLifecycleStage.FATIGUE: 0.4,
    ProductLifecycleStage.DECAY: 0.15,
    ProductLifecycleStage.DEATH: 0.0,
}

# 生命周期实验调整因子
_LIFECYCLE_EXPERIMENT_FACTOR: dict[ProductLifecycleStage, float] = {
    ProductLifecycleStage.LAUNCH: 2.0,
    ProductLifecycleStage.GROWTH: 1.2,
    ProductLifecycleStage.PEAK: 1.0,
    ProductLifecycleStage.PLATEAU: 1.5,
    ProductLifecycleStage.FATIGUE: 1.8,
    ProductLifecycleStage.DECAY: 0.5,
    ProductLifecycleStage.DEATH: 0.0,
}

# 生命周期对应的默认动作
_LIFECYCLE_ACTION: dict[ProductLifecycleStage, PortfolioAction] = {
    ProductLifecycleStage.LAUNCH: PortfolioAction.EXPLORE,
    ProductLifecycleStage.GROWTH: PortfolioAction.INCREASE_INVESTMENT,
    ProductLifecycleStage.PEAK: PortfolioAction.MAINTAIN,
    ProductLifecycleStage.PLATEAU: PortfolioAction.EXPLORE,
    ProductLifecycleStage.FATIGUE: PortfolioAction.DECREASE_INVESTMENT,
    ProductLifecycleStage.DECAY: PortfolioAction.HARVEST,
    ProductLifecycleStage.DEATH: PortfolioAction.SUNSET,
}


class LifecycleAllocator:
    """生命周期分配器。

    根据产品所处生命周期阶段调整预算和实验分配。
    """

    def __init__(
        self,
        budget_factors: dict[ProductLifecycleStage, float] | None = None,
        experiment_factors: dict[ProductLifecycleStage, float] | None = None,
    ) -> None:
        self._budget_factors = dict(budget_factors or _LIFECYCLE_BUDGET_FACTOR)
        self._experiment_factors = dict(
            experiment_factors or _LIFECYCLE_EXPERIMENT_FACTOR
        )

    def adjust_budget(
        self,
        allocation: BudgetAllocation,
        stage: ProductLifecycleStage,
    ) -> BudgetAllocation:
        """根据生命周期阶段调整预算分配。

        Args:
            allocation: 原始预算分配
            stage:      生命周期阶段

        Returns:
            调整后的 BudgetAllocation
        """
        factor = self._budget_factors.get(stage, 1.0)
        adjusted = round(allocation.allocated_budget * factor, 2)
        prev = allocation.previous_budget
        change_pct = (
            (adjusted - prev) / prev if prev > 0 else 0.0
        )

        return BudgetAllocation(
            product_id=allocation.product_id,
            allocated_budget=adjusted,
            allocation_pct=allocation.allocation_pct,
            previous_budget=prev,
            change_pct=round(change_pct, 4),
            reason=f"lifecycle_adjusted_{stage.value}",
        )

    def adjust_experiments(
        self,
        allocation: ExperimentAllocation,
        stage: ProductLifecycleStage,
    ) -> ExperimentAllocation:
        """根据生命周期阶段调整实验分配。

        Args:
            allocation: 原始实验分配
            stage:      生命周期阶段

        Returns:
            调整后的 ExperimentAllocation
        """
        factor = self._experiment_factors.get(stage, 1.0)
        adjusted = max(0, round(allocation.allocated_slots * factor))
        prev = allocation.previous_slots
        change_pct = (
            (adjusted - prev) / prev if prev > 0 else 0.0
        )

        return ExperimentAllocation(
            product_id=allocation.product_id,
            allocated_slots=adjusted,
            allocation_pct=allocation.allocation_pct,
            previous_slots=prev,
            change_pct=round(change_pct, 4),
            reason=f"lifecycle_adjusted_{stage.value}",
        )

    def get_action(
        self, stage: ProductLifecycleStage
    ) -> PortfolioAction:
        """获取生命周期阶段对应的默认组合动作。

        LAUNCH → EXPLORE
        GROWTH → INCREASE_INVESTMENT
        PEAK   → MAINTAIN
        DECAY  → HARVEST
        DEATH  → SUNSET
        """
        return _LIFECYCLE_ACTION.get(stage, PortfolioAction.MAINTAIN)

    def get_budget_factor(self, stage: ProductLifecycleStage) -> float:
        return self._budget_factors.get(stage, 1.0)

    def get_experiment_factor(self, stage: ProductLifecycleStage) -> float:
        return self._experiment_factors.get(stage, 1.0)

    def get_strategy_description(
        self, stage: ProductLifecycleStage
    ) -> str:
        """获取生命周期阶段的策略描述。"""
        descriptions = {
            ProductLifecycleStage.LAUNCH: "探索期：高实验投入，低预算，快速验证产品方向",
            ProductLifecycleStage.GROWTH: "增长期：高预算投入，维持实验，快速放量",
            ProductLifecycleStage.PEAK: "巅峰期：维持预算，效率最大化，精细运营",
            ProductLifecycleStage.PLATEAU: "平台期：增加实验投入，寻找新增长点",
            ProductLifecycleStage.FATIGUE: "疲劳期：减少预算，高实验投入，寻找新赢家",
            ProductLifecycleStage.DECAY: "衰退期：最低预算，收割剩余价值",
            ProductLifecycleStage.DEATH: "死亡期：停止投入，退出市场",
        }
        return descriptions.get(stage, "未知阶段")

    def __repr__(self) -> str:
        return f"LifecycleAllocator(stages={len(self._budget_factors)})"