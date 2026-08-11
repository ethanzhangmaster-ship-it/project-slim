"""E10.2 Phase 5 — Policy Engine.

Core rule engine that evaluates LearningSignal feedback and
generates OptimizationDecision. Translates ROAS/CPI/CTR
metrics into actionable growth decisions.

Rules:
    ROAS > 1.5  → SCALE  (increase budget)
    ROAS 0.8-1.5 → WATCH (observe)
    ROAS < 0.8   → KILL  (pause)
    RETEST       → create new test campaign
"""

from __future__ import annotations

from market_ops.execution_runtime.schemas import ActionType, LearningSignal
from market_ops.execution_runtime.optimization_schema import OptimizationDecision


class OptimizationPolicy:
    """Rule-based optimization policy engine.

    Evaluates learning signals and generates optimization
    decisions based on ROAS thresholds.

    Args:
        scale_threshold: ROAS above which to SCALE. Default: 1.5.
        kill_threshold: ROAS below which to KILL. Default: 0.8.
    """

    SCALE_THRESHOLD: float = 1.5
    KILL_THRESHOLD: float = 0.8

    def __init__(
        self,
        scale_threshold: float = 1.5,
        kill_threshold: float = 0.8,
    ) -> None:
        self._scale_threshold = scale_threshold
        self._kill_threshold = kill_threshold

    def evaluate(self, signal: LearningSignal, campaign_id: str = "") -> OptimizationDecision:
        """Evaluate a LearningSignal and produce an OptimizationDecision.

        Args:
            signal: LearningSignal from the feedback loop.
            campaign_id: Platform campaign ID.

        Returns:
            OptimizationDecision with action and confidence.
        """
        roas = signal.metrics.get("roas", 0.0)
        spend = signal.metrics.get("spend", 0.0)
        revenue = signal.metrics.get("revenue", 0.0)

        if roas > self._scale_threshold:
            return OptimizationDecision(
                campaign_id=campaign_id or signal.task_id,
                action=ActionType.SCALE.value,
                confidence=signal.confidence,
                reason=f"ROAS {roas:.2f} > {self._scale_threshold} — scale up",
                expected_impact=round((roas - self._scale_threshold) * spend * 0.3, 2),
                metrics=signal.metrics,
            )
        elif roas >= self._kill_threshold:
            return OptimizationDecision(
                campaign_id=campaign_id or signal.task_id,
                action=ActionType.WATCH.value,
                confidence=0.5,
                reason=f"ROAS {roas:.2f} in [{self._kill_threshold}, {self._scale_threshold}] — observe",
                expected_impact=0.0,
                metrics=signal.metrics,
            )
        else:
            return OptimizationDecision(
                campaign_id=campaign_id or signal.task_id,
                action=ActionType.KILL.value,
                confidence=signal.confidence,
                reason=f"ROAS {roas:.2f} < {self._kill_threshold} — kill",
                expected_impact=round(spend - revenue, 2),
                metrics=signal.metrics,
            )

    def evaluate_batch(
        self,
        signals: list[LearningSignal],
        campaign_ids: list[str] | None = None,
    ) -> list[OptimizationDecision]:
        """Evaluate multiple signals at once.

        Args:
            signals: List of LearningSignals.
            campaign_ids: Optional list of campaign IDs (must match signals length).

        Returns:
            List of OptimizationDecisions.
        """
        if campaign_ids is None:
            campaign_ids = [""] * len(signals)

        return [
            self.evaluate(signal, cid)
            for signal, cid in zip(signals, campaign_ids)
        ]