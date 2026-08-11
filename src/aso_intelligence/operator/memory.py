"""
E16.6.13 — Operator Memory.

Records operation experiences and connects to E16.6.4 pattern store.
Provides stats on what actions work best per market/genre.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.aso_intelligence.operator.models import ASOOperationExperience
from src.aso_intelligence.experiment_memory.experiment_store import (
    ASOExperimentStore,
)
from src.aso_intelligence.experiment_memory.experiment_models import (
    ASOPattern,
)


class OperatorMemory:
    """Learn from past ASO operations."""

    def __init__(self, store: Optional[ASOExperimentStore] = None):
        self.store = store
        self._experiences: List[ASOOperationExperience] = []

    # ------------------------------------------------------------------ #
    def record(self, experience: ASOOperationExperience) -> None:
        """Record one operation experience and persist to E16.6.4."""
        self._experiences.append(experience)

        if self.store:
            market = experience.market.upper() if experience.market else "XX"
            pattern = ASOPattern(
                category=f"operator:{market}",
                condition=f"op:{experience.action_type}",
                action=experience.action_type,
                result=(
                    f"Reward {experience.reward:+.1%}, "
                    f"CVR {experience.cvr_change:+.0%}, "
                    f"Revenue {experience.revenue_change:+.0%}"
                ),
                confidence=min(0.95, 0.3 + abs(experience.reward) * 2),
                sample_size=1,
                success_rate=1.0 if experience.success else 0.0,
                reward=experience.reward,
                pattern_id=f"operator:{market}:{experience.action_type}",
            )
            self.store.record_pattern(pattern)

    # ------------------------------------------------------------------ #
    def stats(
        self,
        market: Optional[str] = None,
        action_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Statistics for a market + action type combo."""
        exps = self._experiences
        if market:
            exps = [e for e in exps if e.market.upper() == market.upper()]
        if action_type:
            exps = [e for e in exps if e.action_type == action_type]

        if not exps:
            return {"count": 0, "success_rate": 0.0, "avg_reward": 0.0}

        successes = sum(1 for e in exps if e.success)
        return {
            "count": len(exps),
            "success_rate": round(successes / len(exps), 4),
            "avg_reward": round(
                sum(e.reward for e in exps) / len(exps), 6
            ),
        }

    # ------------------------------------------------------------------ #
    def experience_count(self) -> int:
        return len(self._experiences)


__all__ = ["OperatorMemory"]
