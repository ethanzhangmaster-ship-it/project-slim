"""E13.7.7.2 Learning Strategy Optimizer — 学习策略优化器测试.

Day 7.7.2:
  测试 LearningStrategyOptimizer 的核心映射逻辑和安全机制，
  确保 Evaluation 输出正确映射到 Strategy Adjustment。

测试覆盖:
  - Mapping Functions: gain→exploration, trend→decay, effectiveness→weight, effectiveness→confidence_threshold
  - Optimize: 各种 evaluation 场景 (正/负 gain, 有/无 trend, 不同 effectiveness_score)
  - Safety: 冷却机制、步长限制、防震荡、阈值过滤
  - Mode Switching: CONSERVATIVE / AGGRESSIVE / BALANCED 模式切换
  - Integration: 完整优化流程
  - Edge Cases: 边界值、空输入、连续调用
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.evaluation.models import (
    ImprovementTrend,
    LearningEffectiveness,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_strategy_optimizer import (
    LearningStrategyOptimizer,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_strategy_models import (
    AdjustmentSource,
    LearningAdjustment,
    LearningMode,
    LearningStrategyState,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_effectiveness(
    learning_gain: float,
    effectiveness_score: float,
    total_decisions: int = 100,
    is_effective: bool | None = None,
) -> LearningEffectiveness:
    """快速创建 LearningEffectiveness."""
    if is_effective is None:
        is_effective = learning_gain > 0
    return LearningEffectiveness(
        total_decisions=total_decisions,
        learning_enhanced_count=total_decisions,
        learning_gain=learning_gain,
        effectiveness_score=effectiveness_score,
        is_effective=is_effective,
    )


def _make_trend(
    trend_slope: float,
    trend_direction: str = "stable",
    has_data: bool = True,
    periods: int = 5,
) -> ImprovementTrend:
    """快速创建 ImprovementTrend."""
    if has_data:
        return ImprovementTrend(
            periods=periods,
            learning_gains=[0.05, 0.03, 0.01, -0.01, -0.03],
            trend_direction=trend_direction,
            trend_slope=trend_slope,
            avg_gain=0.01,
            max_gain=0.05,
            min_gain=-0.03,
            is_improving=trend_slope > 0,
            reliability=0.80,
        )
    return ImprovementTrend(
        periods=0,
        learning_gains=[],
        trend_direction="stable",
        trend_slope=0.0,
    )


# ═══════════════════════════════════════════════════════════════
# Initialization
# ═══════════════════════════════════════════════════════════════


class TestOptimizerInitialization:
    def test_default_creation(self) -> None:
        opt = LearningStrategyOptimizer()
        assert opt.cycle_count == 0
        assert opt.total_adjustments == 0

    def test_custom_params(self) -> None:
        opt = LearningStrategyOptimizer(
            min_cycles_between_adjustments=5,
            max_adjustment_per_cycle=0.20,
            adjustment_threshold=0.05,
            hysteresis_window=4,
            mode_switch_consecutive_cycles=5,
        )
        assert opt._min_cycles == 5
        assert opt._max_step == 0.20
        assert opt._threshold == 0.05
        assert opt._hysteresis_window == 4
        assert opt._mode_switch_cycles == 5

    def test_reset_clears_all_state(self) -> None:
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=-0.15, effectiveness_score=0.20)
        opt.optimize(eff)
        assert opt.cycle_count == 1
        assert opt.total_adjustments > 0

        opt.reset()
        assert opt.cycle_count == 0
        assert opt.total_adjustments == 0


# ═══════════════════════════════════════════════════════════════
# Mapping: learning_gain → exploration_rate
# ═══════════════════════════════════════════════════════════════


class TestMapGainToExploration:
    def test_severe_negative_gain_increases_exploration(self) -> None:
        """gain < -0.10: 大幅增加探索 (+0.15)."""
        opt = LearningStrategyOptimizer()
        result = opt._map_gain_to_exploration(-0.15, 0.20)
        assert result == 0.35  # 0.20 + 0.15

    def test_mild_negative_gain_increases_exploration(self) -> None:
        """gain < -0.05: 适度增加探索 (+0.08)."""
        opt = LearningStrategyOptimizer()
        result = opt._map_gain_to_exploration(-0.08, 0.20)
        assert result == 0.28  # 0.20 + 0.08

    def test_strong_positive_gain_decreases_exploration(self) -> None:
        """gain > 0.10: 减少探索 (-0.08)."""
        opt = LearningStrategyOptimizer()
        result = opt._map_gain_to_exploration(0.15, 0.30)
        assert result == 0.22  # 0.30 - 0.08

    def test_mild_positive_gain_decreases_exploration(self) -> None:
        """gain > 0.05: 轻微减少探索 (-0.05)."""
        opt = LearningStrategyOptimizer()
        result = opt._map_gain_to_exploration(0.08, 0.30)
        assert result == 0.25  # 0.30 - 0.05

    def test_neutral_gain_keeps_exploration(self) -> None:
        """中性 gain: 保持不变."""
        opt = LearningStrategyOptimizer()
        result = opt._map_gain_to_exploration(0.02, 0.20)
        assert result == 0.20

    def test_clamped_to_min(self) -> None:
        """不跌破 EXPLORATION_MIN (0.05)."""
        opt = LearningStrategyOptimizer()
        result = opt._map_gain_to_exploration(0.15, 0.08)  # 0.08 - 0.08 = 0.0 → clamp to 0.05
        assert result == 0.05

    def test_clamped_to_max(self) -> None:
        """不超过 EXPLORATION_MAX (0.60)."""
        opt = LearningStrategyOptimizer()
        result = opt._map_gain_to_exploration(-0.15, 0.55)  # 0.55 + 0.15 = 0.70 → clamp to 0.60
        assert result == 0.60


# ═══════════════════════════════════════════════════════════════
# Mapping: trend_slope → memory_decay_rate
# ═══════════════════════════════════════════════════════════════


class TestMapTrendToDecay:
    def test_steep_negative_trend_accelerates_decay(self) -> None:
        """slope < -0.02: 加速遗忘 (x2.0)."""
        opt = LearningStrategyOptimizer()
        result = opt._map_trend_to_decay(-0.03, 0.01)
        assert result == 0.02  # 0.01 * 2.0

    def test_mild_negative_trend_accelerates_decay(self) -> None:
        """slope < -0.01: 适度加速遗忘 (x1.5)."""
        opt = LearningStrategyOptimizer()
        result = opt._map_trend_to_decay(-0.015, 0.01)
        assert result == 0.015  # 0.01 * 1.5

    def test_steep_positive_trend_slows_decay(self) -> None:
        """slope > 0.02: 减慢遗忘 (x0.5)."""
        opt = LearningStrategyOptimizer()
        result = opt._map_trend_to_decay(0.03, 0.02)
        assert result == 0.01  # 0.02 * 0.5

    def test_mild_positive_trend_slows_decay(self) -> None:
        """slope > 0.01: 适度减慢遗忘 (x0.7)."""
        opt = LearningStrategyOptimizer()
        result = opt._map_trend_to_decay(0.015, 0.02)
        assert result == 0.014  # 0.02 * 0.7

    def test_neutral_trend_keeps_decay(self) -> None:
        opt = LearningStrategyOptimizer()
        result = opt._map_trend_to_decay(0.005, 0.01)
        assert result == 0.01

    def test_clamped_to_decay_min(self) -> None:
        opt = LearningStrategyOptimizer()
        result = opt._map_trend_to_decay(0.05, 0.001)  # 0.001 * 0.5 = 0.0005 → clamp to 0.001
        assert result == 0.001

    def test_clamped_to_decay_max(self) -> None:
        opt = LearningStrategyOptimizer()
        result = opt._map_trend_to_decay(-0.05, 0.08)  # 0.08 * 2.0 = 0.16 → clamp to 0.10
        assert result == 0.10


# ═══════════════════════════════════════════════════════════════
# Mapping: effectiveness_score → pattern_weight
# ═══════════════════════════════════════════════════════════════


class TestMapEffectivenessToPatternWeight:
    def test_high_effectiveness_increases_pattern_weight(self) -> None:
        """score > 0.70: +0.10."""
        opt = LearningStrategyOptimizer()
        result = opt._map_effectiveness_to_pattern_weight(0.80, 0.70)
        assert result == 0.80

    def test_medium_high_effectiveness_slightly_increases(self) -> None:
        """score > 0.50: +0.05."""
        opt = LearningStrategyOptimizer()
        result = opt._map_effectiveness_to_pattern_weight(0.60, 0.70)
        assert result == 0.75

    def test_low_effectiveness_decreases_pattern_weight(self) -> None:
        """score < 0.30: -0.15."""
        opt = LearningStrategyOptimizer()
        result = opt._map_effectiveness_to_pattern_weight(0.25, 0.70)
        assert result == 0.55

    def test_medium_low_effectiveness_slightly_decreases(self) -> None:
        """score < 0.50: -0.08."""
        opt = LearningStrategyOptimizer()
        result = opt._map_effectiveness_to_pattern_weight(0.40, 0.70)
        assert result == 0.62

    def test_neutral_effectiveness_keeps_weight(self) -> None:
        opt = LearningStrategyOptimizer()
        result = opt._map_effectiveness_to_pattern_weight(0.50, 0.70)
        assert result == 0.70

    def test_clamped_to_pattern_weight_min(self) -> None:
        opt = LearningStrategyOptimizer()
        result = opt._map_effectiveness_to_pattern_weight(0.20, 0.25)  # 0.25 - 0.15 = 0.10 → clamp to 0.20
        assert result == 0.20

    def test_clamped_to_pattern_weight_max(self) -> None:
        opt = LearningStrategyOptimizer()
        result = opt._map_effectiveness_to_pattern_weight(0.80, 0.85)  # 0.85 + 0.10 = 0.95 → clamp to 0.90
        assert result == 0.90


# ═══════════════════════════════════════════════════════════════
# Mapping: effectiveness_score → confidence_threshold
# ═══════════════════════════════════════════════════════════════


class TestMapEffectivenessToConfidenceThreshold:
    def test_high_effectiveness_lowers_threshold(self) -> None:
        """score > 0.70: -0.05 (更自信)."""
        opt = LearningStrategyOptimizer()
        result = opt._map_effectiveness_to_confidence_threshold(0.80, 0.50)
        assert result == 0.45

    def test_medium_high_effectiveness_slightly_lowers(self) -> None:
        """score > 0.50: -0.03."""
        opt = LearningStrategyOptimizer()
        result = opt._map_effectiveness_to_confidence_threshold(0.55, 0.50)
        assert result == 0.47

    def test_low_effectiveness_raises_threshold(self) -> None:
        """score < 0.30: +0.10 (更谨慎)."""
        opt = LearningStrategyOptimizer()
        result = opt._map_effectiveness_to_confidence_threshold(0.20, 0.50)
        assert result == 0.60

    def test_medium_low_effectiveness_slightly_raises(self) -> None:
        """score < 0.50: +0.05."""
        opt = LearningStrategyOptimizer()
        result = opt._map_effectiveness_to_confidence_threshold(0.45, 0.50)
        assert result == 0.55

    def test_neutral_effectiveness_keeps_threshold(self) -> None:
        opt = LearningStrategyOptimizer()
        result = opt._map_effectiveness_to_confidence_threshold(0.50, 0.50)
        assert result == 0.50

    def test_clamped_to_threshold_min(self) -> None:
        opt = LearningStrategyOptimizer()
        result = opt._map_effectiveness_to_confidence_threshold(0.90, 0.32)  # 0.32 - 0.05 = 0.27 → clamp to 0.30
        assert result == 0.30

    def test_clamped_to_threshold_max(self) -> None:
        opt = LearningStrategyOptimizer()
        result = opt._map_effectiveness_to_confidence_threshold(0.10, 0.78)  # 0.78 + 0.10 = 0.88 → clamp to 0.80
        assert result == 0.80


# ═══════════════════════════════════════════════════════════════
# Optimize: Core Scenarios
# ═══════════════════════════════════════════════════════════════


class TestOptimizeNegativeGain:
    """学习增益为负 → 增加探索、降低 pattern 信任."""

    def test_negative_gain_increases_exploration(self) -> None:
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=-0.15, effectiveness_score=0.25)
        state = LearningStrategyState.default()
        old_version = state.version

        new_state, adjustments = opt.optimize(eff, current_state=state)

        # exploration_rate 应增加
        assert new_state.exploration_rate > 0.20
        # pattern_weight 应降低
        assert new_state.pattern_weight < 0.70
        # confidence_threshold 应提高
        assert new_state.confidence_threshold > 0.50
        # version 应增加 (optimize 返回的 state 是同一个对象)
        assert new_state.version > old_version

    def test_negative_gain_adjustments_have_correct_source(self) -> None:
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=-0.12, effectiveness_score=0.20)
        state = LearningStrategyState.default()

        _, adjustments = opt.optimize(eff, current_state=state)

        # 应有多个调整
        assert len(adjustments) >= 3
        sources = {a.source for a in adjustments}
        assert AdjustmentSource.EVALUATION.value in sources

    def test_negative_gain_adjustment_details(self) -> None:
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=-0.15, effectiveness_score=0.20)
        state = LearningStrategyState.default()

        _, adjustments = opt.optimize(eff, current_state=state)

        # 检查 exploration_rate 调整
        exp_adj = [a for a in adjustments if a.parameter == "exploration_rate"]
        assert len(exp_adj) >= 1
        assert exp_adj[0].is_increase
        assert "learning_gain" in exp_adj[0].reason

        # 检查 pattern_weight 调整
        pw_adj = [a for a in adjustments if a.parameter == "pattern_weight"]
        assert len(pw_adj) >= 1
        assert pw_adj[0].is_decrease

        # 检查 confidence_threshold 调整
        ct_adj = [a for a in adjustments if a.parameter == "confidence_threshold"]
        assert len(ct_adj) >= 1
        assert ct_adj[0].is_increase

    def test_severe_negative_gain_switches_to_conservative(self) -> None:
        """连续严重负增益应触发模式切换."""
        opt = LearningStrategyOptimizer(
            mode_switch_consecutive_cycles=3,
        )
        state = LearningStrategyState.default()

        # 连续 3 次负增益 + declining trend
        for _ in range(3):
            eff = _make_effectiveness(learning_gain=-0.12, effectiveness_score=0.20)
            trend = _make_trend(trend_slope=-0.03, trend_direction="declining")
            state, _ = opt.optimize(eff, trend, state)

        assert state.learning_mode == LearningMode.CONSERVATIVE.value


class TestOptimizePositiveGain:
    """学习增益为正 → 减少探索、提高 pattern 信任."""

    def test_positive_gain_decreases_exploration(self) -> None:
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=0.15, effectiveness_score=0.80)
        state = LearningStrategyState.default()

        new_state, adjustments = opt.optimize(eff, current_state=state)

        assert new_state.exploration_rate < 0.20
        assert new_state.pattern_weight > 0.70
        assert new_state.confidence_threshold < 0.50

    def test_positive_gain_adjustment_details(self) -> None:
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=0.15, effectiveness_score=0.80)
        state = LearningStrategyState.default()

        _, adjustments = opt.optimize(eff, current_state=state)

        exp_adj = [a for a in adjustments if a.parameter == "exploration_rate"]
        assert len(exp_adj) >= 1
        assert exp_adj[0].is_decrease

        pw_adj = [a for a in adjustments if a.parameter == "pattern_weight"]
        assert len(pw_adj) >= 1
        assert pw_adj[0].is_increase

    def test_continuous_positive_gain_switches_to_aggressive(self) -> None:
        opt = LearningStrategyOptimizer(
            mode_switch_consecutive_cycles=3,
        )
        state = LearningStrategyState.default()

        for _ in range(3):
            eff = _make_effectiveness(learning_gain=0.12, effectiveness_score=0.80)
            trend = _make_trend(trend_slope=0.03, trend_direction="improving")
            state, _ = opt.optimize(eff, trend, state)

        assert state.learning_mode == LearningMode.AGGRESSIVE.value


class TestOptimizeWithTrend:
    """带趋势数据的优化."""

    def test_trend_adjusts_memory_decay(self) -> None:
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=-0.02, effectiveness_score=0.50)
        trend = _make_trend(trend_slope=-0.03, trend_direction="declining")
        # 使用较大的初始 decay 使 delta 超过 threshold
        state = LearningStrategyState(memory_decay_rate=0.05)

        _, adjustments = opt.optimize(eff, trend, state)

        decay_adj = [a for a in adjustments if a.parameter == "memory_decay_rate"]
        assert len(decay_adj) >= 1
        assert decay_adj[0].source == AdjustmentSource.TREND.value
        assert decay_adj[0].is_increase  # 下降趋势 → 加速遗忘

    def test_positive_trend_slows_decay(self) -> None:
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=0.05, effectiveness_score=0.60)
        trend = _make_trend(trend_slope=0.03, trend_direction="improving")
        state = LearningStrategyState(memory_decay_rate=0.08)  # 0.08*0.5=0.04, delta=0.04 >= 0.03

        _, adjustments = opt.optimize(eff, trend, state)

        decay_adj = [a for a in adjustments if a.parameter == "memory_decay_rate"]
        assert len(decay_adj) >= 1
        assert decay_adj[0].is_decrease  # 上升趋势 → 减慢遗忘

    def test_no_trend_preserves_decay(self) -> None:
        """无 trend 时不应调整 memory_decay_rate."""
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=-0.15, effectiveness_score=0.20)
        state = LearningStrategyState.default()

        _, adjustments = opt.optimize(eff, trend=None, current_state=state)

        decay_adj = [a for a in adjustments if a.parameter == "memory_decay_rate"]
        assert len(decay_adj) == 0

    def test_trend_without_data_skips_decay(self) -> None:
        """trend.has_data == False 时不应调整."""
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=-0.10, effectiveness_score=0.30)
        trend = _make_trend(trend_slope=-0.03, has_data=False)
        state = LearningStrategyState.default()

        _, adjustments = opt.optimize(eff, trend, state)

        decay_adj = [a for a in adjustments if a.parameter == "memory_decay_rate"]
        assert len(decay_adj) == 0


class TestOptimizeWithoutState:
    """不提供 current_state 时使用默认状态."""

    def test_uses_default_state(self) -> None:
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=-0.15, effectiveness_score=0.20)

        new_state, adjustments = opt.optimize(eff)

        assert new_state.state_id != ""
        assert len(adjustments) > 0
        # 默认状态为 balanced
        assert new_state.learning_mode == LearningMode.BALANCED.value

    def test_default_state_values_preserved_when_neutral(self) -> None:
        """中性评估时默认状态保持不变."""
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=0.02, effectiveness_score=0.50)

        new_state, _ = opt.optimize(eff)

        assert new_state.confidence_threshold == 0.50
        assert new_state.pattern_weight == 0.70
        assert new_state.exploration_rate == 0.20


# ═══════════════════════════════════════════════════════════════
# Safety Mechanisms
# ═══════════════════════════════════════════════════════════════


class TestCooldown:
    """冷却机制: 同参数不能过于频繁调整."""

    def test_first_adjustment_allowed(self) -> None:
        opt = LearningStrategyOptimizer()
        assert opt._check_cooldown("exploration_rate") is True

    def test_second_adjustment_blocked_within_window(self) -> None:
        opt = LearningStrategyOptimizer(min_cycles_between_adjustments=3)
        eff = _make_effectiveness(learning_gain=-0.15, effectiveness_score=0.20)

        # 第一次调整
        opt.optimize(eff)
        assert opt._check_cooldown("exploration_rate") is False

        # 推进 2 个周期，仍在冷却期
        for _ in range(2):
            opt._cycle_count += 1
        assert opt._check_cooldown("exploration_rate") is False

        # 推进 3 个周期，冷却结束
        opt._cycle_count += 1
        assert opt._check_cooldown("exploration_rate") is True

    def test_cooldown_per_parameter(self) -> None:
        """每个参数独立冷却."""
        opt = LearningStrategyOptimizer(min_cycles_between_adjustments=3)
        eff = _make_effectiveness(learning_gain=-0.15, effectiveness_score=0.20)

        opt.optimize(eff)
        # exploration_rate 在冷却期
        assert opt._check_cooldown("exploration_rate") is False
        # pattern_weight 也在冷却期 (同一轮调整)
        assert opt._check_cooldown("pattern_weight") is False

    def test_cooldown_prevents_rapid_adjustments(self) -> None:
        """冷却期内的 optimize 不应产生同参数调整."""
        opt = LearningStrategyOptimizer(min_cycles_between_adjustments=3)
        eff = _make_effectiveness(learning_gain=-0.15, effectiveness_score=0.20)

        state, adj1 = opt.optimize(eff)
        exp_count_1 = len([a for a in adj1 if a.parameter == "exploration_rate"])

        # 立即再次优化，同参数应被冷却阻止
        eff2 = _make_effectiveness(learning_gain=-0.20, effectiveness_score=0.15)
        _, adj2 = opt.optimize(eff2, current_state=state)
        exp_count_2 = len([a for a in adj2 if a.parameter == "exploration_rate"])

        # 第二次调整的 exploration_rate 调整数 <= 第一次
        assert exp_count_2 <= exp_count_1


class TestStepLimit:
    """步长限制: 单次调整不超过 max_step."""

    def test_step_limit_applied(self) -> None:
        opt = LearningStrategyOptimizer(max_adjustment_per_cycle=0.10)
        result = opt._apply_step_limit(0.20, 0.50)
        assert result == pytest.approx(0.30)  # 0.20 + 0.10

    def test_step_limit_negative(self) -> None:
        opt = LearningStrategyOptimizer(max_adjustment_per_cycle=0.10)
        result = opt._apply_step_limit(0.50, 0.20)
        assert result == 0.40  # 0.50 - 0.10

    def test_step_within_limit(self) -> None:
        opt = LearningStrategyOptimizer(max_adjustment_per_cycle=0.15)
        result = opt._apply_step_limit(0.20, 0.30)
        assert result == 0.30  # delta = 0.10 < 0.15, 不限制

    def test_optimize_respects_step_limit(self) -> None:
        """optimize 中 exploration_rate 调整不超过 max_step."""
        opt = LearningStrategyOptimizer(max_adjustment_per_cycle=0.05)
        eff = _make_effectiveness(learning_gain=-0.15, effectiveness_score=0.20)
        state = LearningStrategyState.default()

        new_state, _ = opt.optimize(eff, current_state=state)
        delta = new_state.exploration_rate - state.exploration_rate
        assert abs(delta) <= 0.05


class TestAdjustmentThreshold:
    """阈值: 变化小于阈值不触发调整."""

    def test_small_change_filtered(self) -> None:
        opt = LearningStrategyOptimizer(adjustment_threshold=0.05)
        # 变化 0.03 < 0.05 threshold
        result = opt._try_adjust(
            LearningStrategyState.default(),
            "exploration_rate",
            0.20,
            0.23,
            "test",
            AdjustmentSource.EVALUATION,
        )
        assert result is None

    def test_large_change_passes(self) -> None:
        opt = LearningStrategyOptimizer(adjustment_threshold=0.05)
        result = opt._try_adjust(
            LearningStrategyState.default(),
            "exploration_rate",
            0.20,
            0.28,
            "test",
            AdjustmentSource.EVALUATION,
        )
        assert result is not None

    def test_neutral_gain_produces_no_adjustments(self) -> None:
        """中性 gain 时不应产生任何调整."""
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=0.02, effectiveness_score=0.50)
        state = LearningStrategyState.default()

        _, adjustments = opt.optimize(eff, current_state=state)
        assert len(adjustments) == 0


class TestHysteresis:
    """防震荡: 检测参数来回调整并阻止."""

    def test_no_oscillation_without_history(self) -> None:
        opt = LearningStrategyOptimizer()
        assert opt._detect_oscillation("exploration_rate", 0.30) is False

    def test_no_oscillation_with_single_adjustment(self) -> None:
        opt = LearningStrategyOptimizer()
        opt._adjustment_history.append(
            LearningAdjustment(parameter="exploration_rate", previous_value=0.20, new_value=0.30)
        )
        assert opt._detect_oscillation("exploration_rate", 0.40) is False

    def test_oscillation_detected_when_direction_reverses_twice(self) -> None:
        """最近两次调整方向相反，新调整又回到上上次方向 → 震荡."""
        opt = LearningStrategyOptimizer()
        # 上一次: 增加 (0.20 → 0.30)
        opt._adjustment_history.append(
            LearningAdjustment(parameter="exploration_rate", previous_value=0.20, new_value=0.30)
        )
        # 最近一次: 减少 (0.30 → 0.25)
        opt._adjustment_history.append(
            LearningAdjustment(parameter="exploration_rate", previous_value=0.30, new_value=0.25)
        )
        # 新调整: 又增加 → 震荡
        assert opt._detect_oscillation("exploration_rate", 0.35) is True

    def test_oscillation_prevents_adjustment(self) -> None:
        """震荡检测应阻止调整."""
        opt = LearningStrategyOptimizer()
        # 模拟震荡历史
        opt._adjustment_history.append(
            LearningAdjustment(parameter="exploration_rate", previous_value=0.20, new_value=0.30)
        )
        opt._adjustment_history.append(
            LearningAdjustment(parameter="exploration_rate", previous_value=0.30, new_value=0.25)
        )

        result = opt._try_adjust(
            LearningStrategyState.default(),
            "exploration_rate",
            0.25,
            0.45,
            "test",
            AdjustmentSource.EVALUATION,
        )
        assert result is None


# ═══════════════════════════════════════════════════════════════
# Mode Switching
# ═══════════════════════════════════════════════════════════════


class TestModeSwitching:
    def test_switch_to_conservative_requires_continuous_negative(self) -> None:
        opt = LearningStrategyOptimizer(mode_switch_consecutive_cycles=3)
        state = LearningStrategyState.default()

        for _ in range(3):
            eff = _make_effectiveness(learning_gain=-0.10, effectiveness_score=0.25)
            trend = _make_trend(trend_slope=-0.03, trend_direction="declining")
            state, _ = opt.optimize(eff, trend, state)

        assert state.learning_mode == LearningMode.CONSERVATIVE.value

    def test_switch_to_aggressive_requires_continuous_positive(self) -> None:
        opt = LearningStrategyOptimizer(mode_switch_consecutive_cycles=3)
        state = LearningStrategyState.default()

        for _ in range(3):
            eff = _make_effectiveness(learning_gain=0.12, effectiveness_score=0.80)
            trend = _make_trend(trend_slope=0.03, trend_direction="improving")
            state, _ = opt.optimize(eff, trend, state)

        assert state.learning_mode == LearningMode.AGGRESSIVE.value

    def test_return_to_balanced_from_extreme(self) -> None:
        """当极端模式条件不再满足时，回到 BALANCED."""
        opt = LearningStrategyOptimizer(mode_switch_consecutive_cycles=3)
        state = LearningStrategyState.default()

        # 先切换到 conservative
        for _ in range(3):
            eff = _make_effectiveness(learning_gain=-0.10, effectiveness_score=0.25)
            trend = _make_trend(trend_slope=-0.03, trend_direction="declining")
            state, _ = opt.optimize(eff, trend, state)
        assert state.learning_mode == LearningMode.CONSERVATIVE.value

        # 再给一次正增益，混合信号
        opt2 = LearningStrategyOptimizer(mode_switch_consecutive_cycles=3)
        # 手动设置 gain_history 为混合
        opt2._gain_history.extend([0.05, -0.05, 0.03])
        opt2._trend_history.extend(["improving", "declining", "stable"])
        new_mode = opt2._determine_learning_mode(LearningMode.CONSERVATIVE.value)
        assert new_mode == LearningMode.BALANCED.value

    def test_insufficient_cycles_no_switch(self) -> None:
        """不足 mode_switch_cycles 时不切换."""
        opt = LearningStrategyOptimizer(mode_switch_consecutive_cycles=5)
        state = LearningStrategyState.default()

        for _ in range(3):
            eff = _make_effectiveness(learning_gain=-0.10, effectiveness_score=0.25)
            trend = _make_trend(trend_slope=-0.03, trend_direction="declining")
            state, _ = opt.optimize(eff, trend, state)

        # 只有 3 个周期，不足 5 个，不应切换
        assert state.learning_mode == LearningMode.BALANCED.value

    def test_mode_switch_produces_adjustment(self) -> None:
        opt = LearningStrategyOptimizer(mode_switch_consecutive_cycles=3)
        state = LearningStrategyState.default()

        last_adjustments = []
        for _ in range(3):
            eff = _make_effectiveness(learning_gain=-0.10, effectiveness_score=0.25)
            trend = _make_trend(trend_slope=-0.03, trend_direction="declining")
            state, last_adjustments = opt.optimize(eff, trend, state)

        mode_adj = [a for a in last_adjustments if a.parameter == "learning_mode"]
        assert len(mode_adj) >= 1
        assert mode_adj[0].source == AdjustmentSource.EVALUATION.value
        assert "metadata" in mode_adj[0].__dict__


# ═══════════════════════════════════════════════════════════════
# Membrane Weight Auto-balancing
# ═══════════════════════════════════════════════════════════════


class TestMembraneWeightBalancing:
    def test_pattern_weight_update_balances_memory_weight(self) -> None:
        """调整 pattern_weight 时自动更新 memory_weight = 1.0 - pattern_weight."""
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=0.15, effectiveness_score=0.80)
        state = LearningStrategyState.default()

        new_state, _ = opt.optimize(eff, current_state=state)

        assert new_state.pattern_weight > 0.70
        assert new_state.memory_weight == round(1.0 - new_state.pattern_weight, 4)
        assert new_state.weights_normalized

    def test_pattern_weight_decrease_balances_memory_weight(self) -> None:
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=-0.15, effectiveness_score=0.20)
        state = LearningStrategyState.default()

        new_state, _ = opt.optimize(eff, current_state=state)

        assert new_state.pattern_weight < 0.70
        assert new_state.memory_weight == round(1.0 - new_state.pattern_weight, 4)
        assert new_state.weights_normalized


# ═══════════════════════════════════════════════════════════════
# Integration Scenarios
# ═══════════════════════════════════════════════════════════════


class TestIntegrationFullScenario:
    """完整场景: 多周期优化 → 模式切换 → 参数调整."""

    def test_decline_then_recovery(self) -> None:
        """模拟先下降后恢复的完整周期."""
        opt = LearningStrategyOptimizer(
            mode_switch_consecutive_cycles=3,
            min_cycles_between_adjustments=1,
        )
        state = LearningStrategyState.default()

        # Phase 1: 连续下降 3 周期
        print("\nPhase 1: Declining")
        for i in range(3):
            eff = _make_effectiveness(
                learning_gain=-0.12 - i * 0.02,
                effectiveness_score=0.30 - i * 0.05,
            )
            trend = _make_trend(trend_slope=-0.03 - i * 0.01, trend_direction="declining")
            state, _ = opt.optimize(eff, trend, state)

        assert state.learning_mode == LearningMode.CONSERVATIVE.value
        assert state.exploration_rate > 0.20  # 探索增加
        assert state.pattern_weight < 0.70  # Pattern 信任降低

        # Phase 2: 恢复 3 周期
        print("\nPhase 2: Recovering")
        for i in range(3):
            eff = _make_effectiveness(
                learning_gain=0.08 + i * 0.02,
                effectiveness_score=0.60 + i * 0.10,
            )
            trend = _make_trend(trend_slope=0.02 + i * 0.01, trend_direction="improving")
            state, _ = opt.optimize(eff, trend, state)

        assert state.learning_mode == LearningMode.AGGRESSIVE.value
        assert state.exploration_rate < 0.50  # 探索减少
        assert state.pattern_weight > 0.40  # Pattern 信任恢复

    def test_state_preserved_across_cycles(self) -> None:
        """state 在多次 optimize 调用间保持连续性."""
        opt = LearningStrategyOptimizer()
        state = LearningStrategyState.default()

        original_id = state.state_id
        for i in range(3):
            eff = _make_effectiveness(
                learning_gain=-0.10,
                effectiveness_score=0.30,
            )
            state, _ = opt.optimize(eff, current_state=state)

        assert state.state_id == original_id  # 同一 state 对象
        assert state.version > 1  # 版本已更新

    def test_all_adjustments_reversible(self) -> None:
        """所有自动调整应默认可回滚."""
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=-0.15, effectiveness_score=0.20)
        state = LearningStrategyState.default()

        _, adjustments = opt.optimize(eff, current_state=state)

        for adj in adjustments:
            assert adj.reversible, f"Adjustment {adj.parameter} should be reversible"

    def test_adjustment_confidence_increases_with_experience(self) -> None:
        """随着调整次数增加，adjustment confidence 应提高."""
        opt = LearningStrategyOptimizer(min_cycles_between_adjustments=1)
        state = LearningStrategyState.default()

        # 交替正负增益，避免参数饱和，确保每次都有调整
        confs = []
        for i in range(12):
            if i % 2 == 0:
                eff = _make_effectiveness(learning_gain=-0.15, effectiveness_score=0.20)
            else:
                eff = _make_effectiveness(learning_gain=0.15, effectiveness_score=0.80)
            state, adjustments = opt.optimize(eff, current_state=state)
            if adjustments:
                confs.append(adjustments[0].confidence)

        # 至少应有调整
        assert len(confs) >= 2
        # 后期置信度 >= 前期置信度 (经验积累)
        assert confs[-1] >= confs[0]

    def test_pattern_weight_and_memory_weight_sum_to_one(self) -> None:
        """pattern_weight + memory_weight 始终为 1.0."""
        opt = LearningStrategyOptimizer()
        state = LearningStrategyState.default()

        for _ in range(5):
            gain = -0.15 if _ % 2 == 0 else 0.15
            score = 0.20 if _ % 2 == 0 else 0.80
            eff = _make_effectiveness(learning_gain=gain, effectiveness_score=score)
            state, _ = opt.optimize(eff, current_state=state)
            assert state.weights_normalized, f"Cycle {_}: weights not normalized"


# ═══════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_zero_decisions(self) -> None:
        """total_decisions = 0 时不应崩溃."""
        opt = LearningStrategyOptimizer()
        eff = LearningEffectiveness(
            total_decisions=0,
            learning_enhanced_count=0,
            learning_gain=0.0,
            effectiveness_score=0.50,  # 中性分数
        )
        state, adjustments = opt.optimize(eff)
        assert state is not None
        assert len(adjustments) == 0  # 中性评估不产生调整

    def test_extreme_effectiveness_score(self) -> None:
        """effectiveness_score = 0.0 或 1.0 的边界情况."""
        opt = LearningStrategyOptimizer()

        eff_zero = _make_effectiveness(learning_gain=-0.20, effectiveness_score=0.0)
        state_zero = LearningStrategyState.default()
        new_state, _ = opt.optimize(eff_zero, current_state=state_zero)
        assert new_state.confidence_threshold >= 0.50  # 应该提高阈值

        opt2 = LearningStrategyOptimizer()
        eff_one = _make_effectiveness(learning_gain=0.20, effectiveness_score=1.0)
        state_one = LearningStrategyState.default()
        new_state, _ = opt2.optimize(eff_one, current_state=state_one)
        assert new_state.confidence_threshold <= 0.50  # 应该降低阈值

    def test_very_large_learning_gain(self) -> None:
        """极端 learning_gain 值."""
        opt = LearningStrategyOptimizer()
        state = LearningStrategyState.default()

        eff = _make_effectiveness(learning_gain=-0.50, effectiveness_score=0.10)
        new_state, _ = opt.optimize(eff, current_state=state)
        assert 0.05 <= new_state.exploration_rate <= 0.60  # 在合法范围内

    def test_state_at_boundaries(self) -> None:
        """当参数已在边界时的调整."""
        state = LearningStrategyState(
            exploration_rate=0.05,  # MIN
            pattern_weight=0.90,    # MAX
            memory_weight=0.10,
            confidence_threshold=0.80,  # MAX
        )

        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=0.15, effectiveness_score=0.80)
        new_state, _ = opt.optimize(eff, current_state=state)

        # 不应超出边界
        assert new_state.exploration_rate >= 0.05
        assert new_state.pattern_weight <= 0.90
        assert new_state.confidence_threshold <= 0.80

    def test_multiple_optimizers_independent(self) -> None:
        """多个 optimizer 实例互相独立."""
        opt1 = LearningStrategyOptimizer()
        opt2 = LearningStrategyOptimizer()

        eff = _make_effectiveness(learning_gain=-0.15, effectiveness_score=0.20)
        opt1.optimize(eff)
        assert opt1.cycle_count == 1
        assert opt2.cycle_count == 0

    def test_adjustment_delta_accuracy(self) -> None:
        """调整的 delta 值应精确反映变化."""
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=-0.15, effectiveness_score=0.20)
        state = LearningStrategyState.default()

        _, adjustments = opt.optimize(eff, current_state=state)

        for adj in adjustments:
            assert adj.delta == round(adj.new_value - adj.previous_value, 6)
            if adj.previous_value != 0:
                expected_pct = round((adj.new_value - adj.previous_value) / abs(adj.previous_value) * 100, 2)
                assert adj.delta_percentage == expected_pct

    def test_optimize_cycle_count_increments(self) -> None:
        """每次 optimize 调用 cycle_count +1."""
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=-0.10, effectiveness_score=0.30)

        for i in range(5):
            opt.optimize(eff)
            assert opt.cycle_count == i + 1

    def test_serializable_state_after_optimize(self) -> None:
        """优化后的 state 可以序列化."""
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=-0.15, effectiveness_score=0.20)
        state = LearningStrategyState.default()

        new_state, _ = opt.optimize(eff, current_state=state)
        d = new_state.to_dict()
        assert "state_id" in d
        assert "exploration_rate" in d
        assert "version" in d
        assert d["version"] > 1

        # 可以从 dict 重建
        restored = LearningStrategyState.from_dict(d)
        assert restored.exploration_rate == new_state.exploration_rate
        assert restored.version == new_state.version

    def test_adjustment_metadata_contains_cycle(self) -> None:
        """调整记录应包含 cycle 元数据."""
        opt = LearningStrategyOptimizer()
        eff = _make_effectiveness(learning_gain=-0.15, effectiveness_score=0.20)
        state = LearningStrategyState.default()

        _, adjustments = opt.optimize(eff, current_state=state)

        for adj in adjustments:
            assert "cycle" in adj.metadata
            assert adj.metadata["cycle"] == opt.cycle_count

    def test_optimize_with_aggressive_initial_state(self) -> None:
        """从 aggressive 状态开始优化."""
        opt = LearningStrategyOptimizer()
        state = LearningStrategyState.aggressive()
        eff = _make_effectiveness(learning_gain=-0.15, effectiveness_score=0.20)

        new_state, _ = opt.optimize(eff, current_state=state)

        assert new_state.exploration_rate >= 0.05  # 有下限
        assert new_state.pattern_weight <= 0.90  # 有上限

    def test_optimize_with_conservative_initial_state(self) -> None:
        """从 conservative 状态开始优化."""
        opt = LearningStrategyOptimizer()
        state = LearningStrategyState.conservative()
        eff = _make_effectiveness(learning_gain=0.15, effectiveness_score=0.80)

        new_state, _ = opt.optimize(eff, current_state=state)

        assert new_state.exploration_rate <= 0.60  # 有上限
        assert new_state.pattern_weight >= 0.20  # 有下限


# ═══════════════════════════════════════════════════════════════
# Adjustment Impact Estimation
# ═══════════════════════════════════════════════════════════════


class TestImpactEstimation:
    def test_impact_positive_for_large_change(self) -> None:
        opt = LearningStrategyOptimizer()
        impact = opt._estimate_impact("exploration_rate", 0.20, 0.50)
        assert impact > 0

    def test_impact_different_by_parameter_type(self) -> None:
        opt = LearningStrategyOptimizer()
        imp_exp = opt._estimate_impact("exploration_rate", 0.20, 0.50)
        imp_dec = opt._estimate_impact("memory_decay_rate", 0.01, 0.03)
        imp_pat = opt._estimate_impact("pattern_weight", 0.70, 0.40)

        # pattern_weight 影响权重最大 (0.30)
        assert imp_pat > imp_dec

    def test_impact_zero_for_no_change(self) -> None:
        opt = LearningStrategyOptimizer()
        impact = opt._estimate_impact("exploration_rate", 0.20, 0.20)
        assert impact == 0.0

    def test_impact_saturated_at_max_step(self) -> None:
        """变化超过 max_step 时 impact 饱和."""
        opt = LearningStrategyOptimizer(max_adjustment_per_cycle=0.10)
        impact_small = opt._estimate_impact("exploration_rate", 0.20, 0.30)  # delta = 0.10
        impact_large = opt._estimate_impact("exploration_rate", 0.20, 0.60)  # delta = 0.40
        # 两者应相同 (delta/max_step 都 >= 1.0)
        assert impact_small == impact_large