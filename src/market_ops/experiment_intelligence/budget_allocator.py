"""E9.9 Module 4: Budget Allocator.

Allocates experiment budgets across three strategies:
  - FIXED: equal split
  - DYNAMIC: winners get more, losers get less
  - BANDIT: Thompson Sampling (Beta distribution)
"""

from __future__ import annotations

import random
from typing import Any

from market_ops.experiment_intelligence.schemas import (
    ExperimentPlan, BudgetMode, PerformanceSnapshot,
)


class BudgetAllocator:
    """Allocates budget to experiments.

    Usage:
        allocator = BudgetAllocator()
        plans = allocator.allocate(plans, total_budget=2000, mode=BudgetMode.FIXED)
    """

    def __init__(self) -> None:
        self._performance_history: dict[str, list[PerformanceSnapshot]] = {}

    def allocate(
        self,
        plans: list[ExperimentPlan],
        total_budget: float = 2000.0,
        mode: BudgetMode = BudgetMode.FIXED,
        performance_history: dict[str, list[PerformanceSnapshot]] | None = None,
    ) -> list[ExperimentPlan]:
        """Allocate budget to experiments.

        Args:
            plans: Experiment plans to allocate budget to
            total_budget: Total budget across all experiments
            mode: Allocation strategy
            performance_history: Optional performance data for dynamic/bandit modes

        Returns:
            Updated plans with allocated budgets
        """
        if performance_history:
            self._performance_history = performance_history

        if mode == BudgetMode.FIXED:
            return self._allocate_fixed(plans, total_budget)
        elif mode == BudgetMode.DYNAMIC:
            return self._allocate_dynamic(plans, total_budget)
        elif mode == BudgetMode.BANDIT:
            return self._allocate_bandit(plans, total_budget)
        else:
            return self._allocate_fixed(plans, total_budget)

    # ── Fixed Allocation ───────────────────────────────────

    def _allocate_fixed(
        self, plans: list[ExperimentPlan], total_budget: float
    ) -> list[ExperimentPlan]:
        """Equal split: each experiment gets the same budget."""
        if not plans:
            return plans

        budget_per = total_budget / len(plans)
        for plan in plans:
            plan.budget = round(budget_per, 2)
            plan.daily_budget = round(
                budget_per / max(1, plan.duration_days), 2
            )

        return plans

    # ── Dynamic Allocation ─────────────────────────────────

    def _allocate_dynamic(
        self, plans: list[ExperimentPlan], total_budget: float
    ) -> list[ExperimentPlan]:
        """Winners get more budget, losers get less.

        Uses performance scores from PerformanceSnapshot history.
        """
        if not plans:
            return plans

        # Calculate performance scores
        scores = {}
        for plan in plans:
            score = self._get_performance_score(plan.experiment_id)
            scores[plan.experiment_id] = max(0.1, score)  # floor at 0.1

        # Normalize scores
        total_score = sum(scores.values())
        if total_score <= 0:
            return self._allocate_fixed(plans, total_budget)

        for plan in plans:
            weight = scores[plan.experiment_id] / total_score
            plan.budget = round(total_budget * weight, 2)
            plan.daily_budget = round(
                plan.budget / max(1, plan.duration_days), 2
            )

        return plans

    # ── Bandit Allocation (Thompson Sampling) ──────────────

    def _allocate_bandit(
        self, plans: list[ExperimentPlan], total_budget: float
    ) -> list[ExperimentPlan]:
        """Thompson Sampling: sample from Beta(alpha, beta) for each arm.

        Alpha = successes + 1, Beta = failures + 1
        """
        if not plans:
            return plans

        samples = {}
        for plan in plans:
            alpha, beta = self._get_beta_params(plan.experiment_id)
            # Random sampling is inherently non-deterministic; use seed for reproducibility
            sampled = random.betavariate(alpha, beta)
            samples[plan.experiment_id] = max(0.01, sampled)

        # Normalize sampled values
        total_sample = sum(samples.values())
        if total_sample <= 0:
            return self._allocate_fixed(plans, total_budget)

        for plan in plans:
            weight = samples[plan.experiment_id] / total_sample
            plan.budget = round(total_budget * weight, 2)
            plan.daily_budget = round(
                plan.budget / max(1, plan.duration_days), 2
            )

        return plans

    # ── Performance Helpers ────────────────────────────────

    def _get_performance_score(self, experiment_id: str) -> float:
        """Calculate performance score from history."""
        history = self._performance_history.get(experiment_id, [])
        if not history:
            return 0.5  # neutral score for no data

        latest = history[-1]
        # Weighted score: ROAS dominant + CTR secondary
        roas_score = min(latest.roas / 2.0, 1.0) if latest.roas > 0 else 0.0
        ctr_score = min(latest.ctr / 0.05, 1.0) if latest.ctr > 0 else 0.0
        return roas_score * 0.7 + ctr_score * 0.3

    def _get_beta_params(self, experiment_id: str) -> tuple[float, float]:
        """Get Beta distribution parameters for Thompson Sampling.

        Alpha = success_count + 1, Beta = failure_count + 1
        Success = ROAS > 1.0, Failure = ROAS <= 1.0
        """
        history = self._performance_history.get(experiment_id, [])
        if not history:
            return (1.0, 1.0)  # uniform prior

        successes = sum(1 for h in history if h.roas > 1.0)
        failures = len(history) - successes

        return (float(successes + 1), float(failures + 1))

    # ── Summary ────────────────────────────────────────────

    def get_allocation_summary(
        self, plans: list[ExperimentPlan], mode: BudgetMode
    ) -> dict[str, Any]:
        """Get summary of budget allocation."""
        budgets = [p.budget for p in plans]
        return {
            "mode": mode.value,
            "total_budget": round(sum(budgets), 2),
            "num_experiments": len(plans),
            "avg_budget": round(sum(budgets) / max(1, len(budgets)), 2),
            "min_budget": min(budgets) if budgets else 0,
            "max_budget": max(budgets) if budgets else 0,
            "budget_range": round(max(budgets) - min(budgets), 2) if budgets else 0,
        }