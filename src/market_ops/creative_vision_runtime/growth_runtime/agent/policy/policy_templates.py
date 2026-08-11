"""E13.7.4.2 Policy Templates — 预设策略模板.

提供三种预设策略模式:
  - Conservative: 保守模式 (新产品、高风险阶段)
  - Balanced: 平衡模式 (默认，稳定产品)
  - Aggressive: 激进模式 (Scale 阶段)

每种模板定义:
  - 预算变动上限
  - 置信度阈值
  - 审批要求
  - 日花费上限
  - Campaign 创建限制
  - 素材创建限制

使用方式:
    >>> from .policy_templates import PolicyTemplate, CONSERVATIVE, BALANCED, AGGRESSIVE
    >>> engine = CONSERVATIVE.create_engine()
    >>> result = engine.evaluate(context)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .policy_engine import PolicyEngine, create_policy_engine
from .risk_rules import build_default_rules


# ═══════════════════════════════════════════════════════════════
# Policy Template
# ═══════════════════════════════════════════════════════════════


@dataclass
class PolicyTemplate:
    """策略模板 — 预设的规则配置.

    Attributes:
        name: 模板名称
        description: 模板描述
        budget_increase_ratio: 预算增幅上限 (无需审批)
        budget_decrease_ratio: 预算削减上限 (无需审批)
        min_confidence: 最低置信度
        daily_spend_limit: 日花费上限 (PolicyContext 默认值)
        max_campaign_per_day: 每日最大 Campaign 数
        max_creative_per_day: 每日最大素材数
        min_campaign_age_hours: 新手保护期 (小时)
        require_approval_for_budget_change: 预算变动是否需要审批
        require_approval_for_targeting: 定向变更是否需要审批
        auto_execute: 是否自动执行 (无需审批)
        strict_mode: 严格模式
        max_consecutive_errors: 最大连续错误数
        max_batch_size: 最大批量操作数
    """
    name: str = ""
    description: str = ""
    # 预算
    budget_increase_ratio: float = 0.1
    budget_decrease_ratio: float = 0.5
    # 置信度
    min_confidence: float = 0.7
    # 限制
    daily_spend_limit: float = 10000.0
    max_campaign_per_day: int = 5
    max_creative_per_day: int = 20
    min_campaign_age_hours: float = 24.0
    # 审批
    require_approval_for_budget_change: bool = True
    require_approval_for_targeting: bool = True
    auto_execute: bool = False
    strict_mode: bool = False
    # 错误限制
    max_consecutive_errors: int = 3
    max_batch_size: int = 5

    def create_engine(self) -> PolicyEngine:
        """根据模板创建 PolicyEngine."""
        rules = build_default_rules(
            budget_increase_ratio=self.budget_increase_ratio,
            min_confidence=self.min_confidence,
            min_campaign_age_hours=self.min_campaign_age_hours,
            max_consecutive_errors=self.max_consecutive_errors,
            max_batch_size=self.max_batch_size,
        )
        return create_policy_engine(
            rules=rules,
            strict_mode=self.strict_mode,
        )

    def apply_to_context_defaults(self) -> dict[str, Any]:
        """获取模板的 PolicyContext 默认值."""
        return {
            "daily_spend_limit": self.daily_spend_limit,
            "max_campaign_per_day": self.max_campaign_per_day,
            "max_creative_per_day": self.max_creative_per_day,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "budget_increase_ratio": self.budget_increase_ratio,
            "budget_decrease_ratio": self.budget_decrease_ratio,
            "min_confidence": self.min_confidence,
            "daily_spend_limit": self.daily_spend_limit,
            "max_campaign_per_day": self.max_campaign_per_day,
            "max_creative_per_day": self.max_creative_per_day,
            "min_campaign_age_hours": self.min_campaign_age_hours,
            "require_approval_for_budget_change": self.require_approval_for_budget_change,
            "require_approval_for_targeting": self.require_approval_for_targeting,
            "auto_execute": self.auto_execute,
            "strict_mode": self.strict_mode,
            "max_consecutive_errors": self.max_consecutive_errors,
            "max_batch_size": self.max_batch_size,
        }


# ═══════════════════════════════════════════════════════════════
# Preset Templates
# ═══════════════════════════════════════════════════════════════

# Conservative — 保守模式
CONSERVATIVE = PolicyTemplate(
    name="conservative",
    description="保守模式：适合新产品、测试阶段、高风险环境",
    budget_increase_ratio=0.1,      # 10% 预算变动需要审批
    budget_decrease_ratio=0.3,      # 30% 削减需要审批
    min_confidence=0.8,             # 置信度 > 80%
    daily_spend_limit=1000.0,       # 日花费上限 $1000
    max_campaign_per_day=2,         # 每天最多 2 个 Campaign
    max_creative_per_day=5,         # 每天最多 5 个素材
    min_campaign_age_hours=48.0,    # 48h 新手保护期
    require_approval_for_budget_change=True,
    require_approval_for_targeting=True,
    auto_execute=False,
    strict_mode=False,
    max_consecutive_errors=2,
    max_batch_size=2,
)

# Balanced — 平衡模式 (默认)
BALANCED = PolicyTemplate(
    name="balanced",
    description="平衡模式：适合稳定运行的产品，默认推荐",
    budget_increase_ratio=0.2,      # 20% 预算变动需要审批
    budget_decrease_ratio=0.5,      # 50% 削减需要审批
    min_confidence=0.7,             # 置信度 > 70%
    daily_spend_limit=5000.0,       # 日花费上限 $5000
    max_campaign_per_day=5,         # 每天最多 5 个 Campaign
    max_creative_per_day=20,        # 每天最多 20 个素材
    min_campaign_age_hours=24.0,    # 24h 新手保护期
    require_approval_for_budget_change=True,
    require_approval_for_targeting=True,
    auto_execute=False,
    strict_mode=False,
    max_consecutive_errors=3,
    max_batch_size=5,
)

# Aggressive — 激进模式
AGGRESSIVE = PolicyTemplate(
    name="aggressive",
    description="激进模式：适合 Scale 阶段、已验证的爆款产品",
    budget_increase_ratio=0.5,      # 50% 预算变动需要审批
    budget_decrease_ratio=0.7,      # 70% 削减需要审批
    min_confidence=0.5,             # 置信度 > 50%
    daily_spend_limit=50000.0,      # 日花费上限 $50000
    max_campaign_per_day=20,        # 每天最多 20 个 Campaign
    max_creative_per_day=100,       # 每天最多 100 个素材
    min_campaign_age_hours=6.0,     # 6h 新手保护期
    require_approval_for_budget_change=True,  # 仍需审批但阈值更高
    require_approval_for_targeting=False,     # 定向变更不要求审批
    auto_execute=True,
    strict_mode=False,
    max_consecutive_errors=5,
    max_batch_size=20,
)

# 模板注册表
TEMPLATES: dict[str, PolicyTemplate] = {
    "conservative": CONSERVATIVE,
    "balanced": BALANCED,
    "aggressive": AGGRESSIVE,
}


def get_template(name: str) -> PolicyTemplate | None:
    """获取指定模板."""
    return TEMPLATES.get(name.lower())


def list_templates() -> list[dict[str, Any]]:
    """列出所有模板."""
    return [
        {"name": t.name, "description": t.description}
        for t in TEMPLATES.values()
    ]