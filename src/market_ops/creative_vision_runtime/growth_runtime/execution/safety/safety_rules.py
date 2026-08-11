"""E13.6.4 Safety Rules — 具体安全规则实现.

提供内置的安全规则工厂函数，覆盖预算、素材变异、暂停、回滚保护等场景。

规则分类:
  - Budget Rules: 预算放量/缩减的金额限制
  - Creative Rules: 素材变异置信度检查
  - Campaign Rules: 暂停/冻结操作保护
  - Rollback Rules: 回滚保护
  - Global Rules: 全局安全限制 (日预算上限等)

连接:
  E13.6.4 SafetyEngine → SafetyRule (from safety_rules) → SafetyEvaluation
"""

from __future__ import annotations

from typing import Any

from .safety_models import RiskCategory, RuleSeverity, SafetyDecision, SafetyRule


# ═══════════════════════════════════════════════════════════════
# Budget Rules
# ═══════════════════════════════════════════════════════════════


def budget_scale_rule(
    budget_threshold_warn: float = 100.0,
    budget_threshold_approval: float = 500.0,
    budget_threshold_block: float = 1000.0,
) -> SafetyRule:
    """预算放量规则 — 根据放量金额分级限制.

    | 金额范围              | 决策              |
    |----------------------|------------------|
    | < $100/day           | ALLOW (自动)      |
    | $100 ~ $500/day      | WARN (记录警告)    |
    | $500 ~ $1000/day     | REQUIRE_APPROVAL  |
    | > $1000/day          | BLOCK (禁止)      |

    Args:
        budget_threshold_warn: 警告阈值 (默认 $100)
        budget_threshold_approval: 审批阈值 (默认 $500)
        budget_threshold_block: 阻止阈值 (默认 $1000)
    """
    def _condition(action: Any, context: Any) -> bool:
        budget_impact = _get_budget_impact(action, context)
        return budget_impact >= budget_threshold_warn

    def _decision_fn(action: Any, context: Any) -> SafetyDecision:
        impact = _get_budget_impact(action, context)
        if impact >= budget_threshold_block:
            return SafetyDecision.BLOCK
        if impact >= budget_threshold_approval:
            return SafetyDecision.REQUIRE_APPROVAL
        return SafetyDecision.WARN

    def _reason_fn(action: Any, context: Any) -> str:
        impact = _get_budget_impact(action, context)
        if impact >= budget_threshold_block:
            return f"预算放量 ${impact:.0f}/day 超过阻止阈值 ${budget_threshold_block:.0f}/day"
        if impact >= budget_threshold_approval:
            return f"预算放量 ${impact:.0f}/day 超过审批阈值 ${budget_threshold_approval:.0f}/day"
        return f"预算放量 ${impact:.0f}/day 超过警告阈值 ${budget_threshold_warn:.0f}/day"

    return SafetyRule(
        name="budget_scale_limit",
        description="限制单次预算放量幅度，防止失控放量",
        category=RiskCategory.BUDGET_SCALE,
        severity=RuleSeverity.HIGH,
        condition=_condition,
        decision=SafetyDecision.WARN,
        decision_fn=_decision_fn,
        reason_fn=_reason_fn,
        priority=10,
    )


def budget_reduce_rule(
    max_reduce_pct: float = 50.0,
) -> SafetyRule:
    """预算缩减规则 — 防止过度缩减导致投放中断.

    | 缩减比例         | 决策              |
    |-----------------|------------------|
    | < 50%           | ALLOW            |
    | >= 50%          | REQUIRE_APPROVAL |

    Args:
        max_reduce_pct: 最大允许缩减百分比 (默认 50%)
    """
    def _condition(action: Any, context: Any) -> bool:
        pct = _get_budget_reduce_pct(action, context)
        return pct >= max_reduce_pct

    return SafetyRule(
        name="budget_reduce_limit",
        description=f"预算缩减超过 {max_reduce_pct}% 需要审批",
        category=RiskCategory.BUDGET_REDUCE,
        severity=RuleSeverity.HIGH,
        condition=_condition,
        decision=SafetyDecision.REQUIRE_APPROVAL,
        reason_template=f"预算缩减超过 {max_reduce_pct}% 限制，需要审批",
        priority=10,
    )


def daily_budget_cap_rule(daily_cap: float = 10000.0) -> SafetyRule:
    """全局日预算上限规则 — 防止单日总消耗超标.

    Args:
        daily_cap: 日预算上限 (默认 $10000)
    """
    def _condition(action: Any, context: Any) -> bool:
        current_daily = _get_current_daily_spend(action, context)
        budget_impact = _get_budget_impact(action, context)
        return (current_daily + budget_impact) > daily_cap

    return SafetyRule(
        name="daily_budget_cap",
        description=f"全局日预算上限 ${daily_cap:.0f}",
        category=RiskCategory.BUDGET_SCALE,
        severity=RuleSeverity.CRITICAL,
        condition=_condition,
        decision=SafetyDecision.BLOCK,
        reason_template=f"执行后日预算将超过上限 ${daily_cap:.0f}",
        priority=5,
    )


