"""E13.7.4 Agent Policy System — 安全策略层.

Agent Policy 定义 Agent 在生产环境中的操作边界:
  - Level 0: 自动 — 分析、报告、建议
  - Level 1: 半自动 — 生成素材、调整小预算、暂停低效广告
  - Level 2: 人工确认 — 创建新 Campaign、增加预算 >30%、改变投放国家

Policy 确保 Agent 在安全边界内自主运行，不会无限自由。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PolicyLevel(int, Enum):
    """策略安全等级.

    Level 0: 全自动 — 分析、报告、建议 (零风险)
    Level 1: 半自动 — 小预算调整、素材生成、暂停低效广告 (低风险)
    Level 2: 人工确认 — 创建 Campaign、大预算变动、改变投放地区 (高风险)
    """
    AUTO = 0
    SEMI_AUTO = 1
    REQUIRE_APPROVAL = 2


class PolicyAction(str, Enum):
    """策略动作类型."""
    ALLOW = "allow"
    ALLOW_WITH_LIMIT = "allow_with_limit"
    REQUIRE_APPROVAL = "require_approval"
    BLOCK = "block"


@dataclass
class ActionRule:
    """单个动作的策略规则.

    Attributes:
        action_type: 动作类型
        level: 安全等级
        budget_limit: 预算上限 (仅 ALLOW_WITH_LIMIT 时生效)
        max_change_ratio: 最大变动比例 (仅 ALLOW_WITH_LIMIT 时生效)
        description: 规则说明
    """
    action_type: str
    level: PolicyLevel = PolicyLevel.REQUIRE_APPROVAL
    budget_limit: float = 0.0
    max_change_ratio: float = 0.0
    description: str = ""

    def evaluate(self, params: dict[str, Any] | None = None) -> PolicyAction:
        """评估动作是否允许执行.

        Args:
            params: 动作参数

        Returns:
            PolicyAction: 策略决策
        """
        params = params or {}

        if self.level == PolicyLevel.AUTO:
            return PolicyAction.ALLOW

        if self.level == PolicyLevel.SEMI_AUTO:
            # 检查预算限制
            budget = params.get("budget", 0)
            if self.budget_limit > 0 and budget > self.budget_limit:
                return PolicyAction.REQUIRE_APPROVAL

            # 检查变动比例
            change_ratio = params.get("change_ratio", 0)
            if self.max_change_ratio > 0 and abs(change_ratio) > self.max_change_ratio:
                return PolicyAction.REQUIRE_APPROVAL

            return PolicyAction.ALLOW_WITH_LIMIT

        return PolicyAction.REQUIRE_APPROVAL


@dataclass
class AgentPolicy:
    """Agent 安全策略 — 定义 Agent 的生产操作边界.

    Attributes:
        policy_id: 策略 ID
        name: 策略名称
        max_daily_spend: 每日最大花费
        max_budget_change_ratio: 单次预算最大变动比例
        max_budget_change_amount: 单次预算最大变动金额
        allowed_countries: 允许投放的国家列表
        blocked_countries: 禁止投放的国家列表
        allowed_platforms: 允许的投放平台
        action_rules: 逐动作规则
        require_confirmation: 需要人工确认的动作列表
        auto_actions: 完全自动的动作列表
        global_cooldown_minutes: 全局冷却时间 (分钟)
        max_consecutive_errors: 最大连续错误数
        enabled: 是否启用
    """
    policy_id: str = ""
    name: str = "Default Production Policy"
    max_daily_spend: float = 10000.0
    max_budget_change_ratio: float = 0.2
    max_budget_change_amount: float = 2000.0
    allowed_countries: list[str] = field(default_factory=list)
    blocked_countries: list[str] = field(default_factory=list)
    allowed_platforms: list[str] = field(default_factory=lambda: ["meta"])
    action_rules: dict[str, ActionRule] = field(default_factory=dict)
    require_confirmation: list[str] = field(default_factory=list)
    auto_actions: list[str] = field(default_factory=list)
    global_cooldown_minutes: float = 5.0
    max_consecutive_errors: int = 3
    enabled: bool = True

    def evaluate_action(
        self,
        action_type: str,
        params: dict[str, Any] | None = None,
    ) -> PolicyAction:
        """评估单个动作是否允许执行.

        Args:
            action_type: 动作类型
            params: 动作参数

        Returns:
            PolicyAction: 策略决策
        """
        # 明确阻止
        if action_type in self.require_confirmation:
            return PolicyAction.REQUIRE_APPROVAL

        # 明确允许
        if action_type in self.auto_actions:
            return PolicyAction.ALLOW

        # 查规则表
        rule = self.action_rules.get(action_type)
        if rule:
            return rule.evaluate(params)

        # 默认: 需要审批
        return PolicyAction.REQUIRE_APPROVAL

    def is_allowed(self, action_type: str, params: dict[str, Any] | None = None) -> bool:
        """检查动作是否允许 (不触发审批)."""
        decision = self.evaluate_action(action_type, params)
        return decision in (PolicyAction.ALLOW, PolicyAction.ALLOW_WITH_LIMIT)

    def check_budget_limit(
        self,
        current_spend: float,
        proposed_spend: float,
    ) -> tuple[bool, str]:
        """检查预算是否超出限制.

        Returns:
            (allowed, reason)
        """
        if current_spend + proposed_spend > self.max_daily_spend:
            return False, (
                f"Daily spend limit exceeded: "
                f"${current_spend + proposed_spend:,.0f} > ${self.max_daily_spend:,.0f}"
            )

        if proposed_spend > self.max_budget_change_amount:
            return False, (
                f"Budget change exceeds max: "
                f"${proposed_spend:,.0f} > ${self.max_budget_change_amount:,.0f}"
            )

        return True, "OK"

    def check_country(self, country: str) -> bool:
        """检查国家是否允许."""
        if self.blocked_countries and country in self.blocked_countries:
            return False
        if self.allowed_countries and country not in self.allowed_countries:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "max_daily_spend": self.max_daily_spend,
            "max_budget_change_ratio": self.max_budget_change_ratio,
            "max_budget_change_amount": self.max_budget_change_amount,
            "allowed_countries": self.allowed_countries,
            "blocked_countries": self.blocked_countries,
            "allowed_platforms": self.allowed_platforms,
            "require_confirmation": self.require_confirmation,
            "auto_actions": self.auto_actions,
            "action_rules_count": len(self.action_rules),
            "global_cooldown_minutes": self.global_cooldown_minutes,
            "max_consecutive_errors": self.max_consecutive_errors,
            "enabled": self.enabled,
        }


# ═══════════════════════════════════════════════════════════════
# Factory Functions
# ═══════════════════════════════════════════════════════════════


def create_default_policy() -> AgentPolicy:
    """创建默认生产策略.

    Level 0 (自动):
      - query_metrics, query_adjust, query_creative_performance
      - check_fatigue, query_memory
      - monitor, collect_result, wait
      - record_episode, update_memory

    Level 1 (半自动):
      - generate_creative, mutate_creative (预算上限 $500)
      - pause_campaign, resume_campaign
      - update_budget (变动 < 20%)

    Level 2 (需审批):
      - create_campaign
      - update_budget (变动 >= 20% 或 > $2000)
      - batch_create, batch_scale
    """
    policy = AgentPolicy(
        policy_id="default_production_policy",
        name="Default Production Policy",
        max_daily_spend=10000.0,
        max_budget_change_ratio=0.2,
        max_budget_change_amount=2000.0,
        allowed_countries=[],
        blocked_countries=[],
        allowed_platforms=["meta"],
        global_cooldown_minutes=5.0,
        max_consecutive_errors=3,
        enabled=True,
        # Level 0: 全自动
        auto_actions=[
            "query_metrics",
            "query_adjust",
            "query_creative_performance",
            "check_fatigue",
            "query_memory",
            "monitor",
            "collect_result",
            "wait",
            "record_episode",
            "update_memory",
        ],
        # Level 2: 需审批
        require_confirmation=[
            "create_campaign",
            "batch_create",
            "batch_scale",
            "scale_budget",
        ],
        # Level 1: 半自动 (有预算/比例限制)
        action_rules={
            "update_budget": ActionRule(
                action_type="update_budget",
                level=PolicyLevel.SEMI_AUTO,
                budget_limit=2000.0,
                max_change_ratio=0.2,
                description="预算调整 < 20% 或 < $2000 自动执行",
            ),
            "pause_campaign": ActionRule(
                action_type="pause_campaign",
                level=PolicyLevel.SEMI_AUTO,
                description="暂停 Campaign 半自动执行",
            ),
            "resume_campaign": ActionRule(
                action_type="resume_campaign",
                level=PolicyLevel.SEMI_AUTO,
                description="恢复 Campaign 半自动执行",
            ),
            "generate_creative": ActionRule(
                action_type="generate_creative",
                level=PolicyLevel.SEMI_AUTO,
                budget_limit=500.0,
                description="生成素材半自动执行",
            ),
            "mutate_creative": ActionRule(
                action_type="mutate_creative",
                level=PolicyLevel.SEMI_AUTO,
                budget_limit=500.0,
                description="变异素材半自动执行",
            ),
            "upload_creative": ActionRule(
                action_type="upload_creative",
                level=PolicyLevel.SEMI_AUTO,
                description="上传素材半自动执行",
            ),
            "create_creative": ActionRule(
                action_type="create_creative",
                level=PolicyLevel.SEMI_AUTO,
                budget_limit=500.0,
                description="创建素材半自动执行",
            ),
        },
    )
    return policy


def create_strict_policy() -> AgentPolicy:
    """创建严格策略 (测试环境)."""
    policy = create_default_policy()
    policy.name = "Strict Production Policy"
    policy.max_daily_spend = 1000.0
    policy.max_budget_change_ratio = 0.1
    policy.max_budget_change_amount = 500.0
    policy.auto_actions = [
        "query_metrics", "query_adjust", "query_creative_performance",
        "check_fatigue", "query_memory", "monitor", "collect_result", "wait",
    ]
    policy.require_confirmation = [
        "create_campaign", "batch_create", "batch_scale", "scale_budget",
        "update_budget", "pause_campaign", "resume_campaign",
        "generate_creative", "mutate_creative", "create_creative", "upload_creative",
    ]
    policy.action_rules = {}
    return policy


def create_permissive_policy() -> AgentPolicy:
    """创建宽松策略 (仅用于非生产环境测试)."""
    policy = AgentPolicy(
        policy_id="permissive_policy",
        name="Permissive Policy (Testing Only)",
        max_daily_spend=50000.0,
        max_budget_change_ratio=0.5,
        max_budget_change_amount=10000.0,
        global_cooldown_minutes=1.0,
        max_consecutive_errors=10,
        auto_actions=[
            "query_metrics", "query_adjust", "query_creative_performance",
            "check_fatigue", "query_memory", "monitor", "collect_result", "wait",
            "record_episode", "update_memory",
            "generate_creative", "mutate_creative", "create_creative", "upload_creative",
            "pause_campaign", "resume_campaign", "update_budget",
        ],
        require_confirmation=[
            "create_campaign",
            "batch_create",
            "batch_scale",
            "scale_budget",
        ],
    )
    return policy