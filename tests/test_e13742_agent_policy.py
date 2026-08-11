"""E13.7.4.2 Agent Policy System — 测试套件.

覆盖:
  - Policy Models (PolicyDecision, PolicyActionType, PolicyContext, RiskRule, RuleResult, PolicyResult)
  - Risk Rules (预算增幅, 日花费, 置信度, Campaign 创建, 素材数, 新手保护, 连续错误, 出价变更, 定向变更, 批量操作, 预算削减, 风险评分)
  - Policy Engine (单规则评估, 多规则聚合, 统计, 规则管理, 严格模式, 回滚自动批准)
  - Approval Manager (创建审批, 批准/拒绝/取消, 过期, 查询, 统计)
  - Policy Templates (Conservative/Balanced/Aggressive 模板)
  - Integration (PolicyEngine → ApprovalManager 完整链路)
"""

import time
import uuid

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent.policy import (
    # Enums
    PolicyDecision,
    PolicyActionType,
    RuleSeverity,
    ApprovalStatus,
    # Models
    PolicyContext,
    PolicyResult,
    RuleResult,
    RiskRule,
    ApprovalRequest,
    # Helpers
    SEVERITY_TO_DECISION,
    DECISION_SEVERITY,
    most_severe_decision,
    # Rules
    build_default_rules,
    build_custom_budget_rule,
    # Engine
    PolicyEngine,
    EngineStats,
    create_policy_engine,
    # Approval
    ApprovalManager,
    ApprovalRecord,
    create_approval_manager,
    # Templates
    PolicyTemplate,
    CONSERVATIVE,
    BALANCED,
    AGGRESSIVE,
    TEMPLATES,
    get_template,
    list_templates,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def make_context(**kwargs) -> PolicyContext:
    """创建测试用 PolicyContext."""
    defaults = {
        "action_type": PolicyActionType.UPDATE_BUDGET,
        "campaign_id": "test_campaign_001",
        "budget_change": 100.0,
        "budget_change_ratio": 0.1,
        "current_budget": 1000.0,
        "current_spend": 500.0,
        "daily_spend_limit": 10000.0,
        "daily_spend": 2000.0,
        "confidence": 0.85,
        "risk_score": 0.2,
        "agent_cycle": 5,
        "agent_consecutive_errors": 0,
        "campaign_age_hours": 48.0,
        "creative_count": 5,
        "max_creative_per_day": 20,
        "max_campaign_per_day": 5,
        "user_confirmation": False,
    }
    defaults.update(kwargs)
    return PolicyContext(**defaults)


# ═══════════════════════════════════════════════════════════════
# Test Policy Models
# ═══════════════════════════════════════════════════════════════


class TestPolicyDecision:
    """测试 PolicyDecision 枚举."""

    def test_all_decision_values(self):
        assert PolicyDecision.ALLOW == "allow"
        assert PolicyDecision.WARN == "warn"
        assert PolicyDecision.BLOCK == "block"
        assert PolicyDecision.REQUIRE_APPROVAL == "require_approval"

    def test_decision_severity_ordering(self):
        assert DECISION_SEVERITY[PolicyDecision.ALLOW] == 0
        assert DECISION_SEVERITY[PolicyDecision.WARN] == 1
        assert DECISION_SEVERITY[PolicyDecision.REQUIRE_APPROVAL] == 2
        assert DECISION_SEVERITY[PolicyDecision.BLOCK] == 3

    def test_most_severe_decision(self):
        assert most_severe_decision([]) == PolicyDecision.ALLOW
        assert most_severe_decision([PolicyDecision.ALLOW]) == PolicyDecision.ALLOW
        assert most_severe_decision([PolicyDecision.ALLOW, PolicyDecision.WARN]) == PolicyDecision.WARN
        assert most_severe_decision([PolicyDecision.WARN, PolicyDecision.BLOCK]) == PolicyDecision.BLOCK
        assert most_severe_decision(
            [PolicyDecision.ALLOW, PolicyDecision.WARN, PolicyDecision.REQUIRE_APPROVAL, PolicyDecision.BLOCK]
        ) == PolicyDecision.BLOCK


class TestPolicyActionType:
    """测试 PolicyActionType 枚举."""

    def test_all_action_types(self):
        assert PolicyActionType.CREATE_CAMPAIGN == "create_campaign"
        assert PolicyActionType.UPDATE_BUDGET == "update_budget"
        assert PolicyActionType.PAUSE_CAMPAIGN == "pause_campaign"
        assert PolicyActionType.RESUME_CAMPAIGN == "resume_campaign"
        assert PolicyActionType.CREATE_CREATIVE == "create_creative"
        assert PolicyActionType.MUTATE_CREATIVE == "mutate_creative"
        assert PolicyActionType.CHANGE_TARGETING == "change_targeting"
        assert PolicyActionType.CHANGE_BIDDING == "change_bidding"
        assert PolicyActionType.SCALE_BUDGET == "scale_budget"
        assert PolicyActionType.BATCH_CREATE == "batch_create"
        assert PolicyActionType.ROLLBACK == "rollback"


class TestRuleSeverity:
    """测试 RuleSeverity 枚举."""

    def test_severity_values(self):
        assert RuleSeverity.CRITICAL == "critical"
        assert RuleSeverity.HIGH == "high"
        assert RuleSeverity.MEDIUM == "medium"
        assert RuleSeverity.LOW == "low"

    def test_severity_to_decision(self):
        assert SEVERITY_TO_DECISION[RuleSeverity.CRITICAL] == PolicyDecision.BLOCK
        assert SEVERITY_TO_DECISION[RuleSeverity.HIGH] == PolicyDecision.REQUIRE_APPROVAL
        assert SEVERITY_TO_DECISION[RuleSeverity.MEDIUM] == PolicyDecision.WARN
        assert SEVERITY_TO_DECISION[RuleSeverity.LOW] == PolicyDecision.ALLOW


class TestPolicyContext:
    """测试 PolicyContext."""

    def test_default_context(self):
        ctx = PolicyContext()
        assert ctx.action_type == ""
        assert ctx.confidence == 0.5
        assert ctx.daily_spend_limit == 10000.0

    def test_context_to_dict(self):
        ctx = make_context()
        d = ctx.to_dict()
        assert d["action_type"] == PolicyActionType.UPDATE_BUDGET
        assert d["campaign_id"] == "test_campaign_001"
        assert d["budget_change_ratio"] == 0.1

    def test_context_metadata(self):
        ctx = make_context(metadata={"batch_size": 10, "custom_key": "value"})
        assert ctx.metadata["batch_size"] == 10
        assert ctx.metadata["custom_key"] == "value"


class TestRiskRule:
    """测试 RiskRule 基础类."""

    def test_rule_triggered(self):
        rule = RiskRule(
            name="test_rule",
            severity=RuleSeverity.MEDIUM,
            condition=lambda ctx: ctx.budget_change_ratio > 0.3,
            reason_template="预算变动过大",
        )
        ctx = make_context(budget_change_ratio=0.5)
        result = rule.evaluate(ctx)
        assert result.triggered
        assert result.decision == PolicyDecision.WARN

    def test_rule_not_triggered(self):
        rule = RiskRule(
            name="test_rule",
            severity=RuleSeverity.MEDIUM,
            condition=lambda ctx: ctx.budget_change_ratio > 0.3,
            reason_template="预算变动过大",
        )
        ctx = make_context(budget_change_ratio=0.1)
        result = rule.evaluate(ctx)
        assert not result.triggered
        assert result.decision == PolicyDecision.ALLOW

    def test_rule_disabled(self):
        rule = RiskRule(
            name="test_rule",
            severity=RuleSeverity.MEDIUM,
            enabled=False,
            condition=lambda ctx: ctx.budget_change_ratio > 0.3,
            reason_template="预算变动过大",
        )
        ctx = make_context(budget_change_ratio=0.5)
        result = rule.evaluate(ctx)
        assert not result.triggered

    def test_rule_action_type_filter(self):
        rule = RiskRule(
            name="test_rule",
            severity=RuleSeverity.MEDIUM,
            condition=lambda ctx: True,
            reason_template="test",
            action_types=[PolicyActionType.CREATE_CAMPAIGN],
        )
        ctx = make_context(action_type=PolicyActionType.UPDATE_BUDGET)
        result = rule.evaluate(ctx)
        assert not result.triggered

    def test_rule_action_type_match(self):
        rule = RiskRule(
            name="test_rule",
            severity=RuleSeverity.MEDIUM,
            condition=lambda ctx: True,
            reason_template="test",
            action_types=[PolicyActionType.UPDATE_BUDGET],
        )
        ctx = make_context(action_type=PolicyActionType.UPDATE_BUDGET)
        result = rule.evaluate(ctx)
        assert result.triggered

    def test_rule_condition_error_handling(self):
        rule = RiskRule(
            name="test_rule",
            severity=RuleSeverity.MEDIUM,
            condition=lambda ctx: 1 / 0,  # 故意触发异常
            reason_template="test",
        )
        ctx = make_context()
        result = rule.evaluate(ctx)
        assert not result.triggered  # 异常时不应触发

    def test_rule_reason_template_replacement(self):
        rule = RiskRule(
            name="test_rule",
            severity=RuleSeverity.MEDIUM,
            condition=lambda ctx: ctx.budget_change_ratio > 0.3,
            reason_template="预算变动 {budget_change_ratio} 超过 30% 上限",
        )
        ctx = make_context(budget_change_ratio=0.5)
        result = rule.evaluate(ctx)
        assert "50.0%" in result.reason

    def test_rule_to_dict(self):
        rule = RiskRule(
            name="test_rule",
            description="test description",
            severity=RuleSeverity.HIGH,
            action_types=[PolicyActionType.UPDATE_BUDGET],
        )
        d = rule.to_dict()
        assert d["name"] == "test_rule"
        assert d["severity"] == "high"
        assert PolicyActionType.UPDATE_BUDGET in d["action_types"]


class TestPolicyResult:
    """测试 PolicyResult."""

    def test_result_to_dict(self):
        result = PolicyResult(
            decision=PolicyDecision.WARN,
            reason="test reason",
            risk_score=0.3,
            triggered_rules=["rule_1"],
            warnings=["warning 1"],
            is_blocked=False,
            requires_approval=False,
        )
        d = result.to_dict()
        assert d["decision"] == "warn"
        assert d["reason"] == "test reason"
        assert d["risk_score"] == 0.3
        assert d["triggered_rules"] == ["rule_1"]


# ═══════════════════════════════════════════════════════════════
# Test Risk Rules
# ═══════════════════════════════════════════════════════════════


class TestBudgetIncreaseRule:
    """测试预算增幅规则."""

    def test_budget_increase_10_percent_allowed(self):
        """预算增加 10% -> ALLOW (默认规则)."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            budget_change_ratio=0.1,
        )
        result = engine.evaluate(ctx)
        assert result.decision == PolicyDecision.ALLOW

    def test_budget_increase_50_percent_requires_approval(self):
        """预算增加 50% -> REQUIRE_APPROVAL."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            budget_change_ratio=0.5,
        )
        result = engine.evaluate(ctx)
        assert result.decision == PolicyDecision.REQUIRE_APPROVAL

    def test_budget_increase_exactly_30_not_triggered(self):
        """预算增加恰好 30% 不触发 (ratio > 0.3 才触发)."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            budget_change_ratio=0.3,
        )
        result = engine.evaluate(ctx)
        # 30% 不触发 budget_increase_limit (strict >)
        assert result.decision != PolicyDecision.REQUIRE_APPROVAL or "budget_increase_limit" not in str(result.triggered_rules)

    def test_budget_increase_31_percent_requires_approval(self):
        """预算增加 31% -> REQUIRE_APPROVAL."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            budget_change_ratio=0.31,
        )
        result = engine.evaluate(ctx)
        assert "budget_increase_limit" in result.triggered_rules

    def test_scale_budget_triggers_same_rule(self):
        """SCALE_BUDGET 也触发预算增幅规则."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.SCALE_BUDGET,
            budget_change_ratio=0.5,
        )
        result = engine.evaluate(ctx)
        assert result.decision == PolicyDecision.REQUIRE_APPROVAL


class TestDailySpendRule:
    """测试日花费上限规则."""

    def test_daily_spend_under_limit_allowed(self):
        """日花费未超限 -> ALLOW."""
        engine = create_policy_engine()
        ctx = make_context(
            daily_spend=5000.0,
            daily_spend_limit=10000.0,
        )
        result = engine.evaluate(ctx)
        assert result.decision != PolicyDecision.BLOCK

    def test_daily_spend_exceeded_blocked(self):
        """日花费超限 -> BLOCK."""
        engine = create_policy_engine()
        ctx = make_context(
            daily_spend=15000.0,
            daily_spend_limit=10000.0,
        )
        result = engine.evaluate(ctx)
        assert result.decision == PolicyDecision.BLOCK
        assert "daily_spend_limit" in result.triggered_rules

    def test_daily_spend_exactly_at_limit_not_blocked(self):
        """日花费恰好等于上限不触发."""
        engine = create_policy_engine()
        ctx = make_context(
            daily_spend=10000.0,
            daily_spend_limit=10000.0,
        )
        result = engine.evaluate(ctx)
        assert "daily_spend_limit" not in result.triggered_rules


class TestConfidenceRule:
    """测试置信度规则."""

    def test_high_confidence_no_warning(self):
        """高置信度 (0.85) -> 无警告."""
        engine = create_policy_engine()
        ctx = make_context(confidence=0.85)
        result = engine.evaluate(ctx)
        assert "low_confidence_warning" not in result.triggered_rules

    def test_low_confidence_warning(self):
        """低置信度 (0.5) -> WARN."""
        engine = create_policy_engine()
        ctx = make_context(confidence=0.5)
        result = engine.evaluate(ctx)
        assert "low_confidence_warning" in result.triggered_rules
        assert result.decision == PolicyDecision.WARN

    def test_borderline_confidence_69(self):
        """置信度 0.69 -> WARN."""
        engine = create_policy_engine()
        ctx = make_context(confidence=0.69)
        result = engine.evaluate(ctx)
        assert "low_confidence_warning" in result.triggered_rules


class TestCampaignCreationRule:
    """测试 Campaign 创建限制规则."""

    def test_under_limit_allowed(self):
        """未超限 -> ALLOW."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.CREATE_CAMPAIGN,
            metadata={"campaign_creation_count": 3},
            max_campaign_per_day=5,
        )
        result = engine.evaluate(ctx)
        assert "campaign_creation_limit" not in result.triggered_rules

    def test_over_limit_blocked(self):
        """超限 -> BLOCK."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.CREATE_CAMPAIGN,
            metadata={"campaign_creation_count": 6},
            max_campaign_per_day=5,
        )
        result = engine.evaluate(ctx)
        assert result.decision == PolicyDecision.BLOCK
        assert "campaign_creation_limit" in result.triggered_rules


class TestCreativeCountRule:
    """测试素材创建限制规则."""

    def test_under_limit_allowed(self):
        """未超限 -> ALLOW."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.CREATE_CREATIVE,
            creative_count=10,
            max_creative_per_day=20,
        )
        result = engine.evaluate(ctx)
        assert "creative_count_limit" not in result.triggered_rules

    def test_over_limit_blocked(self):
        """超限 -> BLOCK."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.CREATE_CREATIVE,
            creative_count=25,
            max_creative_per_day=20,
        )
        result = engine.evaluate(ctx)
        assert result.decision == PolicyDecision.BLOCK
        assert "creative_count_limit" in result.triggered_rules


class TestCampaignAgeRule:
    """测试新手保护期规则."""

    def test_old_campaign_allowed(self):
        """老 Campaign (48h) -> 允许修改."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            campaign_id="test_123",
            campaign_age_hours=48.0,
        )
        result = engine.evaluate(ctx)
        assert "campaign_age_protection" not in result.triggered_rules

    def test_new_campaign_warned(self):
        """新 Campaign (4h) -> WARN."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            campaign_id="test_123",
            campaign_age_hours=4.0,
        )
        result = engine.evaluate(ctx)
        assert "campaign_age_protection" in result.triggered_rules

    def test_no_campaign_id_no_action(self):
        """无 campaign_id 时不触发."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            campaign_id="",
            campaign_age_hours=4.0,
        )
        result = engine.evaluate(ctx)
        assert "campaign_age_protection" not in result.triggered_rules


