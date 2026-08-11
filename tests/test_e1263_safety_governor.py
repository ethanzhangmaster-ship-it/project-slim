"""E12.6.3 — Safety Governor 测试。

覆盖:
  - Models: SafetyAction, RiskLevel, SafetyContext, SafetyDecision, RiskReport, RollbackRecord
  - RiskDetector: mutation/spend/prediction/knowledge risk, total score
  - SafetyPolicy: 5 条规则（HighMutation, LargeSpend, InsufficientData, WinnerProtection, PopulationCollapse）
  - RollbackManager: creative/budget/strategy rollback
  - SafetyGovernor: allow/modify/block/rollback paths
  - Integration: Decision → Safety, Resource → Safety, Evolution → Safety
"""

import pytest
from datetime import datetime, timezone

from market_ops.creative_vision_runtime.reality.meta_intelligence.governance import (
    HighMutationPolicy,
    InsufficientDataPolicy,
    LargeSpendPolicy,
    PopulationCollapsePolicy,
    RiskDetector,
    RiskLevel,
    RiskReport,
    RollbackManager,
    RollbackRecord,
    SafetyAction,
    SafetyContext,
    SafetyDecision,
    SafetyGovernor,
    SafetyPolicy,
    WinnerProtectionPolicy,
    get_risk_threshold,
    get_safety_action_priority,
    risk_level_from_score,
    DEFAULT_SAFETY_POLICIES,
)


# ── Helpers ─────────────────────────────────────────────────


def make_context(
    product_id: str = "P04",
    action: str = "START_EXPERIMENT",
    predicted_impact: float = 0.0,
    spend_amount: float = 1000.0,
    mutation_distance: float = 0.3,
    confidence: float = 0.8,
    knowledge_confidence: float = 0.7,
    population_diversity: float = 0.5,
    historical_winner_similarity: float = 0.6,
    experiment_count: int = 5,
    daily_budget_limit: float = 10000.0,
    max_mutation_distance: float = 0.70,
) -> SafetyContext:
    return SafetyContext(
        product_id=product_id,
        action=action,
        predicted_impact=predicted_impact,
        spend_amount=spend_amount,
        mutation_distance=mutation_distance,
        confidence=confidence,
        knowledge_confidence=knowledge_confidence,
        population_diversity=population_diversity,
        historical_winner_similarity=historical_winner_similarity,
        experiment_count=experiment_count,
        daily_budget_limit=daily_budget_limit,
        max_mutation_distance=max_mutation_distance,
    )


# ═══════════════════════════════════════════════════════════════
# TestSafetyModels — 20 tests
# ═══════════════════════════════════════════════════════════════


