"""E17.6 — Permission Gate（复用 EP0.11 security.permissions，不重造）。

三级权限：
- SAFE       —— 自动执行（只读分析 / 生成候选素材 / dry-run）
- CONTROLLED —— 需人工审批（预算增加 / 商店页更新 / 价格调整）
- CRITICAL   —— 禁止自动执行（大额预算 / 全量发布 / 直接扣费类）

判定为确定性规则：按 (domain, action_type) 查表 + risk_level 升级。
每次判定写入 EP0 PermissionAudit（可产出违规报告）。
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, Optional, Tuple

from security.permissions import Action, PermissionAudit, Resource

from .models import ExecutionAction, ExecutionDomain


class PermissionTier(str, Enum):
    SAFE = "safe"              # 自动执行
    CONTROLLED = "controlled"  # 需审批（WAITING_APPROVAL）
    CRITICAL = "critical"      # 禁止自动执行（永远人工）


# (domain, action_type) -> tier。未列出的 action_type 用 domain 默认值。
_ACTION_TIERS: Dict[Tuple[str, str], PermissionTier] = {
    # UA：读安全，动钱受控
    (ExecutionDomain.UA.value, "monitor_metrics"): PermissionTier.SAFE,
    (ExecutionDomain.UA.value, "check_budget"): PermissionTier.SAFE,
    (ExecutionDomain.UA.value, "run_experiment"): PermissionTier.CONTROLLED,
    (ExecutionDomain.UA.value, "increase_budget"): PermissionTier.CONTROLLED,
    (ExecutionDomain.UA.value, "pause_campaigns"): PermissionTier.CONTROLLED,
    (ExecutionDomain.UA.value, "reallocate_budget"): PermissionTier.CONTROLLED,
    # ASO：分析安全，改店受控
    (ExecutionDomain.ASO.value, "keyword_analysis"): PermissionTier.SAFE,
    (ExecutionDomain.ASO.value, "update_listing"): PermissionTier.CONTROLLED,
    (ExecutionDomain.ASO.value, "run_ab_experiment"): PermissionTier.CONTROLLED,
    # CREATIVE：纯生成/评分安全
    (ExecutionDomain.CREATIVE.value, "analyze_dna"): PermissionTier.SAFE,
    (ExecutionDomain.CREATIVE.value, "generate_creatives"): PermissionTier.SAFE,
    (ExecutionDomain.CREATIVE.value, "clip_screen"): PermissionTier.SAFE,
    # ECONOMY（PAYMENT 域）：分析安全，改价一律 CRITICAL
    (ExecutionDomain.ECONOMY.value, "analyze_revenue"): PermissionTier.SAFE,
    (ExecutionDomain.ECONOMY.value, "design_pricing"): PermissionTier.SAFE,
    (ExecutionDomain.ECONOMY.value, "apply_pricing"): PermissionTier.CRITICAL,
    (ExecutionDomain.ECONOMY.value, "ab_test_pricing"): PermissionTier.CONTROLLED,
    # RELEASE：halt 永远允许自动（止血优先），推进受控
    (ExecutionDomain.RELEASE.value, "halt_release"): PermissionTier.SAFE,
    (ExecutionDomain.RELEASE.value, "advance_rollout"): PermissionTier.CONTROLLED,
    (ExecutionDomain.RELEASE.value, "triage_health"): PermissionTier.SAFE,
    # ANALYTICS：只读，永远安全
}

_DOMAIN_DEFAULTS: Dict[str, PermissionTier] = {
    ExecutionDomain.UA.value: PermissionTier.CONTROLLED,
    ExecutionDomain.ASO.value: PermissionTier.CONTROLLED,
    ExecutionDomain.CREATIVE.value: PermissionTier.SAFE,
    ExecutionDomain.ECONOMY.value: PermissionTier.CRITICAL,
    ExecutionDomain.RELEASE.value: PermissionTier.CONTROLLED,
    ExecutionDomain.ANALYTICS.value: PermissionTier.SAFE,
}

# 执行域 -> EP0 Resource（用于 PermissionAudit 记录）
_DOMAIN_RESOURCES: Dict[str, Resource] = {
    ExecutionDomain.UA.value: Resource.META_ADS,
    ExecutionDomain.ASO.value: Resource.GOOGLE_PLAY,
    ExecutionDomain.CREATIVE.value: Resource.EXPERIMENT,
    ExecutionDomain.ECONOMY.value: Resource.REVENUE_DATA,
    ExecutionDomain.RELEASE.value: Resource.GOOGLE_PLAY,
    ExecutionDomain.ANALYTICS.value: Resource.REVENUE_DATA,
}

# risk_level 升级阈值：SAFE 高风险升 CONTROLLED；CONTROLLED 超高风险升 CRITICAL
_RISK_ESCALATE_CONTROLLED = 0.6
_RISK_ESCALATE_CRITICAL = 0.85


class PermissionChecker:
    """确定性权限判定 + EP0 PermissionAudit 记录。"""

    def __init__(self, audit: Optional[PermissionAudit] = None,
                 agent: str = "execution_router"):
        self.audit = audit or PermissionAudit()
        self.agent = agent

    def tier(self, action: ExecutionAction) -> PermissionTier:
        base = _ACTION_TIERS.get(
            (action.domain, action.action_type),
            _DOMAIN_DEFAULTS.get(action.domain, PermissionTier.CONTROLLED),
        )
        # 显式要求审批：SAFE 至少升 CONTROLLED
        if action.approval_required and base == PermissionTier.SAFE:
            base = PermissionTier.CONTROLLED
        # 风险升级
        if base == PermissionTier.SAFE and action.risk_level >= _RISK_ESCALATE_CONTROLLED:
            base = PermissionTier.CONTROLLED
        elif base == PermissionTier.CONTROLLED and action.risk_level >= _RISK_ESCALATE_CRITICAL:
            base = PermissionTier.CRITICAL
        return base

    def check(self, action: ExecutionAction) -> PermissionTier:
        """判定权限级并写入 EP0 PermissionAudit。"""
        t = self.tier(action)
        resource = _DOMAIN_RESOURCES.get(action.domain, Resource.DECISION_LOG)
        ep0_action = Action.READ if t == PermissionTier.SAFE else Action.EXECUTE
        # CRITICAL 视作"不允许自动"，记为 violation 供报告
        self.audit.check(self.agent, resource, ep0_action,
                         allowed=(t != PermissionTier.CRITICAL))
        return t


__all__ = ["PermissionTier", "PermissionChecker"]
