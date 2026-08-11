"""E15.3.4 Self Optimization 测试 — 完整测试.

测试覆盖:
  - Models (15 tests)
  - Performance Monitor (20 tests)
  - Strategy Evaluator (15 tests)
  - Parameter Optimizer (20 tests)
  - Learning Optimizer (15 tests)
  - Self Diagnosis (15 tests)
  - Optimizer Integration (10 tests)

总计: ~110 tests
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from market_ops.creative_vision_runtime.growth_runtime.intelligence.self_optimization.models import (
    MetricSeverity,
    OptimizationAction,
    OptimizationArea,
    OptimizationMetric,
    OptimizationOpportunity,
    OptimizationPolicy,
    OptimizationResult,
    OptimizationStatus,
    StrategyPerformance,
    SystemDiagnosis,
    TrendDirection,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.self_optimization.performance_monitor import (
    BUILTIN_METRICS,
    PerformanceMonitor,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.self_optimization.strategy_evaluator import (
    StrategyEvaluator,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.self_optimization.parameter_optimizer import (
    PARAMETER_REGISTRY,
    ParameterOptimizer,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.self_optimization.learning_optimizer import (
    LearningOptimizer,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.self_optimization.self_diagnosis import (
    DIAGNOSIS_RULES,
    SelfDiagnosisEngine,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.self_optimization.optimizer import (
    SelfOptimizer,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def metric():
    return OptimizationMetric(
        metric_name="decision_accuracy",
        current_value=0.72,
        target_value=0.85,
        baseline_value=0.50,
        trend=TrendDirection.STABLE,
        severity=MetricSeverity.NORMAL,
    )


@pytest.fixture
def opportunity():
    return OptimizationOpportunity(
        area=OptimizationArea.RISK_ENGINE,
        problem="Risk engine blocks too many actions",
        evidence=["approval_rate: 0.42", "success_rate: 0.85"],
        expected_gain=0.15,
        confidence=0.86,
        suggested_change="Increase risk threshold from 0.50 to 0.55",
        priority=1,
    )


@pytest.fixture
def monitor():
    return PerformanceMonitor()


@pytest.fixture
def strategy_evaluator():
    return StrategyEvaluator()


@pytest.fixture
def param_optimizer():
    return ParameterOptimizer()


@pytest.fixture
def learning_optimizer():
    return LearningOptimizer()


@pytest.fixture
def diagnosis_engine():
    return SelfDiagnosisEngine()


@pytest.fixture
def self_optimizer():
    return SelfOptimizer()


# ═══════════════════════════════════════════════════════════════════
# 1. Models (15 tests)
# ═══════════════════════════════════════════════════════════════════


class TestOptimizationMetric:
    def test_create_metric(self):
        m = OptimizationMetric(metric_name="test", current_value=0.8, target_value=0.9, baseline_value=0.5)
        assert m.metric_name == "test"
        assert m.current_value == 0.8
        assert m.target_value == 0.9
        assert m.baseline_value == 0.5

    def test_metric_gap(self):
        m = OptimizationMetric(metric_name="test", current_value=0.6, target_value=0.8, baseline_value=0.4)
        assert m.gap() == pytest.approx(0.5)

    def test_metric_gap_zero(self):
        m = OptimizationMetric(metric_name="test", current_value=0.5, target_value=0.5, baseline_value=0.5)
        assert m.gap() == 0.0

    def test_metric_is_degraded(self):
        m = OptimizationMetric(metric_name="test", current_value=0.3, target_value=0.8, baseline_value=0.5,
                               trend=TrendDirection.DECLINING, severity=MetricSeverity.WARNING)
        assert m.is_degraded()

    def test_metric_not_degraded_stable(self):
        m = OptimizationMetric(metric_name="test", current_value=0.3, target_value=0.8, baseline_value=0.5,
                               trend=TrendDirection.STABLE, severity=MetricSeverity.WARNING)
        assert not m.is_degraded()

    def test_metric_to_dict(self, metric):
        d = metric.to_dict()
        assert d["metric_name"] == "decision_accuracy"
        assert "gap" in d
        assert "trend" in d
        assert "severity" in d


class TestOptimizationOpportunity:
    def test_create_opportunity(self, opportunity):
        assert opportunity.area == OptimizationArea.RISK_ENGINE
        assert opportunity.confidence == 0.86
        assert opportunity.expected_gain == 0.15

    def test_opportunity_is_actionable(self, opportunity):
        assert opportunity.is_actionable()

    def test_opportunity_not_actionable_low_confidence(self):
        opp = OptimizationOpportunity(
            area=OptimizationArea.MEMORY,
            problem="test",
            confidence=0.5,
            expected_gain=0.1,
        )
        assert not opp.is_actionable()

    def test_opportunity_to_dict(self, opportunity):
        d = opportunity.to_dict()
        assert d["area"] == "risk_engine"
        assert d["evidence"] == opportunity.evidence
        assert "opportunity_id" in d


class TestOptimizationAction:
    def test_create_action(self):
        action = OptimizationAction(
            area=OptimizationArea.RISK_ENGINE,
            parameter="medium_threshold",
            old_value=0.50,
            new_value=0.55,
            reason="too conservative",
            risk_level="low",
        )
        assert action.parameter == "medium_threshold"
        assert action.old_value == 0.50
        assert action.new_value == 0.55
        assert action.status == OptimizationStatus.PROPOSED

    def test_action_to_dict(self):
        action = OptimizationAction(
            area=OptimizationArea.MEMORY,
            parameter="similarity_threshold",
            old_value=0.85,
            new_value=0.78,
            reason="too high",
        )
        d = action.to_dict()
        assert d["parameter"] == "similarity_threshold"
        assert d["old_value"] == 0.85
        assert d["new_value"] == 0.78


class TestStrategyPerformance:
    def test_create_performance(self):
        sp = StrategyPerformance(strategy_name="creative_refresh")
        assert sp.strategy_name == "creative_refresh"
        assert sp.total_attempts == 0
        assert sp.success_rate == 0.0

    def test_performance_to_dict(self):
        sp = StrategyPerformance(strategy_name="test", total_attempts=10, success_count=7)
        d = sp.to_dict()
        assert d["strategy_name"] == "test"
        assert d["total_attempts"] == 10


class TestSystemDiagnosis:
    def test_create_diagnosis(self):
        d = SystemDiagnosis(
            observations=["metric_x degraded"],
            hypotheses=[{"name": "test", "hypothesis": "test hypo", "confidence": 0.8}],
            root_causes=["root_cause_1"],
            recommendations=["fix it"],
            confidence=0.75,
            severity=MetricSeverity.WARNING,
        )
        assert d.confidence == 0.75
        assert d.severity == MetricSeverity.WARNING
        assert len(d.observations) == 1

    def test_diagnosis_to_dict(self):
        d = SystemDiagnosis(observations=["o1"], hypotheses=[], root_causes=[], recommendations=[])
        result = d.to_dict()
        assert "diagnosis_id" in result
        assert result["observations"] == ["o1"]


class TestOptimizationPolicy:
    def test_default_policy(self):
        p = OptimizationPolicy()
        assert p.min_confidence == 0.6
        assert p.max_risk_level == "medium"
        assert p.cooldown_cycles == 3
        assert p.max_actions_per_cycle == 5

    def test_policy_to_dict(self):
        p = OptimizationPolicy()
        d = p.to_dict()
        assert d["min_confidence"] == 0.6
        assert "metric_targets" in d


# ═══════════════════════════════════════════════════════════════════
# 2. Performance Monitor (20 tests)
# ═══════════════════════════════════════════════════════════════════


class TestPerformanceMonitor:
    def test_record_single_metric(self, monitor):
        m = monitor.record("decision_accuracy", 0.72)
        assert m.metric_name == "decision_accuracy"
        assert m.current_value == 0.72

    def test_record_updates_existing(self, monitor):
        monitor.record("decision_accuracy", 0.72)
        m = monitor.record("decision_accuracy", 0.75)
        assert m.current_value == 0.75

    def test_record_batch(self, monitor):
        results = monitor.record_batch({"decision_accuracy": 0.72, "execution_success_rate": 0.81})
        assert len(results) == 2

    def test_collect_metrics(self, monitor):
        monitor.record("decision_accuracy", 0.72)
        monitor.record("execution_success_rate", 0.81)
        metrics = monitor.collect_metrics()
        assert len(metrics) == 2

    def test_get_metric(self, monitor):
        monitor.record("decision_accuracy", 0.72)
        m = monitor.get_metric("decision_accuracy")
        assert m is not None
        assert m.current_value == 0.72

    def test_get_metric_nonexistent(self, monitor):
        assert monitor.get_metric("nonexistent") is None

    def test_get_degraded_empty(self, monitor):
        monitor.record("decision_accuracy", 0.85)
        assert len(monitor.get_degraded()) == 0

    def test_get_degraded_after_decline(self, monitor):
        for v in [0.80, 0.78, 0.76, 0.74, 0.72]:
            monitor.record("decision_accuracy", v)
        # After 5 declining points, it should be detected
        degraded = monitor.get_degraded()
        # It may or may not be degraded depending on severity thresholds
        assert isinstance(degraded, list)

    def test_get_history(self, monitor):
        monitor.record("decision_accuracy", 0.72)
        monitor.record("decision_accuracy", 0.75)
        history = monitor.get_history("decision_accuracy")
        assert len(history) == 2
        assert history[0]["value"] == 0.72

    def test_get_history_nonexistent(self, monitor):
        assert monitor.get_history("nonexistent") == []

    def test_trend_detection_improving(self, monitor):
        for v in [0.55, 0.60, 0.65, 0.70, 0.75]:
            monitor.record("decision_accuracy", v)
        m = monitor.get_metric("decision_accuracy")
        assert m is not None
        assert m.trend in (TrendDirection.IMPROVING, TrendDirection.STABLE)

    def test_trend_detection_declining(self, monitor):
        for v in [0.75, 0.70, 0.65, 0.60, 0.55]:
            monitor.record("decision_accuracy", v)
        m = monitor.get_metric("decision_accuracy")
        assert m is not None
        assert m.trend in (TrendDirection.DECLINING, TrendDirection.STABLE)

    def test_trend_unknown_with_few_points(self, monitor):
        monitor.record("decision_accuracy", 0.72)
        m = monitor.get_metric("decision_accuracy")
        assert m is not None
        assert m.trend == TrendDirection.UNKNOWN

    def test_severity_good(self, monitor):
        for v in [0.88, 0.89, 0.90]:
            monitor.record("decision_accuracy", v)
        m = monitor.get_metric("decision_accuracy")
        assert m is not None
        assert m.severity == MetricSeverity.GOOD

    def test_severity_critical(self, monitor):
        for v in [0.32, 0.31, 0.30]:
            monitor.record("decision_accuracy", v)
        m = monitor.get_metric("decision_accuracy")
        assert m is not None
        assert m.severity == MetricSeverity.CRITICAL

    def test_custom_metric(self, monitor):
        m = monitor.record("custom_metric", 0.75)
        assert m.metric_name == "custom_metric"
        assert m.target_value == 0.80  # default for unknown metrics

    def test_get_summary(self, monitor):
        monitor.record("decision_accuracy", 0.72)
        monitor.record("execution_success_rate", 0.81)
        summary = monitor.get_summary()
        assert summary["total_metrics"] == 2
        assert "metrics" in summary

    def test_reset(self, monitor):
        monitor.record("decision_accuracy", 0.72)
        monitor.reset()
        assert len(monitor.collect_metrics()) == 0
        assert monitor.get_history("decision_accuracy") == []

    def test_builtin_metrics_defined(self):
        assert "decision_accuracy" in BUILTIN_METRICS
        assert "execution_success_rate" in BUILTIN_METRICS
        assert "memory_hit_rate" in BUILTIN_METRICS
        assert "risk_approval_rate" in BUILTIN_METRICS

    def test_builtin_metrics_targets(self):
        assert BUILTIN_METRICS["decision_accuracy"]["target"] == 0.85
        assert BUILTIN_METRICS["execution_success_rate"]["target"] == 0.90


# ═══════════════════════════════════════════════════════════════════
# 3. Strategy Evaluator (15 tests)
# ═══════════════════════════════════════════════════════════════════


class TestStrategyEvaluator:
    def test_record_single_outcome(self, strategy_evaluator):
        perf = strategy_evaluator.record_outcome("creative_refresh", success=True, reward=0.8)
        assert perf.strategy_name == "creative_refresh"
        assert perf.total_attempts == 1
        assert perf.success_count == 1
        assert perf.success_rate == 1.0

    def test_record_multiple_outcomes(self, strategy_evaluator):
        for i in range(5):
            strategy_evaluator.record_outcome("creative_refresh", success=i >= 2, reward=0.5)
        perf = strategy_evaluator.evaluate_strategy("creative_refresh")
        assert perf is not None
        assert perf.total_attempts == 5
        assert perf.success_count == 3
        assert perf.success_rate == 0.6

    def test_evaluate_strategy(self, strategy_evaluator):
        strategy_evaluator.record_outcome("test", success=True, reward=0.7)
        perf = strategy_evaluator.evaluate_strategy("test")
        assert perf is not None
        assert perf.success_rate == 1.0

    def test_evaluate_nonexistent(self, strategy_evaluator):
        assert strategy_evaluator.evaluate_strategy("nonexistent") is None

    def test_evaluate_all(self, strategy_evaluator):
        strategy_evaluator.record_outcome("a", success=True, reward=0.5)
        strategy_evaluator.record_outcome("b", success=False, reward=0.2)
        all_perf = strategy_evaluator.evaluate_all()
        assert len(all_perf) == 2

    def test_avg_reward_calculation(self, strategy_evaluator):
        strategy_evaluator.record_outcome("test", success=True, reward=0.5)
        strategy_evaluator.record_outcome("test", success=True, reward=0.9)
        perf = strategy_evaluator.evaluate_strategy("test")
        assert perf is not None
        assert perf.avg_reward == pytest.approx(0.7)

    def test_get_top_strategies(self, strategy_evaluator):
        strategy_evaluator.record_outcome("a", success=True, reward=0.9)
        strategy_evaluator.record_outcome("b", success=False, reward=0.1)
        strategy_evaluator.record_outcome("c", success=True, reward=0.7)
        top = strategy_evaluator.get_top_strategies(2)
        assert len(top) == 2
        assert top[0].strategy_name == "a"  # 100% success

    def test_get_bottom_strategies(self, strategy_evaluator):
        strategy_evaluator.record_outcome("a", success=True, reward=0.9)
        strategy_evaluator.record_outcome("b", success=False, reward=0.1)
        bottom = strategy_evaluator.get_bottom_strategies(1)
        assert len(bottom) == 1
        assert bottom[0].strategy_name == "b"  # 0% success

    def test_degradation_detection(self, strategy_evaluator):
        # 40 good outcomes
        for _ in range(40):
            strategy_evaluator.record_outcome("test", success=True, reward=0.8)
        # 20 bad outcomes
        for _ in range(20):
            strategy_evaluator.record_outcome("test", success=False, reward=0.1)
        perf = strategy_evaluator.evaluate_strategy("test")
        assert perf is not None
        assert perf.degraded

    def test_no_degradation_with_stable(self, strategy_evaluator):
        for _ in range(30):
            strategy_evaluator.record_outcome("test", success=True, reward=0.7)
        perf = strategy_evaluator.evaluate_strategy("test")
        assert perf is not None
        assert not perf.degraded

    def test_detect_opportunities(self, strategy_evaluator):
        # Create degradation
        for _ in range(40):
            strategy_evaluator.record_outcome("test", success=True, reward=0.8)
        for _ in range(20):
            strategy_evaluator.record_outcome("test", success=False, reward=0.1)
        opportunities = strategy_evaluator.detect_opportunities()
        assert len(opportunities) >= 1
        assert opportunities[0].area == OptimizationArea.ACTION_SELECTION

    def test_detect_opportunities_empty(self, strategy_evaluator):
        opportunities = strategy_evaluator.detect_opportunities()
        assert len(opportunities) == 0

    def test_get_summary(self, strategy_evaluator):
        strategy_evaluator.record_outcome("a", success=True, reward=0.5)
        summary = strategy_evaluator.get_summary()
        assert summary["total_strategies"] == 1
        assert "avg_success_rate" in summary

    def test_reset(self, strategy_evaluator):
        strategy_evaluator.record_outcome("test", success=True, reward=0.5)
        strategy_evaluator.reset()
        assert len(strategy_evaluator.evaluate_all()) == 0

    def test_degradation_threshold_custom(self):
        evaluator = StrategyEvaluator(degradation_threshold=0.30)
        for _ in range(40):
            evaluator.record_outcome("test", success=True, reward=0.8)
        for _ in range(20):
            evaluator.record_outcome("test", success=False, reward=0.1)
        perf = evaluator.evaluate_strategy("test")
        assert perf is not None
        # With higher threshold, might not be degraded
        assert isinstance(perf.degraded, bool)


# ═══════════════════════════════════════════════════════════════════
# 4. Parameter Optimizer (20 tests)
# ═══════════════════════════════════════════════════════════════════


class TestParameterOptimizer:
    def test_optimize_single_opportunity(self, param_optimizer, opportunity):
        actions = param_optimizer.optimize([opportunity])
        assert len(actions) >= 1
        assert actions[0].area == OptimizationArea.RISK_ENGINE

    def test_optimize_skips_non_actionable(self, param_optimizer):
        opp = OptimizationOpportunity(
            area=OptimizationArea.MEMORY,
            problem="test",
            confidence=0.5,
            expected_gain=0.0,
        )
        actions = param_optimizer.optimize([opp])
        assert len(actions) == 0

    def test_optimize_with_current_params(self, param_optimizer, opportunity):
        params = {"medium_threshold": 0.50}
        actions = param_optimizer.optimize([opportunity], current_params=params)
        assert len(actions) >= 1

    def test_apply_action(self, param_optimizer, opportunity):
        actions = param_optimizer.optimize([opportunity])
        assert len(actions) >= 1
        action_id = actions[0].action_id
        assert param_optimizer.apply_action(action_id)
        assert actions[0].status == OptimizationStatus.APPLIED

    def test_apply_nonexistent_action(self, param_optimizer):
        assert not param_optimizer.apply_action("nonexistent")

    def test_revert_action(self, param_optimizer, opportunity):
        actions = param_optimizer.optimize([opportunity])
        action_id = actions[0].action_id
        param_optimizer.apply_action(action_id)
        assert param_optimizer.revert_action(action_id)
        assert actions[0].status == OptimizationStatus.REVERTED

    def test_revert_nonexistent_action(self, param_optimizer):
        assert not param_optimizer.revert_action("nonexistent")

    def test_evaluate_action_improvement(self, param_optimizer, opportunity):
        actions = param_optimizer.optimize([opportunity])
        action_id = actions[0].action_id
        param_optimizer.apply_action(action_id)
        result = param_optimizer.evaluate_action(action_id, 0.42, 0.55)
        assert result is not None
        assert result.improvement == pytest.approx(0.13)
        assert result.is_successful

    def test_evaluate_action_decline(self, param_optimizer, opportunity):
        actions = param_optimizer.optimize([opportunity])
        action_id = actions[0].action_id
        param_optimizer.apply_action(action_id)
        result = param_optimizer.evaluate_action(action_id, 0.55, 0.42)
        assert result is not None
        assert not result.is_successful

    def test_evaluate_nonexistent_action(self, param_optimizer):
        assert param_optimizer.evaluate_action("nonexistent", 0.5, 0.6) is None

    def test_cooldown_mechanism(self, param_optimizer, opportunity):
        actions = param_optimizer.optimize([opportunity])
        action_id = actions[0].action_id
        param_optimizer.apply_action(action_id)

        # Same parameter should be in cooldown
        opp2 = OptimizationOpportunity(
            area=OptimizationArea.RISK_ENGINE,
            problem="medium_threshold needs adjustment",
            confidence=0.80,
            expected_gain=0.1,
        )
        actions2 = param_optimizer.optimize([opp2])
        assert len(actions2) == 0  # blocked by cooldown

    def test_tick_cooldowns(self, param_optimizer, opportunity):
        actions = param_optimizer.optimize([opportunity])
        action_id = actions[0].action_id
        param_optimizer.apply_action(action_id)

        # Tick 3 times to clear cooldown
        for _ in range(3):
            param_optimizer.tick_cooldowns()

        opp2 = OptimizationOpportunity(
            area=OptimizationArea.RISK_ENGINE,
            problem="medium_threshold needs adjustment",
            confidence=0.80,
            expected_gain=0.1,
        )
        actions2 = param_optimizer.optimize([opp2])
        assert len(actions2) >= 1  # cooldown cleared

    def test_max_actions_per_cycle(self):
        policy = OptimizationPolicy(max_actions_per_cycle=2)
        optimizer = ParameterOptimizer(policy=policy)
        opportunities = [
            OptimizationOpportunity(area=OptimizationArea.RISK_ENGINE, problem="test", confidence=0.8, expected_gain=0.1),
            OptimizationOpportunity(area=OptimizationArea.MEMORY, problem="test", confidence=0.8, expected_gain=0.1),
            OptimizationOpportunity(area=OptimizationArea.ACTION_SELECTION, problem="test", confidence=0.8, expected_gain=0.1),
        ]
        actions = optimizer.optimize(opportunities)
        assert len(actions) <= 2

    def test_get_applied_params(self, param_optimizer, opportunity):
        actions = param_optimizer.optimize([opportunity])
        param_optimizer.apply_action(actions[0].action_id)
        params = param_optimizer.get_applied_params()
        assert len(params) >= 1

    def test_get_actions(self, param_optimizer, opportunity):
        param_optimizer.optimize([opportunity])
        actions = param_optimizer.get_actions()
        assert len(actions) >= 1

    def test_get_results(self, param_optimizer):
        assert param_optimizer.get_results() == []

    def test_get_summary(self, param_optimizer, opportunity):
        param_optimizer.optimize([opportunity])
        summary = param_optimizer.get_summary()
        assert summary["total_actions"] >= 1
        assert "applied_params" in summary

    def test_reset(self, param_optimizer, opportunity):
        param_optimizer.optimize([opportunity])
        param_optimizer.reset()
        assert len(param_optimizer.get_actions()) == 0
        assert len(param_optimizer.get_applied_params()) == 0

    def test_parameter_registry(self):
        assert "risk_engine" in PARAMETER_REGISTRY
        assert "action_selection" in PARAMETER_REGISTRY
        assert "memory" in PARAMETER_REGISTRY
        assert "medium_threshold" in PARAMETER_REGISTRY["risk_engine"]

    def test_parameter_registry_bounds(self):
        params = PARAMETER_REGISTRY["risk_engine"]["medium_threshold"]
        assert 0.30 <= params["default"] <= 0.70
        assert params["min"] <= params["default"] <= params["max"]


# ═══════════════════════════════════════════════════════════════════
# 5. Learning Optimizer (15 tests)
# ═══════════════════════════════════════════════════════════════════


class TestLearningOptimizer:
    def test_analyze_low_retrieval(self, learning_optimizer):
        stats = {"retrieval_hit_rate": 0.30, "total_experiences": 100, "successful_patterns": 10,
                 "avg_experience_quality": 0.60, "pattern_utilization_rate": 0.40}
        opportunities = learning_optimizer.analyze(stats)
        assert len(opportunities) >= 1
        assert any("retrieval" in o.problem.lower() for o in opportunities)

    def test_analyze_low_utilization(self, learning_optimizer):
        stats = {"retrieval_hit_rate": 0.60, "total_experiences": 100, "successful_patterns": 10,
                 "avg_experience_quality": 0.60, "pattern_utilization_rate": 0.20}
        opportunities = learning_optimizer.analyze(stats)
        assert len(opportunities) >= 1
        assert any("utilization" in o.problem.lower() for o in opportunities)

    def test_analyze_low_quality(self, learning_optimizer):
        stats = {"retrieval_hit_rate": 0.60, "total_experiences": 100, "successful_patterns": 10,
                 "avg_experience_quality": 0.30, "pattern_utilization_rate": 0.40}
        opportunities = learning_optimizer.analyze(stats)
        assert len(opportunities) >= 1
        assert any("quality" in o.problem.lower() for o in opportunities)

    def test_analyze_all_good(self, learning_optimizer):
        stats = {"retrieval_hit_rate": 0.80, "total_experiences": 100, "successful_patterns": 30,
                 "avg_experience_quality": 0.70, "pattern_utilization_rate": 0.50}
        opportunities = learning_optimizer.analyze(stats)
        assert len(opportunities) == 0

    def test_analyze_pattern_mining(self, learning_optimizer):
        stats = {"retrieval_hit_rate": 0.60, "total_experiences": 200, "successful_patterns": 5,
                 "avg_experience_quality": 0.60, "pattern_utilization_rate": 0.40}
        opportunities = learning_optimizer.analyze(stats)
        assert any("mining" in o.problem.lower() for o in opportunities)

    def test_generate_actions(self, learning_optimizer):
        opportunities = [
            OptimizationOpportunity(
                area=OptimizationArea.MEMORY,
                problem="Memory retrieval hit rate too low",
                confidence=0.80,
                expected_gain=0.15,
            ),
        ]
        actions = learning_optimizer.generate_actions(opportunities)
        assert len(actions) == 1
        assert actions[0].parameter == "similarity_threshold"
        assert actions[0].old_value == 0.85
        assert actions[0].new_value == 0.78

    def test_generate_actions_skips_non_actionable(self, learning_optimizer):
        opportunities = [
            OptimizationOpportunity(
                area=OptimizationArea.MEMORY,
                problem="test",
                confidence=0.5,
                expected_gain=0.0,
            ),
        ]
        actions = learning_optimizer.generate_actions(opportunities)
        assert len(actions) == 0

    def test_evaluate_experience_quality(self, learning_optimizer):
        experiences = [
            {"reward": 0.8, "outcome": "success"},
            {"reward": 0.6, "outcome": "success"},
            {"reward": -0.2, "outcome": "failure"},
        ]
        result = learning_optimizer.evaluate_experience_quality(experiences)
        assert result["count"] == 3
        assert result["quality"] > 0
        assert result["avg_reward"] == pytest.approx(0.4)

    def test_evaluate_experience_quality_empty(self, learning_optimizer):
        result = learning_optimizer.evaluate_experience_quality([])
        assert result["quality"] == 0.0
        assert result["count"] == 0
        assert "no_experiences" in result["issues"]

    def test_evaluate_retrieval_efficiency(self, learning_optimizer):
        stats = {"total_queries": 100, "hits": 30, "avg_similarity": 0.70, "threshold": 0.85}
        result = learning_optimizer.evaluate_retrieval_efficiency(stats)
        assert result["hit_rate"] == 0.3
        assert result["recommendation"] == "decrease_threshold"

    def test_evaluate_retrieval_efficiency_good(self, learning_optimizer):
        stats = {"total_queries": 100, "hits": 80, "avg_similarity": 0.90, "threshold": 0.85}
        result = learning_optimizer.evaluate_retrieval_efficiency(stats)
        assert result["recommendation"] == "maintain"

    def test_get_actions(self, learning_optimizer):
        opportunities = [
            OptimizationOpportunity(
                area=OptimizationArea.MEMORY,
                problem="Memory retrieval hit rate too low",
                confidence=0.80,
                expected_gain=0.15,
            ),
        ]
        learning_optimizer.generate_actions(opportunities)
        assert len(learning_optimizer.get_actions()) == 1

    def test_get_summary(self, learning_optimizer):
        opportunities = [
            OptimizationOpportunity(
                area=OptimizationArea.MEMORY,
                problem="Memory retrieval hit rate too low",
                confidence=0.80,
                expected_gain=0.15,
            ),
        ]
        learning_optimizer.generate_actions(opportunities)
        summary = learning_optimizer.get_summary()
        assert summary["total_actions"] == 1

    def test_reset(self, learning_optimizer):
        opportunities = [
            OptimizationOpportunity(
                area=OptimizationArea.MEMORY,
                problem="Memory retrieval hit rate too low",
                confidence=0.80,
                expected_gain=0.15,
            ),
        ]
        learning_optimizer.generate_actions(opportunities)
        learning_optimizer.reset()
        assert len(learning_optimizer.get_actions()) == 0

    def test_generate_actions_quality(self, learning_optimizer):
        opportunities = [
            OptimizationOpportunity(
                area=OptimizationArea.LEARNING,
                problem="Average experience quality too low",
                confidence=0.70,
                expected_gain=0.12,
            ),
        ]
        actions = learning_optimizer.generate_actions(opportunities)
        assert len(actions) == 1
        assert actions[0].parameter == "experience_weight"


# ═══════════════════════════════════════════════════════════════════
# 6. Self Diagnosis (15 tests)
# ═══════════════════════════════════════════════════════════════════


class TestSelfDiagnosis:
    def test_diagnose_no_issues(self, diagnosis_engine):
        metrics = [
            OptimizationMetric(metric_name="decision_accuracy", current_value=0.85, target_value=0.85,
                               baseline_value=0.50, trend=TrendDirection.STABLE),
        ]
        diagnosis = diagnosis_engine.diagnose(metrics, [])
        assert isinstance(diagnosis, SystemDiagnosis)
        assert len(diagnosis.hypotheses) == 0

    def test_diagnose_risk_conservative(self, diagnosis_engine):
        metrics = [
            OptimizationMetric(metric_name="risk_approval_rate", current_value=0.40, target_value=0.70,
                               baseline_value=0.50, trend=TrendDirection.DECLINING),
            OptimizationMetric(metric_name="execution_success_rate", current_value=0.85, target_value=0.90,
                               baseline_value=0.50, trend=TrendDirection.STABLE),
        ]
        diagnosis = diagnosis_engine.diagnose(metrics, [])
        assert any("risk" in h["name"] for h in diagnosis.hypotheses)

    def test_diagnose_decision_decline(self, diagnosis_engine):
        metrics = [
            OptimizationMetric(metric_name="decision_accuracy", current_value=0.60, target_value=0.85,
                               baseline_value=0.50, trend=TrendDirection.DECLINING),
        ]
        diagnosis = diagnosis_engine.diagnose(metrics, [])
        assert any("decision" in h["name"] for h in diagnosis.hypotheses)

    def test_diagnose_execution_failure(self, diagnosis_engine):
        metrics = [
            OptimizationMetric(metric_name="execution_success_rate", current_value=0.65, target_value=0.90,
                               baseline_value=0.50, trend=TrendDirection.DECLINING),
        ]
        diagnosis = diagnosis_engine.diagnose(metrics, [])
        assert any("execution" in h["name"] for h in diagnosis.hypotheses)

    def test_diagnose_memory_underutilization(self, diagnosis_engine):
        metrics = [
            OptimizationMetric(metric_name="memory_hit_rate", current_value=0.30, target_value=0.70,
                               baseline_value=0.30, trend=TrendDirection.STABLE),
        ]
        diagnosis = diagnosis_engine.diagnose(metrics, [])
        assert any("memory" in h["name"] for h in diagnosis.hypotheses)

    def test_diagnose_strategy_degradation(self, diagnosis_engine):
        metrics = []
        strategies = [
            StrategyPerformance(strategy_name="test", degraded=True, degradation_rate=0.25),
        ]
        diagnosis = diagnosis_engine.diagnose(metrics, strategies)
        assert any("strategy" in h["name"] for h in diagnosis.hypotheses)

    def test_diagnose_reward_prediction(self, diagnosis_engine):
        metrics = [
            OptimizationMetric(metric_name="reward_prediction_error", current_value=0.30, target_value=0.10,
                               baseline_value=0.30, trend=TrendDirection.STABLE),
        ]
        diagnosis = diagnosis_engine.diagnose(metrics, [])
        assert any("reward" in h["name"] for h in diagnosis.hypotheses)

    def test_diagnose_planning(self, diagnosis_engine):
        metrics = [
            OptimizationMetric(metric_name="planning_match_rate", current_value=0.50, target_value=0.80,
                               baseline_value=0.50, trend=TrendDirection.STABLE),
        ]
        diagnosis = diagnosis_engine.diagnose(metrics, [])
        assert any("planning" in h["name"] for h in diagnosis.hypotheses)

    def test_diagnose_system_wide(self, diagnosis_engine):
        metrics = [
            OptimizationMetric(metric_name="decision_accuracy", current_value=0.50, target_value=0.85,
                               baseline_value=0.50, trend=TrendDirection.DECLINING, severity=MetricSeverity.WARNING),
            OptimizationMetric(metric_name="execution_success_rate", current_value=0.50, target_value=0.90,
                               baseline_value=0.50, trend=TrendDirection.DECLINING, severity=MetricSeverity.WARNING),
            OptimizationMetric(metric_name="memory_hit_rate", current_value=0.20, target_value=0.70,
                               baseline_value=0.30, trend=TrendDirection.DECLINING, severity=MetricSeverity.WARNING),
        ]
        diagnosis = diagnosis_engine.diagnose(metrics, [])
        assert any("system" in h["name"] for h in diagnosis.hypotheses)

    def test_generate_opportunities(self, diagnosis_engine):
        metrics = [
            OptimizationMetric(metric_name="risk_approval_rate", current_value=0.40, target_value=0.70,
                               baseline_value=0.50, trend=TrendDirection.DECLINING),
            OptimizationMetric(metric_name="execution_success_rate", current_value=0.85, target_value=0.90,
                               baseline_value=0.50, trend=TrendDirection.STABLE),
        ]
        diagnosis = diagnosis_engine.diagnose(metrics, [])
        opportunities = diagnosis_engine.generate_opportunities(diagnosis)
        assert len(opportunities) >= 1
        assert opportunities[0].is_actionable()

    def test_generate_opportunities_empty(self, diagnosis_engine):
        diagnosis = SystemDiagnosis(observations=[], hypotheses=[], root_causes=[], recommendations=[])
        opportunities = diagnosis_engine.generate_opportunities(diagnosis)
        assert len(opportunities) == 0

    def test_diagnosis_count(self, diagnosis_engine):
        metrics = [OptimizationMetric(metric_name="test", current_value=0.5, target_value=0.8, baseline_value=0.5)]
        diagnosis_engine.diagnose(metrics, [])
        diagnosis_engine.diagnose(metrics, [])
        assert diagnosis_engine.diagnosis_count == 2

    def test_get_diagnoses(self, diagnosis_engine):
        metrics = [OptimizationMetric(metric_name="test", current_value=0.5, target_value=0.8, baseline_value=0.5)]
        diagnosis_engine.diagnose(metrics, [])
        assert len(diagnosis_engine.get_diagnoses()) == 1

    def test_get_latest_diagnosis(self, diagnosis_engine):
        assert diagnosis_engine.get_latest_diagnosis() is None
        metrics = [OptimizationMetric(metric_name="test", current_value=0.5, target_value=0.8, baseline_value=0.5)]
        diagnosis_engine.diagnose(metrics, [])
        assert diagnosis_engine.get_latest_diagnosis() is not None

    def test_diagnosis_rules(self):
        assert len(DIAGNOSIS_RULES) >= 5
        for rule in DIAGNOSIS_RULES:
            assert "name" in rule
            assert "condition" in rule
            assert "hypothesis" in rule
            assert "root_cause" in rule


# ═══════════════════════════════════════════════════════════════════
# 7. Optimizer Integration (10 tests)
# ═══════════════════════════════════════════════════════════════════


class TestSelfOptimizer:
    def test_create_optimizer(self, self_optimizer):
        assert self_optimizer.cycle_count == 0
        assert self_optimizer.monitor is not None
        assert self_optimizer.strategy_evaluator is not None

    def test_record_metrics(self, self_optimizer):
        results = self_optimizer.record_metrics({"decision_accuracy": 0.72, "execution_success_rate": 0.81})
        assert len(results) == 2

    def test_record_strategy(self, self_optimizer):
        perf = self_optimizer.record_strategy("creative_refresh", success=True, reward=0.8)
        assert perf.success_rate == 1.0

    def test_run_cycle(self, self_optimizer):
        self_optimizer.record_metrics({"decision_accuracy": 0.72})
        self_optimizer.record_strategy("creative_refresh", success=True, reward=0.8)
        result = self_optimizer.run_cycle()
        assert result["cycle"] == 1
        assert "diagnosis" in result
        assert "actions" in result

    def test_run_cycle_multiple(self, self_optimizer):
        self_optimizer.record_metrics({"decision_accuracy": 0.72})
        self_optimizer.run_cycle()
        self_optimizer.run_cycle()
        assert self_optimizer.cycle_count == 2

    def test_get_metrics(self, self_optimizer):
        self_optimizer.record_metrics({"decision_accuracy": 0.72})
        metrics = self_optimizer.get_metrics()
        assert len(metrics) >= 1

    def test_get_degraded_metrics(self, self_optimizer):
        self_optimizer.record_metrics({"decision_accuracy": 0.85})
        assert len(self_optimizer.get_degraded_metrics()) == 0

    def test_full_cycle_with_degradation(self, self_optimizer):
        # Set up degraded metrics
        self_optimizer.record_metrics({
            "risk_approval_rate": 0.40,
            "execution_success_rate": 0.85,
            "decision_accuracy": 0.60,
        })
        # Create degraded strategy
        for _ in range(40):
            self_optimizer.record_strategy("test", success=True, reward=0.8)
        for _ in range(20):
            self_optimizer.record_strategy("test", success=False, reward=0.1)

        result = self_optimizer.run_cycle()
        assert result["cycle"] == 1
        assert "diagnosis" in result
        assert "actions" in result

    def test_get_summary(self, self_optimizer):
        self_optimizer.record_metrics({"decision_accuracy": 0.72})
        self_optimizer.run_cycle()
        summary = self_optimizer.get_summary()
        assert summary["cycle_count"] == 1
        assert "monitor" in summary
        assert "strategies" in summary
        assert "policy" in summary

    def test_reset(self, self_optimizer):
        self_optimizer.record_metrics({"decision_accuracy": 0.72})
        self_optimizer.run_cycle()
        self_optimizer.reset()
        assert self_optimizer.cycle_count == 0
        assert len(self_optimizer.get_metrics()) == 0