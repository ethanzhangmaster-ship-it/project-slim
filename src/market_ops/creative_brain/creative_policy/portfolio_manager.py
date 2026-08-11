"""V4.3 Portfolio Manager — dynamic portfolio allocation.

Manages creative portfolio composition:
  - Winner: 50% (proven high-ROAS)
  - Explore: 20% (novel combinations)
  - Adapt: 20% (cross-market adaptation)
  - Retest: 10% (previously failed, retry)

Allocation is dynamic, not fixed. Adjusts based on:
  - Market conditions
  - Trend changes
  - Risk signals
  - Historical performance
"""

from __future__ import annotations

from typing import Any

from .schemas import Portfolio, PortfolioCategory, CreativeTask, PolicyAction


class PortfolioManager:
    """Dynamic portfolio allocation manager."""

    DEFAULT_ALLOCATION = {
        PortfolioCategory.WINNER: 0.50,
        PortfolioCategory.EXPLORE: 0.20,
        PortfolioCategory.ADAPT: 0.20,
        PortfolioCategory.RETEST: 0.10,
    }

    def __init__(self) -> None:
        self._current: Portfolio = Portfolio(
            categories=dict(self.DEFAULT_ALLOCATION),
        )
        self._history: list[dict[str, Any]] = []

    def allocate(self, tasks: list[CreativeTask],
                 total_capacity: int = 100) -> Portfolio:
        """Allocate creative tasks into portfolio categories.

        Args:
            tasks: All creative tasks with decisions.
            total_capacity: Maximum creatives to allocate.

        Returns:
            Portfolio with category allocations.
        """
        # Categorize tasks
        winners = [t for t in tasks if t.action == PolicyAction.GENERATE
                   and t.roi_prediction >= 0.7]
        explores = [t for t in tasks if t.action == PolicyAction.GENERATE
                    and t.roi_prediction < 0.7]
        adapts = [t for t in tasks if t.action == PolicyAction.ADAPT]
        retests = [t for t in tasks if t.action == PolicyAction.RETEST]

        # Sort by priority within each category
        winners.sort(key=lambda t: -t.priority.total_score)
        explores.sort(key=lambda t: -t.priority.total_score)
        adapts.sort(key=lambda t: -t.priority.total_score)
        retests.sort(key=lambda t: -t.priority.total_score)

        # Allocate based on current ratios
        categories = self._current.categories
        allocations = {
            PortfolioCategory.WINNER: min(
                len(winners), int(total_capacity * categories.get(PortfolioCategory.WINNER, 0.5))
            ),
            PortfolioCategory.EXPLORE: min(
                len(explores), int(total_capacity * categories.get(PortfolioCategory.EXPLORE, 0.2))
            ),
            PortfolioCategory.ADAPT: min(
                len(adapts), int(total_capacity * categories.get(PortfolioCategory.ADAPT, 0.2))
            ),
            PortfolioCategory.RETEST: min(
                len(retests), int(total_capacity * categories.get(PortfolioCategory.RETEST, 0.1))
            ),
        }

        # Fill remaining capacity with winners
        remaining = total_capacity - sum(allocations.values())
        if remaining > 0 and len(winners) > allocations[PortfolioCategory.WINNER]:
            allocations[PortfolioCategory.WINNER] += remaining

        self._current = Portfolio(
            categories=categories,
            total_creatives=total_capacity,
            allocations=allocations,
            explore_ratio=self._current.explore_ratio,
            exploit_ratio=self._current.exploit_ratio,
        )

        self._history.append(self._current.to_dict())
        return self._current

    def update_allocation(self, new_categories: dict[PortfolioCategory, float]) -> None:
        """Update portfolio allocation ratios.

        Example: shift to 40% winner, 30% explore, 20% adapt, 10% retest
        """
        total = sum(new_categories.values())
        if abs(total - 1.0) > 0.01:
            # Normalize
            new_categories = {k: v / total for k, v in new_categories.items()}
        self._current.categories = new_categories

    def adjust_for_market_change(self, trend_shifts: dict[str, str]) -> Portfolio:
        """Adjust portfolio based on market trend changes.

        If trends are growing → increase WINNER
        If trends are dead → increase EXPLORE (find new winners)
        """
        growing_count = sum(1 for v in trend_shifts.values() if v == "growing")
        dead_count = sum(1 for v in trend_shifts.values() if v == "dead")
        total = max(len(trend_shifts), 1)

        # Adjust ratios
        if dead_count / total > 0.3:
            # Many dead trends → explore more
            new_categories = dict(self._current.categories)
            new_categories[PortfolioCategory.WINNER] = max(0.30, new_categories.get(PortfolioCategory.WINNER, 0.5) - 0.10)
            new_categories[PortfolioCategory.EXPLORE] = min(0.40, new_categories.get(PortfolioCategory.EXPLORE, 0.2) + 0.10)
            self.update_allocation(new_categories)
        elif growing_count / total > 0.3:
            # Many growing trends → exploit winners
            new_categories = dict(self._current.categories)
            new_categories[PortfolioCategory.WINNER] = min(0.60, new_categories.get(PortfolioCategory.WINNER, 0.5) + 0.05)
            new_categories[PortfolioCategory.EXPLORE] = max(0.10, new_categories.get(PortfolioCategory.EXPLORE, 0.2) - 0.05)
            self.update_allocation(new_categories)

        return self._current

    @property
    def current(self) -> Portfolio:
        return self._current

    @property
    def history(self) -> list[dict[str, Any]]:
        return list(self._history)