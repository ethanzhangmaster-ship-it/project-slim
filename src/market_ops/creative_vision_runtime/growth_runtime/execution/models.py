"""E13.6.1 Execution Foundation — 执行层数据模型.

定义统一执行协议，将 Decision Engine 输出转换为可执行的 ExecutionTask。

核心模型:
  - ExecutionStatus: 任务状态枚举 (PENDING/RUNNING/SUCCESS/FAILED/CANCELLED/ROLLED_BACK)
  - ExecutionAction: 单个执行动作 (原子操作)
  - ExecutionTask: 执行任务 (决策 → 动作序列)
  - ExecutionPlan: 执行计划 (任务序列 + 依赖关系)

连接:
  E13.5.5 DecisionOutput → E13.6.1 ExecutionTask → E13.6.3 Campaign/Creative/Budget Executor
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class ExecutionStatus(str, Enum):
    """执行任务状态 — 任务生命周期.

    | Status      | 说明         |
    |-------------|-------------|
    | PENDING     | 等待执行      |
    | QUEUED      | 已入队        |
    | RUNNING     | 执行中        |
    | SUCCESS     | 执行成功      |
    | FAILED      | 执行失败      |
    | CANCELLED   | 已取消        |
    | ROLLED_BACK | 已回滚        |
    | TIMED_OUT   | 超时          |
    """
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"
    TIMED_OUT = "timed_out"


class ExecutionActionType(str, Enum):
    """执行动作类型 — 系统支持的操作类型.

    | Type              | 说明         |
    |-------------------|-------------|
    | CREATE_CAMPAIGN   | 创建广告系列   |
    | UPDATE_CAMPAIGN   | 更新广告系列   |
    | PAUSE_CAMPAIGN    | 暂停广告系列   |
    | CREATE_AD_SET     | 创建广告组    |
    | UPDATE_BUDGET     | 调整预算      |
    | CREATE_CREATIVE   | 创建素材      |
    | UPLOAD_CREATIVE   | 上传素材      |
    | MUTATE_CREATIVE   | 素材变异      |
    | PAUSE_CREATIVE    | 暂停素材      |
    | SCALE_BUDGET      | 放量         |
    | REDUCE_BUDGET     | 降预算        |
    | FREEZE_CAMPAIGN   | 冻结广告系列   |
    | MONITOR           | 监控         |
    | COLLECT_RESULT    | 收集结果      |
    """
    CREATE_CAMPAIGN = "create_campaign"
    UPDATE_CAMPAIGN = "update_campaign"
    PAUSE_CAMPAIGN = "pause_campaign"
    CREATE_AD_SET = "create_ad_set"
    UPDATE_BUDGET = "update_budget"
    CREATE_CREATIVE = "create_creative"
    UPLOAD_CREATIVE = "upload_creative"
    MUTATE_CREATIVE = "mutate_creative"
    PAUSE_CREATIVE = "pause_creative"
    SCALE_BUDGET = "scale_budget"
    REDUCE_BUDGET = "reduce_budget"
    FREEZE_CAMPAIGN = "freeze_campaign"
    MONITOR = "monitor"
    COLLECT_RESULT = "collect_result"


class ExecutionPriority(str, Enum):
    """执行优先级.

    | CRITICAL | 紧急: ROAS 骤降 / 预算浪费 |
    | HIGH     | 高: 素材疲劳 / 规模化机会 |
    | MEDIUM   | 中: 优化机会 |
    | LOW      | 低: 实验性动作 |
    """
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ExecutionDomain(str, Enum):
    """执行领域 — 指定执行器."""
    CAMPAIGN = "campaign"
    CREATIVE = "creative"
    BUDGET = "budget"
    MONITOR = "monitor"


# ═══════════════════════════════════════════════════════════════
# Execution Action
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExecutionAction:
    """单个执行动作 — 原子操作.

    Attributes:
        action_id: 动作唯一标识
        action_type: 动作类型
        domain: 执行领域
        target_entity: 目标实体 (campaign_id / creative_id / adset_id)
        target_entity_type: 目标实体类型
        parameters: 动作参数
        priority: 优先级
        max_retries: 最大重试次数
        retry_count: 当前重试次数
        timeout_seconds: 超时时间
        depends_on: 依赖的动作 ID 列表
        rollback_action_id: 回滚动作 ID
        status: 动作状态
        started_at: 开始时间
        completed_at: 完成时间
        error_message: 错误信息
        result: 执行结果
        metadata: 扩展元数据
    """
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: ExecutionActionType = ExecutionActionType.MONITOR
    domain: ExecutionDomain = ExecutionDomain.MONITOR
    target_entity: str = ""
    target_entity_type: str = "campaign"
    parameters: dict[str, Any] = field(default_factory=dict)
    priority: ExecutionPriority = ExecutionPriority.MEDIUM
    max_retries: int = 3
    retry_count: int = 0
    timeout_seconds: int = 300
    depends_on: list[str] = field(default_factory=list)
    rollback_action_id: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: str = ""
    completed_at: str = ""
    error_message: str = ""
    result: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "domain": self.domain.value,
            "target_entity": self.target_entity,
            "target_entity_type": self.target_entity_type,
            "parameters": self.parameters,
            "priority": self.priority.value,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "timeout_seconds": self.timeout_seconds,
            "depends_on": self.depends_on,
            "rollback_action_id": self.rollback_action_id,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
            "result": self.result,
            "metadata": self.metadata,
        }

    @property
    def is_pending(self) -> bool:
        return self.status == ExecutionStatus.PENDING

    @property
    def is_running(self) -> bool:
        return self.status == ExecutionStatus.RUNNING

    @property
    def is_completed(self) -> bool:
        return self.status in {ExecutionStatus.SUCCESS, ExecutionStatus.FAILED}

    @property
    def is_success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS

    @property
    def is_failed(self) -> bool:
        return self.status == ExecutionStatus.FAILED

    @property
    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries

    def mark_running(self) -> None:
        self.status = ExecutionStatus.RUNNING
        self.started_at = datetime.now(timezone.utc).isoformat()

    def mark_success(self, result: dict[str, Any] | None = None) -> None:
        self.status = ExecutionStatus.SUCCESS
        self.completed_at = datetime.now(timezone.utc).isoformat()
        if result:
            self.result = result

    def mark_failed(self, error: str = "") -> None:
        self.status = ExecutionStatus.FAILED
        self.completed_at = datetime.now(timezone.utc).isoformat()
        self.error_message = error

    def mark_cancelled(self, reason: str = "") -> None:
        self.status = ExecutionStatus.CANCELLED
        self.completed_at = datetime.now(timezone.utc).isoformat()
        if reason:
            self.error_message = reason


# ═══════════════════════════════════════════════════════════════
# Execution Task
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExecutionTask:
    """执行任务 — 将 Decision 转换为可执行的动作序列.

    一个 ExecutionTask 对应一个 GrowthDecision，包含多个有序的 ExecutionAction。

    Attributes:
        task_id: 任务唯一标识
        decision_id: 关联的决策 ID
        opportunity_id: 关联的机会 ID
        strategy_id: 关联的策略 ID
        strategy_name: 策略名称
        decision_type: 原始决策类型
        actions: 执行动作序列 (有序)
        status: 任务状态
        priority: 优先级
        requires_approval: 是否需要审批
        risk_level: 风险等级
        estimated_duration_hours: 预计执行时长 (小时)
        deadline: 截止时间
        started_at: 开始时间
        completed_at: 完成时间
        error_message: 错误信息
        rollback_plan: 回滚计划
        metadata: 扩展元数据
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = ""
    opportunity_id: str = ""
    strategy_id: str = ""
    strategy_name: str = ""
    decision_type: str = ""
    actions: list[ExecutionAction] = field(default_factory=list)
    status: ExecutionStatus = ExecutionStatus.PENDING
    priority: ExecutionPriority = ExecutionPriority.MEDIUM
    requires_approval: bool = False
    risk_level: str = "safe"
    estimated_duration_hours: float = 72.0
    deadline: str = ""
    started_at: str = ""
    completed_at: str = ""
    error_message: str = ""
    rollback_plan: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "decision_id": self.decision_id,
            "opportunity_id": self.opportunity_id,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "decision_type": self.decision_type,
            "actions": [a.to_dict() for a in self.actions],
            "status": self.status.value,
            "priority": self.priority.value,
            "requires_approval": self.requires_approval,
            "risk_level": self.risk_level,
            "estimated_duration_hours": self.estimated_duration_hours,
            "deadline": self.deadline,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
            "rollback_plan": self.rollback_plan,
            "metadata": self.metadata,
        }

    @property
    def is_pending(self) -> bool:
        return self.status == ExecutionStatus.PENDING

    @property
    def is_running(self) -> bool:
        return self.status == ExecutionStatus.RUNNING

    @property
    def is_completed(self) -> bool:
        return self.status in {ExecutionStatus.SUCCESS, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED}

    @property
    def is_success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS

    @property
    def is_failed(self) -> bool:
        return self.status == ExecutionStatus.FAILED

    @property
    def action_count(self) -> int:
        return len(self.actions)

    @property
    def has_actions(self) -> bool:
        return len(self.actions) > 0

    def get_pending_actions(self) -> list[ExecutionAction]:
        """获取待执行的 Action."""
        return [a for a in self.actions if a.is_pending]

    def get_failed_actions(self) -> list[ExecutionAction]:
        """获取失败的 Action."""
        return [a for a in self.actions if a.is_failed]

    def get_actions_by_domain(self, domain: ExecutionDomain) -> list[ExecutionAction]:
        """按领域获取 Action."""
        return [a for a in self.actions if a.domain == domain]

    def add_action(self, action: ExecutionAction) -> None:
        """添加动作."""
        self.actions.append(action)

    def mark_queued(self) -> None:
        self.status = ExecutionStatus.QUEUED

    def mark_running(self) -> None:
        self.status = ExecutionStatus.RUNNING
        self.started_at = datetime.now(timezone.utc).isoformat()

    def mark_success(self) -> None:
        self.status = ExecutionStatus.SUCCESS
        self.completed_at = datetime.now(timezone.utc).isoformat()

    def mark_failed(self, error: str = "") -> None:
        self.status = ExecutionStatus.FAILED
        self.completed_at = datetime.now(timezone.utc).isoformat()
        self.error_message = error

    def mark_cancelled(self, reason: str = "") -> None:
        self.status = ExecutionStatus.CANCELLED
        self.completed_at = datetime.now(timezone.utc).isoformat()
        if reason:
            self.error_message = reason

    def all_actions_completed(self) -> bool:
        """所有 Action 是否已完成."""
        if not self.actions:
            return False
        return all(a.is_completed for a in self.actions)

    def compute_overall_status(self) -> ExecutionStatus:
        """根据 Action 状态计算整体状态."""
        if not self.actions:
            return self.status

        if any(a.is_running for a in self.actions):
            return ExecutionStatus.RUNNING
        if all(a.is_success for a in self.actions):
            return ExecutionStatus.SUCCESS
        if any(a.is_failed for a in self.actions):
            return ExecutionStatus.FAILED
        if all(a.is_pending for a in self.actions):
            return ExecutionStatus.PENDING
        return self.status


