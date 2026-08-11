"""
E16.6.12 — Game Lifecycle Manager.

Determines each game's lifecycle stage for ASO investment decisions:
  * NEW — recently launched (<30 days), low installs → explore keywords
  * GROWTH — organic growth >10% → invest heavily
  * MATURE — stable revenue → maintain
  * DECLINING — 3+ months of decline → evaluate
  * SUNSET — revenue below threshold → stop investment
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.aso_intelligence.portfolio.models import (
    ASOGamePortfolio,
    ASOLifecycle,
)


class GameLifecycleManager:
    """Classify games into lifecycle stages."""

    SUNSET_REVENUE_THRESHOLD = 200  # $/month
    GROWTH_THRESHOLD = 0.10  # 10% organic growth
    NEW_DAY_THRESHOLD = 30  # days since launch

    # ------------------------------------------------------------------ #
    def classify(self, game: ASOGamePortfolio,
                 organic_growth: float = 0.0,
                 days_since_launch: Optional[int] = None,
                 months_declining: int = 0) -> ASOLifecycle:
        """Classify a game's lifecycle stage.

        ``organic_growth`` — % organic install change (month-over-month)
        ``days_since_launch`` — days since game launched
        ``months_declining`` — consecutive months of decline
        """
        # NEW: recently launched
        if days_since_launch is not None and days_since_launch < self.NEW_DAY_THRESHOLD:
            return ASOLifecycle.NEW

        # SUNSET: below revenue threshold
        if game.organic_revenue < self.SUNSET_REVENUE_THRESHOLD:
            return ASOLifecycle.SUNSET

        # DECLINING: 3+ months of decline
        if months_declining >= 3:
            return ASOLifecycle.DECLINING

        # GROWTH: organic growth > 10%
        if organic_growth >= self.GROWTH_THRESHOLD:
            return ASOLifecycle.GROWTH

        # MATURE: stable
        return ASOLifecycle.MATURE

    # ------------------------------------------------------------------ #
    def strategy(self, lifecycle: ASOLifecycle) -> str:
        """Get the ASO strategy for a lifecycle stage."""
        strategies = {
            ASOLifecycle.NEW: (
                "Focus on keyword discovery — identify top 10 keywords "
                "and ensure listing covers them"
            ),
            ASOLifecycle.GROWTH: (
                "Aggressive ASO investment — test keyword variants, "
                "optimise screenshots, iterate on icon"
            ),
            ASOLifecycle.MATURE: (
                "Maintain — monitor CVR, seasonal refreshes, "
                "defend against competitor changes"
            ),
            ASOLifecycle.DECLINING: (
                "Evaluate — test major listing refresh or new creative "
                "direction; if no improvement in 60 days → sunset"
            ),
            ASOLifecycle.SUNSET: (
                "Stop ASO investment — maintain current listing only. "
                "Reallocate resources to GROWTH games"
            ),
        }
        return strategies.get(lifecycle, "Monitor")

    # ------------------------------------------------------------------ #
    def classify_all(
        self,
        games: List[ASOGamePortfolio],
        growth_map: Dict[str, float] = None,
        days_map: Dict[str, int] = None,
        declining_map: Dict[str, int] = None,
    ) -> Dict[str, ASOLifecycle]:
        """Classify all games."""
        growth_map = growth_map or {}
        days_map = days_map or {}
        declining_map = declining_map or {}
        return {
            g.game_id: self.classify(
                g,
                organic_growth=growth_map.get(g.game_id, 0.0),
                days_since_launch=days_map.get(g.game_id),
                months_declining=declining_map.get(g.game_id, 0),
            )
            for g in games
        }


__all__ = ["GameLifecycleManager"]
