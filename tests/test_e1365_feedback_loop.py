"""E13.6.5 Feedback Loop - test suite.

Tests cover:
  - Models: ExecutionFeedback, RewardSignal, FeedbackResult, FeedbackConfig
  - ResultAnalyzer: analysis, batch, trends
  - RewardCalculator: four-dimension reward, confidence, distribution
  - FeedbackProcessor: processing, Memory writes, lesson extraction
  - FeedbackLoop: full loop, batch, stats
  - Integration: end-to-end pipeline
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from market_ops.creative_vision_runtime.growth_runtime.execution.feedback.models import (
    ExecutionFeedback,
    FeedbackConfig,
    FeedbackResult,
    RewardSignal,
    create_conservative_config,
    create_default_config,
    create_exploration_config,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.feedback.result_analyzer import (
    ResultAnalyzer,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.feedback.reward_calculator import (
    RewardCalculator,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.feedback.feedback_processor import (
    FeedbackProcessor,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.feedback.feedback_loop import (
    FeedbackLoop,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.execution_core import (
    EngineResult,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.execution_context import (
    ExecutionContext,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.audit_log import (
    AuditLog,
    AuditEntry,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.base_executor import (
    ExecutionResult,
    ExecutionResultStatus,
    GuardContext,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.models import (
    ExecutionAction,
    ExecutionActionType,
    ExecutionDomain,
    ExecutionPriority,
)


# ============================================================
# Helpers
# ============================================================


def _make_engine_result(
    plan_id="plan_001",
    task_id="task_001",
    total=3,
    success=3,
    failure=0,
    skipped=0,
    rollback=0,
    started_at="2026-01-01T00:00:00",
    completed_at="2026-01-01T00:00:01",
):
    return EngineResult(
        plan_id=plan_id,
        task_id=task_id,
        total_nodes=total,
        success_count=success,
        failure_count=failure,
        skipped_count=skipped,
        rollback_count=rollback,
        started_at=started_at,
        completed_at=completed_at,
    )


def _make_context(
    decision_id="d001",
    opportunity_id="o001",
    strategy_id="s001",
):
    return ExecutionContext(
        decision_id=decision_id,
        opportunity_id=opportunity_id,
        strategy_id=strategy_id,
        reason="test execution",
    )


def _make_audit_log():
    log = AuditLog()
    action = ExecutionAction(
        action_type=ExecutionActionType.SCALE_BUDGET,
        domain=ExecutionDomain.BUDGET,
        priority=ExecutionPriority.HIGH,
    )
    result = ExecutionResult(
        action_id="a001",
        action_type=ExecutionActionType.SCALE_BUDGET,
        status=ExecutionResultStatus.SUCCESS,
        executor="test_executor",
        reason="growth opportunity",
        confidence=0.85,
    )
    log.record(result, reason="test", task_id="task_001", decision_id="d001")
    return log


def _make_safety_evaluation(
    decision="ALLOW",
    risk_score=0.1,
    is_blocked=False,
    requires_approval=False,
    warnings=None,
    triggered_rules=None,
):
    return {
        "decision": decision,
        "risk_score": risk_score,
        "is_blocked": is_blocked,
        "requires_approval": requires_approval,
        "warnings": warnings or [],
        "triggered_rules": triggered_rules or [],
    }


# ============================================================
# Test: ExecutionFeedback Model
# ============================================================


class TestExecutionFeedback:

    def test_create_default(self):
        fb = ExecutionFeedback()
        assert fb.feedback_id != ""
        assert fb.decision_id == ""
        assert fb.total_nodes == 0
        assert fb.success_rate == 1.0

    def test_create_with_data(self):
        fb = ExecutionFeedback(
            decision_id="d001",
            total_nodes=10,
            success_nodes=8,
            failure_nodes=1,
            skipped_nodes=1,
            rollback_nodes=0,
        )
        assert fb.decision_id == "d001"
        assert fb.total_nodes == 10
        assert fb.success_rate == 0.8
        assert fb.has_failures is True
        assert fb.has_rollbacks is False

    def test_success_rate_perfect(self):
        fb = ExecutionFeedback(total_nodes=5, success_nodes=5)
        assert fb.success_rate == 1.0

    def test_success_rate_zero_nodes(self):
        fb = ExecutionFeedback(total_nodes=0, success_nodes=0)
        assert fb.success_rate == 1.0

    def test_success_rate_partial(self):
        fb = ExecutionFeedback(total_nodes=10, success_nodes=3)
        assert fb.success_rate == 0.3

    def test_has_failures_true(self):
        fb = ExecutionFeedback(failure_nodes=2)
        assert fb.has_failures is True

    def test_has_failures_false(self):
        fb = ExecutionFeedback(failure_nodes=0)
        assert fb.has_failures is False

    def test_has_rollbacks_true(self):
        fb = ExecutionFeedback(rollback_nodes=1)
        assert fb.has_rollbacks is True

    def test_was_blocked_true(self):
        fb = ExecutionFeedback(safety_evaluation={"is_blocked": True})
        assert fb.was_blocked is True

    def test_was_blocked_false(self):
        fb = ExecutionFeedback(safety_evaluation={"is_blocked": False})
        assert fb.was_blocked is False

    def test_was_blocked_no_eval(self):
        fb = ExecutionFeedback(safety_evaluation=None)
        assert fb.was_blocked is False

    def test_needed_approval_true(self):
        fb = ExecutionFeedback(safety_evaluation={"requires_approval": True})
        assert fb.needed_approval is True

    def test_needed_approval_false(self):
        fb = ExecutionFeedback(safety_evaluation={"requires_approval": False})
        assert fb.needed_approval is False

    def test_to_dict(self):
        fb = ExecutionFeedback(
            decision_id="d001",
            task_id="t001",
            total_nodes=3,
            success_nodes=3,
        )
        d = fb.to_dict()
        assert d["decision_id"] == "d001"
        assert d["task_id"] == "t001"
        assert d["success_rate"] == 1.0

    def test_execution_duration(self):
        fb = ExecutionFeedback(execution_duration_ms=1500.0)
        assert fb.execution_duration_ms == 1500.0


# ============================================================
# Test: RewardSignal Model
# ============================================================


class TestRewardSignal:

    def test_create_default(self):
        r = RewardSignal()
        assert r.reward_id != ""
        assert r.total_reward == 0.0
        assert r.reward_level == "neutral"

    def test_is_positive(self):
        r = RewardSignal(total_reward=0.5)
        assert r.is_positive is True
        assert r.is_negative is False
        assert r.is_neutral is False

    def test_is_negative(self):
        r = RewardSignal(total_reward=-0.5)
        assert r.is_negative is True
        assert r.is_positive is False

    def test_is_neutral(self):
        r = RewardSignal(total_reward=0.0)
        assert r.is_neutral is True

    def test_is_neutral_boundary(self):
        r = RewardSignal(total_reward=0.1)
        assert r.is_neutral is True

    def test_four_dimensions(self):
        r = RewardSignal(
            execution_reward=0.8,
            efficiency_reward=0.5,
            safety_reward=0.9,
            outcome_reward=0.3,
        )
        assert r.execution_reward == 0.8
        assert r.efficiency_reward == 0.5
        assert r.safety_reward == 0.9
        assert r.outcome_reward == 0.3

    def test_confidence(self):
        r = RewardSignal(confidence=0.85)
        assert r.confidence == 0.85

    def test_reward_level_positive(self):
        r = RewardSignal(total_reward=0.5, reward_level="positive")
        assert r.reward_level == "positive"

    def test_reward_level_negative(self):
        r = RewardSignal(total_reward=-0.5, reward_level="negative")
        assert r.reward_level == "negative"

    def test_to_dict(self):
        r = RewardSignal(
            decision_id="d001",
            total_reward=0.75,
            execution_reward=0.8,
            efficiency_reward=0.5,
            safety_reward=0.9,
            outcome_reward=0.8,
            components={"a": 0.5},
        )
        d = r.to_dict()
        assert d["decision_id"] == "d001"
        assert d["total_reward"] == 0.75
        assert d["execution_reward"] == 0.8
        assert d["components"]["a"] == 0.5


# ============================================================
# Test: FeedbackResult Model
# ============================================================


class TestFeedbackResult:

    def test_create_default(self):
        r = FeedbackResult()
        assert r.next_action == ""
        assert r.memory_updated is False
        assert r.is_successful_loop is False

    def test_is_successful_loop(self):
        reward = RewardSignal(total_reward=0.5)
        r = FeedbackResult(memory_updated=True, reward=reward)
        assert r.is_successful_loop is True

    def test_is_successful_loop_no_reward(self):
        r = FeedbackResult(memory_updated=True)
        assert r.is_successful_loop is False

    def test_should_reinforce(self):
        r = FeedbackResult(next_action="reinforce")
        assert r.should_reinforce is True
        assert r.should_adjust is False
        assert r.should_abandon is False

    def test_should_adjust(self):
        r = FeedbackResult(next_action="adjust")
        assert r.should_adjust is True
        assert r.should_reinforce is False

    def test_should_abandon(self):
        r = FeedbackResult(next_action="abandon")
        assert r.should_abandon is True

    def test_lessons(self):
        r = FeedbackResult(lessons=["lesson1", "lesson2"])
        assert len(r.lessons) == 2

    def test_recommendations(self):
        r = FeedbackResult(recommendations=["rec1"])
        assert len(r.recommendations) == 1

    def test_to_dict(self):
        feedback = ExecutionFeedback(decision_id="d001")
        reward = RewardSignal(total_reward=0.75)
        r = FeedbackResult(
            feedback_id="f001",
            decision_id="d001",
            feedback=feedback,
            reward=reward,
            memory_updated=True,
            next_action="reinforce",
        )
        d = r.to_dict()
        assert d["decision_id"] == "d001"
        assert d["memory_updated"] is True
        assert d["next_action"] == "reinforce"
        assert d["feedback"] is not None
        assert d["reward"] is not None


# ============================================================
# Test: FeedbackConfig
# ============================================================


class TestFeedbackConfig:

    def test_default_config(self):
        c = FeedbackConfig()
        assert c.validate() is True
        assert c.execution_weight == 0.30
        assert c.safety_weight == 0.25
        assert c.outcome_weight == 0.30

    def test_weights_sum_to_one(self):
        c = FeedbackConfig()
        assert c.validate() is True

    def test_exploration_config(self):
        c = create_exploration_config()
        assert c.outcome_weight == 0.45
        assert c.safety_weight == 0.15
        assert c.validate() is True

    def test_conservative_config(self):
        c = create_conservative_config()
        assert c.safety_weight == 0.45
        assert c.outcome_weight == 0.20
        assert c.min_confidence == 0.5
        assert c.validate() is True

    def test_invalid_weights(self):
        c = FeedbackConfig(execution_weight=0.5, efficiency_weight=0.5)
        assert c.validate() is False

    def test_to_dict(self):
        c = FeedbackConfig()
        d = c.to_dict()
        assert d["execution_weight"] == 0.30
        assert d["positive_threshold"] == 0.1


# ============================================================
# Test: ResultAnalyzer
# ============================================================


class TestResultAnalyzer:

    def test_analyze_basic(self):
        analyzer = ResultAnalyzer()
        result = _make_engine_result(total=3, success=3)
        context = _make_context()
        fb = analyzer.analyze(result, context=context)
        assert fb.total_nodes == 3
        assert fb.success_nodes == 3
        assert fb.failure_nodes == 0
        assert fb.decision_id == "d001"

    def test_analyze_with_audit_log(self):
        analyzer = ResultAnalyzer()
        result = _make_engine_result()
        audit = _make_audit_log()
        fb = analyzer.analyze(result, audit_log=audit)
        assert len(fb.audit_entries) == 1

    def test_analyze_with_safety_eval(self):
        analyzer = ResultAnalyzer()
        result = _make_engine_result()
        safety = _make_safety_evaluation(risk_score=0.3)
        fb = analyzer.analyze(result, safety_evaluation=safety)
        assert fb.safety_evaluation is not None
        assert fb.safety_evaluation["risk_score"] == 0.3

    def test_analyze_with_failures(self):
        analyzer = ResultAnalyzer()
        result = _make_engine_result(total=5, success=3, failure=2)
        fb = analyzer.analyze(result)
        assert fb.failure_nodes == 2
        assert fb.has_failures is True
        assert fb.success_rate == 0.6

    def test_analyze_with_rollbacks(self):
        analyzer = ResultAnalyzer()
        result = _make_engine_result(total=5, success=4, rollback=1)
        fb = analyzer.analyze(result)
        assert fb.rollback_nodes == 1
        assert fb.has_rollbacks is True

    def test_analyze_extracts_task_id(self):
        analyzer = ResultAnalyzer()
        result = _make_engine_result(task_id="task_xyz")
        fb = analyzer.analyze(result)
        assert fb.task_id == "task_xyz"

    def test_analyze_extracts_plan_id(self):
        analyzer = ResultAnalyzer()
        result = _make_engine_result(plan_id="plan_abc")
        fb = analyzer.analyze(result)
        assert fb.plan_id == "plan_abc"

    def test_analyze_action_type(self):
        analyzer = ResultAnalyzer()
        result = _make_engine_result()
        audit = _make_audit_log()
        fb = analyzer.analyze(result, audit_log=audit)
        assert fb.action_type == "scale_budget"

    def test_analyze_calculates_duration(self):
        analyzer = ResultAnalyzer()
        result = _make_engine_result(
            started_at="2026-01-01T00:00:00",
            completed_at="2026-01-01T00:00:02",
        )
        fb = analyzer.analyze(result)
        assert fb.execution_duration_ms == 2000.0

    def test_analyze_no_duration(self):
        analyzer = ResultAnalyzer()
        result = EngineResult(plan_id="p1", task_id="t1", started_at="", completed_at="")
        fb = analyzer.analyze(result)
        assert fb.execution_duration_ms == 0.0

    def test_analyze_batch(self):
        analyzer = ResultAnalyzer()
        results = [
            _make_engine_result(plan_id="p1"),
            _make_engine_result(plan_id="p2"),
        ]
        fbs = analyzer.analyze_batch(results)
        assert len(fbs) == 2
        assert fbs[0].plan_id == "p1"
        assert fbs[1].plan_id == "p2"

    def test_analyze_trends_improving(self):
        analyzer = ResultAnalyzer()
        fbs = [
            ExecutionFeedback(total_nodes=5, success_nodes=3),
            ExecutionFeedback(total_nodes=5, success_nodes=4),
            ExecutionFeedback(total_nodes=5, success_nodes=5),
        ]
        trends = analyzer.analyze_trends(fbs)
        assert trends["trends"]["success_rate"] == "improving"

    def test_analyze_trends_declining(self):
        analyzer = ResultAnalyzer()
        fbs = [
            ExecutionFeedback(total_nodes=5, success_nodes=5),
            ExecutionFeedback(total_nodes=5, success_nodes=3),
        ]
        trends = analyzer.analyze_trends(fbs)
        assert trends["trends"]["success_rate"] == "declining"

    def test_analyze_trends_empty(self):
        analyzer = ResultAnalyzer()
        trends = analyzer.analyze_trends([])
        assert trends["count"] == 0

    def test_analyze_trends_blocked_count(self):
        analyzer = ResultAnalyzer()
        fbs = [
            ExecutionFeedback(safety_evaluation={"is_blocked": True}),
            ExecutionFeedback(safety_evaluation={"is_blocked": False}),
        ]
        trends = analyzer.analyze_trends(fbs)
        assert trends["blocked_count"] == 1

    def test_analysis_count(self):
        analyzer = ResultAnalyzer()
        assert analyzer.analysis_count == 0
        analyzer.analyze(_make_engine_result())
        assert analyzer.analysis_count == 1
        analyzer.analyze(_make_engine_result())
        assert analyzer.analysis_count == 2

    def test_reset(self):
        analyzer = ResultAnalyzer()
        analyzer.analyze(_make_engine_result())
        analyzer.reset()
        assert analyzer.analysis_count == 0


# ============================================================
# Test: RewardCalculator
# ============================================================


class TestRewardCalculator:

    def test_calculate_perfect_execution(self):
        calc = RewardCalculator()
        fb = ExecutionFeedback(total_nodes=3, success_nodes=3, execution_duration_ms=500)
        reward = calc.calculate(fb)
        assert reward.is_positive is True
        assert reward.total_reward > 0.3

    def test_calculate_all_failed(self):
        calc = RewardCalculator()
        fb = ExecutionFeedback(total_nodes=5, success_nodes=0, failure_nodes=5)
        reward = calc.calculate(fb)
        assert reward.is_negative is True
        assert reward.total_reward < 0.0

    def test_calculate_execution_reward_perfect(self):
        calc = RewardCalculator()
        fb = ExecutionFeedback(total_nodes=10, success_nodes=10)
        r = calc._calc_execution_reward(fb)
        assert r == 1.0

    def test_calculate_execution_reward_all_fail(self):
        calc = RewardCalculator()
        fb = ExecutionFeedback(total_nodes=5, success_nodes=0, failure_nodes=5)
        r = calc._calc_execution_reward(fb)
        assert r < -0.5

    def test_calculate_execution_reward_with_rollbacks(self):
        calc = RewardCalculator()
        fb = ExecutionFeedback(total_nodes=5, success_nodes=3, failure_nodes=1, rollback_nodes=1)
        r = calc._calc_execution_reward(fb)
        assert r < 0.0

    def test_calculate_efficiency_reward_fast(self):
        calc = RewardCalculator()
        fb = ExecutionFeedback(total_nodes=3, success_nodes=3, execution_duration_ms=100)
        r = calc._calc_efficiency_reward(fb)
        assert r > 0.0

    def test_calculate_efficiency_reward_slow(self):
        calc = RewardCalculator()
        fb = ExecutionFeedback(total_nodes=3, success_nodes=3, execution_duration_ms=60000)
        r = calc._calc_efficiency_reward(fb)
        assert r < 0.0

    def test_calculate_safety_reward_safe(self):
        calc = RewardCalculator()
        fb = ExecutionFeedback(safety_evaluation=_make_safety_evaluation(risk_score=0.0))
        r = calc._calc_safety_reward(fb)
        assert r == 1.0

    def test_calculate_safety_reward_blocked(self):
        calc = RewardCalculator()
        fb = ExecutionFeedback(safety_evaluation=_make_safety_evaluation(is_blocked=True))
        r = calc._calc_safety_reward(fb)
        assert r <= 0.0

    def test_calculate_safety_reward_approval(self):
        calc = RewardCalculator()
        fb = ExecutionFeedback(safety_evaluation=_make_safety_evaluation(
            requires_approval=True, risk_score=0.0, triggered_rules=[],
        ))
        r = calc._calc_safety_reward(fb)
        assert r == 0.5

    def test_calculate_safety_reward_with_warnings(self):
        calc = RewardCalculator()
        fb = ExecutionFeedback(
            safety_evaluation=_make_safety_evaluation(
                risk_score=0.2,
                warnings=["warn1", "warn2"],
            )
        )
        r = calc._calc_safety_reward(fb)
        assert r < 1.0

    def test_calculate_outcome_from_metrics_positive(self):
        calc = RewardCalculator()
        metrics = {"roas_change": 0.3, "revenue_change": 0.2}
        r = calc._calc_outcome_from_metrics(metrics)
        assert r > 0.0

    def test_calculate_outcome_from_metrics_negative(self):
        calc = RewardCalculator()
        metrics = {"roas_change": -0.3, "cpa_change": 0.5}
        r = calc._calc_outcome_from_metrics(metrics)
        assert r < 0.0

    def test_calculate_outcome_from_execution_blocked(self):
        calc = RewardCalculator()
        fb = ExecutionFeedback(safety_evaluation=_make_safety_evaluation(is_blocked=True))
        r = calc._calc_outcome_from_execution(fb)
        assert r == -0.5

    def test_calculate_outcome_from_execution_failed(self):
        calc = RewardCalculator()
        fb = ExecutionFeedback(total_nodes=5, success_nodes=3, failure_nodes=2)
        r = calc._calc_outcome_from_execution(fb)
        assert r == -0.3

    def test_calculate_outcome_from_execution_success(self):
        calc = RewardCalculator()
        fb = ExecutionFeedback(total_nodes=5, success_nodes=5)
        r = calc._calc_outcome_from_execution(fb)
        assert r == 0.3

    def test_calculate_confidence_basic(self):
        calc = RewardCalculator()
        fb = ExecutionFeedback()
        c = calc._calc_confidence(fb)
        assert c == 0.5

    def test_calculate_confidence_with_audit(self):
        calc = RewardCalculator()
        fb = ExecutionFeedback(
            total_nodes=5,
            audit_entries=[{"action_id": "a1"}],
            safety_evaluation=_make_safety_evaluation(),
        )
        c = calc._calc_confidence(fb)
        assert c > 0.5

    def test_calculate_batch(self):
        calc = RewardCalculator()
        fbs = [
            ExecutionFeedback(total_nodes=3, success_nodes=3),
            ExecutionFeedback(total_nodes=10, success_nodes=0, failure_nodes=10),
        ]
        rewards = calc.calculate_batch(fbs)
        assert len(rewards) == 2
        assert rewards[0].is_positive is True
        assert rewards[1].is_negative is True

    def test_reward_distribution(self):
        calc = RewardCalculator()
        rewards = [
            RewardSignal(total_reward=0.5),
            RewardSignal(total_reward=-0.5),
            RewardSignal(total_reward=0.0),
        ]
        dist = calc.get_reward_distribution(rewards)
        assert dist["distribution"]["positive"] == 1
        assert dist["distribution"]["negative"] == 1
        assert dist["distribution"]["neutral"] == 1

    def test_calculation_count(self):
        calc = RewardCalculator()
        assert calc.calculation_count == 0
        calc.calculate(ExecutionFeedback(total_nodes=1, success_nodes=1))
        assert calc.calculation_count == 1

    def test_reset(self):
        calc = RewardCalculator()
        calc.calculate(ExecutionFeedback(total_nodes=1, success_nodes=1))
        calc.reset()
        assert calc.calculation_count == 0

    def test_custom_config(self):
        config = FeedbackConfig(
            execution_weight=0.5,
            efficiency_weight=0.0,
            safety_weight=0.3,
            outcome_weight=0.2,
        )
        calc = RewardCalculator(config=config)
        fb = ExecutionFeedback(total_nodes=3, success_nodes=3)
        reward = calc.calculate(fb)
        assert reward is not None


# ============================================================
# Test: FeedbackProcessor
# ============================================================


class TestFeedbackProcessor:

    def test_process_without_memory(self):
        processor = FeedbackProcessor()
        fb = ExecutionFeedback(decision_id="d001", total_nodes=3, success_nodes=3)
        reward = RewardSignal(total_reward=0.75, decision_id="d001")
        result = processor.process(fb, reward)
        assert result.feedback_id == fb.feedback_id
        assert result.decision_id == "d001"
        assert result.memory_updated is False
        assert result.experience_stored is False

    def test_process_with_decision_memory(self):
        dm = MagicMock()
        dm.record_outcome.return_value = None
        processor = FeedbackProcessor(decision_memory=dm)
        fb = ExecutionFeedback(decision_id="d001", total_nodes=3, success_nodes=3)
        reward = RewardSignal(total_reward=0.75, decision_id="d001")
        result = processor.process(fb, reward)
        assert result.memory_updated is True
        dm.record_outcome.assert_called_once()

    def test_process_with_experience_store(self):
        es = MagicMock()
        es.add_experience.return_value = None
        processor = FeedbackProcessor(experience_store=es)
        fb = ExecutionFeedback(decision_id="d001", total_nodes=3, success_nodes=3)
        reward = RewardSignal(total_reward=0.75, decision_id="d001")
        result = processor.process(fb, reward)
        assert result.experience_stored is True

    def test_extract_lessons_positive(self):
        processor = FeedbackProcessor()
        fb = ExecutionFeedback(total_nodes=3, success_nodes=3)
        reward = RewardSignal(total_reward=0.75, execution_reward=0.8, safety_reward=0.9, outcome_reward=0.6)
        lessons = processor._extract_lessons(fb, reward)
        assert len(lessons) > 0

    def test_extract_lessons_failure(self):
        processor = FeedbackProcessor()
        fb = ExecutionFeedback(total_nodes=5, success_nodes=2, failure_nodes=3, rollback_nodes=2)
        reward = RewardSignal(total_reward=-0.5)
        lessons = processor._extract_lessons(fb, reward)
        assert len(lessons) > 0

    def test_extract_lessons_blocked(self):
        processor = FeedbackProcessor()
        fb = ExecutionFeedback(safety_evaluation=_make_safety_evaluation(is_blocked=True))
        reward = RewardSignal(total_reward=-0.8)
        lessons = processor._extract_lessons(fb, reward)
        assert any("block" in l.lower() or "intercept" in l.lower() or "安全" in l for l in lessons)

    def test_generate_recommendations_positive(self):
        processor = FeedbackProcessor()
        fb = ExecutionFeedback(total_nodes=3, success_nodes=3)
        reward = RewardSignal(total_reward=0.75)
        recs = processor._generate_recommendations(fb, reward)
        assert len(recs) > 0

    def test_generate_recommendations_negative(self):
        processor = FeedbackProcessor()
        fb = ExecutionFeedback(
            total_nodes=5, success_nodes=2, failure_nodes=3,
            safety_evaluation=_make_safety_evaluation(is_blocked=True),
        )
        reward = RewardSignal(total_reward=-0.8)
        recs = processor._generate_recommendations(fb, reward)
        assert len(recs) > 0

    def test_determine_next_action_reinforce(self):
        processor = FeedbackProcessor()
        fb = ExecutionFeedback(total_nodes=3, success_nodes=3)
        reward = RewardSignal(total_reward=0.75, confidence=0.8)
        action = processor._determine_next_action(fb, reward)
        assert action == "reinforce"

    def test_determine_next_action_adjust(self):
        processor = FeedbackProcessor()
        fb = ExecutionFeedback(total_nodes=5, success_nodes=2, failure_nodes=3)
        reward = RewardSignal(total_reward=-0.5)
        action = processor._determine_next_action(fb, reward)
        assert action == "adjust"

    def test_determine_next_action_abandon(self):
        processor = FeedbackProcessor()
        fb = ExecutionFeedback(safety_evaluation=_make_safety_evaluation(is_blocked=True))
        reward = RewardSignal(total_reward=-0.8)
        action = processor._determine_next_action(fb, reward)
        assert action == "abandon"

    def test_determine_next_action_observe(self):
        processor = FeedbackProcessor()
        fb = ExecutionFeedback(total_nodes=3, success_nodes=3)
        reward = RewardSignal(total_reward=0.0)
        action = processor._determine_next_action(fb, reward)
        assert action == "observe"

    def test_determine_next_action_low_confidence(self):
        processor = FeedbackProcessor()
        fb = ExecutionFeedback(total_nodes=3, success_nodes=3)
        reward = RewardSignal(total_reward=0.75, confidence=0.2)
        action = processor._determine_next_action(fb, reward)
        assert action == "observe"

    def test_process_count(self):
        processor = FeedbackProcessor()
        assert processor.process_count == 0
        processor.process(ExecutionFeedback(), RewardSignal())
        assert processor.process_count == 1

    def test_reset(self):
        processor = FeedbackProcessor()
        processor.process(ExecutionFeedback(), RewardSignal())
        processor.reset()
        assert processor.process_count == 0


# ============================================================
# Test: FeedbackLoop
# ============================================================


class TestFeedbackLoop:

    def test_run_basic(self):
        loop = FeedbackLoop()
        result = _make_engine_result()
        fb_result = loop.run(result)
        assert fb_result.feedback is not None
        assert fb_result.reward is not None
        assert fb_result.memory_updated is False

    def test_run_with_context(self):
        loop = FeedbackLoop()
        result = _make_engine_result()
        context = _make_context()
        fb_result = loop.run(result, context=context)
        assert fb_result.feedback.decision_id == "d001"

    def test_run_with_audit_log(self):
        loop = FeedbackLoop()
        result = _make_engine_result()
        audit = _make_audit_log()
        fb_result = loop.run(result, audit_log=audit)
        assert len(fb_result.feedback.audit_entries) > 0

    def test_run_with_safety_evaluation(self):
        loop = FeedbackLoop()
        result = _make_engine_result()
        safety = _make_safety_evaluation(risk_score=0.3)
        fb_result = loop.run(result, safety_evaluation=safety)
        assert fb_result.feedback.safety_evaluation is not None

    def test_run_with_business_metrics(self):
        loop = FeedbackLoop()
        result = _make_engine_result()
        metrics = {"roas_change": 0.3}
        fb_result = loop.run(result, business_metrics=metrics)
        assert fb_result.reward.outcome_reward > 0.0

    def test_run_with_decision_memory(self):
        dm = MagicMock()
        dm.record_outcome.return_value = None
        loop = FeedbackLoop(decision_memory=dm)
        result = _make_engine_result()
        context = _make_context()
        fb_result = loop.run(result, context=context)
        assert fb_result.memory_updated is True

    def test_run_simple(self):
        loop = FeedbackLoop()
        result = _make_engine_result()
        fb_result = loop.run_simple(result)
        assert fb_result.feedback is not None
        assert fb_result.reward is not None

    def test_run_batch(self):
        loop = FeedbackLoop()
        results = [
            _make_engine_result(plan_id="p1"),
            _make_engine_result(plan_id="p2"),
        ]
        fb_results = loop.run_batch(results)
        assert len(fb_results) == 2

    def test_get_history(self):
        loop = FeedbackLoop()
        loop.run(_make_engine_result())
        loop.run(_make_engine_result(plan_id="p2"))
        history = loop.get_history()
        assert len(history) == 2

    def test_get_by_decision(self):
        loop = FeedbackLoop()
        context = _make_context(decision_id="d_target")
        loop.run(_make_engine_result(), context=context)
        loop.run(_make_engine_result(plan_id="p2"), context=_make_context(decision_id="d_other"))
        results = loop.get_by_decision("d_target")
        assert len(results) == 1

    def test_get_positive_results(self):
        loop = FeedbackLoop()
        result = _make_engine_result(total=3, success=3)
        loop.run(result)
        positive = loop.get_positive_results()
        assert len(positive) > 0

    def test_get_negative_results(self):
        loop = FeedbackLoop()
        result = _make_engine_result(total=5, success=0, failure=5)
        loop.run(result)
        negative = loop.get_negative_results()
        assert len(negative) > 0

    def test_stats(self):
        loop = FeedbackLoop()
        loop.run(_make_engine_result())
        stats = loop.stats()
        assert stats["total_loops"] == 1
        assert "positive_rate" in stats

    def test_stats_empty(self):
        loop = FeedbackLoop()
        stats = loop.stats()
        assert stats["total_loops"] == 0

    def test_get_trends(self):
        loop = FeedbackLoop()
        loop.run(_make_engine_result())
        trends = loop.get_trends()
        assert trends["count"] > 0

    def test_loop_count(self):
        loop = FeedbackLoop()
        assert loop.loop_count == 0
        loop.run(_make_engine_result())
        assert loop.loop_count == 1

    def test_reset(self):
        loop = FeedbackLoop()
        loop.run(_make_engine_result())
        loop.reset()
        assert loop.loop_count == 0
        assert len(loop.get_history()) == 0


# ============================================================
# Test: Integration
# ============================================================


class TestIntegration:

    def test_full_pipeline_positive(self):
        """Positive: perfect execution -> positive reward -> reinforce."""
        dm = MagicMock()
        dm.record_outcome.return_value = None
        es = MagicMock()
        es.add_experience.return_value = None

        loop = FeedbackLoop(decision_memory=dm, experience_store=es)
        result = _make_engine_result(total=3, success=3)
        context = _make_context()
        audit = _make_audit_log()
        safety = _make_safety_evaluation(risk_score=0.0)

        fb_result = loop.run(
            result,
            audit_log=audit,
            context=context,
            safety_evaluation=safety,
        )

        assert fb_result.reward.is_positive is True
        assert fb_result.next_action == "reinforce"
        assert fb_result.memory_updated is True
        assert fb_result.experience_stored is True
        assert len(fb_result.lessons) > 0

    def test_full_pipeline_failure(self):
        """Negative: execution failure -> negative reward -> adjust."""
        loop = FeedbackLoop()
        result = _make_engine_result(total=10, success=0, failure=10)
        context = _make_context()

        fb_result = loop.run(result, context=context)

        assert fb_result.reward.is_negative is True
        assert fb_result.next_action == "adjust"

    def test_full_pipeline_blocked(self):
        """Safety blocked -> abandon."""
        loop = FeedbackLoop()
        result = _make_engine_result(total=3, success=3)
        safety = _make_safety_evaluation(is_blocked=True, risk_score=0.9)

        fb_result = loop.run(result, safety_evaluation=safety)

        assert fb_result.next_action == "abandon"
        assert fb_result.feedback.was_blocked is True

    def test_full_pipeline_approval(self):
        """Approval required scenario."""
        loop = FeedbackLoop()
        result = _make_engine_result(total=3, success=3)
        safety = _make_safety_evaluation(requires_approval=True, risk_score=0.5)

        fb_result = loop.run(result, safety_evaluation=safety)

        assert fb_result.feedback.needed_approval is True

    def test_full_pipeline_with_business_metrics(self):
        """With business metrics."""
        dm = MagicMock()
        dm.record_outcome.return_value = None
        loop = FeedbackLoop(decision_memory=dm)
        result = _make_engine_result(total=3, success=3)
        context = _make_context()
        metrics = {"roas_change": 0.5, "revenue_change": 0.3}

        fb_result = loop.run(result, context=context, business_metrics=metrics)

        assert fb_result.reward.outcome_reward > 0.3
        assert fb_result.memory_updated is True

    def test_full_pipeline_no_decision_id(self):
        """No decision ID scenario."""
        loop = FeedbackLoop()
        result = _make_engine_result()
        fb_result = loop.run(result)
        assert fb_result.feedback.decision_id == ""

    def test_evolution_trigger(self):
        """Memory Evolution trigger."""
        me = MagicMock()
        me.evolve.return_value = None
        processor = FeedbackProcessor(
            memory_evolution=me,
            config=FeedbackConfig(evolution_trigger_threshold=3),
        )
        for i in range(3):
            fb = ExecutionFeedback(decision_id=f"d{i:03d}", total_nodes=3, success_nodes=3)
            reward = RewardSignal(total_reward=0.75, decision_id=f"d{i:03d}")
            processor.process(fb, reward)

        me.evolve.assert_called_once()

    def test_multiple_loops_history(self):
        """Multiple loop history."""
        loop = FeedbackLoop()
        for i in range(5):
            result = _make_engine_result(plan_id=f"plan_{i:03d}")
            loop.run(result)

        history = loop.get_history()
        assert len(history) == 5
        stats = loop.stats()
        assert stats["total_loops"] == 5

    def test_exploration_config_loop(self):
        """Exploration config loop."""
        config = create_exploration_config()
        loop = FeedbackLoop(config=config)
        result = _make_engine_result(total=3, success=3)
        metrics = {"roas_change": 0.3}

        fb_result = loop.run(result, business_metrics=metrics)
        assert fb_result.reward is not None
        assert fb_result.reward.outcome_reward > 0.0

    def test_conservative_config_loop(self):
        """Conservative config loop."""
        config = create_conservative_config()
        loop = FeedbackLoop(config=config)
        result = _make_engine_result(total=3, success=3)
        safety = _make_safety_evaluation(risk_score=0.1, warnings=["w1"])

        fb_result = loop.run(result, safety_evaluation=safety)
        assert fb_result.reward is not None
        assert fb_result.reward.safety_reward < 1.0

    def test_processor_lesson_limit(self):
        """Lesson limit."""
        processor = FeedbackProcessor(config=FeedbackConfig(max_lessons=2))
        fb = ExecutionFeedback(
            total_nodes=5, success_nodes=2, failure_nodes=3,
            rollback_nodes=2,
            safety_evaluation=_make_safety_evaluation(
                is_blocked=True, warnings=["w1", "w2", "w3"],
            ),
        )
        reward = RewardSignal(total_reward=-0.8, execution_reward=-0.5, safety_reward=-0.5)
        lessons = processor._extract_lessons(fb, reward)
        assert len(lessons) <= 2

    def test_processor_recommendation_limit(self):
        """Recommendation limit."""
        processor = FeedbackProcessor(config=FeedbackConfig(max_recommendations=2))
        fb = ExecutionFeedback(
            total_nodes=5, success_nodes=2, failure_nodes=3,
            rollback_nodes=2,
            safety_evaluation=_make_safety_evaluation(is_blocked=True),
        )
        reward = RewardSignal(total_reward=-0.8, execution_reward=-0.5, safety_reward=-0.5)
        recs = processor._generate_recommendations(fb, reward)
        assert len(recs) <= 2

    def test_reward_distribution_mixed(self):
        """Mixed reward distribution."""
        calc = RewardCalculator()
        rewards = [
            RewardSignal(total_reward=0.8),
            RewardSignal(total_reward=0.5),
            RewardSignal(total_reward=0.0),
            RewardSignal(total_reward=-0.3),
            RewardSignal(total_reward=-0.8),
        ]
        dist = calc.get_reward_distribution(rewards)
        assert dist["distribution"]["positive"] == 2
        assert dist["distribution"]["neutral"] == 1
        assert dist["distribution"]["negative"] == 2

    def test_trends_integration(self):
        """Trends integration."""
        loop = FeedbackLoop()
        for i in range(4):
            result = _make_engine_result(
                total=5,
                success=min(i + 2, 5),
                failure=max(3 - i, 0),
            )
            loop.run(result)

        trends = loop.get_trends()
        assert trends["count"] == 4