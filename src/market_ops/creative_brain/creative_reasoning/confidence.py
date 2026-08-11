"""V4.2 Confidence Engine — weighted confidence scoring.

Computes confidence scores for every reasoning output using:
  - Retriever Score (similarity quality)
  - Pattern Score (pattern match strength)
  - Graph Score (knowledge graph coverage)
  - Learning Score (historical learning weight)
  - Trend Score (trend alignment)

Output: ConfidenceScore with overall weighted confidence.

Acceptance: Confidence Calibration error ≤ 10%.
"""

from __future__ import annotations

from typing import Any

from .schemas import ConfidenceScore, EvidenceItem, EvidenceSource


class ConfidenceEngine:
    """Computes weighted confidence scores for reasoning decisions.

    Each source contributes a score [0, 1], then weighted by importance.
    Default weights: pattern=0.30, retriever=0.25, graph=0.15, learning=0.15, trend=0.15
    """

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = weights or {
            "retriever": 0.25,
            "pattern": 0.30,
            "graph": 0.15,
            "learning": 0.15,
            "trend": 0.15,
        }

    def compute(self, retriever_score: float = 0.0,
                pattern_score: float = 0.0,
                graph_score: float = 0.0,
                learning_score: float = 0.0,
                trend_score: float = 0.0) -> ConfidenceScore:
        """Compute weighted confidence from all sources."""
        score = ConfidenceScore(
            retriever_score=retriever_score,
            pattern_score=pattern_score,
            graph_score=graph_score,
            learning_score=learning_score,
            trend_score=trend_score,
            weights=self._weights,
        )
        score.compute_overall()
        return score

    def compute_from_evidence(self, evidence: list[EvidenceItem]) -> ConfidenceScore:
        """Compute confidence from evidence items."""
        source_scores: dict[str, list[float]] = {
            "retriever": [],
            "pattern": [],
            "graph": [],
            "learning": [],
            "trend": [],
        }

        for e in evidence:
            src = e.source.value
            if src in source_scores:
                source_scores[src].append(e.strength)

        def avg(vals: list[float]) -> float:
            if not vals:
                return 0.0
            return sum(vals) / len(vals)

        return self.compute(
            retriever_score=avg(source_scores["retriever"]),
            pattern_score=avg(source_scores["pattern"]),
            graph_score=avg(source_scores["graph"]),
            learning_score=avg(source_scores["learning"]),
            trend_score=avg(source_scores["trend"]),
        )

    def calibrate(self, predicted_confidence: float,
                  actual_outcome: float) -> float:
        """Compute calibration error between predicted confidence and actual outcome.

        Target: calibration error ≤ 10%.
        """
        return abs(predicted_confidence - actual_outcome)

    def interpret(self, score: ConfidenceScore) -> str:
        """Human-readable interpretation of confidence score."""
        overall = score.overall
        if overall >= 0.8:
            level = "HIGH"
        elif overall >= 0.5:
            level = "MEDIUM"
        elif overall >= 0.3:
            level = "LOW"
        else:
            level = "VERY LOW"

        breakdown = []
        if score.pattern_score > 0:
            breakdown.append(f"Pattern: {score.pattern_score:.0%}")
        if score.retriever_score > 0:
            breakdown.append(f"Retriever: {score.retriever_score:.0%}")
        if score.graph_score > 0:
            breakdown.append(f"Graph: {score.graph_score:.0%}")

        return (
            f"Confidence: {overall:.0%} ({level}). "
            f"Sources: {', '.join(breakdown) if breakdown else 'none'}."
        )

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    def update_weights(self, new_weights: dict[str, float]) -> None:
        """Update source weights (e.g., from learning loop feedback)."""
        total = sum(new_weights.values())
        if total > 0:
            self._weights = {k: v / total for k, v in new_weights.items()}