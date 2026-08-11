"""E14.3.1 UA Feedback Loop — 集成测试.

验证 UA Agent 反馈闭环的完整功能:
  - Feedback Models (10)
  - Feedback Collector (10)
  - Reward Calculator (10)
  - Outcome Evaluator (10)
  - Learning Engine (10)
  - Feedback Loop (10)
  - UA Agent Feedback Integration (15)
  - Integration & E2E (10)

总计: 85 个测试用例
"""

from __future__ import annotations

import pytest
import time

from market_ops.creative_vision_runtime.growth_runtime.agent.ua_agent import (
    # E14.3 existing
    UAGrowthAgent,
    UAMetrics,
    UAAnalyzer,
    UADiagnosis,
    DiagnosisType,
    DiagnosisSeverity,
    UAStrategy,
    StrategyType,
    UAActionSelector,
    UAMemory,
    UADecisionRecord,
    DecisionOutcome,
    ExperienceEntry,
    GrowthRecommendation,
    UAAgentState,
    create_ua_agent,
    # E14.3.1 feedback
    UAActionOutcome,
    FeedbackBatch,
    FeedbackCollector,
    create_feedback_collector,
    # E14.3.1 evaluation
    EvaluationResult,
    EvaluationBatch,
    RewardCalculator,
    OutcomeEvaluator,
    RewardConfig,
    DEFAULT_REWARD_CONFIG,
    create_reward_calculator,
    create_outcome_evaluator,
    # E14.3.1 learning
    LearningResult,
    FeedbackLoopResult,
    FeedbackLoopBatch,
    LearningEngine,
    FeedbackLoop,
    create_feedback_loop,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def good_before():
    return {"roas": 1.3, "ltv": 4.5, "spend": 10000, "revenue": 13000, "cpi": 2.1, "ctr": 0.8, "cvr": 0.04, "payer_rate": 0.05, "d7_retention": 0.35}


@pytest.fixture
def good_after():
    return {"roas": 1.6, "ltv": 5.2, "spend": 10500, "revenue": 16800, "cpi": 1.9, "ctr": 0.9, "cvr": 0.045, "payer_rate": 0.06, "d7_retention": 0.38}


@pytest.fixture
def bad_after():
    return {"roas": 0.9, "ltv": 3.8, "spend": 12000, "revenue": 10800, "cpi": 2.8, "ctr": 0.6, "cvr": 0.03, "payer_rate": 0.03, "d7_retention": 0.28}


@pytest.fixture
def neutral_after():
    return {"roas": 1.32, "ltv": 4.55, "spend": 10100, "revenue": 13332, "cpi": 2.09, "ctr": 0.81, "cvr": 0.041, "payer_rate": 0.051, "d7_retention": 0.353}


@pytest.fixture
def collector():
    return FeedbackCollector()


@pytest.fixture
def reward_calc():
    return RewardCalculator()


@pytest.fixture
def evaluator():
    return OutcomeEvaluator()


@pytest.fixture
def memory():
    return UAMemory()


@pytest.fixture
def learner():
    return LearningEngine()


@pytest.fixture
def feedback_loop():
    return FeedbackLoop()


@pytest.fixture
def ua_agent():
    agent = create_ua_agent()
    return agent


# ═══════════════════════════════════════════════════════════════
# Test Feedback Models
# ═══════════════════════════════════════════════════════════════


class TestUAActionOutcome:
    """UAActionOutcome 模型测试."""

    def test_create_outcome_defaults(self):
        o = UAActionOutcome()
        assert o.outcome_id != ""
        assert o.action_id == ""
        assert o.reward == 0.0
        assert o.success is False
        assert o.observation_period_hours == 24

    def test_create_outcome_with_data(self):
        o = UAActionOutcome(
            action_id="act_001",
            action_type="generate_variants",
            target="campaign_p04",
            spend_delta=0.05,
            revenue_delta=0.29,
            roas_delta=0.23,
            ltv_delta=0.16,
            reward=0.45,
            success=True,
            observation_period_hours=48,
        )
        assert o.action_id == "act_001"
        assert o.roas_delta == 0.23
        assert o.reward == 0.45
        assert o.success is True
        assert o.observation_period_hours == 48

    def test_outcome_to_dict(self, good_before, good_after):
        o = UAActionOutcome(
            action_id="act_001",
            action_type="test",
            before_metrics=good_before,
            after_metrics=good_after,
            reward=0.5,
            success=True,
        )
        d = o.to_dict()
        assert d["outcome_id"] == o.outcome_id
        assert d["action_id"] == "act_001"
        assert d["reward"] == 0.5
        assert d["success"] is True
        assert "before_metrics" in d
        assert "after_metrics" in d

    def test_is_positive(self):
        o = UAActionOutcome(reward=0.3)
        assert o.is_positive is True
        o2 = UAActionOutcome(reward=-0.1)
        assert o2.is_positive is False

    def test_is_strong_positive(self):
        o = UAActionOutcome(reward=0.5)
        assert o.is_strong_positive is True
        o2 = UAActionOutcome(reward=0.3)
        assert o2.is_strong_positive is False

    def test_is_negative(self):
        o = UAActionOutcome(reward=-0.1)
        assert o.is_negative is True
        o2 = UAActionOutcome(reward=0.1)
        assert o2.is_negative is False

    def test_summary(self):
        o = UAActionOutcome(
            action_type="generate_variants",
            roas_delta=0.23,
            ltv_delta=0.16,
            reward=0.45,
            success=True,
        )
        s = o.summary
        assert "generate_variants" in s
        assert "ROAS" in s
        assert "reward" in s

    def test_outcome_observed_at(self):
        o = UAActionOutcome()
        assert o.observed_at != ""

    def test_outcome_metadata(self):
        o = UAActionOutcome(metadata={"source": "meta_ads", "platform": "ios"})
        assert o.metadata["source"] == "meta_ads"

    def test_feedback_batch_creation(self):
        outcomes = [UAActionOutcome(reward=0.5, success=True), UAActionOutcome(reward=-0.2, success=False)]
        batch = FeedbackBatch(outcomes=outcomes, total_reward=0.3, success_rate=0.5)
        assert batch.outcome_count == 2
        assert batch.total_reward == 0.3
        assert batch.success_rate == 0.5

    def test_feedback_batch_to_dict(self):
        batch = FeedbackBatch(outcomes=[UAActionOutcome()], total_reward=0.5, success_rate=1.0)
        d = batch.to_dict()
        assert d["outcome_count"] == 1
        assert d["total_reward"] == 0.5


# ═══════════════════════════════════════════════════════════════
# Test Feedback Collector
# ═══════════════════════════════════════════════════════════════


class TestFeedbackCollector:
    """FeedbackCollector 测试."""

    def test_collect_basic(self, collector, good_before, good_after):
        outcome = collector.collect(
            action_id="act_001",
            action_type="generate_variants",
            target="campaign_p04",
            before_metrics=good_before,
            after_metrics=good_after,
        )
        assert outcome.action_id == "act_001"
        assert outcome.action_type == "generate_variants"
        assert outcome.target == "campaign_p04"
        assert outcome.observation_period_hours == 24

    def test_collect_computes_deltas(self, collector, good_before, good_after):
        outcome = collector.collect(
            action_id="act_001",
            action_type="test",
            target="t",
            before_metrics=good_before,
            after_metrics=good_after,
        )
        # ROAS: 1.3 → 1.6 = +23.1%
        assert outcome.roas_delta == pytest.approx(0.230769, rel=0.1)
        # LTV: 4.5 → 5.2 = +15.6%
        assert outcome.ltv_delta == pytest.approx(0.155556, rel=0.1)
        # Spend: 10000 → 10500 = +5%
        assert outcome.spend_delta == pytest.approx(0.05, rel=0.1)

    def test_collect_negative_deltas(self, collector, good_before, bad_after):
        outcome = collector.collect(
            action_id="act_002",
            action_type="test",
            target="t",
            before_metrics=good_before,
            after_metrics=bad_after,
        )
        assert outcome.roas_delta < 0
        assert outcome.ltv_delta < 0

    def test_collect_zero_before(self, collector):
        outcome = collector.collect(
            action_id="act_003",
            action_type="test",
            target="t",
            before_metrics={},
            after_metrics={"roas": 1.5, "ltv": 4.0, "spend": 5000},
        )
        # When before is 0, delta = after value
        assert outcome.roas_delta == 1.5
        assert outcome.ltv_delta == 4.0
        assert outcome.spend_delta == 5000

    def test_collect_from_metrics(self, collector, good_before, good_after):
        before_m = UAMetrics(roas=1.3, ltv=4.5, spend=10000)
        after_m = UAMetrics(roas=1.6, ltv=5.2, spend=10500)
        outcome = collector.collect_from_metrics(
            action_id="act_001",
            action_type="test",
            target="t",
            before=before_m,
            after=after_m,
        )
        assert outcome.roas_delta > 0

    def test_collect_with_metadata(self, collector, good_before, good_after):
        outcome = collector.collect(
            action_id="act_001",
            action_type="test",
            target="t",
            before_metrics=good_before,
            after_metrics=good_after,
            metadata={"campaign": "p04", "platform": "meta"},
        )
        assert outcome.metadata["campaign"] == "p04"

    def test_collect_batch(self, collector, good_before, good_after, bad_after):
        actions = [
            {"action_id": "a1", "action_type": "t1", "target": "x"},
            {"action_id": "a2", "action_type": "t2", "target": "y"},
        ]
        pairs = [(good_before, good_after), (good_before, bad_after)]
        batch = collector.collect_batch(actions, pairs)
        assert len(batch.outcomes) == 2
        assert batch.outcomes[0].action_id == "a1"
        assert batch.outcomes[1].action_id == "a2"

    def test_collect_from_resolutions(self, collector, good_before, good_after):
        resolutions = [
            {
                "record_id": "r1",
                "action_id": "a1",
                "action_type": "test",
                "target": "x",
                "before_metrics": good_before,
                "after_metrics": good_after,
            }
        ]
        batch = collector.collect_from_resolutions(resolutions)
        assert len(batch.outcomes) == 1

    def test_delta_summary(self, collector, good_before, good_after):
        outcome = collector.collect("a1", "test", "t", good_before, good_after)
        summary = collector.get_delta_summary(outcome)
        assert "roas_delta" in summary
        assert "ltv_delta" in summary
        assert "spend_delta" in summary

    def test_delta_summary_batch(self, collector, good_before, good_after):
        batch = collector.collect_batch(
            [{"action_id": "a1", "action_type": "t", "target": "x"}],
            [(good_before, good_after)],
        )
        summary = collector.get_delta_summary_batch(batch)
        assert "roas_delta" in summary
        assert "ltv_delta" in summary


# ═══════════════════════════════════════════════════════════════
# Test Reward Calculator
# ═══════════════════════════════════════════════════════════════


class TestRewardCalculator:
    """RewardCalculator 测试."""

    def test_calculate_positive(self, reward_calc, collector, good_before, good_after):
        outcome = collector.collect("a1", "test", "t", good_before, good_after)
        reward = reward_calc.calculate(outcome)
        # ROAS +23%, LTV +16%, spend +5% → should be positive
        assert reward > 0

    def test_calculate_negative(self, reward_calc, collector, good_before, bad_after):
        outcome = collector.collect("a1", "test", "t", good_before, bad_after)
        reward = reward_calc.calculate(outcome)
        # ROAS -31%, LTV -16%, spend +20% → should be negative
        assert reward < 0

    def test_calculate_neutral(self, reward_calc, collector, good_before, neutral_after):
        outcome = collector.collect("a1", "test", "t", good_before, neutral_after)
        reward = reward_calc.calculate(outcome)
        # Near-zero changes → should be near zero
        assert abs(reward) < 0.2

    def test_calculate_clamped(self, reward_calc):
        # Extreme values should be clamped to [-1, 1]
        outcome = UAActionOutcome(roas_delta=10.0, ltv_delta=10.0, spend_delta=-5.0)
        reward = reward_calc.calculate(outcome)
        assert -1.0 <= reward <= 1.0

    def test_calculate_roas_weight(self, good_before, good_after):
        # Higher ROAS weight should give higher reward
        calc_default = RewardCalculator()
        calc_roas = RewardCalculator(RewardConfig(roas_weight=0.8, ltv_weight=0.1, spend_risk_weight=0.1))
        collector = FeedbackCollector()
        outcome = collector.collect("a1", "test", "t", good_before, good_after)
        r_default = calc_default.calculate(outcome)
        r_roas = calc_roas.calculate(outcome)
        assert r_roas > r_default  # ROAS-heavy config should give higher reward for ROAS improvement

    def test_calculate_from_dicts(self, reward_calc, good_before, good_after):
        reward = reward_calc.calculate_from_dicts(good_before, good_after)
        assert reward > 0

    def test_calculate_batch(self, reward_calc, collector, good_before, good_after, bad_after):
        o1 = collector.collect("a1", "t", "x", good_before, good_after)
        o2 = collector.collect("a2", "t", "x", good_before, bad_after)
        rewards = reward_calc.calculate_batch([o1, o2])
        assert len(rewards) == 2
        assert rewards[0] > rewards[1]

    def test_reward_config_defaults(self):
        config = RewardConfig()
        assert config.roas_weight == 0.5
        assert config.ltv_weight == 0.3
        assert config.spend_risk_weight == 0.2
        assert config.success_threshold == 0.3

    def test_reward_config_custom(self):
        config = RewardConfig(roas_weight=0.6, success_threshold=0.4)
        assert config.roas_weight == 0.6
        assert config.success_threshold == 0.4

    def test_reward_history(self, reward_calc, collector, good_before, good_after):
        outcome = collector.collect("a1", "test", "t", good_before, good_after)
        reward_calc.calculate(outcome)
        reward_calc.calculate(outcome)
        history = reward_calc.get_history()
        assert len(history) == 2

    def test_reward_avg(self, reward_calc, collector, good_before, good_after):
        outcome = collector.collect("a1", "test", "t", good_before, good_after)
        reward_calc.calculate(outcome)
        avg = reward_calc.get_avg_reward()
        assert avg > 0


# ═══════════════════════════════════════════════════════════════
# Test Outcome Evaluator
# ═══════════════════════════════════════════════════════════════


class TestOutcomeEvaluator:
    """OutcomeEvaluator 测试."""

    def test_evaluate_success(self, evaluator, collector, good_before, good_after):
        outcome = collector.collect("a1", "test", "t", good_before, good_after)
        calc = RewardCalculator()
        reward = calc.calculate(outcome)
        result = evaluator.evaluate(outcome, reward)
        assert result.decision_outcome == DecisionOutcome.SUCCESS
        assert result.confidence_adjustment > 0

    def test_evaluate_failure(self, evaluator, collector, good_before, bad_after):
        outcome = collector.collect("a1", "test", "t", good_before, bad_after)
        calc = RewardCalculator()
        reward = calc.calculate(outcome)
        result = evaluator.evaluate(outcome, reward)
        assert result.decision_outcome == DecisionOutcome.FAILURE
        assert result.confidence_adjustment < 0

    def test_evaluate_partial(self, evaluator):
        # Partial: reward between 0.05 and 0.3
        outcome = UAActionOutcome()
        result = evaluator.evaluate(outcome, reward=0.15)
        assert result.decision_outcome == DecisionOutcome.PARTIAL

    def test_evaluate_neutral(self, evaluator):
        outcome = UAActionOutcome()
        result = evaluator.evaluate(outcome, reward=0.01)
        assert result.decision_outcome == DecisionOutcome.PENDING

    def test_confidence_adjustment_strong(self, evaluator):
        outcome = UAActionOutcome()
        result = evaluator.evaluate(outcome, reward=0.8)
        assert result.confidence_adjustment == 0.15

    def test_confidence_adjustment_medium(self, evaluator):
        outcome = UAActionOutcome()
        result = evaluator.evaluate(outcome, reward=0.4)
        assert result.confidence_adjustment == 0.10

    def test_confidence_adjustment_negative(self, evaluator):
        outcome = UAActionOutcome()
        result = evaluator.evaluate(outcome, reward=-0.5)
        assert result.confidence_adjustment == -0.10

    def test_evaluate_explanation(self, evaluator, collector, good_before, good_after):
        outcome = collector.collect("a1", "test", "t", good_before, good_after)
        calc = RewardCalculator()
        reward = calc.calculate(outcome)
        result = evaluator.evaluate(outcome, reward)
        assert "ROAS" in result.explanation
        assert "LTV" in result.explanation

    def test_evaluate_batch(self, evaluator, collector, good_before, good_after, bad_after):
        o1 = collector.collect("a1", "t", "x", good_before, good_after)
        o2 = collector.collect("a2", "t", "x", good_before, bad_after)
        batch = evaluator.evaluate_batch([o1, o2])
        assert len(batch.results) == 2
        assert batch.result_count == 2

    def test_evaluate_from_feedback_batch(self, evaluator, collector, good_before, good_after):
        actions = [{"action_id": "a1", "action_type": "t", "target": "x"}]
        pairs = [(good_before, good_after)]
        fb = collector.collect_batch(actions, pairs)
        batch = evaluator.evaluate_from_feedback_batch(fb)
        assert batch.result_count == 1

    def test_evaluator_stats(self, evaluator, collector, good_before, good_after):
        outcome = collector.collect("a1", "test", "t", good_before, good_after)
        calc = RewardCalculator()
        reward = calc.calculate(outcome)
        evaluator.evaluate(outcome, reward)
        stats = evaluator.stats()
        assert stats["total"] == 1
        assert stats["success"] == 1


# ═══════════════════════════════════════════════════════════════
# Test Learning Engine
# ═══════════════════════════════════════════════════════════════


class TestLearningEngine:
    """LearningEngine 测试."""

    def test_learn_from_success(self, learner, collector, good_before, good_after, memory):
        evaluator = OutcomeEvaluator()
        outcome = collector.collect("a1", "generate_variants", "x", good_before, good_after)
        calc = RewardCalculator()
        reward = calc.calculate(outcome)
        evaluation = evaluator.evaluate(outcome, reward)

        result = learner.learn(
            outcome=outcome,
            evaluation=evaluation,
            memory=memory,
            diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
            strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
        )
        assert result.confidence_adjustment > 0
        assert result.learning_summary != ""

    def test_learn_from_failure(self, learner, collector, good_before, bad_after, memory):
        evaluator = OutcomeEvaluator()
        outcome = collector.collect("a1", "test", "x", good_before, bad_after)
        calc = RewardCalculator()
        reward = calc.calculate(outcome)
        evaluation = evaluator.evaluate(outcome, reward)

        result = learner.learn(
            outcome=outcome,
            evaluation=evaluation,
            memory=memory,
        )
        assert result.confidence_adjustment < 0

    def test_learn_updates_memory(self, learner, collector, good_before, good_after, memory):
        # Record a decision first
        record = memory.record_decision(
            diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
            strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
            action_type="generate_variants",
            before_metrics=good_before,
        )

        evaluator = OutcomeEvaluator()
        outcome = collector.collect("a1", "generate_variants", "x", good_before, good_after)
        calc = RewardCalculator()
        reward = calc.calculate(outcome)
        evaluation = evaluator.evaluate(outcome, reward)

        learner.learn(
            outcome=outcome,
            evaluation=evaluation,
            memory=memory,
            diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
            strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
            record_id=record.record_id,
        )

        # Check record was resolved
        resolved = memory.get_record(record.record_id)
        assert resolved.is_resolved
        assert resolved.is_success

    def test_learn_with_record_id(self, learner, collector, good_before, good_after, memory):
        record = memory.record_decision(
            diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
            strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
            action_type="generate_variants",
            before_metrics=good_before,
        )
        evaluator = OutcomeEvaluator()
        outcome = collector.collect("a1", "generate_variants", "x", good_before, good_after)
        calc = RewardCalculator()
        reward = calc.calculate(outcome)
        evaluation = evaluator.evaluate(outcome, reward)

        result = learner.learn(
            outcome=outcome,
            evaluation=evaluation,
            memory=memory,
            record_id=record.record_id,
        )
        assert memory.get_record(record.record_id).is_resolved

    def test_learn_accumulates_experience(self, learner, collector, good_before, good_after, memory):
        evaluator = OutcomeEvaluator()
        outcome = collector.collect("a1", "generate_variants", "x", good_before, good_after)
        calc = RewardCalculator()
        reward = calc.calculate(outcome)
        evaluation = evaluator.evaluate(outcome, reward)

        for _ in range(3):
            learner.learn(
                outcome=outcome,
                evaluation=evaluation,
                memory=memory,
                diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
                strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
            )

        exps = memory.get_experiences(diagnosis_type=DiagnosisType.CREATIVE_FATIGUE)
        found = [e for e in exps if e.action_type == "generate_variants"]
        assert len(found) > 0
        assert found[0].total_count >= 3

    def test_learn_from_dicts(self, learner, memory):
        result = learner.learn_from_dicts(
            outcome_data={"action_id": "a1", "action_type": "test", "roas_delta": 0.2, "ltv_delta": 0.1, "spend_delta": 0.05},
            evaluation_data={"reward": 0.4, "decision_outcome": DecisionOutcome.SUCCESS, "confidence_adjustment": 0.1},
            memory=memory,
        )
        assert result.confidence_adjustment == pytest.approx(0.033, rel=0.1)  # scaled by min_samples (1/3)

    def test_learning_history(self, learner, collector, good_before, good_after, memory):
        evaluator = OutcomeEvaluator()
        outcome = collector.collect("a1", "test", "x", good_before, good_after)
        calc = RewardCalculator()
        reward = calc.calculate(outcome)
        evaluation = evaluator.evaluate(outcome, reward)

        learner.learn(outcome=outcome, evaluation=evaluation, memory=memory)
        learner.learn(outcome=outcome, evaluation=evaluation, memory=memory)
        assert len(learner.get_history()) == 2

    def test_learner_improved_count(self, learner, collector, good_before, good_after, bad_after, memory):
        evaluator = OutcomeEvaluator()
        o1 = collector.collect("a1", "test", "x", good_before, good_after)
        o2 = collector.collect("a2", "test", "x", good_before, bad_after)
        calc = RewardCalculator()

        learner.learn(outcome=o1, evaluation=evaluator.evaluate(o1, calc.calculate(o1)), memory=memory)
        learner.learn(outcome=o2, evaluation=evaluator.evaluate(o2, calc.calculate(o2)), memory=memory)

        assert learner.get_improved_count() >= 1
        assert learner.get_degraded_count() >= 1

    def test_learner_reset(self, learner, collector, good_before, good_after, memory):
        evaluator = OutcomeEvaluator()
        outcome = collector.collect("a1", "test", "x", good_before, good_after)
        calc = RewardCalculator()
        reward = calc.calculate(outcome)
        evaluation = evaluator.evaluate(outcome, reward)
        learner.learn(outcome=outcome, evaluation=evaluation, memory=memory)

        learner.reset()
        assert len(learner.get_history()) == 0


# ═══════════════════════════════════════════════════════════════
# Test Feedback Loop
# ═══════════════════════════════════════════════════════════════


class TestFeedbackLoop:
    """FeedbackLoop 完整闭环测试."""

    def test_run_success(self, feedback_loop, good_before, good_after, memory):
        result = feedback_loop.run(
            action_id="act_001",
            action_type="generate_variants",
            target="campaign_p04",
            before_metrics=good_before,
            after_metrics=good_after,
            memory=memory,
            diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
            strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
        )
        assert result.outcome is not None
        assert result.evaluation is not None
        assert result.learning is not None
        assert result.evaluation.reward > 0
        assert result.improved is True

    def test_run_failure(self, feedback_loop, good_before, bad_after, memory):
        result = feedback_loop.run(
            action_id="act_002",
            action_type="adjust_bid",
            target="campaign_p04",
            before_metrics=good_before,
            after_metrics=bad_after,
            memory=memory,
        )
        assert result.evaluation.reward < 0
        assert result.improved is False

    def test_run_neutral(self, feedback_loop, good_before, neutral_after, memory):
        result = feedback_loop.run(
            action_id="act_003",
            action_type="monitor_only",
            target="campaign_p04",
            before_metrics=good_before,
            after_metrics=neutral_after,
            memory=memory,
        )
        assert abs(result.evaluation.reward) < 0.2

    def test_run_updates_memory(self, feedback_loop, good_before, good_after, memory):
        # First record a decision
        record = memory.record_decision(
            diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
            strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
            action_type="generate_variants",
            before_metrics=good_before,
        )

        result = feedback_loop.run(
            action_id="act_001",
            action_type="generate_variants",
            target="x",
            before_metrics=good_before,
            after_metrics=good_after,
            memory=memory,
            diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
            strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
            record_id=record.record_id,
        )

        resolved = memory.get_record(record.record_id)
        assert resolved.is_resolved
        assert resolved.is_success

    def test_run_returns_recommendation(self, feedback_loop, good_before, good_after, memory):
        result = feedback_loop.run(
            action_id="act_001",
            action_type="generate_variants",
            target="x",
            before_metrics=good_before,
            after_metrics=good_after,
            memory=memory,
        )
        assert result.recommendation != ""

    def test_run_batch(self, feedback_loop, good_before, good_after, bad_after, memory):
        actions = [
            {"action_id": "a1", "action_type": "t1", "target": "x"},
            {"action_id": "a2", "action_type": "t2", "target": "y"},
        ]
        pairs = [(good_before, good_after), (good_before, bad_after)]
        batch = feedback_loop.run_batch(actions, pairs, memory)
        assert len(batch.results) == 2
        assert batch.improved_count >= 1

    def test_run_from_resolutions(self, feedback_loop, good_before, good_after, memory):
        record = memory.record_decision(
            diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
            strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
            action_type="generate_variants",
            action_target="x",
            before_metrics=good_before,
        )
        resolutions = [{
            "record_id": record.record_id,
            "action_id": record.record_id,
            "action_type": "generate_variants",
            "action_target": "x",
            "target": "x",
            "diagnosis_type": "creative_fatigue",
            "strategy_type": "generate_creative_variants",
            "before_metrics": good_before,
            "after_metrics": good_after,
        }]
        batch = feedback_loop.run_from_resolutions(resolutions, memory)
        assert len(batch.results) == 1

    def test_loop_history(self, feedback_loop, good_before, good_after, memory):
        feedback_loop.run(
            action_id="a1", action_type="test", target="x",
            before_metrics=good_before, after_metrics=good_after, memory=memory,
        )
        feedback_loop.run(
            action_id="a2", action_type="test", target="x",
            before_metrics=good_before, after_metrics=good_after, memory=memory,
        )
        assert len(feedback_loop.get_history()) == 2

    def test_loop_improvement_rate(self, feedback_loop, good_before, good_after, memory):
        for i in range(5):
            feedback_loop.run(
                action_id=f"a{i}", action_type="test", target="x",
                before_metrics=good_before, after_metrics=good_after, memory=memory,
            )
        rate = feedback_loop.get_improvement_rate()
        assert rate > 0.5

    def test_loop_avg_reward(self, feedback_loop, good_before, good_after, memory):
        feedback_loop.run(
            action_id="a1", action_type="test", target="x",
            before_metrics=good_before, after_metrics=good_after, memory=memory,
        )
        avg = feedback_loop.get_avg_reward()
        assert avg > 0

    def test_loop_stats(self, feedback_loop, good_before, good_after, memory):
        feedback_loop.run(
            action_id="a1", action_type="test", target="x",
            before_metrics=good_before, after_metrics=good_after, memory=memory,
        )
        stats = feedback_loop.stats()
        assert stats["total_loops"] == 1
        assert stats["improvement_rate"] > 0

    def test_loop_reset(self, feedback_loop, good_before, good_after, memory):
        feedback_loop.run(
            action_id="a1", action_type="test", target="x",
            before_metrics=good_before, after_metrics=good_after, memory=memory,
        )
        feedback_loop.reset()
        assert len(feedback_loop.get_history()) == 0
        assert feedback_loop.stats()["total_loops"] == 0


# ═══════════════════════════════════════════════════════════════
# Test UA Agent Feedback Integration
# ═══════════════════════════════════════════════════════════════


class TestUAGrowthAgentFeedback:
    """UA Agent 反馈闭环集成测试."""

    def test_evaluate_outcome(self, ua_agent, good_before, good_after):
        result = ua_agent.evaluate_outcome(
            action_id="act_001",
            action_type="generate_variants",
            target="campaign_p04",
            before_metrics=good_before,
            after_metrics=good_after,
            diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
            strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
        )
        assert result.outcome is not None
        assert result.evaluation is not None
        assert result.evaluation.reward > 0

    def test_evaluate_outcome_failure(self, ua_agent, good_before, bad_after):
        result = ua_agent.evaluate_outcome(
            action_id="act_002",
            action_type="adjust_bid",
            target="x",
            before_metrics=good_before,
            after_metrics=bad_after,
        )
        assert result.evaluation.reward < 0

    def test_evaluate_outcome_state_transition(self, ua_agent, good_before, good_after):
        assert ua_agent.state == UAAgentState.IDLE
        ua_agent.evaluate_outcome(
            action_id="act_001", action_type="test", target="x",
            before_metrics=good_before, after_metrics=good_after,
        )
        assert ua_agent.state == UAAgentState.IDLE

    def test_run_feedback_loop(self, ua_agent, good_before, good_after):
        result = ua_agent.run_feedback_loop(
            action_id="act_001", action_type="test", target="x",
            before_metrics=good_before, after_metrics=good_after,
        )
        assert result.improved is True

    def test_collect_feedback(self, ua_agent, good_before, good_after):
        outcome = ua_agent.collect_feedback(
            action_id="act_001", action_type="test", target="x",
            before_metrics=good_before, after_metrics=good_after,
        )
        assert isinstance(outcome, UAActionOutcome)
        assert outcome.roas_delta > 0

    def test_evaluate_pending_decisions(self, ua_agent, good_before, good_after):
        # First, analyze to create a decision record
        ua_agent.analyze_metrics({
            "spend": 10000, "revenue": 13000, "roas": 1.3,
            "cpi": 2.1, "ctr": 0.8, "fatigue": 0.72, "frequency": 4.5,
        })

        # Get pending records
        pending = ua_agent.get_memory().get_pending()
        assert len(pending) > 0

        # Build after_metrics_map
        after_map = {}
        for r in pending:
            after_map[r.record_id] = good_after

        batch = ua_agent.evaluate_pending_decisions(after_map)
        assert batch.result_count > 0

    def test_evaluate_outcome_from_records(self, ua_agent, good_before, good_after):
        record = ua_agent.get_memory().record_decision(
            diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
            strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
            action_type="generate_variants",
            action_target="x",
            before_metrics=good_before,
        )

        result = ua_agent.evaluate_outcome_from_records(
            before_metrics=good_before,
            after_metrics=good_after,
            record_id=record.record_id,
        )
        assert result.evaluation is not None
        assert result.evaluation.reward > 0

    def test_evaluate_outcome_from_records_not_found(self, ua_agent, good_before, good_after):
        result = ua_agent.evaluate_outcome_from_records(
            before_metrics=good_before,
            after_metrics=good_after,
            record_id="nonexistent",
        )
        assert result.recommendation == "决策记录未找到"

    def test_feedback_loop_stats(self, ua_agent, good_before, good_after):
        ua_agent.evaluate_outcome(
            action_id="act_001", action_type="test", target="x",
            before_metrics=good_before, after_metrics=good_after,
        )
        stats = ua_agent.get_feedback_loop_stats()
        assert stats["total_loops"] >= 1

    def test_feedback_history(self, ua_agent, good_before, good_after):
        ua_agent.evaluate_outcome(
            action_id="act_001", action_type="test", target="x",
            before_metrics=good_before, after_metrics=good_after,
        )
        history = ua_agent.get_feedback_history()
        assert len(history) >= 1

    def test_get_feedback_loop(self, ua_agent):
        loop = ua_agent.get_feedback_loop()
        assert isinstance(loop, FeedbackLoop)

    def test_get_feedback_collector(self, ua_agent):
        collector = ua_agent.get_feedback_collector()
        assert isinstance(collector, FeedbackCollector)

    def test_feedback_loop_in_agent_stats(self, ua_agent):
        stats = ua_agent.stats()
        assert "feedback_loop" in stats

    def test_full_analyze_then_evaluate_cycle(self, ua_agent, good_before, good_after):
        """完整闭环: Analyze → Execute → Evaluate."""
        # Step 1: Analyze (creates decision records)
        rec = ua_agent.analyze_metrics({
            "spend": 10000, "revenue": 13000, "roas": 1.3,
            "cpi": 2.1, "ctr": 0.8, "fatigue": 0.72, "frequency": 4.5,
        })
        assert rec is not None
        assert len(rec.diagnoses) > 0

        # Step 2: Evaluate outcome (simulating 24h later)
        result = ua_agent.evaluate_outcome(
            action_id="act_feedback",
            action_type="generate_variants",
            target="campaign_p04",
            before_metrics=good_before,
            after_metrics=good_after,
            diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
            strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
        )
        assert result.improved is True

        # Step 3: Verify memory updated
        assert len(ua_agent.get_feedback_history()) >= 1

    def test_multiple_feedback_cycles(self, ua_agent, good_before, good_after):
        """多次反馈闭环."""
        for i in range(5):
            ua_agent.evaluate_outcome(
                action_id=f"act_{i:03d}",
                action_type="generate_variants",
                target="campaign_p04",
                before_metrics=good_before,
                after_metrics=good_after,
                diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
                strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
            )

        stats = ua_agent.get_feedback_loop_stats()
        assert stats["total_loops"] == 5
        assert stats["improvement_rate"] > 0.5


# ═══════════════════════════════════════════════════════════════
# Test Integration & E2E
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """E2E 集成测试."""

    def test_full_decision_feedback_loop(self, ua_agent, good_before, good_after):
        """完整决策→执行→反馈闭环."""
        # Phase 1: Decision
        rec = ua_agent.quick_analysis(
            spend=10000, revenue=13000, roas=1.3,
            cpi=2.1, ctr=0.8, cvr=0.04, ltv=4.5,
            fatigue=0.72, frequency=4.5,
            campaign_id="p04",
        )
        assert len(rec.diagnoses) > 0  # Should detect issues

        # Phase 2: Feedback (simulating 24h after execution)
        result = ua_agent.evaluate_outcome(
            action_id="act_after_analysis",
            action_type="generate_variants",
            target="p04",
            before_metrics=good_before,
            after_metrics=good_after,
            diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
            strategy_type=StrategyType.GENERATE_CREATIVE_VARIANTS,
        )
        assert result.improved is True

        # Phase 3: Re-analyze (should have higher confidence due to experience)
        rec2 = ua_agent.quick_analysis(
            spend=10000, revenue=13000, roas=1.3,
            cpi=2.1, ctr=0.8, cvr=0.04, ltv=4.5,
            fatigue=0.72, frequency=4.5,
            campaign_id="p04",
        )
        assert rec2 is not None  # Should still work

    def test_agent_reset_clears_feedback(self, ua_agent, good_before, good_after):
        ua_agent.evaluate_outcome(
            action_id="act_001", action_type="test", target="x",
            before_metrics=good_before, after_metrics=good_after,
        )
        assert len(ua_agent.get_feedback_history()) >= 1

        ua_agent.reset()
        assert len(ua_agent.get_feedback_history()) == 0
        assert ua_agent.get_feedback_loop_stats()["total_loops"] == 0

    def test_factory_functions(self):
        collector = create_feedback_collector()
        assert isinstance(collector, FeedbackCollector)

        calc = create_reward_calculator()
        assert isinstance(calc, RewardCalculator)

        evaluator = create_outcome_evaluator()
        assert isinstance(evaluator, OutcomeEvaluator)

        loop = create_feedback_loop()
        assert isinstance(loop, FeedbackLoop)

    def test_custom_reward_config(self, good_before, bad_after):
        config = RewardConfig(roas_weight=0.7, ltv_weight=0.2, spend_risk_weight=0.1)
        calc = RewardCalculator(config)
        collector = FeedbackCollector()
        outcome = collector.collect("a1", "test", "x", good_before, bad_after)
        reward = calc.calculate(outcome)
        assert isinstance(reward, float)

    def test_learning_result_model(self):
        r = LearningResult(confidence_adjustment=0.15, learning_summary="test")
        d = r.to_dict()
        assert d["confidence_adjustment"] == 0.15
        assert d["learning_summary"] == "test"

    def test_feedback_loop_result_model(self):
        r = FeedbackLoopResult(
            action_id="act_001",
            improved=True,
            recommendation="test recommendation",
        )
        d = r.to_dict()
        assert d["action_id"] == "act_001"
        assert d["improved"] is True
        assert d["recommendation"] == "test recommendation"

    def test_feedback_loop_batch_model(self):
        batch = FeedbackLoopBatch(
            improved_count=5,
            total_confidence_adjustment=0.5,
            avg_reward=0.3,
        )
        d = batch.to_dict()
        assert d["improved_count"] == 5
        assert d["total_confidence_adjustment"] == 0.5
        assert d["avg_reward"] == 0.3

    def test_evaluation_batch_model(self):
        batch = EvaluationBatch(avg_reward=0.5, success_rate=0.8)
        d = batch.to_dict()
        assert d["avg_reward"] == 0.5
        assert d["success_rate"] == 0.8

    def test_evaluation_result_model(self):
        r = EvaluationResult(
            outcome_id="o1",
            reward=0.45,
            decision_outcome=DecisionOutcome.SUCCESS,
            confidence_adjustment=0.1,
            explanation="test",
        )
        d = r.to_dict()
        assert d["reward"] == 0.45
        assert d["decision_outcome"] == "success"
        assert d["confidence_adjustment"] == 0.1

    def test_reward_config_to_dict(self):
        config = RewardConfig(roas_weight=0.6)
        d = config.to_dict()
        assert d["roas_weight"] == 0.6
        assert d["ltv_weight"] == 0.3