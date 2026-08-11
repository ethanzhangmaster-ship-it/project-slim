"""V4.3 Creative Scheduler — schedule production order by priority.

Takes priority-ranked creatives and produces an ordered schedule.
Not random generation — highest priority first.

Example output:
  1. Dragon Merge US 95%
  2. Witch Evolution JP 92%
  3. Goods Sort US 89%
"""

from __future__ import annotations

from typing import Any

from .schemas import CreativeTask, PriorityScore, PolicyAction


class CreativeScheduler:
    """Schedule creative production by priority order."""

    def __init__(self) -> None:
        self._scheduled: list[CreativeTask] = []
        self._history: list[list[CreativeTask]] = []

    def schedule(self, tasks: list[CreativeTask],
                 max_generate: int = 50) -> list[CreativeTask]:
        """Schedule creatives by priority.

        Only schedules GENERATE and ADAPT tasks.
        RETEST and KILL are handled separately.

        Args:
            tasks: All creative tasks with decisions.
            max_generate: Maximum number to schedule for generation.

        Returns:
            Ordered list of scheduled tasks.
        """
        # Filter to actionable tasks
        actionable = [
            t for t in tasks
            if t.action in (PolicyAction.GENERATE, PolicyAction.ADAPT)
        ]

        # Sort by priority descending
        actionable.sort(key=lambda t: -t.priority.total_score)

        # Limit to max_generate
        scheduled = actionable[:max_generate]

        # Mark as scheduled
        for t in scheduled:
            t.status = "scheduled"

        self._scheduled = scheduled
        self._history.append(scheduled)
        return scheduled

    def get_schedule(self) -> list[CreativeTask]:
        """Get current schedule."""
        return list(self._scheduled)

    def get_top_n(self, n: int = 10) -> list[dict[str, Any]]:
        """Get top N scheduled creatives."""
        return [
            {
                "rank": i + 1,
                "creative_id": t.creative_id,
                "priority": t.priority.total_score,
                "action": t.action.value,
                "country": t.country,
                "dna": t.dna,
            }
            for i, t in enumerate(self._scheduled[:n])
        ]

    def get_schedule_by_country(self, country: str) -> list[CreativeTask]:
        """Get scheduled creatives filtered by country."""
        return [t for t in self._scheduled if t.country == country]

    def get_schedule_by_action(self, action: PolicyAction) -> list[CreativeTask]:
        """Get scheduled creatives filtered by action."""
        return [t for t in self._scheduled if t.action == action]

    def get_schedule_summary(self) -> dict[str, Any]:
        """Get schedule summary."""
        countries: dict[str, int] = {}
        actions: dict[str, int] = {}
        for t in self._scheduled:
            countries[t.country] = countries.get(t.country, 0) + 1
            actions[t.action.value] = actions.get(t.action.value, 0) + 1

        return {
            "total_scheduled": len(self._scheduled),
            "by_country": countries,
            "by_action": actions,
            "avg_priority": round(
                sum(t.priority.total_score for t in self._scheduled) /
                max(len(self._scheduled), 1), 1
            ),
        }