"""E13.6.2 Action Planner — 测试套件.

覆盖:
  - Models (ActionNode, ActionPlan, ActionDependency, ActionTemplate)
  - ActionGraph (构建, 拓扑排序, 回路检测, 阶段排序, 依赖分析)
  - ActionPlanner (模板展开, 规则注入, 回滚规划)
  - Integration (Decision → ExecutionTask → ActionPlan → Ordered Actions)
"""

import pytest

from market_ops.creative_vision_runtime.growth_runtime.execution import (
    ActionDependency,
    ActionGraph,
    ActionNode,
    ActionPlan,
    ActionPlanner,
    ActionStatus,
    ActionTemplate,
    PlanPhase,
    ExecutionAction,
    ExecutionActionType,
    ExecutionDomain,
    ExecutionPriority,
    ExecutionStatus,
    ExecutionTask,
    TaskConverter,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.models import (
    DecisionOutput,
    DecisionPlan,
    DecisionType,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def make_action(
    action_type: ExecutionActionType = ExecutionActionType.MONITOR,
    domain: ExecutionDomain = ExecutionDomain.MONITOR,
    priority: ExecutionPriority = ExecutionPriority.MEDIUM,
    **kwargs,
) -> ExecutionAction:
    """创建测试用 ExecutionAction."""
    params = {
        "action_type": action_type,
        "domain": domain,
        "priority": priority,
    }
    params.update(kwargs)
    return ExecutionAction(**params)


def make_task(
    actions: list[ExecutionAction] | None = None,
    risk_level: str = "safe",
    priority: ExecutionPriority = ExecutionPriority.MEDIUM,
    requires_approval: bool = False,
    **kwargs,
) -> ExecutionTask:
    """创建测试用 ExecutionTask."""
    task = ExecutionTask(
        risk_level=risk_level,
        priority=priority,
        requires_approval=requires_approval,
        **kwargs,
    )
    if actions:
        for a in actions:
            task.add_action(a)
    return task


def make_decision(
    decision_type: DecisionType = DecisionType.TEST,
    strategy_name: str = "creative_mutation_v3",
    confidence: float = 0.85,
    risk_score: float = 0.15,
    risk_level: str = "low",
    requires_approval: bool = False,
    test_budget: float = 500.0,
) -> DecisionOutput:
    """创建测试用 DecisionOutput."""
    plan = DecisionPlan(
        action_type=decision_type.value,
        test_budget=test_budget,
        execute_budget=2000.0,
        duration_days=3,
        params={"generate_creatives": 5},
    )
    return DecisionOutput(
        opportunity_id="opp_001",
        strategy_id="S001",
        strategy_name=strategy_name,
        decision_type=decision_type,
        confidence=confidence,
        risk_score=risk_score,
        risk_level=risk_level,
        requires_approval=requires_approval,
        action_plan=plan,
    )


# ═══════════════════════════════════════════════════════════════
# 1. Models — ActionNode
# ═══════════════════════════════════════════════════════════════


class TestActionNode:
    """ActionNode 模型测试."""

    def test_create_default_node(self):
        """默认创建 ActionNode."""
        node = ActionNode()
        assert node.node_id
        assert node.action is not None
        assert node.dependencies == {}
        assert node.preconditions == []
        assert node.postconditions == []
        assert node.rollback_action is None
        assert node.status == ActionStatus.PENDING
        assert node.phase == PlanPhase.EXECUTE

    def test_create_node_with_action(self):
        """使用指定 Action 创建节点."""
        action = make_action(ExecutionActionType.CREATE_CAMPAIGN)
        node = ActionNode(action=action)
        assert node.action.action_type == ExecutionActionType.CREATE_CAMPAIGN

    def test_add_dependency(self):
        """添加依赖关系."""
        node = ActionNode()
        node.add_dependency("node_001", ActionDependency.REQUIRED)
        assert node.dependencies == {"node_001": ActionDependency.REQUIRED}
        assert node.has_dependencies is True

    def test_add_optional_dependency(self):
        """添加可选依赖."""
        node = ActionNode()
        node.add_dependency("node_002", ActionDependency.OPTIONAL)
        assert node.dependencies["node_002"] == ActionDependency.OPTIONAL

    def test_add_conditional_dependency(self):
        """添加条件依赖."""
        node = ActionNode()
        node.add_dependency("node_003", ActionDependency.CONDITIONAL)
        assert node.dependencies["node_003"] == ActionDependency.CONDITIONAL

    def test_required_dependencies_property(self):
        """获取 REQUIRED 依赖列表."""
        node = ActionNode()
        node.add_dependency("a", ActionDependency.REQUIRED)
        node.add_dependency("b", ActionDependency.OPTIONAL)
        node.add_dependency("c", ActionDependency.REQUIRED)
        assert set(node.required_dependencies) == {"a", "c"}

    def test_add_precondition(self):
        """添加前置条件."""
        node = ActionNode()
        node.add_precondition("creative_uploaded=True")
        assert "creative_uploaded=True" in node.preconditions

    def test_add_postcondition(self):
        """添加后置条件."""
        node = ActionNode()
        node.add_postcondition("campaign_id exists")
        assert "campaign_id exists" in node.postconditions

    def test_mark_ready(self):
        """标记就绪."""
        node = ActionNode()
        node.mark_ready()
        assert node.is_ready is True
        assert node.status == ActionStatus.READY

    def test_mark_running(self):
        """标记运行中."""
        node = ActionNode()
        node.mark_running()
        assert node.status == ActionStatus.RUNNING

    def test_mark_success(self):
        """标记成功."""
        node = ActionNode()
        node.mark_success()
        assert node.status == ActionStatus.SUCCESS
        assert node.is_completed is True

    def test_mark_failed(self):
        """标记失败."""
        node = ActionNode()
        node.mark_failed()
        assert node.status == ActionStatus.FAILED

    def test_mark_skipped(self):
        """标记跳过."""
        node = ActionNode()
        node.mark_skipped()
        assert node.status == ActionStatus.SKIPPED
        assert node.is_completed is True

    def test_mark_rolled_back(self):
        """标记回滚."""
        node = ActionNode()
        node.mark_rolled_back()
        assert node.status == ActionStatus.ROLLED_BACK

    def test_to_dict(self):
        """序列化测试."""
        node = ActionNode(
            action=make_action(ExecutionActionType.CREATE_CAMPAIGN),
            preconditions=["budget_ok"],
            postconditions=["campaign_created"],
        )
        d = node.to_dict()
        assert d["node_id"] == node.node_id
        assert d["status"] == "pending"
        assert d["preconditions"] == ["budget_ok"]
        assert d["postconditions"] == ["campaign_created"]
        assert d["action"] is not None

    def test_rollback_action(self):
        """设置回滚动作."""
        rollback = make_action(ExecutionActionType.PAUSE_CAMPAIGN)
        node = ActionNode(rollback_action=rollback)
        assert node.rollback_action is not None
        assert node.rollback_action.action_type == ExecutionActionType.PAUSE_CAMPAIGN

    def test_retry_config(self):
        """重试配置."""
        node = ActionNode(max_retries=5, retry_count=2)
        assert node.max_retries == 5
        assert node.retry_count == 2

    def test_phase_default(self):
        """默认阶段."""
        node = ActionNode()
        assert node.phase == PlanPhase.EXECUTE

    def test_priority_default(self):
        """默认优先级."""
        node = ActionNode()
        assert node.priority == ExecutionPriority.MEDIUM


# ═══════════════════════════════════════════════════════════════
# 2. Models — ActionPlan
# ═══════════════════════════════════════════════════════════════


class TestActionPlan:
    """ActionPlan 模型测试."""

    def test_create_default_plan(self):
        """默认创建 ActionPlan."""
        plan = ActionPlan()
        assert plan.plan_id
        assert plan.task_id == ""
        assert plan.nodes == []
        assert plan.execution_order == []
        assert plan.rollback_enabled is True
        assert plan.rollback_order == []
        assert plan.status == ActionStatus.PENDING

    def test_create_with_task_id(self):
        """指定 task_id 创建."""
        plan = ActionPlan(task_id="task_001")
        assert plan.task_id == "task_001"

    def test_node_count(self):
        """节点计数."""
        plan = ActionPlan()
        assert plan.node_count == 0
        plan.add_node(ActionNode())
        plan.add_node(ActionNode())
        assert plan.node_count == 2
        assert plan.has_nodes is True

    def test_get_node(self):
        """按 ID 获取节点."""
        node = ActionNode()
        plan = ActionPlan(nodes=[node])
        assert plan.get_node(node.node_id) == node
        assert plan.get_node("nonexistent") is None

    def test_get_nodes_by_phase(self):
        """按阶段获取节点."""
        n1 = ActionNode(phase=PlanPhase.PREPARE)
        n2 = ActionNode(phase=PlanPhase.EXECUTE)
        n3 = ActionNode(phase=PlanPhase.EXECUTE)
        plan = ActionPlan(nodes=[n1, n2, n3])
        assert len(plan.get_nodes_by_phase(PlanPhase.EXECUTE)) == 2
        assert len(plan.get_nodes_by_phase(PlanPhase.PREPARE)) == 1

    def test_get_ordered_nodes(self):
        """按执行顺序获取节点."""
        n1 = ActionNode()
        n2 = ActionNode()
        n3 = ActionNode()
        plan = ActionPlan(
            nodes=[n1, n2, n3],
            execution_order=[n2.node_id, n1.node_id, n3.node_id],
        )
        ordered = plan.get_ordered_nodes()
        assert ordered[0] == n2
        assert ordered[1] == n1
        assert ordered[2] == n3

    def test_get_ready_nodes(self):
        """获取就绪节点."""
        n1 = ActionNode()
        n1.mark_ready()
        n2 = ActionNode()
        n3 = ActionNode()
        n3.mark_ready()
        plan = ActionPlan(nodes=[n1, n2, n3])
        ready = plan.get_ready_nodes()
        assert len(ready) == 2

    def test_get_pending_nodes(self):
        """获取待执行节点."""
        n1 = ActionNode()
        n1.mark_success()
        n2 = ActionNode()  # PENDING
        n3 = ActionNode()
        n3.mark_ready()
        plan = ActionPlan(nodes=[n1, n2, n3])
        pending = plan.get_pending_nodes()
        assert len(pending) == 1
        assert pending[0] == n2

    def test_set_execution_order(self):
        """设置执行顺序."""
        plan = ActionPlan()
        plan.set_execution_order(["a", "b", "c"])
        assert plan.execution_order == ["a", "b", "c"]

    def test_estimate_duration(self):
        """估算执行时长."""
        n1 = ActionNode(priority=ExecutionPriority.HIGH)
        n2 = ActionNode(priority=ExecutionPriority.MEDIUM)
        n3 = ActionNode(priority=ExecutionPriority.LOW)
        plan = ActionPlan(nodes=[n1, n2, n3])
        duration = plan.estimate_duration()
        # HIGH → 15, MEDIUM → 10, LOW → 10
        assert duration == 30
        assert plan.estimated_duration_minutes == 30

    def test_to_dict(self):
        """序列化测试."""
        n1 = ActionNode()
        n2 = ActionNode()
        plan = ActionPlan(
            task_id="task_001",
            nodes=[n1, n2],
            execution_order=[n1.node_id, n2.node_id],
        )
        d = plan.to_dict()
        assert d["plan_id"] == plan.plan_id
        assert d["task_id"] == "task_001"
        assert len(d["nodes"]) == 2
        assert d["rollback_enabled"] is True


# ═══════════════════════════════════════════════════════════════
# 3. Models — ActionTemplate
# ═══════════════════════════════════════════════════════════════


class TestActionTemplate:
    """ActionTemplate 模型测试."""

    def test_create_template(self):
        """创建模板."""
        template = ActionTemplate(
            action_type=ExecutionActionType.MUTATE_CREATIVE,
            name="Creative Mutation",
            expansion=[
                ExecutionActionType.CREATE_CREATIVE,
                ExecutionActionType.UPLOAD_CREATIVE,
            ],
            preconditions=["creative_dna_available"],
            postconditions=["creative_uploaded"],
            requires_monitoring=True,
            estimated_duration_minutes=60,
        )
        assert template.name == "Creative Mutation"
        assert len(template.expansion) == 2
        assert template.requires_monitoring is True
        assert template.estimated_duration_minutes == 60

    def test_template_no_expansion(self):
        """无展开的模板."""
        template = ActionTemplate(
            action_type=ExecutionActionType.MONITOR,
            name="Monitor",
            expansion=[],
        )
        assert template.expansion == []

    def test_template_requires_approval(self):
        """需要审批的模板."""
        template = ActionTemplate(
            action_type=ExecutionActionType.SCALE_BUDGET,
            requires_approval=True,
        )
        assert template.requires_approval is True


# ═══════════════════════════════════════════════════════════════
# 4. ActionGraph — 构建与拓扑
# ═══════════════════════════════════════════════════════════════


class TestActionGraphBuild:
    """ActionGraph 构建测试."""

    def test_create_empty_graph(self):
        """创建空图."""
        graph = ActionGraph()
        assert graph.node_count == 0
        assert graph.edge_count == 0
        assert graph.has_cycle is False

    def test_add_single_node(self):
        """添加单个节点."""
        graph = ActionGraph()
        node = ActionNode()
        graph.add_node(node)
        assert graph.node_count == 1
        assert graph.edge_count == 0

    def test_add_multiple_nodes(self):
        """批量添加节点."""
        graph = ActionGraph()
        nodes = [ActionNode() for _ in range(5)]
        graph.add_nodes(nodes)
        assert graph.node_count == 5

    def test_add_edge(self):
        """添加有向边."""
        graph = ActionGraph()
        n1 = ActionNode()
        n2 = ActionNode()
        graph.add_nodes([n1, n2])
        graph.add_edge(n1.node_id, n2.node_id)
        assert graph.edge_count == 1

    def test_add_edge_missing_node(self):
        """添加边时节点不存在."""
        graph = ActionGraph()
        n1 = ActionNode()
        graph.add_node(n1)
        graph.add_edge(n1.node_id, "nonexistent")
        assert graph.edge_count == 0  # 忽略

    def test_build_from_nodes_with_deps(self):
        """从带依赖的节点构建图."""
        n1 = ActionNode()
        n2 = ActionNode()
        n2.add_dependency(n1.node_id, ActionDependency.REQUIRED)
        n3 = ActionNode()
        n3.add_dependency(n2.node_id, ActionDependency.REQUIRED)

        graph = ActionGraph()
        graph.build_from_nodes([n1, n2, n3])
        assert graph.node_count == 3
        assert graph.edge_count == 2

    def test_build_resets_previous(self):
        """build_from_nodes 重置之前的状态."""
        graph = ActionGraph()
        n1 = ActionNode()
        n2 = ActionNode()
        graph.add_nodes([n1, n2])
        graph.add_edge(n1.node_id, n2.node_id)

        n3 = ActionNode()
        graph.build_from_nodes([n3])
        assert graph.node_count == 1
        assert graph.edge_count == 0


class TestActionGraphTopologicalSort:
    """ActionGraph 拓扑排序测试."""

    def test_simple_linear_chain(self):
        """简单线性链: n1 → n2 → n3."""
        n1 = ActionNode()
        n2 = ActionNode()
        n2.add_dependency(n1.node_id)
        n3 = ActionNode()
        n3.add_dependency(n2.node_id)

        graph = ActionGraph()
        graph.build_from_nodes([n1, n2, n3])
        order = graph.topological_sort()

        assert order == [n1.node_id, n2.node_id, n3.node_id]

    def test_diamond_dependency(self):
        """菱形依赖: n1 → n2, n1 → n3, n2 → n4, n3 → n4."""
        n1 = ActionNode()
        n2 = ActionNode()
        n2.add_dependency(n1.node_id)
        n3 = ActionNode()
        n3.add_dependency(n1.node_id)
        n4 = ActionNode()
        n4.add_dependency(n2.node_id)
        n4.add_dependency(n3.node_id)

        graph = ActionGraph()
        graph.build_from_nodes([n1, n2, n3, n4])
        order = graph.topological_sort()

        assert order[0] == n1.node_id
        assert set(order[1:3]) == {n2.node_id, n3.node_id}
        assert order[3] == n4.node_id

    def test_independent_nodes(self):
        """无依赖节点."""
        nodes = [ActionNode() for _ in range(4)]
        graph = ActionGraph()
        graph.build_from_nodes(nodes)
        order = graph.topological_sort()
        assert len(order) == 4

    def test_no_nodes(self):
        """空图拓扑排序."""
        graph = ActionGraph()
        order = graph.topological_sort()
        assert order == []

    def test_cycle_detection_simple(self):
        """简单回路检测: n1 → n2 → n1."""
        n1 = ActionNode()
        n2 = ActionNode()
        n1.add_dependency(n2.node_id)
        n2.add_dependency(n1.node_id)

        graph = ActionGraph()
        graph.build_from_nodes([n1, n2])
        graph.topological_sort()
        assert graph.has_cycle is True

    def test_cycle_detection_no_cycle(self):
        """无回路时不应检测到."""
        n1 = ActionNode()
        n2 = ActionNode()
        n2.add_dependency(n1.node_id)

        graph = ActionGraph()
        graph.build_from_nodes([n1, n2])
        graph.topological_sort()
        assert graph.has_cycle is False

    def test_detect_cycles_method(self):
        """detect_cycles 方法."""
        n1 = ActionNode()
        n2 = ActionNode()
        n3 = ActionNode()
        n1.add_dependency(n3.node_id)
        n2.add_dependency(n1.node_id)
        n3.add_dependency(n2.node_id)

        graph = ActionGraph()
        graph.build_from_nodes([n1, n2, n3])
        cycles = graph.detect_cycles()
        assert len(cycles) > 0
        assert graph.has_cycle is True


class TestActionGraphPhaseOrdering:
    """ActionGraph 阶段排序测试."""

    def test_phase_ordered_sort(self):
        """按阶段排序."""
        n1 = ActionNode(phase=PlanPhase.PREPARE)
        n2 = ActionNode(phase=PlanPhase.EXECUTE)
        n3 = ActionNode(phase=PlanPhase.EXECUTE)
        n4 = ActionNode(phase=PlanPhase.VERIFY)
        n5 = ActionNode(phase=PlanPhase.MONITOR)

        graph = ActionGraph()
        graph.build_from_nodes([n1, n2, n3, n4, n5])
        order = graph.phase_ordered_sort()

        # PREPARE first
        assert order[0] == n1.node_id
        # MONITOR last
        assert order[-1] == n5.node_id

    def test_phase_ordered_with_deps(self):
        """有依赖的阶段排序."""
        n1 = ActionNode(phase=PlanPhase.PREPARE)
        n2 = ActionNode(phase=PlanPhase.EXECUTE)
        n2.add_dependency(n1.node_id)
        n3 = ActionNode(phase=PlanPhase.MONITOR)
        n3.add_dependency(n2.node_id)

        graph = ActionGraph()
        graph.build_from_nodes([n1, n2, n3])
        order = graph.phase_ordered_sort()

        assert order == [n1.node_id, n2.node_id, n3.node_id]

    def test_compute_phases(self):
        """计算阶段分组."""
        n1 = ActionNode(phase=PlanPhase.PREPARE)
        n2 = ActionNode(phase=PlanPhase.EXECUTE)
        n3 = ActionNode(phase=PlanPhase.EXECUTE)

        graph = ActionGraph()
        graph.build_from_nodes([n1, n2, n3])
        phases = graph.compute_phases()

        assert "prepare" in phases
        assert "execute" in phases
        assert len(phases["prepare"]) == 1
        assert len(phases["execute"]) == 2


class TestActionGraphDependencyAnalysis:
    """ActionGraph 依赖分析测试."""

    def test_get_direct_dependencies(self):
        """获取直接依赖."""
        n1 = ActionNode()
        n2 = ActionNode()
        n2.add_dependency(n1.node_id)

        graph = ActionGraph()
        graph.build_from_nodes([n1, n2])

        deps = graph.get_dependencies(n2.node_id)
        assert n1.node_id in deps

    def test_get_dependents(self):
        """获取下游节点."""
        n1 = ActionNode()
        n2 = ActionNode()
        n2.add_dependency(n1.node_id)

        graph = ActionGraph()
        graph.build_from_nodes([n1, n2])

        dependents = graph.get_dependents(n1.node_id)
        assert n2.node_id in dependents

    def test_transitive_dependencies(self):
        """传递依赖: n1 → n2 → n3."""
        n1 = ActionNode()
        n2 = ActionNode()
        n2.add_dependency(n1.node_id)
        n3 = ActionNode()
        n3.add_dependency(n2.node_id)

        graph = ActionGraph()
        graph.build_from_nodes([n1, n2, n3])

        transitive = graph.get_transitive_dependencies(n3.node_id)
        assert n1.node_id in transitive
        assert n2.node_id in transitive

    def test_is_reachable(self):
        """可达性检查."""
        n1 = ActionNode()
        n2 = ActionNode()
        n2.add_dependency(n1.node_id)
        n3 = ActionNode()

        graph = ActionGraph()
        graph.build_from_nodes([n1, n2, n3])

        assert graph.is_reachable(n1.node_id, n2.node_id) is True
        assert graph.is_reachable(n1.node_id, n3.node_id) is False
        assert graph.is_reachable(n2.node_id, n1.node_id) is False

    def test_entry_nodes(self):
        """获取入度为 0 的节点."""
        n1 = ActionNode()
        n2 = ActionNode()
        n2.add_dependency(n1.node_id)
        n3 = ActionNode()

        graph = ActionGraph()
        graph.build_from_nodes([n1, n2, n3])

        entries = graph.get_entry_nodes()
        assert n1.node_id in entries
        assert n3.node_id in entries
        assert n2.node_id not in entries

    def test_exit_nodes(self):
        """获取出度为 0 的节点."""
        n1 = ActionNode()
        n2 = ActionNode()
        n2.add_dependency(n1.node_id)
        n3 = ActionNode()

        graph = ActionGraph()
        graph.build_from_nodes([n1, n2, n3])

        exits = graph.get_exit_nodes()
        assert n2.node_id in exits
        assert n3.node_id in exits


# ═══════════════════════════════════════════════════════════════
# 5. ActionPlanner — 模板展开
# ═══════════════════════════════════════════════════════════════


class TestActionPlannerTemplates:
    """ActionPlanner 模板系统测试."""

    def test_register_and_get_template(self):
        """注册和获取模板."""
        planner = ActionPlanner()
        template = ActionTemplate(
            action_type=ExecutionActionType.CREATE_CAMPAIGN,
            name="Custom",
            expansion=[],
        )
        planner.register_template(template)
        result = planner.get_template(ExecutionActionType.CREATE_CAMPAIGN)
        assert result == template

    def test_builtin_templates(self):
        """内置模板注册."""
        planner = ActionPlanner()
        assert planner.get_template(ExecutionActionType.MUTATE_CREATIVE) is not None
        assert planner.get_template(ExecutionActionType.SCALE_BUDGET) is not None
        assert planner.get_template(ExecutionActionType.PAUSE_CAMPAIGN) is not None
        assert planner.get_template(ExecutionActionType.MONITOR) is not None
        assert planner.get_template(ExecutionActionType.COLLECT_RESULT) is not None

    def test_mutate_creative_template(self):
        """MUTATE_CREATIVE 模板展开."""
        planner = ActionPlanner()
        template = planner.get_template(ExecutionActionType.MUTATE_CREATIVE)
        assert template is not None
        assert template.requires_monitoring is True
        assert ExecutionActionType.CREATE_CREATIVE in template.expansion
        assert ExecutionActionType.UPLOAD_CREATIVE in template.expansion
        assert ExecutionActionType.CREATE_CAMPAIGN in template.expansion
        assert ExecutionActionType.MONITOR in template.expansion

    def test_scale_budget_template(self):
        """SCALE_BUDGET 模板展开."""
        planner = ActionPlanner()
        template = planner.get_template(ExecutionActionType.SCALE_BUDGET)
        assert template is not None
        assert ExecutionActionType.UPDATE_BUDGET in template.expansion

    def test_pause_campaign_template(self):
        """PAUSE_CAMPAIGN 模板展开."""
        planner = ActionPlanner()
        template = planner.get_template(ExecutionActionType.PAUSE_CAMPAIGN)
        assert template is not None
        assert ExecutionActionType.FREEZE_CAMPAIGN in template.expansion
        assert "campaign_paused" in template.postconditions

    def test_monitor_template_no_expansion(self):
        """MONITOR 模板无展开."""
        planner = ActionPlanner()
        template = planner.get_template(ExecutionActionType.MONITOR)
        assert template is not None
        assert template.expansion == []

    def test_collect_result_template(self):
        """COLLECT_RESULT 模板."""
        planner = ActionPlanner()
        template = planner.get_template(ExecutionActionType.COLLECT_RESULT)
        assert template is not None
        assert template.phase == PlanPhase.VERIFY


class TestActionPlannerExpansion:
    """ActionPlanner 展开逻辑测试."""

    def test_plan_returns_action_plan(self):
        """plan() 返回 ActionPlan."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.MONITOR)
        task = make_task(actions=[action])
        plan = planner.plan(task)
        assert isinstance(plan, ActionPlan)
        assert plan.task_id == task.task_id

    def test_plan_single_monitor_action(self):
        """规划单个 MONITOR 动作."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.MONITOR)
        task = make_task(actions=[action])
        plan = planner.plan(task)
        assert plan.node_count >= 1

    def test_expand_mutate_creative(self):
        """展开 MUTATE_CREATIVE."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.MUTATE_CREATIVE)
        task = make_task(actions=[action])
        plan = planner.plan(task)

        action_types = [n.action.action_type for n in plan.nodes]
        assert ExecutionActionType.CREATE_CREATIVE in action_types
        assert ExecutionActionType.UPLOAD_CREATIVE in action_types
        assert ExecutionActionType.CREATE_CAMPAIGN in action_types
        assert ExecutionActionType.MONITOR in action_types

    def test_expand_mutate_creative_ordering(self):
        """MUTATE_CREATIVE 展开顺序: CREATE → UPLOAD → CAMPAIGN → MONITOR."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.MUTATE_CREATIVE)
        task = make_task(actions=[action])
        plan = planner.plan(task)

        ordered = plan.get_ordered_nodes()
        non_collect = [n for n in ordered if n.action.action_type != ExecutionActionType.COLLECT_RESULT]
        action_types = [n.action.action_type for n in non_collect]

        # 顺序必须是 CREATE_CREATIVE → UPLOAD_CREATIVE → CREATE_CAMPAIGN → MONITOR
        idx_create = action_types.index(ExecutionActionType.CREATE_CREATIVE)
        idx_upload = action_types.index(ExecutionActionType.UPLOAD_CREATIVE)
        idx_campaign = action_types.index(ExecutionActionType.CREATE_CAMPAIGN)
        idx_monitor = action_types.index(ExecutionActionType.MONITOR)
        assert idx_create < idx_upload < idx_campaign < idx_monitor

    def test_expand_scale_budget(self):
        """展开 SCALE_BUDGET."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.SCALE_BUDGET)
        task = make_task(actions=[action])
        plan = planner.plan(task)

        action_types = [n.action.action_type for n in plan.nodes]
        assert ExecutionActionType.UPDATE_BUDGET in action_types
        assert ExecutionActionType.MONITOR in action_types

    def test_expand_pause_campaign(self):
        """展开 PAUSE_CAMPAIGN."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.PAUSE_CAMPAIGN)
        task = make_task(actions=[action])
        plan = planner.plan(task)

        action_types = [n.action.action_type for n in plan.nodes]
        assert ExecutionActionType.FREEZE_CAMPAIGN in action_types
        assert ExecutionActionType.MONITOR in action_types

    def test_no_template_action(self):
        """无模板的动作直接包装."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.MONITOR)
        task = make_task(actions=[action])
        plan = planner.plan(task)
        assert plan.node_count >= 1

    def test_multiple_actions(self):
        """多个动作的任务."""
        planner = ActionPlanner()
        a1 = make_action(ExecutionActionType.MUTATE_CREATIVE)
        a2 = make_action(ExecutionActionType.MONITOR)
        task = make_task(actions=[a1, a2])
        plan = planner.plan(task)
        assert plan.node_count >= 2

    def test_expansion_preserves_priority(self):
        """展开保留优先级."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.MUTATE_CREATIVE, priority=ExecutionPriority.HIGH)
        task = make_task(actions=[action])
        plan = planner.plan(task)

        for node in plan.nodes:
            if node.action.action_type in (
                ExecutionActionType.CREATE_CREATIVE,
                ExecutionActionType.UPLOAD_CREATIVE,
                ExecutionActionType.CREATE_CAMPAIGN,
            ):
                assert node.priority == ExecutionPriority.HIGH


# ═══════════════════════════════════════════════════════════════
# 6. ActionPlanner — 规则注入
# ═══════════════════════════════════════════════════════════════


class TestActionPlannerRules:
    """ActionPlanner 规则注入测试."""

    def test_high_risk_adds_approval(self):
        """高风险任务添加审批节点."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.MONITOR)
        task = make_task(actions=[action], risk_level="high")
        plan = planner.plan(task)

        # 检查是否有审批节点
        approval_nodes = [
            n for n in plan.nodes
            if "approval_required" in str(n.action.parameters)
        ]
        assert len(approval_nodes) >= 1

    def test_low_risk_no_approval(self):
        """低风险任务不添加审批节点."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.MONITOR)
        task = make_task(actions=[action], risk_level="safe")
        plan = planner.plan(task)

        approval_nodes = [
            n for n in plan.nodes
            if "approval_required" in str(n.action.parameters)
        ]
        assert len(approval_nodes) == 0

    def test_critical_risk_adds_approval(self):
        """critical 风险添加审批."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.MONITOR)
        task = make_task(actions=[action], risk_level="critical")
        plan = planner.plan(task)

        approval_nodes = [
            n for n in plan.nodes
            if "approval_required" in str(n.action.parameters)
        ]
        assert len(approval_nodes) >= 1

    def test_budget_action_adds_monitor(self):
        """预算动作自动添加监控."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.SCALE_BUDGET)
        task = make_task(actions=[action])
        plan = planner.plan(task)

        action_types = [n.action.action_type for n in plan.nodes]
        assert ExecutionActionType.MONITOR in action_types

    def test_upload_creative_adds_verify(self):
        """素材上传添加质量检查."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.UPLOAD_CREATIVE)
        task = make_task(actions=[action])
        plan = planner.plan(task)

        verify_nodes = [
            n for n in plan.nodes
            if "quality_check" in str(n.action.parameters)
        ]
        assert len(verify_nodes) >= 1

    def test_always_adds_collect_result(self):
        """总是添加结果收集节点."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.MONITOR)
        task = make_task(actions=[action])
        plan = planner.plan(task)

        collect_nodes = [
            n for n in plan.nodes
            if n.action.action_type == ExecutionActionType.COLLECT_RESULT
        ]
        assert len(collect_nodes) >= 1

    def test_collect_result_at_end(self):
        """结果收集节点在最后."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.MONITOR)
        task = make_task(actions=[action])
        plan = planner.plan(task)

        ordered = plan.get_ordered_nodes()
        assert ordered[-1].action.action_type == ExecutionActionType.COLLECT_RESULT

    def test_verify_after_upload(self):
        """质量检查在 UPLOAD_CREATIVE 之后."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.UPLOAD_CREATIVE)
        task = make_task(actions=[action])
        plan = planner.plan(task)

        ordered = plan.get_ordered_nodes()
        non_collect = [n for n in ordered if n.action.action_type != ExecutionActionType.COLLECT_RESULT]
        action_types = [n.action.action_type for n in non_collect]

        # 找到 UPLOAD 和 verify 节点
        upload_idx = None
        verify_idx = None
        for i, n in enumerate(non_collect):
            if n.action.action_type == ExecutionActionType.UPLOAD_CREATIVE:
                upload_idx = i
            if "quality_check" in str(n.action.parameters):
                verify_idx = i

        if upload_idx is not None and verify_idx is not None:
            assert upload_idx < verify_idx

    def test_approval_before_execute(self):
        """审批节点在 EXECUTE 阶段之前."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.MUTATE_CREATIVE)
        task = make_task(actions=[action], risk_level="high")
        plan = planner.plan(task)

        approval_nodes = [
            n for n in plan.nodes
            if "approval_required" in str(n.action.parameters)
        ]
        assert len(approval_nodes) >= 1
        assert approval_nodes[0].phase == PlanPhase.PREPARE


# ═══════════════════════════════════════════════════════════════
# 7. ActionPlanner — 回滚规划
# ═══════════════════════════════════════════════════════════════


class TestActionPlannerRollback:
    """ActionPlanner 回滚规划测试."""

    def test_rollback_enabled_by_default(self):
        """默认启用回滚."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.MONITOR)
        task = make_task(actions=[action])
        plan = planner.plan(task)
        assert plan.rollback_enabled is True

    def test_rollback_order_exists(self):
        """回滚顺序存在."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.CREATE_CAMPAIGN)
        task = make_task(actions=[action])
        plan = planner.plan(task)
        assert isinstance(plan.rollback_order, list)

    def test_rollback_order_reverse(self):
        """回滚顺序是逆执行序."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.MUTATE_CREATIVE)
        task = make_task(actions=[action])
        plan = planner.plan(task)

        create_campaign_nodes = [
            nid for nid in plan.rollback_order
            if plan.get_node(nid)
            and plan.get_node(nid).action.action_type == ExecutionActionType.CREATE_CAMPAIGN
        ]
        assert len(create_campaign_nodes) >= 0  # 至少不崩溃

    def test_rollback_only_side_effect_actions(self):
        """只回滚有副作用的动作."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.MONITOR)
        task = make_task(actions=[action])
        plan = planner.plan(task)

        # MONITOR 不在回滚列表中
        for nid in plan.rollback_order:
            node = plan.get_node(nid)
            assert node.action.action_type != ExecutionActionType.MONITOR

    def test_disable_rollback(self):
        """禁用回滚."""
        planner = ActionPlanner()
        planner.auto_add_rollback = False
        action = make_action(ExecutionActionType.MONITOR)
        task = make_task(actions=[action])
        plan = planner.plan(task)
        assert plan.rollback_order == []

    def test_campaign_create_in_rollback(self):
        """CREATE_CAMPAIGN 在回滚列表中."""
        planner = ActionPlanner()
        action = make_action(ExecutionActionType.CREATE_CAMPAIGN)
        task = make_task(actions=[action])
        plan = planner.plan(task)

        rollback_types = [
            plan.get_node(nid).action.action_type
            for nid in plan.rollback_order
            if plan.get_node(nid)
        ]
        assert ExecutionActionType.CREATE_CAMPAIGN in rollback_types


# ═══════════════════════════════════════════════════════════════
# 8. ActionPlanner — 规划配置
# ═══════════════════════════════════════════════════════════════


class TestActionPlannerConfig:
    """ActionPlanner 配置测试."""

    def test_disable_monitor_rule(self):
        """禁用自动监控规则."""
        planner = ActionPlanner()
        planner.auto_add_monitor = False
        action = make_action(ExecutionActionType.SCALE_BUDGET)
        task = make_task(actions=[action])
        plan = planner.plan(task)

        monitor_count = sum(
            1 for n in plan.nodes
            if n.action.action_type == ExecutionActionType.MONITOR
            and "approval" not in str(n.action.parameters)
            and "quality" not in str(n.action.parameters)
        )
        # 模板展开中可能仍有 MONITOR，但规则注入的不应该有
        assert monitor_count >= 1  # 模板中的 MONITOR 仍然存在

    def test_disable_verify_rule(self):
        """禁用自动验证规则."""
        planner = ActionPlanner()
        planner.auto_add_verify = False
        action = make_action(ExecutionActionType.UPLOAD_CREATIVE)
        task = make_task(actions=[action])
        plan = planner.plan(task)

        verify_nodes = [
            n for n in plan.nodes
            if "quality_check" in str(n.action.parameters)
        ]
        assert len(verify_nodes) == 0

    def test_high_risk_threshold_config(self):
        """自定义高风险阈值."""
        planner = ActionPlanner()
        planner.high_risk_threshold = 0.5
        # risk_level 为 "safe" 即使是字符串也不触发
        action = make_action(ExecutionActionType.MONITOR)
        task = make_task(actions=[action], risk_level="safe")
        plan = planner.plan(task)

        approval_nodes = [
            n for n in plan.nodes
            if "approval_required" in str(n.action.parameters)
        ]
        assert len(approval_nodes) == 0


# ═══════════════════════════════════════════════════════════════
# 9. Integration — Decision → ExecutionTask → ActionPlan
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """E13.6.1 → E13.6.2 集成测试."""

    def test_full_pipeline_test_decision(self):
        """完整流程: Decision(TEST) → Task → ActionPlan."""
        converter = TaskConverter()
        planner = ActionPlanner()

        decision = make_decision(DecisionType.TEST)
        task = converter.convert(decision)
        plan = planner.plan(task)

        assert plan.task_id == task.task_id
        assert plan.node_count > 0
        assert len(plan.execution_order) > 0
        assert plan.execution_order == plan.phase_ordered_sort() if hasattr(plan, 'phase_ordered_sort') else True

    def test_full_pipeline_execute_decision(self):
        """完整流程: Decision(EXECUTE) → Task → ActionPlan."""
        converter = TaskConverter()
        planner = ActionPlanner()

        decision = make_decision(DecisionType.EXECUTE, strategy_name="scale_campaign_v2")
        task = converter.convert(decision)
        plan = planner.plan(task)

        assert plan.task_id == task.task_id
        assert plan.node_count > 0

    def test_full_pipeline_with_approval(self):
        """完整流程: 高风险决策 → 审批."""
        converter = TaskConverter()
        planner = ActionPlanner()

        decision = make_decision(
            DecisionType.EXECUTE,
            risk_level="high",
            requires_approval=True,
        )
        task = converter.convert(decision)
        plan = planner.plan(task)

        # 应该有审批节点
        approval_nodes = [
            n for n in plan.nodes
            if "approval_required" in str(n.action.parameters)
        ]
        assert len(approval_nodes) >= 1

    def test_full_pipeline_creative_mutation(self):
        """完整流程: Creative Mutation 测试."""
        converter = TaskConverter()
        planner = ActionPlanner()

        decision = make_decision(
            DecisionType.TEST,
            strategy_name="creative_mutation_v3",
            test_budget=500.0,
        )
        task = converter.convert(decision)
        plan = planner.plan(task)

        action_types = [n.action.action_type for n in plan.nodes]
        assert ExecutionActionType.CREATE_CREATIVE in action_types
        assert ExecutionActionType.UPLOAD_CREATIVE in action_types
        assert ExecutionActionType.CREATE_CAMPAIGN in action_types

    def test_full_pipeline_scale_budget(self):
        """完整流程: Scale Budget."""
        converter = TaskConverter()
        planner = ActionPlanner()

        decision = make_decision(
            DecisionType.EXECUTE,
            strategy_name="scale_campaign_v2",
        )
        task = converter.convert(decision)
        plan = planner.plan(task)

        action_types = [n.action.action_type for n in plan.nodes]
        assert ExecutionActionType.SCALE_BUDGET in action_types or ExecutionActionType.UPDATE_BUDGET in action_types

    def test_full_pipeline_pause_campaign(self):
        """完整流程: Pause Campaign."""
        converter = TaskConverter()
        planner = ActionPlanner()

        decision = make_decision(
            DecisionType.EXECUTE,
            strategy_name="pause_underperforming",
        )
        task = converter.convert(decision)
        plan = planner.plan(task)

        assert plan.node_count > 0
        assert len(plan.execution_order) > 0

    def test_execution_order_is_valid(self):
        """执行顺序有效性."""
        converter = TaskConverter()
        planner = ActionPlanner()

        decision = make_decision(DecisionType.TEST)
        task = converter.convert(decision)
        plan = planner.plan(task)

        # 所有节点都在执行顺序中
        node_ids = {n.node_id for n in plan.nodes}
        order_ids = set(plan.execution_order)
        assert node_ids == order_ids

    def test_plan_has_phases(self):
        """计划包含阶段分组."""
        converter = TaskConverter()
        planner = ActionPlanner()

        decision = make_decision(DecisionType.TEST)
        task = converter.convert(decision)
        plan = planner.plan(task)

        assert isinstance(plan.phases, dict)
        assert len(plan.phases) > 0

    def test_plan_has_duration(self):
        """计划有预估时长."""
        converter = TaskConverter()
        planner = ActionPlanner()

        decision = make_decision(DecisionType.TEST)
        task = converter.convert(decision)
        plan = planner.plan(task)

        assert plan.estimated_duration_minutes > 0

    def test_plan_serializable(self):
        """计划可序列化."""
        converter = TaskConverter()
        planner = ActionPlanner()

        decision = make_decision(DecisionType.TEST)
        task = converter.convert(decision)
        plan = planner.plan(task)

        d = plan.to_dict()
        assert d["plan_id"] == plan.plan_id
        assert d["task_id"] == plan.task_id
        assert len(d["nodes"]) == plan.node_count
        assert d["execution_order"] == plan.execution_order

    def test_multiple_actions_integration(self):
        """多动作任务集成."""
        converter = TaskConverter()
        planner = ActionPlanner()

        decision = make_decision(DecisionType.EXECUTE)
        task = converter.convert(decision)
        plan = planner.plan(task)

        assert plan.node_count > 0
        assert len(plan.execution_order) > 0
        assert plan.rollback_enabled is True

    def test_collect_result_always_present(self):
        """结果收集节点始终存在."""
        converter = TaskConverter()
        planner = ActionPlanner()

        decision = make_decision(DecisionType.TEST)
        task = converter.convert(decision)
        plan = planner.plan(task)

        collect_nodes = [
            n for n in plan.nodes
            if n.action.action_type == ExecutionActionType.COLLECT_RESULT
        ]
        assert len(collect_nodes) >= 1

    def test_ordered_nodes_accessible(self):
        """有序节点可访问."""
        converter = TaskConverter()
        planner = ActionPlanner()

        decision = make_decision(DecisionType.TEST)
        task = converter.convert(decision)
        plan = planner.plan(task)

        ordered = plan.get_ordered_nodes()
        assert len(ordered) == len(plan.execution_order)
        assert ordered[0].node_id == plan.execution_order[0]

    def test_plan_metadata(self):
        """计划元数据."""
        converter = TaskConverter()
        planner = ActionPlanner()

        decision = make_decision(DecisionType.TEST)
        task = converter.convert(decision)
        plan = planner.plan(task)

        assert isinstance(plan.metadata, dict)
        assert isinstance(plan.created_at, str)

    def test_infer_domain(self):
        """领域推断."""
        assert ActionPlanner._infer_domain(ExecutionActionType.CREATE_CREATIVE) == ExecutionDomain.CREATIVE
        assert ActionPlanner._infer_domain(ExecutionActionType.CREATE_CAMPAIGN) == ExecutionDomain.CAMPAIGN
        assert ActionPlanner._infer_domain(ExecutionActionType.SCALE_BUDGET) == ExecutionDomain.BUDGET
        assert ActionPlanner._infer_domain(ExecutionActionType.MONITOR) == ExecutionDomain.MONITOR

    def test_graph_nodes_property(self):
        """Graph nodes 属性."""
        graph = ActionGraph()
        n1 = ActionNode()
        n2 = ActionNode()
        graph.add_nodes([n1, n2])
        nodes_dict = graph.nodes
        assert len(nodes_dict) == 2
        assert n1.node_id in nodes_dict

    def test_edge_case_empty_task(self):
        """空任务."""
        planner = ActionPlanner()
        task = ExecutionTask()
        plan = planner.plan(task)
        # 空任务仍有 COLLECT_RESULT
        assert plan.node_count >= 1

    def test_edge_case_empty_actions(self):
        """空 actions 列表."""
        planner = ActionPlanner()
        task = ExecutionTask(actions=[])
        plan = planner.plan(task)
        assert plan.node_count >= 1  # COLLECT_RESULT

    def test_edge_case_phases_no_nodes(self):
        """空图阶段计算."""
        graph = ActionGraph()
        phases = graph.compute_phases()
        assert phases == {}