"""E15.1.2 Context State 测试 — 运行时状态测试.

测试覆盖:
  - WorkflowState 枚举与转换
  - TaskExecutionStatus 枚举
  - TaskExecutionState 生命周期
  - 重试机制
  - 序列化
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.workflow.models import (
    WorkflowStatus,
)
from market_ops.creative_vision_runtime.growth_runtime.workflow.state import (
    TaskExecutionState,
    TaskExecutionStatus,
    WorkflowState,
)


class TestWorkflowState:
    """WorkflowState 枚举测试."""

    def test_values(self):
        assert WorkflowState.CREATED.value == "created"
        assert WorkflowState.RUNNING.value == "running"
        assert WorkflowState.PAUSED.value == "paused"
        assert WorkflowState.WAITING.value == "waiting"
        assert WorkflowState.SUCCESS.value == "success"
        assert WorkflowState.FAILED.value == "failed"
        assert WorkflowState.CANCELLED.value == "cancelled"

    def test_is_terminal(self):
        assert WorkflowState.CREATED.is_terminal() is False
        assert WorkflowState.RUNNING.is_terminal() is False
        assert WorkflowState.PAUSED.is_terminal() is False
        assert WorkflowState.WAITING.is_terminal() is False
        assert WorkflowState.SUCCESS.is_terminal() is True
        assert WorkflowState.FAILED.is_terminal() is True
        assert WorkflowState.CANCELLED.is_terminal() is True

    def test_is_active(self):
        assert WorkflowState.CREATED.is_active() is False
        assert WorkflowState.RUNNING.is_active() is True
        assert WorkflowState.PAUSED.is_active() is True
        assert WorkflowState.WAITING.is_active() is True
        assert WorkflowState.SUCCESS.is_active() is False
        assert WorkflowState.FAILED.is_active() is False

    def test_from_workflow_status(self):
        assert WorkflowState.from_workflow_status(WorkflowStatus.CREATED) == WorkflowState.CREATED
        assert WorkflowState.from_workflow_status(WorkflowStatus.RUNNING) == WorkflowState.RUNNING
        assert WorkflowState.from_workflow_status(WorkflowStatus.WAITING_APPROVAL) == WorkflowState.WAITING
        assert WorkflowState.from_workflow_status(WorkflowStatus.SUCCESS) == WorkflowState.SUCCESS
        assert WorkflowState.from_workflow_status(WorkflowStatus.FAILED) == WorkflowState.FAILED
        assert WorkflowState.from_workflow_status(WorkflowStatus.CANCELLED) == WorkflowState.CANCELLED


class TestTaskExecutionStatus:
    """TaskExecutionStatus 枚举测试."""

    def test_values(self):
        assert TaskExecutionStatus.PENDING.value == "pending"
        assert TaskExecutionStatus.RUNNING.value == "running"
        assert TaskExecutionStatus.WAITING.value == "waiting"
        assert TaskExecutionStatus.COMPLETED.value == "completed"
        assert TaskExecutionStatus.FAILED.value == "failed"
        assert TaskExecutionStatus.SKIPPED.value == "skipped"
        assert TaskExecutionStatus.TIMEOUT.value == "timeout"


class TestTaskExecutionState:
    """TaskExecutionState 单元测试."""

    def setup_method(self):
        self.state = TaskExecutionState(
            task_id="task_001",
            task_name="Analyze",
            retry_max=3,
        )

    def test_default_state(self):
        assert self.state.task_id == "task_001"
        assert self.state.task_name == "Analyze"
        assert self.state.status == TaskExecutionStatus.PENDING
        assert self.state.retry_current == 0

    def test_lifecycle(self):
        self.state.start()
        assert self.state.status == TaskExecutionStatus.RUNNING
        assert self.state.started_at != ""

        self.state.complete({"roas": 0.48})
        assert self.state.status == TaskExecutionStatus.COMPLETED
        assert self.state.completed_at != ""
        assert self.state.output["roas"] == 0.48
        assert self.state.duration_ms >= 0

    def test_fail(self):
        self.state.start()
        self.state.fail("Connection timeout")
        assert self.state.status == TaskExecutionStatus.FAILED
        assert self.state.error == "Connection timeout"

    def test_skip(self):
        self.state.start()
        self.state.skip("Already processed")
        assert self.state.status == TaskExecutionStatus.SKIPPED
        assert self.state.error == "Already processed"

    def test_skip_without_reason(self):
        self.state.skip()
        assert self.state.status == TaskExecutionStatus.SKIPPED
        assert self.state.error == ""

    def test_timeout(self):
        self.state.start()
        self.state.timeout()
        assert self.state.status == TaskExecutionStatus.TIMEOUT

    def test_wait(self):
        self.state.wait()
        assert self.state.status == TaskExecutionStatus.WAITING

    def test_is_terminal(self):
        assert self.state.is_terminal() is False
        self.state.complete()
        assert self.state.is_terminal() is True

    def test_all_terminal_states(self):
        for status in [TaskExecutionStatus.COMPLETED, TaskExecutionStatus.FAILED,
                       TaskExecutionStatus.SKIPPED, TaskExecutionStatus.TIMEOUT]:
            state = TaskExecutionState(status=status)
            assert state.is_terminal() is True

    # ── Retry ────────────────────────────────────────────────

    def test_can_retry(self):
        assert self.state.can_retry() is True
        self.state.retry_max = 0
        assert self.state.can_retry() is False

    def test_retry(self):
        self.state.fail("error")
        assert self.state.can_retry() is True
        self.state.retry()
        assert self.state.status == TaskExecutionStatus.PENDING
        assert self.state.retry_current == 1
        assert self.state.error == ""
        assert self.state.can_retry() is True

    def test_retry_exhausted(self):
        self.state.retry_max = 2
        self.state.fail("error")
        self.state.retry()
        self.state.fail("error")
        self.state.retry()
        assert self.state.retry_current == 2
        assert self.state.can_retry() is False

    def test_retry_preserves_task_info(self):
        self.state.fail("error")
        self.state.retry()
        assert self.state.task_id == "task_001"
        assert self.state.task_name == "Analyze"

    # ── Duration ─────────────────────────────────────────────

    def test_duration(self):
        self.state.start()
        self.state.complete()
        assert self.state.duration_ms >= 0

    def test_duration_without_start(self):
        """未 start 直接 complete 不应报错."""
        self.state.complete()
        assert self.state.duration_ms == 0.0

    def test_duration_skip(self):
        self.state.start()
        self.state.skip()
        assert self.state.duration_ms >= 0

    # ── Serialization ────────────────────────────────────────

    def test_to_dict(self):
        self.state.start()
        self.state.complete({"roas": 0.48})
        d = self.state.to_dict()
        assert d["task_id"] == "task_001"
        assert d["status"] == "completed"
        assert d["output"]["roas"] == 0.48

    def test_from_dict(self):
        data = {
            "task_id": "task_001",
            "task_name": "Analyze",
            "status": "completed",
            "output": {"roas": 0.48},
            "retry_current": 1,
            "retry_max": 3,
        }
        state = TaskExecutionState.from_dict(data)
        assert state.task_id == "task_001"
        assert state.status == TaskExecutionStatus.COMPLETED
        assert state.output["roas"] == 0.48
        assert state.retry_current == 1

    def test_roundtrip(self):
        self.state.start()
        self.state.complete({"roas": 0.48})
        data = self.state.to_dict()
        restored = TaskExecutionState.from_dict(data)
        assert restored.task_id == self.state.task_id
        assert restored.status == TaskExecutionStatus.COMPLETED
        assert restored.output["roas"] == 0.48

    # ── Metadata ─────────────────────────────────────────────

    def test_metadata(self):
        state = TaskExecutionState(
            metadata={"adapter": "meta", "confidence": 0.9},
        )
        assert state.metadata["adapter"] == "meta"

    def test_default_output(self):
        state = TaskExecutionState()
        assert state.output == {}