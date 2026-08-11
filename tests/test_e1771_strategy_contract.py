"""E13.7.7.1 Learning Strategy Contract — 学习策略控制平面模型测试.

Day 7.7.1:
  测试三个核心模型的创建、属性、序列化和集成场景，
  确保 Adaptive Layer 的共享协议正确无误。

测试覆盖:
  - LearningStrategyState: 创建、工厂方法、验证、属性、序列化、克隆
  - LearningAdjustment: 创建、delta 计算、百分比、显著性、序列化
  - LearningPolicyDecision: 创建、调整管理、回滚、优先级、序列化
  - Integration: 完整场景 (状态→调整→决策→回滚)
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_strategy_models import (
    AdjustmentSource,
    LearningAdjustment,
    LearningMode,
    LearningPolicyDecision,
    LearningStrategyState,
    PolicyAction,
    PolicyPriority,
)


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class TestLearningMode:
    def test_enum_values(self) -> None:
        assert LearningMode.AGGRESSIVE.value == "aggressive"
        assert LearningMode.BALANCED.value == "balanced"
        assert LearningMode.CONSERVATIVE.value == "conservative"

    def test_enum_membership(self) -> None:
        assert LearningMode("aggressive") == LearningMode.AGGRESSIVE
        assert LearningMode("balanced") == LearningMode.BALANCED


class TestPolicyAction:
    def test_all_actions_defined(self) -> None:
        actions = {a.value for a in PolicyAction}
        assert "increase_exploration" in actions
        assert "reduce_pattern_weight" in actions
        assert "refresh_memory" in actions
        assert "strengthen_pattern" in actions
        assert "decay_pattern" in actions
        assert "adjust_confidence_threshold" in actions
        assert "switch_learning_mode" in actions

    def test_action_count(self) -> None:
        assert len(list(PolicyAction)) == 7


class TestAdjustmentSource:
    def test_enum_values(self) -> None:
        assert AdjustmentSource.EVALUATION.value == "evaluation"
        assert AdjustmentSource.TREND.value == "trend"
        assert AdjustmentSource.MANUAL.value == "manual"


class TestPolicyPriority:
    def test_enum_values(self) -> None:
        assert PolicyPriority.HIGH.value == "high"
        assert PolicyPriority.MEDIUM.value == "medium"
        assert PolicyPriority.LOW.value == "low"


# ═══════════════════════════════════════════════════════════════
# LearningStrategyState
# ═══════════════════════════════════════════════════════════════


class TestLearningStrategyStateCreation:
    def test_default_creation(self) -> None:
        state = LearningStrategyState()
        assert state.state_id != ""
        assert state.confidence_threshold == 0.50
        assert state.pattern_weight == 0.70
        assert state.memory_weight == 0.30
        assert state.exploration_rate == 0.20
        assert state.memory_decay_rate == 0.01
        assert state.learning_mode == LearningMode.BALANCED.value
        assert state.min_samples_for_confidence == 10
        assert state.version == 1

    def test_custom_creation(self) -> None:
        state = LearningStrategyState(
            confidence_threshold=0.60,
            pattern_weight=0.80,
            exploration_rate=0.30,
            learning_mode=LearningMode.AGGRESSIVE.value,
        )
        assert state.confidence_threshold == 0.60
        assert state.pattern_weight == 0.80
        assert state.exploration_rate == 0.30
        assert state.is_aggressive

    def test_unique_state_ids(self) -> None:
        s1 = LearningStrategyState()
        s2 = LearningStrategyState()
        assert s1.state_id != s2.state_id


class TestLearningStrategyStateFactories:
    def test_default_factory(self) -> None:
        state = LearningStrategyState.default()
        assert state.learning_mode == LearningMode.BALANCED.value
        assert state.confidence_threshold == 0.50
        assert state.exploration_rate == 0.20
        assert state.is_balanced

    def test_aggressive_factory(self) -> None:
        state = LearningStrategyState.aggressive()
        assert state.learning_mode == LearningMode.AGGRESSIVE.value
        assert state.confidence_threshold == 0.40
        assert state.pattern_weight == 0.85
        assert state.exploration_rate == 0.05
        assert state.is_aggressive
        assert not state.is_balanced

    def test_conservative_factory(self) -> None:
        state = LearningStrategyState.conservative()
        assert state.learning_mode == LearningMode.CONSERVATIVE.value
        assert state.confidence_threshold == 0.65
        assert state.pattern_weight == 0.40
        assert state.exploration_rate == 0.50
        assert state.is_conservative

    def test_factory_mode_consistency(self) -> None:
        """Factory 创建的 state 的 mode 与属性一致."""
        agg = LearningStrategyState.aggressive()
        assert agg.is_aggressive
        assert agg.exploration_rate < 0.20  # 低探索

        con = LearningStrategyState.conservative()
        assert con.is_conservative
        assert con.exploration_rate > 0.30  # 高探索


class TestLearningStrategyStateValidation:
    def test_clamps_confidence_threshold(self) -> None:
        s1 = LearningStrategyState(confidence_threshold=1.5)
        assert s1.confidence_threshold == 1.0

        s2 = LearningStrategyState(confidence_threshold=-0.5)
        assert s2.confidence_threshold == 0.0

    def test_clamps_pattern_weight(self) -> None:
        s1 = LearningStrategyState(pattern_weight=2.0)
        assert s1.pattern_weight == 1.0

        s2 = LearningStrategyState(pattern_weight=-0.5)
        assert s2.pattern_weight == 0.0

    def test_clamps_exploration_rate(self) -> None:
        s1 = LearningStrategyState(exploration_rate=2.0)
        assert s1.exploration_rate == 1.0

        s2 = LearningStrategyState(exploration_rate=-0.5)
        assert s2.exploration_rate == 0.0

    def test_clamps_memory_decay_rate(self) -> None:
        s1 = LearningStrategyState(memory_decay_rate=1.0)
        assert s1.memory_decay_rate == 0.1  # clamped to max

        s2 = LearningStrategyState(memory_decay_rate=0.0)
        assert s2.memory_decay_rate == 0.001  # clamped to min

    def test_clamps_min_samples(self) -> None:
        s = LearningStrategyState(min_samples_for_confidence=0)
        assert s.min_samples_for_confidence == 1

        s2 = LearningStrategyState(min_samples_for_confidence=-5)
        assert s2.min_samples_for_confidence == 1


class TestLearningStrategyStateProperties:
    def test_exploitation_rate(self) -> None:
        state = LearningStrategyState(exploration_rate=0.20)
        assert state.exploitation_rate == 0.80

        state2 = LearningStrategyState(exploration_rate=0.50)
        assert state2.exploitation_rate == 0.50

    def test_is_aggressive(self) -> None:
        assert LearningStrategyState(learning_mode="aggressive").is_aggressive
        assert not LearningStrategyState(learning_mode="balanced").is_aggressive

    def test_is_balanced(self) -> None:
        assert LearningStrategyState(learning_mode="balanced").is_balanced
        assert not LearningStrategyState(learning_mode="aggressive").is_balanced

    def test_is_conservative(self) -> None:
        assert LearningStrategyState(learning_mode="conservative").is_conservative
        assert not LearningStrategyState(learning_mode="balanced").is_conservative

    def test_weights_normalized_default(self) -> None:
        state = LearningStrategyState.default()
        assert state.weights_normalized  # 0.70 + 0.30 = 1.0

    def test_weights_not_normalized(self) -> None:
        state = LearningStrategyState(pattern_weight=0.50, memory_weight=0.80)
        assert not state.weights_normalized  # 0.50 + 0.80 != 1.0


class TestLearningStrategyStateSerialization:
    def test_to_dict_roundtrip(self) -> None:
        original = LearningStrategyState(
            confidence_threshold=0.55,
            pattern_weight=0.75,
            memory_weight=0.25,
            exploration_rate=0.15,
            learning_mode="aggressive",
            metadata={"key": "value"},
        )
        d = original.to_dict()
        restored = LearningStrategyState.from_dict(d)

        assert restored.confidence_threshold == original.confidence_threshold
        assert restored.pattern_weight == original.pattern_weight
        assert restored.memory_weight == original.memory_weight
        assert restored.exploration_rate == original.exploration_rate
        assert restored.learning_mode == original.learning_mode
        assert restored.metadata == original.metadata

    def test_from_dict_with_defaults(self) -> None:
        state = LearningStrategyState.from_dict({})
        assert state.confidence_threshold == 0.50
        assert state.pattern_weight == 0.70
        assert state.learning_mode == "balanced"

    def test_to_dict_contains_all_fields(self) -> None:
        state = LearningStrategyState()
        d = state.to_dict()
        assert "state_id" in d
        assert "confidence_threshold" in d
        assert "pattern_weight" in d
        assert "memory_weight" in d
        assert "exploration_rate" in d
        assert "memory_decay_rate" in d
        assert "learning_mode" in d
        assert "min_samples_for_confidence" in d
        assert "version" in d
        assert "created_at" in d
        assert "updated_at" in d
        assert "metadata" in d


class TestLearningStrategyStateClone:
    def test_clone_creates_new_state(self) -> None:
        original = LearningStrategyState(confidence_threshold=0.60)
        clone = original.clone()

        assert clone.state_id != original.state_id
        assert clone.confidence_threshold == original.confidence_threshold
        assert clone.pattern_weight == original.pattern_weight
        assert clone.exploration_rate == original.exploration_rate

    def test_clone_is_independent(self) -> None:
        original = LearningStrategyState(confidence_threshold=0.60)
        clone = original.clone()

        clone.confidence_threshold = 0.80
        assert original.confidence_threshold == 0.60
        assert clone.confidence_threshold == 0.80

    def test_clone_deep_copies_metadata(self) -> None:
        original = LearningStrategyState(metadata={"a": 1})
        clone = original.clone()

        clone.metadata["a"] = 2
        assert original.metadata["a"] == 1
        assert clone.metadata["a"] == 2


class TestLearningStrategyStateBumpVersion:
    def test_bump_version_increments(self) -> None:
        state = LearningStrategyState()
        assert state.version == 1
        state.bump_version()
        assert state.version == 2
        state.bump_version()
        assert state.version == 3

    def test_bump_updates_timestamp(self) -> None:
        import time
        state = LearningStrategyState()
        old_ts = state.updated_at
        time.sleep(0.001)  # 确保时间戳前进
        state.bump_version()
        assert state.updated_at > old_ts


# ═══════════════════════════════════════════════════════════════
# LearningAdjustment
# ═══════════════════════════════════════════════════════════════


class TestLearningAdjustmentCreation:
    def test_default_creation(self) -> None:
        adj = LearningAdjustment()
        assert adj.adjustment_id != ""
        assert adj.reason == ""
        assert adj.parameter == ""
        assert adj.previous_value == 0.0
        assert adj.new_value == 0.0
        assert adj.source == AdjustmentSource.EVALUATION.value
        assert adj.reversible is True

    def test_full_creation(self) -> None:
        adj = LearningAdjustment(
            state_id="state_001",
            reason="learning_gain negative",
            parameter="pattern_weight",
            previous_value=0.70,
            new_value=0.40,
            impact_prediction=0.15,
            confidence=0.85,
            source=AdjustmentSource.EVALUATION.value,
            source_detail="evaluation_id_123",
        )
        assert adj.state_id == "state_001"
        assert adj.parameter == "pattern_weight"
        assert adj.previous_value == 0.70
        assert adj.new_value == 0.40
        assert adj.confidence == 0.85

    def test_unique_adjustment_ids(self) -> None:
        a1 = LearningAdjustment()
        a2 = LearningAdjustment()
        assert a1.adjustment_id != a2.adjustment_id


class TestLearningAdjustmentDelta:
    def test_delta_positive(self) -> None:
        adj = LearningAdjustment(previous_value=0.50, new_value=0.80)
        assert adj.delta == 0.30

    def test_delta_negative(self) -> None:
        adj = LearningAdjustment(previous_value=0.80, new_value=0.50)
        assert adj.delta == -0.30

    def test_delta_zero(self) -> None:
        adj = LearningAdjustment(previous_value=0.50, new_value=0.50)
        assert adj.delta == 0.0

    def test_delta_percentage_basic(self) -> None:
        adj = LearningAdjustment(previous_value=0.50, new_value=0.75)
        assert adj.delta_percentage == 50.0

    def test_delta_percentage_decrease(self) -> None:
        adj = LearningAdjustment(previous_value=0.80, new_value=0.20)
        assert adj.delta_percentage == -75.0

    def test_delta_percentage_zero_previous(self) -> None:
        """当 previous_value=0 时，percentage 为 0 或 inf."""
        adj1 = LearningAdjustment(previous_value=0.0, new_value=0.0)
        assert adj1.delta_percentage == 0.0

        adj2 = LearningAdjustment(previous_value=0.0, new_value=0.5)
        assert adj2.delta_percentage == float("inf")


class TestLearningAdjustmentDirection:
    def test_is_increase(self) -> None:
        adj = LearningAdjustment(previous_value=0.30, new_value=0.60)
        assert adj.is_increase
        assert not adj.is_decrease

    def test_is_decrease(self) -> None:
        adj = LearningAdjustment(previous_value=0.60, new_value=0.30)
        assert adj.is_decrease
        assert not adj.is_increase

    def test_neither_when_equal(self) -> None:
        adj = LearningAdjustment(previous_value=0.50, new_value=0.50)
        assert not adj.is_increase
        assert not adj.is_decrease


class TestLearningAdjustmentSignificance:
    def test_significant_change(self) -> None:
        adj = LearningAdjustment(previous_value=0.50, new_value=0.60)
        assert adj.delta_percentage == 20.0
        assert adj.is_significant

    def test_insignificant_change(self) -> None:
        adj = LearningAdjustment(previous_value=0.50, new_value=0.51)
        assert adj.delta_percentage == 2.0
        assert not adj.is_significant

    def test_significant_negative_change(self) -> None:
        adj = LearningAdjustment(previous_value=0.80, new_value=0.40)
        assert adj.delta_percentage == -50.0
        assert adj.is_significant


class TestLearningAdjustmentSerialization:
    def test_to_dict(self) -> None:
        adj = LearningAdjustment(
            state_id="s1",
            reason="test",
            parameter="exploration_rate",
            previous_value=0.20,
            new_value=0.50,
            impact_prediction=0.10,
            confidence=0.75,
            source=AdjustmentSource.TREND.value,
        )
        d = adj.to_dict()
        assert d["adjustment_id"] == adj.adjustment_id
        assert d["parameter"] == "exploration_rate"
        assert d["delta"] == 0.30
        assert d["delta_percentage"] == 150.0
        assert d["confidence"] == 0.75
        assert d["source"] == "trend"


# ═══════════════════════════════════════════════════════════════
# LearningPolicyDecision
# ═══════════════════════════════════════════════════════════════


class TestLearningPolicyDecisionCreation:
    def test_default_creation(self) -> None:
        decision = LearningPolicyDecision()
        assert decision.decision_id != ""
        assert decision.action == PolicyAction.INCREASE_EXPLORATION.value
        assert decision.priority == PolicyPriority.MEDIUM.value
        assert decision.confidence == 0.0
        assert decision.evidence == []
        assert decision.adjustments == []
        assert decision.reversible is True

    def test_full_creation(self) -> None:
        decision = LearningPolicyDecision(
            state_id="state_001",
            action=PolicyAction.REDUCE_PATTERN_WEIGHT.value,
            priority=PolicyPriority.HIGH.value,
            evidence=["learning_gain < 0", "trend declining"],
            confidence=0.85,
            expected_impact=0.20,
            triggered_by="eval_001",
        )
        assert decision.state_id == "state_001"
        assert decision.action == "reduce_pattern_weight"
        assert decision.priority == "high"
        assert len(decision.evidence) == 2
        assert decision.confidence == 0.85
        assert decision.is_high_priority

    def test_unique_decision_ids(self) -> None:
        d1 = LearningPolicyDecision()
        d2 = LearningPolicyDecision()
        assert d1.decision_id != d2.decision_id


class TestLearningPolicyDecisionPriority:
    def test_is_high_priority(self) -> None:
        d = LearningPolicyDecision(priority=PolicyPriority.HIGH.value)
        assert d.is_high_priority

    def test_not_high_priority(self) -> None:
        d = LearningPolicyDecision(priority=PolicyPriority.MEDIUM.value)
        assert not d.is_high_priority

    def test_is_emergency_true(self) -> None:
        d = LearningPolicyDecision(
            priority=PolicyPriority.HIGH.value,
            confidence=0.85,
        )
        assert d.is_emergency

    def test_is_emergency_false_low_confidence(self) -> None:
        d = LearningPolicyDecision(
            priority=PolicyPriority.HIGH.value,
            confidence=0.50,
        )
        assert not d.is_emergency

    def test_is_emergency_false_medium_priority(self) -> None:
        d = LearningPolicyDecision(
            priority=PolicyPriority.MEDIUM.value,
            confidence=0.90,
        )
        assert not d.is_emergency


class TestLearningPolicyDecisionAdjustments:
    def test_add_adjustment(self) -> None:
        decision = LearningPolicyDecision()
        adj = LearningAdjustment(
            reason="test",
            parameter="pattern_weight",
            previous_value=0.70,
            new_value=0.40,
        )
        decision.add_adjustment(adj)
        assert decision.adjustment_count == 1
        assert decision.adjustments[0] is adj

    def test_multiple_adjustments(self) -> None:
        decision = LearningPolicyDecision()
        decision.add_adjustment(LearningAdjustment(parameter="a", new_value=0.5))
        decision.add_adjustment(LearningAdjustment(parameter="b", new_value=0.3))
        decision.add_adjustment(LearningAdjustment(parameter="c", new_value=0.8))
        assert decision.adjustment_count == 3

    def test_total_impact_from_adjustments(self) -> None:
        decision = LearningPolicyDecision()
        decision.add_adjustment(LearningAdjustment(
            parameter="exploration_rate",
            previous_value=0.20,
            new_value=0.50,
            impact_prediction=0.10,
        ))
        decision.add_adjustment(LearningAdjustment(
            parameter="pattern_weight",
            previous_value=0.70,
            new_value=0.40,
            impact_prediction=0.05,
        ))
        assert decision.total_impact == 0.15

    def test_total_impact_fallback(self) -> None:
        """无 adjustments 时使用 expected_impact."""
        decision = LearningPolicyDecision(expected_impact=0.25)
        assert decision.total_impact == 0.25


class TestLearningPolicyDecisionRollback:
    def test_can_rollback_with_snapshot(self) -> None:
        state = LearningStrategyState.default()
        decision = LearningPolicyDecision(
            previous_state_snapshot=state.to_dict(),
            reversible=True,
        )
        assert decision.can_rollback()

    def test_cannot_rollback_without_snapshot(self) -> None:
        decision = LearningPolicyDecision(reversible=True)
        assert not decision.can_rollback()

    def test_cannot_rollback_irreversible(self) -> None:
        state = LearningStrategyState.default()
        decision = LearningPolicyDecision(
            previous_state_snapshot=state.to_dict(),
            reversible=False,
        )
        assert not decision.can_rollback()

    def test_rollback_state_restores(self) -> None:
        original = LearningStrategyState(
            confidence_threshold=0.60,
            pattern_weight=0.80,
            exploration_rate=0.10,
        )
        decision = LearningPolicyDecision(
            previous_state_snapshot=original.to_dict(),
            reversible=True,
        )
        restored = decision.rollback_state()
        assert restored is not None
        assert restored.confidence_threshold == 0.60
        assert restored.pattern_weight == 0.80
        assert restored.exploration_rate == 0.10

    def test_rollback_returns_none_when_cannot(self) -> None:
        decision = LearningPolicyDecision(reversible=True)
        assert decision.rollback_state() is None


class TestLearningPolicyDecisionSerialization:
    def test_to_dict(self) -> None:
        state = LearningStrategyState.default()
        decision = LearningPolicyDecision(
            state_id=state.state_id,
            action=PolicyAction.INCREASE_EXPLORATION.value,
            priority=PolicyPriority.HIGH.value,
            evidence=["e1", "e2"],
            confidence=0.90,
            expected_impact=0.15,
            previous_state_snapshot=state.to_dict(),
            triggered_by="eval_001",
        )
        decision.add_adjustment(LearningAdjustment(
            parameter="exploration_rate",
            previous_value=0.20,
            new_value=0.50,
            impact_prediction=0.10,
            confidence=0.80,
        ))

        d = decision.to_dict()
        assert d["action"] == "increase_exploration"
        assert d["priority"] == "high"
        assert d["evidence"] == ["e1", "e2"]
        assert d["confidence"] == 0.90
        assert d["adjustment_count"] == 1
        assert d["previous_state_snapshot"] is not None
        assert d["triggered_by"] == "eval_001"


# ═══════════════════════════════════════════════════════════════
# Integration Scenarios
# ═══════════════════════════════════════════════════════════════


class TestIntegrationScenario:
    """完整场景: 状态 → 调整 → 决策 → 回滚."""

    def test_full_scenario_learning_gain_negative(self) -> None:
        """模拟 Day 7.7 核心场景: 学习增益为负，切换到保守模式."""
        # 1. 当前状态: 平衡模式
        state = LearningStrategyState.default()
        assert state.is_balanced
        assert state.exploration_rate == 0.20
        assert state.pattern_weight == 0.70

        # 2. 评估结果: learning_gain = -0.08 (负增益)
        # 做快照
        snapshot = state.to_dict()

        # 3. 创建调整
        adj1 = LearningAdjustment(
            state_id=state.state_id,
            reason="learning_gain negative (-0.08)",
            parameter="exploration_rate",
            previous_value=0.20,
            new_value=0.50,
            impact_prediction=0.10,
            confidence=0.85,
            source=AdjustmentSource.EVALUATION.value,
        )
        adj2 = LearningAdjustment(
            state_id=state.state_id,
            reason="learning_gain negative (-0.08)",
            parameter="pattern_weight",
            previous_value=0.70,
            new_value=0.40,
            impact_prediction=0.05,
            confidence=0.80,
            source=AdjustmentSource.EVALUATION.value,
        )
        adj3 = LearningAdjustment(
            state_id=state.state_id,
            reason="learning_gain negative (-0.08)",
            parameter="memory_decay_rate",
            previous_value=0.01,
            new_value=0.03,
            impact_prediction=0.03,
            confidence=0.75,
            source=AdjustmentSource.EVALUATION.value,
        )

        # 4. 创建策略决策
        decision = LearningPolicyDecision(
            state_id=state.state_id,
            action=PolicyAction.SWITCH_LEARNING_MODE.value,
            priority=PolicyPriority.HIGH.value,
            evidence=[
                "learning_gain = -0.08 < 0",
                "success_rate declining over 3 cycles",
                "trend_direction: declining",
            ],
            confidence=0.85,
            expected_impact=0.20,
            previous_state_snapshot=snapshot,
            triggered_by="eval_001",
        )
        decision.add_adjustment(adj1)
        decision.add_adjustment(adj2)
        decision.add_adjustment(adj3)

        # 5. 应用调整到状态
        state.exploration_rate = 0.50
        state.pattern_weight = 0.40
        state.memory_decay_rate = 0.03
        state.learning_mode = LearningMode.CONSERVATIVE.value
        state.bump_version()

        assert state.exploration_rate == 0.50
        assert state.pattern_weight == 0.40
        assert state.memory_decay_rate == 0.03
        assert state.is_conservative
        assert state.version == 2
        assert decision.adjustment_count == 3
        assert decision.is_emergency
        assert decision.total_impact == 0.18

        # 6. 验证可回滚
        assert decision.can_rollback()
        restored = decision.rollback_state()
        assert restored is not None
        assert restored.exploration_rate == 0.20
        assert restored.pattern_weight == 0.70
        assert restored.memory_decay_rate == 0.01

    def test_scenario_pattern_decay_detected(self) -> None:
        """模拟 Pattern 衰减场景: 增加探索 + 衰减 pattern."""
        state = LearningStrategyState.aggressive()
        snapshot = state.to_dict()

        decision = LearningPolicyDecision(
            state_id=state.state_id,
            action=PolicyAction.DECAY_PATTERN.value,
            priority=PolicyPriority.MEDIUM.value,
            evidence=["Pattern A success_rate: 0.85 → 0.55"],
            confidence=0.70,
            expected_impact=0.10,
            previous_state_snapshot=snapshot,
        )
        decision.add_adjustment(LearningAdjustment(
            parameter="pattern_weight",
            previous_value=0.85,
            new_value=0.60,
            impact_prediction=0.05,
            confidence=0.70,
        ))
        decision.add_adjustment(LearningAdjustment(
            parameter="exploration_rate",
            previous_value=0.05,
            new_value=0.25,
            impact_prediction=0.05,
            confidence=0.65,
        ))

        assert decision.adjustment_count == 2
        assert decision.can_rollback()

        # 应用
        state.pattern_weight = 0.60
        state.exploration_rate = 0.25
        assert state.exploration_rate == 0.25

    def test_scenario_continuous_success(self) -> None:
        """模拟连续成功: 强化 pattern，降低探索."""
        state = LearningStrategyState.default()

        decision = LearningPolicyDecision(
            state_id=state.state_id,
            action=PolicyAction.STRENGTHEN_PATTERN.value,
            priority=PolicyPriority.LOW.value,
            evidence=["Pattern B success: 10/10", "learning_gain: +0.12"],
            confidence=0.90,
            previous_state_snapshot=state.to_dict(),
        )
        decision.add_adjustment(LearningAdjustment(
            parameter="pattern_weight",
            previous_value=0.70,
            new_value=0.85,
            impact_prediction=0.08,
            confidence=0.90,
        ))
        decision.add_adjustment(LearningAdjustment(
            parameter="exploration_rate",
            previous_value=0.20,
            new_value=0.10,
            impact_prediction=0.02,
            confidence=0.70,
        ))

        assert decision.action == "strengthen_pattern"
        assert decision.priority == "low"
        assert not decision.is_emergency

    def test_scenario_mode_switch_aggressive_to_conservative(self) -> None:
        """激进→保守: 市场突变场景."""
        state = LearningStrategyState.aggressive()
        snapshot = state.to_dict()

        decision = LearningPolicyDecision(
            state_id=state.state_id,
            action=PolicyAction.SWITCH_LEARNING_MODE.value,
            priority=PolicyPriority.HIGH.value,
            evidence=["Market shift detected", "All patterns declining"],
            confidence=0.88,
            previous_state_snapshot=snapshot,
        )
        decision.add_adjustment(LearningAdjustment(
            parameter="learning_mode",
            previous_value=0.0,  # 非数值型参数
            new_value=0.0,
            impact_prediction=0.30,
            confidence=0.88,
        ))

        # 应用
        state.learning_mode = LearningMode.CONSERVATIVE.value
        state.exploration_rate = 0.50
        state.confidence_threshold = 0.65
        state.bump_version()

        assert state.is_conservative
        assert state.version == 2

    def test_roundtrip_serialization(self) -> None:
        """完整序列化往返: state → dict → from_dict."""
        original = LearningStrategyState(
            confidence_threshold=0.55,
            pattern_weight=0.75,
            exploration_rate=0.15,
            learning_mode="aggressive",
            metadata={"game": "Merge Witch", "country": "US"},
        )
        original.bump_version()
        original.bump_version()

        d = original.to_dict()
        restored = LearningStrategyState.from_dict(d)

        assert restored.confidence_threshold == 0.55
        assert restored.pattern_weight == 0.75
        assert restored.exploration_rate == 0.15
        assert restored.learning_mode == "aggressive"
        assert restored.version == 3
        assert restored.metadata == {"game": "Merge Witch", "country": "US"}

    def test_adjustment_chain_serialization(self) -> None:
        """调整链序列化: 完整决策对象可序列化."""
        state = LearningStrategyState.default()
        decision = LearningPolicyDecision(
            state_id=state.state_id,
            action=PolicyAction.INCREASE_EXPLORATION.value,
            previous_state_snapshot=state.to_dict(),
        )

        for i in range(3):
            decision.add_adjustment(LearningAdjustment(
                state_id=state.state_id,
                parameter=f"param_{i}",
                previous_value=float(i) * 0.1,
                new_value=float(i) * 0.1 + 0.1,
                impact_prediction=0.05,
                confidence=0.7 + float(i) * 0.05,
            ))

        d = decision.to_dict()
        assert d["adjustment_count"] == 3
        assert len(d["adjustments"]) == 3
        assert d["previous_state_snapshot"] is not None
        assert d["previous_state_snapshot"]["learning_mode"] == "balanced"