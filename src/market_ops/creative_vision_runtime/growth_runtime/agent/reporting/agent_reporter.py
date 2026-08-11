"""E13.7.4.4 Agent Reporter — 主报告器.

AgentReporter 是报告系统的核心，统一管理所有报告生成器:
  - 生成完整 Agent 周期报告 (Decision + Execution + Learning + Health)
  - 输出多种格式 (JSON / Markdown / Text)
  - 与 ReportStore 集成存储
  - 提供 API 接口 (status, latest, history)

连接:
  - DecisionReportBuilder: 决策报告
  - ExecutionReportBuilder: 执行报告
  - HealthReportBuilder: 健康报告
  - LearningReportBuilder: 学习报告
  - ReportStore: 持久化存储
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from .report_models import (
    AgentReport,
    ReportFormat,
    ReportQuery,
    ReportSection,
    ReportStatus,
    ReportSummary,
    ReportType,
)
from .decision_report import (
    DecisionReportBuilder,
    DecisionEntry,
    DecisionEvidence,
)
from .execution_report import (
    ExecutionReportBuilder,
    ExecutionAction,
    ExecutionTask,
)
from .health_report import HealthReportBuilder
from .learning_report import (
    LearningReportBuilder,
    LearningEntry,
    PatternUpdate,
    MemoryFeedback,
)
from .report_store import (
    ReportStore,
    InMemoryReportStore,
    FileReportStore,
)


# ═══════════════════════════════════════════════════════════════
# AgentReporter
# ═══════════════════════════════════════════════════════════════


class AgentReporter:
    """Agent 主报告器.

    AgentReporter 是报告系统的统一入口，管理一个完整周期的报告生成:
      - 收集决策、执行、学习、健康数据
      - 生成统一格式的 AgentReport
      - 存储到 ReportStore
      - 提供查询接口

    使用方式:
        reporter = AgentReporter(agent_id="ua_agent_01", store=create_report_store())
        reporter.start_cycle("cycle_001")

        # 添加决策
        reporter.add_decision_section(
            observations={"ROAS": (0.53, 0.75)},
            reasoning=["CRT 下降 34%"],
            decisions=[{"action": "MUTATE_CREATIVE", "target": "camp_123", "reason": "疲劳", "confidence": 0.87}],
        )

        # 添加执行
        reporter.add_execution_section(
            task_name="Generate Mutation",
            actions=[{"action_type": "generate_dna", "target": "creative_123", "status": "success"}],
        )

        # 生成并保存
        report = reporter.finalize()
        reporter.save()

        # 查询
        latest = reporter.get_latest()
        history = reporter.get_history(limit=10)

    Attributes:
        agent_id: Agent 标识
        store: 报告存储
        current_report: 当前正在构建的报告
    """

    def __init__(
        self,
        agent_id: str = "",
        store: ReportStore | None = None,
    ):
        self.agent_id = agent_id
        self.store = store or InMemoryReportStore()
        self.current_report: AgentReport | None = None
        self._on_report_finalized: list[Callable[[AgentReport], None]] = []

    # ── Lifecycle ───────────────────────────────────────────────

    def start_cycle(self, cycle_id: str = "") -> AgentReport:
        """开始新周期报告.

        Args:
            cycle_id: 循环 ID

        Returns:
            AgentReport: 新建的报告对象
        """
        self.current_report = AgentReport(
            agent_id=self.agent_id,
            cycle_id=cycle_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            status=ReportStatus.DRAFT,
        )
        return self.current_report

    def finalize(self) -> AgentReport:
        """完成报告 (标记为 FINAL)."""
        if self.current_report is None:
            self.current_report = AgentReport(
                agent_id=self.agent_id,
                status=ReportStatus.FINAL,
            )
        self.current_report.finalize()
        for callback in self._on_report_finalized:
            callback(self.current_report)
        return self.current_report

    def save(self) -> None:
        """保存当前报告到存储."""
        if self.current_report:
            self.store.save(self.current_report)

    def reset(self) -> None:
        """重置 (清空当前报告)."""
        self.current_report = None

    # ── Section Builders ────────────────────────────────────────

    def add_decision_section(
        self,
        campaign_name: str = "",
        observations: dict[str, tuple[float, float | None]] | None = None,
        reasoning_points: list[str] | None = None,
        decisions: list[dict[str, Any]] | None = None,
        similar_cases: int = 0,
        success_rate: float = 0.0,
        evidence: list[DecisionEvidence] | None = None,
    ) -> ReportSection:
        """添加决策报告 section.

        Args:
            campaign_name: 活动名称
            observations: 观测数据
            reasoning_points: 推理点
            decisions: 决策列表
            similar_cases: 相似案例数
            success_rate: 案例成功率
            evidence: 决策证据

        Returns:
            ReportSection: 决策报告 section
        """
        if self.current_report is None:
            self.start_cycle()

        builder = DecisionReportBuilder()

        # 观测
        if observations:
            for name, (value, prev) in observations.items():
                builder.add_observation(name, value, prev)

        # 推理
        if reasoning_points:
            for point in reasoning_points:
                builder.add_reasoning(point)

        # 决策
        if decisions:
            ev_list: list[DecisionEvidence] = evidence or []
            if similar_cases > 0:
                ev_list.append(DecisionEvidence(
                    source="PatternMemory",
                    description=f"similar cases = {similar_cases}, success rate = {success_rate:.0%}",
                    confidence=min(0.5 + success_rate * 0.5, 0.95),
                ))
            for d in decisions:
                entry = DecisionEntry(
                    action=d["action"],
                    target=d.get("target", campaign_name),
                    reason=d.get("reason", ""),
                    confidence=d.get("confidence", 0.0),
                    evidence=ev_list,
                    expected_outcome=d.get("expected", ""),
                    risk_level=d.get("risk_level", "low"),
                )
                builder.add_decision(entry)

        section = builder.build()
        self.current_report.add_section(section)
        return section

    def add_execution_section(
        self,
        task_name: str,
        actions: list[dict] | None = None,
        description: str = "",
        risk_level: str = "low",
        approval_required: bool = False,
        approval_status: str = "not_required",
        spend: float = 0.0,
        roas: float = 0.0,
    ) -> ReportSection:
        """添加执行报告 section.

        Args:
            task_name: 任务名称
            actions: 动作列表
            description: 描述
            risk_level: 风险等级
            approval_required: 是否需要审批
            approval_status: 审批状态
            spend: 花费
            roas: ROAS

        Returns:
            ReportSection: 执行报告 section
        """
        if self.current_report is None:
            self.start_cycle()

        builder = ExecutionReportBuilder()
        task = builder.set_task(
            task_name=task_name,
            description=description,
            risk_level=risk_level,
            approval_required=approval_required,
            approval_status=approval_status,
            spend=spend,
            roas=roas,
        )

        if actions:
            for a in actions:
                builder.add_action(
                    task=task,
                    action_type=a["action_type"],
                    target=a.get("target", ""),
                    status=a.get("status", "success"),
                    result=a.get("result", ""),
                    error=a.get("error", ""),
                    duration_ms=a.get("duration_ms", 0.0),
                )

        section = builder.build()
        self.current_report.add_section(section)
        return section

    def add_health_section(
        self,
        status: str,
        triggered_rules: list[str] | None = None,
        warnings: list[str] | None = None,
        recommendations: list[str] | None = None,
        active_alerts: int = 0,
        critical_alerts: int = 0,
        **metric_categories,
    ) -> ReportSection:
        """添加健康报告 section.

        Args:
            status: 健康状态
            triggered_rules: 触发规则
            warnings: 警告
            recommendations: 建议
            active_alerts: 活跃告警
            critical_alerts: 严重告警
            **metric_categories: 各类指标

        Returns:
            ReportSection: 健康报告 section
        """
        if self.current_report is None:
            self.start_cycle()

        builder = HealthReportBuilder()
        builder.set_status(status)

        if triggered_rules:
            builder.add_triggered_rules(triggered_rules)
        if warnings:
            builder.add_warnings(warnings)
        if recommendations:
            for r in recommendations:
                builder.add_recommendation(r)

        builder.set_alerts(active=active_alerts, critical=critical_alerts)

        if "runtime_metrics" in metric_categories:
            builder.add_runtime_metrics(**metric_categories["runtime_metrics"])
        if "decision_metrics" in metric_categories:
            builder.add_decision_metrics(**metric_categories["decision_metrics"])
        if "execution_metrics" in metric_categories:
            builder.add_execution_metrics(**metric_categories["execution_metrics"])
        if "tool_metrics" in metric_categories:
            builder.add_tool_metrics(**metric_categories["tool_metrics"])

        section = builder.build()
        self.current_report.add_section(section)
        return section

    def add_learning_section(
        self,
        learnings: list[dict] | None = None,
        pattern_updates: list[dict] | None = None,
        memory_feedbacks: list[dict] | None = None,
    ) -> ReportSection:
        """添加学习报告 section.

        Args:
            learnings: 学习记录
            pattern_updates: 模式更新
            memory_feedbacks: 记忆更新

        Returns:
            ReportSection: 学习报告 section
        """
        if self.current_report is None:
            self.start_cycle()

        builder = LearningReportBuilder()

        if learnings:
            for l in learnings:
                builder.add_learning(LearningEntry(
                    action=l["action"],
                    condition=l.get("condition", ""),
                    reward=l.get("reward", 0.0),
                    confidence=l.get("confidence", 0.0),
                    experience_count=l.get("experience_count", 1),
                    source=l.get("source", ""),
                ))

        if pattern_updates:
            for p in pattern_updates:
                builder.add_pattern_update(PatternUpdate(
                    pattern_name=p["name"],
                    old_value=p.get("old"),
                    new_value=p.get("new", 0.0),
                    change=p.get("change", "stable"),
                    description=p.get("description", ""),
                ))

        if memory_feedbacks:
            for m in memory_feedbacks:
                builder.add_memory_feedback(MemoryFeedback(
                    memory_type=m["type"],
                    key=m["key"],
                    action=m["action"],
                    value=m["value"],
                    confidence=m.get("confidence", 1.0),
                ))

        section = builder.build()
        self.current_report.add_section(section)
        return section

    def add_section(self, section: ReportSection) -> None:
        """直接添加预构建的 section."""
        if self.current_report is None:
            self.start_cycle()
        self.current_report.add_section(section)

    # ── Query API ───────────────────────────────────────────────

    def get_latest(self) -> AgentReport | None:
        """获取最新报告 (从存储)."""
        return self.store.get_latest(self.agent_id)

    def get_history(self, limit: int = 50) -> list[AgentReport]:
        """获取历史报告."""
        return self.store.get_history(self.agent_id, limit=limit)

    def get_report(self, report_id: str) -> AgentReport | None:
        """获取指定报告."""
        return self.store.get(report_id)

    def query(self, query: ReportQuery) -> list[AgentReport]:
        """查询报告."""
        return self.store.query(query)

    def get_decision_history(self, limit: int = 50) -> list[dict]:
        """获取最近决策历史."""
        reports = self.store.get_history(self.agent_id, limit=limit)
        decisions = []
        for report in reports:
            for section in report.get_sections_by_type(ReportType.DECISION):
                decisions.append({
                    "report_id": report.report_id,
                    "cycle_id": report.cycle_id,
                    "timestamp": report.timestamp,
                    "summary": section.summary,
                    "confidence": section.confidence,
                })
        return decisions[-limit:]

    def get_execution_history(self, limit: int = 50) -> list[dict]:
        """获取最近执行历史."""
        reports = self.store.get_history(self.agent_id, limit=limit)
        executions = []
        for report in reports:
            for section in report.get_sections_by_type(ReportType.EXECUTION):
                executions.append({
                    "report_id": report.report_id,
                    "cycle_id": report.cycle_id,
                    "timestamp": report.timestamp,
                    "summary": section.summary,
                    "confidence": section.confidence,
                })
        return executions[-limit:]

    def get_learning_history(self, limit: int = 50) -> list[dict]:
        """获取最近学习历史."""
        reports = self.store.get_history(self.agent_id, limit=limit)
        learnings = []
        for report in reports:
            for section in report.get_sections_by_type(ReportType.LEARNING):
                learnings.append({
                    "report_id": report.report_id,
                    "cycle_id": report.cycle_id,
                    "timestamp": report.timestamp,
                    "summary": section.summary,
                    "confidence": section.confidence,
                })
        return learnings[-limit:]

    def get_health_history(self, limit: int = 50) -> list[dict]:
        """获取最近健康历史."""
        reports = self.store.get_history(self.agent_id, limit=limit)
        healths = []
        for report in reports:
            for section in report.get_sections_by_type(ReportType.HEALTH):
                healths.append({
                    "report_id": report.report_id,
                    "cycle_id": report.cycle_id,
                    "timestamp": report.timestamp,
                    "summary": section.summary,
                    "confidence": section.confidence,
                })
        return healths[-limit:]

    # ── Status ──────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """获取 Reporter 状态."""
        latest = self.get_latest()
        return {
            "agent_id": self.agent_id,
            "total_reports": self.store.count(),
            "latest_report": latest.report_id if latest else None,
            "latest_status": latest.status.value if latest else "none",
            "latest_confidence": latest.overall_confidence if latest else 0.0,
            "store_stats": self.store.stats(),
        }

    # ── Output ──────────────────────────────────────────────────

    def render(self, report: AgentReport | None = None, format: ReportFormat = ReportFormat.JSON) -> str:
        """渲染报告.

        Args:
            report: 要渲染的报告 (默认当前报告)
            format: 输出格式

        Returns:
            str: 渲染后的文本
        """
        target = report or self.current_report
        if target is None:
            return ""

        if format == ReportFormat.JSON:
            import json
            return json.dumps(target.to_dict(), ensure_ascii=False, indent=2)
        elif format == ReportFormat.MARKDOWN:
            return target.to_markdown()
        elif format == ReportFormat.TEXT:
            return target.to_text()
        else:
            return target.to_markdown()

    # ── Callbacks ───────────────────────────────────────────────

    def on_report_finalized(self, callback: Callable[[AgentReport], None]) -> None:
        """注册报告完成回调."""
        self._on_report_finalized.append(callback)


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_agent_reporter(
    agent_id: str = "",
    store_type: str = "memory",
    **store_kwargs,
) -> AgentReporter:
    """创建 AgentReporter.

    Args:
        agent_id: Agent 标识
        store_type: 存储类型 ("memory" | "file")
        **store_kwargs: 存储参数

    Returns:
        AgentReporter: 实例
    """
    if store_type == "file":
        store = FileReportStore(**store_kwargs)
    else:
        store = InMemoryReportStore(**store_kwargs)
    return AgentReporter(agent_id=agent_id, store=store)