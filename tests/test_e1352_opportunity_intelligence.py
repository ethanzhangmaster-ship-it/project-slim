"""E13.5.2 Opportunity Intelligence Engine — 测试套件.

覆盖:
  - Rule Detection (7 rules)
  - Rule Engine (registration, defaults, error handling)
  - Opportunity Ranker (scoring, memory boost, top-n)
  - Opportunity Intelligence Engine (full pipeline, quick analyze)
  - Integration (end-to-end pipeline)
"""

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
    CurrentMetrics,
    DecisionPriority,
    ExpectedImpact,
    GrowthOpportunity,
    MemoryContext,
    OpportunitySource,
    OpportunityType,
    SignalSummary,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.opportunity_intelligence import (
    OpportunityIntelligenceEngine,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.opportunity_ranker import (
    OpportunityRanker,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.opportunity_rules import (
    AudienceExpansionRule,
    BudgetOptimizationRule,
    CreativeFatigueRule,
    ExperimentLaunchRule,
    MonetizationOptimizationRule,
    OpportunityRule,
    RiskMitigationRule,
    RuleEngine,
    ScalingOpportunityRule,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def make_signals(**kwargs) -> SignalSummary:
    defaults = {"fatigue_detected": False, "anomaly_detected": False, "trend": "stable"}
    defaults.update(kwargs)
    return SignalSummary(**defaults)


def make_metrics(**kwargs) -> CurrentMetrics:
    return CurrentMetrics(**kwargs)


def make_predictions(**kwargs) -> dict:
    return dict(kwargs)


# ═══════════════════════════════════════════════════════════════
# Test: CreativeFatigueRule
# ═══════════════════════════════════════════════════════════════


class TestCreativeFatigueRule:
    def test_no_fatigue_signal_returns_empty(self):
        rule = CreativeFatigueRule()
        signals = make_signals(fatigue_detected=False)
        metrics = make_metrics(ctr=0.01, frequency=4.0, roas=0.7)
        predictions = make_predictions(ctr_decay=0.35, roas_decay=0.20, fatigue_probability=0.9)
        result = rule.detect(signals, metrics, predictions)
        assert result == []

    def test_fatigue_with_all_conditions_met(self):
        rule = CreativeFatigueRule()
        signals = make_signals(fatigue_detected=True)
        metrics = make_metrics(ctr=0.005, frequency=4.5, roas=0.6)
        predictions = make_predictions(ctr_decay=0.35, roas_decay=0.20, fatigue_probability=0.87)
        result = rule.detect(signals, metrics, predictions)
        assert len(result) == 1
        opp = result[0]
        assert opp.opportunity_type == OpportunityType.CREATIVE_REFRESH
        assert opp.confidence > 0.5
        assert opp.urgency > 0.3
        assert "Creative fatigue" in opp.reason

    def test_fatigue_only_one_condition_not_enough(self):
        rule = CreativeFatigueRule()
        signals = make_signals(fatigue_detected=True)
        metrics = make_metrics(ctr=0.015, frequency=1.5, roas=1.2)
        predictions = make_predictions(ctr_decay=0.05, roas_decay=0.02, fatigue_probability=0.3)
        result = rule.detect(signals, metrics, predictions)
        assert result == []

    def test_fatigue_custom_thresholds(self):
        rule = CreativeFatigueRule(ctr_decay_threshold=0.10, frequency_threshold=2.0, roas_decay_threshold=0.05)
        signals = make_signals(fatigue_detected=True)
        metrics = make_metrics(ctr=0.008, frequency=2.5, roas=0.9)
        predictions = make_predictions(ctr_decay=0.15, roas_decay=0.08, fatigue_probability=0.7)
        result = rule.detect(signals, metrics, predictions)
        assert len(result) == 1

    def test_fatigue_priority_computed(self):
        rule = CreativeFatigueRule()
        signals = make_signals(fatigue_detected=True)
        metrics = make_metrics(ctr=0.004, frequency=6.0, roas=0.4)
        predictions = make_predictions(ctr_decay=0.50, roas_decay=0.30, fatigue_probability=0.95)
        result = rule.detect(signals, metrics, predictions)
        assert len(result) == 1
        assert result[0].priority in {DecisionPriority.HIGH, DecisionPriority.CRITICAL}

    def test_fatigue_source_is_signal_engine(self):
        rule = CreativeFatigueRule()
        signals = make_signals(fatigue_detected=True)
        metrics = make_metrics(ctr=0.005, frequency=4.0, roas=0.7)
        predictions = make_predictions(ctr_decay=0.30, roas_decay=0.15, fatigue_probability=0.8)
        result = rule.detect(signals, metrics, predictions)
        assert len(result) == 1
        assert result[0].source == OpportunitySource.SIGNAL_ENGINE

    def test_fatigue_no_predictions_defaults(self):
        rule = CreativeFatigueRule()
        signals = make_signals(fatigue_detected=True)
        metrics = make_metrics(ctr=0.005, frequency=4.0, roas=0.7)
        result = rule.detect(signals, metrics, None)
        assert result == []


# ═══════════════════════════════════════════════════════════════
# Test: ScalingOpportunityRule
# ═══════════════════════════════════════════════════════════════


class TestScalingOpportunityRule:
    def test_roas_below_target_returns_empty(self):
        rule = ScalingOpportunityRule(target_roas=1.2)
        signals = make_signals(trend="improving")
        metrics = make_metrics(roas=0.9, ctr=0.02, spend=200)
        result = rule.detect(signals, metrics)
        assert result == []

    def test_scaling_opportunity_detected(self):
        rule = ScalingOpportunityRule(target_roas=1.2)
        signals = make_signals(trend="improving")
        metrics = make_metrics(roas=1.8, ctr=0.025, spend=300, revenue=540)
        result = rule.detect(signals, metrics)
        assert len(result) == 1
        opp = result[0]
        assert opp.opportunity_type == OpportunityType.CREATIVE_SCALE
        assert opp.confidence > 0.5
        assert "Scaling opportunity" in opp.reason

    def test_trend_declining_blocks_scaling(self):
        rule = ScalingOpportunityRule()
        signals = make_signals(trend="declining")
        metrics = make_metrics(roas=1.8, ctr=0.025, spend=300)
        result = rule.detect(signals, metrics)
        assert result == []

    def test_spend_below_min_returns_empty(self):
        rule = ScalingOpportunityRule(spend_min=100)
        signals = make_signals(trend="improving")
        metrics = make_metrics(roas=1.8, ctr=0.025, spend=30)
        result = rule.detect(signals, metrics)
        assert result == []

    def test_ctr_below_min_returns_empty(self):
        rule = ScalingOpportunityRule(ctr_min=0.01)
        signals = make_signals(trend="improving")
        metrics = make_metrics(roas=1.8, ctr=0.005, spend=300)
        result = rule.detect(signals, metrics)
        assert result == []

    def test_scaling_expected_impact(self):
        rule = ScalingOpportunityRule()
        signals = make_signals(trend="improving")
        metrics = make_metrics(roas=1.5, ctr=0.02, spend=200, revenue=300)
        result = rule.detect(signals, metrics)
        assert len(result) == 1
        assert result[0].expected_impact.spend_change > 0

    def test_scaling_stable_trend(self):
        rule = ScalingOpportunityRule()
        signals = make_signals(trend="stable")
        metrics = make_metrics(roas=1.5, ctr=0.02, spend=200)
        result = rule.detect(signals, metrics)
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════
# Test: BudgetOptimizationRule
# ═══════════════════════════════════════════════════════════════


class TestBudgetOptimizationRule:
    def test_no_winner_returns_empty(self):
        rule = BudgetOptimizationRule(winner_roas=1.5)
        signals = make_signals()
        metrics = make_metrics(roas=1.1, spend=200)
        predictions = make_predictions(idle_budget_ratio=0.20)
        result = rule.detect(signals, metrics, predictions)
        assert result == []

    def test_no_idle_budget_returns_empty(self):
        rule = BudgetOptimizationRule()
        signals = make_signals()
        metrics = make_metrics(roas=1.6, spend=200)
        predictions = make_predictions(idle_budget_ratio=0.05)
        result = rule.detect(signals, metrics, predictions)
        assert result == []

    def test_budget_redistribution_detected(self):
        rule = BudgetOptimizationRule()
        signals = make_signals()
        metrics = make_metrics(roas=1.6, spend=200, revenue=320)
        predictions = make_predictions(idle_budget_ratio=0.20)
        result = rule.detect(signals, metrics, predictions)
        assert len(result) == 1
        opp = result[0]
        assert opp.opportunity_type == OpportunityType.BUDGET_REDISTRIBUTION
        assert "Budget redistribution" in opp.reason

    def test_budget_no_predictions_returns_empty(self):
        rule = BudgetOptimizationRule()
        signals = make_signals()
        metrics = make_metrics(roas=1.6, spend=200)
        result = rule.detect(signals, metrics, None)
        assert result == []


# ═══════════════════════════════════════════════════════════════
# Test: MonetizationOptimizationRule
# ═══════════════════════════════════════════════════════════════


class TestMonetizationOptimizationRule:
    def test_no_predictions_returns_empty(self):
        rule = MonetizationOptimizationRule()
        signals = make_signals()
        metrics = make_metrics()
        result = rule.detect(signals, metrics, None)
        assert result == []

    def test_insufficient_conditions_returns_empty(self):
        rule = MonetizationOptimizationRule()
        signals = make_signals()
        metrics = make_metrics(revenue=1000)
        predictions = make_predictions(payer_rate_change=0.10, ltv_change=0.02, arppu_change=0.03)
        result = rule.detect(signals, metrics, predictions)
        assert result == []

    def test_monetization_opportunity_detected(self):
        rule = MonetizationOptimizationRule()
        signals = make_signals()
        metrics = make_metrics(revenue=1000, spend=500)
        predictions = make_predictions(payer_rate_change=0.08, ltv_change=0.15, arppu_change=0.12)
        result = rule.detect(signals, metrics, predictions)
        assert len(result) == 1
        opp = result[0]
        assert opp.opportunity_type == OpportunityType.MONETIZATION_OPTIMIZATION
        assert "Monetization optimization" in opp.reason

    def test_monetization_custom_thresholds(self):
        rule = MonetizationOptimizationRule(payer_rate_increase=0.02, ltv_increase=0.05)
        signals = make_signals()
        metrics = make_metrics(revenue=1000)
        predictions = make_predictions(payer_rate_change=0.03, ltv_change=0.06, arppu_change=0.01)
        result = rule.detect(signals, metrics, predictions)
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════
# Test: AudienceExpansionRule
# ═══════════════════════════════════════════════════════════════


class TestAudienceExpansionRule:
    def test_roas_below_min_returns_empty(self):
        rule = AudienceExpansionRule(min_roas=1.0)
        signals = make_signals(trend="stable")
        metrics = make_metrics(roas=0.7, spend=200)
        result = rule.detect(signals, metrics)
        assert result == []

    def test_spend_below_min_returns_empty(self):
        rule = AudienceExpansionRule(min_spend=200)
        signals = make_signals(trend="stable")
        metrics = make_metrics(roas=1.2, spend=50)
        result = rule.detect(signals, metrics)
        assert result == []

    def test_fatigue_blocks_expansion(self):
        rule = AudienceExpansionRule()
        signals = make_signals(fatigue_detected=True, trend="stable")
        metrics = make_metrics(roas=1.2, spend=200)
        result = rule.detect(signals, metrics)
        assert result == []

    def test_declining_trend_blocks_expansion(self):
        rule = AudienceExpansionRule()
        signals = make_signals(trend="declining")
        metrics = make_metrics(roas=1.2, spend=200)
        result = rule.detect(signals, metrics)
        assert result == []

    def test_audience_expansion_detected(self):
        rule = AudienceExpansionRule()
        signals = make_signals(trend="stable")
        metrics = make_metrics(roas=1.2, spend=200, revenue=240)
        result = rule.detect(signals, metrics)
        assert len(result) == 1
        opp = result[0]
        assert opp.opportunity_type == OpportunityType.AUDIENCE_EXPANSION
        assert "Audience expansion" in opp.reason

    def test_lookalike_boosts_confidence(self):
        rule = AudienceExpansionRule()
        signals = make_signals(trend="stable")
        metrics = make_metrics(roas=1.2, spend=200)
        predictions = make_predictions(lookalike_ready=True)
        result = rule.detect(signals, metrics, predictions)
        assert len(result) == 1
        assert result[0].confidence >= 0.6


# ═══════════════════════════════════════════════════════════════
# Test: RiskMitigationRule
# ═══════════════════════════════════════════════════════════════


class TestRiskMitigationRule:
    def test_no_anomaly_returns_empty(self):
        rule = RiskMitigationRule()
        signals = make_signals(anomaly_detected=False)
        metrics = make_metrics(roas=0.3, spend=200, revenue=60)
        predictions = make_predictions(roas_crash=0.50, spend_spike_ratio=2.5)
        result = rule.detect(signals, metrics, predictions)
        assert result == []

    def test_risk_mitigation_detected_roas_crash(self):
        rule = RiskMitigationRule()
        signals = make_signals(anomaly_detected=True)
        metrics = make_metrics(roas=0.2, spend=200, revenue=40)
        predictions = make_predictions(roas_crash=0.60, spend_spike_ratio=1.0)
        result = rule.detect(signals, metrics, predictions)
        assert len(result) == 1
        opp = result[0]
        assert opp.opportunity_type == OpportunityType.RISK_MITIGATION
        assert "Risk mitigation" in opp.reason
        assert opp.urgency > 0.3

    def test_risk_mitigation_detected_spend_spike(self):
        rule = RiskMitigationRule()
        signals = make_signals(anomaly_detected=True)
        metrics = make_metrics(roas=0.8, spend=500, revenue=400)
        predictions = make_predictions(roas_crash=0.10, spend_spike_ratio=3.0)
        result = rule.detect(signals, metrics, predictions)
        assert len(result) == 1

    def test_risk_below_thresholds_returns_empty(self):
        rule = RiskMitigationRule()
        signals = make_signals(anomaly_detected=True)
        metrics = make_metrics(roas=0.9, spend=100)
        predictions = make_predictions(roas_crash=0.10, spend_spike_ratio=1.2)
        result = rule.detect(signals, metrics, predictions)
        assert result == []

    def test_risk_priority_is_critical_or_high(self):
        rule = RiskMitigationRule()
        signals = make_signals(anomaly_detected=True)
        metrics = make_metrics(roas=0.1, spend=500, revenue=50)
        predictions = make_predictions(roas_crash=0.80, spend_spike_ratio=3.0)
        result = rule.detect(signals, metrics, predictions)
        assert len(result) == 1
        assert result[0].priority in {DecisionPriority.CRITICAL, DecisionPriority.HIGH}


# ═══════════════════════════════════════════════════════════════
# Test: ExperimentLaunchRule
# ═══════════════════════════════════════════════════════════════


class TestExperimentLaunchRule:
    def test_no_new_dna_or_audience_returns_empty(self):
        rule = ExperimentLaunchRule()
        signals = make_signals(trend="stable")
        metrics = make_metrics()
        result = rule.detect(signals, metrics, None)
        assert result == []

    def test_experiment_with_new_dna(self):
        rule = ExperimentLaunchRule()
        signals = make_signals(trend="stable")
        metrics = make_metrics()
        predictions = make_predictions(new_dna_available=True)
        result = rule.detect(signals, metrics, predictions)
        assert len(result) == 1
        opp = result[0]
        assert opp.opportunity_type == OpportunityType.EXPERIMENT_LAUNCH
        assert "new DNA" in opp.reason

    def test_experiment_with_new_audience(self):
        rule = ExperimentLaunchRule()
        signals = make_signals(trend="stable")
        metrics = make_metrics()
        predictions = make_predictions(new_audience_available=True)
        result = rule.detect(signals, metrics, predictions)
        assert len(result) == 1
        assert "new audience" in result[0].reason

    def test_declining_trend_blocks_experiment(self):
        rule = ExperimentLaunchRule()
        signals = make_signals(trend="declining")
        metrics = make_metrics()
        predictions = make_predictions(new_dna_available=True)
        result = rule.detect(signals, metrics, predictions)
        assert result == []

    def test_experiment_low_priority(self):
        rule = ExperimentLaunchRule()
        signals = make_signals(trend="stable")
        metrics = make_metrics()
        predictions = make_predictions(new_dna_available=True)
        result = rule.detect(signals, metrics, predictions)
        assert len(result) == 1
        assert result[0].priority == DecisionPriority.LOW


# ═══════════════════════════════════════════════════════════════
# Test: RuleEngine
# ═══════════════════════════════════════════════════════════════


class TestRuleEngine:
    def test_register_single_rule(self):
        engine = RuleEngine()
        engine.register(CreativeFatigueRule())
        assert engine.rule_count == 1

    def test_register_defaults(self):
        engine = RuleEngine()
        engine.register_defaults()
        assert engine.rule_count == 7

    def test_detect_multiple_rules(self):
        engine = RuleEngine()
        engine.register_defaults()
        signals = make_signals(fatigue_detected=True, trend="improving")
        metrics = make_metrics(roas=1.5, ctr=0.02, frequency=4.0, spend=300, revenue=450)
        predictions = make_predictions(ctr_decay=0.30, roas_decay=0.15, fatigue_probability=0.85)
        result = engine.detect(signals, metrics, predictions)
        assert len(result) >= 2  # fatigue + scaling at least

    def test_detect_empty_signals(self):
        engine = RuleEngine()
        engine.register_defaults()
        signals = make_signals()
        metrics = make_metrics()
        result = engine.detect(signals, metrics)
        assert result == []

    def test_get_rule_names(self):
        engine = RuleEngine()
        engine.register(CreativeFatigueRule())
        engine.register(ScalingOpportunityRule())
        names = engine.get_rule_names()
        assert "creative_fatigue" in names
        assert "scaling_opportunity" in names

    def test_clear_rules(self):
        engine = RuleEngine()
        engine.register_defaults()
        assert engine.rule_count == 7
        engine.clear()
        assert engine.rule_count == 0

    def test_rule_error_does_not_break_others(self):
        class BrokenRule(OpportunityRule):
            name = "broken"
            def detect(self, signals, metrics, predictions=None):
                raise RuntimeError("broken")

        engine = RuleEngine()
        engine.register(CreativeFatigueRule())
        engine.register(BrokenRule())
        signals = make_signals(fatigue_detected=True)
        metrics = make_metrics(ctr=0.005, frequency=4.0, roas=0.7)
        predictions = make_predictions(ctr_decay=0.35, roas_decay=0.15, fatigue_probability=0.85)
        result = engine.detect(signals, metrics, predictions)
        assert len(result) == 1  # only fatigue rule succeeded


# ═══════════════════════════════════════════════════════════════
# Test: OpportunityRanker
# ═══════════════════════════════════════════════════════════════


class TestOpportunityRanker:
    def _make_opp(self, impact=0.5, confidence=0.6, urgency=0.4, opp_type=OpportunityType.CREATIVE_SCALE):
        opp = GrowthOpportunity(
            opportunity_type=opp_type,
            impact_score=impact,
            confidence=confidence,
            urgency=urgency,
            reason="test",
            recommended_action="test_action",
        )
        opp.compute_priority()
        return opp

    def test_rank_empty_list(self):
        ranker = OpportunityRanker()
        result = ranker.rank([])
        assert result == []

    def test_rank_single_opportunity(self):
        ranker = OpportunityRanker()
        opp = self._make_opp()
        result = ranker.rank([opp])
        assert len(result) == 1
        assert "rank_score" in result[0].metadata

    def test_rank_sorts_by_score(self):
        ranker = OpportunityRanker()
        high = self._make_opp(impact=0.9, confidence=0.9, urgency=0.9)
        low = self._make_opp(impact=0.2, confidence=0.2, urgency=0.1)
        result = ranker.rank([low, high])
        assert result[0].impact_score > result[1].impact_score

    def test_rank_top_n(self):
        ranker = OpportunityRanker()
        opps = [self._make_opp(impact=i * 0.1, confidence=0.5, urgency=0.3) for i in range(10)]
        result = ranker.rank(opps, top_n=3)
        assert len(result) == 3

    def test_rank_top_n_zero_returns_all(self):
        ranker = OpportunityRanker()
        opps = [self._make_opp() for _ in range(5)]
        result = ranker.rank(opps, top_n=0)
        assert len(result) == 5

    def test_memory_boost_with_strategies(self):
        ranker = OpportunityRanker()
        opp = self._make_opp()
        memory = MemoryContext(recommended_strategies=["s1", "s2"])
        boost = ranker._compute_memory_boost(opp, memory)
        assert boost > 0

    def test_memory_boost_with_patterns(self):
        ranker = OpportunityRanker()
        opp = self._make_opp()
        memory = MemoryContext(matched_patterns=["p1", "p2"])
        boost = ranker._compute_memory_boost(opp, memory)
        assert boost > 0

    def test_memory_boost_with_failures(self):
        ranker = OpportunityRanker()
        opp = self._make_opp()
        memory = MemoryContext(relevant_failures=["f1", "f2", "f3", "f4"])
        boost = ranker._compute_memory_boost(opp, memory)
        assert boost < 0

    def test_memory_boost_with_historical_success(self):
        ranker = OpportunityRanker()
        opp = self._make_opp()
        memory = MemoryContext(historical_success_rate=0.8)
        boost = ranker._compute_memory_boost(opp, memory)
        assert boost > 0

    def test_memory_boost_no_context(self):
        ranker = OpportunityRanker()
        opp = self._make_opp()
        boost = ranker._compute_memory_boost(opp, None)
        assert boost == 0.0

    def test_memory_boost_clamped(self):
        ranker = OpportunityRanker()
        opp = self._make_opp()
        memory = MemoryContext(
            recommended_strategies=["s1", "s2", "s3", "s4", "s5"],
            matched_patterns=["p1", "p2", "p3", "p4", "p5"],
        )
        boost = ranker._compute_memory_boost(opp, memory)
        assert boost <= ranker.MAX_MEMORY_BOOST

    def test_get_top(self):
        ranker = OpportunityRanker()
        opps = [self._make_opp(impact=i * 0.1) for i in range(5)]
        top = ranker.get_top(opps, n=3)
        assert len(top) == 3

    def test_get_critical_only(self):
        ranker = OpportunityRanker()
        critical = self._make_opp(impact=0.9, urgency=0.9)
        low = self._make_opp(impact=0.1, urgency=0.1)
        critical.compute_priority()
        low.compute_priority()
        result = ranker.get_critical_only([critical, low])
        assert len(result) == 1

    def test_get_actionable_only(self):
        ranker = OpportunityRanker()
        actionable = self._make_opp(impact=0.8, confidence=0.8)
        not_actionable = self._make_opp(impact=0.1, confidence=0.1)
        result = ranker.get_actionable_only([actionable, not_actionable])
        assert len(result) == 1

    def test_rank_with_memory_empty_opportunities(self):
        ranker = OpportunityRanker()
        result = ranker.rank_with_memory([])
        assert result == []

    def test_rank_with_memory_preserves_all(self):
        ranker = OpportunityRanker()
        opps = [self._make_opp(impact=i * 0.1) for i in range(5)]
        result = ranker.rank_with_memory(opps, top_n=0)
        assert len(result) == 5

    def test_score_formula(self):
        ranker = OpportunityRanker()
        opp = GrowthOpportunity(impact_score=0.5, confidence=0.6, urgency=0.4)
        score = ranker._compute_score(opp, 0.0)
        expected = 0.5 * 0.4 + 0.6 * 0.3 + 0.4 * 0.2
        assert score == pytest.approx(expected, 0.001)


# ═══════════════════════════════════════════════════════════════
# Test: OpportunityIntelligenceEngine
# ═══════════════════════════════════════════════════════════════


class TestOpportunityIntelligenceEngine:
    def test_engine_creation(self):
        engine = OpportunityIntelligenceEngine()
        assert engine.rule_engine.rule_count == 7
        assert engine.analysis_count == 0

    def test_analyze_fatigue_scenario(self):
        engine = OpportunityIntelligenceEngine()
        signals = make_signals(fatigue_detected=True, trend="declining")
        metrics = make_metrics(roas=0.7, ctr=0.005, frequency=5.0, spend=400, revenue=280)
        predictions = make_predictions(ctr_decay=0.35, roas_decay=0.15, fatigue_probability=0.87)
        result = engine.analyze(signals, metrics, predictions)
        assert len(result) >= 1
        types = [o.opportunity_type for o in result]
        assert OpportunityType.CREATIVE_REFRESH in types

    def test_analyze_scaling_scenario(self):
        engine = OpportunityIntelligenceEngine()
        signals = make_signals(trend="improving")
        metrics = make_metrics(roas=1.8, ctr=0.025, spend=300, revenue=540)
        result = engine.analyze(signals, metrics)
        assert len(result) >= 1
        types = [o.opportunity_type for o in result]
        assert OpportunityType.CREATIVE_SCALE in types

    def test_analyze_empty_returns_empty_list(self):
        engine = OpportunityIntelligenceEngine()
        signals = make_signals()
        metrics = make_metrics()
        result = engine.analyze(signals, metrics)
        assert result == []

    def test_analyze_top_n_limit(self):
        engine = OpportunityIntelligenceEngine()
        signals = make_signals(fatigue_detected=True, trend="improving", anomaly_detected=True)
        metrics = make_metrics(roas=1.5, ctr=0.02, frequency=4.0, spend=300, revenue=450)
        predictions = make_predictions(ctr_decay=0.30, roas_decay=0.15, fatigue_probability=0.85, roas_crash=0.40, spend_spike_ratio=2.5)
        result = engine.analyze(signals, metrics, predictions, top_n=2)
        assert len(result) <= 2

    def test_analyze_results_are_sorted(self):
        engine = OpportunityIntelligenceEngine()
        signals = make_signals(fatigue_detected=True, trend="improving", anomaly_detected=True)
        metrics = make_metrics(roas=1.5, ctr=0.02, frequency=4.0, spend=300, revenue=450)
        predictions = make_predictions(ctr_decay=0.30, roas_decay=0.15, fatigue_probability=0.85, roas_crash=0.40, spend_spike_ratio=2.5)
        result = engine.analyze(signals, metrics, predictions)
        if len(result) >= 2:
            scores = [o.metadata.get("rank_score", 0) for o in result]
            assert scores == sorted(scores, reverse=True)

    def test_analyze_increments_count(self):
        engine = OpportunityIntelligenceEngine()
        signals = make_signals(fatigue_detected=True)
        metrics = make_metrics(ctr=0.005, frequency=4.0, roas=0.7)
        predictions = make_predictions(ctr_decay=0.35, roas_decay=0.15, fatigue_probability=0.85)
        engine.analyze(signals, metrics, predictions)
        engine.analyze(signals, metrics, predictions)
        assert engine.analysis_count == 2

    def test_analyze_quick(self):
        engine = OpportunityIntelligenceEngine()
        result = engine.analyze_quick(
            fatigue_detected=True,
            roas=0.7, ctr=0.005, frequency=5.0, spend=400, revenue=280,
            predictions=make_predictions(ctr_decay=0.35, fatigue_probability=0.87),
            top_n=3,
        )
        assert len(result) >= 1

    def test_get_top_opportunities(self):
        engine = OpportunityIntelligenceEngine()
        signals = make_signals(fatigue_detected=True, trend="improving")
        metrics = make_metrics(roas=1.5, ctr=0.02, frequency=4.0, spend=300, revenue=450)
        predictions = make_predictions(ctr_decay=0.30, roas_decay=0.15, fatigue_probability=0.85)
        opps = engine.analyze(signals, metrics, predictions)
        top = engine.get_top_opportunities(opps, n=1)
        assert len(top) <= 1

    def test_get_critical_opportunities(self):
        engine = OpportunityIntelligenceEngine()
        signals = make_signals(anomaly_detected=True)
        metrics = make_metrics(roas=0.2, spend=200, revenue=40)
        predictions = make_predictions(roas_crash=0.60, spend_spike_ratio=3.0)
        opps = engine.analyze(signals, metrics, predictions)
        critical = engine.get_critical_opportunities(opps)
        assert len(critical) >= 1

    def test_get_actionable_opportunities(self):
        engine = OpportunityIntelligenceEngine()
        signals = make_signals(fatigue_detected=True)
        metrics = make_metrics(ctr=0.005, frequency=4.0, roas=0.7)
        predictions = make_predictions(ctr_decay=0.35, roas_decay=0.15, fatigue_probability=0.85)
        opps = engine.analyze(signals, metrics, predictions)
        actionable = engine.get_actionable_opportunities(opps)
        assert len(actionable) >= 1

    def test_analyze_with_memory_no_memory_connected(self):
        engine = OpportunityIntelligenceEngine()
        signals = make_signals(fatigue_detected=True)
        metrics = make_metrics(ctr=0.005, frequency=4.0, roas=0.7)
        predictions = make_predictions(ctr_decay=0.35, fatigue_probability=0.85)
        result = engine.analyze_with_memory(signals, metrics, predictions)
        assert len(result) >= 1

    def test_analyze_with_memory_context(self):
        engine = OpportunityIntelligenceEngine()
        signals = make_signals(fatigue_detected=True)
        metrics = make_metrics(ctr=0.005, frequency=4.0, roas=0.7)
        predictions = make_predictions(ctr_decay=0.35, fatigue_probability=0.87)
        memory = MemoryContext(
            matched_patterns=["p_creative_refresh"],
            recommended_strategies=["s_creative_revival"],
            historical_success_rate=0.8,
        )
        result = engine.analyze(signals, metrics, predictions, memory_context=memory)
        assert len(result) >= 1
        assert "memory_boost" in result[0].metadata

    def test_analyze_budget_scenario(self):
        engine = OpportunityIntelligenceEngine()
        signals = make_signals(trend="stable")
        metrics = make_metrics(roas=1.6, spend=200, revenue=320)
        predictions = make_predictions(idle_budget_ratio=0.25)
        result = engine.analyze(signals, metrics, predictions)
        types = [o.opportunity_type for o in result]
        assert OpportunityType.BUDGET_REDISTRIBUTION in types

    def test_analyze_monetization_scenario(self):
        engine = OpportunityIntelligenceEngine()
        signals = make_signals()
        metrics = make_metrics(revenue=1000, spend=500)
        predictions = make_predictions(payer_rate_change=0.10, ltv_change=0.15, arppu_change=0.12)
        result = engine.analyze(signals, metrics, predictions)
        types = [o.opportunity_type for o in result]
        assert OpportunityType.MONETIZATION_OPTIMIZATION in types


# ═══════════════════════════════════════════════════════════════
# Test: Integration
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    def test_full_pipeline_fatigue_to_opportunity(self):
        """完整链路: Reality Signal → Rules → Rank → Opportunities."""
        engine = OpportunityIntelligenceEngine()

        # 模拟 Reality Insight 输入
        signals = SignalSummary(
            active_signals=["creative_fatigue", "ctr_drop"],
            fatigue_detected=True,
            anomaly_detected=False,
            prediction={"fatigue_probability": 0.87},
            trend="declining",
        )
        metrics = CurrentMetrics(
            spend=500.0, revenue=600.0, roas=1.2,
            ctr=0.008, frequency=4.5, impressions=50000, clicks=400,
        )
        predictions = {
            "ctr_decay": 0.35,
            "roas_decay": 0.15,
            "fatigue_probability": 0.87,
        }

        # Step 1: Analyze
        opportunities = engine.analyze(signals, metrics, predictions, top_n=5)

        # Step 2: Verify
        assert len(opportunities) >= 1
        top = opportunities[0]
        assert top.opportunity_type == OpportunityType.CREATIVE_REFRESH
        assert "rank_score" in top.metadata
        assert top.metadata["rank_score"] > 0

    def test_full_pipeline_scaling_to_opportunity(self):
        """完整链路: 放量场景."""
        engine = OpportunityIntelligenceEngine()

        signals = SignalSummary(
            active_signals=["roas_above_target"],
            trend="improving",
        )
        metrics = CurrentMetrics(
            spend=500.0, revenue=1000.0, roas=2.0,
            ctr=0.03, frequency=2.0, impressions=60000, clicks=1800,
        )

        opportunities = engine.analyze(signals, metrics, top_n=5)
        assert len(opportunities) >= 1
        types = [o.opportunity_type for o in opportunities]
        assert OpportunityType.CREATIVE_SCALE in types

    def test_full_pipeline_risk_to_opportunity(self):
        """完整链路: 风险场景."""
        engine = OpportunityIntelligenceEngine()

        signals = SignalSummary(
            active_signals=["roas_crash", "spend_spike"],
            anomaly_detected=True,
            trend="declining",
        )
        metrics = CurrentMetrics(
            spend=1000.0, revenue=400.0, roas=0.4,
            ctr=0.003, frequency=2.0,
        )
        predictions = {
            "roas_crash": 0.60,
            "spend_spike_ratio": 3.0,
        }

        opportunities = engine.analyze(signals, metrics, predictions, top_n=5)
        assert len(opportunities) >= 1
        types = [o.opportunity_type for o in opportunities]
        assert OpportunityType.RISK_MITIGATION in types

    def test_multi_opportunity_ranking(self):
        """多机会场景: 按优先级排序."""
        engine = OpportunityIntelligenceEngine()

        signals = SignalSummary(
            active_signals=["creative_fatigue", "roas_crash"],
            fatigue_detected=True,
            anomaly_detected=True,
            trend="declining",
        )
        metrics = CurrentMetrics(
            spend=500.0, revenue=300.0, roas=0.6,
            ctr=0.005, frequency=5.0,
        )
        predictions = {
            "ctr_decay": 0.40,
            "roas_decay": 0.20,
            "fatigue_probability": 0.90,
            "roas_crash": 0.50,
            "spend_spike_ratio": 2.5,
        }

        opportunities = engine.analyze(signals, metrics, predictions, top_n=10)
        assert len(opportunities) >= 2

        # 风险缓解应该排在前面 (更高紧急性)
        high_priority = [o for o in opportunities if o.is_high_priority]
        assert len(high_priority) >= 1

    def test_memory_context_enhancement(self):
        """Memory 上下文增强."""
        engine = OpportunityIntelligenceEngine()

        signals = make_signals(fatigue_detected=True, trend="declining")
        metrics = make_metrics(roas=0.7, ctr=0.005, frequency=5.0, spend=400, revenue=280)
        predictions = make_predictions(ctr_decay=0.35, fatigue_probability=0.87)

        # 无 Memory
        no_memory = engine.analyze(signals, metrics, predictions, top_n=5)

        # 有 Memory
        memory = MemoryContext(
            matched_patterns=["p_creative_refresh"],
            recommended_strategies=["s_creative_revival"],
            historical_success_rate=0.85,
        )
        with_memory = engine.analyze(signals, metrics, predictions, memory_context=memory, top_n=5)

        assert len(no_memory) >= 1
        assert len(with_memory) >= 1
        # Memory-enhanced 应该有更高的 rank_score
        assert with_memory[0].metadata["memory_boost"] > no_memory[0].metadata["memory_boost"]

    def test_rule_engine_isolation(self):
        """规则引擎隔离: 各规则独立运行."""
        engine = RuleEngine()
        engine.register_defaults()

        # 仅疲劳信号
        signals = make_signals(fatigue_detected=True)
        metrics = make_metrics(ctr=0.005, frequency=4.0, roas=0.7)
        predictions = make_predictions(ctr_decay=0.35, fatigue_probability=0.85)
        result = engine.detect(signals, metrics, predictions)
        types = [o.opportunity_type for o in result]
        assert OpportunityType.CREATIVE_REFRESH in types
        # 不应该有放量机会 (无趋势)
        assert OpportunityType.CREATIVE_SCALE not in types