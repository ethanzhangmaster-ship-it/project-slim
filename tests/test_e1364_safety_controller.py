"""E13.6.4 Safety Controller — 测试套件.

覆盖:
  - Safety Models (SafetyDecision, RiskCategory, SafetyRule, SafetyEvaluation, ApprovalRequest)
  - Safety Rules (预算放量/缩减, 素材变异, 暂停/冻结, 回滚保护, 日预算上限)
  - Safety Policy (策略管理, 规则增删, 默认/激进/保守策略)
  - Approval Manager (创建审批, 批准/拒绝, 过期, 查询)
  - Safety Engine (单动作评估, 计划评估, 上下文集成)
  - Integration (完整链路: SafetyEngine → ExecutionContext → ExecutionEngine)
"""

import pytest

from market_ops.creative_vision_runtime.growth_runtime.execution import (
    ExecutionAction,
    ExecutionActionType,
    ExecutionContext,
    ExecutionDomain,
    ExecutionEngine,
    ExecutionPriority,
    ExecutorRegistry,
    GuardContext,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.safety import (
    ApprovalManager,
    ApprovalRequest,
    ApprovalStatus,
    RiskCategory,
    RuleResult,
    RuleSeverity,
    SafetyDecision,
    SafetyEngine,
    SafetyEvaluation,
    SafetyPolicy,
    SafetyRule,
    budget_reduce_rule,
    budget_scale_rule,
    campaign_create_rule,
    campaign_freeze_rule,
    campaign_pause_rule,
    create_aggressive_policy,
    create_conservative_policy,
    create_default_policy,
    creative_mutation_safety_rule,
    daily_budget_cap_rule,
    get_rules_for_action_type,
    rollback_protection_rule,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def make_action(
    action_type: ExecutionActionType = ExecutionActionType.MONITOR,
    **params,
) -> ExecutionAction:
    """创建测试用 ExecutionAction."""
    return ExecutionAction(
        action_type=action_type,
        domain=ExecutionDomain.MONITOR,
        parameters=params,
    )


def make_context(**kwargs) -> ExecutionContext:
    """创建测试用 ExecutionContext."""
    return ExecutionContext(**kwargs)


# ═══════════════════════════════════════════════════════════════
# Test Safety Decision
# ═══════════════════════════════════════════════════════════════


class TestSafetyDecision:
    """测试 SafetyDecision 枚举."""

    def test_allow(self):
        assert SafetyDecision.ALLOW.value == "allow"

    def test_warn(self):
        assert SafetyDecision.WARN.value == "warn"

    def test_block(self):
        assert SafetyDecision.BLOCK.value == "block"

    def test_require_approval(self):
        assert SafetyDecision.REQUIRE_APPROVAL.value == "require_approval"

    def test_all_values(self):
        values = [d.value for d in SafetyDecision]
        assert "allow" in values
        assert "warn" in values
        assert "block" in values
        assert "require_approval" in values


class TestRiskCategory:
    """测试 RiskCategory 枚举."""

    def test_budget_scale(self):
        assert RiskCategory.BUDGET_SCALE.value == "budget_scale"

    def test_creative_mutation(self):
        assert RiskCategory.CREATIVE_MUTATION.value == "creative_mutation"

    def test_campaign_pause(self):
        assert RiskCategory.CAMPAIGN_PAUSE.value == "campaign_pause"

    def test_all_categories(self):
        categories = [c.value for c in RiskCategory]
        assert "budget_scale" in categories
        assert "budget_reduce" in categories
        assert "creative_mutation" in categories
        assert "campaign_pause" in categories
        assert "rollback" in categories
        assert "general" in categories


class TestApprovalStatus:
    """测试 ApprovalStatus 枚举."""

    def test_pending(self):
        assert ApprovalStatus.PENDING.value == "pending"

    def test_approved(self):
        assert ApprovalStatus.APPROVED.value == "approved"

    def test_denied(self):
        assert ApprovalStatus.DENIED.value == "denied"

    def test_expired(self):
        assert ApprovalStatus.EXPIRED.value == "expired"


class TestRuleSeverity:
    """测试 RuleSeverity 枚举."""

    def test_critical(self):
        assert RuleSeverity.CRITICAL.value == "critical"

    def test_high(self):
        assert RuleSeverity.HIGH.value == "high"

    def test_medium(self):
        assert RuleSeverity.MEDIUM.value == "medium"

    def test_low(self):
        assert RuleSeverity.LOW.value == "low"


# ═══════════════════════════════════════════════════════════════
# Test Safety Rule
# ═══════════════════════════════════════════════════════════════


class TestSafetyRule:
    """测试 SafetyRule 模型."""

    def test_create_default(self):
        rule = SafetyRule(name="test_rule")
        assert rule.name == "test_rule"
        assert rule.enabled is True
        assert rule.priority == 100

    def test_evaluate_not_triggered(self):
        rule = SafetyRule(
            name="test",
            condition=lambda a, c: False,
            decision=SafetyDecision.WARN,
        )
        triggered, reason, decision = rule.evaluate(None, None)
        assert triggered is False
        assert decision == SafetyDecision.ALLOW

    def test_evaluate_triggered(self):
        rule = SafetyRule(
            name="test",
            condition=lambda a, c: True,
            decision=SafetyDecision.BLOCK,
            reason_template="blocked_reason",
        )
        triggered, reason, decision = rule.evaluate(None, None)
        assert triggered is True
        assert reason == "blocked_reason"
        assert decision == SafetyDecision.BLOCK

    def test_evaluate_disabled_rule(self):
        rule = SafetyRule(
            name="test",
            condition=lambda a, c: True,
            decision=SafetyDecision.BLOCK,
            enabled=False,
        )
        triggered, reason, decision = rule.evaluate(None, None)
        assert triggered is False

    def test_evaluate_no_condition(self):
        rule = SafetyRule(name="test")
        triggered, reason, decision = rule.evaluate(None, None)
        assert triggered is False

    def test_evaluate_with_decision_fn(self):
        def _decision_fn(a, c):
            return SafetyDecision.BLOCK

        rule = SafetyRule(
            name="test",
            condition=lambda a, c: True,
            decision=SafetyDecision.WARN,
            decision_fn=_decision_fn,
        )
        triggered, reason, decision = rule.evaluate(None, None)
        assert decision == SafetyDecision.BLOCK

    def test_evaluate_with_reason_fn(self):
        def _reason_fn(a, c):
            return "dynamic_reason"

        rule = SafetyRule(
            name="test",
            condition=lambda a, c: True,
            reason_template="static",
            reason_fn=_reason_fn,
        )
        triggered, reason, decision = rule.evaluate(None, None)
        assert reason == "dynamic_reason"

    def test_evaluate_exception_safe(self):
        def _bad_condition(a, c):
            raise ValueError("error")

        rule = SafetyRule(
            name="test",
            condition=_bad_condition,
        )
        triggered, reason, decision = rule.evaluate(None, None)
        assert triggered is False

    def test_to_dict(self):
        rule = SafetyRule(
            name="test_rule",
            description="desc",
            category=RiskCategory.BUDGET_SCALE,
            severity=RuleSeverity.HIGH,
            decision=SafetyDecision.BLOCK,
            reason_template="reason",
            priority=10,
        )
        d = rule.to_dict()
        assert d["name"] == "test_rule"
        assert d["category"] == "budget_scale"
        assert d["decision"] == "block"


# ═══════════════════════════════════════════════════════════════
# Test Safety Evaluation
# ═══════════════════════════════════════════════════════════════


class TestRuleResult:
    """测试 RuleResult 模型."""

    def test_create_default(self):
        rr = RuleResult()
        assert rr.triggered is False

    def test_triggered_result(self):
        rr = RuleResult(
            rule_name="test",
            triggered=True,
            decision=SafetyDecision.BLOCK,
            reason="reason",
        )
        assert rr.triggered is True
        assert rr.decision == SafetyDecision.BLOCK
        assert rr.reason == "reason"

    def test_to_dict(self):
        rr = RuleResult(
            rule_id="r1",
            rule_name="test",
            triggered=True,
            decision=SafetyDecision.WARN,
            reason="warning",
        )
        d = rr.to_dict()
        assert d["rule_id"] == "r1"
        assert d["triggered"] is True
        assert d["decision"] == "warn"


class TestSafetyEvaluation:
    """测试 SafetyEvaluation 模型."""

    def test_create_default(self):
        ev = SafetyEvaluation()
        assert ev.decision == SafetyDecision.ALLOW
        assert ev.risk_score == 0.0
        assert ev.is_blocked is False
        assert ev.is_allowed is True

    def test_blocked_evaluation(self):
        ev = SafetyEvaluation(
            decision=SafetyDecision.BLOCK,
            is_blocked=True,
        )
        assert ev.is_blocked is True
        assert ev.is_allowed is False

    def test_requires_approval(self):
        ev = SafetyEvaluation(
            decision=SafetyDecision.REQUIRE_APPROVAL,
            requires_approval=True,
        )
        assert ev.requires_approval is True

    def test_with_warnings(self):
        ev = SafetyEvaluation(warnings=["w1", "w2"])
        assert ev.has_warnings is True
        assert len(ev.warnings) == 2

    def test_triggered_rules(self):
        ev = SafetyEvaluation(
            triggered_rules=["rule1", "rule2"],
            reasons=["reason1", "reason2"],
        )
        assert ev.triggered_count == 2
        assert len(ev.reasons) == 2

    def test_to_dict(self):
        ev = SafetyEvaluation(
            action_id="act_1",
            action_type="scale_budget",
            decision=SafetyDecision.WARN,
            risk_score=0.5,
            warnings=["w1"],
        )
        d = ev.to_dict()
        assert d["action_id"] == "act_1"
        assert d["decision"] == "warn"
        assert d["risk_score"] == 0.5


# ═══════════════════════════════════════════════════════════════
# Test Approval Request
# ═══════════════════════════════════════════════════════════════


class TestApprovalRequest:
    """测试 ApprovalRequest 模型."""

    def test_create_default(self):
        req = ApprovalRequest()
        assert req.is_pending is True
        assert req.is_approved is False
        assert req.is_denied is False

    def test_approve(self):
        req = ApprovalRequest()
        req.approve("admin", "looks good")
        assert req.is_approved is True
        assert req.approved_by == "admin"
        assert req.notes == "looks good"
        assert req.approved_at != ""

    def test_deny(self):
        req = ApprovalRequest()
        req.deny("admin", "too risky")
        assert req.is_denied is True
        assert req.approved_by == "admin"
        assert req.notes == "too risky"

    def test_cancel(self):
        req = ApprovalRequest()
        req.cancel()
        assert req.status == ApprovalStatus.CANCELLED

    def test_expire(self):
        req = ApprovalRequest()
        req.expire()
        assert req.status == ApprovalStatus.EXPIRED

    def test_is_expired_by_expires_at(self):
        from datetime import datetime, timezone, timedelta
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        req = ApprovalRequest(expires_at=past)
        assert req.is_expired is True

    def test_is_not_expired_future(self):
        from datetime import datetime, timezone, timedelta
        future = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        req = ApprovalRequest(expires_at=future)
        assert req.is_expired is False

    def test_to_dict(self):
        req = ApprovalRequest(
            action_id="act_1",
            action_type="scale_budget",
            risk_score=0.7,
            reason="high_risk",
        )
        d = req.to_dict()
        assert d["action_id"] == "act_1"
        assert d["status"] == "pending"


# ═══════════════════════════════════════════════════════════════
# Test Safety Rules — Budget
# ═══════════════════════════════════════════════════════════════


class TestBudgetScaleRule:
    """测试预算放量规则."""

    def test_below_warn_allowed(self):
        rule = budget_scale_rule()
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=50)
        ctx = make_context()
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is False

    def test_warn_threshold(self):
        rule = budget_scale_rule()
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=200)
        ctx = make_context()
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is True
        assert decision == SafetyDecision.WARN

    def test_approval_threshold(self):
        rule = budget_scale_rule()
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=600)
        ctx = make_context()
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is True
        assert decision == SafetyDecision.REQUIRE_APPROVAL

    def test_block_threshold(self):
        rule = budget_scale_rule()
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=1500)
        ctx = make_context()
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is True
        assert decision == SafetyDecision.BLOCK

    def test_from_guard_context(self):
        rule = budget_scale_rule()
        action = make_action(ExecutionActionType.SCALE_BUDGET)
        ctx = make_context(guard_context=GuardContext(budget_impact=800))
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert decision == SafetyDecision.REQUIRE_APPROVAL

    def test_custom_thresholds(self):
        rule = budget_scale_rule(
            budget_threshold_warn=200,
            budget_threshold_approval=1000,
            budget_threshold_block=2000,
        )
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=1500)
        ctx = make_context()
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert decision == SafetyDecision.REQUIRE_APPROVAL


