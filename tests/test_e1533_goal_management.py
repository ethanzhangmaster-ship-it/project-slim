"""E15.3.3 Goal Management 测试 — 完整测试.

测试覆盖:
  - Goal Model (20 tests)
  - Goal Store (15 tests)
  - Decomposition (20 tests)
  - Progress Tracking (20 tests)
  - Evaluation (15 tests)
  - Adaptation (10 tests)
  - Integration (10 tests)

总计: ~110 tests
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from market_ops.creative_vision_runtime.growth_runtime.intelligence.goal_management.models import (
    Goal,
    GoalAdaptation,
    GoalPriority,
    GoalProgress,
    GoalResult,
    GoalStatus,
    GoalType,
    ProgressTrend,
    SubGoal,
    SubGoalStrategy,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.goal_management.goal_store import (
    GoalStore,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.goal_management.goal_decomposer import (
    GoalDecomposer,
    DECOMPOSITION_RULES,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.goal_management.progress_tracker import (
    ProgressTracker,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.goal_management.evaluator import (
    GoalEvaluator,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.goal_management.goal_manager import (
    GoalManager,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def roas_goal() -> Goal:
    return Goal(
        name="Increase ROAS",
        description="Increase D30 ROAS for US iOS",
        type=GoalType.OPTIMIZATION,
        metric="roas",
        current_value=0.45,
        target_value=0.65,
        baseline_value=0.45,
        direction="above",
        priority=GoalPriority.P1,
        deadline="2026-08-30T00:00:00+00:00",
        tags=["ua", "ios", "us"],
    )


@pytest.fixture
def spend_goal() -> Goal:
    return Goal(
        name="Reduce Spend",
        metric="spend",
        current_value=600,
        target_value=500,
        baseline_value=600,
        direction="below",
        priority=GoalPriority.P2,
    )


@pytest.fixture
def goal_store() -> GoalStore:
    return GoalStore()


@pytest.fixture
def goal_manager() -> GoalManager:
    return GoalManager()


# ═══════════════════════════════════════════════════════════════════
# 1. Goal Model Tests (20 tests)
# ═══════════════════════════════════════════════════════════════════


class TestGoalModel:
    """目标模型测试."""

    def test_create_goal(self, roas_goal):
        assert roas_goal.name == "Increase ROAS"
        assert roas_goal.metric == "roas"
        assert roas_goal.target_value == 0.65
        assert roas_goal.baseline_value == 0.45
        assert roas_goal.status == GoalStatus.CREATED

    def test_goal_progress_at_start(self, roas_goal):
        assert roas_goal.progress() == 0.0

    def test_goal_progress_halfway(self, roas_goal):
        roas_goal.current_value = 0.55
        assert roas_goal.progress() == 0.5

    def test_goal_progress_achieved(self, roas_goal):
        roas_goal.current_value = 0.65
        assert roas_goal.progress() == 1.0

    def test_goal_progress_exceeded(self, roas_goal):
        roas_goal.current_value = 0.80
        assert roas_goal.progress() == 1.0  # capped at 1.0

    def test_goal_progress_below(self, spend_goal):
        spend_goal.current_value = 550
        assert spend_goal.progress() == 0.5

    def test_goal_progress_below_achieved(self, spend_goal):
        spend_goal.current_value = 500
        assert spend_goal.progress() == 1.0

    def test_goal_gap(self, roas_goal):
        roas_goal.current_value = 0.55
        assert roas_goal.gap() == pytest.approx(0.5)  # (0.65-0.55)/(0.65-0.45)

    def test_goal_gap_achieved(self, roas_goal):
        roas_goal.current_value = 0.65
        assert roas_goal.gap() == 0.0

    def test_goal_is_achieved(self, roas_goal):
        roas_goal.current_value = 0.65
        assert roas_goal.is_achieved()

    def test_goal_is_not_achieved(self, roas_goal):
        roas_goal.current_value = 0.55
        assert not roas_goal.is_achieved()

    def test_goal_is_active(self, roas_goal):
        assert not roas_goal.is_active()
        roas_goal.status = GoalStatus.ACTIVE
        assert roas_goal.is_active()

    def test_goal_is_expired_future(self, roas_goal):
        assert not roas_goal.is_expired()

    def test_goal_is_expired_past(self):
        past_goal = Goal(
            name="Past Goal", metric="roas",
            baseline_value=0.4, target_value=0.6,
            deadline="2020-01-01T00:00:00+00:00",
        )
        assert past_goal.is_expired()

    def test_goal_to_dict(self, roas_goal):
        d = roas_goal.to_dict()
        assert d["name"] == "Increase ROAS"
        assert d["metric"] == "roas"
        assert "progress" in d
        assert "gap" in d

    def test_goal_progress_no_baseline_change(self):
        goal = Goal(metric="roas", baseline_value=0.5, target_value=0.5, current_value=0.5)
        assert goal.progress() == 0.0

    def test_goal_type_enum(self):
        assert GoalType.OPTIMIZATION.value == "optimization"
        assert GoalType.GROWTH.value == "growth"
        assert GoalType.RISK_MITIGATION.value == "risk_mitigation"

    def test_goal_status_enum(self):
        assert GoalStatus.CREATED.value == "created"
        assert GoalStatus.ACTIVE.value == "active"
        assert GoalStatus.ACHIEVED.value == "achieved"
        assert GoalStatus.FAILED.value == "failed"

    def test_goal_priority_enum(self):
        assert GoalPriority.P1.value == 1
        assert GoalPriority.P5.value == 5

    def test_goal_default_values(self):
        goal = Goal()
        assert goal.goal_id != ""
        assert goal.status == GoalStatus.CREATED
        assert goal.priority == GoalPriority.P3


# ═══════════════════════════════════════════════════════════════════
# 2. SubGoal Model Tests
# ═══════════════════════════════════════════════════════════════════


class TestSubGoalModel:
    """子目标模型测试."""

    def test_create_subgoal(self):
        sg = SubGoal(
            parent_goal_id="g1",
            objective="Improve CTR",
            metric="ctr",
            target=0.05,
            baseline=0.03,
            direction="above",
            strategy=SubGoalStrategy.CREATIVE_EVOLUTION,
        )
        assert sg.parent_goal_id == "g1"
        assert sg.strategy == SubGoalStrategy.CREATIVE_EVOLUTION

    def test_subgoal_update_progress(self):
        sg = SubGoal(
            metric="ctr", target=0.05, baseline=0.03,
            current_value=0.03, direction="above",
        )
        sg.update_progress(0.04)
        assert sg.progress == 0.5
        assert sg.current_value == 0.04

    def test_subgoal_update_progress_achieved(self):
        sg = SubGoal(
            metric="ctr", target=0.05, baseline=0.03,
            current_value=0.03, direction="above",
        )
        sg.update_progress(0.05)
        assert sg.progress == 1.0

    def test_subgoal_is_achieved(self):
        sg = SubGoal(
            metric="ctr", target=0.05, baseline=0.03,
            current_value=0.05, direction="above",
        )
        assert sg.is_achieved()

    def test_subgoal_to_dict(self):
        sg = SubGoal(
            parent_goal_id="g1",
            objective="Test",
            metric="roas",
            strategy=SubGoalStrategy.BUDGET_OPTIMIZATION,
        )
        d = sg.to_dict()
        assert d["strategy"] == "budget_optimization"
        assert d["parent_goal_id"] == "g1"


# ═══════════════════════════════════════════════════════════════════
# 3. Goal Store Tests (15 tests)
# ═══════════════════════════════════════════════════════════════════


class TestGoalStore:
    """目标存储测试."""

    def test_save_and_get_goal(self, goal_store, roas_goal):
        goal_store.save_goal(roas_goal)
        assert goal_store.get_goal(roas_goal.goal_id) is roas_goal

    def test_get_all_goals(self, goal_store, roas_goal, spend_goal):
        goal_store.save_goal(roas_goal)
        goal_store.save_goal(spend_goal)
        assert goal_store.count() == 2

    def test_get_active_goals(self, goal_store, roas_goal):
        roas_goal.status = GoalStatus.ACTIVE
        goal_store.save_goal(roas_goal)
        assert len(goal_store.get_active_goals()) == 1

    def test_get_goals_by_type(self, goal_store, roas_goal):
        goal_store.save_goal(roas_goal)
        found = goal_store.get_goals_by_type("optimization")
        assert len(found) == 1

    def test_get_goals_by_priority(self, goal_store, roas_goal, spend_goal):
        roas_goal.status = GoalStatus.ACTIVE
        spend_goal.status = GoalStatus.ACTIVE
        goal_store.save_goal(roas_goal)
        goal_store.save_goal(spend_goal)
        found = goal_store.get_goals_by_priority(min_priority=2)
        assert len(found) == 2  # P1 and P2

    def test_get_goals_by_tag(self, goal_store, roas_goal):
        goal_store.save_goal(roas_goal)
        found = goal_store.get_goals_by_tag("ios")
        assert len(found) == 1

    def test_update_goal(self, goal_store, roas_goal):
        goal_store.save_goal(roas_goal)
        updated = goal_store.update_goal(roas_goal.goal_id, target_value=0.70)
        assert updated is not None
        assert updated.target_value == 0.70

    def test_update_nonexistent_goal(self, goal_store):
        assert goal_store.update_goal("nonexistent", target_value=0.7) is None

    def test_delete_goal(self, goal_store, roas_goal):
        goal_store.save_goal(roas_goal)
        assert goal_store.delete_goal(roas_goal.goal_id)
        assert goal_store.get_goal(roas_goal.goal_id) is None

    def test_exists(self, goal_store, roas_goal):
        assert not goal_store.exists(roas_goal.goal_id)
        goal_store.save_goal(roas_goal)
        assert goal_store.exists(roas_goal.goal_id)

    def test_save_and_get_subgoals(self, goal_store, roas_goal):
        goal_store.save_goal(roas_goal)
        sg = SubGoal(parent_goal_id=roas_goal.goal_id, objective="Test")
        goal_store.save_subgoal(sg)
        assert len(goal_store.get_subgoals(roas_goal.goal_id)) == 1

    def test_get_active_subgoals(self, goal_store, roas_goal):
        goal_store.save_goal(roas_goal)
        sg1 = SubGoal(parent_goal_id=roas_goal.goal_id, status=GoalStatus.ACTIVE)
        sg2 = SubGoal(parent_goal_id=roas_goal.goal_id, status=GoalStatus.ACHIEVED)
        goal_store.save_subgoal(sg1)
        goal_store.save_subgoal(sg2)
        assert len(goal_store.get_active_subgoals(roas_goal.goal_id)) == 1

    def test_delete_subgoal(self, goal_store, roas_goal):
        goal_store.save_goal(roas_goal)
        sg = SubGoal(parent_goal_id=roas_goal.goal_id)
        goal_store.save_subgoal(sg)
        assert goal_store.delete_subgoal(sg.subgoal_id)
        assert len(goal_store.get_subgoals(roas_goal.goal_id)) == 0

    def test_get_stats(self, goal_store, roas_goal):
        goal_store.save_goal(roas_goal)
        stats = goal_store.get_stats()
        assert stats["total_goals"] == 1

    def test_clear(self, goal_store, roas_goal):
        goal_store.save_goal(roas_goal)
        goal_store.clear()
        assert goal_store.count() == 0


# ═══════════════════════════════════════════════════════════════════
# 4. Goal Decomposer Tests (20 tests)
# ═══════════════════════════════════════════════════════════════════


class TestGoalDecomposer:
    """目标分解器测试."""

    def test_decompose_roas(self, roas_goal):
        decomposer = GoalDecomposer()
        subgoals = decomposer.decompose(roas_goal)
        assert len(subgoals) == 4
        assert any(sg.strategy == SubGoalStrategy.CREATIVE_EVOLUTION for sg in subgoals)
        assert any(sg.strategy == SubGoalStrategy.CPI_REDUCTION for sg in subgoals)

    def test_decompose_revenue(self):
        goal = Goal(metric="revenue", target_value=10000, baseline_value=5000, direction="above")
        decomposer = GoalDecomposer()
        subgoals = decomposer.decompose(goal)
        assert len(subgoals) == 3
        assert any(sg.strategy == SubGoalStrategy.AUDIENCE_EXPANSION for sg in subgoals)

    def test_decompose_ctr(self):
        goal = Goal(metric="ctr", target_value=0.05, baseline_value=0.03, direction="above")
        decomposer = GoalDecomposer()
        subgoals = decomposer.decompose(goal)
        assert len(subgoals) == 3

    def test_decompose_cpi(self):
        goal = Goal(metric="cpi", target_value=2.0, baseline_value=3.0, direction="below")
        decomposer = GoalDecomposer()
        subgoals = decomposer.decompose(goal)
        assert len(subgoals) == 3

    def test_decompose_payer_rate(self):
        goal = Goal(metric="payer_rate", target_value=0.05, baseline_value=0.02, direction="above")
        decomposer = GoalDecomposer()
        subgoals = decomposer.decompose(goal)
        assert len(subgoals) == 3

    def test_decompose_retention(self):
        goal = Goal(metric="retention", target_value=0.4, baseline_value=0.3, direction="above")
        decomposer = GoalDecomposer()
        subgoals = decomposer.decompose(goal)
        assert len(subgoals) == 3

    def test_decompose_spend(self):
        goal = Goal(metric="spend", target_value=500, baseline_value=800, direction="below")
        decomposer = GoalDecomposer()
        subgoals = decomposer.decompose(goal)
        assert len(subgoals) == 3

    def test_decompose_unknown_metric(self):
        goal = Goal(metric="unknown_metric", target_value=1.0, baseline_value=0.5, direction="above")
        decomposer = GoalDecomposer()
        subgoals = decomposer.decompose(goal)
        assert len(subgoals) == 3  # generic decomposition

    def test_decompose_batch(self, roas_goal, spend_goal):
        decomposer = GoalDecomposer()
        result = decomposer.decompose_batch([roas_goal, spend_goal])
        assert len(result) == 2
        assert len(result[roas_goal.goal_id]) == 4
        assert len(result[spend_goal.goal_id]) == 3

    def test_subgoal_inherits_parent_id(self, roas_goal):
        decomposer = GoalDecomposer()
        subgoals = decomposer.decompose(roas_goal)
        for sg in subgoals:
            assert sg.parent_goal_id == roas_goal.goal_id

    def test_subgoal_inherits_priority(self, roas_goal):
        decomposer = GoalDecomposer()
        subgoals = decomposer.decompose(roas_goal)
        for sg in subgoals:
            assert sg.priority == roas_goal.priority

    def test_subgoal_target_based_on_weight(self, roas_goal):
        decomposer = GoalDecomposer()
        subgoals = decomposer.decompose(roas_goal)
        # Each subgoal target should be proportional to its weight
        for sg in subgoals:
            assert sg.target >= roas_goal.baseline_value

    def test_decomposition_count(self, roas_goal):
        decomposer = GoalDecomposer()
        assert decomposer.decomposition_count == 0
        decomposer.decompose(roas_goal)
        assert decomposer.decomposition_count == 1

    def test_add_custom_rule(self):
        decomposer = GoalDecomposer()
        decomposer.add_rule("custom_metric", [
            {"objective": "Custom Action", "metric": "custom", "strategy": SubGoalStrategy.CUSTOM, "weight": 1.0},
        ])
        goal = Goal(metric="custom_metric", target_value=1.0, baseline_value=0.5, direction="above")
        subgoals = decomposer.decompose(goal)
        assert len(subgoals) == 1
        assert subgoals[0].objective == "Custom Action"

    def test_remove_rule(self):
        decomposer = GoalDecomposer()
        assert decomposer.remove_rule("roas")
        assert "roas" not in decomposer.get_rules()

    def test_get_supported_metrics(self):
        decomposer = GoalDecomposer()
        metrics = decomposer.get_supported_metrics()
        assert "roas" in metrics
        assert "revenue" in metrics
        assert "ctr" in metrics

    def test_get_rules_returns_copy(self):
        decomposer = GoalDecomposer()
        rules = decomposer.get_rules()
        rules["new_key"] = []
        assert "new_key" not in decomposer.get_rules()

    def test_decompose_below_direction(self):
        goal = Goal(metric="spend", target_value=500, baseline_value=800, current_value=800, direction="below")
        decomposer = GoalDecomposer()
        subgoals = decomposer.decompose(goal)
        for sg in subgoals:
            assert sg.direction == "below"

    def test_subgoal_initial_status(self, roas_goal):
        decomposer = GoalDecomposer()
        subgoals = decomposer.decompose(roas_goal)
        for sg in subgoals:
            assert sg.status == GoalStatus.CREATED

    def test_strategy_enum_values(self):
        assert SubGoalStrategy.CREATIVE_EVOLUTION.value == "creative_evolution"
        assert SubGoalStrategy.BUDGET_OPTIMIZATION.value == "budget_optimization"
        assert SubGoalStrategy.AUDIENCE_EXPANSION.value == "audience_expansion"


# ═══════════════════════════════════════════════════════════════════
# 5. Progress Tracker Tests (20 tests)
# ═══════════════════════════════════════════════════════════════════


class TestProgressTracker:
    """进度追踪器测试."""

    def test_track_goal_initial(self, roas_goal):
        tracker = ProgressTracker()
        progress = tracker.track_goal(roas_goal, {"roas": 0.45})
        assert progress.progress == 0.0
        assert progress.current_value == 0.45

    def test_track_goal_progress(self, roas_goal):
        tracker = ProgressTracker()
        progress = tracker.track_goal(roas_goal, {"roas": 0.55})
        assert progress.progress == 0.5

    def test_track_goal_updates_current_value(self, roas_goal):
        tracker = ProgressTracker()
        tracker.track_goal(roas_goal, {"roas": 0.55})
        assert roas_goal.current_value == 0.55

    def test_track_goal_trend_data(self, roas_goal):
        tracker = ProgressTracker()
        tracker.track_goal(roas_goal, {"roas": 0.50})
        tracker.track_goal(roas_goal, {"roas": 0.55})
        progress = tracker.track_goal(roas_goal, {"roas": 0.60})
        assert len(progress.trend_data) == 3

    def test_track_goal_trend_improving(self, roas_goal):
        tracker = ProgressTracker()
        tracker.track_goal(roas_goal, {"roas": 0.50})
        tracker.track_goal(roas_goal, {"roas": 0.55})
        progress = tracker.track_goal(roas_goal, {"roas": 0.60})
        assert progress.trend == ProgressTrend.IMPROVING

    def test_track_goal_trend_declining(self, roas_goal):
        tracker = ProgressTracker()
        tracker.track_goal(roas_goal, {"roas": 0.60})
        tracker.track_goal(roas_goal, {"roas": 0.55})
        progress = tracker.track_goal(roas_goal, {"roas": 0.50})
        assert progress.trend == ProgressTrend.DECLINING

    def test_track_goal_trend_stable(self, roas_goal):
        tracker = ProgressTracker()
        tracker.track_goal(roas_goal, {"roas": 0.55})
        tracker.track_goal(roas_goal, {"roas": 0.55})
        progress = tracker.track_goal(roas_goal, {"roas": 0.55})
        assert progress.trend == ProgressTrend.STABLE

    def test_track_goal_trend_unknown_single_point(self, roas_goal):
        tracker = ProgressTracker()
        progress = tracker.track_goal(roas_goal, {"roas": 0.55})
        assert progress.trend == ProgressTrend.UNKNOWN

    def test_track_subgoal(self):
        tracker = ProgressTracker()
        sg = SubGoal(
            metric="ctr", target=0.05, baseline=0.03,
            current_value=0.03, direction="above",
        )
        updated = tracker.track_subgoal(sg, {"ctr": 0.04})
        assert updated.progress == 0.5

    def test_track_all_subgoals(self):
        tracker = ProgressTracker()
        sgs = [
            SubGoal(metric="ctr", target=0.05, baseline=0.03, current_value=0.03, direction="above"),
            SubGoal(metric="cpi", target=2.0, baseline=3.0, current_value=3.0, direction="below"),
        ]
        updated = tracker.track_all_subgoals(sgs, {"ctr": 0.04, "cpi": 2.5})
        assert updated[0].progress == 0.5
        assert updated[1].progress == 0.5

    def test_get_progress(self, roas_goal):
        tracker = ProgressTracker()
        tracker.track_goal(roas_goal, {"roas": 0.55})
        cached = tracker.get_progress(roas_goal.goal_id)
        assert cached is not None
        assert cached.progress == 0.5

    def test_get_progress_nonexistent(self):
        tracker = ProgressTracker()
        assert tracker.get_progress("nonexistent") is None

    def test_get_all_progress(self, roas_goal, spend_goal):
        tracker = ProgressTracker()
        tracker.track_goal(roas_goal, {"roas": 0.55})
        tracker.track_goal(spend_goal, {"spend": 550})
        all_progress = tracker.get_all_progress()
        assert len(all_progress) == 2

    def test_get_progress_summary(self, roas_goal):
        tracker = ProgressTracker()
        tracker.track_goal(roas_goal, {"roas": 0.55})
        summary = tracker.get_progress_summary(roas_goal.goal_id)
        assert summary is not None
        assert summary["progress"] == 0.5

    def test_estimated_completion(self, roas_goal):
        tracker = ProgressTracker()
        tracker.track_goal(roas_goal, {"roas": 0.50})
        progress = tracker.track_goal(roas_goal, {"roas": 0.55})
        # With improving trend, should estimate completion
        assert progress.estimated_completion is not None

    def test_trend_data_max_points(self, roas_goal):
        tracker = ProgressTracker(max_trend_points=3)
        for i in range(5):
            tracker.track_goal(roas_goal, {"roas": 0.45 + i * 0.02})
        progress = tracker.get_progress(roas_goal.goal_id)
        assert len(progress.trend_data) == 3

    def test_track_count(self, roas_goal):
        tracker = ProgressTracker()
        assert tracker.track_count == 0
        tracker.track_goal(roas_goal, {"roas": 0.55})
        assert tracker.track_count == 1

    def test_reset(self, roas_goal):
        tracker = ProgressTracker()
        tracker.track_goal(roas_goal, {"roas": 0.55})
        tracker.reset()
        assert tracker.track_count == 0
        assert tracker.get_progress(roas_goal.goal_id) is None

    def test_remaining_gap(self, roas_goal):
        tracker = ProgressTracker()
        progress = tracker.track_goal(roas_goal, {"roas": 0.55})
        assert progress.remaining_gap == pytest.approx(0.5)

    def test_get_trend_data(self, roas_goal):
        tracker = ProgressTracker()
        tracker.track_goal(roas_goal, {"roas": 0.55})
        data = tracker.get_trend_data(roas_goal.goal_id)
        assert len(data) == 1
        assert data[0]["progress"] == 0.5


# ═══════════════════════════════════════════════════════════════════
# 6. Goal Evaluator Tests (15 tests)
# ═══════════════════════════════════════════════════════════════════


class TestGoalEvaluator:
    """目标评估器测试."""

    def test_evaluate_achieved(self, roas_goal):
        evaluator = GoalEvaluator()
        roas_goal.current_value = 0.65
        assert evaluator.evaluate(roas_goal) == GoalStatus.ACHIEVED

    def test_evaluate_active(self, roas_goal):
        evaluator = GoalEvaluator()
        roas_goal.current_value = 0.55
        roas_goal.status = GoalStatus.ACTIVE
        assert evaluator.evaluate(roas_goal) == GoalStatus.ACTIVE

    def test_evaluate_expired_failed(self):
        evaluator = GoalEvaluator()
        goal = Goal(
            metric="roas", baseline_value=0.4, target_value=0.6,
            current_value=0.45,
            deadline="2020-01-01T00:00:00+00:00",
        )
        assert evaluator.evaluate(goal) == GoalStatus.FAILED

    def test_evaluate_expired_near_completion(self):
        evaluator = GoalEvaluator()
        goal = Goal(
            metric="roas", baseline_value=0.4, target_value=0.6,
            current_value=0.58,  # progress = 0.9
            deadline="2020-01-01T00:00:00+00:00",
        )
        assert evaluator.evaluate(goal) == GoalStatus.ACHIEVED

    def test_evaluate_batch(self, roas_goal, spend_goal):
        evaluator = GoalEvaluator()
        roas_goal.current_value = 0.65
        spend_goal.current_value = 550
        results = evaluator.evaluate_batch([roas_goal, spend_goal])
        assert results[roas_goal.goal_id] == GoalStatus.ACHIEVED
        assert results[spend_goal.goal_id] == GoalStatus.ACTIVE

    def test_evaluate_subgoal_achieved(self):
        evaluator = GoalEvaluator()
        sg = SubGoal(
            metric="ctr", target=0.05, baseline=0.03,
            current_value=0.05, direction="above",
        )
        assert evaluator.evaluate_subgoal(sg) == GoalStatus.ACHIEVED

    def test_evaluate_subgoal_active(self):
        evaluator = GoalEvaluator()
        sg = SubGoal(
            metric="ctr", target=0.05, baseline=0.03,
            current_value=0.04, direction="above",
        )
        assert evaluator.evaluate_subgoal(sg) == GoalStatus.ACTIVE

    def test_evaluate_subgoals_batch(self):
        evaluator = GoalEvaluator()
        sgs = [
            SubGoal(metric="ctr", target=0.05, baseline=0.03, current_value=0.05, direction="above"),
            SubGoal(metric="cpi", target=2.0, baseline=3.0, current_value=2.5, direction="below"),
        ]
        results = evaluator.evaluate_subgoals(sgs)
        assert len(results) == 2

    def test_build_result(self, roas_goal):
        evaluator = GoalEvaluator()
        roas_goal.current_value = 0.65
        roas_goal.status = GoalStatus.ACTIVE
        subgoals = [
            SubGoal(parent_goal_id=roas_goal.goal_id, status=GoalStatus.ACHIEVED),
            SubGoal(parent_goal_id=roas_goal.goal_id, status=GoalStatus.ACHIEVED),
            SubGoal(parent_goal_id=roas_goal.goal_id, status=GoalStatus.FAILED),
        ]
        result = evaluator.build_result(roas_goal, subgoals)
        assert result.status == GoalStatus.ACHIEVED
        assert result.subgoals_completed == 2
        assert result.subgoals_total == 3

    def test_build_result_failed(self, roas_goal):
        evaluator = GoalEvaluator()
        roas_goal.current_value = 0.48
        roas_goal.status = GoalStatus.ACTIVE
        past_deadline = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        roas_goal.deadline = past_deadline
        subgoals = [
            SubGoal(parent_goal_id=roas_goal.goal_id, status=GoalStatus.FAILED),
        ]
        result = evaluator.build_result(roas_goal, subgoals)
        assert result.status == GoalStatus.FAILED

    def test_needs_adaptation_declining(self, roas_goal):
        evaluator = GoalEvaluator()
        progress = GoalProgress(
            goal_id=roas_goal.goal_id,
            trend=ProgressTrend.DECLINING,
            trend_data=[{"progress": p} for p in [0.5, 0.4, 0.3]],
        )
        assert evaluator.needs_adaptation(roas_goal, progress)

    def test_needs_adaptation_stagnant(self, roas_goal):
        evaluator = GoalEvaluator()
        progress = GoalProgress(
            goal_id=roas_goal.goal_id,
            trend=ProgressTrend.STABLE,
            trend_data=[{"progress": 0.5} for _ in range(4)],
        )
        assert evaluator.needs_adaptation(roas_goal, progress)

    def test_needs_adaptation_improving(self, roas_goal):
        evaluator = GoalEvaluator()
        progress = GoalProgress(
            goal_id=roas_goal.goal_id,
            trend=ProgressTrend.IMPROVING,
            trend_data=[{"progress": p} for p in [0.3, 0.4, 0.5]],
            remaining_gap=0.3,
        )
        assert not evaluator.needs_adaptation(roas_goal, progress)

    def test_needs_adaptation_large_gap(self, roas_goal):
        evaluator = GoalEvaluator()
        progress = GoalProgress(
            goal_id=roas_goal.goal_id,
            trend=ProgressTrend.STABLE,
            remaining_gap=0.6,
            trend_data=[{"progress": p} for p in [0.2, 0.25, 0.3]],
        )
        assert evaluator.needs_adaptation(roas_goal, progress)

    def test_evaluation_count(self, roas_goal):
        evaluator = GoalEvaluator()
        assert evaluator.evaluation_count == 0
        evaluator.evaluate(roas_goal)
        assert evaluator.evaluation_count == 1


# ═══════════════════════════════════════════════════════════════════
# 7. GoalAdaptation & GoalResult Model Tests
# ═══════════════════════════════════════════════════════════════════


class TestGoalAdaptation:
    """目标调整和结果测试."""

    def test_create_adaptation(self):
        a = GoalAdaptation(
            goal_id="g1",
            reason="ROAS declining",
            previous_target=0.65,
            new_target=0.60,
            previous_strategy="creative_evolution",
            new_strategy="budget_optimization",
        )
        assert a.goal_id == "g1"
        assert a.reason == "ROAS declining"

    def test_adaptation_to_dict(self):
        a = GoalAdaptation(
            goal_id="g1",
            reason="Test",
            previous_target=0.65,
            new_target=0.60,
            previous_subgoals=["sg1", "sg2"],
            new_subgoals=["sg3", "sg4", "sg5"],
        )
        d = a.to_dict()
        assert d["previous_target"] == 0.65
        assert len(d["previous_subgoals"]) == 2

    def test_create_goal_result(self):
        result = GoalResult(
            goal_id="g1",
            goal_name="ROAS",
            status=GoalStatus.ACHIEVED,
            final_value=0.67,
            target_value=0.65,
            achievement_rate=1.0,
            duration_days=30,
            subgoals_completed=3,
            subgoals_total=4,
            lessons=["Creative evolution worked"],
        )
        assert result.status == GoalStatus.ACHIEVED
        assert result.subgoals_completed == 3

    def test_goal_result_to_dict(self):
        result = GoalResult(
            goal_id="g1",
            goal_name="ROAS",
            status=GoalStatus.ACHIEVED,
            final_value=0.67,
            target_value=0.65,
        )
        d = result.to_dict()
        assert d["status"] == "achieved"
        assert d["final_value"] == 0.67


# ═══════════════════════════════════════════════════════════════════
# 8. GoalManager Integration Tests (10 tests)
# ═══════════════════════════════════════════════════════════════════


class TestGoalManager:
    """GoalManager 集成测试."""

    def test_create_goal(self, goal_manager):
        goal = goal_manager.create_goal(
            name="Increase ROAS",
            metric="roas",
            target_value=0.65,
            baseline_value=0.45,
        )
        assert goal.name == "Increase ROAS"
        assert goal.status == GoalStatus.CREATED
        assert goal_manager.get_goal(goal.goal_id) is goal

    def test_activate_goal(self, goal_manager):
        goal = goal_manager.create_goal(
            name="Test", metric="roas", target_value=0.8, baseline_value=0.5,
        )
        assert goal_manager.activate_goal(goal.goal_id)
        assert goal.status == GoalStatus.ACTIVE

    def test_activate_already_active(self, goal_manager):
        goal = goal_manager.create_goal(
            name="Test", metric="roas", target_value=0.8, baseline_value=0.5,
        )
        goal_manager.activate_goal(goal.goal_id)
        assert not goal_manager.activate_goal(goal.goal_id)

    def test_pause_and_resume_goal(self, goal_manager):
        goal = goal_manager.create_goal(
            name="Test", metric="roas", target_value=0.8, baseline_value=0.5,
        )
        goal_manager.activate_goal(goal.goal_id)
        assert goal_manager.pause_goal(goal.goal_id)
        assert goal.status == GoalStatus.PAUSED
        assert goal_manager.resume_goal(goal.goal_id)
        assert goal.status == GoalStatus.ACTIVE

    def test_cancel_goal(self, goal_manager):
        goal = goal_manager.create_goal(
            name="Test", metric="roas", target_value=0.8, baseline_value=0.5,
        )
        goal_manager.activate_goal(goal.goal_id)
        assert goal_manager.cancel_goal(goal.goal_id)
        assert goal.status == GoalStatus.CANCELLED

    def test_decompose_goal(self, goal_manager):
        goal = goal_manager.create_goal(
            name="ROAS", metric="roas", target_value=0.65, baseline_value=0.45,
        )
        goal_manager.activate_goal(goal.goal_id)
        subgoals = goal_manager.decompose_goal(goal.goal_id)
        assert len(subgoals) == 4
        assert len(goal_manager.get_subgoals(goal.goal_id)) == 4

    def test_update_progress(self, goal_manager):
        goal = goal_manager.create_goal(
            name="ROAS", metric="roas", target_value=0.65, baseline_value=0.45,
        )
        goal_manager.activate_goal(goal.goal_id)
        progress = goal_manager.update_progress(goal.goal_id, {"roas": 0.55})
        assert progress is not None
        assert progress.progress == 0.5

    def test_evaluate_goal(self, goal_manager):
        goal = goal_manager.create_goal(
            name="ROAS", metric="roas", target_value=0.65, baseline_value=0.45,
        )
        goal_manager.activate_goal(goal.goal_id)
        goal_manager.update_progress(goal.goal_id, {"roas": 0.65})
        status = goal_manager.evaluate_goal(goal.goal_id)
        assert status == GoalStatus.ACHIEVED

    def test_adapt_goal(self, goal_manager):
        goal = goal_manager.create_goal(
            name="ROAS", metric="roas", target_value=0.65, baseline_value=0.45,
        )
        goal_manager.activate_goal(goal.goal_id)
        goal_manager.decompose_goal(goal.goal_id)
        adaptation = goal_manager.adapt_goal(
            goal.goal_id,
            reason="ROAS declining despite creative changes",
            new_target=0.60,
        )
        assert adaptation is not None
        assert adaptation.new_target == 0.60
        assert goal.target_value == 0.60

    def test_get_goal_summary(self, goal_manager):
        goal = goal_manager.create_goal(
            name="ROAS", metric="roas", target_value=0.65, baseline_value=0.45,
        )
        goal_manager.activate_goal(goal.goal_id)
        goal_manager.update_progress(goal.goal_id, {"roas": 0.55})
        summary = goal_manager.get_goal_summary(goal.goal_id)
        assert summary is not None
        assert summary["goal"]["name"] == "ROAS"
        assert summary["progress"] is not None

    def test_get_stats(self, goal_manager):
        goal_manager.create_goal(name="Test", metric="roas", target_value=0.8, baseline_value=0.5)
        stats = goal_manager.get_stats()
        assert stats["store"]["total_goals"] == 1

    def test_full_workflow(self, goal_manager):
        """完整工作流: 创建 → 激活 → 拆解 → 追踪 → 评估 → 结果."""
        # 1. 创建
        goal = goal_manager.create_goal(
            name="Increase ROAS",
            metric="roas",
            target_value=0.65,
            baseline_value=0.45,
            priority=GoalPriority.P1,
        )
        assert goal.status == GoalStatus.CREATED

        # 2. 激活
        goal_manager.activate_goal(goal.goal_id)
        assert goal.status == GoalStatus.ACTIVE

        # 3. 拆解
        subgoals = goal_manager.decompose_goal(goal.goal_id)
        assert len(subgoals) > 0

        # 4. 追踪 (模拟 3 周进度)
        progress = goal_manager.update_progress(goal.goal_id, {"roas": 0.55})
        assert progress.progress == 0.5

        # 5. 评估
        status = goal_manager.evaluate_goal(goal.goal_id)
        assert status == GoalStatus.ACTIVE

        # 6. 最终达成
        goal_manager.update_progress(goal.goal_id, {"roas": 0.65})
        status = goal_manager.evaluate_goal(goal.goal_id)
        assert status == GoalStatus.ACHIEVED

        # 7. 构建结果
        result = goal_manager.build_result(goal.goal_id)
        assert result is not None
        assert result.status == GoalStatus.ACHIEVED