"""
E15.2.6 — IAA Growth Report (result-driven daily view).

This is the ONLY report the operator should need to read. It reframes
all monetization output around the single KPI the business cares about:

        Maximize  IAA Revenue / DAU

Everything else (eCPM, fill, waterfall depth, network health) is an
*input lever*, not the headline. The report shows:

  * IAA Revenue + Revenue/DAU (the KPI)
  * Day-over-day growth of that KPI
  * AI Actions currently live, each with measured $/day impact
  * Experiment portfolio: running / winning / rolled-back / memorized
  * AI-attributed lift = (sum of winner lifts) / total revenue

Data sources (all already available):
  * MAX  -> revenue, impressions, eCPM, experiments   (have)
  * Adjust -> DAU, retention                          (pending key)
  * Unity SDK -> ad request/impression/session        (pending SDK)

Until Adjust connects, DAU and true Revenue/DAU are shown as "pending"
and growth is reported on raw revenue; the structure is identical.

Deterministic — no LLM. Read-only over report + store.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from operation.optimizer.experiments.experiment_models import (
    APPLIED, MEMORIZED, ROLLBACK, WINNER,
)
from operation.optimizer.intel_models import MonetizationDailyReport

# Day-over-day growth needs the previous run's total revenue. We persist a
# tiny per-account snapshot so each daily run can show "vs yesterday".
SNAP_DIR = os.path.join("outputs", "growth")


def save_prior_revenue(account: str, revenue: float, date: str,
                       snap_dir: str = SNAP_DIR) -> None:
    os.makedirs(snap_dir, exist_ok=True)
    p = os.path.join(snap_dir, f"{account}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"account": account,
                   "revenue": round(revenue, 2), "date": date}, f)


def load_prior_revenue(account: str,
                       snap_dir: str = SNAP_DIR) -> Optional[float]:
    p = os.path.join(snap_dir, f"{account}.json")
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f).get("revenue")
    except (OSError, ValueError):
        return None


def _money(x: float) -> str:
    return f"${x:,.0f}"


def _pct(x: float) -> str:
    return f"{x:+.1f}%"


def build_growth_report(
    account: str,
    report: MonetizationDailyReport,
    store=None,
    dau: Optional[float] = None,
    prior_revenue: Optional[float] = None,
) -> Dict[str, Any]:
    """Assemble the structured growth report.

    dau / prior_revenue let callers supply Adjust-derived DAU and the
    previous day's revenue for a true Revenue/DAU and growth figure.
    """
    revenue = report.revenue
    impressions = report.impressions
    blended_ecpm = report.blended_ecpm

    # ---- DAU / Revenue-per-DAU ---------------------------------------- #
    if dau is None:
        dau = (report.user_metrics or {}).get("dau")
    if not dau:                      # None or 0 -> pending, never render "0"
        dau = None
    rpd = (revenue / dau) if dau else None
    prior_rpd = None
    if prior_revenue is not None and dau:
        prior_rpd = prior_revenue / dau
    growth_pct = None
    if prior_revenue is not None and prior_revenue > 0:
        growth_pct = (revenue - prior_revenue) / prior_revenue * 100.0

    # ---- experiment portfolio ----------------------------------------- #
    defs: List[Any] = []
    if store is not None:
        defs = list(store.load(account).values())
    running = [e for e in defs if e.status == APPLIED
               or (e.applied_at and e.decision == "")]
    winning = [e for e in defs if e.status == WINNER]
    rolled = [e for e in defs if e.status == ROLLBACK]
    memorized = [e for e in defs if e.status == MEMORIZED]

    # ---- A/B experiment portfolio ------------------------------------ #
    # Every tracked experiment is an A/B test on Revenue/DAU. Sum of the
    # hypothesized lifts is an *indicative pipeline upside* — only realized
    # and confirmed once each is applied and measured (never assumed).
    ab_total = len(defs)
    ab_revenue = sum(1 for e in defs if (e.ab_kind or "revenue") == "revenue")
    ab_hedge = sum(1 for e in defs if (e.ab_kind or "revenue") == "risk_hedge")
    ab_lift_sum = round(sum(
        (e.expected_lift_pct or 0.0) for e in defs
        if (e.ab_kind or "revenue") == "revenue"), 2)

    # ---- AI actions with measured impact ------------------------------ #
    actions: List[Dict[str, Any]] = []
    total_winner_lift = 0.0
    for e in winning:
        imp = e.impact or {}
        before = imp.get("before_rev_per_day", 0.0) or 0.0
        after = imp.get("after_rev_per_day", 0.0) or 0.0
        lift = after - before
        total_winner_lift += lift
        net = imp.get("net_impact_pct")
        actions.append({
            "title": e.title,
            "status": "WINNER",
            "lift_per_day": round(lift, 2),
            "net_impact_pct": net,
            "decision": e.decision or "KEEP",
        })
    for e in running:
        exp_impact = (e.params or {}).get("expected_impact", "")
        actions.append({
            "title": e.title,
            "status": "RUNNING",
            "lift_per_day": None,
            "net_impact_pct": None,
            "expected_impact": exp_impact,
            "applied_at": e.applied_at,
        })

    ai_lift_pct = (total_winner_lift / revenue * 100.0) if revenue > 0 else 0.0

    return {
        "account": account,
        "date": report.date,
        "dau": dau,
        "dau_pending": dau is None,
        "iia_revenue": round(revenue, 2),
        "revenue_per_dau": round(rpd, 4) if rpd is not None else None,
        "prior_revenue": prior_revenue,
        "prior_revenue_per_dau": round(prior_rpd, 4) if prior_rpd is not None else None,
        "growth_pct": round(growth_pct, 2) if growth_pct is not None else None,
        "blended_ecpm": round(blended_ecpm, 2),
        "impressions": impressions,
        "health_score": report.health_score,
        "health_grade": report.health_grade,
        "actions": actions,
        "total_winner_lift_per_day": round(total_winner_lift, 2),
        "ai_attributed_lift_pct": round(ai_lift_pct, 2),
        "experiments": {
            "running": len(running),
            "winning": len(winning),
            "rolled_back": len(rolled),
            "memorized": len(memorized),
        },
        "ab_portfolio": {
            "total": ab_total,
            "revenue_experiments": ab_revenue,
            "risk_hedges": ab_hedge,
            "expected_lift_sum_pct": ab_lift_sum,
        },
    }


def render_growth_markdown(r: Dict[str, Any]) -> str:
    dau = f"{r['dau']:,.0f}" if r["dau"] else "— (pending Adjust DAU)"
    rpd = (f"${r['revenue_per_dau']:.3f}"
           if r["revenue_per_dau"] is not None else "— (pending DAU)")
    prior = (_money(r["prior_revenue"]) if r["prior_revenue"] is not None
             else "—")
    growth = (_pct(r["growth_pct"]) if r["growth_pct"] is not None else "—")
    lines = [
        f"## 📈 IAA Growth Report — {r['account']}",
        "",
        f"> **昨天总览** · DAU {dau} · IAA收入 {_money(r['iia_revenue'])} "
        f"· AI贡献 +{r['ai_attributed_lift_pct']:.1f}% · "
        f"R/DAU {rpd} ({growth} vs 前日)",
        "",
        f"DATE: {r['date']}",
        f"DAU: {dau}",
        f"IAA Revenue: {_money(r['iia_revenue'])}",
        f"Revenue/DAU: {rpd}",
        f"Yesterday: {prior}   ({growth})",
        f"Blended eCPM: ${r['blended_ecpm']:.2f}   "
        f"Health: {r['health_score']} {r['health_grade']}",
        "",
        "--------------------------------",
        "",
        "AI Actions:",
    ]
    if not r["actions"]:
        lines.append("  (none live — system watching for opportunities)")
    for i, a in enumerate(r["actions"], 1):
        if a["status"] == "WINNER":
            lift = (f"+{_money(a['lift_per_day'])}/day"
                    if a["lift_per_day"] else "")
            net = (f" (net {_pct(a['net_impact_pct'])})"
                   if a["net_impact_pct"] is not None else "")
            lines.append(f"{i}. {a['title']}  Impact: {lift}{net}")
        else:
            exp = a.get("expected_impact", "")
            lines.append(f"{i}. {a['title']}  [RUNNING · observing] "
                         f"{('exp: ' + exp) if exp else ''}")
    lines += [
        "",
        f"Total measured lift (winners): "
        f"+{_money(r['total_winner_lift_per_day'])}/day",
        f"AI-attributed lift: +{r['ai_attributed_lift_pct']:.1f}% of revenue",
        "",
        f"Experiments: running {r['experiments']['running']} · "
        f"winning {r['experiments']['winning']} · "
        f"rolled-back {r['experiments']['rolled_back']} · "
        f"memorized {r['experiments']['memorized']}",
        "",
        f"A/B pipeline: {r['ab_portfolio']['total']} 实验 "
        f"（{r['ab_portfolio']['revenue_experiments']} 收入 / "
        f"{r['ab_portfolio']['risk_hedges']} 风险对冲）· "
        f"预估可释放 Revenue/DAU 提升 "
        f"{r['ab_portfolio']['expected_lift_sum_pct']:+.1f}%"
        f"（假设全部命中，需实测验证）",
    ]
    return "\n".join(lines)


def render_growth_card(r: Dict[str, Any]) -> str:
    """Compact one-block card body for Feishu — the operator's daily glance.

    Lead with the user's exact north-star view:
        '昨天：DAU · IAA收入 · AI贡献%'
    """
    dau = (f"{r['dau']:,.0f}" if r["dau"]
           else "—(pending DAU)")
    rev = f"${r['iia_revenue']:,.0f}"
    ai = f"+{r['ai_attributed_lift_pct']:.1f}%"
    rpd = (f"${r['revenue_per_dau']:.3f}"
           if r["revenue_per_dau"] is not None else "—(pending DAU)")
    growth = (_pct(r["growth_pct"]) if r["growth_pct"] is not None else "—")
    head = (f"📈 昨天 · {r['account']}\n"
            f"DAU {dau} · IAA收入 {rev} · AI贡献 {ai}\n"
            f"R/DAU {rpd} ({growth} vs 前日)")
    acts = ""
    for a in r["actions"]:
        if a["status"] == "WINNER":
            acts += f"  ✅ {a['title']} +${a['lift_per_day']:,.0f}/d\n"
        else:
            acts += f"  🔧 {a['title']} (observing)\n"
    ex = r["experiments"]
    foot = (f"exp ▶{ex['running']} 🏆{ex['winning']} "
            f"↩{ex['rolled_back']} 🧠{ex['memorized']} · "
            f"A/B 预估释放 {r['ab_portfolio']['expected_lift_sum_pct']:+.1f}%")
    return head + "\n" + (acts or "  (watching for opportunities)\n") + foot


__all__ = ["build_growth_report", "render_growth_markdown",
           "render_growth_card"]