class TestBudgetReduceRule:
    """测试预算缩减规则."""

    def test_below_threshold_allowed(self):
        rule = budget_reduce_rule()
        action = make_action(ExecutionActionType.REDUCE_BUDGET, reduce_pct=30)
        ctx = make_context()
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is False

    def test_above_threshold(self):
        rule = budget_reduce_rule()
        action = make_action(ExecutionActionType.REDUCE_BUDGET, reduce_pct=60)
        ctx = make_context()
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is True
        assert decision == SafetyDecision.REQUIRE_APPROVAL

    def test_custom_threshold(self):
        rule = budget_reduce_rule(max_reduce_pct=30)
        action = make_action(ExecutionActionType.REDUCE_BUDGET, reduce_pct=40)
        ctx = make_context()
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is True


class TestDailyBudgetCapRule:
    """测试日预算上限规则."""

    def test_within_cap(self):
        rule = daily_budget_cap_rule(10000)
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=500)
        ctx = make_context(metadata={"daily_spend": 5000})
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is False

    def test_exceeds_cap(self):
        rule = daily_budget_cap_rule(10000)
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=500)
        ctx = make_context(metadata={"daily_spend": 9800})
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is True
        assert decision == SafetyDecision.BLOCK


# ═══════════════════════════════════════════════════════════════
# Test Safety Rules — Creative
# ═══════════════════════════════════════════════════════════════


