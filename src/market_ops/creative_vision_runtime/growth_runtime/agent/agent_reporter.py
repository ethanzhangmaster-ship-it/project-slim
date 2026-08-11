"""E13.7.4 Agent Reporter — 人机接口报告系统.

Agent Reporter 为人类运营者生成可读的每日/每周增长报告:
  - 每日 Growth Report: 收入、花费、ROAS、动作、学习
  - 每周 Summary: 趋势、赢家、输家、建议
  - 告警通知: 异常事件推送

连接 ProductionMemory 和 HealthMonitor, 输出结构化报告。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .agent_health import HealthSnapshot, HealthStatus
from .production_memory import CycleRecord, ProductionMemory


@dataclass
class DailyReport:
    """每日增长报告.

    Attributes:
        report_id: 报告 ID
        date: 报告日期
        generated_at: 生成时间
        revenue: 总收入
        spend: 总花费
        roas: ROAS
        actions_taken: 执行的动作列表
        results: 结果摘要
        learnings: 经验教训
        top_winners: 表现最好的素材/Campaign
        top_losers: 表现最差的素材/Campaign
        health_status: 健康状态
        recommendations: 建议
    """
    report_id: str = ""
    date: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    revenue: float = 0.0
    spend: float = 0.0
    roas: float = 0.0
    actions_taken: list[dict[str, Any]] = field(default_factory=list)
    results: dict[str, Any] = field(default_factory=dict)
    learnings: list[str] = field(default_factory=list)
    top_winners: list[dict[str, Any]] = field(default_factory=list)
    top_losers: list[dict[str, Any]] = field(default_factory=list)
    health_status: str = ""
    recommendations: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        """生成可读文本报告."""
        lines = []
        lines.append("=" * 40)
        lines.append(f"Growth Agent Daily Report")
        lines.append(f"Date: {self.date}")
        lines.append("=" * 40)
        lines.append("")
        lines.append(f"Revenue: ${self.revenue:,.0f}")
        lines.append(f"Spend:   ${self.spend:,.0f}")
        lines.append(f"ROAS:    {self.roas:.2f}")
        lines.append("")

        if self.actions_taken:
            lines.append("Actions:")
            for action in self.actions_taken:
                status = action.get("status", "?")
                icon = "✅" if status == "success" else "❌"
                lines.append(f"  {icon} {action.get('description', action.get('action_type', '?'))}")
                if action.get("reason"):
                    lines.append(f"     Reason: {action['reason']}")
            lines.append("")

        if self.learnings:
            lines.append("Learning:")
            for learning in self.learnings:
                lines.append(f"  • {learning}")
            lines.append("")

        if self.top_winners:
            lines.append("Top Winners:")
            for w in self.top_winners:
                lines.append(f"  • {w.get('name', '?')}: {w.get('performance', '?')}")
            lines.append("")

        if self.top_losers:
            lines.append("Top Losers:")
            for l in self.top_losers:
                lines.append(f"  • {l.get('name', '?')}: {l.get('performance', '?')}")
            lines.append("")

        if self.recommendations:
            lines.append("Recommendations:")
            for rec in self.recommendations:
                lines.append(f"  • {rec}")
            lines.append("")

        lines.append("=" * 40)
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "date": self.date,
            "generated_at": self.generated_at,
            "revenue": self.revenue,
            "spend": self.spend,
            "roas": self.roas,
            "actions_taken": self.actions_taken,
            "results": self.results,
            "learnings": self.learnings,
            "top_winners": self.top_winners,
            "top_losers": self.top_losers,
            "health_status": self.health_status,
            "recommendations": self.recommendations,
        }


@dataclass
class WeeklyReport:
    """每周增长报告.

    Attributes:
        report_id: 报告 ID
        week_start: 周开始日期
        week_end: 周结束日期
        generated_at: 生成时间
        total_revenue: 总营收
        total_spend: 总花费
        avg_roas: 平均 ROAS
        roas_trend: ROAS 趋势
        top_actions: 最频繁的动作
        top_patterns: 最成功的模式
        health_summary: 健康摘要
        strategic_recommendations: 战略建议
    """
    report_id: str = ""
    week_start: str = ""
    week_end: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_revenue: float = 0.0
    total_spend: float = 0.0
    avg_roas: float = 0.0
    roas_trend: list[dict[str, Any]] = field(default_factory=list)
    top_actions: list[dict[str, Any]] = field(default_factory=list)
    top_patterns: list[dict[str, Any]] = field(default_factory=list)
    health_summary: dict[str, Any] = field(default_factory=dict)
    strategic_recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "week_start": self.week_start,
            "week_end": self.week_end,
            "generated_at": self.generated_at,
            "total_revenue": self.total_revenue,
            "total_spend": self.total_spend,
            "avg_roas": self.avg_roas,
            "roas_trend": self.roas_trend,
            "top_actions": self.top_actions,
            "top_patterns": self.top_patterns,
            "health_summary": self.health_summary,
            "strategic_recommendations": self.strategic_recommendations,
        }


@dataclass
class AgentReporter:
    """Agent 报告生成器.

    从 ProductionMemory 和 HealthMonitor 中提取数据,
    生成面向人类的可读报告。
    """

    def __init__(
        self,
        memory: ProductionMemory | None = None,
        health_snapshot: HealthSnapshot | None = None,
    ):
        self._memory = memory or ProductionMemory()
        self._health_snapshot = health_snapshot

    # ── 每日报告 ──────────────────────────────────────────────

    def generate_daily_report(
        self,
        date: str | None = None,
        records: list[CycleRecord] | None = None,
    ) -> DailyReport:
        """生成每日增长报告.

        Args:
            date: 日期 (格式: 20260727, 默认今天)
            records: 循环记录 (默认从 memory 获取当日)

        Returns:
            DailyReport: 每日报告
        """
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y%m%d")

        if records is None:
            records = self._memory.get_by_date(date)

        report = DailyReport(
            report_id=f"daily_{date}",
            date=date,
        )

        # 汇总指标
        total_revenue = 0.0
        total_spend = 0.0
        actions_taken: list[dict[str, Any]] = []
        learnings: list[str] = []

        for r in records:
            obs = r.observation
            total_revenue += obs.get("revenue", 0)
            total_spend += obs.get("spend", 0)

            # 收集动作
            decision = r.decision
            actions = decision.get("actions", [])
            if isinstance(actions, list):
                for action in actions:
                    if isinstance(action, dict):
                        actions_taken.append({
                            "action_type": action.get("action_type", "unknown"),
                            "description": action.get("description", ""),
                            "reason": r.reasoning.get("cause", ""),
                            "status": "success" if r.success else "failed",
                        })

            # 收集学习
            learning = r.learning
            pattern = learning.get("pattern", "")
            if pattern:
                learnings.append(pattern)

        report.revenue = total_revenue
        report.spend = total_spend
        report.roas = total_revenue / max(total_spend, 1)
        report.actions_taken = actions_taken
        report.learnings = list(set(learnings))  # 去重

        # 健康状态
        if self._health_snapshot:
            report.health_status = self._health_snapshot.status.value
            report.recommendations = self._health_snapshot.recommendations

        # 胜负分析
        report.top_winners = self._extract_winners(records)
        report.top_losers = self._extract_losers(records)

        # 建议
        if not report.recommendations:
            report.recommendations = self._generate_recommendations(records)

        return report

    def _extract_winners(self, records: list[CycleRecord]) -> list[dict[str, Any]]:
        """提取表现最好的项."""
        winners = []
        for r in records:
            if r.success and r.learning:
                winners.append({
                    "name": r.learning.get("pattern", r.cycle_id),
                    "performance": r.result.get("summary", ""),
                    "cycle_id": r.cycle_id,
                })
        return winners[:3]

    def _extract_losers(self, records: list[CycleRecord]) -> list[dict[str, Any]]:
        """提取表现最差的项."""
        losers = []
        for r in records:
            if not r.success:
                losers.append({
                    "name": r.reasoning.get("cause", r.cycle_id),
                    "performance": r.reasoning.get("diagnosis", ""),
                    "cycle_id": r.cycle_id,
                })
        return losers[:3]

    def _generate_recommendations(self, records: list[CycleRecord]) -> list[str]:
        """基于记录生成建议."""
        recs = []
        if not records:
            return recs

        success_rate = sum(1 for r in records if r.success) / len(records)
        if success_rate < 0.5:
            recs.append("Low success rate detected — review policy thresholds")
        elif success_rate > 0.8:
            recs.append("High success rate — consider scaling winning strategies")

        patterns = self._memory.get_patterns()
        if patterns:
            recs.append(f"Continue leveraging pattern: {patterns[0]['pattern']}")

        return recs

    # ── 每周报告 ──────────────────────────────────────────────

    def generate_weekly_report(
        self,
        records: list[CycleRecord] | None = None,
    ) -> WeeklyReport:
        """生成每周增长报告."""
        if records is None:
            records = self._memory.get_recent(200)

        today = datetime.now(timezone.utc)
        week_start = today.strftime("%Y%m%d")

        total_revenue = sum(r.observation.get("revenue", 0) for r in records)
        total_spend = sum(r.observation.get("spend", 0) for r in records)

        # ROAS 趋势
        roas_trend = []
        for r in records:
            obs = r.observation
            rev = obs.get("revenue", 0)
            spd = obs.get("spend", 1)
            roas_trend.append({
                "cycle_id": r.cycle_id,
                "roas": round(rev / max(spd, 1), 2),
                "success": r.success,
            })

        # 最频繁动作
        action_counts: dict[str, int] = {}
        for r in records:
            decision = r.decision
            actions = decision.get("actions", [])
            if isinstance(actions, list):
                for action in actions:
                    if isinstance(action, dict):
                        at = action.get("action_type", "unknown")
                        action_counts[at] = action_counts.get(at, 0) + 1

        top_actions = sorted(
            [{"action_type": k, "count": v} for k, v in action_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:5]

        # 最佳模式
        top_patterns = self._memory.get_patterns()[:5]

        return WeeklyReport(
            report_id=f"weekly_{week_start}",
            week_start=week_start,
            week_end=today.strftime("%Y%m%d"),
            total_revenue=total_revenue,
            total_spend=total_spend,
            avg_roas=round(total_revenue / max(total_spend, 1), 2),
            roas_trend=roas_trend,
            top_actions=top_actions,
            top_patterns=top_patterns,
            health_summary=(
                self._health_snapshot.to_dict()
                if self._health_snapshot else {}
            ),
            strategic_recommendations=self._generate_recommendations(records),
        )

    # ── 告警 ──────────────────────────────────────────────────

    def generate_alert(self, reason: str, severity: str = "warning") -> dict[str, Any]:
        """生成告警通知."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "severity": severity,
            "health_status": (
                self._health_snapshot.status.value
                if self._health_snapshot else "unknown"
            ),
        }

    # ── 更新 ──────────────────────────────────────────────────

    def update_health(self, snapshot: HealthSnapshot) -> None:
        """更新健康快照."""
        self._health_snapshot = snapshot

    def update_memory(self, memory: ProductionMemory) -> None:
        """更新记忆引用."""
        self._memory = memory


# ═══════════════════════════════════════════════════════════════
# Factory Functions
# ═══════════════════════════════════════════════════════════════


def create_reporter(
    memory: ProductionMemory | None = None,
    health_snapshot: HealthSnapshot | None = None,
) -> AgentReporter:
    """创建默认报告生成器."""
    return AgentReporter(memory=memory, health_snapshot=health_snapshot)