class TestErrorRateRule:
    """测试连续错误规则."""

    def test_no_errors_allowed(self):
        """无错误 -> ALLOW."""
        engine = create_policy_engine()
        ctx = make_context(agent_consecutive_errors=0)
        result = engine.evaluate(ctx)
        assert "consecutive_errors_limit" not in result.triggered_rules

    def test_too_many_errors_blocked(self):
        """连续错误 > 3 -> BLOCK."""
        engine = create_policy_engine()
        ctx = make_context(agent_consecutive_errors=5)
        result = engine.evaluate(ctx)
        assert result.decision == PolicyDecision.BLOCK
        assert "consecutive_errors_limit" in result.triggered_rules


class TestTargetingChangeRule:
    """测试定向变更规则."""

    def test_targeting_change_requires_approval(self):
        """定向变更 -> REQUIRE_APPROVAL."""
        engine = create_policy_engine()
        ctx = make_context(action_type=PolicyActionType.CHANGE_TARGETING)
        result = engine.evaluate(ctx)
        assert result.decision == PolicyDecision.REQUIRE_APPROVAL
        assert "targeting_change_approval" in result.triggered_rules


class TestBiddingChangeRule:
    """测试出价变更规则."""

    def test_small_bidding_change_allowed(self):
        """小幅度出价变更 -> ALLOW."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.CHANGE_BIDDING,
            budget_change_ratio=0.1,
        )
        result = engine.evaluate(ctx)
        assert "bidding_change_limit" not in result.triggered_rules

    def test_large_bidding_change_requires_approval(self):
        """大幅度出价变更 -> REQUIRE_APPROVAL."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.CHANGE_BIDDING,
            budget_change_ratio=0.3,
        )
        result = engine.evaluate(ctx)
        assert "bidding_change_limit" in result.triggered_rules


