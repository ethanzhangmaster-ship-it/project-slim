"""
E16.6.7 — Keyword Opportunity Engine.

Analyses keyword gaps, competitor keyword signals, and portfolio gaps
to generate actionable KeywordOpportunity records.

Sources:
  1. Competitor keyword signals (upcoming E16.6.10 bridge)
  2. Gap analysis (high-value keywords not in current portfolio)
  3. Portfolio deprioritisation signals (DEAD keywords that should be dropped)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from src.aso_intelligence.keyword.models import (
    KeywordReality,
    KeywordValueScore,
    KeywordPortfolioEntry,
    KeywordPortfolioType,
    KeywordOpportunity,
)


class KeywordOpportunityEngine:
    """Identify keyword growth opportunities from multiple signals."""

    # ------------------------------------------------------------------ #
    def _opportunity_level(
        self, score: float, is_gap: bool = False
    ) -> str:
        if is_gap and score >= 500.0:
            return "HIGH"
        if score >= 200.0:
            return "HIGH"
        if score >= 50.0:
            return "MEDIUM"
        return "LOW"

    def _action_for(
        self, level: str, is_gap: bool
    ) -> str:
        if is_gap:
            return "ADD_KEYWORD"
        if level == "LOW":
            return "DEPRIORITIZE"
        return "INVESTIGATE"

    # ------------------------------------------------------------------ #
    def analyze_competitor_signal(
        self,
        keyword: str,
        country: str,
        competitor_rank: int,
        competitor_installs: int,
        your_current_keywords: Set[str],
        score: float = 0.0,
        reason: str = "",
    ) -> Optional[KeywordOpportunity]:
        """Generate opportunity from a competitor keyword signal.

        If the keyword is not already in your portfolio and has potential,
        this creates a HIGH-priority ADD_KEYWORD opportunity.
        """
        is_uncovered = keyword not in your_current_keywords
        if not is_uncovered:
            return None

        level = self._opportunity_level(score or 100.0, is_gap=True)
        if level in ("HIGH", "MEDIUM"):
            return KeywordOpportunity(
                keyword=keyword,
                country=country,
                opportunity_type=level,
                score=max(score, 50.0),
                reason=reason or (
                    f"Competitor keyword rising (rank #{competitor_rank}), "
                    f"not in your portfolio"
                ),
                action="ADD_KEYWORD",
                expected_cvr_uplift=0.05,
                expected_revenue_uplift=0.08,
                source="competitor_signal",
            )
        return None

    # ------------------------------------------------------------------ #
    def analyze_gap(
        self,
        score: KeywordValueScore,
        current_keywords: Set[str],
        current_portfolio: List[KeywordPortfolioEntry],
    ) -> Optional[KeywordOpportunity]:
        """Identify high-value keywords not currently targeted."""
        if score.keyword in current_keywords:
            return None

        # Check if already in portfolio
        in_portfolio = any(
            e.keyword == score.keyword for e in current_portfolio
        )
        if in_portfolio:
            return None

        level = self._opportunity_level(score.score, is_gap=True)
        if level in ("HIGH", "MEDIUM"):
            return KeywordOpportunity(
                keyword=score.keyword,
                country=score.country,
                opportunity_type=level,
                score=score.score,
                reason=(
                    f"High-value keyword not in current portfolio "
                    f"(score {score.score:.1f})"
                ),
                action="ADD_KEYWORD",
                expected_cvr_uplift=0.05,
                expected_revenue_uplift=0.10,
                source="keyword_analysis",
            )
        return None

    # ------------------------------------------------------------------ #
    def analyze_deprioritize(
        self,
        entry: KeywordPortfolioEntry,
    ) -> Optional[KeywordOpportunity]:
        """Identify DEAD keywords that should be dropped."""
        if entry.portfolio_type != KeywordPortfolioType.DEAD:
            return None

        return KeywordOpportunity(
            keyword=entry.keyword,
            country=entry.country,
            opportunity_type="LOW",
            score=entry.score,
            reason=(
                f"DEAD keyword: {entry.installs:,} installs but "
                f"LTV ${entry.ltv:.2f}. Reallocate to higher-value targets."
            ),
            action="DEPRIORITIZE",
            source="portfolio_gap",
        )

    # ------------------------------------------------------------------ #
    def analyze_all(
        self,
        scores: List[KeywordValueScore],
        portfolio: List[KeywordPortfolioEntry],
        competitor_keywords: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[KeywordOpportunity]:
        """Run all opportunity analyses and return ranked results."""
        opportunities: List[KeywordOpportunity] = []

        current_keywords = {e.keyword for e in portfolio}
        scored_keywords = {s.keyword for s in scores}

        # Gap analysis: high-value keywords not in portfolio
        for score in scores:
            gap = self.analyze_gap(score, current_keywords, portfolio)
            if gap:
                opportunities.append(gap)

        # Deprioritize analysis: DEAD keywords
        for entry in portfolio:
            dep = self.analyze_deprioritize(entry)
            if dep:
                opportunities.append(dep)

        # Competitor signal analysis
        if competitor_keywords:
            for kw, data in competitor_keywords.items():
                comp = self.analyze_competitor_signal(
                    keyword=kw,
                    country=data.get("country", "US"),
                    competitor_rank=data.get("rank", 30),
                    competitor_installs=data.get("installs", 0),
                    your_current_keywords=current_keywords,
                    score=data.get("score", 100.0),
                    reason=data.get("reason", ""),
                )
                if comp:
                    opportunities.append(comp)

        # Sort by score descending
        opportunities.sort(key=lambda o: o.score, reverse=True)
        return opportunities


__all__ = ["KeywordOpportunityEngine"]
