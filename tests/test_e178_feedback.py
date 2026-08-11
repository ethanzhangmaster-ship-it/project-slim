"""E17.8 Feedback Ingestion — 测试用例.

Day 7.8 Step 4:
  覆盖 Feedback Ingestion 层的:
    - FeedbackClassification / FeedbackAction 枚举
    - LearningFeedback 模型 (factory methods, properties, classification, serialization)
    - LearningFeedbackRouter 引擎 (route, route_batch, query, stats, reset)
    - Orchestrator 集成 (FEEDBACK_INGESTION 阶段)
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_feedback_models import (
    FeedbackAction,
    FeedbackClassification,
    LearningFeedback,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.outcome_measurement_models import (
    OutcomeMeasurement,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_feedback_router import (
    LearningFeedbackRouter,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def empty_router() -> LearningFeedbackRouter:
    """空路由器."""
    return LearningFeedbackRouter()


@pytest.fixture
def good_outcome() -> OutcomeMeasurement:
    """正向学习结果."""
    return OutcomeMeasurement.from_execution(
        cycle_number=1,
        execution_action="execute_learning",
        execution_success=True,
        metrics_before={"roas": 0.8, "ctr": 2.1, "cvr": 5.0},
        metrics_after={"roas": 0.95, "ctr": 2.4, "cvr": 5.5},
        strategy_state_before={"learning_mode": "balanced", "exploration_rate": 0.3},
        strategy_state_after={"learning_mode": "balanced", "exploration_rate": 0.25},
        measurement_confidence=0.8,
    )


@pytest.fixture
def bad_outcome() -> OutcomeMeasurement:
    """负向学习结果."""
    return OutcomeMeasurement.from_execution(
        cycle_number=2,
        execution_action="execute_learning",
        execution_success=True,
        metrics_before={"roas": 1.2, "ctr": 3.0, "cvr": 6.0},
        metrics_after={"roas": 0.8, "ctr": 2.5, "cvr": 5.0},
        strategy_state_before={"learning_mode": "balanced", "exploration_rate": 0.2},
        strategy_state_after={"learning_mode": "aggressive", "exploration_rate": 0.4},
        measurement_confidence=0.6,
    )


@pytest.fixture
def stagnant_outcome() -> OutcomeMeasurement:
    """停滞学习结果 — 执行成功但指标无变化."""
    return OutcomeMeasurement(
        is_measurable=True,
        learning_gain=0.03,  # |gain| <= 0.05 → STAGNANT
        reward_delta=0.0,
        confidence_delta=0.0,
        success_delta=1.0,
        execution_action="execute_learning",
        execution_success=True,
        cycle_number=3,
    )


@pytest.fixture
def not_measurable_outcome() -> OutcomeMeasurement:
    """不可测量结果."""
    return OutcomeMeasurement.not_measurable(
        cycle_number=0, reason="No execution result"
    )


@pytest.fixture
def strong_positive_outcome() -> OutcomeMeasurement:
    """强正向结果."""
    return OutcomeMeasurement.from_execution(
        cycle_number=1,
        execution_action="execute_learning",
        execution_success=True,
        metrics_before={"roas": 0.3, "ctr": 1.0, "cvr": 2.0},
        metrics_after={"roas": 1.5, "ctr": 3.0, "cvr": 8.0},
    )


# ═══════════════════════════════════════════════════════════════
# Section 1: FeedbackClassification & FeedbackAction
# ═══════════════════════════════════════════════════════════════


class TestFeedbackClassification:
    """FeedbackClassification 枚举测试."""

    def test_values(self) -> None:
        assert FeedbackClassification.GOOD_LEARNING.value == "good_learning"
        assert FeedbackClassification.BAD_LEARNING.value == "bad_learning"
        assert FeedbackClassification.INSUFFICIENT_DATA.value == "insufficient_data"
        assert FeedbackClassification.STAGNANT.value == "stagnant"

    def test_all_four_categories(self) -> None:
        assert len(FeedbackClassification) == 4


class TestFeedbackAction:
    """FeedbackAction 枚举测试."""

    def test_values(self) -> None:
        assert FeedbackAction.INCREASE_CONFIDENCE.value == "increase_confidence"
        assert FeedbackAction.SCALE_UP.value == "scale_up"
        assert FeedbackAction.REDUCE_EXPLORATION.value == "reduce_exploration"
        assert FeedbackAction.ROLLBACK_STRATEGY.value == "rollback_strategy"
        assert FeedbackAction.CONTINUE_SAMPLING.value == "continue_sampling"
        assert FeedbackAction.INVESTIGATE.value == "investigate"
        assert FeedbackAction.MAINTAIN.value == "maintain"
        assert FeedbackAction.ADJUST_WEIGHTS.value == "adjust_weights"

    def test_all_eight_actions(self) -> None:
        assert len(FeedbackAction) == 8


# ═══════════════════════════════════════════════════════════════
# Section 2: LearningFeedback Model
# ═══════════════════════════════════════════════════════════════


class TestLearningFeedbackDefaults:
    """LearningFeedback 默认值测试."""

    def test_default(self) -> None:
        f = LearningFeedback()
        assert f.feedback_id != ""
        assert f.cycle_number == 0
        assert f.classification == FeedbackClassification.INSUFFICIENT_DATA.value
        assert f.actions == []
        assert f.confidence_adjustment == 0.0
        assert f.exploration_adjustment == 0.0
        assert f.is_actionable is False
        assert f.outcome_measurement is None
        assert f.effectiveness is None

    def test_default_properties(self) -> None:
        f = LearningFeedback()
        assert f.is_good is False
        assert f.is_bad is False
        assert f.is_insufficient is True
        assert f.is_stagnant is False
        assert f.has_effectiveness is False
        assert f.has_outcome is False


class TestLearningFeedbackClassification:
    """分类逻辑测试."""

    def test_good_learning(self, good_outcome: OutcomeMeasurement) -> None:
        """正向学习."""
        f = LearningFeedback.from_measurement(good_outcome, cycle_number=1)
        assert f.classification == FeedbackClassification.GOOD_LEARNING.value
        assert f.is_good is True
        assert f.is_bad is False
        assert f.is_actionable is True
        assert FeedbackAction.INCREASE_CONFIDENCE.value in f.actions
        assert f.confidence_adjustment > 0.0
        assert f.exploration_adjustment < 0.0  # 减少探索

    def test_strong_positive(self, strong_positive_outcome: OutcomeMeasurement) -> None:
        """强正向."""
        f = LearningFeedback.from_measurement(strong_positive_outcome, cycle_number=1)
        assert f.classification == FeedbackClassification.GOOD_LEARNING.value
        assert FeedbackAction.SCALE_UP.value in f.actions
        assert "Strong learning gain" in f.recommendation

    def test_bad_learning(self, bad_outcome: OutcomeMeasurement) -> None:
        """负向学习."""
        f = LearningFeedback.from_measurement(bad_outcome, cycle_number=2)
        assert f.classification == FeedbackClassification.BAD_LEARNING.value
        assert f.is_bad is True
        assert f.is_actionable is True
        assert FeedbackAction.REDUCE_EXPLORATION.value in f.actions
        assert f.confidence_adjustment < 0.0
        assert f.exploration_adjustment < 0.0

    def test_stagnant(self, stagnant_outcome: OutcomeMeasurement) -> None:
        """停滞."""
        f = LearningFeedback.from_measurement(stagnant_outcome, cycle_number=3)
        assert f.classification == FeedbackClassification.STAGNANT.value
        assert f.is_stagnant is True
        assert FeedbackAction.MAINTAIN.value in f.actions
        assert f.confidence_adjustment == 0.0
        assert f.exploration_adjustment == 0.0

    def test_insufficient(self, not_measurable_outcome: OutcomeMeasurement) -> None:
        """不可测量."""
        f = LearningFeedback.from_measurement(not_measurable_outcome, cycle_number=0)
        assert f.classification == FeedbackClassification.INSUFFICIENT_DATA.value
        assert f.is_insufficient is True
        assert f.is_actionable is False
        assert FeedbackAction.CONTINUE_SAMPLING.value in f.actions

    def test_insufficient_none(self) -> None:
        """None outcome."""
        f = LearningFeedback.from_measurement(None, cycle_number=0)
        assert f.is_insufficient is True
        assert f.is_actionable is False


class TestLearningFeedbackBadLearningLevels:
    """负向学习分级测试."""

    def test_moderate_bad(self) -> None:
        """中等负向: REDUCE_EXPLORATION only (no INVESTIGATE)."""
        outcome = OutcomeMeasurement(
            is_measurable=True,
            learning_gain=-0.1,
            reward_delta=-0.1,
            success_delta=-1.0,
        )
        f = LearningFeedback.from_measurement(outcome, cycle_number=1)
        assert f.classification == FeedbackClassification.BAD_LEARNING.value
        assert FeedbackAction.REDUCE_EXPLORATION.value in f.actions
        # learning_gain=-0.1 在 [-0.15, -0.05) 区间，不加 INVESTIGATE
        assert FeedbackAction.INVESTIGATE.value not in f.actions

    def test_strong_bad(self) -> None:
        """强负向: ROLLBACK + INVESTIGATE."""
        outcome = OutcomeMeasurement(
            is_measurable=True,
            learning_gain=-0.5,
            reward_delta=-0.5,
            success_delta=-1.0,
        )
        f = LearningFeedback.from_measurement(outcome, cycle_number=1)
        assert f.classification == FeedbackClassification.BAD_LEARNING.value
        assert FeedbackAction.ROLLBACK_STRATEGY.value in f.actions
        assert FeedbackAction.INVESTIGATE.value in f.actions


class TestLearningFeedbackStagnantLevels:
    """停滞学习分级测试."""

    def test_true_plateau(self) -> None:
        """真正停滞: ADJUST_WEIGHTS."""
        outcome = OutcomeMeasurement(
            is_measurable=True,
            learning_gain=0.0,
            reward_delta=0.0,
            confidence_delta=0.0,
            success_delta=1.0,
        )
        f = LearningFeedback.from_measurement(outcome, cycle_number=1)
        assert FeedbackAction.ADJUST_WEIGHTS.value in f.actions

    def test_stagnant_with_failures(self) -> None:
        """停滞但有失败: 应为 INVESTIGATE (reward_delta > 0.02 避开 plateau)."""
        outcome = OutcomeMeasurement(
            is_measurable=True,
            learning_gain=0.0,
            reward_delta=0.05,  # > 0.02 避开 true_plateau 分支
            confidence_delta=0.0,
            success_delta=-1.0,
        )
        f = LearningFeedback.from_measurement(outcome, cycle_number=1)
        assert FeedbackAction.INVESTIGATE.value in f.actions
        assert "Stagnant with failures" in f.recommendation


class TestLearningFeedbackInsufficient:
    """INSUFFICIENT_DATA 工厂方法测试."""

    def test_insufficient_factory(self) -> None:
        f = LearningFeedback.insufficient(cycle_number=5, reason="No data")
        assert f.cycle_number == 5
        assert f.classification == FeedbackClassification.INSUFFICIENT_DATA.value
        assert f.is_actionable is False
        assert FeedbackAction.CONTINUE_SAMPLING.value in f.actions
        assert f.recommendation == "No data"

    def test_insufficient_default_reason(self) -> None:
        f = LearningFeedback.insufficient()
        assert "Insufficient data" in f.recommendation


class TestLearningFeedbackSerialization:
    """序列化测试."""

    def test_to_dict(self, good_outcome: OutcomeMeasurement) -> None:
        f = LearningFeedback.from_measurement(good_outcome, cycle_number=1)
        d = f.to_dict()
        assert d["cycle_number"] == 1
        assert d["classification"] == FeedbackClassification.GOOD_LEARNING.value
        assert isinstance(d["actions"], list)
        assert "confidence_adjustment" in d
        assert "exploration_adjustment" in d
        assert d["is_actionable"] is True
        assert d["is_good"] is True
        assert d["is_bad"] is False
        assert "outcome_measurement" in d
        assert "created_at" in d

    def test_to_dict_insufficient(self) -> None:
        f = LearningFeedback.insufficient(cycle_number=3)
        d = f.to_dict()
        assert d["cycle_number"] == 3
        assert d["is_actionable"] is False
        assert d["classification"] == "insufficient_data"


# ═══════════════════════════════════════════════════════════════
# Section 3: LearningFeedbackRouter
# ═══════════════════════════════════════════════════════════════


class TestFeedbackRouterInit:
    """LearningFeedbackRouter 初始化测试."""

    def test_init(self) -> None:
        router = LearningFeedbackRouter()
        assert router.route_count == 0
        assert router.get_history() == []
        assert router.get_latest() is None

    def test_repr(self) -> None:
        router = LearningFeedbackRouter()
        assert "LearningFeedbackRouter" in repr(router)
        assert "routes=0" in repr(router)


class TestFeedbackRouterRoute:
    """route() 方法测试."""

    def test_route_good(self, empty_router: LearningFeedbackRouter, good_outcome: OutcomeMeasurement) -> None:
        f = empty_router.route(good_outcome, cycle_number=1)
        assert f.is_good is True
        assert empty_router.route_count == 1

    def test_route_bad(self, empty_router: LearningFeedbackRouter, bad_outcome: OutcomeMeasurement) -> None:
        f = empty_router.route(bad_outcome, cycle_number=2)
        assert f.is_bad is True

    def test_route_stagnant(self, empty_router: LearningFeedbackRouter, stagnant_outcome: OutcomeMeasurement) -> None:
        f = empty_router.route(stagnant_outcome, cycle_number=3)
        assert f.is_stagnant is True

    def test_route_insufficient(self, empty_router: LearningFeedbackRouter, not_measurable_outcome: OutcomeMeasurement) -> None:
        f = empty_router.route(not_measurable_outcome, cycle_number=0)
        assert f.is_insufficient is True

    def test_route_none(self, empty_router: LearningFeedbackRouter) -> None:
        f = empty_router.route(None, cycle_number=0)
        assert f.is_insufficient is True

    def test_route_increments_count(self, empty_router: LearningFeedbackRouter, good_outcome: OutcomeMeasurement) -> None:
        empty_router.route(good_outcome, cycle_number=1)
        empty_router.route(good_outcome, cycle_number=2)
        assert empty_router.route_count == 2

    def test_route_with_effectiveness(self, empty_router: LearningFeedbackRouter, good_outcome: OutcomeMeasurement) -> None:
        """带 effectiveness 参数."""
        f = empty_router.route(good_outcome, cycle_number=1, effectiveness=None)
        assert f.is_good is True
        assert f.has_effectiveness is False


class TestFeedbackRouterBatch:
    """route_batch() 方法测试."""

    def test_route_batch(
        self,
        empty_router: LearningFeedbackRouter,
        good_outcome: OutcomeMeasurement,
        bad_outcome: OutcomeMeasurement,
        not_measurable_outcome: OutcomeMeasurement,
    ) -> None:
        results = empty_router.route_batch(
            [(good_outcome, 1), (bad_outcome, 2), (not_measurable_outcome, 0)],
        )
        assert len(results) == 3
        assert results[0].is_good
        assert results[1].is_bad
        assert results[2].is_insufficient
        assert empty_router.route_count == 3

    def test_route_batch_empty(self, empty_router: LearningFeedbackRouter) -> None:
        results = empty_router.route_batch([])
        assert results == []
        assert empty_router.route_count == 0


class TestFeedbackRouterQuery:
    """查询方法测试."""

    def test_get_history(self, empty_router: LearningFeedbackRouter, good_outcome: OutcomeMeasurement) -> None:
        empty_router.route(good_outcome, cycle_number=1)
        empty_router.route(good_outcome, cycle_number=2)
        history = empty_router.get_history()
        assert len(history) == 2
        assert history[0].cycle_number == 1
        assert history[1].cycle_number == 2

    def test_get_history_empty(self, empty_router: LearningFeedbackRouter) -> None:
        assert empty_router.get_history() == []

    def test_get_latest(self, empty_router: LearningFeedbackRouter, good_outcome: OutcomeMeasurement, bad_outcome: OutcomeMeasurement) -> None:
        empty_router.route(good_outcome, cycle_number=1)
        empty_router.route(bad_outcome, cycle_number=2)
        latest = empty_router.get_latest()
        assert latest is not None
        assert latest.cycle_number == 2
        assert latest.is_bad is True

    def test_get_latest_empty(self, empty_router: LearningFeedbackRouter) -> None:
        assert empty_router.get_latest() is None


class TestFeedbackRouterStats:
    """统计方法测试."""

    def test_get_stats_empty(self, empty_router: LearningFeedbackRouter) -> None:
        stats = empty_router.get_stats()
        assert stats["route_count"] == 0
        assert stats["good_count"] == 0
        assert stats["bad_count"] == 0
        assert stats["insufficient_count"] == 0
        assert stats["stagnant_count"] == 0
        assert stats["actionable_rate"] == 0.0

    def test_get_stats_with_data(
        self,
        empty_router: LearningFeedbackRouter,
        good_outcome: OutcomeMeasurement,
        bad_outcome: OutcomeMeasurement,
        stagnant_outcome: OutcomeMeasurement,
        not_measurable_outcome: OutcomeMeasurement,
    ) -> None:
        empty_router.route(good_outcome, cycle_number=1)
        empty_router.route(bad_outcome, cycle_number=2)
        empty_router.route(stagnant_outcome, cycle_number=3)
        empty_router.route(not_measurable_outcome, cycle_number=0)

        stats = empty_router.get_stats()
        assert stats["route_count"] == 4
        assert stats["good_count"] == 1
        assert stats["bad_count"] == 1
        assert stats["stagnant_count"] == 1
        assert stats["insufficient_count"] == 1
        assert stats["actionable_rate"] == 0.75  # 3/4 actionable

    def test_get_stats_actionable_rate(self, empty_router: LearningFeedbackRouter, good_outcome: OutcomeMeasurement) -> None:
        empty_router.route(good_outcome, cycle_number=1)
        empty_router.route(good_outcome, cycle_number=2)
        stats = empty_router.get_stats()
        assert stats["actionable_rate"] == 1.0


class TestFeedbackRouterReset:
    """reset() 方法测试."""

    def test_reset(self, empty_router: LearningFeedbackRouter, good_outcome: OutcomeMeasurement) -> None:
        empty_router.route(good_outcome, cycle_number=1)
        empty_router.route(good_outcome, cycle_number=2)
        assert empty_router.route_count == 2

        empty_router.reset()
        assert empty_router.route_count == 0
        assert empty_router.get_history() == []
        assert empty_router.get_latest() is None

    def test_reset_then_route(self, empty_router: LearningFeedbackRouter, good_outcome: OutcomeMeasurement) -> None:
        empty_router.route(good_outcome, cycle_number=1)
        empty_router.reset()
        f = empty_router.route(good_outcome, cycle_number=1)
        assert f.is_good
        assert empty_router.route_count == 1


# ═══════════════════════════════════════════════════════════════
# Section 4: Orchestrator Integration
# ═══════════════════════════════════════════════════════════════


class TestOrchestratorFeedbackIntegration:
    """Orchestrator 中的 Feedback Ingestion 集成测试."""

    def test_orchestrator_has_feedback_router(self) -> None:
        """Orchestrator 初始化时创建 FeedbackRouter."""
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_cycle_orchestrator import (
            LearningCycleOrchestrator,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_orchestration_models import (
            OrchestratorConfig,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_execution_adapter import (
            LearningExecutionAdapter,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_policy_controller import (
            LearningPolicyController,
        )

        orchestrator = LearningCycleOrchestrator(
            config=OrchestratorConfig.test_mode(),
            policy_controller=LearningPolicyController(),
            execution_adapter=LearningExecutionAdapter(),
        )
        assert orchestrator._feedback_router is not None
        assert isinstance(orchestrator._feedback_router, LearningFeedbackRouter)

    def test_feedback_after_single_cycle(self) -> None:
        """单周期后反馈为 INSUFFICIENT_DATA."""
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_cycle_orchestrator import (
            LearningCycleOrchestrator,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_orchestration_models import (
            OrchestratorConfig,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_execution_adapter import (
            LearningExecutionAdapter,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_policy_controller import (
            LearningPolicyController,
        )

        orchestrator = LearningCycleOrchestrator(
            config=OrchestratorConfig.test_mode(),
            policy_controller=LearningPolicyController(),
            execution_adapter=LearningExecutionAdapter(),
        )
        orchestrator.start()
        orchestrator.run_cycle()

        latest = orchestrator._feedback_router.get_latest()
        assert latest is not None
        assert latest.is_insufficient is True

    def test_feedback_after_two_cycles(self) -> None:
        """两个周期后反馈可分类."""
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_cycle_orchestrator import (
            LearningCycleOrchestrator,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_orchestration_models import (
            OrchestratorConfig,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_execution_adapter import (
            LearningExecutionAdapter,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_policy_controller import (
            LearningPolicyController,
        )

        orchestrator = LearningCycleOrchestrator(
            config=OrchestratorConfig.test_mode(),
            policy_controller=LearningPolicyController(),
            execution_adapter=LearningExecutionAdapter(),
        )
        orchestrator.start()
        orchestrator.run_cycle()
        orchestrator.run_cycle()

        latest = orchestrator._feedback_router.get_latest()
        assert latest is not None
        assert latest.is_insufficient is False  # 有数据了

    def test_feedback_history_grows(self) -> None:
        """反馈历史随周期增长."""
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_cycle_orchestrator import (
            LearningCycleOrchestrator,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_orchestration_models import (
            OrchestratorConfig,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_execution_adapter import (
            LearningExecutionAdapter,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_policy_controller import (
            LearningPolicyController,
        )

        orchestrator = LearningCycleOrchestrator(
            config=OrchestratorConfig.test_mode(),
            policy_controller=LearningPolicyController(),
            execution_adapter=LearningExecutionAdapter(),
        )
        orchestrator.start()
        orchestrator.run_cycle()
        orchestrator.run_cycle()
        orchestrator.run_cycle()

        history = orchestrator._feedback_router.get_history()
        assert len(history) == 3

    def test_feedback_stats_after_cycles(self) -> None:
        """多周期后反馈统计正确."""
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_cycle_orchestrator import (
            LearningCycleOrchestrator,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_orchestration_models import (
            OrchestratorConfig,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_execution_adapter import (
            LearningExecutionAdapter,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_policy_controller import (
            LearningPolicyController,
        )

        orchestrator = LearningCycleOrchestrator(
            config=OrchestratorConfig.test_mode(),
            policy_controller=LearningPolicyController(),
            execution_adapter=LearningExecutionAdapter(),
        )
        orchestrator.start()
        for _ in range(5):
            orchestrator.run_cycle()

        stats = orchestrator._feedback_router.get_stats()
        assert stats["route_count"] == 5
        # 第1个周期 insufficient，后4个有数据
        assert stats["insufficient_count"] == 1

    def test_feedback_accessible_via_orchestrator(self) -> None:
        """通过 Orchestrator 访问反馈路由器."""
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_cycle_orchestrator import (
            LearningCycleOrchestrator,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_orchestration_models import (
            OrchestratorConfig,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_execution_adapter import (
            LearningExecutionAdapter,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_policy_controller import (
            LearningPolicyController,
        )

        orchestrator = LearningCycleOrchestrator(
            config=OrchestratorConfig.test_mode(),
            policy_controller=LearningPolicyController(),
            execution_adapter=LearningExecutionAdapter(),
        )
        orchestrator.start()
        orchestrator.run_cycle()

        router = orchestrator._feedback_router
        assert isinstance(router, LearningFeedbackRouter)
        assert router.route_count == 1

    def test_state_transition_includes_feedback_ingestion(self) -> None:
        """状态转换包含 FEEDBACK_INGESTION."""
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_cycle_orchestrator import (
            LearningCycleOrchestrator,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_orchestration_models import (
            CycleOrchestrationState,
            OrchestratorConfig,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_execution_adapter import (
            LearningExecutionAdapter,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_policy_controller import (
            LearningPolicyController,
        )

        orchestrator = LearningCycleOrchestrator(
            config=OrchestratorConfig.test_mode(),
            policy_controller=LearningPolicyController(),
            execution_adapter=LearningExecutionAdapter(),
        )
        orchestrator.start()
        result = orchestrator.run_cycle()

        # 状态转换记录应包含 FEEDBACK_INGESTION
        states = [t["to"] for t in result.state_transitions]
        assert CycleOrchestrationState.FEEDBACK_INGESTION.value in states
        assert CycleOrchestrationState.MEASURE_OUTCOME.value in states
        assert CycleOrchestrationState.EVALUATE.value in states

    def test_feedback_ingestion_before_evaluate(self) -> None:
        """FEEDBACK_INGESTION 在 EVALUATE 之前."""
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_cycle_orchestrator import (
            LearningCycleOrchestrator,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_orchestration_models import (
            OrchestratorConfig,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_execution_adapter import (
            LearningExecutionAdapter,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_policy_controller import (
            LearningPolicyController,
        )

        orchestrator = LearningCycleOrchestrator(
            config=OrchestratorConfig.test_mode(),
            policy_controller=LearningPolicyController(),
            execution_adapter=LearningExecutionAdapter(),
        )
        orchestrator.start()
        result = orchestrator.run_cycle()

        states = [t["to"] for t in result.state_transitions]
        fb_idx = states.index("feedback_ingestion")
        eval_idx = states.index("evaluate")
        assert fb_idx < eval_idx


# ═══════════════════════════════════════════════════════════════
# Run
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])