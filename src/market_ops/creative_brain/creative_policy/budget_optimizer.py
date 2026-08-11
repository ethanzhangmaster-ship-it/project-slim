"""V4.3 Budget Optimizer — budget allocation across countries/platforms.

Input: ROI, Risk, Trend, Confidence per country
Output: Budget allocation (US 40%, JP 30%, KR 20%, SEA 10%)

Not equal distribution — optimized for maximum ROI.
"""

from __future__ import annotations

from typing import Any

from .schemas import BudgetAllocation


class BudgetOptimizer:
    """Optimize budget allocation across countries."""

    def __init__(self, total_budget: float = 10000.0) -> None:
        self._total_budget = total_budget
        self._current: BudgetAllocation = BudgetAllocation(total_budget=total_budget)
        self._history: list[BudgetAllocation] = []

    def allocate(self, countries: list[dict[str, Any]]) -> BudgetAllocation:
        """Allocate budget across countries based on performance.

        Args:
            countries: List of country performance dicts:
                {country, avg_roi, avg_confidence, trend_status, risk_level}

        Returns:
            BudgetAllocation with per-country amounts.
        """
        if not countries:
            return self._current

        # Calculate score per country
        scores: dict[str, float] = {}
        for c in countries:
            country = c["country"]
            roi = c.get("avg_roi", 0.5)
            confidence = c.get("avg_confidence", 0.5)
            trend = c.get("trend_status", "stable")

            # Trend multiplier
            trend_mult = {"growing": 1.3, "stable": 1.0, "declining": 0.7, "dead": 0.2}
            trend_factor = trend_mult.get(trend, 1.0)

            # Risk penalty
            risk_level = c.get("risk_level", "safe")
            risk_mult = {"safe": 1.0, "caution": 0.8, "warning": 0.5, "critical": 0.1, "halt": 0.0}
            risk_factor = risk_mult.get(risk_level, 1.0)

            # Composite score
            score = (roi * 0.4 + confidence * 0.3 + trend_factor * 0.2 + risk_factor * 0.1)
            scores[country] = max(0.01, score)

        # Normalize to percentages
        total_score = sum(scores.values())
        allocations: dict[str, float] = {}
        allocations_pct: dict[str, float] = {}
        for country, score in scores.items():
            pct = score / total_score
            allocations_pct[country] = round(pct * 100, 1)
            allocations[country] = round(self._total_budget * pct, 2)

        self._current = BudgetAllocation(
            total_budget=self._total_budget,
            allocations=allocations,
            allocations_pct=allocations_pct,
            remaining=self._total_budget - sum(allocations.values()),
        )

        self._history.append(self._current)
        return self._current

    def update_total_budget(self, new_total: float) -> None:
        """Update total budget and recalculate allocations."""
        self._total_budget = new_total
        if self._current.allocations_pct:
            allocations = {
                k: round(new_total * v / 100, 2)
                for k, v in self._current.allocations_pct.items()
            }
            self._current.allocations = allocations
            self._current.total_budget = new_total
            self._current.remaining = new_total - sum(allocations.values())

    @property
    def current(self) -> BudgetAllocation:
        return self._current

    @property
    def history(self) -> list[BudgetAllocation]:
        return list(self._history)