class TestSafetyModels:
    """SafetyAction, RiskLevel, SafetyContext, SafetyDecision, RiskReport, RollbackRecord"""

    # ── SafetyAction ──

    def test_safety_action_enum_values(self):
        assert SafetyAction.ALLOW.value == "allow"
        assert SafetyAction.MODIFY.value == "modify"
        assert SafetyAction.BLOCK.value == "block"
        assert SafetyAction.ROLLBACK.value == "rollback"
        assert SafetyAction.REQUIRE_REVIEW.value == "require_review"

    def test_safety_action_priority(self):
        assert get_safety_action_priority(SafetyAction.ALLOW) == 0
        assert get_safety_action_priority(SafetyAction.ROLLBACK) == 100
        assert get_safety_action_priority(SafetyAction.BLOCK) > get_safety_action_priority(SafetyAction.MODIFY)

    # ── RiskLevel ──

    def test_risk_level_enum_values(self):
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_risk_level_from_score_low(self):
        assert risk_level_from_score(0.0) == RiskLevel.LOW
        assert risk_level_from_score(0.24) == RiskLevel.LOW

    def test_risk_level_from_score_medium(self):
        assert risk_level_from_score(0.25) == RiskLevel.MEDIUM
        assert risk_level_from_score(0.49) == RiskLevel.MEDIUM

    def test_risk_level_from_score_high(self):
        assert risk_level_from_score(0.50) == RiskLevel.HIGH
        assert risk_level_from_score(0.74) == RiskLevel.HIGH

    def test_risk_level_from_score_critical(self):
        assert risk_level_from_score(0.75) == RiskLevel.CRITICAL
        assert risk_level_from_score(1.0) == RiskLevel.CRITICAL

    def test_get_risk_threshold(self):
        low = get_risk_threshold(RiskLevel.LOW)
        assert low[0] == 0.0
        assert low[1] == 0.25

    # ── SafetyContext ──

    def test_context_creation(self):
        ctx = make_context()
        assert ctx.product_id == "P04"
        assert ctx.action == "START_EXPERIMENT"

    def test_context_is_high_spend(self):
        assert make_context(spend_amount=6000.0).is_high_spend is True
        assert make_context(spend_amount=3000.0).is_high_spend is False

    def test_context_is_high_mutation(self):
        assert make_context(mutation_distance=0.8).is_high_mutation is True
        assert make_context(mutation_distance=0.3).is_high_mutation is False

    def test_context_is_low_confidence(self):
        assert make_context(confidence=0.3).is_low_confidence is True
        assert make_context(confidence=0.8).is_low_confidence is False

    def test_context_is_winner_divergent(self):
        assert make_context(historical_winner_similarity=0.1).is_winner_divergent is True
        assert make_context(historical_winner_similarity=0.5).is_winner_divergent is False

    def test_context_is_population_collapsed(self):
        assert make_context(population_diversity=0.1).is_population_collapsed is True
        assert make_context(population_diversity=0.3).is_population_collapsed is False

    def test_context_has_insufficient_data(self):
        assert make_context(experiment_count=1).has_insufficient_data is True
        assert make_context(experiment_count=5).has_insufficient_data is False

    def test_context_to_dict(self):
        ctx = make_context()
        d = ctx.to_dict()
        assert d["product_id"] == "P04"
        assert "is_high_spend" in d

    # ── SafetyDecision ──

    def test_decision_creation(self):
        d = SafetyDecision(
            product_id="P04",
            action=SafetyAction.ALLOW,
            risk_level=RiskLevel.LOW,
        )
        assert d.is_allowed is True
        assert d.is_blocked is False

    def test_decision_is_blocked(self):
        d = SafetyDecision(action=SafetyAction.BLOCK, risk_level=RiskLevel.HIGH)
        assert d.is_blocked is True
        assert d.is_allowed is False

    def test_decision_is_modified(self):
        d = SafetyDecision(action=SafetyAction.MODIFY, risk_level=RiskLevel.MEDIUM)
        assert d.is_modified is True

    def test_decision_needs_review(self):
        d = SafetyDecision(action=SafetyAction.REQUIRE_REVIEW, risk_level=RiskLevel.MEDIUM)
        assert d.needs_review is True

    def test_decision_is_safe(self):
        d = SafetyDecision(action=SafetyAction.ALLOW, risk_level=RiskLevel.LOW)
        assert d.is_safe is True

        d2 = SafetyDecision(action=SafetyAction.BLOCK, risk_level=RiskLevel.HIGH)
        assert d2.is_safe is False

    def test_decision_action_label(self):
        d = SafetyDecision(action=SafetyAction.ALLOW, risk_level=RiskLevel.LOW)
        assert d.action_label == "放行"

    def test_decision_to_dict(self):
        d = SafetyDecision(
            product_id="P04",
            action=SafetyAction.BLOCK,
            risk_level=RiskLevel.HIGH,
            score=0.65,
            reasons=["test"],
            constraints={"max_budget": 1000},
        )
        dd = d.to_dict()
        assert dd["action"] == "block"
        assert dd["is_blocked"] is True
        assert dd["constraints"]["max_budget"] == 1000

    def test_decision_repr(self):
        d = SafetyDecision(action=SafetyAction.BLOCK, risk_level=RiskLevel.HIGH, score=0.65)
        r = repr(d)
        assert "block" in r
        assert "high" in r

    # ── RiskReport ──

    def test_risk_report_creation(self):
        report = RiskReport(
            product_id="P04",
            total_score=0.45,
            risk_level=RiskLevel.MEDIUM,
        )
        assert report.report_id.startswith("RR_")
        assert report.total_score == 0.45

    def test_risk_report_to_dict(self):
        report = RiskReport(
            product_id="P04",
            total_score=0.45,
            risk_level=RiskLevel.MEDIUM,
            mutation_risk=0.3,
            spend_risk=0.2,
            prediction_risk=0.4,
            knowledge_risk=0.3,
        )
        d = report.to_dict()
        assert d["mutation_risk"] == 0.3

    # ── RollbackRecord ──

    def test_rollback_record_creation(self):
        record = RollbackRecord(
            product_id="P04",
            target_type="budget",
            target_id="budget_p04",
            before_state={"budget": 5000},
            after_state={"budget": 3000},
            reason="population collapse",
        )
        assert record.record_id.startswith("RB_")
        assert record.has_changes is True

    def test_rollback_record_no_changes(self):
        record = RollbackRecord(
            product_id="P04",
            target_type="budget",
            target_id="budget_p04",
            before_state={"budget": 5000},
            after_state={"budget": 5000},
            reason="no change",
        )
        assert record.has_changes is False


# ═══════════════════════════════════════════════════════════════
# TestRiskDetector — 30 tests
# ═══════════════════════════════════════════════════════════════


