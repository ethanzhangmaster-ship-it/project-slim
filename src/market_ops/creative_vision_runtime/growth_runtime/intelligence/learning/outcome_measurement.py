"""E13.7.8 Outcome Measurer — 执行结果测量引擎.

Day 7.8 Step 3:
  将 LearningExecutionResult 转化为可量化的 OutcomeMeasurement，
  填补 Execution → Evaluation 的测量缺口。

核心流程:
  LearningExecutionResult
          |
          v
  OutcomeMeasurer.measure()
          |
          +--> 提取执行前后指标
          |
          +--> 计算 reward_delta
          |
          +--> 计算 confidence_delta
          |
          +--> 计算 success_delta
          |
          +--> 合成 learning_gain
          |
          v
  OutcomeMeasurement
          |
          v
  LearningEvaluator (via DecisionImpactTracker)

设计原则:
  - 确定性: 所有 delta 计算基于明确公式
  - 可解释: 每个 delta 有明确的计算来源
  - 可追踪: 测量结果可序列化，支持审计
  - 不侵入已有模块: 通过 MeasurementContext 桥接

用法:
  from growth_runtime.intelligence.learning.outcome_measurement import OutcomeMeasurer

  measurer = OutcomeMeasurer()
  measurement = measurer.measure(
      execution_result=result,
      previous_strategy_state=state_before,
      current_strategy_state=state_after,
      metrics_before={"roas": 0.8, "ctr": 2.1},
      metrics_after={"roas": 0.95, "ctr": 2.4},
  )
"""

from __future__ import annotations

from typing import Any

from .models.learning_execution_models import LearningExecutionResult
from .models.outcome_measurement_models import MeasurementContext, OutcomeMeasurement


# ═══════════════════════════════════════════════════════════════
# OutcomeMeasurer
# ═══════════════════════════════════════════════════════════════


