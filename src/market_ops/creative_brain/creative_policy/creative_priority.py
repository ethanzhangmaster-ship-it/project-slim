"""V4.3 Creative Priority — compute priority scores for all creatives.

Priority = ROI × Trend × Confidence × Novelty × Budget
Output: 0-100 score, sorted queue.

Used by Creative Scheduler and Resource Allocator.
"""

from __future__ import annotations

from typing import Any

from .schemas import PriorityScore


class CreativePriority:
    """Compute and rank creative priority scores."""

    # Weight multipliers for each dimension
    WEIGHTS = {
        "roi": 0.30,
        "trend": 0.25,
        "confidence": 0.25,
        "novelty": 0.10,
        "budget": 0.10,
    }

    def compute(self, creative_id: str, dna: dict[str, Any],
                roi_prediction: float, trend_status: str,
                reasoning_confidence: float, budget: float,
                country: str = "", platform: str = "facebook",
                existing_dna_list: list[dict[str, Any]] | None = None,
                ) -> PriorityScore:
        """Compute priority score for a single creative.

        Args:
            creative_id: Unique creative identifier.
            dna: DNA attributes of the creative.
            roi_prediction: Predicted ROAS (0-1+).
            trend_status: growing/stable/declining/dead.
            reasoning_confidence: Reasoning engine confidence (0-1).
            budget: Allocated budget.
            country: Target country.
            platform: Target platform.
            existing_dna_list: Existing creatives for novelty calculation.

        Returns:
            PriorityScore with 0-100 total_score.
        """
        # 1. ROI score (0-25)
        roi_score = min(roi_prediction, 1.5) / 1.5 * 25

        # 2. Trend score (0-25)
        trend_map = {"growing": 25, "stable": 15, "declining": 8, "dead": 0}
        trend_score = trend_map.get(trend_status, 10)

        # 3. Confidence score (0-25)
        confidence_score = reasoning_confidence * 25

        # 4. Novelty score (0-25) — diversity bonus
        novelty_score = self._compute_novelty(dna, existing_dna_list or [])

        # 5. Budget score (0-25) — efficiency
        budget_score = self._compute_budget_efficiency(budget)

        # Weighted total
        total_score = (
            roi_score * self.WEIGHTS["roi"] * 4 +
            trend_score * self.WEIGHTS["trend"] * 4 +
            confidence_score * self.WEIGHTS["confidence"] * 4 +
            novelty_score * self.WEIGHTS["novelty"] * 4 +
            budget_score * self.WEIGHTS["budget"] * 4
        )
        total_score = min(100.0, max(0.0, total_score))

        return PriorityScore(
            creative_id=creative_id,
            total_score=round(total_score, 1),
            roi_score=round(roi_score, 2),
            trend_score=round(trend_score, 2),
            confidence_score=round(confidence_score, 2),
            novelty_score=round(novelty_score, 2),
            budget_score=round(budget_score, 2),
            country=country,
            platform=platform,
            dna=dna,
        )

    def _compute_novelty(self, dna: dict[str, Any],
                          existing: list[dict[str, Any]]) -> float:
        """Compute novelty score based on DNA diversity.

        Higher score = more different from existing creatives.
        """
        if not existing:
            return 25.0  # First creative is maximally novel

        # Count matching DNA dimensions
        max_overlap = 0
        for existing_dna in existing:
            overlap = sum(
                1 for k in dna if k in existing_dna and dna[k] == existing_dna[k]
            )
            max_overlap = max(max_overlap, overlap)

        # Fewer overlaps = more novel = higher score
        dna_keys = len(dna) or 1
        overlap_ratio = max_overlap / dna_keys
        return 25.0 * (1.0 - overlap_ratio)

    def _compute_budget_efficiency(self, budget: float) -> float:
        """Compute budget efficiency score.

        Lower budget per creative = higher efficiency (within reason).
        """
        if budget <= 0:
            return 0.0
        if budget <= 100:
            return 25.0
        if budget <= 200:
            return 20.0
        if budget <= 500:
            return 15.0
        return 10.0

    def rank(self, scores: list[PriorityScore]) -> list[PriorityScore]:
        """Rank creatives by total_score descending."""
        return sorted(scores, key=lambda s: -s.total_score)

    def compute_batch(self, creatives: list[dict[str, Any]],
                      existing_dna_list: list[dict[str, Any]] | None = None,
                      ) -> list[PriorityScore]:
        """Compute priority for a batch of creatives.

        Args:
            creatives: List of creative dicts with keys:
                creative_id, dna, roi_prediction, trend_status,
                reasoning_confidence, budget, country, platform.
            existing_dna_list: Existing creatives for novelty.

        Returns:
            Ranked list of PriorityScore.
        """
        scores = []
        for c in creatives:
            score = self.compute(
                creative_id=c["creative_id"],
                dna=c.get("dna", {}),
                roi_prediction=c.get("roi_prediction", 0.5),
                trend_status=c.get("trend_status", "stable"),
                reasoning_confidence=c.get("reasoning_confidence", 0.5),
                budget=c.get("budget", 100.0),
                country=c.get("country", ""),
                platform=c.get("platform", "facebook"),
                existing_dna_list=existing_dna_list,
            )
            scores.append(score)
        return self.rank(scores)