class TestRiskDetector:
    """RiskDetector — 5 维风险评估"""

    # ── Mutation Risk ──

    def test_mutation_risk_low(self):
        ctx = make_context(mutation_distance=0.2)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.mutation_risk < 0.5

    def test_mutation_risk_high(self):
        ctx = make_context(mutation_distance=0.9)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.mutation_risk > 0.7

    def test_mutation_risk_zero(self):
        ctx = make_context(mutation_distance=0.0)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.mutation_risk == 0.0

    def test_mutation_risk_at_max(self):
        ctx = make_context(mutation_distance=0.7)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.mutation_risk == pytest.approx(1.0)

    # ── Spend Risk ──

    def test_spend_risk_low(self):
        ctx = make_context(spend_amount=1000.0, daily_budget_limit=10000.0)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.spend_risk < 0.3

    def test_spend_risk_high(self):
        ctx = make_context(spend_amount=8000.0, daily_budget_limit=10000.0)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.spend_risk == pytest.approx(0.8)

    def test_spend_risk_exceeds_limit(self):
        ctx = make_context(spend_amount=15000.0, daily_budget_limit=10000.0)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.spend_risk == 1.0

    def test_spend_risk_zero_budget_limit(self):
        ctx = make_context(spend_amount=5000.0, daily_budget_limit=0.0)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.spend_risk == 1.0

    # ── Prediction Risk ──

    def test_prediction_risk_high_confidence(self):
        ctx = make_context(confidence=0.9)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.prediction_risk < 0.2

    def test_prediction_risk_low_confidence(self):
        ctx = make_context(confidence=0.3)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.prediction_risk == pytest.approx(0.7)

    def test_prediction_risk_zero_confidence(self):
        ctx = make_context(confidence=0.0)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.prediction_risk == 1.0

    def test_prediction_risk_full_confidence(self):
        ctx = make_context(confidence=1.0)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.prediction_risk == 0.0

    # ── Knowledge Risk ──

    def test_knowledge_risk_high(self):
        ctx = make_context(knowledge_confidence=0.2)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.knowledge_risk == pytest.approx(0.8)

    def test_knowledge_risk_low(self):
        ctx = make_context(knowledge_confidence=0.9)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.knowledge_risk < 0.2

    # ── Diversity Risk ──

    def test_diversity_risk_healthy(self):
        ctx = make_context(population_diversity=0.8)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.diversity_risk == pytest.approx(0.2)

    def test_diversity_risk_collapsed(self):
        ctx = make_context(population_diversity=0.1)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.diversity_risk == pytest.approx(0.9)

    # ── Total Score ──

    def test_total_score_low_risk(self):
        ctx = make_context(
            mutation_distance=0.1, spend_amount=500.0,
            confidence=0.95, knowledge_confidence=0.9,
        )
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.total_score < 0.25
        assert report.risk_level == RiskLevel.LOW

    def test_total_score_medium_risk(self):
        ctx = make_context(
            mutation_distance=0.4, spend_amount=3000.0,
            confidence=0.6, knowledge_confidence=0.6,
        )
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert 0.25 <= report.total_score < 0.75

    def test_total_score_high_risk(self):
        ctx = make_context(
            mutation_distance=0.8, spend_amount=8000.0,
            confidence=0.3, knowledge_confidence=0.3,
        )
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.total_score >= 0.5

    def test_total_score_critical(self):
        ctx = make_context(
            mutation_distance=0.9, spend_amount=10000.0,
            confidence=0.1, knowledge_confidence=0.1,
        )
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.total_score >= 0.75
        assert report.risk_level == RiskLevel.CRITICAL

    def test_total_score_formula_weights(self):
        ctx = make_context(
            mutation_distance=0.7, spend_amount=5000.0,
            confidence=0.5, knowledge_confidence=0.5,
        )
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        expected = (
            1.0 * 0.30 + 0.5 * 0.25 + 0.5 * 0.25 + 0.5 * 0.20
        )
        assert report.total_score == pytest.approx(expected, abs=0.01)

    def test_risk_detector_details(self):
        ctx = make_context(mutation_distance=0.9, spend_amount=8000.0, confidence=0.2)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert len(report.details) > 0

    def test_risk_detector_safe_details(self):
        ctx = make_context(mutation_distance=0.1, spend_amount=500.0, confidence=0.9)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert any("acceptable" in d for d in report.details)

    def test_risk_detector_custom_weights(self):
        ctx = make_context(mutation_distance=0.5, spend_amount=5000.0, confidence=0.5)
        detector = RiskDetector(mutation_weight=0.5, spend_weight=0.2, prediction_weight=0.2, knowledge_weight=0.1)
        report = detector.evaluate(ctx)
        assert report.total_score > 0

    def test_risk_detector_repr(self):
        detector = RiskDetector()
        r = repr(detector)
        assert "RiskDetector" in r

    def test_risk_score_clamped(self):
        ctx = make_context(mutation_distance=2.0, spend_amount=50000.0, confidence=-1.0)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert 0.0 <= report.total_score <= 1.0

    def test_safe_context_low_risk(self):
        ctx = make_context(mutation_distance=0.05, spend_amount=100.0, confidence=0.99, knowledge_confidence=0.99)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.risk_level == RiskLevel.LOW

    def test_mutation_risk_zero_max_distance(self):
        ctx = make_context(mutation_distance=0.5, max_mutation_distance=0.0)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.mutation_risk == 1.0

    def test_spend_risk_zero(self):
        ctx = make_context(spend_amount=0.0)
        detector = RiskDetector()
        report = detector.evaluate(ctx)
        assert report.spend_risk == 0.0


# ═══════════════════════════════════════════════════════════════
# TestSafetyPolicy — 30 tests
# ═══════════════════════════════════════════════════════════════


class TestHighMutationPolicy:
    """HighMutationPolicy — 高突变 → MODIFY"""

    def test_triggers_on_high_mutation(self):
        ctx = make_context(mutation_distance=0.85)
        policy = HighMutationPolicy()
        decision = policy.evaluate(ctx)
        assert decision is not None
        assert decision.action == SafetyAction.MODIFY
        assert decision.constraints["max_mutation_distance"] == 0.3

    def test_no_trigger_low_mutation(self):
        ctx = make_context(mutation_distance=0.5)
        policy = HighMutationPolicy()
        decision = policy.evaluate(ctx)
        assert decision is None

    def test_no_trigger_at_boundary(self):
        ctx = make_context(mutation_distance=0.70)
        policy = HighMutationPolicy()
        decision = policy.evaluate(ctx)
        assert decision is None

    def test_rule_name(self):
        assert HighMutationPolicy().name == "high_mutation"


