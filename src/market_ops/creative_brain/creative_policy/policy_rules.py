"""V4.3 Policy Rules — multi-dimensional decision rules.

Not hardcoded rules. Each rule considers:
  - Reasoning Confidence
  - Validation Accuracy
  - Trend (growing/stable/declining/dead)
  - ROI prediction
  - Budget constraint

All thresholds come from DecisionPolicy, enabling auto-optimization.
"""

from __future__ import annotations

from typing import Any

from .schemas import DecisionPolicy, PolicyAction


class PolicyRules:
    """Multi-dimensional decision rules engine.

    Evaluates each creative against policy thresholds and returns
    a PolicyAction with supporting evidence.
    """

    def evaluate(self, creative_data: dict[str, Any],
                 policy: DecisionPolicy) -> tuple[PolicyAction, dict[str, Any]]:
        """Evaluate a single creative against policy rules.

        Args:
            creative_data: Creative with reasoning/validation results.
                Expected keys: reasoning_confidence, validation_accuracy,
                trend_status, roi_prediction, budget, country, platform.
            policy: Current DecisionPolicy with thresholds.

        Returns:
            (PolicyAction, evidence_dict)
        """
        confidence = creative_data.get("reasoning_confidence", 0.5)
        validation_accuracy = creative_data.get("validation_accuracy", 0.5)
        trend = creative_data.get("trend_status", "stable")
        roi = creative_data.get("roi_prediction", 0.5)
        budget = creative_data.get("budget", 100.0)

        evidence = {
            "reasoning_confidence": confidence,
            "validation_accuracy": validation_accuracy,
            "trend_status": trend,
            "roi_prediction": roi,
            "budget": budget,
        }

        # Apply trend adjustments
        adjusted_confidence = self._apply_trend_adjustment(
            confidence, trend, policy
        )
        evidence["adjusted_confidence"] = adjusted_confidence

        # Composite score
        composite = (
            adjusted_confidence * 0.35 +
            validation_accuracy * 0.20 +
            roi * 0.30 +
            (1.0 if budget <= policy.max_budget_per_creative else 0.0) * 0.15
        )
        evidence["composite_score"] = round(composite, 3)

        # Decision logic
        if confidence > 0.8 and validation_accuracy > 0.5 and roi > 0.6:
            # High confidence specific check
            action = self._decide_high_confidence(composite, policy)
        else:
            action = self._decide_standard(composite, adjusted_confidence,
                                           roi, trend, policy)

        evidence["reason"] = self._build_reason(action, evidence)
        return action, evidence

    def _apply_trend_adjustment(self, confidence: float,
                                 trend: str, policy: DecisionPolicy) -> float:
        """Apply trend bonus/penalty to confidence."""
        if trend == "growing":
            return min(1.0, confidence + policy.trend_growing_bonus)
        elif trend == "dead":
            return max(0.0, confidence - policy.trend_dead_penalty)
        return confidence

    def _decide_high_confidence(self, composite: float,
                                 policy: DecisionPolicy) -> PolicyAction:
        """Decision for high-confidence creatives."""
        if composite >= 0.65:
            return PolicyAction.GENERATE
        elif composite >= 0.50:
            return PolicyAction.ADAPT
        else:
            return PolicyAction.RETEST

    def _decide_standard(self, composite: float, confidence: float,
                          roi: float, trend: str,
                          policy: DecisionPolicy) -> PolicyAction:
        """Standard decision logic."""
        # Kill: too low confidence or ROI
        if roi < policy.roi_threshold_kill or trend == "dead":
            return PolicyAction.KILL

        # Generate: high composite + good ROI
        if composite >= 0.60 and roi >= policy.roi_threshold_go:
            return PolicyAction.GENERATE

        # Adapt: moderate confidence, not dead
        if composite >= 0.45 and trend != "dead":
            return PolicyAction.ADAPT

        # Retest: borderline
        if composite >= 0.30:
            return PolicyAction.RETEST

        # Low composite → kill
        return PolicyAction.KILL

    def _build_reason(self, action: PolicyAction,
                      evidence: dict[str, Any]) -> str:
        """Build human-readable reason for decision."""
        reasons = {
            PolicyAction.GENERATE: (
                f"High confidence ({evidence['reasoning_confidence']:.0%}), "
                f"ROI {evidence['roi_prediction']:.2f}, "
                f"trend {evidence['trend_status']}"
            ),
            PolicyAction.ADAPT: (
                f"Moderate confidence ({evidence['reasoning_confidence']:.0%}), "
                f"adapt for {evidence['trend_status']} market"
            ),
            PolicyAction.RETEST: (
                f"Borderline confidence ({evidence['reasoning_confidence']:.0%}), "
                f"retest with modified parameters"
            ),
            PolicyAction.KILL: (
                f"Low ROI ({evidence['roi_prediction']:.2f}) or "
                f"dead trend ({evidence['trend_status']})"
            ),
            PolicyAction.DONT_GENERATE: (
                f"Budget constraint or risk override"
            ),
        }
        return reasons.get(action, "Unknown reason")

    def evaluate_batch(self, creatives: list[dict[str, Any]],
                       policy: DecisionPolicy) -> list[tuple[PolicyAction, dict[str, Any]]]:
        """Evaluate a batch of creatives."""
        return [self.evaluate(c, policy) for c in creatives]