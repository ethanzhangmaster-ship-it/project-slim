"""
E15.2.5 — HealthScorer.

Health answers ONE question: *is this account monetizing efficiently
right now?* It measures current-state efficiency and fragility only.
It deliberately does NOT include upside/opportunity — that lives in
OpportunityScorer, so a high-headroom account is not mislabeled "broken".

Five weighted dimensions (0-100 each):
    1. eCPM Efficiency   (0.25) — value dilution from parasite backfill
    2. Demand Quality    (0.15) — fill rate (responses/attempts); skipped
                                   if the report has no responses column
    3. Waterfall Efficiency (0.20) — attempts-per-impression depth
    4. Network Health    (0.25) — share of requests wasted on zombie nets
    5. Revenue Stability (0.15) — concentration on a single app

Deterministic; grounded on real ACCT_2 numbers.
"""
from __future__ import annotations

from typing import Dict, List

from operation.optimizer.intel_models import IntelSignal, SegmentStat
from operation.optimizer.scoring.score_models import Dimension, ScoreResult

# parasite backfill: eCPM below this fraction of blend dilutes value
_PARASITE_RATIO = 0.15
# waterfall depth (attempts/impression) mapping
_DEPTH_BEST, _DEPTH_WORST = 10.0, 50.0
# revenue-stability mapping on top-app share
_STABLE_SHARE, _FRAGILE_SHARE = 0.50, 1.00


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _lin(x: float, x_good: float, x_bad: float) -> float:
    """Map x to 0-100: x_good -> 100, x_bad -> 0 (monotonic either way)."""
    if x_good == x_bad:
        return 100.0
    t = (x - x_bad) / (x_good - x_bad)
    return _clamp(t * 100.0)


class HealthScorer:
    WEIGHTS = {
        "ecpm_efficiency": 0.25,
        "demand_quality": 0.15,
        "waterfall_efficiency": 0.20,
        "network_health": 0.25,
        "revenue_stability": 0.15,
    }

    def score(self, total: SegmentStat,
              by_network: Dict[str, SegmentStat],
              by_app: Dict[str, SegmentStat],
              blended_ecpm: float,
              signals: List[IntelSignal]) -> ScoreResult:
        dims: List[Dimension] = []

        # 1. eCPM efficiency — impressions NOT diluted by parasite backfill
        parasite_imp = sum(
            s.impressions for s in by_network.values()
            if blended_ecpm > 0 and s.ecpm < blended_ecpm * _PARASITE_RATIO)
        dilution = (parasite_imp / total.impressions) if total.impressions else 0.0
        eff = _clamp(100.0 * (1.0 - dilution))
        dims.append(Dimension(
            "ecpm_efficiency", eff, self.WEIGHTS["ecpm_efficiency"],
            f"{dilution:.0%} of impressions from parasite backfill (eCPM < 15% blend)"))

        # 2. demand quality — fill rate (responses/attempts). Skip if absent.
        if total.responses > 0 and total.attempts > 0:
            fill = total.responses / total.attempts
            dq = _lin(fill, 0.50, 0.02)
            dims.append(Dimension(
                "demand_quality", dq, self.WEIGHTS["demand_quality"],
                f"fill rate {fill:.1%} (responses/attempts)"))

        # 3. waterfall efficiency — depth (attempts/impression)
        depth = total.attempts / max(total.impressions, 1)
        we = _lin(depth, _DEPTH_BEST, _DEPTH_WORST)
        dims.append(Dimension(
            "waterfall_efficiency", we, self.WEIGHTS["waterfall_efficiency"],
            f"depth {depth:.1f} attempts/impression"))

        # 4. network health — requests wasted on zombie networks
        zombie_att = sum(int(s.metrics.get("attempts", 0)) for s in signals
                         if s.rule == "zombie_network")
        zshare = (zombie_att / total.attempts) if total.attempts else 0.0
        nh = _clamp(100.0 * (1.0 - zshare))
        dims.append(Dimension(
            "network_health", nh, self.WEIGHTS["network_health"],
            f"{zshare:.0%} of requests on zombie networks ({zombie_att:,} att)"))

        # 5. revenue stability — top-app concentration
        app_total = sum(s.revenue for s in by_app.values()) or 0.0
        top_share = (max((s.revenue for s in by_app.values()), default=0.0)
                     / app_total) if app_total else 0.0
        rs = _lin(top_share, _STABLE_SHARE, _FRAGILE_SHARE)
        dims.append(Dimension(
            "revenue_stability", rs, self.WEIGHTS["revenue_stability"],
            f"top app = {top_share:.0%} of revenue"))

        raw = ScoreResult.weighted(dims)
        val = int(round(raw))
        grade = "A" if val >= 90 else "B" if val >= 75 else \
                "C" if val >= 60 else "D"
        headline = (f"Health {val}/100 ({grade}) — current monetization efficiency; "
                    f"low health reflects state, not lost cause")
        return ScoreResult(
            kind="health", score=val, grade=grade, headline=headline,
            dimensions=dims,
            metrics={"dilution": round(dilution, 4),
                     "waterfall_depth": round(depth, 1),
                     "zombie_request_share": round(zshare, 4),
                     "top_app_share": round(top_share, 4)},
        )
