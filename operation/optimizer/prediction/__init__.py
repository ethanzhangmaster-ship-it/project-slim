"""E15.2.5 Autonomous IAA — increment 2: eCPM Prediction (module 6).

Deterministic, dependency-free eCPM forecasting so the agent moves from
reactive (what happened) to predictive (what will happen). Built from the
day dimension already present in MAX Report rows.

No numpy / no LLM / no MAX writes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from operation.optimizer.intel_models import fnum


@dataclass
class EcmpPoint:
    """One day's eCPM observation for a single segment series."""
    day: str
    ecpm: float
    impressions: int


@dataclass
class EcmpForecast:
    """Predicted next-period eCPM for one (app, geo, format, network)."""
    segment: str            # human label: app · geo · format · network
    network: str
    n_days: int
    historical_mean: float
    last_ecpm: float
    predicted_ecpm: float
    lower: float            # 95% confidence band (clamped >= 0)
    upper: float
    trend: str              # UP | DOWN | FLAT
    slope: float            # eCPM per day
    r2: float
    confidence: str         # HIGH | MEDIUM | LOW
    total_impressions: int
    last_impressions: int
    early_warning: bool = False
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment": self.segment, "network": self.network,
            "n_days": self.n_days,
            "historical_mean": round(self.historical_mean, 2),
            "last_ecpm": round(self.last_ecpm, 2),
            "predicted_ecpm": round(self.predicted_ecpm, 2),
            "lower": round(self.lower, 2), "upper": round(self.upper, 2),
            "trend": self.trend, "slope": round(self.slope, 4),
            "r2": round(self.r2, 3), "confidence": self.confidence,
            "total_impressions": self.total_impressions,
            "last_impressions": self.last_impressions,
            "early_warning": self.early_warning, "note": self.note,
        }


@dataclass
class AccountEcmpForecast:
    """All eCPM forecasts for one account over a period."""
    account: str
    period_start: str
    period_end: str
    generated_at: str
    forecasts: List[EcmpForecast] = field(default_factory=list)

    @property
    def n_total(self) -> int:
        return len(self.forecasts)

    @property
    def n_up(self) -> int:
        return sum(1 for f in self.forecasts if f.trend == "UP")

    @property
    def n_down(self) -> int:
        return sum(1 for f in self.forecasts if f.trend == "DOWN")

    @property
    def n_flat(self) -> int:
        return sum(1 for f in self.forecasts if f.trend == "FLAT")

    @property
    def n_early_warning(self) -> int:
        return sum(1 for f in self.forecasts if f.early_warning)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account": self.account,
            "period": {"start": self.period_start, "end": self.period_end},
            "generated_at": self.generated_at,
            "summary": {"total": self.n_total, "up": self.n_up,
                        "down": self.n_down, "flat": self.n_flat,
                        "early_warning": self.n_early_warning},
            "forecasts": [f.to_dict() for f in self.forecasts],
        }


