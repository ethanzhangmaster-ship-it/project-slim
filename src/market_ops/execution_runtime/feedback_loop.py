"""E10.1 Feedback Loop — Execution → Learning signal conversion.

Transforms PerformanceSnapshot into standardized LearningSignal
for consumption by E9.9.5 Learning Layer.

No real platform API calls. No modification to Decision Layer.
"""

from __future__ import annotations

from market_ops.execution_runtime.schemas import (
    PerformanceSnapshot,
    LearningSignal,
    FeedbackType,
)


class FeedbackLoop:
    """Generates learning signals from performance snapshots.

    Usage:
        loop = FeedbackLoop()
        signal = loop.generate(snapshot)
        history = loop.get_history(task_id)
    """

    def __init__(self) -> None:
        self._signals: dict[str, LearningSignal] = {}

    def generate(self, snapshot: PerformanceSnapshot) -> LearningSignal:
        """Analyze a PerformanceSnapshot and produce a LearningSignal.

        Args:
            snapshot: Post-execution performance metrics.

        Returns:
            LearningSignal with feedback classification and recommendation.
        """
        feedback_type, recommendation, confidence = self._analyze(snapshot)

        signal = LearningSignal(
            task_id=snapshot.task_id,
            action_type=snapshot.status,
            feedback_type=feedback_type,
            confidence=confidence,
            metrics={
                "impressions": snapshot.impressions,
                "clicks": snapshot.clicks,
                "conversions": snapshot.conversions,
                "spend": snapshot.spend,
                "revenue": snapshot.revenue,
                "roas": snapshot.roas,
                "ctr": snapshot.ctr,
                "cvr": snapshot.cvr,
                "status": snapshot.status,
            },
            recommendation=recommendation,
        )
        self._signals[signal.signal_id] = signal
        return signal

    def get_history(self, task_id: str) -> list[LearningSignal]:
        """Get all learning signals for a given task.

        Args:
            task_id: The task ID to query.

        Returns:
            List of LearningSignal, newest first.
        """
        matches = [s for s in self._signals.values() if s.task_id == task_id]
        return sorted(matches, key=lambda s: s.created_at, reverse=True)

    @property
    def signals(self) -> list[LearningSignal]:
        """All generated learning signals."""
        return list(self._signals.values())

    # ───────────────────────────────────────────────────────
    # Internal: Outcome analysis
    # ───────────────────────────────────────────────────────

    @staticmethod
    def _analyze(
        snapshot: PerformanceSnapshot,
    ) -> tuple[str, str, float]:
        """Determine feedback type, recommendation, and confidence.

        Rules:
          SUCCESS : ROAS >= 1.5 and status == "active"
          NEUTRAL : 1.0 <= ROAS < 1.5
          WARNING : 0.7 <= ROAS < 1.0
          FAILURE : status == "failed" or ROAS < 0.7

        Returns:
            (feedback_type, recommendation, confidence)
        """
        roas = snapshot.roas
        status = snapshot.status

        if status == "failed":
            return FeedbackType.FAILURE.value, "STOP_LEARNING", 0.0

        if roas >= 1.5:
            confidence = min(0.99, 0.8 + (roas - 1.5) * 0.2)
            return FeedbackType.SUCCESS.value, "SCALE_VALIDATED", round(confidence, 2)

        if roas >= 1.0:
            confidence = min(0.79, 0.5 + (roas - 1.0) * 0.6)
            return FeedbackType.NEUTRAL.value, "KEEP_MONITORING", round(confidence, 2)

        if roas >= 0.7:
            confidence = min(0.49, 0.3 + (roas - 0.7) * 0.6)
            return FeedbackType.WARNING.value, "OPTIMIZATION_REQUIRED", round(confidence, 2)

        return FeedbackType.FAILURE.value, "STOP_LEARNING", 0.0
