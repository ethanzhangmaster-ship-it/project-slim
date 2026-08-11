"""E9.9 Module 7: Feedback Engine.

Generates learning signals from experiment results → E9.7 Learning Loop.
Does NOT modify E9.7 source code. Writes to JSON files that E9.7 reads.

Signals:
  - DNA weight updates: winner genes get +weight, loser genes get -weight
  - Mutation strategy updates: increase/decrease mutation probability
  - Prediction weight updates: adjust LTV/retention weights
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_ops.experiment_intelligence.schemas import (
    ExperimentResult, ExperimentCandidate, FeedbackSignal,
    ExperimentDecision,
)


# ── Weight adjustment parameters ───────────────────────────

WINNER_WEIGHT_DELTA = 0.06         # +0.06 for winner genes
FAILED_WEIGHT_DELTA = -0.03        # -0.03 for failed genes
PROMISING_WEIGHT_DELTA = 0.02      # +0.02 for promising (inconclusive but positive)
MAX_WEIGHT = 1.0                   # Weight ceiling
MIN_WEIGHT = 0.01                  # Weight floor


class FeedbackEngine:
    """Generates learning feedback from experiment results.

    Usage:
        feedback = FeedbackEngine()
        signals = feedback.generate_feedback(results, candidates)
        feedback.apply_feedback_to_e97(signals)
    """

    def __init__(
        self,
        e97_learning_dir: str | Path = "output/creative_learning",
    ) -> None:
        self._e97_dir = Path(e97_learning_dir)

    def generate_feedback(
        self,
        results: list[ExperimentResult],
        candidates: list[ExperimentCandidate],
    ) -> list[FeedbackSignal]:
        """Generate learning signals from experiment results.

        Args:
            results: Experiment results from ResultAnalyzer
            candidates: Original experiment candidates (for gene mapping)

        Returns:
            List of FeedbackSignal objects
        """
        signals = []

        # Build candidate lookup by genome_id
        candidate_map = {c.genome_id: c for c in candidates}

        for result in results:
            candidate = candidate_map.get(result.variant_genome_id)
            if not candidate:
                continue

            signal = FeedbackSignal(
                creative_id=result.control_creative_id,
                experiment_id=result.experiment_id,
                confidence=result.confidence,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

            # Generate DNA weight updates
            signal.dna_weight_update = self._update_dna_weights(
                result, candidate
            )

            # Generate mutation strategy updates
            signal.mutation_strategy_update = self._update_mutation_strategy(
                result, candidate
            )

            # Generate prediction weight updates
            signal.prediction_weight_update = self._update_prediction_weights(
                result
            )

            signals.append(signal)

        return signals

    # ── DNA Weight Updates ─────────────────────────────────

    def _update_dna_weights(
        self,
        result: ExperimentResult,
        candidate: ExperimentCandidate,
    ) -> dict[str, float]:
        """Calculate DNA weight updates based on experiment outcome.

        Winner:  increase weight of mutation dimension
        Failed:  decrease weight of mutation dimension

        Key format: "{dimension}.{value}"
        e.g., "hook.challenge", "visual.3d_cartoon"
        """
        updates: dict[str, float] = {}

        if result.decision == ExperimentDecision.WINNER.value:
            delta = WINNER_WEIGHT_DELTA
        elif result.decision == ExperimentDecision.FAILED.value:
            delta = FAILED_WEIGHT_DELTA
        else:
            # Inconclusive but positive lift → small positive
            delta = PROMISING_WEIGHT_DELTA if result.lift > 0 else 0.0

        if delta == 0.0:
            return updates

        # Map candidate dimensions to weight keys
        dimension_map = {
            "hook": ("hook", candidate.hook),
            "reward": ("reward", candidate.reward),
            "visual": ("visual", candidate.visual_style),
            "fantasy": ("fantasy", candidate.fantasy),
        }

        # Update the mutation type's dimension
        dim_key = candidate.mutation_type
        if dim_key in dimension_map:
            dim, value = dimension_map[dim_key]
            if value:
                weight_key = f"{dim}.{value}"
                updates[weight_key] = round(delta, 4)

        return updates

    # ── Mutation Strategy Updates ──────────────────────────

    def _update_mutation_strategy(
        self,
        result: ExperimentResult,
        candidate: ExperimentCandidate,
    ) -> dict[str, str]:
        """Calculate mutation strategy adjustments.

        WINNER → "increase" probability of this mutation type
        FAILED → "decrease" probability of this mutation type
        """
        updates: dict[str, str] = {}

        if result.decision == ExperimentDecision.WINNER.value:
            updates[candidate.mutation_type] = "increase"
        elif result.decision == ExperimentDecision.FAILED.value:
            updates[candidate.mutation_type] = "decrease"
        else:
            updates[candidate.mutation_type] = "maintain"

        return updates

    # ── Prediction Weight Updates ──────────────────────────

    def _update_prediction_weights(
        self, result: ExperimentResult
    ) -> dict[str, float]:
        """Calculate prediction weight adjustments.

        If actual ROAS > predicted, increase LTV weight.
        If actual ROAS < predicted, decrease LTV weight.
        """
        updates: dict[str, float] = {}

        if result.decision == ExperimentDecision.WINNER.value:
            updates["ltv_weight"] = 1.05
            updates["retention_weight"] = 1.02
        elif result.decision == ExperimentDecision.FAILED.value:
            updates["ltv_weight"] = 0.95
            updates["retention_weight"] = 0.98
        else:
            updates["ltv_weight"] = 1.0
            updates["retention_weight"] = 1.0

        return updates

    # ── Apply to E9.7 ──────────────────────────────────────

    def apply_feedback_to_e97(
        self, signals: list[FeedbackSignal]
    ) -> dict[str, bool]:
        """Write feedback signals to E9.7 learning interface.

        Updates:
          - output/creative_learning/dna_weight_config.json
          - output/creative_learning/mutation_strategy.json

        Does NOT modify E9.7 source code. E9.7 reads these files
        on its next run.

        Returns:
            {file: success} status dict
        """
        results = {}

        # Update DNA weight config
        results["dna_weight_config"] = self._update_dna_weight_file(signals)

        # Update mutation strategy config
        results["mutation_strategy"] = self._update_mutation_strategy_file(signals)

        return results

    def _update_dna_weight_file(
        self, signals: list[FeedbackSignal]
    ) -> bool:
        """Update dna_weight_config.json with experiment feedback."""
        path = self._e97_dir / "dna_weight_config.json"

        try:
            # Load existing weights
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    weights = json.load(f)
            else:
                weights = {}

            # Apply updates
            for signal in signals:
                for key, delta in signal.dna_weight_update.items():
                    current = weights.get(key, 0.5)
                    new_value = current + delta
                    weights[key] = round(
                        max(MIN_WEIGHT, min(MAX_WEIGHT, new_value)), 4
                    )

            # Write back
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(weights, f, ensure_ascii=False, indent=2)

            return True
        except Exception:
            return False

    def _update_mutation_strategy_file(
        self, signals: list[FeedbackSignal]
    ) -> bool:
        """Update mutation_strategy.json with experiment feedback."""
        path = self._e97_dir / "mutation_strategy.json"

        try:
            # Load existing strategies
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    strategies = json.load(f)
            else:
                strategies = {}

            # Apply updates
            for signal in signals:
                for mtype, action in signal.mutation_strategy_update.items():
                    if mtype not in strategies:
                        strategies[mtype] = {"probability": 0.5, "count": 0}
                    strategies[mtype]["count"] += 1
                    if action == "increase":
                        strategies[mtype]["probability"] = min(
                            0.9, strategies[mtype]["probability"] + 0.05
                        )
                    elif action == "decrease":
                        strategies[mtype]["probability"] = max(
                            0.1, strategies[mtype]["probability"] - 0.05
                        )

            # Write back
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(strategies, f, ensure_ascii=False, indent=2)

            return True
        except Exception:
            return False

    # ── Summary ────────────────────────────────────────────

    def get_feedback_summary(
        self, signals: list[FeedbackSignal]
    ) -> dict[str, Any]:
        """Get summary of generated feedback signals."""
        total_weight_updates = sum(
            len(s.dna_weight_update) for s in signals
        )
        total_strategy_updates = sum(
            len(s.mutation_strategy_update) for s in signals
        )

        return {
            "total_signals": len(signals),
            "total_dna_weight_updates": total_weight_updates,
            "total_strategy_updates": total_strategy_updates,
            "avg_confidence": (
                round(sum(s.confidence for s in signals) / max(1, len(signals)), 3)
                if signals else 0.0
            ),
            "by_action": {
                action: sum(
                    1 for s in signals
                    if action in s.mutation_strategy_update.values()
                )
                for action in ["increase", "decrease", "maintain"]
            },
        }