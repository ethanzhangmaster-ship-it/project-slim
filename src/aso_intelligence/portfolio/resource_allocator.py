"""
E16.6.12 — ASO Resource Allocator.

Distributes limited AI/human ASO resources across the game portfolio.
Top-ranked games get the largest allocation.
"""

from __future__ import annotations

from typing import List

from src.aso_intelligence.portfolio.models import (
    ASOGamePortfolio,
    ASOOpportunityScore,
    ASOResourceAllocation,
)


class ASOResourceAllocator:
    """Allocate ASO resources across the game portfolio."""

    MIN_CREATIVE = 5
    MIN_LOCALIZATION = 1
    MIN_EXPERIMENTS = 1

    # ------------------------------------------------------------------ #
    def allocate(
        self,
        ranked_scores: List[ASOOpportunityScore],
        games: List[ASOGamePortfolio],
        total_creative_budget: int = 100,
        total_localization_budget: int = 50,
        total_experiment_budget: int = 20,
    ) -> List[ASOResourceAllocation]:
        """Allocate budgets proportionally to ranking.

        Top 20% games get 50% of budget.
        Middle 40% get 30%.
        Bottom 40% get 20% (shared).
        """
        n = len(ranked_scores)
        if n == 0:
            return []

        game_map = {g.game_id: g for g in games}
        allocations: List[ASOResourceAllocation] = []

        for i, score in enumerate(ranked_scores):
            pct = i / max(n, 1)  # 0 = top, 1 = bottom
            game = game_map.get(score.game_id)

            if pct < 0.2:
                # Top 20%
                weight = 0.5 / max(0.2 * n, 1)
                priority = "high"
                reason = "Top ASO opportunity — invest heavily"
            elif pct < 0.6:
                # Middle 40%
                weight = 0.3 / max(0.4 * n, 1)
                priority = "medium"
                reason = "Moderate ASO opportunity — maintain investment"
            else:
                # Bottom 40%
                weight = 0.2 / max(0.4 * n, 1)
                priority = "low"
                reason = "Low ASO opportunity — maintain only"

            alloc = ASOResourceAllocation(
                game_id=score.game_id,
                rank=i + 1,
                creative_budget=max(
                    self.MIN_CREATIVE,
                    int(total_creative_budget * weight),
                ),
                localization_budget=max(
                    self.MIN_LOCALIZATION,
                    int(total_localization_budget * weight),
                ),
                experiment_budget=max(
                    self.MIN_EXPERIMENTS,
                    int(total_experiment_budget * weight),
                ),
                priority=priority,
                reason=reason,
            )
            allocations.append(alloc)

        return allocations


__all__ = ["ASOResourceAllocator"]
