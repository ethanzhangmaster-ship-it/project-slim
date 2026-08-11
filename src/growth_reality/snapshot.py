"""E17.1 Growth Reality Hub — 公司级快照聚合。

把多游戏 GrowthRealitySnapshot 汇总成 CompanySnapshot：
- 舰队总量（revenue / dau / spend / installs）
- 平均置信度
- at_risk 名单（置信度<0.4 或 收入<=0）
- to_markdown() 全中文 CEO 视图
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .models import GrowthRealitySnapshot


@dataclass
class CompanySnapshot:
    as_of: str
    game_count: int
    total_revenue: float
    total_dau: int
    total_spend: float
    total_installs: int
    avg_confidence: float
    per_game: Dict[str, GrowthRealitySnapshot] = field(default_factory=dict)
    at_risk: List[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append("# 公司增长现实快照（Growth Reality Hub）")
        lines.append("")
        lines.append(f"- 快照时间：`{self.as_of}`")
        lines.append(f"- 在册游戏：**{self.game_count}** 款")
        lines.append(f"- 舰队日收入：**${self.total_revenue:,.2f}**")
        lines.append(f"- 舰队 DAU：**{self.total_dau:,}**")
        lines.append(f"- 舰队日花费：${self.total_spend:,.2f}")
        lines.append(f"- 平均数据置信度：**{self.avg_confidence:.0%}**")
        lines.append("")
        if self.at_risk:
            lines.append(f"## ⚠️ 风险名单（{len(self.at_risk)}）")
            for gid in self.at_risk:
                lines.append(f"- {gid}")
            lines.append("")
        lines.append("## 逐游戏概览")
        lines.append("")
        lines.append("| 游戏 | 日收入 | DAU | ARPU | ROAS | 置信度 | 覆盖域 |")
        lines.append("|---|---|---|---|---|---|---|")
        for gid, s in sorted(self.per_game.items()):
            rev = s.revenue.daily_revenue if s.revenue else 0.0
            dau = s.product.dau if s.product else 0
            arpu = (rev / dau) if dau else 0.0
            roas = s.acquisition.roas if s.acquisition else 0.0
            cov = ",".join(s.covered_domains()) or "—"
            lines.append(
                f"| {gid} | ${rev:,.2f} | {dau:,} | ${arpu:,.3f} | "
                f"{roas:.2f} | {s.confidence:.0%} | {cov} |"
            )
        return "\n".join(lines)


def build_company_snapshot(
    snapshots: List[GrowthRealitySnapshot], as_of: str
) -> CompanySnapshot:
    total_rev = 0.0
    total_dau = 0
    total_spend = 0.0
    total_inst = 0
    conf_sum = 0.0
    per_game: Dict[str, GrowthRealitySnapshot] = {}
    at_risk: List[str] = []

    for s in snapshots:
        per_game[s.game_id] = s
        if s.revenue:
            total_rev += s.revenue.daily_revenue
        if s.product:
            total_dau += s.product.dau
        if s.acquisition:
            total_spend += s.acquisition.spend
            total_inst += s.acquisition.installs
        conf_sum += s.confidence
        if s.confidence < 0.4 or (s.revenue and s.revenue.daily_revenue <= 0):
            at_risk.append(s.game_id)

    n = len(snapshots) or 1
    return CompanySnapshot(
        as_of=as_of,
        game_count=len(snapshots),
        total_revenue=total_rev,
        total_dau=total_dau,
        total_spend=total_spend,
        total_installs=total_inst,
        avg_confidence=conf_sum / n,
        per_game=per_game,
        at_risk=at_risk,
    )
