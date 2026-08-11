"""
E15.2.5 Rule 6 — GeoOpportunityAnalyzer.

Finds tier-1 style geos where eCPM is far above the account blend but
volume is tiny — the highest-ROI UA targets. (UA execution itself is
Growth OS scope; this only surfaces the signal for the daily report.)
ACCT_2 grounding: dk/ch/nz/se eCPM $130-510 with near-zero volume,
while us delivers 67% of revenue at $126 eCPM.
"""
from __future__ import annotations

from typing import Dict, List

from operation.optimizer.intel_models import IntelSignal, SegmentStat


class GeoOpportunityAnalyzer:
    ECPM_MULTIPLIER = 1.5
    MAX_REVENUE_SHARE = 0.05
    MIN_IMPRESSIONS = 10      # some evidence, not a single fluke
    TOP_N = 5

    def analyze(self, by_country: Dict[str, SegmentStat],
                blended_ecpm: float) -> List[IntelSignal]:
        signals: List[IntelSignal] = []
        total_rev = sum(s.revenue for s in by_country.values())
        if blended_ecpm <= 0 or total_rev <= 0:
            return signals
        cands = []
        for cc, s in by_country.items():
            share = s.revenue / total_rev
            if (s.ecpm > blended_ecpm * self.ECPM_MULTIPLIER
                    and share < self.MAX_REVENUE_SHARE
                    and s.impressions >= self.MIN_IMPRESSIONS):
                cands.append((cc, s, share))
        cands.sort(key=lambda x: -x[1].ecpm)
        for cc, s, share in cands[: self.TOP_N]:
            signals.append(IntelSignal(
                rule="geo_opportunity",
                severity="info",
                action="handoff_ua",
                target=cc,
                confidence=round(min(0.9, 0.5 + s.impressions / 200.0), 2),
                reason=(f"geo '{cc}' eCPM ${s.ecpm:.2f} "
                        f"({s.ecpm / blended_ecpm:.1f}x blend) with only "
                        f"{share:.1%} revenue share — surface as UA target, "
                        f"hand to Growth OS (not a monetization action)"),
                metrics={"ecpm": round(s.ecpm, 2), "impressions": s.impressions,
                         "revenue": round(s.revenue, 2),
                         "revenue_share": round(share, 4),
                         "note": "UA execution is Growth OS scope — informational only"},
            ))
        return signals
