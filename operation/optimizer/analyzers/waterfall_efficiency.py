"""
E15.2.5 Rule 3 — WaterfallEfficiencyAnalyzer.

Waste = failed requests / total requests. Bidding traffic inflates raw
attempt counts, so absolute waste is informational; the real value is
COMPARATIVE waste across segments (network / format / country) and the
account-level depth (attempts per impression) trend.
ACCT_2 baseline: 140,411 att / 4,988 imp -> 96.4% waste, depth 28.
"""
from __future__ import annotations

from typing import Dict, List

from operation.optimizer.intel_models import IntelSignal, SegmentStat


class WaterfallEfficiencyAnalyzer:
    DEPTH_WARNING = 25.0       # attempts per impression
    DEPTH_CRITICAL = 40.0
    SEGMENT_MIN_ATTEMPTS = 2_000
    SEGMENT_WASTE_FLAG = 0.995   # segment waste above this -> flag

    @staticmethod
    def waste_score(s: SegmentStat) -> float:
        if s.attempts <= 0:
            return 0.0
        return 1.0 - (s.impressions / s.attempts)

    def analyze(self, total: SegmentStat,
                segments: Dict[str, Dict[str, SegmentStat]]) -> List[IntelSignal]:
        """segments: {"network": {...}, "ad_format": {...}, "country": {...}}"""
        signals: List[IntelSignal] = []

        depth = total.attempts / max(total.impressions, 1)
        waste = self.waste_score(total)
        if depth >= self.DEPTH_WARNING:
            severity = "critical" if depth >= self.DEPTH_CRITICAL else "warning"
            signals.append(IntelSignal(
                rule="waterfall_waste",
                severity=severity,
                action="reduce_waterfall_depth",
                target="ACCOUNT",
                confidence=0.9,
                reason=(f"Waterfall depth {depth:.1f} attempts/impression "
                        f"(waste {waste:.1%}) — trim non-producing networks"),
                metrics={"depth": round(depth, 1), "waste": round(waste, 4),
                         "attempts": total.attempts, "impressions": total.impressions},
            ))

        # comparative waste per segment dimension
        for dim, stats in segments.items():
            for key, s in stats.items():
                if s.attempts < self.SEGMENT_MIN_ATTEMPTS:
                    continue
                w = self.waste_score(s)
                if w >= self.SEGMENT_WASTE_FLAG and s.revenue < 1.0:
                    signals.append(IntelSignal(
                        rule="waterfall_waste",
                        severity="warning",
                        action="review_segment",
                        target=f"{dim}:{key}",
                        confidence=0.8,
                        reason=(f"{dim} '{key}' waste {w:.2%} "
                                f"({s.attempts:,} att, {s.impressions} imp, ${s.revenue:.2f})"),
                        metrics={"dimension": dim, "waste": round(w, 4),
                                 "attempts": s.attempts, "impressions": s.impressions,
                                 "revenue": round(s.revenue, 2)},
                    ))
        return signals
