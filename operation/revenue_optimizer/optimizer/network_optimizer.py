"""
E15.2.6 — Network Optimizer.

Surfaces revenue opportunities that live at the *network* layer: removing
zombie networks (free waterfall slots) and promoting hidden-winners (capture
their eCPM-implied potential). Reuses OpportunityDetector and filters to the
two network-lever actions.
"""
from __future__ import annotations

from typing import List, Optional

from operation.optimizer.intel_models import MonetizationDailyReport
from operation.revenue_optimizer.models import RevenueOpportunity
from operation.revenue_optimizer.opportunity.detector import OpportunityDetector


class NetworkOptimizer:
    ACTIONS = ("disable_network", "quarantine_network",
               "increase_bid_opportunity")

    def __init__(self) -> None:
        self._det = OpportunityDetector()

    def optimize(self, report: MonetizationDailyReport,
                 dau: Optional[float] = None) -> List[RevenueOpportunity]:
        return [o for o in self._det.detect(report, dau)
                if o.action in self.ACTIONS]
