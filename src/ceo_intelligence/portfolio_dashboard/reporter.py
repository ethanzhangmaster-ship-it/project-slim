"""E17.10 Portfolio Dashboard — renderers.

Two file-based views (Lean discipline: no server, no framework):
- ``to_markdown``  : CEO 全盘视图（中文晨读文档）
- ``to_html``      : 自包含静态 HTML 快照（inline CSS、<details> 折叠、
                     无外部依赖、浅色主题）

Deterministic: same dashboard -> identical bytes.
"""
from __future__ import annotations

import html as _html
from typing import Dict, List

from .models import GameStatus, PortfolioDashboard, RiskLevel

_STATUS_LABEL: Dict[str, str] = {
    "healthy": "🟢 健康",
    "attention": "🟡 需关注",
    "critical": "🔴 危急",
}

_GAME_STATUS_LABEL: Dict[GameStatus, str] = {
    GameStatus.HEALTHY: "🟢",
    GameStatus.ATTENTION: "🟡",
    GameStatus.CRITICAL: "🔴",
}

_KIND_LABEL: Dict[str, str] = {
    "auto": "🤖 已自动执行",
    "approval": "✋ 待审批",
    "block": "⛔ 已阻断",
}

_RISK_LABEL: Dict[RiskLevel, str] = {
    RiskLevel.HIGH: "🔴 高",
    RiskLevel.MEDIUM: "🟡 中",
    RiskLevel.LOW: "⚪ 低",
}


