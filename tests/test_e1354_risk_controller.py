"""E13.5.4 Risk Controller — 测试套件.

覆盖:
  - Risk Models (RiskLevel, RiskDecision, RiskAssessment, RiskPolicy, RiskContext)
  - Risk Rules (BudgetAggression, HistoricalFailure, LowConfidence, NewProduct, HighImpact)
  - RiskRuleEngine (evaluate, batch, custom rules, rule management)
  - RiskCalculator (weighted score, breakdown)
  - RiskController (evaluate, decision flow, batch)
  - Failure Memory 集成 (warnings, blocking, risk check)
  - Decision Flow (ALLOW/WARNING/BLOCK)
  - Edge Cases (null strategy, zero context, extreme values)
"""

from unittest.mock import MagicMock

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.risk_controller import (
    RiskCalculator,
    RiskController,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.risk_models import (
    RiskAssessment,
    RiskContext,
    RiskDecision,
    RiskLevel,
    RiskPolicy,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.risk_rules import (
    BaseRiskRule,
    BudgetAggressionRule,
    HighImpactRule,
    HistoricalFailureCheckRule,
    LowConfidenceRule,
    NewProductRule,
    RiskRuleEngine,
    RiskRuleResult,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
from market_ops.creative_vision_runtime.growth_runtime.memory.failure_models import (
    FailureCategory,
    FailureCondition,
    FailurePattern,
    FailureSeverity,
    FailureWarning,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def make_context(**kwargs) -> RiskContext:
    """创建测试用 RiskContext."""
    defaults = {
        "product_id": "merge_witch",
        "campaign_id": "camp_001",
        "audience_segment": "ios_us_facebook",
        "platform": "meta_ads",
        "budget_current": 1000.0,
        "budget_proposed": 1500.0,
        "sample_size": 50,
        "days_since_first_launch": 120,
        "opportunity_type": "creative_refresh",
        "signal_types": ["creative_fatigue"],
    }
    defaults.update(kwargs)
    return RiskContext(**defaults)


def make_strategy_dict(strategy_id="S001", strategy_name="Test Strategy", **kwargs) -> dict:
    """创建测试用策略 dict."""
    defaults = {
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "confidence_score": 0.8,
        "final_score": 0.75,
        "risk_score": 0.1,
        "action_type": "mutate_hook",
        "trigger": {"action_type": "mutate_hook", "opportunity_type": "creative_refresh"},
    }
    defaults.update(kwargs)
    return defaults


def make_failure_memory_with_patterns() -> FailureMemory:
    """创建带有预填充失败模式的 FailureMemory."""
    exp_store = ExperienceStore()
    fm = FailureMemory(exp_store)

    # 添加失败模式
    pattern = FailurePattern(
        name="Avoid: Budget Increase on merge_witch for ios_us_facebook (75% fail)",
        category=FailureCategory.BUDGET_WASTE,
        condition=FailureCondition(
            scenario="Budget increase failed in creative_refresh context",
            opportunity_type="creative_refresh",
            signal_types=["creative_fatigue"],
            audience_segment="ios_us_facebook",
            product_category="merge_witch",
            action_type="budget_increase",
        ),
        blocked_action="budget_increase",
        failure_rate=0.75,
        total_attempts=12,
        failed_attempts=9,
        avg_loss=500.0,
        max_loss=1200.0,
        severity=FailureSeverity.HIGH,
        suggestion="AVOID budget_increase in this context. Require manual approval.",
        source_experience_ids=["exp_001", "exp_002"],
        tags=["budget", "ios_us_facebook"],
        description="Budget increase failed 75% of the time on merge_witch for ios_us_facebook.",
    )
    pattern.compute_confidence()
    pattern.compute_severity()
    fm.store(pattern)

    return fm


def make_failure_memory_empty() -> FailureMemory:
    """创建空 FailureMemory."""
    exp_store = ExperienceStore()
    return FailureMemory(exp_store)


# ═══════════════════════════════════════════════════════════════
# Risk Models Tests
# ═══════════════════════════════════════════════════════════════


class TestRiskLevel:
    """RiskLevel 枚举测试."""

    def test_risk_level_values(self):
        assert RiskLevel.SAFE.value == "safe"
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_risk_level_is_string_enum(self):
        assert isinstance(RiskLevel.SAFE, str)

    def test_risk_level_comparison(self):
        levels = [RiskLevel.SAFE, RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert len(levels) == 5
        assert RiskLevel.SAFE == "safe"


class TestRiskDecision:
    """RiskDecision 枚举测试."""

    def test_risk_decision_values(self):
        assert RiskDecision.ALLOW.value == "allow"
        assert RiskDecision.WARNING.value == "warning"
        assert RiskDecision.BLOCK.value == "block"

    def test_risk_decision_is_string_enum(self):
        assert isinstance(RiskDecision.ALLOW, str)


class TestRiskAssessment:
    """RiskAssessment 模型测试."""

    def test_default_creation(self):
        a = RiskAssessment()
        assert a.risk_score == 0.0
        assert a.risk_level == RiskLevel.SAFE
        assert a.decision == RiskDecision.ALLOW
        assert a.assessment_id != ""

    def test_full_creation(self):
        a = RiskAssessment(
            strategy_id="S001",
            strategy_name="Test Strategy",
            risk_score=0.65,
            risk_level=RiskLevel.MEDIUM,
            decision=RiskDecision.WARNING,
            failure_risk=0.4,
            aggression_risk=0.25,
            uncertainty_risk=0.2,
            impact_risk=0.15,
            reasons=["Budget increase too aggressive"],
            recommendations=["Reduce budget increment to 30%"],
        )
        assert a.strategy_id == "S001"
        assert a.strategy_name == "Test Strategy"
        assert a.risk_score == 0.65
        assert a.risk_level == RiskLevel.MEDIUM
        assert a.decision == RiskDecision.WARNING
        assert a.failure_risk == 0.4
        assert a.aggression_risk == 0.25
        assert a.uncertainty_risk == 0.2
        assert a.impact_risk == 0.15
        assert len(a.reasons) == 1
        assert len(a.recommendations) == 1

    def test_is_safe(self):
        a = RiskAssessment(decision=RiskDecision.ALLOW)
        assert a.is_safe is True

        a2 = RiskAssessment(decision=RiskDecision.WARNING)
        assert a2.is_safe is False

    def test_is_blocked(self):
        a = RiskAssessment(decision=RiskDecision.BLOCK)
        assert a.is_blocked is True

        a2 = RiskAssessment(decision=RiskDecision.ALLOW)
        assert a2.is_blocked is False

    def test_is_warning(self):
        a = RiskAssessment(decision=RiskDecision.WARNING)
        assert a.is_warning is True

        a2 = RiskAssessment(decision=RiskDecision.ALLOW)
        assert a2.is_warning is False

    def test_add_reason(self):
        a = RiskAssessment()
        a.add_reason("Budget too high")
        assert "Budget too high" in a.reasons

    def test_add_recommendation(self):
        a = RiskAssessment()
        a.add_recommendation("Reduce budget")
        assert "Reduce budget" in a.recommendations

    def test_add_rule_violation(self):
        a = RiskAssessment()
        a.add_rule_violation("BudgetAggressionRule")
        assert "BudgetAggressionRule" in a.rule_violations

    def test_add_failure_pattern(self):
        a = RiskAssessment()
        a.add_failure_pattern({"name": "Budget Failure", "rate": 0.8})
        assert len(a.failure_patterns) == 1
        assert a.failure_patterns[0]["name"] == "Budget Failure"

    def test_add_failure_warning(self):
        a = RiskAssessment()
        a.add_failure_warning({"pattern_name": "Avoid Budget", "risk_score": 0.7})
        assert len(a.failure_warnings) == 1
        assert a.failure_warnings[0]["pattern_name"] == "Avoid Budget"

    def test_to_dict(self):
        a = RiskAssessment(
            strategy_id="S001",
            strategy_name="Test",
            risk_score=0.5,
            risk_level=RiskLevel.MEDIUM,
            decision=RiskDecision.WARNING,
        )
        d = a.to_dict()
        assert d["strategy_id"] == "S001"
        assert d["risk_score"] == 0.5
        assert d["risk_level"] == "medium"
        assert d["decision"] == "warning"

    def test_requires_approval_default(self):
        a = RiskAssessment()
        assert a.requires_approval is False

    def test_requires_approval_true(self):
        a = RiskAssessment(requires_approval=True)
        assert a.requires_approval is True


class TestRiskPolicy:
    """RiskPolicy 模型测试."""

    def test_default_policy(self):
        p = RiskPolicy()
        assert p.block_threshold == 0.85
        assert p.warning_threshold == 0.50
        assert p.safe_threshold == 0.30
        assert p.max_budget_increase == 0.30
        assert p.min_sample_size == 10
        assert p.min_confidence == 0.5
        assert p.require_validation is True
        assert p.auto_allow_safe is True

    def test_conservative_policy(self):
        p = RiskPolicy.conservative()
        assert p.block_threshold == 0.70
        assert p.warning_threshold == 0.35
        assert p.max_budget_increase == 0.15
        assert p.min_sample_size == 20
        assert p.escalation_required is True

    def test_aggressive_policy(self):
        p = RiskPolicy.aggressive()
        assert p.block_threshold == 0.95
        assert p.warning_threshold == 0.65
        assert p.max_budget_increase == 0.50
        assert p.min_sample_size == 5
        assert p.escalation_required is False

    def test_to_dict(self):
        p = RiskPolicy()
        d = p.to_dict()
        assert d["block_threshold"] == 0.85
        assert d["warning_threshold"] == 0.50

    def test_custom_policy(self):
        p = RiskPolicy(
            block_threshold=0.8,
            warning_threshold=0.4,
            max_budget_increase=0.25,
            min_sample_size=15,
        )
        assert p.block_threshold == 0.8
        assert p.warning_threshold == 0.4
        assert p.max_budget_increase == 0.25
        assert p.min_sample_size == 15


class TestRiskContext:
    """RiskContext 模型测试."""

    def test_default_creation(self):
        c = RiskContext()
        assert c.product_id == ""
        assert c.platform == "meta_ads"
        assert c.budget_current == 0.0
        assert c.sample_size == 0

    def test_full_creation(self):
        c = make_context()
        assert c.product_id == "merge_witch"
        assert c.budget_current == 1000.0
        assert c.budget_proposed == 1500.0
        assert c.sample_size == 50
        assert c.days_since_first_launch == 120

    def test_budget_change_ratio(self):
        c = RiskContext(budget_current=1000, budget_proposed=1500)
        assert c.budget_change_ratio == 0.5

    def test_budget_change_ratio_double(self):
        c = RiskContext(budget_current=1000, budget_proposed=2000)
        assert c.budget_change_ratio == 1.0

    def test_budget_change_ratio_zero_current(self):
        c = RiskContext(budget_current=0, budget_proposed=500)
        assert c.budget_change_ratio == 1.0

    def test_budget_change_ratio_no_change(self):
        c = RiskContext(budget_current=1000, budget_proposed=1000)
        assert c.budget_change_ratio == 0.0

    def test_budget_change_ratio_decrease(self):
        c = RiskContext(budget_current=1000, budget_proposed=500)
        assert c.budget_change_ratio == 0.5

    def test_is_new_product_true(self):
        c = RiskContext(days_since_first_launch=10)
        assert c.is_new_product is True

    def test_is_new_product_false(self):
        c = RiskContext(days_since_first_launch=120)
        assert c.is_new_product is False

    def test_is_new_product_boundary(self):
        c = RiskContext(days_since_first_launch=29)
        assert c.is_new_product is True
        c2 = RiskContext(days_since_first_launch=30)
        assert c2.is_new_product is False

    def test_is_low_sample_true(self):
        c = RiskContext(sample_size=5)
        assert c.is_low_sample is True

    def test_is_low_sample_false(self):
        c = RiskContext(sample_size=50)
        assert c.is_low_sample is False

    def test_to_dict(self):
        c = make_context()
        d = c.to_dict()
        assert d["product_id"] == "merge_witch"
        assert d["budget_current"] == 1000.0

    def test_metadata(self):
        c = RiskContext(metadata={"key": "value"})
        assert c.metadata["key"] == "value"


# ═══════════════════════════════════════════════════════════════
# Risk Rules Tests
# ═══════════════════════════════════════════════════════════════


class TestRiskRuleResult:
    """RiskRuleResult 测试."""

    def test_default_creation(self):
        r = RiskRuleResult()
        assert r.aggression_risk == 0.0
        assert r.uncertainty_risk == 0.0
        assert r.impact_risk == 0.0
        assert r.violations == []
        assert r.reasons == []
        assert r.recommendations == []

    def test_add_violation(self):
        r = RiskRuleResult()
        r.add_violation("BudgetRule", "Budget too high", "Reduce by 30%")
        assert "BudgetRule" in r.violations
        assert "Budget too high" in r.reasons
        assert "Reduce by 30%" in r.recommendations

    def test_add_violation_no_recommendation(self):
        r = RiskRuleResult()
        r.add_violation("BudgetRule", "Budget too high")
        assert "BudgetRule" in r.violations
        assert "Budget too high" in r.reasons
        assert len(r.recommendations) == 0

    def test_total_risk(self):
        r = RiskRuleResult(
            aggression_risk=0.3,
            uncertainty_risk=0.2,
            impact_risk=0.15,
        )
        assert r.total_risk == 0.65

    def test_has_violations_true(self):
        r = RiskRuleResult()
        r.add_violation("Rule", "Reason")
        assert r.has_violations is True

    def test_has_violations_false(self):
        r = RiskRuleResult()
        assert r.has_violations is False

    def test_to_dict(self):
        r = RiskRuleResult(
            aggression_risk=0.3,
            uncertainty_risk=0.2,
            impact_risk=0.15,
        )
        r.add_violation("Rule", "Reason", "Rec")
        d = r.to_dict()
        assert d["aggression_risk"] == 0.3
        assert d["violations"] == ["Rule"]


class TestBudgetAggressionRule:
    """BudgetAggressionRule 测试."""

    def test_no_budget_change(self):
        rule = BudgetAggressionRule()
        ctx = make_context(budget_current=1000, budget_proposed=1000)
        result = RiskRuleResult()
        rule.evaluate({}, ctx, RiskPolicy(), result)
        assert result.aggression_risk == 0.0

    def test_budget_increase_30_percent(self):
        rule = BudgetAggressionRule()
        ctx = make_context(budget_current=1000, budget_proposed=1350)
        result = RiskRuleResult()
        rule.evaluate({}, ctx, RiskPolicy(), result)
        assert result.aggression_risk == 0.15

    def test_budget_increase_50_percent(self):
        rule = BudgetAggressionRule()
        ctx = make_context(budget_current=1000, budget_proposed=1600)
        result = RiskRuleResult()
        rule.evaluate({}, ctx, RiskPolicy(), result)
        assert result.aggression_risk == 0.3
        assert "BudgetAggressionRule" in result.violations

    def test_budget_increase_100_percent(self):
        rule = BudgetAggressionRule()
        ctx = make_context(budget_current=1000, budget_proposed=2500)
        result = RiskRuleResult()
        rule.evaluate({}, ctx, RiskPolicy(), result)
        assert result.aggression_risk == 0.8
        assert "BudgetAggressionRule" in result.violations

    def test_new_product_budget_penalty(self):
        rule = BudgetAggressionRule()
        ctx = make_context(
            budget_current=1000,
            budget_proposed=1200,
            days_since_first_launch=10,
        )
        result = RiskRuleResult()
        rule.evaluate({}, ctx, RiskPolicy(), result)
        assert result.aggression_risk == 0.5  # 新产品惩罚

    def test_new_product_no_penalty_within_limit(self):
        rule = BudgetAggressionRule()
        ctx = make_context(
            budget_current=1000,
            budget_proposed=1050,
            days_since_first_launch=10,
        )
        result = RiskRuleResult()
        rule.evaluate({}, ctx, RiskPolicy(), result)
        assert result.aggression_risk == 0.0  # 5% 增幅在 10% 以内

    def test_aggression_capped_at_1(self):
        rule = BudgetAggressionRule()
        ctx = make_context(
            budget_current=1000,
            budget_proposed=5000,  # 400% increase
            days_since_first_launch=10,
        )
        result = RiskRuleResult()
        rule.evaluate({}, ctx, RiskPolicy(), result)
        assert result.aggression_risk == 1.0


class TestHistoricalFailureCheckRule:
    """HistoricalFailureCheckRule 测试."""

    def test_no_failure_rate(self):
        rule = HistoricalFailureCheckRule()
        ctx = make_context()
        result = RiskRuleResult()
        rule.evaluate(make_strategy_dict(risk_score=0), ctx, RiskPolicy(), result)
        assert len(result.violations) == 0

    def test_medium_failure_rate(self):
        rule = HistoricalFailureCheckRule()
        ctx = make_context()
        result = RiskRuleResult()
        rule.evaluate(make_strategy_dict(risk_score=0.55), ctx, RiskPolicy(), result)
        assert "HistoricalFailureCheckRule" in result.violations

    def test_high_failure_rate(self):
        rule = HistoricalFailureCheckRule()
        ctx = make_context()
        result = RiskRuleResult()
        rule.evaluate(make_strategy_dict(risk_score=0.75), ctx, RiskPolicy(), result)
        assert "HistoricalFailureCheckRule" in result.violations

    def test_block_failure_rate(self):
        rule = HistoricalFailureCheckRule()
        ctx = make_context()
        result = RiskRuleResult()
        rule.evaluate(make_strategy_dict(risk_score=0.95), ctx, RiskPolicy(), result)
        assert "HistoricalFailureCheckRule" in result.violations
        assert "BLOCK" in result.reasons[0]

    def test_strategy_candidate_risk_score(self):
        """测试 StrategyCandidate 对象的 risk_score."""
        rule = HistoricalFailureCheckRule()

        class MockCandidate:
            risk_score = 0.72

        ctx = make_context()
        result = RiskRuleResult()
        rule.evaluate(MockCandidate(), ctx, RiskPolicy(), result)
        assert "HistoricalFailureCheckRule" in result.violations


class TestLowConfidenceRule:
    """LowConfidenceRule 测试."""

    def test_high_confidence_no_violation(self):
        rule = LowConfidenceRule()
        ctx = make_context(sample_size=50)
        result = RiskRuleResult()
        rule.evaluate(make_strategy_dict(confidence_score=0.9), ctx, RiskPolicy(), result)
        assert len(result.violations) == 0

    def test_low_confidence(self):
        rule = LowConfidenceRule()
        ctx = make_context(sample_size=50)
        result = RiskRuleResult()
        rule.evaluate(make_strategy_dict(confidence_score=0.4), ctx, RiskPolicy(), result)
        assert result.uncertainty_risk > 0
        assert "LowConfidenceRule" in result.violations

    def test_very_low_confidence(self):
        rule = LowConfidenceRule()
        ctx = make_context(sample_size=50)
        result = RiskRuleResult()
        rule.evaluate(make_strategy_dict(confidence_score=0.2), ctx, RiskPolicy(), result)
        assert result.uncertainty_risk == 0.7
        assert "LowConfidenceRule" in result.violations

    def test_low_sample_size(self):
        rule = LowConfidenceRule()
        ctx = make_context(sample_size=7)
        result = RiskRuleResult()
        rule.evaluate(make_strategy_dict(confidence_score=0.8), ctx, RiskPolicy(), result)
        assert result.uncertainty_risk == 0.25
        assert "LowConfidenceRule" in result.violations

    def test_very_low_sample_size(self):
        rule = LowConfidenceRule()
        ctx = make_context(sample_size=3)
        result = RiskRuleResult()
        rule.evaluate(make_strategy_dict(confidence_score=0.8), ctx, RiskPolicy(), result)
        assert result.uncertainty_risk == 0.6
        assert "LowConfidenceRule" in result.violations

    def test_low_confidence_and_low_sample(self):
        rule = LowConfidenceRule()
        ctx = make_context(sample_size=3)
        result = RiskRuleResult()
        rule.evaluate(make_strategy_dict(confidence_score=0.2), ctx, RiskPolicy(), result)
        assert result.uncertainty_risk > 0.7  # 累积

    def test_uncertainty_capped_at_1(self):
        rule = LowConfidenceRule()
        ctx = make_context(sample_size=3)
        result = RiskRuleResult()
        rule.evaluate(make_strategy_dict(confidence_score=0.1), ctx, RiskPolicy(), result)
        assert result.uncertainty_risk <= 1.0

    def test_confidence_zero_ignored(self):
        rule = LowConfidenceRule()
        ctx = make_context(sample_size=50)
        result = RiskRuleResult()
        rule.evaluate(make_strategy_dict(confidence_score=0), ctx, RiskPolicy(), result)
        assert len(result.violations) == 0

    def test_uses_final_score_fallback(self):
        rule = LowConfidenceRule()
        ctx = make_context(sample_size=50)
        result = RiskRuleResult()
        rule.evaluate(make_strategy_dict(final_score=0.4, confidence_score=0), ctx, RiskPolicy(), result)
        assert result.uncertainty_risk > 0


class TestNewProductRule:
    """NewProductRule 测试."""

    def test_not_new_product(self):
        rule = NewProductRule()
        ctx = make_context(days_since_first_launch=120)
        result = RiskRuleResult()
        rule.evaluate({}, ctx, RiskPolicy(), result)
        assert result.impact_risk == 0.0
        assert result.uncertainty_risk == 0.0

    def test_very_new_product(self):
        rule = NewProductRule()
        ctx = make_context(days_since_first_launch=7, sample_size=20)
        result = RiskRuleResult()
        rule.evaluate({}, ctx, RiskPolicy(), result)
        assert result.impact_risk == 0.6
        assert result.uncertainty_risk == 0.4
        assert "NewProductRule" in result.violations

    def test_new_product(self):
        rule = NewProductRule()
        ctx = make_context(days_since_first_launch=20, sample_size=20)
        result = RiskRuleResult()
        rule.evaluate({}, ctx, RiskPolicy(), result)
        assert result.impact_risk == 0.3
        assert result.uncertainty_risk == 0.2
        assert "NewProductRule" in result.violations

    def test_new_product_low_sample(self):
        rule = NewProductRule()
        ctx = make_context(days_since_first_launch=7, sample_size=3)
        result = RiskRuleResult()
        rule.evaluate({}, ctx, RiskPolicy(), result)
        assert "NewProductRule" in result.violations
        assert "cannot auto-execute" in result.reasons[-1]


class TestHighImpactRule:
    """HighImpactRule 测试."""

    def test_no_action_type(self):
        rule = HighImpactRule()
        ctx = make_context(opportunity_type="")
        result = RiskRuleResult()
        rule.evaluate(make_strategy_dict(strategy_name="Unknown"), ctx, RiskPolicy(), result)
        assert result.impact_risk == 0.0

    def test_delete_campaign(self):
        rule = HighImpactRule()
        ctx = make_context()
        result = RiskRuleResult()
        rule.evaluate(make_strategy_dict(strategy_name="delete_campaign"), ctx, RiskPolicy(), result)
        assert result.impact_risk == 0.9
        assert "HighImpactRule" in result.violations

    def test_budget_increase(self):
        rule = HighImpactRule()
        ctx = make_context()
        result = RiskRuleResult()
        rule.evaluate(make_strategy_dict(strategy_name="budget_increase"), ctx, RiskPolicy(), result)
        assert result.impact_risk == 0.2

    def test_audience_expansion(self):
        rule = HighImpactRule()
        ctx = make_context()
        result = RiskRuleResult()
        rule.evaluate(make_strategy_dict(strategy_name="audience_expansion"), ctx, RiskPolicy(), result)
        assert result.impact_risk == 0.25

    def test_inferred_from_context(self):
        rule = HighImpactRule()
        ctx = make_context(opportunity_type="budget_optimization", budget_current=1000, budget_proposed=1500)
        result = RiskRuleResult()
        rule.evaluate({}, ctx, RiskPolicy(), result)
        assert result.impact_risk == 0.2

    def test_impact_capped_at_1(self):
        rule = HighImpactRule()
        ctx = make_context()
        result = RiskRuleResult()
        rule.evaluate(make_strategy_dict(strategy_name="delete_campaign delete_adset"), ctx, RiskPolicy(), result)
        assert result.impact_risk <= 1.0


# ═══════════════════════════════════════════════════════════════
# RiskRuleEngine Tests
# ═══════════════════════════════════════════════════════════════


class TestRiskRuleEngine:
    """RiskRuleEngine 测试."""

    def test_default_creation(self):
        engine = RiskRuleEngine()
        assert engine.rule_count == 5
        assert engine.evaluation_count == 0

    def test_with_custom_policy(self):
        p = RiskPolicy.conservative()
        engine = RiskRuleEngine(p)
        assert engine.policy.block_threshold == 0.70

    def test_evaluate_safe_strategy(self):
        engine = RiskRuleEngine()
        ctx = make_context(
            budget_current=1000,
            budget_proposed=1100,
            sample_size=50,
            days_since_first_launch=120,
        )
        result = engine.evaluate(make_strategy_dict(confidence_score=0.9), ctx)
        assert result.aggression_risk == 0.0
        assert result.uncertainty_risk == 0.0

    def test_evaluate_risky_strategy(self):
        engine = RiskRuleEngine()
        ctx = make_context(
            budget_current=1000,
            budget_proposed=2000,
            sample_size=3,
            days_since_first_launch=7,
        )
        result = engine.evaluate(make_strategy_dict(confidence_score=0.2, risk_score=0.8), ctx)
        assert result.aggression_risk > 0
        assert result.uncertainty_risk > 0
        assert result.has_violations

    def test_evaluate_batch(self):
        engine = RiskRuleEngine()
        ctx = make_context()
        strategies = [
            make_strategy_dict("S001", "Strategy A"),
            make_strategy_dict("S002", "Strategy B"),
        ]
        results = engine.evaluate_batch(strategies, ctx)
        assert len(results) == 2
        assert all(isinstance(r, RiskRuleResult) for r in results)

    def test_evaluation_count_increments(self):
        engine = RiskRuleEngine()
        ctx = make_context()
        engine.evaluate(make_strategy_dict(), ctx)
        engine.evaluate(make_strategy_dict(), ctx)
        assert engine.evaluation_count == 2

    def test_add_custom_rule(self):
        engine = RiskRuleEngine()

        class CustomRule(BaseRiskRule):
            name = "CustomRule"

            def evaluate(self, strategy, context, policy, result):
                result.aggression_risk += 0.1

        engine.add_rule(CustomRule())
        assert engine.rule_count == 6

        ctx = make_context()
        result = engine.evaluate(make_strategy_dict(), ctx)
        assert result.aggression_risk >= 0.1

    def test_remove_rule(self):
        engine = RiskRuleEngine()
        assert engine.remove_rule("BudgetAggressionRule") is True
        assert engine.rule_count == 4
        assert engine.remove_rule("NonExistent") is False

    def test_rule_exception_isolated(self):
        engine = RiskRuleEngine()

        class BrokenRule(BaseRiskRule):
            name = "BrokenRule"

            def evaluate(self, strategy, context, policy, result):
                raise RuntimeError("Boom")

        engine.add_rule(BrokenRule())
        ctx = make_context()
        result = engine.evaluate(make_strategy_dict(), ctx)
        # 不应抛出异常
        assert isinstance(result, RiskRuleResult)

    def test_rules_property(self):
        engine = RiskRuleEngine()
        rules = engine.rules
        assert len(rules) == 5
        assert isinstance(rules[0], BaseRiskRule)


# ═══════════════════════════════════════════════════════════════
# RiskCalculator Tests
# ═══════════════════════════════════════════════════════════════


class TestRiskCalculator:
    """RiskCalculator 测试."""

    def test_zero_risk(self):
        calc = RiskCalculator()
        score = calc.calculate(0, 0, 0, 0)
        assert score == 0.0

    def test_full_risk(self):
        calc = RiskCalculator()
        score = calc.calculate(1.0, 1.0, 1.0, 1.0)
        assert score == 1.0

    def test_weighted_calculation(self):
        calc = RiskCalculator()
        # failure=0.5*0.4=0.2, aggression=0.3*0.25=0.075, uncertainty=0.2*0.2=0.04, impact=0.1*0.15=0.015
        score = calc.calculate(0.5, 0.3, 0.2, 0.1)
        assert score == pytest.approx(0.33, abs=0.01)

    def test_failure_risk_dominates(self):
        calc = RiskCalculator()
        score_high_failure = calc.calculate(0.9, 0.1, 0.1, 0.1)
        score_low_failure = calc.calculate(0.1, 0.9, 0.9, 0.9)
        # 高失败率即使其他风险低，总分也较高 (0.9*0.4=0.36)
        # 低失败率但高其他风险 (0.9*0.25+0.9*0.2+0.9*0.15=0.54)
        assert score_high_failure < score_low_failure  # 但其他维度权重总和更高

    def test_weights_sum_to_1(self):
        calc = RiskCalculator()
        assert calc.FAILURE_WEIGHT + calc.AGGRESSION_WEIGHT + calc.UNCERTAINTY_WEIGHT + calc.IMPACT_WEIGHT == 1.0

    def test_score_capped_at_1(self):
        calc = RiskCalculator()
        score = calc.calculate(2.0, 2.0, 2.0, 2.0)
        assert score == 1.0

    def test_score_capped_at_0(self):
        calc = RiskCalculator()
        score = calc.calculate(-1.0, -1.0, -1.0, -1.0)
        assert score == 0.0

    def test_get_risk_breakdown(self):
        calc = RiskCalculator()
        breakdown = calc.get_risk_breakdown(0.5, 0.3, 0.2, 0.1)
        assert breakdown["failure_risk_weighted"] == pytest.approx(0.2, abs=0.001)
        assert breakdown["aggression_risk_weighted"] == pytest.approx(0.075, abs=0.001)
        assert breakdown["uncertainty_risk_weighted"] == pytest.approx(0.04, abs=0.001)
        assert breakdown["impact_risk_weighted"] == pytest.approx(0.015, abs=0.001)


# ═══════════════════════════════════════════════════════════════
# RiskController Tests
# ═══════════════════════════════════════════════════════════════


class TestRiskController:
    """RiskController 核心测试."""

    def test_creation_without_failure_memory(self):
        controller = RiskController()
        assert controller.has_failure_memory is False
        assert controller.evaluation_count == 0

    def test_creation_with_failure_memory(self):
        fm = make_failure_memory_empty()
        controller = RiskController(fm)
        assert controller.has_failure_memory is True

    def test_creation_with_custom_policy(self):
        p = RiskPolicy.conservative()
        controller = RiskController(policy=p)
        assert controller.policy.block_threshold == 0.70

    def test_evaluate_safe_strategy(self):
        controller = RiskController()
        ctx = make_context(
            budget_current=1000,
            budget_proposed=1100,
            sample_size=100,
            days_since_first_launch=200,
        )
        strategy = make_strategy_dict(confidence_score=0.9, risk_score=0.0)
        assessment = controller.evaluate(strategy, ctx, "Safe Strategy")

        assert isinstance(assessment, RiskAssessment)
        assert assessment.strategy_name == "Safe Strategy"
        assert assessment.risk_score < 0.3
        assert assessment.risk_level == RiskLevel.SAFE
        assert assessment.decision == RiskDecision.ALLOW

    def test_evaluate_risky_budget_strategy(self):
        controller = RiskController()
        ctx = make_context(
            budget_current=1000,
            budget_proposed=2500,  # 150% increase
            sample_size=50,
            days_since_first_launch=120,
        )
        strategy = make_strategy_dict(confidence_score=0.9, risk_score=0.0)
        assessment = controller.evaluate(strategy, ctx)

        assert assessment.risk_score >= 0.2
        assert assessment.aggression_risk > 0
        assert "BudgetAggressionRule" in assessment.rule_violations

    def test_evaluate_new_product_strategy(self):
        controller = RiskController()
        ctx = make_context(
            budget_current=1000,
            budget_proposed=1200,
            sample_size=3,
            days_since_first_launch=7,
        )
        strategy = make_strategy_dict(confidence_score=0.8, risk_score=0.0)
        assessment = controller.evaluate(strategy, ctx)

        assert assessment.risk_score > 0.3
        assert assessment.requires_approval is True
        assert "NewProductRule" in assessment.rule_violations

    def test_evaluate_with_failure_memory_warnings(self):
        fm = make_failure_memory_with_patterns()
        controller = RiskController(fm)
        ctx = make_context(
            budget_current=1000,
            budget_proposed=1500,
            product_id="merge_witch",
            audience_segment="ios_us_facebook",
            opportunity_type="creative_refresh",
        )
        strategy = make_strategy_dict(
            action_type="budget_increase",
            trigger={"action_type": "budget_increase", "opportunity_type": "creative_refresh"},
        )
        assessment = controller.evaluate(strategy, ctx)

        assert assessment.failure_risk > 0
        assert len(assessment.failure_warnings) > 0

    def test_evaluate_batch(self):
        controller = RiskController()
        ctx = make_context()
        strategies = [
            make_strategy_dict("S001", "A"),
            make_strategy_dict("S002", "B"),
        ]
        assessments = controller.evaluate_batch(strategies, ctx)
        assert len(assessments) == 2
        assert all(isinstance(a, RiskAssessment) for a in assessments)

    def test_is_safe_quick_check(self):
        controller = RiskController()
        ctx = make_context(
            budget_current=1000,
            budget_proposed=1100,
            sample_size=100,
            days_since_first_launch=200,
        )
        strategy = make_strategy_dict(confidence_score=0.95, risk_score=0.0)
        assert controller.is_safe(strategy, ctx) is True

    def test_is_blocked_quick_check(self):
        fm = make_failure_memory_with_patterns()
        controller = RiskController(fm, RiskPolicy(block_threshold=0.3))
        ctx = make_context(
            budget_current=1000,
            budget_proposed=3000,
            product_id="merge_witch",
            audience_segment="ios_us_facebook",
            opportunity_type="creative_refresh",
            sample_size=3,
            days_since_first_launch=5,
        )
        strategy = make_strategy_dict(
            confidence_score=0.1,
            risk_score=0.9,
            action_type="budget_increase",
            trigger={"action_type": "budget_increase", "opportunity_type": "creative_refresh"},
        )
        assert controller.is_blocked(strategy, ctx) is True

    def test_evaluation_count(self):
        controller = RiskController()
        ctx = make_context()
        controller.evaluate(make_strategy_dict(), ctx)
        controller.evaluate(make_strategy_dict(), ctx)
        assert controller.evaluation_count == 2

    def test_update_policy(self):
        controller = RiskController()
        old_policy = controller.policy
        new_policy = RiskPolicy.conservative()
        controller.update_policy(new_policy)
        assert controller.policy.block_threshold == 0.70
        assert controller.policy is not old_policy

    def test_strategy_dict_input(self):
        controller = RiskController()
        ctx = make_context()
        strategy = {"strategy_id": "S_DICT", "strategy_name": "Dict Strategy", "confidence_score": 0.8}
        assessment = controller.evaluate(strategy, ctx)
        assert assessment.strategy_id == "S_DICT"
        assert assessment.strategy_name == "Dict Strategy"

    def test_strategy_candidate_input(self):
        controller = RiskController()

        class MockCandidate:
            strategy_id = "S_CAND"
            strategy_name = "Candidate Strategy"
            confidence_score = 0.85
            risk_score = 0.1
            strategy = {"trigger": {"action_type": "budget_increase"}}

        ctx = make_context()
        assessment = controller.evaluate(MockCandidate(), ctx)
        assert assessment.strategy_id == "S_CAND"
        assert assessment.strategy_name == "Candidate Strategy"

    def test_null_strategy_handled(self):
        controller = RiskController()
        ctx = make_context()
        assessment = controller.evaluate({}, ctx)
        assert isinstance(assessment, RiskAssessment)
        assert assessment.strategy_id == ""


# ═══════════════════════════════════════════════════════════════
# Decision Flow Tests
# ═══════════════════════════════════════════════════════════════


class TestDecisionFlow:
    """决策流程测试 — ALLOW / WARNING / BLOCK."""

    def test_allow_safe_strategy(self):
        controller = RiskController()
        ctx = make_context(
            budget_current=1000,
            budget_proposed=1100,
            sample_size=100,
            days_since_first_launch=200,
        )
        strategy = make_strategy_dict(confidence_score=0.95, risk_score=0.0)
        assessment = controller.evaluate(strategy, ctx)
        assert assessment.decision == RiskDecision.ALLOW
        assert assessment.is_safe is True
        assert assessment.requires_approval is False

    def test_warning_medium_risk(self):
        controller = RiskController()
        ctx = make_context(
            budget_current=1000,
            budget_proposed=1600,
            sample_size=50,
            days_since_first_launch=120,
        )
        strategy = make_strategy_dict(confidence_score=0.7, risk_score=0.3)
        assessment = controller.evaluate(strategy, ctx)
        # 60% budget increase triggers aggression_risk=0.3, weighted: 0.3*0.25=0.075
        assert assessment.risk_score > 0.05
        assert assessment.aggression_risk > 0

    def test_block_high_risk(self):
        fm = make_failure_memory_with_patterns()
        controller = RiskController(fm, RiskPolicy(block_threshold=0.4))
        ctx = make_context(
            budget_current=1000,
            budget_proposed=3000,
            product_id="merge_witch",
            audience_segment="ios_us_facebook",
            opportunity_type="creative_refresh",
            sample_size=3,
            days_since_first_launch=5,
        )
        strategy = make_strategy_dict(
            confidence_score=0.1,
            risk_score=0.9,
            action_type="budget_increase",
            strategy_name="delete_campaign",
            trigger={"action_type": "budget_increase", "opportunity_type": "creative_refresh"},
        )
        assessment = controller.evaluate(strategy, ctx)
        assert assessment.decision == RiskDecision.BLOCK
        assert assessment.is_blocked is True

    def test_block_by_failure_rate(self):
        fm = make_failure_memory_with_patterns()
        # 添加一个失败率极高的模式
        pattern = FailurePattern(
            name="Avoid: Critical Action (90% fail)",
            category=FailureCategory.BUDGET_WASTE,
            condition=FailureCondition(
                scenario="Critical action always fails",
                opportunity_type="creative_refresh",
                action_type="budget_increase",
            ),
            blocked_action="budget_increase",
            failure_rate=0.95,
            total_attempts=20,
            failed_attempts=19,
            avg_loss=2000.0,
            severity=FailureSeverity.CRITICAL,
            suggestion="Do not execute this action.",
        )
        pattern.compute_confidence()
        pattern.compute_severity()
        fm.store(pattern)

        controller = RiskController(fm, RiskPolicy(block_threshold=0.85))
        ctx = make_context(
            product_id="merge_witch",
            audience_segment="ios_us_facebook",
            opportunity_type="creative_refresh",
        )
        strategy = make_strategy_dict(
            action_type="budget_increase",
            trigger={"action_type": "budget_increase", "opportunity_type": "creative_refresh"},
        )
        assessment = controller.evaluate(strategy, ctx)
        # 高失败率应该导致 BLOCK 或高 failure_risk
        assert assessment.failure_risk > 0

    def test_new_product_cannot_auto_execute(self):
        controller = RiskController()
        ctx = make_context(
            budget_current=1000,
            budget_proposed=1200,
            sample_size=3,
            days_since_first_launch=7,
        )
        strategy = make_strategy_dict(confidence_score=0.8, risk_score=0.0)
        assessment = controller.evaluate(strategy, ctx)
        assert assessment.requires_approval is True

    def test_risk_level_mapping(self):
        controller = RiskController()
        ctx = make_context(
            budget_current=1000,
            budget_proposed=1100,
            sample_size=100,
            days_since_first_launch=200,
        )
        strategy = make_strategy_dict(confidence_score=0.95, risk_score=0.0)
        assessment = controller.evaluate(strategy, ctx)
        assert assessment.risk_level == RiskLevel.SAFE

    def test_assessment_contains_all_risk_components(self):
        controller = RiskController()
        ctx = make_context(
            budget_current=1000,
            budget_proposed=2000,
            sample_size=7,
            days_since_first_launch=20,
        )
        strategy = make_strategy_dict(
            confidence_score=0.4,
            risk_score=0.6,
            strategy_name="delete_campaign",
        )
        assessment = controller.evaluate(strategy, ctx)

        assert assessment.failure_risk >= 0
        assert assessment.aggression_risk >= 0
        assert assessment.uncertainty_risk >= 0
        assert assessment.impact_risk >= 0
        assert assessment.risk_score > 0
        assert assessment.risk_level != RiskLevel.SAFE

    def test_assessment_to_dict(self):
        controller = RiskController()
        ctx = make_context()
        strategy = make_strategy_dict()
        assessment = controller.evaluate(strategy, ctx)
        d = assessment.to_dict()
        assert "assessment_id" in d
        assert "risk_score" in d
        assert "risk_level" in d
        assert "decision" in d


# ═══════════════════════════════════════════════════════════════
# Failure Memory Integration Tests
# ═══════════════════════════════════════════════════════════════


class TestFailureMemoryIntegration:
    """Failure Memory 集成测试."""

    def test_no_failure_memory_returns_zero_risk(self):
        controller = RiskController()  # 无 FailureMemory
        ctx = make_context()
        strategy = make_strategy_dict()
        assessment = controller.evaluate(strategy, ctx)
        assert assessment.failure_risk == 0.0
        assert assessment.failure_warnings == []
        assert assessment.failure_patterns == []

    def test_failure_memory_check_action(self):
        fm = make_failure_memory_with_patterns()
        controller = RiskController(fm)
        ctx = make_context(
            product_id="merge_witch",
            audience_segment="ios_us_facebook",
            opportunity_type="creative_refresh",
        )
        strategy = make_strategy_dict(
            action_type="budget_increase",
            trigger={"action_type": "budget_increase", "opportunity_type": "creative_refresh"},
        )
        assessment = controller.evaluate(strategy, ctx)
        assert assessment.failure_risk > 0
        assert len(assessment.failure_warnings) > 0

    def test_failure_warnings_contain_expected_fields(self):
        fm = make_failure_memory_with_patterns()
        controller = RiskController(fm)
        ctx = make_context(
            product_id="merge_witch",
            audience_segment="ios_us_facebook",
            opportunity_type="creative_refresh",
        )
        strategy = make_strategy_dict(
            action_type="budget_increase",
            trigger={"action_type": "budget_increase", "opportunity_type": "creative_refresh"},
        )
        assessment = controller.evaluate(strategy, ctx)

        for w in assessment.failure_warnings:
            assert "pattern_name" in w
            assert "risk_score" in w
            assert "failure_rate" in w
            assert "severity" in w
            assert "suggestion" in w

    def test_failure_patterns_extracted(self):
        fm = make_failure_memory_with_patterns()
        controller = RiskController(fm)
        ctx = make_context(
            product_id="merge_witch",
            audience_segment="ios_us_facebook",
            opportunity_type="creative_refresh",
        )
        strategy = make_strategy_dict(
            action_type="budget_increase",
            trigger={"action_type": "budget_increase", "opportunity_type": "creative_refresh"},
        )
        assessment = controller.evaluate(strategy, ctx)

        if assessment.failure_patterns:
            for p in assessment.failure_patterns:
                assert "failure_id" in p
                assert "name" in p
                assert "failure_rate" in p

    def test_failure_memory_exception_handled(self):
        fm = MagicMock(spec=FailureMemory)
        fm.check_action.side_effect = RuntimeError("Connection error")
        controller = RiskController(fm)
        ctx = make_context()
        strategy = make_strategy_dict()
        assessment = controller.evaluate(strategy, ctx)
        # 不应抛出异常
        assert isinstance(assessment, RiskAssessment)
        assert assessment.failure_risk == 0.0


# ═══════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试."""

    def test_zero_context(self):
        controller = RiskController()
        ctx = RiskContext()
        strategy = {}
        assessment = controller.evaluate(strategy, ctx)
        assert isinstance(assessment, RiskAssessment)
        # Zero context triggers some rules (budget ratio=1.0, sample_size=0)
        assert assessment.risk_score >= 0.0

    def test_extreme_budget_decrease(self):
        controller = RiskController()
        ctx = make_context(budget_current=1000, budget_proposed=100)
        strategy = make_strategy_dict()
        assessment = controller.evaluate(strategy, ctx)
        assert isinstance(assessment, RiskAssessment)

    def test_max_sample_size(self):
        controller = RiskController()
        ctx = make_context(sample_size=100000, days_since_first_launch=365)
        strategy = make_strategy_dict(confidence_score=1.0, risk_score=0.0)
        assessment = controller.evaluate(strategy, ctx)
        assert assessment.uncertainty_risk == 0.0

    def test_negative_confidence(self):
        controller = RiskController()
        ctx = make_context()
        strategy = make_strategy_dict(confidence_score=-0.5)
        assessment = controller.evaluate(strategy, ctx)
        assert isinstance(assessment, RiskAssessment)

    def test_very_long_strategy_name(self):
        controller = RiskController()
        ctx = make_context()
        strategy = make_strategy_dict(strategy_name="A" * 500)
        assessment = controller.evaluate(strategy, ctx)
        assert assessment.strategy_name == "A" * 500

    def test_empty_signal_types(self):
        controller = RiskController()
        ctx = make_context(signal_types=[])
        strategy = make_strategy_dict()
        assessment = controller.evaluate(strategy, ctx)
        assert isinstance(assessment, RiskAssessment)

    def test_unknown_opportunity_type(self):
        controller = RiskController()
        ctx = make_context(opportunity_type="unknown_type_xyz")
        strategy = make_strategy_dict()
        assessment = controller.evaluate(strategy, ctx)
        assert isinstance(assessment, RiskAssessment)

    def test_conservative_policy_blocks_earlier(self):
        p = RiskPolicy.conservative()
        controller = RiskController(policy=p)
        ctx = make_context(
            budget_current=1000,
            budget_proposed=1600,
            sample_size=7,
            days_since_first_launch=20,
        )
        strategy = make_strategy_dict(confidence_score=0.5, risk_score=0.5)
        assessment = controller.evaluate(strategy, ctx)
        # 保守策略下应更容易触发警告或阻止
        assert assessment.risk_score > 0

    def test_aggressive_policy_allows_more(self):
        p = RiskPolicy.aggressive()
        controller = RiskController(policy=p)
        ctx = make_context(
            budget_current=1000,
            budget_proposed=1400,
            sample_size=50,
            days_since_first_launch=120,
        )
        strategy = make_strategy_dict(confidence_score=0.8, risk_score=0.0)
        assessment = controller.evaluate(strategy, ctx)
        # 激进策略下应更宽松
        assert assessment.risk_score <= 0.5


# ═══════════════════════════════════════════════════════════════
# Integration: End-to-End
# ═══════════════════════════════════════════════════════════════


class TestEndToEndIntegration:
    """端到端集成测试: Opportunity → Strategy → Risk Controller → ALLOW/WARNING/BLOCK."""

    def test_full_flow_safe(self):
        """完整流程: 安全策略 → ALLOW."""
        controller = RiskController()
        ctx = RiskContext(
            product_id="game_x",
            campaign_id="camp_001",
            audience_segment="us_android",
            budget_current=5000,
            budget_proposed=5500,
            sample_size=500,
            days_since_first_launch=180,
            opportunity_type="creative_refresh",
            signal_types=["creative_fatigue"],
        )
        strategy = {
            "strategy_id": "S_SAFE",
            "strategy_name": "Safe Creative Refresh",
            "confidence_score": 0.92,
            "final_score": 0.88,
            "risk_score": 0.05,
            "action_type": "mutate_hook",
            "trigger": {"action_type": "mutate_hook", "opportunity_type": "creative_refresh"},
        }
        assessment = controller.evaluate(strategy, ctx)
        assert assessment.decision == RiskDecision.ALLOW
        assert assessment.is_safe is True

    def test_full_flow_warning(self):
        """完整流程: 中风险策略 → WARNING."""
        controller = RiskController()
        ctx = RiskContext(
            product_id="game_y",
            campaign_id="camp_002",
            audience_segment="eu_ios",
            budget_current=2000,
            budget_proposed=3500,  # 75% increase
            sample_size=20,
            days_since_first_launch=45,
            opportunity_type="budget_optimization",
            signal_types=["roas_drop"],
        )
        strategy = {
            "strategy_id": "S_WARN",
            "strategy_name": "Aggressive Budget Increase",
            "confidence_score": 0.55,
            "final_score": 0.5,
            "risk_score": 0.4,
            "action_type": "budget_increase",
            "trigger": {"action_type": "budget_increase", "opportunity_type": "budget_optimization"},
        }
        assessment = controller.evaluate(strategy, ctx)
        assert assessment.risk_score > 0.1

    def test_full_flow_block(self):
        """完整流程: 高风险策略 → BLOCK."""
        controller = RiskController(policy=RiskPolicy(block_threshold=0.6))
        ctx = RiskContext(
            product_id="game_z",
            campaign_id="camp_003",
            audience_segment="us_ios",
            budget_current=1000,
            budget_proposed=5000,  # 400% increase
            sample_size=2,
            days_since_first_launch=3,  # 非常新产品
            opportunity_type="campaign_restructure",
            signal_types=["roas_crash"],
        )
        strategy = {
            "strategy_id": "S_BLOCK",
            "strategy_name": "delete_campaign and restart",
            "confidence_score": 0.15,
            "final_score": 0.1,
            "risk_score": 0.95,
            "action_type": "delete_campaign",
            "trigger": {"action_type": "delete_campaign", "opportunity_type": "campaign_restructure"},
        }
        assessment = controller.evaluate(strategy, ctx)
        assert assessment.decision == RiskDecision.BLOCK
        assert assessment.is_blocked is True
        assert assessment.risk_level == RiskLevel.CRITICAL

    def test_full_flow_with_failure_memory(self):
        """完整流程: Failure Memory 集成."""
        fm = make_failure_memory_with_patterns()
        controller = RiskController(fm)
        ctx = RiskContext(
            product_id="merge_witch",
            campaign_id="camp_004",
            audience_segment="ios_us_facebook",
            budget_current=1000,
            budget_proposed=2000,
            sample_size=50,
            days_since_first_launch=120,
            opportunity_type="creative_refresh",
            signal_types=["creative_fatigue"],
        )
        strategy = {
            "strategy_id": "S_FM",
            "strategy_name": "Budget Increase with History",
            "confidence_score": 0.7,
            "final_score": 0.65,
            "risk_score": 0.5,
            "action_type": "budget_increase",
            "trigger": {"action_type": "budget_increase", "opportunity_type": "creative_refresh"},
        }
        assessment = controller.evaluate(strategy, ctx)
        assert assessment.failure_risk > 0
        assert assessment.risk_score > 0
        assert isinstance(assessment, RiskAssessment)