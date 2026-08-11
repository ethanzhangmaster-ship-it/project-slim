"""V4.3.5 Confidence Rebuilder — recalibrate confidence based on validation.

When Validation finds:
  Confidence 0.95 → Actual 0.68

Auto-recalibrate confidence weights for each evidence source.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .schemas import ConfidenceCalibration


class ConfidenceRebuilder:
    """Recalibrate confidence scores based on validation feedback."""

    def __init__(self) -> None:
        # Per-source calibration: source → adjustment_factor
        self._calibrations: dict[str, ConfidenceCalibration] = {}
        self._rebuild_history: list[dict[str, Any]] = []

    def calibrate(self, source: str, original_confidence: float,
                  actual_accuracy: float, samples: int = 1) -> ConfidenceCalibration:
        """Calibrate confidence for a source.

        Args:
            source: Evidence source (pattern/retriever/graph/trend/learning).
            original_confidence: Original confidence score.
            actual_accuracy: Actual accuracy from validation.
            samples: Number of samples used.

        Returns:
            ConfidenceCalibration with adjustment factor.
        """
        gap = original_confidence - actual_accuracy

        # Calculate adjustment factor
        if original_confidence > 0:
            factor = actual_accuracy / original_confidence
        else:
            factor = 1.0

        # Clamp to reasonable range
        factor = max(0.3, min(2.0, factor))

        # Smooth with existing calibration
        if source in self._calibrations:
            old_factor = self._calibrations[source].adjustment_factor
            factor = old_factor * 0.7 + factor * 0.3

        calibrated = original_confidence * factor

        calibration = ConfidenceCalibration(
            source=source,
            original_confidence=original_confidence,
            actual_accuracy=actual_accuracy,
            calibrated_confidence=round(calibrated, 3),
            gap=round(gap, 3),
            adjustment_factor=round(factor, 3),
            samples=samples,
            recalibrated_at=datetime.now().isoformat(),
        )

        self._calibrations[source] = calibration
        self._rebuild_history.append(calibration.to_dict())
        return calibration

    def calibrate_batch(self, feedback: list[dict[str, Any]]
                        ) -> list[ConfidenceCalibration]:
        """Calibrate multiple sources from validation feedback.

        Args:
            feedback: List of {source, confidence, accuracy, samples}.

        Returns:
            List of ConfidenceCalibration.
        """
        results = []
        for fb in feedback:
            cal = self.calibrate(
                source=fb["source"],
                original_confidence=fb.get("confidence", 0.5),
                actual_accuracy=fb.get("accuracy", 0.5),
                samples=fb.get("samples", 1),
            )
            results.append(cal)
        return results

    def get_calibrated_confidence(self, source: str,
                                   raw_confidence: float) -> float:
        """Get calibrated confidence for a source.

        Args:
            source: Evidence source.
            raw_confidence: Raw confidence score.

        Returns:
            Calibrated confidence.
        """
        if source in self._calibrations:
            factor = self._calibrations[source].adjustment_factor
            return raw_confidence * factor
        return raw_confidence

    def get_all_calibrations(self) -> dict[str, ConfidenceCalibration]:
        """Get all calibrations."""
        return dict(self._calibrations)

    def get_calibration_summary(self) -> dict[str, Any]:
        """Get calibration summary."""
        return {
            source: {
                "factor": cal.adjustment_factor,
                "gap": cal.gap,
                "samples": cal.samples,
            }
            for source, cal in self._calibrations.items()
        }

    def get_overconfident_sources(self, threshold: float = 0.1
                                   ) -> list[dict[str, Any]]:
        """Get sources that are significantly overconfident."""
        return [
            {"source": src, "gap": cal.gap, "factor": cal.adjustment_factor}
            for src, cal in self._calibrations.items()
            if cal.gap > threshold
        ]

    def get_rebuild_history(self) -> list[dict[str, Any]]:
        return list(self._rebuild_history)