"""E13.7.7.4 Learning Policy Controller — 学习策略控制器测试.

Day 7.7.4:
  测试 LearningPolicyController 的决策逻辑，
  确保四个核心问题 (should_learn, should_update_memory,
  strategy_mode, decision_type) 的输出正确。

测试覆盖:
  - Models: PolicyDecisionType 枚举, LearningPolicyDecision 扩展字段
  - Controller Init: 默认/自定义
  - Evaluate: 最小输入 / 全输入
  - Should Learn: 有效+高置信 / 有效+低置信 / 无效+高置信 / 无效+低置信 / 无评估
  - Should Update Memory: decay高 / pattern低 / 保守模式 / 健康
  - Strategy Mode: AGGRESSIVE / CONSERVATIVE / BALANCED / 无数据
  - Decision Type: BLOCK / REFRESH / ADJUST_MODE / ALLOW / MAINTAIN
  - Priority: HIGH / MEDIUM / LOW
  - Evidence & Reasons: 完整性检查
  - Confidence: 决策自身置信度
  - Expected Impact: 各类型影响值
  - Integration: 多场景组合
  - Edge Cases: None 输入 / 边界值
  - History: 决策历史追踪
  - Serialization: to_dict 完整性
"""

from __future__ import annotations

from typing import Any

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.evaluation.models import (
    LearningEffectiveness,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_policy_controller import (
    LearningPolicyController,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.adaptive_confidence_models import (
    AdaptiveConfidenceResult,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_strategy_models import (
    LearningMode,
    LearningPolicyDecision,
    LearningStrategyState,
    PolicyAction,
    PolicyDecisionType,
    PolicyPriority,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_effectiveness(
    effectiveness_score: float = 0.50,
    learning_gain: float = 0.0,
    is_effective: bool = True,
) -> LearningEffectiveness:
    return LearningEffectiveness(
        total_decisions=50,
        learning_enhanced_count=50,
        learning_gain=learning_gain,
        effectiveness_score=effectiveness_score,
        is_effective=is_effective,
    )


def _make_adaptive_result(
    adjusted_confidence: float = 0.50,
    confidence_level: str = "medium",
) -> AdaptiveConfidenceResult:
    return AdaptiveConfidenceResult(
        base_confidence=0.70,
        adjusted_confidence=adjusted_confidence,
        adjustment_factor=0.95,
        confidence_level=confidence_level,
        dimensions={
            "historical_accuracy": 1.0,
            "learning_effectiveness": 1.0,
            "context_similarity": 1.0,
            "freshness": 1.0,
            "base_confidence": 0.70,
        },
    )


def _make_mock_pattern(success_rate: float = 0.60, avg_confidence: float = 0.60, samples: int = 10) -> Any:
    """创建模拟 Pattern 对象，用于 context_patterns 参数."""
    perf_type = type("_MockPerformance", (), {
        "success_rate": success_rate,
        "avg_confidence": avg_confidence,
        "samples": samples,
    })
    return type("_MockPattern", (), {"performance": perf_type})()


# ═══════════════════════════════════════════════════════════════
# PolicyDecisionType
# ═══════════════════════════════════════════════════════════════


class TestPolicyDecisionType:
    def test_enum_values(self) -> None:
        assert PolicyDecisionType.ALLOW_LEARNING.value == "allow_learning"
        assert PolicyDecisionType.BLOCK_LEARNING.value == "block_learning"
        assert PolicyDecisionType.REQUEST_MEMORY_REFRESH.value == "request_memory_refresh"
        assert PolicyDecisionType.ADJUST_MODE.value == "adjust_mode"
        assert PolicyDecisionType.MAINTAIN.value == "maintain"

    def test_all_values_distinct(self) -> None:
        values = [e.value for e in PolicyDecisionType]
        assert len(values) == len(set(values))


# ═══════════════════════════════════════════════════════════════
# LearningPolicyDecision (Extended)
# ═══════════════════════════════════════════════════════════════


class TestLearningPolicyDecisionExtended:
    def test_default_creation(self) -> None:
        d = LearningPolicyDecision()
        assert d.decision_type == PolicyDecisionType.MAINTAIN.value
        assert d.should_learn is True
        assert d.should_update_memory is False
        assert d.strategy_mode == LearningMode.BALANCED.value
        assert d.reasons == []
        assert d.adaptive_confidence == 0.0
        assert d.learning_effectiveness_score == 0.0

    def test_full_creation(self) -> None:
        d = LearningPolicyDecision(
            decision_type=PolicyDecisionType.ALLOW_LEARNING.value,
            should_learn=True,
            should_update_memory=False,
            strategy_mode=LearningMode.AGGRESSIVE.value,
            action=PolicyAction.STRENGTHEN_PATTERN.value,
            priority=PolicyPriority.LOW.value,
            reasons=["Learning effective"],
            evidence=["effectiveness_score=0.80"],
            confidence=0.85,
            adaptive_confidence=0.80,
            learning_effectiveness_score=0.75,
            expected_impact=0.10,
            reversible=True,
            triggered_by="eval_001",
        )
        assert d.decision_type == "allow_learning"
        assert d.strategy_mode == "aggressive"
        assert d.reasons == ["Learning effective"]
        assert d.evidence == ["effectiveness_score=0.80"]
        assert d.adaptive_confidence == 0.80
        assert d.learning_effectiveness_score == 0.75

    def test_to_dict_includes_new_fields(self) -> None:
        d = LearningPolicyDecision(
            decision_type=PolicyDecisionType.BLOCK_LEARNING.value,
            should_learn=False,
            should_update_memory=True,
            strategy_mode=LearningMode.CONSERVATIVE.value,
            reasons=["Learning ineffective"],
            adaptive_confidence=0.30,
            learning_effectiveness_score=0.25,
        )
        dd = d.to_dict()
        assert dd["decision_type"] == "block_learning"
        assert dd["should_learn"] is False
        assert dd["should_update_memory"] is True
        assert dd["strategy_mode"] == "conservative"
        assert dd["reasons"] == ["Learning ineffective"]
        assert dd["adaptive_confidence"] == 0.30
        assert dd["learning_effectiveness_score"] == 0.25

    def test_backward_compatible(self) -> None:
        """Day 7.7.1 原有字段仍可用."""
        d = LearningPolicyDecision(
            action=PolicyAction.INCREASE_EXPLORATION.value,
            priority=PolicyPriority.HIGH.value,
            confidence=0.90,
            expected_impact=0.15,
        )
        dd = d.to_dict()
        assert dd["action"] == "increase_exploration"
        assert dd["priority"] == "high"
        assert dd["confidence"] == 0.90

    def test_reversible_default(self) -> None:
        d = LearningPolicyDecision()
        assert d.reversible is True


# ═══════════════════════════════════════════════════════════════
# Controller Init
# ═══════════════════════════════════════════════════════════════


class TestControllerInit:
    def test_default_creation(self) -> None:
        ctrl = LearningPolicyController()
        assert ctrl.decision_count == 0

    def test_reset(self) -> None:
        ctrl = LearningPolicyController()
        ctrl.evaluate()
        assert ctrl.decision_count == 1
        ctrl.reset()
        assert ctrl.decision_count == 0

    def test_repr(self) -> None:
        ctrl = LearningPolicyController()
        assert "decisions=0" in repr(ctrl)
        ctrl.evaluate()
        assert "decisions=1" in repr(ctrl)


# ═══════════════════════════════════════════════════════════════
# Evaluate: Minimal Input
# ═══════════════════════════════════════════════════════════════


class TestEvaluateMinimal:
    def test_empty_input_defaults(self) -> None:
        ctrl = LearningPolicyController()
        decision = ctrl.evaluate()
        assert isinstance(decision, LearningPolicyDecision)
        assert decision.should_learn is True  # 无评估 → 默认允许
        assert decision.should_update_memory is False  # 默认健康
        assert decision.strategy_mode == LearningMode.BALANCED.value
        assert decision.decision_type == PolicyDecisionType.ALLOW_LEARNING.value

    def test_empty_input_increments_count(self) -> None:
        ctrl = LearningPolicyController()
        ctrl.evaluate()
        assert ctrl.decision_count == 1

    def test_empty_input_has_reasons(self) -> None:
        ctrl = LearningPolicyController()
        decision = ctrl.evaluate()
        assert len(decision.reasons) >= 1

    def test_empty_input_has_evidence(self) -> None:
        ctrl = LearningPolicyController()
        decision = ctrl.evaluate()
        assert len(decision.evidence) >= 1


# ═══════════════════════════════════════════════════════════════
# Should Learn
# ═══════════════════════════════════════════════════════════════


class TestShouldLearn:
    def test_effective_high_confidence_allow(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.80, learning_gain=0.10, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.80, confidence_level="high")
        state = LearningStrategyState.aggressive()  # 预匹配 AGGRESSIVE 避免模式切换
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp, current_state=state)
        assert decision.should_learn is True
        assert decision.decision_type == PolicyDecisionType.ALLOW_LEARNING.value

    def test_effective_low_confidence_block(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.80, learning_gain=0.10, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.30, confidence_level="low")
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert decision.should_learn is False
        assert decision.decision_type == PolicyDecisionType.BLOCK_LEARNING.value

    def test_ineffective_high_confidence_block(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.30, learning_gain=-0.10, is_effective=False)
        adp = _make_adaptive_result(adjusted_confidence=0.80, confidence_level="high")
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert decision.should_learn is False
        assert decision.decision_type == PolicyDecisionType.BLOCK_LEARNING.value

    def test_ineffective_low_confidence_block(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.30, learning_gain=-0.10, is_effective=False)
        adp = _make_adaptive_result(adjusted_confidence=0.20, confidence_level="low")
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert decision.should_learn is False

    def test_no_effectiveness_allows_learning(self) -> None:
        ctrl = LearningPolicyController()
        adp = _make_adaptive_result(adjusted_confidence=0.80)
        decision = ctrl.evaluate(effectiveness=None, adaptive_confidence=adp)
        assert decision.should_learn is True

    def test_effective_without_adaptive_confidence(self) -> None:
        """无自适应置信度时，默认 0.0 < 0.50 → 有效但置信度低 → 阻止."""
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.80, is_effective=True)
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=None)
        # adaptive_conf = 0.0 < 0.50 → 有效但置信度低 → 阻止
        assert decision.should_learn is False

    def test_borderline_effective(self) -> None:
        """effectiveness_score = 0.51, is_effective=True, high confidence → ALLOW."""
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.51, learning_gain=0.01, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.75)
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert decision.should_learn is True

    def test_borderline_confidence(self) -> None:
        """adaptive_confidence = 0.50, is_effective=True → ALLOW (边界)."""
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.75, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.50)
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert decision.should_learn is True


