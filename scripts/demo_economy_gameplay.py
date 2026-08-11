"""Economy & Gameplay Analyzers — 完整 Mock 演示.

构造丰富的 mock 数据，运行经济系统分析器和玩法分析器，
输出格式化的分析报告，展示完整的洞察与建议。

运行: python scripts/demo_economy_gameplay.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime

sys.path.insert(0, "src")

from market_ops.creative_vision_runtime.reality.analyzers import (
    EconomyAnalyzer,
    EconomySnapshot,
    GameplayAnalyzer,
    GameplaySnapshot,
)


# ---------------------------------------------------------------------------
# 报告渲染工具
# ---------------------------------------------------------------------------

# ANSI 颜色码（Windows 10+ 支持）
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


def enable_ansi_colors() -> None:
    """Windows 启用 ANSI 颜色支持。"""
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)


def banner(title: str, color: str = C.CYAN) -> None:
    line = "═" * 70
    print(f"\n{color}{C.BOLD}{line}")
    print(f"  {title}")
    print(f"{line}{C.RESET}")


def section(title: str, color: str = C.BLUE) -> None:
    print(f"\n{color}{C.BOLD}┌─ {title} {'─' * max(1, 60 - len(title))}{C.RESET}")
    print(f"{color}{C.BOLD}└{C.RESET}")


def metric(label: str, value: str, status: str = "", indent: int = 2) -> None:
    """打印单个指标。"""
    pad = " " * indent
    status_color = {
        "good": C.GREEN,
        "warn": C.YELLOW,
        "bad": C.RED,
        "info": C.GRAY,
        "": "",
    }.get(status, "")
    status_icon = {
        "good": "✓",
        "warn": "⚠",
        "bad": "✗",
        "info": "ℹ",
        "": "",
    }.get(status, "")
    status_reset = C.RESET if status_color else ""
    print(f"{pad}{label:<35} {status_color}{status_icon} {value}{status_reset}")


def insight(text: str, idx: int) -> None:
    """打印洞察条目。"""
    print(f"  {C.YELLOW}💡 [{idx}]{C.RESET} {text}")


def table_row(cols: list[str], widths: list[int]) -> None:
    cells = []
    for col, w in zip(cols, widths):
        cells.append(f"{col:<{w}}")
    print(f"  {C.GRAY}│{C.RESET} " + f" {C.GRAY}│{C.RESET} ".join(cells) + f" {C.GRAY}│{C.RESET}")


def table_sep(widths: list[int]) -> None:
    parts = ["─" * (w + 2) for w in widths]
    print(f"  {C.GRAY}┌{'┬'.join(parts)}┐{C.RESET}")


def table_bot(widths: list[int]) -> None:
    parts = ["─" * (w + 2) for w in widths]
    print(f"  {C.GRAY}└{'┴'.join(parts)}┘{C.RESET}")


def status_color(status: str) -> str:
    return {
        "balanced": C.GREEN,
        "inflation": C.RED,
        "deflation": C.YELLOW,
        "healthy": C.GREEN,
        "choke_point": C.RED,
        "too_easy": C.YELLOW,
        "too_steep": C.RED,
        "too_flat": C.YELLOW,
    }.get(status, C.GRAY)


def status_icon(status: str) -> str:
    return {
        "balanced": "✓",
        "inflation": "↑",
        "deflation": "↓",
        "healthy": "✓",
        "choke_point": "✗",
        "too_easy": "○",
    }.get(status, "·")


# ---------------------------------------------------------------------------
# 经济系统分析报告
# ---------------------------------------------------------------------------

def render_economy_report(snapshot: EconomySnapshot) -> None:
    banner(f"💰 经济系统分析报告  |  Project #{snapshot.project_id}", C.MAGENTA)

    print(f"\n  {C.GRAY}分析周期: {snapshot.period_start} → {snapshot.period_end}{C.RESET}")

    # ── 整体状态 ──────────────────────────────────────
    section("整体经济状态")
    overall_color = status_color(snapshot.overall_status)
    metric("整体状态", f"{overall_color}{snapshot.overall_status.upper()}{C.RESET}",
           "good" if snapshot.overall_status == "balanced" else "bad")
    metric("平均通胀率", f"{snapshot.avg_inflation_rate:+.1%}",
           "good" if abs(snapshot.avg_inflation_rate) < 0.20 else "warn")
    metric("异常资源数", f"{len(snapshot.imbalanced_resources)} / {len(snapshot.resources)}")
    metric("通胀资源", ", ".join(snapshot.inflation_resources) or "无", "bad" if snapshot.inflation_resources else "good")
    metric("通缩资源", ", ".join(snapshot.deflation_resources) or "无", "warn" if snapshot.deflation_resources else "good")

    # ── 付费与经济关系 ──────────────────────────────────
    section("付费与经济关系")
    metric("付费/非付费资源比", f"{snapshot.payer_resource_ratio:.1f}x",
           "warn" if snapshot.payer_resource_ratio > 3.0 else "good")
    metric("资源囤积者数量", f"{snapshot.resource_hoarder_count:,}", "warn")
    metric("资源匮乏者数量", f"{snapshot.resource_starved_count:,}", "warn")

    # ── 各资源详情表 ──────────────────────────────────
    section("各资源产出/消耗详情")

    widths = [12, 12, 12, 10, 10, 8]
    headers = ["资源", "总产出", "总消耗", "净余额", "通胀率", "状态"]
    table_sep(widths)
    table_row(headers, widths)
    sep_parts = ["─" * (w + 2) for w in widths]
    print(f"  {C.GRAY}├{'┼'.join(sep_parts)}┤{C.RESET}")

    for flow in snapshot.resources:
        sc = status_color(flow.status)
        si = status_icon(flow.status)
        cols = [
            f"{C.BOLD}{flow.resource_name}{C.RESET}",
            f"{flow.total_source:>10,.0f}",
            f"{flow.total_sink:>10,.0f}",
            f"{flow.net_balance:>+10,.0f}",
            f"{flow.inflation_rate:>+9.1%}",
            f"{sc}{si} {flow.status}{C.RESET}",
        ]
        table_row(cols, widths)
    table_bot(widths)

    # ── Top 来源 / 去向 ────────────────────────────────
    section("资源产出/消耗 Top 3")
    for flow in snapshot.resources:
        print(f"\n  {C.BOLD}{C.CYAN}● {flow.resource_name}{C.RESET} "
              f"({status_color(flow.status)}{flow.status}{C.RESET})")
        print(f"    {C.GREEN}产出来源:{C.RESET}")
        for name, value in flow.top_sources:
            bar = "█" * int(value / max(v for _, v in flow.top_sources) * 20) if flow.top_sources else ""
            print(f"      {name:<12} {value:>10,.0f}  {C.GREEN}{bar}{C.RESET}")
        print(f"    {C.RED}消耗去向:{C.RESET}")
        for name, value in flow.top_sinks:
            bar = "█" * int(value / max(v for _, v in flow.top_sinks) * 20) if flow.top_sinks else ""
            print(f"      {name:<12} {value:>10,.0f}  {C.RED}{bar}{C.RESET}")

    # ── 洞察 ──────────────────────────────────────────
    section("经济系统洞察与建议")
    if not snapshot.insights:
        print(f"  {C.GRAY}（无洞察）{C.RESET}")
    for i, text in enumerate(snapshot.insights, 1):
        insight(text, i)


# ---------------------------------------------------------------------------
# 玩法分析报告
# ---------------------------------------------------------------------------

def render_gameplay_report(snapshot: GameplaySnapshot) -> None:
    banner(f"🎮 玩法分析报告  |  Project #{snapshot.project_id}", C.CYAN)

    print(f"\n  {C.GRAY}分析周期: {snapshot.period_start} → {snapshot.period_end}{C.RESET}")

    # ── 整体活跃与会话 ──────────────────────────────────
    section("整体活跃与会话")
    metric("活跃玩家数", f"{snapshot.total_players:,}")
    metric("平均会话时长", f"{snapshot.avg_session_len:.0f}s ({snapshot.avg_session_len/60:.1f}min)",
           "warn" if snapshot.avg_session_len < 180 else "good")
    metric("人均会话数", f"{snapshot.avg_sessions_per_user:.1f}")

    # ── 难度曲线评价 ──────────────────────────────────
    section("难度曲线评价")
    curve_color = status_color(snapshot.difficulty_curve)
    curve_status = {
        "healthy": ("健康", "good"),
        "too_steep": ("过陡", "bad"),
        "too_flat": ("过平", "warn"),
    }.get(snapshot.difficulty_curve, (snapshot.difficulty_curve, ""))
    metric("难度曲线", f"{curve_color}{curve_status[0]}{C.RESET}", curve_status[1])
    metric("卡点关卡数", f"{len(snapshot.choke_points)} / {len(snapshot.levels)}",
           "bad" if len(snapshot.choke_points) >= 3 else "warn" if snapshot.choke_points else "good")
    metric("流失关卡数", f"{len(snapshot.churn_levels)}",
           "bad" if len(snapshot.churn_levels) >= 2 else "warn" if snapshot.churn_levels else "good")

    # ── 关卡表现详情表 ──────────────────────────────────
    section("关卡通过率详情")

    widths = [12, 10, 10, 10, 10, 12, 10, 10]
    headers = ["关卡", "尝试", "通过", "通过率", "平均尝试", "流失率", "时长(s)", "状态"]
    table_sep(widths)
    table_row(headers, widths)
    sep_parts = ["─" * (w + 2) for w in widths]
    print(f"  {C.GRAY}├{'┼'.join(sep_parts)}┤{C.RESET}")

    max_attempts = max((l.attempts for l in snapshot.levels), default=1)
    for level in snapshot.levels:
        sc = status_color(level.status)
        si = status_icon(level.status)
        # 通过率柱状图
        bar_len = int(level.pass_rate * 15)
        bar = C.GREEN + "█" * bar_len + C.GRAY + "░" * (15 - bar_len) + C.RESET
        cols = [
            f"{C.BOLD}{level.level_id}{C.RESET}",
            f"{level.attempts:>8,}",
            f"{level.passes:>8,}",
            f"{bar} {level.pass_rate:>5.0%}",
            f"{level.avg_attempts:>8.1f}",
            f"{level.churn_rate:>10.0%}",
            f"{level.avg_duration_s:>8.0f}",
            f"{sc}{si} {level.status}{C.RESET}",
        ]
        table_row(cols, widths)
    table_bot(widths)

    # ── 玩法模式参与度 ──────────────────────────────────
    section("玩法模式参与度")

    widths_m = [16, 12, 12, 12, 12, 12]
    headers_m = ["玩法模式", "参与人数", "总场次", "人均场次", "平均时长", "留存提升"]
    table_sep(widths_m)
    table_row(headers_m, widths_m)
    sep_parts = ["─" * (w + 2) for w in widths_m]
    print(f"  {C.GRAY}├{'┼'.join(sep_parts)}┤{C.RESET}")

    max_part = max((m.participants for m in snapshot.modes), default=1)
    for mode in snapshot.modes:
        lift_color = C.GREEN if mode.retention_lift > 0.10 else C.GRAY
        lift_str = f"{lift_color}{mode.retention_lift:+.0%}{C.RESET}" if mode.retention_lift != 0 else "—"
        cols = [
            f"{C.BOLD}{mode.mode_name}{C.RESET}",
            f"{mode.participants:>10,}",
            f"{mode.sessions:>10,}",
            f"{mode.avg_sessions:>10.1f}",
            f"{mode.avg_duration_s:>10.0f}s",
            f"{lift_str:>12}",
        ]
        table_row(cols, widths_m)
    table_bot(widths_m)

    # ── 热门玩法 ──────────────────────────────────────
    section("最受欢迎玩法 Top 3")
    for i, mode_name in enumerate(snapshot.popular_modes[:3], 1):
        mode = next((m for m in snapshot.modes if m.mode_name == mode_name), None)
        if mode:
            bar_len = int(mode.participants / max_part * 25)
            print(f"  {C.BOLD}{i}.{C.RESET} {mode_name:<12} "
                  f"{C.CYAN}{mode.participants:>6,}{C.RESET} "
                  f"{C.GRAY}({mode.sessions:,} 场次){C.RESET} "
                  f"{C.CYAN}{'█' * bar_len}{C.RESET}")

    # ── 玩家行为热度 ──────────────────────────────────
    section("玩家行为热度 Top 5")
    if snapshot.top_actions:
        max_count = max(c for _, c in snapshot.top_actions)
        for action, count in snapshot.top_actions:
            bar_len = int(count / max_count * 25)
            print(f"  {action:<12} {count:>10,}  {C.MAGENTA}{'█' * bar_len}{C.RESET}")

    # ── 洞察 ──────────────────────────────────────────
    section("玩法洞察与建议")
    if not snapshot.insights:
        print(f"  {C.GRAY}（无洞察）{C.RESET}")
    for i, text in enumerate(snapshot.insights, 1):
        insight(text, i)


# ---------------------------------------------------------------------------
# JSON 完整输出
# ---------------------------------------------------------------------------

def export_json(
    economy: EconomySnapshot,
    gameplay: GameplaySnapshot,
    path: str = "scripts/economy_gameplay_report.json",
) -> None:
    """导出完整 JSON 报告。"""
    report = {
        "report_generated_at": datetime.now().isoformat(),
        "project_id": economy.project_id,
        "economy": economy.to_dict(),
        "gameplay": gameplay.to_dict(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n{C.GREEN}✓{C.RESET} JSON 报告已导出: {C.BOLD}{path}{C.RESET}")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main() -> None:
    enable_ansi_colors()

    project_id = 102
    lookback_days = 30

    print(f"\n{C.BOLD}╔════════════════════════════════════════════════════════════════╗")
    print(f"║  Phase 4 演示 — Economy & Gameplay Analyzers (Mock Mode)       ║")
    print(f"║  Project #{project_id}  |  Lookback: {lookback_days} days                       ║")
    print(f"╚════════════════════════════════════════════════════════════════╝{C.RESET}")

    start_ts = datetime.now()

    # ── 1. 运行经济系统分析器 ──────────────────────────
    print(f"\n{C.GRAY}[{datetime.now().strftime('%H:%M:%S')}] ⏳ 运行 EconomyAnalyzer...{C.RESET}")
    economy_analyzer = EconomyAnalyzer()
    economy_snapshot = economy_analyzer.analyze(
        project_id=project_id,
        lookback_days=lookback_days,
    )
    elapsed_e = (datetime.now() - start_ts).total_seconds()
    print(f"{C.GRAY}[{datetime.now().strftime('%H:%M:%S')}] {C.GREEN}✓{C.RESET} "
          f"EconomyAnalyzer 完成 ({elapsed_e:.2f}s, analyzed={economy_analyzer.total_analyzed})")

    # ── 2. 运行玩法分析器 ──────────────────────────────
    start_g = datetime.now()
    print(f"\n{C.GRAY}[{datetime.now().strftime('%H:%M:%S')}] ⏳ 运行 GameplayAnalyzer...{C.RESET}")
    gameplay_analyzer = GameplayAnalyzer()
    gameplay_snapshot = gameplay_analyzer.analyze(
        project_id=project_id,
        lookback_days=lookback_days,
    )
    elapsed_g = (datetime.now() - start_g).total_seconds()
    print(f"{C.GRAY}[{datetime.now().strftime('%H:%M:%S')}] {C.GREEN}✓{C.RESET} "
          f"GameplayAnalyzer 完成 ({elapsed_g:.2f}s, analyzed={gameplay_analyzer.total_analyzed})")

    # ── 3. 渲染报告 ────────────────────────────────────
    render_economy_report(economy_snapshot)
    render_gameplay_report(gameplay_snapshot)

    # ── 4. 汇总 ────────────────────────────────────────
    banner("📊 汇总", C.BOLD)
    metric("经济整体状态", economy_snapshot.overall_status.upper(),
           "good" if economy_snapshot.overall_status == "balanced" else "bad")
    metric("平均通胀率", f"{economy_snapshot.avg_inflation_rate:+.1%}",
           "good" if abs(economy_snapshot.avg_inflation_rate) < 0.20 else "warn")
    metric("通胀资源数", str(len(economy_snapshot.inflation_resources)), "bad" if economy_snapshot.inflation_resources else "good")
    metric("通缩资源数", str(len(economy_snapshot.deflation_resources)), "warn" if economy_snapshot.deflation_resources else "good")
    metric("难度曲线", gameplay_snapshot.difficulty_curve,
           "good" if gameplay_snapshot.difficulty_curve == "healthy" else "warn")
    metric("卡点关卡", ", ".join(gameplay_snapshot.choke_points) or "无",
           "bad" if gameplay_snapshot.choke_points else "good")
    metric("流失关卡", ", ".join(gameplay_snapshot.churn_levels) or "无",
           "warn" if gameplay_snapshot.churn_levels else "good")
    metric("热门玩法 Top1", gameplay_snapshot.popular_modes[0] if gameplay_snapshot.popular_modes else "—")
    metric("经济洞察数", str(len(economy_snapshot.insights)))
    metric("玩法洞察数", str(len(gameplay_snapshot.insights)))

    total_elapsed = (datetime.now() - start_ts).total_seconds()
    print(f"\n{C.GRAY}总耗时: {total_elapsed:.2f}s{C.RESET}")

    # ── 5. 导出 JSON ───────────────────────────────────
    export_json(economy_snapshot, gameplay_snapshot)

    print(f"\n{C.GREEN}{C.BOLD}✓ 演示完成{C.RESET}\n")


if __name__ == "__main__":
    main()
