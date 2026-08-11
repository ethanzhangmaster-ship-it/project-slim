"""
E16.6.6 — ASO Action Rewarder.

Connects E16.6.6 (Revenue Attribution) → E16.6.4 (Experiment Memory).

Transforms revenue-attributed experiment results into ``ASOPattern`` records
stored in the E16.6.4 store, so the rest of the ASO system learns from
revenue-adjusted outcomes.

Key upgrade over E16.6.4's naive CVR reward:
  * ``Reward = CVR uplift × Revenue quality × LTV multiplier``
  * CVR traps (installs up, payer rate down) → penalised
  * Country-aware reward weighting
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.aso_intelligence.revenue.models import (
    ASOAcquisitionEvent,
    ASORevenueAttribution,
    ASOActionReward,
)
from src.aso_intelligence.revenue.quality import ASOUserQualityAnalyzer
from src.aso_intelligence.experiment_memory.experiment_store import ASOExperimentStore
from src.aso_intelligence.experiment_memory.experiment_models import (
    ASOPattern,
)


class ASOActionRewarder:
    """Evaluate ASO experiments with revenue-adjusted rewards and persist
    the learnings into E16.6.4's pattern store.

    This is where "CVR uplift alone is not enough" becomes a hard rule.
    """

    def __init__(
        self,
        store: ASOExperimentStore,
        quality: Optional[ASOUserQualityAnalyzer] = None,
    ):
        self.store = store
        self.quality = quality or ASOUserQualityAnalyzer()

    # ------------------------------------------------------------------ #
    def evaluate(
        self,
        experiment_id: str,
        game_id: str,
        attribution_before: ASORevenueAttribution,
        attribution_after: ASORevenueAttribution,
    ) -> ASOActionReward:
        """Compute revenue-adjusted reward for one experiment.

        Uses payer rate as the revenue quality signal and LTV as the
        monetisation signal — the two metrics that matter for IAP games.
        """
        cvr_uplift = (
            (attribution_after.installs - attribution_before.installs)
            / max(attribution_before.installs, 1)
        )
        reward = ASOActionReward(
            experiment_id=experiment_id,
            game_id=game_id,
            cvr_uplift=max(0.0, cvr_uplift),
            payer_rate_before=attribution_before.payer_rate,
            payer_rate_after=attribution_after.payer_rate,
            ltv_before=attribution_before.ltv,
            ltv_after=attribution_after.ltv,
        )
        reward.compute()
        return reward

    # ------------------------------------------------------------------ #
    def persist_pattern(
        self,
        game_id: str,
        category: str,
        condition: str,
        action: str,
        reward: ASOActionReward,
    ) -> ASOPattern:
        """Write a revenue-adjusted ``ASOPattern`` into E16.6.4's store.

        ``condition`` describes the ASO context (e.g. "screenshot_weak").
        ``action`` describes what was done (e.g. "UPDATE_SCREENSHOT").
        ``reward.final_reward`` is the revenue-adjusted value.
        """
        result_str = (
            f"+{reward.final_reward:.1%} revenue-adjusted "
            f"(CVR {reward.cvr_uplift:+.0%}, "
            f"payer quality {reward.revenue_quality:.2f})"
        )
        pattern = ASOPattern(
            category=category,
            condition=condition,
            action=action,
            result=result_str,
            confidence=round(
                max(0.0, 1.0 - abs(reward.revenue_quality - 1.0)), 4
            ),
            sample_size=1,
            success_rate=0.0 if reward.is_fake_growth else 1.0,
            reward=reward.final_reward,
            pattern_id=f"{category}:{condition}:{action}:revenue",
        )
        self.store.record_pattern(pattern)
        return pattern

    # ------------------------------------------------------------------ #
    def evaluate_and_learn(
        self,
        experiment_id: str,
        game_id: str,
        category: str,
        condition: str,
        action: str,
        attribution_before: ASORevenueAttribution,
        attribution_after: ASORevenueAttribution,
    ) -> ASOActionReward:
        """Convenience: evaluate + persist in one call."""
        reward = self.evaluate(
            experiment_id, game_id, attribution_before, attribution_after
        )
        self.persist_pattern(game_id, category, condition, action, reward)
        return reward


__all__ = ["ASOActionRewarder"]