class TestBatchOperationRule:
    """测试批量操作限制."""

    def test_small_batch_allowed(self):
        """小批量操作 -> ALLOW."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.BATCH_CREATE,
            metadata={"batch_size": 3},
        )
        result = engine.evaluate(ctx)
        assert "batch_operation_limit" not in result.triggered_rules

    def test_large_batch_requires_approval(self):
        """大批量操作 -> REQUIRE_APPROVAL."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.BATCH_CREATE,
            metadata={"batch_size": 10},
        )
        result = engine.evaluate(ctx)
        assert "batch_operation_limit" in result.triggered_rules


class TestBudgetDecreaseRule:
    """测试预算削减规则."""

    def test_small_decrease_allowed(self):
        """小幅度削减 -> ALLOW."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            budget_change_ratio=-0.2,
        )
        result = engine.evaluate(ctx)
        assert "budget_decrease_limit" not in result.triggered_rules

    def test_large_decrease_requires_approval(self):
        """大幅削减 -> REQUIRE_APPROVAL."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            budget_change_ratio=-0.6,
        )
        result = engine.evaluate(ctx)
        assert "budget_decrease_limit" in result.triggered_rules


class TestRiskScoreRule:
    """测试风险评分规则."""

    def test_low_risk_allowed(self):
        """低风险 -> ALLOW."""
        engine = create_policy_engine()
        ctx = make_context(risk_score=0.3)
        result = engine.evaluate(ctx)
        assert "high_risk_score_block" not in result.triggered_rules

    def test_high_risk_blocked(self):
        """高风险 -> BLOCK."""
        engine = create_policy_engine()
        ctx = make_context(risk_score=0.9)
        result = engine.evaluate(ctx)
        assert result.decision == PolicyDecision.BLOCK
        assert "high_risk_score_block" in result.triggered_rules


