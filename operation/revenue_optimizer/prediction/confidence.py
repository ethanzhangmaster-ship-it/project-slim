"""
E15.2.6 §5 — Confidence Estimator.

Combines three independent signals into one confidence in [0, 0.95]:
  1. the rule's own signal confidence,
  2. target-segment sample size (more impressions -> more trust),
  3. historical prior from OptimizationMemory (a proven track record on the
     same (action, target) lifts confidence).

This is what lets the Safety Gate (§8) demand confidence >= 0.8 before any
change is auto-approved.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from operation.revenue_optimizer.models import RevenueOpportunity


class ConfidenceEstimator:
    MAX = 0.95
    MIN_IMP_FOR_FULL = 1000
    PRIOR_BUMP = 0.10       # max lift from a strong memory prior

    def estimate(self, opp: RevenueOpportunity,
                 ctx: Dict[str, Any],
                 memory=None) -> float:
        # 1. base signal confidence
        conf = min(max(opp.confidence, 0.0), 1.0)

        # 2. sample-size factor
        imps = float((opp.metrics or {}).get("impressions", 0) or 0)
        if imps >= self.MIN_IMP_FOR_FULL:
            sample = 1.0
        elif imps <= 0:
            sample = 0.6
        else:
            sample = 0.6 + 0.4 * (imps / self.MIN_IMP_FOR_FULL)
        conf *= sample

        # 3. memory prior bump
        if memory is not None:
            q = memory.query(action=opp.action, target=opp.target)
            p = q.get("prior", {})
            if p.get("n"):
                hit = p.get("hit_rate") or 0.0
                conf = min(self.MAX, conf + self.PRIOR_BUMP * hit)

        return round(min(conf, self.MAX), 4)
