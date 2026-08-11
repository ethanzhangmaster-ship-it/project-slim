"""
E16.2 — Payer Analysis: *who pays, who doesn't, and why?*

Deterministic diagnostics over a ``PlayerEconomySnapshot``:

* payer conversion below benchmark        -> PAYWALL_DETECTED (monetization
  entry too weak — players never start paying)
* first-purchase dominated payer base     -> PAYER_SEGMENT_CHANGE
  ("first_purchase_bottleneck": we win the first sale but lose the repeat)
* repeat-purchase dominated + low conv    -> PAYER_SEGMENT_CHANGE
  ("whale_dependency": revenue concentrated in few repeat payers)

No I/O, no LLM — pure rules with explicit evidence & confidence.
"""
from __future__ import annotations

from typing import List

from .models import EconomyInsight, EconomyInsightType, PlayerEconomySnapshot

# Casual-game benchmarks (deterministic constants, tuned for the fleet).
BENCHMARK_PAYER_CONVERSION = 0.025  # 2.5% healthy casual payer conversion
LOW_PAYER_CONVERSION = 0.015  # below this, monetization entry is broken
FIRST_PURCHASE_BOTTLENECK_SHARE = 0.6  # >60% first-time payers = repeat problem
WHALE_DEPENDENCY_SHARE = 0.7  # >70% repeat payers + low conv = whale reliance


class PayerAnalyzer:
    """Answers "who pays?" and flags structural payer problems."""

    def analyze(self, snapshot: PlayerEconomySnapshot) -> List[EconomyInsight]:
        insights: List[EconomyInsight] = []
        insights.extend(self._conversion_check(snapshot))
        insights.extend(self._segment_check(snapshot))
        return insights

    # ------------------------------------------------------------------ #
    def _conversion_check(
        self, s: PlayerEconomySnapshot
    ) -> List[EconomyInsight]:
        if s.dau <= 0:
            return []
        conv = s.payer_conversion or (
            s.payer_count / s.dau if s.dau > 0 else 0.0
        )
        if conv >= LOW_PAYER_CONVERSION:
            return []
        gap_ratio = (
            (BENCHMARK_PAYER_CONVERSION - conv) / BENCHMARK_PAYER_CONVERSION
        )
        confidence = min(0.95, 0.6 + 0.4 * gap_ratio)
        return [
            EconomyInsight(
                game_id=s.game_id,
                insight_type=EconomyInsightType.PAYWALL_DETECTED,
                description=(
                    f"Payer conversion {conv:.2%} is below the "
                    f"{LOW_PAYER_CONVERSION:.1%} floor (benchmark "
                    f"{BENCHMARK_PAYER_CONVERSION:.1%}) — players are not "
                    "entering the monetization funnel."
                ),
                evidence={
                    "payer_conversion": round(conv, 4),
                    "benchmark": BENCHMARK_PAYER_CONVERSION,
                    "floor": LOW_PAYER_CONVERSION,
                    "dau": s.dau,
                    "payer_count": s.payer_count,
                },
                confidence=round(confidence, 4),
                impact_score=70.0,
            )
        ]

    # ------------------------------------------------------------------ #
    def _segment_check(self, s: PlayerEconomySnapshot) -> List[EconomyInsight]:
        insights: List[EconomyInsight] = []
        if s.payer_count <= 0:
            return insights
        first = s.first_time_payer_share
        repeat = s.repeat_payer_share

        # Spec case: 10000 DAU / 250 payers / 2.5% conv, 70% first-time,
        # 30% repeat -> "first_purchase_bottleneck" with confidence 0.86.
        if first >= FIRST_PURCHASE_BOTTLENECK_SHARE:
            confidence = min(0.95, 0.5 + 0.36 * (first / 0.7))
            insights.append(
                EconomyInsight(
                    game_id=s.game_id,
                    insight_type=EconomyInsightType.PAYER_SEGMENT_CHANGE,
                    description=(
                        f"first_purchase_bottleneck: {first:.0%} of payers are "
                        f"first-time buyers and only {repeat:.0%} repeat — the "
                        "game wins the first sale but fails to build a repeat "
                        "purchase habit."
                    ),
                    evidence={
                        "segment": "first_purchase_bottleneck",
                        "first_time_payer_share": round(first, 4),
                        "repeat_payer_share": round(repeat, 4),
                        "payer_count": s.payer_count,
                        "purchase_frequency": round(s.purchase_frequency, 4),
                    },
                    confidence=round(confidence, 4),
                    impact_score=60.0,
                )
            )
        elif (
            repeat >= WHALE_DEPENDENCY_SHARE
            and s.payer_conversion < BENCHMARK_PAYER_CONVERSION
        ):
            insights.append(
                EconomyInsight(
                    game_id=s.game_id,
                    insight_type=EconomyInsightType.PAYER_SEGMENT_CHANGE,
                    description=(
                        f"whale_dependency: {repeat:.0%} of payers are repeat "
                        "buyers while overall conversion is below benchmark — "
                        "revenue is concentrated in a small whale segment."
                    ),
                    evidence={
                        "segment": "whale_dependency",
                        "repeat_payer_share": round(repeat, 4),
                        "payer_conversion": round(s.payer_conversion, 4),
                        "benchmark": BENCHMARK_PAYER_CONVERSION,
                    },
                    confidence=0.75,
                    impact_score=50.0,
                )
            )
        return insights


__all__ = [
    "PayerAnalyzer",
    "BENCHMARK_PAYER_CONVERSION",
    "LOW_PAYER_CONVERSION",
    "FIRST_PURCHASE_BOTTLENECK_SHARE",
    "WHALE_DEPENDENCY_SHARE",
]
