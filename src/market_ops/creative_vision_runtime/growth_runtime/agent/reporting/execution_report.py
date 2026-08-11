"""E13.7.4.4 Execution Report — 执行报告生成器.

执行报告追踪 Agent 每一步执行:
  - 执行任务 (Task)
  - 动作列表 (Actions)
  - 安全评估 (Risk, Approval)
  - 执行结果 (Success/Failure, Metrics)
  - 回滚记录 (Rollback)

连接:
  - E13.6 Execution Engine: 执行结果
  - E13.7.4.2 Policy: 审批状态
  - E13.7.1 Real Tool Adapter: 工具调用
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .report_models import (
    ReportSection,
    ReportEvidence,
    ReportMetric,
    ReportType,
)


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExecutionAction:
    """单个执行动作."""

    action_id: str
    action_type: str          # "create_campaign", "update_budget", "upload_creative"
    target: str               # campaign_id / creative_id
    status: str = "pending"   # "success", "failure", "pending", "rollback"
    result: str = ""          # 结果描述
    error: str = ""           # 错误信息
    duration_ms: float = 0.0
    rollback_id: str = ""     # 关联的回滚 ID


@dataclass
class ExecutionTask:
    """执行任务."""

    task_id: str
    task_name: str          # "Generate Creative Mutation", "Scale Budget"
    description: str = ""
    actions: list[ExecutionAction] = field(default_factory=list)
    risk_level: str = "low"
    approval_required: bool = False
    approval_status: str = "not_required"
    overall_status: str = "pending"
    spend: float = 0.0
    roas: float = 0.0
    started_at: str = ""
    completed_at: str = ""

    @property
    def success_count(self) -> int:
        return sum(1 for a in self.actions if a.status == "success")

    @property
    def failure_count(self) -> int:
        return sum(1 for a in self.actions if a.status == "failure")

    @property
    def rollback_count(self) -> int:
        return sum(1 for a in self.actions if a.status == "rollback")

    @property
    def success_rate(self) -> float:
        total = len(self.actions)
        if total == 0:
            return 1.0
        return self.success_count / total


# ═══════════════════════════════════════════════════════════════
# ExecutionReportBuilder
# ═══════════════════════════════════════════════════════════════


class ExecutionReportBuilder:
    """执行报告生成器.

    使用方式:
        builder = ExecutionReportBuilder()
        builder.set_task("Generate Creative Mutation", "基于疲劳检测触发素材变异")
        builder.add_action(ExecutionAction(
            action_id="a1",
            action_type="generate_dna",
            target="creative_123",
            status="success",
            result="生成 3 个变异体",
            duration_ms=1500,
        ))
        builder.add_action(ExecutionAction(...))
        section = builder.build()
    """

    def __init__(self):
        self._tasks: list[ExecutionTask] = []

    def set_task(
        self,
        task_name: str,
        description: str = "",
        task_id: str = "",
        risk_level: str = "low",
        approval_required: bool = False,
        approval_status: str = "not_required",
        spend: float = 0.0,
        roas: float = 0.0,
    ) -> ExecutionTask:
        """创建并添加一个执行任务.

        Returns:
            ExecutionTask: 创建的任务对象
        """
        task = ExecutionTask(
            task_id=task_id or f"task_{len(self._tasks) + 1}",
            task_name=task_name,
            description=description,
            risk_level=risk_level,
            approval_required=approval_required,
            approval_status=approval_status,
            spend=spend,
            roas=roas,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self._tasks.append(task)
        return task

    def add_action(
        self,
        task: ExecutionTask,
        action_type: str,
        target: str,
        status: str = "success",
        result: str = "",
        error: str = "",
        duration_ms: float = 0.0,
        action_id: str = "",
    ) -> ExecutionAction:
        """向任务添加执行动作.

        Args:
            task: 目标任务
            action_type: 动作类型
            target: 目标
            status: 状态
            result: 结果描述
            error: 错误信息
            duration_ms: 耗时 (毫秒)
            action_id: 动作 ID

        Returns:
            ExecutionAction: 创建的动作对象
        """
        action = ExecutionAction(
            action_id=action_id or f"act_{len(task.actions) + 1}",
            action_type=action_type,
            target=target,
            status=status,
            result=result,
            error=error,
            duration_ms=duration_ms,
        )
        task.actions.append(action)
        return action

    def build(self) -> ReportSection:
        """构建 ReportSection."""
        content_lines = []
        all_metrics: list[ReportMetric] = []
        total_actions = 0
        total_success = 0
        total_failure = 0
        total_rollback = 0

        for task in self._tasks:
            task.completed_at = datetime.now(timezone.utc).isoformat()

            # 任务状态
            if task.failure_count > 0:
                task.overall_status = "partial_failure" if task.success_count > 0 else "failure"
            else:
                task.overall_status = "success"

            total_actions += len(task.actions)
            total_success += task.success_count
            total_failure += task.failure_count
            total_rollback += task.rollback_count

            content_lines.append(f"### Task: {task.task_name}")
            content_lines.append("")
            if task.description:
                content_lines.append(f"*{task.description}*")
                content_lines.append("")

            # 安全信息
            risk_emoji = {"low": "LOW", "medium": "MEDIUM", "high": "HIGH"}.get(task.risk_level, "LOW")
            content_lines.append(f"**Safety**: Risk {risk_emoji} | Approval: {task.approval_status.upper()}")
            content_lines.append("")

            # 动作列表
            status_emoji = {"success": "✓", "failure": "✗", "pending": "○", "rollback": "↩"}
            content_lines.append("| Action | Target | Status | Result |")
            content_lines.append("|--------|--------|--------|--------|")
            for action in task.actions:
                emoji = status_emoji.get(action.status, "?")
                result_text = action.result if action.status == "success" else (action.error or action.result)
                content_lines.append(
                    f"| {action.action_type} | {action.target} | {emoji} {action.status} | {result_text} |"
                )
            content_lines.append("")

            # 结果摘要
            content_lines.append(f"**Result**: {task.success_count}/{len(task.actions)} actions succeeded")
            if task.spend > 0:
                content_lines.append(f"**Spend**: ${task.spend:.2f}")
            if task.roas > 0:
                content_lines.append(f"**ROAS**: {task.roas:.2f}")
            content_lines.append("")

            all_metrics.append(ReportMetric(
                name=f"{task.task_name}_success_rate",
                value=task.success_rate,
                unit="%",
            ))

        content = "\n".join(content_lines)

        # 整体指标
        if total_actions > 0:
            all_metrics.append(ReportMetric(
                name="total_actions",
                value=float(total_actions),
                unit="count",
            ))
            all_metrics.append(ReportMetric(
                name="execution_success_rate",
                value=total_success / total_actions,
                unit="%",
            ))
            all_metrics.append(ReportMetric(
                name="execution_failure_rate",
                value=total_failure / total_actions,
                unit="%",
            ))
            all_metrics.append(ReportMetric(
                name="rollback_rate",
                value=total_rollback / total_actions,
                unit="%",
            ))

        # 摘要
        if total_actions:
            summary = f"Execution: {total_success}/{total_actions} succeeded, {total_failure} failed, {total_rollback} rollback"
        else:
            summary = "No execution actions recorded."

        overall_confidence = 1.0
        if total_actions > 0:
            overall_confidence = total_success / total_actions

        section = ReportSection(
            type=ReportType.EXECUTION,
            title="Growth Agent Execution Report",
            content=content,
            summary=summary,
            metrics=all_metrics,
            confidence=overall_confidence,
        )

        return section


# ═══════════════════════════════════════════════════════════════
# Helper: Quick Execution Report
# ═══════════════════════════════════════════════════════════════


def create_execution_report(
    task_name: str,
    actions: list[dict],
    risk_level: str = "low",
    approval_required: bool = False,
    spend: float = 0.0,
    roas: float = 0.0,
) -> ReportSection:
    """快捷创建执行报告.

    Args:
        task_name: 任务名称
        actions: 动作列表 [{action_type, target, status, result}]
        risk_level: 风险等级
        approval_required: 是否需要审批
        spend: 花费
        roas: ROAS

    Returns:
        ReportSection: 执行报告 section
    """
    builder = ExecutionReportBuilder()
    task = builder.set_task(
        task_name=task_name,
        risk_level=risk_level,
        approval_required=approval_required,
        approval_status="required" if approval_required else "not_required",
        spend=spend,
        roas=roas,
    )
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
    return builder.build()