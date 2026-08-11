"""E13.6.2 Action Planner — 动作规划引擎.

将 ExecutionTask 中的原子动作自动展开为可执行的 Action Graph，包含:
  1. 模板展开: 将高层动作展开为子动作序列
  2. 依赖注入: 自动建立动作间的前置/后置条件
  3. 规则注入: 高风险动作添加审批、预算变化添加监控
  4. 回滚规划: 为关键动作生成回滚路径

核心流程:
  ExecutionTask
      ↓
  ActionPlanner.plan()
      ↓
  ActionGraph.build_from_nodes()
      ↓
  ActionPlan (有序节点 + 依赖 + 回滚)

连接:
  E13.6.1 ExecutionTask → E13.6.2 ActionPlanner → E13.6.2 ActionPlan
"""

from __future__ import annotations

from typing import Any

from .action_graph import ActionGraph
from .action_models import (
    ActionDependency,
    ActionNode,
    ActionPlan,
    ActionStatus,
    ActionTemplate,
    PlanPhase,
)
from .models import (
    ExecutionAction,
    ExecutionActionType,
    ExecutionDomain,
    ExecutionPriority,
    ExecutionStatus,
    ExecutionTask,
)


class ActionPlanner:
    """动作规划器 — 将 ExecutionTask 展开为有序 ActionPlan.

    用法:
        planner = ActionPlanner()
        plan = planner.plan(task)
        for node in plan.get_ordered_nodes():
            print(f"{node.node_id}: {node.action.action_type.value}")
    """

    # ── 模板注册表 ────────────────────────────────────────────

    _templates: dict[ExecutionActionType, ActionTemplate] = {}

    # ── 规则配置 ──────────────────────────────────────────────

    high_risk_threshold: float = 0.8
    auto_add_monitor: bool = True
    auto_add_verify: bool = True
    auto_add_rollback: bool = True

    def __init__(self):
        self._init_templates()

    # ═══════════════════════════════════════════════════════════
    # 主入口
    # ═══════════════════════════════════════════════════════════

    def plan(self, task: ExecutionTask) -> ActionPlan:
        """将 ExecutionTask 规划为 ActionPlan.

        Args:
            task: E13.6.1 执行任务

        Returns:
            ActionPlan: 有序执行计划
        """
        # 1. 展开所有 Action
        nodes = self._expand_task(task)

        # 2. 注入规则 (审批/监控/验证)
        nodes = self._inject_rules(nodes, task)

        # 3. 构建图
        graph = ActionGraph()
        graph.build_from_nodes(nodes)

        # 4. 拓扑排序
        order = graph.phase_ordered_sort()

        # 5. 构建 ActionPlan
        plan = ActionPlan(task_id=task.task_id)
        plan.nodes = nodes
        plan.set_execution_order(order)
        plan.phases = graph.compute_phases()
        plan.estimate_duration()

        # 6. 生成回滚顺序
        if self.auto_add_rollback:
            plan.rollback_order = self._build_rollback_order(nodes, order)

        return plan

    # ═══════════════════════════════════════════════════════════
    # 模板系统
    # ═══════════════════════════════════════════════════════════

    def _init_templates(self) -> None:
        """初始化动作模板."""
        # ── Creative Mutation ──
        self.register_template(ActionTemplate(
            action_type=ExecutionActionType.MUTATE_CREATIVE,
            name="Creative Mutation",
            expansion=[
                ExecutionActionType.CREATE_CREATIVE,
                ExecutionActionType.UPLOAD_CREATIVE,
                ExecutionActionType.CREATE_CAMPAIGN,
                ExecutionActionType.MONITOR,
            ],
            preconditions=["creative_dna_available"],
            postconditions=["creative_uploaded", "campaign_created"],
            requires_monitoring=True,
            estimated_duration_minutes=60,
            phase=PlanPhase.PREPARE,
        ))

        # ── Upload Creative ──
        self.register_template(ActionTemplate(
            action_type=ExecutionActionType.UPLOAD_CREATIVE,
            name="Upload Creative",
            expansion=[
                ExecutionActionType.MONITOR,
            ],
            preconditions=["creative_generated"],
            postconditions=["creative_uploaded"],
            estimated_duration_minutes=15,
            phase=PlanPhase.EXECUTE,
        ))

        # ── Create Campaign ──
        self.register_template(ActionTemplate(
            action_type=ExecutionActionType.CREATE_CAMPAIGN,
            name="Create Campaign",
            expansion=[
                ExecutionActionType.MONITOR,
            ],
            preconditions=["creative_uploaded", "budget_allocated"],
            postconditions=["campaign_active"],
            estimated_duration_minutes=30,
            phase=PlanPhase.EXECUTE,
        ))

        # ── Scale Budget ──
        self.register_template(ActionTemplate(
            action_type=ExecutionActionType.SCALE_BUDGET,
            name="Scale Budget",
            expansion=[
                ExecutionActionType.UPDATE_BUDGET,
                ExecutionActionType.MONITOR,
            ],
            preconditions=["risk_checked"],
            postconditions=["budget_updated"],
            requires_monitoring=True,
            estimated_duration_minutes=20,
            phase=PlanPhase.EXECUTE,
        ))

        # ── Update Budget ──
        self.register_template(ActionTemplate(
            action_type=ExecutionActionType.UPDATE_BUDGET,
            name="Update Budget",
            expansion=[
                ExecutionActionType.MONITOR,
            ],
            preconditions=["budget_validated"],
            postconditions=["budget_updated"],
            estimated_duration_minutes=15,
            phase=PlanPhase.EXECUTE,
        ))

        # ── Pause Campaign ──
        self.register_template(ActionTemplate(
            action_type=ExecutionActionType.PAUSE_CAMPAIGN,
            name="Pause Campaign",
            expansion=[
                ExecutionActionType.FREEZE_CAMPAIGN,
                ExecutionActionType.MONITOR,
            ],
            preconditions=["campaign_active"],
            postconditions=["campaign_paused"],
            estimated_duration_minutes=10,
            phase=PlanPhase.EXECUTE,
        ))

        # ── Monitor ──
        self.register_template(ActionTemplate(
            action_type=ExecutionActionType.MONITOR,
            name="Monitor",
            expansion=[],
            postconditions=["metrics_collected"],
            requires_monitoring=False,
            estimated_duration_minutes=5,
            phase=PlanPhase.MONITOR,
        ))

        # ── Collect Result ──
        self.register_template(ActionTemplate(
            action_type=ExecutionActionType.COLLECT_RESULT,
            name="Collect Result",
            expansion=[],
            postconditions=["result_collected"],
            estimated_duration_minutes=5,
            phase=PlanPhase.VERIFY,
        ))

    def register_template(self, template: ActionTemplate) -> None:
        """注册动作模板."""
        self._templates[template.action_type] = template

    def get_template(self, action_type: ExecutionActionType) -> ActionTemplate | None:
        """获取动作模板."""
        return self._templates.get(action_type)

    # ═══════════════════════════════════════════════════════════
    # 展开逻辑
    # ═══════════════════════════════════════════════════════════

    def _expand_task(self, task: ExecutionTask) -> list[ActionNode]:
        """展开 ExecutionTask 中的所有 Action.

        Args:
            task: 执行任务

        Returns:
            list[ActionNode]: 展开后的节点列表
        """
        all_nodes: list[ActionNode] = []

        for action in task.actions:
            expanded = self._expand_action(action)
            all_nodes.extend(expanded)

        # 建立节点间依赖关系
        self._link_dependencies(all_nodes)

        return all_nodes

    def _expand_action(self, action: ExecutionAction) -> list[ActionNode]:
        """展开单个 Action.

        Args:
            action: 执行动作

        Returns:
            list[ActionNode]: 展开后的节点列表 (1 个原始节点 + N 个子节点)
        """
        template = self.get_template(action.action_type)
        nodes: list[ActionNode] = []

        # 始终创建原始动作节点
        original_node = ActionNode(
            action=action,
            priority=action.priority,
            phase=template.phase if template else PlanPhase.EXECUTE,
        )
        nodes.append(original_node)

        if template and template.expansion:
            # 有模板: 展开为子动作序列，依赖原始节点
            prev_node_id = original_node.node_id

            for i, sub_action_type in enumerate(template.expansion):
                sub_action = ExecutionAction(
                    action_type=sub_action_type,
                    domain=self._infer_domain(sub_action_type),
                    target_entity=action.target_entity,
                    target_entity_type=action.target_entity_type,
                    parameters=action.parameters,
                    priority=action.priority,
                )
                node = ActionNode(
                    action=sub_action,
                    phase=template.phase,
                    priority=action.priority,
                    preconditions=list(template.preconditions) if i == 0 else [],
                    postconditions=list(template.postconditions) if i == len(template.expansion) - 1 else [],
                )
                node.add_dependency(prev_node_id, ActionDependency.REQUIRED)
                prev_node_id = node.node_id
                nodes.append(node)

        return nodes

    def _link_dependencies(self, nodes: list[ActionNode]) -> None:
        """自动建立节点间依赖关系.

        规则:
          - 同阶段节点: 按顺序建立 REQUIRED 依赖
          - 跨阶段节点: PREPARE → EXECUTE → VERIFY → MONITOR
        """
        phase_order = {
            PlanPhase.PREPARE: 0,
            PlanPhase.EXECUTE: 1,
            PlanPhase.VERIFY: 2,
            PlanPhase.MONITOR: 3,
        }

        # 按阶段分组
        phases: dict[PlanPhase, list[ActionNode]] = {}
        for node in nodes:
            phases.setdefault(node.phase, []).append(node)

        # 跨阶段依赖: 前一阶段最后一个 → 后一阶段第一个
        sorted_phases = sorted(phases.keys(), key=lambda p: phase_order.get(p, 99))
        for i in range(len(sorted_phases) - 1):
            prev_phase_nodes = phases[sorted_phases[i]]
            next_phase_nodes = phases[sorted_phases[i + 1]]
            if prev_phase_nodes and next_phase_nodes:
                last_of_prev = prev_phase_nodes[-1]
                first_of_next = next_phase_nodes[0]
                if first_of_next.node_id not in last_of_prev.dependencies:
                    # 只在没有直接依赖时添加跨阶段依赖
                    first_of_next.add_dependency(last_of_prev.node_id, ActionDependency.REQUIRED)

    # ═══════════════════════════════════════════════════════════
    # 规则注入
    # ═══════════════════════════════════════════════════════════

    def _inject_rules(
        self,
        nodes: list[ActionNode],
        task: ExecutionTask,
    ) -> list[ActionNode]:
        """注入规划规则.

        规则:
          1. 高风险任务 → 添加审批节点
          2. 预算变化 → 添加监控节点
          3. 素材上传 → 添加质量检查节点
          4. 所有任务 → 添加结果收集节点 (尾部)
        """
        # Rule 1: 高风险 → 审批
        if task.risk_level in {"high", "critical"}:
            approval_node = self._create_approval_node(task)
            # 插入到第一个 EXECUTE 节点之前
            nodes = self._insert_before_phase(nodes, approval_node, PlanPhase.EXECUTE)

        # Rule 2: 预算变化 → 自动监控
        if self.auto_add_monitor:
            has_budget_action = any(
                n.action.action_type in {
                    ExecutionActionType.SCALE_BUDGET,
                    ExecutionActionType.UPDATE_BUDGET,
                    ExecutionActionType.REDUCE_BUDGET,
                }
                for n in nodes
            )
            if has_budget_action:
                # 确保有监控节点
                has_monitor = any(
                    n.action.action_type == ExecutionActionType.MONITOR
                    for n in nodes
                )
                if not has_monitor:
                    monitor_node = self._create_monitor_node(task)
                    nodes.append(monitor_node)

        # Rule 3: 素材上传 → 质量检查
        if self.auto_add_verify:
            has_upload = any(
                n.action.action_type == ExecutionActionType.UPLOAD_CREATIVE
                for n in nodes
            )
            if has_upload:
                verify_node = self._create_verify_node(task)
                # 插入到 UPLOAD_CREATIVE 之后
                nodes = self._insert_after_action(nodes, verify_node, ExecutionActionType.UPLOAD_CREATIVE)

        # Rule 4: 尾部添加结果收集
        collect_node = self._create_collect_node(task)
        nodes.append(collect_node)

        return nodes

    def _insert_before_phase(
        self,
        nodes: list[ActionNode],
        new_node: ActionNode,
        target_phase: PlanPhase,
    ) -> list[ActionNode]:
        """在指定阶段的第一个节点之前插入新节点."""
        result: list[ActionNode] = []
        inserted = False
        for node in nodes:
            if not inserted and node.phase == target_phase:
                # 建立依赖: new_node → node
                node.add_dependency(new_node.node_id, ActionDependency.REQUIRED)
                result.append(new_node)
                inserted = True
            result.append(node)
        if not inserted:
            result.append(new_node)
        return result

    def _insert_after_action(
        self,
        nodes: list[ActionNode],
        new_node: ActionNode,
        after_type: ExecutionActionType,
    ) -> list[ActionNode]:
        """在指定类型的节点之后插入新节点."""
        result: list[ActionNode] = []
        for node in nodes:
            result.append(node)
            if node.action.action_type == after_type:
                new_node.add_dependency(node.node_id, ActionDependency.REQUIRED)
                result.append(new_node)
        return result

    # ═══════════════════════════════════════════════════════════
    # 节点工厂
    # ═══════════════════════════════════════════════════════════

    def _create_approval_node(self, task: ExecutionTask) -> ActionNode:
        """创建审批节点."""
        action = ExecutionAction(
            action_type=ExecutionActionType.MONITOR,
            domain=ExecutionDomain.MONITOR,
            parameters={"type": "approval_required", "reason": "high_risk"},
            priority=ExecutionPriority.CRITICAL,
        )
        return ActionNode(
            action=action,
            preconditions=["risk_validated"],
            postconditions=["approval_granted"],
            phase=PlanPhase.PREPARE,
            priority=ExecutionPriority.CRITICAL,
        )

    def _create_monitor_node(self, task: ExecutionTask) -> ActionNode:
        """创建监控节点."""
        action = ExecutionAction(
            action_type=ExecutionActionType.MONITOR,
            domain=ExecutionDomain.MONITOR,
            parameters={"duration_days": 3, "metrics": ["ctr", "cvr", "roas", "spend"]},
            priority=ExecutionPriority.MEDIUM,
        )
        return ActionNode(
            action=action,
            postconditions=["metrics_collected"],
            phase=PlanPhase.MONITOR,
            priority=ExecutionPriority.MEDIUM,
        )

    def _create_verify_node(self, task: ExecutionTask) -> ActionNode:
        """创建验证节点."""
        action = ExecutionAction(
            action_type=ExecutionActionType.MONITOR,
            domain=ExecutionDomain.MONITOR,
            parameters={"type": "quality_check", "check": "creative_validation"},
            priority=ExecutionPriority.MEDIUM,
        )
        return ActionNode(
            action=action,
            preconditions=["creative_uploaded"],
            postconditions=["creative_verified"],
            phase=PlanPhase.VERIFY,
            priority=ExecutionPriority.MEDIUM,
        )

    def _create_collect_node(self, task: ExecutionTask) -> ActionNode:
        """创建结果收集节点."""
        action = ExecutionAction(
            action_type=ExecutionActionType.COLLECT_RESULT,
            domain=ExecutionDomain.MONITOR,
            parameters={"task_id": task.task_id},
            priority=ExecutionPriority.LOW,
        )
        return ActionNode(
            action=action,
            postconditions=["result_collected"],
            phase=PlanPhase.MONITOR,
            priority=ExecutionPriority.LOW,
        )

    # ═══════════════════════════════════════════════════════════
    # 回滚规划
    # ═══════════════════════════════════════════════════════════

    def _build_rollback_order(
        self,
        nodes: list[ActionNode],
        execution_order: list[str],
    ) -> list[str]:
        """生成回滚顺序 (逆执行序)."""
        node_map = {n.node_id: n for n in nodes}

        # 只回滚有副作用的动作
        rollback_types = {
            ExecutionActionType.CREATE_CAMPAIGN,
            ExecutionActionType.UPDATE_CAMPAIGN,
            ExecutionActionType.SCALE_BUDGET,
            ExecutionActionType.UPDATE_BUDGET,
            ExecutionActionType.CREATE_AD_SET,
        }

        rollback_order: list[str] = []
        for node_id in reversed(execution_order):
            node = node_map.get(node_id)
            if node and node.action.action_type in rollback_types:
                rollback_order.append(node_id)

        return rollback_order

    # ═══════════════════════════════════════════════════════════
    # 辅助
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _infer_domain(action_type: ExecutionActionType) -> ExecutionDomain:
        """从动作类型推断执行领域."""
        creative_types = {
            ExecutionActionType.CREATE_CREATIVE,
            ExecutionActionType.UPLOAD_CREATIVE,
            ExecutionActionType.MUTATE_CREATIVE,
            ExecutionActionType.PAUSE_CREATIVE,
        }
        campaign_types = {
            ExecutionActionType.CREATE_CAMPAIGN,
            ExecutionActionType.UPDATE_CAMPAIGN,
            ExecutionActionType.PAUSE_CAMPAIGN,
            ExecutionActionType.CREATE_AD_SET,
            ExecutionActionType.FREEZE_CAMPAIGN,
        }
        budget_types = {
            ExecutionActionType.SCALE_BUDGET,
            ExecutionActionType.REDUCE_BUDGET,
            ExecutionActionType.UPDATE_BUDGET,
        }
        if action_type in creative_types:
            return ExecutionDomain.CREATIVE
        if action_type in campaign_types:
            return ExecutionDomain.CAMPAIGN
        if action_type in budget_types:
            return ExecutionDomain.BUDGET
        return ExecutionDomain.MONITOR