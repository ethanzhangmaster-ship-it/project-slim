"""
E15.1.2 — Game Decision Engine (Auto KEEP / SCALE / KILL)
==========================================================

The hardest problem for a one-person game studio is not building —
it is knowing WHEN TO KILL. This engine gives every live game a daily
fund-manager verdict from its own economics:

    input  (GameProduct.metrics):
        d1_retention, d7_retention, cpi, roas, arpdau
    output (GameDecision):
        KEEP  / SCALE (+budget) / KILL   + human reason + payback horizon

Payback model (deterministic power-law retention):

    fit r(n) = d1 * n**b, with b = ln(d7/d1)/ln(7)
    cumulative retained-days  D(N) = sum_{n=1..N} r(n)
    cumulative revenue/install R(N) = arpdau * D(N)
    payback_days = smallest N where R(N) >= cpi   (else > horizon)

Verdict logic (realised ROAS is authoritative — it is ground truth;
the payback projection only rules when ROAS is absent or marginal):

    KILL   realised roas < 0.30                        (bleeding money)
           OR (not proven profitable AND d1 < 0.20)    (leaky bucket)
           OR (not proven profitable AND payback > 90)  (won't recoup)
    SCALE  roas >= 1.0 AND retention healthy AND payback <= 45
    KEEP   everything else, with the dominant reason spelled out

"proven profitable" == realised roas >= 1.0. A game the market has
already shown recoups spend is never killed on a theoretical model.

Everything is a PROPOSAL: requires_manual_apply is always True. The
brain never raises a budget or archives a game by itself.
"""
from __future__ import annotations

import math
from typing import List, Optional

from operation.publishing_factory.catalog.game_registry import GameRegistry
from operation.publishing_factory.catalog.product_profile import GameProduct

from .models import GameDecision, Verdict

# --- IAA (no-UA) fleet mode --------------------------------------------- #
# This system's live reality: pure in-app-ads games, NO UA buying, so no
# CPI/ROAS exists. IAA verdicts are driven by what IS real in the MAX
# report: per-app revenue, revenue share, eCPM vs the account blend,
# request volume and the show path. Thresholds calibrated on the real
# 3-account fleet (2026-07 window):
#   Merge Monster    99.0% share, eCPM 1.39x blend      -> SCALE (winner)
#   Drama Hospital   62.8% share, eCPM 2.69x blend      -> SCALE
#   Be A Master Chef 37.2% share, eCPM 0.49x blend      -> KEEP  (optimise)
#   Hospital Fever    0.4% share, eCPM 0.02x, 1.1k req/d -> KILL (zombie)
#   Merge Legend     0 imps, 1.3k req/d, 3.8k fills      -> FIX  (show path)
#   merge witches    4 req/d, $0                         -> KILL (dead)
_IAA_ECPM_WINNER = 1.30      # eCPM >= 1.3x blend (same bar as HiddenWinner)
_IAA_SHARE_WINNER = 0.20     # carries >= 20% of account revenue
# A dominant carrier IS the blend, so its ratio tends to 1.0 and the
# 1.3x bar can never fire. If one app carries >= 60% of revenue and its
# eCPM is not dragging the blend (>= 0.9x), it is a winner by definition.
_IAA_SHARE_DOMINANT = 0.60
_IAA_ECPM_DOMINANT_MIN = 0.90
_IAA_ECPM_ZOMBIE = 0.10      # eCPM < 10% of blend
_IAA_SHARE_ZOMBIE = 0.05     # AND share < 5%
_IAA_DEAD_ATT_PER_DAY = 50.0     # < 50 requests/day == no real users
_IAA_DEAD_REVENUE = 0.10         # AND < $0.10 in the whole window

# --- documented benchmarks (US casual) ---------------------------------- #
_D1_GOOD = 0.35          # day-1 retention healthy at/above this
_D7_GOOD = 0.10          # day-7 retention healthy at/above this
_D1_BAD = 0.20           # below this, retention is catastrophic
_PAYBACK_KILL = 90.0     # can't recoup CPI within 90d -> kill candidate
_PAYBACK_SCALE = 45.0    # recoups within 45d -> strong scale candidate
_ROAS_SCALE = 1.00       # already profitable
_ROAS_KILL = 0.30        # bleeding money
_SCALE_BUDGET_PCT = 30.0
_HORIZON = 365           # cap for payback search


