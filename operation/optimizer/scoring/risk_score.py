"""
E15.2.5 — RiskScorer.

Risk answers: *how fragile is this revenue?* It isolates single-points-of-
failure so a concentrated account is not silently rewarded for looking
"efficient". High risk does NOT mean act — for country concentration the
right response is *monitor / hand to UA*, never in-app "diversify".

Three weighted dimensions (0-100, higher = riskier):
    1. App Concentration     (0.45) — revenue on a single app
    2. Network Concentration (0.35) — revenue on a single ad network
    3. Geo Concentration     (0.20) — revenue on a single country
                                       (informational — UA/Growth scope)
"""
from __future__ import annotations

from typing import Dict, List

from operation.optimizer.intel_models import SegmentStat
from operation.optimizer.scoring.score_models import Dimension, ScoreResult


def _top_share(stats: Dict[str, SegmentStat]) -> float:
    total = sum(s.revenue for s in stats.values())
    if total <= 0:
        return 0.0
    return max((s.revenue for s in stats.values()), default=0.0) / total


class RiskScorer:
    WEIGHTS = {
        "app_concentration": 0.45,
        "network_concentration": 0.35,
        "geo_concentration": 0.20,
    }

    def score(self, by_app: Dict[str, SegmentStat],
              by_network: Dict[str, SegmentStat],
              by_country: Dict[str, SegmentStat]) -> ScoreResult:
        app_s = _top_share(by_app)
        net_s = _top_share(by_network)
        geo_s = _top_share(by_country)

        # concentration share maps directly to a 0-100 risk contribution;
        # below 50% share carries little single-point-of-failure risk.
        def risk_of(share: float) -> float:
            return max(0.0, min(100.0, (share - 0.5) / 0.5 * 100.0))

        dims = [
            Dimension("app_concentration", risk_of(app_s),
                      self.WEIGHTS["app_concentration"],
                      f"top app = {app_s:.0%} of revenue"),
            Dimension("network_concentration", risk_of(net_s),
                      self.WEIGHTS["network_concentration"],
                      f"top network = {net_s:.0%} of revenue"),
            Dimension("geo_concentration", risk_of(geo_s),
                      self.WEIGHTS["geo_concentration"],
                      f"top country = {geo_s:.0%} of revenue (UA scope)"),
        ]

        raw = ScoreResult.weighted(dims)
        val = int(round(raw))
        grade = "HIGH" if val >= 66 else "MEDIUM" if val >= 33 else "LOW"
        headline = (f"Risk {val}/100 ({grade}) — "
                    f"app {app_s:.0%} / net {net_s:.0%} / geo {geo_s:.0%} concentration")
        return ScoreResult(
            kind="risk", score=val, grade=grade, headline=headline,
            dimensions=dims,
            metrics={"top_app_share": round(app_s, 4),
                     "top_network_share": round(net_s, 4),
                     "top_country_share": round(geo_s, 4)},
        )
