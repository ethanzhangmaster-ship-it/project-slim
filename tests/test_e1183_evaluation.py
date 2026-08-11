"""E11.8.3 — Evolution Evaluation Engine Tests。

覆盖：
  - Models: EvaluationStatus, MetricComparison, EvolutionEvaluation, EvolutionRecommendation
  - MetricEvaluator: compare / compare_focused
  - ImprovementDetector: detect / detect_with_details
  - StrategyJudge: judge / judge_with_reason
  - EvaluationEngine: evaluate / evaluate_with_focus
  - Controller Integration: evaluate_evolution / evaluate_and_learn
  - Full Pipeline
  - Package Exports
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.autonomous_controller.strategy.evaluation.models import (
    EvaluationStatus,
    EvolutionEvaluation,
    EvolutionRecommendation,
    MetricComparison,
)
from market_ops.creative_vision_runtime.autonomous_controller.strategy.evaluation.metric_evaluator import (
    MetricEvaluator,
)
from market_ops.creative_vision_runtime.autonomous_controller.strategy.evaluation.improvement_detector import (
    ImprovementDetector,
)
from market_ops.creative_vision_runtime.autonomous_controller.strategy.evaluation.strategy_judge import (
    StrategyJudge,
)
from market_ops.creative_vision_runtime.autonomous_controller.strategy.evaluation.evaluation_engine import (
    EvolutionEvaluationEngine,
)
from market_ops.creative_vision_runtime.autonomous_controller.strategy.models import (
    EvolutionObjective,
    EvolutionStrategy,
    Intensity,
    MutationFocus,
    StrategyType,
)


# ── Helpers ──────────────────────────────────────────────────


def _make_strategy(
    strategy_type: StrategyType = StrategyType.EXPLORE_NEW,
    confidence: float = 0.7,
) -> EvolutionStrategy:
    obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
    return EvolutionStrategy(
        strategy_type=strategy_type,
        objective=obj,
        mutation_focus=MutationFocus.HOOK,
        intensity=Intensity.MEDIUM,
        confidence=confidence,
        reason=f"Test {strategy_type.value}",
    )


def _make_comparisons(improved: int, degraded: int, significance: str = "marginal") -> list[MetricComparison]:
    comps = []
    for i in range(improved):
        comps.append(MetricComparison(
            metric=f"metric_{i}",
            before=0.5,
            after=0.65,
            improvement=True,
            significance=significance,
        ))
    for i in range(degraded):
        comps.append(MetricComparison(
            metric=f"metric_bad_{i}",
            before=0.5,
            after=0.4,
            improvement=False,
            significance=significance,
        ))
    return comps


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


class TestEvaluationStatus:
    """EvaluationStatus 枚举测试。"""

    def test_values(self):
        assert EvaluationStatus.SUCCESS.value == "success"
        assert EvaluationStatus.PARTIAL.value == "partial"
        assert EvaluationStatus.FAILED.value == "failed"
        assert EvaluationStatus.INCONCLUSIVE.value == "inconclusive"


class TestEvolutionRecommendation:
    """EvolutionRecommendation 枚举测试。"""

    def test_values(self):
        assert EvolutionRecommendation.KEEP.value == "keep"
        assert EvolutionRecommendation.SCALE.value == "scale"
        assert EvolutionRecommendation.ITERATE.value == "iterate"
        assert EvolutionRecommendation.ROLLBACK.value == "rollback"
        assert EvolutionRecommendation.RETIRE.value == "retire"


class TestMetricComparison:
    """MetricComparison 测试。"""

    def test_create_improvement(self):
        m = MetricComparison(
            metric="ROI",
            before=0.45,
            after=0.62,
            improvement=True,
            significance="significant",
        )
        assert m.metric == "ROI"
        assert m.before == 0.45
        assert m.after == 0.62
        assert m.delta == pytest.approx(0.17)
        assert m.delta_pct == pytest.approx(0.17 / 0.45)
        assert m.improvement is True

    def test_create_degradation(self):
        m = MetricComparison(
            metric="CTR",
            before=0.04,
            after=0.03,
            improvement=False,
            significance="significant",
        )
        assert m.delta == pytest.approx(-0.01)
        assert m.improvement is False

    def test_delta_auto_computed(self):
        m = MetricComparison(metric="ROI", before=1.0, after=1.5)
        assert m.delta == pytest.approx(0.5)

    def test_delta_pct_auto_computed(self):
        m = MetricComparison(metric="ROI", before=1.0, after=1.5)
        assert m.delta_pct == pytest.approx(0.5)

    def test_is_significant(self):
        m = MetricComparison(significance="significant")
        assert m.is_significant is True

    def test_is_marginal(self):
        m = MetricComparison(significance="marginal")
        assert m.is_marginal is True

    def test_abs_delta(self):
        m = MetricComparison(metric="ROI", before=1.0, after=1.5)
        assert m.abs_delta == pytest.approx(0.5)

    def test_to_dict(self):
        m = MetricComparison(
            metric="ROI", before=0.45, after=0.62, improvement=True
        )
        d = m.to_dict()
        assert d["metric"] == "ROI"
        assert d["improvement"] is True

    def test_repr(self):
        m = MetricComparison(
            metric="ROI", before=0.45, after=0.62, improvement=True
        )
        r = repr(m)
        assert "ROI" in r


class TestEvolutionEvaluation:
    """EvolutionEvaluation 测试。"""

    def test_create_default(self):
        e = EvolutionEvaluation()
        assert e.evaluation_id.startswith("eval_")
        assert e.status == EvaluationStatus.INCONCLUSIVE
        assert e.score == 0.0

    def test_create_success(self):
        e = EvolutionEvaluation(
            strategy_id="strat_abc",
            status=EvaluationStatus.SUCCESS,
            score=85.0,
            improvements=[
                MetricComparison(metric="ROI", before=0.45, after=0.62, improvement=True),
                MetricComparison(metric="CTR", before=0.03, after=0.035, improvement=True),
            ],
            recommendation=EvolutionRecommendation.SCALE,
            confidence=0.9,
        )
        assert e.is_success is True
        assert e.improved_count == 2
        assert e.degraded_count == 0
        assert e.total_metrics == 2

    def test_is_partial(self):
        e = EvolutionEvaluation(status=EvaluationStatus.PARTIAL)
        assert e.is_partial is True
        assert e.is_success is False
        assert e.is_failed is False

    def test_is_failed(self):
        e = EvolutionEvaluation(status=EvaluationStatus.FAILED)
        assert e.is_failed is True

    def test_is_inconclusive(self):
        e = EvolutionEvaluation(status=EvaluationStatus.INCONCLUSIVE)
        assert e.is_inconclusive is True

    def test_improved_and_degraded_count(self):
        e = EvolutionEvaluation(improvements=[
            MetricComparison(metric="a", improvement=True),
            MetricComparison(metric="b", improvement=True),
            MetricComparison(metric="c", improvement=False),
        ])
        assert e.improved_count == 2
        assert e.degraded_count == 1

    def test_avg_improvement(self):
        e = EvolutionEvaluation(improvements=[
            MetricComparison(metric="a", before=1.0, after=1.2, improvement=True),
            MetricComparison(metric="b", before=1.0, after=0.9, improvement=False),
        ])
        # delta_pct: 0.2 and -0.1 → avg = 0.05
        assert e.avg_improvement == pytest.approx(0.05)

    def test_avg_improvement_empty(self):
        e = EvolutionEvaluation()
        assert e.avg_improvement == 0.0

    def test_is_actionable_scale(self):
        e = EvolutionEvaluation(recommendation=EvolutionRecommendation.SCALE)
        assert e.is_actionable is True

    def test_is_actionable_keep(self):
        e = EvolutionEvaluation(recommendation=EvolutionRecommendation.KEEP)
        assert e.is_actionable is False

    def test_to_dict(self):
        e = EvolutionEvaluation(
            evaluation_id="eval_123",
            strategy_id="strat_abc",
            status=EvaluationStatus.SUCCESS,
            score=85.0,
            recommendation=EvolutionRecommendation.SCALE,
        )
        d = e.to_dict()
        assert d["evaluation_id"] == "eval_123"
        assert d["status"] == "success"
        assert d["recommendation"] == "scale"

    def test_repr(self):
        e = EvolutionEvaluation(
            status=EvaluationStatus.SUCCESS,
            score=85.0,
            recommendation=EvolutionRecommendation.SCALE,
        )
        r = repr(e)
        assert "success" in r
        assert "85.0" in r

    def test_metadata(self):
        e = EvolutionEvaluation(metadata={"source": "engine"})
        assert e.metadata["source"] == "engine"


# ═══════════════════════════════════════════════════════════════
# MetricEvaluator
# ═══════════════════════════════════════════════════════════════


class TestMetricEvaluator:
    """MetricEvaluator 测试。"""

    def test_compare_basic(self):
        e = MetricEvaluator(metrics=["ROI", "CTR"])
        before = {"ROI": 0.45, "CTR": 0.03}
        after = {"ROI": 0.62, "CTR": 0.035}
        comps = e.compare(before, after)
        assert len(comps) == 2
        roi = [c for c in comps if c.metric == "ROI"][0]
        assert roi.improvement is True
        assert roi.delta_pct == pytest.approx(0.17 / 0.45)

    def test_compare_degradation(self):
        e = MetricEvaluator(metrics=["CTR"])
        before = {"CTR": 0.04}
        after = {"CTR": 0.03}
        comps = e.compare(before, after)
        assert comps[0].improvement is False
        assert comps[0].delta < 0

    def test_compare_cpa_lower_better(self):
        e = MetricEvaluator(metrics=["CPA"])
        before = {"CPA": 10.0}
        after = {"CPA": 8.0}
        comps = e.compare(before, after)
        assert comps[0].improvement is True  # CPA lower is better

    def test_compare_cpa_higher_worse(self):
        e = MetricEvaluator(metrics=["CPA"])
        before = {"CPA": 8.0}
        after = {"CPA": 10.0}
        comps = e.compare(before, after)
        assert comps[0].improvement is False

    def test_compare_missing_metric_skipped(self):
        e = MetricEvaluator(metrics=["ROI", "CTR"])
        before = {"ROI": 0.5}
        after = {"ROI": 0.6}
        comps = e.compare(before, after)
        assert len(comps) == 1  # CTR skipped

    def test_compare_significance(self):
        e = MetricEvaluator(metrics=["ROI"])
        before = {"ROI": 1.0}
        after = {"ROI": 1.08}  # 8% change → significant
        comps = e.compare(before, after)
        assert comps[0].significance == "significant"

    def test_compare_marginal(self):
        e = MetricEvaluator(metrics=["ROI"])
        before = {"ROI": 1.0}
        after = {"ROI": 1.03}  # 3% change → marginal
        comps = e.compare(before, after)
        assert comps[0].significance == "marginal"

    def test_compare_none_significance(self):
        e = MetricEvaluator(metrics=["ROI"])
        before = {"ROI": 1.0}
        after = {"ROI": 1.005}  # 0.5% change → none
        comps = e.compare(before, after)
        assert comps[0].significance == "none"

    def test_compare_focused(self):
        e = MetricEvaluator(metrics=["ROI", "CTR", "CVR"])
        before = {"ROI": 0.5, "CTR": 0.03, "CVR": 0.08}
        after = {"ROI": 0.6, "CTR": 0.035, "CVR": 0.09}
        comps = e.compare_focused(before, after, focus_metrics=["ROI"])
        assert len(comps) == 1
        assert comps[0].metric == "ROI"

    def test_summarize(self):
        e = MetricEvaluator(metrics=["ROI", "CTR"])
        before = {"ROI": 0.45, "CTR": 0.03}
        after = {"ROI": 0.62, "CTR": 0.025}
        comps = e.compare(before, after)
        summary = e.summarize(comps)
        assert summary["total"] == 2
        assert summary["improved"] == 1
        assert summary["degraded"] == 1
        assert summary["best_metric"] is not None
        assert summary["worst_metric"] is not None

    def test_summarize_empty(self):
        e = MetricEvaluator()
        summary = e.summarize([])
        assert summary["total"] == 0
        assert summary["best_metric"] is None

    def test_repr(self):
        e = MetricEvaluator()
        assert "MetricEvaluator" in repr(e)


# ═══════════════════════════════════════════════════════════════
# ImprovementDetector
# ═══════════════════════════════════════════════════════════════


class TestImprovementDetector:
    """ImprovementDetector 测试。"""

    def test_detect_success(self):
        d = ImprovementDetector()
        comps = _make_comparisons(improved=4, degraded=1)
        status, score = d.detect(comps)
        assert status == EvaluationStatus.SUCCESS

    def test_detect_failed(self):
        d = ImprovementDetector()
        comps = _make_comparisons(improved=1, degraded=4)
        status, score = d.detect(comps)
        assert status == EvaluationStatus.FAILED

    def test_detect_partial(self):
        d = ImprovementDetector()
        comps = _make_comparisons(improved=3, degraded=4)  # 3/7 = 0.428 → PARTIAL
        status, score = d.detect(comps)
        assert status == EvaluationStatus.PARTIAL

    def test_detect_inconclusive(self):
        d = ImprovementDetector()
        comps = _make_comparisons(improved=1, degraded=0)
        status, score = d.detect(comps)
        assert status == EvaluationStatus.INCONCLUSIVE

    def test_detect_with_details(self):
        d = ImprovementDetector()
        comps = _make_comparisons(improved=4, degraded=1)
        details = d.detect_with_details(comps)
        assert details["status"] == EvaluationStatus.SUCCESS
        assert details["improved_count"] == 4
        assert details["degraded_count"] == 1
        assert "reason" in details

    def test_detect_with_details_partial(self):
        d = ImprovementDetector()
        comps = _make_comparisons(improved=3, degraded=4)  # 3/7 = 0.428 → PARTIAL
        details = d.detect_with_details(comps)
        assert details["status"] == EvaluationStatus.PARTIAL
        assert details["improvement_ratio"] == pytest.approx(3/7, rel=1e-3)

    def test_detect_with_details_inconclusive(self):
        d = ImprovementDetector()
        comps = _make_comparisons(improved=1, degraded=0)
        details = d.detect_with_details(comps)
        assert details["status"] == EvaluationStatus.INCONCLUSIVE

    def test_significant_weighted_higher(self):
        """Significant指标权重更高。"""
        d = ImprovementDetector()
        comps_sig = _make_comparisons(improved=3, degraded=0, significance="significant")
        comps_none = _make_comparisons(improved=3, degraded=0, significance="none")
        _, score_sig = d.detect(comps_sig)
        _, score_none = d.detect(comps_none)
        assert score_sig > score_none

    def test_repr(self):
        d = ImprovementDetector()
        assert "ImprovementDetector" in repr(d)


# ═══════════════════════════════════════════════════════════════
# StrategyJudge
# ═══════════════════════════════════════════════════════════════


class TestStrategyJudge:
    """StrategyJudge 测试。"""

    def test_judge_success_high_confidence(self):
        j = StrategyJudge()
        e = EvolutionEvaluation(
            status=EvaluationStatus.SUCCESS,
            score=85.0,
            confidence=0.9,
        )
        rec = j.judge(e)
        assert rec == EvolutionRecommendation.SCALE

    def test_judge_success_moderate_confidence(self):
        j = StrategyJudge()
        e = EvolutionEvaluation(
            status=EvaluationStatus.SUCCESS,
            score=75.0,
            confidence=0.7,
        )
        rec = j.judge(e)
        assert rec == EvolutionRecommendation.KEEP

    def test_judge_partial(self):
        j = StrategyJudge()
        e = EvolutionEvaluation(
            status=EvaluationStatus.PARTIAL,
            score=50.0,
        )
        rec = j.judge(e)
        assert rec == EvolutionRecommendation.ITERATE

    def test_judge_failed(self):
        j = StrategyJudge()
        e = EvolutionEvaluation(
            status=EvaluationStatus.FAILED,
            score=20.0,
        )
        rec = j.judge(e)
        assert rec == EvolutionRecommendation.ROLLBACK

    def test_judge_failed_retire(self):
        j = StrategyJudge()
        e = EvolutionEvaluation(
            status=EvaluationStatus.FAILED,
            score=10.0,
        )
        rec = j.judge(e, consecutive_failures=5)
        assert rec == EvolutionRecommendation.RETIRE

    def test_judge_inconclusive(self):
        j = StrategyJudge()
        e = EvolutionEvaluation(
            status=EvaluationStatus.INCONCLUSIVE,
            score=0.0,
        )
        rec = j.judge(e)
        assert rec == EvolutionRecommendation.KEEP

    def test_judge_with_reason(self):
        j = StrategyJudge()
        e = EvolutionEvaluation(
            status=EvaluationStatus.SUCCESS,
            score=90.0,
            confidence=0.85,
            improvements=[
                MetricComparison(metric="ROI", improvement=True),
                MetricComparison(metric="CTR", improvement=True),
            ],
        )
        result = j.judge_with_reason(e)
        assert result["recommendation"] == EvolutionRecommendation.SCALE
        assert "reason" in result
        assert result["confidence"] > 0

    def test_judge_with_reason_partial(self):
        j = StrategyJudge()
        e = EvolutionEvaluation(status=EvaluationStatus.PARTIAL, score=50.0)
        result = j.judge_with_reason(e)
        assert result["recommendation"] == EvolutionRecommendation.ITERATE
        assert "Partial" in result["reason"]

    def test_custom_thresholds(self):
        j = StrategyJudge(scale_threshold=0.5)
        e = EvolutionEvaluation(
            status=EvaluationStatus.SUCCESS,
            score=85.0,
            confidence=0.6,
        )
        rec = j.judge(e)
        assert rec == EvolutionRecommendation.SCALE

    def test_repr(self):
        j = StrategyJudge()
        assert "StrategyJudge" in repr(j)


# ═══════════════════════════════════════════════════════════════
# EvaluationEngine
# ═══════════════════════════════════════════════════════════════


class TestEvaluationEngine:
    """EvolutionEvaluationEngine 测试。"""

    def test_evaluate_success(self):
        engine = EvolutionEvaluationEngine()
        before = {"ROI": 0.5, "CTR": 0.03, "CVR": 0.08}
        after = {"ROI": 0.7, "CTR": 0.04, "CVR": 0.10}
        evaluation = engine.evaluate(before, after)
        assert evaluation.status == EvaluationStatus.SUCCESS
        assert evaluation.score > 0
        assert evaluation.total_metrics >= 3

    def test_evaluate_failed(self):
        engine = EvolutionEvaluationEngine()
        before = {"ROI": 0.7, "CTR": 0.04, "CVR": 0.10}
        after = {"ROI": 0.5, "CTR": 0.03, "CVR": 0.08}
        evaluation = engine.evaluate(before, after)
        assert evaluation.status == EvaluationStatus.FAILED

    def test_evaluate_with_strategy(self):
        engine = EvolutionEvaluationEngine()
        strategy = _make_strategy(StrategyType.EXPLOIT_WINNER, confidence=0.85)
        before = {"ROI": 0.5, "CTR": 0.03}
        after = {"ROI": 0.7, "CTR": 0.04}
        evaluation = engine.evaluate(before, after, strategy=strategy)
        assert evaluation.strategy_id == strategy.strategy_id
        assert evaluation.recommendation == EvolutionRecommendation.SCALE

    def test_evaluate_partial(self):
        engine = EvolutionEvaluationEngine()
        before = {"ROI": 0.5, "CTR": 0.03, "CVR": 0.08}
        after = {"ROI": 0.7, "CTR": 0.025, "CVR": 0.10}  # CTR degraded
        evaluation = engine.evaluate(before, after)
        assert evaluation.status in (EvaluationStatus.SUCCESS, EvaluationStatus.PARTIAL)

    def test_evaluate_batch(self):
        engine = EvolutionEvaluationEngine()
        pairs = [
            ({"ROI": 0.5, "CTR": 0.03}, {"ROI": 0.7, "CTR": 0.04}),
            ({"ROI": 0.7, "CTR": 0.04}, {"ROI": 0.5, "CTR": 0.03}),
        ]
        results = engine.evaluate_batch(pairs)
        assert len(results) == 2

    def test_evaluate_with_focus(self):
        engine = EvolutionEvaluationEngine()
        before = {"ROI": 0.5, "CTR": 0.03, "CVR": 0.08}
        after = {"ROI": 0.7, "CTR": 0.025, "CVR": 0.10}
        evaluation = engine.evaluate_with_focus(
            before, after, focus_metrics=["ROI"]
        )
        assert evaluation.total_metrics == 1
        assert evaluation.improvements[0].metric == "ROI"

    def test_evaluate_with_consecutive_failures(self):
        engine = EvolutionEvaluationEngine()
        before = {"ROI": 0.7, "CTR": 0.04}
        after = {"ROI": 0.5, "CTR": 0.03}
        evaluation = engine.evaluate(
            before, after, consecutive_failures=5
        )
        assert evaluation.recommendation == EvolutionRecommendation.RETIRE

    def test_dependency_injection(self):
        m = MetricEvaluator(metrics=["ROI"])
        d = ImprovementDetector()
        j = StrategyJudge()
        engine = EvolutionEvaluationEngine(
            metric_evaluator=m,
            improvement_detector=d,
            strategy_judge=j,
        )
        assert engine.metric_evaluator is m
        assert engine.improvement_detector is d
        assert engine.strategy_judge is j

    def test_repr(self):
        engine = EvolutionEvaluationEngine()
        assert "EvolutionEvaluationEngine" in repr(engine)


# ═══════════════════════════════════════════════════════════════
# Controller Integration
# ═══════════════════════════════════════════════════════════════


class TestControllerEvaluationIntegration:
    """Controller E11.8.3 集成测试。"""

    @pytest.fixture
    def controller(self):
        from unittest.mock import MagicMock
        from market_ops.creative_vision_runtime.autonomous_controller.controller import (
            AutonomousCreativeController,
        )
        engine = MagicMock()
        return AutonomousCreativeController(intelligence_engine=engine)

    def test_evaluate_evolution(self, controller):
        before = {"ROI": 0.5, "CTR": 0.03}
        after = {"ROI": 0.7, "CTR": 0.04}
        evaluation = controller.evaluate_evolution(before, after)
        assert isinstance(evaluation, EvolutionEvaluation)
        assert evaluation.status == EvaluationStatus.SUCCESS

    def test_evaluate_evolution_with_strategy(self, controller):
        strategy = _make_strategy(StrategyType.EXPLOIT_WINNER, confidence=0.85)
        before = {"ROI": 0.5, "CTR": 0.03}
        after = {"ROI": 0.7, "CTR": 0.04}
        evaluation = controller.evaluate_evolution(before, after, strategy=strategy)
        assert evaluation.strategy_id == strategy.strategy_id

    def test_evaluate_evolution_failed(self, controller):
        before = {"ROI": 0.7, "CTR": 0.04}
        after = {"ROI": 0.3, "CTR": 0.02}
        evaluation = controller.evaluate_evolution(before, after)
        assert evaluation.status == EvaluationStatus.FAILED
        assert evaluation.recommendation == EvolutionRecommendation.ROLLBACK

    def test_evaluate_and_learn(self, controller):
        strategy = _make_strategy(StrategyType.EXPLOIT_WINNER, confidence=0.85)
        before = {"ROI": 0.5, "CTR": 0.03}
        after = {"ROI": 0.7, "CTR": 0.04}
        result = controller.evaluate_and_learn(before, after, strategy=strategy)
        assert "evaluation" in result
        assert "memory_record" in result
        assert "new_strategies" in result

    def test_evaluation_engine_property(self, controller):
        assert controller.evaluation_engine is not None
        assert isinstance(controller.evaluation_engine, EvolutionEvaluationEngine)

    def test_constructor_injection(self):
        from unittest.mock import MagicMock
        from market_ops.creative_vision_runtime.autonomous_controller.controller import (
            AutonomousCreativeController,
        )
        engine = MagicMock()
        eval_engine = EvolutionEvaluationEngine()
        controller = AutonomousCreativeController(
            intelligence_engine=engine,
            evaluation_engine=eval_engine,
        )
        assert controller.evaluation_engine is eval_engine


# ═══════════════════════════════════════════════════════════════
# Full Pipeline
# ═══════════════════════════════════════════════════════════════


class TestFullPipeline:
    """端到端评估流程。"""

    def test_evaluate_chain(self):
        """完整评估链路。"""
        # 1. MetricEvaluator
        m = MetricEvaluator(metrics=["ROI", "CTR", "CVR"])
        before = {"ROI": 0.5, "CTR": 0.03, "CVR": 0.08}
        after = {"ROI": 0.7, "CTR": 0.04, "CVR": 0.10}
        comps = m.compare(before, after)
        assert len(comps) == 3

        # 2. ImprovementDetector
        d = ImprovementDetector()
        status, score = d.detect(comps)
        assert status == EvaluationStatus.SUCCESS

        # 3. StrategyJudge
        j = StrategyJudge()
        e = EvolutionEvaluation(
            status=status,
            score=score,
            improvements=comps,
            confidence=0.85,
        )
        rec = j.judge(e)
        assert rec == EvolutionRecommendation.SCALE

    def test_engine_full_pipeline(self):
        """Engine 一键完整评估。"""
        engine = EvolutionEvaluationEngine()
        before = {"ROI": 0.5, "CTR": 0.03, "CVR": 0.08}
        after = {"ROI": 0.7, "CTR": 0.04, "CVR": 0.10}
        strategy = _make_strategy(StrategyType.EXPLOIT_WINNER, confidence=0.85)

        evaluation = engine.evaluate(before, after, strategy=strategy)

        assert evaluation.evaluation_id != ""
        assert evaluation.status == EvaluationStatus.SUCCESS
        assert evaluation.recommendation == EvolutionRecommendation.SCALE
        assert evaluation.confidence == 0.85
        assert evaluation.reason != ""

    def test_controller_full_pipeline(self):
        """Controller evaluate_and_learn 完整闭环。"""
        from unittest.mock import MagicMock
        from market_ops.creative_vision_runtime.autonomous_controller.controller import (
            AutonomousCreativeController,
        )
        engine = MagicMock()
        controller = AutonomousCreativeController(intelligence_engine=engine)

        strategy = _make_strategy(StrategyType.EXPLOIT_WINNER, confidence=0.85)
        before = {"ROI": 0.5, "CTR": 0.03, "CVR": 0.08}
        after = {"ROI": 0.7, "CTR": 0.04, "CVR": 0.10}

        result = controller.evaluate_and_learn(
            before, after, strategy=strategy
        )

        assert result["evaluation"].status == EvaluationStatus.SUCCESS
        assert result["memory_record"] is not None
        # SCALE → no new strategies needed
        assert result["new_strategies"] is None

    def test_controller_evaluate_and_learn_failed(self):
        """失败场景 → 生成修正策略。"""
        from unittest.mock import MagicMock
        from market_ops.creative_vision_runtime.autonomous_controller.controller import (
            AutonomousCreativeController,
        )
        engine = MagicMock()
        controller = AutonomousCreativeController(intelligence_engine=engine)

        strategy = _make_strategy(StrategyType.EXPLORE_NEW, confidence=0.5)
        before = {"ROI": 0.7, "CTR": 0.04, "CVR": 0.10}
        after = {"ROI": 0.3, "CTR": 0.02, "CVR": 0.05}

        result = controller.evaluate_and_learn(
            before, after, strategy=strategy
        )

        assert result["evaluation"].status == EvaluationStatus.FAILED
        # ROLLBACK → 需要生成新策略
        assert result["new_strategies"] is not None


# ═══════════════════════════════════════════════════════════════
# Package Exports
# ═══════════════════════════════════════════════════════════════


class TestPackageExports:
    """包导出测试。"""

    def test_exports_models(self):
        from market_ops.creative_vision_runtime.autonomous_controller.strategy.evaluation import (
            EvaluationStatus,
            MetricComparison,
            EvolutionEvaluation,
            EvolutionRecommendation,
        )
        assert EvaluationStatus is not None
        assert MetricComparison is not None
        assert EvolutionEvaluation is not None
        assert EvolutionRecommendation is not None

    def test_exports_engines(self):
        from market_ops.creative_vision_runtime.autonomous_controller.strategy.evaluation import (
            MetricEvaluator,
            ImprovementDetector,
            StrategyJudge,
            EvolutionEvaluationEngine,
        )
        assert MetricEvaluator is not None
        assert ImprovementDetector is not None
        assert StrategyJudge is not None
        assert EvolutionEvaluationEngine is not None