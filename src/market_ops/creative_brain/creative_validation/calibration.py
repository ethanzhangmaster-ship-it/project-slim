"""V4.2 Calibration — verify if confidence scores are trustworthy.

Measures:
  - ECE (Expected Calibration Error): target ≤ 0.10
  - MCE (Maximum Calibration Error)
  - Brier Score
  - Reliability Diagram

Answers: "When the engine says 92% confident, is it really 92% correct?"
"""

from __future__ import annotations

import math
from typing import Any

from .schemas import ReplayRecord, CalibrationResult


class CalibrationEvaluator:
    """Evaluate how well confidence scores align with actual accuracy.

    A well-calibrated model: confidence=0.8 → 80% of those predictions are correct.
    """

    def evaluate(self, records: list[ReplayRecord],
                 num_bins: int = 10) -> CalibrationResult:
        """Compute calibration metrics.

        Args:
            records: Replay records with confidence and correctness.
            num_bins: Number of bins for reliability diagram.

        Returns:
            CalibrationResult with ECE, MCE, Brier Score.
        """
        if not records:
            return CalibrationResult(num_bins=num_bins)

        # Sort by confidence
        sorted_records = sorted(records, key=lambda r: r.confidence)

        # Bin records by confidence
        bin_size = max(1, len(sorted_records) // num_bins)
        bins = []
        for i in range(num_bins):
            start = i * bin_size
            end = start + bin_size if i < num_bins - 1 else len(sorted_records)
            if start >= len(sorted_records):
                break
            bin_records = sorted_records[start:end]
            if bin_records:
                avg_confidence = sum(r.confidence for r in bin_records) / len(bin_records)
                accuracy = sum(1 for r in bin_records if r.is_correct) / len(bin_records)
                bins.append({
                    "avg_confidence": round(avg_confidence, 4),
                    "accuracy": round(accuracy, 4),
                    "count": len(bin_records),
                    "gap": round(abs(avg_confidence - accuracy), 4),
                })

        # ECE: weighted average of |confidence - accuracy|
        total = len(records)
        ece = 0.0
        for b in bins:
            ece += (b["count"] / total) * b["gap"]

        # MCE: max gap
        mce = max(b["gap"] for b in bins) if bins else 0.0

        # Brier Score: mean squared error
        brier = sum(
            (r.confidence - (1.0 if r.is_correct else 0.0)) ** 2
            for r in records
        ) / total if total > 0 else 0.0

        return CalibrationResult(
            ece=ece,
            mce=mce,
            brier_score=brier,
            reliability_curve=bins,
            num_bins=num_bins,
            is_calibrated=ece < 0.1,
        )

    def interpret(self, result: CalibrationResult) -> str:
        """Human-readable interpretation of calibration."""
        if result.is_calibrated:
            level = "WELL CALIBRATED"
        elif result.ece < 0.15:
            level = "ACCEPTABLE"
        elif result.ece < 0.25:
            level = "NEEDS IMPROVEMENT"
        else:
            level = "POORLY CALIBRATED"

        lines = [
            f"Calibration: {level}",
            f"  ECE: {result.ece:.4f} (target: < 0.10)",
            f"  MCE: {result.mce:.4f}",
            f"  Brier Score: {result.brier_score:.4f}",
            f"  Reliability Curve: {len(result.reliability_curve)} bins",
        ]

        if result.reliability_curve:
            lines.append("")
            lines.append("  Reliability per bin:")
            for i, b in enumerate(result.reliability_curve):
                lines.append(
                    f"    Bin {i+1}: conf={b['avg_confidence']:.2f} "
                    f"→ acc={b['accuracy']:.2f} "
                    f"(gap={b['gap']:.3f}, n={b['count']})"
                )

        if not result.is_calibrated:
            lines.append("")
            if result.ece > 0.1:
                lines.append("  Recommendation: Confidence scores are over/under-confident.")
                lines.append("  Consider adjusting confidence weights or adding calibration layer.")

        return "\n".join(lines)