# ═══════════════════════════════════════════════════════════════
# Creative Rules
# ═══════════════════════════════════════════════════════════════


def creative_mutation_safety_rule(
    min_confidence: float = 0.6,
    block_confidence: float = 0.3,
) -> SafetyRule:
    """素材变异安全规则 — 防止低置信度创意直接扩大投放.

    | 置信度范围         | 决策              |
    |-------------------|------------------|
    | >= 0.6            | ALLOW            |
    | 0.3 ~ 0.6         | WARN             |
    | < 0.3             | BLOCK            |

    Args:
        min_confidence: 最低置信度阈值 (默认 0.6)
        block_confidence: 阻止阈值 (默认 0.3)
    """
    def _condition(action: Any, context: Any) -> bool:
        confidence = _get_confidence(action, context)
        return confidence < min_confidence

    def _decision_fn(action: Any, context: Any) -> SafetyDecision:
        confidence = _get_confidence(action, context)
        if confidence < block_confidence:
            return SafetyDecision.BLOCK
        return SafetyDecision.WARN

    return SafetyRule(
        name="creative_mutation_safety",
        description="防止低置信度素材变异直接扩大投放",
        category=RiskCategory.CREATIVE_MUTATION,
        severity=RuleSeverity.HIGH,
        condition=_condition,
        decision=SafetyDecision.WARN,
        decision_fn=_decision_fn,
        reason_template="素材变异置信度不足，建议先小规模测试",
        priority=15,
    )


# ═══════════════════════════════════════════════════════════════
# Campaign Rules
# ═══════════════════════════════════════════════════════════════


def campaign_pause_rule(
    min_campaign_age_hours: int = 24,
) -> SafetyRule:
    """暂停广告系列规则 — 防止过早暂停新创建的广告系列.

    Args:
        min_campaign_age_hours: 最小运行时长 (默认 24 小时)
    """
    def _condition(action: Any, context: Any) -> bool:
        age_hours = _get_campaign_age_hours(action, context)
        return age_hours < min_campaign_age_hours

    return SafetyRule(
        name="campaign_pause_protection",
        description=f"禁止暂停运行不足 {min_campaign_age_hours} 小时的广告系列",
        category=RiskCategory.CAMPAIGN_PAUSE,
        severity=RuleSeverity.HIGH,
        condition=_condition,
        decision=SafetyDecision.BLOCK,
        reason_template=f"广告系列运行不足 {min_campaign_age_hours} 小时，数据不足无法判断",
        priority=15,
    )


def campaign_freeze_rule() -> SafetyRule:
    """冻结广告系列规则 — 冻结操作必须审批."""
    return SafetyRule(
        name="campaign_freeze_approval",
        description="冻结广告系列必须经过审批",
        category=RiskCategory.CAMPAIGN_FREEZE,
        severity=RuleSeverity.CRITICAL,
        condition=lambda action, context: True,
        decision=SafetyDecision.REQUIRE_APPROVAL,
        reason_template="冻结广告系列属于高风险操作，需要审批",
        priority=5,
    )


def campaign_create_rule(max_active_campaigns: int = 50) -> SafetyRule:
    """创建广告系列规则 — 限制同时活跃的广告系列数量.

    Args:
        max_active_campaigns: 最大活跃广告系列数 (默认 50)
    """
    def _condition(action: Any, context: Any) -> bool:
        active = _get_active_campaign_count(action, context)
        return active >= max_active_campaigns

    return SafetyRule(
        name="campaign_create_limit",
        description=f"最大活跃广告系列数限制 ({max_active_campaigns})",
        category=RiskCategory.CAMPAIGN_CREATE,
        severity=RuleSeverity.MEDIUM,
        condition=_condition,
        decision=SafetyDecision.WARN,
        reason_template=f"活跃广告系列数已达 {max_active_campaigns}，建议先优化现有系列",
        priority=20,
    )


# ═══════════════════════════════════════════════════════════════
# Rollback Rules
# ═══════════════════════════════════════════════════════════════


def rollback_protection_rule(
    max_consecutive_failures: int = 3,
) -> SafetyRule:
    """回滚保护规则 — 连续失败多次后自动进入保护流程.

    Args:
        max_consecutive_failures: 最大连续失败次数 (默认 3)
    """
    def _condition(action: Any, context: Any) -> bool:
        failures = _get_consecutive_failures(action, context)
        return failures >= max_consecutive_failures

    return SafetyRule(
        name="rollback_protection",
        description=f"连续失败 {max_consecutive_failures} 次后自动进入保护",
        category=RiskCategory.ROLLBACK,
        severity=RuleSeverity.CRITICAL,
        condition=_condition,
        decision=SafetyDecision.BLOCK,
        reason_template=f"连续失败 {max_consecutive_failures} 次，系统进入保护模式",
        priority=5,
    )


