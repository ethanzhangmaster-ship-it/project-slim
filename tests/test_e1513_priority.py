"""E15.1.3 Task Scheduler 测试 — 优先级调度.

测试覆盖:
  - TaskPriority 枚举 (CRITICAL/HIGH/NORMAL/LOW)
  - from_string / from_metadata 解析
  - 优先级排序 (CRITICAL > HIGH > NORMAL > LOW)
  - 同层并行任务按优先级调度
  - 多 Workflow 优先级竞争
  - set_priority 通过 metadata
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.workflow.builder import WorkflowBuilder
from market_ops.creative_vision_runtime.growth_runtime.workflow.context import ExecutionContext
from market_ops.creative_vision_runtime.growth_runtime.workflow.scheduler import (
    TaskPriority,
    TaskScheduleStatus,
    TaskScheduler,
)


# ═══════════════════════════════════════════════════════════════
# Test: TaskPriority Enum
# ═══════════════════════════════════════════════════════════════


class TestTaskPriority:
    """TaskPriority 枚举测试."""

    def test_priority_values(self):
        assert TaskPriority.CRITICAL.value == 1
        assert TaskPriority.HIGH.value == 2
        assert TaskPriority.NORMAL.value == 3
        assert TaskPriority.LOW.value == 4

    def test_priority_ordering(self):
        assert TaskPriority.CRITICAL < TaskPriority.HIGH
        assert TaskPriority.HIGH < TaskPriority.NORMAL
        assert TaskPriority.NORMAL < TaskPriority.LOW

    def test_from_string(self):
        assert TaskPriority.from_string("critical") == TaskPriority.CRITICAL
        assert TaskPriority.from_string("high") == TaskPriority.HIGH
        assert TaskPriority.from_string("normal") == TaskPriority.NORMAL
        assert TaskPriority.from_string("low") == TaskPriority.LOW

    def test_from_string_case_insensitive(self):
        assert TaskPriority.from_string("CRITICAL") == TaskPriority.CRITICAL
        assert TaskPriority.from_string("High") == TaskPriority.HIGH

    def test_from_string_unknown_defaults_to_normal(self):
        assert TaskPriority.from_string("unknown") == TaskPriority.NORMAL
        assert TaskPriority.from_string("") == TaskPriority.NORMAL

    def test_from_metadata_string(self):
        assert TaskPriority.from_metadata({"priority": "critical"}) == TaskPriority.CRITICAL
        assert TaskPriority.from_metadata({"priority": "high"}) == TaskPriority.HIGH

    def test_from_metadata_int(self):
        assert TaskPriority.from_metadata({"priority": 1}) == TaskPriority.CRITICAL
        assert TaskPriority.from_metadata({"priority": 3}) == TaskPriority.NORMAL

    def test_from_metadata_missing(self):
        assert TaskPriority.from_metadata({}) == TaskPriority.NORMAL

    def test_from_metadata_invalid_int(self):
        assert TaskPriority.from_metadata({"priority": 99}) == TaskPriority.NORMAL


# ═══════════════════════════════════════════════════════════════
# Test: Priority Ordering in Schedule
# ═══════════════════════════════════════════════════════════════


class TestPriorityOrdering:
    """优先级排序测试."""

    def test_critical_before_normal(self):
        """CRITICAL 任务排在 NORMAL 之前."""
        builder = WorkflowBuilder("Priority WF", workflow_id="wf_pri")
        builder.add_step("Task A", "task_a", task_id="t_a", metadata={"priority": "normal"})
        builder.add_step("Task B", "task_b", task_id="t_b", metadata={"priority": "critical"})
        builder.add_step("Task C", "task_c", task_id="t_c", metadata={"priority": "high"})
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        result = scheduler.schedule()
        assert len(result.next_tasks) == 3
        # CRITICAL 优先
        assert result.next_tasks[0] == "t_b"
        assert result.next_tasks[1] == "t_c"
        assert result.next_tasks[2] == "t_a"

    def test_same_priority_preserves_order(self):
        """同优先级保持原始顺序."""
        builder = WorkflowBuilder("Same Pri", workflow_id="wf_sp")
        builder.add_step("Task A", "task_a", task_id="t_a", metadata={"priority": "normal"})
        builder.add_step("Task B", "task_b", task_id="t_b", metadata={"priority": "normal"})
        builder.add_step("Task C", "task_c", task_id="t_c", metadata={"priority": "normal"})
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        result = scheduler.schedule()
        assert len(result.next_tasks) == 3
        # 同优先级，按排序后的顺序 (alphabetical by task_id)
        assert result.next_tasks[0] == "t_a"

    def test_default_priority_is_normal(self):
        """默认优先级为 NORMAL."""
        builder = WorkflowBuilder("Default Pri", workflow_id="wf_dp")
        builder.add_step("Task A", "task_a", task_id="t_a")
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        info = scheduler.get_task_schedule_info("t_a")
        assert info is not None
        assert info.priority == TaskPriority.NORMAL

    def test_priority_reflected_in_schedule_info(self):
        """优先级反映在 TaskScheduleInfo 中."""
        builder = WorkflowBuilder("Info Pri", workflow_id="wf_ip")
        builder.add_step("Task A", "task_a", task_id="t_a", metadata={"priority": "critical"})
        builder.add_step("Task B", "task_b", task_id="t_b", metadata={"priority": "low"})
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        info_a = scheduler.get_task_schedule_info("t_a")
        assert info_a is not None
        assert info_a.priority == TaskPriority.CRITICAL

        info_b = scheduler.get_task_schedule_info("t_b")
        assert info_b is not None
        assert info_b.priority == TaskPriority.LOW


# ═══════════════════════════════════════════════════════════════
# Test: Priority with Dependencies
# ═══════════════════════════════════════════════════════════════


class TestPriorityWithDependencies:
    """优先级 + 依赖组合测试."""

    def test_dependency_overrides_priority(self):
        """依赖未满足时，优先级不生效 — 任务被阻塞."""
        builder = WorkflowBuilder("Dep + Pri", workflow_id="wf_dpri")
        builder.add_step("Task A", "task_a", task_id="t_a", metadata={"priority": "low"})
        builder.add_step("Task B", "task_b", task_id="t_b", metadata={"priority": "critical"})
        builder.add_step("Task C", "task_c", task_id="t_c", metadata={"priority": "high"})
        builder.depends_on("t_b", "t_a")
        builder.depends_on("t_c", "t_a")
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        # 只有 t_a 就绪 (依赖未满足，t_b/t_c 被阻塞)
        result = scheduler.schedule()
        assert result.next_tasks == ["t_a"]

    def test_priority_among_ready_tasks(self):
        """就绪任务中按优先级排序."""
        builder = WorkflowBuilder("Ready Pri", workflow_id="wf_rp")
        builder.add_step("Task A", "task_a", task_id="t_a", metadata={"priority": "low"})
        builder.add_step("Task B", "task_b", task_id="t_b", metadata={"priority": "critical"})
        builder.add_step("Task C", "task_c", task_id="t_c", metadata={"priority": "high"})
        builder.depends_on("t_b", "t_a")
        builder.depends_on("t_c", "t_a")
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        ctx.complete_task("t_a")
        result = scheduler.schedule()
        # t_b (CRITICAL) 排在 t_c (HIGH) 前面
        assert result.next_tasks[0] == "t_b"
        assert result.next_tasks[1] == "t_c"

    def test_stop_loss_priority_pattern(self):
        """止损场景: CRITICAL 止损任务优先."""
        builder = WorkflowBuilder("Stop Loss", workflow_id="wf_sl")
        builder.add_step("Analyze ROAS", "analyze", task_id="t_analyze", metadata={"priority": "high"})
        builder.add_step("Stop Loss", "stop_loss", task_id="t_stop_loss", metadata={"priority": "critical"})
        builder.add_step("Generate Report", "report", task_id="t_report", metadata={"priority": "low"})
        builder.depends_on("t_stop_loss", "t_analyze")
        builder.depends_on("t_report", "t_analyze")
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        ctx.complete_task("t_analyze")
        result = scheduler.schedule()
        assert result.next_tasks[0] == "t_stop_loss"
        assert result.next_tasks[1] == "t_report"


# ═══════════════════════════════════════════════════════════════
# Test: TaskScheduler API
# ═══════════════════════════════════════════════════════════════


class TestTaskSchedulerAPI:
    """TaskScheduler complete/fail 方法."""

    def setup_method(self):
        builder = WorkflowBuilder("API Test", workflow_id="wf_api")
        builder.add_step("Task A", "task_a", task_id="t_a")
        builder.add_step("Task B", "task_b", task_id="t_b")
        builder.depends_on("t_b", "t_a")
        self.wf = builder.build()
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.scheduler = TaskScheduler(self.wf, self.ctx)

    def test_complete_returns_next_schedule(self):
        """complete() 返回更新后的调度结果."""
        self.ctx.start()
        result = self.scheduler.complete("t_a", {"roas": 0.48})
        assert result.next_tasks == ["t_b"]
        assert result.completed_tasks[0].task_id == "t_a"

    def test_fail_returns_failure_resolution(self):
        """fail() 返回失败恢复决策."""
        self.ctx.start()
        resolution = self.scheduler.fail("t_a", "network error")
        assert resolution.action is not None  # RETRY or FAIL_WORKFLOW

    def test_fail_then_retry_makes_task_ready_again(self):
        """失败后重试，任务回到就绪状态."""
        # 需要 retry_count > 0 才能重试
        builder = WorkflowBuilder("Retry Test", workflow_id="wf_retry")
        builder.add_step("Task A", "task_a", task_id="t_a", retry_count=3)
        builder.add_step("Task B", "task_b", task_id="t_b")
        builder.depends_on("t_b", "t_a")
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()
        scheduler.fail("t_a", "network error")
        ctx.retry_task("t_a")

        result = scheduler.schedule()
        # 重试后 t_a 回到 PENDING → 依赖已满足 → READY
        assert "t_a" in result.next_tasks

    def test_schedule_is_alias_for_get_next_tasks(self):
        """schedule() 和 get_next_tasks() 返回相同结果."""
        self.ctx.start()
        r1 = self.scheduler.schedule()
        r2 = self.scheduler.get_next_tasks()
        assert r1.next_tasks == r2.next_tasks
        assert r1.state == r2.state

    def test_task_schedule_info_includes_priority(self):
        """TaskScheduleInfo 包含优先级."""
        self.ctx.start()
        info = self.scheduler.get_task_schedule_info("t_a")
        assert info is not None
        assert info.priority == TaskPriority.NORMAL
        assert info.status == TaskScheduleStatus.READY