"""Opportunity Ranking Engine — score, sort, and recommend actions."""

from __future__ import annotations

from typing import Any

from market_ops.creative_opportunity.schemas import (
    Opportunity,
    RankedOpportunity,
    Recommendation,
    OpportunityStatus,
)


class OpportunityRanker:
    """Rank opportunities and generate BUILD/WATCH/IGNORE recommendations."""

    # Score thresholds for recommendations
    BUILD_THRESHOLD = 80.0
    WATCH_THRESHOLD = 60.0

    def __init__(self) -> None:
        self._ranked: list[RankedOpportunity] = []

    def rank(self, opportunities: list[Opportunity]) -> list[RankedOpportunity]:
        """Rank all opportunities and assign recommendations.

        Returns:
            Sorted list of RankedOpportunity (highest score first).
        """
        sorted_opps = sorted(opportunities, key=lambda o: o.score, reverse=True)
        self._ranked = []

        for rank, opp in enumerate(sorted_opps, start=1):
            rec, reason = self._decide(opp, rank, len(sorted_opps))
            ranked = RankedOpportunity(
                opportunity=opp,
                rank=rank,
                recommendation=rec,
                reason=reason,
            )
            self._ranked.append(ranked)

        return list(self._ranked)

    def get_build_recommendations(self) -> list[RankedOpportunity]:
        """Return only BUILD recommendations."""
        return [r for r in self._ranked if r.recommendation == Recommendation.BUILD]

    def get_watch_recommendations(self) -> list[RankedOpportunity]:
        """Return only WATCH recommendations."""
        return [r for r in self._ranked if r.recommendation == Recommendation.WATCH]

    def get_top(self, n: int = 5) -> list[RankedOpportunity]:
        """Return top N ranked opportunities."""
        return self._ranked[:n]

    # ── Decision Logic ──────────────────────────────────────

    def _decide(
        self, opp: Opportunity, rank: int, total: int
    ) -> tuple[Recommendation, str]:
        """Decide recommendation for a single opportunity.

        Rules:
            Score >= 80   → BUILD
            Score >= 60   → WATCH
            Score < 60    → IGNORE
        """
        if opp.score >= self.BUILD_THRESHOLD:
            return (
                Recommendation.BUILD,
                f"High score ({opp.score:.0f}) with strong {self._strongest_component(opp)}. "
                f"Estimated {opp.estimated_dev_days} days to prototype.",
            )
        elif opp.score >= self.WATCH_THRESHOLD:
            return (
                Recommendation.WATCH,
                f"Promising ({opp.score:.0f}) but needs more validation. "
                f"Monitor market signals for {opp.name}.",
            )
        else:
            return (
                Recommendation.IGNORE,
                f"Score ({opp.score:.0f}) below threshold. Market momentum or "
                f"competition gap too weak.",
            )

    @staticmethod
    def _strongest_component(opp: Opportunity) -> str:
        """Identify the strongest scoring component for messaging."""
        components = {
            "market momentum": opp.market_momentum,
            "competition gap": opp.competition_gap,
            "UA potential": opp.ua_potential,
            "creative fit": opp.creative_fit,
            "historical success": opp.historical_success,
        }
        return max(components, key=components.get)
