"""E17.8 Policy Adjustment — 测试用例.

Day 7.8 Step 6:
  覆盖 Policy Adjustment 层的:
    - AdjustmentDirection 枚举
    - PolicyAdjustment 模型 (factory methods, properties, serialization)
    - PolicyAdjustmentSet 模型 (factory methods, aggregation, serialization)
    - PolicyAdjuster 引擎 (good_learning, bad_learning, stagnant, insufficient, default)
    - Orchestrator 集成 (POLICY_ADJUSTMENT 阶段)
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_policy_models import (
    AdjustmentDirection,
    PolicyAdjustment,
    PolicyAdjustmentSet,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_feedback_models import (
    LearningFeedback,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.outcome_measurement_models import (
    OutcomeMeasurement,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.cycle_gate_models import (
    CycleGateResult,
    GateDecision,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_policy_adjuster import (
    PolicyAdjuster,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def adjuster() -> PolicyAdjuster:
    """空调整器."""
    return PolicyAdjuster()


@pytest.fixture
def good_feedback() -> LearningFeedback:
    """GOOD_LEARNING 反馈."""
    outcome = OutcomeMeasurement.from_execution(
        cycle_number=1,
        execution_action="execute_learning",
        execution_success=True,
        metrics_before={"roas": 0.8, "ctr": 2.1},
        metrics_after={"roas": 1.2, "ctr": 3.0},
        strategy_state_before={"learning_mode": "balanced"},
        strategy_state_after={"learning_mode": "balanced"},
        measurement_confidence=0.8,
    )
    return LearningFeedback.from_measurement(outcome=outcome, cycle_number=1)


@pytest.fixture
def bad_feedback() -> LearningFeedback:
    """BAD_LEARNING 反馈 (moderate)."""
    outcome = OutcomeMeasurement(
        cycle_number=2,
        is_measurable=True,
        learning_gain=-0.15,
        reward_delta=-0.1,
        confidence_delta=-0.02,
        success_delta=-0.05,
    )
    return LearningFeedback.from_measurement(outcome=outcome, cycle_number=2)


@pytest.fixture
def stagnant_feedback() -> LearningFeedback:
    """STAGNANT 反馈."""
    outcome = OutcomeMeasurement(
        cycle_number=3,
        is_measurable=True,
        learning_gain=0.03,
        reward_delta=0.01,
        confidence_delta=0.01,
        success_delta=0.0,
    )
    return LearningFeedback.from_measurement(outcome=outcome, cycle_number=3)


@pytest.fixture
def insufficient_feedback() -> LearningFeedback:
    """INSUFFICIENT_DATA 反馈."""
    outcome = OutcomeMeasurement(
        cycle_number=4,
        is_measurable=False,
        learning_gain=0.0,
        reward_delta=0.0,
        confidence_delta=0.0,
        success_delta=0.0,
    )
    return LearningFeedback.from_measurement(outcome=outcome, cycle_number=4)


@pytest.fixture
def continue_gate() -> CycleGateResult:
    """CONTINUE 门控."""
    return CycleGateResult.continue_result(cycle_number=1)


@pytest.fixture
def rollback_gate() -> CycleGateResult:
    """ROLLBACK 门控."""
    return CycleGateResult.rollback_result(
        cycle_number=2,
        reason="Strong negative learning",
        triggered_rule="strong_negative_learning",
    )


@pytest.fixture
def default_params() -> dict[str, float]:
    """默认策略参数."""
    return {
        "exploration_rate": 0.3,
        "confidence_threshold": 0.5,
        "pattern_weight": 0.7,
        "memory_weight": 0.3,
    }


# ═══════════════════════════════════════════════════════════════
# Test: AdjustmentDirection
# ═══════════════════════════════════════════════════════════════


class TestAdjustmentDirection:
    """AdjustmentDirection 枚举测试."""

    def test_enum_values(self):
        assert AdjustmentDirection.INCREASE.value == "increase"
        assert AdjustmentDirection.DECREASE.value == "decrease"
        assert AdjustmentDirection.MAINTAIN.value == "maintain"

    def test_enum_count(self):
        assert len(AdjustmentDirection) == 3


# ═══════════════════════════════════════════════════════════════
# Test: PolicyAdjustment Model
# ═══════════════════════════════════════════════════════════════


class TestPolicyAdjustmentModel:
    """PolicyAdjustment 模型测试."""

    def test_default(self):
        adj = PolicyAdjustment()
        assert adj.direction == AdjustmentDirection.MAINTAIN.value
        assert adj.adjustment_delta == 0.0
        assert adj.is_significant is False
        assert adj.confidence == 0.0

    def test_increase(self):
        adj = PolicyAdjustment.increase(
            target_policy="exploration_rate",
            current_value=0.3,
            delta=0.05,
            reason="Test increase",
            confidence=0.8,
            cycle_number=1,
            source="good_learning",
        )
        assert adj.target_policy == "exploration_rate"
        assert adj.current_value == 0.3
        assert adj.recommended_value == 0.35
        assert adj.adjustment_delta == 0.05
        assert adj.direction == "increase"
        assert adj.is_significant is True
        assert adj.is_high_confidence is True

    def test_decrease(self):
        adj = PolicyAdjustment.decrease(
            target_policy="exploration_rate",
            current_value=0.3,
            delta=0.05,
            reason="Test decrease",
            confidence=0.6,
            cycle_number=2,
            source="bad_learning",
        )
        assert adj.recommended_value == 0.25
        assert adj.adjustment_delta == -0.05
        assert adj.direction == "decrease"
        assert adj.is_significant is True
        assert adj.is_high_confidence is False

    def test_decrease_floor(self):
        """下调不会低于 0."""
        adj = PolicyAdjustment.decrease(
            target_policy="exploration_rate",
            current_value=0.02,
            delta=0.1,
            reason="Test floor",
        )
        assert adj.recommended_value == 0.0

    def test_maintain(self):
        adj = PolicyAdjustment.maintain(
            target_policy="exploration_rate",
            current_value=0.3,
            reason="Keep current",
            cycle_number=3,
            source="stagnant",
        )
        assert adj.recommended_value == 0.3
        assert adj.adjustment_delta == 0.0
        assert adj.direction == "maintain"
        assert adj.confidence == 1.0

    def test_is_significant_threshold(self):
        """delta <= 0.01 不算显著."""
        adj = PolicyAdjustment.increase(
            target_policy="test",
            current_value=0.5,
            delta=0.005,
        )
        assert adj.is_significant is False

    def test_to_dict(self):
        adj = PolicyAdjustment.increase(
            target_policy="exploration_rate",
            current_value=0.3,
            delta=0.05,
            reason="Test",
            confidence=0.8,
            cycle_number=1,
            source="good_learning",
        )
        d = adj.to_dict()
        assert d["target_policy"] == "exploration_rate"
        assert d["direction"] == "increase"
        assert d["is_significant"] is True
        assert "adjustment_id" in d
        assert "created_at" in d


# ═══════════════════════════════════════════════════════════════
# Test: PolicyAdjustmentSet Model
# ═══════════════════════════════════════════════════════════════


class TestPolicyAdjustmentSet:
    """PolicyAdjustmentSet 模型测试."""

    def test_empty(self):
        s = PolicyAdjustmentSet.empty(cycle_number=1)
        assert s.is_empty is True
        assert s.total_adjustments == 0
        assert s.has_significant_changes is False
        assert s.summary == "No policy adjustments"

    def test_from_adjustments(self):
        adjustments = [
            PolicyAdjustment.increase(
                target_policy="exploration_rate",
                current_value=0.3,
                delta=0.05,
                confidence=0.8,
            ),
            PolicyAdjustment.decrease(
                target_policy="pattern_weight",
                current_value=0.7,
                delta=0.03,
                confidence=0.6,
            ),
        ]
        s = PolicyAdjustmentSet.from_adjustments(
            adjustments=adjustments,
            cycle_number=1,
            source_feedback="good_learning",
            source_gate="continue",
        )
        assert s.total_adjustments == 2
        assert s.significant_count == 2
        assert s.high_confidence_count == 1
        assert s.has_significant_changes is True
        assert s.source_feedback == "good_learning"
        assert s.source_gate == "continue"

    def test_summary(self):
        adjustments = [
            PolicyAdjustment.increase(
                target_policy="exploration_rate",
                current_value=0.3,
                delta=0.05,
                confidence=0.8,
            ),
        ]
        s = PolicyAdjustmentSet.from_adjustments(adjustments=adjustments)
        assert "exploration_rate" in s.summary
        assert "0.3" in s.summary

    def test_summary_no_significant(self):
        adjustments = [
            PolicyAdjustment.increase(
                target_policy="test",
                current_value=0.5,
                delta=0.005,
            ),
        ]
        s = PolicyAdjustmentSet.from_adjustments(adjustments=adjustments)
        assert "Minor adjustments only" in s.summary

    def test_to_dict(self):
        adjustments = [
            PolicyAdjustment.increase(
                target_policy="exploration_rate",
                current_value=0.3,
                delta=0.05,
                confidence=0.8,
            ),
        ]
        s = PolicyAdjustmentSet.from_adjustments(
            adjustments=adjustments,
            cycle_number=1,
            source_feedback="good_learning",
        )
        d = s.to_dict()
        assert d["total_adjustments"] == 1
        assert d["is_empty"] is False
        assert len(d["adjustments"]) == 1
        assert "set_id" in d


# ═══════════════════════════════════════════════════════════════
# Test: PolicyAdjuster Engine
# ═══════════════════════════════════════════════════════════════


class TestPolicyAdjusterEngine:
    """PolicyAdjuster 引擎测试."""

    def test_create_adjuster(self, adjuster):
        assert adjuster.adjust_count == 0

    def test_adjust_good_learning(self, adjuster, good_feedback, continue_gate, default_params):
        """GOOD_LEARNING → 下调 exploration, 上调 confidence_threshold."""
        result = adjuster.adjust(
            feedback=good_feedback,
            gate_result=continue_gate,
            cycle_number=1,
        )
        assert result.total_adjustments > 0
        assert result.source_feedback == "good_learning"
        # 应该有 exploration_rate 下调
        exp_adjustments = [a for a in result.adjustments
                           if a.target_policy == "exploration_rate"]
        assert len(exp_adjustments) > 0
        assert exp_adjustments[0].direction == "decrease"

    def test_adjust_bad_learning(self, adjuster, bad_feedback, continue_gate, default_params):
        """BAD_LEARNING → 上调 exploration, 下调 pattern_weight."""
        result = adjuster.adjust(
            feedback=bad_feedback,
            gate_result=continue_gate,
            cycle_number=2,
        )
        assert result.source_feedback == "bad_learning"
        # exploration_rate 上调
        exp_adjustments = [a for a in result.adjustments
                           if a.target_policy == "exploration_rate"]
        assert len(exp_adjustments) > 0
        assert exp_adjustments[0].direction == "increase"

    def test_adjust_bad_learning_with_rollback(self, adjuster, bad_feedback, rollback_gate, default_params):
        """BAD_LEARNING + ROLLBACK gate → 更激进的调整."""
        # 先执行一次正常 bad_learning
        result_normal = adjuster.adjust(
            feedback=bad_feedback,
            gate_result=CycleGateResult.continue_result(cycle_number=1),
            cycle_number=1,
        )
        # 再执行一次 rollback
        result_rollback = adjuster.adjust(
            feedback=bad_feedback,
            gate_result=rollback_gate,
            cycle_number=2,
        )
        # rollback 版本应该有更大的调整幅度（或至少相同）
        normal_total = sum(abs(a.adjustment_delta) for a in result_normal.adjustments)
        rollback_total = sum(abs(a.adjustment_delta) for a in result_rollback.adjustments)
        assert rollback_total >= normal_total

    def test_adjust_stagnant(self, adjuster, stagnant_feedback, continue_gate, default_params):
        """STAGNANT → 微调 exploration."""
        result = adjuster.adjust(
            feedback=stagnant_feedback,
            gate_result=continue_gate,
            cycle_number=3,
        )
        assert result.source_feedback == "stagnant"
        # 应该有 exploration_rate 微上调
        exp_adjustments = [a for a in result.adjustments
                           if a.target_policy == "exploration_rate"]
        if exp_adjustments:
            assert exp_adjustments[0].direction == "increase"

    def test_adjust_insufficient(self, adjuster, insufficient_feedback, continue_gate, default_params):
        """INSUFFICIENT_DATA → 全部维持."""
        result = adjuster.adjust(
            feedback=insufficient_feedback,
            gate_result=continue_gate,
            cycle_number=4,
        )
        assert result.source_feedback == "insufficient_data"
        # 所有调整都是 maintain
        for a in result.adjustments:
            assert a.direction == "maintain"
            assert a.adjustment_delta == 0.0

    def test_adjust_no_feedback(self, adjuster, continue_gate, default_params):
        """无 feedback → 默认维持."""
        result = adjuster.adjust(
            feedback=None,
            gate_result=continue_gate,
            cycle_number=1,
        )
        for a in result.adjustments:
            assert a.direction == "maintain"

    def test_adjust_count(self, adjuster, good_feedback, continue_gate):
        """调整计数."""
        assert adjuster.adjust_count == 0
        adjuster.adjust(feedback=good_feedback, gate_result=continue_gate, cycle_number=1)
        assert adjuster.adjust_count == 1
        adjuster.adjust(feedback=good_feedback, gate_result=continue_gate, cycle_number=2)
        assert adjuster.adjust_count == 2

    def test_history(self, adjuster, good_feedback, continue_gate):
        """调整历史."""
        adjuster.adjust(feedback=good_feedback, gate_result=continue_gate, cycle_number=1)
        adjuster.adjust(feedback=good_feedback, gate_result=continue_gate, cycle_number=2)
        history = adjuster.get_history()
        assert len(history) == 2
        assert all(isinstance(s, PolicyAdjustmentSet) for s in history)

    def test_get_latest(self, adjuster, good_feedback, continue_gate):
        """获取最近一次调整."""
        assert adjuster.get_latest() is None
        adjuster.adjust(feedback=good_feedback, gate_result=continue_gate, cycle_number=1)
        latest = adjuster.get_latest()
        assert latest is not None
        assert latest.cycle_number == 1

    def test_get_stats(self, adjuster, good_feedback, bad_feedback, continue_gate):
        """获取统计."""
        adjuster.adjust(feedback=good_feedback, gate_result=continue_gate, cycle_number=1)
        adjuster.adjust(feedback=bad_feedback, gate_result=continue_gate, cycle_number=2)
        stats = adjuster.get_stats()
        assert stats["adjust_count"] == 2
        assert stats["total_adjustments"] > 0
        assert "recent_direction" in stats

    def test_get_stats_empty(self):
        """空统计."""
        adjuster = PolicyAdjuster()
        stats = adjuster.get_stats()
        assert stats["adjust_count"] == 0
        assert stats["total_adjustments"] == 0

    def test_reset(self, adjuster, good_feedback, continue_gate):
        """重置."""
        adjuster.adjust(feedback=good_feedback, gate_result=continue_gate, cycle_number=1)
        assert adjuster.adjust_count == 1
        adjuster.reset()
        assert adjuster.adjust_count == 0
        assert len(adjuster.get_history()) == 0


# ═══════════════════════════════════════════════════════════════
# Test: Adjustment Constraints
# ═══════════════════════════════════════════════════════════════


class TestAdjustmentConstraints:
    """调整约束测试."""

    def test_delta_within_bounds(self, adjuster, good_feedback, continue_gate):
        """单次调整幅度不超过 max_delta (0.1)."""
        result = adjuster.adjust(
            feedback=good_feedback,
            gate_result=continue_gate,
            cycle_number=1,
        )
        for a in result.adjustments:
            assert abs(a.adjustment_delta) <= 0.1, (
                f"{a.target_policy}: delta={a.adjustment_delta} exceeds max"
            )

    def test_good_learning_confidence_high(self, adjuster, good_feedback, continue_gate):
        """GOOD_LEARNING 调整置信度较高."""
        result = adjuster.adjust(
            feedback=good_feedback,
            gate_result=continue_gate,
            cycle_number=1,
        )
        for a in result.adjustments:
            if a.is_significant:
                assert a.confidence >= 0.5

    def test_bad_learning_exploration_increases(self, adjuster, bad_feedback, continue_gate):
        """BAD_LEARNING 时 exploration_rate 上调."""
        result = adjuster.adjust(
            feedback=bad_feedback,
            gate_result=continue_gate,
            cycle_number=1,
        )
        exp_adjustments = [a for a in result.adjustments
                           if a.target_policy == "exploration_rate"]
        assert len(exp_adjustments) > 0
        assert exp_adjustments[0].direction == "increase"

    def test_insufficient_no_changes(self, adjuster, insufficient_feedback, continue_gate):
        """INSUFFICIENT_DATA 时无任何变化."""
        result = adjuster.adjust(
            feedback=insufficient_feedback,
            gate_result=continue_gate,
            cycle_number=1,
        )
        assert result.significant_count == 0
        assert result.has_significant_changes is False


# ═══════════════════════════════════════════════════════════════
# Test: POLICY_ADJUSTMENT in Orchestrator
# ═══════════════════════════════════════════════════════════════


class TestPolicyAdjustmentOrchestratorIntegration:
    """Orchestrator 集成测试."""

    @pytest.fixture
    def orchestrator(self):
        """创建带 PolicyAdjuster 的编排器."""
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_cycle_orchestrator import (
            LearningCycleOrchestrator,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_orchestration_models import (
            OrchestratorConfig,
        )

        config = OrchestratorConfig.test_mode()
        orch = LearningCycleOrchestrator(config=config)
        return orch

    def test_policy_adjuster_initialized(self, orchestrator):
        """PolicyAdjuster 已初始化."""
        assert orchestrator.policy_adjuster is not None
        assert orchestrator.policy_adjuster.adjust_count == 0

    def test_policy_adjustment_in_state_transitions(self, orchestrator):
        """POLICY_ADJUSTMENT 出现在状态转换中."""
        orchestrator.start()
        result = orchestrator.run_cycle()
        transitions = result.state_transitions
        states = [t["to"] for t in transitions]
        assert "policy_adjustment" in states

    def test_policy_adjustments_in_result(self, orchestrator):
        """policy_adjustments 出现在结果中."""
        orchestrator.start()
        result = orchestrator.run_cycle()
        assert result.policy_adjustments is not None

    def test_policy_adjuster_stats_in_status(self, orchestrator):
        """PolicyAdjuster 统计出现在 get_status() 中."""
        orchestrator.start()
        orchestrator.run_cycle()
        status = orchestrator.get_status()
        assert "policy_adjuster" in status
        assert status["policy_adjuster"]["adjust_count"] >= 1

    def test_policy_adjuster_reset_with_orchestrator(self, orchestrator):
        """Orchestrator reset 重置 PolicyAdjuster."""
        orchestrator.start()
        orchestrator.run_cycle()
        assert orchestrator.policy_adjuster.adjust_count > 0
        orchestrator.reset()
        assert orchestrator.policy_adjuster.adjust_count == 0

    def test_disable_policy_adjustment(self):
        """显式禁用 policy adjustment."""
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_cycle_orchestrator import (
            LearningCycleOrchestrator,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_orchestration_models import (
            OrchestratorConfig,
        )

        config = OrchestratorConfig.test_mode()
        config.enable_policy_adjustment = False
        orch = LearningCycleOrchestrator(config=config)
        orch.start()
        result = orch.run_cycle()
        # 禁用时返回空集合
        assert result.policy_adjustments.is_empty is True