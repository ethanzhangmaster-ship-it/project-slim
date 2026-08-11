"""E11.5.3 — Autonomous Feedback Loop 测试。

测试范围：
  - PerformanceSignal: 数据模型 + 属性 + 序列化
  - FitnessScore: 数据模型 + 属性 + 序列化
  - LearningSignal: 数据模型 + 属性 + 序列化
  - EvolutionFeedback: 统一反馈输出 + 属性
  - LearningDirection: 枚举值
  - PerformanceCollector: collect + collect_batch + 指标计算 + 无效数据
  - Evaluator: evaluate + evaluate_batch + 评分 + 排名 + stats
  - LearningEngine: generate + generate_batch + 方向判定 + 失败跟踪 + 洞察 + 突变推荐
  - FeedbackEngine: process + process_batch + 过滤 + stats
  - Controller Integration: receive_feedback + receive_and_evolve
  - Full Pipeline: Performance → Fitness → Learning → Controller
  - Package exports
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from market_ops.creative_vision_runtime.autonomous_controller.feedback.models import (
    PerformanceSignal,
    FitnessScore,
    LearningSignal,
    EvolutionFeedback,
    LearningDirection,
)
from market_ops.creative_vision_runtime.autonomous_controller.feedback.performance_collector import (
    PerformanceCollector,
)
from market_ops.creative_vision_runtime.autonomous_controller.feedback.evaluator import (
    Evaluator,
)
from market_ops.creative_vision_runtime.autonomous_controller.feedback.learning_engine import (
    LearningEngine,
)
from market_ops.creative_vision_runtime.autonomous_controller.feedback.feedback_engine import (
    FeedbackEngine,
)

# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_exp_result(
    creative_id: str = "c001",
    genome_id: str = "g001",
    impressions: int = 10000,
    clicks: int = 500,
    installs: int = 30,
    revenue: float = 1600.0,
    spend: float = 1000.0,
    period: str = "7d",
) -> dict:
    return {
        "creative_id": creative_id,
        "genome_id": genome_id,
        "impressions": impressions,
        "clicks": clicks,
        "installs": installs,
        "revenue": revenue,
        "spend": spend,
        "period": period,
    }


def _make_high_perf(genome_id: str = "g_winner") -> dict:
    """High performance: ROI 2.0, CTR 5%, CVR 6%."""
    return _make_exp_result(
        creative_id="c_winner",
        genome_id=genome_id,
        impressions=50000,
        clicks=2500,
        installs=150,
        revenue=10000.0,
        spend=5000.0,
    )


def _make_medium_perf(genome_id: str = "g_avg") -> dict:
    """Medium performance: ROI 1.25, CTR 2%, CVR 3%."""
    return _make_exp_result(
        creative_id="c_avg",
        genome_id=genome_id,
        impressions=20000,
        clicks=400,
        installs=12,
        revenue=1500.0,
        spend=1200.0,
    )


def _make_low_perf(genome_id: str = "g_low") -> dict:
    """Low performance: ROI 0.5, CTR 0.5%, CVR 1%."""
    return _make_exp_result(
        creative_id="c_low",
        genome_id=genome_id,
        impressions=10000,
        clicks=50,
        installs=1,
        revenue=500.0,
        spend=1000.0,
    )


# ═══════════════════════════════════════════════════════════
# 1. Models — PerformanceSignal
# ═══════════════════════════════════════════════════════════

class TestPerformanceSignal:
    """PerformanceSignal 数据模型测试。"""

    def test_create_default(self):
        """默认创建：auto-generated signal_id 和 created_at。"""
        ps = PerformanceSignal()
        assert ps.signal_id.startswith("ps_")
        assert ps.created_at != ""

    def test_create_with_values(self):
        """带值创建。"""
        ps = PerformanceSignal(
            signal_id="ps_test_001",
            genome_id="g001",
            creative_id="c001",
            impressions=10000,
            clicks=500,
            installs=30,
            revenue=1600.0,
            spend=1000.0,
            ctr=0.05,
            cvr=0.06,
            roi=1.6,
            period="14d",
        )
        assert ps.genome_id == "g001"
        assert ps.creative_id == "c001"
        assert ps.impressions == 10000
        assert ps.clicks == 500
        assert ps.installs == 30
        assert ps.revenue == 1600.0
        assert ps.spend == 1000.0
        assert ps.ctr == 0.05
        assert ps.cvr == 0.06
        assert ps.roi == 1.6
        assert ps.period == "14d"

    def test_has_sufficient_data_true(self):
        """有足够数据用于评估。"""
        ps = PerformanceSignal(impressions=1000, clicks=100, spend=100.0)
        assert ps.has_sufficient_data is True

    def test_has_sufficient_data_false_low_impressions(self):
        """曝光不足 → 数据不足。"""
        ps = PerformanceSignal(impressions=50, clicks=10, spend=100.0)
        assert ps.has_sufficient_data is False

    def test_has_sufficient_data_false_no_clicks(self):
        """无点击 → 数据不足。"""
        ps = PerformanceSignal(impressions=1000, clicks=0, spend=100.0)
        assert ps.has_sufficient_data is False

    def test_has_sufficient_data_false_no_spend(self):
        """无花费 → 数据不足。"""
        ps = PerformanceSignal(impressions=1000, clicks=100, spend=0.0)
        assert ps.has_sufficient_data is False

    def test_is_positive_roi(self):
        """ROI >= 1.0 为正。"""
        assert PerformanceSignal(roi=1.0).is_positive_roi is True
        assert PerformanceSignal(roi=1.5).is_positive_roi is True
        assert PerformanceSignal(roi=0.99).is_positive_roi is False

    def test_is_high_roi(self):
        """ROI >= 1.5 为高。"""
        assert PerformanceSignal(roi=1.5).is_high_roi is True
        assert PerformanceSignal(roi=2.0).is_high_roi is True
        assert PerformanceSignal(roi=1.49).is_high_roi is False

    def test_cost_per_install(self):
        """CPI = spend / installs。"""
        ps = PerformanceSignal(spend=1000.0, installs=50)
        assert ps.cost_per_install == 20.0

    def test_cost_per_install_zero_installs(self):
        """零安装 → CPI 无穷大。"""
        ps = PerformanceSignal(spend=1000.0, installs=0)
        assert ps.cost_per_install == float("inf")

    def test_revenue_per_install(self):
        """RPI = revenue / installs。"""
        ps = PerformanceSignal(revenue=1600.0, installs=32)
        assert ps.revenue_per_install == 50.0

    def test_revenue_per_install_zero_installs(self):
        """零安装 → RPI 为 0。"""
        ps = PerformanceSignal(revenue=1600.0, installs=0)
        assert ps.revenue_per_install == 0.0

    def test_to_dict(self):
        """to_dict 包含所有关键字段。"""
        ps = PerformanceSignal(
            genome_id="g001",
            creative_id="c001",
            impressions=1000,
            clicks=100,
            installs=10,
            revenue=1500.0,
            spend=1000.0,
            ctr=0.1,
            cvr=0.1,
            roi=1.5,
            period="7d",
        )
        d = ps.to_dict()
        assert d["genome_id"] == "g001"
        assert d["roi"] == 1.5
        assert d["has_sufficient_data"] is True

    def test_from_dict(self):
        """from_dict 正确解析。"""
        d = {
            "genome_id": "g001",
            "creative_id": "c001",
            "impressions": 10000,
            "clicks": 500,
            "installs": 30,
            "revenue": 1600.0,
            "spend": 1000.0,
            "ctr": 0.05,
            "cvr": 0.06,
            "roi": 1.6,
            "period": "7d",
        }
        ps = PerformanceSignal.from_dict(d)
        assert ps.genome_id == "g001"
        assert ps.roi == 1.6
        assert ps.ctr == 0.05

    def test_from_dict_defaults(self):
        """from_dict 缺失字段使用默认值。"""
        ps = PerformanceSignal.from_dict({"genome_id": "g001"})
        assert ps.impressions == 0
        assert ps.clicks == 0
        assert ps.spend == 0.0
        assert ps.period == "7d"

    def test_repr(self):
        """repr 包含关键信息。"""
        ps = PerformanceSignal(genome_id="g001", roi=1.6, ctr=0.05)
        r = repr(ps)
        assert "g001" in r
        assert "1.60" in r


# ═══════════════════════════════════════════════════════════
# 2. Models — FitnessScore
# ═══════════════════════════════════════════════════════════

class TestFitnessScore:
    """FitnessScore 数据模型测试。"""

    def test_create_default(self):
        """默认创建。"""
        fs = FitnessScore()
        assert fs.overall_score == 0.0
        assert fs.rank == 0
        assert fs.evaluated_at != ""

    def test_create_with_values(self):
        """带值创建。"""
        fs = FitnessScore(
            genome_id="g001",
            overall_score=85.0,
            roi_score=100.0,
            ctr_score=100.0,
            cvr_score=60.0,
            revenue_score=80.0,
            rank=1,
        )
        assert fs.genome_id == "g001"
        assert fs.overall_score == 85.0
        assert fs.roi_score == 100.0
        assert fs.ctr_score == 100.0
        assert fs.cvr_score == 60.0
        assert fs.rank == 1

    def test_is_winner(self):
        """overall >= 80 为 winner。"""
        assert FitnessScore(overall_score=80.0).is_winner is True
        assert FitnessScore(overall_score=85.0).is_winner is True
        assert FitnessScore(overall_score=79.99).is_winner is False

    def test_is_average(self):
        """50 <= overall < 80 为 average。"""
        assert FitnessScore(overall_score=50.0).is_average is True
        assert FitnessScore(overall_score=65.0).is_average is True
        assert FitnessScore(overall_score=79.99).is_average is True
        assert FitnessScore(overall_score=80.0).is_average is False
        assert FitnessScore(overall_score=49.99).is_average is False

    def test_is_failed(self):
        """overall < 50 为 failed。"""
        assert FitnessScore(overall_score=49.99).is_failed is True
        assert FitnessScore(overall_score=0.0).is_failed is True
        assert FitnessScore(overall_score=50.0).is_failed is False

    def test_to_dict(self):
        """to_dict 包含所有字段。"""
        fs = FitnessScore(
            genome_id="g001",
            overall_score=82.0,
            roi_score=100.0,
            ctr_score=60.0,
            cvr_score=100.0,
            revenue_score=80.0,
            rank=1,
        )
        d = fs.to_dict()
        assert d["genome_id"] == "g001"
        assert d["overall_score"] == 82.0
        assert d["rank"] == 1

    def test_repr(self):
        """repr 包含关键信息。"""
        fs = FitnessScore(genome_id="g001", overall_score=82.0, rank=1)
        r = repr(fs)
        assert "g001" in r
        assert "82" in r


# ═══════════════════════════════════════════════════════════
# 3. Models — LearningSignal / LearningDirection
# ═══════════════════════════════════════════════════════════

class TestLearningSignal:
    """LearningSignal 数据模型测试。"""

    def test_create_default(self):
        """默认创建。"""
        ls = LearningSignal()
        assert ls.signal_id.startswith("ls_")
        assert ls.direction == LearningDirection.KEEP
        assert ls.confidence == 0.0
        assert ls.insights == []
        assert ls.recommended_mutations == []
        assert ls.consecutive_failures == 0

    def test_create_with_values(self):
        """带值创建。"""
        ls = LearningSignal(
            genome_id="g001",
            direction=LearningDirection.MUTATE,
            confidence=0.85,
            insights=["Low CTR", "Poor conversion"],
            recommended_mutations=["increase_hook_contrast"],
            consecutive_failures=2,
        )
        assert ls.genome_id == "g001"
        assert ls.direction == LearningDirection.MUTATE
        assert ls.confidence == 0.85
        assert len(ls.insights) == 2
        assert len(ls.recommended_mutations) == 1

    def test_should_evolve(self):
        """MUTATE 方向 → should_evolve=True。"""
        assert LearningSignal(direction=LearningDirection.MUTATE).should_evolve is True
        assert LearningSignal(direction=LearningDirection.KEEP).should_evolve is False
        assert LearningSignal(direction=LearningDirection.IMPROVE).should_evolve is False

    def test_should_retire(self):
        """RETIRE 方向 → should_retire=True。"""
        assert LearningSignal(direction=LearningDirection.RETIRE).should_retire is True
        assert LearningSignal(direction=LearningDirection.MUTATE).should_retire is False
        assert LearningSignal(direction=LearningDirection.KEEP).should_retire is False

    def test_to_dict(self):
        """to_dict 包含所有字段。"""
        ls = LearningSignal(
            genome_id="g001",
            direction=LearningDirection.IMPROVE,
            confidence=0.7,
            insights=["insight_1"],
            recommended_mutations=["mut_1"],
            consecutive_failures=0,
        )
        d = ls.to_dict()
        assert d["genome_id"] == "g001"
        assert d["direction"] == "improve"
        assert d["confidence"] == 0.7
        assert d["insights"] == ["insight_1"]

    def test_repr(self):
        """repr 包含关键信息。"""
        ls = LearningSignal(genome_id="g001", direction=LearningDirection.KEEP, confidence=0.9)
        r = repr(ls)
        assert "g001" in r
        assert "keep" in r


class TestLearningDirection:
    """LearningDirection 枚举测试。"""

    def test_values(self):
        assert LearningDirection.IMPROVE.value == "improve"
        assert LearningDirection.KEEP.value == "keep"
        assert LearningDirection.MUTATE.value == "mutate"
        assert LearningDirection.RETIRE.value == "retire"

    def test_is_string_enum(self):
        assert LearningDirection.IMPROVE == "improve"
        assert LearningDirection.KEEP == "keep"


# ═══════════════════════════════════════════════════════════
# 4. Models — EvolutionFeedback
# ═══════════════════════════════════════════════════════════

class TestEvolutionFeedback:
    """EvolutionFeedback 统一反馈输出测试。"""

    def test_create_default(self):
        """默认创建：auto-generated feedback_id。"""
        ef = EvolutionFeedback()
        assert ef.feedback_id.startswith("ef_")
        assert ef.genome_id == ""
        assert ef.fitness is None
        assert ef.learning_signal is None

    def test_create_with_fitness_and_learning(self):
        """带 Fitness 和 LearningSignal 创建。"""
        fitness = FitnessScore(genome_id="g001", overall_score=85.0)
        learning = LearningSignal(
            genome_id="g001",
            direction=LearningDirection.KEEP,
            confidence=0.85,
        )
        ef = EvolutionFeedback(
            genome_id="g001",
            fitness=fitness,
            learning_signal=learning,
        )
        assert ef.genome_id == "g001"
        assert ef.fitness.overall_score == 85.0
        assert ef.learning_signal.direction == LearningDirection.KEEP

    def test_is_winner(self):
        """fitness 为 winner → is_winner=True。"""
        fitness = FitnessScore(overall_score=85.0)
        ef = EvolutionFeedback(fitness=fitness)
        assert ef.is_winner is True

    def test_is_winner_false_no_fitness(self):
        """无 fitness → is_winner=False。"""
        ef = EvolutionFeedback()
        assert ef.is_winner is False

    def test_needs_evolution_mutate(self):
        """MUTATE 方向 → needs_evolution=True。"""
        learning = LearningSignal(direction=LearningDirection.MUTATE)
        ef = EvolutionFeedback(learning_signal=learning)
        assert ef.needs_evolution is True

    def test_needs_evolution_improve(self):
        """IMPROVE 方向 → needs_evolution=True。"""
        learning = LearningSignal(direction=LearningDirection.IMPROVE)
        ef = EvolutionFeedback(learning_signal=learning)
        assert ef.needs_evolution is True

    def test_needs_evolution_false_keep(self):
        """KEEP 方向 → needs_evolution=False。"""
        learning = LearningSignal(direction=LearningDirection.KEEP)
        ef = EvolutionFeedback(learning_signal=learning)
        assert ef.needs_evolution is False

    def test_needs_evolution_false_no_learning(self):
        """无 learning_signal → needs_evolution=False。"""
        ef = EvolutionFeedback()
        assert ef.needs_evolution is False

    def test_to_dict(self):
        """to_dict 包含 fitness 和 learning_signal。"""
        fitness = FitnessScore(genome_id="g001", overall_score=82.0)
        learning = LearningSignal(genome_id="g001", direction=LearningDirection.KEEP, confidence=0.82)
        ef = EvolutionFeedback(genome_id="g001", fitness=fitness, learning_signal=learning)
        d = ef.to_dict()
        assert d["genome_id"] == "g001"
        assert d["fitness"]["overall_score"] == 82.0
        assert d["learning_signal"]["direction"] == "keep"

    def test_to_dict_none_fields(self):
        """None fitness/learning → to_dict 返回 None。"""
        ef = EvolutionFeedback(genome_id="g001")
        d = ef.to_dict()
        assert d["fitness"] is None
        assert d["learning_signal"] is None

    def test_repr(self):
        """repr 包含关键信息。"""
        fitness = FitnessScore(overall_score=82.0)
        ef = EvolutionFeedback(genome_id="g001", fitness=fitness)
        r = repr(ef)
        assert "g001" in r
        assert "82" in r

    def test_repr_no_fitness(self):
        """无 fitness 时 repr 不报错。"""
        ef = EvolutionFeedback(genome_id="g001")
        r = repr(ef)
        assert "g001" in r
        assert "N/A" in r


# ═══════════════════════════════════════════════════════════
# 5. PerformanceCollector
# ═══════════════════════════════════════════════════════════

class TestPerformanceCollector:
    """PerformanceCollector 测试。"""

    def test_collect_basic(self):
        """基本收集：自动计算 CTR/CVR/ROI。"""
        collector = PerformanceCollector()
        result = collector.collect(_make_exp_result())

        assert isinstance(result, PerformanceSignal)
        assert result.genome_id == "g001"
        # CTR = 500/10000 = 0.05
        assert result.ctr == pytest.approx(0.05, abs=0.001)
        # CVR = 30/500 = 0.06
        assert result.cvr == pytest.approx(0.06, abs=0.001)
        # ROI = 1600/1000 = 1.6
        assert result.roi == pytest.approx(1.6, abs=0.001)

    def test_collect_preserves_explicit_ctr_cvr_roi(self):
        """显式传入 CTR/CVR/ROI 不被覆盖。"""
        collector = PerformanceCollector()
        result = collector.collect({
            "genome_id": "g001",
            "impressions": 10000,
            "clicks": 500,
            "installs": 30,
            "revenue": 1600.0,
            "spend": 1000.0,
            "ctr": 0.03,
            "cvr": 0.04,
            "roi": 1.2,
        })
        assert result.ctr == 0.03
        assert result.cvr == 0.04
        assert result.roi == 1.2

    def test_collect_zero_impressions(self):
        """零曝光不崩溃。"""
        collector = PerformanceCollector()
        result = collector.collect({
            "genome_id": "g001",
            "impressions": 0,
            "clicks": 0,
            "installs": 0,
            "revenue": 0.0,
            "spend": 0.0,
        })
        assert result.ctr == 0.0
        assert result.cvr == 0.0
        assert result.roi == 0.0

    def test_collect_zero_spend(self):
        """零花费 → ROI 不计算。"""
        collector = PerformanceCollector()
        result = collector.collect({
            "genome_id": "g001",
            "impressions": 10000,
            "clicks": 500,
            "installs": 30,
            "revenue": 1600.0,
            "spend": 0.0,
        })
        assert result.roi == 0.0

    def test_collect_batch(self):
        """批量收集。"""
        collector = PerformanceCollector()
        results = collector.collect_batch([
            _make_exp_result(genome_id="g001"),
            _make_exp_result(genome_id="g002"),
        ])
        assert len(results) == 2
        assert results[0].genome_id == "g001"
        assert results[1].genome_id == "g002"

    def test_collected_count(self):
        """collected_count 正确递增。"""
        collector = PerformanceCollector()
        assert collector.collected_count == 0
        collector.collect(_make_exp_result())
        assert collector.collected_count == 1
        collector.collect(_make_exp_result())
        assert collector.collected_count == 2

    def test_reset(self):
        """reset 清零计数。"""
        collector = PerformanceCollector()
        collector.collect(_make_exp_result())
        collector.reset()
        assert collector.collected_count == 0

    def test_roi_calculation_high_performer(self):
        """高 ROI 素材正确计算。"""
        collector = PerformanceCollector()
        result = collector.collect(_make_high_perf())
        # ROI = 10000/5000 = 2.0
        assert result.roi == pytest.approx(2.0, abs=0.01)
        # CTR = 2500/50000 = 0.05
        assert result.ctr == pytest.approx(0.05, abs=0.001)

    def test_roi_calculation_low_performer(self):
        """低 ROI 素材正确计算。"""
        collector = PerformanceCollector()
        result = collector.collect(_make_low_perf())
        assert result.roi == pytest.approx(0.5, abs=0.01)


# ═══════════════════════════════════════════════════════════
# 6. Evaluator
# ═══════════════════════════════════════════════════════════

class TestEvaluator:
    """Evaluator 测试。"""

    def test_evaluate_high_roi(self):
        """高 ROI → ROI score = 100。"""
        evaluator = Evaluator()
        signal = PerformanceSignal(
            genome_id="g001",
            roi=1.5,
            ctr=0.05,
            cvr=0.06,
            revenue=5000.0,
            impressions=10000,
            clicks=500,
            spend=1000.0,
        )
        score = evaluator.evaluate(signal)
        assert score.roi_score == 100.0
        # overall = 100*0.5 + 100*0.3 + 100*0.2 = 100
        assert score.overall_score == 100.0

    def test_evaluate_medium_roi(self):
        """中等 ROI → ROI score = 60。"""
        evaluator = Evaluator()
        signal = PerformanceSignal(
            genome_id="g001",
            roi=1.2,
            ctr=0.02,
            cvr=0.03,
            revenue=1500.0,
            impressions=10000,
            clicks=500,
            spend=1000.0,
        )
        score = evaluator.evaluate(signal)
        assert score.roi_score == 60.0
        # ROI=60, CTR=60, CVR=60 → overall = 60*0.5+60*0.3+60*0.2 = 60
        assert score.overall_score == 60.0

    def test_evaluate_low_roi(self):
        """低 ROI → ROI score = 20。"""
        evaluator = Evaluator()
        signal = PerformanceSignal(
            genome_id="g001",
            roi=0.5,
            ctr=0.005,
            cvr=0.01,
            revenue=500.0,
            impressions=10000,
            clicks=500,
            spend=1000.0,
        )
        score = evaluator.evaluate(signal)
        assert score.roi_score == 20.0
        assert score.ctr_score == 20.0
        assert score.cvr_score == 20.0
        # overall = 20*0.5+20*0.3+20*0.2 = 20
        assert score.overall_score == 20.0

    def test_evaluate_high_ctr(self):
        """CTR >= 3% → CTR score = 100。"""
        evaluator = Evaluator()
        signal = PerformanceSignal(
            genome_id="g001",
            roi=1.0,
            ctr=0.03,
            cvr=0.05,
            revenue=5000.0,
            impressions=10000,
            clicks=500,
            spend=1000.0,
        )
        score = evaluator.evaluate(signal)
        assert score.ctr_score == 100.0

    def test_evaluate_high_cvr(self):
        """CVR >= 5% → CVR score = 100。"""
        evaluator = Evaluator()
        signal = PerformanceSignal(
            genome_id="g001",
            roi=1.0,
            ctr=0.05,
            cvr=0.05,
            revenue=5000.0,
            impressions=10000,
            clicks=500,
            spend=1000.0,
        )
        score = evaluator.evaluate(signal)
        assert score.cvr_score == 100.0

    def test_evaluate_revenue_score_with_sufficient_data(self):
        """有收入 + 足够数据 → revenue_score = 80。"""
        evaluator = Evaluator()
        signal = PerformanceSignal(
            genome_id="g001",
            revenue=5000.0,
            impressions=10000,
            clicks=500,
            spend=1000.0,
        )
        score = evaluator.evaluate(signal)
        assert score.revenue_score == 80.0

    def test_evaluate_revenue_score_no_revenue(self):
        """无收入 → revenue_score = 40。"""
        evaluator = Evaluator()
        signal = PerformanceSignal(
            genome_id="g001",
            revenue=0.0,
            impressions=10000,
            clicks=500,
            spend=1000.0,
        )
        score = evaluator.evaluate(signal)
        assert score.revenue_score == 40.0

    def test_evaluate_batch(self):
        """批量评估。"""
        evaluator = Evaluator()
        signals = [
            PerformanceSignal(genome_id="g001", roi=1.5, ctr=0.05, cvr=0.06, revenue=5000, impressions=10000, clicks=500, spend=1000),
            PerformanceSignal(genome_id="g002", roi=1.2, ctr=0.02, cvr=0.03, revenue=1500, impressions=10000, clicks=500, spend=1000),
        ]
        scores = evaluator.evaluate_batch(signals)
        assert len(scores) == 2
        assert scores[0].genome_id == "g001"
        assert scores[1].genome_id == "g002"

    def test_ranking(self):
        """排名按 overall_score 降序。"""
        evaluator = Evaluator()
        evaluator.evaluate(_make_high_perf_signal("g_winner"))
        evaluator.evaluate(_make_medium_perf_signal("g_avg"))
        evaluator.evaluate(_make_low_perf_signal("g_low"))

        assert evaluator.get_rank("g_winner") == 1
        assert evaluator.get_rank("g_avg") == 2
        assert evaluator.get_rank("g_low") == 3

    def test_get_rank_unknown(self):
        """未知 genome → rank=0。"""
        evaluator = Evaluator()
        assert evaluator.get_rank("unknown") == 0

    def test_get_top(self):
        """get_top 返回前 N 名。"""
        evaluator = Evaluator()
        for i in range(5):
            evaluator.evaluate(PerformanceSignal(
                genome_id=f"g{i}",
                roi=1.0 + i * 0.2,
                ctr=0.05,
                cvr=0.06,
                revenue=5000,
                impressions=10000,
                clicks=500,
                spend=1000,
            ))
        top3 = evaluator.get_top(3)
        assert len(top3) == 3
        assert top3[0].rank == 1
        assert top3[1].rank == 2
        assert top3[2].rank == 3

    def test_evaluate_count(self):
        """evaluate_count 正确递增。"""
        evaluator = Evaluator()
        evaluator.evaluate(_make_high_perf_signal())
        evaluator.evaluate(_make_medium_perf_signal())
        assert evaluator.evaluate_count == 2

    def test_get_stats(self):
        """get_stats 返回统计信息。"""
        evaluator = Evaluator()
        evaluator.evaluate(_make_high_perf_signal("g_winner"))
        stats = evaluator.get_stats()
        assert stats["evaluate_count"] == 1
        assert stats["total_genomes"] == 1
        assert stats["top_genome"] == "g_winner"

    def test_reset(self):
        """reset 清空所有数据。"""
        evaluator = Evaluator()
        evaluator.evaluate(_make_high_perf_signal())
        evaluator.reset()
        assert evaluator.evaluate_count == 0
        assert evaluator.get_stats()["total_genomes"] == 0


# ═══════════════════════════════════════════════════════════
# 7. LearningEngine
# ═══════════════════════════════════════════════════════════

class TestLearningEngine:
    """LearningEngine 测试。"""

    def test_generate_winner(self):
        """Winner (fitness >= 80) → KEEP。"""
        engine = LearningEngine()
        fitness = FitnessScore(genome_id="g001", overall_score=85.0)
        signal = engine.generate(fitness)

        assert signal.direction == LearningDirection.KEEP
        assert signal.confidence > 0.8
        assert "Keep current gene configuration" in signal.recommended_mutations

    def test_generate_average(self):
        """Average (50-80) → IMPROVE。"""
        engine = LearningEngine()
        fitness = FitnessScore(genome_id="g001", overall_score=65.0, roi_score=60.0, ctr_score=60.0, cvr_score=60.0)
        signal = engine.generate(fitness)

        assert signal.direction == LearningDirection.IMPROVE
        assert signal.confidence > 0.5
        assert any("improve" in m.lower() or "increase" in m.lower() or "optimize" in m.lower()
                   for m in signal.recommended_mutations)

    def test_generate_failed(self):
        """Failed (fitness < 50) → MUTATE。"""
        engine = LearningEngine()
        fitness = FitnessScore(genome_id="g001", overall_score=30.0, ctr_score=20.0, cvr_score=20.0)
        signal = engine.generate(fitness)

        assert signal.direction == LearningDirection.MUTATE
        assert signal.consecutive_failures == 1

    def test_generate_failed_with_performance(self):
        """带性能数据生成：包含洞察。"""
        engine = LearningEngine()
        fitness = FitnessScore(genome_id="g001", overall_score=30.0, roi_score=20.0, ctr_score=20.0, cvr_score=20.0)
        perf = PerformanceSignal(roi=0.5, ctr=0.005, cvr=0.01, revenue=500.0, impressions=10000, clicks=500, spend=1000.0)
        signal = engine.generate(fitness, perf)

        assert signal.direction == LearningDirection.MUTATE
        assert len(signal.insights) > 0
        assert len(signal.recommended_mutations) > 0

    def test_consecutive_failures_retire(self):
        """连续 3 次 MUTATE → 触发 RETIRE 逻辑。"""
        engine = LearningEngine()
        fitness = FitnessScore(genome_id="g001", overall_score=30.0, ctr_score=20.0, cvr_score=20.0)

        engine.generate(fitness)  # failure 1
        engine.generate(fitness)  # failure 2
        signal = engine.generate(fitness)  # failure 3

        assert signal.consecutive_failures >= 3

    def test_consecutive_failures_reset_on_keep(self):
        """KEEP 方向重置失败计数。"""
        engine = LearningEngine()
        fail_fitness = FitnessScore(genome_id="g001", overall_score=30.0, ctr_score=20.0, cvr_score=20.0)
        win_fitness = FitnessScore(genome_id="g001", overall_score=85.0)

        engine.generate(fail_fitness)  # failure 1
        engine.generate(win_fitness)   # KEEP → reset
        assert engine.get_consecutive_failures("g001") == 0

    def test_consecutive_failures_reset_on_improve(self):
        """IMPROVE 方向重置失败计数。"""
        engine = LearningEngine()
        fail_fitness = FitnessScore(genome_id="g001", overall_score=30.0, ctr_score=20.0, cvr_score=20.0)
        avg_fitness = FitnessScore(genome_id="g001", overall_score=65.0)

        engine.generate(fail_fitness)  # failure 1
        engine.generate(avg_fitness)   # IMPROVE → reset
        assert engine.get_consecutive_failures("g001") == 0

    def test_get_consecutive_failures_unknown(self):
        """未知 genome → 0。"""
        engine = LearningEngine()
        assert engine.get_consecutive_failures("unknown") == 0

    def test_generate_batch(self):
        """批量生成学习信号。"""
        engine = LearningEngine()
        scores = [
            FitnessScore(genome_id="g001", overall_score=85.0),
            FitnessScore(genome_id="g002", overall_score=65.0),
            FitnessScore(genome_id="g003", overall_score=30.0, ctr_score=20.0, cvr_score=20.0),
        ]
        signals = engine.generate_batch(scores)
        assert len(signals) == 3
        assert signals[0].direction == LearningDirection.KEEP
        assert signals[1].direction == LearningDirection.IMPROVE
        assert signals[2].direction == LearningDirection.MUTATE

    def test_confidence_winner(self):
        """Winner → confidence = overall_score / 100。"""
        engine = LearningEngine()
        fitness = FitnessScore(overall_score=85.0)
        signal = engine.generate(fitness)
        assert signal.confidence == pytest.approx(0.85)

    def test_confidence_average(self):
        """Average → confidence = 0.5 + 0.3*(score-50)/30。"""
        engine = LearningEngine()
        fitness = FitnessScore(overall_score=65.0)
        signal = engine.generate(fitness)
        expected = 0.5 + 0.3 * 15 / 30  # 0.65
        assert signal.confidence == pytest.approx(expected, abs=0.01)

    def test_confidence_failed(self):
        """Failed → confidence = max(0.1, 0.3 + 0.2*score/50)。"""
        engine = LearningEngine()
        fitness = FitnessScore(overall_score=30.0)
        signal = engine.generate(fitness)
        expected = max(0.1, 0.3 + 0.2 * 30 / 50)  # 0.42
        assert signal.confidence == pytest.approx(expected, abs=0.01)

    def test_confidence_very_low(self):
        """Very low score → confidence >= 0.1。"""
        engine = LearningEngine()
        fitness = FitnessScore(overall_score=0.0)
        signal = engine.generate(fitness)
        assert signal.confidence >= 0.1

    def test_generate_count(self):
        """generate_count 正确递增。"""
        engine = LearningEngine()
        engine.generate(FitnessScore(overall_score=85.0))
        engine.generate(FitnessScore(overall_score=65.0))
        assert engine.generate_count == 2

    def test_get_stats(self):
        """get_stats 返回统计信息。"""
        engine = LearningEngine()
        engine.generate(FitnessScore(genome_id="g001", overall_score=30.0, ctr_score=20.0, cvr_score=20.0))
        stats = engine.get_stats()
        assert stats["generate_count"] == 1
        assert stats["tracked_genomes"] == 1
        assert "g001" in stats["failure_counts"]

    def test_reset(self):
        """reset 清空所有数据。"""
        engine = LearningEngine()
        engine.generate(FitnessScore(genome_id="g001", overall_score=30.0, ctr_score=20.0, cvr_score=20.0))
        engine.reset()
        assert engine.generate_count == 0
        assert engine.get_consecutive_failures("g001") == 0

    def test_insights_winner_with_performance(self):
        """Winner + 正 ROI → 包含对应洞察。"""
        engine = LearningEngine()
        fitness = FitnessScore(genome_id="g001", overall_score=85.0, roi_score=100.0, ctr_score=100.0, cvr_score=100.0)
        perf = PerformanceSignal(roi=1.8, ctr=0.05, cvr=0.06, revenue=5000, impressions=10000, clicks=500, spend=1000.0)
        signal = engine.generate(fitness, perf)
        assert "Strong ROI performance" in signal.insights
        assert "High CTR engagement" in signal.insights
        assert "Excellent conversion rate" in signal.insights
        assert "Positive ROI achieved" in signal.insights

    def test_insights_no_insights_fallback(self):
        """无特定洞察时使用 fallback。"""
        engine = LearningEngine()
        fitness = FitnessScore(genome_id="g001", overall_score=65.0, roi_score=60.0, ctr_score=60.0, cvr_score=60.0)
        signal = engine.generate(fitness)
        assert "Moderate performance across metrics" in signal.insights

    def test_mutations_keep(self):
        """KEEP 方向 → 保留当前配置。"""
        engine = LearningEngine()
        fitness = FitnessScore(overall_score=85.0)
        signal = engine.generate(fitness)
        assert "Keep current gene configuration" in signal.recommended_mutations

    def test_mutations_improve_with_low_roi(self):
        """IMPROVE + 低 ROI → 包含 improve_reward_reveal_curve。"""
        engine = LearningEngine()
        fitness = FitnessScore(genome_id="g001", overall_score=65.0, roi_score=60.0, ctr_score=80.0, cvr_score=80.0)
        signal = engine.generate(fitness)
        assert "improve_reward_reveal_curve" in signal.recommended_mutations

    def test_mutations_improve_with_low_ctr(self):
        """IMPROVE + 低 CTR → 包含 increase_hook_contrast。"""
        engine = LearningEngine()
        fitness = FitnessScore(genome_id="g001", overall_score=65.0, roi_score=80.0, ctr_score=60.0, cvr_score=80.0)
        signal = engine.generate(fitness)
        assert "increase_hook_contrast" in signal.recommended_mutations

    def test_mutations_mutate_default(self):
        """MUTATE → 默认突变列表。"""
        engine = LearningEngine()
        fitness = FitnessScore(genome_id="g001", overall_score=30.0, ctr_score=20.0, cvr_score=20.0)
        signal = engine.generate(fitness)
        assert "increase_hook_contrast" in signal.recommended_mutations
        assert "increase_transition_speed" in signal.recommended_mutations
        assert "optimize_reward_reveal_curve" in signal.recommended_mutations


# ═══════════════════════════════════════════════════════════
# 8. FeedbackEngine
# ═══════════════════════════════════════════════════════════

class TestFeedbackEngine:
    """FeedbackEngine 统一入口测试。"""

    def test_process_high_performer(self):
        """高表现素材 → 完整反馈链路。"""
        engine = FeedbackEngine()
        feedback = engine.process(_make_high_perf())

        assert isinstance(feedback, EvolutionFeedback)
        assert feedback.genome_id == "g_winner"
        assert feedback.fitness is not None
        assert feedback.learning_signal is not None
        assert feedback.fitness.is_winner
        assert feedback.learning_signal.direction == LearningDirection.KEEP

    def test_process_medium_performer(self):
        """中等表现素材 → IMPROVE。"""
        engine = FeedbackEngine()
        feedback = engine.process(_make_medium_perf())

        assert feedback.learning_signal.direction == LearningDirection.IMPROVE

    def test_process_low_performer(self):
        """低表现素材 → MUTATE。"""
        engine = FeedbackEngine()
        feedback = engine.process(_make_low_perf())

        assert feedback.learning_signal.direction == LearningDirection.MUTATE

    def test_process_batch(self):
        """批量处理。"""
        engine = FeedbackEngine()
        results = [
            _make_high_perf("g_w"),
            _make_medium_perf("g_a"),
            _make_low_perf("g_l"),
        ]
        feedbacks = engine.process_batch(results)

        assert len(feedbacks) == 3
        assert feedbacks[0].is_winner
        assert feedbacks[1].learning_signal.direction == LearningDirection.IMPROVE
        assert feedbacks[2].learning_signal.direction == LearningDirection.MUTATE

    def test_collect_and_evaluate(self):
        """仅收集+评估，不生成学习信号。"""
        engine = FeedbackEngine()
        results = [_make_high_perf(), _make_medium_perf()]
        scores = engine.collect_and_evaluate(results)

        assert len(scores) == 2
        assert all(isinstance(s, FitnessScore) for s in scores)

    def test_evaluate_only(self):
        """仅评估已有 PerformanceSignal。"""
        engine = FeedbackEngine()
        signals = [
            PerformanceSignal(genome_id="g001", roi=1.5, ctr=0.05, cvr=0.06, revenue=5000, impressions=10000, clicks=500, spend=1000),
            PerformanceSignal(genome_id="g002", roi=1.2, ctr=0.02, cvr=0.03, revenue=1500, impressions=10000, clicks=500, spend=1000),
        ]
        scores = engine.evaluate_only(signals)
        assert len(scores) == 2

    def test_get_learning_signals(self):
        """提取所有学习信号。"""
        engine = FeedbackEngine()
        feedbacks = engine.process_batch([
            _make_high_perf("g_w"),
            _make_low_perf("g_l"),
        ])
        signals = engine.get_learning_signals(feedbacks)
        assert len(signals) == 2

    def test_get_evolution_candidates(self):
        """获取需要进化的反馈（MUTATE/IMPROVE）。"""
        engine = FeedbackEngine()
        feedbacks = engine.process_batch([
            _make_high_perf("g_w"),
            _make_medium_perf("g_a"),
            _make_low_perf("g_l"),
        ])
        candidates = engine.get_evolution_candidates(feedbacks)
        # g_w = KEEP, g_a = IMPROVE, g_l = MUTATE → 2 candidates
        assert len(candidates) == 2
        assert all(c.needs_evolution for c in candidates)

    def test_get_retirement_candidates(self):
        """RETIRE 方向 → 退役候选。"""
        engine = FeedbackEngine()
        # 手动构造一个 RETIRE 的反馈
        learning = LearningSignal(
            genome_id="g_r",
            direction=LearningDirection.RETIRE,
            confidence=0.9,
            consecutive_failures=3,
        )
        ef = EvolutionFeedback(genome_id="g_r", learning_signal=learning)
        candidates = engine.get_retirement_candidates([ef])
        assert len(candidates) == 1
        assert candidates[0].genome_id == "g_r"

    def test_get_retirement_candidates_none(self):
        """无 RETIRE 方向时返回空。"""
        engine = FeedbackEngine()
        feedbacks = engine.process_batch([_make_high_perf()])
        candidates = engine.get_retirement_candidates(feedbacks)
        assert len(candidates) == 0

    def test_get_winners(self):
        """获取 Winner 反馈。"""
        engine = FeedbackEngine()
        feedbacks = engine.process_batch([
            _make_high_perf("g_w"),
            _make_low_perf("g_l"),
        ])
        winners = engine.get_winners(feedbacks)
        assert len(winners) == 1
        assert winners[0].genome_id == "g_w"

    def test_process_count(self):
        """process_count 正确递增。"""
        engine = FeedbackEngine()
        engine.process(_make_high_perf())
        engine.process(_make_medium_perf())
        assert engine.process_count == 2

    def test_get_stats(self):
        """get_stats 返回完整统计。"""
        engine = FeedbackEngine()
        engine.process(_make_high_perf("g_w"))
        engine.process(_make_medium_perf("g_a"))
        stats = engine.get_stats()
        assert stats["process_count"] == 2
        assert stats["collected"] == 2
        assert stats["evaluated"] == 2
        assert stats["learning_generated"] == 2
        assert stats["top_genome"] == "g_w"

    def test_reset(self):
        """reset 清空所有子引擎。"""
        engine = FeedbackEngine()
        engine.process(_make_high_perf())
        engine.reset()
        assert engine.process_count == 0
        assert engine.get_stats()["collected"] == 0

    def test_dependency_injection(self):
        """支持自定义子引擎注入。"""
        collector = PerformanceCollector()
        evaluator = Evaluator()
        learner = LearningEngine()
        engine = FeedbackEngine(
            collector=collector,
            evaluator=evaluator,
            learner=learner,
        )
        feedback = engine.process(_make_high_perf())
        assert feedback.is_winner


# ═══════════════════════════════════════════════════════════
# 9. Controller Integration
# ═══════════════════════════════════════════════════════════

class TestControllerFeedbackIntegration:
    """Controller receive_feedback / receive_and_evolve 测试。"""

    @pytest.fixture
    def controller(self):
        """创建带 Mock 引擎的 Controller。"""
        from market_ops.creative_vision_runtime.intelligence.engine import (
            VisionIntelligenceEngine,
        )
        from market_ops.creative_vision_runtime.autonomous_controller.controller import (
            AutonomousCreativeController,
        )
        from market_ops.creative_vision_runtime.autonomous_controller.models import (
            ControllerConfig,
        )

        mock_intelligence = MagicMock(spec=VisionIntelligenceEngine)
        mock_intelligence.analyze_batch.return_value = {}
        mock_intelligence.extract_winner_dna.return_value = None

        config = ControllerConfig(max_cycles=1)
        return AutonomousCreativeController(
            intelligence_engine=mock_intelligence,
            config=config,
        )

    def test_receive_feedback(self, controller):
        """receive_feedback 返回 EvolutionFeedback 列表。"""
        results = [
            _make_high_perf("g_w"),
            _make_low_perf("g_l"),
        ]
        feedbacks = controller.receive_feedback(results)

        assert len(feedbacks) == 2
        assert all(isinstance(f, EvolutionFeedback) for f in feedbacks)
        assert feedbacks[0].is_winner
        assert feedbacks[1].learning_signal.direction == LearningDirection.MUTATE

    def test_receive_and_evolve(self, controller):
        """receive_and_evolve 返回反馈 + 候选 + 循环。"""
        results = [
            _make_high_perf("g_w"),
            _make_medium_perf("g_a"),
            _make_low_perf("g_l"),
        ]
        output = controller.receive_and_evolve(
            experiment_results=results,
            asset_ids=["a1", "a2"],
            genomes={"a1": {"genome_id": "g_w"}, "a2": {"genome_id": "g_a"}},
        )

        assert "feedbacks" in output
        assert "evolution_candidates" in output
        assert "cycles" in output
        assert len(output["feedbacks"]) == 3
        # g_a (IMPROVE) + g_l (MUTATE) → 2 candidates
        assert len(output["evolution_candidates"]) == 2
        assert len(output["cycles"]) == 2

    def test_receive_and_evolve_no_candidates(self, controller):
        """所有素材都是 Winner → 无进化候选。"""
        results = [_make_high_perf("g_w1"), _make_high_perf("g_w2")]
        output = controller.receive_and_evolve(
            experiment_results=results,
            asset_ids=["a1"],
            genomes={"a1": {"genome_id": "g_w1"}},
        )

        assert len(output["feedbacks"]) == 2
        assert len(output["evolution_candidates"]) == 0
        assert len(output["cycles"]) == 0

    def test_feedback_engine_property(self, controller):
        """feedback_engine 属性可访问。"""
        assert isinstance(controller.feedback_engine, FeedbackEngine)


# ═══════════════════════════════════════════════════════════
# 10. Full Pipeline
# ═══════════════════════════════════════════════════════════

class TestFullPipeline:
    """完整链路：Performance → Fitness → Learning → Controller。"""

    def test_full_pipeline_high_performer(self):
        """高表现素材 → KEEP。"""
        engine = FeedbackEngine()
        feedback = engine.process(_make_high_perf())

        assert feedback.is_winner
        assert feedback.learning_signal.direction == LearningDirection.KEEP
        assert feedback.learning_signal.confidence > 0.8

    def test_full_pipeline_medium_performer(self):
        """中等表现素材 → IMPROVE。"""
        engine = FeedbackEngine()
        feedback = engine.process(_make_medium_perf())

        assert not feedback.is_winner
        assert feedback.learning_signal.direction == LearningDirection.IMPROVE
        assert len(feedback.learning_signal.recommended_mutations) > 0

    def test_full_pipeline_low_performer(self):
        """低表现素材 → MUTATE。"""
        engine = FeedbackEngine()
        feedback = engine.process(_make_low_perf())

        assert feedback.learning_signal.direction == LearningDirection.MUTATE
        assert feedback.learning_signal.consecutive_failures == 1

    def test_pipeline_ranking(self):
        """多素材 → 正确排名。"""
        engine = FeedbackEngine()
        feedbacks = engine.process_batch([
            _make_high_perf("g_w"),
            _make_medium_perf("g_a"),
            _make_low_perf("g_l"),
        ])

        # 验证排名
        scores = [f.fitness for f in feedbacks]
        for s in scores:
            assert s.rank > 0
        # 排名唯一
        ranks = [s.rank for s in scores]
        assert len(ranks) == len(set(ranks))

    def test_pipeline_feedback_evolve_connection(self):
        """验证反馈 → 进化候选的连接。"""
        engine = FeedbackEngine()
        feedbacks = engine.process_batch([
            _make_high_perf("g_w"),
            _make_medium_perf("g_a"),
            _make_low_perf("g_l"),
        ])

        candidates = engine.get_evolution_candidates(feedbacks)
        # IMPROVE + MUTATE → 2 candidates
        assert len(candidates) == 2

        winners = engine.get_winners(feedbacks)
        assert len(winners) == 1

    def test_pipeline_repeated_failures_lead_to_more_mutations(self):
        """连续失败 → 突变推荐增加。"""
        engine = LearningEngine()
        low_fitness = FitnessScore(genome_id="g001", overall_score=30.0, ctr_score=20.0, cvr_score=20.0)

        s1 = engine.generate(low_fitness)
        s2 = engine.generate(low_fitness)
        s3 = engine.generate(low_fitness)

        assert s3.consecutive_failures >= 3
        # 连续失败后仍有突变推荐
        assert len(s3.recommended_mutations) > 0


# ═══════════════════════════════════════════════════════════
# 11. Package Exports
# ═══════════════════════════════════════════════════════════

def test_package_exports():
    """__init__.py 导出所有核心类。"""
    import market_ops.creative_vision_runtime.autonomous_controller.feedback as fb

    assert hasattr(fb, "PerformanceSignal")
    assert hasattr(fb, "FitnessScore")
    assert hasattr(fb, "LearningSignal")
    assert hasattr(fb, "EvolutionFeedback")
    assert hasattr(fb, "LearningDirection")
    assert hasattr(fb, "PerformanceCollector")
    assert hasattr(fb, "Evaluator")
    assert hasattr(fb, "LearningEngine")
    assert hasattr(fb, "FeedbackEngine")


# ═══════════════════════════════════════════════════════════
# Helpers for Evaluator tests
# ═══════════════════════════════════════════════════════════

def _make_high_perf_signal(genome_id: str = "g001") -> PerformanceSignal:
    return PerformanceSignal(
        genome_id=genome_id,
        roi=1.5,
        ctr=0.05,
        cvr=0.06,
        revenue=5000.0,
        impressions=10000,
        clicks=500,
        spend=1000.0,
    )


def _make_medium_perf_signal(genome_id: str = "g001") -> PerformanceSignal:
    return PerformanceSignal(
        genome_id=genome_id,
        roi=1.2,
        ctr=0.02,
        cvr=0.03,
        revenue=1500.0,
        impressions=10000,
        clicks=500,
        spend=1000.0,
    )


def _make_low_perf_signal(genome_id: str = "g001") -> PerformanceSignal:
    return PerformanceSignal(
        genome_id=genome_id,
        roi=0.5,
        ctr=0.005,
        cvr=0.01,
        revenue=500.0,
        impressions=10000,
        clicks=500,
        spend=1000.0,
    )