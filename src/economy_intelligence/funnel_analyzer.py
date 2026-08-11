"""
E16.2 — Funnel Analyzer: *where does the player -> payer journey break?*

Two data sources, two lenses:

1. ``PurchaseFunnel`` (Install -> L5 -> L10 -> first_shortage -> offer_shown
   -> purchase): find the stage with excessive drop. A level stage losing
   40%+ of players combined with a weak purchase tail = an economy paywall
   that is too strong -> recommend lowering resource consumption ~20%.

2. ``PlayerEconomySnapshot`` resource flow: shortage rate too high ->
   RESOURCE_SHORTAGE; currency piling up + weak purchasing ->
   RESOURCE_SURPLUS (nothing worth buying / faucet too generous).
"""
from __future__ import annotations

from typing import List, Optional

from .models import (
    EconomyInsight,
    EconomyInsightType,
    PlayerEconomySnapshot,
    PurchaseFunnel,
)

PAYWALL_DROP_THRESHOLD = 0.40  # a stage losing >=40% of players is a wall
WEAK_PURCHASE_TAIL = 0.02  # purchase stage converting <2% of its input
SHORTAGE_RATE_HIGH = 0.35  # >=35% of sessions hit "not enough resources"
SURPLUS_BALANCE_RATIO = 3.0  # balance >= 3x earn rate = hoarding
SURPLUS_LOW_FREQUENCY = 0.5  # purchases/payer/period below this = not buying


class FunnelAnalyzer:
    """Finds paywalls and resource-economy imbalances."""

    # ------------------------------------------------------------------ #
    def analyze_funnel(self, funnel: PurchaseFunnel) -> List[EconomyInsight]:
        insights: List[EconomyInsight] = []
        wall = self._find_paywall(funnel)
        if wall is not None:
            stage, drop = wall
            purchase_conv = self._purchase_tail(funnel)
            weak_tail = (
                purchase_conv is not None and purchase_conv < WEAK_PURCHASE_TAIL
            )
            confidence = 0.7 + (0.15 if weak_tail else 0.0) + min(
                0.1, (drop - PAYWALL_DROP_THRESHOLD)
            )
            insights.append(
                EconomyInsight(
                    game_id=funnel.game_id,
                    insight_type=EconomyInsightType.PAYWALL_DETECTED,
                    description=(
                        f"Stage '{stage}' loses {drop:.0%} of players"
                        + (
                            f" while purchase conversion is only "
                            f"{purchase_conv:.1%}"
                            if purchase_conv is not None
                            else ""
                        )
                        + " — the economy wall is too strong. Recommend "
                        "lowering resource consumption ~20% around this stage."
                    ),
                    evidence={
                        "stage": stage,
                        "drop_rate": round(drop, 4),
                        "purchase_conversion": purchase_conv,
                        "recommended_consumption_cut_pct": 20,
                    },
                    confidence=round(min(confidence, 0.95), 4),
                    impact_score=65.0,
                )
            )
        return insights

    # ------------------------------------------------------------------ #
    def analyze_resources(
        self, s: PlayerEconomySnapshot
    ) -> List[EconomyInsight]:
        insights: List[EconomyInsight] = []

        if s.resource_shortage_rate >= SHORTAGE_RATE_HIGH:
            insights.append(
                EconomyInsight(
                    game_id=s.game_id,
                    insight_type=EconomyInsightType.RESOURCE_SHORTAGE,
                    description=(
                        f"{s.resource_shortage_rate:.0%} of sessions hit a "
                        "resource shortage — friction is high; pair shortage "
                        "moments with a well-priced offer instead of a hard "
                        "wall."
                    ),
                    evidence={
                        "resource_shortage_rate": round(
                            s.resource_shortage_rate, 4
                        ),
                        "threshold": SHORTAGE_RATE_HIGH,
                        "currency_earn_rate": round(s.currency_earn_rate, 4),
                        "currency_spend_rate": round(s.currency_spend_rate, 4),
                    },
                    confidence=0.8,
                    impact_score=55.0,
                )
            )

        hoarding = (
            s.currency_earn_rate > 0
            and s.currency_balance_avg
            >= SURPLUS_BALANCE_RATIO * s.currency_earn_rate
        )
        not_buying = s.purchase_frequency < SURPLUS_LOW_FREQUENCY
        if hoarding and not_buying:
            insights.append(
                EconomyInsight(
                    game_id=s.game_id,
                    insight_type=EconomyInsightType.RESOURCE_SURPLUS,
                    description=(
                        f"Average currency balance "
                        f"{s.currency_balance_avg:.0f} is "
                        f">={SURPLUS_BALANCE_RATIO:.0f}x the per-period earn "
                        f"rate while purchase frequency is only "
                        f"{s.purchase_frequency:.2f} — players are hoarding: "
                        "either sinks are too weak or nothing is worth buying."
                    ),
                    evidence={
                        "currency_balance_avg": round(s.currency_balance_avg, 2),
                        "currency_earn_rate": round(s.currency_earn_rate, 2),
                        "purchase_frequency": round(s.purchase_frequency, 4),
                        "balance_to_earn_ratio": round(
                            s.currency_balance_avg / s.currency_earn_rate, 2
                        )
                        if s.currency_earn_rate > 0
                        else None,
                    },
                    confidence=0.82,
                    impact_score=50.0,
                )
            )
        return insights

    # ------------------------------------------------------------------ #
    @staticmethod
    def _find_paywall(funnel: PurchaseFunnel) -> Optional[tuple]:
        """Return (stage_name, drop_rate) of the worst level-progression wall."""
        worst: Optional[tuple] = None
        for stage in funnel.stages:
            if stage.drop_rate is None:
                continue
            # purchase / offer stages are expected to convert poorly; walls
            # live in the progression stages before monetization.
            if stage.name.lower() in ("purchase", "offer_shown"):
                continue
            if stage.drop_rate >= PAYWALL_DROP_THRESHOLD:
                if worst is None or stage.drop_rate > worst[1]:
                    worst = (stage.name, stage.drop_rate)
        return worst

    @staticmethod
    def _purchase_tail(funnel: PurchaseFunnel) -> Optional[float]:
        for stage in funnel.stages:
            if stage.name.lower() == "purchase":
                return stage.conversion_from_previous
        return None


__all__ = [
    "FunnelAnalyzer",
    "PAYWALL_DROP_THRESHOLD",
    "WEAK_PURCHASE_TAIL",
    "SHORTAGE_RATE_HIGH",
    "SURPLUS_BALANCE_RATIO",
    "SURPLUS_LOW_FREQUENCY",
]