# ═══════════════════════════════════════════════════════════════
# Test Policy Engine
# ═══════════════════════════════════════════════════════════════


class TestPolicyEngine:
    """测试 PolicyEngine 核心引擎."""

    def test_create_engine(self):
        engine = create_policy_engine()
        assert len(engine.rules) == 12  # 12 条默认规则
        assert not engine.strict_mode

    def test_engine_allows_safe_action(self):
        """安全动作 -> ALLOW."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.PAUSE_CAMPAIGN,
            budget_change_ratio=0.0,
            confidence=0.85,
            agent_consecutive_errors=0,
        )
        result = engine.evaluate(ctx)
        assert result.decision == PolicyDecision.ALLOW

    def test_engine_multiple_rules_most_severe_wins(self):
        """多规则触发时取最严格决策."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            budget_change_ratio=0.5,  # 触发 budget_increase_limit (REQUIRE_APPROVAL)
            confidence=0.5,           # 触发 low_confidence_warning (WARN)
            daily_spend=15000,        # 触发 daily_spend_limit (BLOCK)
            daily_spend_limit=10000,
        )
        result = engine.evaluate(ctx)
        assert result.decision == PolicyDecision.BLOCK  # BLOCK 最严格

    def test_engine_quick_check(self):
        engine = create_policy_engine()
        ctx = make_context(budget_change_ratio=0.1)
        assert engine.quick_check(ctx)  # ALLOW

        ctx2 = make_context(daily_spend=15000, daily_spend_limit=10000)
        assert not engine.quick_check(ctx2)  # BLOCK

    def test_engine_is_blocked(self):
        engine = create_policy_engine()
        ctx = make_context(daily_spend=15000, daily_spend_limit=10000)
        assert engine.is_blocked(ctx)

    def test_engine_needs_approval(self):
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            budget_change_ratio=0.5,
        )
        assert engine.needs_approval(ctx)

    def test_engine_stats(self):
        engine = create_policy_engine()
        ctx = make_context(budget_change_ratio=0.1)
        engine.evaluate(ctx)
        engine.evaluate(ctx)
        assert engine.stats.total_evaluations == 2
        assert engine.stats.total_allowed >= 1

    def test_engine_add_remove_rule(self):
        engine = create_policy_engine()
        initial_count = len(engine.rules)
        rule = build_custom_budget_rule(max_ratio=0.15)
        engine.add_rule(rule)
        assert len(engine.rules) == initial_count + 1
        assert engine.remove_rule(rule.rule_id)
        assert len(engine.rules) == initial_count

    def test_engine_enable_disable_rule(self):
        engine = create_policy_engine()
        first_rule = engine.rules[0]
        assert engine.disable_rule(first_rule.rule_id)
        assert not engine.get_rule(first_rule.rule_id).enabled
        assert engine.enable_rule(first_rule.rule_id)
        assert engine.get_rule(first_rule.rule_id).enabled

    def test_engine_get_rules_by_action(self):
        engine = create_policy_engine()
        rules = engine.get_rules_by_action(PolicyActionType.CREATE_CAMPAIGN)
        assert len(rules) > 0
        for rule in rules:
            assert not rule.action_types or PolicyActionType.CREATE_CAMPAIGN in rule.action_types

    def test_engine_strict_mode(self):
        """严格模式下 REQUIRE_APPROVAL 升级为 BLOCK."""
        engine = PolicyEngine(strict_mode=True)
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            budget_change_ratio=0.5,
        )
        result = engine.evaluate(ctx)
        # 严格模式下 budget_increase_limit 触发 REQUIRE_APPROVAL → 升级为 BLOCK
        assert result.decision == PolicyDecision.BLOCK

    def test_engine_auto_approve_rollback(self):
        """回滚操作自动批准."""
        engine = create_policy_engine(auto_approve_rollback=True)
        ctx = make_context(
            action_type=PolicyActionType.ROLLBACK,
            budget_change_ratio=0.5,  # 本来会触发 REQUIRE_APPROVAL
        )
        result = engine.evaluate(ctx)
        assert result.decision == PolicyDecision.ALLOW

    def test_engine_evaluation_history(self):
        engine = create_policy_engine()
        for i in range(5):
            ctx = make_context(budget_change_ratio=0.1 * (i + 1))
            engine.evaluate(ctx)
        assert len(engine.evaluation_history) == 5

    def test_engine_get_summary(self):
        engine = create_policy_engine()
        summary = engine.get_summary()
        assert "rules_count" in summary
        assert "enabled_rules_count" in summary
        assert summary["rules_count"] == 12

    def test_engine_get_rules_status(self):
        engine = create_policy_engine()
        status = engine.get_rules_status()
        assert len(status) == 12
        for rule in status:
            assert "rule_id" in rule
            assert "name" in rule
            assert "enabled" in rule

    def test_engine_reset_stats(self):
        engine = create_policy_engine()
        ctx = make_context()
        engine.evaluate(ctx)
        engine.reset_stats()
        assert engine.stats.total_evaluations == 0
        assert len(engine.evaluation_history) == 0

    def test_build_default_rules(self):
        rules = build_default_rules()
        assert len(rules) == 12
        # 验证按 priority 排序
        for i in range(len(rules) - 1):
            assert rules[i].priority <= rules[i + 1].priority

    def test_build_custom_budget_rule(self):
        rule = build_custom_budget_rule(max_ratio=0.15, rule_name="my_rule")
        ctx = make_context(action_type=PolicyActionType.UPDATE_BUDGET, budget_change_ratio=0.2)
        result = rule.evaluate(ctx)
        assert result.triggered
        assert result.rule_name == "my_rule"


