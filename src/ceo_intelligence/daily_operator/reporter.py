"""E17.9 — Morning Report Generator（晨报三版本）。

同一份 Daily Run 数据 → 三个视角的中文 Markdown：
- ceo     ：公司状态一句话定调 + 舰队大盘 + Top 机会 + 今日行动（AUTO/审批/阻断）+ 昨天环比
- ua      ：只看买量/素材（ua_scale / ua_stop_loss / creative_refresh）+ 花费/ROAS 大盘
- product ：只看产品/变现/商店（revenue_recovery / retention / monetization /
            aso_optimization / release_health）+ 风险名单

确定性：同数据同输出（无时间戳注入——日期由调用方传入）。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .models import (
    ActionKind,
    CompanyStatus,
    DailyActionItem,
    GamePriority,
    OperatorDayRecord,
    STATUS_LABEL,
)

UA_TYPES = {"ua_scale", "ua_stop_loss", "creative_refresh"}
PRODUCT_TYPES = {
    "revenue_recovery", "retention", "monetization",
    "aso_optimization", "release_health",
}

_KIND_TITLE = {
    ActionKind.AUTO: "✅ 已自动执行（AUTO）",
    ActionKind.APPROVAL: "🖐 等你审批（APPROVAL）",
    ActionKind.BLOCK: "⛔ 已被模拟闸门阻断（BLOCK）",
}


class MorningReporter:
    """build_all(...) → {"ceo": md, "ua": md, "product": md}。"""

    def build_all(
        self,
        date: str,
        company,
        status: CompanyStatus,
        priorities: List[GamePriority],
        actions: List[DailyActionItem],
        yesterday: Optional[OperatorDayRecord] = None,
        today: Optional[OperatorDayRecord] = None,
    ) -> Dict[str, str]:
        return {
            "ceo": self.build_ceo(
                date, company, status, priorities, actions, yesterday, today
            ),
            "ua": self.build_ua(date, company, priorities, actions),
            "product": self.build_product(date, company, priorities, actions),
        }

    # ------------------------------------------------------------------ #
    def build_ceo(
        self,
        date: str,
        company,
        status: CompanyStatus,
        priorities: List[GamePriority],
        actions: List[DailyActionItem],
        yesterday: Optional[OperatorDayRecord] = None,
        today: Optional[OperatorDayRecord] = None,
    ) -> str:
        lines: List[str] = []
        lines.append(f"# CEO 晨报 · {date}")
        lines.append("")
        lines.append(f"**公司状态：{STATUS_LABEL[status.value]}**")
        lines.append("")
        lines.append("## 舰队大盘")
        lines.append("")
        lines.append(f"- 在册游戏：**{company.game_count}** 款")
        lines.append(f"- 舰队日收入：**${company.total_revenue:,.2f}**")
        lines.append(f"- 舰队 DAU：{company.total_dau:,}")
        lines.append(f"- 舰队日花费：${company.total_spend:,.2f}")
        lines.append(f"- 数据置信度：{company.avg_confidence:.0%}")
        if company.at_risk:
            names = "、".join(company.at_risk[:8])
            more = f" 等 {len(company.at_risk)} 款" if len(company.at_risk) > 8 else ""
            lines.append(f"- ⚠️ 风险名单：{names}{more}")
        lines.append("")

        if yesterday is not None and today is not None:
            lines.append("## 昨天 vs 今天")
            lines.append("")
            lines.append("| 指标 | 昨天 | 今天 |")
            lines.append("|---|---|---|")
            lines.append(f"| 决策数 | {yesterday.decisions} | {today.decisions} |")
            lines.append(f"| 自动执行 | {yesterday.executed} | {today.executed} |")
            lines.append(f"| 待审批 | {yesterday.approved} | {today.approved} |")
            lines.append(f"| 阻断 | {yesterday.blocked} | {today.blocked} |")
            lines.append(
                f"| 预期收入影响 | {yesterday.revenue_impact:+.1%} "
                f"| {today.revenue_impact:+.1%} |"
            )
            lines.append("")

        lines.append(self._priorities_section(
            "今日最大机会（Top 10）", priorities
        ))
        lines.append(self._actions_section(actions))
        lines.append("---")
        lines.append("_由 Daily Growth Operator 自动生成 · 全 SIM，无真实 API 调用_")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    def build_ua(
        self,
        date: str,
        company,
        priorities: List[GamePriority],
        actions: List[DailyActionItem],
    ) -> str:
        pri = [p for p in priorities if p.opportunity_type in UA_TYPES]
        act = [a for a in actions if a.opportunity_type in UA_TYPES]
        lines: List[str] = []
        lines.append(f"# UA 晨报 · {date}")
        lines.append("")
        lines.append(f"- 舰队日花费：**${company.total_spend:,.2f}**")
        lines.append(f"- 舰队日收入：${company.total_revenue:,.2f}")
        overall = (
            company.total_revenue / company.total_spend
            if company.total_spend else 0.0
        )
        lines.append(f"- 大盘 ROAS（收入/花费）：**{overall:.2f}**")
        lines.append("")
        lines.append(self._priorities_section("买量/素材机会", pri))
        lines.append(self._actions_section(act))
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    def build_product(
        self,
        date: str,
        company,
        priorities: List[GamePriority],
        actions: List[DailyActionItem],
    ) -> str:
        pri = [p for p in priorities if p.opportunity_type in PRODUCT_TYPES]
        act = [a for a in actions if a.opportunity_type in PRODUCT_TYPES]
        lines: List[str] = []
        lines.append(f"# Product 晨报 · {date}")
        lines.append("")
        lines.append(f"- 在册游戏：{company.game_count} 款")
        lines.append(f"- 舰队 DAU：{company.total_dau:,}")
        if company.at_risk:
            lines.append(f"- ⚠️ 风险名单（{len(company.at_risk)}）："
                         f"{'、'.join(company.at_risk[:10])}")
        lines.append("")
        lines.append(self._priorities_section("产品/变现/商店机会", pri))
        lines.append(self._actions_section(act))
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    @staticmethod
    def _priorities_section(title: str, priorities: List[GamePriority]) -> str:
        lines = [f"## {title}", ""]
        if not priorities:
            lines.append("（今日无）")
            lines.append("")
            return "\n".join(lines)
        lines.append("| # | 游戏 | 行动 | 优先级 | 预期影响 | 置信 | 紧迫 | 模拟 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for p in priorities:
            gate = p.gate.upper() if p.gate else "—"
            lines.append(
                f"| {p.rank} | {p.game_id} | {p.action} "
                f"| {p.priority_score_value:.4f} | {p.impact:+.1%} "
                f"| {p.confidence:.0%} | {p.urgency:.0%} | {gate} |"
            )
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _actions_section(actions: List[DailyActionItem]) -> str:
        lines = ["## 今日行动", ""]
        if not actions:
            lines.append("（今日无需行动）")
            lines.append("")
            return "\n".join(lines)
        for kind in (ActionKind.AUTO, ActionKind.APPROVAL, ActionKind.BLOCK):
            group = [a for a in actions if a.kind == kind]
            if not group:
                continue
            lines.append(f"### {_KIND_TITLE[kind]}")
            lines.append("")
            for a in group:
                lines.append(f"- **{a.game_id}** — {a.action}（{a.detail}）")
            lines.append("")
        return "\n".join(lines)

__all__ = ["MorningReporter", "UA_TYPES", "PRODUCT_TYPES"]