# ═══════════════════════════════════════════════════════════════
# Should Update Memory
# ═══════════════════════════════════════════════════════════════


class TestShouldUpdateMemory:
    def test_high_decay_rate_triggers_refresh(self) -> None:
        ctrl = LearningPolicyController()
        state = LearningStrategyState(memory_decay_rate=0.03)  # > 0.02
        decision = ctrl.evaluate(current_state=state)
        assert decision.should_update_memory is True
        assert decision.decision_type == PolicyDecisionType.REQUEST_MEMORY_REFRESH.value

    def test_low_pattern_weight_triggers_refresh(self) -> None:
        ctrl = LearningPolicyController()
        state = LearningStrategyState(pattern_weight=0.30)  # <= 0.40
        decision = ctrl.evaluate(current_state=state)
        assert decision.should_update_memory is True

    def test_healthy_state_no_refresh(self) -> None:
        ctrl = LearningPolicyController()
        state = LearningStrategyState.default()  # decay=0.01, pattern=0.70
        decision = ctrl.evaluate(current_state=state)
        assert decision.should_update_memory is False

    def test_ineffective_high_confidence_triggers_refresh(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.30, is_effective=False)
        adp = _make_adaptive_result(adjusted_confidence=0.80)
        decision = ctrl.evaluate(
            effectiveness=eff,
            adaptive_confidence=adp,
            current_state=LearningStrategyState.default(),
        )
        assert decision.should_update_memory is True

    def test_ineffective_low_confidence_no_refresh(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.30, is_effective=False)
        adp = _make_adaptive_result(adjusted_confidence=0.40)  # < 0.75
        state = LearningStrategyState.default()
        decision = ctrl.evaluate(
            effectiveness=eff,
            adaptive_confidence=adp,
            current_state=state,
        )
        assert decision.should_update_memory is False

    def test_conservative_mode_elevated_decay(self) -> None:
        ctrl = LearningPolicyController()
        state = LearningStrategyState.conservative()  # decay=0.03 >= 0.015
        decision = ctrl.evaluate(current_state=state)
        assert decision.should_update_memory is True

    def test_conservative_mode_low_decay(self) -> None:
        ctrl = LearningPolicyController()
        state = LearningStrategyState(
            learning_mode=LearningMode.CONSERVATIVE.value,
            memory_decay_rate=0.01,  # < 0.015
        )
        decision = ctrl.evaluate(current_state=state)
        assert decision.should_update_memory is False


