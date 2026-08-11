"""
E15.2.5 — OpportunityScorer.

Opportunity answers: *how much recoverable value is on the table through
in-app monetization ops?* This is the score that stops a low health
number from reading as "hopeless" — a messy account is often a HIGH
opportunity account.

Scope guard: opportunity here is strictly in-app monetization headroom
(waterfall cleanup, bid floors, surfacing high-eCPM demand). It does NOT
include user acquisition / geo scaling — that is Growth OS territory and
must never inflate this score.

Three weighted dimensions (0-100):
    1. Value Recapture   (0.40) — $ recoverable vs current revenue
    2. Structural Headroom (0.35) — how much waterfall/network waste is fixable
    3. Demand Upside     (0.25) — strength of hidden high-eCPM demand levers
"""
from __future__ import annotations

from typing import Dict, List

from operation.optimizer.intel_models import IntelSignal, SegmentStat
from operation.optimizer.scoring.score_models import Dimension, ScoreResult
from operation.optimizer.scoring.health_score import _clamp, _lin, _PARASITE_RATIO


class OpportunityScorer:
    WEIGHTS = {
        "value_recapture": 0.40,
        "structural_headroom": 0.35,
        "demand_upside": 0.25,
    }
    # map recoverable % of revenue -> 0-100 (40% uplift potential == max)
    _RECAPTURE_FULL = 0.40
    _DEPTH_BEST, _DEPTH_WORST = 10.0, 50.0

    def score(self, total: SegmentStat,
              by_network: Dict[str, SegmentStat],
              blended_ecpm: float,
              signals: List[IntelSignal]) -> ScoreResult:
        dims: List[Dimension] = []
        revenue = max(total.revenue, 1e-9)

        # 1. Value recapture ------------------------------------------------
        # (a) parasite backfill: value if those impressions cleared at blend
        parasite_recapture = 0.0
        for s in by_network.values():
            if blended_ecpm > 0 and s.ecpm < blended_ecpm * _PARASITE_RATIO:
                parasite_recapture += s.impressions / 1000.0 * (blended_ecpm - s.ecpm)
        # (b) hidden winners: value of roughly doubling their won impressions
        winner_uplift = 0.0
        for s in signals:
            if s.rule == "hidden_winner":
                winner_uplift += (s.metrics.get("impressions", 0) / 1000.0
                                  * s.metrics.get("ecpm", 0.0))
        recoverable = parasite_recapture + winner_uplift
        recapture_pct = recoverable / revenue
        vr = _lin(recapture_pct, self._RECAPTURE_FULL, 0.0)
        dims.append(Dimension(
            "value_recapture", vr, self.WEIGHTS["value_recapture"],
            f"~${recoverable:.0f} recoverable ({recapture_pct:.0%} of ${revenue:.0f})"))

        # 2. Structural headroom -------------------------------------------
        zombie_att = sum(int(s.metrics.get("attempts", 0)) for s in signals
                         if s.rule == "zombie_network")
        zshare = (zombie_att / total.attempts) if total.attempts else 0.0
        depth = total.attempts / max(total.impressions, 1)
        # more waste = more fixable headroom (inverse of efficiency)
        zombie_head = _clamp(zshare / 0.30 * 100.0)             # 30% zombie == max
        depth_head = 100.0 - _lin(depth, self._DEPTH_BEST, self._DEPTH_WORST)
        sh = (zombie_head + depth_head) / 2.0
        dims.append(Dimension(
            "structural_headroom", sh, self.WEIGHTS["structural_headroom"],
            f"{zshare:.0%} zombie requests, depth {depth:.1f} — cleanup headroom"))

        # 3. Demand upside --------------------------------------------------
        levers = [s for s in signals if s.rule in ("hidden_winner", "bid_floor")]
        strength = sum(s.confidence for s in levers)
        du = _clamp(strength / 2.5 * 100.0)   # ~2.5 confidence-weighted levers == max
        best = max((s.metrics.get("ecpm", 0.0) for s in signals
                    if s.rule == "hidden_winner"), default=0.0)
        du_detail = (f"{len(levers)} actionable demand levers"
                     + (f", best hidden eCPM ${best:.0f}" if best else ""))
        dims.append(Dimension(
            "demand_upside", du, self.WEIGHTS["demand_upside"], du_detail))

        raw = ScoreResult.weighted(dims)
        val = int(round(raw))
        grade = "HIGH" if val >= 66 else "MEDIUM" if val >= 40 else "LOW"
        headline = (f"Opportunity {val}/100 ({grade}) — "
                    f"~${recoverable:.0f} in-app upside identified")
        return ScoreResult(
            kind="opportunity", score=val, grade=grade, headline=headline,
            dimensions=dims,
            metrics={"recoverable_usd": round(recoverable, 2),
                     "recapture_pct": round(recapture_pct, 4),
                     "parasite_recapture_usd": round(parasite_recapture, 2),
                     "hidden_winner_uplift_usd": round(winner_uplift, 2)},
        )
