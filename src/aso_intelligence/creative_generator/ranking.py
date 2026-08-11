"""
E16.6.8 — Creative Ranking Engine.

Ranks generated creative candidates by commercial potential.

Formula: Final Score = Vision Score × ASO Relevance × Historical Pattern × Revenue Prediction

Where:
  * Vision Score = weighted score from ASOVisionEvaluator
  * ASO Relevance = how well the candidate matches the ASO opportunity
  * Historical Pattern = boost from E16.6.4 if similar creative patterns succeeded
  * Revenue Prediction = adjusted for user quality (high CVR + low LTV → downweight)
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.aso_intelligence.creative_generator.models import (
    CreativeCandidate,
    CreativeScore,
)


class CreativeRankingEngine:
    """Rank creative candidates and select the best one."""

    def __init__(self):
        # Weights for the composite formula
        self.vision_weight: float = 0.4
        self.relevance_weight: float = 0.3
        self.pattern_weight: float = 0.2
        self.revenue_weight: float = 0.1

    # ------------------------------------------------------------------ #
    def compute_composite(
        self,
        candidate: CreativeCandidate,
        relevance_score: float = 1.0,
        pattern_boost: float = 1.0,
        revenue_quality: float = 1.0,
    ) -> float:
        """Compute the composite final score.

        ``relevance_score`` — how well the candidate addresses the ASO insight (0–2)
        ``pattern_boost`` — multiplier from historical pattern success (1.0 = neutral)
        ``revenue_quality`` — payer quality multiplier (E16.6.6; < 1 = penalise)
        """
        if candidate.score is None:
            return 0.0

        vision = candidate.score.compute_final()

        # Cap extreme values
        relevance = min(2.0, max(0.0, relevance_score))
        pattern = min(2.0, max(0.5, pattern_boost))
        revenue = min(1.5, max(0.1, revenue_quality))

        # Weighted composite
        composite = (
            self.vision_weight * vision
            + self.relevance_weight * relevance
            + self.pattern_weight * pattern
            + self.revenue_weight * revenue
        )
        return round(composite, 4)

    # ------------------------------------------------------------------ #
    def rank(
        self,
        candidates: List[CreativeCandidate],
        relevance_map: Optional[Dict[str, float]] = None,
        pattern_map: Optional[Dict[str, float]] = None,
        revenue_quality: float = 1.0,
    ) -> List[CreativeCandidate]:
        """Rank candidates by composite score descending.

        ``relevance_map`` — candidate_id → relevance_score
        ``pattern_map``   — candidate_id → pattern_boost
        """
        relevance_map = relevance_map or {}
        pattern_map = pattern_map or {}

        for c in candidates:
            rel = relevance_map.get(c.candidate_id, 1.0)
            pat = pattern_map.get(c.candidate_id, 1.0)
            c.score = c.score or CreativeScore()
            c.score.pattern_boost = pat
            c.score.revenue_quality = revenue_quality

        ranked = sorted(
            candidates,
            key=lambda c: (
                self.compute_composite(
                    c,
                    relevance_score=relevance_map.get(c.candidate_id, 1.0),
                    pattern_boost=pattern_map.get(c.candidate_id, 1.0),
                    revenue_quality=revenue_quality,
                )
                if c.score else 0.0
            ),
            reverse=True,
        )
        return ranked

    # ------------------------------------------------------------------ #
    def select_top(
        self,
        candidates: List[CreativeCandidate],
        k: int = 1,
        revenue_quality: float = 1.0,
    ) -> List[CreativeCandidate]:
        """Select top-k candidates after ranking with revenue adjustment.

        If ``revenue_quality < 0.8`` (from E16.6.6 feedback), high-CVR
        candidates are penalised, giving way to quality-focused variants.
        """
        ranked = self.rank(candidates, revenue_quality=revenue_quality)

        # Apply revenue gate: if previous pattern showed low user quality,
        # deprioritise hook-heavy candidates in favour of clarity-heavy ones
        if revenue_quality < 0.8:
            quality_ranked = sorted(
                ranked,
                key=lambda c: (
                    c.score.clarity_score * 0.6 + c.score.emotional_score * 0.4
                    if c.score else 0.0
                ),
                reverse=True,
            )
            return quality_ranked[:k]

        return ranked[:k]

    # ------------------------------------------------------------------ #
    def format_ranking(
        self, candidates: List[CreativeCandidate]
    ) -> List[Dict]:
        """Format ranking for display."""
        return [
            {
                "variant": c.variant_label,
                "composite": self.compute_composite(c),
                "vision": c.score.compute_final() if c.score else 0.0,
                "hook": c.score.hook_score if c.score else 0.0,
                "clarity": c.score.clarity_score if c.score else 0.0,
                "compliance": c.score.store_compliance if c.score else 1.0,
            }
            for c in candidates
        ]


__all__ = ["CreativeRankingEngine"]