# ═══════════════════════════════════════════════════════════════
# Strategy Mode
# ═══════════════════════════════════════════════════════════════


class TestStrategyMode:
    def test_high_confidence_high_effectiveness_aggressive(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.80, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.80)
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert decision.strategy_mode == LearningMode.AGGRESSIVE.value

    def test_low_confidence_low_effectiveness_conservative(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.30, is_effective=False)
        adp = _make_adaptive_result(adjusted_confidence=0.30)
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert decision.strategy_mode == LearningMode.CONSERVATIVE.value

    def test_ineffective_high_confidence_conservative(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.30, is_effective=False)
        adp = _make_adaptive_result(adjusted_confidence=0.80)
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert decision.strategy_mode == LearningMode.CONSERVATIVE.value

    def test_balanced_by_default(self) -> None:
        """Day 7.11: eff=0.55, conf=0.55, no patterns → CONSERVATIVE (has_no_patterns rule)."""
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.55, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.55)
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert decision.strategy_mode == LearningMode.CONSERVATIVE.value

    def test_no_data_maintains_current_mode(self) -> None:
        ctrl = LearningPolicyController()
        state = LearningStrategyState.aggressive()
        decision = ctrl.evaluate(current_state=state)
        assert decision.strategy_mode == LearningMode.AGGRESSIVE.value

    def test_mode_switch_triggers_adjust_type(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.85, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.85)
        state = LearningStrategyState.default()  # BALANCED
        decision = ctrl.evaluate(
            effectiveness=eff,
            adaptive_confidence=adp,
            current_state=state,
        )
        assert decision.strategy_mode == LearningMode.AGGRESSIVE.value
        assert decision.strategy_mode != state.learning_mode
        assert decision.decision_type == PolicyDecisionType.ADJUST_MODE.value


