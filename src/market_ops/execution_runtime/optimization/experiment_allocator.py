"""E10.2 Phase 5 — Experiment Allocator.

Multi-campaign budget allocation based on ROAS ranking.
Scores campaigns and allocates budget proportionally:
  - High ROAS → SCALE (increase budget)
  - Medium ROAS → WATCH (maintain)
  - Low ROAS → KILL (pause)

Phase 5 uses rule-based allocation (ROAS ranking).
Future upgrade: Multi-Armed Bandit.

Algorithm:
    1. Score each campaign by ROAS
    2. Rank by score descending
    3. Top performers → SCALE
    4. Bottom performers → KILL
    5. Middle → WATCH
"""

from __future__ import annotations

from market_ops.execution_runtime.optimization_schema import CampaignScore
from market_ops.execution_runtime.schemas import ActionType


class ExperimentAllocator:
    """Multi-campaign budget allocator.

    Ranks campaigns by ROAS and assigns SCALE/KILL/WATCH
    actions based on relative performance.

    Args:
        scale_threshold: ROAS above which to SCALE. Default: 1.5.
        kill_threshold: ROAS below which to KILL. Default: 0.8.
        scale_ratio: Budget increase ratio for top performers. Default: 0.30.
    """

    SCALE_THRESHOLD: float = 1.5
    KILL_THRESHOLD: float = 0.8

    def __init__(
        self,
        scale_threshold: float = 1.5,
        kill_threshold: float = 0.8,
        scale_ratio: float = 0.30,
    ) -> None:
        self._scale_threshold = scale_threshold
        self._kill_threshold = kill_threshold
        self._scale_ratio = scale_ratio

    def score_campaigns(
        self,
        campaigns: dict[str, dict[str, float]],
    ) -> list[CampaignScore]:
        """Score and rank multiple campaigns by ROAS.

        Args:
            campaigns: Dict of campaign_id → {"roas": float, "spend": float, "revenue": float}.

        Returns:
            List of CampaignScore sorted by score descending.
        """
        scores: list[CampaignScore] = []

        for cid, data in campaigns.items():
            roas = data.get("roas", 0.0)
            spend = data.get("spend", 0.0)
            revenue = data.get("revenue", 0.0)

            # Score = ROAS (primary) + spend factor (secondary)
            score = roas + (spend / 10000.0) * 0.1

            if roas > self._scale_threshold:
                action = ActionType.SCALE.value
            elif roas >= self._kill_threshold:
                action = ActionType.WATCH.value
            else:
                action = ActionType.KILL.value

            scores.append(CampaignScore(
                campaign_id=cid,
                roas=roas,
                spend=spend,
                revenue=revenue,
                score=round(score, 2),
                action=action,
            ))

        # Sort by score descending
        scores.sort(key=lambda s: s.score, reverse=True)

        # Assign ranks
        for i, s in enumerate(scores):
            s.rank = i + 1

        return scores

    def allocate(
        self,
        campaigns: dict[str, dict[str, float]],
    ) -> dict[str, dict[str, float]]:
        """Allocate budget changes across campaigns.

        Args:
            campaigns: Dict of campaign_id → {"roas": float, "spend": float, "revenue": float}.

        Returns:
            Dict of campaign_id → {"action": str, "budget_after": float, "budget_delta": float}.
        """
        scores = self.score_campaigns(campaigns)
        allocation: dict[str, dict[str, float]] = {}

        for s in scores:
            data = campaigns[s.campaign_id]
            current_budget = data.get("spend", 100.0)

            if s.action == ActionType.SCALE.value:
                new_budget = round(current_budget * (1.0 + self._scale_ratio), 2)
                allocation[s.campaign_id] = {
                    "action": ActionType.SCALE.value,
                    "budget_before": current_budget,
                    "budget_after": new_budget,
                    "budget_delta": round(new_budget - current_budget, 2),
                }
            elif s.action == ActionType.KILL.value:
                allocation[s.campaign_id] = {
                    "action": ActionType.KILL.value,
                    "budget_before": current_budget,
                    "budget_after": 0.0,
                    "budget_delta": -current_budget,
                }
            else:
                allocation[s.campaign_id] = {
                    "action": ActionType.WATCH.value,
                    "budget_before": current_budget,
                    "budget_after": current_budget,
                    "budget_delta": 0.0,
                }

        return allocation

    def get_top_performers(
        self,
        campaigns: dict[str, dict[str, float]],
        top_n: int = 3,
    ) -> list[CampaignScore]:
        """Get the top N performing campaigns.

        Args:
            campaigns: Campaign data dict.
            top_n: Number of top performers to return.

        Returns:
            Top N CampaignScore objects.
        """
        scores = self.score_campaigns(campaigns)
        return [s for s in scores if s.action == ActionType.SCALE.value][:top_n]