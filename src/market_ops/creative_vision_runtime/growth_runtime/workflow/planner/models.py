"""E15.2.1 Planner Models — 执行计划数据模型.

定义:
  - WorkflowType:   Workflow 类型枚举
  - RiskLevel:      风险等级
  - PlanningTask:   规划任务 (模板展开后的任务描述)
  - ExecutionPlan:  执行计划 (Planner 主输出)
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


class WorkflowType(str, Enum):
    """E15.2.1 Workflow 类型 — 模板分类."""
    CREATIVE_REFRESH = "creative_refresh"
    CREATIVE_TEST = "creative_test"
    BUDGET_OPTIMIZE = "budget_optimize"
    CAMPAIGN_PAUSE = "campaign_pause"
    CAMPAIGN_SCALE = "campaign_scale"
    AUDIENCE_EXPAND = "audience_expand"
    REVENUE_OPTIMIZE = "revenue_optimize"
    MONITOR_ONLY = "monitor_only"
    CUSTOM = "custom"


class RiskLevel(str, Enum):
    """E15.2.1 风险等级."""
    NONE = "none"             # 无风险 (monitor)
    LOW = "low"               # 低风险 (creative refresh)
    MEDIUM = "medium"         # 中等风险 (budget adjust)
    HIGH = "high"             # 高风险 (scale)
    CRITICAL = "critical"     # 极高风险 (stop loss)


class PlanStatus(str, Enum):
    """E15.2.1 计划状态."""
    DRAFT = "draft"
    VALIDATED = "validated"
    REJECTED = "rejected"       # 规则验证不通过
    APPROVED = "approved"       # 人工审批通过
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


# ═══════════════════════════════════════════════════════════════
# Planning Task
# ═══════════════════════════════════════════════════════════════


@dataclass
class PlanningTask:
    """E15.2.1 规划任务 — 模板展开后的单个任务描述.

    Attributes:
        task_id:         任务唯一标识
        name:            任务名称
        action_type:     对应的执行动作类型
        adapter:         目标适配器 (e.g. "meta_ads", "lovart", "adjust")
        requires_approval: 是否需要审批
        parameters:      任务参数
        depends_on:      依赖的任务 ID 列表
        timeout_ms:      超时 (毫秒)
        retry_count:     最大重试次数
        phase:           所属阶段 (prepare/execute/verify/monitor/rollback)
        order:           执行顺序
        metadata:        扩展元数据
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    action_type: str = ""
    adapter: str = ""
    requires_approval: bool = False
    parameters: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    timeout_ms: int = 0
    retry_count: int = 0
    phase: str = "execute"
    order: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "action_type": self.action_type,
            "adapter": self.adapter,
            "requires_approval": self.requires_approval,
            "parameters": self.parameters,
            "depends_on": self.depends_on,
            "timeout_ms": self.timeout_ms,
            "retry_count": self.retry_count,
            "phase": self.phase,
            "order": self.order,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanningTask":
        return cls(
            task_id=data.get("task_id", str(uuid.uuid4())),
            name=data.get("name", ""),
            action_type=data.get("action_type", ""),
            adapter=data.get("adapter", ""),
            requires_approval=data.get("requires_approval", False),
            parameters=data.get("parameters", {}),
            depends_on=data.get("depends_on", []),
            timeout_ms=data.get("timeout_ms", 0),
            retry_count=data.get("retry_count", 0),
            phase=data.get("phase", "execute"),
            order=data.get("order", 0),
            metadata=data.get("metadata", {}),
        )


# ═══════════════════════════════════════════════════════════════
# Execution Plan
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExecutionPlan:
    """E15.2.1 执行计划 — Planner 的核心输出.

    将 Growth Opportunity 转换为结构化的执行计划，
    包含任务列表、风险评估、模板来源和记忆增强信息。

    Attributes:
        plan_id:          计划唯一标识
        opportunity_id:   来源机会 ID
        opportunity_type: 机会类型
        action_type:      执行动作类型
        workflow_type:    Workflow 模板类型
        template_name:    使用的模板名称
        tasks:            规划任务列表 (有序)
        confidence:       计划置信度
        risk_level:       风险等级
        status:           计划状态
        required_approval: 是否需要审批
        validation_errors: 规则验证错误列表
        warnings:         警告信息
        pattern_boost:    记忆增强 (是否有历史模式支持)
        pattern_score:    匹配模式评分
        pattern_success_rate: 历史模式成功率
        context:          执行上下文
        created_at:       创建时间
        metadata:         扩展元数据
    """
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    opportunity_id: str = ""
    opportunity_type: str = ""
    action_type: str = ""
    workflow_type: WorkflowType = WorkflowType.CUSTOM
    template_name: str = ""
    tasks: list[PlanningTask] = field(default_factory=list)
    confidence: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    status: PlanStatus = PlanStatus.DRAFT
    required_approval: bool = False
    validation_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pattern_boost: bool = False
    pattern_score: float = 0.0
    pattern_success_rate: float = 0.0
    context: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return len(self.validation_errors) == 0

    @property
    def is_approved(self) -> bool:
        return self.status == PlanStatus.APPROVED

    @property
    def task_count(self) -> int:
        return len(self.tasks)

    def get_tasks_by_phase(self, phase: str) -> list[PlanningTask]:
        return [t for t in self.tasks if t.phase == phase]

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "opportunity_id": self.opportunity_id,
            "opportunity_type": self.opportunity_type,
            "action_type": self.action_type,
            "workflow_type": self.workflow_type.value,
            "template_name": self.template_name,
            "tasks": [t.to_dict() for t in self.tasks],
            "confidence": self.confidence,
            "risk_level": self.risk_level.value,
            "status": self.status.value,
            "required_approval": self.required_approval,
            "validation_errors": self.validation_errors,
            "warnings": self.warnings,
            "pattern_boost": self.pattern_boost,
            "pattern_score": self.pattern_score,
            "pattern_success_rate": self.pattern_success_rate,
            "context": self.context,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionPlan":
        tasks = [PlanningTask.from_dict(t) for t in data.get("tasks", [])]
        return cls(
            plan_id=data.get("plan_id", str(uuid.uuid4())),
            opportunity_id=data.get("opportunity_id", ""),
            opportunity_type=data.get("opportunity_type", ""),
            action_type=data.get("action_type", ""),
            workflow_type=WorkflowType(data.get("workflow_type", "custom")),
            template_name=data.get("template_name", ""),
            tasks=tasks,
            confidence=data.get("confidence", 0.0),
            risk_level=RiskLevel(data.get("risk_level", "low")),
            status=PlanStatus(data.get("status", "draft")),
            required_approval=data.get("required_approval", False),
            validation_errors=data.get("validation_errors", []),
            warnings=data.get("warnings", []),
            pattern_boost=data.get("pattern_boost", False),
            pattern_score=data.get("pattern_score", 0.0),
            pattern_success_rate=data.get("pattern_success_rate", 0.0),
            context=data.get("context", {}),
            created_at=data.get("created_at", ""),
            metadata=data.get("metadata", {}),
        )


__all__ = [
    "WorkflowType",
    "RiskLevel",
    "PlanStatus",
    "PlanningTask",
    "ExecutionPlan",
]