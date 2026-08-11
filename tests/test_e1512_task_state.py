"""E15.1.2 Task State 测试 — 上下文 Task 状态管理测试.

测试覆盖:
  - ExecutionContext 中 Task 状态管理
  - init_task_state / start_task / complete_task / fail_task / skip_task
  - retry_task
  - 查询方法 (pending/running/completed/failed)
  - all_tasks_completed / has_failed_task
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.workflow.builder import (
    create_campaign_optimization_workflow,
)
from market_ops.creative_vision_runtime.growth_runtime.workflow.context import ExecutionContext
from market_ops.creative_vision_runtime.growth_runtime.workflow.state import (
    TaskExecutionStatus,
    WorkflowState,
)


class TestTaskStateManagement:
    """ExecutionContext Task 状态管理测试."""

    def setup_method(self):
        self.wf = create_campaign_optimization_workflow()
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.tasks = self.wf.flat_topological_order()

    # ── Init ─────────────────────────────────────────────────

    def test_init_task_state(self):
        state = self.ctx.init_task_state("new_task", "New Task", retry_max=3)
        assert state.task_id == "new_task"
        assert state.task_name == "New Task"
        assert state.retry_max == 3
        assert state.status == TaskExecutionStatus.PENDING

    def test_init_existing_task_returns_existing(self):
        task = self.tasks[0]
        state1 = self.ctx.init_task_state(task.task_id, "Custom Name")
        state2 = self.ctx.init_task_state(task.task_id, "Other Name")
        # 已经存在，返回原来的
        assert state1.task_name == task.name

    # ── Start ────────────────────────────────────────────────

    def test_start_task(self):
        task = self.tasks[0]
        state = self.ctx.start_task(task.task_id)
        assert state is not None
        assert state.status == TaskExecutionStatus.RUNNING
        assert state.started_at != ""

    def test_start_task_nonexistent(self):
        assert self.ctx.start_task("nonexistent") is None

    # ── Complete ─────────────────────────────────────────────

    def test_complete_task(self):
        task = self.tasks[0]
        self.ctx.start_task(task.task_id)
        state = self.ctx.complete_task(task.task_id, {"roas": 0.48})
        assert state.status == TaskExecutionStatus.COMPLETED
        assert state.output["roas"] == 0.48

        # 输出也记录到 context.outputs
        output = self.ctx.get_output(task.task_id)
        assert output["roas"] == 0.48

    def test_complete_task_without_output(self):
        task = self.tasks[0]
        self.ctx.complete_task(task.task_id)
        state = self.ctx.get_task_state(task.task_id)
        assert state.status == TaskExecutionStatus.COMPLETED

    def test_complete_task_nonexistent(self):
        assert self.ctx.complete_task("nonexistent") is None

    # ── Fail ─────────────────────────────────────────────────

    def test_fail_task(self):
        task = self.tasks[0]
        self.ctx.start_task(task.task_id)
        state = self.ctx.fail_task(task.task_id, "API timeout")
        assert state.status == TaskExecutionStatus.FAILED
        assert state.error == "API timeout"

    def test_fail_task_nonexistent(self):
        assert self.ctx.fail_task("nonexistent") is None

    # ── Skip ─────────────────────────────────────────────────

    def test_skip_task(self):
        task = self.tasks[0]
        state = self.ctx.skip_task(task.task_id, "Already done")
        assert state.status == TaskExecutionStatus.SKIPPED
        assert state.error == "Already done"

    def test_skip_task_nonexistent(self):
        assert self.ctx.skip_task("nonexistent") is None

    # ── Retry ────────────────────────────────────────────────

    def test_retry_task(self):
        task = self.tasks[0]
        # 设置 retry_max 使任务可重试
        state = self.ctx.get_task_state(task.task_id)
        state.retry_max = 3
        self.ctx.fail_task(task.task_id, "error")
        state = self.ctx.retry_task(task.task_id)
        assert state is not None
        assert state.status == TaskExecutionStatus.PENDING
        assert state.retry_current == 1
        assert state.error == ""

    def test_retry_task_exhausted(self):
        task = self.tasks[0]
        state = self.ctx.get_task_state(task.task_id)
        state.retry_max = 1
        self.ctx.fail_task(task.task_id, "error")
        self.ctx.retry_task(task.task_id)
        self.ctx.fail_task(task.task_id, "error again")
        result = self.ctx.retry_task(task.task_id)
        assert result is None

    def test_retry_task_nonexistent(self):
        assert self.ctx.retry_task("nonexistent") is None

    # ── Update State ─────────────────────────────────────────

    def test_update_task_state(self):
        task = self.tasks[0]
        state = self.ctx.update_task_state(task.task_id, TaskExecutionStatus.RUNNING)
        assert state.status == TaskExecutionStatus.RUNNING

    def test_update_task_state_nonexistent(self):
        assert self.ctx.update_task_state("nonexistent", TaskExecutionStatus.RUNNING) is None

    # ── Query ────────────────────────────────────────────────

    def test_get_pending_tasks(self):
        pending = self.ctx.get_pending_tasks()
        assert len(pending) == 5

    def test_get_running_tasks(self):
        task = self.tasks[0]
        self.ctx.start_task(task.task_id)
        running = self.ctx.get_running_tasks()
        assert len(running) == 1

    def test_get_completed_tasks(self):
        task = self.tasks[0]
        self.ctx.complete_task(task.task_id)
        completed = self.ctx.get_completed_tasks()
        assert len(completed) == 1

    def test_get_failed_tasks(self):
        task = self.tasks[0]
        self.ctx.fail_task(task.task_id, "oops")
        failed = self.ctx.get_failed_tasks()
        assert len(failed) == 1

    # ── All Completed / Has Failed ───────────────────────────

    def test_all_tasks_completed(self):
        assert self.ctx.all_tasks_completed() is False
        for task in self.tasks:
            self.ctx.complete_task(task.task_id)
        assert self.ctx.all_tasks_completed() is True

    def test_all_tasks_completed_empty(self):
        ctx = ExecutionContext()
        assert ctx.all_tasks_completed() is False

    def test_has_failed_task(self):
        assert self.ctx.has_failed_task() is False
        self.ctx.fail_task(self.tasks[0].task_id, "error")
        assert self.ctx.has_failed_task() is True

    # ── Cross-Task Data Flow ─────────────────────────────────

    def test_cross_task_data_flow(self):
        """模拟跨 Task 数据传递: Analyze → Generate → Approve."""
        analyze = self.tasks[0]
        generate = self.tasks[1]
        approve = self.tasks[2]

        # Task 1: Analyze
        self.ctx.start_task(analyze.task_id)
        self.ctx.complete_task(analyze.task_id, {"roas": 0.48, "fatigue": 0.76})

        # Task 2: Generate — 读取 Analyze 输出
        analysis = self.ctx.get_output(analyze.task_id)
        assert analysis["fatigue"] == 0.76
        self.ctx.start_task(generate.task_id)
        self.ctx.complete_task(generate.task_id, {"creative_id": "crt_001"})

        # Task 3: Approve
        self.ctx.start_task(approve.task_id)
        self.ctx.complete_task(approve.task_id, {"approved": True})

        # 验证所有输出
        assert self.ctx.get_output(analyze.task_id)["roas"] == 0.48
        assert self.ctx.get_output(generate.task_id)["creative_id"] == "crt_001"
        assert self.ctx.get_output(approve.task_id)["approved"] is True

    # ── Full Workflow Simulation ─────────────────────────────

    def test_full_workflow_simulation(self):
        """完整 5 步 Workflow 模拟."""
        self.ctx.start()

        # 按拓扑顺序执行每个 Task
        for task in self.tasks:
            assert self.ctx.get_task_state(task.task_id).status == TaskExecutionStatus.PENDING
            self.ctx.start_task(task.task_id)
            assert self.ctx.get_task_state(task.task_id).status == TaskExecutionStatus.RUNNING
            self.ctx.complete_task(task.task_id, {"task": task.name, "done": True})
            assert self.ctx.get_task_state(task.task_id).status == TaskExecutionStatus.COMPLETED

        self.ctx.complete()
        assert self.ctx.all_tasks_completed()
        assert self.ctx.state == WorkflowState.SUCCESS
        assert self.ctx.progress()["percentage"] == 100.0