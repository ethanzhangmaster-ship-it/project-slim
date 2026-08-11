"""E13.6.2 Action Models — 动作规划数据模型.

将 ExecutionTask 中的原子动作组织为可执行 Action Graph，包含依赖关系、前置/后置条件、
回滚路径和执行顺序。

核心模型:
  - ActionStatus: 动作节点状态枚举
  - ActionDependency: 依赖类型枚举 (REQUIRED/OPTIONAL/CONDITIONAL)
  - ActionNode: 执行图节点 (Action + 依赖 + 条件)
  - ActionPlan: 执行计划 (有序节点 + 回滚)
  - ActionTemplate: 动作模板 (展开规则)

连接:
  E13.6.1 ExecutionTask → E13.6.2 ActionPlanner → E13.6.2 ActionPlan
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .models import ExecutionAction, ExecutionActionType, ExecutionDomain, ExecutionPriority


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class ActionStatus(str, Enum):
    """动作节点状态."""
    PENDING = "pending"
    READY = "ready"           # 前置条件满足，可执行
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"       # 条件不满足，跳过
    ROLLED_BACK = "rolled_back"


class ActionDependency(str, Enum):
    """依赖类型 — 节点间关系.

    | REQUIRED    | 必须在前置节点成功后才可执行 |
    | OPTIONAL    | 前置节点完成即可执行 (失败也允许) |
    | CONDITIONAL | 前置节点满足特定条件才执行 |
    """
    REQUIRED = "required"
    OPTIONAL = "optional"
    CONDITIONAL = "conditional"


class PlanPhase(str, Enum):
    """规划阶段 — 执行计划的不同阶段."""
    PREPARE = "prepare"       # 准备阶段
    EXECUTE = "execute"       # 执行阶段
    VERIFY = "verify"         # 验证阶段
    MONITOR = "monitor"       # 监控阶段
    ROLLBACK = "rollback"     # 回滚阶段


# ═══════════════════════════════════════════════════════════════
# Action Node
# ═══════════════════════════════════════════════════════════════


@dataclass
class ActionNode:
    """执行图节点 — 将 ExecutionAction 包装为图节点.

    Attributes:
        node_id: 节点唯一标识
        action: 对应的 ExecutionAction
        dependencies: 依赖节点 ID → 依赖类型
        preconditions: 前置条件 (描述字符串)
        postconditions: 后置条件 (描述字符串)
        rollback_action: 回滚动作
        status: 节点状态
        phase: 所属阶段
        priority: 节点优先级
        retry_count: 当前重试次数
        max_retries: 最大重试次数
        metadata: 扩展元数据
    """
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action: ExecutionAction = field(default_factory=ExecutionAction)
    dependencies: dict[str, ActionDependency] = field(default_factory=dict)
    preconditions: list[str] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)
    rollback_action: ExecutionAction | None = None
    status: ActionStatus = ActionStatus.PENDING
    phase: PlanPhase = PlanPhase.EXECUTE
    priority: ExecutionPriority = ExecutionPriority.MEDIUM
    retry_count: int = 0
    max_retries: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "action": self.action.to_dict() if self.action else None,
            "dependencies": {k: v.value for k, v in self.dependencies.items()},
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "rollback_action": self.rollback_action.to_dict() if self.rollback_action else None,
            "status": self.status.value,
            "phase": self.phase.value,
            "priority": self.priority.value,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "metadata": self.metadata,
        }

    @property
    def is_ready(self) -> bool:
        return self.status == ActionStatus.READY

    @property
    def is_completed(self) -> bool:
        return self.status in {ActionStatus.SUCCESS, ActionStatus.SKIPPED}

    @property
    def has_dependencies(self) -> bool:
        return len(self.dependencies) > 0

    @property
    def required_dependencies(self) -> list[str]:
        return [k for k, v in self.dependencies.items() if v == ActionDependency.REQUIRED]

    def add_dependency(self, node_id: str, dep_type: ActionDependency = ActionDependency.REQUIRED) -> None:
        self.dependencies[node_id] = dep_type

    def add_precondition(self, condition: str) -> None:
        self.preconditions.append(condition)

    def add_postcondition(self, condition: str) -> None:
        self.postconditions.append(condition)

    def mark_ready(self) -> None:
        self.status = ActionStatus.READY

    def mark_running(self) -> None:
        self.status = ActionStatus.RUNNING

    def mark_success(self) -> None:
        self.status = ActionStatus.SUCCESS

    def mark_failed(self) -> None:
        self.status = ActionStatus.FAILED

    def mark_skipped(self) -> None:
        self.status = ActionStatus.SKIPPED

    def mark_rolled_back(self) -> None:
        self.status = ActionStatus.ROLLED_BACK


# ═══════════════════════════════════════════════════════════════
# Action Plan
# ═══════════════════════════════════════════════════════════════


@dataclass
class ActionPlan:
    """执行计划 — 将 ExecutionTask 展开为有序 Action Graph.

    Attributes:
        plan_id: 计划唯一标识
        task_id: 关联的 ExecutionTask ID
        nodes: 所有执行节点
        execution_order: 节点 ID 执行顺序
        phases: 各阶段节点 ID 列表
        estimated_duration_minutes: 预计执行时长 (分钟)
        rollback_enabled: 是否启用回滚
        rollback_order: 回滚节点 ID 顺序 (逆序)
        status: 计划状态
        created_at: 创建时间
        metadata: 扩展元数据
    """
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    nodes: list[ActionNode] = field(default_factory=list)
    execution_order: list[str] = field(default_factory=list)
    phases: dict[str, list[str]] = field(default_factory=dict)
    estimated_duration_minutes: int = 0
    rollback_enabled: bool = True
    rollback_order: list[str] = field(default_factory=list)
    status: ActionStatus = ActionStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "task_id": self.task_id,
            "nodes": [n.to_dict() for n in self.nodes],
            "execution_order": self.execution_order,
            "phases": self.phases,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "rollback_enabled": self.rollback_enabled,
            "rollback_order": self.rollback_order,
            "status": self.status.value,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def has_nodes(self) -> bool:
        return len(self.nodes) > 0

    def get_node(self, node_id: str) -> ActionNode | None:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def get_nodes_by_phase(self, phase: PlanPhase) -> list[ActionNode]:
        return [n for n in self.nodes if n.phase == phase]

    def get_ordered_nodes(self) -> list[ActionNode]:
        """按执行顺序返回节点."""
        node_map = {n.node_id: n for n in self.nodes}
        return [node_map[nid] for nid in self.execution_order if nid in node_map]

    def get_ready_nodes(self) -> list[ActionNode]:
        """获取所有就绪节点."""
        return [n for n in self.nodes if n.is_ready]

    def get_pending_nodes(self) -> list[ActionNode]:
        """获取所有待执行节点."""
        return [n for n in self.nodes if n.status == ActionStatus.PENDING]

    def add_node(self, node: ActionNode) -> None:
        self.nodes.append(node)

    def set_execution_order(self, order: list[str]) -> None:
        self.execution_order = order

    def estimate_duration(self) -> int:
        """估算执行时长 (分钟)."""
        # 每个节点预估 5-15 分钟
        total = sum(
            15 if n.action.priority == ExecutionPriority.HIGH else 10
            for n in self.nodes
        )
        self.estimated_duration_minutes = total
        return total


# ═══════════════════════════════════════════════════════════════
# Action Template
# ═══════════════════════════════════════════════════════════════


@dataclass
class ActionTemplate:
    """动作模板 — 定义单个动作类型的展开规则.

    Attributes:
        template_id: 模板唯一标识
        action_type: 匹配的动作类型
        name: 模板名称
        expansion: 展开后的子动作类型序列
        preconditions: 全局前置条件
        postconditions: 全局后置条件
        requires_approval: 是否需要审批
        requires_monitoring: 是否需要监控
        estimated_duration_minutes: 预估时长
        phase: 所属阶段
    """
    template_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: ExecutionActionType = ExecutionActionType.MONITOR
    name: str = ""
    expansion: list[ExecutionActionType] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)
    requires_approval: bool = False
    requires_monitoring: bool = True
    estimated_duration_minutes: int = 30
    phase: PlanPhase = PlanPhase.EXECUTE