class TestLargeSpendPolicy:
    """LargeSpendPolicy — 大额 + 低置信度 → BLOCK"""

    def test_triggers_on_large_spend_low_confidence(self):
        ctx = make_context(spend_amount=6000.0, confidence=0.6)
        policy = LargeSpendPolicy()
        decision = policy.evaluate(ctx)
        assert decision is not None
        assert decision.action == SafetyAction.BLOCK

    def test_no_trigger_small_spend(self):
        ctx = make_context(spend_amount=3000.0, confidence=0.6)
        policy = LargeSpendPolicy()
        decision = policy.evaluate(ctx)
        assert decision is None

    def test_no_trigger_high_confidence(self):
        ctx = make_context(spend_amount=6000.0, confidence=0.9)
        policy = LargeSpendPolicy()
        decision = policy.evaluate(ctx)
        assert decision is None

    def test_no_trigger_both_ok(self):
        ctx = make_context(spend_amount=3000.0, confidence=0.9)
        policy = LargeSpendPolicy()
        decision = policy.evaluate(ctx)
        assert decision is None

    def test_triggers_at_boundary(self):
        ctx = make_context(spend_amount=5000.01, confidence=0.79)
        policy = LargeSpendPolicy()
        decision = policy.evaluate(ctx)
        assert decision is not None


class TestInsufficientDataPolicy:
    """InsufficientDataPolicy — 数据不足 → REQUIRE_REVIEW"""

    def test_triggers_on_low_experiment_count(self):
        ctx = make_context(experiment_count=1)
        policy = InsufficientDataPolicy()
        decision = policy.evaluate(ctx)
        assert decision is not None
        assert decision.action == SafetyAction.REQUIRE_REVIEW

    def test_no_trigger_sufficient_experiments(self):
        ctx = make_context(experiment_count=5)
        policy = InsufficientDataPolicy()
        decision = policy.evaluate(ctx)
        assert decision is None

    def test_triggers_at_boundary(self):
        ctx = make_context(experiment_count=2)
        policy = InsufficientDataPolicy()
        decision = policy.evaluate(ctx)
        assert decision is not None


class TestWinnerProtectionPolicy:
    """WinnerProtectionPolicy — winner 相似度低 → BLOCK"""

    def test_triggers_on_low_similarity(self):
        ctx = make_context(historical_winner_similarity=0.1)
        policy = WinnerProtectionPolicy()
        decision = policy.evaluate(ctx)
        assert decision is not None
        assert decision.action == SafetyAction.BLOCK

    def test_no_trigger_high_similarity(self):
        ctx = make_context(historical_winner_similarity=0.5)
        policy = WinnerProtectionPolicy()
        decision = policy.evaluate(ctx)
        assert decision is None

    def test_no_trigger_at_boundary(self):
        ctx = make_context(historical_winner_similarity=0.20)
        policy = WinnerProtectionPolicy()
        decision = policy.evaluate(ctx)
        assert decision is None


class TestPopulationCollapsePolicy:
    """PopulationCollapsePolicy — 多样性低 → ROLLBACK"""

    def test_triggers_on_low_diversity(self):
        ctx = make_context(population_diversity=0.1)
        policy = PopulationCollapsePolicy()
        decision = policy.evaluate(ctx)
        assert decision is not None
        assert decision.action == SafetyAction.ROLLBACK
        assert decision.risk_level == RiskLevel.CRITICAL

    def test_no_trigger_healthy_diversity(self):
        ctx = make_context(population_diversity=0.5)
        policy = PopulationCollapsePolicy()
        decision = policy.evaluate(ctx)
        assert decision is None

    def test_no_trigger_at_boundary(self):
        ctx = make_context(population_diversity=0.15)
        policy = PopulationCollapsePolicy()
        decision = policy.evaluate(ctx)
        assert decision is None


class TestSafetyPolicyBase:
    """SafetyPolicy 基类"""

    def test_policy_abstract(self):
        with pytest.raises(TypeError):
            SafetyPolicy()  # type: ignore

    def test_policy_repr(self):
        policy = HighMutationPolicy()
        r = repr(policy)
        assert "HighMutationPolicy" in r

    def test_default_policies_count(self):
        assert len(DEFAULT_SAFETY_POLICIES) == 5

    def test_default_policies_order(self):
        # PopulationCollapse should be first (highest priority)
        assert isinstance(DEFAULT_SAFETY_POLICIES[0], PopulationCollapsePolicy)


# ═══════════════════════════════════════════════════════════════
# TestRollbackManager — 20 tests
# ═══════════════════════════════════════════════════════════════


