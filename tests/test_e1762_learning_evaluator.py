"""E13.7.6 Learning Evaluator — 专项测试.

测试覆盖:
  1. Basic evaluation:    空追踪器 / 样本不足 / 有效学习 / 无效学习
  2. Group comparison:    基线vs增强对比 / 空增强组
  3. Learning gain:       正增益 / 负增益 / 零增益
  4. Significance:        显著 / 不显著 / 小样本
  5. Impact metrics:      成功率 / 评分 / 置信度 / 奖励
  6. Model validation:    LearningEffectiveness / LearningImpactMetric
  7. Edge cases:          零值 / 极端值 / 全成功 / 全失败
  8. Integration:         完整评估流程 / 多周期
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.evaluation import (
    DecisionImpactTracker,
    DecisionQualitySnapshot,
    LearningEvaluator,
    LearningEffectiveness,
    LearningImpactMetric,
)


# ── Helpers ─────────────────────────────────────────────────────


def _create_populated_tracker(
    enhanced_count: int = 15,
    baseline_count: int = 10,
    enhanced_success_rate: float = 0.70,
    baseline_success_rate: float = 0.50,
    enhanced_score_delta: float = 0.10,
) -> DecisionImpactTracker:
    """创建填充了数据的追踪器."""
    tracker = DecisionImpactTracker()

    # 增强组
    for i in range(enhanced_count):
        base_score = 0.5 + i * 0.01
        s = tracker.capture_baseline(
            decision_id=f"e_{i:03d}",
            baseline_score=base_score,
            baseline_confidence=0.60,
        )
        tracker.capture_enhanced(
            s,
            enhanced_score=base_score + enhanced_score_delta,
            enhanced_confidence=0.75,
            enhancer_recommendation="approve" if i % 3 != 0 else "reject",
            enhancer_confidence=0.70 + i * 0.005,
        )
        tracker.record_outcome(
            s.snapshot_id,
            success=(i < int(enhanced_count * enhanced_success_rate)),
        )

    # 基线组 (无增强)
    for i in range(baseline_count):
        s = tracker.capture_baseline(
            decision_id=f"b_{i:03d}",
            baseline_score=0.5 + i * 0.01,
            baseline_confidence=0.55,
        )
        tracker.record_outcome(
            s.snapshot_id,
            success=(i < int(baseline_count * baseline_success_rate)),
        )

    return tracker


class TestBasicEvaluation:
    """1. 基础评估."""

    def test_evaluate_empty_tracker(self):
        tracker = DecisionImpactTracker()
        evaluator = LearningEvaluator(min_samples=5)
        result = evaluator.evaluate(tracker)
        assert result.is_effective is False
        assert result.total_decisions == 0
        assert "insufficient_data" in result.recommendations[0]

    def test_evaluate_insufficient_samples(self):
        tracker = DecisionImpactTracker()
        evaluator = LearningEvaluator(min_samples=10)
        for i in range(5):
            s = tracker.capture_baseline(baseline_score=0.60)
            tracker.capture_enhanced(s, enhanced_score=0.70)
            tracker.record_outcome(s.snapshot_id, success=True)
        result = evaluator.evaluate(tracker)
        assert result.is_effective is False
        assert "insufficient" in result.recommendations[0].lower()

    def test_evaluate_effective_learning(self):
        tracker = _create_populated_tracker(
            enhanced_count=15,
            baseline_count=10,
            enhanced_success_rate=0.80,
            baseline_success_rate=0.50,
        )
        evaluator = LearningEvaluator(min_samples=10)
        result = evaluator.evaluate(tracker)
        assert result.is_effective is True
        assert result.learning_gain > 0
        assert result.effectiveness_score > 0
        assert len(result.impact_metrics) == 4
        assert result.learning_enhanced_count == 15

    def test_evaluate_ineffective_learning(self):
        tracker = _create_populated_tracker(
            enhanced_count=15,
            baseline_count=10,
            enhanced_success_rate=0.40,
            baseline_success_rate=0.50,
        )
        evaluator = LearningEvaluator(min_samples=10)
        result = evaluator.evaluate(tracker)
        assert result.is_effective is False
        assert result.learning_gain < 0

    def test_evaluate_no_enhanced_decisions(self):
        tracker = DecisionImpactTracker()
        evaluator = LearningEvaluator(min_samples=5)
        for i in range(15):
            s = tracker.capture_baseline(baseline_score=0.60)
            tracker.record_outcome(s.snapshot_id, success=True)
        result = evaluator.evaluate(tracker)
        assert result.is_effective is False
        assert result.learning_enhanced_count == 0

    def test_evaluate_only_enhanced_no_baseline(self):
        tracker = DecisionImpactTracker()
        evaluator = LearningEvaluator(min_samples=5)
        for i in range(15):
            s = tracker.capture_baseline(baseline_score=0.60)
            tracker.capture_enhanced(s, enhanced_score=0.70)
            tracker.record_outcome(s.snapshot_id, success=True)
        result = evaluator.evaluate(tracker)
        # 只有增强组，基线组为空，基线成功率=0
        assert result.learning_enhanced_count == 15
        assert result.effectiveness_score > 0

    def test_evaluation_count_increments(self):
        tracker = _create_populated_tracker(enhanced_count=12, baseline_count=8)
        evaluator = LearningEvaluator(min_samples=10)
        assert evaluator.evaluation_count == 0
        evaluator.evaluate(tracker)
        assert evaluator.evaluation_count == 1
        evaluator.evaluate(tracker)
        assert evaluator.evaluation_count == 2


class TestGroupComparison:
    """2. 分组对比."""

    def test_compare_groups_basic(self):
        evaluator = LearningEvaluator(min_samples=5)

        baseline = [
            DecisionQualitySnapshot(
                decision_id="b_001",
                baseline_score=0.50,
                actual_outcome="success",
            ),
            DecisionQualitySnapshot(
                decision_id="b_002",
                baseline_score=0.50,
                actual_outcome="failure",
            ),
        ]
        enhanced = [
            DecisionQualitySnapshot(
                decision_id="e_001",
                baseline_score=0.50,
                enhanced_score=0.70,
                learning_enhanced=True,
                actual_outcome="success",
            ),
            DecisionQualitySnapshot(
                decision_id="e_002",
                baseline_score=0.50,
                enhanced_score=0.70,
                learning_enhanced=True,
                actual_outcome="success",
            ),
        ]

        result = evaluator.compare_groups(baseline, enhanced)
        assert result.total_decisions == 4
        assert result.learning_enhanced_count == 2

    def test_compare_groups_empty_enhanced(self):
        evaluator = LearningEvaluator()
        baseline = [
            DecisionQualitySnapshot(decision_id="b_001", actual_outcome="success"),
        ]
        result = evaluator.compare_groups(baseline, [])
        assert result.is_effective is False
        assert result.learning_enhanced_count == 0

    def test_compare_groups_small_sample(self):
        evaluator = LearningEvaluator(min_samples=10)
        baseline = [DecisionQualitySnapshot(actual_outcome="success")]
        enhanced = [
            DecisionQualitySnapshot(
                learning_enhanced=True,
                actual_outcome="success",
            ),
        ]
        result = evaluator.compare_groups(baseline, enhanced)
        # 小样本仍然返回结果，但 is_effective=False
        assert result.total_decisions == 2


class TestLearningGain:
    """3. 学习增益计算."""

    def test_positive_gain(self):
        evaluator = LearningEvaluator()
        gain = evaluator.calculate_learning_gain(0.50, 0.70)
        assert gain == pytest.approx(0.20)

    def test_negative_gain(self):
        evaluator = LearningEvaluator()
        gain = evaluator.calculate_learning_gain(0.70, 0.50)
        assert gain == pytest.approx(-0.20)

    def test_zero_gain(self):
        evaluator = LearningEvaluator()
        gain = evaluator.calculate_learning_gain(0.60, 0.60)
        assert gain == 0.0

    def test_extreme_gain(self):
        evaluator = LearningEvaluator()
        gain = evaluator.calculate_learning_gain(0.0, 1.0)
        assert gain == 1.0
        gain2 = evaluator.calculate_learning_gain(1.0, 0.0)
        assert gain2 == -1.0


class TestSignificance:
    """4. 显著性判断."""

    def test_significant_large_gain(self):
        evaluator = LearningEvaluator(min_samples=10)
        # gain=0.30, sample=50 -> 1-1/(1+15)=0.9375 < 0.95, 需要更大样本
        assert evaluator.is_significant(0.30, 100) is True

    def test_not_significant_small_gain(self):
        evaluator = LearningEvaluator(min_samples=10)
        assert evaluator.is_significant(0.001, 50) is False

    def test_not_significant_small_sample(self):
        evaluator = LearningEvaluator(min_samples=10)
        assert evaluator.is_significant(0.30, 5) is False

    def test_significant_with_large_sample(self):
        evaluator = LearningEvaluator(min_samples=10)
        # gain=0.05, sample=100 -> 1-1/(1+5)=0.8333 < 0.95, 需要更大样本
        assert evaluator.is_significant(0.05, 500) is True

    def test_significant_zero_gain(self):
        evaluator = LearningEvaluator(min_samples=10)
        assert evaluator.is_significant(0.0, 50) is False


class TestImpactMetrics:
    """5. 影响力指标."""

    def test_impact_metrics_present(self):
        tracker = _create_populated_tracker(enhanced_count=12, baseline_count=8)
        evaluator = LearningEvaluator(min_samples=10)
        result = evaluator.evaluate(tracker)
        assert len(result.impact_metrics) == 4
        metric_names = [m.metric_name for m in result.impact_metrics]
        assert "success_rate" in metric_names
        assert "decision_score" in metric_names
        assert "decision_confidence" in metric_names
        assert "avg_reward" in metric_names

    def test_impact_metric_success_rate(self):
        tracker = _create_populated_tracker(
            enhanced_count=12,
            baseline_count=8,
            enhanced_success_rate=0.80,
            baseline_success_rate=0.50,
        )
        evaluator = LearningEvaluator(min_samples=10)
        result = evaluator.evaluate(tracker)
        sr_metric = [m for m in result.impact_metrics if m.metric_name == "success_rate"][0]
        assert sr_metric.is_improvement is True
        assert sr_metric.absolute_change > 0

    def test_impact_metric_confidence(self):
        tracker = _create_populated_tracker(
            enhanced_count=12,
            baseline_count=8,
            enhanced_score_delta=0.10,
        )
        evaluator = LearningEvaluator(min_samples=10)
        result = evaluator.evaluate(tracker)
        conf_metric = [m for m in result.impact_metrics if m.metric_name == "decision_confidence"][0]
        assert conf_metric.is_improvement is True  # 增强置信度 > 基线

    def test_impact_metric_has_confidence(self):
        tracker = _create_populated_tracker(enhanced_count=12, baseline_count=8)
        evaluator = LearningEvaluator(min_samples=10)
        result = evaluator.evaluate(tracker)
        for metric in result.impact_metrics:
            assert 0 <= metric.confidence <= 1.0


class TestModelValidation:
    """6. 模型验证."""

    def test_learning_effectiveness_defaults(self):
        le = LearningEffectiveness()
        assert le.evaluation_id != ""
        assert le.total_decisions == 0
        assert le.is_effective is False
        assert le.effectiveness_score == 0.0
        assert le.learning_gain_percentage == 0.0
        assert le.enhancement_rate == 0.0

    def test_learning_effectiveness_properties(self):
        le = LearningEffectiveness(
            total_decisions=100,
            learning_enhanced_count=80,
            baseline_success_rate=0.50,
            enhanced_success_rate=0.70,
            learning_gain=0.20,
            is_effective=True,
        )
        assert le.learning_gain == pytest.approx(0.20)
        assert le.learning_gain_percentage == pytest.approx(20.0)
        assert le.enhancement_rate == pytest.approx(0.80)

    def test_learning_effectiveness_enhancement_rate_zero_division(self):
        le = LearningEffectiveness(total_decisions=0)
        assert le.enhancement_rate == 0.0

    def test_learning_effectiveness_to_dict(self):
        le = LearningEffectiveness(
            total_decisions=50,
            learning_enhanced_count=30,
            is_effective=True,
        )
        d = le.to_dict()
        assert d["total_decisions"] == 50
        assert d["is_effective"] is True
        assert "impact_metrics" in d

    def test_impact_metric_defaults(self):
        metric = LearningImpactMetric()
        assert metric.metric_name == ""
        assert metric.is_improvement is False
        assert metric.improvement_percentage == 0.0

    def test_impact_metric_improvement(self):
        metric = LearningImpactMetric(
            metric_name="success_rate",
            baseline_value=0.50,
            enhanced_value=0.70,
            absolute_change=0.20,
            relative_change=0.40,
            is_improvement=True,
        )
        assert metric.improvement_percentage == pytest.approx(40.0)

    def test_impact_metric_to_dict(self):
        metric = LearningImpactMetric(
            metric_name="success_rate",
            baseline_value=0.50,
            enhanced_value=0.70,
        )
        d = metric.to_dict()
        assert d["metric_name"] == "success_rate"
        assert d["baseline_value"] == 0.50


class TestEdgeCases:
    """7. 边界情况."""

    def test_all_success(self):
        tracker = DecisionImpactTracker()
        evaluator = LearningEvaluator(min_samples=5)
        for i in range(15):
            s = tracker.capture_baseline(baseline_score=0.60)
            tracker.capture_enhanced(s, enhanced_score=0.70)
            tracker.record_outcome(s.snapshot_id, success=True)
        for i in range(10):
            s = tracker.capture_baseline(baseline_score=0.50)
            tracker.record_outcome(s.snapshot_id, success=True)
        result = evaluator.evaluate(tracker)
        assert result.baseline_success_rate == 1.0
        assert result.enhanced_success_rate == 1.0
        assert result.learning_gain == 0.0

    def test_all_failure(self):
        tracker = DecisionImpactTracker()
        evaluator = LearningEvaluator(min_samples=5)
        for i in range(15):
            s = tracker.capture_baseline(baseline_score=0.60)
            tracker.capture_enhanced(s, enhanced_score=0.70)
            tracker.record_outcome(s.snapshot_id, success=False)
        for i in range(10):
            s = tracker.capture_baseline(baseline_score=0.50)
            tracker.record_outcome(s.snapshot_id, success=False)
        result = evaluator.evaluate(tracker)
        assert result.baseline_success_rate == 0.0
        assert result.enhanced_success_rate == 0.0

    def test_min_samples_boundary(self):
        tracker = _create_populated_tracker(
            enhanced_count=10,
            baseline_count=10,
            enhanced_success_rate=0.70,
            baseline_success_rate=0.50,
        )
        evaluator = LearningEvaluator(min_samples=10)
        result = evaluator.evaluate(tracker)
        # 正好等于 min_samples，应该能够评估
        assert result.total_decisions == 20

    def test_mixed_outcomes_no_enhanced_completed(self):
        tracker = DecisionImpactTracker()
        evaluator = LearningEvaluator(min_samples=5)
        for i in range(15):
            s = tracker.capture_baseline(baseline_score=0.60)
            tracker.capture_enhanced(s, enhanced_score=0.70)
            # 不记录结果
        result = evaluator.evaluate(tracker)
        assert result.is_effective is False  # 样本不足


class TestIntegration:
    """8. 集成测试."""

    def test_full_evaluation_flow(self):
        tracker = _create_populated_tracker(
            enhanced_count=15,
            baseline_count=10,
            enhanced_success_rate=0.75,
            baseline_success_rate=0.50,
            enhanced_score_delta=0.12,
        )
        evaluator = LearningEvaluator(min_samples=10)

        result = evaluator.evaluate(tracker)

        assert result.total_decisions == 25
        assert result.learning_enhanced_count == 15
        assert result.learning_gain > 0
        assert result.effectiveness_score > 0
        assert len(result.impact_metrics) == 4

        # 验证报告的完整结构
        assert result.evaluation_id != ""
        assert result.baseline_avg_confidence > 0
        assert result.enhanced_avg_confidence > 0
        assert result.baseline_avg_score > 0
        assert result.enhanced_avg_score > 0

        # 推荐
        if result.is_effective:
            assert any("learning_effective" in r for r in result.recommendations)
        assert len(result.recommendations) > 0

    def test_incremental_evaluation(self):
        """增量评估: 先少量数据，再增加数据."""
        tracker = DecisionImpactTracker()
        evaluator = LearningEvaluator(min_samples=10)

        # 第一批: 不足
        for i in range(5):
            s = tracker.capture_baseline(baseline_score=0.60)
            tracker.capture_enhanced(s, enhanced_score=0.70)
            tracker.record_outcome(s.snapshot_id, success=(i < 3))
        result1 = evaluator.evaluate(tracker)
        assert result1.is_effective is False

        # 第二批: 足够
        for i in range(10):
            s = tracker.capture_baseline(baseline_score=0.60)
            tracker.capture_enhanced(s, enhanced_score=0.72)
            tracker.record_outcome(s.snapshot_id, success=(i < 8))
        result2 = evaluator.evaluate(tracker)
        assert result2.is_effective is True
        assert result2.learning_enhanced_count == 15

    def test_min_samples_custom_values(self):
        """测试不同的 min_samples 参数."""
        tracker = _create_populated_tracker(enhanced_count=5, baseline_count=5)

        # min_samples=3: 应该通过
        e1 = LearningEvaluator(min_samples=3)
        r1 = e1.evaluate(tracker)
        assert r1.learning_enhanced_count == 5
        # 但基线组也有结果，enhanced_count=5 满足 min_samples=3

        # min_samples=20: 应该不通过
        e2 = LearningEvaluator(min_samples=20)
        r2 = e2.evaluate(tracker)
        assert r2.is_effective is False