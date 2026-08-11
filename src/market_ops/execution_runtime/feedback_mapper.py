"""E10.2 Phase 4 — Feedback Mapper.

Maps PerformanceSnapshot data into LearningSignal for the
E9.9.5 Decision Layer. Translates ROAS/CPI/CTR metrics
into actionable feedback: SCALE, WATCH, or KILL.

Signal rules:
    D7 ROAS > 1.5   → SCALE  (SUCCESS)
    D7 ROAS 0.8-1.5 → WATCH  (NEUTRAL)
    D7 ROAS < 0.8   → KILL   (FAILURE)

This completes the Execution → Attribution → Feedback loop.
"""

from __future__ import annotations

from market_ops.execution_runtime.schemas import (
    PerformanceSnapshot,
    LearningSignal,
    FeedbackType,
    ActionType,
)


class FeedbackMapper:
    """Maps PerformanceSnapshot to LearningSignal.

    Uses ROAS-based rules to generate actionable feedback
    for the E9.9.5 Decision Layer.

    Rules:
        D7 ROAS > 1.5   → SCALE  (strong performer)
        D7 ROAS 0.8-1.5 → WATCH  (needs more data)
        D7 ROAS < 0.8   → KILL   (underperformer)

    Usage:
        mapper = FeedbackMapper()
        snapshot = PerformanceSnapshot(roas=2.0, spend=500, revenue=1000)
        signal = mapper.map(snapshot, task_id="t_001")
        print(signal.recommendation)  # "SCALE: ROAS 2.0"
    """

    # ── ROAS thresholds ────────────────────────────────────
    SCALE_THRESHOLD: float = 1.5
    KILL_THRESHOLD: float = 0.8

    def map(self, snapshot: PerformanceSnapshot, task_id: str = "") -> LearningSignal:
        """Map a PerformanceSnapshot to a LearningSignal.

        Args:
            snapshot: PerformanceSnapshot from PerformanceCollector.
            task_id: ExecutionTask ID for correlation.

        Returns:
            LearningSignal with recommendation and confidence.
        """
        roas = snapshot.roas
        spend = snapshot.spend
        revenue = snapshot.revenue

        if roas > self.SCALE_THRESHOLD:
            return self._build_signal(
                snapshot=snapshot,
                task_id=task_id,
                action=ActionType.SCALE.value,
                feedback=FeedbackType.SUCCESS.value,
                recommendation=f"SCALE: ROAS {roas:.2f} (spend ${spend:.0f} → revenue ${revenue:.0f})",
                confidence=min(0.95, 0.5 + min(roas / 5.0, 0.5)),
            )
        elif roas >= self.KILL_THRESHOLD:
            return self._build_signal(
                snapshot=snapshot,
                task_id=task_id,
                action=ActionType.WATCH.value,
                feedback=FeedbackType.NEUTRAL.value,
                recommendation=f"WATCH: ROAS {roas:.2f} (marginal, need more data)",
                confidence=0.5,
            )
        else:
            return self._build_signal(
                snapshot=snapshot,
                task_id=task_id,
                action=ActionType.KILL.value,
                feedback=FeedbackType.FAILURE.value,
                recommendation=f"KILL: ROAS {roas:.2f} (spend ${spend:.0f} > revenue ${revenue:.0f})",
                confidence=min(0.95, 0.5 + (1.0 - roas) / 2.0),
            )

    def _build_signal(
        self,
        snapshot: PerformanceSnapshot,
        task_id: str,
        action: str,
        feedback: str,
        recommendation: str,
        confidence: float,
    ) -> LearningSignal:
        """Build a LearningSignal from snapshot data."""
        return LearningSignal(
            task_id=task_id or snapshot.task_id,
            action_type=action,
            feedback_type=feedback,
            confidence=round(confidence, 2),
            metrics={
                "roas": round(snapshot.roas, 2),
                "spend": round(snapshot.spend, 2),
                "revenue": round(snapshot.revenue, 2),
                "impressions": snapshot.impressions,
                "clicks": snapshot.clicks,
                "conversions": snapshot.conversions,
                "ctr": round(snapshot.ctr, 4),
                "cvr": round(snapshot.cvr, 4),
            },
            recommendation=recommendation,
        )