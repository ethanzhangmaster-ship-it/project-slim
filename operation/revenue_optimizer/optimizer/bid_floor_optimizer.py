"""
E15.2.6 — Bid Floor Optimizer.

Surfaces opportunities to lift the price floor on parasite backfill networks
(those whose eCPM is far below the account blend while consuming a large
impression share). Reuses OpportunityDetector, filtered to bid-constraint.
"""
from __future__ import annotations

from typing import List, Optional

from operation.optimizer.intel_models import MonetizationDailyReport
from operation.revenue_optimizer.models import RevenueOpportunity
from operation.revenue_optimizer.opportunity.detector import OpportunityDetector


class BidFloorOptimizer:
    ACTIONS = ("adjust_bid_constraint",)

    def __init__(self) -> None:
        self._det = OpportunityDetector()

    def optimize(self, report: MonetizationDailyReport,
                 dau: Optional[float] = None) -> List[RevenueOpportunity]:
        return [o for o in self._det.detect(report, dau)
                if o.action in self.ACTIONS]