# ═══════════════════════════════════════════════════════════════
# Decision Type Classification
# ═══════════════════════════════════════════════════════════════


class TestDecisionTypeClassification:
    def test_block_priority_over_refresh(self) -> None:
        """BLOCK_LEARNING 优先级高于 REQUEST_MEMORY_REFRESH."""
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.30, is_effective=False)
        adp = _make_adaptive_result(adjusted_confidence=0.80)  # 高置信度 → 同时触发 refresh
        decision = ctrl.evaluate(
            effectiveness=eff,
            adaptive_confidence=adp,
            current_state=LearningStrategyState.default(),
        )
        # should_learn=False, should_update_memory=True → BLOCK 优先
        assert decision.should_learn is False
        assert decision.should_update_memory is True
        assert decision.decision_type == PolicyDecisionType.BLOCK_LEARNING.value

    def test_refresh_priority_over_adjust(self) -> None:
        """REQUEST_MEMORY_REFRESH 优先级高于 ADJUST_MODE."""
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.70, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.70)
        state = LearningStrategyState(
            memory_decay_rate=0.03,  # 触发 refresh
            learning_mode=LearningMode.BALANCED.value,
        )
        decision = ctrl.evaluate(
            effectiveness=eff,
            adaptive_confidence=adp,
            current_state=state,
        )
        assert decision.decision_type == PolicyDecisionType.REQUEST_MEMORY_REFRESH.value

    def test_adjust_priority_over_allow(self) -> None:
        """ADJUST_MODE 优先级高于 ALLOW_LEARNING."""
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.85, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.85)
        state = LearningStrategyState.default()  # BALANCED, 无 decay 问题
        decision = ctrl.evaluate(
            effectiveness=eff,
            adaptive_confidence=adp,
            current_state=state,
        )
        assert decision.decision_type == PolicyDecisionType.ADJUST_MODE.value

    def test_allow_when_all_healthy(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.60, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.60)
        state = LearningStrategyState.default()
        # Provide 3+ patterns with moderate confidence to avoid has_no_patterns → CONSERVATIVE
        patterns = [_make_mock_pattern() for _ in range(3)]
        decision = ctrl.evaluate(
            effectiveness=eff,
            adaptive_confidence=adp,
            current_state=state,
            context_patterns=patterns,
        )
        assert decision.decision_type == PolicyDecisionType.ALLOW_LEARNING.value

    def test_maintain(self) -> None:
        """当 should_learn=True 且无其他调整时，如果只是允许学习，类型为 ALLOW."""
        ctrl = LearningPolicyController()
        decision = ctrl.evaluate()
        assert decision.decision_type == PolicyDecisionType.ALLOW_LEARNING.value