class EcmpPredictor:
    """Closed-form OLS eCPM forecaster (no external deps)."""

    MIN_DAYS = 5                 # need >=5 daily points to trust a trend
    MIN_IMP_PER_DAY = 30         # drop noisy low-volume days from the fit
    SLOPE_MIN_FRACTION = 0.05    # slope must exceed 5% of mean to be "real"
    R2_MIN = 0.25                # minimum fit to call a trend significant
    Z = 1.96                     # ~95% band
    EARLY_WARN_DROP = 0.85       # predicted < 85% of last -> warn
    FLOOR_FRACTION = 0.10        # lift estimate: drop imps below 10% blend

    # ---------------------------------------------------------------- #
    def build_series(self, rows: List[dict]
                     ) -> Dict[str, List[EcmpPoint]]:
        """Group raw rows into per-(app,geo,format,network) daily series."""
        series: Dict[str, Dict[str, EcmpPoint]] = {}
        for r in rows:
            app = r.get("application") or "?"
            geo = (r.get("country") or "?").lower()
            fmt = r.get("ad_format") or "?"
            net = r.get("network") or "?"
            seg = f"{app} · {geo} · {fmt} · {net}"
            day = str(r.get("day") or "")
            imp = int(fnum(r.get("impressions"), 0))
            rev = fnum(r.get("estimated_revenue"), 0.0)
            ecpm = fnum(r.get("ecpm"), 0.0)
            # prefer the explicit ecpm column; fall back to rev/imp
            if ecpm <= 0 and imp > 0:
                ecpm = rev / imp * 1000.0
            d = series.setdefault(seg, {})
            p = d.get(day)
            if p is None:
                d[day] = EcmpPoint(day=day, ecpm=ecpm, impressions=imp)
            else:
                # same day already seen (multiple pages) -> blend by volume
                tot = p.impressions + imp
                p.ecpm = (p.ecpm * p.impressions + ecpm * imp) / tot if tot else p.ecpm
                p.impressions = tot
        # ordered point lists
        out: Dict[str, List[EcmpPoint]] = {}
        for seg, by_day in series.items():
            pts = sorted(by_day.values(), key=lambda x: x.day)
            out[seg] = pts
        return out

    # ---------------------------------------------------------------- #
    def predict_series(self, seg: str, network: str,
                       points: List[EcmpPoint]) -> Optional[EcmpForecast]:
        """Fit OLS on day-index vs eCPM. Returns None if too sparse."""
        pts = [p for p in points if p.impressions >= self.MIN_IMP_PER_DAY]
        n = len(pts)
        if n < self.MIN_DAYS:
            return None
        xs = list(range(n))
        ys = [p.ecpm for p in pts]
        mean_x = (n - 1) / 2.0
        mean_y = sum(ys) / n
        sxx = sum((x - mean_x) ** 2 for x in xs)
        sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        ss_tot = sum((y - mean_y) ** 2 for y in ys)
        if sxx == 0:
            slope = 0.0
        else:
            slope = sxy / sxx
        intercept = mean_y - slope * mean_x
        yhat = intercept + slope * n          # predict next day (x = n)
        yhat = max(0.0, yhat)                 # eCPM cannot be negative
        # residual std
        if n > 2:
            ss_res = sum((y - (intercept + slope * x)) ** 2
                         for x, y in zip(xs, ys))
            res_var = ss_res / (n - 2)
        else:
            res_var = 0.0
        res_std = res_var ** 0.5
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        if ss_tot <= 1e-9:
            r2 = 0.0
        # band: residual-based, with a small floor (2% of mean) so a near
        # perfect line still shows a non-zero uncertainty interval.
        band = max(self.Z * res_std, 0.02 * max(mean_y, 1e-6))
        lower = max(0.0, yhat - band)
        upper = yhat + band

        # trend classification
        significant = (abs(slope) > self.SLOPE_MIN_FRACTION * max(mean_y, 1e-6)
                       and r2 >= self.R2_MIN)
        if significant and slope > 0:
            trend = "UP"
        elif significant and slope < 0:
            trend = "DOWN"
        else:
            trend = "FLAT"

        # confidence
        band_frac = (self.Z * res_std) / max(mean_y, 1e-6)
        if n >= 8 and r2 >= 0.5 and band_frac < 0.3:
            confidence = "HIGH"
        elif n >= self.MIN_DAYS and r2 >= self.R2_MIN:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        early = (trend == "DOWN" and confidence in ("HIGH", "MEDIUM")
                 and yhat < self.EARLY_WARN_DROP * pts[-1].ecpm)

        note = (f"n={n}d, slope {slope:+.3f}/d, R²={r2:.2f}, "
                f"band ±${self.Z * res_std:.2f}")
        return EcmpForecast(
            segment=seg, network=network, n_days=n,
            historical_mean=mean_y, last_ecpm=pts[-1].ecpm,
            predicted_ecpm=yhat, lower=lower, upper=upper,
            trend=trend, slope=slope, r2=r2, confidence=confidence,
            total_impressions=sum(p.impressions for p in pts),
            last_impressions=pts[-1].impressions,
            early_warning=early, note=note)

    # ---------------------------------------------------------------- #
    def predict_account(self, rows: List[dict], account: str,
                        period_start: str, period_end: str,
                        today: Optional[str] = None) -> AccountEcmpForecast:
        series = self.build_series(rows)
        rec = AccountEcmpForecast(
            account=account, period_start=period_start, period_end=period_end,
            generated_at=today or _today())
        for seg, pts in series.items():
            net = seg.split(" · ")[-1]
            fc = self.predict_series(seg, net, pts)
            if fc is not None:
                rec.forecasts.append(fc)
        # biggest segments first for rendering
        rec.forecasts.sort(key=lambda f: -f.total_impressions)
        return rec

    # ---------------------------------------------------------------- #
    def estimate_floor_lift(self, rows: List[dict], seg: str,
                            floor_ecpm: float) -> Optional[float]:
        """Counterfactual lift if a floor drops low-eCPM days' impressions.

        Approximate: at the (app,geo,format,network) level, days whose
        blended eCPM < floor are assumed to lose their low-value fill. We
        recompute the blend excluding those days' revenue+impressions.
        Returns lift % (new_blend / old_blend - 1), or None if <MIN_DAYS.

        `seg` must equal the label produced by build_series, i.e.
        "app · geo · format · network".
        """
        sub = self.build_series([r for r in rows
                                 if f"{r.get('application') or '?'} · "
                                    f"{(r.get('country') or '?').lower()} · "
                                    f"{r.get('ad_format') or '?'} · "
                                    f"{r.get('network') or '?'}" == seg])
        pts = [p for p in sub.get(seg, []) if p.impressions >= self.MIN_IMP_PER_DAY]
        if len(pts) < self.MIN_DAYS:
            return None
        old_rev = sum(p.ecpm * p.impressions / 1000.0 for p in pts)
        old_imp = sum(p.impressions for p in pts)
        if old_imp <= 0:
            return None
        new_rev = sum(p.ecpm * p.impressions / 1000.0 for p in pts
                      if p.ecpm >= floor_ecpm)
        new_imp = sum(p.impressions for p in pts if p.ecpm >= floor_ecpm)
        if new_imp <= 0:
            return None
        old_blend = old_rev / old_imp * 1000.0
        new_blend = new_rev / new_imp * 1000.0
        if old_blend <= 0:
            return None
        return (new_blend / old_blend - 1.0) * 100.0


def _today() -> str:
    from datetime import date as _d
    return _d.today().isoformat()
