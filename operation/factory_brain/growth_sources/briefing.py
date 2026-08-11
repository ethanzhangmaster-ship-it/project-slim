"""
E15.1.2 — Growth weekly briefing
=================================

Turns the discovered market opportunities into a human-readable weekly
card and (optionally) pushes it to Feishu — zero clicks for the operator.

Pipeline (all local, zero API writes):
    1. run the growth sources (mock + real-if-configured)
    2. merge + rank (handled by MarketOpportunityIngester)
    3. render a markdown briefing of the top-N opportunities
    4. persist outputs/growth/<date>.md
    5. push a Feishu interactive card (best-effort; missing webhook /
       rate-limit is caught and reported, never fatal)

This is fully deterministic and side-effect free on any external system:
``real_api_called`` is locked ``False``.
"""
from __future__ import annotations

import os
from datetime import date
from typing import Dict, List, Optional

from .ingester import MarketOpportunityIngester, build_default_sources, build_pipeline_sources
from .base import MarketSource


def build_markdown(report: Dict[str, object],
                   top_n: int = 5,
                   today: Optional[date] = None) -> str:
    """Render the discovery report as a Feishu-friendly markdown card."""
    today = today or date.today()
    datestr = today.isoformat()
    sources: List[Dict[str, object]] = list(report.get("sources", []))  # type: ignore[assignment]
    opps: List[Dict[str, object]] = list(report.get("opportunities", []))  # type: ignore[assignment]

    real_fetched = sum(
        int(s.get("count", 0) or 0)
        for s in sources if s.get("kind") == "real")
    mock_fetched = sum(
        int(s.get("count", 0) or 0)
        for s in sources if s.get("kind") == "mock")
    if real_fetched > 0:
        data_note = "真实市场信号已接入（mock + 真实源合并）"
    else:
        data_note = ("mock 信号（真实市场源未配置；接入后自动替换，"  # noqa: E501
                     "流程不变）")

    lines: List[str] = [
        f"# 🎮 每周新游戏机会（自动发现）",
        "",
        f"_生成 {datestr} · 数据源：Growth OS（{data_note}）_",
        "",
        f"共发现 **{len(opps)}** 条去重机会，按综合分排序，Top {top_n}：",
        "",
        "| # | 机会 | 来源 | 综合分 | 目标市场 | 信号 |",
        "|---|---|---|---|---|---|",
    ]
    for i, o in enumerate(opps[:top_n], 1):
        oid = str(o.get("opportunity_id", ""))
        # Mock opportunities normalize source -> "growth_os" (drop-in
        # semantics); the unambiguous mock marker is the "mock_" id prefix
        # (or a literal [MOCK] in the note), so the operator never
        # mistakes demo signals for real market intelligence.
        is_mock = oid.startswith("mock_") or "[MOCK]" in oid \
            or str(o.get("notes", "")).startswith("[MOCK]")
        tag = "[MOCK]" if is_mock else str(o.get("source", ""))
        genre = str(o.get("genre", ""))
        theme = str(o.get("theme", ""))
        combo = f"{genre} × {theme}" if theme else genre
        score = float(o.get("score", 0.0))
        geos = ",".join(o.get("target_geos", ["US"]) or ["US"])  # type: ignore[arg-type]
        note = str(o.get("notes", "") or "").replace("\n", " ").strip()
        if len(note) > 48:
            note = note[:45] + "..."
        lines.append(
            f"| {i} | {combo} | {tag} | {score:.3f} | {geos} | {note} |")

    lines += [
        "",
        "---",
        "",
        "- 🟢 已落盘 `data/market_opportunities.json`，Factory Brain 自动进入 spec 流水线",
        "- 🔧 真市场源（App Store 排名 / TikTok 话题 / Sensor Tower 等）接入后，",
        "  仅需注册一个 adapter + 配 endpoint，整条链路不动",
        "- 📌 本卡为只读发现，未对任一外部系统执行写操作",
        "",
    ]
    return "\n".join(lines)


def run(notify: bool = True,
        dry_run: bool = False,
        top_n: int = 5,
        out_dir: str = "outputs/growth",
        today: Optional[date] = None,
        sources: Optional[List[MarketSource]] = None) -> Dict[str, object]:
    """Run the growth discovery, write a briefing, push a Feishu card.

    Args:
        sources: Source list; defaults to ``build_default_sources()``
                 (mock + real seam). Pass ``build_pipeline_sources()`` to
                 also include public-chart data.

    Returns a report dict:
        {report, markdown, file, notified, notify_error, real_api_called}
    """
    today = today or date.today()
    datestr = today.isoformat()
    if sources is None:
        sources = build_default_sources()

    ing = MarketOpportunityIngester(sources)
    report = ing.run(dry_run=dry_run)  # ingester handles drop-in write
    md = build_markdown(report, top_n=top_n, today=today)

    out_path = os.path.join(out_dir, f"{datestr}.md")
    if not dry_run:
        os.makedirs(out_dir, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(md)

    notified = False
    notify_error: Optional[str] = None
    if notify:
        try:
            from operation.optimizer.notify.feishu import send_markdown_card
            res = send_markdown_card(
                f"🎮 每周新游机会 {datestr}", md, color="green")
            notified = res is not None
        except Exception as exc:  # noqa: BLE001 — webhook missing / rate-limit
            notify_error = f"{type(exc).__name__}: {exc}"

    return {
        "report": report,
        "markdown": md,
        "file": (out_path if not dry_run else None),
        "notified": notified,
        "notify_error": notify_error,
        "real_api_called": False,
    }


__all__ = ["build_markdown", "run"]
