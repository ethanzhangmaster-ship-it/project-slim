"""E15.1.3 DAG Scheduler 测试 — 核心调度功能.

测试覆盖:
  - DAGScheduler 创建与初始化
  - get_next_tasks() 基础调度
  - get_ready_tasks() 就绪任务
  - can_proceed() 可继续性判断
  - 线性 DAG 调度 (A→B→C)
  - 菱形 DAG 调度 (A→B,C→D)
  - ScheduleResult 状态与序列化
  - 预设 Workflow 调度
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.workflow.builder import (
    WorkflowBuilder,
    create_campaign_optimization_workflow,
)
from market_ops.creative_vision_runtime.growth_runtime.workflow.context import ExecutionContext
from market_ops.creative_vision_runtime.growth_runtime.workflow.scheduler import (
    DAGScheduler,
    ScheduleResult,
    ScheduleState,
    TaskScheduleInfo,
    TaskScheduleStatus,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_linear_workflow():
    """创建线性 Workflow: A → B → C."""
    builder = WorkflowBuilder("Linear Workflow", workflow_id="wf_linear")
    builder.add_step("Task A", "task_a", task_id="t_a")
    builder.add_step("Task B", "task_b", task_id="t_b")
    builder.add_step("Task C", "task_c", task_id="t_c")
    builder.depends_on("t_b", "t_a")
    builder.depends_on("t_c", "t_b")
    return builder.build()


def _make_diamond_workflow():
    """创建菱形 Workflow: A → B, C → D."""
    builder = WorkflowBuilder("Diamond Workflow", workflow_id="wf_diamond")
    builder.add_step("Task A", "task_a", task_id="t_a")
    builder.add_step("Task B", "task_b", task_id="t_b")
    builder.add_step("Task C", "task_c", task_id="t_c")
    builder.add_step("Task D", "task_d", task_id="t_d")
    builder.depends_on("t_b", "t_a")
    builder.depends_on("t_c", "t_a")
    builder.depends_on("t_d", "t_b")
    builder.depends_on("t_d", "t_c")
    return builder.build()


# ═══════════════════════════════════════════════════════════════
# Test: Scheduler Creation
# ═══════════════════════════════════════════════════════════════


class TestSchedulerCreation:
    """DAGScheduler 创建测试."""

    def test_create_with_definition_and_context(self):
        wf = _make_linear_workflow()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = DAGScheduler(wf, ctx)
        assert scheduler.definition is wf
        assert scheduler.context is ctx

    def test_create_rejects_none_definition(self):
        ctx = ExecutionContext(workflow_id="wf_001")
        with pytest.raises(ValueError, match="definition cannot be None"):
            DAGScheduler(None, ctx)

    def test_create_rejects_none_context(self):
        wf = _make_linear_workflow()
        with pytest.raises(ValueError, match="context cannot be None"):
            DAGScheduler(wf, None)


# ═══════════════════════════════════════════════════════════════
# Test: Linear DAG Scheduling
# ═══════════════════════════════════════════════════════════════


class TestLinearDAGScheduling:
    """线性 DAG 调度测试 (A → B → C)."""

    def setup_method(self):
        self.wf = _make_linear_workflow()
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.scheduler = DAGScheduler(self.wf, self.ctx)
        self.tasks = self.wf.flat_topological_order()

    def test_initial_state_ready(self):
        """初始状态: 入口任务就绪."""
        self.ctx.start()
        result = self.scheduler.get_next_tasks()
        assert result.state == ScheduleState.READY
        assert len(result.next_tasks) == 1
        assert result.next_tasks[0] == self.tasks[0].task_id  # Task A

    def test_initial_state_without_start(self):
        """CREATED 状态不可调度."""
        result = self.scheduler.get_next_tasks()
        assert result.state == ScheduleState.READY
        assert len(result.next_tasks) == 1

    def test_step_by_step_execution(self):
        """逐步执行: A → B → C."""
        self.ctx.start()

        # Step 1: 执行 Task A
        result = self.scheduler.get_next_tasks()
        assert result.next_tasks == [self.tasks[0].task_id]
        self.ctx.complete_task(self.tasks[0].task_id, {"x": 1})

        # Step 2: 执行 Task B
        result = self.scheduler.get_next_tasks()
        assert result.next_tasks == [self.tasks[1].task_id]
        self.ctx.complete_task(self.tasks[1].task_id, {"y": 2})

        # Step 3: 执行 Task C
        result = self.scheduler.get_next_tasks()
        assert result.next_tasks == [self.tasks[2].task_id]
        self.ctx.complete_task(self.tasks[2].task_id, {"z": 3})

        # 全部完成
        result = self.scheduler.get_next_tasks()
        assert result.state == ScheduleState.COMPLETED
        assert len(result.next_tasks) == 0

    def test_mid_chain_blocked(self):
        """中间任务未完成时，下游被阻塞."""
        self.ctx.start()
        self.ctx.complete_task(self.tasks[0].task_id)

        result = self.scheduler.get_next_tasks()
        assert result.next_tasks == [self.tasks[1].task_id]
        assert len(result.blocked_tasks) == 1
        assert result.blocked_tasks[0].task_id == self.tasks[2].task_id

    def test_get_ready_tasks(self):
        """get_ready_tasks() 返回 WorkflowTask 对象."""
        self.ctx.start()
        tasks = self.scheduler.get_ready_tasks()
        assert len(tasks) == 1
        assert tasks[0].task_id == self.tasks[0].task_id

    def test_can_proceed(self):
        """can_proceed() 检查."""
        self.ctx.start()
        assert self.scheduler.can_proceed() is True

        # 完成所有任务
        for t in self.tasks:
            self.ctx.complete_task(t.task_id)
        assert self.scheduler.can_proceed() is False


# ═══════════════════════════════════════════════════════════════
# Test: Diamond DAG Scheduling
# ═══════════════════════════════════════════════════════════════


class TestDiamondDAGScheduling:
    """菱形 DAG 调度测试 (A → B,C → D)."""

    def setup_method(self):
        self.wf = _make_diamond_workflow()
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.scheduler = DAGScheduler(self.wf, self.ctx)
        self.tasks = {t.name: t for t in self.wf.tasks}

    def test_parallel_tasks_ready(self):
        """A 完成后, B 和 C 同时就绪."""
        self.ctx.start()
        self.ctx.complete_task(self.tasks["Task A"].task_id)

        result = self.scheduler.get_next_tasks()
        assert result.state == ScheduleState.READY
        ready_ids = set(result.next_tasks)
        assert self.tasks["Task B"].task_id in ready_ids
        assert self.tasks["Task C"].task_id in ready_ids

    def test_d_requires_both_b_and_c(self):
        """D 需要 B 和 C 都完成."""
        self.ctx.start()
        self.ctx.complete_task(self.tasks["Task A"].task_id)
        self.ctx.complete_task(self.tasks["Task B"].task_id)

        result = self.scheduler.get_next_tasks()
        # C 就绪，但 D 被阻塞 (C 未完成)
        assert result.next_tasks == [self.tasks["Task C"].task_id]
        assert len(result.blocked_tasks) == 1
        assert result.blocked_tasks[0].task_id == self.tasks["Task D"].task_id

    def test_diamond_full_execution(self):
        """完整菱形执行."""
        self.ctx.start()
        a = self.tasks["Task A"]
        b = self.tasks["Task B"]
        c = self.tasks["Task C"]
        d = self.tasks["Task D"]

        self.ctx.complete_task(a.task_id)
        self.ctx.complete_task(b.task_id)
        self.ctx.complete_task(c.task_id)

        result = self.scheduler.get_next_tasks()
        assert result.next_tasks == [d.task_id]

        self.ctx.complete_task(d.task_id)
        result = self.scheduler.get_next_tasks()
        assert result.state == ScheduleState.COMPLETED


# ═══════════════════════════════════════════════════════════════
# Test: ScheduleResult
# ═══════════════════════════════════════════════════════════════


class TestScheduleResult:
    """ScheduleResult 测试."""

    def test_has_next(self):
        result = ScheduleResult(next_tasks=["t1", "t2"])
        assert result.has_next() is True

        result = ScheduleResult(next_tasks=[])
        assert result.has_next() is False

    def test_is_terminal(self):
        result = ScheduleResult(state=ScheduleState.COMPLETED)
        assert result.is_terminal() is True

        result = ScheduleResult(state=ScheduleState.FAILED)
        assert result.is_terminal() is True

        result = ScheduleResult(state=ScheduleState.READY)
        assert result.is_terminal() is False

    def test_to_dict(self):
        result = ScheduleResult(
            next_tasks=["t1"],
            state=ScheduleState.READY,
            reason="1 task(s) ready to execute",
        )
        d = result.to_dict()
        assert d["next_tasks"] == ["t1"]
        assert d["state"] == "ready"
        assert d["reason"] == "1 task(s) ready to execute"

    def test_to_dict_with_blocked(self):
        info = TaskScheduleInfo(
            task_id="t2",
            task_name="Task B",
            status=TaskScheduleStatus.BLOCKED,
            reason="Blocked by: t1(running)",
        )
        result = ScheduleResult(
            next_tasks=["t1"],
            blocked_tasks=[info],
            state=ScheduleState.READY,
        )
        d = result.to_dict()
        assert len(d["blocked_tasks"]) == 1
        assert d["blocked_tasks"][0]["task_id"] == "t2"
        assert d["blocked_tasks"][0]["status"] == "blocked"


# ═══════════════════════════════════════════════════════════════
# Test: Preset Workflow
# ═══════════════════════════════════════════════════════════════


class TestPresetWorkflowScheduling:
    """预设 Workflow 调度测试."""

    def test_campaign_optimization_start(self):
        """Campaign Optimization 初始调度."""
        wf = create_campaign_optimization_workflow()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = DAGScheduler(wf, ctx)
        ctx.start()

        result = scheduler.get_next_tasks()
        assert result.state == ScheduleState.READY
        assert len(result.next_tasks) == 1

    def test_campaign_optimization_full(self):
        """Campaign Optimization 完整执行."""
        wf = create_campaign_optimization_workflow()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = DAGScheduler(wf, ctx)
        ctx.start()

        for task in wf.flat_topological_order():
            result = scheduler.get_next_tasks()
            if task.requires_approval:
                assert result.state == ScheduleState.WAITING
                ctx.set_approval_context(
                    task_id=task.task_id,
                    requested_by="system",
                    risk_level="low",
                    reason="test",
                )
                ctx.metadata["approval"]["status"] = "approved"
                result = scheduler.get_next_tasks()
            assert result.next_tasks == [task.task_id]
            ctx.complete_task(task.task_id)

        result = scheduler.get_next_tasks()
        assert result.state == ScheduleState.COMPLETED


# ═══════════════════════════════════════════════════════════════
# Test: Task Schedule Status
# ═══════════════════════════════════════════════════════════════


class TestTaskScheduleStatus:
    """TaskScheduleStatus 查询测试."""

    def setup_method(self):
        self.wf = _make_linear_workflow()
        self.ctx = ExecutionContext.from_definition(self.wf)
        self.scheduler = DAGScheduler(self.wf, self.ctx)
        self.tasks = self.wf.flat_topological_order()

    def test_entry_task_ready(self):
        self.ctx.start()
        status = self.scheduler.get_task_schedule_status(self.tasks[0].task_id)
        assert status == TaskScheduleStatus.READY

    def test_downstream_task_blocked(self):
        self.ctx.start()
        status = self.scheduler.get_task_schedule_status(self.tasks[1].task_id)
        assert status == TaskScheduleStatus.BLOCKED

    def test_completed_task(self):
        self.ctx.start()
        self.ctx.complete_task(self.tasks[0].task_id)
        status = self.scheduler.get_task_schedule_status(self.tasks[0].task_id)
        assert status == TaskScheduleStatus.COMPLETED

    def test_unknown_task_raises(self):
        self.ctx.start()
        with pytest.raises(ValueError, match="not found"):
            self.scheduler.get_task_schedule_status("nonexistent")

    def test_get_all_task_schedule_infos(self):
        self.ctx.start()
        infos = self.scheduler.get_all_task_schedule_infos()
        assert len(infos) == 3
        statuses = {i.task_id: i.status for i in infos}
        assert statuses[self.tasks[0].task_id] == TaskScheduleStatus.READY
        assert statuses[self.tasks[1].task_id] == TaskScheduleStatus.BLOCKED
        assert statuses[self.tasks[2].task_id] == TaskScheduleStatus.BLOCKED