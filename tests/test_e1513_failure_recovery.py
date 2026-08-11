"""E15.1.3 DAG Scheduler 测试 — 失败恢复.

测试覆盖:
  - 重试次数未耗尽 → RETRY
  - 重试次数耗尽 → SKIP / SKIP_DOWNSTREAM / FAIL_WORKFLOW
  - 可重试任务的 WAITING_RETRY 状态
  - 不可恢复失败 → Workflow FAILED
  - 可选任务失败不影响下游
  - FailureResolution 各动作
  - can_retry() 判断
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.workflow.builder import WorkflowBuilder
from market_ops.creative_vision_runtime.growth_runtime.workflow.context import ExecutionContext
from market_ops.creative_vision_runtime.growth_runtime.workflow.scheduler import (
    DAGScheduler,
    FailureAction,
    FailureResolution,
    ScheduleState,
    TaskScheduleStatus,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_retry_workflow():
    """带重试的 Workflow: A(retry=3) → B → C."""
    builder = WorkflowBuilder("Retry Workflow", workflow_id="wf_retry")
    builder.add_step("Task A", "task_a", task_id="t_a", retry_count=3)
    builder.add_step("Task B", "task_b", task_id="t_b")
    builder.add_step("Task C", "task_c", task_id="t_c")
    builder.depends_on("t_b", "t_a")
    builder.depends_on("t_c", "t_b")
    return builder.build()


def _make_optional_task_workflow():
    """带可选任务的 Workflow: A → B(optional) → C."""
    builder = WorkflowBuilder("Optional Workflow", workflow_id="wf_optional")
    builder.add_step("Task A", "task_a", task_id="t_a")
    builder.add_step("Task B", "task_b", task_id="t_b", metadata={"optional": True})
    builder.add_step("Task C", "task_c", task_id="t_c")
    builder.depends_on("t_b", "t_a")
    builder.depends_on("t_c", "t_b")
    return builder.build()


# ═══════════════════════════════════════════════════════════════
# Test: FailureResolution
# ═══════════════════════════════════════════════════════════════


class TestFailureResolution:
    """FailureResolution 模型测试."""

    def test_default_action(self):
        fr = FailureResolution()
        assert fr.action == FailureAction.FAIL_WORKFLOW
        assert fr.reason == ""
        assert fr.retry_delay_ms == 0

    def test_retry_resolution(self):
        fr = FailureResolution(
            action=FailureAction.RETRY,
            reason="2 attempts remaining",
            retry_delay_ms=5000,
        )
        assert fr.action == FailureAction.RETRY
        assert fr.retry_delay_ms == 5000

    def test_skip_resolution(self):
        fr = FailureResolution(
            action=FailureAction.SKIP,
            reason="No downstream tasks",
        )
        assert fr.action == FailureAction.SKIP

    def test_skip_downstream_resolution(self):
        fr = FailureResolution(
            action=FailureAction.SKIP_DOWNSTREAM,
            reason="Critical downstream blocked",
        )
        assert fr.action == FailureAction.SKIP_DOWNSTREAM


# ═══════════════════════════════════════════════════════════════
# Test: Retry Logic
# ═══════════════════════════════════════════════════════════════


class TestRetryLogic:
    """重试逻辑测试."""

    def setup_method(self):
        self.wf = _make_retry_workflow()
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.scheduler = DAGScheduler(self.wf, self.ctx)
        self.tasks = {t.name: t for t in self.wf.tasks}

    def test_task_with_retry_remaining_returns_retry(self):
        """有重试次数 → RETRY."""
        self.ctx.start()
        self.ctx.fail_task(self.tasks["Task A"].task_id, "network error")

        resolution = self.scheduler.resolve_failure(self.tasks["Task A"].task_id)
        assert resolution.action == FailureAction.RETRY
        assert "3 retry" in resolution.reason

    def test_task_retry_exhausted_no_downstream_returns_skip(self):
        """重试耗尽 + 无下游 → SKIP."""
        self.ctx.start()
        task_c = self.tasks["Task C"]
        # 手动模拟重试耗尽
        state = self.ctx.get_task_state(task_c.task_id)
        assert state is not None
        state.retry_current = 0
        state.retry_max = 0  # 无重试
        self.ctx.fail_task(task_c.task_id, "error")

        resolution = self.scheduler.resolve_failure(task_c.task_id)
        assert resolution.action == FailureAction.SKIP

    def test_task_retry_exhausted_with_downstream_returns_skip_downstream(self):
        """重试耗尽 + 有下游 → SKIP_DOWNSTREAM."""
        self.ctx.start()
        task_a = self.tasks["Task A"]
        state = self.ctx.get_task_state(task_a.task_id)
        assert state is not None
        state.retry_current = 3
        state.retry_max = 3  # 重试耗尽
        self.ctx.fail_task(task_a.task_id, "persistent error")

        resolution = self.scheduler.resolve_failure(task_a.task_id)
        assert resolution.action == FailureAction.SKIP_DOWNSTREAM

    def test_can_retry(self):
        """can_retry() 判断."""
        self.ctx.start()
        self.ctx.fail_task(self.tasks["Task A"].task_id, "error")
        assert self.scheduler.can_retry(self.tasks["Task A"].task_id) is True

        # 耗尽重试
        state = self.ctx.get_task_state(self.tasks["Task A"].task_id)
        assert state is not None
        state.retry_current = 3
        state.retry_max = 3
        assert self.scheduler.can_retry(self.tasks["Task A"].task_id) is False

    def test_unknown_task_returns_fail_workflow(self):
        """未知任务 → FAIL_WORKFLOW."""
        self.ctx.start()
        resolution = self.scheduler.resolve_failure("nonexistent")
        assert resolution.action == FailureAction.FAIL_WORKFLOW

    def test_no_execution_state_returns_fail_workflow(self):
        """无执行状态 → FAIL_WORKFLOW."""
        self.ctx.start()
        # 创建一个 ctx 但没有 init task state
        ctx = ExecutionContext(workflow_id=self.wf.workflow_id)
        ctx.start()
        scheduler = DAGScheduler(self.wf, ctx)
        resolution = scheduler.resolve_failure(self.tasks["Task A"].task_id)
        assert resolution.action == FailureAction.FAIL_WORKFLOW


# ═══════════════════════════════════════════════════════════════
# Test: WAITING_RETRY Status
# ═══════════════════════════════════════════════════════════════


class TestWaitingRetryStatus:
    """WAITING_RETRY 调度状态."""

    def setup_method(self):
        self.wf = _make_retry_workflow()
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.scheduler = DAGScheduler(self.wf, self.ctx)
        self.tasks = {t.name: t for t in self.wf.tasks}

    def test_failed_with_retry_shows_waiting_retry(self):
        """失败但可重试 → WAITING_RETRY."""
        self.ctx.start()
        self.ctx.fail_task(self.tasks["Task A"].task_id, "error")

        status = self.scheduler.get_task_schedule_status(self.tasks["Task A"].task_id)
        assert status == TaskScheduleStatus.WAITING_RETRY

    def test_waiting_retry_in_schedule_result(self):
        """WAITING_RETRY 出现在 failed_tasks 中."""
        self.ctx.start()
        self.ctx.fail_task(self.tasks["Task A"].task_id, "error")

        result = self.scheduler.get_next_tasks()
        failed_ids = [t.task_id for t in result.failed_tasks]
        assert self.tasks["Task A"].task_id in failed_ids

    def test_after_retry_task_becomes_pending(self):
        """重试后 Task 回到 PENDING."""
        self.ctx.start()
        self.ctx.fail_task(self.tasks["Task A"].task_id, "error")
        self.ctx.retry_task(self.tasks["Task A"].task_id)

        status = self.scheduler.get_task_schedule_status(self.tasks["Task A"].task_id)
        assert status == TaskScheduleStatus.READY


# ═══════════════════════════════════════════════════════════════
# Test: Workflow Failure
# ═══════════════════════════════════════════════════════════════


class TestWorkflowFailure:
    """Workflow 级别失败."""

    def setup_method(self):
        self.wf = _make_retry_workflow()
        self.tasks = {t.name: t for t in self.wf.tasks}

    def test_all_tasks_failed_no_retry_workflow_fails(self):
        """所有任务失败且无重试 → Workflow FAILED."""
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.scheduler = DAGScheduler(self.wf, self.ctx)
        self.ctx.start()

        for task in self.wf.tasks:
            state = self.ctx.get_task_state(task.task_id)
            assert state is not None
            state.retry_max = 0
            self.ctx.fail_task(task.task_id, "error")

        result = self.scheduler.get_next_tasks()
        assert result.state == ScheduleState.FAILED

    def test_single_failure_with_retry_does_not_fail_workflow(self):
        """单个失败但有重试 → Workflow 不失败."""
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.scheduler = DAGScheduler(self.wf, self.ctx)
        self.ctx.start()

        self.ctx.fail_task(self.tasks["Task A"].task_id, "error")
        result = self.scheduler.get_next_tasks()
        # 有重试 → 不是 FAILED
        assert result.state != ScheduleState.FAILED

    def test_failure_with_retry_exhausted_blocks_downstream(self):
        """重试耗尽后下游被阻塞."""
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.scheduler = DAGScheduler(self.wf, self.ctx)
        self.ctx.start()

        state = self.ctx.get_task_state(self.tasks["Task A"].task_id)
        assert state is not None
        state.retry_current = 3
        state.retry_max = 3
        self.ctx.fail_task(self.tasks["Task A"].task_id, "error")

        result = self.scheduler.get_next_tasks()
        # 下游被阻塞
        blocked_ids = [t.task_id for t in result.blocked_tasks]
        assert self.tasks["Task B"].task_id in blocked_ids


# ═══════════════════════════════════════════════════════════════
# Test: Optional Task
# ═══════════════════════════════════════════════════════════════


class TestOptionalTask:
    """可选任务失败恢复."""

    def setup_method(self):
        self.wf = _make_optional_task_workflow()
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.scheduler = DAGScheduler(self.wf, self.ctx)
        self.tasks = {t.name: t for t in self.wf.tasks}

    def test_optional_task_failure_resolves_to_skip(self):
        """可选任务失败 → SKIP."""
        self.ctx.start()
        task_b = self.tasks["Task B"]
        state = self.ctx.get_task_state(task_b.task_id)
        assert state is not None
        state.retry_current = 0
        state.retry_max = 0
        self.ctx.fail_task(task_b.task_id, "error")

        resolution = self.scheduler.resolve_failure(task_b.task_id)
        assert resolution.action == FailureAction.SKIP

    def test_optional_task_skip_unblocks_downstream(self):
        """可选任务 SKIP 后下游解锁."""
        self.ctx.start()
        self.ctx.complete_task(self.tasks["Task A"].task_id)
        task_b = self.tasks["Task B"]
        self.ctx.skip_task(task_b.task_id)

        status = self.scheduler.get_task_schedule_status(self.tasks["Task C"].task_id)
        assert status == TaskScheduleStatus.READY


# ═══════════════════════════════════════════════════════════════
# Test: Timeout Recovery
# ═══════════════════════════════════════════════════════════════


class TestTimeoutRecovery:
    """超时恢复."""

    def setup_method(self):
        self.wf = _make_retry_workflow()
        self.tasks = {t.name: t for t in self.wf.tasks}

    def test_timeout_with_retry_shows_waiting_retry(self):
        """超时但可重试 → WAITING_RETRY."""
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.scheduler = DAGScheduler(self.wf, self.ctx)
        self.ctx.start()

        state = self.ctx.get_task_state(self.tasks["Task A"].task_id)
        assert state is not None
        state.timeout()

        status = self.scheduler.get_task_schedule_status(self.tasks["Task A"].task_id)
        assert status == TaskScheduleStatus.WAITING_RETRY

    def test_timeout_exhausted_shows_failed(self):
        """超时且重试耗尽 → FAILED."""
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.scheduler = DAGScheduler(self.wf, self.ctx)
        self.ctx.start()

        state = self.ctx.get_task_state(self.tasks["Task A"].task_id)
        assert state is not None
        state.retry_current = 3
        state.retry_max = 3
        state.timeout()

        status = self.scheduler.get_task_schedule_status(self.tasks["Task A"].task_id)
        assert status == TaskScheduleStatus.FAILED