class PortfolioReporter:
    """Renders a PortfolioDashboard to Markdown and static HTML."""

    # ------------------------------------------------------------------ #
    # Markdown
    # ------------------------------------------------------------------ #
    def to_markdown(self, dash: PortfolioDashboard) -> str:
        k = dash.kpi
        lines: List[str] = []
        lines.append(f"# 组合仪表盘（Portfolio Dashboard）· {dash.date}")
        lines.append("")
        lines.append(
            f"**公司状态：{_STATUS_LABEL.get(dash.company_status, dash.company_status)}**"
        )
        lines.append("")
        lines.append("## 舰队 KPI")
        lines.append("")
        lines.append(f"- 在册游戏：**{k.total_games}** 款"
                     f"（🟢 {k.healthy_games} / 🟡 {k.attention_games} / 🔴 {k.critical_games}）")
        lines.append(f"- 舰队日收入：**${k.total_daily_revenue:,.2f}**")
        lines.append(f"- 舰队 DAU：**{k.total_dau:,}**")
        lines.append(f"- 舰队日花费：${k.total_spend:,.2f}（安装 {k.total_installs:,}）")
        lines.append(f"- 平均数据置信度：{k.avg_confidence:.0%}")
        lines.append(
            f"- 今日行动：🤖 自动 {k.auto_actions} / ✋ 待审批 {k.approval_actions}"
            f" / ⛔ 阻断 {k.blocked_actions}"
        )
        lines.append(
            f"- 自动执行预期收入影响：{k.expected_revenue_impact:+.1%}"
        )
        if k.portfolio_sim_p50 is not None:
            lines.append(f"- 组合模拟 p50（基线情景）：{k.portfolio_sim_p50:+.1%}")
        lines.append("")

        # tiles
        lines.append("## 游戏矩阵")
        lines.append("")
        lines.append(
            "| # | 游戏 | 状态 | 日收入 | DAU | ROAS | 置信度 | 首要动作 | 决策 | 闸门 | 优先分 |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for t in dash.tiles:
            rev = f"${t.daily_revenue:,.2f}" if t.daily_revenue is not None else "—"
            dau = f"{t.dau:,}" if t.dau is not None else "—"
            roas = f"{t.roas:.2f}" if t.roas is not None else "—"
            rank = str(t.rank) if t.rank else "—"
            lines.append(
                f"| {rank} | {t.game_id} | {_GAME_STATUS_LABEL[t.status]} "
                f"| {rev} | {dau} | {roas} | {t.confidence:.0%} "
                f"| {t.top_action or '—'} | {t.decision_type or '—'} "
                f"| {t.gate or '—'} | {t.priority_score:.4f} |"
            )
        lines.append("")

        # decision queue
        lines.append("## 决策队列")
        lines.append("")
        if not dash.decision_queue:
            lines.append("（今日无待处理决策）")
            lines.append("")
        else:
            for kind in ("approval", "block", "auto"):
                group = dash.queue_by_kind(kind)
                if not group:
                    continue
                lines.append(f"### {_KIND_LABEL[kind]}（{len(group)}）")
                lines.append("")
                for e in group:
                    detail = f" — {e.detail}" if e.detail else ""
                    lines.append(f"- **{e.game_id}**：{e.action}{detail}")
                lines.append("")

        # risk flags
        lines.append("## 风险旗标")
        lines.append("")
        if not dash.risk_flags:
            lines.append("（无风险旗标）")
            lines.append("")
        else:
            for f in dash.risk_flags:
                lines.append(
                    f"- {_RISK_LABEL[f.level]} | **{f.game_id}** | {f.domain} | {f.reason}"
                )
            lines.append("")

        # learned patterns
        lines.append("## 记忆图谱 · 已学到的模式")
        lines.append("")
        if dash.memory_summary:
            lines.append(f"> {dash.memory_summary}")
            lines.append("")
        if dash.learned_patterns:
            lines.append("| 策略 | 域 | 动作 | 样本 | 成功率 | 平均收入增量 | 置信加成 |")
            lines.append("|---|---|---|---|---|---|---|")
            for p in dash.learned_patterns:
                lines.append(
                    f"| {p.strategy_type} | {p.domain} | {p.action_type} "
                    f"| {p.samples} | {p.success_rate:.0%} "
                    f"| {p.avg_revenue_delta:+.1%} | +{p.confidence_boost:.0%} |"
                )
            lines.append("")
        elif not dash.memory_summary:
            lines.append("（暂无沉淀模式）")
            lines.append("")

        if dash.notes:
            lines.append("## 备注")
            lines.append("")
            for note in dash.notes:
                lines.append(f"- {note}")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # HTML (self-contained, light theme, zero external deps)
    # ------------------------------------------------------------------ #
    def to_html(self, dash: PortfolioDashboard) -> str:
        k = dash.kpi
        esc = _html.escape

        status_color = {
            "healthy": "#16a34a",
            "attention": "#d97706",
            "critical": "#dc2626",
        }.get(dash.company_status, "#334155")

        tile_rows: List[str] = []
        for t in dash.tiles:
            rev = f"${t.daily_revenue:,.2f}" if t.daily_revenue is not None else "—"
            dau = f"{t.dau:,}" if t.dau is not None else "—"
            roas = f"{t.roas:.2f}" if t.roas is not None else "—"
            rank = str(t.rank) if t.rank else "—"
            tile_rows.append(
                "<tr>"
                f"<td>{rank}</td>"
                f"<td class='gid'>{esc(t.game_id)}</td>"
                f"<td>{_GAME_STATUS_LABEL[t.status]}</td>"
                f"<td>{rev}</td><td>{dau}</td><td>{roas}</td>"
                f"<td>{t.confidence:.0%}</td>"
                f"<td>{esc(t.top_action) or '—'}</td>"
                f"<td>{esc(t.decision_type) or '—'}</td>"
                f"<td>{esc(t.gate) or '—'}</td>"
                f"<td>{t.priority_score:.4f}</td>"
                "</tr>"
            )

        queue_sections: List[str] = []
        for kind in ("approval", "block", "auto"):
            group = dash.queue_by_kind(kind)
            if not group:
                continue
            items = "".join(
                f"<li><b>{esc(e.game_id)}</b>：{esc(e.action)}"
                + (f" — <span class='muted'>{esc(e.detail)}</span>" if e.detail else "")
                + "</li>"
                for e in group
            )
            open_attr = " open" if kind == "approval" else ""
            queue_sections.append(
                f"<details{open_attr}><summary>{_KIND_LABEL[kind]}（{len(group)}）"
                f"</summary><ul>{items}</ul></details>"
            )
        queue_html = "".join(queue_sections) or "<p class='muted'>今日无待处理决策</p>"

        flag_items = "".join(
            f"<li>{_RISK_LABEL[f.level]} | <b>{esc(f.game_id)}</b> | "
            f"{esc(f.domain)} | {esc(f.reason)}</li>"
            for f in dash.risk_flags
        )
        flags_html = (
            f"<ul>{flag_items}</ul>" if flag_items else "<p class='muted'>无风险旗标</p>"
        )

        pattern_rows = "".join(
            "<tr>"
            f"<td>{esc(p.strategy_type)}</td><td>{esc(p.domain)}</td>"
            f"<td>{esc(p.action_type)}</td><td>{p.samples}</td>"
            f"<td>{p.success_rate:.0%}</td><td>{p.avg_revenue_delta:+.1%}</td>"
            f"<td>+{p.confidence_boost:.0%}</td>"
            "</tr>"
            for p in dash.learned_patterns
        )
        memory_html = ""
        if dash.memory_summary:
            memory_html += f"<p class='memo'>{esc(dash.memory_summary)}</p>"
        if pattern_rows:
            memory_html += (
                "<table><thead><tr><th>策略</th><th>域</th><th>动作</th>"
                "<th>样本</th><th>成功率</th><th>平均收入增量</th><th>置信加成</th>"
                f"</tr></thead><tbody>{pattern_rows}</tbody></table>"
            )
        if not memory_html:
            memory_html = "<p class='muted'>暂无沉淀模式</p>"

        sim_line = (
            f"<div class='kpi'><div class='kv'>{k.portfolio_sim_p50:+.1%}</div>"
            "<div class='kl'>组合模拟 p50（基线）</div></div>"
            if k.portfolio_sim_p50 is not None
            else ""
        )

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Portfolio Dashboard · {esc(dash.date)}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin: 0; padding: 24px; background: #f8fafc; color: #0f172a;
         font-family: "Segoe UI", "Microsoft YaHei", system-ui, sans-serif; }}
  .wrap {{ max-width: 1080px; margin: 0 auto; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  h2 {{ font-size: 16px; margin: 28px 0 10px; border-left: 4px solid #2563eb;
       padding-left: 8px; }}
  .status {{ display: inline-block; padding: 2px 10px; border-radius: 999px;
            color: #fff; font-size: 13px; background: {status_color}; }}
  .kpis {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 14px; }}
  .kpi {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px;
         padding: 12px 16px; min-width: 130px; }}
  .kv {{ font-size: 20px; font-weight: 700; }}
  .kl {{ font-size: 12px; color: #64748b; margin-top: 2px; }}
  table {{ border-collapse: collapse; width: 100%; background: #ffffff;
          font-size: 13px; }}
  th, td {{ border: 1px solid #e2e8f0; padding: 6px 8px; text-align: left; }}
  th {{ background: #f1f5f9; }}
  .gid {{ font-weight: 600; }}
  details {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px;
            padding: 8px 12px; margin: 8px 0; }}
  summary {{ cursor: pointer; font-weight: 600; }}
  .muted {{ color: #64748b; }}
  .memo {{ background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px;
          padding: 8px 12px; }}
  footer {{ margin-top: 28px; font-size: 12px; color: #94a3b8; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>组合仪表盘 · {esc(dash.date)}</h1>
  <span class="status">{_STATUS_LABEL.get(dash.company_status, esc(dash.company_status))}</span>

  <div class="kpis">
    <div class="kpi"><div class="kv">{k.total_games}</div>
      <div class="kl">在册游戏（🟢{k.healthy_games} 🟡{k.attention_games} 🔴{k.critical_games}）</div></div>
    <div class="kpi"><div class="kv">${k.total_daily_revenue:,.2f}</div>
      <div class="kl">舰队日收入</div></div>
    <div class="kpi"><div class="kv">{k.total_dau:,}</div>
      <div class="kl">舰队 DAU</div></div>
    <div class="kpi"><div class="kv">${k.total_spend:,.2f}</div>
      <div class="kl">舰队日花费</div></div>
    <div class="kpi"><div class="kv">{k.avg_confidence:.0%}</div>
      <div class="kl">平均数据置信度</div></div>
    <div class="kpi"><div class="kv">{k.auto_actions}/{k.approval_actions}/{k.blocked_actions}</div>
      <div class="kl">自动 / 待审批 / 阻断</div></div>
    <div class="kpi"><div class="kv">{k.expected_revenue_impact:+.1%}</div>
      <div class="kl">自动执行预期收入影响</div></div>
    {sim_line}
  </div>

  <h2>游戏矩阵</h2>
  <table>
    <thead><tr><th>#</th><th>游戏</th><th>状态</th><th>日收入</th><th>DAU</th>
    <th>ROAS</th><th>置信度</th><th>首要动作</th><th>决策</th><th>闸门</th>
    <th>优先分</th></tr></thead>
    <tbody>{"".join(tile_rows)}</tbody>
  </table>

  <h2>决策队列</h2>
  {queue_html}

  <h2>风险旗标</h2>
  {flags_html}

  <h2>记忆图谱 · 已学到的模式</h2>
  {memory_html}

  <footer>LaunchForge E17.10 Portfolio Dashboard · 确定性文件快照 · 无外部依赖</footer>
</div>
</body>
</html>
"""


__all__ = ["PortfolioReporter"]
