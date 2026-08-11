"""E6.1: Trend Memory — tracks trend lifecycles from emergence to decline.

Remembers:
  - Trend duration (how long do trends last?)
  - Trend intervals (how often do new trends emerge?)
  - Which signals reliably predict breakthrough trends
  - Trend correlation patterns (does trend A predict trend B?)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from market_ops.market_intelligence.trend_detector import TrendSignal


class TrendMemory:
    """Tracks the lifecycle of market trends.

    Learn: "Rescue hook trend has 3-6 month window, peaks at month 2,
            best time to enter is weeks 1-3 after initial signal."
    """

    def __init__(self) -> None:
        self._trends: list[TrendSignal] = []   # historical trends
        self._lifecycles: dict[str, list[dict[str, Any]]] = {}  # trend → timeline
        # Learned patterns
        self._avg_lifespan_days: float = 90  # default: trends last ~90 days
        self._avg_peak_days: float = 45       # default: peak at day 45
        self._signal_sequence: dict[str, list[str]] = {}  # signal A → signal B → signal C

    def record_trend(self, trend: TrendSignal) -> None:
        """Record a trend observation."""
        self._trends.append(trend)

        key = f"{trend.category}:{trend.subcategory}"
        self._lifecycles.setdefault(key, []).append({
            "timestamp": trend.detected_at,
            "direction": trend.direction.value,
            "growth": trend.growth_pct,
            "velocity": trend.velocity_score,
            "confidence": trend.confidence.value,
        })

        # Update signal sequence learning
        self._learn_signal_sequence(trend)

    def record_batch(self, trends: list[TrendSignal]) -> None:
        for t in trends:
            self.record_trend(t)

    def get_trend_lifecycle(self, category: str, subcategory: str) -> dict[str, Any]:
        """Get the lifecycle of a specific trend."""
        key = f"{category}:{subcategory}"
        timeline = self._lifecycles.get(key, [])

        if not timeline:
            return {
                "trend": f"{category}/{subcategory}",
                "status": "no_data",
                "stages": [],
            }

        # Classify stages
        stages = []
        for entry in timeline:
            if entry["growth"] >= 200:
                stages.append("exploding")
            elif entry["growth"] >= 50:
                stages.append("rising")
            elif entry["growth"] < -20:
                stages.append("declining")
            else:
                stages.append("stable")

        return {
            "trend": f"{category}/{subcategory}",
            "observations": len(timeline),
            "current_stage": stages[-1] if stages else "unknown",
            "stage_progression": " → ".join(stages[-5:]) if len(stages) >= 5 else " → ".join(stages),
            "avg_growth": round(sum(e["growth"] for e in timeline) / len(timeline), 1),
        }

    def predict_next_trends(self) -> list[dict[str, Any]]:
        """Predict what trends are likely to emerge next based on signal sequences.

        If signal A reliably precedes trend B, this flags B as likely.
        """
        predictions = []

        # Most recent signals
        recent_trends = self._trends[-10:]
        recent_signals = set(t.subcategory for t in recent_trends)

        for signal, sequence in self._signal_sequence.items():
            follow_ons = [s for s in sequence if s not in recent_signals]
            if follow_ons:
                predictions.append({
                    "from_signal": signal,
                    "predicted_next": follow_ons,
                    "confidence": 0.4 + len(sequence) * 0.05,  # more precedents = more confidence
                })

        return sorted(predictions, key=lambda p: p["confidence"], reverse=True)

    def get_statistics(self) -> dict[str, Any]:
        """Memory statistics."""
        return {
            "total_trends_tracked": len(self._trends),
            "unique_categories": len(set(t.category for t in self._trends)),
            "trends_per_week": round(len(self._trends) / max(1, 8), 1),
            "avg_lifespan_days": round(self._avg_lifespan_days, 0),
            "avg_peak_days": round(self._avg_peak_days, 0),
            "signal_sequences_learned": len(self._signal_sequence),
        }

    def _learn_signal_sequence(self, trend: TrendSignal) -> None:
        """Learn: does this signal predict another?"""
        # Group by category and track temporal ordering
        cat_trends = [t for t in self._trends if t.category == trend.category]
        if len(cat_trends) < 2:
            return

        for other in cat_trends[-5:-1]:
            if other.subcategory != trend.subcategory:
                self._signal_sequence.setdefault(
                    other.subcategory, []
                ).append(trend.subcategory)
