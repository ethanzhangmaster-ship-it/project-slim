"""
E16.6.12 — ASO Portfolio Scoring Engine.

Computes the ASO Opportunity Score for each game.

  Score = Revenue Potential × Growth Gap × Market Opportunity × Execution Confidence / Investment Cost
"""

from __future__ import annotations

from typing import Optional

from src.aso_intelligence.portfolio.models import (
    ASOGamePortfolio,
    ASOOpportunityScore,
)


class ASOPortfolioScoringEngine:
    """Score games by ASO investment opportunity."""

    # ------------------------------------------------------------------ #
    def compute(self, game: ASOGamePortfolio) -> ASOOpportunityScore:
        """Compute the full opportunity score for one game."""
        revenue_potential = self._revenue_potential(game)
        growth_gap = self._growth_gap(game)
        market_opportunity = self._market_opportunity(game)
        execution_confidence = self._execution_confidence(game)
        investment_cost = self._investment_cost(game)

        score = ASOOpportunityScore(
            game_id=game.game_id,
            revenue_potential=revenue_potential,
            growth_gap=growth_gap,
            market_opportunity=market_opportunity,
            execution_confidence=execution_confidence,
            investment_cost=investment_cost,
        )
        score.compute()
        return score

    # ------------------------------------------------------------------ #
    def _revenue_potential(self, game: ASOGamePortfolio) -> float:
        """Revenue potential (0–1): based on current organic revenue + payer quality."""
        rev = game.organic_revenue
        if rev >= 10000:
            return 1.0
        if rev >= 5000:
            return 0.8
        if rev >= 2000:
            return 0.6
        if rev >= 500:
            return 0.4
        if rev >= 100:
            return 0.2
        return 0.05

    # ------------------------------------------------------------------ #
    def _growth_gap(self, game: ASOGamePortfolio) -> float:
        """Growth gap (0–1): how much room for improvement.

        Low ASO score = high growth gap.
        """
        aso = game.aso_score
        if aso <= 20:
            return 1.0  # massive room
        if aso <= 40:
            return 0.8
        if aso <= 60:
            return 0.5
        if aso <= 80:
            return 0.2
        return 0.05  # near ceiling

    # ------------------------------------------------------------------ #
    def _market_opportunity(self, game: ASOGamePortfolio) -> float:
        """Market opportunity (0–1): combined opportunity signals."""
        opp = 0.2  # baseline

        opp += game.keyword_opportunity * 0.3
        opp += game.localization_opportunity * 0.25
        opp += game.creative_opportunity * 0.25

        return min(1.0, opp)

    # ------------------------------------------------------------------ #
    def _execution_confidence(self, game: ASOGamePortfolio) -> float:
        """Execution confidence (0–1): based on genre + past success."""
        return 0.6 + game.keyword_opportunity * 0.2 + game.creative_opportunity * 0.2

    # ------------------------------------------------------------------ #
    def _investment_cost(self, game: ASOGamePortfolio) -> float:
        """Relative investment cost."""
        return (game.ai_generation_cost * 0.3
                + game.human_review_cost * 0.7)


__all__ = ["ASOPortfolioScoringEngine"]