class TestCreativeMutationRule:
    """测试素材变异规则."""

    def test_high_confidence_allowed(self):
        rule = creative_mutation_safety_rule()
        action = make_action(ExecutionActionType.MUTATE_CREATIVE)
        ctx = make_context(guard_context=GuardContext(confidence=0.8))
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is False

    def test_medium_confidence_warn(self):
        rule = creative_mutation_safety_rule()
        action = make_action(ExecutionActionType.MUTATE_CREATIVE)
        ctx = make_context(guard_context=GuardContext(confidence=0.5))
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is True
        assert decision == SafetyDecision.WARN

    def test_low_confidence_block(self):
        rule = creative_mutation_safety_rule()
        action = make_action(ExecutionActionType.MUTATE_CREATIVE)
        ctx = make_context(guard_context=GuardContext(confidence=0.1))
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is True
        assert decision == SafetyDecision.BLOCK

    def test_custom_thresholds(self):
        rule = creative_mutation_safety_rule(
            min_confidence=0.8,
            block_confidence=0.5,
        )
        action = make_action(ExecutionActionType.MUTATE_CREATIVE)
        ctx = make_context(guard_context=GuardContext(confidence=0.6))
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is True
        assert decision == SafetyDecision.WARN


# ═══════════════════════════════════════════════════════════════
# Test Safety Rules — Campaign
# ═══════════════════════════════════════════════════════════════


