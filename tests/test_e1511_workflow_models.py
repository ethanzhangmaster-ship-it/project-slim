"""E15.1.1 Workflow Models 测试 — 核心数据模型测试.

测试覆盖:
  - WorkflowTask 创建/序列化
  - WorkflowDefinition 任务管理
  - DAG 依赖管理 (add/remove dependency)
  - 拓扑排序 (分层/扁平)
  - 循环检测
  - WorkflowInstance 生命周期
  - JSON 序列化/反序列化
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.workflow.models import (
    TaskStatus,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowTask,
)


class TestWorkflowTask:
    """WorkflowTask 单元测试."""

    def test_create_task(self):
        task = WorkflowTask(
            name="Analyze",
            action_type="performance_analysis",
            description="Analyze campaign performance",
        )
        assert task.name == "Analyze"
        assert task.action_type == "performance_analysis"
        assert task.task_id != ""
        assert task.depends_on == []

    def test_default_values(self):
        task = WorkflowTask()
        assert task.name == ""
        assert task.action_type == ""
        assert task.requires_approval is False
        assert task.timeout_ms == 0
        assert task.retry_count == 0

    def test_requires_approval(self):
        task = WorkflowTask(name="Approve", requires_approval=True, approval_threshold="Budget > 20%")
        assert task.requires_approval is True
        assert task.approval_threshold == "Budget > 20%"

    def test_parameters(self):
        task = WorkflowTask(
            name="Update Budget",
            parameters={"old_budget": 100, "new_budget": 80},
        )
        assert task.parameters["old_budget"] == 100
        assert task.parameters["new_budget"] == 80

    def test_depends_on(self):
        task = WorkflowTask(name="Execute", depends_on=["analyze", "approve"])
        assert len(task.depends_on) == 2
        assert "analyze" in task.depends_on

    def test_to_dict(self):
        task = WorkflowTask(
            task_id="t1",
            name="Analyze",
            action_type="performance_analysis",
            depends_on=["init"],
            requires_approval=True,
            timeout_ms=5000,
            retry_count=3,
        )
        d = task.to_dict()
        assert d["task_id"] == "t1"
        assert d["name"] == "Analyze"
        assert d["action_type"] == "performance_analysis"
        assert d["depends_on"] == ["init"]
        assert d["requires_approval"] is True
        assert d["timeout_ms"] == 5000
        assert d["retry_count"] == 3

    def test_from_dict(self):
        data = {
            "task_id": "t1",
            "name": "Analyze",
            "action_type": "performance_analysis",
            "depends_on": ["init"],
            "requires_approval": True,
            "timeout_ms": 5000,
            "retry_count": 3,
        }
        task = WorkflowTask.from_dict(data)
        assert task.task_id == "t1"
        assert task.name == "Analyze"
        assert task.requires_approval is True

    def test_unique_ids(self):
        t1 = WorkflowTask()
        t2 = WorkflowTask()
        assert t1.task_id != t2.task_id


class TestWorkflowDefinition:
    """WorkflowDefinition 单元测试."""

    def setup_method(self):
        self.wf = WorkflowDefinition(
            name="Campaign Optimizer",
            version="1.0.0",
            description="Optimize campaign budgets",
        )

    # ── Task Management ──────────────────────────────────────

    def test_add_task(self):
        task = WorkflowTask(name="Analyze", action_type="analysis")
        self.wf.add_task(task)
        assert len(self.wf.tasks) == 1
        assert self.wf.get_task(task.task_id) is task

    def test_add_duplicate_task_raises(self):
        task = WorkflowTask(name="Analyze")
        self.wf.add_task(task)
        with pytest.raises(ValueError, match="already exists"):
            self.wf.add_task(task)

    def test_remove_task(self):
        task = WorkflowTask(name="Analyze")
        self.wf.add_task(task)
        assert self.wf.remove_task(task.task_id) is True
        assert len(self.wf.tasks) == 0

    def test_remove_nonexistent_task(self):
        assert self.wf.remove_task("nonexistent") is False

    def test_remove_task_cleans_up_dependencies(self):
        t1 = WorkflowTask(name="Analyze")
        t2 = WorkflowTask(name="Execute", depends_on=[t1.task_id])
        self.wf.add_task(t1)
        self.wf.add_task(t2)

        self.wf.remove_task(t1.task_id)
        assert len(self.wf.tasks) == 1
        assert self.wf.tasks[0].depends_on == []

    def test_get_task_by_name(self):
        t1 = WorkflowTask(name="Analyze")
        self.wf.add_task(t1)
        found = self.wf.get_task_by_name("Analyze")
        assert found is t1

    def test_get_task_by_name_not_found(self):
        assert self.wf.get_task_by_name("Nonexistent") is None

    # ── Dependency Management ────────────────────────────────

    def test_add_dependency(self):
        t1 = WorkflowTask(name="Analyze")
        t2 = WorkflowTask(name="Execute")
        self.wf.add_task(t1)
        self.wf.add_task(t2)
        self.wf.add_dependency(t2.task_id, t1.task_id)

        assert t1.task_id in t2.depends_on

    def test_add_dependency_task_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            self.wf.add_dependency("nonexistent", "also_nonexistent")

    def test_add_dependency_dep_not_found(self):
        t1 = WorkflowTask(name="Analyze")
        self.wf.add_task(t1)
        with pytest.raises(ValueError, match="not found"):
            self.wf.add_dependency(t1.task_id, "nonexistent")

    def test_remove_dependency(self):
        t1 = WorkflowTask(name="Analyze")
        t2 = WorkflowTask(name="Execute", depends_on=[t1.task_id])
        self.wf.add_task(t1)
        self.wf.add_task(t2)
        assert self.wf.remove_dependency(t2.task_id, t1.task_id) is True
        assert t1.task_id not in t2.depends_on

    def test_remove_dependency_nonexistent(self):
        assert self.wf.remove_dependency("nonexistent", "also") is False

    def test_no_duplicate_dependency(self):
        t1 = WorkflowTask(name="Analyze")
        t2 = WorkflowTask(name="Execute")
        self.wf.add_task(t1)
        self.wf.add_task(t2)
        self.wf.add_dependency(t2.task_id, t1.task_id)
        self.wf.add_dependency(t2.task_id, t1.task_id)
        assert t2.depends_on.count(t1.task_id) == 1

    # ── DAG Query ────────────────────────────────────────────

    def test_get_entry_tasks(self):
        t1 = WorkflowTask(name="A")  # no deps
        t2 = WorkflowTask(name="B", depends_on=[t1.task_id])
        t3 = WorkflowTask(name="C", depends_on=[t1.task_id])
        self.wf.add_task(t1)
        self.wf.add_task(t2)
        self.wf.add_task(t3)

        entries = self.wf.get_entry_tasks()
        assert len(entries) == 1
        assert entries[0].name == "A"

    def test_get_exit_tasks(self):
        t1 = WorkflowTask(name="A")
        t2 = WorkflowTask(name="B", depends_on=[t1.task_id])
        t3 = WorkflowTask(name="C", depends_on=[t1.task_id])
        self.wf.add_task(t1)
        self.wf.add_task(t2)
        self.wf.add_task(t3)

        exits = self.wf.get_exit_tasks()
        assert len(exits) == 2
        names = {t.name for t in exits}
        assert names == {"B", "C"}

    def test_get_downstream_tasks(self):
        t1 = WorkflowTask(name="A")
        t2 = WorkflowTask(name="B", depends_on=[t1.task_id])
        t3 = WorkflowTask(name="C", depends_on=[t1.task_id])
        self.wf.add_task(t1)
        self.wf.add_task(t2)
        self.wf.add_task(t3)

        downstream = self.wf.get_downstream_tasks(t1.task_id)
        assert len(downstream) == 2

    def test_get_upstream_tasks(self):
        t1 = WorkflowTask(name="A")
        t2 = WorkflowTask(name="B", depends_on=[t1.task_id])
        self.wf.add_task(t1)
        self.wf.add_task(t2)

        upstream = self.wf.get_upstream_tasks(t2.task_id)
        assert len(upstream) == 1
        assert upstream[0].name == "A"

    # ── Topological Sort ─────────────────────────────────────

    def test_topological_order_simple_chain(self):
        t1 = WorkflowTask(name="A")
        t2 = WorkflowTask(name="B", depends_on=[t1.task_id])
        t3 = WorkflowTask(name="C", depends_on=[t2.task_id])
        self.wf.add_task(t1)
        self.wf.add_task(t2)
        self.wf.add_task(t3)

        layers = self.wf.topological_order()
        assert len(layers) == 3
        assert layers[0][0].name == "A"
        assert layers[1][0].name == "B"
        assert layers[2][0].name == "C"

    def test_topological_order_parallel(self):
        t1 = WorkflowTask(name="A")
        t2 = WorkflowTask(name="B", depends_on=[t1.task_id])
        t3 = WorkflowTask(name="C", depends_on=[t1.task_id])
        self.wf.add_task(t1)
        self.wf.add_task(t2)
        self.wf.add_task(t3)

        layers = self.wf.topological_order()
        assert len(layers) == 2
        assert len(layers[0]) == 1  # A
        assert len(layers[1]) == 2  # B, C (parallel)

    def test_topological_order_diamond(self):
        t1 = WorkflowTask(name="A")
        t2 = WorkflowTask(name="B", depends_on=[t1.task_id])
        t3 = WorkflowTask(name="C", depends_on=[t1.task_id])
        t4 = WorkflowTask(name="D", depends_on=[t2.task_id, t3.task_id])
        self.wf.add_task(t1)
        self.wf.add_task(t2)
        self.wf.add_task(t3)
        self.wf.add_task(t4)

        layers = self.wf.topological_order()
        assert len(layers) == 3
        assert layers[0][0].name == "A"
        assert {t.name for t in layers[1]} == {"B", "C"}
        assert layers[2][0].name == "D"

    def test_topological_order_independent(self):
        t1 = WorkflowTask(name="A")
        t2 = WorkflowTask(name="B")
        self.wf.add_task(t1)
        self.wf.add_task(t2)

        layers = self.wf.topological_order()
        assert len(layers) == 1
        assert len(layers[0]) == 2

    def test_flat_topological_order(self):
        t1 = WorkflowTask(name="A")
        t2 = WorkflowTask(name="B", depends_on=[t1.task_id])
        t3 = WorkflowTask(name="C", depends_on=[t2.task_id])
        self.wf.add_task(t1)
        self.wf.add_task(t2)
        self.wf.add_task(t3)

        flat = self.wf.flat_topological_order()
        assert [t.name for t in flat] == ["A", "B", "C"]

    def test_topological_order_with_cycle_raises(self):
        t1 = WorkflowTask(name="A", depends_on=["t2"])
        t2 = WorkflowTask(name="B", depends_on=["t1"])
        t1.task_id = "t1"
        t2.task_id = "t2"
        self.wf.add_task(t1)
        self.wf.add_task(t2)

        with pytest.raises(ValueError, match="circular dependency"):
            self.wf.topological_order()

    # ── Cycle Detection ──────────────────────────────────────

    def test_simple_cycle_detected(self):
        t1 = WorkflowTask(name="A", depends_on=["t2"])
        t2 = WorkflowTask(name="B", depends_on=["t1"])
        t1.task_id = "t1"
        t2.task_id = "t2"
        self.wf.add_task(t1)
        self.wf.add_task(t2)

        assert self.wf._has_cycle() is True

    def test_self_loop_detected(self):
        t1 = WorkflowTask(name="A", depends_on=["t1"])
        t1.task_id = "t1"
        self.wf.add_task(t1)

        assert self.wf._has_cycle() is True

    def test_no_cycle(self):
        t1 = WorkflowTask(name="A")
        t2 = WorkflowTask(name="B", depends_on=[t1.task_id])
        t3 = WorkflowTask(name="C", depends_on=[t2.task_id])
        self.wf.add_task(t1)
        self.wf.add_task(t2)
        self.wf.add_task(t3)

        assert self.wf._has_cycle() is False

    def test_long_cycle_detected(self):
        t1 = WorkflowTask(name="A", depends_on=["t4"])
        t2 = WorkflowTask(name="B", depends_on=["t1"])
        t3 = WorkflowTask(name="C", depends_on=["t2"])
        t4 = WorkflowTask(name="D", depends_on=["t3"])
        t1.task_id = "t1"
        t2.task_id = "t2"
        t3.task_id = "t3"
        t4.task_id = "t4"
        self.wf.add_task(t1)
        self.wf.add_task(t2)
        self.wf.add_task(t3)
        self.wf.add_task(t4)

        assert self.wf._has_cycle() is True

    # ── Validation ───────────────────────────────────────────

    def test_valid_workflow(self):
        t1 = WorkflowTask(name="A")
        t2 = WorkflowTask(name="B", depends_on=[t1.task_id])
        self.wf.add_task(t1)
        self.wf.add_task(t2)
        assert self.wf.is_valid() is True
        assert self.wf.validate() == []

    def test_empty_workflow_invalid(self):
        errors = self.wf.validate()
        assert "no tasks" in errors[0]

    def test_broken_dependency_invalid(self):
        t1 = WorkflowTask(name="A", depends_on=["nonexistent"])
        self.wf.add_task(t1)
        errors = self.wf.validate()
        assert len(errors) == 1
        assert "non-existent" in errors[0]

    def test_cycle_invalid(self):
        t1 = WorkflowTask(name="A", depends_on=["t2"])
        t2 = WorkflowTask(name="B", depends_on=["t1"])
        t1.task_id = "t1"
        t2.task_id = "t2"
        self.wf.add_task(t1)
        self.wf.add_task(t2)
        errors = self.wf.validate()
        assert any("circular" in e.lower() for e in errors)

    # ── Serialization ────────────────────────────────────────

    def test_to_dict(self):
        t1 = WorkflowTask(name="A")
        t2 = WorkflowTask(name="B", depends_on=[t1.task_id])
        self.wf.add_task(t1)
        self.wf.add_task(t2)

        d = self.wf.to_dict()
        assert d["name"] == "Campaign Optimizer"
        assert d["version"] == "1.0.0"
        assert len(d["tasks"]) == 2

    def test_from_dict(self):
        data = {
            "workflow_id": "wf_001",
            "name": "Test",
            "version": "2.0.0",
            "tasks": [
                {"task_id": "t1", "name": "A", "action_type": "analysis"},
                {"task_id": "t2", "name": "B", "action_type": "execute", "depends_on": ["t1"]},
            ],
        }
        wf = WorkflowDefinition.from_dict(data)
        assert wf.workflow_id == "wf_001"
        assert wf.name == "Test"
        assert wf.version == "2.0.0"
        assert len(wf.tasks) == 2
        assert wf.tasks[1].depends_on == ["t1"]

    def test_roundtrip(self):
        t1 = WorkflowTask(name="A")
        t2 = WorkflowTask(name="B", depends_on=[t1.task_id])
        self.wf.add_task(t1)
        self.wf.add_task(t2)

        data = self.wf.to_dict()
        restored = WorkflowDefinition.from_dict(data)
        assert restored.name == self.wf.name
        assert len(restored.tasks) == len(self.wf.tasks)
        assert restored.tasks[1].depends_on == [t1.task_id]

    # ── Complex DAG ──────────────────────────────────────────

    def test_complex_dag(self):
        """8 步 Growth Recovery Workflow."""
        t1 = WorkflowTask(name="Analyze Adjust", action_type="analyze_adjust")
        t2 = WorkflowTask(name="Detect Fatigue", action_type="detect_fatigue", depends_on=[t1.task_id])
        t3 = WorkflowTask(name="Mutate Creative", action_type="mutate_creative", depends_on=[t2.task_id])
        t4 = WorkflowTask(name="Human Approval", action_type="human_approval", depends_on=[t3.task_id], requires_approval=True)
        t5 = WorkflowTask(name="Upload to Meta", action_type="upload_creative", depends_on=[t4.task_id])
        t6 = WorkflowTask(name="Launch Test", action_type="create_campaign", depends_on=[t5.task_id])
        t7 = WorkflowTask(name="Observe D7", action_type="observe_result", depends_on=[t6.task_id])
        t8 = WorkflowTask(name="Store Learning", action_type="store_learning", depends_on=[t7.task_id])

        for t in [t1, t2, t3, t4, t5, t6, t7, t8]:
            self.wf.add_task(t)

        assert self.wf.is_valid()
        assert len(self.wf.topological_order()) == 8
        assert len(self.wf.get_entry_tasks()) == 1
        assert len(self.wf.get_exit_tasks()) == 1


class TestWorkflowInstance:
    """WorkflowInstance 单元测试."""

    def test_create_instance(self):
        inst = WorkflowInstance(
            workflow_id="wf_001",
            workflow_name="Campaign Optimizer",
            context={"game": "P04", "campaign": "fb_android"},
        )
        assert inst.workflow_id == "wf_001"
        assert inst.status == WorkflowStatus.CREATED
        assert inst.context["game"] == "P04"

    def test_lifecycle(self):
        inst = WorkflowInstance(workflow_id="wf_001")
        inst.start()
        assert inst.status == WorkflowStatus.RUNNING
        assert inst.started_at != ""

        inst.complete(WorkflowStatus.SUCCESS)
        assert inst.status == WorkflowStatus.SUCCESS
        assert inst.completed_at != ""
        assert inst.is_terminal() is True

    def test_fail(self):
        inst = WorkflowInstance(workflow_id="wf_001")
        inst.fail("Connection timeout")
        assert inst.status == WorkflowStatus.FAILED
        assert inst.error == "Connection timeout"
        assert inst.is_terminal() is True

    def test_cancel(self):
        inst = WorkflowInstance(workflow_id="wf_001")
        inst.cancel()
        assert inst.status == WorkflowStatus.CANCELLED
        assert inst.is_terminal() is True

    def test_task_statuses(self):
        inst = WorkflowInstance(workflow_id="wf_001")
        inst.update_task_status("t1", TaskStatus.RUNNING)
        inst.update_task_status("t2", TaskStatus.SUCCESS)
        assert inst.get_task_status("t1") == TaskStatus.RUNNING
        assert inst.get_task_status("t2") == TaskStatus.SUCCESS
        assert inst.get_task_status("t3") == TaskStatus.PENDING

    def test_is_terminal(self):
        inst = WorkflowInstance(workflow_id="wf_001")
        assert inst.is_terminal() is False
        inst.start()
        assert inst.is_terminal() is False
        inst.complete()
        assert inst.is_terminal() is True

    def test_to_dict(self):
        inst = WorkflowInstance(
            workflow_id="wf_001",
            workflow_name="Test",
            context={"game": "P04"},
        )
        inst.update_task_status("t1", TaskStatus.SUCCESS)
        d = inst.to_dict()
        assert d["status"] == "created"
        assert d["task_statuses"]["t1"] == "success"

    def test_from_dict(self):
        data = {
            "instance_id": "inst_001",
            "workflow_id": "wf_001",
            "workflow_name": "Test",
            "status": "running",
            "context": {"game": "P04"},
            "task_statuses": {"t1": "success", "t2": "failed"},
        }
        inst = WorkflowInstance.from_dict(data)
        assert inst.instance_id == "inst_001"
        assert inst.status == WorkflowStatus.RUNNING
        assert inst.get_task_status("t1") == TaskStatus.SUCCESS

    def test_roundtrip(self):
        inst = WorkflowInstance(
            workflow_id="wf_001",
            workflow_name="Test",
            context={"game": "P04"},
        )
        inst.update_task_status("t1", TaskStatus.SUCCESS)
        data = inst.to_dict()
        restored = WorkflowInstance.from_dict(data)
        assert restored.workflow_id == inst.workflow_id
        assert restored.get_task_status("t1") == TaskStatus.SUCCESS


class TestWorkflowStatus:
    """枚举值测试."""

    def test_workflow_status_values(self):
        assert WorkflowStatus.CREATED.value == "created"
        assert WorkflowStatus.RUNNING.value == "running"
        assert WorkflowStatus.WAITING_APPROVAL.value == "waiting_approval"
        assert WorkflowStatus.SUCCESS.value == "success"
        assert WorkflowStatus.FAILED.value == "failed"
        assert WorkflowStatus.CANCELLED.value == "cancelled"

    def test_task_status_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.SUCCESS.value == "success"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.SKIPPED.value == "skipped"
        assert TaskStatus.CANCELLED.value == "cancelled"