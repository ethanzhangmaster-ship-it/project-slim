"""
E15.2.6 — Waterfall Optimizer.

Surfaces opportunities to trim an over-deep waterfall (too many low-yield
instances) which wastes auction latency and request budget. Reuses
OpportunityDetector, filtered to waterfall_waste.
"""
from __future__ import annotations

from typing import List, Optional

from operation.optimizer.intel_models import MonetizationDailyReport
from operation.revenue_optimizer.models import RevenueOpportunity
from operation.revenue_optimizer.opportunity.detector import OpportunityDetector


class WaterfallOptimizer:
    ACTIONS = ("reduce_waterfall_depth",)

    def __init__(self) -> None:
        self._det = OpportunityDetector()

    def optimize(self, report: MonetizationDailyReport,
                 dau: Optional[float] = None) -> List[RevenueOpportunity]:
        # waterfall_waste signals are advisory; map to an opportunity if present
        out = []
        for o in self._det.detect(report, dau):
            if o.rule == "waterfall_waste":
                out.append(o)
        return out
