"""E15.1.3 Task Scheduler 测试 — 条件调度.

测试覆盖:
  - Callable 条件表达式 (lambda)
  - 字符串条件表达式 ("roas < 0.5")
  - 条件满足 → READY
  - 条件不满足 → CONDITION_NOT_MET
  - 条件 + 审批组合
  - 条件 + 依赖组合
  - 变量从 context.variables 读取
  - 变量从 task outputs 读取
  - 条件表达式边界情况
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.workflow.builder import WorkflowBuilder
from market_ops.creative_vision_runtime.growth_runtime.workflow.context import ExecutionContext
from market_ops.creative_vision_runtime.growth_runtime.workflow.scheduler import (
    ScheduleState,
    TaskScheduleStatus,
    TaskScheduler,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_condition_workflow():
    """条件分支 Workflow: A → B(condition: roas < 0.5) → Reduce Budget
                                → C(condition: roas >= 0.5) → Increase Spend."""
    builder = WorkflowBuilder("Condition WF", workflow_id="wf_cond")
    builder.add_step("Analyze", "analyze", task_id="t_analyze")
    builder.add_step(
        "Reduce Budget",
        "reduce_budget",
        task_id="t_reduce",
        metadata={"condition_expr": "roas < 0.5"},
    )
    builder.add_step(
        "Increase Spend",
        "increase_spend",
        task_id="t_increase",
        metadata={"condition_expr": "roas >= 0.5"},
    )
    builder.depends_on("t_reduce", "t_analyze")
    builder.depends_on("t_increase", "t_analyze")
    return builder.build()


# ═══════════════════════════════════════════════════════════════
# Test: Callable Condition
# ═══════════════════════════════════════════════════════════════


class TestCallableCondition:
    """Callable 条件表达式."""

    def test_lambda_condition_met(self):
        """lambda 条件满足 → READY."""
        builder = WorkflowBuilder("Lambda Cond", workflow_id="wf_lambda")
        builder.add_step(
            "Task A",
            "task_a",
            task_id="t_a",
            metadata={"condition": lambda ctx: ctx.get_variable("roas", 1.0) < 0.5},
        )
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        ctx.set_variable("roas", 0.3)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        status = scheduler.get_task_schedule_status("t_a")
        assert status == TaskScheduleStatus.READY

    def test_lambda_condition_not_met(self):
        """lambda 条件不满足 → CONDITION_NOT_MET."""
        builder = WorkflowBuilder("Lambda Fail", workflow_id="wf_lf")
        builder.add_step(
            "Task A",
            "task_a",
            task_id="t_a",
            metadata={"condition": lambda ctx: ctx.get_variable("roas", 1.0) < 0.5},
        )
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        ctx.set_variable("roas", 0.8)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        status = scheduler.get_task_schedule_status("t_a")
        assert status == TaskScheduleStatus.CONDITION_NOT_MET

    def test_no_condition_defaults_to_ready(self):
        """无条件 → READY."""
        builder = WorkflowBuilder("No Cond", workflow_id="wf_nc")
        builder.add_step("Task A", "task_a", task_id="t_a")
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        status = scheduler.get_task_schedule_status("t_a")
        assert status == TaskScheduleStatus.READY

    def test_lambda_can_access_context_variables(self):
        """lambda 可访问 context 变量."""
        builder = WorkflowBuilder("Lambda Var", workflow_id="wf_lv")
        builder.add_step(
            "Task A",
            "task_a",
            task_id="t_a",
            metadata={"condition": lambda ctx: ctx.get_variable("fatigue", 0) > 0.7},
        )
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        ctx.set_variable("fatigue", 0.85)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        assert scheduler.get_task_schedule_status("t_a") == TaskScheduleStatus.READY


# ═══════════════════════════════════════════════════════════════
# Test: String Expression Condition
# ═══════════════════════════════════════════════════════════════


class TestStringExpressionCondition:
    """字符串条件表达式."""

    def test_less_than_met(self):
        """roas < 0.5 满足."""
        builder = WorkflowBuilder("LT Met", workflow_id="wf_ltm")
        builder.add_step(
            "Task A", "task_a", task_id="t_a",
            metadata={"condition_expr": "roas < 0.5"},
        )
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        ctx.set_variable("roas", 0.3)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        assert scheduler.get_task_schedule_status("t_a") == TaskScheduleStatus.READY

    def test_less_than_not_met(self):
        """roas < 0.5 不满足."""
        builder = WorkflowBuilder("LT Not", workflow_id="wf_ltn")
        builder.add_step(
            "Task A", "task_a", task_id="t_a",
            metadata={"condition_expr": "roas < 0.5"},
        )
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        ctx.set_variable("roas", 0.8)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        assert scheduler.get_task_schedule_status("t_a") == TaskScheduleStatus.CONDITION_NOT_MET

    def test_greater_than_met(self):
        """fatigue > 0.7 满足."""
        builder = WorkflowBuilder("GT Met", workflow_id="wf_gtm")
        builder.add_step(
            "Task A", "task_a", task_id="t_a",
            metadata={"condition_expr": "fatigue > 0.7"},
        )
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        ctx.set_variable("fatigue", 0.85)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        assert scheduler.get_task_schedule_status("t_a") == TaskScheduleStatus.READY

    def test_greater_equal_met(self):
        """roas >= 0.5 满足."""
        builder = WorkflowBuilder("GE Met", workflow_id="wf_gem")
        builder.add_step(
            "Task A", "task_a", task_id="t_a",
            metadata={"condition_expr": "roas >= 0.5"},
        )
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        ctx.set_variable("roas", 0.5)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        assert scheduler.get_task_schedule_status("t_a") == TaskScheduleStatus.READY

    def test_equal_met(self):
        """budget == 5000 满足."""
        builder = WorkflowBuilder("EQ Met", workflow_id="wf_eqm")
        builder.add_step(
            "Task A", "task_a", task_id="t_a",
            metadata={"condition_expr": "budget == 5000"},
        )
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        ctx.set_variable("budget", 5000)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        assert scheduler.get_task_schedule_status("t_a") == TaskScheduleStatus.READY

    def test_not_equal_met(self):
        """budget != 3000 满足."""
        builder = WorkflowBuilder("NE Met", workflow_id="wf_nem")
        builder.add_step(
            "Task A", "task_a", task_id="t_a",
            metadata={"condition_expr": "budget != 3000"},
        )
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        ctx.set_variable("budget", 5000)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        assert scheduler.get_task_schedule_status("t_a") == TaskScheduleStatus.READY

    def test_variable_not_found_returns_false(self):
        """变量不存在 → 条件不满足."""
        builder = WorkflowBuilder("No Var", workflow_id="wf_nv")
        builder.add_step(
            "Task A", "task_a", task_id="t_a",
            metadata={"condition_expr": "nonexistent < 0.5"},
        )
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        assert scheduler.get_task_schedule_status("t_a") == TaskScheduleStatus.CONDITION_NOT_MET

    def test_invalid_expression_returns_false(self):
        """无效表达式 → 条件不满足."""
        builder = WorkflowBuilder("Invalid Expr", workflow_id="wf_ie")
        builder.add_step(
            "Task A", "task_a", task_id="t_a",
            metadata={"condition_expr": "not a valid expression"},
        )
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        assert scheduler.get_task_schedule_status("t_a") == TaskScheduleStatus.CONDITION_NOT_MET


# ═══════════════════════════════════════════════════════════════
# Test: Condition from Outputs
# ═══════════════════════════════════════════════════════════════


class TestConditionFromOutputs:
    """条件从 Task outputs 中读取."""

    def test_condition_reads_from_outputs(self):
        """条件表达式从上游 Task 输出读取变量."""
        builder = WorkflowBuilder("Output Cond", workflow_id="wf_oc")
        builder.add_step("Analyze", "analyze", task_id="t_analyze")
        builder.add_step(
            "Reduce Budget",
            "reduce_budget",
            task_id="t_reduce",
            metadata={"condition_expr": "roas < 0.5"},
        )
        builder.depends_on("t_reduce", "t_analyze")
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        # 完成 Analyze，输出 roas
        ctx.complete_task("t_analyze", {"roas": 0.3})

        status = scheduler.get_task_schedule_status("t_reduce")
        assert status == TaskScheduleStatus.READY

    def test_condition_from_outputs_not_met(self):
        """输出不满足条件."""
        builder = WorkflowBuilder("Output Fail", workflow_id="wf_of")
        builder.add_step("Analyze", "analyze", task_id="t_analyze")
        builder.add_step(
            "Reduce Budget",
            "reduce_budget",
            task_id="t_reduce",
            metadata={"condition_expr": "roas < 0.5"},
        )
        builder.depends_on("t_reduce", "t_analyze")
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        ctx.complete_task("t_analyze", {"roas": 0.8})

        status = scheduler.get_task_schedule_status("t_reduce")
        assert status == TaskScheduleStatus.CONDITION_NOT_MET


# ═══════════════════════════════════════════════════════════════
# Test: Condition + Approval
# ═══════════════════════════════════════════════════════════════


class TestConditionWithApproval:
    """条件 + 审批组合."""

    def test_condition_checked_before_approval(self):
        """条件不满足时，不会检查审批."""
        builder = WorkflowBuilder("Cond + Approve", workflow_id="wf_ca")
        builder.add_step(
            "Task A",
            "task_a",
            task_id="t_a",
            requires_approval=True,
            metadata={"condition_expr": "roas < 0.5"},
        )
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        ctx.set_variable("roas", 0.8)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        status = scheduler.get_task_schedule_status("t_a")
        # 条件不满足 → CONDITION_NOT_MET (不是 WAITING_APPROVAL)
        assert status == TaskScheduleStatus.CONDITION_NOT_MET

    def test_condition_met_then_approval_checked(self):
        """条件满足后，审批检查生效."""
        builder = WorkflowBuilder("Cond OK + Approve", workflow_id="wf_coa")
        builder.add_step(
            "Task A",
            "task_a",
            task_id="t_a",
            requires_approval=True,
            metadata={"condition_expr": "roas < 0.5"},
        )
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        ctx.set_variable("roas", 0.3)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        status = scheduler.get_task_schedule_status("t_a")
        assert status == TaskScheduleStatus.WAITING_APPROVAL


# ═══════════════════════════════════════════════════════════════
# Test: Condition in ScheduleResult
# ═══════════════════════════════════════════════════════════════


class TestConditionInScheduleResult:
    """CONDITION_NOT_MET 在 ScheduleResult 中."""

    def test_condition_not_met_in_result(self):
        """条件不满足的任务出现在 condition_not_met_tasks."""
        builder = WorkflowBuilder("Result Cond", workflow_id="wf_rc")
        builder.add_step(
            "Task A",
            "task_a",
            task_id="t_a",
            metadata={"condition_expr": "roas < 0.5"},
        )
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        ctx.set_variable("roas", 0.8)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        result = scheduler.schedule()
        assert result.state == ScheduleState.BLOCKED
        assert len(result.condition_not_met_tasks) == 1
        assert result.condition_not_met_tasks[0].task_id == "t_a"

    def test_condition_not_met_blocks_workflow(self):
        """所有任务条件不满足 → BLOCKED."""
        builder = WorkflowBuilder("All Cond Blocked", workflow_id="wf_acb")
        builder.add_step(
            "Task A", "task_a", task_id="t_a",
            metadata={"condition_expr": "roas < 0.5"},
        )
        builder.add_step(
            "Task B", "task_b", task_id="t_b",
            metadata={"condition_expr": "fatigue > 0.7"},
        )
        wf = builder.build()
        ctx = ExecutionContext.from_definition(wf)
        ctx.set_variable("roas", 0.8)
        ctx.set_variable("fatigue", 0.3)
        scheduler = TaskScheduler(wf, ctx)
        ctx.start()

        result = scheduler.schedule()
        assert result.state == ScheduleState.BLOCKED
        assert len(result.condition_not_met_tasks) == 2


# ═══════════════════════════════════════════════════════════════
# Test: ROAS Recovery Scenario
# ═══════════════════════════════════════════════════════════════


class TestROASRecoveryScenario:
    """ROAS 恢复场景: 条件分支."""

    def setup_method(self):
        self.wf = _make_condition_workflow()
        self.tasks = {t.name: t for t in self.wf.tasks}

    def test_roas_low_triggers_reduce_budget(self):
        """ROAS < 0.5 → Reduce Budget 就绪, Increase Spend 阻塞."""
        ctx = ExecutionContext.from_definition(self.wf)
        ctx.set_variable("roas", 0.3)
        scheduler = TaskScheduler(self.wf, ctx)
        ctx.start()

        ctx.complete_task(self.tasks["Analyze"].task_id, {"roas": 0.3})

        result = scheduler.schedule()
        assert result.next_tasks == [self.tasks["Reduce Budget"].task_id]
        assert len(result.condition_not_met_tasks) == 1
        assert result.condition_not_met_tasks[0].task_id == self.tasks["Increase Spend"].task_id

    def test_roas_high_triggers_increase_spend(self):
        """ROAS >= 0.5 → Increase Spend 就绪, Reduce Budget 阻塞."""
        ctx = ExecutionContext.from_definition(self.wf)
        ctx.set_variable("roas", 0.8)
        scheduler = TaskScheduler(self.wf, ctx)
        ctx.start()

        ctx.complete_task(self.tasks["Analyze"].task_id, {"roas": 0.8})

        result = scheduler.schedule()
        assert result.next_tasks == [self.tasks["Increase Spend"].task_id]
        assert len(result.condition_not_met_tasks) == 1
        assert result.condition_not_met_tasks[0].task_id == self.tasks["Reduce Budget"].task_id

    def test_roas_boundary_turns_on_increase(self):
        """ROAS == 0.5 → Increase Spend (>=)."""
        ctx = ExecutionContext.from_definition(self.wf)
        ctx.set_variable("roas", 0.5)
        scheduler = TaskScheduler(self.wf, ctx)
        ctx.start()

        ctx.complete_task(self.tasks["Analyze"].task_id, {"roas": 0.5})

        result = scheduler.schedule()
        assert result.next_tasks == [self.tasks["Increase Spend"].task_id]