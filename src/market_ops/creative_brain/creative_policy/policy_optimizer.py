"""V4.3 Policy Optimizer — learn optimal thresholds from historical replay data.

Takes V4.2.1 Historical Replay results and learns:
  - Optimal confidence thresholds for GO/TEST/KILL
  - Optimal ROI thresholds
  - Trend bonus/penalty values
  - Explore/Exploit ratios

Uses grid search over historical data to find thresholds that maximize
cumulative ROI, Winner Recall, or composite score.
"""

from __future__ import annotations

import random
from typing import Any

from .schemas import DecisionPolicy


class PolicyOptimizer:
    """Learn optimal policy thresholds from historical replay data.

    Simulates policy decisions against historical ground truth and
    finds thresholds that maximize cumulative ROI.
    """

    def __init__(self) -> None:
        self._optimization_history: list[dict[str, Any]] = []

    def optimize(self, replay_records: list[dict[str, Any]],
                 initial_policy: DecisionPolicy | None = None,
                 method: str = "grid_search") -> DecisionPolicy:
        """Optimize policy thresholds using historical replay data.

        Args:
            replay_records: List of replay records with keys:
                creative_id, predicted_decision, actual_decision,
                confidence, actual_roas, predicted_roas, is_correct.
            initial_policy: Starting policy (defaults to standard).
            method: "grid_search" or "random_search".

        Returns:
            Optimized DecisionPolicy with updated thresholds.
        """
        policy = initial_policy or DecisionPolicy()

        if method == "random_search":
            best_policy = self._random_search(replay_records, policy)
        else:
            best_policy = self._grid_search(replay_records, policy)

        best_policy.version = self._next_version(policy.version)
        best_policy.previous_version = policy.version
        best_policy.improved_from = initial_policy.version if initial_policy else ""

        self._optimization_history.append({
            "from_version": policy.version,
            "to_version": best_policy.version,
            "method": method,
        })

        return best_policy

    def _grid_search(self, records: list[dict[str, Any]],
                     base: DecisionPolicy) -> DecisionPolicy:
        """Grid search over threshold space."""
        best_policy = base
        best_score = self._evaluate_policy(base, records)

        # Search ranges
        conf_go_range = [0.55, 0.60, 0.65, 0.70, 0.72, 0.75, 0.78, 0.80, 0.85]
        conf_kill_range = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45]
        roi_go_range = [0.5, 0.6, 0.7, 0.8, 0.9]
        roi_kill_range = [0.1, 0.15, 0.2, 0.25, 0.3]
        trend_bonus_range = [0.05, 0.10, 0.15, 0.20]
        explore_range = [0.10, 0.15, 0.20, 0.25, 0.30]

        for conf_go in conf_go_range:
            for conf_kill in conf_kill_range:
                if conf_kill >= conf_go:
                    continue
                for roi_go in roi_go_range:
                    for roi_kill in roi_kill_range:
                        if roi_kill >= roi_go:
                            continue
                        for trend_bonus in trend_bonus_range:
                            for explore in explore_range:
                                candidate = DecisionPolicy(
                                    confidence_threshold_go=conf_go,
                                    confidence_threshold_kill=conf_kill,
                                    roi_threshold_go=roi_go,
                                    roi_threshold_kill=roi_kill,
                                    trend_growing_bonus=trend_bonus,
                                    default_explore_ratio=explore,
                                )
                                score = self._evaluate_policy(candidate, records)
                                if score > best_score:
                                    best_score = score
                                    best_policy = candidate

        best_policy.improvement_score = best_score
        return best_policy

    def _random_search(self, records: list[dict[str, Any]],
                       base: DecisionPolicy, n_trials: int = 100) -> DecisionPolicy:
        """Random search over threshold space."""
        random.seed(42)
        best_policy = base
        best_score = self._evaluate_policy(base, records)

        for _ in range(n_trials):
            candidate = DecisionPolicy(
                confidence_threshold_go=random.uniform(0.55, 0.85),
                confidence_threshold_kill=random.uniform(0.20, 0.45),
                roi_threshold_go=random.uniform(0.5, 0.9),
                roi_threshold_kill=random.uniform(0.1, 0.3),
                trend_growing_bonus=random.uniform(0.05, 0.20),
                default_explore_ratio=random.uniform(0.10, 0.30),
            )
            # Ensure kill < go thresholds
            if candidate.confidence_threshold_kill >= candidate.confidence_threshold_go:
                candidate.confidence_threshold_kill = candidate.confidence_threshold_go - 0.2

            score = self._evaluate_policy(candidate, records)
            if score > best_score:
                best_score = score
                best_policy = candidate

        best_policy.improvement_score = best_score
        return best_policy

    def _evaluate_policy(self, policy: DecisionPolicy,
                         records: list[dict[str, Any]]) -> float:
        """Evaluate a policy against historical records.

        Simulates what would have happened if this policy was used.
        Returns a composite score (higher = better).

        Score = accuracy * 0.3 + cumulative_roi * 0.5 + winner_recall * 0.2
        """
        if not records:
            return 0.0

        correct = 0
        total_roi = 0.0
        winners_found = 0
        total_winners = 0

        for r in records:
            actual_roas = r.get("actual_roas", 0)
            is_winner = actual_roas >= 0.5
            if is_winner:
                total_winners += 1

            # Simulate policy decision
            confidence = r.get("confidence", 0.5)
            if confidence >= policy.confidence_threshold_go:
                simulated_action = "GO"
            elif confidence >= 0.45:
                simulated_action = "TEST"
            elif confidence >= policy.confidence_threshold_kill:
                simulated_action = "EXPLORE"
            else:
                simulated_action = "AVOID"

            actual_decision = r.get("actual_decision", "")
            if simulated_action == actual_decision:
                correct += 1

            # If policy would have gone with this creative
            if simulated_action in ("GO", "TEST"):
                total_roi += actual_roas
                if is_winner:
                    winners_found += 1

        accuracy = correct / len(records)
        avg_roi = total_roi / len(records)
        winner_recall = winners_found / max(total_winners, 1)

        return accuracy * 0.3 + avg_roi * 0.5 + winner_recall * 0.2

    def _next_version(self, current_version: str) -> str:
        """Increment policy version."""
        parts = current_version.split(".")
        if len(parts) == 3:
            parts[2] = str(int(parts[2]) + 1)
        return ".".join(parts)

    def get_optimization_history(self) -> list[dict[str, Any]]:
        return list(self._optimization_history)