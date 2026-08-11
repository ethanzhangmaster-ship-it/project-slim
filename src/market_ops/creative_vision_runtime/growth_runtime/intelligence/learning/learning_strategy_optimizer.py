"""E13.7.7.2 Learning Strategy Optimizer — 学习策略优化器.

Day 7.7.2:
  根据 Evaluation 结果自动调整 LearningStrategyState，
  使系统从 "学习但不调整" 升级为 "学习并根据效果调整学习策略"。

核心流程:
  Evaluation Results (LearningEffectiveness + ImprovementTrend)
              |
              v
  LearningStrategyOptimizer.optimize()
              |
              +--> _map_gain_to_exploration()     → 调整 exploration_rate
              |
              +--> _map_trend_to_decay()          → 调整 memory_decay_rate
              |
              +--> _map_effectiveness_to_weight() → 调整 pattern_weight
              |
              +--> _determine_learning_mode()     → 切换学习模式
              |
              +--> _apply_cooldown()              → 冷却检查
              |
              +--> _apply_hysteresis()            → 防震荡
              |
              v
  (LearningStrategyState, list[LearningAdjustment])

设计原则:
  - 纯函数式映射，不修改 Evaluation / Memory / Decision
  - 冷却机制: 两次调整之间至少间隔 N 个周期
  - 防震荡: 检测参数来回调整，拒绝反向调整
  - 最大步长: 单次调整不超过 max_adjustment_per_cycle
  - 所有调整记录为 LearningAdjustment，可追溯可审计

用法:
  from growth_runtime.intelligence.learning.learning_strategy_optimizer import (
      LearningStrategyOptimizer,
  )

  optimizer = LearningStrategyOptimizer()
  new_state, adjustments = optimizer.optimize(
      effectiveness=eval_result,
      trend=trend_result,
      current_state=state,
  )
"""

from __future__ import annotations

from collections import deque
from typing import Any

from .evaluation.models import (
    ImprovementTrend,
    LearningEffectiveness,
)
from .models.learning_strategy_models import (
    AdjustmentSource,
    LearningAdjustment,
    LearningMode,
    LearningStrategyState,
)


# ═══════════════════════════════════════════════════════════════
# LearningStrategyOptimizer
# ═══════════════════════════════════════════════════════════════