# ═══════════════════════════════════════════════════════════════
# Test Approval Manager
# ═══════════════════════════════════════════════════════════════


class TestApprovalManager:
    """测试 ApprovalManager."""

    def test_create_approval(self):
        manager = create_approval_manager()
        request = manager.create_approval(
            action_type="update_budget",
            action_params={"campaign_id": "123", "new_budget": 500},
            reason="预算增加超过30%",
        )
        assert request.status == ApprovalStatus.PENDING
        assert request.action_type == "update_budget"
        assert "123" in str(request.action_params)

    def test_create_approval_with_policy_result(self):
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            budget_change_ratio=0.5,
        )
        result = engine.evaluate(ctx)

        manager = create_approval_manager()
        request = manager.create_approval(
            action_type=PolicyActionType.UPDATE_BUDGET,
            reason=result.reason,
            policy_result=result,
        )
        assert request.status == ApprovalStatus.PENDING

    def test_approve_request(self):
        manager = create_approval_manager()
        request = manager.create_approval(
            action_type="update_budget",
            reason="test",
        )
        approved = manager.approve(request.request_id, resolver="admin", note="approved")
        assert approved is not None
        assert approved.status == ApprovalStatus.APPROVED
        assert manager.is_approved(request.request_id)

    def test_reject_request(self):
        manager = create_approval_manager()
        request = manager.create_approval(
            action_type="update_budget",
            reason="test",
        )
        rejected = manager.reject(request.request_id, resolver="admin", note="rejected")
        assert rejected is not None
        assert rejected.status == ApprovalStatus.REJECTED
        assert not manager.is_pending(request.request_id)

    def test_cancel_request(self):
        manager = create_approval_manager()
        request = manager.create_approval(
            action_type="update_budget",
            reason="test",
        )
        cancelled = manager.cancel(request.request_id, note="cancelled by user")
        assert cancelled is not None
        assert cancelled.status == ApprovalStatus.CANCELLED

    def test_expire_request(self):
        manager = create_approval_manager()
        request = manager.create_approval(
            action_type="update_budget",
            reason="test",
        )
        expired = manager.expire(request.request_id)
        assert expired is not None
        assert expired.status == ApprovalStatus.EXPIRED

    def test_get_pending(self):
        manager = create_approval_manager()
        r1 = manager.create_approval(action_type="a", reason="test")
        r2 = manager.create_approval(action_type="b", reason="test")
        pending = manager.get_pending()
        assert len(pending) == 2
        manager.approve(r1.request_id)
        pending = manager.get_pending()
        assert len(pending) == 1

    def test_get_all_active(self):
        manager = create_approval_manager()
        r1 = manager.create_approval(action_type="a", reason="test")
        r2 = manager.create_approval(action_type="b", reason="test")
        manager.approve(r1.request_id)
        active = manager.get_all_active()
        assert len(active) == 2  # 1 approved + 1 pending

    def test_get_history(self):
        manager = create_approval_manager()
        for i in range(3):
            r = manager.create_approval(action_type=f"test_{i}", reason="test")
            manager.reject(r.request_id)
        history = manager.get_history()
        assert len(history) == 3

    def test_get_stats(self):
        manager = create_approval_manager()
        r1 = manager.create_approval(action_type="a", reason="test")
        manager.approve(r1.request_id)
        r2 = manager.create_approval(action_type="b", reason="test")
        manager.reject(r2.request_id)
        r3 = manager.create_approval(action_type="c", reason="test")

        stats = manager.get_stats()
        assert stats["pending_requests"] == 1
        assert stats["status_counts"]["approved"] == 1
        assert stats["status_counts"]["rejected"] == 1

    def test_approve_non_existent(self):
        manager = create_approval_manager()
        result = manager.approve("non_existent_id")
        assert result is None

    def test_approve_already_resolved(self):
        manager = create_approval_manager()
        request = manager.create_approval(action_type="test", reason="test")
        manager.reject(request.request_id)
        result = manager.approve(request.request_id)
        assert result is None

    def test_pending_count(self):
        manager = create_approval_manager()
        assert manager.pending_count == 0
        manager.create_approval(action_type="test", reason="test")
        assert manager.pending_count == 1

    def test_total_count(self):
        manager = create_approval_manager()
        r = manager.create_approval(action_type="test", reason="test")
        manager.reject(r.request_id)
        assert manager.total_count == 1

    def test_reset(self):
        manager = create_approval_manager()
        manager.create_approval(action_type="test", reason="test")
        manager.reset()
        assert manager.pending_count == 0
        assert manager.total_count == 0

    def test_request_is_expired(self):
        request = ApprovalRequest(expires_at="2020-01-01T00:00:00+00:00")
        assert request.is_expired

    def test_request_not_expired(self):
        request = ApprovalRequest(expires_at="2099-01-01T00:00:00+00:00")
        assert not request.is_expired


