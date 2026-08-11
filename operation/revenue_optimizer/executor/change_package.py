"""
E15.2.6 §7 — Change Package Builder.

Because the MAX Management API cannot write expanded-targeting waterfalls
(PATCH 403/422), the autopilot never mutates MAX. Instead it emits a structured
ChangePackage the operator applies manually in the dashboard. Each package is
a set of atomic ChangeActions tagged requires_manual_apply=True.

Supported action kinds map 1:1 to the intel rules' recommended levers.
"""
from __future__ import annotations

from typing import List, Optional

from operation.revenue_optimizer.models import (
    ChangeAction, ChangePackage, RevenueOpportunity,
)


class ChangePackageBuilder:
    def build(self, opp: RevenueOpportunity,
              experiment_id: Optional[str] = None) -> ChangePackage:
        actions: List[ChangeAction] = []
        t = opp.target
        if opp.action in ("disable_network", "quarantine_network"):
            actions.append(ChangeAction(type="disable_network", network=t))
        elif opp.action == "increase_bid_opportunity":
            actions.append(ChangeAction(type="increase_bid_opportunity",
                                         network=t))
        elif opp.action == "adjust_bid_constraint":
            rng = (opp.metrics or {}).get("recommended_floor_range") or [0.0, 0.0]
            val = float(rng[0]) if rng else 0.0
            actions.append(ChangeAction(type="change_floor", network=t,
                                         value=round(val, 2)))
        elif opp.action == "diversify":
            actions.append(ChangeAction(type="diversify", network=t))
        else:
            # unknown lever: record as advisory only
            actions.append(ChangeAction(type="review", network=t))
        return ChangePackage(
            account=opp.app_id, experiment_id=experiment_id or opp.id,
            actions=actions, note=opp.reason)
