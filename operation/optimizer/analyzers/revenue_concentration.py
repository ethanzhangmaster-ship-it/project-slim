"""
E15.2.5 Rule 5 — RevenueConcentrationAnalyzer (RevenueDependencyAnalyzer).

Detects dangerous dependency on a single app / network / country.
ACCT_2 grounding: Merge Monster contributes 99% of account revenue.
"""
from __future__ import annotations

from typing import Dict, List

from operation.optimizer.intel_models import IntelSignal, SegmentStat


class RevenueConcentrationAnalyzer:
    HIGH_RISK = 0.80       # one segment >= 80% of revenue
    MEDIUM_RISK = 0.60
    MIN_TOTAL_REVENUE = 10.0   # below this, concentration is meaningless

    DIM_LABEL = {"application": "app", "network": "network", "country": "country"}

    def analyze(self, segments: Dict[str, Dict[str, SegmentStat]]) -> List[IntelSignal]:
        """segments: {"application": {...}, "network": {...}, "country": {...}}"""
        signals: List[IntelSignal] = []
        for dim, stats in segments.items():
            total = sum(s.revenue for s in stats.values())
            if total < self.MIN_TOTAL_REVENUE or not stats:
                continue
            top_key, top = max(stats.items(), key=lambda kv: kv[1].revenue)
            share = top.revenue / total
            if share >= self.HIGH_RISK:
                sev, risk = "critical", "HIGH"
            elif share >= self.MEDIUM_RISK:
                sev, risk = "warning", "MEDIUM"
            else:
                continue
            label = self.DIM_LABEL.get(dim, dim)
            # CALIBRATION (user): country concentration is a UA / audience
            # problem, NOT something in-app monetization should "diversify".
            # Acting on geo here would cross the Monetization != Growth
            # boundary, so country only ever gets a monitor/hand-off action.
            if dim == "country":
                action = "monitor"
                scope_note = ("geo concentration is UA/Growth OS scope — "
                              "monitor only; do NOT diversify country from "
                              "the monetization system")
                reason = (f"One {label} contributes {share:.0%} of revenue "
                          f"('{top_key}' ${top.revenue:.2f} of ${total:.2f}) — "
                          f"audience risk {risk}; hand to Growth OS, monitor here")
            else:
                action = "diversify"
                scope_note = ("in-app monetization scope"
                              if dim == "network"
                              else "portfolio scope")
                reason = (f"One {label} contributes {share:.0%} of revenue "
                          f"('{top_key}' ${top.revenue:.2f} of ${total:.2f}) — risk {risk}")
            signals.append(IntelSignal(
                rule="revenue_concentration",
                severity=sev,
                action=action,
                target=f"{dim}:{top_key}",
                confidence=0.95,
                reason=reason,
                metrics={"risk": risk, "dimension": dim, "top": top_key,
                         "share": round(share, 4),
                         "top_revenue": round(top.revenue, 2),
                         "total_revenue": round(total, 2),
                         "scope": scope_note},
            ))
        order = {"critical": 0, "warning": 1}
        signals.sort(key=lambda x: (order.get(x.severity, 2), -x.metrics["share"]))
        return signals
