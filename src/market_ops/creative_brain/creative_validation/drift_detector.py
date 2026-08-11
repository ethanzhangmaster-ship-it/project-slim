"""V4.2 Drift Detector — detect distribution shifts in creative patterns.

Detects:
  - Creative Drift: DNA performance changes
  - Trend Drift: Trend direction changes
  - Country Drift: Country-specific performance shifts
  - Genre Drift: Game genre performance changes

Outputs: DriftResult with direction, confidence, expiration status.
"""

from __future__ import annotations

import math
from typing import Any

from .schemas import DriftResult, DriftType


class DriftDetector:
    """Detect when creative patterns are shifting.

    Monitors DNA dimensions for performance changes and flags
    patterns that are growing, declining, or expired.
    """

    DRIFT_THRESHOLD_PCT = 20.0  # 20% change = significant drift

    def detect(self, current_data: list[dict[str, Any]],
               previous_data: list[dict[str, Any]] | None = None,
               drift_type: DriftType = DriftType.CREATIVE) -> list[DriftResult]:
        """Detect drift between current and previous data.

        Args:
            current_data: Current creative performance data.
            previous_data: Previous creative performance data.
            drift_type: Type of drift to detect.

        Returns:
            List of DriftResult for each detected drift.
        """
        if not previous_data:
            return []

        current_scores = self._compute_scores(current_data)
        previous_scores = self._compute_scores(previous_data)

        results = []
        for key, curr_score in current_scores.items():
            prev_score = previous_scores.get(key, curr_score)
            change_pct = self._compute_change(curr_score, prev_score)

            if abs(change_pct) >= self.DRIFT_THRESHOLD_PCT:
                direction = "growing" if change_pct > 0 else "declining"

                # Parse dimension and value from key
                parts = key.split("=", 1)
                dimension = parts[0] if len(parts) > 0 else key
                value = parts[1] if len(parts) > 1 else ""

                results.append(DriftResult(
                    drift_type=drift_type,
                    affected_dimension=dimension,
                    affected_value=value,
                    direction=direction,
                    current_score=curr_score,
                    previous_score=prev_score,
                    change_pct=change_pct,
                    is_expired=change_pct < -30,
                    confidence=min(1.0, abs(change_pct) / 50),
                ))

        results.sort(key=lambda r: abs(r.change_pct), reverse=True)
        return results

    def detect_creative_drift(self, current: list[dict[str, Any]],
                              previous: list[dict[str, Any]]) -> list[DriftResult]:
        """Detect creative DNA drift."""
        return self.detect(current, previous, DriftType.CREATIVE)

    def detect_trend_drift(self, current: list[dict[str, Any]],
                           previous: list[dict[str, Any]]) -> list[DriftResult]:
        """Detect trend direction drift."""
        return self.detect(current, previous, DriftType.TREND)

    def detect_country_drift(self, current: list[dict[str, Any]],
                             previous: list[dict[str, Any]]) -> list[DriftResult]:
        """Detect country-specific drift."""
        return self.detect(current, previous, DriftType.COUNTRY)

    def detect_genre_drift(self, current: list[dict[str, Any]],
                           previous: list[dict[str, Any]]) -> list[DriftResult]:
        """Detect game genre drift."""
        return self.detect(current, previous, DriftType.GENRE)

    def detect_platform_drift(self, current: list[dict[str, Any]],
                              previous: list[dict[str, Any]]) -> list[DriftResult]:
        """Detect platform-specific drift."""
        return self.detect(current, previous, DriftType.PLATFORM)

    def detect_network_drift(self, current: list[dict[str, Any]],
                             previous: list[dict[str, Any]]) -> list[DriftResult]:
        """Detect ad network drift."""
        return self.detect(current, previous, DriftType.NETWORK)

    def get_expired_patterns(self, results: list[DriftResult]) -> list[DriftResult]:
        """Get patterns that have expired (should be retired)."""
        return [r for r in results if r.is_expired]

    def get_growing_patterns(self, results: list[DriftResult]) -> list[DriftResult]:
        """Get patterns that are growing (should be invested in)."""
        return [r for r in results if r.direction == "growing"]

    def summarize(self, results: list[DriftResult]) -> str:
        """Generate a human-readable drift summary."""
        if not results:
            return "No significant drift detected."

        growing = self.get_growing_patterns(results)
        expired = self.get_expired_patterns(results)

        lines = []
        if growing:
            lines.append("Growing patterns (invest):")
            for r in growing[:5]:
                lines.append(
                    f"  {r.affected_dimension}={r.affected_value}: "
                    f"{r.change_pct:+.0f}% (conf: {r.confidence:.0%})"
                )
        if expired:
            lines.append("Expired patterns (retire):")
            for r in expired[:5]:
                lines.append(
                    f"  {r.affected_dimension}={r.affected_value}: "
                    f"{r.change_pct:+.0f}%"
                )

        if not growing and not expired:
            lines.append(f"Drift detected in {len(results)} dimensions.")
            for r in results[:5]:
                lines.append(
                    f"  {r.affected_dimension}={r.affected_value}: "
                    f"{r.change_pct:+.0f}% ({r.direction})"
                )

        return "\n".join(lines)

    # ── Private ──

    def _compute_scores(self, data: list[dict[str, Any]]) -> dict[str, float]:
        """Compute average ROAS per DNA dimension value."""
        scores: dict[str, tuple[float, int]] = {}

        for item in data:
            dna = item.get("dna", {})
            perf = item.get("performance", {})
            roas = perf.get("roas_d7", 0)

            for dim, val in dna.items():
                if not val:
                    continue
                key = f"{dim}={val}"
                if key not in scores:
                    scores[key] = (0.0, 0)
                total, count = scores[key]
                scores[key] = (total + roas, count + 1)

        return {
            key: total / count if count > 0 else 0.0
            for key, (total, count) in scores.items()
        }

    def _compute_change(self, current: float, previous: float) -> float:
        """Compute percentage change."""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return ((current - previous) / abs(previous)) * 100