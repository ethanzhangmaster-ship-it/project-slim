"""
E13.2.8 — Module 6: Decision Interface
======================================

Maps each detected Opportunity to a *proposed* Decision.

Hard constraint (per E13.2.8 scope):
  * Decisions are NEVER executed here.
  * No MAX API call, no Adjust call, no RemoteConfig write.
  * `status` is always "proposed". The E13.3.3 Autonomous Executor is the
    only component allowed to apply a decision.

This is the seam where E13.3's Reality Layer -> Decision Engine plugs in.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import List


@dataclass
class Decision:
    decision_id: str
    opportunity_id: str
    action_type: str       # change_waterfall | review_bidding | adjust_ad_frequency
    target: str
    mutation: dict
    rationale: str
    status: str = "proposed"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


def create_decisions(opportunities: List) -> List[Decision]:
    decisions: List[Decision] = []
    for o in opportunities:
        seg = o.segment
        target = "_".join(str(seg.get(k, "")) for k in ("country", "platform", "ad_format", "network")
                          if seg.get(k))
        if o.type in ("ecpm_drop", "revenue_drop"):
            action = "change_waterfall"
            mutation = {
                "move": "mintegral",
                "below": "admob",
                "note": "Re-prioritise waterfall; promote a healthy network above the "
                        "underperforming one for this segment.",
            }
            rationale = (f"{o.type} on {target} ({o.detail.get('drop_pct')}% drop). "
                         f"Re-prioritise waterfall before bidding changes.")
        elif o.type == "fill_drop":
            action = "review_bidding"
            mutation = {
                "increase_bid_floor": False,
                "check_mediation_timeout": True,
                "enable_backup_networks": True,
            }
            rationale = (f"fill_rate dropped {o.detail.get('drop_pct')}% on {target}. "
                         f"Likely a mediation timeout / over-tight bid floor.")
        elif o.type == "ad_frequency_issue":
            action = "adjust_ad_frequency"
            mutation = {
                "remote_config": {"ads.reward_frequency": "increase_interval_by_1"},
                "rollout": "canary_10pct",
            }
            rationale = (f"Ad load rose while D1 retention fell on {target}. "
                         f"Reduce ad frequency via RemoteConfig and re-measure.")
        else:
            action = "review"
            mutation = {}
            rationale = "Unmapped opportunity; manual review."

        decisions.append(Decision(
            decision_id=str(uuid.uuid4())[:8],
            opportunity_id=o.id,
            action_type=action,
            target=target,
            mutation=mutation,
            rationale=rationale,
        ))
    return decisions
