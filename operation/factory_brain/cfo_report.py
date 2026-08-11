# -*- coding: utf-8 -*-
"""CFO Report — run the E16.1.x brain on REAL fleet data.

Reads real MAX Report API dumps (data/<ACCT>_report.json, pulled daily by the
09:30 automation) + real DAU metrics (outputs/user_metrics/<ACCT>.json), builds
per-game daily revenue series, then runs:

  * E16.1.2 RevenueForecaster  -> 7d/30d revenue forecast per game + fleet
  * E16.1.4 PortfolioIntelligence -> SCALE/MAINTAIN/REDUCE/SUNSET verdicts

Output: outputs/cfo_report/<date>.md — a real business report with real dollars.

Usage:
    python -m operation.factory_brain.cfo_report
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date as _date
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.revenue_intelligence.forecasting import RevenueForecaster  # noqa: E402
from src.revenue_intelligence.models import RevenueSnapshot  # noqa: E402
from src.revenue_intelligence.portfolio import (  # noqa: E402
    GamePortfolioEntry,
    PortfolioIntelligence,
)

ACCOUNTS = ["ACCT_1", "ACCT_2", "ACCT_3"]
DATA_DIR = ROOT / "data"
METRICS_DIR = ROOT / "outputs" / "user_metrics"
OUT_DIR = ROOT / "outputs" / "cfo_report"

# Below this total window revenue a title is noise, grouped into long tail.
TAIL_THRESHOLD = 1.0


def load_daily_series() -> Tuple[Dict[str, Dict[str, float]], Dict[str, str], str, str]:
    """Return {game: {day: revenue}}, {game: account}, window start, window end.

    MAX Report API lags 1-2 days: the final day of the window is always
    partially reported and would poison trend/forecast (fake decline).
    We drop the last day deterministically.
    """
    series: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    owner: Dict[str, str] = {}
    start = end = ""
    all_days: set = set()
    for acct in ACCOUNTS:
        fp = DATA_DIR / f"{acct}_report.json"
        if not fp.exists():
            continue
        d = json.loads(fp.read_text(encoding="utf-8"))
        start = min(start, d["start"]) if start else d["start"]
        end = max(end, d["end"]) if end else d["end"]
        for r in d.get("rows", []):
            app = (r.get("application") or "?").strip()
            rev = float(r.get("estimated_revenue") or 0)
            series[app][r["day"]] += rev
            all_days.add(r["day"])
            owner.setdefault(app, acct)
    # Drop trailing incomplete day
    if all_days:
        last_day = max(all_days)
        for app in list(series):
            series[app].pop(last_day, None)
            if not series[app]:
                del series[app]
        end = max((d for d in all_days if d != last_day), default=end)
    return series, owner, start, end


def load_dau() -> Dict[str, int]:
    dau: Dict[str, int] = {}
    for acct in ACCOUNTS:
        fp = METRICS_DIR / f"{acct}.json"
        if fp.exists():
            d = json.loads(fp.read_text(encoding="utf-8"))
            dau[acct] = int(d.get("dau") or 0)
    return dau


def trend_of(days: List[float]) -> str:
    if len(days) < 4:
        return "flat"
    half = len(days) // 2
    a, b = sum(days[:half]) / max(half, 1), sum(days[half:]) / max(len(days) - half, 1)
    if a <= 0 and b <= 0:
        return "flat"
    change = (b - a) / (a if a > 0 else 1)
    return "up" if change > 0.15 else ("down" if change < -0.15 else "flat")


def main() -> Path:
    series, owner, start, end = load_daily_series()
    acct_dau = load_dau()
    forecaster = RevenueForecaster()
    portfolio = PortfolioIntelligence()

    # ---- per-game aggregation ----
    games = []  # (name, acct, total, daily list sorted by day)
    tail_total = 0.0
    tail_count = 0
    for app, by_day in series.items():
        total = sum(by_day.values())
        if total < TAIL_THRESHOLD:
            tail_total += total
            tail_count += 1
            continue
        days = [v for _, v in sorted(by_day.items())]
        games.append((app, owner[app], total, sorted(by_day.items())))
    games.sort(key=lambda g: -g[2])

    fleet_total = sum(g[2] for g in games) + tail_total
    n_days = len({d for _, _, _, day_list in games for d, _ in day_list}) or 1

    # ---- fleet-level daily series & forecast ----
    fleet_by_day: Dict[str, float] = defaultdict(float)
    for _, _, _, day_list in games:
        for d, v in day_list:
            fleet_by_day[d] += v
    fleet_days = sorted(fleet_by_day.items())
    fleet_history = [
        RevenueSnapshot(game_id="FLEET", date=d, revenue_total=v, ad_revenue=v)
        for d, v in fleet_days
    ]
    fleet_fc = forecaster.forecast(fleet_history)

    # ---- per-game forecast + portfolio entries ----
    entries: List[GamePortfolioEntry] = []
    game_fc = {}
    for app, acct, total, day_list in games:
        history = [
            RevenueSnapshot(game_id=app, date=d, revenue_total=v, ad_revenue=v)
            for d, v in day_list
        ]
        fc = forecaster.forecast(history)
        game_fc[app] = fc
        daily_vals = [v for _, v in day_list]
        # No UA spend on these titles -> ad revenue is ~gross profit before
        # store/platform costs; use revenue as profit proxy, roas n/a -> 0.
        entries.append(
            GamePortfolioEntry(
                game_id=app,
                revenue=round(total, 2),
                profit=round(total, 2),
                roas=0.0,
                dau=acct_dau.get(acct, 0),
                trend=trend_of(daily_vals),
                genre=acct,  # account as coarse genre bucket
            )
        )
    report = portfolio.evaluate(entries)

    # ---- render ----
    today = _date.today().isoformat()
    lines = [
        f"# CFO 经营报告（真实数据） — {today}",
        "",
        f"数据源：AppLovin MAX Report API 真实报表，窗口 {start} → {end}（延迟1-2天）",
        "",
        "## 一、这段时间到底赚了多少钱",
        "",
        f"- **全舰队真实广告收入：${fleet_total:,.2f}**（{n_days} 天，日均 ${fleet_total / n_days:,.2f}）",
        f"- 有收入的游戏 {len(games)} 款；长尾 {tail_count} 款合计 ${tail_total:,.2f}（<$1，基本判死）",
        "",
        "| 游戏 | 账号 | 窗口收入 | 日均 | 趋势 |",
        "|---|---|---:|---:|---|",
    ]
    for app, acct, total, day_list in games:
        daily_vals = [v for _, v in day_list]
        lines.append(
            f"| {app} | {acct} | ${total:,.2f} | ${total / max(len(daily_vals), 1):,.2f} | {trend_of(daily_vals)} |"
        )

    lines += [
        "",
        "## 二、未来 30 天预测（E16.1.2 Forecaster，基于真实日序列）",
        "",
        f"- 全舰队：**未来7天 ≈ ${fleet_fc.next_7d_revenue:,.2f}，未来30天 ≈ ${fleet_fc.next_30d_revenue:,.2f}**"
        f"（趋势 {fleet_fc.trend}，置信 {fleet_fc.confidence:.2f}）",
    ]
    if fleet_fc.risk_flags:
        lines.append(f"- 风险旗标：{', '.join(fleet_fc.risk_flags)}")
    lines += ["", "| 游戏 | 7天预测 | 30天预测 | 趋势 | 置信 |", "|---|---:|---:|---|---:|"]
    for app, _, total, _ in games[:10]:
        fc = game_fc[app]
        lines.append(
            f"| {app} | ${fc.next_7d_revenue:,.2f} | ${fc.next_30d_revenue:,.2f} | {fc.trend} | {fc.confidence:.2f} |"
        )

    lines += [
        "",
        "## 三、组合判决（E16.1.4 Portfolio — 谁该加倍，谁该砍）",
        "",
        "| 游戏 | 判决 | 评分 | 理由 |",
        "|---|---|---:|---|",
    ]
    for dec in report.decisions:
        lines.append(
            f"| {dec.game_id} | **{dec.verdict.value if hasattr(dec.verdict, 'value') else dec.verdict}** "
            f"| {dec.score:.0f} | {dec.rationale} |"
        )

    lines += ["", "## 四、结论（人话）", ""]
    # deterministic plain-language conclusions from real numbers
    if games:
        top_name, top_acct, top_total, _ = games[0]
        top_share = top_total / fleet_total if fleet_total > 0 else 0
        lines.append(
            f"1. **这家公司目前本质上是一款游戏**：{top_name} 占全舰队收入 "
            f"{top_share:.0%}（${top_total:,.2f}）。它死，舰队死。"
        )
    from src.revenue_intelligence.portfolio import PortfolioVerdict

    scale_list = [d.game_id for d in report.decisions if d.verdict in (PortfolioVerdict.SCALE, PortfolioVerdict.REPLICATE)]
    sunset_list = [d.game_id for d in report.decisions if d.verdict == PortfolioVerdict.SUNSET]
    if scale_list:
        lines.append(
            f"2. **值得真金白银投入的只有 {len(scale_list)} 款**：{', '.join(scale_list)}。"
            f"其余维持或放弃。"
        )
    lines.append(
        f"3. **长尾是幻觉**：{tail_count} 款游戏合计 ${tail_total:,.2f}"
        f"（日均不足 ${tail_total / max(n_days, 1):.2f}），不值得任何维护时间。"
        + (f" 另有 {len(sunset_list)} 款建议停止维护：{', '.join(sunset_list[:5])}{'…' if len(sunset_list) > 5 else ''}。" if sunset_list else "")
    )
    lines.append(
        f"4. **未来 30 天全舰队预计 ${fleet_fc.next_30d_revenue:,.2f}**"
        f"（趋势 {fleet_fc.trend}）。当前月化收入 ≈ ${fleet_total / n_days * 30:,.0f}，"
        f"离一人公司可持续线还差一个量级——增量只能来自：给头部游戏买量试验，或复制头部模式做新游。"
    )
    lines.append("")
    out_path = OUT_DIR / f"{today}.md"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"written: {out_path}")
    print(f"fleet total ${fleet_total:,.2f} | 30d forecast ${fleet_fc.next_30d_revenue:,.2f}")
    return out_path


if __name__ == "__main__":
    main()