class TestRollbackManager:
    """RollbackManager — 创意/预算/策略回滚"""

    # ── Creative Rollback ──

    def test_save_creative_state(self):
        rm = RollbackManager()
        rm.save_creative_state("P04", "genome_1", {"hook": "rescue", "visual": "cute"})
        state = rm.get_creative_state("P04", "genome_1")
        assert state is not None
        assert state["hook"] == "rescue"

    def test_rollback_creative(self):
        rm = RollbackManager()
        rm.save_creative_state("P04", "genome_1", {"hook": "rescue", "version": 1})
        rm.save_creative_state("P04", "genome_1", {"hook": "horror", "version": 2})
        record = rm.rollback_creative("P04", "genome_1", "unsafe mutation")
        assert record is not None
        assert record.target_type == "creative"
        assert record.before_state["hook"] == "horror"
        assert record.after_state["hook"] == "rescue"

    def test_rollback_creative_insufficient_history(self):
        rm = RollbackManager()
        rm.save_creative_state("P04", "genome_1", {"hook": "rescue"})
        record = rm.rollback_creative("P04", "genome_1", "no history")
        assert record is None

    def test_get_creative_state_nonexistent(self):
        rm = RollbackManager()
        state = rm.get_creative_state("P99", "nonexistent")
        assert state is None

    # ── Budget Rollback ──

    def test_save_budget_state(self):
        rm = RollbackManager()
        rm.save_budget_state("P04", {"budget": 3000, "daily_cap": 500})
        state = rm.get_budget_state("P04")
        assert state is not None
        assert state["budget"] == 3000

    def test_rollback_budget(self):
        rm = RollbackManager()
        rm.save_budget_state("P04", {"budget": 3000})
        rm.save_budget_state("P04", {"budget": 10000})
        record = rm.rollback_budget("P04", "overspend")
        assert record is not None
        assert record.target_type == "budget"
        assert record.after_state["budget"] == 3000

    def test_rollback_budget_insufficient_history(self):
        rm = RollbackManager()
        rm.save_budget_state("P04", {"budget": 3000})
        record = rm.rollback_budget("P04", "no history")
        assert record is None

    def test_rollback_budget_custom_target(self):
        rm = RollbackManager()
        rm.save_budget_state("P04", {"budget": 3000})
        rm.save_budget_state("P04", {"budget": 10000})
        record = rm.rollback_budget("P04", "custom", target_budget=5000)
        assert record is not None
        assert record.after_state["budget"] == 5000

    # ── Strategy Rollback ──

    def test_save_strategy_state(self):
        rm = RollbackManager()
        rm.save_strategy_state("P04", "strategy_v1", {"roi_target": 1.5, "fatigue_limit": 0.3})
        state = rm.get_strategy_state("P04", "strategy_v1")
        assert state is not None
        assert state["roi_target"] == 1.5

    def test_rollback_strategy(self):
        rm = RollbackManager()
        rm.save_strategy_state("P04", "strategy_v1", {"roi_target": 1.5})
        rm.save_strategy_state("P04", "strategy_v1", {"roi_target": 3.0})
        record = rm.rollback_strategy("P04", "strategy_v1", "too aggressive")
        assert record is not None
        assert record.target_type == "strategy"
        assert record.after_state["roi_target"] == 1.5

    def test_rollback_strategy_insufficient_history(self):
        rm = RollbackManager()
        rm.save_strategy_state("P04", "strategy_v1", {"roi_target": 1.5})
        record = rm.rollback_strategy("P04", "strategy_v1", "no history")
        assert record is None

    # ── History Management ──

    def test_get_history(self):
        rm = RollbackManager()
        rm.save_budget_state("P04", {"budget": 3000})
        rm.save_budget_state("P04", {"budget": 10000})
        rm.rollback_budget("P04", "test")
        history = rm.get_history()
        assert len(history) == 1

    def test_get_history_filtered(self):
        rm = RollbackManager()
        rm.save_budget_state("P04", {"budget": 3000})
        rm.save_budget_state("P04", {"budget": 10000})
        rm.save_budget_state("P05", {"budget": 5000})
        rm.save_budget_state("P05", {"budget": 8000})
        rm.rollback_budget("P04", "test")
        rm.rollback_budget("P05", "test")
        history = rm.get_history(product_id="P04")
        assert len(history) == 1
        assert history[0].product_id == "P04"

    def test_get_history_by_type(self):
        rm = RollbackManager()
        rm.save_creative_state("P04", "g1", {"v": 1})
        rm.save_creative_state("P04", "g1", {"v": 2})
        rm.rollback_creative("P04", "g1", "test")
        history = rm.get_history(target_type="creative")
        assert len(history) == 1

    def test_get_history_count(self):
        rm = RollbackManager()
        assert rm.get_history_count() == 0
        rm.save_budget_state("P04", {"budget": 3000})
        rm.save_budget_state("P04", {"budget": 10000})
        rm.rollback_budget("P04", "test")
        assert rm.get_history_count() == 1

    def test_get_snapshot_count(self):
        rm = RollbackManager()
        rm.save_creative_state("P04", "g1", {"v": 1})
        rm.save_creative_state("P04", "g1", {"v": 2})
        rm.save_creative_state("P05", "g2", {"v": 1})
        counts = rm.get_snapshot_count("creative")
        assert len(counts) == 2

    def test_clear_history(self):
        rm = RollbackManager()
        rm.save_budget_state("P04", {"budget": 3000})
        rm.clear_history()
        assert rm.get_history_count() == 0
        state = rm.get_budget_state("P04")
        assert state is None

    def test_max_history_limit(self):
        rm = RollbackManager(max_history=3)
        for i in range(5):
            rm.save_budget_state("P04", {"budget": i * 1000})
        state = rm.get_budget_state("P04")
        assert state is not None
        assert state["budget"] == 4000  # last 3: 2000, 3000, 4000

    def test_rollback_manager_repr(self):
        rm = RollbackManager()
        r = repr(rm)
        assert "RollbackManager" in r


# ═══════════════════════════════════════════════════════════════
# TestSafetyGovernor — 30 tests
# ═══════════════════════════════════════════════════════════════