class LearningStrategyOptimizer:
    """学习策略优化器 — 根据评估结果自动调整学习策略.

    用法:
        optimizer = LearningStrategyOptimizer()
        new_state, adjustments = optimizer.optimize(
            effectiveness=effectiveness,
            trend=trend,
            current_state=state,
        )
    """

    # ── 默认参数 ──────────────────────────────────────────────

    # 冷却: 至少间隔 N 个周期才能再次调整同一参数
    DEFAULT_MIN_CYCLES_BETWEEN_ADJUSTMENTS = 3

    # 单次调整最大变化量 (防止剧烈震荡)
    DEFAULT_MAX_ADJUSTMENT_PER_CYCLE = 0.15

    # 调整阈值: 变化量小于此值不触发调整 (避免微调)
    DEFAULT_ADJUSTMENT_THRESHOLD = 0.03

    # 防震荡窗口: 在此窗口内检测参数是否来回调整
    DEFAULT_HYSTERESIS_WINDOW = 3

    # 模式切换: 需要连续 N 个周期的趋势确认
    DEFAULT_MODE_SWITCH_CONSECUTIVE_CYCLES = 3

    # ── 映射阈值 ──────────────────────────────────────────────

    # exploration_rate 范围
    EXPLORATION_MIN = 0.05
    EXPLORATION_MAX = 0.60

    # memory_decay_rate 范围
    DECAY_MIN = 0.001
    DECAY_MAX = 0.10

    # pattern_weight 范围
    PATTERN_WEIGHT_MIN = 0.20
    PATTERN_WEIGHT_MAX = 0.90

    def __init__(
        self,
        min_cycles_between_adjustments: int = DEFAULT_MIN_CYCLES_BETWEEN_ADJUSTMENTS,
        max_adjustment_per_cycle: float = DEFAULT_MAX_ADJUSTMENT_PER_CYCLE,
        adjustment_threshold: float = DEFAULT_ADJUSTMENT_THRESHOLD,
        hysteresis_window: int = DEFAULT_HYSTERESIS_WINDOW,
        mode_switch_consecutive_cycles: int = DEFAULT_MODE_SWITCH_CONSECUTIVE_CYCLES,
    ) -> None:
        """初始化优化器.

        Args:
            min_cycles_between_adjustments: 同参数最小调整间隔
            max_adjustment_per_cycle: 单次调整最大变化量
            adjustment_threshold: 最小调整阈值
            hysteresis_window: 防震荡窗口大小
            mode_switch_consecutive_cycles: 模式切换所需连续周期数
        """
        self._min_cycles = min_cycles_between_adjustments
        self._max_step = max_adjustment_per_cycle
        self._threshold = adjustment_threshold
        self._hysteresis_window = hysteresis_window
        self._mode_switch_cycles = mode_switch_consecutive_cycles

        # 内部状态
        self._cycle_count: int = 0
        self._last_adjustment_cycle: dict[str, int] = {}  # parameter → cycle
        self._adjustment_history: deque[LearningAdjustment] = deque(maxlen=hysteresis_window * 3)
        self._gain_history: deque[float] = deque(maxlen=mode_switch_consecutive_cycles)
        self._trend_history: deque[str] = deque(maxlen=mode_switch_consecutive_cycles)

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def total_adjustments(self) -> int:
        return len(self._adjustment_history)

    # ── Public API ───────────────────────────────────────────────

    def optimize(
        self,
        effectiveness: LearningEffectiveness,
        trend: ImprovementTrend | None = None,
        current_state: LearningStrategyState | None = None,
    ) -> tuple[LearningStrategyState, list[LearningAdjustment]]:
        """执行一次策略优化.

        Args:
            effectiveness: 学习有效性评估结果
            trend: 改进趋势 (可选)
            current_state: 当前策略状态 (None 则使用默认)

        Returns:
            (new_state, adjustments): 新状态和调整记录列表
        """
        self._cycle_count += 1
        state = current_state or LearningStrategyState.default()
        adjustments: list[LearningAdjustment] = []

        # 记录历史 (用于模式切换判断)
        self._gain_history.append(effectiveness.learning_gain)
        if trend is not None:
            self._trend_history.append(trend.trend_direction)

        # ── 1. 调整 exploration_rate ──
        target_exp = self._map_gain_to_exploration(
            effectiveness.learning_gain,
            state.exploration_rate,
        )
        adj = self._try_adjust(
            state, "exploration_rate", state.exploration_rate, target_exp,
            reason=f"learning_gain={effectiveness.learning_gain:+.4f}",
            source=AdjustmentSource.EVALUATION,
        )
        if adj:
            adjustments.append(adj)

        # ── 2. 调整 memory_decay_rate (基于趋势) ──
        if trend is not None and trend.has_data:
            target_decay = self._map_trend_to_decay(
                trend.trend_slope,
                state.memory_decay_rate,
            )
            adj = self._try_adjust(
                state, "memory_decay_rate", state.memory_decay_rate, target_decay,
                reason=f"trend_slope={trend.trend_slope:+.4f}, direction={trend.trend_direction}",
                source=AdjustmentSource.TREND,
            )
            if adj:
                adjustments.append(adj)

        # ── 3. 调整 pattern_weight (基于 effectiveness_score) ──
        target_pw = self._map_effectiveness_to_pattern_weight(
            effectiveness.effectiveness_score,
            state.pattern_weight,
        )
        adj = self._try_adjust(
            state, "pattern_weight", state.pattern_weight, target_pw,
            reason=f"effectiveness_score={effectiveness.effectiveness_score:.4f}",
            source=AdjustmentSource.EVALUATION,
        )
        if adj:
            adjustments.append(adj)

        # ── 4. 调整 confidence_threshold ──
        target_ct = self._map_effectiveness_to_confidence_threshold(
            effectiveness.effectiveness_score,
            state.confidence_threshold,
        )
        adj = self._try_adjust(
            state, "confidence_threshold", state.confidence_threshold, target_ct,
            reason=f"effectiveness_score={effectiveness.effectiveness_score:.4f}",
            source=AdjustmentSource.EVALUATION,
        )
        if adj:
            adjustments.append(adj)

        # ── 5. 判断学习模式切换 ──
        new_mode = self._determine_learning_mode(state.learning_mode)
        if new_mode != state.learning_mode:
            adj = LearningAdjustment(
                state_id=state.state_id,
                reason=f"mode switch: {state.learning_mode} → {new_mode}",
                parameter="learning_mode",
                previous_value=0.0,
                new_value=0.0,
                impact_prediction=0.15,
                confidence=self._mode_switch_confidence(),
                source=AdjustmentSource.EVALUATION.value,
                metadata={
                    "gain_history": list(self._gain_history),
                    "trend_history": list(self._trend_history),
                },
            )
            adjustments.append(adj)
            state.learning_mode = new_mode

        # ── 6. 更新状态 ──
        if adjustments:
            state.bump_version()

        # 记录调整历史
        for adj in adjustments:
            self._adjustment_history.append(adj)

        return state, adjustments

    def reset(self) -> None:
        """重置优化器内部状态."""
        self._cycle_count = 0
        self._last_adjustment_cycle.clear()
        self._adjustment_history.clear()
        self._gain_history.clear()
        self._trend_history.clear()

    # ═══════════════════════════════════════════════════════════
    # Mapping Functions
    # ═══════════════════════════════════════════════════════════

    def _map_gain_to_exploration(
        self,
        learning_gain: float,
        current_rate: float,
    ) -> float:
        """learning_gain → exploration_rate 映射.

        逻辑:
          - gain < -0.10: 学习严重失效 → 大幅增加探索
          - gain < -0.05: 学习轻微失效 → 适度增加探索
          - gain > +0.10: 学习有效 → 减少探索，专注利用
          - gain > +0.05: 学习较有效 → 轻微减少探索
          - 其他: 保持
        """
        if learning_gain < -0.10:
            target = current_rate + 0.15
        elif learning_gain < -0.05:
            target = current_rate + 0.08
        elif learning_gain > 0.10:
            target = current_rate - 0.08
        elif learning_gain > 0.05:
            target = current_rate - 0.05
        else:
            target = current_rate

        return self._clamp(target, self.EXPLORATION_MIN, self.EXPLORATION_MAX)

    def _map_trend_to_decay(
        self,
        trend_slope: float,
        current_rate: float,
    ) -> float:
        """trend_slope → memory_decay_rate 映射.

        逻辑:
          - slope < -0.02: 趋势明显下降 → 加速遗忘 (衰减 x2)
          - slope < -0.01: 趋势轻微下降 → 适度加速遗忘
          - slope > +0.02: 趋势明显上升 → 减慢遗忘 (衰减 x0.5)
          - slope > +0.01: 趋势轻微上升 → 适度减慢遗忘
          - 其他: 保持
        """
        if trend_slope < -0.02:
            target = current_rate * 2.0
        elif trend_slope < -0.01:
            target = current_rate * 1.5
        elif trend_slope > 0.02:
            target = current_rate * 0.5
        elif trend_slope > 0.01:
            target = current_rate * 0.7
        else:
            target = current_rate

        return self._clamp(target, self.DECAY_MIN, self.DECAY_MAX)

    def _map_effectiveness_to_pattern_weight(
        self,
        effectiveness_score: float,
        current_weight: float,
    ) -> float:
        """effectiveness_score → pattern_weight 映射.

        逻辑:
          - score > 0.70: 学习高度有效 → 增加 pattern 信任
          - score > 0.50: 学习有效 → 轻微增加
          - score < 0.30: 学习无效 → 大幅降低 pattern 信任
          - score < 0.50: 学习效果不佳 → 适度降低
          - 其他: 保持
        """
        if effectiveness_score > 0.70:
            target = current_weight + 0.10
        elif effectiveness_score > 0.50:
            target = current_weight + 0.05
        elif effectiveness_score < 0.30:
            target = current_weight - 0.15
        elif effectiveness_score < 0.50:
            target = current_weight - 0.08
        else:
            target = current_weight

        return self._clamp(target, self.PATTERN_WEIGHT_MIN, self.PATTERN_WEIGHT_MAX)

    def _map_effectiveness_to_confidence_threshold(
        self,
        effectiveness_score: float,
        current_threshold: float,
    ) -> float:
        """effectiveness_score → confidence_threshold 映射.

        逻辑:
          - score > 0.70: 学习有效 → 可降低门槛 (更自信)
          - score < 0.30: 学习无效 → 提高门槛 (更谨慎)
        """
        if effectiveness_score > 0.70:
            target = current_threshold - 0.05
        elif effectiveness_score > 0.50:
            target = current_threshold - 0.03
        elif effectiveness_score < 0.30:
            target = current_threshold + 0.10
        elif effectiveness_score < 0.50:
            target = current_threshold + 0.05
        else:
            target = current_threshold

        return self._clamp(target, 0.30, 0.80)

    def _determine_learning_mode(self, current_mode: str) -> str:
        """根据历史趋势决定学习模式.

        条件:
          - CONSERVATIVE: 连续 N 个周期 gain < 0 且趋势为 declining
          - AGGRESSIVE:   连续 N 个周期 gain > 0 且趋势为 improving
          - 其他: 保持 BALANCED (或维持当前模式)
        """
        if len(self._gain_history) < self._mode_switch_cycles:
            return current_mode

        gains = list(self._gain_history)
        trends = list(self._trend_history) if self._trend_history else []

        all_negative = all(g < 0 for g in gains)
        all_positive = all(g > 0 for g in gains)

        # 切换到 CONSERVATIVE
        if all_negative:
            if trends and all(t == "declining" for t in trends):
                return LearningMode.CONSERVATIVE.value

        # 切换到 AGGRESSIVE
        if all_positive:
            if trends and all(t == "improving" for t in trends):
                return LearningMode.AGGRESSIVE.value

        # 如果当前是极端模式但条件不再满足 → 回到 BALANCED
        if current_mode in (LearningMode.AGGRESSIVE.value, LearningMode.CONSERVATIVE.value):
            if not all_negative and not all_positive:
                return LearningMode.BALANCED.value

        return current_mode

    def _mode_switch_confidence(self) -> float:
        """计算模式切换决策的置信度."""
        if len(self._gain_history) < self._mode_switch_cycles:
            return 0.0
        # 连续一致性越高，置信度越高
        consistency = len(self._gain_history) / self._mode_switch_cycles
        return min(0.95, consistency * 0.85)

    # ═══════════════════════════════════════════════════════════
    # Safety Mechanisms
    # ═══════════════════════════════════════════════════════════

    def _try_adjust(
        self,
        state: LearningStrategyState,
        parameter: str,
        current_value: float,
        target_value: float,
        reason: str,
        source: AdjustmentSource,
    ) -> LearningAdjustment | None:
        """尝试调整参数，经过冷却、阈值、步长、防震荡检查.

        Returns:
            LearningAdjustment 或 None (调整被阻止)
        """
        # 1. 阈值检查: 变化太小不调整
        if abs(target_value - current_value) < self._threshold:
            return None

        # 2. 冷却检查: 同参数调整太频繁
        if not self._check_cooldown(parameter):
            return None

        # 3. 步长限制: 单次调整不超过 max_step
        clamped_target = self._apply_step_limit(current_value, target_value)

        # 4. 防震荡: 检测是否在来回调整
        if self._detect_oscillation(parameter, clamped_target):
            return None

        # 5. 应用调整
        self._last_adjustment_cycle[parameter] = self._cycle_count
        self._apply_to_state(state, parameter, clamped_target)

        return LearningAdjustment(
            state_id=state.state_id,
            reason=reason,
            parameter=parameter,
            previous_value=round(current_value, 4),
            new_value=round(clamped_target, 4),
            impact_prediction=self._estimate_impact(parameter, current_value, clamped_target),
            confidence=self._adjustment_confidence(parameter),
            source=source.value,
            reversible=True,
            metadata={
                "cycle": self._cycle_count,
                "original_target": round(target_value, 4),
            },
        )

    def _check_cooldown(self, parameter: str) -> bool:
        """检查参数是否在冷却期."""
        last_cycle = self._last_adjustment_cycle.get(parameter, -self._min_cycles)
        return (self._cycle_count - last_cycle) >= self._min_cycles

    def _apply_step_limit(self, current: float, target: float) -> float:
        """限制单次调整步长."""
        delta = target - current
        if abs(delta) <= self._max_step:
            return target
        return current + (self._max_step if delta > 0 else -self._max_step)

    def _detect_oscillation(self, parameter: str, new_value: float) -> bool:
        """检测参数是否在震荡 (来回调整).

        检查最近 N 次调整中是否有方向相反的调整。
        """
        recent = [
            a for a in self._adjustment_history
            if a.parameter == parameter
        ]
        if len(recent) < 2:
            return False

        # 检查最近两次调整方向
        last_two = recent[-2:]
        last_dir = last_two[-1].is_increase
        prev_dir = last_two[-2].is_increase

        # 如果最近一次和之前方向相反，且新值又回到之前方向 → 震荡
        if last_dir != prev_dir:
            # 新调整方向与上上次相同 → 震荡
            new_dir = new_value > last_two[-1].new_value
            if new_dir == prev_dir:
                return True

        return False

    def _apply_to_state(
        self,
        state: LearningStrategyState,
        parameter: str,
        value: float,
    ) -> None:
        """将调整值应用到状态."""
        if parameter == "exploration_rate":
            state.exploration_rate = value
        elif parameter == "memory_decay_rate":
            state.memory_decay_rate = value
        elif parameter == "pattern_weight":
            state.pattern_weight = value
            state.memory_weight = round(1.0 - value, 4)
        elif parameter == "confidence_threshold":
            state.confidence_threshold = value

    def _estimate_impact(
        self,
        parameter: str,
        old_value: float,
        new_value: float,
    ) -> float:
        """估算调整的预期影响."""
        delta = abs(new_value - old_value)
        # 各参数影响权重不同
        weights = {
            "exploration_rate": 0.25,
            "memory_decay_rate": 0.15,
            "pattern_weight": 0.30,
            "confidence_threshold": 0.20,
        }
        base = weights.get(parameter, 0.1)
        # 变化越大，影响越大 (但边际递减)
        impact = base * min(1.0, delta / self._max_step)
        return round(impact, 4)

    def _adjustment_confidence(self, parameter: str) -> float:
        """计算调整决策的置信度.

        基于:
          - 历史调整历史 (稳定性)
          - 周期数 (经验)
        """
        recent_same_param = sum(
            1 for a in self._adjustment_history
            if a.parameter == parameter
        )
        # 经验因子: 调整次数越多，越有把握
        experience = min(1.0, recent_same_param / 10.0)
        # 周期因子: 周期越多，数据越可靠
        cycle_factor = min(1.0, self._cycle_count / 20.0)
        return round((experience * 0.4) + (cycle_factor * 0.3) + 0.30, 4)

    # ═══════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _clamp(value: float, min_val: float, max_val: float) -> float:
        return round(max(min_val, min(max_val, value)), 4)


__all__ = [
    "LearningStrategyOptimizer",
]