# ═══════════════════════════════════════════════════════════════
# Execution Plan
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExecutionPlan:
    """执行计划 — 多个 ExecutionTask 的组合.

    将高层策略拆解为多步骤执行方案，包含任务间依赖关系。

    Attributes:
        plan_id: 计划唯一标识
        decision_id: 关联的决策 ID
        tasks: 执行任务列表 (有序)
        status: 计划状态
        total_actions: 总动作数
        completed_actions: 已完成动作数
        created_at: 创建时间
        metadata: 扩展元数据
    """
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = ""
    tasks: list[ExecutionTask] = field(default_factory=list)
    status: ExecutionStatus = ExecutionStatus.PENDING
    total_actions: int = 0
    completed_actions: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "decision_id": self.decision_id,
            "tasks": [t.to_dict() for t in self.tasks],
            "status": self.status.value,
            "total_actions": self.total_actions,
            "completed_actions": self.completed_actions,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @property
    def task_count(self) -> int:
        return len(self.tasks)

    @property
    def has_tasks(self) -> bool:
        return len(self.tasks) > 0

    @property
    def progress(self) -> float:
        """执行进度 [0, 1]."""
        if self.total_actions == 0:
            return 0.0
        return self.completed_actions / self.total_actions

    def add_task(self, task: ExecutionTask) -> None:
        self.tasks.append(task)
        self.total_actions += task.action_count

    def get_pending_tasks(self) -> list[ExecutionTask]:
        return [t for t in self.tasks if t.is_pending]

    def get_running_tasks(self) -> list[ExecutionTask]:
        return [t for t in self.tasks if t.is_running]

    def recompute_progress(self) -> None:
        """重新计算进度."""
        self.total_actions = sum(t.action_count for t in self.tasks)
        self.completed_actions = sum(
            sum(1 for a in t.actions if a.is_completed)
            for t in self.tasks
        )

    def compute_status(self) -> ExecutionStatus:
        """根据任务状态计算计划状态."""
        if not self.tasks:
            return ExecutionStatus.PENDING
        if any(t.is_running for t in self.tasks):
            return ExecutionStatus.RUNNING
        if all(t.is_success for t in self.tasks):
            return ExecutionStatus.SUCCESS
        if any(t.is_failed for t in self.tasks):
            return ExecutionStatus.FAILED
        if all(t.is_pending for t in self.tasks):
            return ExecutionStatus.PENDING
        return ExecutionStatus.PENDING