# ═══════════════════════════════════════════════════════════════
# Test Policy Templates
# ═══════════════════════════════════════════════════════════════


class TestPolicyTemplates:
    """测试预设策略模板."""

    def test_conservative_template(self):
        template = CONSERVATIVE
        assert template.name == "conservative"
        assert template.budget_increase_ratio == 0.1
        assert template.min_confidence == 0.8
        assert template.daily_spend_limit == 1000.0
        assert template.max_campaign_per_day == 2
        assert template.max_creative_per_day == 5
        assert template.min_campaign_age_hours == 48.0
        assert template.max_consecutive_errors == 2
        assert template.max_batch_size == 2
        assert not template.auto_execute

    def test_balanced_template(self):
        template = BALANCED
        assert template.name == "balanced"
        assert template.budget_increase_ratio == 0.2
        assert template.min_confidence == 0.7
        assert template.daily_spend_limit == 5000.0
        assert template.max_campaign_per_day == 5
        assert template.max_creative_per_day == 20
        assert template.min_campaign_age_hours == 24.0
        assert template.max_consecutive_errors == 3
        assert template.max_batch_size == 5

    def test_aggressive_template(self):
        template = AGGRESSIVE
        assert template.name == "aggressive"
        assert template.budget_increase_ratio == 0.5
        assert template.min_confidence == 0.5
        assert template.daily_spend_limit == 50000.0
        assert template.max_campaign_per_day == 20
        assert template.max_creative_per_day == 100
        assert template.min_campaign_age_hours == 6.0
        assert template.auto_execute

    def test_template_create_engine(self):
        """测试模板创建引擎."""
        engine = CONSERVATIVE.create_engine()
        assert isinstance(engine, PolicyEngine)

    def test_template_apply_to_context_defaults(self):
        defaults = BALANCED.apply_to_context_defaults()
        assert defaults["daily_spend_limit"] == 5000.0
        assert defaults["max_campaign_per_day"] == 5
        assert defaults["max_creative_per_day"] == 20

    def test_template_to_dict(self):
        d = BALANCED.to_dict()
        assert d["name"] == "balanced"
        assert "budget_increase_ratio" in d

    def test_get_template(self):
        assert get_template("conservative") is CONSERVATIVE
        assert get_template("balanced") is BALANCED
        assert get_template("aggressive") is AGGRESSIVE
        assert get_template("nonexistent") is None

    def test_get_template_case_insensitive(self):
        assert get_template("CONSERVATIVE") is CONSERVATIVE
        assert get_template("Balanced") is BALANCED

    def test_list_templates(self):
        templates = list_templates()
        assert len(templates) == 3
        names = [t["name"] for t in templates]
        assert "conservative" in names
        assert "balanced" in names
        assert "aggressive" in names

    def test_conservative_engine_stricter(self):
        """保守模式引擎比平衡模式更严格."""
        conservative_engine = CONSERVATIVE.create_engine()
        balanced_engine = BALANCED.create_engine()

        # 15% 预算变动在保守模式触发审批，在平衡模式不触发
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            budget_change_ratio=0.15,
        )
        c_result = conservative_engine.evaluate(ctx)
        b_result = balanced_engine.evaluate(ctx)

        assert c_result.decision == PolicyDecision.REQUIRE_APPROVAL
        assert b_result.decision != PolicyDecision.REQUIRE_APPROVAL

    def test_aggressive_engine_more_lenient(self):
        """激进模式引擎更宽松."""
        aggressive_engine = AGGRESSIVE.create_engine()
        balanced_engine = BALANCED.create_engine()

        # 30% 预算变动在激进模式不触发审批，在平衡模式触发
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            budget_change_ratio=0.3,
        )
        a_result = aggressive_engine.evaluate(ctx)
        assert "budget_increase_limit" not in a_result.triggered_rules

        b_result = balanced_engine.evaluate(ctx)
        # balanced 用的是 20% 上限，30% > 20% 会触发
        assert "budget_increase_limit" in b_result.triggered_rules


