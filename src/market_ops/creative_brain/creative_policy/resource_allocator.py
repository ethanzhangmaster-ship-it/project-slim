"""V4.3 Resource Allocator — allocate limited generation capacity.

If today can only generate 20 creatives, the Brain decides:
  Dragon: 6, Merge: 5, Sort: 4, Runner: 2, Novel: 3

Not equal distribution — allocated by priority and portfolio.
"""

from __future__ import annotations

from typing import Any

from .schemas import CreativeTask, Portfolio, PortfolioCategory, PolicyAction


class ResourceAllocator:
    """Allocate limited creative generation capacity."""

    def __init__(self) -> None:
        self._allocations: list[dict[str, Any]] = []

    def allocate(self, tasks: list[CreativeTask],
                 portfolio: Portfolio,
                 max_capacity: int = 20) -> list[CreativeTask]:
        """Allocate tasks within capacity limit.

        Args:
            tasks: All creative tasks sorted by priority.
            portfolio: Current portfolio allocation.
            max_capacity: Maximum number of creatives to generate.

        Returns:
            Selected tasks that fit within capacity.
        """
        if len(tasks) <= max_capacity:
            for t in tasks:
                t.status = "scheduled"
            return tasks

        # Allocate by portfolio category
        selected: list[CreativeTask] = []

        # Sort by category and priority
        category_order = [
            PortfolioCategory.WINNER,
            PortfolioCategory.ADAPT,
            PortfolioCategory.EXPLORE,
            PortfolioCategory.RETEST,
        ]

        for category in category_order:
            alloc_count = portfolio.allocations.get(category, 0)
            # Cap at remaining capacity
            alloc_count = min(alloc_count, max_capacity - len(selected))

            # Get tasks for this category
            category_tasks = self._get_category_tasks(tasks, category)
            category_tasks.sort(key=lambda t: -t.priority.total_score)

            # Take top N from this category
            for t in category_tasks[:alloc_count]:
                t.status = "scheduled"
                selected.append(t)

        # Fill remaining with highest priority
        remaining = max_capacity - len(selected)
        if remaining > 0:
            already_selected = {t.creative_id for t in selected}
            remaining_tasks = [
                t for t in tasks
                if t.creative_id not in already_selected
                and t.action in (PolicyAction.GENERATE, PolicyAction.ADAPT)
            ]
            remaining_tasks.sort(key=lambda t: -t.priority.total_score)
            for t in remaining_tasks[:remaining]:
                t.status = "scheduled"
                selected.append(t)

        self._allocations.append({
            "capacity": max_capacity,
            "allocated": len(selected),
            "by_category": self._count_by_category(selected),
        })

        return selected

    def _get_category_tasks(self, tasks: list[CreativeTask],
                            category: PortfolioCategory) -> list[CreativeTask]:
        """Map tasks to portfolio categories."""
        if category == PortfolioCategory.WINNER:
            return [t for t in tasks
                    if t.action == PolicyAction.GENERATE and t.roi_prediction >= 0.7]
        elif category == PortfolioCategory.EXPLORE:
            return [t for t in tasks
                    if t.action == PolicyAction.GENERATE and t.roi_prediction < 0.7]
        elif category == PortfolioCategory.ADAPT:
            return [t for t in tasks if t.action == PolicyAction.ADAPT]
        elif category == PortfolioCategory.RETEST:
            return [t for t in tasks if t.action == PolicyAction.RETEST]
        return []

    def _count_by_category(self, tasks: list[CreativeTask]) -> dict[str, int]:
        """Count tasks by portfolio category."""
        counts: dict[str, int] = {}
        for t in tasks:
            if t.action == PolicyAction.GENERATE and t.roi_prediction >= 0.7:
                counts["winner"] = counts.get("winner", 0) + 1
            elif t.action == PolicyAction.GENERATE:
                counts["explore"] = counts.get("explore", 0) + 1
            elif t.action == PolicyAction.ADAPT:
                counts["adapt"] = counts.get("adapt", 0) + 1
            elif t.action == PolicyAction.RETEST:
                counts["retest"] = counts.get("retest", 0) + 1
        return counts

    def get_allocation_history(self) -> list[dict[str, Any]]:
        return list(self._allocations)