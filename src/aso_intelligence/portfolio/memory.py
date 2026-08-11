"""
E16.6.12 — Portfolio Memory.

Learns which genres/types of games benefit most from ASO investment.
Tracks genre-level ROI across the portfolio.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.aso_intelligence.experiment_memory.experiment_store import (
    ASOExperimentStore,
)
from src.aso_intelligence.experiment_memory.experiment_models import (
    ASOPattern,
)


class PortfolioMemory:
    """Learn genre-level ASO ROI patterns."""

    def __init__(self, store: Optional[ASOExperimentStore] = None):
        self.store = store
        self._investments: List[Dict] = []

    # ------------------------------------------------------------------ #
    def record_investment(
        self,
        game_id: str,
        genre: str,
        aso_investment_hours: float,
        revenue_uplift: float,
        success: bool,
    ) -> None:
        """Record one ASO investment outcome."""
        record = {
            "game_id": game_id,
            "genre": genre,
            "aso_investment_hours": aso_investment_hours,
            "revenue_uplift": revenue_uplift,
            "success": success,
        }
        self._investments.append(record)

        # Persist to E16.6.4 store
        if self.store and success:
            roi = revenue_uplift / max(aso_investment_hours, 0.5)
            pattern = ASOPattern(
                category=f"portfolio:{genre}",
                condition=f"aso_investment:{genre}",
                action="ASO_INVESTMENT",
                result=(
                    f"Genre {genre} ASO investment: "
                    f"${revenue_uplift:.0f} uplift from "
                    f"{aso_investment_hours:.0f}h (ROI {roi:.1f}x)"
                ),
                confidence=min(0.95, 0.4 + abs(revenue_uplift) / 500),
                sample_size=1,
                success_rate=1.0,
                reward=roi / 100.0,
                pattern_id=f"portfolio:aso_roi:{genre}",
            )
            self.store.record_pattern(pattern)

    # ------------------------------------------------------------------ #
    def genre_roi(self, genre: str) -> float:
        """Average ROI for a genre (revenue per hour)."""
        records = [r for r in self._investments if r["genre"] == genre]
        if not records:
            return 0.0

        total_uplift = sum(r["revenue_uplift"] for r in records)
        total_hours = sum(r["aso_investment_hours"] for r in records)
        return round(total_uplift / max(total_hours, 0.5), 4)

    # ------------------------------------------------------------------ #
    def genre_success_rate(self, genre: str) -> float:
        records = [r for r in self._investments if r["genre"] == genre]
        if not records:
            return 0.0
        successes = sum(1 for r in records if r["success"])
        return round(successes / len(records), 4)

    # ------------------------------------------------------------------ #
    def high_roi_genres(self, min_records: int = 2) -> List[str]:
        """Genres with proven high ASO ROI."""
        genres = set(r["genre"] for r in self._investments)
        results = []
        for g in genres:
            records = [r for r in self._investments if r["genre"] == g]
            if len(records) >= min_records:
                roi = self.genre_roi(g)
                if roi > 10:  # $10/hour threshold
                    results.append(g)
        return results

    # ------------------------------------------------------------------ #
    def investment_count(self) -> int:
        return len(self._investments)


__all__ = ["PortfolioMemory"]
