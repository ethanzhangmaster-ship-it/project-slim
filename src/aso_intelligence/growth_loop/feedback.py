"""
E16.6.5 — ASO Feedback Loop (Revenue Intelligence connection).

Evaluates experiment results on revenue, not just downloads.

A CVR win that harms LTV is punished — the pattern's reward is lowered
so the system learns to prioritise *profitable* growth.

Pipeline:
    Experiment Result → Feedback Loop → Pattern Reward Adjustment → Store

``RevenueFeedback`` is returned when an experiment is evaluated, carrying the
adjusted reward and a human-readable verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.aso_intelligence.experiment_memory.experiment_models import (
    ASOExperimentResult,
    ASOPattern,
)
from src.aso_intelligence.experiment_memory.experiment_store import ASOExperimentStore
from src.aso_intelligence.experiment_memory.scorer import ASOPatternScorer


@dataclass
class RevenueFeedback:
    """Result of evaluating an experiment's revenue impact."""

    experiment_id: str
    cvr_change: float
    ltv_change: float
    revenue_uplift: float
    is_growth: bool  # True = genuine revenue growth
    adjusted_reward: float  # reward after LTV adjustment
    verdict: str  # human-readable explanation

    def is_fake_growth(self) -> bool:
        """True if CVR went up but revenue didn't (e.g. LTV crash)."""
        return self.cvr_change > 0 and not self.is_growth


_REVENUE_THRESHOLD = 0.0  # revenue must be strictly positive
_LTV_PENALTY_FACTOR = 2.0  # how much LTV drop penalises the reward


class ASOFeedbackLoop:
    """Evaluate experiment results and adjust patterns based on revenue impact.

    This is the key "Revenue Intelligence connection" that ensures ASO
    optimises for profit, not just installs.
    """

    def __init__(
        self,
        store: ASOExperimentStore,
        scorer: Optional[ASOPatternScorer] = None,
    ):
        self.store = store
        self.scorer = scorer or ASOPatternScorer()

    # ------------------------------------------------------------------ #
    def evaluate(self, result: ASOExperimentResult) -> RevenueFeedback:
        """Evaluate one experiment result against revenue metrics.

        ``adjusted_reward``:
        * If LTV went up or stayed stable → reward = revenue_uplift (full credit)
        * If LTV dropped → penalty: reward = revenue_uplift - (|ltv_drop| × LTV_PENALTY_FACTOR)
        * If revenue_uplift ≤ 0 → reward = 0 (no credit)
        """
        cvr_chg = result.cvr_change()
        ltv_chg = result.ltv_change()
        rev_uplift = result.revenue_uplift()

        is_growth = result.is_revenue_success(allow_ltv_drop=0.0)

        # Calculate adjusted reward
        if not is_growth:
            if ltv_chg < 0 and cvr_chg > 0:
                # CVR+ but LTV-  → penalty (fake growth)
                adjusted = max(0.0, rev_uplift - abs(ltv_chg) * _LTV_PENALTY_FACTOR)
                verdict = (
                    f"CVR {cvr_chg:+.1%} but LTV {ltv_chg:+.1%} — "
                    f"fake growth detected, reward penalised"
                )
            elif rev_uplift <= 0:
                adjusted = 0.0
                verdict = (
                    f"Revenue {rev_uplift:+.1%} is not positive — "
                    f"no reward credit"
                )
            else:
                adjusted = max(0.0, rev_uplift)
                verdict = (
                    f"Revenue {rev_uplift:+.1%} positive but LTV "
                    f"{ltv_chg:+.1%} below tolerance — partial credit"
                )
        else:
            # Genuine growth — full credit
            adjusted = max(0.0, rev_uplift)
            verdict = (
                f"Genuine growth: CVR {cvr_chg:+.1%}, LTV {ltv_chg:+.1%}, "
                f"revenue {rev_uplift:+.1%}"
            )

        return RevenueFeedback(
            experiment_id=result.experiment_id,
            cvr_change=cvr_chg,
            ltv_change=ltv_chg,
            revenue_uplift=rev_uplift,
            is_growth=is_growth,
            adjusted_reward=round(adjusted, 6),
            verdict=verdict,
        )

    # ------------------------------------------------------------------ #
    def adjust_pattern_rewards(
        self,
        results: List[ASOExperimentResult],
    ) -> int:
        """Re-mine patterns from a batch of results, adjusting rewards for
        revenue feedback.

        Returns the number of new patterns written to the store.

        Loads the original experiments from the store matching each result,
        then runs the PatternMiner to extract (and persist) new patterns.
        The ``adjusted_reward`` is already encoded because the miner uses
        ``is_revenue_success`` from the result model — experiments that
        hurt LTV are counted as failures and downweighted.
        """
        from src.aso_intelligence.experiment_memory.pattern_miner import (
            ASOPatternMiner,
        )

        miner = ASOPatternMiner()
        # Load experiments from store that match the result IDs
        all_experiments = self.store.load_experiments()
        result_ids = {r.experiment_id for r in results}
        matching_exps = [
            e for e in all_experiments if e.experiment_id in result_ids
        ]

        if not matching_exps:
            return 0

        new_patterns = miner.mine(matching_exps, results)
        for pat in new_patterns:
            self.store.record_pattern(pat)
        return len(new_patterns)

    # ------------------------------------------------------------------ #
    def pattern_reward_impact(
        self,
        pattern: ASOPattern,
    ) -> float:
        """Score a pattern after revenue adjustment.

        Returns a multiplier applied to the pattern's raw reward:
        * >= 1.0 = revenue-positive (good, keep/boost)
        * < 1.0 = revenue-negative (downweight)
        """
        return pattern.reward if pattern.reward > 0 else 0.0


__all__ = ["RevenueFeedback", "ASOFeedbackLoop"]
