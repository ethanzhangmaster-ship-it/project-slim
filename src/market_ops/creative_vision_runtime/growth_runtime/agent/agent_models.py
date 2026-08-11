"""E13.7.1 Agent Models — 自主增长 Agent 核心数据模型.

定义 GrowthAgent 的完整数据模型:
  - AgentPhase: Agent 生命周期阶段
  - AgentGoal: Agent 目标
  - Observation: 环境观察
  - Insight: 推理洞察
  - GrowthPlan: 增长计划
  - AgentContext: Agent 上下文
  - AgentProfile: Agent 人格配置

连接:
  E13.7 Agent Core → Observer → Reasoner → Planner → Executor → Learner
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Agent Phase
# ═══════════════════════════════════════════════════════════════


class AgentPhase(str, Enum):
    """Agent 生命周期阶段.

    IDLE → OBSERVING → REASONING → PLANNING → EXECUTING → LEARNING → IDLE
    """
    IDLE = "idle"
    OBSERVING = "observing"
    REASONING = "reasoning"
    PLANNING = "planning"
    EXECUTING = "executing"
    LEARNING = "learning"
    WAITING = "waiting"      # 等待外部数据/审批
    ERROR = "error"


class GoalStatus(str, Enum):
    """目标状态."""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GoalPriority(str, Enum):
    """目标优先级."""
    CRITICAL = "critical"    # 紧急: ROAS 骤降
    HIGH = "high"            # 高: 素材疲劳
    MEDIUM = "medium"        # 中: 优化机会
    LOW = "low"              # 低: 实验


class InsightType(str, Enum):
    """洞察类型."""
    OPPORTUNITY = "opportunity"    # 发现机会
    THREAT = "threat"              # 发现威胁
    PATTERN = "pattern"            # 发现模式
    ANOMALY = "anomaly"            # 发现异常
    CONFIRMATION = "confirmation"  # 确认已有假设
    REJECTION = "rejection"        # 否定已有假设


class PlanStatus(str, Enum):
    """计划状态."""
    DRAFT = "draft"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ═══════════════════════════════════════════════════════════════
# Agent Goal
# ═══════════════════════════════════════════════════════════════


@dataclass
class AgentGoal:
    """Agent 目标 — 描述 Agent 要达成的目标.

    Attributes:
        goal_id: 目标 ID
        title: 目标标题
        description: 目标描述
        priority: 优先级
        status: 目标状态
        success_criteria: 成功标准 (可量化指标)
        target_metric: 目标指标名称
        target_value: 目标值
        current_value: 当前值
        deadline: 截止时间
        parent_goal_id: 父目标 ID
        sub_goals: 子目标列表
        created_at: 创建时间
        completed_at: 完成时间
        metadata: 扩展元数据
    """
    goal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    priority: GoalPriority = GoalPriority.MEDIUM
    status: GoalStatus = GoalStatus.PENDING
    success_criteria: str = ""
    target_metric: str = ""
    target_value: float = 0.0
    current_value: float = 0.0
    deadline: str = ""
    parent_goal_id: str = ""
    sub_goals: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def progress(self) -> float:
        """目标进度 [0, 1]."""
        if self.target_value == 0:
            return 0.0
        return min(1.0, max(0.0, self.current_value / self.target_value))

    @property
    def is_overdue(self) -> bool:
        if not self.deadline:
            return False
        return datetime.now(timezone.utc).isoformat() > self.deadline

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "success_criteria": self.success_criteria,
            "target_metric": self.target_metric,
            "target_value": self.target_value,
            "current_value": self.current_value,
            "progress": round(self.progress, 4),
            "deadline": self.deadline,
            "parent_goal_id": self.parent_goal_id,
            "sub_goals": self.sub_goals,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Observation
# ═══════════════════════════════════════════════════════════════


@dataclass
class Observation:
    """环境观察 — Agent 对外部世界的感知.

    Attributes:
        observation_id: 观察 ID
        phase: 观察所处的 Agent 阶段
        source: 数据来源
        data: 观察数据
        summary: 观察摘要
        significance: 重要性评分 [0, 1]
        timestamp: 观察时间
        metadata: 扩展元数据
    """
    observation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    phase: AgentPhase = AgentPhase.OBSERVING
    source: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    significance: float = 0.5
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "phase": self.phase.value,
            "source": self.source,
            "data": self.data,
            "summary": self.summary,
            "significance": self.significance,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Insight
# ═══════════════════════════════════════════════════════════════


@dataclass
class Insight:
    """推理洞察 — Agent 推理产出.

    Attributes:
        insight_id: 洞察 ID
        insight_type: 洞察类型
        title: 洞察标题
        description: 洞察描述
        reasoning: 推理过程 (Chain of Thought)
        confidence: 置信度 [0, 1]
        evidence: 支撑证据
        related_observations: 关联的观察 ID
        related_memories: 关联的记忆 ID
        suggested_action: 建议行动
        urgency: 紧急程度 [0, 1]
        timestamp: 洞察时间
        metadata: 扩展元数据
    """
    insight_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    insight_type: InsightType = InsightType.OPPORTUNITY
    title: str = ""
    description: str = ""
    reasoning: str = ""
    confidence: float = 0.5
    evidence: list[str] = field(default_factory=list)
    related_observations: list[str] = field(default_factory=list)
    related_memories: list[str] = field(default_factory=list)
    suggested_action: str = ""
    urgency: float = 0.5
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "insight_type": self.insight_type.value,
            "title": self.title,
            "description": self.description,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "related_observations": self.related_observations,
            "related_memories": self.related_memories,
            "suggested_action": self.suggested_action,
            "urgency": self.urgency,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Growth Plan
# ═══════════════════════════════════════════════════════════════


@dataclass
class GrowthPlan:
    """增长计划 — Agent 规划产出.

    Attributes:
        plan_id: 计划 ID
        goal_id: 关联的目标 ID
        title: 计划标题
        description: 计划描述
        strategy: 采用的策略
        actions: 要执行的动作列表
        expected_outcome: 预期结果
        expected_metrics: 预期指标变化
        budget: 预算分配
        risk_level: 风险等级
        confidence: 置信度
        status: 计划状态
        timeline: 时间线
        dependencies: 依赖关系
        rollback_plan: 回滚计划
        created_at: 创建时间
        metadata: 扩展元数据
    """
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal_id: str = ""
    title: str = ""
    description: str = ""
    strategy: str = ""
    actions: list[dict[str, Any]] = field(default_factory=list)
    expected_outcome: str = ""
    expected_metrics: dict[str, float] = field(default_factory=dict)
    budget: float = 0.0
    risk_level: str = "safe"
    confidence: float = 0.5
    status: PlanStatus = PlanStatus.DRAFT
    timeline: list[dict[str, str]] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    rollback_plan: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal_id": self.goal_id,
            "title": self.title,
            "description": self.description,
            "strategy": self.strategy,
            "actions": self.actions,
            "expected_outcome": self.expected_outcome,
            "expected_metrics": self.expected_metrics,
            "budget": self.budget,
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "status": self.status.value,
            "timeline": self.timeline,
            "dependencies": self.dependencies,
            "rollback_plan": self.rollback_plan,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Agent Context
# ═══════════════════════════════════════════════════════════════


@dataclass
class AgentContext:
    """Agent 上下文 — 当前会话的完整上下文.

    Attributes:
        session_id: 会话 ID
        profile: Agent 人格配置
        phase: 当前阶段
        active_goals: 活动目标
        recent_observations: 最近观察
        recent_insights: 最近洞察
        active_plans: 活动计划
        metrics_snapshot: 当前指标快照
        cycle_count: 循环计数
        started_at: 会话开始时间
        last_active_at: 最后活跃时间
        metadata: 扩展元数据
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    profile: AgentProfile | None = None
    phase: AgentPhase = AgentPhase.IDLE
    active_goals: list[AgentGoal] = field(default_factory=list)
    recent_observations: list[Observation] = field(default_factory=list)
    recent_insights: list[Insight] = field(default_factory=list)
    active_plans: list[GrowthPlan] = field(default_factory=list)
    metrics_snapshot: dict[str, Any] = field(default_factory=dict)
    cycle_count: int = 0
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_active_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "phase": self.phase.value,
            "active_goals": [g.to_dict() for g in self.active_goals],
            "recent_observation_count": len(self.recent_observations),
            "recent_insight_count": len(self.recent_insights),
            "active_plan_count": len(self.active_plans),
            "metrics_snapshot": self.metrics_snapshot,
            "cycle_count": self.cycle_count,
            "started_at": self.started_at,
            "last_active_at": self.last_active_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Agent Profile
