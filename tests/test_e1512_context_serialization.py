"""E15.1.2 Context Serialization 测试 — 序列化与恢复测试.

测试覆盖:
  - ExecutionContext 序列化/反序列化
  - TaskExecutionState 序列化/反序列化
  - 完整往返 (roundtrip)
  - 断点恢复场景
"""

from __future__ import annotations

import json

import pytest

from market_ops.creative_vision_runtime.growth_runtime.workflow.builder import (
    create_campaign_optimization_workflow,
)
from market_ops.creative_vision_runtime.growth_runtime.workflow.context import ExecutionContext
from market_ops.creative_vision_runtime.growth_runtime.workflow.state import (
    TaskExecutionState,
    TaskExecutionStatus,
    WorkflowState,
)


class TestSerialization:
    """ExecutionContext 序列化测试."""

    def setup_method(self):
        self.wf = create_campaign_optimization_workflow()
        self.ctx = ExecutionContext.from_definition(
            self.wf,
            variables={"game": "P04", "budget": 5000},
            metadata={"trigger": "opportunity_detector"},
        )

    # ── Basic Serialization ──────────────────────────────────

    def test_to_dict(self):
        self.ctx.start()
        d = self.ctx.to_dict()
        assert d["context_id"] == self.ctx.context_id
        assert d["workflow_id"] == self.ctx.workflow_id
        assert d["state"] == "running"
        assert d["variables"]["game"] == "P04"
        assert len(d["task_states"]) == 5

    def test_from_dict(self):
        self.ctx.start()
        d = self.ctx.to_dict()
        restored = ExecutionContext.from_dict(d)
        assert restored.context_id == self.ctx.context_id
        assert restored.state == WorkflowState.RUNNING
        assert restored.get_variable("game") == "P04"

    def test_roundtrip(self):
        self.ctx.start()
        self.ctx.record_output("t1", {"a": 1})
        self.ctx.set_variable("fatigue", 0.76)

        d = self.ctx.to_dict()
        restored = ExecutionContext.from_dict(d)

        assert restored.context_id == self.ctx.context_id
        assert restored.state == self.ctx.state
        assert restored.get_variable("fatigue") == 0.76
        assert restored.get_output("t1")["a"] == 1

    def test_roundtrip_with_task_states(self):
        tasks = self.wf.flat_topological_order()
        self.ctx.start()
        self.ctx.complete_task(tasks[0].task_id, {"roas": 0.48})
        self.ctx.complete_task(tasks[1].task_id, {"rec": "reduce_20_percent"})

        d = self.ctx.to_dict()
        restored = ExecutionContext.from_dict(d)

        assert restored.get_task_state(tasks[0].task_id).status == TaskExecutionStatus.COMPLETED
        assert restored.get_output(tasks[0].task_id)["roas"] == 0.48
        assert restored.get_task_state(tasks[1].task_id).status == TaskExecutionStatus.COMPLETED

    # ── JSON Serialization ───────────────────────────────────

    def test_json_roundtrip(self):
        self.ctx.start()
        self.ctx.complete_task(self.wf.tasks[0].task_id, {"roas": 0.48})

        json_str = json.dumps(self.ctx.to_dict(), ensure_ascii=False)
        data = json.loads(json_str)
        restored = ExecutionContext.from_dict(data)

        assert restored.context_id == self.ctx.context_id
        assert restored.state == WorkflowState.RUNNING
        assert restored.get_output(self.wf.tasks[0].task_id)["roas"] == 0.48

    def test_json_with_complex_output(self):
        self.ctx.record_output("analyze", {
            "metrics": {"roas": 0.48, "ctr": 0.02},
            "tags": ["fatigue", "high_cpa"],
            "confidence": 0.91,
        })
        json_str = json.dumps(self.ctx.to_dict(), ensure_ascii=False)
        data = json.loads(json_str)
        restored = ExecutionContext.from_dict(data)
        assert restored.get_output("analyze")["metrics"]["roas"] == 0.48
        assert "fatigue" in restored.get_output("analyze")["tags"]

    # ── Resume Scenario ──────────────────────────────────────

    def test_resume_after_pause(self):
        """模拟断点恢复: 暂停后从序列化恢复."""
        tasks = self.wf.flat_topological_order()
        self.ctx.start()

        # 执行前两个 Task
        self.ctx.complete_task(tasks[0].task_id, {"a": 1})
        self.ctx.complete_task(tasks[1].task_id, {"b": 2})

        # 暂停
        self.ctx.pause()
        assert self.ctx.state == WorkflowState.PAUSED

        # 序列化 + 恢复
        d = self.ctx.to_dict()
        restored = ExecutionContext.from_dict(d)

        # 验证状态恢复
        assert restored.state == WorkflowState.PAUSED
        assert restored.get_output(tasks[0].task_id)["a"] == 1
        assert restored.get_output(tasks[1].task_id)["b"] == 2
        assert restored.get_task_state(tasks[2].task_id).status == TaskExecutionStatus.PENDING

        # 恢复执行
        restored.resume()
        assert restored.state == WorkflowState.RUNNING

    def test_resume_after_failure(self):
        """模拟失败后恢复."""
        tasks = self.wf.flat_topological_order()
        self.ctx.start()

        self.ctx.complete_task(tasks[0].task_id)
        self.ctx.fail_task(tasks[1].task_id, "API timeout")

        # 序列化
        d = self.ctx.to_dict()
        restored = ExecutionContext.from_dict(d)

        assert restored.get_task_state(tasks[0].task_id).status == TaskExecutionStatus.COMPLETED
        assert restored.get_task_state(tasks[1].task_id).status == TaskExecutionStatus.FAILED
        assert restored.get_task_state(tasks[1].task_id).error == "API timeout"

        # 设置 retry_max 使任务可重试
        restored.get_task_state(tasks[1].task_id).retry_max = 3
        # 重试失败任务
        restored.retry_task(tasks[1].task_id)
        assert restored.get_task_state(tasks[1].task_id).status == TaskExecutionStatus.PENDING

    def test_resume_with_all_completed(self):
        """全部完成后恢复."""
        self.ctx.start()
        for task in self.wf.flat_topological_order():
            self.ctx.complete_task(task.task_id)
        self.ctx.complete()

        d = self.ctx.to_dict()
        restored = ExecutionContext.from_dict(d)

        assert restored.state == WorkflowState.SUCCESS
        assert restored.all_tasks_completed()
        assert restored.is_terminal()

    # ── TaskExecutionState Serialization ─────────────────────

    def test_task_state_roundtrip(self):
        state = TaskExecutionState(
            task_id="task_001",
            task_name="Analyze",
            retry_max=3,
        )
        state.start()
        state.complete({"roas": 0.48})

        d = state.to_dict()
        restored = TaskExecutionState.from_dict(d)

        assert restored.task_id == "task_001"
        assert restored.status == TaskExecutionStatus.COMPLETED
        assert restored.output["roas"] == 0.48
        assert restored.duration_ms >= 0

    def test_task_state_failed_roundtrip(self):
        state = TaskExecutionState(task_id="t1", task_name="Test")
        state.fail("error")
        state.retry()
        state.fail("error again")

        d = state.to_dict()
        restored = TaskExecutionState.from_dict(d)

        assert restored.task_id == "t1"
        assert restored.retry_current == 1
        assert restored.error == "error again"

    # ── Empty Context ────────────────────────────────────────

    def test_empty_context_roundtrip(self):
        ctx = ExecutionContext()
        d = ctx.to_dict()
        restored = ExecutionContext.from_dict(d)
        assert restored.state == WorkflowState.CREATED
        assert restored.task_states == {}
        assert restored.variables == {}

    def test_empty_context_json(self):
        ctx = ExecutionContext()
        json_str = json.dumps(ctx.to_dict(), ensure_ascii=False)
        data = json.loads(json_str)
        restored = ExecutionContext.from_dict(data)
        assert restored.context_id == ctx.context_id

    # ── Metadata Preservation ────────────────────────────────

    def test_metadata_preserved(self):
        self.ctx.metadata = {
            "trigger": "growth_opportunity_detector",
            "source": "E12.4 Feedback Controller",
            "operator": "AI",
            "approval": {
                "task_id": "approve",
                "requested_by": "AI",
                "risk_level": "high",
            },
        }
        d = self.ctx.to_dict()
        restored = ExecutionContext.from_dict(d)
        assert restored.metadata["trigger"] == "growth_opportunity_detector"
        assert restored.metadata["operator"] == "AI"
        assert restored.metadata["approval"]["risk_level"] == "high"

    # ── Timestamp Preservation ───────────────────────────────

    def test_timestamps_preserved(self):
        self.ctx.start()
        self.ctx.pause()
        self.ctx.resume()

        d = self.ctx.to_dict()
        restored = ExecutionContext.from_dict(d)

        assert restored.created_at == self.ctx.created_at
        assert restored.paused_at == self.ctx.paused_at
        assert restored.resumed_at == self.ctx.resumed_at