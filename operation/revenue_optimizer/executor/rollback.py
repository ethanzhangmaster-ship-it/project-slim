"""
E15.2.6 §8/§9 — Rollback Planner.

Produces the inverse ChangePackage for a previously-emitted package, so a
LOSER experiment can be reverted in MAX. Inverse map:
  disable_network        -> enable_network
  increase_bid_opportunity -> revert_bid_opportunity
  change_floor           -> remove_floor (value cleared)
  diversify              -> revert_diversify
"""
from __future__ import annotations

from typing import Dict

from operation.revenue_optimizer.models import (
    ChangeAction, ChangePackage,
)

_INVERSE = {
    "disable_network": "enable_network",
    "increase_bid_opportunity": "revert_bid_opportunity",
    "change_floor": "remove_floor",
    "diversify": "revert_diversify",
    "review": "review",
}


class RollbackPlanner:
    def plan(self, pkg: ChangePackage) -> ChangePackage:
        inv_actions = []
        for a in pkg.actions:
            inv_type = _INVERSE.get(a.type, "review")
            inv_actions.append(ChangeAction(
                type=inv_type, network=a.network, value=None,
                requires_manual_apply=True))
        return ChangePackage(
            account=pkg.account, experiment_id=pkg.experiment_id,
            actions=inv_actions,
            note=f"rollback of {pkg.experiment_id}", created_at="")
