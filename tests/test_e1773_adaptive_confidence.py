"""E13.7.7.3 Adaptive Confidence Engine — 自适应置信度引擎测试.

Day 7.7.3:
  测试 AdaptiveConfidenceEngine 的四个维度因子计算和历史准确率追踪，
  确保静态 confidence 正确升级为自适应 confidence。

测试覆盖:
  - Models: ConfidenceRecord, AdaptiveConfidenceResult, ConfidenceDimension
  - Engine Init: 默认/自定义参数
  - Adjust: 中性/降级/升级场景
  - Dimension 1: Historical Accuracy (历史准确率)
  - Dimension 2: Learning Effectiveness (学习有效性)
  - Dimension 3: Context Similarity (上下文相似度)
  - Dimension 4: Freshness (数据时效性)
  - Record Outcome: 结果记录与准确率追踪
  - Integration: 完整预测→调整→反馈闭环
  - Edge Cases: 边界值、空输入
  - Custom Weights: 通过 LearningStrategyState 配置
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.adaptive_confidence_engine import (
    AdaptiveConfidenceEngine,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.evaluation.models import (
    LearningEffectiveness,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.adaptive_confidence_models import (
    AdaptiveConfidenceResult,
    ConfidenceDimension,
    ConfidenceRecord,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_strategy_models import (
    LearningStrategyState,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_effectiveness(effectiveness_score: float) -> LearningEffectiveness:
    return LearningEffectiveness(
        total_decisions=50,
        learning_enhanced_count=50,
        learning_gain=0.05,
        effectiveness_score=effectiveness_score,
        is_effective=effectiveness_score >= 0.50,
    )


def _make_timestamps(days_ago: list[float]) -> list[str]:
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    return [(now - timedelta(days=d)).isoformat() for d in days_ago]


# ═══════════════════════════════════════════════════════════════
# ConfidenceRecord
# ═══════════════════════════════════════════════════════════════


class TestConfidenceRecord:
    def test_default_creation(self) -> None:
        r = ConfidenceRecord()
        assert r.record_id != ""
        assert r.source == ""
        assert r.base_confidence == 0.0
        assert r.actual_outcome == "pending"
        assert not r.is_resolved

    def test_full_creation(self) -> None:
        r = ConfidenceRecord(
            source="enhancer",
            context_key="action:increase_budget",
            base_confidence=0.75,
            adjusted_confidence=0.60,
            dimensions={"historical_accuracy": 0.80, "freshness": 0.70},
            actual_outcome="success",
            is_accurate=True,
        )
        assert r.source == "enhancer"
        assert r.base_confidence == 0.75
        assert r.adjusted_confidence == 0.60
        assert r.is_resolved
        assert r.is_accurate

    def test_is_resolved(self) -> None:
        assert not ConfidenceRecord(actual_outcome="pending").is_resolved
        assert ConfidenceRecord(actual_outcome="success").is_resolved
        assert ConfidenceRecord(actual_outcome="failure").is_resolved

    def test_confidence_delta(self) -> None:
        r = ConfidenceRecord(base_confidence=0.80, adjusted_confidence=0.60)
        assert r.confidence_delta == -0.20

        r2 = ConfidenceRecord(base_confidence=0.50, adjusted_confidence=0.70)
        assert r2.confidence_delta == 0.20

    def test_to_dict(self) -> None:
        r = ConfidenceRecord(
            source="predictor",
            base_confidence=0.70,
            adjusted_confidence=0.65,
            dimensions={"historical_accuracy": 0.90},
            actual_outcome="success",
            is_accurate=True,
        )
        d = r.to_dict()
        assert d["source"] == "predictor"
        assert d["base_confidence"] == 0.70
        assert d["adjusted_confidence"] == 0.65
        assert d["is_accurate"] is True


# ═══════════════════════════════════════════════════════════════
# AdaptiveConfidenceResult
# ═══════════════════════════════════════════════════════════════


class TestAdaptiveConfidenceResult:
    def test_default_creation(self) -> None:
        r = AdaptiveConfidenceResult()
        assert r.result_id != ""
        assert r.base_confidence == 0.0
        assert r.adjusted_confidence == 0.0
        assert r.adjustment_factor == 1.0
        assert r.confidence_level == "insufficient"

    def test_is_adjusted(self) -> None:
        assert AdaptiveConfidenceResult(base_confidence=0.7, adjusted_confidence=0.6).is_adjusted
        assert not AdaptiveConfidenceResult(base_confidence=0.7, adjusted_confidence=0.7).is_adjusted

    def test_is_downgraded(self) -> None:
        assert AdaptiveConfidenceResult(base_confidence=0.7, adjusted_confidence=0.5).is_downgraded
        assert not AdaptiveConfidenceResult(base_confidence=0.7, adjusted_confidence=0.8).is_downgraded

    def test_is_upgraded(self) -> None:
        assert AdaptiveConfidenceResult(base_confidence=0.5, adjusted_confidence=0.7).is_upgraded
        assert not AdaptiveConfidenceResult(base_confidence=0.7, adjusted_confidence=0.5).is_upgraded

    def test_is_reliable(self) -> None:
        assert AdaptiveConfidenceResult(confidence_level="high").is_reliable
        assert AdaptiveConfidenceResult(confidence_level="medium").is_reliable
        assert not AdaptiveConfidenceResult(confidence_level="low").is_reliable

    def test_dominant_factor(self) -> None:
        r = AdaptiveConfidenceResult(
            dimensions={
                "historical_accuracy": 0.60,
                "learning_effectiveness": 1.0,
                "context_similarity": 1.0,
                "freshness": 1.0,
                "base_confidence": 0.80,
            },
        )
        factor, value = r.dominant_factor
        assert factor == "historical_accuracy"
        assert value == 0.60

    def test_dominant_factor_all_nominal(self) -> None:
        r = AdaptiveConfidenceResult(
            dimensions={
                "historical_accuracy": 1.0,
                "learning_effectiveness": 1.0,
                "base_confidence": 0.80,
            },
        )
        factor, value = r.dominant_factor
        assert factor == "base_confidence"

    def test_confidence_level_score(self) -> None:
        assert AdaptiveConfidenceResult(confidence_level="high").confidence_level_score == 0.85
        assert AdaptiveConfidenceResult(confidence_level="medium").confidence_level_score == 0.55
        assert AdaptiveConfidenceResult(confidence_level="low").confidence_level_score == 0.30
        assert AdaptiveConfidenceResult(confidence_level="insufficient").confidence_level_score == 0.10

    def test_to_dict(self) -> None:
        r = AdaptiveConfidenceResult(
            base_confidence=0.75,
            adjusted_confidence=0.60,
            adjustment_factor=0.80,
            dimensions={"historical_accuracy": 0.70, "freshness": 0.90},
            dimension_weights={"historical_accuracy": 0.30, "freshness": 0.25},
            adjustments=["Historical accuracy low"],
            confidence_level="medium",
            warnings=["Stale data"],
            metadata={"source": "enhancer"},
        )
        d = r.to_dict()
        assert d["base_confidence"] == 0.75
        assert d["adjusted_confidence"] == 0.60
        assert d["confidence_level"] == "medium"
        assert len(d["adjustments"]) >= 1
        assert len(d["warnings"]) >= 1


# ═══════════════════════════════════════════════════════════════
# Engine Initialization
# ═══════════════════════════════════════════════════════════════


class TestEngineInit:
    def test_default_creation(self) -> None:
        engine = AdaptiveConfidenceEngine()
        assert engine.history_count == 0
        assert engine.pending_count == 0
        assert engine.adjustment_count == 0

    def test_custom_params(self) -> None:
        engine = AdaptiveConfidenceEngine(
            max_history=50,
            min_samples_for_accuracy=10,
            freshness_days_recent=3,
            freshness_days_stale=14,
        )
        assert engine._max_history == 50
        assert engine._min_samples == 10
        assert engine._freshness_recent == 3
        assert engine._freshness_stale == 14

    def test_with_strategy_state(self) -> None:
        state = LearningStrategyState.default()
        engine = AdaptiveConfidenceEngine(strategy_state=state)
        assert engine._strategy_state is state

    def test_reset_clears_all(self) -> None:
        engine = AdaptiveConfidenceEngine()
        result = engine.adjust(base_confidence=0.80, source="test")
        engine.record_outcome(result.result_id, "success")
        assert engine.history_count == 1
        assert engine.adjustment_count == 1

        engine.reset()
        assert engine.history_count == 0
        assert engine.pending_count == 0
        assert engine.adjustment_count == 0


# ═══════════════════════════════════════════════════════════════
# Adjust: Basic Scenarios
# ═══════════════════════════════════════════════════════════════


class TestAdjustBasic:
    def test_neutral_adjust_no_history(self) -> None:
        """无历史数据时，所有维度为 1.0，不调整."""
        engine = AdaptiveConfidenceEngine()
        result = engine.adjust(base_confidence=0.80, source="enhancer")

        assert result.base_confidence == 0.80
        assert result.adjusted_confidence == 0.80
        assert not result.is_adjusted
        assert result.adjustment_factor == 1.0

    def test_adjust_returns_result_with_dimensions(self) -> None:
        engine = AdaptiveConfidenceEngine()
        result = engine.adjust(base_confidence=0.75, source="enhancer")

        assert ConfidenceDimension.HISTORICAL_ACCURACY.value in result.dimensions
        assert ConfidenceDimension.LEARNING_EFFECTIVENESS.value in result.dimensions
        assert ConfidenceDimension.CONTEXT_SIMILARITY.value in result.dimensions
        assert ConfidenceDimension.FRESHNESS.value in result.dimensions
        assert ConfidenceDimension.BASE_CONFIDENCE.value in result.dimensions

    def test_adjust_increments_count(self) -> None:
        engine = AdaptiveConfidenceEngine()
        for i in range(5):
            engine.adjust(base_confidence=0.7, source="test")
        assert engine.adjustment_count == 5

    def test_adjust_creates_pending_record(self) -> None:
        engine = AdaptiveConfidenceEngine()
        result = engine.adjust(base_confidence=0.80, source="enhancer")
        assert engine.pending_count == 1

    def test_adjust_confidence_clamped(self) -> None:
        """调整后置信度在 [0, 1] 范围内."""
        engine = AdaptiveConfidenceEngine()
        result = engine.adjust(base_confidence=1.0, source="test")
        assert 0.0 <= result.adjusted_confidence <= 1.0

        result = engine.adjust(base_confidence=0.0, source="test")
        assert 0.0 <= result.adjusted_confidence <= 1.0

    def test_adjust_levels(self) -> None:
        engine = AdaptiveConfidenceEngine()
        assert engine.adjust(base_confidence=0.80).confidence_level == "high"
        assert engine.adjust(base_confidence=0.60).confidence_level == "medium"
        assert engine.adjust(base_confidence=0.30).confidence_level == "low"
        assert engine.adjust(base_confidence=0.10).confidence_level == "insufficient"


# ═══════════════════════════════════════════════════════════════
# Dimension 1: Historical Accuracy
# ═══════════════════════════════════════════════════════════════


class TestHistoricalAccuracy:
    def test_no_history_returns_neutral(self) -> None:
        engine = AdaptiveConfidenceEngine()
        assert engine._compute_historical_accuracy("enhancer") == 1.0

    def test_insufficient_samples_returns_neutral(self) -> None:
        engine = AdaptiveConfidenceEngine(min_samples_for_accuracy=5)
        # 只有 3 条记录
        result = engine.adjust(base_confidence=0.80, source="test")
        engine.record_outcome(result.result_id, "success")
        engine.adjust(base_confidence=0.80, source="test")
        result = engine.adjust(base_confidence=0.80, source="test")
        engine.record_outcome(result.result_id, "success")
        engine.adjust(base_confidence=0.80, source="test")
        result = engine.adjust(base_confidence=0.80, source="test")
        engine.record_outcome(result.result_id, "success")

        assert engine._compute_historical_accuracy("test") == 1.0  # 不足 5 条

    def test_perfect_accuracy(self) -> None:
        engine = AdaptiveConfidenceEngine(min_samples_for_accuracy=3)
        # 3 条高置信度成功预测
        for _ in range(3):
            result = engine.adjust(base_confidence=0.80, source="test")
            engine.record_outcome(result.result_id, "success")

        assert engine._compute_historical_accuracy("test") == 1.0

    def test_poor_accuracy_downgrades_confidence(self) -> None:
        engine = AdaptiveConfidenceEngine(min_samples_for_accuracy=3)
        # 3 条高置信度失败预测
        for _ in range(3):
            result = engine.adjust(base_confidence=0.80, source="test")
            engine.record_outcome(result.result_id, "failure")

        ha = engine._compute_historical_accuracy("test")
        assert ha < 0.50  # 准确率低

        # 后续调整应该被降级
        result = engine.adjust(base_confidence=0.80, source="test")
        assert result.adjusted_confidence < 0.80

    def test_mixed_accuracy(self) -> None:
        engine = AdaptiveConfidenceEngine(min_samples_for_accuracy=3)
        for _ in range(3):
            result = engine.adjust(base_confidence=0.80, source="test")
            engine.record_outcome(result.result_id, "success")
        for _ in range(3):
            result = engine.adjust(base_confidence=0.80, source="test")
            engine.record_outcome(result.result_id, "failure")

        ha = engine._compute_historical_accuracy("test")
        assert 0.40 < ha < 0.60  # 约 50%

    def test_accuracy_per_source(self) -> None:
        """不同 source 的准确率独立计算."""
        engine = AdaptiveConfidenceEngine(min_samples_for_accuracy=3)

        # enhancer: 全部成功
        for _ in range(3):
            r = engine.adjust(base_confidence=0.80, source="enhancer")
            engine.record_outcome(r.result_id, "success")

        # predictor: 全部失败
        for _ in range(3):
            r = engine.adjust(base_confidence=0.80, source="predictor")
            engine.record_outcome(r.result_id, "failure")

        assert engine._compute_historical_accuracy("enhancer") == 1.0
        assert engine._compute_historical_accuracy("predictor") < 0.50

    def test_low_confidence_predictions_not_counted(self) -> None:
        """低置信度预测不计入 decisive accuracy."""
        engine = AdaptiveConfidenceEngine(min_samples_for_accuracy=3)
        # 低置信度预测成功 → 不计入
        for _ in range(5):
            result = engine.adjust(base_confidence=0.30, source="test")
            engine.record_outcome(result.result_id, "success")

        ha = engine._compute_historical_accuracy("test")
        assert ha == 1.0  # 无 decisive 样本 → 回退


# ═══════════════════════════════════════════════════════════════
# Dimension 2: Learning Effectiveness
# ═══════════════════════════════════════════════════════════════


class TestLearningEffectiveness:
    def test_no_effectiveness_returns_neutral(self) -> None:
        engine = AdaptiveConfidenceEngine()
        assert engine._compute_learning_effectiveness(None) == 1.0

    def test_high_effectiveness(self) -> None:
        engine = AdaptiveConfidenceEngine()
        eff = _make_effectiveness(0.80)
        assert engine._compute_learning_effectiveness(eff) == 1.0

    def test_medium_effectiveness(self) -> None:
        engine = AdaptiveConfidenceEngine()
        eff = _make_effectiveness(0.55)
        assert engine._compute_learning_effectiveness(eff) == 0.95

    def test_low_medium_effectiveness(self) -> None:
        engine = AdaptiveConfidenceEngine()
        eff = _make_effectiveness(0.35)
        assert engine._compute_learning_effectiveness(eff) == 0.85

    def test_very_low_effectiveness(self) -> None:
        engine = AdaptiveConfidenceEngine()
        eff = _make_effectiveness(0.15)
        assert engine._compute_learning_effectiveness(eff) == 0.70

    def test_effectiveness_downgrades_confidence(self) -> None:
        engine = AdaptiveConfidenceEngine()
        eff = _make_effectiveness(0.20)  # 很低
        result = engine.adjust(base_confidence=0.80, effectiveness=eff)
        assert result.adjusted_confidence < 0.80

    def test_effectiveness_preserves_confidence_when_high(self) -> None:
        engine = AdaptiveConfidenceEngine()
        eff = _make_effectiveness(0.85)
        result = engine.adjust(base_confidence=0.80, effectiveness=eff)
        assert result.adjusted_confidence == 0.80  # 无其他降级因子


# ═══════════════════════════════════════════════════════════════
# Dimension 3: Context Similarity
# ═══════════════════════════════════════════════════════════════


class TestContextSimilarity:
    def test_empty_context_returns_neutral(self) -> None:
        engine = AdaptiveConfidenceEngine()
        assert engine._compute_context_similarity({}, "test") == 1.0

    def test_no_history_returns_neutral(self) -> None:
        engine = AdaptiveConfidenceEngine()
        ctx = {"action_type": "increase_budget"}
        assert engine._compute_context_similarity(ctx, "test") == 1.0

    def test_same_context_high_similarity(self) -> None:
        engine = AdaptiveConfidenceEngine(min_samples_for_accuracy=1)
        ctx = {"action_type": "increase_budget", "strategy": "scale_winning"}

        # 先建立历史
        r = engine.adjust(base_confidence=0.80, source="test", context=ctx)
        engine.record_outcome(r.result_id, "success")

        sim = engine._compute_context_similarity(ctx, "test")
        assert sim >= 0.95  # 相同上下文

    def test_different_context_low_similarity(self) -> None:
        engine = AdaptiveConfidenceEngine(min_samples_for_accuracy=1)
        ctx1 = {"action_type": "increase_budget", "strategy": "scale_winning"}
        ctx2 = {"action_type": "pause_campaign", "strategy": "cut_losses"}

        r = engine.adjust(base_confidence=0.80, source="test", context=ctx1)
        engine.record_outcome(r.result_id, "success")

        sim = engine._compute_context_similarity(ctx2, "test")
        assert sim < 0.95  # 不同上下文

    def test_context_similarity_affects_adjustment(self) -> None:
        engine = AdaptiveConfidenceEngine(min_samples_for_accuracy=1)
        ctx1 = {"action_type": "increase_budget"}
        ctx2 = {"action_type": "pause_campaign"}

        r = engine.adjust(base_confidence=0.80, source="test", context=ctx1)
        engine.record_outcome(r.result_id, "success")

        # 陌生上下文应降级
        result = engine.adjust(base_confidence=0.80, source="test", context=ctx2)
        assert result.adjusted_confidence < 0.80

    def test_key_similarity_exact(self) -> None:
        engine = AdaptiveConfidenceEngine()
        assert engine._key_similarity("a:1|b:2", "a:1|b:2") == 1.0

    def test_key_similarity_partial(self) -> None:
        engine = AdaptiveConfidenceEngine()
        sim = engine._key_similarity("a:1|b:2|c:3", "a:1|b:2|d:4")
        # 交集: {a:1, b:2}, 并集: {a:1, b:2, c:3, d:4} → 2/4 = 0.5
        assert sim == 0.5

    def test_key_similarity_none(self) -> None:
        engine = AdaptiveConfidenceEngine()
        assert engine._key_similarity("a:1", "b:2") == 0.0

    def test_make_context_key(self) -> None:
        engine = AdaptiveConfidenceEngine()
        key = engine._make_context_key({"b": "2", "a": "1"})
        assert key == "a:1|b:2"  # 排序后


# ═══════════════════════════════════════════════════════════════
# Dimension 4: Freshness
# ═══════════════════════════════════════════════════════════════


class TestFreshness:
    def test_no_timestamps_returns_neutral(self) -> None:
        engine = AdaptiveConfidenceEngine()
        assert engine._compute_freshness(None) == 1.0

    def test_empty_timestamps_returns_neutral(self) -> None:
        engine = AdaptiveConfidenceEngine()
        assert engine._compute_freshness([]) == 1.0

    def test_recent_data_returns_full(self) -> None:
        engine = AdaptiveConfidenceEngine(freshness_days_recent=7)
        ts = _make_timestamps([1, 2, 3])  # 1-3天前
        assert engine._compute_freshness(ts) == 1.0

    def test_stale_data_returns_low(self) -> None:
        engine = AdaptiveConfidenceEngine(freshness_days_stale=30)
        ts = _make_timestamps([40, 45, 50])  # 40-50天前
        assert engine._compute_freshness(ts) == 0.70

    def test_mixed_data_returns_intermediate(self) -> None:
        engine = AdaptiveConfidenceEngine(freshness_days_recent=7, freshness_days_stale=30)
        ts = _make_timestamps([2, 20])  # 混合
        fr = engine._compute_freshness(ts)
        assert 0.70 < fr < 1.0

    def test_freshness_affects_adjustment(self) -> None:
        engine = AdaptiveConfidenceEngine(freshness_days_stale=30)
        stale_ts = _make_timestamps([40, 45])
        result = engine.adjust(base_confidence=0.80, data_timestamps=stale_ts)
        assert result.adjusted_confidence < 0.80

    def test_freshness_preserves_when_recent(self) -> None:
        engine = AdaptiveConfidenceEngine()
        recent_ts = _make_timestamps([1, 2])
        result = engine.adjust(base_confidence=0.80, data_timestamps=recent_ts)
        assert result.adjusted_confidence == 0.80  # 近期数据 → 不降级


# ═══════════════════════════════════════════════════════════════
# Record Outcome
# ═══════════════════════════════════════════════════════════════


class TestRecordOutcome:
    def test_record_success(self) -> None:
        engine = AdaptiveConfidenceEngine()
        result = engine.adjust(base_confidence=0.80, source="test")
        record = engine.record_outcome(result.result_id, "success")

        assert record is not None
        assert record.actual_outcome == "success"
        assert record.is_accurate
        assert engine.history_count == 1
        assert engine.pending_count == 0

    def test_record_failure_downgrades(self) -> None:
        engine = AdaptiveConfidenceEngine()
        result = engine.adjust(base_confidence=0.80, source="test")
        record = engine.record_outcome(result.result_id, "failure")

        assert record is not None
        assert record.actual_outcome == "failure"
        assert not record.is_accurate  # 高置信度 + 失败 = 不准确

    def test_record_unknown_result_id(self) -> None:
        engine = AdaptiveConfidenceEngine()
        record = engine.record_outcome("nonexistent", "success")
        assert record is None

    def test_record_partial_outcome(self) -> None:
        engine = AdaptiveConfidenceEngine()
        result = engine.adjust(base_confidence=0.80, source="test")
        record = engine.record_outcome(result.result_id, "partial")

        assert record is not None
        assert record.actual_outcome == "partial"

    def test_high_confidence_failure_is_inaccurate(self) -> None:
        engine = AdaptiveConfidenceEngine()
        engine._judge_accuracy(0.80, "failure") is False

    def test_low_confidence_failure_is_accurate(self) -> None:
        engine = AdaptiveConfidenceEngine()
        assert engine._judge_accuracy(0.30, "failure") is True

    def test_low_confidence_success_neutral(self) -> None:
        """低置信度成功 → 不计为准确 (保守预测)."""
        engine = AdaptiveConfidenceEngine()
        assert engine._judge_accuracy(0.30, "success") is False

    def test_medium_confidence_success_accurate(self) -> None:
        engine = AdaptiveConfidenceEngine()
        assert engine._judge_accuracy(0.60, "success") is True

    def test_medium_confidence_failure_inaccurate(self) -> None:
        engine = AdaptiveConfidenceEngine()
        assert engine._judge_accuracy(0.60, "failure") is False

    def test_multiple_records_accumulate(self) -> None:
        engine = AdaptiveConfidenceEngine()
        for _ in range(10):
            r = engine.adjust(base_confidence=0.80, source="test")
            engine.record_outcome(r.result_id, "success")

        assert engine.history_count == 10
        assert engine.pending_count == 0


# ═══════════════════════════════════════════════════════════════
# Integration Scenarios
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    def test_full_predict_adjust_feedback_loop(self) -> None:
        """完整闭环: 预测 → 调整 → 记录结果 → 影响后续."""
        engine = AdaptiveConfidenceEngine(min_samples_for_accuracy=3)

        # Phase 1: 建立不良历史 (3 次高置信度失败)
        for _ in range(3):
            r = engine.adjust(base_confidence=0.85, source="test")
            engine.record_outcome(r.result_id, "failure")

        # Phase 2: 后续预测应被降级
        result = engine.adjust(base_confidence=0.85, source="test")
        assert result.adjusted_confidence < 0.85
        assert result.is_downgraded
        assert "Historical accuracy" in str(result.adjustments)

    def test_all_dimensions_combined_downgrade(self) -> None:
        """所有维度同时降级."""
        engine = AdaptiveConfidenceEngine(min_samples_for_accuracy=3)

        # 建立不良历史
        for _ in range(3):
            r = engine.adjust(base_confidence=0.80, source="test")
            engine.record_outcome(r.result_id, "failure")

        eff = _make_effectiveness(0.20)  # 低有效性
        stale_ts = _make_timestamps([40, 45])  # 过期数据
        ctx = {"action_type": "unknown_action"}  # 陌生上下文

        # 先建立历史上下文
        r = engine.adjust(
            base_confidence=0.80, source="test",
            context={"action_type": "known_action"},
        )
        engine.record_outcome(r.result_id, "success")

        result = engine.adjust(
            base_confidence=0.80,
            source="test",
            effectiveness=eff,
            data_timestamps=stale_ts,
            context=ctx,
        )

        # 应该大幅降级
        assert result.adjusted_confidence < 0.50
        assert result.is_downgraded
        assert len(result.adjustments) >= 2

    def test_confidence_recovery_after_good_history(self) -> None:
        """好的历史记录应恢复置信度."""
        engine = AdaptiveConfidenceEngine(min_samples_for_accuracy=3)

        # 先建立好的历史
        for _ in range(5):
            r = engine.adjust(base_confidence=0.80, source="test")
            engine.record_outcome(r.result_id, "success")

        result = engine.adjust(base_confidence=0.80, source="test")
        assert result.adjusted_confidence >= 0.80  # 全部准确 → 不降级

    def test_warnings_generated(self) -> None:
        engine = AdaptiveConfidenceEngine(min_samples_for_accuracy=3)

        for _ in range(3):
            r = engine.adjust(base_confidence=0.80, source="test")
            engine.record_outcome(r.result_id, "failure")

        eff = _make_effectiveness(0.15)
        stale_ts = _make_timestamps([50])
        result = engine.adjust(
            base_confidence=0.80,
            source="test",
            effectiveness=eff,
            data_timestamps=stale_ts,
        )

        assert len(result.warnings) >= 1  # 应该至少有一个警告

    def test_get_accuracy_stats(self) -> None:
        engine = AdaptiveConfidenceEngine(min_samples_for_accuracy=1)
        for _ in range(3):
            r = engine.adjust(base_confidence=0.80, source="test")
            engine.record_outcome(r.result_id, "success")
        for _ in range(2):
            r = engine.adjust(base_confidence=0.80, source="test")
            engine.record_outcome(r.result_id, "failure")

        stats = engine.get_accuracy_stats("test")
        assert stats["total"] == 5
        assert stats["accuracy"] == 0.60  # 3/5

    def test_get_accuracy_stats_empty(self) -> None:
        engine = AdaptiveConfidenceEngine()
        stats = engine.get_accuracy_stats()
        assert stats["total"] == 0
        assert stats["accuracy"] == 0.0

    def test_get_accuracy_stats_by_confidence_level(self) -> None:
        engine = AdaptiveConfidenceEngine(min_samples_for_accuracy=1)
        # 高置信度
        r = engine.adjust(base_confidence=0.80, source="test")
        engine.record_outcome(r.result_id, "success")
        # 低置信度
        r = engine.adjust(base_confidence=0.30, source="test")
        engine.record_outcome(r.result_id, "success")

        stats = engine.get_accuracy_stats("test")
        assert "high_confidence_accuracy" in stats
        assert "medium_confidence_accuracy" in stats
        assert "low_confidence_accuracy" in stats


# ═══════════════════════════════════════════════════════════════
# Custom Weights via LearningStrategyState
# ═══════════════════════════════════════════════════════════════


class TestCustomWeights:
    def test_strategy_state_weights_used(self) -> None:
        state = LearningStrategyState(
            pattern_weight=0.50,  # 用作 historical_accuracy 权重
            memory_weight=0.50,   # 用作 learning_effectiveness 权重
        )
        engine = AdaptiveConfidenceEngine(strategy_state=state)
        weights = engine._get_weights()
        assert weights["historical_accuracy"] == 0.50
        assert weights["learning_effectiveness"] == 0.50

    def test_default_weights_when_no_state(self) -> None:
        engine = AdaptiveConfidenceEngine()
        weights = engine._get_weights()
        assert weights["historical_accuracy"] == 0.30
        assert weights["learning_effectiveness"] == 0.20
        assert weights["context_similarity"] == 0.25
        assert weights["freshness"] == 0.25

    def test_weights_sum_to_one(self) -> None:
        engine = AdaptiveConfidenceEngine()
        weights = engine._get_weights()
        assert sum(weights.values()) == 1.0


# ═══════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_zero_base_confidence(self) -> None:
        engine = AdaptiveConfidenceEngine()
        result = engine.adjust(base_confidence=0.0, source="test")
        assert result.adjusted_confidence == 0.0
        assert result.confidence_level == "insufficient"

    def test_max_base_confidence(self) -> None:
        engine = AdaptiveConfidenceEngine()
        result = engine.adjust(base_confidence=1.0, source="test")
        assert result.adjusted_confidence <= 1.0

    def test_negative_base_confidence_clamped(self) -> None:
        engine = AdaptiveConfidenceEngine()
        result = engine.adjust(base_confidence=-0.5, source="test")
        assert result.adjusted_confidence >= 0.0

    def test_empty_context(self) -> None:
        engine = AdaptiveConfidenceEngine()
        result = engine.adjust(base_confidence=0.75, context={})
        assert result.adjusted_confidence == 0.75  # 无历史 → 不调整

    def test_empty_source(self) -> None:
        engine = AdaptiveConfidenceEngine()
        result = engine.adjust(base_confidence=0.75, source="")
        assert result.adjusted_confidence == 0.75

    def test_invalid_timestamps_handled(self) -> None:
        engine = AdaptiveConfidenceEngine()
        result = engine.adjust(
            base_confidence=0.75,
            data_timestamps=["invalid", "also-invalid"],
        )
        assert result.dimensions["freshness"] == 0.85  # 回退到保守值

    def test_max_history_enforced(self) -> None:
        engine = AdaptiveConfidenceEngine(max_history=5)
        for _ in range(10):
            r = engine.adjust(base_confidence=0.80, source="test")
            engine.record_outcome(r.result_id, "success")

        assert engine.history_count == 5  # 不超过 max_history

    def test_multiple_engines_independent(self) -> None:
        e1 = AdaptiveConfidenceEngine()
        e2 = AdaptiveConfidenceEngine()

        r1 = e1.adjust(base_confidence=0.80, source="test")
        e1.record_outcome(r1.result_id, "success")

        assert e1.history_count == 1
        assert e2.history_count == 0

    def test_record_outcome_already_resolved(self) -> None:
        """同一个 result_id 不能重复记录."""
        engine = AdaptiveConfidenceEngine()
        result = engine.adjust(base_confidence=0.80, source="test")
        engine.record_outcome(result.result_id, "success")
        # 第二次记录应返回 None
        assert engine.record_outcome(result.result_id, "failure") is None

    def test_result_serializable(self) -> None:
        engine = AdaptiveConfidenceEngine()
        result = engine.adjust(
            base_confidence=0.75,
            source="enhancer",
            context={"action": "test"},
            effectiveness=_make_effectiveness(0.60),
            data_timestamps=_make_timestamps([5, 10]),
        )
        d = result.to_dict()
        assert "result_id" in d
        assert "base_confidence" in d
        assert "adjusted_confidence" in d
        assert "dimensions" in d
        assert "adjustments" in d
        assert "warnings" in d
        assert "confidence_level" in d

    def test_all_dimensions_present_in_result(self) -> None:
        engine = AdaptiveConfidenceEngine()
        result = engine.adjust(
            base_confidence=0.75,
            source="test",
            effectiveness=_make_effectiveness(0.80),
            data_timestamps=_make_timestamps([1, 2]),
            context={"action": "test"},
        )

        dims = result.dimensions
        for dim in ConfidenceDimension:
            assert dim.value in dims, f"Missing dimension: {dim.value}"

    def test_engine_repr(self) -> None:
        engine = AdaptiveConfidenceEngine()
        r = engine.adjust(base_confidence=0.80, source="test")
        engine.record_outcome(r.result_id, "success")
        rep = repr(engine)
        assert "history=1" in rep
        assert "pending=0" in rep