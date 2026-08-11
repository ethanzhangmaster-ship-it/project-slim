"""
E16.2 — Price Strategy Agent: *at what price should we sell?*

Two capabilities:

1. ``simulate_price_change`` — constant-elasticity price simulation.
   With elasticity e = 1.5 (casual IAP demand is elastic):
       purchase_ratio = (new/old) ** (-e)
       revenue_ratio  = (new/old) ** (1 - e)
   Spec example: $9.99 -> $7.99 gives purchases ~ +40% (>= +35%) and
   revenue ~ +12%.

2. ``diagnose`` — lineup-relative price diagnostics:
   * priced above lineup median with conversion far below lineup mean
     -> PRICE_TOO_HIGH
   * priced below median with conversion far above mean (money left on
     the table) -> PRICE_TOO_LOW
"""
from __future__ import annotations

from statistics import median
from typing import List

from .models import (
    EconomyInsight,
    EconomyInsightType,
    ProductOffer,
    RevenueImpactPrediction,
)

PRICE_ELASTICITY = 1.5  # demand elasticity for casual IAP
HIGH_PRICE_CONVERSION_RATIO = 0.5  # conv < 50% of lineup mean = suspicious
LOW_PRICE_CONVERSION_RATIO = 2.0  # conv > 200% of lineup mean = underpriced


class PriceStrategyAgent:
    """Simulates price changes and diagnoses mispriced offers."""

    def __init__(self, elasticity: float = PRICE_ELASTICITY):
        self.elasticity = elasticity

    # ------------------------------------------------------------------ #
    def simulate_price_change(
        self,
        offer_id: str,
        old_price: float,
        new_price: float,
        *,
        confidence: float = 0.75,
    ) -> RevenueImpactPrediction:
        if old_price <= 0 or new_price <= 0:
            return RevenueImpactPrediction(
                offer_id=offer_id,
                old_price=old_price,
                new_price=new_price,
                price_change_pct=0.0,
                predicted_purchase_rate_change_pct=0.0,
                predicted_revenue_change_pct=0.0,
                confidence=0.0,
                note="invalid price input",
            )
        ratio = new_price / old_price
        purchase_ratio = ratio ** (-self.elasticity)
        revenue_ratio = ratio ** (1.0 - self.elasticity)
        price_change_pct = (ratio - 1.0) * 100.0
        purchase_change_pct = (purchase_ratio - 1.0) * 100.0
        revenue_change_pct = (revenue_ratio - 1.0) * 100.0
        direction = "cut" if new_price < old_price else "raise"
        return RevenueImpactPrediction(
            offer_id=offer_id,
            old_price=old_price,
            new_price=new_price,
            price_change_pct=price_change_pct,
            predicted_purchase_rate_change_pct=purchase_change_pct,
            predicted_revenue_change_pct=revenue_change_pct,
            confidence=confidence,
            note=(
                f"constant-elasticity model (e={self.elasticity}): price "
                f"{direction} {abs(price_change_pct):.1f}% -> purchases "
                f"{purchase_change_pct:+.1f}%, revenue "
                f"{revenue_change_pct:+.1f}%"
            ),
        )

    # ------------------------------------------------------------------ #
    def diagnose(
        self, game_id: str, offers: List[ProductOffer]
    ) -> List[EconomyInsight]:
        priced = [o for o in offers if o.price > 0 and o.impressions > 0]
        if len(priced) < 2:
            return []
        med_price = median(o.price for o in priced)
        mean_conv = sum(o.conversion_rate for o in priced) / len(priced)
        if mean_conv <= 0:
            return []

        insights: List[EconomyInsight] = []
        for o in priced:
            conv_ratio = o.conversion_rate / mean_conv
            if (
                o.price > med_price
                and conv_ratio < HIGH_PRICE_CONVERSION_RATIO
            ):
                sim = self.simulate_price_change(
                    o.offer_id, o.price, round(o.price * 0.8, 2)
                )
                insights.append(
                    EconomyInsight(
                        game_id=game_id,
                        insight_type=EconomyInsightType.PRICE_TOO_HIGH,
                        description=(
                            f"'{o.name}' at ${o.price:.2f} converts "
                            f"{o.conversion_rate:.2%} — under half the lineup "
                            f"average; a ~20% price cut projects revenue "
                            f"{sim.predicted_revenue_change_pct:+.1f}%."
                        ),
                        evidence={
                            "offer_id": o.offer_id,
                            "price": o.price,
                            "lineup_median_price": med_price,
                            "conversion_rate": o.conversion_rate,
                            "lineup_mean_conversion": round(mean_conv, 4),
                            "simulation": sim.to_dict(),
                        },
                        confidence=0.78,
                        impact_score=55.0,
                    )
                )
            elif (
                o.price < med_price
                and conv_ratio > LOW_PRICE_CONVERSION_RATIO
            ):
                sim = self.simulate_price_change(
                    o.offer_id, o.price, round(o.price * 1.2, 2)
                )
                insights.append(
                    EconomyInsight(
                        game_id=game_id,
                        insight_type=EconomyInsightType.PRICE_TOO_LOW,
                        description=(
                            f"'{o.name}' at ${o.price:.2f} converts "
                            f"{o.conversion_rate:.2%} — over twice the lineup "
                            "average; value may be underpriced."
                        ),
                        evidence={
                            "offer_id": o.offer_id,
                            "price": o.price,
                            "lineup_median_price": med_price,
                            "conversion_rate": o.conversion_rate,
                            "lineup_mean_conversion": round(mean_conv, 4),
                            "simulation": sim.to_dict(),
                        },
                        confidence=0.7,
                        impact_score=40.0,
                    )
                )
        return insights


__all__ = ["PriceStrategyAgent", "PRICE_ELASTICITY"]
