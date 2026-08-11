"""E13.7.6 Improvement Measure — 改进量化测量器.

Day 7.6.3:
  量化多周期学习改进趋势，
  生成学习有效性报告，
  回答: "系统是否在持续变聪明？"

核心功能:
  - measure(): 基于追踪器数据计算改进趋势
  - track_improvement(): 追踪多周期改进
  - generate_report(): 生成可读报告

设计原则:
  - 滑动窗口分析 (window_size 可配置)
  - 线性回归趋势检测
  - 支持多维度分组趋势
"""

from __future__ import annotations

import math
from typing import Any

from .decision_impact_tracker import DecisionImpactTracker
from .models import (
    DecisionQualitySnapshot,
    ImprovementTrend,
    LearningEffectiveness,
)


class ImprovementMeasure:
    """改进量化测量器 — 量化学习改进趋势.

    用法:
        measure = ImprovementMeasure(window_size=10)
        trend = measure.measure(tracker)

        if trend.is_improving:
            print(f"Trend: {trend.trend_direction} (slope={trend.trend_slope:.4f})")

        report = measure.generate_report(effectiveness)
    """

    def __init__(self, window_size: int = 10) -> None:
        """初始化测量器.

        Args:
            window_size: 滑动窗口大小
        """
        self._window_size = max(window_size, 2)
        self._measurement_count: int = 0

    @property
    def measurement_count(self) -> int:
        return self._measurement_count

    # ── Public API ───────────────────────────────────────────────

    def measure(
        self,
        tracker: DecisionImpactTracker,
    ) -> ImprovementTrend:
        """基于追踪器数据计算改进趋势.

        Args:
            tracker: 决策质量追踪器

        Returns:
            ImprovementTrend: 改进趋势
        """
        self._measurement_count += 1

        completed = tracker.get_completed_snapshots()
        if len(completed) < self._window_size:
            return ImprovementTrend(
                periods=len(completed),
                summary=f"insufficient_data: need {self._window_size}, have {len(completed)}",
                metadata={"reason": "insufficient_data"},
            )

        # 按时序分组
        windows = self._create_windows(completed)
        periods = len(windows)

        baseline_values: list[float] = []
        enhanced_values: list[float] = []
        learning_gains: list[float] = []

        for window in windows:
            enhanced = [s for s in window if s.learning_enhanced]
            baseline_only = [s for s in window if not s.learning_enhanced]

            b_sr = self._success_rate(baseline_only)
            e_sr = self._success_rate(enhanced)

            baseline_values.append(b_sr)
            enhanced_values.append(e_sr)
            learning_gains.append(e_sr - b_sr)

        # 趋势方向
        trend_direction, trend_slope = self._detect_trend(learning_gains)

        # 统计
        avg_gain = self._mean(learning_gains) if learning_gains else 0.0
        max_gain = max(learning_gains) if learning_gains else 0.0
        min_gain = min(learning_gains) if learning_gains else 0.0

        # 可靠性
        reliability = self._calc_reliability(learning_gains, periods)

        # 判断是否改善
        is_improving = trend_direction == "improving" and avg_gain > 0

        # 生成摘要
        summary = self._generate_summary(
            trend_direction=trend_direction,
            avg_gain=avg_gain,
            periods=periods,
            is_improving=is_improving,
        )

        return ImprovementTrend(
            periods=periods,
            baseline_values=[round(v, 4) for v in baseline_values],
            enhanced_values=[round(v, 4) for v in enhanced_values],
            learning_gains=[round(v, 4) for v in learning_gains],
            trend_direction=trend_direction,
            trend_slope=round(trend_slope, 4),
            avg_gain=round(avg_gain, 4),
            max_gain=round(max_gain, 4),
            min_gain=round(min_gain, 4),
            is_improving=is_improving,
            reliability=round(reliability, 4),
            summary=summary,
            metadata={
                "window_size": self._window_size,
                "total_completed": len(completed),
            },
        )

    def track_improvement(
        self,
        snapshots: list[DecisionQualitySnapshot],
    ) -> ImprovementTrend:
        """直接追踪快照列表的改进趋势.

        Args:
            snapshots: 决策质量快照列表

        Returns:
            ImprovementTrend: 改进趋势
        """
        self._measurement_count += 1

        completed = [s for s in snapshots if s.has_outcome]
        if len(completed) < self._window_size:
            return ImprovementTrend(
                periods=len(completed),
                summary=f"insufficient_data: need {self._window_size}, have {len(completed)}",
                metadata={"reason": "insufficient_data"},
            )

        windows = self._create_windows(completed)
        periods = len(windows)

        baseline_values: list[float] = []
        enhanced_values: list[float] = []
        learning_gains: list[float] = []

        for window in windows:
            enhanced = [s for s in window if s.learning_enhanced]
            baseline_only = [s for s in window if not s.learning_enhanced]

            b_sr = self._success_rate(baseline_only)
            e_sr = self._success_rate(enhanced)

            baseline_values.append(b_sr)
            enhanced_values.append(e_sr)
            learning_gains.append(e_sr - b_sr)

        trend_direction, trend_slope = self._detect_trend(learning_gains)
        avg_gain = self._mean(learning_gains) if learning_gains else 0.0
        max_gain = max(learning_gains) if learning_gains else 0.0
        min_gain = min(learning_gains) if learning_gains else 0.0
        reliability = self._calc_reliability(learning_gains, periods)
        is_improving = trend_direction == "improving" and avg_gain > 0

        return ImprovementTrend(
            periods=periods,
            baseline_values=[round(v, 4) for v in baseline_values],
            enhanced_values=[round(v, 4) for v in enhanced_values],
            learning_gains=[round(v, 4) for v in learning_gains],
            trend_direction=trend_direction,
            trend_slope=round(trend_slope, 4),
            avg_gain=round(avg_gain, 4),
            max_gain=round(max_gain, 4),
            min_gain=round(min_gain, 4),
            is_improving=is_improving,
            reliability=round(reliability, 4),
            summary=self._generate_summary(
                trend_direction=trend_direction,
                avg_gain=avg_gain,
                periods=periods,
                is_improving=is_improving,
            ),
            metadata={
                "window_size": self._window_size,
                "total_completed": len(completed),
            },
        )

    def generate_report(
        self,
        effectiveness: LearningEffectiveness,
    ) -> str:
        """生成可读的学习有效性报告.

        Args:
            effectiveness: 学习有效性评估结果

        Returns:
            格式化报告文本
        """
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("LEARNING EFFECTIVENESS REPORT")
        lines.append("=" * 60)
        lines.append(f"Evaluation ID: {effectiveness.evaluation_id}")
        lines.append(f"Total Decisions: {effectiveness.total_decisions}")
        lines.append(
            f"Learning Enhanced: {effectiveness.learning_enhanced_count} "
            f"({effectiveness.enhancement_rate*100:.1f}%)"
        )
        lines.append("")

        lines.append("─" * 40)
        lines.append("SUCCESS RATES")
        lines.append("─" * 40)
        lines.append(f"  Baseline:  {effectiveness.baseline_success_rate*100:.1f}%")
        lines.append(f"  Enhanced:  {effectiveness.enhanced_success_rate*100:.1f}%")
        lines.append(
            f"  Gain:      {effectiveness.learning_gain_percentage:+.1f}%"
        )
        lines.append("")

        lines.append("─" * 40)
        lines.append("SCORES & CONFIDENCE")
        lines.append("─" * 40)
        lines.append(f"  Baseline Score:      {effectiveness.baseline_avg_score:.4f}")
        lines.append(f"  Enhanced Score:      {effectiveness.enhanced_avg_score:.4f}")
        lines.append(
            f"  Baseline Confidence: {effectiveness.baseline_avg_confidence:.4f}"
        )
        lines.append(
            f"  Enhanced Confidence: {effectiveness.enhanced_avg_confidence:.4f}"
        )
        lines.append("")

        lines.append("─" * 40)
        lines.append("IMPACT METRICS")
        lines.append("─" * 40)
        for metric in effectiveness.impact_metrics:
            direction = "↑" if metric.is_improvement else "↓"
            lines.append(
                f"  {direction} {metric.metric_name}: "
                f"{metric.baseline_value:.4f} → {metric.enhanced_value:.4f} "
                f"({metric.relative_change*100:+.1f}%) "
                f"[confidence: {metric.confidence:.2f}]"
            )
        lines.append("")

        lines.append("─" * 40)
        lines.append("VERDICT")
        lines.append("─" * 40)
        lines.append(f"  Effective: {effectiveness.is_effective}")
        lines.append(f"  Score:     {effectiveness.effectiveness_score:.4f}")
        lines.append("")

        if effectiveness.recommendations:
            lines.append("─" * 40)
            lines.append("RECOMMENDATIONS")
            lines.append("─" * 40)
            for i, rec in enumerate(effectiveness.recommendations, 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    def generate_trend_report(self, trend: ImprovementTrend) -> str:
        """生成改进趋势报告.

        Args:
            trend: 改进趋势

        Returns:
            格式化报告文本
        """
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("IMPROVEMENT TREND REPORT")
        lines.append("=" * 60)
        lines.append(f"Trend ID: {trend.trend_id}")
        lines.append(f"Periods: {trend.periods}")
        lines.append(f"Direction: {trend.trend_direction}")
        lines.append(f"Slope: {trend.trend_slope:+.4f}")
        lines.append("")
        lines.append(f"Avg Gain: {trend.avg_gain:+.4f}")
        lines.append(f"Max Gain: {trend.max_gain:+.4f}")
        lines.append(f"Min Gain: {trend.min_gain:+.4f}")
        lines.append(f"Reliability: {trend.reliability:.2f}")
        lines.append(f"Improving: {trend.is_improving}")
        lines.append("")
        lines.append(f"Summary: {trend.summary}")
        lines.append("=" * 60)
        return "\n".join(lines)

    # ── Internal ─────────────────────────────────────────────────

    def _create_windows(
        self, snapshots: list[DecisionQualitySnapshot]
    ) -> list[list[DecisionQualitySnapshot]]:
        """创建滑动窗口."""
        if len(snapshots) <= self._window_size:
            return [snapshots]

        windows: list[list[DecisionQualitySnapshot]] = []
        step = max(1, len(snapshots) // self._window_size)
        for i in range(0, len(snapshots) - self._window_size + 1, step):
            windows.append(snapshots[i : i + self._window_size])
        return windows

    def _detect_trend(self, values: list[float]) -> tuple[str, float]:
        """检测趋势方向和斜率 (简单线性回归)."""
        if len(values) < 2:
            return "stable", 0.0

        n = len(values)
        x_mean = (n - 1) / 2.0
        y_mean = sum(values) / n

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            slope = 0.0
        else:
            slope = numerator / denominator

        if slope > 0.01:
            direction = "improving"
        elif slope < -0.01:
            direction = "declining"
        else:
            direction = "stable"

        return direction, slope

    def _calc_reliability(
        self, values: list[float], periods: int
    ) -> float:
        """计算趋势可靠性."""
        if len(values) < 2:
            return 0.0

        # 样本量因素
        sample_factor = min(periods / 10.0, 1.0)

        # 一致性因素 (增益符号一致的比例)
        if values:
            positive = sum(1 for v in values if v > 0)
            negative = sum(1 for v in values if v < 0)
            consistency = max(positive, negative) / len(values)
        else:
            consistency = 0.0

        # 方差因素 (低方差 = 更可靠)
        mean_val = self._mean(values)
        if len(values) > 1:
            variance = sum((v - mean_val) ** 2 for v in values) / len(values)
            std = math.sqrt(variance)
            stability = 1.0 / (1.0 + std)
        else:
            stability = 0.0

        return (sample_factor * 0.3) + (consistency * 0.4) + (stability * 0.3)

    def _generate_summary(
        self,
        trend_direction: str,
        avg_gain: float,
        periods: int,
        is_improving: bool,
    ) -> str:
        """生成趋势摘要."""
        if not is_improving:
            if trend_direction == "declining":
                return (
                    f"Learning effectiveness is declining over {periods} periods "
                    f"(avg gain: {avg_gain:+.4f}). Review enhancer logic."
                )
            return (
                f"Learning effectiveness is stable over {periods} periods "
                f"(avg gain: {avg_gain:+.4f}). Continue monitoring."
            )
        return (
            f"Learning effectiveness is improving over {periods} periods "
            f"(avg gain: {avg_gain:+.4f}). System is getting smarter."
        )

    @staticmethod
    def _success_rate(snapshots: list[DecisionQualitySnapshot]) -> float:
        """计算成功率."""
        if not snapshots:
            return 0.0
        completed = [s for s in snapshots if s.has_outcome]
        if not completed:
            return 0.0
        return sum(1 for s in completed if s.is_success) / len(completed)

    @staticmethod
    def _mean(values: list[float]) -> float:
        """计算平均值."""
        if not values:
            return 0.0
        return sum(values) / len(values)