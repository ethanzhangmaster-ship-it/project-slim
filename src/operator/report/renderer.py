"""P3.2 — Renderer（CEODailyReport -> Markdown 决策单 / JSON）。

确定性：只依赖 report 数据，不注入时间戳；日期取 report.date。
Markdown 是「运营决策单」而非日志：健康概览 + 机会 + 行动队列（三态）
+ 风险 + 执行小结 + 学习。
"""
from __future__ import annotations

import json
from typing import Any, List

from .models import (
    ACTION_STATE_TITLE,
    ActionState,
    CEODailyReport,
    CEOAction,
)


def _fmt_delta(v: Any) -> str:
    """格式化预算Δ：None/0 显示 —，正加 +，负保留 -。"""
    if v is None:
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if abs(f) < 1e-9:
        return "—"
    return f"{f:+.2f}"


def render_markdown(report: CEODailyReport) -> str:
    lines: List[str] = []
    lines.append(f"# 每日 CEO 决策单 · {report.date}")
    lines.append("")
    hs = report.health_summary
    lines.append(
        f"> report_id：{report.report_id} ｜ 公司状态：{hs.status_label} ｜ "
        f"real_api_called：{report.real_api_called}"
    )
    lines.append("")

    # 一、健康概览
    lines.append("## 一、今日健康概览")
    lines.append("")
    lines.append(f"- 公司状态：**{hs.status_label}**")
    lines.append(
        f"- 在册游戏：**{hs.game_count}** 款 ｜ 舰队日收入：**${hs.total_revenue:,.2f}** "
        f"｜ DAU：{hs.total_dau:,} ｜ 日花费：${hs.total_spend:,.2f} ｜ "
        f"数据置信：{hs.avg_confidence:.0%}"
    )
    if hs.at_risk:
        names = "、".join(hs.at_risk[:8])
        more = f" 等 {len(hs.at_risk)} 款" if len(hs.at_risk) > 8 else ""
        lines.append(f"- ⚠️ 风险名单：{names}{more}")
    lines.append(
        f"- 行动分布：✅ AUTO **{hs.auto_count}** ｜ "
        f"🖐 APPROVAL **{hs.approval_count}** ｜ "
        f"⛔ BLOCKED **{hs.blocked_count}** ｜ "
        f"👁 OBSERVE {hs.observed_count}"
    )
    lines.append("")

    # 二、机会 Top N
    lines.append("## 二、今日最大机会（Top {n}）".format(n=len(report.opportunities)))
    lines.append("")
    if not report.opportunities:
        lines.append("（今日无识别机会）")
    else:
        lines.append("| # | 游戏 | 行动 | 优先级 | 预期影响 | 置信 | 紧迫 | 模拟 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for o in report.opportunities:
            lines.append(
                f"| {o.rank} | {o.game_id} | {o.action} "
                f"| {o.priority_score:.4f} | {o.expected_value:+.1%} "
                f"| {o.confidence:.0%} | {o.urgency:.0%} | {o.sim_gate} |"
            )
    lines.append("")

    # 三、行动队列（三态）
    lines.append("## 三、今日行动队列（决策 → 执行）")
    lines.append("")
    for state in (ActionState.AUTO, ActionState.APPROVAL, ActionState.BLOCKED):
        group = [a for a in report.actions if a.execution_mode == state]
        if not group:
            continue
        lines.append(f"### {ACTION_STATE_TITLE[state.value]}")
        lines.append("")
        for a in group:
            lines.append(
                f"- **[{a.action_id}] {a.game_id}** — {a.action_type}：{a.explanation}"
            )
            lines.append(f"  - 责任来源：`{a.source}` ｜ 优先级：{a.priority:.4f}")
        lines.append("")

    # 四、风险
    lines.append("## 四、风险与注意")
    lines.append("")
    for r in report.risks:
        icon = {"critical": "🔴", "warn": "⚠️", "info": "ℹ️"}.get(r.level, "ℹ️")
        lines.append(f"- {icon} **{r.title}**：{r.detail}")
    lines.append("")

    # 五、执行小结
    es = report.execution_summary
    lines.append("## 五、执行小结")
    lines.append("")
    lines.append(
        f"- 执行 **{es.total_executions}** ｜ 成功 **{es.success}** ｜ "
        f"失败 **{es.failed}** ｜ 回滚 **{es.rollback}** ｜ 拦截 **{es.blocked}**"
    )
    if es.health_level:
        lines.append(f"- 执行健康等级：**{es.health_level}**")
    if es.recovered or es.escalated:
        lines.append(
            f"- 恢复：**{es.recovered}** 自动恢复 ｜ **{es.escalated}** 升级人工"
        )
    lines.append(
        f"- real_api_called：**{es.real_api_called}**"
        + ("（DRY_RUN 纪律）" if not es.real_api_called else "  ⚠️ 出现真实调用")
    )
    for w in es.warnings:
        lines.append(f"- ⚠️ {w}")
    lines.append("")

    # 六、学习
    lines.append("## 六、今日学习（经验回流）")
    lines.append("")
    for l in report.learning_summary:
        lines.append(f"- 🧠 {l}")
    lines.append("")

    # 七、Portfolio Recommendation（跨游戏资源建议，P3.1 接 P3.4.5）
    section = report.portfolio_recommendation
    if section:
        lines.append("## 七、Portfolio Recommendation（跨游戏资源建议）")
        lines.append("")
        status = section.get("status", "")
        badge = {
            "completed": "✅ 可进入人工评审",
            "blocked": "⛔ 已被闸门/约束阻断",
            "insufficient_data": "⚠️ 数据不足，无法优化",
        }.get(status, status)
        lines.append(f"- **编排状态**：`{status}` ｜ {badge}")
        summary = section.get("summary", "")
        if summary:
            lines.append(f"- **摘要**：{summary}")
        recommendation = section.get("recommendation", "")
        if recommendation:
            lines.append(f"- **建议**：{recommendation}")
        guard = section.get("guard_verdict", "")
        confidence = section.get("confidence")
        if guard:
            conf = (
                f" ｜ 置信：{confidence:.0%}"
                if isinstance(confidence, (int, float)) else ""
            )
            lines.append(f"- **提案闸门**：`{guard}`{conf}")
        items = section.get("items") or []
        if items:
            lines.append("")
            lines.append(
                "| # | 游戏 | 建议动作 | 预算Δ | 三态 | 依据 |"
            )
            lines.append("|---|---|---|---|---|---|")
            for it in items:
                lines.append(
                    f"| {it.get('rank', '')} | {it.get('game_id', '')} "
                    f"| {it.get('recommended_action', '')} "
                    f"| {_fmt_delta(it.get('budget_delta'))} "
                    f"| {it.get('action_state', '')} "
                    f"| {it.get('rationale', '')} |"
                )
        lines.append("")
        rap = section.get("real_api_called")
        lines.append(
            f"- real_api_called：**{rap}**"
            + ("（DRY_RUN 纪律：仅建议，不执行）" if not rap else "  ⚠️ 出现真实调用")
        )
        lines.append("")

    # 八、Memory Reasoning（知识推理，P3.6.1——AI CEO 与普通自动化系统的区别：为什么）
    reasoning = report.memory_reasoning
    if reasoning:
        lines.append("## 八、Memory Reasoning（本次建议的知识依据）")
        lines.append("")
        lines.append("- **本次建议参考**：")
        sims = reasoning.get("similar_games") or []
        if sims:
            lines.append(f"  1. Similar games：{', '.join(sims[:5])}")
        validated = reasoning.get("memories_count", 0)
        lines.append(f"  2. 召回记忆：**{validated}** 条")
        sr = reasoning.get("historical_success_rate")
        if isinstance(sr, (int, float)) and sr:
            lines.append(f"  3. Historical success：**{sr:.0%}**")
        latest = reasoning.get("latest_validation", "")
        if latest:
            lines.append(f"  4. Recent validation：{latest[:10]}")
        conflicts = reasoning.get("conflicts") or []
        if conflicts:
            lines.append(f"  ⚠️ Conflict：{len(conflicts)} 组")
            for c in conflicts[:3]:
                lines.append(f"     - {c}")
        else:
            lines.append("  5. Conflict：**none**")
        conf = reasoning.get("confidence")
        if isinstance(conf, (int, float)):
            lines.append(f"- **Confidence：{conf:.2f}**")
        explanation = reasoning.get("explanation", "")
        if explanation:
            lines.append(f"- 解释：{explanation}")
        mr = reasoning.get("real_api_called")
        lines.append(
            f"- real_api_called：**{mr}**"
            + ("（DRY_RUN 纪律：纯检索）" if not mr else "  ⚠️ 出现真实调用")
        )
        lines.append("")

    # 九、Strategic Memory（长期战略规律，P3.6.2——从大量决策中总结的规律）
    strategic = report.strategic_memory
    if strategic:
        lines.append("## 九、Strategic Memory（长期战略规律）")
        lines.append("")
        insights = strategic.get("insights") or []
        if not insights:
            lines.append("（暂无战略规律，记忆样本不足）")
        else:
            by_cat: dict = {}
            for ins in insights:
                by_cat.setdefault(ins.get("category", ""), []).append(ins)
            for cat in sorted(by_cat):
                lines.append(f"- **{cat}**：")
                for ins in by_cat[cat]:
                    sr = ins.get("success_rate")
                    conf = ins.get("confidence")
                    sr_txt = f"{sr:.0%}" if isinstance(sr, (int, float)) else "-"
                    conf_txt = f"{conf:.2f}" if isinstance(conf, (int, float)) else "-"
                    lines.append(
                        f"  - {ins.get('statement', '')} "
                        f"（成功率 {sr_txt} ｜ 置信 {conf_txt} ｜ "
                        f"证据 {ins.get('evidence_count', 0)} 条）"
                    )
        smr = strategic.get("real_api_called")
        lines.append(
            f"- real_api_called：**{smr}**"
            + ("（DRY_RUN 纪律：纯检索）" if not smr else "  ⚠️ 出现真实调用")
        )
        lines.append("")

    # 十、Memory Reflection（认知复盘，P3.6.3——AI CEO 修改自身认知模型）
    reflection = report.reflection
    if reflection:
        lines.append("## 十、Memory Reflection（昨日复盘）")
        lines.append("")

        lines.append(f"- 复盘周期：**{reflection.get('period', '')}**"
                     f"（证据 {reflection.get('evidence_count', 0)} 条，"
                     f"未验证 {reflection.get('unresolved_count', 0)} 条）")
        wins = reflection.get("wins") or []
        mistakes = reflection.get("mistakes") or []
        if wins:
            lines.append(f"- 做对了（wins，{len(wins)}）：")
            for w in wins[:8]:
                lines.append(
                    f"  - `{w.get('record_id', '')}` {w.get('game_id', '')} "
                    f"{w.get('action', '')}（sr={w.get('success_rate', 0.0):.0%}）"
                )
        if mistakes:
            lines.append(f"- 做错了（mistakes，{len(mistakes)}）：")
            for m in mistakes[:8]:
                lines.append(
                    f"  - `{m.get('record_id', '')}` {m.get('game_id', '')} "
                    f"{m.get('action', '')}（sr={m.get('success_rate', 0.0):.0%}）"
                )
        beliefs = reflection.get("changed_beliefs") or []
        if beliefs:
            lines.append(f"- 认知更新（changed_beliefs，{len(beliefs)}）：")
            for b in beliefs[:8]:
                lines.append(
                    f"  - {b.get('belief', '')}（规律 sr="
                    f"{b.get('previous_success_rate', 0.0):.0%} → 窗口 "
                    f"{b.get('window_success_rate', 0.0):.0%}；{b.get('reason', '')}）"
                )
        rules = reflection.get("new_rules") or []
        if rules:
            lines.append(f"- 新规则（new_rules，{len(rules)}）：")
            for r in rules[:8]:
                lines.append(f"  - **{r.get('rule_type', '')}** {r.get('statement', '')}")
        if not wins and not mistakes and not beliefs and not rules:
            lines.append("（本周期无已验证决策，暂无复盘内容）")
        rfl = reflection.get("real_api_called")
        lines.append(
            f"- real_api_called：**{rfl}**"
            + ("（DRY_RUN 纪律：纯检索）" if not rfl else "  ⚠️ 出现真实调用")
        )
        lines.append("")

    # 十一、Memory Governance（P3.6.4）
    governance = report.governance
    if governance and (governance.get("records") or governance.get("health")):
        lines.append("## 十一、Memory Governance（记忆治理）")
        lines.append("")
        lines.append(
            f"- 重复归并：**{governance.get('duplicate_merges', 0)}** 组 ｜ "
            f"废弃：**{governance.get('obsolete_marked', 0)}** 条 ｜ "
            f"矛盾裁决：**{governance.get('conflicts_resolved', 0)}** 组 ｜ "
            f"归档：**{governance.get('archived', 0)}** 条"
        )
        review = int(governance.get("requires_ceo_review", 0) or 0)
        if review:
            lines.append(f"- ⚠️ 待 CEO 关注的矛盾：**{review}** 组")
        health = governance.get("health") or {}
        lines.append(
            f"- 图谱健康度：ACTIVE {health.get('active', 0)} ｜ "
            f"CONFLICTED {health.get('conflicted', 0)} ｜ "
            f"OBSOLETE {health.get('obsolete', 0)} ｜ ARCHIVED {health.get('archived', 0)}"
        )
        lines.append(f"- real_api_called：**{governance.get('real_api_called', False)}**")
        lines.append("")

    lines.append("---")
    lines.append(
        "_由 LaunchForge P3.2 CEO Daily Report 生成 · 全 SIM，无真实 API 调用_"
    )
    return "\n".join(lines)


def render_report_json(report: CEODailyReport) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)


def render_actions_json(report: CEODailyReport) -> str:
    return json.dumps(
        [a.to_dict() for a in report.actions], ensure_ascii=False, indent=2
    )


__all__ = ["render_markdown", "render_report_json", "render_actions_json"]