class TestSafetyGovernor:
    """SafetyGovernor — 核心控制器"""

    def test_governor_creation(self):
        gov = SafetyGovernor()
        assert len(gov.policies) == 5
        assert gov.default_action == SafetyAction.ALLOW

    def test_evaluate_allow(self):
        """安全上下文 → ALLOW"""
        ctx = make_context(
            mutation_distance=0.1, spend_amount=500.0,
            confidence=0.95, knowledge_confidence=0.9,
            population_diversity=0.7, historical_winner_similarity=0.8,
        )
        gov = SafetyGovernor()
        decision = gov.evaluate(ctx)
        assert decision.action == SafetyAction.ALLOW

    def test_evaluate_modify_high_mutation(self):
        """高突变 → MODIFY"""
        ctx = make_context(
            mutation_distance=0.85, spend_amount=1000.0,
            confidence=0.8, population_diversity=0.5,
            historical_winner_similarity=0.5,
        )
        gov = SafetyGovernor()
        decision = gov.evaluate(ctx)
        assert decision.action == SafetyAction.MODIFY
        assert "max_mutation_distance" in decision.constraints

    def test_evaluate_block_large_spend(self):
        """大额花费 → BLOCK"""
        ctx = make_context(
            spend_amount=8000.0, confidence=0.6,
            mutation_distance=0.2, population_diversity=0.5,
            historical_winner_similarity=0.5,
        )
        gov = SafetyGovernor()
        decision = gov.evaluate(ctx)
        assert decision.action == SafetyAction.BLOCK

    def test_evaluate_block_winner_protection(self):
        """Winner 保护 → BLOCK"""
        ctx = make_context(
            historical_winner_similarity=0.1,
            mutation_distance=0.3, spend_amount=1000.0,
            confidence=0.8, population_diversity=0.5,
        )
        gov = SafetyGovernor()
        decision = gov.evaluate(ctx)
        assert decision.action == SafetyAction.BLOCK

    def test_evaluate_rollback_population(self):
        """种群崩溃 → ROLLBACK"""
        ctx = make_context(
            population_diversity=0.1,
            mutation_distance=0.3, spend_amount=1000.0,
            confidence=0.8, historical_winner_similarity=0.5,
        )
        gov = SafetyGovernor()
        decision = gov.evaluate(ctx)
        assert decision.action == SafetyAction.ROLLBACK

    def test_evaluate_require_review(self):
        """数据不足 → REQUIRE_REVIEW"""
        ctx = make_context(
            experiment_count=1,
            mutation_distance=0.2, spend_amount=500.0,
            confidence=0.8, population_diversity=0.5,
            historical_winner_similarity=0.5,
        )
        gov = SafetyGovernor()
        decision = gov.evaluate(ctx)
        assert decision.action == SafetyAction.REQUIRE_REVIEW

    def test_rollback_wins_over_block(self):
        """ROLLBACK 优先级高于 BLOCK"""
        ctx = make_context(
            population_diversity=0.1,  # triggers ROLLBACK
            historical_winner_similarity=0.1,  # would trigger BLOCK
            spend_amount=8000.0, confidence=0.5,  # would trigger BLOCK
            mutation_distance=0.85,  # would trigger MODIFY
        )
        gov = SafetyGovernor()
        decision = gov.evaluate(ctx)
        assert decision.action == SafetyAction.ROLLBACK

    def test_block_wins_over_modify(self):
        """BLOCK 优先级高于 MODIFY"""
        ctx = make_context(
            historical_winner_similarity=0.1,  # BLOCK
            mutation_distance=0.85,  # MODIFY
            spend_amount=1000.0, confidence=0.8,
            population_diversity=0.5,
        )
        gov = SafetyGovernor()
        decision = gov.evaluate(ctx)
        assert decision.action == SafetyAction.BLOCK

    def test_is_safe(self):
        ctx = make_context(
            mutation_distance=0.1, spend_amount=500.0, confidence=0.95,
        )
        gov = SafetyGovernor()
        assert gov.is_safe(ctx) is True

    def test_is_not_safe(self):
        ctx = make_context(spend_amount=8000.0, confidence=0.5)
        gov = SafetyGovernor()
        assert gov.is_safe(ctx) is False

    def test_is_blocked(self):
        ctx = make_context(spend_amount=8000.0, confidence=0.5)
        gov = SafetyGovernor()
        assert gov.is_blocked(ctx) is True

    def test_is_not_blocked(self):
        ctx = make_context(
            mutation_distance=0.1, spend_amount=500.0, confidence=0.95,
        )
        gov = SafetyGovernor()
        assert gov.is_blocked(ctx) is False

    def test_get_risk_report(self):
        ctx = make_context(mutation_distance=0.8, confidence=0.3)
        gov = SafetyGovernor()
        report = gov.get_risk_report(ctx)
        assert isinstance(report, RiskReport)
        assert report.total_score > 0.5

    def test_get_rollback_history(self):
        gov = SafetyGovernor()
        gov.rollback_manager.save_budget_state("P04", {"budget": 3000})
        gov.rollback_manager.save_budget_state("P04", {"budget": 10000})
        gov.rollback_manager.rollback_budget("P04", "test")
        history = gov.get_rollback_history()
        assert len(history) == 1

    def test_get_summary(self):
        ctx = make_context(spend_amount=8000.0, confidence=0.5)
        gov = SafetyGovernor()
        summary = gov.get_summary(ctx)
        assert summary["product_id"] == "P04"
        assert not summary["is_allowed"]
        assert "risk_breakdown" in summary

    def test_decision_has_risk_report(self):
        ctx = make_context(mutation_distance=0.85)
        gov = SafetyGovernor()
        decision = gov.evaluate(ctx)
        assert decision.risk_report is not None

    def test_decision_has_context_snapshot(self):
        ctx = make_context()
        gov = SafetyGovernor()
        decision = gov.evaluate(ctx)
        assert len(decision.context_snapshot) > 0

    def test_custom_policies(self):
        gov = SafetyGovernor(policies=[HighMutationPolicy()])
        assert len(gov.policies) == 1

    def test_custom_risk_detector(self):
        detector = RiskDetector(mutation_weight=0.5)
        gov = SafetyGovernor(risk_detector=detector)
        assert gov.risk_detector.mutation_weight == 0.5

    def test_governor_repr(self):
        gov = SafetyGovernor()
        r = repr(gov)
        assert "SafetyGovernor" in r

    def test_rollback_triggers_manager(self):
        ctx = make_context(population_diversity=0.1)
        gov = SafetyGovernor()
        gov.rollback_manager.save_budget_state("P04", {"budget": 3000})
        gov.rollback_manager.save_budget_state("P04", {"budget": 10000})
        decision = gov.evaluate(ctx)
        assert decision.action == SafetyAction.ROLLBACK
        # 回滚记录应该被创建
        history = gov.get_rollback_history(product_id="P04")
        assert len(history) >= 1

    def test_no_policies_triggered_default(self):
        ctx = make_context(
            mutation_distance=0.2, spend_amount=500.0,
            confidence=0.9, knowledge_confidence=0.8,
            population_diversity=0.5, historical_winner_similarity=0.5,
            experiment_count=10,
        )
        gov = SafetyGovernor()
        decision = gov.evaluate(ctx)
        assert decision.action == SafetyAction.ALLOW
        assert "No safety policies triggered" in decision.reasons[0]

    def test_default_action_custom(self):
        gov = SafetyGovernor(default_action=SafetyAction.REQUIRE_REVIEW)
        ctx = make_context(
            mutation_distance=0.2, spend_amount=500.0, confidence=0.9,
            experiment_count=10, population_diversity=0.5,
            historical_winner_similarity=0.5,
        )
        decision = gov.evaluate(ctx)
        assert decision.action == SafetyAction.REQUIRE_REVIEW

    def test_governor_with_empty_policies(self):
        gov = SafetyGovernor(policies=[])
        ctx = make_context(mutation_distance=0.9, spend_amount=8000.0, confidence=0.3)
        decision = gov.evaluate(ctx)
        assert decision.action == SafetyAction.ALLOW


