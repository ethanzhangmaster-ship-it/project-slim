"""
E15.1.2 — Real Fleet Bridge (Revenue OS -> Factory Brain)
=========================================================

The first REAL-DATA connection between the Revenue OS and the Factory
Brain. Reads the same cached MAX reports the daily monetization batch
already pulls (data/<ACCT>_report.json) plus the account user metrics
(outputs/user_metrics/<ACCT>.json), builds a per-app IAA economics view,
and asks GameDecisionEngine.evaluate_iaa for a fund-manager verdict on
every live game:

    SCALE  proven IAA winner -> replicate its pattern, protect waterfall
    KEEP   earns attention   -> optimise (waterfall / floors / show rate)
    FIX    ads fill but never show -> engineering ticket
    KILL   dead traffic or zombie monetization -> deprioritise

Design points:
    * Reuses operation.optimizer.analyzers.aggregate — Revenue OS math
      is never re-implemented here.
    * Per-app DAU is supported: when the user-metrics source supplies
      `app_dau` keyed by the MAX `application` id (Adjust per-app with a
      token->application mapping, or the manual drop-in `apps` block),
      every game gets its own Rev/DAU vs the north star ($0.03/DAU).
      Where per-app DAU is absent, the account-level Rev/DAU remains as
      the fallback context — fully backward compatible.
    * Zero writes, zero credentials: cached report files only.
      real_api_called is locked False.

CLI (run from launchforge/):
    python -m operation.factory_brain.fleet_bridge ACCT_2 ACCT_3
    -> prints the verdict card and writes outputs/fleet_verdicts/<date>.md
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from operation.optimizer.analyzers.aggregate import aggregate, totals

from .decision_engine import GameDecisionEngine
from .models import GameDecision

NORTH_STAR_RPD = 0.03          # $/DAU/day — whole-system north star

_VERDICT_ORDER = {"scale": 0, "keep": 1, "fix": 2, "kill": 3}
_VERDICT_LABEL = {
    "scale": "SCALE 赢家",
    "keep": "KEEP 优化",
    "fix": "FIX 修链路",
    "kill": "KILL 放弃",
}


# --------------------------------------------------------------------- #
# Data shapes
# --------------------------------------------------------------------- #
@dataclass
class FleetGame:
    """Per-app IAA economics derived from the raw MAX report."""
    app: str
    revenue: float = 0.0
    impressions: int = 0
    attempts: int = 0
    responses: int = 0
    days: int = 0
    share: float = 0.0             # of account revenue
    ecpm: float = 0.0
    ecpm_ratio: float = 0.0        # vs account blended eCPM
    attempts_per_day: float = 0.0
    show_rate: float = 0.0         # impressions / responses
    trend_pct: Optional[float] = None   # 2nd half vs 1st half revenue
    dau: Optional[float] = None         # per-app DAU (when available)
    rev_per_dau: Optional[float] = None  # per-app Rev/DAU vs north star

    def to_entry(self) -> dict:
        d = {
            "app": self.app, "revenue": self.revenue,
            "impressions": self.impressions, "attempts": self.attempts,
            "responses": self.responses, "days": self.days,
            "share": self.share, "ecpm": self.ecpm,
            "ecpm_ratio": self.ecpm_ratio,
            "attempts_per_day": self.attempts_per_day,
            "show_rate": self.show_rate,
        }
        if self.trend_pct is not None:
            d["trend_pct"] = self.trend_pct
        if self.dau is not None:
            d["dau"] = self.dau
        if self.rev_per_dau is not None:
            d["rev_per_dau"] = self.rev_per_dau
        return d

    def to_dict(self) -> dict:
        return self.to_entry()


@dataclass
class FleetVerdictReport:
    """One account's real-fleet verdict card."""
    account: str
    start: str = ""
    end: str = ""
    total_revenue: float = 0.0
    blended_ecpm: float = 0.0
    dau: Optional[float] = None            # account-level (Adjust/manual)
    arpdau: Optional[float] = None         # account revenue per DAU
    north_star: float = NORTH_STAR_RPD
    games: List[FleetGame] = field(default_factory=list)
    verdicts: List[GameDecision] = field(default_factory=list)
    real_api_called: bool = False          # locked False, forever

    @property
    def north_star_met(self) -> Optional[bool]:
        if self.arpdau is None:
            return None
        return self.arpdau >= self.north_star

    def counts(self) -> Dict[str, int]:
        c: Dict[str, int] = {}
        for v in self.verdicts:
            c[v.verdict] = c.get(v.verdict, 0) + 1
        return c

    def to_dict(self) -> dict:
        return {
            "account": self.account, "start": self.start, "end": self.end,
            "total_revenue": round(self.total_revenue, 2),
            "blended_ecpm": round(self.blended_ecpm, 2),
            "dau": self.dau, "arpdau": self.arpdau,
            "north_star": self.north_star,
            "north_star_met": self.north_star_met,
            "games": [g.to_dict() for g in self.games],
            "verdicts": [v.to_dict() for v in self.verdicts],
            "real_api_called": self.real_api_called,
        }