class TestCampaignPauseRule:
    """测试暂停广告系列规则."""

    def test_old_campaign_allowed(self):
        rule = campaign_pause_rule()
        action = make_action(ExecutionActionType.PAUSE_CAMPAIGN, campaign_age_hours=48)
        ctx = make_context()
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is False

    def test_new_campaign_blocked(self):
        rule = campaign_pause_rule()
        action = make_action(ExecutionActionType.PAUSE_CAMPAIGN, campaign_age_hours=10)
        ctx = make_context()
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is True
        assert decision == SafetyDecision.BLOCK

    def test_custom_age(self):
        rule = campaign_pause_rule(min_campaign_age_hours=48)
        action = make_action(ExecutionActionType.PAUSE_CAMPAIGN, campaign_age_hours=24)
        ctx = make_context()
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is True


class TestCampaignFreezeRule:
    """测试冻结广告系列规则."""

    def test_always_require_approval(self):
        rule = campaign_freeze_rule()
        action = make_action(ExecutionActionType.FREEZE_CAMPAIGN)
        ctx = make_context()
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is True
        assert decision == SafetyDecision.REQUIRE_APPROVAL


class TestCampaignCreateRule:
    """测试创建广告系列规则."""

    def test_below_limit_allowed(self):
        rule = campaign_create_rule(50)
        action = make_action(ExecutionActionType.CREATE_CAMPAIGN)
        ctx = make_context(metadata={"active_campaigns": 30})
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is False

    def test_at_limit_warn(self):
        rule = campaign_create_rule(50)
        action = make_action(ExecutionActionType.CREATE_CAMPAIGN)
        ctx = make_context(metadata={"active_campaigns": 50})
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is True
        assert decision == SafetyDecision.WARN


# ═══════════════════════════════════════════════════════════════
# Test Safety Rules — Rollback
# ═══════════════════════════════════════════════════════════════


class TestRollbackProtectionRule:
    """测试回滚保护规则."""

    def test_below_limit_allowed(self):
        rule = rollback_protection_rule(3)
        action = make_action()
        ctx = make_context(metadata={"consecutive_failures": 1})
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is False

    def test_at_limit_blocked(self):
        rule = rollback_protection_rule(3)
        action = make_action()
        ctx = make_context(metadata={"consecutive_failures": 3})
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is True
        assert decision == SafetyDecision.BLOCK

    def test_above_limit_blocked(self):
        rule = rollback_protection_rule(3)
        action = make_action()
        ctx = make_context(metadata={"consecutive_failures": 5})
        triggered, reason, decision = rule.evaluate(action, ctx)
        assert triggered is True
        assert decision == SafetyDecision.BLOCK


# ═══════════════════════════════════════════════════════════════
# Test Rule Factory
# ═══════════════════════════════════════════════════════════════


class TestGetRulesForActionType:
    """测试按动作类型获取规则."""

    def test_scale_budget_rules(self):
        rules = get_rules_for_action_type("scale_budget")
        names = [r.name for r in rules]
        assert "budget_scale_limit" in names
        assert "daily_budget_cap" in names
        assert "rollback_protection" in names

    def test_reduce_budget_rules(self):
        rules = get_rules_for_action_type("reduce_budget")
        names = [r.name for r in rules]
        assert "budget_reduce_limit" in names

    def test_mutate_creative_rules(self):
        rules = get_rules_for_action_type("mutate_creative")
        names = [r.name for r in rules]
        assert "creative_mutation_safety" in names

    def test_pause_campaign_rules(self):
        rules = get_rules_for_action_type("pause_campaign")
        names = [r.name for r in rules]
        assert "campaign_pause_protection" in names

    def test_freeze_campaign_rules(self):
        rules = get_rules_for_action_type("freeze_campaign")
        names = [r.name for r in rules]
        assert "campaign_freeze_approval" in names

    def test_create_campaign_rules(self):
        rules = get_rules_for_action_type("create_campaign")
        names = [r.name for r in rules]
        assert "campaign_create_limit" in names

    def test_all_include_rollback(self):
        for at in ["scale_budget", "mutate_creative", "monitor", "pause_campaign"]:
            rules = get_rules_for_action_type(at)
            names = [r.name for r in rules]
            assert "rollback_protection" in names