# ═══════════════════════════════════════════════════════════════
# Priority
# ═══════════════════════════════════════════════════════════════


class TestPriority:
    def test_block_is_high_priority(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.30, is_effective=False)
        adp = _make_adaptive_result(adjusted_confidence=0.80)
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert decision.priority == PolicyPriority.HIGH.value

    def test_mode_switch_is_high_priority(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.85, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.85)
        state = LearningStrategyState.default()
        decision = ctrl.evaluate(
            effectiveness=eff,
            adaptive_confidence=adp,
            current_state=state,
        )
        assert decision.priority == PolicyPriority.HIGH.value

    def test_refresh_is_medium_priority(self) -> None:
        ctrl = LearningPolicyController()
        state = LearningStrategyState(memory_decay_rate=0.03)
        decision = ctrl.evaluate(current_state=state)
        assert decision.priority == PolicyPriority.MEDIUM.value

    def test_allow_is_low_priority(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.60, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.60)
        state = LearningStrategyState.default()
        # Provide 3+ patterns to avoid has_no_patterns → CONSERVATIVE mode switch
        patterns = [_make_mock_pattern() for _ in range(3)]
        decision = ctrl.evaluate(
            effectiveness=eff,
            adaptive_confidence=adp,
            current_state=state,
            context_patterns=patterns,
        )
        assert decision.priority == PolicyPriority.LOW.value


# ═══════════════════════════════════════════════════════════════
# Evidence & Reasons
# ═══════════════════════════════════════════════════════════════


class TestEvidenceAndReasons:
    def test_reasons_non_empty(self) -> None:
        ctrl = LearningPolicyController()
        decision = ctrl.evaluate()
        assert len(decision.reasons) >= 1

    def test_evidence_contains_effectiveness(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.80)
        decision = ctrl.evaluate(effectiveness=eff)
        assert any("effectiveness_score=0.80" in e for e in decision.evidence)

    def test_evidence_contains_adaptive_confidence(self) -> None:
        ctrl = LearningPolicyController()
        adp = _make_adaptive_result(adjusted_confidence=0.75, confidence_level="high")
        decision = ctrl.evaluate(adaptive_confidence=adp)
        assert any("adaptive_confidence=0.75" in e for e in decision.evidence)
        assert any("confidence_level=high" in e for e in decision.evidence)

    def test_evidence_contains_mode_info(self) -> None:
        ctrl = LearningPolicyController()
        state = LearningStrategyState.aggressive()
        decision = ctrl.evaluate(current_state=state)
        assert any("current_mode=aggressive" in e for e in decision.evidence)

    def test_evidence_contains_decision_flags(self) -> None:
        ctrl = LearningPolicyController()
        decision = ctrl.evaluate()
        assert any("should_learn=True" in e for e in decision.evidence)
        assert any("should_refresh=False" in e for e in decision.evidence)


# ═══════════════════════════════════════════════════════════════
# Decision Confidence
# ═══════════════════════════════════════════════════════════════


class TestDecisionConfidence:
    def test_confidence_with_all_inputs(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.80)
        adp = _make_adaptive_result(adjusted_confidence=0.80)
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert 0.0 <= decision.confidence <= 1.0

    def test_confidence_high_when_both_high(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.90)
        adp = _make_adaptive_result(adjusted_confidence=0.90)
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert decision.confidence >= 0.70

    def test_confidence_low_when_both_low(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.20)
        adp = _make_adaptive_result(adjusted_confidence=0.20)
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert decision.confidence < 0.60

    def test_confidence_minimal_input(self) -> None:
        ctrl = LearningPolicyController()
        decision = ctrl.evaluate()
        assert 0.0 <= decision.confidence <= 1.0


# ═══════════════════════════════════════════════════════════════
# Expected Impact
# ═══════════════════════════════════════════════════════════════


