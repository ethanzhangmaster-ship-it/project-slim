"""
E16.1.2 — Revenue Forecasting (收入预测).

Turns a history of ``RevenueSnapshot`` into a deterministic, explainable
forward view:

* next-7-day / next-30-day revenue projection
* LTV estimate (retention-weighted, 90-day horizon)
* trend classification (up / down / flat)
* risk flags (version fatigue, high volatility, insufficient history)

Pure logic — least-squares trend + retention-weighted lifetime. No ML,
no I/O, fully unit-testable. This is the "CFO looks forward" half of the
Revenue Intelligence Agent; ``analyzer.py`` is the "looks backward" half.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .models import RevenueSnapshot

__all__ = ["RevenueForecast", "RevenueForecaster"]


# --------------------------------------------------------------------------- #
# Result model
# --------------------------------------------------------------------------- #
@dataclass
class RevenueForecast:
    """A deterministic forward projection for one game."""

    game_id: str
    as_of: str  # date label of the latest snapshot used

    daily_run_rate: float = 0.0  # projected revenue for the next single day
    next_7d_revenue: float = 0.0
    next_30d_revenue: float = 0.0
    ltv_estimate: float = 0.0  # per-user, 90-day retention-weighted

    trend: str = "flat"  # "up" | "down" | "flat"
    trend_slope_pct: float = 0.0  # average day-over-day % drift

    risk_flags: List[str] = field(default_factory=list)
    confidence: float = 0.5
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "as_of": self.as_of,
            "daily_run_rate": round(self.daily_run_rate, 4),
            "next_7d_revenue": round(self.next_7d_revenue, 4),
            "next_30d_revenue": round(self.next_30d_revenue, 4),
            "ltv_estimate": round(self.ltv_estimate, 4),
            "trend": self.trend,
            "trend_slope_pct": round(self.trend_slope_pct, 4),
            "risk_flags": list(self.risk_flags),
            "confidence": round(self.confidence, 4),
            "evidence": self.evidence,
        }

    def to_markdown(self) -> str:
        lines = [
            f"## Revenue Forecast — {self.game_id} (as of {self.as_of})",
            f"- Trend: **{self.trend}** ({self.trend_slope_pct:+.1f}%/day)",
            f"- Next 7d revenue: ${self.next_7d_revenue:,.0f}",
            f"- Next 30d revenue: ${self.next_30d_revenue:,.0f}",
            f"- LTV estimate (90d): ${self.ltv_estimate:,.2f}",
            f"- Confidence: {self.confidence:.2f}",
        ]
        if self.risk_flags:
            lines.append(f"- Risks: {', '.join(self.risk_flags)}")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Forecaster
# --------------------------------------------------------------------------- #
class RevenueForecaster:
    """Least-squares trend forecaster over ``RevenueSnapshot`` history.

    Deterministic by design: the same history always yields the same
    forecast, so every projection is auditable and reproducible.
    """

    def __init__(
        self,
        min_history: int = 3,
        flat_band_pct: float = 1.0,  # |slope%| below this → "flat"
        volatility_risk_cv: float = 0.4,  # coefficient of variation threshold
        fatigue_decline_days: int = 3,  # consecutive declines for fatigue
        fatigue_spend_stability_pct: float = 10.0,
    ):
        self.min_history = min_history
        self.flat_band_pct = flat_band_pct
        self.volatility_risk_cv = volatility_risk_cv
        self.fatigue_decline_days = fatigue_decline_days
        self.fatigue_spend_stability_pct = fatigue_spend_stability_pct

    # ------------------------------------------------------------------ #
    def forecast(self, history: List[RevenueSnapshot]) -> RevenueForecast:
        if not history:
            return RevenueForecast(
                game_id="unknown",
                as_of="",
                risk_flags=["no_history"],
                confidence=0.0,
            )

        snaps = sorted(history, key=lambda s: s.date)
        latest = snaps[-1]
        series = [max(0.0, s.revenue_total) for s in snaps]
        n = len(series)

        risk_flags: List[str] = []

        # --- run rate & slope ------------------------------------------- #
        if n == 1:
            run_rate = series[0]
            slope = 0.0
        else:
            slope, intercept = self._least_squares(series)
            run_rate = max(0.0, intercept + slope * n)  # next point (index n)

        mean = sum(series) / n if n else 0.0
        slope_pct = (slope / mean * 100.0) if mean > 1e-9 else 0.0

        # --- projections (clamped at zero) ------------------------------ #
        next_7d = self._project_sum(series, slope, days=7)
        next_30d = self._project_sum(series, slope, days=30)

        # --- trend classification --------------------------------------- #
        if slope_pct > self.flat_band_pct:
            trend = "up"
        elif slope_pct < -self.flat_band_pct:
            trend = "down"
        else:
            trend = "flat"

        # --- LTV estimate ------------------------------------------------ #
        ltv = self._ltv_estimate(latest)

        # --- risks -------------------------------------------------------- #
        if n < self.min_history:
            risk_flags.append("insufficient_history")
        cv = self._cv(series, mean)
        if n >= 3 and cv > self.volatility_risk_cv:
            risk_flags.append("high_volatility")
        if trend == "down":
            risk_flags.append("revenue_decline")
        if self._version_fatigue(snaps):
            risk_flags.append("version_fatigue")

        # --- confidence ---------------------------------------------------- #
        confidence = 0.5
        confidence += min(0.3, 0.03 * n)  # more history → more confidence
        confidence -= min(0.3, cv * 0.5)  # volatility penalty
        if n < self.min_history:
            confidence = min(confidence, 0.4)
        confidence = max(0.05, min(0.95, confidence))

        return RevenueForecast(
            game_id=latest.game_id,
            as_of=latest.date,
            daily_run_rate=run_rate,
            next_7d_revenue=next_7d,
            next_30d_revenue=next_30d,
            ltv_estimate=ltv,
            trend=trend,
            trend_slope_pct=slope_pct,
            risk_flags=risk_flags,
            confidence=confidence,
            evidence={
                "history_points": n,
                "mean_daily_revenue": round(mean, 4),
                "slope_per_day": round(slope, 4),
                "coefficient_of_variation": round(cv, 4),
            },
        )

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    @staticmethod
    def _least_squares(series: List[float]) -> tuple:
        """Return (slope, intercept) of y = a*x + b over index positions."""
        n = len(series)
        xs = list(range(n))
        sum_x = sum(xs)
        sum_y = sum(series)
        sum_xy = sum(x * y for x, y in zip(xs, series))
        sum_x2 = sum(x * x for x in xs)
        denom = n * sum_x2 - sum_x * sum_x
        if abs(denom) < 1e-12:
            return 0.0, series[-1]
        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n
        return slope, intercept

    @staticmethod
    def _project_sum(series: List[float], slope: float, days: int) -> float:
        """Sum of the next ``days`` projected daily revenues, floored at 0."""
        n = len(series)
        if n == 1:
            return max(0.0, series[0]) * days
        _, intercept = RevenueForecaster._least_squares(series)
        total = 0.0
        for i in range(n, n + days):
            total += max(0.0, intercept + slope * i)
        return total

    @staticmethod
    def _cv(series: List[float], mean: float) -> float:
        if mean <= 1e-9 or len(series) < 2:
            return 0.0
        var = sum((v - mean) ** 2 for v in series) / len(series)
        return (var ** 0.5) / mean

    @staticmethod
    def _ltv_estimate(snap: RevenueSnapshot) -> float:
        """Retention-weighted per-user LTV over a ~90 day horizon.

        ARPDAU x estimated active-days:
        day0 (1) + d1 retention covering days 1-6 (6) +
        d7 retention covering days 7-29 (23) + d30 covering days 30-89 (60).
        """
        if snap.dau <= 0:
            return 0.0
        arpdau = snap.revenue_total / snap.dau
        lifetime_days = (
            1.0
            + snap.retention_d1 * 6.0
            + snap.retention_d7 * 23.0
            + snap.retention_d30 * 60.0
        )
        return arpdau * lifetime_days

    def _version_fatigue(self, snaps: List[RevenueSnapshot]) -> bool:
        """Spend stable but revenue declining for N consecutive periods."""
        k = self.fatigue_decline_days
        if len(snaps) < k + 1:
            return False
        tail = snaps[-(k + 1):]
        # revenue strictly declining across the window
        for a, b in zip(tail, tail[1:]):
            if b.revenue_total >= a.revenue_total:
                return False
        # spend stable (no big cuts explaining the decline)
        spends = [s.spend for s in tail]
        base = spends[0]
        if base <= 1e-9:
            return True  # organic revenue declining with no spend at all
        drift = max(abs(s - base) / base * 100.0 for s in spends)
        return drift <= self.fatigue_spend_stability_pct
