"""
E16.6.13 — Operator Monitor.

Tracks before/after metrics for executed operations.
Detects when experiments should conclude and triggers learning.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from src.aso_intelligence.operator.models import ASOOperationExperience


class OperatorMonitor:
    """Monitor operation results and trigger learning."""

    def __init__(self, monitoring_days: int = 14):
        self.monitoring_days = monitoring_days
        self._results: Dict[str, ASOOperationExperience] = {}

    # ------------------------------------------------------------------ #
    def start_monitoring(
        self,
        plan_id: str,
        game_id: str,
        market: str,
        action_type: str,
        before_metrics: Dict[str, float] = None,
    ) -> None:
        """Begin tracking after an operation executes."""
        self._results[plan_id] = ASOOperationExperience(
            plan_id=plan_id,
            game_id=game_id,
            market=market,
            action_type=action_type,
            before_metrics=before_metrics or {},
        )

    # ------------------------------------------------------------------ #
    def collect_result(
        self,
        plan_id: str,
        after_metrics: Dict[str, float],
    ) -> Optional[ASOOperationExperience]:
        """Record after-operation metrics and compute deltas."""
        exp = self._results.get(plan_id)
        if exp is None:
            return None

        exp.after_metrics = after_metrics

        # Compute reward as composite of CVR and revenue changes
        cvr_delta = exp.cvr_change
        rev_delta = exp.revenue_change
        exp.reward = round(
            (1 + cvr_delta) * (1 + rev_delta) - 1, 6
        )

        # Success = positive revenue outcome
        exp.success = exp.reward > 0 and exp.cvr_change > -0.1

        return exp

    # ------------------------------------------------------------------ #
    def get_experience(self, plan_id: str) -> Optional[ASOOperationExperience]:
        return self._results.get(plan_id)

    # ------------------------------------------------------------------ #
    def active_monitoring_count(self) -> int:
        now = datetime.now(timezone.utc)
        count = 0
        for exp in self._results.values():
            if exp.after_metrics:  # Has results → completed
                continue
            count += 1
        return count


__all__ = ["OperatorMonitor"]