# --------------------------------------------------------------------- #
# Bridge
# --------------------------------------------------------------------- #
class RealFleetBridge:
    """Cached MAX report + account user metrics -> IAA verdict card."""

    def __init__(self, data_dir: str = "data",
                 metrics_dir: str = os.path.join("outputs", "user_metrics"),
                 engine: Optional[GameDecisionEngine] = None) -> None:
        self.data_dir = data_dir
        self.metrics_dir = metrics_dir
        self.engine = engine or GameDecisionEngine()

    # ---- loading ------------------------------------------------------ #
    def load_report(self, account: str) -> Optional[dict]:
        """data/<ACCT>_report.json -> {"account","start","end","rows"}.

        Accepts either the wrapped dict the daily batch writes or a bare
        list of rows. Malformed / missing -> None.
        """
        path = os.path.join(self.data_dir, f"{account}_report.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return None
        if isinstance(data, list):
            data = {"account": account, "start": "", "end": "",
                    "rows": data}
        if not isinstance(data, dict):
            return None
        rows = data.get("rows")
        if not isinstance(rows, list) or not rows:
            return None
        return data

    def load_user_metrics(self, account: str) -> dict:
        """outputs/user_metrics/<ACCT>.json -> {"dau","arpdau","app_dau"} or {}.

        `app_dau` maps the MAX `application` id -> average daily active
        users (read from either the `apps` or `app_dau` key).
        """
        path = os.path.join(self.metrics_dir, f"{account}.json")
        if not os.path.exists(path):
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        out: dict = {}
        dau = data.get("dau")
        if isinstance(dau, (int, float)) and dau > 0:
            out["dau"] = float(dau)
        hist = data.get("arpdau_history")
        if isinstance(hist, list) and hist:
            last = hist[-1]
            if isinstance(last, dict):
                arpdau = last.get("arpdau")
                if isinstance(arpdau, (int, float)) and arpdau > 0:
                    out["arpdau"] = float(arpdau)
        raw_apps = data.get("app_dau") or data.get("apps")
        app_dau: Dict[str, float] = {}
        if isinstance(raw_apps, dict):
            for k, v in raw_apps.items():
                dv = v.get("dau") if isinstance(v, dict) else v
                if isinstance(dv, (int, float)) and dv > 0:
                    app_dau[str(k)] = float(dv)
        if app_dau:
            out["app_dau"] = app_dau
        return out

    # ---- per-app economics -------------------------------------------- #
    @staticmethod
    def _trends(rows: List[dict]) -> Dict[str, Optional[float]]:
        """Per-app revenue trend: 2nd half of the window vs 1st half."""
        per_app_day: Dict[str, Dict[str, float]] = {}
        all_days: set = set()
        for r in rows:
            if not isinstance(r, dict):
                continue
            app = str(r.get("application") or "?")
            day = str(r.get("day") or "")
            try:
                rev = float(r.get("estimated_revenue") or 0.0)
            except (TypeError, ValueError):
                rev = 0.0
            per_app_day.setdefault(app, {})
            per_app_day[app][day] = per_app_day[app].get(day, 0.0) + rev
            if day:
                all_days.add(day)
        days_sorted = sorted(all_days)
        if len(days_sorted) < 4:
            return {a: None for a in per_app_day}
        half = len(days_sorted) // 2
        first, second = set(days_sorted[:half]), set(days_sorted[half:])
        out: Dict[str, Optional[float]] = {}
        for app, by_day in per_app_day.items():
            h1 = sum(v for d, v in by_day.items() if d in first)
            h2 = sum(v for d, v in by_day.items() if d in second)
            out[app] = (h2 - h1) / h1 if h1 > 0.005 else None
        return out

    def fleet_games(self, report: dict) -> List[FleetGame]:
        rows = [r for r in report.get("rows", []) if isinstance(r, dict)]
        stats = aggregate(rows, "application")
        t = totals(stats)
        tot_rev = t.revenue if t.revenue > 0 else 1e-9
        blended = (t.revenue / t.impressions * 1000.0
                   if t.impressions > 0 else 0.0)
        trends = self._trends(rows)
        games: List[FleetGame] = []
        for s in sorted(stats.values(), key=lambda x: -x.revenue):
            ecpm = (s.revenue / s.impressions * 1000.0
                    if s.impressions > 0 else 0.0)
            games.append(FleetGame(
                app=s.key,
                revenue=round(s.revenue, 4),
                impressions=s.impressions,
                attempts=s.attempts,
                responses=s.responses,
                days=s.days,
                share=s.revenue / tot_rev,
                ecpm=ecpm,
                ecpm_ratio=(ecpm / blended if blended > 0 else 0.0),
                attempts_per_day=s.attempts / max(1, s.days),
                show_rate=(s.impressions / s.responses
                           if s.responses > 0 else 0.0),
                trend_pct=trends.get(s.key),
            ))
        return games

    # ---- verdict card -------------------------------------------------- #
    def build(self, account: str) -> Optional[FleetVerdictReport]:
        report = self.load_report(account)
        if report is None:
            return None
        games = self.fleet_games(report)
        rows = [r for r in report.get("rows", []) if isinstance(r, dict)]
        stats = aggregate(rows, "application")
        t = totals(stats)
        um = self.load_user_metrics(account)
        # per-app DAU -> per-game Rev/DAU vs north star
        app_dau = um.get("app_dau") or {}
        for g in games:
            d = app_dau.get(g.app)
            if d:
                g.dau = d
                denom = d * max(1, g.days)
                g.rev_per_dau = (g.revenue / denom) if denom else None
        verdicts = self.engine.evaluate_iaa_fleet(
            [g.to_entry() for g in games])
        verdicts.sort(key=lambda v: (_VERDICT_ORDER.get(v.verdict, 9),
                                     -v.metric_snapshot.get("revenue", 0.0)))
        return FleetVerdictReport(
            account=str(report.get("account") or account),
            start=str(report.get("start") or ""),
            end=str(report.get("end") or ""),
            total_revenue=t.revenue,
            blended_ecpm=(t.revenue / t.impressions * 1000.0
                          if t.impressions > 0 else 0.0),
            dau=um.get("dau"),
            arpdau=um.get("arpdau"),
            games=games,
            verdicts=verdicts,
            real_api_called=False,
        )

    def build_all(self, accounts: List[str]) -> List[FleetVerdictReport]:
        out: List[FleetVerdictReport] = []
        for a in accounts:
            r = self.build(a)
            if r is not None:
                out.append(r)
        return out

    # ---- rendering ------------------------------------------------------ #
    @staticmethod
    def render_markdown(reports: List[FleetVerdictReport]) -> str:
        today = date.today().isoformat()
        lines: List[str] = [
            "# 真实舰队每日判决 · Real Fleet Verdicts",
            "",
            f"_生成 {today} · 数据源：MAX 缓存报表 + DAU（账号级 / 单游戏级，"
            f"零 API 写入，全部判决需人工确认）_",
            "",
        ]
        for r in reports:
            ns = ("✅ 达标" if r.north_star_met
                  else ("❌ 未达标" if r.north_star_met is not None
                        else "—（缺 DAU）"))
            arp = (f"${r.arpdau:.4f}" if r.arpdau is not None else "—")
            dau = (f"{r.dau:,.0f}" if r.dau is not None else "—")
            per_app = any(g.rev_per_dau is not None for g in r.games)
            lines += [
                f"## {r.account}  （{r.start} → {r.end}）",
                "",
                f"- 窗口营收 **${r.total_revenue:,.2f}** · 混合 eCPM "
                f"**${r.blended_ecpm:.2f}** · DAU {dau} · "
                f"Rev/DAU {arp}（北极星 ${r.north_star:.2f}：{ns}）"
                + (" · 含单游戏 Rev/DAU" if per_app else ""),
                "",
                "| 判决 | 游戏 | 单游戏 Rev/DAU | 理由 |",
                "|---|---|---|---|",
            ]
            game_by_id = {g.app: g for g in r.games}
            for v in r.verdicts:
                label = _VERDICT_LABEL.get(v.verdict, v.verdict)
                g = game_by_id.get(v.game_id)
                if g is not None and g.rev_per_dau is not None:
                    mark = "✅" if g.rev_per_dau >= r.north_star else "❌"
                    cell = f"{mark}${g.rev_per_dau:.4f}"
                else:
                    cell = "—"
                lines.append(f"| {label} | {v.game_id} | {cell} | {v.reason} |")
            c = r.counts()
            lines += [
                "",
                f"小结：SCALE {c.get('scale', 0)} · KEEP {c.get('keep', 0)}"
                f" · FIX {c.get('fix', 0)} · KILL {c.get('kill', 0)}",
                "",
            ]
        lines += [
            "---",
            "约束：`real_api_called=False`（永远）。所有判决 "
            "`requires_manual_apply=True` —— 大脑提案，人落子。",
            "",
        ]
        return "\n".join(lines)


def main(argv: List[str]) -> int:
    accounts = argv or ["ACCT_2", "ACCT_3"]
    bridge = RealFleetBridge()
    reports = bridge.build_all(accounts)
    if not reports:
        print("NO_DATA: no cached reports found for", accounts)
        return 1
    md = bridge.render_markdown(reports)
    out_dir = os.path.join("outputs", "fleet_verdicts")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{date.today().isoformat()}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    print(f"[saved] {out_path}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))


__all__ = ["FleetGame", "FleetVerdictReport", "RealFleetBridge",
           "NORTH_STAR_RPD"]
