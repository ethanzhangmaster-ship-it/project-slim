"""E13.6.4 Safety Policy — 安全策略管理.

管理安全规则的集合，支持策略加载、保存、启用/禁用规则和策略模板。

核心模型:
  - SafetyPolicy: 安全策略 (规则集合 + 元数据)
  - DefaultSafetyPolicy: 内置默认策略模板

连接:
  E13.6.4 SafetyEngine → SafetyPolicy → SafetyRule
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .safety_models import RiskCategory, SafetyRule
from .safety_rules import (
    budget_reduce_rule,
    budget_scale_rule,
    campaign_create_rule,
    campaign_freeze_rule,
    campaign_pause_rule,
    creative_mutation_safety_rule,
    daily_budget_cap_rule,
    rollback_protection_rule,
)


# ═══════════════════════════════════════════════════════════════
# Safety Policy
# ═══════════════════════════════════════════════════════════════


@dataclass
class SafetyPolicy:
    """安全策略 — 管理一组安全规则.

    Attributes:
        policy_id: 策略唯一标识
        name: 策略名称
        description: 策略描述
        version: 策略版本
        rules: 规则列表
        enabled: 是否启用
        created_at: 创建时间
        updated_at: 更新时间
        metadata: 扩展元数据
    """
    policy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    rules: list[SafetyRule] = field(default_factory=list)
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── 规则管理 ──────────────────────────────────────────────

    def add_rule(self, rule: SafetyRule) -> None:
        """添加规则."""
        self.rules.append(rule)
        self._touch()

    def remove_rule(self, rule_id: str) -> bool:
        """移除规则."""
        for i, rule in enumerate(self.rules):
            if rule.rule_id == rule_id:
                self.rules.pop(i)
                self._touch()
                return True
        return False

    def get_rule(self, rule_id: str) -> SafetyRule | None:
        """获取规则."""
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None

    def enable_rule(self, rule_id: str) -> bool:
        """启用规则."""
        rule = self.get_rule(rule_id)
        if rule:
            rule.enabled = True
            self._touch()
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """禁用规则."""
        rule = self.get_rule(rule_id)
        if rule:
            rule.enabled = False
            self._touch()
            return True
        return False

    # ── 查询 ──────────────────────────────────────────────────

    def get_enabled_rules(self) -> list[SafetyRule]:
        """获取所有启用的规则."""
        return [r for r in self.rules if r.enabled]

    def get_rules_by_category(self, category: RiskCategory) -> list[SafetyRule]:
        """按风险类别获取规则."""
        return [r for r in self.rules if r.category == category]

    def get_rules_sorted(self) -> list[SafetyRule]:
        """按优先级排序的规则列表."""
        return sorted(self.rules, key=lambda r: r.priority)

    @property
    def rule_count(self) -> int:
        return len(self.rules)

    @property
    def enabled_rule_count(self) -> int:
        return len(self.get_enabled_rules())

    # ── 内部方法 ──────────────────────────────────────────────

    def _touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "rules": [r.to_dict() for r in self.rules],
            "enabled": self.enabled,
            "rule_count": self.rule_count,
            "enabled_rule_count": self.enabled_rule_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Default Safety Policy
# ═══════════════════════════════════════════════════════════════


def create_default_policy() -> SafetyPolicy:
    """创建默认安全策略 — 包含所有内置安全规则.

    Returns:
        包含完整内置规则的 SafetyPolicy
    """
    policy = SafetyPolicy(
        name="default_safety_policy",
        description="内置默认安全策略，覆盖预算、素材、广告系列、回滚保护",
        version="1.0.0",
    )

    # 预算规则 (优先级 5-10)
    policy.add_rule(daily_budget_cap_rule())          # priority 5
    policy.add_rule(budget_scale_rule())               # priority 10
    policy.add_rule(budget_reduce_rule())              # priority 10

    # 素材规则 (优先级 15)
    policy.add_rule(creative_mutation_safety_rule())   # priority 15

    # 广告系列规则 (优先级 5-20)
    policy.add_rule(campaign_freeze_rule())            # priority 5
    policy.add_rule(campaign_pause_rule())             # priority 15
    policy.add_rule(campaign_create_rule())            # priority 20

    # 回滚保护 (优先级 5)
    policy.add_rule(rollback_protection_rule())        # priority 5

    return policy


def create_aggressive_policy() -> SafetyPolicy:
    """创建激进策略 — 放宽限制，仅保留关键安全规则.

    适用于: 高置信度决策、已验证的创意、成熟广告系列
    """
    policy = SafetyPolicy(
        name="aggressive_safety_policy",
        description="激进安全策略，仅保留关键限制",
        version="1.0.0",
    )

    # 仅保留最关键的规则
    policy.add_rule(daily_budget_cap_rule(20000.0))
    policy.add_rule(budget_scale_rule(
        budget_threshold_warn=500.0,
        budget_threshold_approval=2000.0,
        budget_threshold_block=5000.0,
    ))
    policy.add_rule(campaign_freeze_rule())
    policy.add_rule(rollback_protection_rule(5))

    return policy


def create_conservative_policy() -> SafetyPolicy:
    """创建保守策略 — 收紧限制，最大化安全保护.

    适用于: 新账户、不稳定的广告系列、测试阶段
    """
    policy = SafetyPolicy(
        name="conservative_safety_policy",
        description="保守安全策略，最大化安全保护",
        version="1.0.0",
    )

    policy.add_rule(daily_budget_cap_rule(1000.0))
    policy.add_rule(budget_scale_rule(
        budget_threshold_warn=50.0,
        budget_threshold_approval=200.0,
        budget_threshold_block=500.0,
    ))
    policy.add_rule(budget_reduce_rule(30.0))
    policy.add_rule(creative_mutation_safety_rule(
        min_confidence=0.8,
        block_confidence=0.5,
    ))
    policy.add_rule(campaign_freeze_rule())
    policy.add_rule(campaign_pause_rule(48))
    policy.add_rule(campaign_create_rule(20))
    policy.add_rule(rollback_protection_rule(2))

    return policy