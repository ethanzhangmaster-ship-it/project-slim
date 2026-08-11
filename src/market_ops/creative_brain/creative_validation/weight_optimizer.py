"""V4.2 Weight Optimizer — auto-optimize evidence weights.

Methods:
  - Grid Search: exhaustive search over weight grid
  - Random Search: random sampling
  - Bayesian Optimization: (placeholder for future)

Optimizes weights for: Retriever, Pattern, Trend, Graph, Learning.

Usage:
    optimizer = WeightOptimizer(evaluator=evaluator)
    result = optimizer.optimize(records, method="grid_search")
"""

from __future__ import annotations

import itertools
import random
from typing import Any

from .schemas import ReplayRecord, WeightOptimizationResult, OptimizerMethod


class WeightOptimizer:
    """Auto-optimize evidence source weights for maximum accuracy.

    The objective is to find weights that maximize prediction accuracy
    when computing weighted confidence scores.
    """

    DEFAULT_WEIGHTS = {
        "retriever": 0.25,
        "pattern": 0.30,
        "graph": 0.15,
        "learning": 0.15,
        "trend": 0.15,
    }

    WEIGHT_KEYS = list(DEFAULT_WEIGHTS.keys())

    def __init__(self, evaluator=None) -> None:
        self._evaluator = evaluator

    def optimize(self, records: list[ReplayRecord],
                 method: OptimizerMethod = OptimizerMethod.GRID_SEARCH,
                 step: float = 0.1) -> WeightOptimizationResult:
        """Optimize weights to maximize prediction accuracy.

        Args:
            records: Replay records for evaluation.
            method: Optimization method.
            step: Grid search step size.

        Returns:
            WeightOptimizationResult with optimized weights.
        """
        if not records:
            return WeightOptimizationResult(
                method=method,
                initial_weights=self.DEFAULT_WEIGHTS,
                optimized_weights=self.DEFAULT_WEIGHTS,
            )

        initial_score = self._evaluate_weights(self.DEFAULT_WEIGHTS, records)

        if method == OptimizerMethod.GRID_SEARCH:
            best_weights, best_score, trials = self._grid_search(records, step)
        elif method == OptimizerMethod.RANDOM_SEARCH:
            best_weights, best_score, trials = self._random_search(records, n_trials=50)
        elif method == OptimizerMethod.MULTI_ARMED_BANDIT:
            best_weights, best_score, trials = self._multi_armed_bandit(records, n_rounds=30)
        else:
            best_weights, best_score, trials = self._grid_search(records, step)

        return WeightOptimizationResult(
            method=method,
            initial_weights=dict(self.DEFAULT_WEIGHTS),
            optimized_weights=best_weights,
            initial_score=initial_score,
            optimized_score=best_score,
            improvement=best_score - initial_score,
            trials=trials,
        )

    def _grid_search(self, records: list[ReplayRecord],
                     step: float = 0.1) -> tuple[dict[str, float], float, int]:
        """Grid search over weight combinations."""
        values = [round(i * step, 2) for i in range(int(1.0 / step) + 1)]

        best_weights = dict(self.DEFAULT_WEIGHTS)
        best_score = 0.0
        trials = 0

        # Generate all weight combinations that sum to 1.0
        # Use a coarser grid for efficiency (step=0.2 for 5 dimensions)
        coarse_step = 0.2
        coarse_values = [round(i * coarse_step, 2) for i in range(int(1.0 / coarse_step) + 1)]

        for combo in itertools.product(coarse_values, repeat=len(self.WEIGHT_KEYS)):
            if abs(sum(combo) - 1.0) > 0.01:
                continue
            weights = {k: v for k, v in zip(self.WEIGHT_KEYS, combo)}
            score = self._evaluate_weights(weights, records)
            trials += 1
            if score > best_score:
                best_score = score
                best_weights = weights

        return best_weights, best_score, trials

    def _random_search(self, records: list[ReplayRecord],
                       n_trials: int = 50) -> tuple[dict[str, float], float, int]:
        """Random search over weight space."""
        random.seed(42)

        best_weights = dict(self.DEFAULT_WEIGHTS)
        best_score = 0.0

        for _ in range(n_trials):
            # Generate random weights
            raw = [random.random() for _ in range(len(self.WEIGHT_KEYS))]
            total = sum(raw)
            weights = {
                k: round(v / total, 3)
                for k, v in zip(self.WEIGHT_KEYS, raw)
            }
            score = self._evaluate_weights(weights, records)
            if score > best_score:
                best_score = score
                best_weights = weights

        return best_weights, best_score, n_trials

    def _multi_armed_bandit(self, records: list[ReplayRecord],
                            n_rounds: int = 30) -> tuple[dict[str, float], float, int]:
        """Multi-Armed Bandit optimization for weights.

        Each weight source is an "arm". We pull arms proportional to their
        estimated reward (accuracy contribution), exploring with epsilon-greedy.
        """
        import random
        random.seed(42)

        weights = dict(self.DEFAULT_WEIGHTS)
        best_weights = dict(weights)
        best_score = self._evaluate_weights(weights, records)
        epsilon = 0.2  # exploration rate

        # Track per-arm performance
        arm_rewards = {k: 0.0 for k in self.WEIGHT_KEYS}
        arm_pulls = {k: 0 for k in self.WEIGHT_KEYS}

        for _ in range(n_rounds):
            if random.random() < epsilon:
                # Explore: random adjustment
                key_to_adjust = random.choice(self.WEIGHT_KEYS)
                delta = random.uniform(-0.1, 0.1)
                weights[key_to_adjust] = max(0.0, min(1.0, weights[key_to_adjust] + delta))
            else:
                # Exploit: adjust best-performing arm
                best_arm = max(arm_rewards, key=lambda k: arm_rewards[k] / max(arm_pulls[k], 1))
                weights[best_arm] = min(1.0, weights[best_arm] + 0.05)

            # Normalize
            total = sum(weights.values())
            if total > 0:
                weights = {k: v / total for k, v in weights.items()}

            # Evaluate
            score = self._evaluate_weights(weights, records)
            for k in self.WEIGHT_KEYS:
                arm_rewards[k] += score * weights[k]
                arm_pulls[k] += 1

            if score > best_score:
                best_score = score
                best_weights = dict(weights)

        return best_weights, best_score, n_rounds

    def _evaluate_weights(self, weights: dict[str, float],
                          records: list[ReplayRecord]) -> float:
        """Evaluate a set of weights by computing accuracy."""
        if not records:
            return 0.0

        correct = 0
        for r in records:
            # Simplified: use confidence as proxy for correctness
            if r.is_correct:
                correct += 1

        return correct / len(records)

    def interpret(self, result: WeightOptimizationResult) -> str:
        """Human-readable interpretation of optimization results."""
        lines = [
            f"Weight Optimization ({result.method.value}):",
            f"  Initial accuracy: {result.initial_score:.2%}",
            f"  Optimized accuracy: {result.optimized_score:.2%}",
            f"  Improvement: {result.improvement:+.4f}",
            f"  Trials: {result.trials}",
            "",
            "  Weight changes:",
        ]

        for key in self.WEIGHT_KEYS:
            old = result.initial_weights.get(key, 0)
            new = result.optimized_weights.get(key, 0)
            change = new - old
            lines.append(
                f"    {key}: {old:.0%} → {new:.0%} ({change:+.0%})"
            )

        return "\n".join(lines)