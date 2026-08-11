"""
E16.6.7 — Keyword Portfolio Manager.

Manages the keyword lifecycle — similar to how UA teams manage creative
lifecycles. Each keyword is classified as:

  * **CORE** — high revenue, stable ranking, high LTV → maintain
  * **GROWTH** — ranking improvement potential, medium-high value → invest
  * **EXPERIMENTAL** — unknown value → test
  * **DEAD** — high installs but low revenue → deprioritise
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.aso_intelligence.keyword.models import (
    KeywordReality,
    KeywordValueScore,
    KeywordPortfolioEntry,
    KeywordPortfolioType,
)


# Thresholds for portfolio classification
_CORE_MIN_LTV = 2.0
_CORE_MIN_REVENUE = 1000.0
_CORE_MIN_SCORE = 500.0
_GROWTH_MIN_SCORE = 100.0
_GROWTH_MAX_RANK = 30  # rank > 30 means room to improve
_DEAD_MAX_LTV = 0.5
_DEAD_MIN_INSTALLS = 5000  # high installs but low LTV


class KeywordPortfolioManager:
    """Classify keywords into lifecycle stages and manage the portfolio."""

    # ------------------------------------------------------------------ #
    def classify(
        self,
        score: KeywordValueScore,
        reality: Optional[KeywordReality] = None,
    ) -> KeywordPortfolioType:
        """Classify a single keyword into its portfolio stage.

        Priority order: DEAD → CORE → GROWTH → EXPERIMENTAL.
        """
        rank = reality.ranking_position if reality else 0
        revenue = reality.revenue if reality else 0.0
        installs = reality.installs if reality else 0
        ltv = reality.ltv if reality else 0.0

        # DEAD: high traffic but no commercial value
        if (score.quality < _DEAD_MAX_LTV * 0.01  # near-zero quality
                and installs >= _DEAD_MIN_INSTALLS):
            return KeywordPortfolioType.DEAD

        if ltv > 0 and ltv < _DEAD_MAX_LTV and installs >= _DEAD_MIN_INSTALLS:
            return KeywordPortfolioType.DEAD

        # CORE: high revenue, good rank, high LTV — all three required
        if (score.score >= _CORE_MIN_SCORE
                and (rank <= 15 or rank == 0)
                and ltv >= _CORE_MIN_LTV):
            return KeywordPortfolioType.CORE

        if (revenue >= _CORE_MIN_REVENUE
                and ltv >= _CORE_MIN_LTV
                and (rank <= 15 or rank == 0)):
            return KeywordPortfolioType.CORE

        # GROWTH: good score, room to improve rank
        if (score.score >= _GROWTH_MIN_SCORE
                and (rank > _GROWTH_MAX_RANK or rank == 0)):
            return KeywordPortfolioType.GROWTH

        if score.score >= _GROWTH_MIN_SCORE:
            return KeywordPortfolioType.GROWTH

        # Default: EXPERIMENTAL (unknown value)
        return KeywordPortfolioType.EXPERIMENTAL

    # ------------------------------------------------------------------ #
    def build_portfolio(
        self,
        scores: List[KeywordValueScore],
        realities: Dict[str, KeywordReality] = None,
    ) -> List[KeywordPortfolioEntry]:
        """Classify all scored keywords into a portfolio."""
        realities = realities or {}
        entries: List[KeywordPortfolioEntry] = []

        for score in scores:
            reality = realities.get(score.keyword)
            pt = self.classify(score, reality)

            reasons: List[str] = []
            if pt == KeywordPortfolioType.CORE:
                reasons.append("High revenue + stable ranking + high LTV")
                reasons.append("Strategy: Maintain")
            elif pt == KeywordPortfolioType.GROWTH:
                reasons.append("Good score, ranking improvement potential")
                reasons.append("Strategy: Invest")
            elif pt == KeywordPortfolioType.EXPERIMENTAL:
                reasons.append("Unknown commercial value")
                reasons.append("Strategy: Test")
            elif pt == KeywordPortfolioType.DEAD:
                reasons.append("High installs but low payer quality")
                reasons.append("Strategy: Deprioritise")

            entries.append(
                KeywordPortfolioEntry(
                    keyword=score.keyword,
                    country=score.country,
                    portfolio_type=pt,
                    score=score.score,
                    ranking_position=reality.ranking_position
                    if reality else 0,
                    revenue=reality.revenue if reality else 0.0,
                    installs=reality.installs if reality else 0,
                    ltv=reality.ltv if reality else 0.0,
                    reason="; ".join(reasons),
                )
            )

        return entries

    # ------------------------------------------------------------------ #
    def portfolio_summary(
        self, entries: List[KeywordPortfolioEntry]
    ) -> Dict[str, int]:
        """Count keywords in each portfolio stage."""
        summary: Dict[str, int] = {}
        for pt in KeywordPortfolioType:
            count = len([e for e in entries if e.portfolio_type == pt])
            if count > 0:
                summary[pt.value] = count
        return summary

    # ------------------------------------------------------------------ #
    def recommend_next_action(
        self, entry: KeywordPortfolioEntry
    ) -> str:
        """Recommend the next action for a portfolio entry."""
        mapping = {
            KeywordPortfolioType.CORE: "Maintain — monitor ranking stability",
            KeywordPortfolioType.GROWTH: (
                "Invest — optimise listing for this keyword, "
                "track ranking improvement"
            ),
            KeywordPortfolioType.EXPERIMENTAL: (
                "Test — add to listing, measure 14-day CVR impact"
            ),
            KeywordPortfolioType.DEAD: (
                "Deprioritise — reduce keyword weight, reallocate to "
                "higher-value targets"
            ),
        }
        return mapping.get(entry.portfolio_type, "Monitor")


__all__ = ["KeywordPortfolioManager"]
