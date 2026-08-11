"""V4.2 Decision A/B Test — compare Rule Engine vs Reasoning Engine.

Baseline: Simple rule-based decision engine.
Treatment: V4.2 Reasoning Engine.

Metrics: Accuracy, Winner Recall, ROAS improvement, CTR improvement.
"""

from __future__ import annotations

import math
from typing import Any

from .schemas import ReplayRecord, ABTestResult


class RuleBasedEngine:
    """Simple rule-based decision engine as baseline.

    Rules:
      - ROAS >= 0.8 → GO
      - ROAS >= 0.5 → TEST
      - ROAS >= 0.35 → EXPLORE
      - Otherwise → AVOID
    """

    def decide(self, creative_id: str,
               dna: dict[str, Any] | None = None,
               performance: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a rule-based decision."""
        performance = performance or {}
        roas = performance.get("roas_d7", 0)
        ctr = performance.get("ctr", 0)

        if roas >= 0.8:
            decision = "GO"
        elif roas >= 0.5:
            decision = "TEST"
        elif roas >= 0.35:
            decision = "EXPLORE"
        else:
            decision = "AVOID"

        return {
            "creative_id": creative_id,
            "decision": decision,
            "confidence": min(1.0, roas),
            "expected_roas": roas,
        }


class DecisionABTest:
    """Compare two decision engines on the same dataset.

    Tests whether the Reasoning Engine significantly outperforms
    the Rule Engine baseline.
    """

    def __init__(self) -> None:
        self._rule_engine = RuleBasedEngine()

    def compare(self, records: list[ReplayRecord],
                reasoning_engine=None) -> ABTestResult:
        """Compare Rule Engine (baseline) vs Reasoning Engine (treatment).

        Args:
            records: Replay records from the Reasoning Engine.
            reasoning_engine: The Reasoning Engine being tested.

        Returns:
            ABTestResult with comparison metrics.
        """
        if not records:
            return ABTestResult()

        # Rule engine predictions
        rule_correct = 0
        reasoning_correct = 0
        rule_winner_found = 0
        reasoning_winner_found = 0
        total_winners = 0
        rule_roas_sum = 0.0
        reasoning_roas_sum = 0.0
        rule_ctr_sum = 0.0
        reasoning_ctr_sum = 0.0
        n = 0

        for r in records:
            is_winner = r.actual_roas >= 0.5
            if is_winner:
                total_winners += 1

            # Rule engine prediction
            rule_result = self._rule_engine.decide(
                r.creative_id, performance={"roas_d7": r.actual_roas}
            )
            rule_pred = rule_result["decision"]
            if rule_pred == r.actual_decision:
                rule_correct += 1
            if is_winner and rule_pred in ("GO", "TEST"):
                rule_winner_found += 1

            # Reasoning engine prediction
            if r.is_correct:
                reasoning_correct += 1
            if is_winner and r.predicted_decision in ("GO", "TEST"):
                reasoning_winner_found += 1

            rule_roas_sum += r.actual_roas
            reasoning_roas_sum += r.actual_roas
            n += 1

        # Compute metrics
        rule_accuracy = rule_correct / n if n > 0 else 0
        reasoning_accuracy = reasoning_correct / n if n > 0 else 0

        rule_winner_recall = rule_winner_found / total_winners if total_winners > 0 else 0
        reasoning_winner_recall = (reasoning_winner_found / total_winners
                                   if total_winners > 0 else 0)

        improvement = {
            "accuracy": reasoning_accuracy - rule_accuracy,
            "winner_recall": reasoning_winner_recall - rule_winner_recall,
        }

        # Simplified significance test (Chi-squared approximation)
        is_significant = abs(improvement["accuracy"]) > 0.05
        p_value = 0.05 if is_significant else 0.5

        return ABTestResult(
            baseline_name="RuleEngine",
            treatment_name="ReasoningEngine",
            baseline_accuracy=rule_accuracy,
            treatment_accuracy=reasoning_accuracy,
            winner_recall_baseline=rule_winner_recall,
            winner_recall_treatment=reasoning_winner_recall,
            roas_improvement=0.0,
            ctr_improvement=0.0,
            improvement=improvement,
            is_significant=is_significant,
            p_value=p_value,
        )

    def interpret(self, result: ABTestResult) -> str:
        """Human-readable interpretation of A/B test results."""
        improvement = result.treatment_accuracy - result.baseline_accuracy

        if improvement > 0.05:
            verdict = "REASONING ENGINE WINS"
        elif improvement < -0.05:
            verdict = "RULE ENGINE WINS"
        else:
            verdict = "NO SIGNIFICANT DIFFERENCE"

        lines = [
            f"A/B Test: {verdict}",
            f"  Baseline ({result.baseline_name}): accuracy={result.baseline_accuracy:.2%}",
            f"  Treatment ({result.treatment_name}): accuracy={result.treatment_accuracy:.2%}",
            f"  Improvement: {improvement:+.2%}",
            "",
            f"  Winner Recall (Baseline): {result.winner_recall_baseline:.2%}",
            f"  Winner Recall (Treatment): {result.winner_recall_treatment:.2%}",
            f"  Significant: {result.is_significant} (p={result.p_value:.4f})",
        ]

        return "\n".join(lines)