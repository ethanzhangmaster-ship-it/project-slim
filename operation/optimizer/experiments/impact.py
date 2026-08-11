"""
E15.2.5+ — Impact Measurement (before/after revenue outcome).

Answers the question the verification engine cannot: *did the applied
change actually create incremental revenue?*

Method (deterministic, MAX report rows only — no user-side key needed):

  anchor    = exp.applied_at (operator marked the change applied)
  BEFORE    = days strictly before anchor
  AFTER     = days strictly after anchor (anchor day excluded: mixed)
  target    = rows whose network == exp.target (fallback: substring match
              against "app · geo · format · network" composite)

  target_delta_pct  = after_rev_per_day / before_rev_per_day - 1
  account_delta_pct = same computed over ALL rows (market/seasonal drift)
  net_impact_pct    = target_delta_pct - account_delta_pct
                      (difference-in-differences vs account baseline)

Guard: both windows need >= MIN_DAYS measurable days, else NOT_MEASURABLE.

Zero MAX writes. No LLM. No numpy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ImpactMeasurement:
    exp_id: str
    target: str
    applied_at: str
    measurable: bool
    before_days: int = 0
    after_days: int = 0
    before_rev_per_day: float = 0.0
    after_rev_per_day: float = 0.0
    before_ecpm: float = 0.0
    after_ecpm: float = 0.0
    target_delta_pct: Optional[float] = None
    account_delta_pct: Optional[float] = None
    net_impact_pct: Optional[float] = None
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exp_id": self.exp_id, "target": self.target,
            "applied_at": self.applied_at, "measurable": self.measurable,
            "before_days": self.before_days, "after_days": self.after_days,
            "before_rev_per_day": round(self.before_rev_per_day, 4),
            "after_rev_per_day": round(self.after_rev_per_day, 4),
            "before_ecpm": round(self.before_ecpm, 4),
            "after_ecpm": round(self.after_ecpm, 4),
            "target_delta_pct": self.target_delta_pct,
            "account_delta_pct": self.account_delta_pct,
            "net_impact_pct": self.net_impact_pct,
            "note": self.note,
        }


def _f(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


class ImpactMeasurer:
    """Before/after difference-in-differences on raw MAX report rows."""

    MIN_DAYS = 2          # each window needs at least this many distinct days

    # ------------------------------------------------------------------ #
    @staticmethod
    def _row_matches(row: Dict[str, Any], target: str) -> bool:
        net = (row.get("network") or "").upper()
        t = (target or "").upper()
        if not t:
            return False
        if net == t:
            return True
        composite = " · ".join([
            str(row.get("application") or ""),
            str(row.get("country") or ""),
            str(row.get("ad_format") or ""),
            net]).upper()
        return t in composite

    @staticmethod
    def _window_stats(rows: List[Dict[str, Any]]) -> Dict[str, float]:
        days = {r.get("day") for r in rows if r.get("day")}
        rev = sum(_f(r.get("estimated_revenue")) for r in rows)
        imp = sum(_f(r.get("impressions")) for r in rows)
        n = len(days)
        return {
            "days": float(n),
            "rev_per_day": (rev / n) if n else 0.0,
            "ecpm": (rev / imp * 1000.0) if imp else 0.0,
        }

    # ------------------------------------------------------------------ #
    def measure(self, rows: List[Dict[str, Any]], exp_id: str,
                target: str, applied_at: str) -> ImpactMeasurement:
        if not applied_at:
            return ImpactMeasurement(
                exp_id=exp_id, target=target, applied_at="",
                measurable=False, note="not applied yet (no anchor date)")

        before = [r for r in rows if (r.get("day") or "") < applied_at]
        after = [r for r in rows if (r.get("day") or "") > applied_at]
        t_before = [r for r in before if self._row_matches(r, target)]
        t_after = [r for r in after if self._row_matches(r, target)]

        tb, ta = self._window_stats(t_before), self._window_stats(t_after)
        ab, aa = self._window_stats(before), self._window_stats(after)

        m = ImpactMeasurement(
            exp_id=exp_id, target=target, applied_at=applied_at,
            measurable=True,
            before_days=int(tb["days"]), after_days=int(ta["days"]),
            before_rev_per_day=tb["rev_per_day"],
            after_rev_per_day=ta["rev_per_day"],
            before_ecpm=tb["ecpm"], after_ecpm=ta["ecpm"])

        if tb["days"] < self.MIN_DAYS or ta["days"] < self.MIN_DAYS:
            m.measurable = False
            m.note = (f"insufficient window (before {int(tb['days'])}d / "
                      f"after {int(ta['days'])}d, need >= {self.MIN_DAYS}d each)")
            return m

        if tb["rev_per_day"] > 0:
            m.target_delta_pct = round(
                (ta["rev_per_day"] / tb["rev_per_day"] - 1.0) * 100.0, 2)
        if ab["rev_per_day"] > 0:
            m.account_delta_pct = round(
                (aa["rev_per_day"] / ab["rev_per_day"] - 1.0) * 100.0, 2)
        if m.target_delta_pct is not None:
            drift = m.account_delta_pct or 0.0
            m.net_impact_pct = round(m.target_delta_pct - drift, 2)
            m.note = (f"target {m.target_delta_pct:+.1f}%/day vs account "
                      f"drift {drift:+.1f}% → net {m.net_impact_pct:+.1f}%")
        else:
            # zero-revenue baseline: any after-revenue is pure upside;
            # a disable/demote action succeeding shows as flat-zero.
            m.net_impact_pct = round(
                100.0 if ta["rev_per_day"] > 0 else 0.0, 2)
            m.note = "zero-revenue baseline; after-window revenue "
            m.note += "appeared" if ta["rev_per_day"] > 0 else "still zero"
        return m
