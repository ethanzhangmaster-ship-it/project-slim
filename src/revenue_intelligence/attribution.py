"""
E16.1 — Revenue Attribution Engine

Answers "why did revenue change?" by decomposing the revenue delta into five
named drivers, whose signed contribution shares always sum to ±100%:

    Revenue = DAU × ARPDAU   (first-order)
    ΔRevenue ≈ ΔDAU·ARPDAU_prev  +  DAU_cur·ΔARPDAU
             = [UA traffic + Product traffic]  +  Monetization
             + Seasonality  +  Noise(residual)

* UA traffic      — portion of the DAU change paid for by UA spend
* Product traffic — organic DAU change (retention / virality / store)
* Monetization    — change in revenue-per-user (ARPDAU)
* Seasonality     — small fixed baseline hypothesis
* Noise           — everything the first-order model does not explain

Deterministic, no I/O.
"""
from __future__ import annotations

from .models import (
    AttributionBreakdown,
    AttributionFactor,
    RevenueDelta,
    RevenueSnapshot,
)


def _arpdau(rev: float, dau: int) -> float:
    return rev / dau if dau and dau > 0 else 0.0


class RevenueAttributionEngine:
    """Decomposes a revenue change into UA / Product / Monetization / Seasonality / Noise."""

    # share of the unexplained residual attributed to seasonality
    SEASONALITY_SHARE = 0.3

    def analyze(
        self,
        current: RevenueSnapshot,
        previous: RevenueSnapshot,
        delta: RevenueDelta,
    ) -> AttributionBreakdown:
        rev_prev = previous.revenue_total
        rev_cur = current.revenue_total
        d_rev = rev_cur - rev_prev

        arpdau_prev = _arpdau(rev_prev, previous.dau)
        arpdau_cur = _arpdau(rev_cur, current.dau)
        d_dau = current.dau - previous.dau

        # first-order decomposition
        traffic_component = d_dau * arpdau_prev
        monetization_component = current.dau * (arpdau_cur - arpdau_prev)

        # split traffic into UA (paid) vs Product (organic)
        ua_share = self._ua_share(delta)
        ua_traffic = traffic_component * ua_share
        product_traffic = traffic_component * (1.0 - ua_share)

        # residual → seasonality + noise
        residual = d_rev - (traffic_component + monetization_component)
        seasonality = residual * self.SEASONALITY_SHARE
        noise = residual - seasonality

        factors = [
            self._factor(
                "ua",
                ua_traffic,
                d_rev,
                "Revenue change from UA-driven user acquisition.",
                0.6 + 0.3 * ua_share if ua_share > 0 else 0.0,
            ),
            self._factor(
                "product",
                product_traffic,
                d_rev,
                "Organic audience change (retention, store, virality).",
                0.6 if (delta.dau_pct not in (None, 0)) else 0.4,
            ),
            self._factor(
                "monetization",
                monetization_component,
                d_rev,
                "Change in revenue-per-user (ARPDAU / ARPPPU).",
                0.6 if monetization_component != 0 else 0.4,
            ),
            self._factor(
                "seasonality",
                seasonality,
                d_rev,
                "Calendar / seasonal baseline hypothesis.",
                0.3,
            ),
            self._factor(
                "noise",
                noise,
                d_rev,
                "Unexplained residual (second-order & model error).",
                0.5,
            ),
        ]

        rev_pct = delta.revenue_total_pct
        return AttributionBreakdown(
            game_id=current.game_id,
            revenue_change_abs=round(d_rev, 4),
            revenue_change_pct=rev_pct,
            total_revenue_current=round(rev_cur, 4),
            total_revenue_previous=round(rev_prev, 4),
            factors=factors,
        )

    # ------------------------------------------------------------------ #
    @staticmethod
    def _ua_share(delta: RevenueDelta) -> float:
        """Fraction of DAU change attributable to UA spend leverage.

        If UA spend grew and DAU grew, the ratio ``spend_pct / dau_pct``
        estimates how much of the audience gain was bought. Clamped 0..1.
        """
        sp = delta.spend_pct
        dp = delta.dau_pct
        if sp is None or dp is None or sp <= 0 or dp <= 0:
            return 0.0
        return min(1.0, max(0.0, sp / dp))

    @staticmethod
    def _factor(
        name: str,
        absolute: float,
        d_rev: float,
        description: str,
        confidence: float,
    ) -> AttributionFactor:
        denom = abs(d_rev) if d_rev != 0 else 0.0
        pct = (absolute / denom * 100.0) if denom else 0.0
        return AttributionFactor(
            name=name,
            contribution_pct=round(pct, 2),
            absolute=round(absolute, 4),
            description=description,
            confidence=round(min(1.0, max(0.0, confidence)), 4),
        )


__all__ = ["RevenueAttributionEngine"]
