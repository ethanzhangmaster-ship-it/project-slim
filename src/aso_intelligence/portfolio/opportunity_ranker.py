"""
E16.6.12 — ASO Opportunity Ranker.

Ranks games by ASO investment opportunity. Revenue-aware: high-download
low-revenue games get downranked.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from src.aso_intelligence.portfolio.models import (
    ASOGamePortfolio,
    ASOOpportunityScore,
)


class ASOOpportunityRanker:
    """Rank games by ASO opportunity, revenue-aware."""

    # ------------------------------------------------------------------ #
    def rank(
        self,
        games: List[ASOGamePortfolio],
        scores: List[ASOOpportunityScore],
    ) -> List[ASOOpportunityScore]:
        """Rank games by opportunity score descending.

        Applies revenue-awareness: if a game has high installs but very low
        revenue (indicator of low payer quality), its score is penalised.
        """
        score_map: Dict[str, ASOOpportunityScore] = {
            s.game_id: s for s in scores
        }
        game_map: Dict[str, ASOGamePortfolio] = {
            g.game_id: g for g in games
        }

        ranked = []
        for s in scores:
            game = game_map.get(s.game_id)
            if game:
                # Revenue-aware penalty: high installs + low revenue → downrank
                if (game.organic_installs > 10000
                        and game.organic_revenue < 500):
                    s.score *= 0.3
                elif (game.organic_installs > 5000
                      and game.organic_revenue < 200):
                    s.score *= 0.5

            ranked.append(s)

        ranked.sort(key=lambda s: s.score, reverse=True)
        return ranked

    # ------------------------------------------------------------------ #
    def top_opportunities(
        self, ranked: List[ASOOpportunityScore], k: int = 5
    ) -> List[ASOOpportunityScore]:
        return ranked[:k]

    # ------------------------------------------------------------------ #
    def describe_opportunity(
        self,
        score: ASOOpportunityScore,
        game: Optional[ASOGamePortfolio] = None,
    ) -> str:
        """Generate a human-readable reason for the ranking."""
        parts: List[str] = []

        if score.revenue_potential >= 0.6:
            parts.append("High payer quality")
        elif score.revenue_potential >= 0.3:
            parts.append("Moderate revenue base")

        if score.growth_gap >= 0.5:
            parts.append("Large ASO improvement room")

        if game:
            if game.keyword_opportunity > 0.5:
                parts.append("Keyword improvement opportunity")
            if game.localization_opportunity > 0.5:
                parts.append("JP/US localization opportunity")
            if game.creative_opportunity > 0.5:
                parts.append("Screenshot/Icon improvement opportunity")

        if not parts:
            parts.append("Stable — maintain current level")

        return "; ".join(parts)


__all__ = ["ASOOpportunityRanker"]