# ═══════════════════════════════════════════════════════════════
# Test Integration
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """测试 PolicyEngine + ApprovalManager 完整链路."""

    def test_full_pipeline_allow(self):
        """完整链路: 评估 → ALLOW → 直接执行."""
        engine = create_policy_engine()
        manager = create_approval_manager()

        ctx = make_context(
            action_type=PolicyActionType.PAUSE_CAMPAIGN,
            budget_change_ratio=0.0,
        )
        result = engine.evaluate(ctx)

        if result.decision in (PolicyDecision.ALLOW, PolicyDecision.WARN):
            # 直接执行
            assert True
        elif result.requires_approval:
            manager.create_approval(
                action_type=PolicyActionType.PAUSE_CAMPAIGN,
                reason=result.reason,
                policy_result=result,
            )

    def test_full_pipeline_require_approval(self):
        """完整链路: 评估 → REQUIRE_APPROVAL → 创建审批 → 批准 → 执行."""
        engine = create_policy_engine()
        manager = create_approval_manager()

        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            budget_change_ratio=0.5,
        )
        result = engine.evaluate(ctx)
        assert result.requires_approval

        # 创建审批
        request = manager.create_approval(
            action_type=PolicyActionType.UPDATE_BUDGET,
            action_params={"campaign_id": "123", "new_budget": 1500},
            reason=result.reason,
            policy_result=result,
        )
        assert request.status == ApprovalStatus.PENDING

        # 批准
        manager.approve(request.request_id, resolver="admin")
        assert manager.is_approved(request.request_id)

        # 执行 (模拟)
        assert True

    def test_full_pipeline_block(self):
        """完整链路: 评估 → BLOCK → 不执行."""
        engine = create_policy_engine()
        manager = create_approval_manager()

        ctx = make_context(
            daily_spend=15000,
            daily_spend_limit=10000,
        )
        result = engine.evaluate(ctx)
        assert result.is_blocked

        # 被阻止，不创建审批，不执行
        assert result.decision == PolicyDecision.BLOCK

    def test_full_pipeline_reject_flow(self):
        """完整链路: 评估 → REQUIRE_APPROVAL → 创建审批 → 拒绝."""
        engine = create_policy_engine()
        manager = create_approval_manager()

        ctx = make_context(
            action_type=PolicyActionType.CHANGE_TARGETING,
        )
        result = engine.evaluate(ctx)
        assert result.requires_approval

        request = manager.create_approval(
            action_type=PolicyActionType.CHANGE_TARGETING,
            reason=result.reason,
            policy_result=result,
        )

        manager.reject(request.request_id, resolver="admin", note="targeting not ready")
        assert not manager.is_pending(request.request_id)
        assert not manager.is_approved(request.request_id)

    def test_multiple_actions_different_decisions(self):
        """测试不同动作类型的不同决策结果."""
        engine = create_policy_engine()

        scenarios = [
            (PolicyActionType.PAUSE_CAMPAIGN, 0.0, 0.0, PolicyDecision.ALLOW),
            (PolicyActionType.UPDATE_BUDGET, 0.5, 0.0, PolicyDecision.REQUIRE_APPROVAL),
            (PolicyActionType.CHANGE_TARGETING, 0.0, 0.0, PolicyDecision.REQUIRE_APPROVAL),
        ]

        for action_type, budget_ratio, risk, expected in scenarios:
            ctx = make_context(
                action_type=action_type,
                budget_change_ratio=budget_ratio,
                risk_score=risk,
            )
            result = engine.evaluate(ctx)
            assert result.decision == expected, f"Failed for {action_type}: expected {expected}, got {result.decision}"

    def test_engine_stats_accumulation(self):
        """测试统计累积."""
        engine = create_policy_engine()

        # 10 次 ALLOW
        for _ in range(10):
            ctx = make_context(budget_change_ratio=0.1)
            engine.evaluate(ctx)

        # 5 次 REQUIRE_APPROVAL
        for _ in range(5):
            ctx = make_context(budget_change_ratio=0.5, action_type=PolicyActionType.UPDATE_BUDGET)
            engine.evaluate(ctx)

        # 2 次 BLOCK
        for _ in range(2):
            ctx = make_context(daily_spend=15000, daily_spend_limit=10000)
            engine.evaluate(ctx)

        stats = engine.stats
        assert stats.total_evaluations == 17
        assert stats.total_blocked == 2
        assert stats.total_approval_required >= 5

    def test_conservative_mode_full_cycle(self):
        """保守模式完整循环."""
        engine = CONSERVATIVE.create_engine()
        manager = create_approval_manager()

        # 保守模式下 15% 预算变动触发审批
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            budget_change_ratio=0.15,
        )
        result = engine.evaluate(ctx)
        assert result.requires_approval

        # 创建审批
        request = manager.create_approval(
            action_type=PolicyActionType.UPDATE_BUDGET,
            action_params={"campaign_id": "123", "new_budget": 1150},
            reason=result.reason,
            policy_result=result,
        )

        # 批准
        manager.approve(request.request_id, resolver="admin")
        assert manager.is_approved(request.request_id)

        # 保守模式下日花费 $1500 触发 BLOCK
        ctx2 = make_context(
            daily_spend=1500,
            daily_spend_limit=1000,  # 保守模式默认 $1000
        )
        result2 = engine.evaluate(ctx2)
        assert result2.is_blocked


