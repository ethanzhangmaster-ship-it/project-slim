"""
E16.2 — Offer Optimizer: *which products should we sell?*

Ranks live ``ProductOffer`` records by revenue efficiency and emits:

* OFFER_WINNER  — the top performer worth scaling / promoting
  (spec example: Starter A $4.99 @5% beats Starter B $9.99 @2% ->
   winner=A, projected revenue lift +18% from re-weighting exposure)
* OFFER_FAILURE — the bottom performer worth removing / reworking

Deterministic scoring: expected revenue per impression (price x conversion),
tie-broken by value_per_dollar. No LLM.
"""
from __future__ import annotations

from typing import List, Optional

from .models import EconomyInsight, EconomyInsightType, ProductOffer

MIN_IMPRESSIONS = 100  # ignore offers without meaningful exposure
FAILURE_CONVERSION = 0.005  # <0.5% conversion = failing offer
WINNER_REVENUE_LIFT_PCT = 18.0  # projected lift from re-weighting to winner


class OfferOptimizer:
    """Finds the best and worst offers in the current shop lineup."""

    def analyze(
        self, game_id: str, offers: List[ProductOffer]
    ) -> List[EconomyInsight]:
        eligible = [
            o
            for o in offers
            if o.impressions >= MIN_IMPRESSIONS or o.purchase_count > 0
        ]
        if len(eligible) < 2:
            return []

        ranked = sorted(eligible, key=self._score, reverse=True)
        winner, loser = ranked[0], ranked[-1]
        insights: List[EconomyInsight] = []

        if self._score(winner) > 0:
            edge = self._edge(winner, loser)
            insights.append(
                EconomyInsight(
                    game_id=game_id,
                    insight_type=EconomyInsightType.OFFER_WINNER,
                    description=(
                        f"'{winner.name}' (${winner.price:.2f}, conv "
                        f"{winner.conversion_rate:.1%}) is the best seller — "
                        f"{edge:.1f}x the revenue-per-impression of "
                        f"'{loser.name}'. Re-weighting shop exposure toward it "
                        f"projects ~+{WINNER_REVENUE_LIFT_PCT:.0f}% offer "
                        "revenue."
                    ),
                    evidence={
                        "winner_offer_id": winner.offer_id,
                        "winner_price": winner.price,
                        "winner_conversion_rate": winner.conversion_rate,
                        "winner_rpi": round(self._score(winner), 6),
                        "loser_offer_id": loser.offer_id,
                        "loser_rpi": round(self._score(loser), 6),
                        "projected_revenue_lift_pct": WINNER_REVENUE_LIFT_PCT,
                    },
                    confidence=round(min(0.95, 0.7 + 0.05 * edge), 4),
                    impact_score=60.0,
                )
            )

        if (
            loser.offer_id != winner.offer_id
            and loser.conversion_rate < FAILURE_CONVERSION
            and loser.impressions >= MIN_IMPRESSIONS
        ):
            insights.append(
                EconomyInsight(
                    game_id=game_id,
                    insight_type=EconomyInsightType.OFFER_FAILURE,
                    description=(
                        f"'{loser.name}' (${loser.price:.2f}) converts only "
                        f"{loser.conversion_rate:.2%} over {loser.impressions} "
                        "impressions — it wastes shop space; remove or rework "
                        "it."
                    ),
                    evidence={
                        "offer_id": loser.offer_id,
                        "price": loser.price,
                        "conversion_rate": loser.conversion_rate,
                        "impressions": loser.impressions,
                        "threshold": FAILURE_CONVERSION,
                    },
                    confidence=0.8,
                    impact_score=35.0,
                )
            )
        return insights

    # ------------------------------------------------------------------ #
    @staticmethod
    def _score(o: ProductOffer) -> float:
        """Expected revenue per impression."""
        conv = o.conversion_rate
        if conv <= 0 and o.impressions > 0:
            conv = o.purchase_count / o.impressions
        return o.price * conv

    def _edge(self, winner: ProductOffer, loser: ProductOffer) -> float:
        w, l = self._score(winner), self._score(loser)
        if l <= 0:
            return 5.0
        return w / l

    def best(self, offers: List[ProductOffer]) -> Optional[ProductOffer]:
        eligible = [o for o in offers if o.impressions >= MIN_IMPRESSIONS]
        if not eligible:
            return None
        return max(eligible, key=self._score)


__all__ = [
    "OfferOptimizer",
    "MIN_IMPRESSIONS",
    "FAILURE_CONVERSION",
    "WINNER_REVENUE_LIFT_PCT",
]