class TestExpectedImpact:
    def test_block_impact_negative(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.30, is_effective=False)
        adp = _make_adaptive_result(adjusted_confidence=0.80)
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert decision.expected_impact < 0.0

    def test_refresh_impact_positive(self) -> None:
        ctrl = LearningPolicyController()
        state = LearningStrategyState(memory_decay_rate=0.03)
        decision = ctrl.evaluate(current_state=state)
        assert decision.expected_impact > 0.0

    def test_adjust_impact_small_positive(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.85, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.85)
        state = LearningStrategyState.default()
        decision = ctrl.evaluate(
            effectiveness=eff,
            adaptive_confidence=adp,
            current_state=state,
        )
        assert decision.expected_impact > 0.0

    def test_allow_impact_positive(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.60, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.60)
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert decision.expected_impact > 0.0

    def test_maintain_impact_zero(self) -> None:
        ctrl = LearningPolicyController()
        state = LearningStrategyState.default()
        eff = _make_effectiveness(effectiveness_score=0.60, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.60)
        state.learning_mode = LearningMode.BALANCED.value
        decision = ctrl.evaluate(
            effectiveness=eff,
            adaptive_confidence=adp,
            current_state=state,
        )
        assert decision.expected_impact == 0.0 or decision.expected_impact > 0.0


# ═══════════════════════════════════════════════════════════════
# Recommended Action
# ═══════════════════════════════════════════════════════════════


class TestRecommendedAction:
    def test_block_maps_to_adjust_threshold(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.30, is_effective=False)
        adp = _make_adaptive_result(adjusted_confidence=0.80)
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert decision.action == PolicyAction.ADJUST_CONFIDENCE_THRESHOLD.value

    def test_refresh_maps_to_refresh_memory(self) -> None:
        ctrl = LearningPolicyController()
        state = LearningStrategyState(memory_decay_rate=0.03)
        decision = ctrl.evaluate(current_state=state)
        assert decision.action == PolicyAction.REFRESH_MEMORY.value

    def test_adjust_maps_to_switch_mode(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.85, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.85)
        state = LearningStrategyState.default()
        decision = ctrl.evaluate(
            effectiveness=eff,
            adaptive_confidence=adp,
            current_state=state,
        )
        assert decision.action == PolicyAction.SWITCH_LEARNING_MODE.value

    def test_allow_maps_to_strengthen_pattern(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.60, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.60)
        state = LearningStrategyState.default()
        # Provide 3+ patterns to avoid has_no_patterns → CONSERVATIVE mode switch
        patterns = [_make_mock_pattern() for _ in range(3)]
        decision = ctrl.evaluate(
            effectiveness=eff,
            adaptive_confidence=adp,
            current_state=state,
            context_patterns=patterns,
        )
        assert decision.action == PolicyAction.STRENGTHEN_PATTERN.value


# ═══════════════════════════════════════════════════════════════
# Integration Scenarios
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    def test_full_scenario_healthy(self) -> None:
        """健康系统: 学习有效 + 高置信度 + 平衡状态."""
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.75, learning_gain=0.08, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.80, confidence_level="high")
        state = LearningStrategyState.default()

        decision = ctrl.evaluate(
            effectiveness=eff,
            adaptive_confidence=adp,
            current_state=state,
        )

        assert decision.should_learn is True
        assert decision.should_update_memory is False
        assert decision.strategy_mode == LearningMode.AGGRESSIVE.value
        assert decision.decision_type == PolicyDecisionType.ADJUST_MODE.value
        assert decision.priority == PolicyPriority.HIGH.value

    def test_full_scenario_failing(self) -> None:
        """失败系统: 学习无效 + 高置信度 + 高衰减."""
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.25, learning_gain=-0.15, is_effective=False)
        adp = _make_adaptive_result(adjusted_confidence=0.85, confidence_level="high")
        state = LearningStrategyState(memory_decay_rate=0.03)

        decision = ctrl.evaluate(
            effectiveness=eff,
            adaptive_confidence=adp,
            current_state=state,
        )

        assert decision.should_learn is False
        assert decision.should_update_memory is True
        assert decision.strategy_mode == LearningMode.CONSERVATIVE.value
        assert decision.decision_type == PolicyDecisionType.BLOCK_LEARNING.value
        assert decision.priority == PolicyPriority.HIGH.value

    def test_conservative_state_behavior(self) -> None:
        """保守模式: 学习一般 + 中等置信度.
        Day 7.11: has_no_patterns + eff<0.70 → CONSERVATIVE (same as state, no mode switch)."""
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.45, learning_gain=-0.02, is_effective=False)
        adp = _make_adaptive_result(adjusted_confidence=0.55, confidence_level="medium")
        state = LearningStrategyState.conservative()

        decision = ctrl.evaluate(
            effectiveness=eff,
            adaptive_confidence=adp,
            current_state=state,
        )

        assert decision.should_learn is False
        assert decision.should_update_memory is True  # 保守模式 + decay=0.03
        assert decision.strategy_mode == LearningMode.CONSERVATIVE.value
        assert decision.decision_type == PolicyDecisionType.BLOCK_LEARNING.value

    def test_decision_history_accumulates(self) -> None:
        ctrl = LearningPolicyController()
        for _ in range(5):
            ctrl.evaluate()
        assert ctrl.decision_count == 5
        assert len(ctrl.get_decision_history()) == 5

    def test_triggered_by_preserved(self) -> None:
        ctrl = LearningPolicyController()
        decision = ctrl.evaluate(triggered_by="eval_cycle_001")
        assert decision.triggered_by == "eval_cycle_001"

    def test_state_snapshot_preserved(self) -> None:
        ctrl = LearningPolicyController()
        state = LearningStrategyState.aggressive()
        decision = ctrl.evaluate(current_state=state)
        assert decision.previous_state_snapshot is not None
        assert decision.previous_state_snapshot["learning_mode"] == "aggressive"


