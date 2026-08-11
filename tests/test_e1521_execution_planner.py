"""E15.2.1 Execution Planner 测试 — 执行规划器完整测试.

测试覆盖:
  - Plan生成 (15 tests)
  - Template选择 (15 tests)
  - Task生成 (15 tests)
  - Rule验证 (15 tests)
  - Pattern Memory调用 (10 tests)
  - 异常Action处理 (10 tests)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from market_ops.creative_vision_runtime.growth_runtime.workflow.models import (
    WorkflowDefinition,
    WorkflowTask,
)
from market_ops.creative_vision_runtime.growth_runtime.workflow.planner.models import (
    ExecutionPlan,
    PlanStatus,
    PlanningTask,
    RiskLevel,
    WorkflowType,
)
from market_ops.creative_vision_runtime.growth_runtime.workflow.planner.planning_rules import (
    PlanningRule,
    SafetyValidator,
)
from market_ops.creative_vision_runtime.growth_runtime.workflow.planner.task_generator import (
    TaskGenerator,
)
from market_ops.creative_vision_runtime.growth_runtime.workflow.planner.workflow_template import (
    TemplateRegistry,
    WorkflowTemplate,
)
from market_ops.creative_vision_runtime.growth_runtime.workflow.planner.execution_planner import (
    ExecutionPlanner,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


def _make_opportunity(action_type="increase_budget", confidence=0.85, **kwargs):
    """创建模拟 GrowthOpportunity."""
    opp = MagicMock()
    opp.opportunity_id = kwargs.get("opportunity_id", "opp_001")
    opp.action = action_type
    opp.action_type = action_type
    opp.confidence = confidence
    opp.severity = kwargs.get("severity", "medium")
    opp.product_id = kwargs.get("product_id", "game_123")
    opp.creative_id = kwargs.get("creative_id", "creative_456")
    opp.budget_multiplier = kwargs.get("budget_multiplier", 1.2)
    opp.target_budget = kwargs.get("target_budget", 1200)
    opp.current_budget = kwargs.get("current_budget", 1000)
    return opp


def _make_pattern_store(with_pattern=True):
    """创建模拟 PatternMemory."""
    store = MagicMock()
    if with_pattern:
        store.enhance_decision.return_value = {
            "matched_pattern": True,
            "pattern_score": 0.88,
            "historical_success_rate": 0.78,
            "enhanced_confidence": 0.90,
        }
    else:
        store.enhance_decision.return_value = {}
    return store


# ═══════════════════════════════════════════════════════════════
# Test: ExecutionPlan 模型
# ═══════════════════════════════════════════════════════════════


class TestExecutionPlan:
    """ExecutionPlan 模型测试 (Plan生成)."""

    def test_create_default_plan(self):
        """创建默认 ExecutionPlan."""
        plan = ExecutionPlan()
        assert plan.plan_id != ""
        assert plan.workflow_type == WorkflowType.CUSTOM
        assert plan.risk_level == RiskLevel.LOW
        assert plan.status == PlanStatus.DRAFT
        assert plan.confidence == 0.0
        assert plan.tasks == []

    def test_create_plan_with_tasks(self):
        """创建包含任务的 ExecutionPlan."""
        tasks = [
            PlanningTask(name="Task A", action_type="analyze", adapter="meta_ads"),
            PlanningTask(name="Task B", action_type="execute", adapter="meta_ads"),
        ]
        plan = ExecutionPlan(
            action_type="increase_budget",
            workflow_type=WorkflowType.BUDGET_OPTIMIZE,
            template_name="budget_optimize",
            tasks=tasks,
            confidence=0.85,
            risk_level=RiskLevel.MEDIUM,
            required_approval=True,
        )
        assert plan.task_count == 2
        assert plan.action_type == "increase_budget"
        assert plan.workflow_type == WorkflowType.BUDGET_OPTIMIZE
        assert plan.required_approval is True

    def test_plan_is_valid_when_no_errors(self):
        """无验证错误时 plan.is_valid = True."""
        plan = ExecutionPlan(validation_errors=[])
        assert plan.is_valid is True

    def test_plan_is_valid_when_has_errors(self):
        """有验证错误时 plan.is_valid = False."""
        plan = ExecutionPlan(validation_errors=["Confidence too low"])
        assert plan.is_valid is False

    def test_plan_is_approved(self):
        """计划审批状态."""
        plan = ExecutionPlan(status=PlanStatus.APPROVED)
        assert plan.is_approved is True

        plan2 = ExecutionPlan(status=PlanStatus.VALIDATED)
        assert plan2.is_approved is False

    def test_get_tasks_by_phase(self):
        """按 phase 获取任务."""
        tasks = [
            PlanningTask(name="Prepare", phase="prepare", order=0),
            PlanningTask(name="Execute", phase="execute", order=1),
            PlanningTask(name="Monitor", phase="monitor", order=2),
        ]
        plan = ExecutionPlan(tasks=tasks)
        assert len(plan.get_tasks_by_phase("prepare")) == 1
        assert len(plan.get_tasks_by_phase("execute")) == 1
        assert len(plan.get_tasks_by_phase("monitor")) == 1
        assert len(plan.get_tasks_by_phase("rollback")) == 0

    def test_plan_to_dict(self):
        """序列化为 dict."""
        plan = ExecutionPlan(
            plan_id="p1",
            action_type="scale",
            workflow_type=WorkflowType.CAMPAIGN_SCALE,
            confidence=0.9,
            risk_level=RiskLevel.HIGH,
            pattern_boost=True,
            pattern_score=0.85,
        )
        d = plan.to_dict()
        assert d["plan_id"] == "p1"
        assert d["action_type"] == "scale"
        assert d["workflow_type"] == "campaign_scale"
        assert d["risk_level"] == "high"
        assert d["pattern_boost"] is True
        assert d["pattern_score"] == 0.85
        assert "tasks" in d

    def test_plan_from_dict(self):
        """从 dict 反序列化."""
        d = {
            "plan_id": "p1",
            "action_type": "scale",
            "workflow_type": "campaign_scale",
            "risk_level": "high",
            "confidence": 0.9,
            "tasks": [
                {"name": "Task A", "action_type": "analyze", "adapter": "meta_ads"},
            ],
        }
        plan = ExecutionPlan.from_dict(d)
        assert plan.plan_id == "p1"
        assert plan.action_type == "scale"
        assert plan.workflow_type == WorkflowType.CAMPAIGN_SCALE
        assert plan.risk_level == RiskLevel.HIGH
        assert plan.task_count == 1

    def test_plan_default_created_at(self):
        """默认创建时间."""
        plan = ExecutionPlan()
        assert plan.created_at != ""

    def test_plan_with_warnings(self):
        """计划包含警告信息."""
        plan = ExecutionPlan(
            warnings=["Low confidence", "No template guardrails"],
        )
        assert len(plan.warnings) == 2
        assert "Low confidence" in plan.warnings

    def test_plan_with_context(self):
        """计划包含执行上下文."""
        plan = ExecutionPlan(
            context={"campaign_id": "123", "budget": 1000},
        )
        assert plan.context["campaign_id"] == "123"
        assert plan.context["budget"] == 1000

    def test_plan_metadata(self):
        """计划扩展元数据."""
        plan = ExecutionPlan(
            metadata={"priority": "high", "source": "auto"},
        )
        assert plan.metadata["priority"] == "high"

    def test_plan_status_lifecycle(self):
        """计划状态生命周期."""
        plan = ExecutionPlan()
        assert plan.status == PlanStatus.DRAFT
        plan.status = PlanStatus.VALIDATED
        assert plan.status == PlanStatus.VALIDATED
        plan.status = PlanStatus.APPROVED
        assert plan.status == PlanStatus.APPROVED
        plan.status = PlanStatus.EXECUTING
        assert plan.status == PlanStatus.EXECUTING
        plan.status = PlanStatus.COMPLETED
        assert plan.status == PlanStatus.COMPLETED

    def test_plan_all_workflow_types(self):
        """所有 WorkflowType 枚举值."""
        for wt in WorkflowType:
            plan = ExecutionPlan(workflow_type=wt)
            assert plan.workflow_type == wt

    def test_plan_all_risk_levels(self):
        """所有 RiskLevel 枚举值."""
        for rl in RiskLevel:
            plan = ExecutionPlan(risk_level=rl)
            assert plan.risk_level == rl


# ═══════════════════════════════════════════════════════════════
# Test: PlanningTask 模型
# ═══════════════════════════════════════════════════════════════


class TestPlanningTask:
    """PlanningTask 模型测试."""

    def test_create_default_task(self):
        """创建默认 PlanningTask."""
        task = PlanningTask()
        assert task.task_id != ""
        assert task.name == ""
        assert task.adapter == ""
        assert task.phase == "execute"
        assert task.order == 0

    def test_create_task_with_deps(self):
        """创建带依赖的任务."""
        task = PlanningTask(
            name="Upload",
            action_type="upload_creative",
            adapter="meta_ads",
            depends_on=["generate_001", "validate_001"],
            requires_approval=True,
            timeout_ms=30000,
            retry_count=2,
        )
        assert len(task.depends_on) == 2
        assert task.requires_approval is True
        assert task.timeout_ms == 30000
        assert task.retry_count == 2

    def test_task_parameters(self):
        """任务参数."""
        task = PlanningTask(
            name="Scale",
            parameters={"old_budget": 100, "new_budget": 150},
        )
        assert task.parameters["old_budget"] == 100
        assert task.parameters["new_budget"] == 150

    def test_task_to_dict(self):
        """任务序列化."""
        task = PlanningTask(
            task_id="t1",
            name="Execute",
            action_type="update_budget",
            adapter="meta_ads",
            phase="execute",
            order=1,
        )
        d = task.to_dict()
        assert d["task_id"] == "t1"
        assert d["name"] == "Execute"
        assert d["adapter"] == "meta_ads"
        assert d["phase"] == "execute"

    def test_task_from_dict(self):
        """任务反序列化."""
        d = {"task_id": "t1", "name": "Execute", "action_type": "update_budget", "adapter": "meta_ads"}
        task = PlanningTask.from_dict(d)
        assert task.task_id == "t1"
        assert task.name == "Execute"
        assert task.adapter == "meta_ads"

    def test_task_metadata(self):
        """任务元数据."""
        task = PlanningTask(
            name="Monitor",
            metadata={"expected_duration": "24h", "alert_threshold": 0.5},
        )
        assert task.metadata["expected_duration"] == "24h"


# ═══════════════════════════════════════════════════════════════
# Test: WorkflowTemplate 模板
# ═══════════════════════════════════════════════════════════════


class TestWorkflowTemplate:
    """WorkflowTemplate 模板测试."""

    def test_create_template(self):
        """创建模板."""
        template = WorkflowTemplate(
            name="test_template",
            workflow_type=WorkflowType.CUSTOM,
            action_type="test_action",
            description="A test template",
            risk_level=RiskLevel.LOW,
        )
        assert template.name == "test_template"
        assert template.workflow_type == WorkflowType.CUSTOM
        assert template.action_type == "test_action"
        assert template.risk_level == RiskLevel.LOW
        assert template.requires_approval is False

    def test_expand_empty_template(self):
        """空模板展开."""
        template = WorkflowTemplate(name="empty", task_definitions=[])
        tasks = template.expand()
        assert tasks == []

    def test_expand_single_task(self):
        """单任务模板展开."""
        template = WorkflowTemplate(
            name="single",
            task_definitions=[
                {"name": "Only Task", "action_type": "monitor", "adapter": "adjust", "phase": "monitor"},
            ],
        )
        tasks = template.expand()
        assert len(tasks) == 1
        assert tasks[0].name == "Only Task"
        assert tasks[0].adapter == "adjust"

    def test_expand_multi_task(self):
        """多任务模板展开."""
        template = WorkflowTemplate(
            name="multi",
            task_definitions=[
                {"name": "Task 1", "phase": "prepare"},
                {"name": "Task 2", "phase": "execute"},
                {"name": "Task 3", "phase": "monitor"},
            ],
        )
        tasks = template.expand()
        assert len(tasks) == 3
        assert tasks[0].name == "Task 1"
        assert tasks[1].name == "Task 2"
        assert tasks[2].name == "Task 3"

    def test_expand_with_context_params(self):
        """模板展开时合并上下文参数."""
        template = WorkflowTemplate(
            name="with_params",
            task_definitions=[
                {"name": "Task", "parameters": {"base": 100}, "phase": "execute"},
            ],
        )
        tasks = template.expand({"params": {"campaign_id": "123"}})
        assert tasks[0].parameters["base"] == 100
        assert tasks[0].parameters["campaign_id"] == "123"

    def test_expand_with_dependencies(self):
        """模板展开保留依赖关系."""
        template = WorkflowTemplate(
            name="with_deps",
            task_definitions=[
                {"name": "Task 1", "phase": "prepare"},
                {"name": "Task 2", "phase": "execute", "depends_on": ["task_1"]},
                {"name": "Task 3", "phase": "execute", "depends_on": ["task_2"]},
            ],
        )
        tasks = template.expand()
        assert len(tasks[1].depends_on) == 1
        assert "task_1" in tasks[1].depends_on
        assert len(tasks[2].depends_on) == 1
        assert "task_2" in tasks[2].depends_on

    def test_expand_task_order(self):
        """模板展开后任务 order 递增."""
        template = WorkflowTemplate(
            name="ordered",
            task_definitions=[
                {"name": "A", "phase": "prepare"},
                {"name": "B", "phase": "execute"},
                {"name": "C", "phase": "monitor"},
            ],
        )
        tasks = template.expand()
        assert tasks[0].order == 0
        assert tasks[1].order == 1
        assert tasks[2].order == 2

    def test_template_default_values(self):
        """模板默认值."""
        template = WorkflowTemplate()
        assert template.name == ""
        assert template.workflow_type == WorkflowType.CUSTOM
        assert template.action_type == ""
        assert template.min_confidence == 0.5
        assert template.max_budget_change == 0.0

    def test_template_to_dict(self):
        """模板序列化."""
        template = WorkflowTemplate(
            name="test",
            workflow_type=WorkflowType.BUDGET_OPTIMIZE,
            action_type="increase_budget",
            risk_level=RiskLevel.MEDIUM,
            requires_approval=True,
            max_budget_change=0.3,
        )
        d = template.to_dict()
        assert d["name"] == "test"
        assert d["workflow_type"] == "budget_optimize"
        assert d["max_budget_change"] == 0.3

    def test_template_with_metadata(self):
        """模板元数据."""
        template = WorkflowTemplate(
            name="meta",
            metadata={"version": "2.0", "author": "system"},
        )
        assert template.metadata["version"] == "2.0"


# ═══════════════════════════════════════════════════════════════
# Test: TemplateRegistry 模板注册中心
# ═══════════════════════════════════════════════════════════════


class TestTemplateRegistry:
    """TemplateRegistry 模板注册中心测试."""

    def test_create_registry_has_builtins(self):
        """创建注册中心自动注册内置模板."""
        registry = TemplateRegistry()
        assert registry.count >= 6

    def test_get_builtin_creative_refresh(self):
        """获取内置 creative_refresh 模板."""
        registry = TemplateRegistry()
        template = registry.get("creative_refresh")
        assert template is not None
        assert template.action_type == "replace_creative"
        assert template.workflow_type == WorkflowType.CREATIVE_REFRESH

    def test_get_builtin_budget_optimize(self):
        """获取内置 budget_optimize 模板."""
        registry = TemplateRegistry()
        template = registry.get("budget_optimize")
        assert template is not None
        assert template.action_type == "increase_budget"
        assert template.requires_approval is True
        assert template.risk_level == RiskLevel.MEDIUM

    def test_get_builtin_campaign_pause(self):
        """获取内置 campaign_pause 模板."""
        registry = TemplateRegistry()
        template = registry.get("campaign_pause")
        assert template is not None
        assert template.action_type == "pause_campaign"
        assert template.risk_level == RiskLevel.CRITICAL

    def test_get_builtin_campaign_scale(self):
        """获取内置 campaign_scale 模板."""
        registry = TemplateRegistry()
        template = registry.get("campaign_scale")
        assert template is not None
        assert template.action_type == "scale"
        assert template.max_budget_change == 0.5

    def test_get_builtin_audience_expand(self):
        """获取内置 audience_expand 模板."""
        registry = TemplateRegistry()
        template = registry.get("audience_expand")
        assert template is not None
        assert template.action_type == "expand_targeting"

    def test_get_builtin_revenue_optimize(self):
        """获取内置 revenue_optimize 模板."""
        registry = TemplateRegistry()
        template = registry.get("revenue_optimize")
        assert template is not None
        assert template.action_type == "optimize_pricing"

    def test_get_nonexistent(self):
        """获取不存在的模板返回 None."""
        registry = TemplateRegistry()
        assert registry.get("nonexistent") is None

    def test_register_custom_template(self):
        """注册自定义模板."""
        registry = TemplateRegistry()
        template = WorkflowTemplate(
            name="custom_test",
            action_type="custom_action",
            workflow_type=WorkflowType.CUSTOM,
        )
        registry.register(template)
        assert registry.get("custom_test") is template
        assert registry.get_best_match("custom_action") is template

    def test_unregister_template(self):
        """注销模板."""
        registry = TemplateRegistry()
        template = WorkflowTemplate(
            name="to_remove",
            action_type="remove_me",
        )
        registry.register(template)
        assert registry.unregister("to_remove") is True
        assert registry.get("to_remove") is None

    def test_unregister_nonexistent(self):
        """注销不存在的模板."""
        registry = TemplateRegistry()
        assert registry.unregister("nonexistent") is False

    def test_get_by_action(self):
        """按 Action 类型获取模板."""
        registry = TemplateRegistry()
        templates = registry.get_by_action("increase_budget")
        assert len(templates) >= 1
        assert templates[0].name == "budget_optimize"

    def test_get_by_workflow_type(self):
        """按 WorkflowType 获取模板."""
        registry = TemplateRegistry()
        template = registry.get_by_workflow_type(WorkflowType.CAMPAIGN_PAUSE)
        assert template is not None
        assert template.name == "campaign_pause"

    def test_list_all(self):
        """列出所有模板."""
        registry = TemplateRegistry()
        all_templates = registry.list_all()
        assert len(all_templates) >= 6
        names = {t.name for t in all_templates}
        assert "creative_refresh" in names
        assert "budget_optimize" in names

    def test_list_action_types(self):
        """列出所有 Action 类型."""
        registry = TemplateRegistry()
        action_types = registry.list_action_types()
        assert "replace_creative" in action_types
        assert "increase_budget" in action_types
        assert "pause_campaign" in action_types


# ═══════════════════════════════════════════════════════════════
# Test: TaskGenerator 任务生成器
# ═══════════════════════════════════════════════════════════════


class TestTaskGenerator:
    """TaskGenerator 任务生成器测试."""

    def test_create_generator(self):
        """创建生成器."""
        gen = TaskGenerator()
        assert gen is not None

    def test_generate_from_template(self):
        """从模板生成任务."""
        registry = TemplateRegistry()
        gen = TaskGenerator(registry)
        template = registry.get("creative_refresh")
        tasks = gen.generate(template)
        assert len(tasks) == 5
        assert tasks[0].name == "Generate Creative"

    def test_generate_resolves_dependencies(self):
        """生成任务正确解析依赖."""
        registry = TemplateRegistry()
        gen = TaskGenerator(registry)
        template = registry.get("creative_refresh")
        tasks = gen.generate(template)

        # task_2 (Validate Asset) depends on task_1 (Generate Creative)
        validate_task = tasks[1]
        generate_task = tasks[0]
        assert generate_task.task_id in validate_task.depends_on

    def test_generate_with_context(self):
        """生成任务时传入上下文."""
        registry = TemplateRegistry()
        gen = TaskGenerator(registry)
        template = registry.get("budget_optimize")
        tasks = gen.generate(template, {"campaign_id": "123", "params": {"budget": 200}})
        assert len(tasks) == 5

    def test_generate_tasks_are_ordered(self):
        """生成任务按 order 排序."""
        registry = TemplateRegistry()
        gen = TaskGenerator(registry)
        template = registry.get("creative_refresh")
        tasks = gen.generate(template)
        for i in range(len(tasks) - 1):
            assert tasks[i].order <= tasks[i + 1].order

    def test_generate_by_action(self):
        """按 Action 类型生成任务."""
        gen = TaskGenerator()
        tasks = gen.generate_by_action("replace_creative")
        assert tasks is not None
        assert len(tasks) == 5

    def test_generate_by_action_unknown(self):
        """未知 Action 类型返回 None."""
        gen = TaskGenerator()
        tasks = gen.generate_by_action("unknown_action")
        assert tasks is None

    def test_generate_by_workflow_type(self):
        """按 WorkflowType 生成任务."""
        gen = TaskGenerator()
        tasks = gen.generate_by_workflow_type(WorkflowType.CAMPAIGN_PAUSE)
        assert tasks is not None
        assert len(tasks) == 4

    def test_generate_by_workflow_type_unknown(self):
        """未知 WorkflowType 返回 None."""
        gen = TaskGenerator()
        tasks = gen.generate_by_workflow_type(WorkflowType.MONITOR_ONLY)
        assert tasks is None

    def test_get_supported_actions(self):
        """获取支持的 Action 列表."""
        gen = TaskGenerator()
        actions = gen.get_supported_actions()
        assert "replace_creative" in actions
        assert "increase_budget" in actions

    def test_supports_action(self):
        """检查 Action 是否支持."""
        gen = TaskGenerator()
        assert gen.supports_action("replace_creative") is True
        assert gen.supports_action("unknown") is False

    def test_generate_each_template_has_tasks(self):
        """每个内置模板展开后都有任务."""
        registry = TemplateRegistry()
        gen = TaskGenerator(registry)
        for template in registry.list_all():
            tasks = gen.generate(template)
            assert len(tasks) > 0, f"Template {template.name} should have tasks"

    def test_generate_budget_optimize_has_rollback(self):
        """预算优化模板包含 rollback 任务."""
        gen = TaskGenerator()
        tasks = gen.generate_by_action("increase_budget")
        rollback_tasks = [t for t in tasks if t.phase == "rollback"]
        assert len(rollback_tasks) == 1
        assert rollback_tasks[0].name == "Rollback if Failed"

    def test_generate_campaign_pause_has_audit(self):
        """暂停模板包含审计记录任务."""
        gen = TaskGenerator()
        tasks = gen.generate_by_action("pause_campaign")
        audit_tasks = [t for t in tasks if t.action_type == "record_audit"]
        assert len(audit_tasks) == 1

    def test_generate_task_has_unique_ids(self):
        """每个生成的任务都有唯一 ID."""
        gen = TaskGenerator()
        tasks = gen.generate_by_action("replace_creative")
        ids = {t.task_id for t in tasks}
        assert len(ids) == len(tasks)


# ═══════════════════════════════════════════════════════════════
# Test: PlanningRule 安全规则
# ═══════════════════════════════════════════════════════════════


class TestPlanningRule:
    """PlanningRule 安全规则测试."""

    def test_create_rule(self):
        """创建规则."""
        rule = PlanningRule(
            rule_id="r1",
            action_type="increase_budget",
            max_budget_change=0.3,
            min_confidence=0.7,
        )
        assert rule.rule_id == "r1"
        assert rule.action_type == "increase_budget"
        assert rule.max_budget_change == 0.3
        assert rule.forbidden is False

    def test_validate_pass(self):
        """规则验证通过."""
        rule = PlanningRule(
            rule_id="r1",
            action_type="increase_budget",
            max_budget_change=0.3,
            min_confidence=0.7,
        )
        plan = ExecutionPlan(
            action_type="increase_budget",
            confidence=0.85,
            context={"budget_multiplier": 1.2},
        )
        errors = rule.validate(plan)
        assert errors == []

    def test_validate_confidence_too_low(self):
        """置信度低于阈值."""
        rule = PlanningRule(
            rule_id="r1",
            action_type="increase_budget",
            min_confidence=0.7,
        )
        plan = ExecutionPlan(
            action_type="increase_budget",
            confidence=0.5,
        )
        errors = rule.validate(plan)
        assert len(errors) >= 1
        assert any("Confidence" in e for e in errors)

    def test_validate_budget_exceeds_limit(self):
        """预算变化超过限制."""
        rule = PlanningRule(
            rule_id="r1",
            action_type="increase_budget",
            max_budget_change=0.3,
        )
        plan = ExecutionPlan(
            action_type="increase_budget",
            context={"budget_multiplier": 1.5},
        )
        errors = rule.validate(plan)
        assert len(errors) >= 1
        assert any("exceeds" in e or "Budget" in e for e in errors)

    def test_validate_budget_at_limit(self):
        """预算变化刚好在限制内."""
        rule = PlanningRule(
            rule_id="r1",
            action_type="increase_budget",
            max_budget_change=0.3,
        )
        plan = ExecutionPlan(
            action_type="increase_budget",
            confidence=0.85,
            context={"budget_multiplier": 1.3},
        )
        errors = rule.validate(plan)
        # 1.3 == 1 + 0.3, not > so should pass
        assert errors == []

    def test_validate_forbidden_action(self):
        """禁止的 Action."""
        rule = PlanningRule(
            rule_id="r1",
            action_type="dangerous_action",
            forbidden=True,
        )
        plan = ExecutionPlan(action_type="dangerous_action")
        errors = rule.validate(plan)
        assert len(errors) >= 1
        assert any("forbidden" in e for e in errors)

    def test_validate_require_approval_missing(self):
        """缺少强制审批."""
        rule = PlanningRule(
            rule_id="r1",
            action_type="increase_budget",
            require_approval=True,
        )
        plan = ExecutionPlan(
            action_type="increase_budget",
            required_approval=False,
            confidence=0.85,
        )
        errors = rule.validate(plan)
        assert len(errors) >= 1
        assert any("approval" in e.lower() for e in errors)

    def test_validate_require_approval_present(self):
        """审批已设置."""
        rule = PlanningRule(
            rule_id="r1",
            action_type="increase_budget",
            require_approval=True,
        )
        plan = ExecutionPlan(
            action_type="increase_budget",
            required_approval=True,
            confidence=0.85,
        )
        errors = rule.validate(plan)
        assert errors == []

    def test_validate_missing_required_adapters(self):
        """缺少必需的适配器."""
        rule = PlanningRule(
            rule_id="r1",
            action_type="test",
            required_adapters=["meta_ads", "adjust"],
        )
        plan = ExecutionPlan(
            action_type="test",
            tasks=[PlanningTask(adapter="meta_ads")],
        )
        errors = rule.validate(plan)
        assert len(errors) >= 1
        assert any("Missing required adapters" in e for e in errors)

    def test_validate_all_required_adapters_present(self):
        """所有必需适配器都存在."""
        rule = PlanningRule(
            rule_id="r1",
            action_type="test",
            required_adapters=["meta_ads", "adjust"],
        )
        plan = ExecutionPlan(
            action_type="test",
            confidence=0.85,
            tasks=[
                PlanningTask(adapter="meta_ads"),
                PlanningTask(adapter="adjust"),
            ],
        )
        errors = rule.validate(plan)
        assert errors == []

    def test_rule_to_dict(self):
        """规则序列化."""
        rule = PlanningRule(
            rule_id="r1",
            action_type="test",
            max_budget_change=0.5,
            require_approval=True,
            min_confidence=0.8,
        )
        d = rule.to_dict()
        assert d["rule_id"] == "r1"
        assert d["action_type"] == "test"
        assert d["max_budget_change"] == 0.5
        assert d["require_approval"] is True

    def test_rule_max_daily_actions(self):
        """每日最大执行次数."""
        rule = PlanningRule(
            rule_id="r1",
            action_type="test",
            max_daily_actions=5,
        )
        assert rule.max_daily_actions == 5

    def test_rule_check_params(self):
        """参数校验."""
        rule = PlanningRule(
            rule_id="r1",
            action_type="test",
            check_params={"min_budget": 100},
        )
        assert rule.check_params["min_budget"] == 100

    def test_rule_metadata(self):
        """规则元数据."""
        rule = PlanningRule(
            rule_id="r1",
            action_type="test",
            metadata={"severity": "critical"},
        )
        assert rule.metadata["severity"] == "critical"


# ═══════════════════════════════════════════════════════════════
# Test: SafetyValidator 安全验证器
# ═══════════════════════════════════════════════════════════════


class TestSafetyValidator:
    """SafetyValidator 安全验证器测试."""

    def test_create_validator(self):
        """创建验证器."""
        validator = SafetyValidator()
        assert validator.rule_count >= 5

    def test_validate_safe_plan(self):
        """验证安全计划."""
        validator = SafetyValidator()
        plan = ExecutionPlan(
            action_type="increase_budget",
            confidence=0.85,
            required_approval=True,
            context={"budget_multiplier": 1.2},
        )
        assert validator.is_safe(plan) is True

    def test_validate_unsafe_plan(self):
        """验证不安全计划."""
        validator = SafetyValidator()
        plan = ExecutionPlan(
            action_type="increase_budget",
            confidence=0.4,  # < 0.7
            required_approval=False,  # 需要审批
        )
        assert validator.is_safe(plan) is False

    def test_validate_pause_campaign(self):
        """验证暂停计划 (不需要审批)."""
        validator = SafetyValidator()
        plan = ExecutionPlan(
            action_type="pause_campaign",
            confidence=0.75,
        )
        assert validator.is_safe(plan) is True

    def test_validate_scale_with_high_confidence(self):
        """验证高置信度放量计划."""
        validator = SafetyValidator()
        plan = ExecutionPlan(
            action_type="scale",
            confidence=0.9,
            required_approval=True,
            context={"budget_multiplier": 1.4},
        )
        assert validator.is_safe(plan) is True

    def test_validate_scale_budget_exceeds(self):
        """验证放量预算超限."""
        validator = SafetyValidator()
        plan = ExecutionPlan(
            action_type="scale",
            confidence=0.9,
            required_approval=True,
            context={"budget_multiplier": 1.6},  # > 1.5
        )
        assert validator.is_safe(plan) is False

    def test_validate_with_warnings(self):
        """验证并返回警告."""
        validator = SafetyValidator()
        plan = ExecutionPlan(
            action_type="increase_budget",
            confidence=0.85,
            required_approval=True,
            risk_level=RiskLevel.HIGH,
            context={"budget_multiplier": 1.2},
        )
        errors, warnings = validator.validate_with_warnings(plan)
        assert errors == []
        assert len(warnings) >= 1  # HIGH risk warning

    def test_validate_with_warnings_low_confidence(self):
        """低置信度警告."""
        validator = SafetyValidator()
        plan = ExecutionPlan(
            action_type="replace_creative",
            confidence=0.55,
        )
        _, warnings = validator.validate_with_warnings(plan)
        assert any("Low confidence" in w for w in warnings)

    def test_validate_with_warnings_custom_workflow(self):
        """自定义 Workflow 警告."""
        validator = SafetyValidator()
        plan = ExecutionPlan(
            action_type="increase_budget",
            confidence=0.85,
            required_approval=True,
            workflow_type=WorkflowType.CUSTOM,
            context={"budget_multiplier": 1.2},
        )
        _, warnings = validator.validate_with_warnings(plan)
        assert any("custom" in w.lower() for w in warnings)

    def test_add_rule(self):
        """添加自定义规则."""
        validator = SafetyValidator()
        rule = PlanningRule(
            rule_id="custom_rule",
            action_type="custom_action",
            forbidden=True,
        )
        validator.add_rule(rule)
        assert validator.get_rule("custom_rule") is rule

    def test_remove_rule(self):
        """移除规则."""
        validator = SafetyValidator()
        validator.add_rule(PlanningRule(rule_id="to_remove", action_type="test"))
        assert validator.remove_rule("to_remove") is True
        assert validator.get_rule("to_remove") is None

    def test_remove_nonexistent_rule(self):
        """移除不存在的规则."""
        validator = SafetyValidator()
        assert validator.remove_rule("nonexistent") is False

    def test_get_rules_by_action(self):
        """按 Action 获取规则."""
        validator = SafetyValidator()
        rules = validator.get_rules_by_action("increase_budget")
        assert len(rules) >= 1
        assert rules[0].rule_id == "budget_increase_limit"

    def test_get_all_rules(self):
        """获取所有规则."""
        validator = SafetyValidator()
        all_rules = validator.get_all_rules()
        assert len(all_rules) >= 5

    def test_validate_unmatched_action_uses_wildcard(self):
        """无匹配规则时检查通配符规则."""
        validator = SafetyValidator()
        validator.add_rule(PlanningRule(
            rule_id="wildcard",
            action_type="*",
            min_confidence=0.5,
        ))
        plan = ExecutionPlan(
            action_type="unmatched_action",
            confidence=0.3,
        )
        errors = validator.validate(plan)
        assert len(errors) >= 1


# ═══════════════════════════════════════════════════════════════
# Test: ExecutionPlanner 主规划器
# ═══════════════════════════════════════════════════════════════


class TestExecutionPlanner:
    """ExecutionPlanner 主规划器测试."""

    def test_create_planner(self):
        """创建规划器."""
        planner = ExecutionPlanner()
        assert planner is not None
        assert len(planner.get_supported_actions()) >= 6

    def test_create_plan_from_opportunity(self):
        """从 Opportunity 创建计划."""
        planner = ExecutionPlanner()
        opp = _make_opportunity(action_type="increase_budget", confidence=0.85)
        plan = planner.create_plan(opp)
        assert plan.plan_id != ""
        assert plan.action_type == "increase_budget"
        assert plan.workflow_type == WorkflowType.BUDGET_OPTIMIZE
        assert plan.task_count == 5
        assert plan.status == PlanStatus.VALIDATED
        assert plan.required_approval is True

    def test_create_plan_creative_refresh(self):
        """创建素材刷新计划."""
        planner = ExecutionPlanner()
        opp = _make_opportunity(action_type="replace_creative", confidence=0.75, severity="low")
        plan = planner.create_plan(opp)
        assert plan.workflow_type == WorkflowType.CREATIVE_REFRESH
        assert plan.task_count == 5
        assert plan.risk_level == RiskLevel.LOW
        assert plan.required_approval is False

    def test_create_plan_campaign_pause(self):
        """创建暂停止损计划."""
        planner = ExecutionPlanner()
        opp = _make_opportunity(action_type="pause_campaign", confidence=0.8)
        plan = planner.create_plan(opp)
        assert plan.workflow_type == WorkflowType.CAMPAIGN_PAUSE
        assert plan.risk_level == RiskLevel.CRITICAL
        assert plan.required_approval is False

    def test_create_plan_scale(self):
        """创建放量计划."""
        planner = ExecutionPlanner()
        opp = _make_opportunity(action_type="scale", confidence=0.9, budget_multiplier=1.4)
        plan = planner.create_plan(opp)
        assert plan.workflow_type == WorkflowType.CAMPAIGN_SCALE
        assert plan.risk_level == RiskLevel.HIGH
        assert plan.required_approval is True

    def test_create_plan_audience_expand(self):
        """创建受众扩展计划."""
        planner = ExecutionPlanner()
        opp = _make_opportunity(action_type="expand_targeting", confidence=0.7)
        plan = planner.create_plan(opp)
        assert plan.workflow_type == WorkflowType.AUDIENCE_EXPAND

    def test_create_plan_revenue_optimize(self):
        """创建收入优化计划."""
        planner = ExecutionPlanner()
        opp = _make_opportunity(action_type="optimize_pricing", confidence=0.8)
        plan = planner.create_plan(opp)
        assert plan.workflow_type == WorkflowType.REVENUE_OPTIMIZE
        assert plan.required_approval is True

    def test_to_workflow_definition(self):
        """将计划转换为 WorkflowDefinition."""
        planner = ExecutionPlanner()
        opp = _make_opportunity(action_type="increase_budget", confidence=0.85)
        plan = planner.create_plan(opp)
        wf = planner.to_workflow_definition(plan)
        assert isinstance(wf, WorkflowDefinition)
        assert len(wf.tasks) == 5
        assert wf.is_valid()

    def test_to_workflow_definition_creative_refresh(self):
        """素材刷新计划转换."""
        planner = ExecutionPlanner()
        opp = _make_opportunity(action_type="replace_creative", confidence=0.75)
        plan = planner.create_plan(opp)
        wf = planner.to_workflow_definition(plan)
        assert isinstance(wf, WorkflowDefinition)
        assert len(wf.tasks) == 5
        assert wf.is_valid()

    def test_to_workflow_definition_campaign_pause(self):
        """暂停计划转换."""
        planner = ExecutionPlanner()
        opp = _make_opportunity(action_type="pause_campaign", confidence=0.8)
        plan = planner.create_plan(opp)
        wf = planner.to_workflow_definition(plan)
        assert isinstance(wf, WorkflowDefinition)
        assert wf.is_valid()

    def test_to_workflow_definition_has_metadata(self):
        """转换的 Workflow 包含元数据."""
        planner = ExecutionPlanner()
        opp = _make_opportunity(action_type="increase_budget", confidence=0.85)
        plan = planner.create_plan(opp)
        wf = planner.to_workflow_definition(plan)
        assert wf.metadata["plan_id"] == plan.plan_id
        assert wf.metadata["action_type"] == "increase_budget"

    def test_create_plan_from_action(self):
        """从 Action 类型直接创建计划."""
        planner = ExecutionPlanner()
        plan = planner.create_plan_from_action("increase_budget", confidence=0.85)
        assert plan.action_type == "increase_budget"
        assert plan.workflow_type == WorkflowType.BUDGET_OPTIMIZE
        assert plan.task_count == 5

    def test_create_plan_from_action_unknown(self):
        """未知 Action 创建计划."""
        planner = ExecutionPlanner()
        plan = planner.create_plan_from_action("unknown_action", confidence=0.5)
        assert plan.status == PlanStatus.REJECTED
        assert len(plan.validation_errors) >= 1

    def test_plan_history(self):
        """计划历史记录."""
        planner = ExecutionPlanner()
        opp = _make_opportunity(action_type="increase_budget", confidence=0.85)
        planner.create_plan(opp)
        planner.create_plan(opp)
        history = planner.get_plan_history()
        assert len(history) == 2

    def test_plan_history_limit(self):
        """计划历史限制."""
        planner = ExecutionPlanner()
        opp = _make_opportunity()
        for _ in range(5):
            planner.create_plan(opp)
        history = planner.get_plan_history(limit=3)
        assert len(history) == 3


# ═══════════════════════════════════════════════════════════════
# Test: Pattern Memory 集成
# ═══════════════════════════════════════════════════════════════


class TestPatternMemoryIntegration:
    """Pattern Memory 集成测试."""

    def test_planner_with_pattern_store(self):
        """带 Pattern Store 的规划器."""
        store = _make_pattern_store(with_pattern=True)
        planner = ExecutionPlanner(pattern_store=store)
        opp = _make_opportunity(action_type="increase_budget", confidence=0.85)
        plan = planner.create_plan(opp)
        assert plan.pattern_boost is True
        assert plan.pattern_score > 0
        assert plan.pattern_success_rate > 0

    def test_planner_without_pattern_store(self):
        """无 Pattern Store 的规划器."""
        planner = ExecutionPlanner(pattern_store=None)
        opp = _make_opportunity(action_type="increase_budget", confidence=0.85)
        plan = planner.create_plan(opp)
        assert plan.pattern_boost is False
        assert plan.pattern_score == 0.0
        assert plan.pattern_success_rate == 0.0

    def test_pattern_store_no_match(self):
        """Pattern Store 无匹配."""
        store = _make_pattern_store(with_pattern=False)
        planner = ExecutionPlanner(pattern_store=store)
        opp = _make_opportunity(action_type="increase_budget", confidence=0.85)
        plan = planner.create_plan(opp)
        assert plan.pattern_boost is False

    def test_pattern_store_enhances_confidence(self):
        """Pattern Store 提升置信度."""
        store = _make_pattern_store(with_pattern=True)
        planner = ExecutionPlanner(pattern_store=store)
        opp = _make_opportunity(action_type="increase_budget", confidence=0.85)
        plan = planner.create_plan(opp)
        assert plan.confidence >= 0.85

    def test_pattern_store_called_with_correct_params(self):
        """Pattern Store 被正确调用."""
        store = _make_pattern_store(with_pattern=True)
        planner = ExecutionPlanner(pattern_store=store)
        opp = _make_opportunity(action_type="increase_budget", confidence=0.85)
        planner.create_plan(opp)
        store.enhance_decision.assert_called_once()
        call_args = store.enhance_decision.call_args[1]
        assert call_args["opportunity_type"] == "increase_budget"

    def test_to_workflow_definition_includes_pattern_info(self):
        """转换的 Workflow 包含 Pattern 信息."""
        store = _make_pattern_store(with_pattern=True)
        planner = ExecutionPlanner(pattern_store=store)
        opp = _make_opportunity(action_type="increase_budget", confidence=0.85)
        plan = planner.create_plan(opp)
        wf = planner.to_workflow_definition(plan)
        assert wf.metadata["pattern_boost"] is True

    def test_get_template(self):
        """获取模板."""
        planner = ExecutionPlanner()
        template = planner.get_template("creative_refresh")
        assert template is not None
        assert template.name == "creative_refresh"

    def test_get_template_nonexistent(self):
        """获取不存在的模板."""
        planner = ExecutionPlanner()
        assert planner.get_template("nonexistent") is None

    def test_list_templates(self):
        """列出所有模板."""
        planner = ExecutionPlanner()
        templates = planner.list_templates()
        assert len(templates) >= 6

    def test_get_supported_actions(self):
        """获取支持的 Action."""
        planner = ExecutionPlanner()
        actions = planner.get_supported_actions()
        assert "replace_creative" in actions
        assert "increase_budget" in actions


# ═══════════════════════════════════════════════════════════════
# Test: 异常 / 边界情况
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """异常和边界情况测试."""

    def test_unknown_action_fallback(self):
        """未知 Action 返回回退计划."""
        planner = ExecutionPlanner()
        opp = _make_opportunity(action_type="unknown_action", confidence=0.5)
        plan = planner.create_plan(opp)
        assert plan.workflow_type == WorkflowType.CUSTOM
        assert plan.status == PlanStatus.REJECTED
        assert len(plan.validation_errors) >= 1
        assert plan.template_name == ""

    def test_zero_confidence(self):
        """零置信度."""
        planner = ExecutionPlanner()
        opp = _make_opportunity(action_type="increase_budget", confidence=0.0)
        plan = planner.create_plan(opp)
        # 验证应该失败 (置信度不够)
        assert plan.status == PlanStatus.REJECTED

    def test_extreme_budget_multiplier(self):
        """极端预算倍数."""
        planner = ExecutionPlanner()
        opp = _make_opportunity(
            action_type="increase_budget",
            confidence=0.9,
            budget_multiplier=3.0,  # +200%
        )
        plan = planner.create_plan(opp)
        assert plan.status == PlanStatus.REJECTED

    def test_empty_context(self):
        """空上下文."""
        planner = ExecutionPlanner()
        opp = _make_opportunity(action_type="increase_budget", confidence=0.85)
        plan = planner.create_plan(opp, context={})
        assert plan.task_count > 0

    def test_opportunity_as_dict(self):
        """Opportunity 作为 dict 传入."""
        planner = ExecutionPlanner()
        opp = {
            "opportunity_id": "opp_dict",
            "action": "increase_budget",
            "action_type": "increase_budget",
            "confidence": 0.85,
            "severity": "medium",
        }
        plan = planner.create_plan(opp)
        assert plan.action_type == "increase_budget"
        assert plan.opportunity_id == "opp_dict"

    def test_opportunity_enum_action(self):
        """Opportunity action 为枚举值."""
        from enum import Enum

        class TestAction(Enum):
            INCREASE_BUDGET = "increase_budget"

        planner = ExecutionPlanner()
        opp = MagicMock()
        opp.opportunity_id = "opp_enum"
        opp.action = TestAction.INCREASE_BUDGET
        opp.action_type = ""
        opp.confidence = 0.85
        opp.severity = "medium"
        opp.product_id = ""
        opp.creative_id = ""
        opp.budget_multiplier = 1.2
        opp.target_budget = 0
        opp.current_budget = 0
        plan = planner.create_plan(opp)
        assert plan.action_type == "increase_budget"

    def test_validate_action_method(self):
        """validate_action 方法 — 低置信度导致验证失败."""
        planner = ExecutionPlanner()
        errors = planner.validate_action("increase_budget", confidence=0.4)
        # 置信度 0.4 < 0.7 → 应该有错误
        assert len(errors) >= 1

    def test_validate_action_with_high_confidence(self):
        """高置信度 Action 验证."""
        planner = ExecutionPlanner()
        errors = planner.validate_action("replace_creative", confidence=0.9)
        assert errors == []

    def test_create_plan_opportunity_context(self):
        """计划包含 Opportunity 上下文."""
        planner = ExecutionPlanner()
        opp = _make_opportunity(
            action_type="increase_budget",
            confidence=0.85,
            product_id="game_789",
            creative_id="creative_999",
            current_budget=500,
            target_budget=600,
        )
        plan = planner.create_plan(opp)
        assert plan.context["product_id"] == "game_789"
        assert plan.context["creative_id"] == "creative_999"
        assert plan.context["current_budget"] == 500
        assert plan.context["target_budget"] == 600

    def test_all_builtin_actions_work(self):
        """所有内置 Action 都能生成计划."""
        planner = ExecutionPlanner()
        for action in planner.get_supported_actions():
            plan = planner.create_plan_from_action(action, confidence=0.85)
            assert plan.task_count > 0, f"Action {action} should have tasks"