# ═══════════════════════════════════════════════════════════════
# TestIntegration — 20 tests
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """Integration tests — 完整流程"""

    def test_decision_to_safety_flow_allow(self):
        """Decision → Safety: ALLOW"""
        gov = SafetyGovernor()
        ctx = make_context(
            action="START_EXPERIMENT",
            mutation_distance=0.2, spend_amount=2000.0,
            confidence=0.85, experiment_count=10,
        )
        decision = gov.evaluate(ctx)
        assert decision.is_allowed

    def test_decision_to_safety_flow_block(self):
        """Decision → Safety: BLOCK"""
        gov = SafetyGovernor()
        ctx = make_context(
            action="START_EXPERIMENT",
            spend_amount=10000.0, confidence=0.5,
        )
        decision = gov.evaluate(ctx)
        assert decision.is_blocked

    def test_resource_to_safety_flow(self):
        """Resource → Safety: 预算调整被阻止"""
        gov = SafetyGovernor()
        ctx = make_context(
            action="ADJUST_BUDGET",
            spend_amount=8000.0, confidence=0.5,
        )
        decision = gov.evaluate(ctx)
        assert decision.action == SafetyAction.BLOCK

    def test_evolution_to_safety_flow_modify(self):
        """Evolution → Safety: 突变被限制"""
        gov = SafetyGovernor()
        ctx = make_context(
            action="MUTATE_DNA",
            mutation_distance=0.9, spend_amount=1000.0,
            confidence=0.8, population_diversity=0.5,
            historical_winner_similarity=0.5,
        )
        decision = gov.evaluate(ctx)
        assert decision.action == SafetyAction.MODIFY
        assert decision.constraints["max_mutation_distance"] == 0.3

    def test_evolution_to_safety_flow_block(self):
        """Evolution → Safety: 突变被阻止"""
        gov = SafetyGovernor()
        ctx = make_context(
            action="MUTATE_DNA",
            mutation_distance=0.5, spend_amount=1000.0,
            confidence=0.8, historical_winner_similarity=0.1,
        )
        decision = gov.evaluate(ctx)
        assert decision.action == SafetyAction.BLOCK

    def test_full_safe_experiment_flow(self):
        """完整的低风险实验流程"""
        gov = SafetyGovernor()
        ctx = make_context(
            action="START_EXPERIMENT",
            mutation_distance=0.2, spend_amount=2000.0,
            confidence=0.9, knowledge_confidence=0.85,
            population_diversity=0.6, historical_winner_similarity=0.7,
            experiment_count=10,
        )
        decision = gov.evaluate(ctx)
        assert decision.is_allowed
        assert decision.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)

    def test_full_risky_experiment_flow(self):
        """完整的高风险实验流程"""
        gov = SafetyGovernor()
        ctx = make_context(
            action="START_EXPERIMENT",
            mutation_distance=0.9, spend_amount=9000.0,
            confidence=0.3, knowledge_confidence=0.3,
            population_diversity=0.1, historical_winner_similarity=0.1,
            experiment_count=1,
        )
        decision = gov.evaluate(ctx)
        assert decision.action == SafetyAction.ROLLBACK

    def test_safety_decision_has_all_info(self):
        """安全决策包含完整信息"""
        gov = SafetyGovernor()
        ctx = make_context(spend_amount=8000.0, confidence=0.5)
        decision = gov.evaluate(ctx)
        summary = gov.get_summary(ctx)
        assert summary["safety_action"] == "block"
        assert summary["risk_score"] > 0
        assert len(summary["reasons"]) > 0

    def test_risk_breakdown_in_summary(self):
        """摘要包含风险分解"""
        gov = SafetyGovernor()
        ctx = make_context(mutation_distance=0.5, spend_amount=3000.0, confidence=0.6)
        summary = gov.get_summary(ctx)
        breakdown = summary["risk_breakdown"]
        assert "mutation_risk" in breakdown
        assert "spend_risk" in breakdown

    def test_multiple_actions_same_product(self):
        """同一产品不同操作的安全性"""
        gov = SafetyGovernor()
        safe_ctx = make_context(
            action="START_EXPERIMENT",
            mutation_distance=0.2, spend_amount=2000.0, confidence=0.85,
        )
        risky_ctx = make_context(
            action="START_EXPERIMENT",
            mutation_distance=0.9, spend_amount=9000.0, confidence=0.3,
        )
        assert gov.evaluate(safe_ctx).is_allowed
        assert gov.evaluate(risky_ctx).is_blocked

    def test_rollback_history_tracking(self):
        """回滚历史追踪"""
        gov = SafetyGovernor()
        rm = gov.rollback_manager
        rm.save_budget_state("P04", {"budget": 3000})
        rm.save_budget_state("P04", {"budget": 10000})
        rm.rollback_budget("P04", "test rollback")
        history = gov.get_rollback_history(product_id="P04")
        assert len(history) == 1
        assert history[0].target_type == "budget"

    def test_governor_with_custom_rollback_manager(self):
        """自定义回滚管理器"""
        rm = RollbackManager(max_history=50)
        gov = SafetyGovernor(rollback_manager=rm)
        assert gov.rollback_manager.max_history == 50

    def test_evaluate_preserves_reasons_order(self):
        """策略评估保持原因顺序"""
        ctx = make_context(
            spend_amount=8000.0, confidence=0.5,
            population_diversity=0.3, historical_winner_similarity=0.3,
            mutation_distance=0.3, experiment_count=5,
        )
        gov = SafetyGovernor()
        decision = gov.evaluate(ctx)
        assert len(decision.reasons) > 0

    def test_context_metadata_preserved(self):
        """上下文元数据保留"""
        ctx = make_context()
        ctx.metadata = {"source": "e12.6.1", "decision_id": "MD_abc"}
        assert ctx.metadata["source"] == "e12.6.1"

    def test_risk_report_auto_id(self):
        """风险报告自动生成 ID"""
        report = RiskReport(product_id="P04")
        assert report.report_id.startswith("RR_")

    def test_safety_decision_auto_id(self):
        """安全决策自动生成 ID"""
        d = SafetyDecision(product_id="P04", action=SafetyAction.ALLOW, risk_level=RiskLevel.LOW)
        assert d.decision_id.startswith("SD_")

    def test_rollback_record_auto_id(self):
        """回滚记录自动生成 ID"""
        record = RollbackRecord(product_id="P04", target_type="budget", target_id="b1")
        assert record.record_id.startswith("RB_")