# ═══════════════════════════════════════════════════════════════


@dataclass
class AgentProfile:
    """Agent 人格配置 — 定义 Agent 的行为特征.

    Attributes:
        name: Agent 名称
        role: 角色描述
        expertise: 专业领域
        risk_tolerance: 风险容忍度 [0, 1]
        autonomy_level: 自主程度 [0, 1]
        max_cycle_budget: 单次循环最大预算
        observation_interval_minutes: 观察间隔 (分钟)
        max_active_goals: 最大活动目标数
        allowed_actions: 允许的动作类型
        require_approval_for: 需要审批的动作类型
        reasoning_model: 推理模型配置
        metadata: 扩展元数据
    """
    name: str = "GrowthAgent"
    role: str = "AI Growth Operator"
    expertise: list[str] = field(default_factory=lambda: [
        "user_acquisition",
        "creative_optimization",
        "budget_allocation",
        "campaign_management",
    ])
    risk_tolerance: float = 0.5
    autonomy_level: float = 0.7
    max_cycle_budget: float = 5000.0
    observation_interval_minutes: int = 60
    max_active_goals: int = 5
    allowed_actions: list[str] = field(default_factory=lambda: [
        "create_campaign",
        "update_budget",
        "pause_campaign",
        "resume_campaign",
        "create_creative",
        "mutate_creative",
        "generate_creative",
        "upload_creative",
        "query_metrics",
        "query_adjust",
        "query_creative_performance",
        "check_fatigue",
        "query_memory",
        "update_memory",
        "record_episode",
        "monitor",
        "collect_result",
        "wait",
    ])
    require_approval_for: list[str] = field(default_factory=lambda: [
        "scale_budget",
        "batch_create",
        "batch_scale",
    ])
    reasoning_model: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "expertise": self.expertise,
            "risk_tolerance": self.risk_tolerance,
            "autonomy_level": self.autonomy_level,
            "max_cycle_budget": self.max_cycle_budget,
            "observation_interval_minutes": self.observation_interval_minutes,
            "max_active_goals": self.max_active_goals,
            "allowed_actions": self.allowed_actions,
            "require_approval_for": self.require_approval_for,
            "reasoning_model": self.reasoning_model,
            "metadata": self.metadata,
        }


def create_growth_agent_profile() -> AgentProfile:
    """创建默认 Growth Agent 配置."""
    return AgentProfile(
        name="GrowthAgent",
        role="AI Growth Operator",
        risk_tolerance=0.5,
        autonomy_level=0.7,
    )


def create_aggressive_agent_profile() -> AgentProfile:
    """创建激进型 Agent 配置 (高风险容忍)."""
    return AgentProfile(
        name="AggressiveGrowthAgent",
        role="Aggressive AI Growth Operator",
        risk_tolerance=0.8,
        autonomy_level=0.9,
        max_cycle_budget=10000.0,
        observation_interval_minutes=30,
    )


def create_conservative_agent_profile() -> AgentProfile:
    """创建保守型 Agent 配置 (低风险容忍)."""
    return AgentProfile(
        name="ConservativeGrowthAgent",
        role="Conservative AI Growth Operator",
        risk_tolerance=0.2,
        autonomy_level=0.3,
        max_cycle_budget=1000.0,
        observation_interval_minutes=120,
        require_approval_for=[
            "scale_budget", "batch_create", "batch_scale",
            "create_campaign", "update_budget",
        ],
    )