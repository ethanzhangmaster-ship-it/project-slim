"""
E16.6.7 — Keyword Value Scoring Engine.

Core algorithm: Score = Demand × Conversion × Quality × Revenue / Competition

Where:
  * Demand     = search_volume (raw)
  * Conversion = store_cvr (0–1)
  * Quality    = payer_rate × LTV (user monetisation potential)
  * Revenue    = 1.0 (neutral default, adjusted by revenue_factor)
  * Competition = keyword difficulty (0–1, lower = better)

This is the evolution of E16.6.6's KeywordValueScore — upgraded with the
full formula structure, normalisation, and ranking utilities.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.aso_intelligence.keyword.models import (
    KeywordReality,
    KeywordValueScore,
)


class KeywordValueScoringEngine:
    """Score keywords by commercial potential."""

    # ------------------------------------------------------------------ #
    def compute(
        self,
        reality: KeywordReality,
        revenue_factor: float = 1.0,
    ) -> KeywordValueScore:
        """Compute a full KeywordValueScore from a KeywordReality."""
        quality = reality.payer_rate * reality.ltv
        kws = KeywordValueScore(
            keyword=reality.keyword,
            country=reality.country,
            demand=float(reality.search_volume),
            conversion=reality.conversion_rate,
            quality=quality,
            revenue_factor=revenue_factor,
            competition=reality.competition,
            date=reality.date,
        )
        kws.compute()
        kws.estimated_installs = int(
            kws.demand * kws.conversion
        ) if kws.conversion > 0 else reality.installs
        kws.estimated_revenue = round(
            kws.estimated_installs * quality * revenue_factor, 2
        )
        return kws

    # ------------------------------------------------------------------ #
    def compute_from_data(
        self,
        keyword: str,
        country: str,
        search_volume: int,
        conversion_rate: float,
        payer_rate: float,
        ltv: float,
        competition: float = 0.5,
        revenue_factor: float = 1.0,
    ) -> KeywordValueScore:
        """Convenience: compute from raw data without building KeywordReality."""
        reality = KeywordReality(
            keyword=keyword,
            country=country,
            search_volume=search_volume,
            conversion_rate=conversion_rate,
            payer_rate=payer_rate,
            ltv=ltv,
            competition=competition,
        )
        return self.compute(reality, revenue_factor)

    # ------------------------------------------------------------------ #
    def rank(
        self, scores: List[KeywordValueScore]
    ) -> List[KeywordValueScore]:
        """Sort by score descending."""
        return sorted(scores, key=lambda s: s.score, reverse=True)

    def top_k(
        self, scores: List[KeywordValueScore], k: int = 10
    ) -> List[KeywordValueScore]:
        return self.rank(scores)[:k]

    # ------------------------------------------------------------------ #
    def identify_high_value(
        self, scores: List[KeywordValueScore], threshold: float = 100.0
    ) -> List[KeywordValueScore]:
        """Keywords above the commercial-value threshold."""
        return [s for s in scores if s.score >= threshold]

    def identify_low_value(
        self, scores: List[KeywordValueScore], threshold: float = 50.0
    ) -> List[KeywordValueScore]:
        """Keywords below the commercial-value threshold."""
        return [s for s in scores if s.score < threshold]

    # ------------------------------------------------------------------ #
    def normalise(
        self,
        scores: List[KeywordValueScore],
        scale: float = 100.0,
    ) -> List[Dict[str, Any]]:
        """Return normalised scores (0–100) and raw data for reporting."""
        max_score = max((s.score for s in scores), default=1.0)
        results: List[Dict[str, Any]] = []
        for s in self.rank(scores):
            normalised = s.score_normalized(max_score)
            results.append({
                "keyword": s.keyword,
                "country": s.country,
                "raw_score": round(s.score, 2),
                "normalised": normalised,
                "demand": s.demand,
                "conversion": s.conversion,
                "quality": s.quality,
                "competition": s.competition,
                "est_revenue": round(s.estimated_revenue, 2),
            })
        return results


__all__ = ["KeywordValueScoringEngine"]
