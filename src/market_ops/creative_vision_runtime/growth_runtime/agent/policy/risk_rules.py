"""E13.7.4.2 Risk Rules — 风险规则集.

定义所有生产环境风险规则:
  - BudgetIncreaseRule: 预算增幅限制
  - DailySpendRule: 日花费上限
  - ConfidenceRule: 置信度要求
  - CampaignCreationRule: Campaign 创建频率限制
  - CreativeCountRule: 素材创建频率限制
  - CampaignAgeRule: Campaign 新手保护期
  - ErrorRateRule: Agent 连续错误率限制
  - BiddingChangeRule: 出价变更限制
  - TargetingChangeRule: 定向变更限制
  - BatchOperationRule: 批量操作限制

每条规则返回 RuleResult，PolicyEngine 聚合所有规则结果。
"""

from __future__ import annotations

from .policy_models import (
    PolicyActionType,
    PolicyContext,
    PolicyDecision,
    RiskRule,
    RuleResult,
    RuleSeverity,
    SEVERITY_TO_DECISION,
)


# ═══════════════════════════════════════════════════════════════
# 1. Budget Increase Rule
# ═══════════════════════════════════════════════════════════════

def _build_budget_increase_rule(max_ratio: float = 0.3) -> RiskRule:
    """预算增幅规则.

    策略: budget_change_ratio > max_ratio → REQUIRE_APPROVAL
    适用动作: UPDATE_BUDGET, SCALE_BUDGET
    """
    def condition(ctx: PolicyContext) -> bool:
        return ctx.budget_change_ratio > max_ratio

    return RiskRule(
        name="budget_increase_limit",
        description=f"预算变动比例超过 {max_ratio:.0%} 需要审批",
        severity=RuleSeverity.HIGH,
        priority=10,
        condition=condition,
        reason_template=f"预算变动比例 {{budget_change_ratio}} 超过 {max_ratio:.0%} 上限",
        action_types=[PolicyActionType.UPDATE_BUDGET, PolicyActionType.SCALE_BUDGET],
    )


# ═══════════════════════════════════════════════════════════════
# 2. Daily Spend Rule
# ═══════════════════════════════════════════════════════════════

def _build_daily_spend_rule() -> RiskRule:
    """日花费上限规则.

    策略: daily_spend > daily_spend_limit → BLOCK
    """
    def condition(ctx: PolicyContext) -> bool:
        return ctx.daily_spend > ctx.daily_spend_limit

    return RiskRule(
        name="daily_spend_limit",
        description="日花费超出预算上限直接阻止",
        severity=RuleSeverity.CRITICAL,
        priority=5,
        condition=condition,
        reason_template="日花费 {daily_spend} 超出预算上限 {daily_spend_limit}",
        action_types=[],
    )


# ═══════════════════════════════════════════════════════════════
# 3. Confidence Rule
# ═══════════════════════════════════════════════════════════════

def _build_confidence_rule(min_confidence: float = 0.7) -> RiskRule:
    """置信度规则.

    策略: confidence < min_confidence → WARN
    """
    def condition(ctx: PolicyContext) -> bool:
        return ctx.confidence < min_confidence

    return RiskRule(
        name="low_confidence_warning",
        description=f"置信度低于 {min_confidence:.0%} 时发出警告",
        severity=RuleSeverity.MEDIUM,
        priority=30,
        condition=condition,
        reason_template=f"Agent 置信度 {{confidence}} 低于 {min_confidence:.0%}，建议人工复核",
        action_types=[],
    )


# ═══════════════════════════════════════════════════════════════
# 4. Campaign Creation Rule
# ═══════════════════════════════════════════════════════════════

def _build_campaign_creation_rule() -> RiskRule:
    """Campaign 创建频率限制.

    策略: creative_count-like counter for campaign creations > max_campaign_per_day → BLOCK
    """
    def condition(ctx: PolicyContext) -> bool:
        # 使用 metadata 中的 campaign_creation_count 字段
        count = ctx.metadata.get("campaign_creation_count", 0)
        return count > ctx.max_campaign_per_day

    return RiskRule(
        name="campaign_creation_limit",
        description="每日创建 Campaign 数量超过上限时阻止",
        severity=RuleSeverity.CRITICAL,
        priority=6,
        condition=condition,
        reason_template="当日已创建 Campaign 数量超过上限 {max_campaign_per_day}",
        action_types=[PolicyActionType.CREATE_CAMPAIGN],
    )


# ═══════════════════════════════════════════════════════════════
# 5. Creative Count Rule
# ═══════════════════════════════════════════════════════════════