# ═══════════════════════════════════════════════════════════════
# Test Safety Policy
# ═══════════════════════════════════════════════════════════════


class TestSafetyPolicy:
    """测试 SafetyPolicy 模型."""

    def test_create_default(self):
        policy = SafetyPolicy(name="test")
        assert policy.name == "test"
        assert policy.rule_count == 0
        assert policy.enabled is True

    def test_add_rule(self):
        policy = SafetyPolicy()
        rule = SafetyRule(name="r1")
        policy.add_rule(rule)
        assert policy.rule_count == 1

    def test_remove_rule(self):
        policy = SafetyPolicy()
        rule = SafetyRule(name="r1")
        policy.add_rule(rule)
        assert policy.remove_rule(rule.rule_id) is True
        assert policy.rule_count == 0

    def test_remove_nonexistent(self):
        policy = SafetyPolicy()
        assert policy.remove_rule("nonexistent") is False

    def test_get_rule(self):
        policy = SafetyPolicy()
        rule = SafetyRule(name="r1")
        policy.add_rule(rule)
        found = policy.get_rule(rule.rule_id)
        assert found is not None
        assert found.name == "r1"

    def test_enable_disable_rule(self):
        policy = SafetyPolicy()
        rule = SafetyRule(name="r1")
        policy.add_rule(rule)
        assert policy.disable_rule(rule.rule_id) is True
        assert rule.enabled is False
        assert policy.enable_rule(rule.rule_id) is True
        assert rule.enabled is True

    def test_get_enabled_rules(self):
        policy = SafetyPolicy()
        r1 = SafetyRule(name="r1", enabled=True)
        r2 = SafetyRule(name="r2", enabled=False)
        policy.add_rule(r1)
        policy.add_rule(r2)
        assert policy.enabled_rule_count == 1

    def test_get_rules_by_category(self):
        policy = SafetyPolicy()
        r1 = SafetyRule(name="r1", category=RiskCategory.BUDGET_SCALE)
        r2 = SafetyRule(name="r2", category=RiskCategory.CREATIVE_MUTATION)
        policy.add_rule(r1)
        policy.add_rule(r2)
        budget_rules = policy.get_rules_by_category(RiskCategory.BUDGET_SCALE)
        assert len(budget_rules) == 1
        assert budget_rules[0].name == "r1"

    def test_get_rules_sorted(self):
        policy = SafetyPolicy()
        r1 = SafetyRule(name="r1", priority=100)
        r2 = SafetyRule(name="r2", priority=10)
        policy.add_rule(r1)
        policy.add_rule(r2)
        sorted_rules = policy.get_rules_sorted()
        assert sorted_rules[0].priority == 10
        assert sorted_rules[1].priority == 100

    def test_to_dict(self):
        policy = SafetyPolicy(name="test", version="1.0.0")
        policy.add_rule(SafetyRule(name="r1"))
        d = policy.to_dict()
        assert d["name"] == "test"
        assert d["rule_count"] == 1


class TestDefaultPolicy:
    """测试默认策略."""

    def test_create_default_policy(self):
        policy = create_default_policy()
        assert policy.name == "default_safety_policy"
        assert policy.rule_count == 8

    def test_create_aggressive_policy(self):
        policy = create_aggressive_policy()
        assert policy.name == "aggressive_safety_policy"
        assert policy.rule_count == 4

    def test_create_conservative_policy(self):
        policy = create_conservative_policy()
        assert policy.name == "conservative_safety_policy"
        assert policy.rule_count == 8


# ═══════════════════════════════════════════════════════════════
# Test Approval Manager
# ═══════════════════════════════════════════════════════════════


