"""E15.3.2 Autonomous Decision Loop 测试 — 完整测试.

测试覆盖:
  - Cycle Model (20 tests)
  - State Machine (20 tests)
  - Goal Evaluation (15 tests)
  - Opportunity Detection (15 tests)
  - Planner Bridge (10 tests)
  - Executor Bridge (10 tests)
  - Learning Feedback (15 tests)
  - Full Loop Integration (20 tests)

总计: 125+ tests
"""

from __future__ import annotations

import time
import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.operator.decision_loop.models import (
    AnomalySignal,
    CycleOutcome,
    CycleResult,
    CycleState,
    CycleSummary,
    DecisionCycle,
    EnvironmentState,
    GoalEvaluation,
    GoalHealth,
    OpportunitySignal,
    TrendSignal,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.operator.decision_loop.state_machine import (
    CycleStateMachine,
    FORBIDDEN_TRANSITIONS,
    VALID_TRANSITIONS,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.operator.decision_loop.evaluator import (
    GoalEvaluator,
    OpportunityEvaluator,
    PerformanceEvaluator,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.operator.decision_loop.planner_bridge import (
    PlannerBridge,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.operator.decision_loop.executor_bridge import (
    ExecutorBridge,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.operator.decision_loop.learner import (
    Learner,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.operator.decision_loop.loop import (
    AutonomousDecisionLoop,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_cycle() -> DecisionCycle:
    return DecisionCycle(
        operator_id="op_test",
        cycle_number=1,
    )


@pytest.fixture
def sample_environment() -> EnvironmentState:
    return EnvironmentState(
        metrics={"roas": 0.65, "ctr": 2.1, "spend": 2500, "revenue": 1800},
        anomalies=[
            AnomalySignal(
                metric="ctr",
                current=2.8,
                baseline=2.1,
                deviation=0.35,
                severity="medium",
                description="CTR above baseline",
            )
        ],
        trends=[
            TrendSignal(
                metric="roas",
                direction="down",
                strength=0.7,
                consecutive_periods=3,
            )
        ],
        opportunities=[
            OpportunitySignal(
                name="Creative A CTR Boost",
                type="SCALE_WINNER_CREATIVE",
                confidence=0.86,
                description="CTR +40% above baseline",
                impacted_metrics=["ctr", "roas"],
                estimated_impact={"ctr": 0.4, "roas": 0.2},
            )
        ],
        risks=["budget_overspend", "creative_fatigue"],
    )


@pytest.fixture
def sample_goals() -> list[dict]:
    return [
        {
            "goal_id": "g1",
            "name": "Increase ROAS",
            "metric": "roas",
            "target": 0.8,
            "direction": "above",
            "priority": "high",
        },
        {
            "goal_id": "g2",
            "name": "Reduce Spend",
            "metric": "spend",
            "target": 500.0,
            "direction": "below",
            "priority": "medium",
        },
    ]


@pytest.fixture
def sample_metrics() -> dict[str, float]:
    return {"roas": 0.55, "ctr": 2.1, "spend": 600, "revenue": 1500, "cvr": 0.03}


@pytest.fixture
def decision_loop() -> AutonomousDecisionLoop:
    loop = AutonomousDecisionLoop(operator_id="test_op")
    loop.setup_goals([
        {"name": "Increase ROAS", "metric": "roas", "target": 0.8, "direction": "above", "priority": "high"},
        {"name": "Reduce Spend", "metric": "spend", "target": 500.0, "direction": "below", "priority": "medium"},
    ])
    loop.setup_environment(
        metrics={"roas": 0.65, "ctr": 2.1, "spend": 2500, "revenue": 1800},
    )
    return loop


# ═══════════════════════════════════════════════════════════════════
# 1. Cycle Model Tests (20 tests)
# ═══════════════════════════════════════════════════════════════════


class TestCycleModel:
    """决策周期模型测试."""

    def test_create_cycle_defaults(self):
        cycle = DecisionCycle()
        assert cycle.cycle_id != ""
        assert cycle.state == CycleState.CREATED
        assert cycle.cycle_number == 0
        assert cycle.operator_id == ""

    def test_create_cycle_with_params(self):
        cycle = DecisionCycle(
            operator_id="op_001",
            cycle_number=5,
        )
        assert cycle.operator_id == "op_001"
        assert cycle.cycle_number == 5

    def test_cycle_state_enum_values(self):
        assert CycleState.CREATED.value == "created"
        assert CycleState.OBSERVING.value == "observing"
        assert CycleState.ANALYZING.value == "analyzing"
        assert CycleState.PLANNING.value == "planning"
        assert CycleState.DECIDING.value == "deciding"
        assert CycleState.EXECUTING.value == "executing"
        assert CycleState.EVALUATING.value == "evaluating"
        assert CycleState.LEARNING.value == "learning"
        assert CycleState.COMPLETED.value == "completed"
        assert CycleState.FAILED.value == "failed"
        assert CycleState.PAUSED.value == "paused"

    def test_cycle_state_count(self):
        assert len(CycleState) == 11

    def test_cycle_duration_seconds(self, sample_cycle):
        assert sample_cycle.duration_seconds() == 0.0  # not completed

    def test_cycle_duration_with_completion(self, sample_cycle):
        from datetime import datetime, timedelta, timezone
        start = datetime.now(timezone.utc) - timedelta(seconds=5)
        sample_cycle.started_at = start.isoformat()
        sample_cycle.completed_at = datetime.now(timezone.utc).isoformat()
        duration = sample_cycle.duration_seconds()
        assert duration > 0

    def test_cycle_to_dict(self, sample_cycle):
        d = sample_cycle.to_dict()
        assert d["cycle_id"] == sample_cycle.cycle_id
        assert d["state"] == "created"
        assert d["cycle_number"] == 1
        assert "duration_seconds" in d

    def test_cycle_metadata(self):
        cycle = DecisionCycle(metadata={"source": "test", "version": "1.0"})
        assert cycle.metadata["source"] == "test"
        assert cycle.metadata["version"] == "1.0"

    def test_cycle_environment_state(self, sample_environment):
        cycle = DecisionCycle(environment_state=sample_environment)
        assert cycle.environment_state is not None
        assert cycle.environment_state.metrics["roas"] == 0.65

    def test_cycle_goal_evaluations(self):
        evals = [
            GoalEvaluation(goal_id="g1", health=GoalHealth.BEHIND, gap=0.25),
            GoalEvaluation(goal_id="g2", health=GoalHealth.ON_TRACK, gap=0.03),
        ]
        cycle = DecisionCycle(goal_evaluations=evals)
        assert len(cycle.goal_evaluations) == 2
        assert cycle.goal_evaluations[0].health == GoalHealth.BEHIND

    def test_cycle_candidate_actions(self):
        actions = [
            {"action_type": "increase_budget", "confidence": 0.8},
            {"action_type": "replace_creative", "confidence": 0.6},
        ]
        cycle = DecisionCycle(candidate_actions=actions)
        assert len(cycle.candidate_actions) == 2

    def test_cycle_selected_action(self):
        cycle = DecisionCycle(
            selected_action={"action_type": "increase_budget", "amount": 0.2}
        )
        assert cycle.selected_action["action_type"] == "increase_budget"

    def test_cycle_risk_assessments(self):
        cycle = DecisionCycle(
            risk_assessments=[
                {"risk_score": 0.15, "level": "low"},
                {"risk_score": 0.45, "level": "medium"},
            ]
        )
        assert len(cycle.risk_assessments) == 2

    def test_cycle_execution_result(self):
        cycle = DecisionCycle(
            execution_result={"status": "executed", "action_type": "increase_budget"}
        )
        assert cycle.execution_result["status"] == "executed"

    def test_cycle_reward(self):
        cycle = DecisionCycle(reward=0.76)
        assert cycle.reward == 0.76

    def test_cycle_error(self):
        cycle = DecisionCycle(error="Connection timeout")
        assert cycle.error == "Connection timeout"

    def test_goal_health_enum(self):
        assert GoalHealth.ON_TRACK.value == "on_track"
        assert GoalHealth.BEHIND.value == "behind"
        assert GoalHealth.AHEAD.value == "ahead"
        assert GoalHealth.ACHIEVED.value == "achieved"
        assert GoalHealth.FAILED.value == "failed"

    def test_cycle_outcome_enum(self):
        assert CycleOutcome.SUCCESS.value == "success"
        assert CycleOutcome.PARTIAL.value == "partial"
        assert CycleOutcome.FAILURE.value == "failure"
        assert CycleOutcome.NO_ACTION.value == "no_action"
        assert CycleOutcome.ERROR.value == "error"

    def test_environment_state_to_dict(self, sample_environment):
        d = sample_environment.to_dict()
        assert d["metrics"]["roas"] == 0.65
        assert len(d["anomalies"]) == 1
        assert len(d["trends"]) == 1
        assert len(d["opportunities"]) == 1
        assert "budget_overspend" in d["risks"]

    def test_environment_state_empty(self):
        env = EnvironmentState()
        assert env.metrics == {}
        assert env.anomalies == []
        assert env.trends == []
        assert env.opportunities == []
        assert env.risks == []


# ═══════════════════════════════════════════════════════════════════
# 2. CycleResult & CycleSummary tests
# ═══════════════════════════════════════════════════════════════════


class TestCycleResult:
    """周期结果和摘要测试."""

    def test_create_result(self):
        result = CycleResult(
            cycle_id="c1",
            cycle_number=1,
            outcome=CycleOutcome.SUCCESS,
            reward=0.85,
            summary="Budget increased successfully",
            action_taken="increase_budget",
        )
        assert result.outcome == CycleOutcome.SUCCESS
        assert result.reward == 0.85

    def test_result_to_dict(self):
        result = CycleResult(
            cycle_id="c1",
            cycle_number=1,
            outcome=CycleOutcome.SUCCESS,
            reward=0.85,
            metrics_before={"roas": 0.65},
            metrics_after={"roas": 0.82},
            lessons=["Budget increase improved ROAS"],
        )
        d = result.to_dict()
        assert d["outcome"] == "success"
        assert d["metrics_before"]["roas"] == 0.65
        assert d["metrics_after"]["roas"] == 0.82

    def test_cycle_summary_empty(self):
        summary = CycleSummary()
        assert summary.total_cycles == 0
        assert summary.successful == 0

    def test_cycle_summary_from_results(self):
        results = [
            CycleResult(cycle_id="c1", cycle_number=1, outcome=CycleOutcome.SUCCESS, reward=0.9),
            CycleResult(cycle_id="c2", cycle_number=2, outcome=CycleOutcome.SUCCESS, reward=0.8),
            CycleResult(cycle_id="c3", cycle_number=3, outcome=CycleOutcome.FAILURE, reward=0.1),
            CycleResult(cycle_id="c4", cycle_number=4, outcome=CycleOutcome.PARTIAL, reward=0.5),
        ]
        summary = CycleSummary.from_results(results)
        assert summary.total_cycles == 4
        assert summary.successful == 2
        assert summary.failed == 1
        assert summary.partial == 1
        assert summary.average_reward == round((0.9 + 0.8 + 0.1 + 0.5) / 4, 4)

    def test_cycle_summary_to_dict(self):
        results = [CycleResult(cycle_id="c1", cycle_number=1, outcome=CycleOutcome.SUCCESS, reward=0.9)]
        summary = CycleSummary.from_results(results)
        d = summary.to_dict()
        assert d["total_cycles"] == 1
        assert d["successful"] == 1

    def test_goal_evaluation_to_dict(self):
        ge = GoalEvaluation(
            goal_id="g1",
            goal_name="ROAS",
            metric="roas",
            target=0.8,
            current=0.55,
            health=GoalHealth.BEHIND,
            gap=0.3125,
            urgency="high",
            recommendation="Need to increase ROAS",
            progress=0.6875,
        )
        d = ge.to_dict()
        assert d["health"] == "behind"
        assert d["gap"] == 0.3125
        assert d["urgency"] == "high"

    def test_anomaly_signal_to_dict(self):
        a = AnomalySignal(
            metric="ctr",
            current=2.8,
            baseline=2.1,
            deviation=0.33,
            severity="high",
            description="CTR spike",
        )
        d = a.to_dict()
        assert d["metric"] == "ctr"
        assert d["severity"] == "high"

    def test_trend_signal_to_dict(self):
        t = TrendSignal(
            metric="roas",
            direction="down",
            strength=0.7,
            consecutive_periods=3,
        )
        d = t.to_dict()
        assert d["direction"] == "down"
        assert d["strength"] == 0.7

    def test_opportunity_signal_to_dict(self):
        o = OpportunitySignal(
            name="Creative A CTR Boost",
            type="SCALE_WINNER_CREATIVE",
            confidence=0.86,
            description="CTR +40%",
            impacted_metrics=["ctr", "roas"],
            estimated_impact={"ctr": 0.4},
        )
        d = o.to_dict()
        assert d["type"] == "SCALE_WINNER_CREATIVE"
        assert d["confidence"] == 0.86


# ═══════════════════════════════════════════════════════════════════
# 3. State Machine Tests (20 tests)
# ═══════════════════════════════════════════════════════════════════


class TestStateMachine:
    """状态机测试."""

    def test_initial_state(self):
        sm = CycleStateMachine()
        assert sm.current_state == CycleState.CREATED

    def test_valid_transition_created_to_observing(self, sample_cycle):
        sm = CycleStateMachine()
        assert sm.transition(sample_cycle, CycleState.OBSERVING)
        assert sm.current_state == CycleState.OBSERVING
        assert sample_cycle.state == CycleState.OBSERVING

    def test_valid_transition_observing_to_analyzing(self, sample_cycle):
        sm = CycleStateMachine()
        sm.transition(sample_cycle, CycleState.OBSERVING)
        assert sm.transition(sample_cycle, CycleState.ANALYZING)

    def test_valid_transition_analyzing_to_planning(self, sample_cycle):
        sm = CycleStateMachine()
        sm.transition(sample_cycle, CycleState.OBSERVING)
        sm.transition(sample_cycle, CycleState.ANALYZING)
        assert sm.transition(sample_cycle, CycleState.PLANNING)

    def test_valid_transition_planning_to_deciding(self, sample_cycle):
        sm = CycleStateMachine()
        sm.transition(sample_cycle, CycleState.OBSERVING)
        sm.transition(sample_cycle, CycleState.ANALYZING)
        sm.transition(sample_cycle, CycleState.PLANNING)
        assert sm.transition(sample_cycle, CycleState.DECIDING)

    def test_valid_transition_deciding_to_executing(self, sample_cycle):
        sm = CycleStateMachine()
        sm.transition(sample_cycle, CycleState.OBSERVING)
        sm.transition(sample_cycle, CycleState.ANALYZING)
        sm.transition(sample_cycle, CycleState.PLANNING)
        sm.transition(sample_cycle, CycleState.DECIDING)
        assert sm.transition(sample_cycle, CycleState.EXECUTING)

    def test_valid_transition_executing_to_evaluating(self, sample_cycle):
        sm = CycleStateMachine()
        sm.run_full_cycle(sample_cycle)
        # Reset and test single step
        sm2 = CycleStateMachine()
        c2 = DecisionCycle(operator_id="test", cycle_number=2)
        sm2.transition(c2, CycleState.OBSERVING)
        sm2.transition(c2, CycleState.ANALYZING)
        sm2.transition(c2, CycleState.PLANNING)
        sm2.transition(c2, CycleState.DECIDING)
        sm2.transition(c2, CycleState.EXECUTING)
        assert sm2.transition(c2, CycleState.EVALUATING)

    def test_valid_transition_evaluating_to_learning(self, sample_cycle):
        sm = CycleStateMachine()
        sm.transition(sample_cycle, CycleState.OBSERVING)
        sm.transition(sample_cycle, CycleState.ANALYZING)
        sm.transition(sample_cycle, CycleState.PLANNING)
        sm.transition(sample_cycle, CycleState.DECIDING)
        sm.transition(sample_cycle, CycleState.EXECUTING)
        sm.transition(sample_cycle, CycleState.EVALUATING)
        assert sm.transition(sample_cycle, CycleState.LEARNING)

    def test_valid_transition_learning_to_completed(self, sample_cycle):
        sm = CycleStateMachine()
        sm.transition(sample_cycle, CycleState.OBSERVING)
        sm.transition(sample_cycle, CycleState.ANALYZING)
        sm.transition(sample_cycle, CycleState.PLANNING)
        sm.transition(sample_cycle, CycleState.DECIDING)
        sm.transition(sample_cycle, CycleState.EXECUTING)
        sm.transition(sample_cycle, CycleState.EVALUATING)
        sm.transition(sample_cycle, CycleState.LEARNING)
        assert sm.transition(sample_cycle, CycleState.COMPLETED)

    def test_completed_to_observing(self, sample_cycle):
        sm = CycleStateMachine()
        sm.run_full_cycle(sample_cycle)
        assert sm.current_state == CycleState.COMPLETED
        assert sm.transition(sample_cycle, CycleState.OBSERVING)

    def test_can_transition_to_failed(self, sample_cycle):
        sm = CycleStateMachine()
        sm.transition(sample_cycle, CycleState.OBSERVING)
        assert sm.can_transition(CycleState.OBSERVING, CycleState.FAILED)

    def test_can_transition_to_paused(self, sample_cycle):
        sm = CycleStateMachine()
        sm.transition(sample_cycle, CycleState.OBSERVING)
        assert sm.can_transition(CycleState.OBSERVING, CycleState.PAUSED)

    def test_cannot_transition_observing_to_executing(self, sample_cycle):
        sm = CycleStateMachine()
        sm.transition(sample_cycle, CycleState.OBSERVING)
        assert not sm.transition(sample_cycle, CycleState.EXECUTING)

    def test_cannot_transition_observing_to_completed(self, sample_cycle):
        sm = CycleStateMachine()
        sm.transition(sample_cycle, CycleState.OBSERVING)
        assert not sm.transition(sample_cycle, CycleState.COMPLETED)

    def test_cannot_transition_executing_to_observing(self, sample_cycle):
        sm = CycleStateMachine()
        for s in [CycleState.OBSERVING, CycleState.ANALYZING, CycleState.PLANNING,
                   CycleState.DECIDING, CycleState.EXECUTING]:
            sm.transition(sample_cycle, s)
        assert not sm.transition(sample_cycle, CycleState.OBSERVING)

    def test_is_forbidden(self):
        sm = CycleStateMachine()
        assert sm.is_forbidden(CycleState.OBSERVING, CycleState.EXECUTING)
        assert sm.is_forbidden(CycleState.EXECUTING, CycleState.OBSERVING)
        assert sm.is_forbidden(CycleState.COMPLETED, CycleState.ANALYZING)

    def test_same_state_transition(self, sample_cycle):
        sm = CycleStateMachine()
        sm.transition(sample_cycle, CycleState.OBSERVING)
        assert sm.can_transition(CycleState.OBSERVING, CycleState.OBSERVING)

    def test_run_full_cycle(self, sample_cycle):
        sm = CycleStateMachine()
        success, error = sm.run_full_cycle(sample_cycle)
        assert success
        assert error is None
        assert sm.current_state == CycleState.COMPLETED
        assert sm.transition_count == 8

    def test_run_sequence(self, sample_cycle):
        sm = CycleStateMachine()
        success, error = sm.run_sequence(sample_cycle, [
            CycleState.OBSERVING, CycleState.ANALYZING, CycleState.PLANNING,
        ])
        assert success
        assert sm.current_state == CycleState.PLANNING

    def test_run_sequence_invalid(self, sample_cycle):
        sm = CycleStateMachine()
        success, error = sm.run_sequence(sample_cycle, [
            CycleState.OBSERVING, CycleState.EXECUTING,  # invalid! skip ANALYZING
        ])
        assert not success
        assert error is not None

    def test_reset_state_machine(self, sample_cycle):
        sm = CycleStateMachine()
        sm.run_full_cycle(sample_cycle)
        sm.reset()
        assert sm.current_state == CycleState.CREATED
        assert sm.transition_count == 0
        assert sm.error_count == 0

    def test_get_allowed_targets(self, sample_cycle):
        sm = CycleStateMachine()
        sm.transition(sample_cycle, CycleState.OBSERVING)
        targets = sm.get_allowed_targets()
        assert CycleState.ANALYZING in targets
        assert CycleState.FAILED in targets
        assert CycleState.PAUSED in targets
        assert CycleState.EXECUTING not in targets

    def test_history_tracking(self, sample_cycle):
        sm = CycleStateMachine()
        sm.transition(sample_cycle, CycleState.OBSERVING)
        sm.transition(sample_cycle, CycleState.ANALYZING)
        history = sm.get_state_sequence()
        assert history == [CycleState.CREATED, CycleState.OBSERVING, CycleState.ANALYZING]

    def test_to_dict(self, sample_cycle):
        sm = CycleStateMachine()
        sm.transition(sample_cycle, CycleState.OBSERVING)
        d = sm.to_dict()
        assert d["current_state"] == "observing"
        assert d["transition_count"] == 1

    def test_failed_to_created(self, sample_cycle):
        sm = CycleStateMachine()
        sm.transition(sample_cycle, CycleState.OBSERVING)
        sm.transition(sample_cycle, CycleState.FAILED)
        assert sm.transition(sample_cycle, CycleState.CREATED)

    def test_paused_to_observing(self, sample_cycle):
        sm = CycleStateMachine()
        sm.transition(sample_cycle, CycleState.OBSERVING)
        sm.transition(sample_cycle, CycleState.PAUSED)
        assert sm.transition(sample_cycle, CycleState.OBSERVING)

    def test_forbidden_transitions_count(self):
        """验证禁止转换数量."""
        assert len(FORBIDDEN_TRANSITIONS) >= 15

    def test_valid_transitions_completeness(self):
        """验证所有状态都有合法转换定义."""
        for state in CycleState:
            assert state in VALID_TRANSITIONS, f"Missing transitions for {state}"


# ═══════════════════════════════════════════════════════════════════
# 4. Goal Evaluation Tests (15 tests)
# ═══════════════════════════════════════════════════════════════════


class TestGoalEvaluator:
    """目标评估器测试."""

    def test_evaluate_single_goal_behind(self, sample_metrics):
        evaluator = GoalEvaluator()
        # gap = (0.63-0.55)/0.63 = 0.127 → BEHIND (0.05 < 0.127 <= 0.15)
        goal = {
            "goal_id": "g1", "name": "ROAS", "metric": "roas",
            "target": 0.63, "direction": "above", "priority": "high",
        }
        result = evaluator.evaluate_single(goal, sample_metrics)
        assert result.health == GoalHealth.BEHIND
        assert result.gap > 0.05
        assert result.urgency in ("high", "medium")

    def test_evaluate_single_goal_on_track(self, sample_metrics):
        evaluator = GoalEvaluator()
        # gap = (0.57-0.55)/0.57 = 0.035 → ON_TRACK (gap <= 0.05)
        goal = {
            "goal_id": "g1", "name": "ROAS", "metric": "roas",
            "target": 0.57, "direction": "above", "priority": "high",
        }
        result = evaluator.evaluate_single(goal, sample_metrics)
        assert result.health == GoalHealth.ON_TRACK

    def test_evaluate_single_goal_achieved(self):
        evaluator = GoalEvaluator()
        goal = {
            "goal_id": "g1", "name": "ROAS", "metric": "roas",
            "target": 0.5, "direction": "above", "priority": "high",
        }
        metrics = {"roas": 0.6}
        result = evaluator.evaluate_single(goal, metrics)
        assert result.health == GoalHealth.ACHIEVED

    def test_evaluate_single_goal_failed(self):
        evaluator = GoalEvaluator()
        goal = {
            "goal_id": "g1", "name": "ROAS", "metric": "roas",
            "target": 0.8, "direction": "above", "priority": "high",
        }
        metrics = {"roas": 0.2}
        result = evaluator.evaluate_single(goal, metrics)
        assert result.health == GoalHealth.FAILED
        assert result.urgency == "critical"

    def test_evaluate_below_direction(self):
        evaluator = GoalEvaluator()
        goal = {
            "goal_id": "g2", "name": "Spend", "metric": "spend",
            "target": 500.0, "direction": "below", "priority": "medium",
        }
        metrics = {"spend": 600}
        result = evaluator.evaluate_single(goal, metrics)
        assert result.health in (GoalHealth.BEHIND, GoalHealth.FAILED)
        assert result.gap > 0

    def test_evaluate_below_direction_achieved(self):
        evaluator = GoalEvaluator()
        goal = {
            "goal_id": "g2", "name": "Spend", "metric": "spend",
            "target": 500.0, "direction": "below", "priority": "medium",
        }
        metrics = {"spend": 400}
        result = evaluator.evaluate_single(goal, metrics)
        assert result.health == GoalHealth.ACHIEVED

    def test_evaluate_multiple_goals(self, sample_goals, sample_metrics):
        evaluator = GoalEvaluator()
        results = evaluator.evaluate(sample_goals, sample_metrics)
        assert len(results) == 2

    def test_evaluate_zero_target(self):
        evaluator = GoalEvaluator()
        goal = {
            "goal_id": "g1", "name": "Zero", "metric": "zero",
            "target": 0, "direction": "above", "priority": "low",
        }
        metrics = {"zero": 10}
        result = evaluator.evaluate_single(goal, metrics)
        assert result.gap == 0.0
        assert result.progress == 0.0

    def test_evaluate_ahead_health(self):
        evaluator = GoalEvaluator()
        goal = {
            "goal_id": "g1", "name": "ROAS", "metric": "roas",
            "target": 0.5, "direction": "above", "priority": "high",
        }
        metrics = {"roas": 0.9}
        result = evaluator.evaluate_single(goal, metrics)
        assert result.health == GoalHealth.ACHIEVED

    def test_urgency_critical(self):
        evaluator = GoalEvaluator()
        goal = {
            "goal_id": "g1", "name": "ROAS", "metric": "roas",
            "target": 0.8, "direction": "above", "priority": "high",
        }
        metrics = {"roas": 0.1}
        result = evaluator.evaluate_single(goal, metrics)
        assert result.urgency == "critical"

    def test_urgency_high_from_priority(self):
        evaluator = GoalEvaluator()
        goal = {
            "goal_id": "g1", "name": "ROAS", "metric": "roas",
            "target": 0.8, "direction": "above", "priority": "high",
        }
        metrics = {"roas": 0.7}
        result = evaluator.evaluate_single(goal, metrics)
        assert result.urgency in ("high", "medium")

    def test_progress_calculation(self):
        evaluator = GoalEvaluator()
        goal = {
            "goal_id": "g1", "name": "ROAS", "metric": "roas",
            "target": 1.0, "direction": "above", "priority": "high",
        }
        metrics = {"roas": 0.75}
        result = evaluator.evaluate_single(goal, metrics)
        assert result.progress == 0.75

    def test_recommendation_generation(self):
        evaluator = GoalEvaluator()
        goal = {
            "goal_id": "g1", "name": "ROAS", "metric": "roas",
            "target": 0.8, "direction": "above", "priority": "high",
        }
        metrics = {"roas": 0.55}
        result = evaluator.evaluate_single(goal, metrics)
        assert "roas" in result.recommendation.lower()

    def test_get_summary(self, sample_goals, sample_metrics):
        evaluator = GoalEvaluator()
        evals = evaluator.evaluate(sample_goals, sample_metrics)
        summary = evaluator.get_summary(evals)
        assert summary["total"] == 2
        assert "avg_gap" in summary

    def test_get_summary_empty(self):
        evaluator = GoalEvaluator()
        summary = evaluator.get_summary([])
        assert summary["total"] == 0


# ═══════════════════════════════════════════════════════════════════
# 5. Opportunity Detection Tests (15 tests)
# ═══════════════════════════════════════════════════════════════════


class TestOpportunityEvaluator:
    """机会评估器测试."""

    def test_evaluate_from_anomalies_ctr(self):
        evaluator = OpportunityEvaluator()
        env = EnvironmentState(
            anomalies=[
                AnomalySignal(metric="ctr", current=2.8, baseline=2.0, deviation=0.4, severity="medium"),
            ]
        )
        opportunities = evaluator.evaluate(env)
        assert len(opportunities) >= 1
        assert any(o.type == "SCALE_WINNER_CREATIVE" for o in opportunities)

    def test_evaluate_from_anomalies_roas(self):
        evaluator = OpportunityEvaluator()
        env = EnvironmentState(
            anomalies=[
                AnomalySignal(metric="roas", current=1.0, baseline=0.8, deviation=0.25, severity="low"),
            ]
        )
        opportunities = evaluator.evaluate(env)
        assert any(o.type == "INCREASE_BUDGET" for o in opportunities)

    def test_evaluate_from_anomalies_fatigue(self):
        evaluator = OpportunityEvaluator()
        env = EnvironmentState(
            anomalies=[
                AnomalySignal(metric="fatigue", current=0.85, baseline=0.5, deviation=0.35, severity="high"),
            ]
        )
        opportunities = evaluator.evaluate(env)
        assert any(o.type == "REPLACE_CREATIVE" for o in opportunities)

    def test_evaluate_from_trends_up(self):
        evaluator = OpportunityEvaluator()
        env = EnvironmentState(
            trends=[
                TrendSignal(metric="roas", direction="up", strength=0.8, consecutive_periods=3),
            ]
        )
        opportunities = evaluator.evaluate(env)
        assert any(o.type == "CAPITALIZE_TREND" for o in opportunities)

    def test_evaluate_from_trends_down(self):
        evaluator = OpportunityEvaluator()
        env = EnvironmentState(
            trends=[
                TrendSignal(metric="ctr", direction="down", strength=0.75, consecutive_periods=3),
            ]
        )
        opportunities = evaluator.evaluate(env)
        assert any(o.type == "INVESTIGATE_DECLINE" for o in opportunities)

    def test_evaluate_from_existing_opportunities(self):
        evaluator = OpportunityEvaluator()
        existing = OpportunitySignal(
            name="Test Opp", type="SCALE_WINNER_CREATIVE", confidence=0.9,
        )
        env = EnvironmentState(opportunities=[existing])
        opportunities = evaluator.evaluate(env)
        assert any(o.name == "Test Opp" for o in opportunities)

    def test_ctr_below_threshold_no_opportunity(self):
        evaluator = OpportunityEvaluator()
        env = EnvironmentState(
            anomalies=[
                AnomalySignal(metric="ctr", current=2.2, baseline=2.0, deviation=0.1, severity="low"),
            ]
        )
        opportunities = evaluator.evaluate(env)
        # CTR deviation below threshold, no SCALE_WINNER_CREATIVE
        scale_opps = [o for o in opportunities if o.type == "SCALE_WINNER_CREATIVE"]
        assert len(scale_opps) == 0

    def test_roas_below_threshold_no_opportunity(self):
        evaluator = OpportunityEvaluator()
        env = EnvironmentState(
            anomalies=[
                AnomalySignal(metric="roas", current=0.85, baseline=0.8, deviation=0.06, severity="low"),
            ]
        )
        opportunities = evaluator.evaluate(env)
        budget_opps = [o for o in opportunities if o.type == "INCREASE_BUDGET"]
        assert len(budget_opps) == 0

    def test_fatigue_below_threshold_no_opportunity(self):
        evaluator = OpportunityEvaluator()
        env = EnvironmentState(
            anomalies=[
                AnomalySignal(metric="fatigue", current=0.5, baseline=0.5, deviation=0.0, severity="low"),
            ]
        )
        opportunities = evaluator.evaluate(env)
        replace_opps = [o for o in opportunities if o.type == "REPLACE_CREATIVE"]
        assert len(replace_opps) == 0

    def test_get_top_opportunities(self, sample_environment):
        evaluator = OpportunityEvaluator()
        top = evaluator.get_top_opportunities(sample_environment, top_n=2)
        assert len(top) <= 2

    def test_get_top_opportunities_sorted(self, sample_environment):
        evaluator = OpportunityEvaluator()
        top = evaluator.get_top_opportunities(sample_environment, top_n=3)
        if len(top) >= 2:
            assert top[0].confidence >= top[1].confidence

    def test_opportunity_confidence_range(self, sample_environment):
        evaluator = OpportunityEvaluator()
        opportunities = evaluator.evaluate(sample_environment)
        for o in opportunities:
            assert 0.0 <= o.confidence <= 1.0

    def test_empty_environment_no_opportunities(self):
        evaluator = OpportunityEvaluator()
        env = EnvironmentState()
        opportunities = evaluator.evaluate(env)
        assert opportunities == []

    def test_weak_trend_no_opportunity(self):
        evaluator = OpportunityEvaluator()
        env = EnvironmentState(
            trends=[
                TrendSignal(metric="roas", direction="up", strength=0.3, consecutive_periods=1),
            ]
        )
        opportunities = evaluator.evaluate(env)
        # Weak trend should not generate CAPITALIZE_TREND
        trend_opps = [o for o in opportunities if o.type == "CAPITALIZE_TREND"]
        assert len(trend_opps) == 0

    def test_negative_deviation_ctr_no_opportunity(self):
        evaluator = OpportunityEvaluator()
        env = EnvironmentState(
            anomalies=[
                AnomalySignal(metric="ctr", current=1.5, baseline=2.0, deviation=-0.25, severity="medium"),
            ]
        )
        opportunities = evaluator.evaluate(env)
        # Negative deviation should not generate positive opportunity
        scale_opps = [o for o in opportunities if o.type == "SCALE_WINNER_CREATIVE"]
        assert len(scale_opps) == 0


# ═══════════════════════════════════════════════════════════════════
# 6. Planner Bridge Tests (10 tests)
# ═══════════════════════════════════════════════════════════════════


class TestPlannerBridge:
    """Planner 桥接器测试."""

    def test_generate_actions_from_opportunities(self, sample_cycle, sample_environment):
        bridge = PlannerBridge()
        goals = []
        actions = bridge.generate_actions(
            sample_cycle, goals, sample_environment.opportunities, sample_environment,
        )
        assert len(actions) >= 1

    def test_generate_actions_from_goals(self, sample_cycle, sample_environment):
        bridge = PlannerBridge()
        goals = [
            GoalEvaluation(
                goal_id="g1", goal_name="ROAS", metric="roas",
                target=0.8, current=0.55, health=GoalHealth.BEHIND,
                gap=0.3125, urgency="high",
            )
        ]
        actions = bridge.generate_actions(sample_cycle, goals, [], sample_environment)
        assert len(actions) >= 1

    def test_generate_actions_always_include_do_nothing(self, sample_cycle):
        bridge = PlannerBridge()
        actions = bridge.generate_actions(sample_cycle, [], [], None)
        assert any(a["action_type"] == "do_nothing" for a in actions)

    def test_opportunity_to_action_scale_winner(self):
        bridge = PlannerBridge()
        opp = OpportunitySignal(
            name="Creative A", type="SCALE_WINNER_CREATIVE", confidence=0.86,
        )
        action = bridge._opportunity_to_action(opp)
        assert action is not None
        assert action["action_type"] == "increase_budget"

    def test_opportunity_to_action_replace_creative(self):
        bridge = PlannerBridge()
        opp = OpportunitySignal(
            name="Creative Fatigue", type="REPLACE_CREATIVE", confidence=0.9,
        )
        action = bridge._opportunity_to_action(opp)
        assert action is not None
        assert action["action_type"] == "replace_creative"

    def test_goal_to_action_behind(self):
        bridge = PlannerBridge()
        ge = GoalEvaluation(
            goal_id="g1", goal_name="ROAS", metric="roas",
            target=0.8, current=0.55, health=GoalHealth.BEHIND,
            gap=0.3125, urgency="high",
        )
        action = bridge._goal_to_action(ge)
        assert action is not None
        assert action["action_type"] == "adjust_budget"

    def test_goal_to_action_on_track_returns_none(self):
        bridge = PlannerBridge()
        ge = GoalEvaluation(
            goal_id="g1", goal_name="ROAS", metric="roas",
            target=0.8, current=0.78, health=GoalHealth.ON_TRACK,
            gap=0.025, urgency="low",
        )
        action = bridge._goal_to_action(ge)
        assert action is None

    def test_generation_count(self, sample_cycle):
        bridge = PlannerBridge()
        assert bridge.generation_count == 0
        bridge.generate_actions(sample_cycle, [], [], None)
        assert bridge.generation_count == 1

    def test_get_stats(self, sample_cycle):
        bridge = PlannerBridge()
        bridge.generate_actions(sample_cycle, [], [], None)
        stats = bridge.get_stats()
        assert stats["generation_count"] == 1
        assert stats["has_planner"] is False

    def test_goal_to_action_metric_mapping(self):
        bridge = PlannerBridge()
        test_cases = [
            ("ctr", "replace_creative"),
            ("cvr", "adjust_bid"),
            ("revenue", "increase_budget"),
            ("spend", "reduce_budget"),
            ("payer_rate", "optimize_pricing"),
            ("retention", "increase_retention"),
        ]
        for metric, expected_action in test_cases:
            ge = GoalEvaluation(
                goal_id="g1", goal_name="Test", metric=metric,
                target=1.0, current=0.5, health=GoalHealth.BEHIND,
                gap=0.5, urgency="high",
            )
            action = bridge._goal_to_action(ge)
            assert action is not None
            assert action["action_type"] == expected_action, f"Expected {expected_action} for {metric}"


# ═══════════════════════════════════════════════════════════════════
# 7. Executor Bridge Tests (10 tests)
# ═══════════════════════════════════════════════════════════════════


class TestExecutorBridge:
    """Executor 桥接器测试."""

    def test_execute_do_nothing(self, sample_cycle):
        bridge = ExecutorBridge()
        result = bridge.execute({"action_type": "do_nothing"}, sample_cycle)
        assert result["status"] == "skipped"
        assert sample_cycle.execution_result["status"] == "skipped"

    def test_execute_simulated_success(self, sample_cycle):
        bridge = ExecutorBridge()
        action = {"action_type": "increase_budget", "confidence": 0.9}
        result = bridge.execute(action, sample_cycle)
        assert result["status"] == "executed"
        assert result["simulated"] is True

    def test_execute_simulated_failure_low_confidence(self, sample_cycle):
        bridge = ExecutorBridge()
        action = {"action_type": "increase_budget", "confidence": 0.1}
        result = bridge.execute(action, sample_cycle)
        assert result["status"] == "failed"

    def test_execute_empty_action(self, sample_cycle):
        bridge = ExecutorBridge()
        result = bridge.execute({}, sample_cycle)
        assert result["status"] == "skipped"

    def test_execute_batch(self, sample_cycle):
        bridge = ExecutorBridge()
        actions = [
            {"action_type": "increase_budget", "confidence": 0.9},
            {"action_type": "replace_creative", "confidence": 0.8},
        ]
        results = bridge.execute_batch(actions, sample_cycle)
        assert len(results) == 2

    def test_execution_count(self, sample_cycle):
        bridge = ExecutorBridge()
        assert bridge.execution_count == 0
        bridge.execute({"action_type": "test", "confidence": 0.9}, sample_cycle)
        assert bridge.execution_count == 1

    def test_success_rate(self, sample_cycle):
        bridge = ExecutorBridge()
        bridge.execute({"action_type": "test", "confidence": 0.9}, sample_cycle)
        assert bridge.success_rate == 1.0

    def test_rollback(self, sample_cycle):
        bridge = ExecutorBridge()
        sample_cycle.selected_action = {"action_type": "increase_budget"}
        result = bridge.rollback(sample_cycle, reason="Risk too high")
        assert result["status"] == "rolled_back"
        assert result["reason"] == "Risk too high"

    def test_get_execution_history(self, sample_cycle):
        bridge = ExecutorBridge()
        bridge.execute({"action_type": "test1", "confidence": 0.9}, sample_cycle)
        bridge.execute({"action_type": "test2", "confidence": 0.8}, sample_cycle)
        history = bridge.get_execution_history()
        assert len(history) == 2

    def test_reset(self, sample_cycle):
        bridge = ExecutorBridge()
        bridge.execute({"action_type": "test", "confidence": 0.9}, sample_cycle)
        bridge.reset()
        assert bridge.execution_count == 0
        assert bridge.success_count == 0


# ═══════════════════════════════════════════════════════════════════
# 8. Learning Feedback Tests (15 tests)
# ═══════════════════════════════════════════════════════════════════


class TestLearner:
    """学习反馈器测试."""

    def test_learn_success(self, sample_cycle):
        learner = Learner()
        cycle_result = CycleResult(
            cycle_id=sample_cycle.cycle_id,
            cycle_number=1,
            outcome=CycleOutcome.SUCCESS,
            reward=0.85,
            action_taken="increase_budget",
            metrics_before={"roas": 0.65},
            metrics_after={"roas": 0.82},
            lessons=["Budget increase improved ROAS"],
        )
        exp = learner.learn(sample_cycle, cycle_result)
        assert exp["outcome"] == "success"
        assert exp["reward"] == 0.85
        assert "roas" in exp["metrics_delta"]

    def test_learn_failure(self, sample_cycle):
        learner = Learner()
        cycle_result = CycleResult(
            cycle_id=sample_cycle.cycle_id,
            cycle_number=1,
            outcome=CycleOutcome.FAILURE,
            reward=0.15,
            action_taken="replace_creative",
            metrics_before={"ctr": 2.1},
            metrics_after={"ctr": 1.9},
        )
        exp = learner.learn(sample_cycle, cycle_result)
        assert exp["outcome"] == "failure"
        assert exp["metrics_delta"]["ctr"] == pytest.approx(-0.2)

    def test_learn_partial(self, sample_cycle):
        learner = Learner()
        cycle_result = CycleResult(
            cycle_id=sample_cycle.cycle_id,
            cycle_number=1,
            outcome=CycleOutcome.PARTIAL,
            reward=0.5,
            action_taken="adjust_bid",
        )
        exp = learner.learn(sample_cycle, cycle_result)
        assert exp["outcome"] == "partial"

    def test_learn_error(self, sample_cycle):
        learner = Learner()
        cycle_result = CycleResult(
            cycle_id=sample_cycle.cycle_id,
            cycle_number=1,
            outcome=CycleOutcome.ERROR,
            reward=0.0,
            action_taken="increase_budget",
        )
        exp = learner.learn(sample_cycle, cycle_result)
        assert exp["outcome"] == "error"

    def test_learn_no_action(self, sample_cycle):
        learner = Learner()
        cycle_result = CycleResult(
            cycle_id=sample_cycle.cycle_id,
            cycle_number=1,
            outcome=CycleOutcome.NO_ACTION,
            reward=0.0,
        )
        exp = learner.learn(sample_cycle, cycle_result)
        assert exp["outcome"] == "no_action"

    def test_learn_count(self, sample_cycle):
        learner = Learner()
        cr = CycleResult(cycle_id="c1", cycle_number=1, outcome=CycleOutcome.SUCCESS, reward=0.9)
        learner.learn(sample_cycle, cr)
        learner.learn(sample_cycle, cr)
        assert learner.learn_count == 2
        assert learner.experience_count == 2

    def test_learn_batch(self, sample_cycle):
        learner = Learner()
        results = [
            (sample_cycle, CycleResult(cycle_id="c1", cycle_number=1, outcome=CycleOutcome.SUCCESS, reward=0.9)),
            (sample_cycle, CycleResult(cycle_id="c2", cycle_number=2, outcome=CycleOutcome.FAILURE, reward=0.1)),
        ]
        experiences = learner.learn_batch(results)
        assert len(experiences) == 2

    def test_get_experiences(self, sample_cycle):
        learner = Learner()
        for i in range(5):
            cr = CycleResult(cycle_id=f"c{i}", cycle_number=i, outcome=CycleOutcome.SUCCESS, reward=0.8)
            learner.learn(sample_cycle, cr)
        exps = learner.get_experiences(limit=3)
        assert len(exps) == 3

    def test_get_stats(self, sample_cycle):
        learner = Learner()
        learner.learn(sample_cycle, CycleResult(
            cycle_id="c1", cycle_number=1, outcome=CycleOutcome.SUCCESS, reward=0.9,
        ))
        learner.learn(sample_cycle, CycleResult(
            cycle_id="c2", cycle_number=2, outcome=CycleOutcome.FAILURE, reward=0.1,
        ))
        stats = learner.get_stats()
        assert stats["learn_count"] == 2
        assert stats["success_rate"] == 0.5
        assert stats["avg_reward"] == 0.5

    def test_get_stats_empty(self):
        learner = Learner()
        stats = learner.get_stats()
        assert stats["learn_count"] == 0
        assert stats["avg_reward"] == 0.0

    def test_metrics_delta_calculation(self, sample_cycle):
        learner = Learner()
        cr = CycleResult(
            cycle_id="c1", cycle_number=1,
            outcome=CycleOutcome.SUCCESS, reward=0.8,
            metrics_before={"roas": 0.65, "ctr": 2.1},
            metrics_after={"roas": 0.82, "ctr": 2.5},
        )
        exp = learner.learn(sample_cycle, cr)
        assert exp["metrics_delta"]["roas"] == pytest.approx(0.17, 0.01)
        assert exp["metrics_delta"]["ctr"] == pytest.approx(0.4, 0.01)

    def test_lesson_generation_success(self, sample_cycle):
        learner = Learner()
        cr = CycleResult(
            cycle_id="c1", cycle_number=1,
            outcome=CycleOutcome.SUCCESS, reward=0.85,
            action_taken="increase_budget",
        )
        exp = learner.learn(sample_cycle, cr)
        assert "succeeded" in exp["lesson"]
        assert "0.85" in exp["lesson"]

    def test_lesson_generation_failure(self, sample_cycle):
        learner = Learner()
        cr = CycleResult(
            cycle_id="c1", cycle_number=1,
            outcome=CycleOutcome.FAILURE, reward=0.1,
            action_taken="replace_creative",
        )
        exp = learner.learn(sample_cycle, cr)
        assert "failed" in exp["lesson"]

    def test_reset(self, sample_cycle):
        learner = Learner()
        cr = CycleResult(cycle_id="c1", cycle_number=1, outcome=CycleOutcome.SUCCESS, reward=0.9)
        learner.learn(sample_cycle, cr)
        learner.reset()
        assert learner.learn_count == 0
        assert learner.experience_count == 0

    def test_context_in_experience(self, sample_cycle):
        learner = Learner()
        cr = CycleResult(cycle_id="c1", cycle_number=1, outcome=CycleOutcome.SUCCESS, reward=0.9)
        exp = learner.learn(sample_cycle, cr, context={"platform": "ios"})
        assert exp["context"]["platform"] == "ios"


# ═══════════════════════════════════════════════════════════════════
# 9. Performance Evaluator Tests
# ═══════════════════════════════════════════════════════════════════


class TestPerformanceEvaluator:
    """性能评估器测试."""

    def test_evaluate_success(self):
        evaluator = PerformanceEvaluator()
        cycle = DecisionCycle(
            operator_id="test", cycle_number=1,
            selected_action={"action_type": "increase_budget"},
        )
        # Big gains to ensure reward >= 0.7
        result = evaluator.evaluate(
            cycle,
            {"roas": 0.5, "ctr": 1.5, "revenue": 1000},
            {"roas": 1.0, "ctr": 3.0, "revenue": 2000},
        )
        assert result.outcome == CycleOutcome.SUCCESS
        assert result.reward > 0.5

    def test_evaluate_failure(self):
        evaluator = PerformanceEvaluator()
        cycle = DecisionCycle(
            operator_id="test", cycle_number=1,
            selected_action={"action_type": "increase_budget"},
        )
        result = evaluator.evaluate(
            cycle,
            {"roas": 0.65, "ctr": 2.1},
            {"roas": 0.40, "ctr": 1.5},
        )
        assert result.outcome in (CycleOutcome.FAILURE, CycleOutcome.PARTIAL)

    def test_evaluate_no_action(self):
        evaluator = PerformanceEvaluator()
        cycle = DecisionCycle(operator_id="test", cycle_number=1)
        result = evaluator.evaluate(cycle, {}, {})
        assert result.outcome == CycleOutcome.NO_ACTION

    def test_evaluate_with_error(self):
        evaluator = PerformanceEvaluator()
        cycle = DecisionCycle(
            operator_id="test", cycle_number=1,
            selected_action={"action_type": "increase_budget"},
            error="Network timeout",
        )
        result = evaluator.evaluate(
            cycle,
            {"roas": 0.65},
            {"roas": 0.82},
        )
        assert result.outcome == CycleOutcome.ERROR

    def test_evaluate_with_risk_assessments(self):
        evaluator = PerformanceEvaluator()
        cycle = DecisionCycle(
            operator_id="test", cycle_number=1,
            selected_action={"action_type": "increase_budget"},
            risk_assessments=[{"risk_score": 0.4}, {"risk_score": 0.15}],
        )
        result = evaluator.evaluate(
            cycle,
            {"roas": 0.65, "ctr": 2.1},
            {"roas": 0.82, "ctr": 2.5},
        )
        # Risk cost should reduce reward
        assert result.reward < 1.0

    def test_performance_gain_calculation(self):
        evaluator = PerformanceEvaluator()
        gain = evaluator._calculate_performance_gain(
            {"roas": 0.65, "ctr": 2.1},
            {"roas": 0.82, "ctr": 2.5},
        )
        assert gain > 0.5

    def test_performance_gain_no_positive_metrics(self):
        evaluator = PerformanceEvaluator()
        gain = evaluator._calculate_performance_gain(
            {"unknown_metric": 10},
            {"unknown_metric": 12},
        )
        assert gain == 0.5

    def test_lessons_extraction_success(self):
        evaluator = PerformanceEvaluator()
        cycle = DecisionCycle(
            operator_id="test", cycle_number=1,
            selected_action={"action_type": "increase_budget"},
        )
        result = evaluator.evaluate(
            cycle,
            {"roas": 0.65, "ctr": 2.1},
            {"roas": 0.82, "ctr": 2.5},
        )
        assert len(result.lessons) > 0

    def test_custom_weights(self):
        evaluator = PerformanceEvaluator(
            performance_weight=0.8, risk_weight=0.1, cost_weight=0.1,
        )
        cycle = DecisionCycle(
            operator_id="test", cycle_number=1,
            selected_action={"action_type": "increase_budget"},
        )
        result = evaluator.evaluate(
            cycle,
            {"roas": 0.65, "ctr": 2.1},
            {"roas": 0.82, "ctr": 2.5},
        )
        assert result.reward > 0


# ═══════════════════════════════════════════════════════════════════
# 10. Full Loop Integration Tests (20 tests)
# ═══════════════════════════════════════════════════════════════════


class TestAutonomousDecisionLoop:
    """自主决策循环集成测试."""

    def test_create_loop(self):
        loop = AutonomousDecisionLoop(operator_id="op_001")
        assert loop.operator_id == "op_001"
        assert not loop.active
        assert loop.total_cycles == 0

    def test_setup_goals(self):
        loop = AutonomousDecisionLoop()
        loop.setup_goals([
            {"name": "ROAS", "metric": "roas", "target": 0.8, "direction": "above"},
        ])
        assert loop._goals[0]["name"] == "ROAS"

    def test_setup_environment(self):
        loop = AutonomousDecisionLoop()
        loop.setup_environment(
            metrics={"roas": 0.65, "ctr": 2.1},
            risks=["overspend"],
        )
        assert loop._environment.metrics["roas"] == 0.65
        assert "overspend" in loop._environment.risks

    def test_update_environment(self):
        loop = AutonomousDecisionLoop()
        loop.setup_environment(metrics={"roas": 0.65})
        loop.update_environment(metrics={"ctr": 2.5})
        assert loop._environment.metrics["roas"] == 0.65
        assert loop._environment.metrics["ctr"] == 2.5

    def test_start_and_stop(self):
        loop = AutonomousDecisionLoop()
        assert loop.start()
        assert loop.active
        assert loop.stop()
        assert not loop.active

    def test_pause_and_resume(self):
        loop = AutonomousDecisionLoop()
        loop.start()
        assert loop.pause()
        assert loop.paused
        assert loop.resume()
        assert not loop.paused

    def test_pause_when_not_active(self):
        loop = AutonomousDecisionLoop()
        assert not loop.pause()

    def test_resume_when_not_paused(self):
        loop = AutonomousDecisionLoop()
        loop.start()
        assert not loop.resume()

    def test_run_cycle_not_active(self):
        loop = AutonomousDecisionLoop()
        result = loop.run_cycle()
        assert result.outcome == CycleOutcome.NO_ACTION
        assert "not active" in result.summary.lower()

    def test_run_cycle_basic(self, decision_loop):
        decision_loop.start()
        result = decision_loop.run_cycle()
        assert result.cycle_number == 1
        assert result.outcome in (
            CycleOutcome.SUCCESS, CycleOutcome.PARTIAL,
            CycleOutcome.FAILURE, CycleOutcome.NO_ACTION,
        )

    def test_run_cycle_increments_count(self, decision_loop):
        decision_loop.start()
        decision_loop.run_cycle()
        assert decision_loop.total_cycles == 1
        decision_loop.run_cycle()
        assert decision_loop.total_cycles == 2

    def test_run_cycle_with_goals(self, decision_loop):
        decision_loop.start()
        result = decision_loop.run_cycle()
        assert result is not None
        assert decision_loop._current_cycle is not None

    def test_run_cycle_with_opportunities(self, decision_loop):
        decision_loop.setup_environment(
            metrics={"roas": 0.65, "ctr": 2.1},
            anomalies=[
                {"metric": "ctr", "current": 2.8, "baseline": 2.1, "deviation": 0.35, "severity": "medium"},
            ],
        )
        decision_loop.start()
        result = decision_loop.run_cycle()
        assert result is not None

    def test_cycle_environment_preserved(self, decision_loop):
        decision_loop.start()
        decision_loop.run_cycle()
        assert decision_loop._current_cycle is not None
        assert decision_loop._current_cycle.environment_state is not None

    def test_get_cycle_summary(self, decision_loop):
        decision_loop.start()
        decision_loop.run_cycle()
        decision_loop.run_cycle()
        summary = decision_loop.get_cycle_summary()
        assert summary.total_cycles == 2

    def test_get_status(self, decision_loop):
        decision_loop.start()
        decision_loop.run_cycle()
        status = decision_loop.get_status()
        assert status["operator_id"] == "test_op"
        assert status["active"] is True
        assert status["total_cycles"] == 1

    def test_reset(self, decision_loop):
        decision_loop.start()
        decision_loop.run_cycle()
        decision_loop.reset()
        assert not decision_loop.active
        assert decision_loop.total_cycles == 0

    def test_set_cycle_interval(self):
        loop = AutonomousDecisionLoop()
        loop.set_cycle_interval(5.0)
        assert loop._cycle_interval_seconds == 5.0

    def test_set_max_cycles(self):
        loop = AutonomousDecisionLoop()
        loop.set_max_cycles(10)
        assert loop._max_cycles == 10

    def test_component_properties(self, decision_loop):
        assert decision_loop.state_machine is not None
        assert decision_loop.goal_evaluator is not None
        assert decision_loop.opportunity_evaluator is not None
        assert decision_loop.planner_bridge is not None
        assert decision_loop.executor_bridge is not None
        assert decision_loop.performance_evaluator is not None
        assert decision_loop.learner is not None

    # ── Additional integration edge cases ──────────────────────

    def test_run_cycle_with_anomalies_and_trends(self, decision_loop):
        decision_loop.setup_environment(
            metrics={"roas": 0.65, "ctr": 2.1, "spend": 2500, "revenue": 1800},
            anomalies=[
                {"metric": "ctr", "current": 2.8, "baseline": 2.1, "deviation": 0.35, "severity": "medium"},
            ],
            trends=[
                {"metric": "roas", "direction": "down", "strength": 0.7, "consecutive_periods": 3},
            ],
        )
        decision_loop.start()
        result = decision_loop.run_cycle()
        assert result is not None

    def test_run_cycle_do_nothing_fallback(self):
        loop = AutonomousDecisionLoop(operator_id="test")
        loop.setup_goals([])
        loop.setup_environment(metrics={})
        loop.start()
        result = loop.run_cycle()
        assert result is not None
        # With no opportunities and no goals, should default to do_nothing
        if loop._current_cycle:
            assert loop._current_cycle.selected_action.get("action_type") == "do_nothing"

    def test_multiple_cycles_accumulate_history(self, decision_loop):
        decision_loop.start()
        for _ in range(3):
            decision_loop.run_cycle()
        assert len(decision_loop.cycle_history) == 3

    def test_run_loop_with_max_cycles(self, decision_loop):
        decision_loop.start()
        decision_loop.set_max_cycles(2)
        results = decision_loop.run_loop(max_cycles=2)
        assert len(results) == 2

    def test_stop_during_cycle(self, decision_loop):
        decision_loop.start()
        decision_loop.run_cycle()
        decision_loop.stop()
        # After stop, next cycle should return NO_ACTION
        result = decision_loop.run_cycle()
        assert result.outcome == CycleOutcome.NO_ACTION

    def test_cycle_state_machine_progression(self, decision_loop):
        decision_loop.start()
        decision_loop.run_cycle()
        sm = decision_loop.state_machine
        assert sm.current_state == CycleState.COMPLETED

    def test_learner_records_experience(self, decision_loop):
        decision_loop.start()
        decision_loop.run_cycle()
        learner = decision_loop.learner
        assert learner.learn_count >= 1
        assert learner.experience_count >= 1