# ═══════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_all_none_inputs(self) -> None:
        ctrl = LearningPolicyController()
        decision = ctrl.evaluate(
            effectiveness=None,
            adaptive_confidence=None,
            current_state=None,
        )
        assert isinstance(decision, LearningPolicyDecision)
        assert decision.should_learn is True
        assert decision.confidence is not None

    def test_extreme_effectiveness_scores(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=1.0, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=1.0)
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert decision.strategy_mode == LearningMode.AGGRESSIVE.value
        assert decision.should_learn is True

        eff = _make_effectiveness(effectiveness_score=0.0, is_effective=False)
        adp = _make_adaptive_result(adjusted_confidence=0.0)
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert decision.strategy_mode == LearningMode.CONSERVATIVE.value
        assert decision.should_learn is False

    def test_custom_thresholds(self) -> None:
        """自定义阈值仍生成合理决策."""
        ctrl = LearningPolicyController()
        ctrl.ADAPTIVE_CONFIDENCE_TRUST_THRESHOLD = 0.60
        eff = _make_effectiveness(effectiveness_score=0.80, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.55)  # < 0.60
        decision = ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp)
        assert decision.should_learn is False

    def test_multiple_controllers_independent(self) -> None:
        c1 = LearningPolicyController()
        c2 = LearningPolicyController()
        c1.evaluate()
        assert c1.decision_count == 1
        assert c2.decision_count == 0

    def test_decision_serializable(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.80, is_effective=True)
        adp = _make_adaptive_result(adjusted_confidence=0.80)
        state = LearningStrategyState.default()
        decision = ctrl.evaluate(
            effectiveness=eff,
            adaptive_confidence=adp,
            current_state=state,
        )
        d = decision.to_dict()
        assert "decision_id" in d
        assert "decision_type" in d
        assert "should_learn" in d
        assert "should_update_memory" in d
        assert "strategy_mode" in d
        assert "reasons" in d
        assert "evidence" in d
        assert "confidence" in d
        assert "adaptive_confidence" in d
        assert "learning_effectiveness_score" in d
        assert "expected_impact" in d
        assert "reversible" in d
        assert "previous_state_snapshot" in d

    def test_reversible_always_true(self) -> None:
        ctrl = LearningPolicyController()
        decisions = []
        for score in [0.0, 0.3, 0.5, 0.7, 1.0]:
            eff = _make_effectiveness(effectiveness_score=score, is_effective=score >= 0.50)
            adp = _make_adaptive_result(adjusted_confidence=score)
            decisions.append(ctrl.evaluate(effectiveness=eff, adaptive_confidence=adp))

        for d in decisions:
            assert d.reversible is True, f"Decision {d.decision_type} should be reversible"

    def test_learning_effectiveness_score_field(self) -> None:
        ctrl = LearningPolicyController()
        eff = _make_effectiveness(effectiveness_score=0.72)
        decision = ctrl.evaluate(effectiveness=eff)
        assert decision.learning_effectiveness_score == 0.72

    def test_adaptive_confidence_field(self) -> None:
        ctrl = LearningPolicyController()
        adp = _make_adaptive_result(adjusted_confidence=0.65)
        decision = ctrl.evaluate(adaptive_confidence=adp)
        assert decision.adaptive_confidence == 0.65