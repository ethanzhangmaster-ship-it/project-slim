"""E15.1.3 DAG Scheduler 测试 — 依赖解析.

测试覆盖:
  - 单依赖解析
  - 多依赖解析 (多上游)
  - 并行任务调度
  - 深层依赖链
  - 依赖完成后的下游解锁
  - 依赖未初始化状态的阻塞
  - 依赖失败后的阻塞
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


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_multi_dep_workflow():
    """多依赖 Workflow: D 依赖 A, B, C 三个上游."""
    builder = WorkflowBuilder("Multi-Dep Workflow", workflow_id="wf_multi")
    builder.add_step("Task A", "task_a", task_id="t_a")
    builder.add_step("Task B", "task_b", task_id="t_b")
    builder.add_step("Task C", "task_c", task_id="t_c")
    builder.add_step("Task D", "task_d", task_id="t_d")
    builder.depends_on("t_d", "t_a")
    builder.depends_on("t_d", "t_b")
    builder.depends_on("t_d", "t_c")
    return builder.build()


def _make_deep_chain_workflow():
    """深层链 Workflow: A → B → C → D → E."""
    builder = WorkflowBuilder("Deep Chain", workflow_id="wf_deep")
    for name, tid in [("A", "t_a"), ("B", "t_b"), ("C", "t_c"), ("D", "t_d"), ("E", "t_e")]:
        builder.add_step(name, f"task_{name.lower()}", task_id=tid)
    builder.depends_on("t_b", "t_a")
    builder.depends_on("t_c", "t_b")
    builder.depends_on("t_d", "t_c")
    builder.depends_on("t_e", "t_d")
    return builder.build()


def _make_fan_out_workflow():
    """扇出 Workflow: A → B, C, D (三个并行下游)."""
    builder = WorkflowBuilder("Fan-out Workflow", workflow_id="wf_fanout")
    builder.add_step("Task A", "task_a", task_id="t_a")
    builder.add_step("Task B", "task_b", task_id="t_b")
    builder.add_step("Task C", "task_c", task_id="t_c")
    builder.add_step("Task D", "task_d", task_id="t_d")
    builder.depends_on("t_b", "t_a")
    builder.depends_on("t_c", "t_a")
    builder.depends_on("t_d", "t_a")
    return builder.build()


# ═══════════════════════════════════════════════════════════════
# Test: Single Dependency
# ═══════════════════════════════════════════════════════════════


class TestSingleDependency:
    """单依赖解析."""

    def setup_method(self):
        builder = WorkflowBuilder("Single Dep", workflow_id="wf_single")
        builder.add_step("Task A", "task_a", task_id="t_a")
        builder.add_step("Task B", "task_b", task_id="t_b")
        builder.depends_on("t_b", "t_a")
        self.wf = builder.build()
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.scheduler = DAGScheduler(self.wf, self.ctx)
        self.tasks = {t.name: t for t in self.wf.tasks}

    def test_b_blocked_when_a_not_completed(self):
        """A 未完成时 B 被阻塞."""
        self.ctx.start()
        status = self.scheduler.get_task_schedule_status(self.tasks["Task B"].task_id)
        assert status == TaskScheduleStatus.BLOCKED

    def test_b_ready_when_a_completed(self):
        """A 完成后 B 就绪."""
        self.ctx.start()
        self.ctx.complete_task(self.tasks["Task A"].task_id)
        status = self.scheduler.get_task_schedule_status(self.tasks["Task B"].task_id)
        assert status == TaskScheduleStatus.READY

    def test_b_blocked_by_running_a(self):
        """A 正在运行时 B 被阻塞."""
        self.ctx.start()
        self.ctx.start_task(self.tasks["Task A"].task_id)
        status = self.scheduler.get_task_schedule_status(self.tasks["Task B"].task_id)
        assert status == TaskScheduleStatus.BLOCKED

    def test_blocked_reason_contains_dependency_info(self):
        """阻塞原因包含依赖信息."""
        self.ctx.start()
        info = self.scheduler.get_task_schedule_info(self.tasks["Task B"].task_id)
        assert info is not None
        assert "Blocked by" in info.reason
        assert self.tasks["Task A"].task_id in info.reason


# ═══════════════════════════════════════════════════════════════
# Test: Multi-Dependency
# ═══════════════════════════════════════════════════════════════


class TestMultiDependency:
    """多依赖解析."""

    def setup_method(self):
        self.wf = _make_multi_dep_workflow()
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.scheduler = DAGScheduler(self.wf, self.ctx)
        self.tasks = {t.name: t for t in self.wf.tasks}

    def test_all_entry_tasks_ready(self):
        """A, B, C 都是入口任务，同时就绪."""
        self.ctx.start()
        result = self.scheduler.get_next_tasks()
        ready_ids = set(result.next_tasks)
        assert self.tasks["Task A"].task_id in ready_ids
        assert self.tasks["Task B"].task_id in ready_ids
        assert self.tasks["Task C"].task_id in ready_ids

    def test_d_blocked_until_all_completed(self):
        """D 需要三个上游都完成."""
        self.ctx.start()
        self.ctx.complete_task(self.tasks["Task A"].task_id)
        self.ctx.complete_task(self.tasks["Task B"].task_id)

        # C 还没完成, D 被阻塞
        status = self.scheduler.get_task_schedule_status(self.tasks["Task D"].task_id)
        assert status == TaskScheduleStatus.BLOCKED

        # 完成 C → D 就绪
        self.ctx.complete_task(self.tasks["Task C"].task_id)
        status = self.scheduler.get_task_schedule_status(self.tasks["Task D"].task_id)
        assert status == TaskScheduleStatus.READY

    def test_d_blocked_by_one_failed_dependency(self):
        """D 被一个失败的上游阻塞."""
        self.ctx.start()
        self.ctx.complete_task(self.tasks["Task A"].task_id)
        self.ctx.complete_task(self.tasks["Task B"].task_id)
        self.ctx.fail_task(self.tasks["Task C"].task_id)

        # C 失败 (无重试), D 被阻塞
        status = self.scheduler.get_task_schedule_status(self.tasks["Task D"].task_id)
        assert status == TaskScheduleStatus.BLOCKED

    def test_d_unblocked_when_all_deps_completed_or_skipped(self):
        """D 在依赖被跳过时也解锁."""
        self.ctx.start()
        self.ctx.complete_task(self.tasks["Task A"].task_id)
        self.ctx.complete_task(self.tasks["Task B"].task_id)
        self.ctx.skip_task(self.tasks["Task C"].task_id)

        status = self.scheduler.get_task_schedule_status(self.tasks["Task D"].task_id)
        assert status == TaskScheduleStatus.READY


# ═══════════════════════════════════════════════════════════════
# Test: Deep Chain
# ═══════════════════════════════════════════════════════════════


class TestDeepChain:
    """深层依赖链."""

    def setup_method(self):
        self.wf = _make_deep_chain_workflow()
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.scheduler = DAGScheduler(self.wf, self.ctx)
        self.tasks = self.wf.flat_topological_order()

    def test_only_entry_ready_initially(self):
        """初始只有入口任务就绪."""
        self.ctx.start()
        result = self.scheduler.get_next_tasks()
        assert len(result.next_tasks) == 1
        assert result.next_tasks[0] == self.tasks[0].task_id

    def test_step_by_step_unlock(self):
        """逐步解锁."""
        self.ctx.start()
        for i, task in enumerate(self.tasks):
            result = self.scheduler.get_next_tasks()
            assert result.next_tasks == [task.task_id], f"Step {i}: expected {task.name}"
            self.ctx.complete_task(task.task_id)

        result = self.scheduler.get_next_tasks()
        assert result.state == ScheduleState.COMPLETED

    def test_mid_chain_completion(self):
        """中间任务完成不影响后续顺序."""
        self.ctx.start()
        self.ctx.complete_task(self.tasks[0].task_id)
        self.ctx.complete_task(self.tasks[1].task_id)

        result = self.scheduler.get_next_tasks()
        assert result.next_tasks == [self.tasks[2].task_id]


# ═══════════════════════════════════════════════════════════════
# Test: Fan-out
# ═══════════════════════════════════════════════════════════════


class TestFanOut:
    """扇出并行调度."""

    def setup_method(self):
        self.wf = _make_fan_out_workflow()
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.scheduler = DAGScheduler(self.wf, self.ctx)
        self.tasks = {t.name: t for t in self.wf.tasks}

    def test_a_completion_unlocks_all_children(self):
        """A 完成后, B/C/D 同时就绪."""
        self.ctx.start()
        self.ctx.complete_task(self.tasks["Task A"].task_id)

        result = self.scheduler.get_next_tasks()
        ready_ids = set(result.next_tasks)
        assert len(ready_ids) == 3
        assert self.tasks["Task B"].task_id in ready_ids
        assert self.tasks["Task C"].task_id in ready_ids
        assert self.tasks["Task D"].task_id in ready_ids

    def test_partial_completion_does_not_unlock(self):
        """部分完成不解锁."""
        self.ctx.start()
        self.ctx.complete_task(self.tasks["Task B"].task_id)

        result = self.scheduler.get_next_tasks()
        # A 仍然就绪 (没有依赖)
        assert len(result.next_tasks) == 1
        assert result.next_tasks[0] == self.tasks["Task A"].task_id


# ═══════════════════════════════════════════════════════════════
# Test: Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestDependencyEdgeCases:
    """依赖解析边界情况."""

    def test_no_dependencies_all_ready(self):
        """无依赖任务全部就绪."""
        builder = WorkflowBuilder("No Deps", workflow_id="wf_nodeps")
        builder.add_step("Task A", "task_a", task_id="t_a")
        builder.add_step("Task B", "task_b", task_id="t_b")
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = DAGScheduler(wf, ctx)
        ctx.start()

        result = scheduler.get_next_tasks()
        assert len(result.next_tasks) == 2

    def test_uninitialized_task_blocked(self):
        """未初始化 exec_state 的任务检查依赖."""
        builder = WorkflowBuilder("Uninit", workflow_id="wf_uninit")
        builder.add_step("Task A", "task_a", task_id="t_a")
        builder.add_step("Task B", "task_b", task_id="t_b")
        builder.depends_on("t_b", "t_a")
        wf = builder.build()
        # 不通过 from_definition 创建，手动创建 ctx
        ctx = ExecutionContext(workflow_id=wf.workflow_id)
        ctx.start()
        scheduler = DAGScheduler(wf, ctx)

        # t_a 无依赖 → 但因未初始化 exec_state，检查依赖后应 READY
        info_a = scheduler.get_task_schedule_info("t_a")
        assert info_a is not None
        assert info_a.status == TaskScheduleStatus.READY

        # t_b 有依赖但 t_a 未初始化 → BLOCKED
        info_b = scheduler.get_task_schedule_info("t_b")
        assert info_b is not None
        assert info_b.status == TaskScheduleStatus.BLOCKED

    def test_dependency_completed_via_skip(self):
        """依赖通过 SKIP 满足."""
        builder = WorkflowBuilder("Skip Dep", workflow_id="wf_skip")
        builder.add_step("Task A", "task_a", task_id="t_a")
        builder.add_step("Task B", "task_b", task_id="t_b")
        builder.depends_on("t_b", "t_a")
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = DAGScheduler(wf, ctx)
        ctx.start()

        ctx.skip_task("t_a")
        status = scheduler.get_task_schedule_status("t_b")
        assert status == TaskScheduleStatus.READY