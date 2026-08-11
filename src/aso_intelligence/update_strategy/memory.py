"""
E16.6.11 — Update Strategy Memory.

Records update experiences and learns patterns about what type of
updates work best for each market / update type combination.

Also provides seasonality intelligence for timing recommendations.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.aso_intelligence.update_strategy.models import (
    ASOUpdateExperience,
    UpdateType,
)
from src.aso_intelligence.experiment_memory.experiment_store import (
    ASOExperimentStore,
)
from src.aso_intelligence.experiment_memory.experiment_models import (
    ASOPattern,
)


class UpdateStrategyMemory:
    """Learn from past update experiences and seasonality patterns."""

    def __init__(self, store: Optional[ASOExperimentStore] = None):
        self.store = store
        self._experiences: List[ASOUpdateExperience] = []

    # ------------------------------------------------------------------ #
    def record_experience(self, experience: ASOUpdateExperience) -> None:
        """Record one update experience."""
        self._experiences.append(experience)

        # Also persist to E16.6.4 store as a pattern
        if self.store and experience.success:
            pattern = ASOPattern(
                category=f"update:{experience.market.lower()}",
                condition=f"update:{experience.update_type.value}",
                action=experience.update_type.value,
                result=(
                    f"Revenue {experience.revenue_change:+.0%} after "
                    f"{experience.update_type.value} update"
                ),
                confidence=min(0.95, 0.5 + abs(experience.revenue_change) * 2),
                sample_size=1,
                success_rate=1.0 if experience.success else 0.0,
                reward=experience.revenue_change,
                pattern_id=(
                    f"update:{experience.market}:"
                    f"{experience.update_type.value}"
                ),
            )
            self.store.record_pattern(pattern)

    # ------------------------------------------------------------------ #
    def query_experiences(
        self, market: Optional[str] = None,
        update_type: Optional[UpdateType] = None,
    ) -> List[ASOUpdateExperience]:
        """Query past experiences."""
        results = self._experiences
        if market:
            results = [e for e in results if e.market.upper() == market.upper()]
        if update_type:
            results = [e for e in results if e.update_type == update_type]
        return results

    # ------------------------------------------------------------------ #
    def success_rate(
        self, market: str, update_type: UpdateType
    ) -> float:
        """Success rate for a specific market + update type."""
        exps = self.query_experiences(market, update_type)
        if not exps:
            return 0.0
        successes = sum(1 for e in exps if e.success)
        return round(successes / len(exps), 4)

    # ------------------------------------------------------------------ #
    def avg_revenue_change(
        self, market: str, update_type: UpdateType
    ) -> float:
        exps = self.query_experiences(market, update_type)
        if not exps:
            return 0.0
        return round(
            sum(e.revenue_change for e in exps) / len(exps), 4
        )

    # ------------------------------------------------------------------ #
    def seasonality_patterns(
        self, month: int
    ) -> List[Dict[str, object]]:
        """Get seasonality intelligence for a month.

        Returns known seasonal patterns that can inform update timing.
        """
        patterns: List[Dict[str, object]] = []

        if month == 9:
            patterns.append({
                "event": "Halloween prep",
                "action": "Prepare spooky screenshots and themed icon",
                "expected_cvr_boost": 0.12,
                "deadline": "September 30",
            })
        elif month == 10:
            patterns.append({
                "event": "Halloween live",
                "action": "Halloween screenshots should be live",
                "expected_cvr_boost": 0.15,
                "deadline": "October 1",
            })
        elif month == 11:
            patterns.append({
                "event": "Holiday season prep",
                "action": "Prepare Christmas/winter screenshots",
                "expected_cvr_boost": 0.18,
                "deadline": "November 25",
            })
        elif month == 12:
            patterns.append({
                "event": "Holiday season live",
                "action": "Festive screenshots should be live",
                "expected_cvr_boost": 0.20,
                "deadline": "December 1",
            })

        return patterns

    # ------------------------------------------------------------------ #
    def experience_count(self) -> int:
        return len(self._experiences)


__all__ = ["UpdateStrategyMemory"]
