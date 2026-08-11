"""
E15.2.5 Rule 2 — HiddenWinnerDetector (UnderUtilizedNetworkDetector).

A network with eCPM far above the account blend but tiny impression share
is winning too few auctions — raise its bid opportunity instead of
mislabeling it "low revenue". Grounded in ACCT_2: MINTEGRAL eCPM $82
with only 208 impressions (1.3% show-rate).
"""
from __future__ import annotations

from typing import Dict, List

from operation.optimizer.intel_models import IntelSignal, SegmentStat


class HiddenWinnerDetector:
    # Calibrated against real ACCT_2 ground truth: MINTEGRAL eCPM $82.28
    # vs blend $57.21 = 1.44x — the flagship hidden winner. A 1.5x cutoff
    # would miss it, so the production threshold is 1.3x.
    ECPM_MULTIPLIER = 1.3          # eCPM > blended * 1.3
    MAX_IMPRESSION_SHARE = 0.05    # <5% of account impressions
    MIN_IMPRESSIONS = 20           # avoid single-lucky-impression noise
    MIN_ATTEMPTS = 1_000           # network must actually be asked

    def analyze(self, by_network: Dict[str, SegmentStat],
                blended_ecpm: float,
                total_impressions: int) -> List[IntelSignal]:
        signals: List[IntelSignal] = []
        if blended_ecpm <= 0 or total_impressions <= 0:
            return signals
        total_revenue = sum(s.revenue for s in by_network.values())
        ecpm_sum = sum(s.ecpm for s in by_network.values())
        for net, s in by_network.items():
            share = s.impressions / total_impressions
            if not (s.ecpm > blended_ecpm * self.ECPM_MULTIPLIER
                    and share < self.MAX_IMPRESSION_SHARE
                    and s.impressions >= self.MIN_IMPRESSIONS
                    and s.attempts >= self.MIN_ATTEMPTS):
                continue

            # Revenue Capture Rate (user calibration): how much of the
            # revenue this network *should* be earning given its eCPM
            # quality is it actually capturing? capture = revenue share /
            # eCPM-potential share. << 1 means a high-quality network is
            # being starved of volume — the core hidden-winner signal.
            rev_share = (s.revenue / total_revenue) if total_revenue > 0 else 0.0
            ecpm_share = (s.ecpm / ecpm_sum) if ecpm_sum > 0 else 0.0
            capture_rate = (rev_share / ecpm_share) if ecpm_share > 0 else 0.0

            # confidence scales with how much data supports the eCPM
            confidence = min(0.95, 0.6 + s.impressions / 1000.0)
            signals.append(IntelSignal(
                rule="hidden_winner",
                severity="warning",
                action="increase_bid_opportunity",
                target=net,
                confidence=round(confidence, 2),
                reason=(f"eCPM ${s.ecpm:.2f} is {s.ecpm / blended_ecpm:.1f}x account blend "
                        f"(${blended_ecpm:.2f}) but impression share only {share:.1%} "
                        f"— capturing {capture_rate:.0%} of its eCPM-implied revenue potential"),
                metrics={
                    "ecpm": round(s.ecpm, 2),
                    "blended_ecpm": round(blended_ecpm, 2),
                    "impressions": s.impressions,
                    "impression_share": round(share, 4),
                    "attempts": s.attempts,
                    "revenue_share": round(rev_share, 4),
                    "ecpm_potential_share": round(ecpm_share, 4),
                    "revenue_capture_rate": round(capture_rate, 3),
                    "issue": "high_value_low_volume",
                },
            ))
        signals.sort(key=lambda x: -x.metrics["ecpm"])
        return signals