class TestApprovalManager:
    """测试 ApprovalManager."""

    def test_create_approval(self):
        mgr = ApprovalManager()
        ev = SafetyEvaluation(
            action_id="act_1",
            action_type="scale_budget",
            risk_score=0.7,
            reasons=["high_budget"],
        )
        req = mgr.create_approval(ev)
        assert req.is_pending is True
        assert req.action_id == "act_1"
        assert req.risk_score == 0.7

    def test_create_approval_for_action(self):
        mgr = ApprovalManager()
        req = mgr.create_approval_for_action(
            action_id="act_2",
            action_type="freeze_campaign",
            risk_score=0.9,
            reason="critical",
        )
        assert req.is_pending is True
        assert req.action_id == "act_2"

    def test_approve_request(self):
        mgr = ApprovalManager()
        ev = SafetyEvaluation(action_id="act_1", action_type="test")
        req = mgr.create_approval(ev)
        result = mgr.approve(req.request_id, "admin", "approved")
        assert result is not None
        assert result.is_approved is True

    def test_deny_request(self):
        mgr = ApprovalManager()
        ev = SafetyEvaluation(action_id="act_1", action_type="test")
        req = mgr.create_approval(ev)
        result = mgr.deny(req.request_id, "admin", "denied")
        assert result is not None
        assert result.is_denied is True

    def test_cancel_request(self):
        mgr = ApprovalManager()
        ev = SafetyEvaluation(action_id="act_1", action_type="test")
        req = mgr.create_approval(ev)
        result = mgr.cancel(req.request_id)
        assert result is not None
        assert result.status == ApprovalStatus.CANCELLED

    def test_get_pending(self):
        mgr = ApprovalManager()
        ev1 = SafetyEvaluation(action_id="act_1", action_type="test")
        ev2 = SafetyEvaluation(action_id="act_2", action_type="test")
        mgr.create_approval(ev1)
        req2 = mgr.create_approval(ev2)
        mgr.approve(req2.request_id)
        pending = mgr.get_pending()
        assert len(pending) == 1

    def test_get_by_action(self):
        mgr = ApprovalManager()
        ev = SafetyEvaluation(action_id="act_1", action_type="test")
        mgr.create_approval(ev)
        results = mgr.get_by_action("act_1")
        assert len(results) == 1

    def test_is_action_approved(self):
        mgr = ApprovalManager()
        ev = SafetyEvaluation(action_id="act_1", action_type="test")
        req = mgr.create_approval(ev)
        assert mgr.is_action_approved("act_1") is False
        mgr.approve(req.request_id)
        assert mgr.is_action_approved("act_1") is True

    def test_is_action_denied(self):
        mgr = ApprovalManager()
        ev = SafetyEvaluation(action_id="act_1", action_type="test")
        req = mgr.create_approval(ev)
        mgr.deny(req.request_id)
        assert mgr.is_action_denied("act_1") is True

    def test_has_pending_approval(self):
        mgr = ApprovalManager()
        ev = SafetyEvaluation(action_id="act_1", action_type="test")
        mgr.create_approval(ev)
        assert mgr.has_pending_approval("act_1") is True
        assert mgr.has_pending_approval("act_2") is False

    def test_expire_stale(self):
        mgr = ApprovalManager()
        from datetime import datetime, timezone, timedelta
        past = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        ev = SafetyEvaluation(action_id="act_1", action_type="test")
        req = mgr.create_approval(ev, expires_in_hours=-1)
        req.expires_at = past
        count = mgr.expire_stale_requests()
        assert count >= 1

    def test_stats(self):
        mgr = ApprovalManager()
        ev = SafetyEvaluation(action_id="act_1", action_type="test")
        req = mgr.create_approval(ev)
        mgr.approve(req.request_id)
        stats = mgr.stats()
        assert stats["total"] == 1
        assert stats["approved"] == 1

    def test_clear(self):
        mgr = ApprovalManager()
        ev = SafetyEvaluation(action_id="act_1", action_type="test")
        mgr.create_approval(ev)
        mgr.clear()
        assert len(mgr.requests) == 0
        assert len(mgr.history) == 0

    def test_to_dict(self):
        mgr = ApprovalManager()
        ev = SafetyEvaluation(action_id="act_1", action_type="test")
        mgr.create_approval(ev)
        d = mgr.to_dict()
        assert "requests" in d
        assert "stats" in d


# ═══════════════════════════════════════════════════════════════
# Test Safety Engine
# ═══════════════════════════════════════════════════════════════