def _fit_b(d1: float, d7: float) -> float:
    """Power-law exponent from d1 -> d7 (negative)."""
    if d1 > 0 and d7 > 0:
        return math.log(d7 / d1) / math.log(7.0)
    return -0.70             # sensible casual default


def payback_days(cpi: float, arpdau: float,
                 d1: float, d7: float, horizon: int = _HORIZON) -> float:
    """Days to recoup CPI. Returns horizon+1 if never within horizon."""
    if cpi <= 0:
        return 0.0
    if arpdau <= 0:
        return float(horizon + 1)
    b = _fit_b(d1 or _D1_GOOD, d7 or _D7_GOOD)
    d1_eff = d1 if d1 > 0 else _D1_GOOD
    cum_rev = 0.0
    cum_days = 0.0
    for n in range(1, horizon + 1):
        r = min(1.0, d1_eff * (n ** b))
        cum_days += r
        cum_rev = arpdau * cum_days
        if cum_rev >= cpi:
            return float(n)
    return float(horizon + 1)


class GameDecisionEngine:
    """Retention/economics-aware KEEP / SCALE / KILL for live games."""

    def evaluate(self, g: GameProduct) -> Optional[GameDecision]:
        """One verdict for one game, or None if it lacks economics data."""
        m = g.metrics or {}
        cpi = float(m.get("cpi", 0.0))
        arpdau = float(m.get("arpdau", 0.0))
        d1 = float(m.get("d1_retention", 0.0))
        d7 = float(m.get("d7_retention", 0.0))
        roas = m.get("roas")
        roas = float(roas) if roas is not None else None

        # need at least CPI + ARPDAU to judge economics
        if cpi <= 0 or arpdau <= 0:
            return None

        pb = payback_days(cpi, arpdau, d1, d7)
        snap = {k: float(v) for k, v in m.items()
                if isinstance(v, (int, float))}

        def mk(verdict: Verdict, reason: str,
               budget: float = 0.0) -> GameDecision:
            return GameDecision(
                game_id=g.game_id, verdict=verdict.value, reason=reason,
                budget_delta_pct=budget, payback_days=round(pb, 1),
                metric_snapshot=snap)

        retention_ok = d1 >= _D1_GOOD and d7 >= _D7_GOOD
        proven_profit = roas is not None and roas >= _ROAS_SCALE

        # --- 1) hard KILL: realised ROAS bleeding money ---------------- #
        if roas is not None and roas < _ROAS_KILL:
            return mk(Verdict.KILL,
                      f"ROAS {roas:.2f} < {_ROAS_KILL:.2f}: bleeding money")

        # --- 2) proven-profitable path (realised ROAS is ground truth) - #
        if proven_profit:
            if retention_ok and pb <= _PAYBACK_SCALE:
                return mk(Verdict.SCALE,
                          f"ROAS {roas:.2f}>=1.0 proven, D1 {d1:.0%}/D7 "
                          f"{d7:.0%} healthy, payback {pb:.0f}d: raise budget",
                          budget=_SCALE_BUDGET_PCT)
            why = ("retention below benchmark" if not retention_ok
                   else f"payback {pb:.0f}d slow")
            return mk(Verdict.KEEP,
                      f"ROAS {roas:.2f} profitable but {why}: "
                      f"hold budget, optimise first")

        # --- 3) not proven profitable: projection rules ---------------- #
        if 0 < d1 < _D1_BAD:
            return mk(Verdict.KILL,
                      f"D1 {d1:.0%} < {_D1_BAD:.0%}: broken retention, "
                      f"UA can't fix a leaky bucket")
        if pb > _PAYBACK_KILL:
            horizon_txt = (">1y" if pb > _HORIZON else f"~{pb:.0f}d")
            return mk(Verdict.KILL,
                      f"projected payback {horizon_txt} > 90d: "
                      f"won't recoup CPI ${cpi:.2f}")

        # --- 4) KEEP (with the dominant reason) ------------------------ #
        bits: List[str] = [f"payback {pb:.0f}d"]
        if roas is not None:
            bits.append(f"ROAS {roas:.2f}")
        if d1 or d7:
            bits.append(f"D1 {d1:.0%}/D7 {d7:.0%}")
        if not retention_ok and (d1 or d7):
            bits.append("retention below benchmark: optimise before scaling")
        elif roas is not None:
            bits.append("ROAS not yet 1.0: keep optimising")
        return mk(Verdict.KEEP, ", ".join(bits))

    def evaluate_fleet(self, registry: GameRegistry) -> List[GameDecision]:
        out: List[GameDecision] = []
        for g in registry.list_all():
            d = self.evaluate(g)
            if d is not None:
                out.append(d)
        return out

    # ------------------------------------------------------------------ #
    # IAA mode — verdicts for the real, no-UA ad-revenue fleet
    # ------------------------------------------------------------------ #
    def evaluate_iaa(self, entry: dict) -> Optional[GameDecision]:
        """Verdict for one live IAA game from real MAX per-app economics.

        entry (all derived from the MAX report + account context):
            app, revenue, share, ecpm, ecpm_ratio, impressions,
            attempts, responses, attempts_per_day, days
            (optional) trend_pct
        """
        app = str(entry.get("app") or entry.get("game_id") or "?")
        rev = float(entry.get("revenue", 0.0))
        share = float(entry.get("share", 0.0))
        ecpm = float(entry.get("ecpm", 0.0))
        ratio = float(entry.get("ecpm_ratio", 0.0))
        imps = int(entry.get("impressions", 0))
        responses = int(entry.get("responses", 0))
        att_day = float(entry.get("attempts_per_day", 0.0))
        trend = entry.get("trend_pct")

        if att_day <= 0 and imps <= 0 and rev <= 0:
            return None                      # no signal at all

        snap = {k: float(v) for k, v in entry.items()
                if isinstance(v, (int, float))}

        def mk(verdict: Verdict, reason: str) -> GameDecision:
            return GameDecision(
                game_id=app, verdict=verdict.value, reason=reason,
                budget_delta_pct=0.0, payback_days=0.0,
                metric_snapshot=snap, mode="iaa")

        # 1) dead traffic: nobody is playing — not worth any attention
        if att_day < _IAA_DEAD_ATT_PER_DAY and rev < _IAA_DEAD_REVENUE:
            return mk(Verdict.KILL,
                      f"dead traffic: {att_day:.0f} req/day, ${rev:.2f} "
                      f"window revenue — no meaningful users, sunset")

        # 2) broken show path: ads FILL but are never SHOWN
        if imps == 0 and responses > 0:
            return mk(Verdict.FIX,
                      f"broken show path: {att_day:,.0f} req/day, "
                      f"{responses:,} fills, 0 impressions — ads load "
                      f"but never show; engineering ticket, not a kill")

        # 3) proven IAA winner: premium eCPM with real share, OR the
        #    dominant carrier of the account (its ratio ~= 1.0 by
        #    construction, so the premium bar cannot apply to it)
        is_premium = share >= _IAA_SHARE_WINNER and ratio >= _IAA_ECPM_WINNER
        is_dominant = (share >= _IAA_SHARE_DOMINANT
                       and ratio >= _IAA_ECPM_DOMINANT_MIN)
        if is_premium or is_dominant:
            t = (f", rev trend {trend:+.0%}"
                 if isinstance(trend, (int, float)) else "")
            return mk(Verdict.SCALE,
                      f"IAA winner: {share:.0%} of account revenue, "
                      f"eCPM ${ecpm:.2f} = {ratio:.2f}x blend{t} — "
                      f"replicate pattern, protect waterfall")

        # 4) zombie monetization: real traffic, negligible money
        if ratio < _IAA_ECPM_ZOMBIE and share < _IAA_SHARE_ZOMBIE:
            return mk(Verdict.KILL,
                      f"zombie: {att_day:,.0f} req/day monetise at eCPM "
                      f"${ecpm:.2f} ({ratio:.2f}x blend), {share:.1%} of "
                      f"revenue — deprioritise")

        # 5) everything else earns attention but needs work
        gaps: List[str] = []
        if ratio < 1.0:
            gaps.append(f"eCPM ${ecpm:.2f} = {ratio:.2f}x blend: "
                        f"waterfall/floor work first")
        if responses > 0 and imps / max(1, responses) < 0.10:
            gaps.append(f"show rate {imps / max(1, responses):.0%}: "
                        f"placement under-used")
        if isinstance(trend, (int, float)) and trend < -0.10:
            gaps.append(f"rev trend {trend:+.0%}")
        why = "; ".join(gaps) if gaps else "healthy, hold course"
        return mk(Verdict.KEEP,
                  f"optimise: {share:.0%} of revenue — {why}")

    def evaluate_iaa_fleet(self, entries: List[dict]) -> List[GameDecision]:
        out: List[GameDecision] = []
        for e in entries:
            d = self.evaluate_iaa(e)
            if d is not None:
                out.append(d)
        return out


__all__ = ["GameDecisionEngine", "payback_days"]
