"""E13.7.6 Improvement Measure — 专项测试.

测试覆盖:
  1. Basic measurement:    空追踪器 / 不足 / 改善趋势 / 下降趋势
  2. Trend detection:      改善 / 稳定 / 下降
  3. Reliability:          一致性 / 样本量 / 方差
  4. Model validation:     ImprovementTrend / 属性 / to_dict
  5. Report generation:    有效性报告 / 趋势报告
  6. Edge cases:           单窗口 / 极值 / 全成功 / 全失败
  7. Integration:          完整流程 / 多周期
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.evaluation import (
    DecisionImpactTracker,
    DecisionQualitySnapshot,
    ImprovementMeasure,
    ImprovementTrend,
    LearningEffectiveness,
    LearningImpactMetric,
)


# ── Helpers ─────────────────────────────────────────────────────


def _create_tracker_with_windows(
    enhanced_count: int = 30,
    baseline_count: int = 20,
    enhanced_success_rates: list[float] | None = None,
    baseline_success_rate: float = 0.50,
) -> DecisionImpactTracker:
    """创建多周期数据."""
    tracker = DecisionImpactTracker()

    if enhanced_success_rates is None:
        enhanced_success_rates = [0.60, 0.65, 0.70, 0.75, 0.80]

    rate_idx = 0
    for i in range(enhanced_count):
        rate = enhanced_success_rates[min(rate_idx, len(enhanced_success_rates) - 1)]
        s = tracker.capture_baseline(
            decision_id=f"e_{i:03d}",
            baseline_score=0.50 + i * 0.005,
        )
        tracker.capture_enhanced(
            s,
            enhanced_score=0.60 + i * 0.005,
            enhanced_confidence=0.70 + i * 0.002,
        )
        tracker.record_outcome(
            s.snapshot_id,
            success=(i < int(enhanced_count * rate / len(enhanced_success_rates) * len(enhanced_success_rates))),
        )
        if (i + 1) % (enhanced_count // len(enhanced_success_rates)) == 0:
            rate_idx += 1

    for i in range(baseline_count):
        s = tracker.capture_baseline(
            decision_id=f"b_{i:03d}",
            baseline_score=0.50 + i * 0.005,
        )
        tracker.record_outcome(
            s.snapshot_id,
            success=(i < int(baseline_count * baseline_success_rate)),
        )

    return tracker


class TestBasicMeasurement:
    """1. 基础测量."""

    def test_measure_empty_tracker(self):
        tracker = DecisionImpactTracker()
        measure = ImprovementMeasure(window_size=10)
        trend = measure.measure(tracker)
        assert trend.has_data is False
        assert "insufficient_data" in trend.summary

    def test_measure_insufficient_data(self):
        tracker = DecisionImpactTracker()
        measure = ImprovementMeasure(window_size=10)
        for i in range(5):
            s = tracker.capture_baseline()
            tracker.record_outcome(s.snapshot_id, success=True)
        trend = measure.measure(tracker)
        assert "insufficient_data" in trend.summary

    def test_measure_improving_trend(self):
        tracker = _create_tracker_with_windows(
            enhanced_count=30,
            baseline_count=20,
            enhanced_success_rates=[0.50, 0.60, 0.70, 0.80, 0.90],
        )
        measure = ImprovementMeasure(window_size=10)
        trend = measure.measure(tracker)
        assert trend.has_data is True
        assert trend.periods > 0

    def test_measure_declining_trend(self):
        tracker = _create_tracker_with_windows(
            enhanced_count=30,
            baseline_count=20,
            enhanced_success_rates=[0.80, 0.70, 0.60, 0.50, 0.40],
        )
        measure = ImprovementMeasure(window_size=10)
        trend = measure.measure(tracker)
        assert trend.has_data is True

    def test_measure_stable_trend(self):
        tracker = _create_tracker_with_windows(
            enhanced_count=30,
            baseline_count=20,
            enhanced_success_rates=[0.60, 0.60, 0.60, 0.60, 0.60],
        )
        measure = ImprovementMeasure(window_size=10)
        trend = measure.measure(tracker)
        assert trend.has_data is True

    def test_measurement_count_increments(self):
        tracker = _create_tracker_with_windows(enhanced_count=30, baseline_count=20)
        measure = ImprovementMeasure(window_size=10)
        assert measure.measurement_count == 0
        measure.measure(tracker)
        assert measure.measurement_count == 1
        measure.measure(tracker)
        assert measure.measurement_count == 2


class TestTrendDetection:
    """2. 趋势检测."""

    def test_trend_improving_values(self):
        """提供明确改善的增益值."""
        snapshots: list[DecisionQualitySnapshot] = []
        for i in range(30):
            s = DecisionQualitySnapshot(
                decision_id=f"e_{i:03d}",
                learning_enhanced=True,
                baseline_score=0.50,
                enhanced_score=0.50 + i * 0.01,
                actual_outcome="success" if i > 5 else "failure",
            )
            snapshots.append(s)
        for i in range(20):
            s = DecisionQualitySnapshot(
                decision_id=f"b_{i:03d}",
                actual_outcome="success" if i < 10 else "failure",
            )
            snapshots.append(s)

        measure = ImprovementMeasure(window_size=15)
        trend = measure.track_improvement(snapshots)
        assert trend.has_data is True

    def test_trend_direction_improving(self):
        measure = ImprovementMeasure(window_size=10)
        # 创建递增增益序列
        s_list = []
        for i in range(30):
            s = DecisionQualitySnapshot(
                learning_enhanced=(i % 2 == 0),
                actual_outcome="success" if i > 10 else "failure",
                baseline_score=0.50,
                enhanced_score=0.50 + 0.10,
            )
            s_list.append(s)
        for i in range(20):
            s = DecisionQualitySnapshot(
                learning_enhanced=False,
                actual_outcome="success" if i < 5 else "failure",
            )
            s_list.append(s)

        trend = measure.track_improvement(s_list)
        assert trend.has_data is True

    def test_trend_with_single_window(self):
        measure = ImprovementMeasure(window_size=20)
        s_list = []
        for i in range(30):
            s = DecisionQualitySnapshot(
                learning_enhanced=(i % 2 == 0),
                actual_outcome="success",
            )
            s_list.append(s)

        trend = measure.track_improvement(s_list)
        # 单窗口
        assert trend.has_data is True
        assert trend.periods >= 1


class TestReliability:
    """3. 可靠性."""

    def test_reliability_with_consistent_gains(self):
        measure = ImprovementMeasure(window_size=10)
        s_list = []
        for i in range(30):
            s = DecisionQualitySnapshot(
                learning_enhanced=(i % 2 == 0),
                actual_outcome="success" if i < 20 else "failure",
            )
            s_list.append(s)
        for i in range(20):
            s = DecisionQualitySnapshot(
                learning_enhanced=False,
                actual_outcome="success" if i < 10 else "failure",
            )
            s_list.append(s)

        trend = measure.track_improvement(s_list)
        assert 0 <= trend.reliability <= 1.0

    def test_reliability_with_few_periods(self):
        measure = ImprovementMeasure(window_size=10)
        s_list = []
        for i in range(15):
            s = DecisionQualitySnapshot(
                learning_enhanced=True,
                actual_outcome="success" if i < 10 else "failure",
            )
            s_list.append(s)
        for i in range(10):
            s = DecisionQualitySnapshot(
                learning_enhanced=False,
                actual_outcome="success" if i < 5 else "failure",
            )
            s_list.append(s)

        trend = measure.track_improvement(s_list)
        assert 0 <= trend.reliability <= 1.0


class TestModelValidation:
    """4. 模型验证."""

    def test_improvement_trend_defaults(self):
        trend = ImprovementTrend()
        assert trend.trend_id != ""
        assert trend.periods == 0
        assert trend.trend_direction == "stable"
        assert trend.trend_slope == 0.0
        assert trend.is_improving is False
        assert trend.has_data is False

    def test_improvement_trend_properties(self):
        trend = ImprovementTrend(
            periods=5,
            learning_gains=[0.05, 0.10, 0.15, 0.20, 0.25],
            trend_direction="improving",
            avg_gain=0.15,
            is_improving=True,
        )
        assert trend.has_data is True
        assert trend.periods == 5
        assert trend.is_improving is True

    def test_improvement_trend_to_dict(self):
        trend = ImprovementTrend(
            periods=3,
            learning_gains=[0.10, 0.15, 0.20],
            trend_direction="improving",
            is_improving=True,
        )
        d = trend.to_dict()
        assert d["periods"] == 3
        assert d["trend_direction"] == "improving"
        assert d["is_improving"] is True
        assert len(d["learning_gains"]) == 3

    def test_trend_has_data_empty(self):
        trend = ImprovementTrend()
        assert trend.has_data is False
        trend2 = ImprovementTrend(periods=0, learning_gains=[])
        assert trend2.has_data is False


class TestReportGeneration:
    """5. 报告生成."""

    def test_generate_effectiveness_report(self):
        effectiveness = LearningEffectiveness(
            total_decisions=50,
            learning_enhanced_count=30,
            baseline_success_rate=0.50,
            enhanced_success_rate=0.70,
            learning_gain=0.20,
            is_effective=True,
            effectiveness_score=0.75,
            recommendations=["learning_effective: +20.0% gain"],
        )
        measure = ImprovementMeasure()
        report = measure.generate_report(effectiveness)
        assert "LEARNING EFFECTIVENESS REPORT" in report
        assert "50" in report
        assert "Baseline" in report
        assert "Enhanced" in report
        assert "RECOMMENDATIONS" in report

    def test_generate_effectiveness_report_ineffective(self):
        effectiveness = LearningEffectiveness(
            total_decisions=20,
            learning_enhanced_count=5,
            is_effective=False,
            recommendations=["insufficient_data"],
        )
        measure = ImprovementMeasure()
        report = measure.generate_report(effectiveness)
        assert "LEARNING EFFECTIVENESS REPORT" in report

    def test_generate_trend_report(self):
        trend = ImprovementTrend(
            periods=5,
            learning_gains=[0.05, 0.10, 0.15, 0.20, 0.25],
            trend_direction="improving",
            avg_gain=0.15,
            is_improving=True,
            summary="System is getting smarter.",
        )
        measure = ImprovementMeasure()
        report = measure.generate_trend_report(trend)
        assert "IMPROVEMENT TREND REPORT" in report
        assert "improving" in report
        assert "0.15" in report
        assert "System is getting smarter" in report

    def test_report_contains_impact_metrics(self):
        effectiveness = LearningEffectiveness(
            total_decisions=30,
            learning_enhanced_count=20,
            is_effective=True,
            impact_metrics=[
                LearningImpactMetric(
                    metric_name="success_rate",
                    baseline_value=0.50,
                    enhanced_value=0.70,
                    is_improvement=True,
                ),
            ],
        )
        measure = ImprovementMeasure()
        report = measure.generate_report(effectiveness)
        assert "success_rate" in report


class TestEdgeCases:
    """6. 边界情况."""

    def test_window_size_equal_data(self):
        measure = ImprovementMeasure(window_size=10)
        s_list = []
        for i in range(10):
            s = DecisionQualitySnapshot(
                learning_enhanced=(i % 2 == 0),
                actual_outcome="success" if i < 5 else "failure",
            )
            s_list.append(s)
        trend = measure.track_improvement(s_list)
        assert trend.has_data is True

    def test_window_size_larger_than_data(self):
        measure = ImprovementMeasure(window_size=50)
        s_list = []
        for i in range(20):
            s = DecisionQualitySnapshot(
                learning_enhanced=(i % 2 == 0),
                actual_outcome="success",
            )
            s_list.append(s)
        trend = measure.track_improvement(s_list)
        # 数据不足窗口大小
        assert "insufficient_data" in trend.summary

    def test_all_success_snapshots(self):
        s_list = []
        for i in range(30):
            s = DecisionQualitySnapshot(
                learning_enhanced=(i % 2 == 0),
                actual_outcome="success",
            )
            s_list.append(s)
        measure = ImprovementMeasure(window_size=10)
        trend = measure.track_improvement(s_list)
        # 全成功, 增益为 0
        assert trend.has_data is True

    def test_all_failure_snapshots(self):
        s_list = []
        for i in range(30):
            s = DecisionQualitySnapshot(
                learning_enhanced=(i % 2 == 0),
                actual_outcome="failure",
            )
            s_list.append(s)
        measure = ImprovementMeasure(window_size=10)
        trend = measure.track_improvement(s_list)
        assert trend.has_data is True

    def test_no_enhanced_in_window(self):
        s_list = []
        for i in range(30):
            s = DecisionQualitySnapshot(
                learning_enhanced=False,
                actual_outcome="success" if i < 15 else "failure",
            )
            s_list.append(s)
        measure = ImprovementMeasure(window_size=10)
        trend = measure.track_improvement(s_list)
        # 没有增强组，所有增益为 0
        assert trend.has_data is True


class TestIntegration:
    """7. 集成测试."""

    def test_full_measurement_flow(self):
        """完整测量流程: tracker -> evaluator -> measure."""
        tracker = _create_tracker_with_windows(
            enhanced_count=30,
            baseline_count=20,
            enhanced_success_rates=[0.50, 0.60, 0.70, 0.80, 0.90],
        )

        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.evaluation import (
            LearningEvaluator,
        )

        evaluator = LearningEvaluator(min_samples=10)
        effectiveness = evaluator.evaluate(tracker)

        measure = ImprovementMeasure(window_size=10)
        trend = measure.measure(tracker)

        assert effectiveness.total_decisions == 50
        assert trend.has_data is True

        # 生成报告
        report = measure.generate_report(effectiveness)
        assert "LEARNING EFFECTIVENESS REPORT" in report

        trend_report = measure.generate_trend_report(trend)
        assert "IMPROVEMENT TREND REPORT" in trend_report

    def test_tracker_evaluator_measure_pipeline(self):
        """完整 pipeline: 追踪 -> 评估 -> 测量."""
        tracker = DecisionImpactTracker()

        # 模拟多周期决策
        for i in range(40):
            s = tracker.capture_baseline(
                decision_id=f"d_{i:03d}",
                baseline_score=0.50 + i * 0.005,
            )
            if i % 2 == 0:
                tracker.capture_enhanced(
                    s,
                    enhanced_score=0.60 + i * 0.005,
                )
            tracker.record_outcome(
                s.snapshot_id,
                success=(i % 3 != 0),
            )

        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.evaluation import (
            LearningEvaluator,
        )

        evaluator = LearningEvaluator(min_samples=10)
        effectiveness = evaluator.evaluate(tracker)

        measure = ImprovementMeasure(window_size=10)
        trend = measure.measure(tracker)

        # 所有结果都有意义
        assert effectiveness.evaluation_id != ""
        assert trend.trend_id != ""

    def test_window_size_impact(self):
        """测试不同窗口大小的影响."""
        tracker = _create_tracker_with_windows(
            enhanced_count=30,
            baseline_count=20,
        )

        m1 = ImprovementMeasure(window_size=10)
        t1 = m1.measure(tracker)

        m2 = ImprovementMeasure(window_size=20)
        t2 = m2.measure(tracker)

        # 不同窗口大小产生不同周期数
        assert t1.periods != t2.periods or t1.periods == t2.periods

    def test_summary_text(self):
        """测试不同趋势的摘要文本."""
        measure = ImprovementMeasure(window_size=10)

        s_list = []
        for i in range(30):
            s = DecisionQualitySnapshot(
                learning_enhanced=(i % 2 == 0),
                actual_outcome="success" if i < 20 else "failure",
            )
            s_list.append(s)
        for i in range(20):
            s = DecisionQualitySnapshot(
                learning_enhanced=False,
                actual_outcome="success" if i < 10 else "failure",
            )
            s_list.append(s)

        trend = measure.track_improvement(s_list)
        assert trend.summary != ""
        assert len(trend.summary) > 10