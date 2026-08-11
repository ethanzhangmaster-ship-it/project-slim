"""
E16.6.4 — ASO Pattern Miner (cf. E13.4 PatternMiner).

Turns a pile of finished experiments + their measured results into a small set
of reusable ``ASOPattern`` records. The grouping key is
``(category, condition, action_type)`` — i.e. "in merge games, when the first
screenshot is weak, replacing it worked".

For each group it computes:
  * ``sample_size``  — how many experiments landed in the group
  * ``success_rate``— fraction that were *revenue* successes (LTV-aware)
  * ``reward``       — mean revenue uplift across the group
  * ``confidence``   — success_rate damped by small-sample penalty
                       (success_rate × min(1, n / min_sample))

Because ``is_revenue_success`` rejects CVR-wins that hurt LTV, a strategy that
boosts downloads but bleeds LTV earns a low (often zero) success_rate and is
therefore down-weighted — exactly the "final goal is revenue, not downloads"
rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from src.aso_intelligence.experiment_memory.experiment_models import (
    ASOExperiment,
    ASOExperimentAction,
    ASOExperimentResult,
    ASOPattern,
)


@dataclass
class ASOPatternMiner:
    """Mines experiments + results into reusable ASO patterns."""

    min_sample: int = 5
    allow_ltv_drop: float = 0.0  # tolerance for LTV decline when counting successes

    # ------------------------------------------------------------------ #
    def _key(self, exp: ASOExperiment) -> Tuple[str, str, str]:
        return (
            exp.category,
            exp.condition,
            exp.action_type.value,
        )

    def mine(
        self,
        experiments: List[ASOExperiment],
        results: List[ASOExperimentResult],
    ) -> List[ASOPattern]:
        """Group experiments by (category, condition, action) and summarise."""
        result_by_id: Dict[str, ASOExperimentResult] = {
            r.experiment_id: r for r in results
        }

        groups: Dict[Tuple[str, str, str], List[ASOExperiment]] = {}
        for exp in experiments:
            groups.setdefault(self._key(exp), []).append(exp)

        patterns: List[ASOPattern] = []
        for (category, condition, action), members in groups.items():
            if not members:
                continue

            n = len(members)
            successes = 0
            rewards: List[float] = []
            for m in members:
                res = result_by_id.get(m.experiment_id)
                if res is None:
                    continue
                rewards.append(res.revenue_uplift())
                if res.is_revenue_success(allow_ltv_drop=self.allow_ltv_drop):
                    successes += 1

            success_rate = round(successes / n, 4) if n else 0.0
            reward = round(sum(rewards) / len(rewards), 6) if rewards else 0.0
            # small-sample damping: confidence rises with evidence volume
            confidence = round(
                success_rate * min(1.0, n / self.min_sample), 4
            )

            result_str = (
                f"+{reward:.0%} revenue (n={n}, "
                f"{successes}/{n} revenue-success)"
            )

            patterns.append(
                ASOPattern(
                    category=category,
                    condition=condition,
                    action=action,
                    result=result_str,
                    confidence=confidence,
                    sample_size=n,
                    success_rate=success_rate,
                    reward=reward,
                    pattern_id=f"{category}:{condition}:{action}",
                )
            )

        # best first: most reward, then most evidence
        patterns.sort(key=lambda p: (p.reward, p.sample_size), reverse=True)
        return patterns


__all__ = ["ASOPatternMiner"]
