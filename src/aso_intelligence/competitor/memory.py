"""
E16.6.10 — Competitor Memory.

Learns from observed competitor patterns and stores them in E16.6.4's
pattern store for future reuse. Not "Merge Dragons changed icon today"
but "merge games using character-focused icons gained +35 ranks on average".
"""

from __future__ import annotations

from typing import Dict, List, Optional
from uuid import uuid4

from src.aso_intelligence.competitor.models import (
    CompetitorChange,
    CompetitorChangeType,
)
from src.aso_intelligence.experiment_memory.experiment_store import (
    ASOExperimentStore,
)
from src.aso_intelligence.experiment_memory.experiment_models import (
    ASOPattern,
)


class CompetitorMemory:
    """Observe competitor changes and learn reusable patterns.

    Connects to E16.6.4's pattern store so the ASO Growth Loop (E16.6.5)
    can reference competitor-validated strategies.
    """

    def __init__(self, store: Optional[ASOExperimentStore] = None):
        self.store = store
        self._observations: List[Dict] = []

    # ------------------------------------------------------------------ #
    def observe(
        self,
        category: str,
        change_type: CompetitorChangeType,
        rank_improvement: int,
        confidence: float,
        note: str = "",
    ) -> Dict:
        """Record one competitor observation for pattern mining.

        Stores the observation in memory for aggregate pattern learning
        when enough data accumulates.
        """
        obs = {
            "observation_id": str(uuid4()),
            "category": category,
            "change_type": change_type.value,
            "rank_improvement": rank_improvement,
            "confidence": confidence,
            "note": note,
        }
        self._observations.append(obs)
        return obs

    # ------------------------------------------------------------------ #
    def learn_pattern(
        self,
        category: str,
        change_type: CompetitorChangeType,
        num_observations: int,
        avg_rank_improvement: float,
        confidence: float,
    ) -> Optional[ASOPattern]:
        """Learn a pattern from aggregated competitor observations.

        Persists to E16.6.4 store if available.
        """
        if self.store is None:
            return None

        pattern_id = f"comp:{category}:{change_type.value}"
        result = (
            f"Competitors using {change_type.value} gained "
            f"avg +{avg_rank_improvement:.0f} ranks "
            f"(n={num_observations})"
        )

        pattern = ASOPattern(
            category=category,
            condition=f"competitor:{change_type.value}",
            action=pattern_id,
            result=result,
            confidence=confidence,
            sample_size=num_observations,
            success_rate=min(1.0, confidence),
            reward=round(avg_rank_improvement / 100.0, 4),
            pattern_id=pattern_id,
        )
        self.store.record_pattern(pattern)
        return pattern

    # ------------------------------------------------------------------ #
    def query_patterns(
        self, category: str, change_type: Optional[CompetitorChangeType] = None
    ) -> List[ASOPattern]:
        """Query competitor-validated patterns from E16.6.4 store."""
        if self.store is None:
            return []

        patterns = self.store.load_patterns()
        result = [
            p
            for p in patterns
            if p.category == category
            and p.condition.startswith("competitor:")
            and (
                change_type is None
                or change_type.value in p.condition
            )
        ]
        return result

    # ------------------------------------------------------------------ #
    def observations_count(self) -> int:
        return len(self._observations)


__all__ = ["CompetitorMemory"]
