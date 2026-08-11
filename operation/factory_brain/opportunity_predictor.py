"""
E15.1.2 — Opportunity Predictor (Product Opportunity Engine)
=============================================================

MarketOpportunity  ->  RoasPrediction (CPI / D30_ROAS / D90_ROAS / confidence)

This is the economics layer of the Product Opportunity Engine: it turns
the abstract 0..1 sub-scores into the numbers an operator actually
decides on — install cost and payback horizon.

Every number is a fixed, documented function of the opportunity's
sub-scores. No LLM, no randomness: same opportunity -> same forecast.

Formulae (deterministic):

    CPI       crowded market costs more, rising demand costs less
              cpi = BASE_CPI * (1 + W_COMP*competition)
                             / (1 + W_TREND*keyword_trend)

    D30_ROAS  driven by monetization strength (eCPM + LTV), scaled by
              how cheap installs are (revenue-per-install / CPI)
              rev_per_install = REV_UNIT * (0.6*ecpm + 0.4*ltv)
              d30 = clamp(D30_SHARE * rev_per_install / cpi, 0, 3)

    D90_ROAS  later-cohort maturation multiplier over D30
              d90 = d30 * D90_MULT

    confidence  opportunity.score() lightly damped by data completeness
"""
from __future__ import annotations

from typing import List

from .models import MarketOpportunity, RoasPrediction

# --- documented constants ------------------------------------------------ #
BASE_CPI = 1.20          # baseline install cost, USD (US casual benchmark)
_W_COMP = 1.00           # competition raises CPI
_W_TREND = 0.60          # rising keyword trend lowers CPI
_CPI_FLOOR = 0.30
_CPI_CEIL = 4.00

_REV_UNIT = 1.60         # USD of lifetime rev per "1.0" monetization unit
_D30_SHARE = 0.62        # share of lifetime value realised by day 30
_D90_MULT = 1.70         # day-90 cohort matures ~1.7x over day-30
_ROAS_CEIL = 3.00        # cap absurd ratios


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class OpportunityPredictor:
    """Deterministic CPI / ROAS forecaster for opportunities."""

    def predict(self, opp: MarketOpportunity) -> RoasPrediction:
        kw = _clamp(opp.keyword_trend, 0.0, 1.0)
        comp = _clamp(opp.competition, 0.0, 1.0)
        ecpm = _clamp(opp.ecpm_signal, 0.0, 1.0)
        ltv = _clamp(opp.ltv_forecast, 0.0, 1.0)

        # 1) CPI
        cpi = BASE_CPI * (1.0 + _W_COMP * comp) / (1.0 + _W_TREND * kw)
        cpi = round(_clamp(cpi, _CPI_FLOOR, _CPI_CEIL), 2)

        # 2) revenue per install from monetization strength
        rev_per_install = _REV_UNIT * (0.60 * ecpm + 0.40 * ltv)

        # 3) D30 / D90 ROAS
        d30 = _D30_SHARE * rev_per_install / cpi if cpi > 0 else 0.0
        d30 = round(_clamp(d30, 0.0, _ROAS_CEIL), 3)
        d90 = round(_clamp(d30 * _D90_MULT, 0.0, _ROAS_CEIL), 3)

        # 4) confidence: opportunity score damped by data completeness
        filled = sum(1 for x in (kw, comp, ecpm, ltv) if x > 0)
        completeness = 0.7 + 0.3 * (filled / 4.0)      # 0.7..1.0
        confidence = round(_clamp(opp.score() * completeness, 0.0, 1.0), 3)

        payback_ok = d90 >= 1.0
        notes = (f"CPI ${cpi:.2f}, D30 {d30:.0%}, D90 {d90:.0%} — "
                 + ("recoups within 90d" if payback_ok
                    else "no 90d payback at this CPI"))
        return RoasPrediction(
            opportunity_id=opp.opportunity_id,
            cpi=cpi, d30_roas=d30, d90_roas=d90,
            confidence=confidence, payback_ok=payback_ok, notes=notes)

    def predict_batch(
            self, opps: List[MarketOpportunity]) -> List[RoasPrediction]:
        return [self.predict(o) for o in opps]


__all__ = ["OpportunityPredictor", "BASE_CPI"]
