"""E12.6.5 — Portfolio Optimizer Controller。

元组合优化器 —— E12.6.5 核心控制器。

整合:
  - PortfolioAnalyzer:     产品组合状态分析
  - FitnessRanker:         产品适应度排名
  - AllocationEngine:      预算分配
  - LifecycleAllocator:    生命周期调整
  - ExperimentAllocator:   实验槽位分配

流程:
  Product State → Portfolio Snapshot → Fitness Ranking →
  Budget Allocation → Experiment Allocation → Portfolio Decisions →
  PortfolioResult
"""

from __future__ import annotations

from typing import Any

from .allocation_engine import AllocationEngine
from .experiment_allocator import ExperimentAllocator
from .fitness_ranker import FitnessRanker
from .lifecycle_allocator import LifecycleAllocator
from .models import (
    BudgetAllocation,
    ExperimentAllocation,
    PortfolioAction,
    PortfolioDecision,
    PortfolioResult,
    PortfolioSnapshot,
    ProductFitness,
    ProductLifecycleStage,
)
from .portfolio_analyzer import PortfolioAnalyzer


class PortfolioOptimizer:
    """元组合优化器。

    职责:
      1. 收集产品状态
      2. 计算产品适应度
      3. 排名产品
      4. 分配预算
      5. 分配实验槽位
      6. 生成组合决策
      7. 输出组合优化结果
    """

    def __init__(
        self,
        analyzer: PortfolioAnalyzer | None = None,
        ranker: FitnessRanker | None = None,
        allocation_engine: AllocationEngine | None = None,
        lifecycle_allocator: LifecycleAllocator | None = None,
        experiment_allocator: ExperimentAllocator | None = None,
    ) -> None:
        self.analyzer = analyzer or PortfolioAnalyzer()
        self.ranker = ranker or FitnessRanker()
        self.allocation_engine = allocation_engine or AllocationEngine()
        self.lifecycle_allocator = lifecycle_allocator or LifecycleAllocator()
        self.experiment_allocator = experiment_allocator or ExperimentAllocator()

        self._last_result: PortfolioResult | None = None

    def optimize(
        self,
        products: list[dict[str, Any]],
        total_budget: float = 0.0,
        total_experiments: int = 0,
        previous_budgets: dict[str, float] | None = None,
        previous_slots: dict[str, int] | None = None,
        transfer_bonus: dict[str, float] | None = None,
    ) -> PortfolioResult:
        """核心入口：优化产品组合。

        流程:
          1. Collect Product State → PortfolioSnapshot
          2. Calculate Product Fitness → Ranking
          3. Allocate Budget
          4. Allocate Experiments
          5. Generate Portfolio Decisions
          6. Build PortfolioResult

        Args:
            products:         产品数据列表，每个字典包含:
                              product_id, revenue_potential, growth_velocity,
                              creative_scalability, market_opportunity, risk,
                              lifecycle_stage, spend, revenue, risk_score,
                              growth_score, diversity_score
            total_budget:     总预算
            total_experiments: 总实验槽位
            previous_budgets: 之前预算 {product_id: amount}
            previous_slots:   之前实验槽位 {product_id: slots}
            transfer_bonus:   跨产品迁移加分 {product_id: bonus}

        Returns:
            PortfolioResult
        """
        previous_budgets = previous_budgets or {}
        previous_slots = previous_slots or {}

        # 1. Collect Product State
        for p in products:
            pid = p.get("product_id", "")
            self.analyzer.add_product_state(pid, p)

        snapshot = self.analyzer.analyze()

        # 2. Calculate Product Fitness
        fitness_scores = self.ranker.calculate_and_rank(products)

        # 3. Allocate Budget
        budget_allocations = self.allocation_engine.allocate(
            fitness_scores=fitness_scores,
            total_budget=total_budget,
            previous_budgets=previous_budgets,
        )

        # 4. Adjust Budget with Lifecycle
        budget_allocations = self._apply_lifecycle_budget(
            budget_allocations, fitness_scores
        )

        # 5. Allocate Experiments
        experiment_allocations = self.experiment_allocator.allocate(
            fitness_scores=fitness_scores,
            total_slots=total_experiments,
            previous_slots=previous_slots,
            transfer_bonus=transfer_bonus,
        )

        # 6. Adjust Experiments with Lifecycle
        experiment_allocations = self._apply_lifecycle_experiments(
            experiment_allocations, fitness_scores
        )

        # 7. Generate Portfolio Decisions
        decisions = self._generate_decisions(
            fitness_scores,
            budget_allocations,
            experiment_allocations,
        )

        # 8. Build Summary
        summary = self._build_summary(
            snapshot, fitness_scores, budget_allocations, decisions
        )

        result = PortfolioResult(
            total_budget=total_budget,
            total_experiments=total_experiments,
            budget_allocations=budget_allocations,
            experiment_allocations=experiment_allocations,
            decisions=decisions,
            fitness_scores=fitness_scores,
            snapshot=snapshot,
            summary=summary,
        )

        self._last_result = result
        return result

    def get_fitness_scores(
        self, products: list[dict[str, Any]]
    ) -> list[ProductFitness]:
        """计算并排名产品适应度。"""
        return self.ranker.calculate_and_rank(products)

    def get_last_result(self) -> PortfolioResult | None:
        """获取上次优化结果。"""
        return self._last_result

    def _apply_lifecycle_budget(
        self,
        allocations: list[BudgetAllocation],
        fitness_scores: list[ProductFitness],
    ) -> list[BudgetAllocation]:
        """应用生命周期调整预算。"""
        fitness_map = {f.product_id: f for f in fitness_scores}
        result = []
        for a in allocations:
            f = fitness_map.get(a.product_id)
            if f:
                result.append(
                    self.lifecycle_allocator.adjust_budget(a, f.lifecycle_stage)
                )
            else:
                result.append(a)
        return result

    def _apply_lifecycle_experiments(
        self,
        allocations: list[ExperimentAllocation],
        fitness_scores: list[ProductFitness],
    ) -> list[ExperimentAllocation]:
        """应用生命周期调整实验。"""
        fitness_map = {f.product_id: f for f in fitness_scores}
        result = []
        for a in allocations:
            f = fitness_map.get(a.product_id)
            if f:
                result.append(
                    self.lifecycle_allocator.adjust_experiments(
                        a, f.lifecycle_stage
                    )
                )
            else:
                result.append(a)
        return result

    def _generate_decisions(
        self,
        fitness_scores: list[ProductFitness],
        budget_allocations: list[BudgetAllocation],
        experiment_allocations: list[ExperimentAllocation],
    ) -> list[PortfolioDecision]:
        """生成组合决策。"""
        budget_map = {b.product_id: b for b in budget_allocations}
        experiment_map = {e.product_id: e for e in experiment_allocations}

        decisions = []
        for f in fitness_scores:
            budget = budget_map.get(f.product_id)
            experiment = experiment_map.get(f.product_id)

            # 确定动作
            action = self._determine_action(
                f, budget, experiment
            )

            # 预算变化
            budget_change = budget.change_pct if budget else 0.0

            # 实验变化
            experiment_change = 0
            if experiment and experiment.previous_slots > 0:
                experiment_change = experiment.allocated_slots - experiment.previous_slots

            # 置信度
            confidence = self._calculate_confidence(f)

            # 理由
            reasons = self._build_decision_reasons(f, budget, experiment)

            decision = PortfolioDecision(
                product_id=f.product_id,
                action=action,
                budget_change=round(budget_change, 4),
                experiment_change=experiment_change,
                confidence=round(confidence, 4),
                reasons=reasons,
                fitness=f.total_fitness,
                lifecycle_stage=f.lifecycle_stage,
            )
            decisions.append(decision)

        return decisions

    def _determine_action(
        self,
        fitness: ProductFitness,
        budget: BudgetAllocation | None,
        experiment: ExperimentAllocation | None,
    ) -> PortfolioAction:
        """确定组合动作。

        优先级:
          1. FITIGUE/DECAY/DEATH → 生命周期覆盖
          2. 高适应度 + 预算增加 → INCREASE_INVESTMENT
          3. 低适应度 + 预算减少 → DECREASE_INVESTMENT
          4. LAUNCH → EXPLORE
          5. 默认 → MAINTAIN
        """
        stage = fitness.lifecycle_stage

        # 生命周期阶段覆盖
        if stage in (
            ProductLifecycleStage.DECAY,
            ProductLifecycleStage.FATIGUE,
            ProductLifecycleStage.DEATH,
        ):
            return self.lifecycle_allocator.get_action(stage)

        # 预算变化驱动
        if budget:
            if budget.is_increased and fitness.total_fitness >= 0.60:
                return PortfolioAction.INCREASE_INVESTMENT
            if budget.is_decreased and fitness.total_fitness < 0.40:
                return PortfolioAction.DECREASE_INVESTMENT
            if budget.is_zero:
                return PortfolioAction.SUNSET

        # 生命周期阶段
        if stage == ProductLifecycleStage.LAUNCH:
            return PortfolioAction.EXPLORE
        if stage == ProductLifecycleStage.GROWTH:
            return PortfolioAction.INCREASE_INVESTMENT

        return PortfolioAction.MAINTAIN

    def _calculate_confidence(self, fitness: ProductFitness) -> float:
        """计算决策置信度。"""
        # 基于适应度级别和生命周期阶段
        base = fitness.total_fitness

        # 明确阶段置信度更高
        stage_boost = 0.0
        if fitness.lifecycle_stage in (
            ProductLifecycleStage.GROWTH,
            ProductLifecycleStage.PEAK,
        ):
            stage_boost = 0.10
        elif fitness.lifecycle_stage in (
            ProductLifecycleStage.DECAY,
            ProductLifecycleStage.DEATH,
        ):
            stage_boost = 0.15

        confidence = min(1.0, base + stage_boost)
        return round(confidence, 4)

    def _build_decision_reasons(
        self,
        fitness: ProductFitness,
        budget: BudgetAllocation | None,
        experiment: ExperimentAllocation | None,
    ) -> list[str]:
        """构建决策理由。"""
        reasons: list[str] = []

        # 适应度相关
        if fitness.is_high_potential:
            reasons.append(f"high fitness score ({fitness.total_fitness:.2f})")
        elif fitness.is_low_potential:
            reasons.append(f"low fitness score ({fitness.total_fitness:.2f})")

        # 生命周期阶段
        description = self.lifecycle_allocator.get_strategy_description(
            fitness.lifecycle_stage
        )
        reasons.append(f"lifecycle: {fitness.lifecycle_stage.value}")

        # 预算变化
        if budget:
            if budget.is_increased:
                reasons.append(
                    f"budget +{budget.change_pct:.0%}"
                )
            elif budget.is_decreased:
                reasons.append(
                    f"budget {budget.change_pct:.0%}"
                )

        # 实验变化
        if experiment:
            if experiment.is_increased:
                reasons.append(
                    f"experiments +{experiment.allocated_slots - experiment.previous_slots}"
                )
            elif experiment.is_decreased:
                reasons.append(
                    f"experiments {experiment.allocated_slots - experiment.previous_slots}"
                )

        return reasons

    def _build_summary(
        self,
        snapshot: PortfolioSnapshot,
        fitness_scores: list[ProductFitness],
        budget_allocations: list[BudgetAllocation],
        decisions: list[PortfolioDecision],
    ) -> str:
        """构建结果摘要。"""
        parts: list[str] = []

        parts.append(
            f"Portfolio: {len(fitness_scores)} products, "
            f"ROAS={snapshot.total_roas:.2f}, "
            f"growth={snapshot.growth_score:.2f}"
        )

        if fitness_scores:
            top = fitness_scores[0]
            parts.append(
                f"Top product: {top.product_id} (fitness={top.total_fitness:.2f})"
            )

        expand = sum(1 for d in decisions if d.is_expansion)
        contract = sum(1 for d in decisions if d.is_contraction)
        maintain = len(decisions) - expand - contract

        parts.append(
            f"Actions: {expand} expand, {maintain} maintain, {contract} contract"
        )

        total_budget = sum(a.allocated_budget for a in budget_allocations)
        parts.append(f"Total allocated: {total_budget:.0f}")

        return " | ".join(parts)

    def __repr__(self) -> str:
        return (
            f"PortfolioOptimizer(products={self.analyzer.product_count})"
        )