class TestSafetyEngine:
    """测试 SafetyEngine."""

    def test_create_default(self):
        engine = SafetyEngine()
        assert engine.policy is not None
        assert engine.enable_auto_rules is True

    def test_evaluate_safe_action(self):
        engine = SafetyEngine()
        action = make_action(ExecutionActionType.MONITOR)
        ctx = make_context()
        ev = engine.evaluate(action, ctx)
        assert ev.decision == SafetyDecision.ALLOW
        assert ev.is_blocked is False

    def test_evaluate_high_budget_blocked(self):
        engine = SafetyEngine()
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=2000)
        ctx = make_context()
        ev = engine.evaluate(action, ctx)
        assert ev.decision == SafetyDecision.BLOCK
        assert ev.is_blocked is True

    def test_evaluate_medium_budget_approval(self):
        engine = SafetyEngine()
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=600)
        ctx = make_context()
        ev = engine.evaluate(action, ctx)
        assert ev.requires_approval is True

    def test_evaluate_low_confidence_creative(self):
        engine = SafetyEngine()
        action = make_action(ExecutionActionType.MUTATE_CREATIVE)
        ctx = make_context(guard_context=GuardContext(confidence=0.2))
        ev = engine.evaluate(action, ctx)
        assert ev.decision == SafetyDecision.BLOCK

    def test_evaluate_freeze_campaign(self):
        engine = SafetyEngine()
        action = make_action(ExecutionActionType.FREEZE_CAMPAIGN)
        ctx = make_context()
        ev = engine.evaluate(action, ctx)
        assert ev.requires_approval is True

    def test_evaluate_new_campaign_pause_blocked(self):
        engine = SafetyEngine()
        action = make_action(ExecutionActionType.PAUSE_CAMPAIGN, campaign_age_hours=5)
        ctx = make_context()
        ev = engine.evaluate(action, ctx)
        assert ev.is_blocked is True

    def test_evaluate_with_rollback_protection(self):
        engine = SafetyEngine()
        action = make_action()
        ctx = make_context(metadata={"consecutive_failures": 5})
        ev = engine.evaluate(action, ctx)
        assert ev.is_blocked is True

    def test_evaluate_risk_score_zero_when_safe(self):
        engine = SafetyEngine()
        action = make_action(ExecutionActionType.MONITOR)
        ctx = make_context()
        ev = engine.evaluate(action, ctx)
        assert ev.risk_score == 0.0

    def test_evaluate_risk_score_nonzero_when_triggered(self):
        engine = SafetyEngine()
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=2000)
        ctx = make_context()
        ev = engine.evaluate(action, ctx)
        assert ev.risk_score > 0.0

    def test_evaluate_rule_results_recorded(self):
        engine = SafetyEngine()
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=2000)
        ctx = make_context()
        ev = engine.evaluate(action, ctx)
        assert len(ev.rule_results) > 0
        triggered = [r for r in ev.rule_results if r.triggered]
        assert len(triggered) > 0

    def test_evaluate_multiple_rules_most_severe(self):
        """测试多条规则触发时取最严格的决策."""
        engine = SafetyEngine()
        # 同时触发 budget_scale (BLOCK) 和 rollback (BLOCK)
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=2000)
        ctx = make_context(metadata={"consecutive_failures": 5})
        ev = engine.evaluate(action, ctx)
        assert ev.decision == SafetyDecision.BLOCK

    def test_evaluate_custom_policy(self):
        policy = create_aggressive_policy()
        engine = SafetyEngine(policy=policy)
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=300)
        ctx = make_context()
        ev = engine.evaluate(action, ctx)
        # 激进策略: warn threshold = 500, 所以 300 不触发
        assert ev.decision == SafetyDecision.ALLOW

    def test_evaluate_conservative_policy(self):
        policy = create_conservative_policy()
        engine = SafetyEngine(policy=policy)
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=100)
        ctx = make_context()
        ev = engine.evaluate(action, ctx)
        # 保守策略: warn threshold = 50, 所以 100 触发 WARN
        assert ev.decision == SafetyDecision.WARN

    def test_evaluate_disable_auto_rules(self):
        engine = SafetyEngine(enable_auto_rules=False)
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=200)
        ctx = make_context()
        ev = engine.evaluate(action, ctx)
        # 策略中默认也有 budget_scale_rule, 所以仍会触发
        # 但 auto_rules 不会重复添加
        assert ev.decision == SafetyDecision.WARN

    def test_evaluate_explicit_action_type(self):
        engine = SafetyEngine()
        action = make_action()
        ctx = make_context()
        ev = engine.evaluate(action, ctx, action_type="scale_budget")
        assert ev.action_type == "scale_budget"

    def test_evaluate_applies_warnings(self):
        engine = SafetyEngine()
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=200)
        ctx = make_context()
        ev = engine.evaluate(action, ctx)
        assert ev.has_warnings is True

    def test_stats_tracking(self):
        engine = SafetyEngine()
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=2000)
        ctx = make_context()
        engine.evaluate(action, ctx)
        stats = engine.stats()
        assert stats["evaluation_count"] == 1
        assert stats["block_count"] == 1

    def test_reset_stats(self):
        engine = SafetyEngine()
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=2000)
        ctx = make_context()
        engine.evaluate(action, ctx)
        engine.reset_stats()
        stats = engine.stats()
        assert stats["evaluation_count"] == 0
        assert stats["block_count"] == 0


# ═══════════════════════════════════════════════════════════════
# Test Safety Engine — apply_to_context
# ═══════════════════════════════════════════════════════════════