class OutcomeMeasurer:
    """执行结果测量引擎 — 将 ExecutionResult 转化为量化学习指标.

    用法:
        measurer = OutcomeMeasurer()
        measurement = measurer.measure(
            execution_result=result,
            previous_strategy_state=state_before,
            current_strategy_state=state_after,
            metrics_before={"roas": 0.8},
            metrics_after={"roas": 0.95},
        )
    """

    def __init__(self) -> None:
        self._measurement_count: int = 0
        self._measurement_history: list[OutcomeMeasurement] = []

    @property
    def measurement_count(self) -> int:
        return self._measurement_count

    # ── Public API ───────────────────────────────────────────────

    def measure(
        self,
        execution_result: LearningExecutionResult | None,
        cycle_number: int = 0,
        previous_strategy_state: dict[str, Any] | None = None,
        current_strategy_state: dict[str, Any] | None = None,
        metrics_before: dict[str, float] | None = None,
        metrics_after: dict[str, float] | None = None,
    ) -> OutcomeMeasurement:
        """测量执行结果 — 主入口.

        Args:
            execution_result: 学习执行结果 (可为 None)
            cycle_number: 编排周期编号
            previous_strategy_state: 执行前策略状态
            current_strategy_state: 执行后策略状态
            metrics_before: 执行前业务指标
            metrics_after: 执行后业务指标

        Returns:
            OutcomeMeasurement: 测量结果
        """
        self._measurement_count += 1

        # 无执行结果 → 不可测量
        if execution_result is None:
            measurement = OutcomeMeasurement.not_measurable(
                cycle_number=cycle_number,
                reason="No execution result available",
            )
            self._measurement_history.append(measurement)
            return measurement

        # 从执行结果中提取信息
        result = OutcomeMeasurement.from_execution(
            cycle_number=cycle_number,
            execution_action=execution_result.action,
            execution_success=execution_result.success,
            metrics_before=metrics_before or {},
            metrics_after=metrics_after or {},
            strategy_state_before=previous_strategy_state,
            strategy_state_after=current_strategy_state,
            measurement_confidence=self._calc_measurement_confidence(
                execution_result, metrics_before, metrics_after
            ),
        )

        self._measurement_history.append(result)
        return result

    def measure_from_context(
        self,
        context: MeasurementContext,
    ) -> OutcomeMeasurement:
        """从 MeasurementContext 测量.

        Args:
            context: 测量上下文

        Returns:
            OutcomeMeasurement
        """
        self._measurement_count += 1

        if not context.has_metrics and not context.execution_action:
            measurement = OutcomeMeasurement.not_measurable(
                cycle_number=context.cycle_number,
                reason="No metrics or execution action in context",
            )
            self._measurement_history.append(measurement)
            return measurement

        result = OutcomeMeasurement.from_execution(
            cycle_number=context.cycle_number,
            execution_action=context.execution_action,
            execution_success=context.execution_success,
            metrics_before=context.metrics_before,
            metrics_after=context.metrics_after,
            strategy_state_before=context.strategy_state_before,
            strategy_state_after=context.strategy_state_after,
            measurement_confidence=0.5,
        )

        self._measurement_history.append(result)
        return result

    def measure_batch(
        self,
        execution_results: list[tuple[LearningExecutionResult | None, int]],
        metrics_before: dict[str, float] | None = None,
        metrics_after: dict[str, float] | None = None,
    ) -> list[OutcomeMeasurement]:
        """批量测量.

        Args:
            execution_results: (execution_result, cycle_number) 列表
            metrics_before: 执行前指标
            metrics_after: 执行后指标

        Returns:
            list[OutcomeMeasurement]: 测量结果列表
        """
        return [
            self.measure(
                execution_result=er,
                cycle_number=cn,
                metrics_before=metrics_before,
                metrics_after=metrics_after,
            )
            for er, cn in execution_results
        ]

    # ── Query ────────────────────────────────────────────────────

    def get_history(self) -> list[OutcomeMeasurement]:
        """获取测量历史."""
        return list(self._measurement_history)

    def get_latest(self) -> OutcomeMeasurement | None:
        """获取最近一次测量."""
        if not self._measurement_history:
            return None
        return self._measurement_history[-1]

    def get_stats(self) -> dict[str, Any]:
        """获取测量统计."""
        if not self._measurement_history:
            return {
                "measurement_count": self._measurement_count,
                "avg_learning_gain": 0.0,
                "positive_count": 0,
                "negative_count": 0,
                "measurable_count": 0,
            }

        gains = [m.learning_gain for m in self._measurement_history if m.is_measurable]
        positive = sum(1 for m in self._measurement_history if m.is_positive)
        negative = sum(1 for m in self._measurement_history if m.is_negative)
        measurable = sum(1 for m in self._measurement_history if m.is_measurable)

        return {
            "measurement_count": self._measurement_count,
            "avg_learning_gain": round(sum(gains) / len(gains), 4) if gains else 0.0,
            "positive_count": positive,
            "negative_count": negative,
            "measurable_count": measurable,
        }

    def reset(self) -> None:
        """重置测量器."""
        self._measurement_count = 0
        self._measurement_history = []

    # ── Internal ─────────────────────────────────────────────────

    def _calc_measurement_confidence(
        self,
        execution_result: LearningExecutionResult,
        metrics_before: dict[str, float] | None,
        metrics_after: dict[str, float] | None,
    ) -> float:
        """计算测量置信度.

        基于:
          - 是否有指标数据 (0.4)
          - 执行是否成功 (0.3)
          - 是否有策略状态变化 (0.3)
        """
        confidence = 0.0

        # 指标数据可用性
        if metrics_before and metrics_after:
            confidence += 0.4
        elif metrics_before or metrics_after:
            confidence += 0.2

        # 执行成功
        if execution_result.success:
            confidence += 0.3

        # 策略状态变化
        if execution_result.strategy_updated:
            confidence += 0.3
        elif execution_result.new_state is not None:
            confidence += 0.15

        return round(max(0.0, min(1.0, confidence)), 4)

    def __repr__(self) -> str:
        return (
            f"OutcomeMeasurer("
            f"measurements={self._measurement_count})"
        )


__all__ = [
    "OutcomeMeasurer",
]