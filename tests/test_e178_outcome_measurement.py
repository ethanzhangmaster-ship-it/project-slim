"""E17.8 Outcome Measurement — 测试用例.

Day 7.8 Step 3:
  覆盖 Outcome Measurement 层的:
    - MeasurementContext 模型
    - OutcomeMeasurement 模型 (factory methods, properties, computation)
    - OutcomeMeasurer 引擎 (measure, measure_from_context, measure_batch, query, stats, reset)
    - Orchestrator 集成 (MEASURE_OUTCOME 阶段)
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_execution_models import (
    LearningExecutionAction,
    LearningExecutionResult,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.outcome_measurement_models import (
    MeasurementContext,
    OutcomeMeasurement,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.outcome_measurement import (
    OutcomeMeasurer,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def empty_measurer() -> OutcomeMeasurer:
    """空测量器."""
    return OutcomeMeasurer()


@pytest.fixture
def success_execution() -> LearningExecutionResult:
    """成功执行结果."""
    return LearningExecutionResult.success_result(
        action=LearningExecutionAction.EXECUTE_LEARNING,
        policy_decision_type="explore",
        previous_state={"learning_mode": "balanced", "exploration_rate": 0.3},
        new_state={"learning_mode": "balanced", "exploration_rate": 0.25},
        reasons=["Learning loop executed successfully"],
        strategy_updated=True,
        memory_updated=True,
    )


@pytest.fixture
def blocked_execution() -> LearningExecutionResult:
    """BLOCK 执行结果."""
    return LearningExecutionResult.blocked_result(
        policy_decision_type="block_learning",
        previous_state={"learning_mode": "conservative", "exploration_rate": 0.1},
        reasons=["Effectiveness below threshold"],
    )


@pytest.fixture
def error_execution() -> LearningExecutionResult:
    """错误执行结果."""
    return LearningExecutionResult.error_result(
        action=LearningExecutionAction.EXECUTE_LEARNING,
        error="Memory consolidation failed",
        policy_decision_type="explore",
        previous_state={"learning_mode": "balanced", "exploration_rate": 0.3},
    )


@pytest.fixture
def metrics_improving() -> tuple[dict[str, float], dict[str, float]]:
    """改善中的业务指标."""
    before = {"roas": 0.8, "ctr": 2.1, "cvr": 5.0, "cpi": 3.5, "spend": 1000.0}
    after = {"roas": 0.95, "ctr": 2.4, "cvr": 5.5, "cpi": 3.2, "spend": 1050.0}
    return before, after


@pytest.fixture
def metrics_declining() -> tuple[dict[str, float], dict[str, float]]:
    """下降中的业务指标."""
    before = {"roas": 1.2, "ctr": 3.0, "cvr": 6.0}
    after = {"roas": 0.8, "ctr": 2.5, "cvr": 5.0}
    return before, after


@pytest.fixture
def metrics_stable() -> tuple[dict[str, float], dict[str, float]]:
    """稳定的业务指标."""
    before = {"roas": 1.0, "ctr": 2.5, "cvr": 5.5}
    after = {"roas": 1.0, "ctr": 2.5, "cvr": 5.5}
    return before, after


# ═══════════════════════════════════════════════════════════════
# Section 1: MeasurementContext
# ═══════════════════════════════════════════════════════════════


class TestMeasurementContext:
    """MeasurementContext 模型测试."""

    def test_default_context(self) -> None:
        """默认上下文."""
        ctx = MeasurementContext()
        assert ctx.execution_action == ""
        assert ctx.execution_success is False
        assert ctx.metrics_before == {}
        assert ctx.metrics_after == {}
        assert ctx.cycle_number == 0
        assert ctx.has_metrics is False
        assert ctx.has_strategy_state is False

    def test_has_metrics_true(self) -> None:
        """有完整指标."""
        ctx = MeasurementContext(
            metrics_before={"roas": 0.8},
            metrics_after={"roas": 0.95},
        )
        assert ctx.has_metrics is True

    def test_has_metrics_partial(self) -> None:
        """只有一侧指标."""
        ctx = MeasurementContext(
            metrics_before={"roas": 0.8},
        )
        assert ctx.has_metrics is False

    def test_has_metrics_empty(self) -> None:
        """无指标."""
        ctx = MeasurementContext()
        assert ctx.has_metrics is False

    def test_has_strategy_state_true(self) -> None:
        """有策略状态快照."""
        ctx = MeasurementContext(
            strategy_state_before={"mode": "balanced"},
            strategy_state_after={"mode": "aggressive"},
        )
        assert ctx.has_strategy_state is True

    def test_has_strategy_state_false(self) -> None:
        """无策略状态快照."""
        ctx = MeasurementContext()
        assert ctx.has_strategy_state is False

    def test_has_strategy_state_partial(self) -> None:
        """只有一侧策略状态."""
        ctx = MeasurementContext(
            strategy_state_before={"mode": "balanced"},
        )
        assert ctx.has_strategy_state is False

    def test_to_dict(self) -> None:
        """序列化."""
        ctx = MeasurementContext(
            execution_action="execute_learning",
            execution_success=True,
            metrics_before={"roas": 0.8},
            metrics_after={"roas": 0.95},
            strategy_state_before={"mode": "balanced"},
            strategy_state_after={"mode": "aggressive"},
            cycle_number=3,
        )
        d = ctx.to_dict()
        assert d["execution_action"] == "execute_learning"
        assert d["execution_success"] is True
        assert d["metrics_before"] == {"roas": 0.8}
        assert d["metrics_after"] == {"roas": 0.95}
        assert d["has_metrics"] is True
        assert d["has_strategy_state"] is True
        assert d["cycle_number"] == 3

    def test_full_context(self) -> None:
        """完整上下文."""
        ctx = MeasurementContext(
            execution_action="execute_learning",
            execution_success=True,
            metrics_before={"roas": 0.8, "ctr": 2.1},
            metrics_after={"roas": 0.95, "ctr": 2.4},
            strategy_state_before={"learning_mode": "balanced", "exploration_rate": 0.3},
            strategy_state_after={"learning_mode": "aggressive", "exploration_rate": 0.25},
            policy_decision_type="explore",
            cycle_number=5,
            metadata={"source": "test"},
        )
        assert ctx.execution_action == "execute_learning"
        assert ctx.execution_success is True
        assert ctx.has_metrics is True
        assert ctx.has_strategy_state is True
        assert ctx.policy_decision_type == "explore"
        assert ctx.cycle_number == 5
        assert ctx.metadata["source"] == "test"


# ═══════════════════════════════════════════════════════════════
# Section 2: OutcomeMeasurement Model
# ═══════════════════════════════════════════════════════════════


class TestOutcomeMeasurementModel:
    """OutcomeMeasurement 模型测试."""

    def test_default(self) -> None:
        """默认测量."""
        m = OutcomeMeasurement()
        assert m.measurement_id != ""
        assert m.cycle_number == 0
        assert m.execution_action == ""
        assert m.execution_success is False
        assert m.reward_delta == 0.0
        assert m.confidence_delta == 0.0
        assert m.success_delta == 0.0
        assert m.learning_gain == 0.0
        assert m.is_measurable is False
        assert m.is_positive is False
        assert m.is_negative is False
        assert m.is_significant is False
        assert m.is_high_confidence is False
        assert m.has_metric_data is False

    def test_not_measurable(self) -> None:
        """不可测量."""
        m = OutcomeMeasurement.not_measurable(
            cycle_number=3,
            reason="No execution result",
        )
        assert m.cycle_number == 3
        assert m.is_measurable is False
        assert m.measurement_confidence == 0.0
        assert len(m.recommendations) == 1
        assert "No execution result" in m.recommendations[0]

    def test_not_measurable_default_reason(self) -> None:
        """不可测量默认原因."""
        m = OutcomeMeasurement.not_measurable(cycle_number=0)
        assert len(m.recommendations) == 1
        assert "previous execution result" in m.recommendations[0]


class TestOutcomeMeasurementProperties:
    """OutcomeMeasurement 属性测试."""

    def test_is_positive(self) -> None:
        """>0 为正."""
        m = OutcomeMeasurement(learning_gain=0.3)
        assert m.is_positive is True
        assert m.is_negative is False

    def test_is_negative(self) -> None:
        """<0 为负."""
        m = OutcomeMeasurement(learning_gain=-0.3)
        assert m.is_positive is False
        assert m.is_negative is True

    def test_is_neutral(self) -> None:
        """=0 为中性."""
        m = OutcomeMeasurement(learning_gain=0.0)
        assert m.is_positive is False
        assert m.is_negative is False

    def test_is_significant_positive(self) -> None:
        """显著的 positive."""
        m = OutcomeMeasurement(learning_gain=0.1)
        assert m.is_significant is True

    def test_is_significant_negative(self) -> None:
        """显著的 negative."""
        m = OutcomeMeasurement(learning_gain=-0.1)
        assert m.is_significant is True

    def test_is_significant_false(self) -> None:
        """不显著 (<0.05)."""
        m = OutcomeMeasurement(learning_gain=0.03)
        assert m.is_significant is False

    def test_is_high_confidence(self) -> None:
        """高置信度."""
        m = OutcomeMeasurement(measurement_confidence=0.8)
        assert m.is_high_confidence is True

    def test_is_high_confidence_false(self) -> None:
        """低置信度."""
        m = OutcomeMeasurement(measurement_confidence=0.5)
        assert m.is_high_confidence is False

    def test_has_metric_data(self) -> None:
        """有指标数据."""
        m = OutcomeMeasurement(metrics_delta={"roas": 0.1})
        assert m.has_metric_data is True

    def test_has_metric_data_empty(self) -> None:
        """无指标数据."""
        m = OutcomeMeasurement()
        assert m.has_metric_data is False


class TestOutcomeMeasurementFromExecution:
    """from_execution 工厂方法测试."""

    def test_from_execution_basic(self) -> None:
        """基本执行结果."""
        m = OutcomeMeasurement.from_execution(
            cycle_number=1,
            execution_action="execute_learning",
            execution_success=True,
        )
        assert m.cycle_number == 1
        assert m.execution_action == "execute_learning"
        assert m.execution_success is True
        assert m.is_measurable is True
        assert m.success_delta == 1.0

    def test_from_execution_failed(self) -> None:
        """失败执行."""
        m = OutcomeMeasurement.from_execution(
            cycle_number=2,
            execution_action="execute_learning",
            execution_success=False,
        )
        assert m.execution_success is False
        assert m.success_delta == -1.0
        assert m.is_measurable is True

    def test_from_execution_no_action(self) -> None:
        """无动作."""
        m = OutcomeMeasurement.from_execution(
            cycle_number=0,
            execution_action="",
            execution_success=False,
        )
        assert m.is_measurable is False
        assert m.execution_action == ""

    def test_from_execution_with_metrics(
        self, metrics_improving: tuple[dict[str, float], dict[str, float]]
    ) -> None:
        """带业务指标."""
        before, after = metrics_improving
        m = OutcomeMeasurement.from_execution(
            cycle_number=1,
            execution_action="execute_learning",
            execution_success=True,
            metrics_before=before,
            metrics_after=after,
        )
        assert m.is_measurable is True
        assert m.metrics_before == before
        assert m.metrics_after == after
        assert len(m.metrics_delta) > 0
        # ROAS 改善 → reward_delta > 0
        assert m.reward_delta > 0.0

    def test_from_execution_with_declining_metrics(
        self, metrics_declining: tuple[dict[str, float], dict[str, float]]
    ) -> None:
        """带下降指标."""
        before, after = metrics_declining
        m = OutcomeMeasurement.from_execution(
            cycle_number=1,
            execution_action="execute_learning",
            execution_success=True,
            metrics_before=before,
            metrics_after=after,
        )
        # ROAS 下降 → reward_delta < 0
        assert m.reward_delta < 0.0

    def test_from_execution_stable_metrics(
        self, metrics_stable: tuple[dict[str, float], dict[str, float]]
    ) -> None:
        """稳定指标."""
        before, after = metrics_stable
        m = OutcomeMeasurement.from_execution(
            cycle_number=1,
            execution_action="execute_learning",
            execution_success=True,
            metrics_before=before,
            metrics_after=after,
        )
        # 指标无变化 → reward_delta ≈ 0
        assert abs(m.reward_delta) < 0.01

    def test_from_execution_with_strategy_change(self) -> None:
        """策略状态变化."""
        m = OutcomeMeasurement.from_execution(
            cycle_number=1,
            execution_action="update_strategy",
            execution_success=True,
            strategy_state_before={"learning_mode": "balanced", "exploration_rate": 0.3},
            strategy_state_after={"learning_mode": "conservative", "exploration_rate": 0.1},
        )
        assert m.strategy_change_detected is True
        # 探索率降低 → 置信度提升
        assert m.confidence_delta > 0.0

    def test_from_execution_strategy_mode_change(self) -> None:
        """策略模式切换."""
        m = OutcomeMeasurement.from_execution(
            cycle_number=1,
            execution_action="update_strategy",
            execution_success=True,
            strategy_state_before={"learning_mode": "balanced"},
            strategy_state_after={"learning_mode": "aggressive"},
        )
        assert m.strategy_change_detected is True
        # 激进模式 → 置信度下降
        assert m.confidence_delta < 0.0

    def test_from_execution_no_strategy_change(self) -> None:
        """策略状态无变化."""
        m = OutcomeMeasurement.from_execution(
            cycle_number=1,
            execution_action="execute_learning",
            execution_success=True,
            strategy_state_before={"learning_mode": "balanced"},
            strategy_state_after={"learning_mode": "balanced"},
        )
        assert m.strategy_change_detected is False

    def test_from_execution_no_strategy_state(self) -> None:
        """无策略状态."""
        m = OutcomeMeasurement.from_execution(
            cycle_number=1,
            execution_action="execute_learning",
            execution_success=True,
        )
        assert m.strategy_change_detected is False
        assert m.confidence_delta == 0.0

    def test_from_execution_with_confidence(self) -> None:
        """带测量置信度."""
        m = OutcomeMeasurement.from_execution(
            cycle_number=1,
            execution_action="execute_learning",
            execution_success=True,
            measurement_confidence=0.85,
        )
        assert m.measurement_confidence == 0.85


class TestOutcomeMeasurementComputation:
    """计算逻辑测试."""

    def test_metrics_delta_basic(self) -> None:
        """基本指标变化率."""
        delta = OutcomeMeasurement._compute_metrics_delta(
            {"roas": 1.0}, {"roas": 1.5}
        )
        assert delta["roas"] == 0.5

    def test_metrics_delta_decline(self) -> None:
        """指标下降."""
        delta = OutcomeMeasurement._compute_metrics_delta(
            {"roas": 1.0}, {"roas": 0.5}
        )
        assert delta["roas"] == -0.5

    def test_metrics_delta_new_key(self) -> None:
        """新增指标."""
        delta = OutcomeMeasurement._compute_metrics_delta(
            {"roas": 1.0}, {"roas": 1.0, "ctr": 3.0}
        )
        assert delta["roas"] == 0.0
        assert delta["ctr"] == 1.0  # new key with value

    def test_metrics_delta_zero_before(self) -> None:
        """before 为 0."""
        delta = OutcomeMeasurement._compute_metrics_delta(
            {"ctr": 0.0}, {"ctr": 2.5}
        )
        assert delta["ctr"] == 1.0

    def test_metrics_delta_both_zero(self) -> None:
        """before after 均为 0."""
        delta = OutcomeMeasurement._compute_metrics_delta(
            {"ctr": 0.0}, {"ctr": 0.0}
        )
        assert delta["ctr"] == 0.0

    def test_metrics_delta_multiple_keys(self) -> None:
        """多指标."""
        delta = OutcomeMeasurement._compute_metrics_delta(
            {"roas": 1.0, "ctr": 2.0, "cvr": 5.0},
            {"roas": 1.2, "ctr": 1.8, "cvr": 6.0},
        )
        assert delta["roas"] == pytest.approx(0.2, rel=0.01)
        assert delta["ctr"] == pytest.approx(-0.1, rel=0.01)
        assert delta["cvr"] == pytest.approx(0.2, rel=0.01)

    def test_reward_delta_positive(self) -> None:
        """正向奖励."""
        delta = OutcomeMeasurement._compute_reward_delta(
            {"roas": 1.0, "ctr": 2.0, "cvr": 5.0},
            {"roas": 1.5, "ctr": 2.5, "cvr": 6.0},
            {"roas": 0.5, "ctr": 0.25, "cvr": 0.2},
        )
        assert delta > 0.0

    def test_reward_delta_negative(self) -> None:
        """负向奖励."""
        delta = OutcomeMeasurement._compute_reward_delta(
            {"roas": 1.0, "ctr": 2.0, "cvr": 5.0},
            {"roas": 0.5, "ctr": 1.5, "cvr": 4.0},
            {"roas": -0.5, "ctr": -0.25, "cvr": -0.2},
        )
        assert delta < 0.0

    def test_reward_delta_no_metrics(self) -> None:
        """无指标."""
        delta = OutcomeMeasurement._compute_reward_delta({}, {}, {})
        assert delta == 0.0

    def test_reward_delta_bounded(self) -> None:
        """奖励在 [-1, 1] 范围内."""
        # 极大的正向变化
        delta = OutcomeMeasurement._compute_reward_delta(
            {"roas": 0.1}, {"roas": 10.0}, {"roas": 99.0}
        )
        assert -1.0 <= delta <= 1.0

    def test_confidence_delta_mode_change_to_conservative(self) -> None:
        """切换到保守模式."""
        delta = OutcomeMeasurement._compute_confidence_delta(
            {"learning_mode": "balanced"}, {"learning_mode": "conservative"}
        )
        assert delta > 0.0

    def test_confidence_delta_mode_change_to_aggressive(self) -> None:
        """切换到激进模式."""
        delta = OutcomeMeasurement._compute_confidence_delta(
            {"learning_mode": "balanced"}, {"learning_mode": "aggressive"}
        )
        assert delta < 0.0

    def test_confidence_delta_exploration_reduced(self) -> None:
        """探索率降低."""
        delta = OutcomeMeasurement._compute_confidence_delta(
            {"learning_mode": "balanced", "exploration_rate": 0.5},
            {"learning_mode": "balanced", "exploration_rate": 0.1},
        )
        assert delta > 0.0

    def test_confidence_delta_no_state(self) -> None:
        """无策略状态."""
        delta = OutcomeMeasurement._compute_confidence_delta(None, None)
        assert delta == 0.0

    def test_success_delta_success(self) -> None:
        """成功 → 1.0."""
        assert OutcomeMeasurement._compute_success_delta(True) == 1.0

    def test_success_delta_failure(self) -> None:
        """失败 → -1.0."""
        assert OutcomeMeasurement._compute_success_delta(False) == -1.0

    def test_learning_gain_positive(self) -> None:
        """正向学习增益."""
        gain = OutcomeMeasurement._compute_learning_gain(
            reward_delta=0.5, confidence_delta=0.2, success_delta=1.0
        )
        assert gain > 0.0
        assert gain == pytest.approx(0.5 * 0.5 + 0.2 * 0.2 + 1.0 * 0.3, rel=0.001)

    def test_learning_gain_negative(self) -> None:
        """负向学习增益."""
        gain = OutcomeMeasurement._compute_learning_gain(
            reward_delta=-0.5, confidence_delta=-0.2, success_delta=-1.0
        )
        assert gain < 0.0

    def test_learning_gain_bounded(self) -> None:
        """学习增益在 [-1, 1] 范围内."""
        gain = OutcomeMeasurement._compute_learning_gain(
            reward_delta=1.0, confidence_delta=1.0, success_delta=1.0
        )
        assert -1.0 <= gain <= 1.0

    def test_detect_strategy_change_true(self) -> None:
        """检测到策略变化."""
        assert (
            OutcomeMeasurement._detect_strategy_change(
                {"mode": "a"}, {"mode": "b"}
            )
            is True
        )

    def test_detect_strategy_change_false(self) -> None:
        """未检测到策略变化."""
        assert (
            OutcomeMeasurement._detect_strategy_change(
                {"mode": "a"}, {"mode": "a"}
            )
            is False
        )

    def test_detect_strategy_change_none_before(self) -> None:
        """before 为 None."""
        assert (
            OutcomeMeasurement._detect_strategy_change(
                None, {"mode": "a"}
            )
            is False
        )

    def test_detect_strategy_change_none_after(self) -> None:
        """after 为 None."""
        assert (
            OutcomeMeasurement._detect_strategy_change(
                {"mode": "a"}, None
            )
            is False
        )


class TestOutcomeMeasurementRecommendations:
    """建议生成测试."""

    def test_strong_positive(self) -> None:
        """强正向."""
        recs = OutcomeMeasurement._generate_recommendations(0.5, 0.3, 0.1)
        assert any("Strong positive" in r for r in recs)

    def test_moderate_positive(self) -> None:
        """中等正向."""
        recs = OutcomeMeasurement._generate_recommendations(0.1, 0.0, 0.0)
        assert any("Moderate positive" in r for r in recs)

    def test_neutral(self) -> None:
        """中性."""
        recs = OutcomeMeasurement._generate_recommendations(0.0, 0.0, 0.0)
        assert any("Neutral" in r for r in recs)

    def test_negative(self) -> None:
        """负向."""
        recs = OutcomeMeasurement._generate_recommendations(-0.2, 0.0, 0.0)
        assert any("Negative learning gain" in r for r in recs)

    def test_strong_negative(self) -> None:
        """强负向."""
        recs = OutcomeMeasurement._generate_recommendations(-0.5, 0.0, 0.0)
        assert any("Strong negative" in r for r in recs)

    def test_reward_improving(self) -> None:
        """奖励改善."""
        recs = OutcomeMeasurement._generate_recommendations(0.0, 0.3, 0.0)
        assert any("Business metrics improving" in r for r in recs)

    def test_reward_declining(self) -> None:
        """奖励下降."""
        recs = OutcomeMeasurement._generate_recommendations(0.0, -0.3, 0.0)
        assert any("Business metrics declining" in r for r in recs)

    def test_confidence_increasing(self) -> None:
        """置信度提升."""
        recs = OutcomeMeasurement._generate_recommendations(0.0, 0.0, 0.2)
        assert any("Decision confidence increasing" in r for r in recs)

    def test_confidence_decreasing(self) -> None:
        """置信度下降."""
        recs = OutcomeMeasurement._generate_recommendations(0.0, 0.0, -0.2)
        assert any("Decision confidence decreasing" in r for r in recs)


class TestOutcomeMeasurementSerialization:
    """序列化测试."""

    def test_to_dict(self) -> None:
        """to_dict 包含所有字段."""
        m = OutcomeMeasurement.from_execution(
            cycle_number=3,
            execution_action="execute_learning",
            execution_success=True,
            metrics_before={"roas": 0.8},
            metrics_after={"roas": 0.95},
            strategy_state_before={"mode": "balanced"},
            strategy_state_after={"mode": "aggressive"},
            measurement_confidence=0.8,
        )
        d = m.to_dict()
        assert d["cycle_number"] == 3
        assert d["execution_action"] == "execute_learning"
        assert d["execution_success"] is True
        assert d["metrics_before"] == {"roas": 0.8}
        assert d["metrics_after"] == {"roas": 0.95}
        assert "metrics_delta" in d
        assert d["strategy_change_detected"] is True
        assert d["measurement_confidence"] == 0.8
        assert "is_positive" in d
        assert "is_negative" in d
        assert "is_significant" in d
        assert "is_high_confidence" in d
        assert "has_metric_data" in d
        assert "recommendations" in d
        assert "created_at" in d

    def test_to_dict_not_measurable(self) -> None:
        """不可测量序列化."""
        m = OutcomeMeasurement.not_measurable(cycle_number=5, reason="test")
        d = m.to_dict()
        assert d["cycle_number"] == 5
        assert d["is_measurable"] is False


# ═══════════════════════════════════════════════════════════════
# Section 3: OutcomeMeasurer Engine
# ═══════════════════════════════════════════════════════════════


class TestOutcomeMeasurerInit:
    """OutcomeMeasurer 初始化测试."""

    def test_init(self) -> None:
        """初始化."""
        measurer = OutcomeMeasurer()
        assert measurer.measurement_count == 0
        assert measurer.get_history() == []
        assert measurer.get_latest() is None

    def test_repr(self) -> None:
        """__repr__."""
        measurer = OutcomeMeasurer()
        assert "OutcomeMeasurer" in repr(measurer)
        assert "measurements=0" in repr(measurer)


class TestOutcomeMeasurerMeasure:
    """measure() 方法测试."""

    def test_measure_none(self, empty_measurer: OutcomeMeasurer) -> None:
        """None 执行结果."""
        m = empty_measurer.measure(None)
        assert m.is_measurable is False
        assert empty_measurer.measurement_count == 1

    def test_measure_success(
        self, empty_measurer: OutcomeMeasurer, success_execution: LearningExecutionResult
    ) -> None:
        """成功执行结果."""
        m = empty_measurer.measure(success_execution, cycle_number=1)
        assert m.is_measurable is True
        assert m.execution_action == "execute_learning"
        assert m.execution_success is True
        assert m.success_delta == 1.0
        assert empty_measurer.measurement_count == 1

    def test_measure_blocked(
        self, empty_measurer: OutcomeMeasurer, blocked_execution: LearningExecutionResult
    ) -> None:
        """BLOCK 执行结果."""
        m = empty_measurer.measure(blocked_execution, cycle_number=2)
        assert m.is_measurable is True
        assert m.execution_action == "block_learning"
        assert m.execution_success is True
        assert m.success_delta == 1.0

    def test_measure_error(
        self, empty_measurer: OutcomeMeasurer, error_execution: LearningExecutionResult
    ) -> None:
        """错误执行结果."""
        m = empty_measurer.measure(error_execution, cycle_number=3)
        assert m.is_measurable is True
        assert m.execution_success is False
        assert m.success_delta == -1.0

    def test_measure_with_metrics(
        self,
        empty_measurer: OutcomeMeasurer,
        success_execution: LearningExecutionResult,
        metrics_improving: tuple[dict[str, float], dict[str, float]],
    ) -> None:
        """带业务指标."""
        before, after = metrics_improving
        m = empty_measurer.measure(
            success_execution,
            cycle_number=1,
            metrics_before=before,
            metrics_after=after,
        )
        assert m.has_metric_data is True
        assert m.reward_delta > 0.0  # 指标改善
        assert m.metrics_before == before
        assert m.metrics_after == after

    def test_measure_with_strategy_state(
        self,
        empty_measurer: OutcomeMeasurer,
        success_execution: LearningExecutionResult,
    ) -> None:
        """带策略状态."""
        m = empty_measurer.measure(
            success_execution,
            cycle_number=1,
            previous_strategy_state={"learning_mode": "balanced", "exploration_rate": 0.3},
            current_strategy_state={"learning_mode": "aggressive", "exploration_rate": 0.25},
        )
        assert m.strategy_change_detected is True

    def test_measure_increments_count(
        self, empty_measurer: OutcomeMeasurer, success_execution: LearningExecutionResult
    ) -> None:
        """递增计数."""
        empty_measurer.measure(success_execution)
        empty_measurer.measure(success_execution)
        empty_measurer.measure(None)
        assert empty_measurer.measurement_count == 3

    def test_measure_confidence_with_metrics(
        self,
        empty_measurer: OutcomeMeasurer,
        success_execution: LearningExecutionResult,
        metrics_improving: tuple[dict[str, float], dict[str, float]],
    ) -> None:
        """有完整指标时置信度高."""
        before, after = metrics_improving
        m = empty_measurer.measure(
            success_execution,
            metrics_before=before,
            metrics_after=after,
        )
        # 有完整指标 + 执行成功 + 策略更新 → 置信度 ≥ 0.7
        assert m.measurement_confidence >= 0.7

    def test_measure_confidence_without_metrics(
        self, empty_measurer: OutcomeMeasurer, success_execution: LearningExecutionResult
    ) -> None:
        """无指标时置信度较低."""
        m = empty_measurer.measure(success_execution)
        # 执行成功(+0.3) + 策略更新(+0.3) = 0.6
        assert m.measurement_confidence == 0.6

    def test_measure_confidence_failed_execution(
        self, empty_measurer: OutcomeMeasurer, error_execution: LearningExecutionResult
    ) -> None:
        """失败执行时置信度较低."""
        m = empty_measurer.measure(error_execution)
        assert m.measurement_confidence < 0.6


class TestOutcomeMeasurerMeasureFromContext:
    """measure_from_context() 方法测试."""

    def test_measure_from_context_with_metrics(self, empty_measurer: OutcomeMeasurer) -> None:
        """带指标的上下文."""
        ctx = MeasurementContext(
            execution_action="execute_learning",
            execution_success=True,
            metrics_before={"roas": 0.8},
            metrics_after={"roas": 0.95},
            strategy_state_before={"mode": "balanced"},
            strategy_state_after={"mode": "aggressive"},
            cycle_number=3,
        )
        m = empty_measurer.measure_from_context(ctx)
        assert m.is_measurable is True
        assert m.cycle_number == 3
        assert m.strategy_change_detected is True
        assert empty_measurer.measurement_count == 1

    def test_measure_from_context_empty(self, empty_measurer: OutcomeMeasurer) -> None:
        """空上下文."""
        ctx = MeasurementContext()
        m = empty_measurer.measure_from_context(ctx)
        assert m.is_measurable is False
        assert "No metrics" in m.recommendations[0]

    def test_measure_from_context_action_only(self, empty_measurer: OutcomeMeasurer) -> None:
        """仅有动作名."""
        ctx = MeasurementContext(execution_action="execute_learning")
        m = empty_measurer.measure_from_context(ctx)
        assert m.is_measurable is True
        assert m.execution_action == "execute_learning"


class TestOutcomeMeasurerBatch:
    """measure_batch() 方法测试."""

    def test_measure_batch(
        self, empty_measurer: OutcomeMeasurer, success_execution: LearningExecutionResult
    ) -> None:
        """批量测量."""
        results = empty_measurer.measure_batch(
            [(success_execution, 1), (success_execution, 2), (None, 3)],
        )
        assert len(results) == 3
        assert results[0].is_measurable is True
        assert results[0].cycle_number == 1
        assert results[1].cycle_number == 2
        assert results[2].is_measurable is False
        assert empty_measurer.measurement_count == 3

    def test_measure_batch_empty(self, empty_measurer: OutcomeMeasurer) -> None:
        """空批量."""
        results = empty_measurer.measure_batch([])
        assert results == []
        assert empty_measurer.measurement_count == 0

    def test_measure_batch_with_metrics(
        self,
        empty_measurer: OutcomeMeasurer,
        success_execution: LearningExecutionResult,
        metrics_improving: tuple[dict[str, float], dict[str, float]],
    ) -> None:
        """批量测量带指标."""
        before, after = metrics_improving
        results = empty_measurer.measure_batch(
            [(success_execution, 1), (success_execution, 2)],
            metrics_before=before,
            metrics_after=after,
        )
        assert len(results) == 2
        for r in results:
            assert r.has_metric_data is True


class TestOutcomeMeasurerQuery:
    """查询方法测试."""

    def test_get_history(
        self, empty_measurer: OutcomeMeasurer, success_execution: LearningExecutionResult
    ) -> None:
        """获取历史."""
        empty_measurer.measure(success_execution, cycle_number=1)
        empty_measurer.measure(success_execution, cycle_number=2)
        history = empty_measurer.get_history()
        assert len(history) == 2
        assert history[0].cycle_number == 1
        assert history[1].cycle_number == 2

    def test_get_history_empty(self, empty_measurer: OutcomeMeasurer) -> None:
        """空历史."""
        assert empty_measurer.get_history() == []

    def test_get_latest(
        self, empty_measurer: OutcomeMeasurer, success_execution: LearningExecutionResult
    ) -> None:
        """获取最新."""
        empty_measurer.measure(success_execution, cycle_number=1)
        empty_measurer.measure(success_execution, cycle_number=2)
        latest = empty_measurer.get_latest()
        assert latest is not None
        assert latest.cycle_number == 2

    def test_get_latest_empty(self, empty_measurer: OutcomeMeasurer) -> None:
        """无最新."""
        assert empty_measurer.get_latest() is None

    def test_get_stats_empty(self, empty_measurer: OutcomeMeasurer) -> None:
        """空统计."""
        stats = empty_measurer.get_stats()
        assert stats["measurement_count"] == 0
        assert stats["avg_learning_gain"] == 0.0
        assert stats["positive_count"] == 0
        assert stats["negative_count"] == 0
        assert stats["measurable_count"] == 0

    def test_get_stats_with_data(
        self,
        empty_measurer: OutcomeMeasurer,
        success_execution: LearningExecutionResult,
        metrics_improving: tuple[dict[str, float], dict[str, float]],
        metrics_declining: tuple[dict[str, float], dict[str, float]],
    ) -> None:
        """有数据的统计."""
        before_good, after_good = metrics_improving
        before_bad, after_bad = metrics_declining

        empty_measurer.measure(
            success_execution, cycle_number=1,
            metrics_before=before_good, metrics_after=after_good,
        )
        empty_measurer.measure(
            success_execution, cycle_number=2,
            metrics_before=before_bad, metrics_after=after_bad,
        )
        empty_measurer.measure(None, cycle_number=3)

        stats = empty_measurer.get_stats()
        assert stats["measurement_count"] == 3
        assert stats["measurable_count"] == 2
        assert stats["positive_count"] >= 0
        assert stats["negative_count"] >= 0

    def test_get_stats_history_independent(self, empty_measurer: OutcomeMeasurer) -> None:
        """get_stats 返回副本."""
        stats1 = empty_measurer.get_stats()
        stats1["measurement_count"] = 999
        stats2 = empty_measurer.get_stats()
        assert stats2["measurement_count"] == 0


class TestOutcomeMeasurerReset:
    """reset() 方法测试."""

    def test_reset(
        self, empty_measurer: OutcomeMeasurer, success_execution: LearningExecutionResult
    ) -> None:
        """重置."""
        empty_measurer.measure(success_execution, cycle_number=1)
        empty_measurer.measure(success_execution, cycle_number=2)
        assert empty_measurer.measurement_count == 2
        assert len(empty_measurer.get_history()) == 2

        empty_measurer.reset()
        assert empty_measurer.measurement_count == 0
        assert empty_measurer.get_history() == []
        assert empty_measurer.get_latest() is None

    def test_reset_then_measure(
        self, empty_measurer: OutcomeMeasurer, success_execution: LearningExecutionResult
    ) -> None:
        """重置后重新测量."""
        empty_measurer.measure(success_execution, cycle_number=1)
        empty_measurer.reset()
        m = empty_measurer.measure(success_execution, cycle_number=1)
        assert m.is_measurable is True
        assert empty_measurer.measurement_count == 1


# ═══════════════════════════════════════════════════════════════
# Section 4: Orchestrator Integration
# ═══════════════════════════════════════════════════════════════


class TestOrchestratorMeasurementIntegration:
    """Orchestrator 中的 OutcomeMeasurement 集成测试."""

    def test_orchestrator_has_outcome_measurer(self) -> None:
        """Orchestrator 初始化时创建 OutcomeMeasurer."""
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
        assert orchestrator._outcome_measurer is not None
        assert isinstance(orchestrator._outcome_measurer, OutcomeMeasurer)

    def test_measurement_after_single_cycle(self) -> None:
        """单周期后无上一轮结果，measurement 不可测量."""
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

        # 第一周期后，之前的执行结果为 None，所以测量不可测量
        latest = orchestrator._outcome_measurer.get_latest()
        assert latest is not None
        assert latest.is_measurable is False

    def test_measurement_after_two_cycles(self) -> None:
        """两个周期后可以测量."""
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
        orchestrator.run_cycle()  # 周期1: 无 previous execution
        orchestrator.run_cycle()  # 周期2: 有 previous execution

        # 第二个周期后，latest 应该是可测量的
        latest = orchestrator._outcome_measurer.get_latest()
        assert latest is not None
        assert latest.is_measurable is True

    def test_measurement_history_grows(self) -> None:
        """测量历史随周期增长."""
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

        history = orchestrator._outcome_measurer.get_history()
        assert len(history) == 3

    def test_measurement_stats_after_cycles(self) -> None:
        """多周期后统计正确."""
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

        stats = orchestrator._outcome_measurer.get_stats()
        assert stats["measurement_count"] == 5
        # 第1个周期不可测量，后4个可测量
        assert stats["measurable_count"] == 4

    def test_reset_clears_orchestrator_state(self) -> None:
        """reset 清除编排器状态，但 measurer 历史独立."""
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

        assert orchestrator._outcome_measurer.measurement_count == 2

        orchestrator.reset()
        # reset 只重置编排器自身状态，不重置 outcome_measurer
        assert orchestrator._outcome_measurer.measurement_count == 2
        assert orchestrator.total_cycles == 0

    def test_measurement_accessible_via_orchestrator(self) -> None:
        """通过 Orchestrator 访问测量器."""
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

        # 可以通过 orchestrator._outcome_measurer 访问
        measurer = orchestrator._outcome_measurer
        assert isinstance(measurer, OutcomeMeasurer)
        assert measurer.measurement_count == 1


# ═══════════════════════════════════════════════════════════════
# Run
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])