class TestSafetyEngineApplyToContext:
    """测试 SafetyEngine.apply_to_context."""

    def test_apply_block_to_context(self):
        engine = SafetyEngine()
        ev = SafetyEvaluation(
            decision=SafetyDecision.BLOCK,
            is_blocked=True,
            risk_score=0.9,
        )
        ctx = make_context()
        engine.apply_to_context(ev, ctx)
        assert ctx.safety_check is False
        assert ctx.risk_score == 0.9

    def test_apply_approval_to_context(self):
        engine = SafetyEngine()
        ev = SafetyEvaluation(
            decision=SafetyDecision.REQUIRE_APPROVAL,
            requires_approval=True,
            risk_score=0.7,
        )
        ctx = make_context()
        engine.apply_to_context(ev, ctx)
        assert ctx.safety_check is True
        assert ctx.approval_required is True
        assert ctx.user_confirmation == "pending"

    def test_apply_allow_to_context(self):
        engine = SafetyEngine()
        ev = SafetyEvaluation(
            decision=SafetyDecision.ALLOW,
            risk_score=0.1,
        )
        ctx = make_context()
        engine.apply_to_context(ev, ctx)
        assert ctx.safety_check is True
        assert ctx.approval_required is False

    def test_apply_stores_evaluation_in_metadata(self):
        engine = SafetyEngine()
        ev = SafetyEvaluation(
            decision=SafetyDecision.WARN,
            risk_score=0.3,
        )
        ctx = make_context()
        engine.apply_to_context(ev, ctx)
        assert "safety_evaluation" in ctx.metadata


# ═══════════════════════════════════════════════════════════════
# Test Integration
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """集成测试: SafetyEngine → ExecutionContext → ExecutionEngine."""

    def test_safe_action_full_pipeline(self):
        """安全动作: SafetyEngine ALLOW → ExecutionEngine 执行."""
        engine = SafetyEngine()
        action = make_action(ExecutionActionType.MONITOR)
        ctx = make_context()

        ev = engine.evaluate(action, ctx)
        assert ev.is_allowed is True
        engine.apply_to_context(ev, ctx)
        assert ctx.can_execute is True

    def test_high_risk_blocked_pipeline(self):
        """高风险动作: SafetyEngine BLOCK → ExecutionEngine 拒绝."""
        engine = SafetyEngine()
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=2000)
        ctx = make_context()

        ev = engine.evaluate(action, ctx)
        assert ev.is_blocked is True
        engine.apply_to_context(ev, ctx)
        assert ctx.safety_check is False

    def test_approval_required_pipeline(self):
        """需审批动作: SafetyEngine REQUIRE_APPROVAL → ExecutionContext pending."""
        engine = SafetyEngine()
        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=600)
        ctx = make_context()

        ev = engine.evaluate(action, ctx)
        assert ev.requires_approval is True
        engine.apply_to_context(ev, ctx)
        assert ctx.approval_required is True
        assert ctx.user_confirmation == "pending"

    def test_approval_workflow_integration(self):
        """审批流程: Evaluation → Approval → Context → Execute."""
        mgr = ApprovalManager()
        engine = SafetyEngine()

        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=600)
        ctx = make_context()

        ev = engine.evaluate(action, ctx)
        assert ev.requires_approval is True

        # 创建审批
        req = mgr.create_approval(ev)
        assert req.is_pending is True

        # 批准
        mgr.approve(req.request_id, "admin")
        ctx.user_confirmation = "approved"
        assert ctx.can_execute is True

    def test_conservative_policy_integration(self):
        """保守策略: 更严格的限制."""
        policy = create_conservative_policy()
        engine = SafetyEngine(policy=policy)

        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=100)
        ctx = make_context()

        ev = engine.evaluate(action, ctx)
        # 保守策略: warn threshold = 50, approval = 200
        assert ev.decision == SafetyDecision.WARN

    def test_aggressive_policy_integration(self):
        """激进策略: 更宽松的限制."""
        policy = create_aggressive_policy()
        engine = SafetyEngine(policy=policy)

        action = make_action(ExecutionActionType.SCALE_BUDGET, budget=300)
        ctx = make_context()

        ev = engine.evaluate(action, ctx)
        # 激进策略: warn threshold = 500
        assert ev.decision == SafetyDecision.ALLOW

    def test_empty_plan_evaluation(self):
        """空计划评估."""
        engine = SafetyEngine()

        from market_ops.creative_vision_runtime.growth_runtime.execution import ActionPlan
        plan = ActionPlan()
        ctx = make_context()

        evals = engine.evaluate_plan(plan, ctx)
        assert len(evals) == 0

    def test_stats_integration(self):
        """多次评估后统计正确."""
        engine = SafetyEngine()

        # 安全动作
        engine.evaluate(
            make_action(ExecutionActionType.MONITOR),
            make_context(),
        )
        # 高风险动作
        engine.evaluate(
            make_action(ExecutionActionType.SCALE_BUDGET, budget=2000),
            make_context(),
        )
        # 中风险动作
        engine.evaluate(
            make_action(ExecutionActionType.SCALE_BUDGET, budget=200),
            make_context(),
        )

        stats = engine.stats()
        assert stats["evaluation_count"] == 3
        assert stats["block_count"] >= 1
        assert stats["warn_count"] >= 1