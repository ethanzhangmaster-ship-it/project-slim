"""E14.2.1 Goal Manager — 业务目标拆解与量化.

将人类自然语言 Business Goal 转换为可量化的 Agent 级子目标:

  输入: "本月利润提升30%"
  输出: {Revenue: +20%, ROAS: +15%, Retention: +10%, PayerRate: +8%}

设计原则:
  - 目标必须可量化 (metric + target_value)
  - 支持约束条件 (budget, risk, time)
  - 子目标必须有明确的责任 Agent
  - 目标进度可追踪
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..communication.agent_message import AgentRole


# ═══════════════════════════════════════════════════════════════
# Goal Models
# ═══════════════════════════════════════════════════════════════


class GoalType(str, Enum):
    """目标类型."""
    PROFIT = "profit"                # 利润
    REVENUE = "revenue"              # 收入
    ROAS = "roas"                    # 广告回报率
    RETENTION = "retention"          # 留存
    PAYER_RATE = "payer_rate"        # 付费率
    CPI = "cpi"                      # 单次安装成本
    LTV = "ltv"                      # 用户生命周期价值
    ARPU = "arpu"                    # 单用户平均收入
    SCALE = "scale"                   # 规模增长
    EFFICIENCY = "efficiency"        # 效率
    CUSTOM = "custom"                # 自定义


class GoalStatus(str, Enum):
    """目标状态."""
    DRAFT = "draft"                  # 草稿
    ACTIVE = "active"                # 执行中
    COMPLETED = "completed"          # 已完成
    FAILED = "failed"                # 失败
    CANCELLED = "cancelled"          # 已取消
    ON_HOLD = "on_hold"              # 暂停


@dataclass
class GoalConstraint:
    """目标约束条件.

    Attributes:
        max_budget: 最大预算
        max_risk_level: 最大风险等级 (0-1)
        deadline_days: 截止天数
        min_roas: 最小 ROAS 底线
        max_cpi: 最大 CPI
        allowed_roles: 允许参与的 Agent 角色
        blacklist_actions: 禁止的操作
        metadata: 扩展元数据
    """
    max_budget: float = 0.0
    max_risk_level: float = 0.5
    deadline_days: int = 30
    min_roas: float = 0.0
    max_cpi: float = 0.0
    allowed_roles: list[AgentRole] = field(default_factory=list)
    blacklist_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_budget": self.max_budget,
            "max_risk_level": self.max_risk_level,
            "deadline_days": self.deadline_days,
            "min_roas": self.min_roas,
            "max_cpi": self.max_cpi,
            "allowed_roles": [r.value for r in self.allowed_roles],
            "blacklist_actions": self.blacklist_actions,
            "metadata": self.metadata,
        }

    @classmethod
    def default(cls) -> GoalConstraint:
        """默认约束."""
        return cls(max_budget=100000, max_risk_level=0.5, deadline_days=30)

    @classmethod
    def aggressive(cls) -> GoalConstraint:
        """激进约束."""
        return cls(max_budget=500000, max_risk_level=0.7, deadline_days=14)

    @classmethod
    def conservative(cls) -> GoalConstraint:
        """保守约束."""
        return cls(max_budget=50000, max_risk_level=0.3, deadline_days=60)


@dataclass
class GrowthGoal:
    """增长目标 — 业务目标的量化表示.

    Attributes:
        goal_id: 目标 ID
        objective: 目标描述 (自然语言)
        goal_type: 目标类型
        target_value: 目标值 (0-1 表示百分比)
        current_value: 当前值
        metric: 核心指标
        status: 目标状态
        constraints: 约束条件
        parent_goal_id: 父目标 (层级分解)
        created_at: 创建时间
        deadline: 截止时间
        metadata: 扩展元数据
    """
    goal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    objective: str = ""
    goal_type: GoalType = GoalType.CUSTOM
    target_value: float = 0.0
    current_value: float = 0.0
    metric: str = ""
    status: GoalStatus = GoalStatus.DRAFT
    constraints: GoalConstraint = field(default_factory=GoalConstraint.default)
    parent_goal_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    deadline: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def progress(self) -> float:
        """目标进度 (0-1)."""
        if self.target_value == 0:
            return 0.0
        return min(self.current_value / self.target_value, 1.0)

    @property
    def gap(self) -> float:
        """目标差距."""
        return max(self.target_value - self.current_value, 0.0)

    @property
    def is_achieved(self) -> bool:
        return self.current_value >= self.target_value

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "objective": self.objective,
            "goal_type": self.goal_type.value,
            "target_value": self.target_value,
            "current_value": self.current_value,
            "metric": self.metric,
            "status": self.status.value,
            "constraints": self.constraints.to_dict(),
            "parent_goal_id": self.parent_goal_id,
            "progress": self.progress,
            "gap": self.gap,
            "is_achieved": self.is_achieved,
            "created_at": self.created_at,
            "deadline": self.deadline,
            "metadata": self.metadata,
        }


@dataclass
class SubGoal:
    """子目标 — 分配给特定 Agent 的量化目标.

    Attributes:
        sub_goal_id: 子目标 ID
        parent_goal_id: 父目标 ID
        agent_role: 负责的 Agent 角色
        goal_type: 目标类型
        target_value: 目标值
        metric: 核心指标
        hypothesis: 实现假设
        action_plan: 行动计划
        priority: 优先级 (0-1)
        expected_contribution: 预期贡献 (对父目标)
        status: 状态
        current_value: 当前值
        metadata: 扩展元数据
    """
    sub_goal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_goal_id: str = ""
    agent_role: AgentRole | None = None
    goal_type: GoalType = GoalType.CUSTOM
    target_value: float = 0.0
    metric: str = ""
    hypothesis: str = ""
    action_plan: str = ""
    priority: float = 0.5
    expected_contribution: float = 0.0
    status: GoalStatus = GoalStatus.DRAFT
    current_value: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def progress(self) -> float:
        if self.target_value == 0:
            return 0.0
        return min(self.current_value / self.target_value, 1.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sub_goal_id": self.sub_goal_id,
            "parent_goal_id": self.parent_goal_id,
            "agent_role": self.agent_role.value if self.agent_role else None,
            "goal_type": self.goal_type.value,
            "target_value": self.target_value,
            "metric": self.metric,
            "hypothesis": self.hypothesis,
            "action_plan": self.action_plan,
            "priority": self.priority,
            "expected_contribution": self.expected_contribution,
            "status": self.status.value,
            "current_value": self.current_value,
            "progress": self.progress,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Goal Decomposition Defaults
# ═══════════════════════════════════════════════════════════════


# 默认分解策略: 利润提升 → 各角色子目标
PROFIT_DECOMPOSITION: dict[AgentRole, list[dict[str, Any]]] = {
    AgentRole.UA: [
        {
            "goal_type": GoalType.ROAS,
            "target_ratio": 0.40,       # 占父目标 40%
            "metric": "roas",
            "hypothesis": "提高 ROAS 直接降低获客成本，增加利润",
            "action_plan": "优化受众定向、降低 CPI、放大高 ROAS 系列",
        },
        {
            "goal_type": GoalType.CPI,
            "target_ratio": 0.10,
            "metric": "cpi",
            "hypothesis": "降低 CPI 可同等预算下获取更多用户",
            "action_plan": "测试新素材、优化受众、调整出价策略",
        },
    ],
    AgentRole.CREATIVE: [
        {
            "goal_type": GoalType.REVENUE,
            "target_ratio": 0.25,
            "metric": "creative_revenue",
            "hypothesis": "新 winning DNA 可提升 CTR 和转化率",
            "action_plan": "检测疲劳素材、分析 winning DNA、生成变体",
        },
    ],
    AgentRole.MONETIZATION: [
        {
            "goal_type": GoalType.PAYER_RATE,
            "target_ratio": 0.15,
            "metric": "payer_rate",
            "hypothesis": "提高付费转化直接增加收入",
            "action_plan": "优化礼包、调整定价、增加限时活动",
        },
        {
            "goal_type": GoalType.ARPU,
            "target_ratio": 0.05,
            "metric": "arpu",
            "hypothesis": "提高 ARPU 增加单用户价值",
            "action_plan": "优化 IAP 瀑布流、测试新定价",
        },
    ],
    AgentRole.PRODUCT: [
        {
            "goal_type": GoalType.RETENTION,
            "target_ratio": 0.05,
            "metric": "d7_retention",
            "hypothesis": "提高留存增加用户 LTV",
            "action_plan": "优化 FTUE、调整关卡难度、增加活动",
        },
    ],
}

# 默认分解策略: ROAS 提升
ROAS_DECOMPOSITION: dict[AgentRole, list[dict[str, Any]]] = {
    AgentRole.UA: [
        {
            "goal_type": GoalType.CPI,
            "target_ratio": 0.50,
            "metric": "cpi",
            "hypothesis": "降低 CPI 是提高 ROAS 最直接手段",
            "action_plan": "优化受众定向、降低出价",
        },
        {
            "goal_type": GoalType.ROAS,
            "target_ratio": 0.20,
            "metric": "roas",
            "hypothesis": "放大高 ROAS 系列",
            "action_plan": "增加高 ROAS 系列预算",
        },
    ],
    AgentRole.CREATIVE: [
        {
            "goal_type": GoalType.REVENUE,
            "target_ratio": 0.30,
            "metric": "ctr",
            "hypothesis": "新素材提升 CTR 和转化率",
            "action_plan": "检测疲劳、生成新变体",
        },
    ],
}

# 默认分解策略: 规模增长
SCALE_DECOMPOSITION: dict[AgentRole, list[dict[str, Any]]] = {
    AgentRole.UA: [
        {
            "goal_type": GoalType.SCALE,
            "target_ratio": 0.60,
            "metric": "installs",
            "hypothesis": "扩大投放规模",
            "action_plan": "增加预算、拓展新渠道",
        },
    ],
    AgentRole.CREATIVE: [
        {
            "goal_type": GoalType.REVENUE,
            "target_ratio": 0.30,
            "metric": "creative_volume",
            "hypothesis": "更多素材支撑更大投放",
            "action_plan": "批量生产素材",
        },
    ],
    AgentRole.MONETIZATION: [
        {
            "goal_type": GoalType.LTV,
            "target_ratio": 0.10,
            "metric": "ltv",
            "hypothesis": "提高 LTV 支撑更高 CPI",
            "action_plan": "优化付费转化",
        },
    ],
}


# ═══════════════════════════════════════════════════════════════
# Goal Manager
# ═══════════════════════════════════════════════════════════════


class GoalManager:
    """目标管理器 — 将 Business Goal 拆解为 Agent 级子目标.

    职责:
      1. 解析自然语言目标
      2. 根据目标类型选择分解策略
      3. 生成量化子目标
      4. 追踪目标进度
      5. 动态调整子目标权重
    """

    # 预定义分解策略
    DECOMPOSITION_STRATEGIES: dict[GoalType, dict[AgentRole, list[dict[str, Any]]]] = {
        GoalType.PROFIT: PROFIT_DECOMPOSITION,
        GoalType.ROAS: ROAS_DECOMPOSITION,
        GoalType.SCALE: SCALE_DECOMPOSITION,
    }

    def __init__(self):
        self._goals: dict[str, GrowthGoal] = {}
        self._sub_goals: dict[str, list[SubGoal]] = defaultdict(list)

    # ── 目标创建 ──────────────────────────────────────────────

    def create_goal(
        self,
        objective: str,
        goal_type: GoalType = GoalType.PROFIT,
        target_value: float = 0.3,
        metric: str = "",
        constraints: GoalConstraint | None = None,
        deadline_days: int = 30,
    ) -> GrowthGoal:
        """创建增长目标.

        Args:
            objective: 目标描述 (e.g. "本月利润提升30%")
            goal_type: 目标类型
            target_value: 目标值
            metric: 核心指标
            constraints: 约束条件
            deadline_days: 截止天数

        Returns:
            GrowthGoal: 创建的目标
        """
        goal = GrowthGoal(
            objective=objective,
            goal_type=goal_type,
            target_value=target_value,
            metric=metric or goal_type.value,
            constraints=constraints or GoalConstraint.default(),
            deadline=(datetime.now(timezone.utc).isoformat() if deadline_days <= 0 else ""),
        )
        self._goals[goal.goal_id] = goal
        return goal

    def parse_goal_text(self, text: str) -> GrowthGoal:
        """解析自然语言目标.

        支持格式:
          - "利润提升30%"
          - "ROAS提升15%"
          - "规模增长50%"

        Returns:
            GrowthGoal: 解析后的目标
        """
        text_lower = text.lower()

        if "利润" in text or "profit" in text_lower:
            return self.create_goal(text, GoalType.PROFIT, target_value=0.3)
        elif "roas" in text_lower:
            return self.create_goal(text, GoalType.ROAS, target_value=0.15)
        elif "规模" in text or "scale" in text_lower:
            return self.create_goal(text, GoalType.SCALE, target_value=0.5)
        elif "留存" in text or "retention" in text_lower:
            return self.create_goal(text, GoalType.RETENTION, target_value=0.1)
        elif "付费" in text or "payer" in text_lower:
            return self.create_goal(text, GoalType.PAYER_RATE, target_value=0.1)
        elif "cpi" in text_lower:
            return self.create_goal(text, GoalType.CPI, target_value=-0.15)
        elif "ltv" in text_lower:
            return self.create_goal(text, GoalType.LTV, target_value=0.2)
        elif "arpu" in text_lower:
            return self.create_goal(text, GoalType.ARPU, target_value=0.1)
        else:
            return self.create_goal(text, GoalType.CUSTOM, target_value=0.2)

    # ── 目标分解 ──────────────────────────────────────────────

    def decompose(
        self,
        goal: GrowthGoal,
        strategy: dict[AgentRole, list[dict[str, Any]]] | None = None,
        target_roles: list[AgentRole] | None = None,
    ) -> list[SubGoal]:
        """将目标分解为 Agent 级子目标.

        Args:
            goal: 父目标
            strategy: 自定义分解策略 (None = 使用默认)
            target_roles: 目标角色 (None = 全部)

        Returns:
            子目标列表
        """
        decomposition = (
            strategy
            or self.DECOMPOSITION_STRATEGIES.get(goal.goal_type)
            or PROFIT_DECOMPOSITION
        )

        roles = target_roles or list(decomposition.keys())
        sub_goals = []

        for role in roles:
            if role not in decomposition:
                continue
            for task_spec in decomposition[role]:
                sub = SubGoal(
                    parent_goal_id=goal.goal_id,
                    agent_role=role,
                    goal_type=task_spec["goal_type"],
                    target_value=goal.target_value * task_spec["target_ratio"],
                    metric=task_spec["metric"],
                    hypothesis=task_spec.get("hypothesis", ""),
                    action_plan=task_spec.get("action_plan", ""),
                    expected_contribution=task_spec["target_ratio"],
                    priority=task_spec["target_ratio"],
                )
                sub_goals.append(sub)

        self._sub_goals[goal.goal_id] = sub_goals
        return sub_goals

    def decompose_goal(
        self,
        objective: str,
        goal_type: GoalType = GoalType.PROFIT,
        target_value: float = 0.3,
        constraints: GoalConstraint | None = None,
    ) -> tuple[GrowthGoal, list[SubGoal]]:
        """一站式: 创建目标 + 分解.

        Returns:
            (GrowthGoal, list[SubGoal])
        """
        goal = self.create_goal(
            objective=objective,
            goal_type=goal_type,
            target_value=target_value,
            constraints=constraints,
        )
        sub_goals = self.decompose(goal)
        return goal, sub_goals

    # ── 进度追踪 ──────────────────────────────────────────────

    def update_progress(self, goal_id: str, current_value: float) -> GrowthGoal | None:
        """更新目标进度."""
        goal = self._goals.get(goal_id)
        if not goal:
            return None
        goal.current_value = current_value
        if goal.is_achieved:
            goal.status = GoalStatus.COMPLETED
        return goal

    def update_sub_goal_progress(
        self, goal_id: str, sub_goal_id: str, current_value: float
    ) -> SubGoal | None:
        """更新子目标进度."""
        subs = self._sub_goals.get(goal_id, [])
        for sub in subs:
            if sub.sub_goal_id == sub_goal_id:
                sub.current_value = current_value
                if sub.progress >= 1.0:
                    sub.status = GoalStatus.COMPLETED
                return sub
        return None

    def get_goal_progress(self, goal_id: str) -> dict[str, Any]:
        """获取目标整体进度."""
        goal = self._goals.get(goal_id)
        if not goal:
            return {}

        subs = self._sub_goals.get(goal_id, [])
        sub_progress = {
            sub.agent_role.value if sub.agent_role else "unknown": {
                "progress": sub.progress,
                "status": sub.status.value,
                "contribution": sub.expected_contribution,
            }
            for sub in subs
        }

        weighted_progress = sum(
            sub.progress * sub.expected_contribution for sub in subs
        ) if subs else 0.0

        return {
            "goal_id": goal_id,
            "objective": goal.objective,
            "overall_progress": goal.progress,
            "weighted_progress": weighted_progress,
            "gap": goal.gap,
            "status": goal.status.value,
            "sub_goals": sub_progress,
            "sub_goal_count": len(subs),
        }

    # ── 查询 ──────────────────────────────────────────────────

    def get_goal(self, goal_id: str) -> GrowthGoal | None:
        return self._goals.get(goal_id)

    def get_sub_goals(self, goal_id: str) -> list[SubGoal]:
        return self._sub_goals.get(goal_id, [])

    def get_sub_goals_by_role(self, goal_id: str, role: AgentRole) -> list[SubGoal]:
        return [
            s for s in self.get_sub_goals(goal_id)
            if s.agent_role == role
        ]

    def get_active_goals(self) -> list[GrowthGoal]:
        return [g for g in self._goals.values() if g.status == GoalStatus.ACTIVE]

    def get_all_goals(self) -> list[GrowthGoal]:
        return list(self._goals.values())

    def activate_goal(self, goal_id: str) -> bool:
        goal = self._goals.get(goal_id)
        if not goal:
            return False
        goal.status = GoalStatus.ACTIVE
        return True

    def complete_goal(self, goal_id: str) -> bool:
        goal = self._goals.get(goal_id)
        if not goal:
            return False
        goal.status = GoalStatus.COMPLETED
        return True

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """目标管理统计."""
        total = len(self._goals)
        if total == 0:
            return {"total_goals": 0}

        status_counts = {}
        for g in self._goals.values():
            status_counts[g.status.value] = status_counts.get(g.status.value, 0) + 1

        total_subs = sum(len(s) for s in self._sub_goals.values())

        return {
            "total_goals": total,
            "total_sub_goals": total_subs,
            "status_counts": status_counts,
            "active_goals": status_counts.get("active", 0),
            "completed_goals": status_counts.get("completed", 0),
            "completion_rate": (
                status_counts.get("completed", 0) / total if total > 0 else 0
            ),
        }

    def reset(self) -> None:
        self._goals.clear()
        self._sub_goals.clear()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_goal_manager() -> GoalManager:
    return GoalManager()