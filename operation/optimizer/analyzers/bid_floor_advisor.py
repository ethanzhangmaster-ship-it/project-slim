"""
E15.2.5 Rule 4 — BidFloorAdvisor (recommendation-only).

MAX Management API cannot read floors on expanded-targeting waterfalls,
so Phase 1 works WITHOUT the current floor: it recommends a minimum
bid constraint for "parasite" backfill networks whose eCPM is far below
the account blend while consuming a large impression share.
ACCT_2 grounding: APPLOVIN_EXCHANGE eCPM $1.41 vs blend $57, 694 imps.

CALIBRATION (user): "set_bid_floor" is too blunt. Bidding networks are
NOT traditional waterfall instances — the correct lever differs:
  * waterfall instance  -> raise the instance CPM floor (per-instance)
  * bidding / exchange   -> raise the unified-auction PRICE FLOOR
                            (auction-level bid filtering), not a waterfall row
So the action is now `adjust_bid_constraint`, the constraint_type is
classified per network, and a floor RANGE (low..high) is given rather
than a single number. Output is always a recommendation
({"type": "recommendation", "requires_manual_apply": true}).
"""
from __future__ import annotations

from typing import Dict, List

from operation.optimizer.intel_models import IntelSignal, SegmentStat

# networks served through MAX unified-auction bidding rather than a
# traditional waterfall instance (price-floor lever differs).
_BIDDING_MARKERS = ("_BIDDING", "_EXCHANGE", "BIDMACHINE")


def classify_constraint(network: str) -> str:
    up = network.upper()
    if any(m in up for m in _BIDDING_MARKERS):
        return "unified_auction_price_floor"
    return "waterfall_instance_floor"


class BidFloorAdvisor:
    ECPM_PARASITE_RATIO = 0.15     # eCPM < 15% of blend
    MIN_IMPRESSION_SHARE = 0.03    # taking >=3% of impressions
    MIN_IMPRESSIONS = 50
    FLOOR_FRACTION = 0.10          # midpoint floor ~= 10% of blended eCPM
    FLOOR_LOW_FRACTION = 0.08      # conservative bound
    FLOOR_HIGH_FRACTION = 0.15     # aggressive bound
    FLOOR_MIN, FLOOR_MAX = 1.0, 20.0

    def _clamp(self, x: float) -> float:
        return min(max(x, self.FLOOR_MIN), self.FLOOR_MAX)

    def analyze(self, by_network: Dict[str, SegmentStat],
                blended_ecpm: float,
                total_impressions: int) -> List[IntelSignal]:
        signals: List[IntelSignal] = []
        if blended_ecpm <= 0 or total_impressions <= 0:
            return signals
        for net, s in by_network.items():
            share = s.impressions / total_impressions
            if not (s.ecpm < blended_ecpm * self.ECPM_PARASITE_RATIO
                    and share >= self.MIN_IMPRESSION_SHARE
                    and s.impressions >= self.MIN_IMPRESSIONS):
                continue
            floor = self._clamp(blended_ecpm * self.FLOOR_FRACTION)
            floor_low = self._clamp(blended_ecpm * self.FLOOR_LOW_FRACTION)
            floor_high = self._clamp(blended_ecpm * self.FLOOR_HIGH_FRACTION)
            ctype = classify_constraint(net)
            lever = ("unified-auction price floor (bid filtering)"
                     if ctype == "unified_auction_price_floor"
                     else "waterfall instance CPM floor")
            signals.append(IntelSignal(
                rule="bid_floor",
                severity="warning",
                action="adjust_bid_constraint",
                target=net,
                confidence=0.85,
                reason=(f"eCPM ${s.ecpm:.2f} is only {s.ecpm / blended_ecpm:.0%} of blend "
                        f"(${blended_ecpm:.2f}) while taking {share:.1%} of impressions "
                        f"— raise its {lever} to filter low-value fill"),
                metrics={
                    "type": "recommendation",
                    "constraint_type": ctype,
                    "current_floor": "unknown (API cannot read expanded-targeting waterfalls)",
                    "recommended_min_floor": round(floor, 2),
                    "recommended_floor_range": [round(floor_low, 2), round(floor_high, 2)],
                    "ecpm": round(s.ecpm, 2),
                    "impression_share": round(share, 4),
                    "watch": "monitor overall fill rate after applying",
                },
            ))
        signals.sort(key=lambda x: x.metrics["ecpm"])
        return signals