def _build_creative_count_rule() -> RiskRule:
    """素材创建频率限制.

    策略: creative_count > max_creative_per_day → BLOCK
    """
    def condition(ctx: PolicyContext) -> bool:
        return ctx.creative_count > ctx.max_creative_per_day

    return RiskRule(
        name="creative_count_limit",
        description="每日创建素材数量超过上限时阻止",
        severity=RuleSeverity.CRITICAL,
        priority=7,
        condition=condition,
        reason_template="当日已创建素材数 {creative_count} 超过上限 {max_creative_per_day}",
        action_types=[PolicyActionType.CREATE_CREATIVE, PolicyActionType.MUTATE_CREATIVE],
    )


# ═══════════════════════════════════════════════════════════════
# 6. Campaign Age Rule (新手保护期)
# ═══════════════════════════════════════════════════════════════

def _build_campaign_age_rule(
    min_age_hours: float = 24.0,
    protected_actions: list[str] | None = None,
) -> RiskRule:
    """Campaign 新手保护期规则.

    策略: campaign_age_hours < min_age_hours 时，禁止修改 Campaign → WARN
    """
    if protected_actions is None:
        protected_actions = [
            PolicyActionType.UPDATE_BUDGET,
            PolicyActionType.PAUSE_CAMPAIGN,
            PolicyActionType.CHANGE_TARGETING,
            PolicyActionType.CHANGE_BIDDING,
        ]

    def condition(ctx: PolicyContext) -> bool:
        if not ctx.campaign_id:
            return False
        return ctx.campaign_age_hours < min_age_hours

    return RiskRule(
        name="campaign_age_protection",
        description=f"Campaign 创建不足 {min_age_hours}h 时限制修改操作",
        severity=RuleSeverity.MEDIUM,
        priority=20,
        condition=condition,
        reason_template=f"Campaign 创建不足 {min_age_hours}h，处于学习期保护阶段",
        action_types=protected_actions,
    )


# ═══════════════════════════════════════════════════════════════
# 7. Error Rate Rule
# ═══════════════════════════════════════════════════════════════

def _build_error_rate_rule(max_consecutive_errors: int = 3) -> RiskRule:
    """连续错误率规则.

    策略: agent_consecutive_errors > max_consecutive_errors → BLOCK
    """
    def condition(ctx: PolicyContext) -> bool:
        return ctx.agent_consecutive_errors > max_consecutive_errors

    return RiskRule(
        name="consecutive_errors_limit",
        description=f"连续错误超过 {max_consecutive_errors} 次时阻止所有操作",
        severity=RuleSeverity.CRITICAL,
        priority=1,
        condition=condition,
        reason_template=f"Agent 连续错误 {max_consecutive_errors}+ 次，暂停所有操作等待人工介入",
        action_types=[],
    )


# ═══════════════════════════════════════════════════════════════
# 8. Bidding Change Rule
# ═══════════════════════════════════════════════════════════════

def _build_bidding_change_rule(max_change_ratio: float = 0.25) -> RiskRule:
    """出价变更限制.

    策略: 出价变动 > 25% → REQUIRE_APPROVAL
    """
    def condition(ctx: PolicyContext) -> bool:
        return ctx.budget_change_ratio > max_change_ratio

    return RiskRule(
        name="bidding_change_limit",
        description=f"出价变动超过 {max_change_ratio:.0%} 需要审批",
        severity=RuleSeverity.HIGH,
        priority=12,
        condition=condition,
        reason_template=f"出价变动比例 {{budget_change_ratio}} 超过 {max_change_ratio:.0%} 上限",
        action_types=[PolicyActionType.CHANGE_BIDDING],
    )


# ═══════════════════════════════════════════════════════════════
# 9. Targeting Change Rule
# ═══════════════════════════════════════════════════════════════

def _build_targeting_change_rule() -> RiskRule:
    """定向变更规则.

    策略: 改变定向 → REQUIRE_APPROVAL (定向变更影响面大)
    """
    def condition(ctx: PolicyContext) -> bool:
        return True  # 定向变更始终需要审批

    return RiskRule(
        name="targeting_change_approval",
        description="改变定向始终需要审批",
        severity=RuleSeverity.HIGH,
        priority=11,
        condition=condition,
        reason_template="定向变更影响面大，需要人工审批确认",
        action_types=[PolicyActionType.CHANGE_TARGETING],
    )


# ═══════════════════════════════════════════════════════════════
# 10. Batch Operation Rule
# ═══════════════════════════════════════════════════════════════

def _build_batch_operation_rule(max_batch_size: int = 5) -> RiskRule:
    """批量操作限制.

    策略: 批量操作数量 > max_batch_size → REQUIRE_APPROVAL
    """
    def condition(ctx: PolicyContext) -> bool:
        batch_size = ctx.metadata.get("batch_size", 0)
        return batch_size > max_batch_size

    return RiskRule(
        name="batch_operation_limit",
        description=f"批量操作超过 {max_batch_size} 个需要审批",
        severity=RuleSeverity.HIGH,
        priority=15,
        condition=condition,
        reason_template=f"批量操作数量超过 {max_batch_size} 个上限",
        action_types=[PolicyActionType.BATCH_CREATE],
    )


