"""E15.1.1 Workflow Builder 测试 — Builder 模式测试.

测试覆盖:
  - WorkflowBuilder 链式构建
  - 步骤添加/移除
  - 依赖管理
  - build() 验证
  - 预设 Workflow 工厂函数
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.workflow.builder import (
    WorkflowBuilder,
    create_campaign_optimization_workflow,
    create_creative_refresh_workflow,
    create_growth_recovery_workflow,
)
from market_ops.creative_vision_runtime.growth_runtime.workflow.models import (
    WorkflowDefinition,
    WorkflowTask,
)


class TestWorkflowBuilder:
    """WorkflowBuilder 单元测试."""

    def test_create_builder(self):
        builder = WorkflowBuilder("campaign_optimizer")
        assert builder._name == "campaign_optimizer"
        assert builder._version == "1.0.0"
        assert builder.task_count() == 0

    def test_add_step(self):
        builder = WorkflowBuilder("test")
        builder.add_step("Analyze", "performance_analysis")
        assert builder.task_count() == 1

    def test_add_step_chain(self):
        builder = WorkflowBuilder("test")
        builder.add_step("A", "analysis") \
               .add_step("B", "execute") \
               .add_step("C", "verify")
        assert builder.task_count() == 3

    def test_add_step_with_options(self):
        builder = WorkflowBuilder("test")
        builder.add_step(
            "Approve",
            "human_approval",
            requires_approval=True,
            approval_threshold="Budget > 20%",
            timeout_ms=5000,
            retry_count=3,
        )
        task = builder.get_task_by_name("Approve")
        assert task.requires_approval is True
        assert task.approval_threshold == "Budget > 20%"
        assert task.timeout_ms == 5000
        assert task.retry_count == 3

    def test_remove_step(self):
        builder = WorkflowBuilder("test")
        builder.add_step("A", "analysis")
        task = builder.get_task_by_name("A")
        builder.remove_step(task.task_id)
        assert builder.task_count() == 0

    def test_get_task(self):
        builder = WorkflowBuilder("test")
        builder.add_step("Analyze", "analysis", task_id="t1")
        task = builder.get_task("t1")
        assert task is not None
        assert task.name == "Analyze"

    def test_get_task_by_name(self):
        builder = WorkflowBuilder("test")
        builder.add_step("Analyze", "analysis")
        task = builder.get_task_by_name("Analyze")
        assert task is not None

    # ── Dependency Management ────────────────────────────────

    def test_depends_on(self):
        builder = WorkflowBuilder("test")
        builder.add_step("A", "analysis") \
               .add_step("B", "execute") \
               .depends_on("B", "A")

        task_b = builder.get_task_by_name("B")
        task_a = builder.get_task_by_name("A")
        assert task_a.task_id in task_b.depends_on

    def test_depends_on_by_name(self):
        """depends_on 支持按名称引用."""
        builder = WorkflowBuilder("test")
        builder.add_step("Analyze Campaign", "analysis") \
               .add_step("Execute", "execute") \
               .depends_on("Execute", "Analyze Campaign")

        task_exec = builder.get_task_by_name("Execute")
        task_analyze = builder.get_task_by_name("Analyze Campaign")
        assert task_analyze.task_id in task_exec.depends_on

    def test_depends_on_nonexistent_raises(self):
        builder = WorkflowBuilder("test")
        builder.add_step("A", "analysis")
        with pytest.raises(ValueError, match="not found"):
            builder.depends_on("A", "B")

    def test_remove_dependency(self):
        builder = WorkflowBuilder("test")
        builder.add_step("A", "analysis") \
               .add_step("B", "execute") \
               .depends_on("B", "A")

        builder.remove_dependency("B", "A")
        task_b = builder.get_task_by_name("B")
        assert task_b.depends_on == []

    # ── Build ────────────────────────────────────────────────

    def test_build_simple(self):
        builder = WorkflowBuilder("test", version="2.0.0")
        builder.add_step("A", "analysis") \
               .add_step("B", "execute") \
               .depends_on("B", "A")

        wf = builder.build()
        assert isinstance(wf, WorkflowDefinition)
        assert wf.name == "test"
        assert wf.version == "2.0.0"
        assert len(wf.tasks) == 2
        assert wf.is_valid()

    def test_build_with_cycle_raises(self):
        builder = WorkflowBuilder("test")
        t1 = builder.add_step("A", "analysis")
        t2 = builder.add_step("B", "execute")

        # Manually create cycle
        task_a = builder.get_task_by_name("A")
        task_b = builder.get_task_by_name("B")
        task_a.depends_on.append(task_b.task_id)
        task_b.depends_on.append(task_a.task_id)

        with pytest.raises(ValueError, match="circular"):
            builder.build()

    def test_build_unchecked(self):
        builder = WorkflowBuilder("test")
        t1 = builder.add_step("A", "analysis")
        t2 = builder.add_step("B", "execute")

        task_a = builder.get_task_by_name("A")
        task_b = builder.get_task_by_name("B")
        task_a.depends_on.append(task_b.task_id)
        task_b.depends_on.append(task_a.task_id)

        # build_unchecked 跳过验证
        wf = builder.build_unchecked()
        assert wf._has_cycle() is True

    def test_build_empty_raises(self):
        builder = WorkflowBuilder("test")
        with pytest.raises(ValueError, match="no tasks"):
            builder.build()

    def test_build_with_metadata(self):
        builder = WorkflowBuilder("test", metadata={"owner": "growth_team"})
        builder.add_step("A", "analysis")
        wf = builder.build()
        assert wf.metadata["owner"] == "growth_team"

    # ── Complex Chain ────────────────────────────────────────

    def test_build_complex_chain(self):
        builder = WorkflowBuilder("complex")
        builder.add_step("Init", "init") \
               .add_step("Stage1", "s1") \
               .add_step("Stage2", "s2") \
               .add_step("Stage3", "s3") \
               .add_step("Final", "final") \
               .depends_on("Stage1", "Init") \
               .depends_on("Stage2", "Stage1") \
               .depends_on("Stage3", "Stage2") \
               .depends_on("Final", "Stage3")

        wf = builder.build()
        assert wf.is_valid()
        layers = wf.topological_order()
        assert len(layers) == 5

    def test_build_parallel_fan_out(self):
        builder = WorkflowBuilder("parallel")
        builder.add_step("A", "analysis") \
               .add_step("B", "b") \
               .add_step("C", "c") \
               .add_step("D", "d") \
               .depends_on("B", "A") \
               .depends_on("C", "A") \
               .depends_on("D", "A")

        wf = builder.build()
        layers = wf.topological_order()
        assert len(layers) == 2
        assert len(layers[1]) == 3  # B, C, D parallel

    def test_build_parallel_fan_in(self):
        builder = WorkflowBuilder("fan_in")
        builder.add_step("A", "a") \
               .add_step("B", "b") \
               .add_step("C", "c") \
               .add_step("D", "d") \
               .depends_on("D", "A") \
               .depends_on("D", "B") \
               .depends_on("D", "C")

        wf = builder.build()
        layers = wf.topological_order()
        assert len(layers) == 2
        assert len(layers[0]) == 3  # A, B, C parallel
        assert len(layers[1]) == 1  # D


class TestPresetWorkflows:
    """预设 Workflow 工厂函数测试."""

    def test_campaign_optimization(self):
        wf = create_campaign_optimization_workflow()
        assert wf.is_valid()
        assert len(wf.tasks) == 5
        assert wf.name == "Campaign Budget Optimization"

        # 验证拓扑顺序
        names = [t.name for t in wf.flat_topological_order()]
        assert names.index("Analyze Campaign") < names.index("Generate Recommendation")
        assert names.index("Generate Recommendation") < names.index("Human Approval")
        assert names.index("Human Approval") < names.index("Update Budget")
        assert names.index("Update Budget") < names.index("Observe Result")

        # 验证审批任务
        approve = wf.get_task_by_name("Human Approval")
        assert approve.requires_approval is True

    def test_creative_refresh(self):
        wf = create_creative_refresh_workflow()
        assert wf.is_valid()
        assert len(wf.tasks) == 5
        assert wf.name == "Creative Refresh"

        names = [t.name for t in wf.flat_topological_order()]
        assert names.index("Detect Fatigue") < names.index("Generate Creative")

    def test_growth_recovery(self):
        wf = create_growth_recovery_workflow()
        assert wf.is_valid()
        assert len(wf.tasks) == 8
        assert wf.name == "Growth Recovery"

        names = [t.name for t in wf.flat_topological_order()]
        assert names.index("Analyze Adjust Data") < names.index("Detect Fatigue")
        assert names.index("Detect Fatigue") < names.index("Mutate Creative")
        assert names.index("Mutate Creative") < names.index("Human Approval")
        assert names.index("Upload to Meta") < names.index("Launch Test Campaign")
        assert names.index("Observe D7 Revenue") < names.index("Store Learning")

        # 验证审批
        approve = wf.get_task_by_name("Human Approval")
        assert approve.requires_approval is True

        # 验证重试
        upload = wf.get_task_by_name("Upload to Meta")
        assert upload.retry_count == 3

    def test_preset_workflows_are_valid(self):
        """所有预设 Workflow 必须通过验证."""
        wfs = [
            create_campaign_optimization_workflow(),
            create_creative_refresh_workflow(),
            create_growth_recovery_workflow(),
        ]
        for wf in wfs:
            assert wf.is_valid(), f"{wf.name} is invalid"
            assert len(wf.get_entry_tasks()) == 1, f"{wf.name} should have 1 entry task"
            assert len(wf.get_exit_tasks()) == 1, f"{wf.name} should have 1 exit task"