# ═══════════════════════════════════════════════════════════════
# Test Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """测试边界情况."""

    def test_empty_context(self):
        """空上下文评估 (confidence=0.5 触发低置信度警告)."""
        engine = create_policy_engine()
        ctx = PolicyContext()
        result = engine.evaluate(ctx)
        # 空上下文 confidence=0.5 < 0.7，触发 WARN
        assert result.decision == PolicyDecision.WARN

    def test_extreme_confidence_zero(self):
        """置信度为 0."""
        engine = create_policy_engine()
        ctx = make_context(confidence=0.0)
        result = engine.evaluate(ctx)
        assert "low_confidence_warning" in result.triggered_rules

    def test_extreme_confidence_one(self):
        """置信度为 1."""
        engine = create_policy_engine()
        ctx = make_context(confidence=1.0)
        result = engine.evaluate(ctx)
        assert "low_confidence_warning" not in result.triggered_rules

    def test_negative_budget_change(self):
        """负预算变动 (削减)."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            budget_change_ratio=-0.1,
        )
        result = engine.evaluate(ctx)
        assert result.decision == PolicyDecision.ALLOW

    def test_zero_budget_change(self):
        """零预算变动."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            budget_change_ratio=0.0,
        )
        result = engine.evaluate(ctx)
        assert result.decision == PolicyDecision.ALLOW

    def test_very_large_budget_change(self):
        """极大预算变动."""
        engine = create_policy_engine()
        ctx = make_context(
            action_type=PolicyActionType.UPDATE_BUDGET,
            budget_change_ratio=10.0,  # 1000%
        )
        result = engine.evaluate(ctx)
        assert result.decision in (PolicyDecision.REQUIRE_APPROVAL, PolicyDecision.BLOCK)

    def test_engine_with_no_rules(self):
        """无规则引擎."""
        engine = PolicyEngine(rules=[])
        ctx = make_context(daily_spend=15000, daily_spend_limit=10000)
        result = engine.evaluate(ctx)
        assert result.decision == PolicyDecision.ALLOW

    def test_approval_manager_queue_full(self):
        """审批队列满."""
        manager = ApprovalManager(max_pending=2)
        manager.create_approval(action_type="a", reason="test")
        manager.create_approval(action_type="b", reason="test")
        with pytest.raises(ValueError, match="待审批队列已满"):
            manager.create_approval(action_type="c", reason="test")