# ═══════════════════════════════════════════════════════════════
# TestEdgeCases — 10 tests
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况"""

    def test_context_all_zeros(self):
        ctx = SafetyContext()
        assert ctx.product_id == ""
        assert ctx.spend_amount == 0.0

    def test_context_all_max_values(self):
        ctx = SafetyContext(
            mutation_distance=1.0, spend_amount=99999.0,
            confidence=0.0, knowledge_confidence=0.0,
            population_diversity=0.0, historical_winner_similarity=0.0,
            experiment_count=0,
        )
        assert ctx.is_high_mutation is True
        assert ctx.is_population_collapsed is True
        assert ctx.is_winner_divergent is True

    def test_risk_level_boundary_exact(self):
        assert risk_level_from_score(0.25) == RiskLevel.MEDIUM
        assert risk_level_from_score(0.50) == RiskLevel.HIGH
        assert risk_level_from_score(0.75) == RiskLevel.CRITICAL

    def test_risk_level_out_of_range(self):
        assert risk_level_from_score(-0.5) == RiskLevel.LOW
        assert risk_level_from_score(1.5) == RiskLevel.CRITICAL

    def test_rollback_no_history(self):
        rm = RollbackManager()
        assert rm.rollback_creative("P04", "g1", "test") is None
        assert rm.rollback_budget("P04", "test") is None
        assert rm.rollback_strategy("P04", "s1", "test") is None

    def test_governor_all_policies_trigger(self):
        ctx = make_context(
            population_diversity=0.1,  # ROLLBACK
            historical_winner_similarity=0.1,  # BLOCK
            spend_amount=8000.0, confidence=0.5,  # BLOCK
            mutation_distance=0.9,  # MODIFY
            experiment_count=1,  # REQUIRE_REVIEW
        )
        gov = SafetyGovernor()
        decision = gov.evaluate(ctx)
        assert decision.action == SafetyAction.ROLLBACK

    def test_risk_detector_with_zero_weights(self):
        detector = RiskDetector(mutation_weight=0.0, spend_weight=0.0, prediction_weight=0.0, knowledge_weight=0.0)
        ctx = make_context(mutation_distance=0.9, spend_amount=10000.0, confidence=0.0)
        report = detector.evaluate(ctx)
        assert report.total_score == 0.0

    def test_rollback_manager_max_history_zero(self):
        rm = RollbackManager(max_history=0)
        rm.save_budget_state("P04", {"budget": 1000})
        state = rm.get_budget_state("P04")
        assert state is None

    def test_safety_decision_constraints_preserved(self):
        ctx = make_context(mutation_distance=0.85)
        gov = SafetyGovernor()
        decision = gov.evaluate(ctx)
        assert decision.constraints["max_mutation_distance"] == 0.3
        assert decision.constraints["original_mutation_distance"] == 0.85

    def test_governor_empty_rollback(self):
        ctx = make_context(population_diversity=0.1)
        gov = SafetyGovernor()
        decision = gov.evaluate(ctx)
        assert decision.action == SafetyAction.ROLLBACK
        # 回滚可能失败（无历史），但决策仍然正确
        assert decision.risk_level == RiskLevel.CRITICAL