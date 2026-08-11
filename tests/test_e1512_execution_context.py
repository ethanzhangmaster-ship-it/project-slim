"""E15.1.2 Execution Context 测试 — 运行时上下文测试.

测试覆盖:
  - ExecutionContext 创建 (create / from_definition)
  - 变量读写
  - 生命周期管理 (start/pause/resume/wait/complete/fail/cancel)
  - 审批上下文
  - 进度查询
  - 摘要
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.workflow.builder import (
    create_campaign_optimization_workflow,
)
from market_ops.creative_vision_runtime.growth_runtime.workflow.events import ContextEvent, ContextEventType
from market_ops.creative_vision_runtime.growth_runtime.workflow.context import ExecutionContext
from market_ops.creative_vision_runtime.growth_runtime.workflow.state import (
    TaskExecutionStatus,
    WorkflowState,
)


class TestExecutionContext:
    """ExecutionContext 单元测试."""

    def setup_method(self):
        self.ctx = ExecutionContext(
            workflow_id="wf_001",
            workflow_name="Campaign Optimizer",
            instance_id="inst_001",
            variables={"game": "P04", "campaign": "fb_android", "budget": 5000},
        )

    # ── Creation ─────────────────────────────────────────────

    def test_create(self):
        ctx = ExecutionContext.create(
            workflow_id="wf_001",
            instance_id="inst_001",
            variables={"game": "P04"},
        )
        assert ctx.workflow_id == "wf_001"
        assert ctx.instance_id == "inst_001"
        assert ctx.state == WorkflowState.CREATED
        assert ctx.get_variable("game") == "P04"

    def test_create_with_auto_instance_id(self):
        ctx = ExecutionContext.create(workflow_id="wf_001")
        assert ctx.instance_id != ""

    def test_create_with_metadata(self):
        ctx = ExecutionContext.create(
            workflow_id="wf_001",
            metadata={"trigger": "opportunity_detector", "source": "E12.4"},
        )
        assert ctx.metadata["trigger"] == "opportunity_detector"

    def test_from_definition(self):
        wf = create_campaign_optimization_workflow()
        ctx = ExecutionContext.from_definition(
            wf,
            variables={"game": "P04"},
        )
        assert ctx.workflow_id == wf.workflow_id
        assert ctx.workflow_name == "Campaign Budget Optimization"
        assert len(ctx.task_states) == 5

        # 所有 Task 状态已初始化
        for task in wf.tasks:
            assert task.task_id in ctx.task_states
            assert ctx.task_states[task.task_id].task_name == task.name

    def test_from_definition_with_metadata(self):
        wf = create_campaign_optimization_workflow()
        ctx = ExecutionContext.from_definition(
            wf,
            metadata={"operator": "AI"},
        )
        assert ctx.metadata["operator"] == "AI"

    # ── Lifecycle ────────────────────────────────────────────

    def test_start(self):
        self.ctx.start()
        assert self.ctx.state == WorkflowState.RUNNING

    def test_pause_resume(self):
        self.ctx.start()
        self.ctx.pause()
        assert self.ctx.state == WorkflowState.PAUSED
        assert self.ctx.paused_at != ""

        self.ctx.resume()
        assert self.ctx.state == WorkflowState.RUNNING
        assert self.ctx.resumed_at != ""

    def test_wait(self):
        self.ctx.start()
        self.ctx.wait()
        assert self.ctx.state == WorkflowState.WAITING

    def test_complete(self):
        self.ctx.start()
        self.ctx.complete()
        assert self.ctx.state == WorkflowState.SUCCESS

    def test_fail(self):
        self.ctx.start()
        self.ctx.fail("Connection timeout")
        assert self.ctx.state == WorkflowState.FAILED
        assert self.ctx.metadata["error"] == "Connection timeout"

    def test_cancel(self):
        self.ctx.cancel()
        assert self.ctx.state == WorkflowState.CANCELLED

    def test_is_terminal(self):
        assert self.ctx.is_terminal() is False
        self.ctx.complete()
        assert self.ctx.is_terminal() is True

    def test_is_active(self):
        assert self.ctx.is_active() is False
        self.ctx.start()
        assert self.ctx.is_active() is True

    def test_full_lifecycle(self):
        assert self.ctx.state == WorkflowState.CREATED
        self.ctx.start()
        assert self.ctx.state == WorkflowState.RUNNING
        self.ctx.wait()
        assert self.ctx.state == WorkflowState.WAITING
        self.ctx.start()
        assert self.ctx.state == WorkflowState.RUNNING
        self.ctx.complete()
        assert self.ctx.state == WorkflowState.SUCCESS

    # ── Variable Management ──────────────────────────────────

    def test_set_get_variable(self):
        self.ctx.set_variable("new_budget", 700)
        assert self.ctx.get_variable("new_budget") == 700

    def test_get_variable_default(self):
        assert self.ctx.get_variable("nonexistent") is None
        assert self.ctx.get_variable("nonexistent", "default") == "default"

    def test_set_variables_batch(self):
        self.ctx.set_variables(fatigue=0.82, roas=0.48)
        assert self.ctx.get_variable("fatigue") == 0.82
        assert self.ctx.get_variable("roas") == 0.48

    def test_get_variables(self):
        self.ctx.set_variables(a=1, b=2)
        all_vars = self.ctx.get_variables()
        assert all_vars["a"] == 1
        assert all_vars["b"] == 2
        # 原始 variables 不受影响
        assert self.ctx.variables["a"] == 1

    def test_variable_override(self):
        self.ctx.set_variable("game", "P05")
        assert self.ctx.get_variable("game") == "P05"

    # ── Output Management ────────────────────────────────────

    def test_record_output(self):
        self.ctx.record_output("analyze", {"roas": 0.48, "fatigue": 0.76})
        output = self.ctx.get_output("analyze")
        assert output["roas"] == 0.48
        assert output["fatigue"] == 0.76

    def test_get_output_nonexistent(self):
        assert self.ctx.get_output("nonexistent") is None

    def test_get_all_outputs(self):
        self.ctx.record_output("t1", {"a": 1})
        self.ctx.record_output("t2", {"b": 2})
        all_out = self.ctx.get_all_outputs()
        assert len(all_out) == 2
        assert all_out["t1"]["a"] == 1

    # ── Approval Context ─────────────────────────────────────

    def test_approval_context(self):
        self.ctx.set_approval_context(
            task_id="approve",
            requested_by="AI",
            risk_level="high",
            reason="Budget reduction > 30%",
        )
        approval = self.ctx.get_approval_context()
        assert approval["task_id"] == "approve"
        assert approval["requested_by"] == "AI"
        assert approval["risk_level"] == "high"

    def test_approval_context_default(self):
        assert self.ctx.get_approval_context() == {}

    # ── Progress ─────────────────────────────────────────────

    def test_progress(self):
        wf = create_campaign_optimization_workflow()
        ctx = ExecutionContext.from_definition(wf)
        p = ctx.progress()
        assert p["total"] == 5
        assert p["completed"] == 0
        assert p["pending"] == 5
        assert p["percentage"] == 0.0

    def test_progress_after_completion(self):
        wf = create_campaign_optimization_workflow()
        ctx = ExecutionContext.from_definition(wf)

        # 完成前两个 Task
        tasks = wf.flat_topological_order()
        ctx.complete_task(tasks[0].task_id, {"result": "ok"})
        ctx.complete_task(tasks[1].task_id, {"result": "ok"})

        p = ctx.progress()
        assert p["completed"] == 2
        assert p["percentage"] == 40.0

    def test_progress_with_failed(self):
        wf = create_campaign_optimization_workflow()
        ctx = ExecutionContext.from_definition(wf)
        tasks = wf.flat_topological_order()
        ctx.complete_task(tasks[0].task_id)
        ctx.fail_task(tasks[1].task_id, "error")

        p = ctx.progress()
        assert p["completed"] == 1
        assert p["failed"] == 1

    # ── Summary ──────────────────────────────────────────────

    def test_summary(self):
        self.ctx.start()
        self.ctx.record_output("t1", {"a": 1})
        summary = self.ctx.summary()
        assert summary["state"] == "running"
        assert summary["workflow_id"] == "wf_001"
        assert "t1" in summary["outputs"]

    # ── Updated At ───────────────────────────────────────────

    def test_updated_at_changes_on_mutation(self):
        old = self.ctx.updated_at
        self.ctx.set_variable("test", 1)
        assert self.ctx.updated_at != old

    def test_updated_at_changes_on_state_change(self):
        old = self.ctx.updated_at
        self.ctx.start()
        assert self.ctx.updated_at != old


class TestContextEvents:
    """ContextEvent 单元测试."""

    def test_create_event(self):
        event = ContextEvent(
            event_type=ContextEventType.CONTEXT_CREATED,
            context_id="ctx_001",
            workflow_id="wf_001",
        )
        assert event.event_type == ContextEventType.CONTEXT_CREATED
        assert event.context_id == "ctx_001"

    def test_to_dict(self):
        event = ContextEvent(
            event_type=ContextEventType.TASK_COMPLETED,
            context_id="ctx_001",
            task_id="task_001",
            payload={"duration_ms": 320},
        )
        d = event.to_dict()
        assert d["event_type"] == "task_completed"
        assert d["task_id"] == "task_001"
        assert d["payload"]["duration_ms"] == 320

    def test_from_dict(self):
        data = {
            "event_id": "evt_001",
            "event_type": "task_completed",
            "context_id": "ctx_001",
            "task_id": "task_001",
        }
        event = ContextEvent.from_dict(data)
        assert event.event_id == "evt_001"
        assert event.event_type == ContextEventType.TASK_COMPLETED

    def test_all_event_types(self):
        for et in ContextEventType:
            event = ContextEvent(event_type=et)
            assert event.event_type == et
            d = event.to_dict()
            roundtrip = ContextEvent.from_dict(d)
            assert roundtrip.event_type == et