# ═══════════════════════════════════════════════════════════════
# Helper Functions — 从 action/context 中提取参数
# ═══════════════════════════════════════════════════════════════


def _get_budget_impact(action: Any, context: Any) -> float:
    """从 action 或 context 中提取预算影响金额."""
    # 从 action.parameters 中获取
    if hasattr(action, "parameters") and isinstance(action.parameters, dict):
        budget = action.parameters.get("budget", 0)
        if isinstance(budget, (int, float)) and budget > 0:
            return float(budget)
        budget_delta = action.parameters.get("budget_delta", 0)
        if isinstance(budget_delta, (int, float)) and budget_delta > 0:
            return float(budget_delta)
    # 从 context.guard_context 中获取
    if hasattr(context, "guard_context") and hasattr(context.guard_context, "budget_impact"):
        impact = context.guard_context.budget_impact
        if isinstance(impact, (int, float)) and impact > 0:
            return float(impact)
    return 0.0


def _get_budget_reduce_pct(action: Any, context: Any) -> float:
    """从 action 或 context 中提取预算缩减百分比."""
    if hasattr(action, "parameters") and isinstance(action.parameters, dict):
        pct = action.parameters.get("reduce_pct", 0)
        if isinstance(pct, (int, float)):
            return float(pct)
    return 0.0


def _get_confidence(action: Any, context: Any) -> float:
    """从 action 或 context 中提取置信度."""
    # 从 context 中获取
    if hasattr(context, "guard_context") and hasattr(context.guard_context, "confidence"):
        conf = context.guard_context.confidence
        if isinstance(conf, (int, float)):
            return float(conf)
    # 从 action.parameters 中获取
    if hasattr(action, "parameters") and isinstance(action.parameters, dict):
        conf = action.parameters.get("confidence", 0.5)
        if isinstance(conf, (int, float)):
            return float(conf)
    return 0.5


def _get_campaign_age_hours(action: Any, context: Any) -> float:
    """从 action 或 context 中提取广告系列运行时长 (小时)."""
    if hasattr(action, "parameters") and isinstance(action.parameters, dict):
        age = action.parameters.get("campaign_age_hours", 999)
        if isinstance(age, (int, float)):
            return float(age)
    return 999.0


def _get_active_campaign_count(action: Any, context: Any) -> int:
    """从 context 中提取活跃广告系列数."""
    if hasattr(context, "metadata") and isinstance(context.metadata, dict):
        count = context.metadata.get("active_campaigns", 0)
        if isinstance(count, (int, float)):
            return int(count)
    return 0


def _get_consecutive_failures(action: Any, context: Any) -> int:
    """从 context 中提取连续失败次数."""
    if hasattr(context, "metadata") and isinstance(context.metadata, dict):
        count = context.metadata.get("consecutive_failures", 0)
        if isinstance(count, (int, float)):
            return int(count)
    return 0


def _get_current_daily_spend(action: Any, context: Any) -> float:
    """从 context 中提取当前日消耗."""
    if hasattr(context, "metadata") and isinstance(context.metadata, dict):
        spend = context.metadata.get("daily_spend", 0)
        if isinstance(spend, (int, float)):
            return float(spend)
    return 0.0


# ═══════════════════════════════════════════════════════════════
# Rule Factory — 按动作类型创建规则集
# ═══════════════════════════════════════════════════════════════


def get_rules_for_action_type(action_type: str) -> list[SafetyRule]:
    """根据动作类型返回适用的安全规则.

    Args:
        action_type: ExecutionActionType 的值

    Returns:
        适用的 SafetyRule 列表
    """
    action_type_lower = action_type.lower()
    rules: list[SafetyRule] = []

    # 预算相关
    if action_type_lower in ("scale_budget", "update_budget"):
        rules.append(budget_scale_rule())
        rules.append(daily_budget_cap_rule())
    elif action_type_lower == "reduce_budget":
        rules.append(budget_reduce_rule())

    # 素材相关
    elif action_type_lower in ("mutate_creative", "create_creative"):
        rules.append(creative_mutation_safety_rule())

    # 广告系列相关
    elif action_type_lower == "pause_campaign":
        rules.append(campaign_pause_rule())
    elif action_type_lower == "freeze_campaign":
        rules.append(campaign_freeze_rule())
    elif action_type_lower == "create_campaign":
        rules.append(campaign_create_rule())

    # 回滚保护 (所有动作类型)
    rules.append(rollback_protection_rule())

    return rules