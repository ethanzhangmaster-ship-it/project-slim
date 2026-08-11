"""E15.1.3 DAG Scheduler 测试 — 上下文感知调度.

测试覆盖:
  - PAUSED 状态阻止调度
  - WAITING 状态阻止调度
  - 审批感知 (requires_approval)
  - 审批通过后任务解锁
  - 终端状态 (SUCCESS/FAILED/CANCELLED)
  - 审批上下文 API
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.workflow.builder import WorkflowBuilder
from market_ops.creative_vision_runtime.growth_runtime.workflow.context import ExecutionContext
from market_ops.creative_vision_runtime.growth_runtime.workflow.scheduler import (
    DAGScheduler,
    ScheduleState,
    TaskScheduleStatus,
)
from market_ops.creative_vision_runtime.growth_runtime.workflow.state import WorkflowState


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_approval_workflow():
    """带审批的 Workflow: A → B(approval) → C."""
    builder = WorkflowBuilder("Approval Workflow", workflow_id="wf_approval")
    builder.add_step("Task A", "task_a", task_id="t_a")
    builder.add_step("Task B", "task_b", task_id="t_b", requires_approval=True)
    builder.add_step("Task C", "task_c", task_id="t_c")
    builder.depends_on("t_b", "t_a")
    builder.depends_on("t_c", "t_b")
    return builder.build()


# ═══════════════════════════════════════════════════════════════
# Test: Context State Awareness
# ═══════════════════════════════════════════════════════════════


class TestContextStateAwareness:
    """上下文状态感知."""

    def setup_method(self):
        builder = WorkflowBuilder("State Aware", workflow_id="wf_state")
        builder.add_step("Task A", "task_a", task_id="t_a")
        self.wf = builder.build()
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.scheduler = DAGScheduler(self.wf, self.ctx)

    def test_paused_context_blocks_scheduling(self):
        """PAUSED → WAITING."""
        self.ctx.start()
        self.ctx.pause()

        result = self.scheduler.get_next_tasks()
        assert result.state == ScheduleState.WAITING
        assert result.reason == "Workflow is paused"
        assert len(result.next_tasks) == 0

    def test_resumed_context_allows_scheduling(self):
        """PAUSED → RESUME → READY."""
        self.ctx.start()
        self.ctx.pause()
        self.ctx.resume()

        result = self.scheduler.get_next_tasks()
        assert result.state == ScheduleState.READY
        assert len(result.next_tasks) == 1

    def test_waiting_context_blocks_scheduling(self):
        """WAITING → WAITING."""
        self.ctx.start()
        self.ctx.wait()

        result = self.scheduler.get_next_tasks()
        assert result.state == ScheduleState.WAITING
        assert "waiting for external event" in result.reason

    def test_success_terminal(self):
        """SUCCESS → COMPLETED."""
        self.ctx.start()
        self.ctx.complete()

        result = self.scheduler.get_next_tasks()
        assert result.state == ScheduleState.COMPLETED
        assert "completed successfully" in result.reason

    def test_failed_terminal(self):
        """FAILED → FAILED."""
        self.ctx.start()
        self.ctx.fail("critical error")

        result = self.scheduler.get_next_tasks()
        assert result.state == ScheduleState.FAILED
        assert result.reason == "Workflow has failed"

    def test_cancelled_terminal(self):
        """CANCELLED → FAILED."""
        self.ctx.start()
        self.ctx.cancel()

        result = self.scheduler.get_next_tasks()
        assert result.state == ScheduleState.FAILED

    def test_can_proceed_paused(self):
        """PAUSED 时 can_proceed() = True (等待恢复)."""
        self.ctx.start()
        self.ctx.pause()
        assert self.scheduler.can_proceed() is True

    def test_can_proceed_terminal(self):
        """终端状态 can_proceed() = False."""
        self.ctx.start()
        self.ctx.complete()
        assert self.scheduler.can_proceed() is False


# ═══════════════════════════════════════════════════════════════
# Test: Approval Awareness
# ═══════════════════════════════════════════════════════════════


class TestApprovalAwareness:
    """审批感知."""

    def setup_method(self):
        self.wf = _make_approval_workflow()
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.scheduler = DAGScheduler(self.wf, self.ctx)
        self.tasks = {t.name: t for t in self.wf.tasks}

    def test_approval_task_waits_when_deps_met(self):
        """依赖满足但未审批 → WAITING_APPROVAL."""
        self.ctx.start()
        self.ctx.complete_task(self.tasks["Task A"].task_id)

        status = self.scheduler.get_task_schedule_status(self.tasks["Task B"].task_id)
        assert status == TaskScheduleStatus.WAITING_APPROVAL

    def test_approval_task_in_schedule_result(self):
        """审批任务出现在 waiting_approval_tasks."""
        self.ctx.start()
        self.ctx.complete_task(self.tasks["Task A"].task_id)

        result = self.scheduler.get_next_tasks()
        assert result.state == ScheduleState.WAITING
        approval_ids = [t.task_id for t in result.waiting_approval_tasks]
        assert self.tasks["Task B"].task_id in approval_ids

    def test_approval_granted_task_becomes_ready(self):
        """审批通过 → READY."""
        self.ctx.start()
        self.ctx.complete_task(self.tasks["Task A"].task_id)

        # 设置审批通过
        self.ctx.set_approval_context(
            task_id=self.tasks["Task B"].task_id,
            requested_by="operator",
            risk_level="low",
            reason="Approved for testing",
        )
        self.ctx.metadata["approval"]["status"] = "approved"

        status = self.scheduler.get_task_schedule_status(self.tasks["Task B"].task_id)
        assert status == TaskScheduleStatus.READY

    def test_approval_not_granted_task_remains_waiting(self):
        """审批未通过 → 仍 WAITING_APPROVAL."""
        self.ctx.start()
        self.ctx.complete_task(self.tasks["Task A"].task_id)

        self.ctx.set_approval_context(
            task_id=self.tasks["Task B"].task_id,
            requested_by="operator",
            risk_level="low",
            reason="Pending review",
        )
        # 未设置 status: "approved"

        status = self.scheduler.get_task_schedule_status(self.tasks["Task B"].task_id)
        assert status == TaskScheduleStatus.WAITING_APPROVAL

    def test_approval_wrong_task_id_not_granted(self):
        """审批上下文 task_id 不匹配 → 不通过."""
        self.ctx.start()
        self.ctx.complete_task(self.tasks["Task A"].task_id)

        self.ctx.set_approval_context(
            task_id="different_task",
            requested_by="operator",
            risk_level="low",
            reason="test",
        )
        self.ctx.metadata["approval"]["status"] = "approved"

        status = self.scheduler.get_task_schedule_status(self.tasks["Task B"].task_id)
        assert status == TaskScheduleStatus.WAITING_APPROVAL

    def test_no_approval_context_means_not_granted(self):
        """无审批上下文 → 不通过."""
        self.ctx.start()
        self.ctx.complete_task(self.tasks["Task A"].task_id)

        status = self.scheduler.get_task_schedule_status(self.tasks["Task B"].task_id)
        assert status == TaskScheduleStatus.WAITING_APPROVAL

    def test_approval_full_flow(self):
        """完整审批流程: A → 审批 B → C."""
        self.ctx.start()

        # A 完成
        self.ctx.complete_task(self.tasks["Task A"].task_id)

        result = self.scheduler.get_next_tasks()
        assert result.state == ScheduleState.WAITING

        # 审批通过
        self.ctx.set_approval_context(
            task_id=self.tasks["Task B"].task_id,
            requested_by="operator",
            risk_level="low",
            reason="Approved",
        )
        self.ctx.metadata["approval"]["status"] = "approved"

        result = self.scheduler.get_next_tasks()
        assert result.next_tasks == [self.tasks["Task B"].task_id]

        # B 完成
        self.ctx.complete_task(self.tasks["Task B"].task_id)

        result = self.scheduler.get_next_tasks()
        assert result.next_tasks == [self.tasks["Task C"].task_id]


# ═══════════════════════════════════════════════════════════════
# Test: Combined Scenarios
# ═══════════════════════════════════════════════════════════════


class TestCombinedScenarios:
    """组合场景."""

    def test_pause_during_approval(self):
        """审批等待中暂停."""
        wf = _make_approval_workflow()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = DAGScheduler(wf, ctx)
        tasks = {t.name: t for t in wf.tasks}

        ctx.start()
        ctx.complete_task(tasks["Task A"].task_id)

        # 审批等待中
        result = scheduler.get_next_tasks()
        assert result.state == ScheduleState.WAITING

        # 暂停
        ctx.pause()
        result = scheduler.get_next_tasks()
        assert result.state == ScheduleState.WAITING
        assert result.reason == "Workflow is paused"

        # 恢复 + 审批
        ctx.resume()
        ctx.set_approval_context(
            task_id=tasks["Task B"].task_id,
            reason="Approved",
        )
        ctx.metadata["approval"]["status"] = "approved"

        result = scheduler.get_next_tasks()
        assert result.next_tasks == [tasks["Task B"].task_id]

    def test_running_task_blocks_context_pause_effect(self):
        """PAUSED 时 running 任务仍被识别."""
        builder = WorkflowBuilder("Running + Pause", workflow_id="wf_rp")
        builder.add_step("Task A", "task_a", task_id="t_a")
        builder.add_step("Task B", "task_b", task_id="t_b")
        builder.depends_on("t_b", "t_a")
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = DAGScheduler(wf, ctx)
        tasks = wf.flat_topological_order()

        ctx.start()
        ctx.start_task(tasks[0].task_id)

        # PAUSED 阻止新调度
        ctx.pause()
        result = scheduler.get_next_tasks()
        assert result.state == ScheduleState.WAITING

        # 恢复后 Task B 仍被阻塞 (A 还在 running)
        ctx.resume()
        result = scheduler.get_next_tasks()
        assert result.state == ScheduleState.RUNNING
        assert len(result.running_tasks) == 1
        assert result.running_tasks[0].task_id == tasks[0].task_id

    def test_created_state_still_schedules(self):
        """CREATED 状态 (未 start) 仍可调度."""
        builder = WorkflowBuilder("Created", workflow_id="wf_created")
        builder.add_step("Task A", "task_a", task_id="t_a")
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = DAGScheduler(wf, ctx)

        # CREATED 状态不被视为终端 → 仍可调度
        result = scheduler.get_next_tasks()
        assert result.state == ScheduleState.READY
        assert len(result.next_tasks) == 1