# ═══════════════════════════════════════════════════════════════
# 11. Budget Decrease Limit
# ═══════════════════════════════════════════════════════════════

def _build_budget_decrease_rule(max_decrease_ratio: float = 0.5) -> RiskRule:
    """预算减少规则.

    策略: 预算减少 > 50% → REQUIRE_APPROVAL (大幅削减可能影响学习期)
    """
    def condition(ctx: PolicyContext) -> bool:
        return ctx.budget_change_ratio < -max_decrease_ratio

    return RiskRule(
        name="budget_decrease_limit",
        description=f"预算减少超过 {max_decrease_ratio:.0%} 需要审批",
        severity=RuleSeverity.HIGH,
        priority=13,
        condition=condition,
        reason_template=f"预算削减比例 {{budget_change_ratio}} 超过 {max_decrease_ratio:.0%} 上限",
        action_types=[PolicyActionType.UPDATE_BUDGET, PolicyActionType.SCALE_BUDGET],
    )


# ═══════════════════════════════════════════════════════════════
# 12. Risk Score Rule
# ═══════════════════════════════════════════════════════════════

def _build_risk_score_rule(max_risk_score: float = 0.8) -> RiskRule:
    """风险评分规则.

    策略: risk_score > max_risk_score → BLOCK
    """
    def condition(ctx: PolicyContext) -> bool:
        return ctx.risk_score > max_risk_score

    return RiskRule(
        name="high_risk_score_block",
        description=f"风险评分超过 {max_risk_score:.0%} 时阻止",
        severity=RuleSeverity.CRITICAL,
        priority=2,
        condition=condition,
        reason_template=f"综合风险评分 {{risk_score}} 超过 {max_risk_score:.0%} 阈值",
        action_types=[],
    )


# ═══════════════════════════════════════════════════════════════
# Default Rules Builder
# ═══════════════════════════════════════════════════════════════

def build_default_rules(
    budget_increase_ratio: float = 0.3,
    min_confidence: float = 0.7,
    min_campaign_age_hours: float = 24.0,
    max_consecutive_errors: int = 3,
    max_batch_size: int = 5,
    max_risk_score: float = 0.8,
) -> list[RiskRule]:
    """构建默认规则集.

    返回按 priority 排序的规则列表。
    优先级顺序: 1(错误率) → 2(风险评分) → 5(日花费) → 6(Campaign创建) → 7(素材数) →
                 10(预算增幅) → 11(定向变更) → 12(出价变更) → 13(预算削减) → 15(批量) →
                 20(新手保护) → 30(置信度)

    Args:
        budget_increase_ratio: 预算增幅上限
        min_confidence: 最低置信度
        min_campaign_age_hours: 新手保护期 (小时)
        max_consecutive_errors: 最大连续错误数
        max_batch_size: 最大批量操作数
        max_risk_score: 最大风险评分

    Returns:
        list[RiskRule]: 默认规则集
    """
    rules = [
        _build_error_rate_rule(max_consecutive_errors),
        _build_risk_score_rule(max_risk_score),
        _build_daily_spend_rule(),
        _build_campaign_creation_rule(),
        _build_creative_count_rule(),
        _build_budget_increase_rule(budget_increase_ratio),
        _build_targeting_change_rule(),
        _build_bidding_change_rule(),
        _build_budget_decrease_rule(),
        _build_batch_operation_rule(max_batch_size),
        _build_campaign_age_rule(min_campaign_age_hours),
        _build_confidence_rule(min_confidence),
    ]
    return sorted(rules, key=lambda r: r.priority)


# ═══════════════════════════════════════════════════════════════
# 自定义规则构建辅助
# ═══════════════════════════════════════════════════════════════

def build_custom_budget_rule(
    max_ratio: float,
    severity: RuleSeverity = RuleSeverity.HIGH,
    rule_name: str = "custom_budget_rule",
) -> RiskRule:
    """构建自定义预算规则.

    Args:
        max_ratio: 预算变动比例上限
        severity: 违反时的严重程度
        rule_name: 规则名称

    Returns:
        RiskRule: 自定义预算规则
    """
    def condition(ctx: PolicyContext) -> bool:
        return abs(ctx.budget_change_ratio) > max_ratio

    return RiskRule(
        name=rule_name,
        description=f"自定义预算规则: 变动超过 {max_ratio:.0%} 触发 {severity.value}",
        severity=severity,
        priority=25,
        condition=condition,
        reason_template=f"预算变动比例 {{budget_change_ratio}} 超过自定义上限 {max_ratio:.0%}",
        action_types=[PolicyActionType.UPDATE_BUDGET, PolicyActionType.SCALE_BUDGET],
    )