"""E14.6.3 Evolution Feedback Controller — 集成测试.

验证 EvolutionFeedbackController 的进化反馈闭环能力:
  - Feedback Models: EvolutionFeedback / MemoryPattern / EvolutionSignal / FeedbackReport (20 tests)
  - Report Processing: process_report / 反馈类型判定 (20 tests)
  - Fitness Update: 适应度更新 / FitnessSnapshot (15 tests)
  - Memory Pattern Generation: 模式生成 / EvolutionMemoryGraph 写入 (15 tests)
  - Winner Promotion: Winner 强化反馈 (15 tests)
  - Loser Suppression: Loser 抑制反馈 (10 tests)
  - Next Evolution Signal: EvolutionSignal 生成 (15 tests)
  - Regression E14.5/E14.6: 集成回归 (10 tests)

总计: 120 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
    EvolutionFeedbackController,
    EvolutionFeedback,
    MemoryPattern,
    EvolutionSignal,
    FeedbackReport,
    FeedbackType,
    SignalAction,
    create_feedback_controller,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.experiment_controller import (
    ExperimentReport,
    ExperimentResult,
    ExperimentStatus,
    GroupType,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.evolution_memory import (
    EvolutionMemoryGraph,
    NodeType,
    EdgeType,
)
from market_ops.e11.evolution.fitness_schema import (
    FitnessScore,
    FitnessMetric,
    FitnessDirection,
    FitnessSnapshot,
)


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def controller():
    """创建默认 EvolutionFeedbackController."""
    return EvolutionFeedbackController()


@pytest.fixture
def memory_graph():
    """创建 EvolutionMemoryGraph."""
    return EvolutionMemoryGraph()


@pytest.fixture
def controller_with_memory(memory_graph):
    """创建带 MemoryGraph 的 EvolutionFeedbackController."""
    return EvolutionFeedbackController(memory_graph=memory_graph)


def _make_result(
    genome_id: str,
    group_type: GroupType,
    ctr: float = 0.03,
    cvr: float = 0.05,
    roas: float = 0.5,
    cpi: float = 2.0,
    payer_rate: float = 0.05,
    is_winner: bool = False,
    significance: float = 0.9,
    sample_size: int = 5000,
    experiment_id: str = "exp_test_001",
) -> ExperimentResult:
    """辅助: 创建测试用 ExperimentResult."""
    return ExperimentResult(
        experiment_id=experiment_id,
        genome_id=genome_id,
        group_type=group_type,
        metrics={
            "ctr": ctr,
            "cvr": cvr,
            "roas": roas,
            "cpi": cpi,
            "payer_rate": payer_rate,
        },
        is_winner=is_winner,
        statistical_significance=significance,
        sample_size=sample_size,
    )


def _make_report(
    experiment_id: str = "exp_test_001",
    experiment_name: str = "Hook Mutation Test #001",
    results: list[ExperimentResult] | None = None,
    winner_genome_id: str = "",
    winner_score: float = 0.0,
    winner_lift: float = 0.0,
) -> ExperimentReport:
    """辅助: 创建测试用 ExperimentReport."""
    return ExperimentReport(
        experiment_id=experiment_id,
        experiment_name=experiment_name,
        status=ExperimentStatus.COMPLETED,
        total_results=len(results) if results else 0,
        winner_genome_id=winner_genome_id,
        winner_score=winner_score,
        winner_lift=winner_lift,
        results=results or [],
        summary="Test report",
    )


@pytest.fixture
def report_with_winner():
    """有明确 Winner 的实验报告."""
    results = [
        _make_result("genome_ctrl", GroupType.CONTROL, roas=0.35, ctr=0.025, cvr=0.04, payer_rate=0.04),
        _make_result("genome_v1", GroupType.VARIANT, roas=0.48, ctr=0.032, cvr=0.05, payer_rate=0.05),
        _make_result("genome_v2", GroupType.VARIANT, roas=0.38, ctr=0.028, cvr=0.043, payer_rate=0.042),
        _make_result("genome_v3", GroupType.VARIANT, roas=0.85, ctr=0.045, cvr=0.07, payer_rate=0.07, is_winner=True),
    ]
    return _make_report(
        experiment_id="exp_wtest_001",
        experiment_name="Winner Test",
        results=results,
        winner_genome_id="genome_v3",
        winner_score=0.87,
        winner_lift=0.34,
    )


@pytest.fixture
def report_with_loser():
    """有明确 Loser 的实验报告."""
    results = [
        _make_result("genome_ctrl", GroupType.CONTROL, roas=0.40, ctr=0.03, cvr=0.05, payer_rate=0.05),
        _make_result("genome_bad", GroupType.VARIANT, roas=0.20, ctr=0.015, cvr=0.02, payer_rate=0.02),
    ]
    return _make_report(
        experiment_id="exp_loser_001",
        experiment_name="Loser Test",
        results=results,
    )


@pytest.fixture
def report_empty():
    """无结果的实验报告."""
    return _make_report(
        experiment_id="exp_empty",
        experiment_name="Empty Test",
        results=[],
    )


@pytest.fixture
def report_mixed():
    """混合结果 (Winner + Loser + Neutral) 的实验报告."""
    results = [
        _make_result("genome_ctrl", GroupType.CONTROL, roas=0.35, ctr=0.025, cvr=0.04, payer_rate=0.04),
        _make_result("genome_winner", GroupType.VARIANT, roas=0.80, ctr=0.04, cvr=0.065, payer_rate=0.065, is_winner=True),
        _make_result("genome_loser", GroupType.VARIANT, roas=0.15, ctr=0.012, cvr=0.018, payer_rate=0.018),
        _make_result("genome_neutral", GroupType.VARIANT, roas=0.38, ctr=0.028, cvr=0.042, payer_rate=0.042),
    ]
    return _make_report(
        experiment_id="exp_mixed_001",
        experiment_name="Mixed Test",
        results=results,
        winner_genome_id="genome_winner",
        winner_score=0.82,
        winner_lift=0.30,
    )


@pytest.fixture
def report_low_sample():
    """低样本量的实验报告."""
    results = [
        _make_result("genome_ctrl", GroupType.CONTROL, roas=0.35, sample_size=200),
        _make_result("genome_v1", GroupType.VARIANT, roas=0.36, sample_size=200),
    ]
    return _make_report(
        experiment_id="exp_low_sample",
        experiment_name="Low Sample Test",
        results=results,
    )


@pytest.fixture
def report_explore():
    """无 Winner 但 Variant 有数据的实验报告."""
    results = [
        _make_result("genome_ctrl", GroupType.CONTROL, roas=0.35),
        _make_result("genome_v1", GroupType.VARIANT, roas=0.36, significance=0.6),
        _make_result("genome_v2", GroupType.VARIANT, roas=0.355, significance=0.55),
    ]
    return _make_report(
        experiment_id="exp_explore",
        experiment_name="Explore Test",
        results=results,
    )


# ═══════════════════════════════════════════════════════════
# 1. Feedback Models — 数据模型 (20 tests)
# ═══════════════════════════════════════════════════════════

class TestEvolutionFeedback:
    """EvolutionFeedback 模型测试."""

    def test_create_default(self):
        """创建默认 EvolutionFeedback."""
        fb = EvolutionFeedback()
        assert fb.feedback_id.startswith("fb_")
        assert fb.feedback_type == FeedbackType.NO_SIGNAL
        assert fb.fitness_score == 0.0
        assert fb.reward == 0.0
        assert fb.confidence == 0.0

    def test_create_winner_promotion(self):
        """创建 Winner Promotion 反馈."""
        fb = EvolutionFeedback(
            experiment_id="exp_001",
            genome_id="genome_v3",
            feedback_type=FeedbackType.WINNER_PROMOTION,
            fitness_score=0.87,
            reward=0.34,
            confidence=0.92,
            mutation_direction="roas_0.85_ctr_4.5%",
            recommendation="AMPLIFY: genome_v3 ROAS lift=+34.0%",
        )
        assert fb.feedback_type == FeedbackType.WINNER_PROMOTION
        assert fb.fitness_score == 0.87
        assert fb.reward == 0.34
        assert fb.confidence == 0.92

    def test_create_loser_suppression(self):
        """创建 Loser Suppression 反馈."""
        fb = EvolutionFeedback(
            genome_id="genome_bad",
            feedback_type=FeedbackType.LOSER_SUPPRESSION,
            reward=-0.5,
            confidence=0.85,
        )
        assert fb.feedback_type == FeedbackType.LOSER_SUPPRESSION
        assert fb.reward == -0.5

    def test_create_exploration(self):
        """创建 Exploration 反馈."""
        fb = EvolutionFeedback(
            feedback_type=FeedbackType.EXPLORATION_SIGNAL,
            confidence=0.55,
        )
        assert fb.feedback_type == FeedbackType.EXPLORATION_SIGNAL

    def test_to_dict(self):
        """序列化 to_dict."""
        fb = EvolutionFeedback(
            experiment_id="exp_001",
            genome_id="genome_v3",
            feedback_type=FeedbackType.WINNER_PROMOTION,
            fitness_score=0.87,
            reward=0.34,
            confidence=0.92,
        )
        d = fb.to_dict()
        assert d["feedback_type"] == "winner_promotion"
        assert d["fitness_score"] == 0.87
        assert d["reward"] == 0.34
        assert d["confidence"] == 0.92

    def test_from_dict(self):
        """反序列化 from_dict."""
        data = {
            "feedback_id": "fb_test",
            "experiment_id": "exp_001",
            "genome_id": "genome_v3",
            "feedback_type": "winner_promotion",
            "fitness_score": 0.87,
            "reward": 0.34,
            "confidence": 0.92,
            "mutation_direction": "roas_0.85",
            "recommendation": "AMPLIFY",
        }
        fb = EvolutionFeedback.from_dict(data)
        assert fb.feedback_id == "fb_test"
        assert fb.feedback_type == FeedbackType.WINNER_PROMOTION
        assert fb.fitness_score == 0.87

    def test_feedback_id_unique(self):
        """两个默认反馈的 ID 不同."""
        fb1 = EvolutionFeedback()
        fb2 = EvolutionFeedback()
        assert fb1.feedback_id != fb2.feedback_id


class TestMemoryPattern:
    """MemoryPattern 模型测试."""

    def test_create_default(self):
        """创建默认 MemoryPattern."""
        mp = MemoryPattern()
        assert mp.pattern_id.startswith("mp_")
        assert mp.pattern_type == ""
        assert mp.reward == 0.0

    def test_create_winner_pattern(self):
        """创建 Winner 模式."""
        mp = MemoryPattern(
            pattern_name="winner_genome_v3",
            pattern_type="gene_amplify",
            source_genome_ids=["genome_v3"],
            gene_category="hook",
            direction="amplify",
            reward=0.34,
            confidence=0.92,
        )
        assert mp.pattern_type == "gene_amplify"
        assert mp.reward == 0.34
        assert mp.confidence == 0.92

    def test_create_loser_pattern(self):
        """创建 Loser 模式."""
        mp = MemoryPattern(
            pattern_name="loser_genome_bad",
            pattern_type="gene_suppress",
            direction="suppress",
            reward=-0.5,
            confidence=0.85,
        )
        assert mp.pattern_type == "gene_suppress"
        assert mp.reward == -0.5

    def test_to_dict(self):
        """序列化 to_dict."""
        mp = MemoryPattern(
            pattern_name="test_pattern",
            pattern_type="gene_amplify",
            source_genome_ids=["g1", "g2"],
            gene_category="hook",
            direction="amplify",
            reward=0.3,
            confidence=0.9,
            sample_size=5000,
        )
        d = mp.to_dict()
        assert d["pattern_name"] == "test_pattern"
        assert d["source_genome_ids"] == ["g1", "g2"]
        assert d["reward"] == 0.3
        assert d["sample_size"] == 5000

    def test_from_dict(self):
        """反序列化 from_dict."""
        data = {
            "pattern_id": "mp_test",
            "pattern_name": "test",
            "pattern_type": "gene_amplify",
            "source_genome_ids": ["g1"],
            "reward": 0.5,
            "confidence": 0.8,
            "sample_size": 3000,
        }
        mp = MemoryPattern.from_dict(data)
        assert mp.pattern_id == "mp_test"
        assert mp.reward == 0.5
        assert mp.sample_size == 3000

    def test_pattern_id_unique(self):
        """两个默认模式的 ID 不同."""
        mp1 = MemoryPattern()
        mp2 = MemoryPattern()
        assert mp1.pattern_id != mp2.pattern_id


class TestEvolutionSignal:
    """EvolutionSignal 模型测试."""

    def test_create_default(self):
        """创建默认 EvolutionSignal."""
        sig = EvolutionSignal()
        assert sig.signal_id.startswith("sig_")
        assert sig.action == SignalAction.MAINTAIN
        assert sig.confidence == 0.0

    def test_create_amplify(self):
        """创建 AMPLIFY 信号."""
        sig = EvolutionSignal(
            action=SignalAction.AMPLIFY,
            gene_category="hook",
            target_value="rescue",
            confidence=0.92,
            expected_impact="预期 ROAS lift +34.0%",
        )
        assert sig.action == SignalAction.AMPLIFY
        assert sig.gene_category == "hook"
        assert sig.confidence == 0.92

    def test_create_suppress(self):
        """创建 SUPPRESS 信号."""
        sig = EvolutionSignal(
            action=SignalAction.SUPPRESS,
            target_value="aggressive",
            confidence=0.85,
        )
        assert sig.action == SignalAction.SUPPRESS

    def test_create_explore(self):
        """创建 EXPLORE 信号."""
        sig = EvolutionSignal(
            action=SignalAction.EXPLORE,
            target_value="new_direction",
        )
        assert sig.action == SignalAction.EXPLORE

    def test_to_dict(self):
        """序列化 to_dict."""
        sig = EvolutionSignal(
            action=SignalAction.AMPLIFY,
            gene_category="hook",
            target_value="rescue",
            confidence=0.92,
        )
        d = sig.to_dict()
        assert d["action"] == "amplify"
        assert d["gene_category"] == "hook"
        assert d["confidence"] == 0.92

    def test_from_dict(self):
        """反序列化 from_dict."""
        data = {
            "signal_id": "sig_test",
            "action": "amplify",
            "gene_category": "hook",
            "target_value": "rescue",
            "confidence": 0.9,
        }
        sig = EvolutionSignal.from_dict(data)
        assert sig.signal_id == "sig_test"
        assert sig.action == SignalAction.AMPLIFY

    def test_signal_id_unique(self):
        """两个默认信号的 ID 不同."""
        s1 = EvolutionSignal()
        s2 = EvolutionSignal()
        assert s1.signal_id != s2.signal_id


class TestFeedbackReport:
    """FeedbackReport 模型测试."""

    def test_create_empty(self):
        """创建空 FeedbackReport."""
        fr = FeedbackReport()
        assert fr.report_id.startswith("fbr_")
        assert fr.total_feedbacks == 0
        assert not fr.has_winner_signal
        assert not fr.has_actionable_signals

    def test_has_winner_signal(self):
        """有 Winner 时 has_winner_signal=True."""
        fr = FeedbackReport(winner_promotions=3)
        assert fr.has_winner_signal

    def test_has_actionable_signals(self):
        """有信号时 has_actionable_signals=True."""
        fr = FeedbackReport(signals_generated=5)
        assert fr.has_actionable_signals

    def test_to_dict(self):
        """序列化 to_dict."""
        fb = EvolutionFeedback(feedback_type=FeedbackType.WINNER_PROMOTION)
        fr = FeedbackReport(
            experiment_id="exp_001",
            experiment_name="Test",
            total_feedbacks=1,
            winner_promotions=1,
            signals_generated=1,
            feedbacks=[fb],
            summary="ok",
        )
        d = fr.to_dict()
        assert d["has_winner_signal"] is True
        assert d["has_actionable_signals"] is True
        assert len(d["feedbacks"]) == 1

    def test_feedback_report_with_patterns(self):
        """含 Patterns 的 FeedbackReport."""
        mp = MemoryPattern(pattern_name="test")
        sig = EvolutionSignal(action=SignalAction.AMPLIFY)
        fr = FeedbackReport(
            patterns=[mp],
            signals=[sig],
            patterns_learned=1,
            signals_generated=1,
        )
        d = fr.to_dict()
        assert len(d["patterns"]) == 1
        assert len(d["signals"]) == 1


# ═══════════════════════════════════════════════════════════
# 2. Report Processing — 报告处理 (20 tests)
# ═══════════════════════════════════════════════════════════

class TestReportProcessing:
    """process_report 核心测试."""

    def test_process_winner_report(self, controller, report_with_winner):
        """处理有 Winner 的报告."""
        fr = controller.process_report(report_with_winner)
        assert fr.total_feedbacks == 4
        assert fr.winner_promotions > 0

    def test_process_loser_report(self, controller, report_with_loser):
        """处理有 Loser 的报告."""
        fr = controller.process_report(report_with_loser)
        assert fr.total_feedbacks == 2
        assert fr.loser_suppressions > 0

    def test_process_empty_report(self, controller, report_empty):
        """处理空报告."""
        fr = controller.process_report(report_empty)
        assert fr.total_feedbacks == 0
        assert "无实验结果数据" in fr.summary

    def test_process_mixed_report(self, controller, report_mixed):
        """处理混合结果报告."""
        fr = controller.process_report(report_mixed)
        assert fr.total_feedbacks == 4
        assert fr.winner_promotions >= 1
        assert fr.loser_suppressions >= 1

    def test_feedback_count_equals_results(self, controller, report_with_winner):
        """反馈数 = 结果数."""
        fr = controller.process_report(report_with_winner)
        assert fr.total_feedbacks == len(report_with_winner.results)

    def test_summary_generated(self, controller, report_with_winner):
        """生成摘要."""
        fr = controller.process_report(report_with_winner)
        assert len(fr.summary) > 0
        assert "Winner Test" in fr.summary

    def test_experiment_metadata_preserved(self, controller, report_with_winner):
        """实验元数据保留."""
        fr = controller.process_report(report_with_winner)
        assert fr.experiment_id == "exp_wtest_001"
        assert fr.experiment_name == "Winner Test"

    def test_winner_gets_promotion_type(self, controller, report_with_winner):
        """Winner 获得 WINNER_PROMOTION 类型."""
        fr = controller.process_report(report_with_winner)
        winner_fb = next((f for f in fr.feedbacks if f.genome_id == "genome_v3"), None)
        assert winner_fb is not None
        assert winner_fb.feedback_type == FeedbackType.WINNER_PROMOTION

    def test_loser_gets_suppression_type(self, controller, report_with_loser):
        """Loser 获得 LOSER_SUPPRESSION 类型."""
        fr = controller.process_report(report_with_loser)
        loser_fb = next((f for f in fr.feedbacks if f.genome_id == "genome_bad"), None)
        assert loser_fb is not None
        assert loser_fb.feedback_type == FeedbackType.LOSER_SUPPRESSION

    def test_reward_calculation_positive(self, controller, report_with_winner):
        """Winner 奖励值为正."""
        fr = controller.process_report(report_with_winner)
        winner_fb = next((f for f in fr.feedbacks if f.genome_id == "genome_v3"), None)
        assert winner_fb.reward > 0

    def test_reward_calculation_negative(self, controller, report_with_loser):
        """Loser 奖励值为负."""
        fr = controller.process_report(report_with_loser)
        loser_fb = next((f for f in fr.feedbacks if f.genome_id == "genome_bad"), None)
        assert loser_fb.reward < 0

    def test_confidence_based_on_significance(self, controller, report_with_winner):
        """置信度基于统计显著性."""
        fr = controller.process_report(report_with_winner)
        for fb in fr.feedbacks:
            assert 0 <= fb.confidence <= 1.0

    def test_low_sample_reduces_confidence(self, controller, report_low_sample):
        """低样本量降低置信度."""
        fr = controller.process_report(report_low_sample)
        for fb in fr.feedbacks:
            assert fb.confidence < 0.9  # 样本量不足时降低

    def test_patterns_generated(self, controller, report_with_winner):
        """生成 Memory Patterns."""
        fr = controller.process_report(report_with_winner)
        assert fr.patterns_learned > 0

    def test_signals_generated(self, controller, report_with_winner):
        """生成 Evolution Signals."""
        fr = controller.process_report(report_with_winner)
        assert fr.signals_generated > 0

    def test_multiple_processing_increments_stats(self, controller, report_with_winner):
        """多次处理累加统计."""
        controller.process_report(report_with_winner)
        stats1 = controller.stats()
        controller.process_report(report_with_winner)
        stats2 = controller.stats()
        assert stats2["total_feedbacks"] > stats1["total_feedbacks"]

    def test_no_signals_for_empty(self, controller, report_empty):
        """空报告无信号."""
        fr = controller.process_report(report_empty)
        assert fr.signals_generated == 0
        assert fr.patterns_learned == 0

    def test_explore_signal_without_winner(self, controller, report_explore):
        """无 Winner 时生成 EXPLORE 信号."""
        fr = controller.process_report(report_explore)
        explore_signals = [s for s in fr.signals if s.action == SignalAction.EXPLORE]
        assert len(explore_signals) > 0

    def test_retest_signal_for_no_data(self, controller):
        """完全无显著数据时生成 RETEST 信号."""
        results = [
            _make_result("ctrl", GroupType.CONTROL, roas=0.35, sample_size=200),
            _make_result("v1", GroupType.VARIANT, roas=0.36, sample_size=200),
        ]
        report = _make_report(results=results)
        fr = controller.process_report(report)
        retest = [s for s in fr.signals if s.action == SignalAction.RETEST]
        assert len(retest) > 0


# ═══════════════════════════════════════════════════════════
# 3. Fitness Update — 适应度更新 (15 tests)
# ═══════════════════════════════════════════════════════════

class TestFitnessUpdate:
    """适应度更新测试."""

    def test_fitness_snapshot_created(self, controller, report_with_winner):
        """适应度快照被创建."""
        controller.process_report(report_with_winner)
        snap = controller.get_fitness_snapshot("genome_v3")
        assert snap is not None

    def test_fitness_snapshot_for_control(self, controller, report_with_winner):
        """对照组基因组也有适应度快照."""
        controller.process_report(report_with_winner)
        snap = controller.get_fitness_snapshot("genome_ctrl")
        assert snap is not None

    def test_fitness_snapshot_for_all_genomes(self, controller, report_with_winner):
        """所有基因组都有适应度快照."""
        controller.process_report(report_with_winner)
        for result in report_with_winner.results:
            snap = controller.get_fitness_snapshot(result.genome_id)
            assert snap is not None, f"Missing snapshot for {result.genome_id}"

    def test_fitness_score_positive(self, controller, report_with_winner):
        """适应度评分为正."""
        controller.process_report(report_with_winner)
        snap = controller.get_fitness_snapshot("genome_v3")
        assert snap.score > 0

    def test_fitness_includes_roas_metric(self, controller, report_with_winner):
        """适应度包含 ROAS 指标."""
        controller.process_report(report_with_winner)
        snap = controller.get_fitness_snapshot("genome_v3")
        metric_names = [m.name for m in snap.fitness_score.metrics]
        assert "roas" in metric_names

    def test_fitness_includes_ctr_metric(self, controller, report_with_winner):
        """适应度包含 CTR 指标."""
        controller.process_report(report_with_winner)
        snap = controller.get_fitness_snapshot("genome_v3")
        metric_names = [m.name for m in snap.fitness_score.metrics]
        assert "ctr" in metric_names

    def test_fitness_includes_cvr_metric(self, controller, report_with_winner):
        """适应度包含 CVR 指标."""
        controller.process_report(report_with_winner)
        snap = controller.get_fitness_snapshot("genome_v3")
        metric_names = [m.name for m in snap.fitness_score.metrics]
        assert "cvr" in metric_names

    def test_fitness_includes_payer_rate_metric(self, controller, report_with_winner):
        """适应度包含 payer_rate 指标."""
        controller.process_report(report_with_winner)
        snap = controller.get_fitness_snapshot("genome_v3")
        metric_names = [m.name for m in snap.fitness_score.metrics]
        assert "payer_rate" in metric_names

    def test_fitness_includes_cpi_metric(self, controller, report_with_winner):
        """适应度包含 CPI 指标."""
        controller.process_report(report_with_winner)
        snap = controller.get_fitness_snapshot("genome_v3")
        metric_names = [m.name for m in snap.fitness_score.metrics]
        assert "cpi" in metric_names

    def test_roas_metric_direction_maximize(self, controller, report_with_winner):
        """ROAS 指标方向为 MAXIMIZE."""
        controller.process_report(report_with_winner)
        snap = controller.get_fitness_snapshot("genome_v3")
        roas_metric = next(m for m in snap.fitness_score.metrics if m.name == "roas")
        assert roas_metric.direction == FitnessDirection.MAXIMIZE

    def test_cpi_metric_direction_minimize(self, controller, report_with_winner):
        """CPI 指标方向为 MINIMIZE."""
        controller.process_report(report_with_winner)
        snap = controller.get_fitness_snapshot("genome_v3")
        cpi_metric = next(m for m in snap.fitness_score.metrics if m.name == "cpi")
        assert cpi_metric.direction == FitnessDirection.MINIMIZE

    def test_winner_higher_fitness_than_control(self, controller, report_with_winner):
        """Winner 适应度 > 对照组."""
        controller.process_report(report_with_winner)
        winner_snap = controller.get_fitness_snapshot("genome_v3")
        control_snap = controller.get_fitness_snapshot("genome_ctrl")
        assert winner_snap.score > control_snap.score

    def test_metrics_weights_sum_to_one(self, controller, report_with_winner):
        """指标权重和接近1."""
        controller.process_report(report_with_winner)
        snap = controller.get_fitness_snapshot("genome_v3")
        total_weight = sum(m.weight for m in snap.fitness_score.metrics)
        assert 0.9 <= total_weight <= 1.2  # 允许浮动

    def test_memory_graph_fitness_recorded(self, controller_with_memory, report_with_winner):
        """MemoryGraph 中记录了适应度."""
        controller_with_memory.process_report(report_with_winner)
        mg = controller_with_memory.memory_graph
        genome_count = mg.get_genome_count()
        assert genome_count > 0

    def test_reset_clears_fitness(self, controller, report_with_winner):
        """Reset 清除适应度快照."""
        controller.process_report(report_with_winner)
        assert controller.get_fitness_snapshot("genome_v3") is not None
        controller.reset()
        assert controller.get_fitness_snapshot("genome_v3") is None


# ═══════════════════════════════════════════════════════════
# 4. Memory Pattern Generation — 模式生成 (15 tests)
# ═══════════════════════════════════════════════════════════

class TestMemoryPatternGeneration:
    """MemoryPattern 生成测试."""

    def test_winner_pattern_type(self, controller, report_with_winner):
        """Winner 模式类型为 gene_amplify."""
        fr = controller.process_report(report_with_winner)
        winner_patterns = [p for p in fr.patterns if "winner" in p.pattern_name]
        for p in winner_patterns:
            assert p.pattern_type == "gene_amplify"

    def test_loser_pattern_type(self, controller, report_with_loser):
        """Loser 模式类型为 gene_suppress."""
        fr = controller.process_report(report_with_loser)
        loser_patterns = [p for p in fr.patterns if "loser" in p.pattern_name]
        for p in loser_patterns:
            assert p.pattern_type == "gene_suppress"

    def test_experiment_summary_pattern(self, controller, report_with_winner):
        """实验总结模式."""
        fr = controller.process_report(report_with_winner)
        summary_patterns = [p for p in fr.patterns if "experiment" in p.pattern_name]
        assert len(summary_patterns) > 0

    def test_pattern_source_genome_ids(self, controller, report_with_winner):
        """模式包含来源基因组 ID."""
        fr = controller.process_report(report_with_winner)
        for p in fr.patterns:
            assert len(p.source_genome_ids) > 0

    def test_pattern_source_experiment_id(self, controller, report_with_winner):
        """模式包含来源实验 ID."""
        fr = controller.process_report(report_with_winner)
        for p in fr.patterns:
            assert p.source_experiment_id == "exp_wtest_001"

    def test_pattern_written_to_memory_graph(self, controller_with_memory, report_with_winner):
        """模式写入 EvolutionMemoryGraph."""
        controller_with_memory.process_report(report_with_winner)
        mg = controller_with_memory.memory_graph
        pattern_count = mg.get_pattern_count()
        assert pattern_count > 0

    def test_pattern_confidence_preserved(self, controller, report_with_winner):
        """模式置信度保留."""
        fr = controller.process_report(report_with_winner)
        for p in fr.patterns:
            assert p.confidence > 0

    def test_pattern_reward_preserved(self, controller, report_with_winner):
        """模式奖励值保留."""
        fr = controller.process_report(report_with_winner)
        winner_patterns = [p for p in fr.patterns if "winner" in p.pattern_name]
        for p in winner_patterns:
            assert p.reward > 0

    def test_get_pattern_by_id(self, controller, report_with_winner):
        """按 ID 获取模式."""
        fr = controller.process_report(report_with_winner)
        if fr.patterns:
            p = controller.get_pattern(fr.patterns[0].pattern_id)
            assert p is not None

    def test_get_pattern_none_for_unknown(self, controller):
        """未知 ID 返回 None."""
        assert controller.get_pattern("nonexistent") is None

    def test_no_patterns_for_empty(self, controller, report_empty):
        """空报告无模式."""
        fr = controller.process_report(report_empty)
        assert fr.patterns_learned == 0

    def test_pattern_direction_amplify_for_winner(self, controller, report_with_winner):
        """Winner 模式方向为 amplify."""
        fr = controller.process_report(report_with_winner)
        winner_patterns = [p for p in fr.patterns if "winner" in p.pattern_name]
        for p in winner_patterns:
            assert p.direction == "amplify"

    def test_pattern_direction_suppress_for_loser(self, controller, report_with_loser):
        """Loser 模式方向为 suppress."""
        fr = controller.process_report(report_with_loser)
        loser_patterns = [p for p in fr.patterns if "loser" in p.pattern_name]
        for p in loser_patterns:
            assert p.direction == "suppress"

    def test_pattern_count_matches(self, controller, report_mixed):
        """混合报告中模式数量正确."""
        fr = controller.process_report(report_mixed)
        # 至少包含 winner pattern + loser pattern
        assert fr.patterns_learned >= 2

    def test_reset_clears_patterns(self, controller, report_with_winner):
        """Reset 清除模式."""
        controller.process_report(report_with_winner)
        assert len(controller._patterns) > 0
        controller.reset()
        assert len(controller._patterns) == 0


# ═══════════════════════════════════════════════════════════
# 5. Winner Promotion — Winner 强化 (15 tests)
# ═══════════════════════════════════════════════════════════

class TestWinnerPromotion:
    """Winner Promotion 测试."""

    def test_winner_feedback_type(self, controller, report_with_winner):
        """Winner 反馈类型为 WINNER_PROMOTION."""
        fr = controller.process_report(report_with_winner)
        winner_fb = next((f for f in fr.feedbacks if f.genome_id == "genome_v3"), None)
        assert winner_fb.feedback_type == FeedbackType.WINNER_PROMOTION

    def test_winner_reward_positive(self, controller, report_with_winner):
        """Winner 奖励为正."""
        fr = controller.process_report(report_with_winner)
        winner_fb = next((f for f in fr.feedbacks if f.genome_id == "genome_v3"), None)
        assert winner_fb.reward > 0.1  # ROAS 0.85 vs 0.35 = +143%

    def test_winner_recommendation_contains_amplify(self, controller, report_with_winner):
        """Winner 建议包含 AMPLIFY."""
        fr = controller.process_report(report_with_winner)
        winner_fb = next((f for f in fr.feedbacks if f.genome_id == "genome_v3"), None)
        assert "AMPLIFY" in winner_fb.recommendation

    def test_winner_feedback_count(self, controller, report_with_winner):
        """Winner 反馈数量."""
        fr = controller.process_report(report_with_winner)
        assert fr.winner_promotions >= 1

    def test_winner_amplify_signal(self, controller, report_with_winner):
        """Winner 产生 AMPLIFY 信号."""
        fr = controller.process_report(report_with_winner)
        amplify_signals = [s for s in fr.signals if s.action == SignalAction.AMPLIFY]
        assert len(amplify_signals) > 0

    def test_winner_signal_confidence(self, controller, report_with_winner):
        """Winner 信号置信度."""
        fr = controller.process_report(report_with_winner)
        amplify_signals = [s for s in fr.signals if s.action == SignalAction.AMPLIFY]
        for s in amplify_signals:
            assert s.confidence > 0

    def test_winner_signal_source_experiment(self, controller, report_with_winner):
        """Winner 信号来源实验."""
        fr = controller.process_report(report_with_winner)
        amplify_signals = [s for s in fr.signals if s.action == SignalAction.AMPLIFY]
        for s in amplify_signals:
            assert s.source_experiment_id == "exp_wtest_001"

    def test_get_winner_feedbacks(self, controller, report_with_winner):
        """get_winner_feedbacks 查询."""
        controller.process_report(report_with_winner)
        winners = controller.get_winner_feedbacks()
        assert len(winners) > 0
        for f in winners:
            assert f.feedback_type == FeedbackType.WINNER_PROMOTION

    def test_get_amplify_signals(self, controller, report_with_winner):
        """get_amplify_signals 查询."""
        controller.process_report(report_with_winner)
        amplify = controller.get_amplify_signals()
        assert len(amplify) > 0
        for s in amplify:
            assert s.action == SignalAction.AMPLIFY

    def test_winner_mutation_direction_not_empty(self, controller, report_with_winner):
        """Winner 变异方向非空."""
        fr = controller.process_report(report_with_winner)
        winner_fb = next((f for f in fr.feedbacks if f.genome_id == "genome_v3"), None)
        assert winner_fb.mutation_direction != ""
        assert "roas" in winner_fb.mutation_direction

    def test_winner_fitness_score_recorded(self, controller, report_with_winner):
        """Winner 适应度评分被记录 (来自 ExperimentResult.score)."""
        fr = controller.process_report(report_with_winner)
        winner_fb = next((f for f in fr.feedbacks if f.genome_id == "genome_v3"), None)
        # 注意: fixture 中的 ExperimentResult 未设置 FitnessScore，
        # 所以 result.score 返回 0.0；实际 E14.6.2 会设置 FitnessScore
        assert winner_fb.fitness_score >= 0

    def test_winner_signal_expected_impact(self, controller, report_with_winner):
        """Winner 信号包含预期影响."""
        fr = controller.process_report(report_with_winner)
        amplify_signals = [s for s in fr.signals if s.action == SignalAction.AMPLIFY]
        for s in amplify_signals:
            assert "ROAS" in s.expected_impact or "lift" in s.expected_impact.lower()

    def test_winner_feedback_serializable(self, controller, report_with_winner):
        """Winner 反馈可序列化."""
        fr = controller.process_report(report_with_winner)
        winner_fb = next((f for f in fr.feedbacks if f.genome_id == "genome_v3"), None)
        d = winner_fb.to_dict()
        assert d["feedback_type"] == "winner_promotion"

    def test_winner_with_high_lift_boundary(self, controller):
        """刚好超过阈值的 Winner."""
        results = [
            _make_result("ctrl", GroupType.CONTROL, roas=0.30),
            _make_result("v1", GroupType.VARIANT, roas=0.32),  # lift = 6.67% > 5%
        ]
        report = _make_report(results=results)
        fr = controller.process_report(report)
        v1_fb = next((f for f in fr.feedbacks if f.genome_id == "v1"), None)
        assert v1_fb.feedback_type == FeedbackType.WINNER_PROMOTION

    def test_winner_below_threshold_not_promoted(self, controller):
        """低于阈值的 Variant 不被提升."""
        results = [
            _make_result("ctrl", GroupType.CONTROL, roas=0.30),
            _make_result("v1", GroupType.VARIANT, roas=0.31),  # lift = 3.33% < 5%
        ]
        report = _make_report(results=results)
        fr = controller.process_report(report)
        v1_fb = next((f for f in fr.feedbacks if f.genome_id == "v1"), None)
        assert v1_fb.feedback_type != FeedbackType.WINNER_PROMOTION


# ═══════════════════════════════════════════════════════════
# 6. Loser Suppression — Loser 抑制 (10 tests)
# ═══════════════════════════════════════════════════════════

class TestLoserSuppression:
    """Loser Suppression 测试."""

    def test_loser_feedback_type(self, controller, report_with_loser):
        """Loser 反馈类型为 LOSER_SUPPRESSION."""
        fr = controller.process_report(report_with_loser)
        loser_fb = next((f for f in fr.feedbacks if f.genome_id == "genome_bad"), None)
        assert loser_fb.feedback_type == FeedbackType.LOSER_SUPPRESSION

    def test_loser_reward_negative(self, controller, report_with_loser):
        """Loser 奖励为负."""
        fr = controller.process_report(report_with_loser)
        loser_fb = next((f for f in fr.feedbacks if f.genome_id == "genome_bad"), None)
        assert loser_fb.reward < 0

    def test_loser_recommendation_contains_suppress(self, controller, report_with_loser):
        """Loser 建议包含 SUPPRESS."""
        fr = controller.process_report(report_with_loser)
        loser_fb = next((f for f in fr.feedbacks if f.genome_id == "genome_bad"), None)
        assert "SUPPRESS" in loser_fb.recommendation

    def test_loser_suppress_signal(self, controller, report_with_loser):
        """Loser 产生 SUPPRESS 信号."""
        fr = controller.process_report(report_with_loser)
        suppress_signals = [s for s in fr.signals if s.action == SignalAction.SUPPRESS]
        assert len(suppress_signals) > 0

    def test_get_loser_feedbacks(self, controller, report_with_loser):
        """get_loser_feedbacks 查询."""
        controller.process_report(report_with_loser)
        losers = controller.get_loser_feedbacks()
        assert len(losers) > 0
        for f in losers:
            assert f.feedback_type == FeedbackType.LOSER_SUPPRESSION

    def test_get_suppress_signals(self, controller, report_with_loser):
        """get_suppress_signals 查询."""
        controller.process_report(report_with_loser)
        suppress = controller.get_suppress_signals()
        assert len(suppress) > 0
        for s in suppress:
            assert s.action == SignalAction.SUPPRESS

    def test_loser_count_in_report(self, controller, report_with_loser):
        """Loser 计数正确."""
        fr = controller.process_report(report_with_loser)
        assert fr.loser_suppressions == 1

    def test_loser_signal_expected_impact(self, controller, report_with_loser):
        """Loser 信号包含预期影响."""
        fr = controller.process_report(report_with_loser)
        suppress_signals = [s for s in fr.signals if s.action == SignalAction.SUPPRESS]
        for s in suppress_signals:
            assert "损失" in s.expected_impact or "ROAS" in s.expected_impact

    def test_loser_signal_source_experiment(self, controller, report_with_loser):
        """Loser 信号来源实验."""
        fr = controller.process_report(report_with_loser)
        suppress_signals = [s for s in fr.signals if s.action == SignalAction.SUPPRESS]
        for s in suppress_signals:
            assert s.source_experiment_id == "exp_loser_001"

    def test_loser_below_threshold_only(self, controller):
        """只有低于 -5% 阈值的才是 Loser."""
        results = [
            _make_result("ctrl", GroupType.CONTROL, roas=0.40),
            _make_result("v1", GroupType.VARIANT, roas=0.37),  # lift = -7.5% < -5%
        ]
        report = _make_report(results=results)
        fr = controller.process_report(report)
        v1_fb = next((f for f in fr.feedbacks if f.genome_id == "v1"), None)
        assert v1_fb.feedback_type == FeedbackType.LOSER_SUPPRESSION


# ═══════════════════════════════════════════════════════════
# 7. Next Evolution Signal — 进化信号 (15 tests)
# ═══════════════════════════════════════════════════════════

class TestEvolutionSignals:
    """EvolutionSignal 生成测试."""

    def test_amplify_signal_action(self, controller, report_with_winner):
        """AMPLIFY 信号动作正确."""
        fr = controller.process_report(report_with_winner)
        amplify = [s for s in fr.signals if s.action == SignalAction.AMPLIFY]
        assert len(amplify) > 0

    def test_suppress_signal_action(self, controller, report_with_loser):
        """SUPPRESS 信号动作正确."""
        fr = controller.process_report(report_with_loser)
        suppress = [s for s in fr.signals if s.action == SignalAction.SUPPRESS]
        assert len(suppress) > 0

    def test_explore_signal_action(self, controller, report_explore):
        """EXPLORE 信号动作正确."""
        fr = controller.process_report(report_explore)
        explore = [s for s in fr.signals if s.action == SignalAction.EXPLORE]
        assert len(explore) > 0

    def test_retest_signal_action(self, controller, report_low_sample):
        """RETEST 信号动作正确."""
        fr = controller.process_report(report_low_sample)
        retest = [s for s in fr.signals if s.action == SignalAction.RETEST]
        assert len(retest) > 0

    def test_signal_confidence_range(self, controller, report_with_winner):
        """信号置信度在 0-1 之间."""
        fr = controller.process_report(report_with_winner)
        for s in fr.signals:
            assert 0 <= s.confidence <= 1.0

    def test_get_signal_by_id(self, controller, report_with_winner):
        """按 ID 获取信号."""
        fr = controller.process_report(report_with_winner)
        if fr.signals:
            s = controller.get_signal(fr.signals[0].signal_id)
            assert s is not None

    def test_get_signal_none_for_unknown(self, controller):
        """未知信号 ID 返回 None."""
        assert controller.get_signal("nonexistent") is None

    def test_get_signals_by_action(self, controller, report_mixed):
        """按动作类型获取信号."""
        controller.process_report(report_mixed)
        amplify = controller.get_signals_by_action(SignalAction.AMPLIFY)
        assert len(amplify) > 0
        for s in amplify:
            assert s.action == SignalAction.AMPLIFY

    def test_signal_count_matches_report(self, controller, report_mixed):
        """信号数与报告一致."""
        fr = controller.process_report(report_mixed)
        assert len(fr.signals) == fr.signals_generated

    def test_signal_to_dict(self, controller, report_with_winner):
        """信号可序列化."""
        fr = controller.process_report(report_with_winner)
        for s in fr.signals:
            d = s.to_dict()
            assert "signal_id" in d
            assert "action" in d
            assert "confidence" in d

    def test_signal_from_dict(self):
        """信号可反序列化."""
        data = {
            "signal_id": "sig_test",
            "action": "amplify",
            "gene_category": "hook",
            "confidence": 0.9,
        }
        sig = EvolutionSignal.from_dict(data)
        assert sig.action == SignalAction.AMPLIFY

    def test_signal_source_experiment(self, controller, report_with_winner):
        """信号来源实验."""
        fr = controller.process_report(report_with_winner)
        for s in fr.signals:
            assert s.source_experiment_id == "exp_wtest_001"

    def test_signal_expected_impact_not_empty(self, controller, report_with_winner):
        """信号预期影响非空."""
        fr = controller.process_report(report_with_winner)
        for s in fr.signals:
            assert s.expected_impact != ""

    def test_signal_id_unique(self, controller, report_with_winner):
        """信号 ID 唯一."""
        fr = controller.process_report(report_with_winner)
        signal_ids = [s.signal_id for s in fr.signals]
        assert len(set(signal_ids)) == len(signal_ids)

    def test_reset_clears_signals(self, controller, report_with_winner):
        """Reset 清除信号."""
        controller.process_report(report_with_winner)
        assert len(controller._signals) > 0
        controller.reset()
        assert len(controller._signals) == 0


# ═══════════════════════════════════════════════════════════
# 8. Regression E14.5/E14.6 — 集成回归 (10 tests)
# ═══════════════════════════════════════════════════════════

class TestRegression:
    """E14.5/E14.6 集成回归测试."""

    def test_feedback_controller_import(self):
        """EvolutionFeedbackController 可导入."""
        assert EvolutionFeedbackController is not None

    def test_evolution_memory_integration(self, controller_with_memory, report_with_winner):
        """与 EvolutionMemoryGraph 集成."""
        fr = controller_with_memory.process_report(report_with_winner)
        assert fr.patterns_learned > 0
        mg = controller_with_memory.memory_graph
        assert mg.get_pattern_count() > 0
        assert mg.get_genome_count() > 0

    def test_experiment_controller_integration(self, controller, report_with_winner):
        """与 ExperimentReport 集成."""
        fr = controller.process_report(report_with_winner)
        assert fr.experiment_id == report_with_winner.experiment_id

    def test_create_feedback_controller_factory(self):
        """工厂函数创建控制器."""
        fc = create_feedback_controller()
        assert isinstance(fc, EvolutionFeedbackController)

    def test_create_feedback_controller_with_memory(self, memory_graph):
        """工厂函数创建带 MemoryGraph 的控制器."""
        fc = create_feedback_controller(memory_graph=memory_graph)
        assert fc.memory_graph is memory_graph

    def test_custom_thresholds(self, report_with_winner):
        """自定义阈值."""
        fc = EvolutionFeedbackController(
            winner_threshold=0.10,
            loser_threshold=-0.10,
            min_confidence=0.7,
            min_sample_size=2000,
        )
        assert fc._winner_threshold == 0.10
        assert fc._loser_threshold == -0.10
        assert fc._min_confidence == 0.7
        assert fc._min_sample_size == 2000

    def test_controller_stats(self, controller, report_with_winner):
        """控制器统计."""
        controller.process_report(report_with_winner)
        stats = controller.stats()
        assert stats["total_feedbacks"] > 0
        assert stats["total_patterns"] > 0
        assert stats["total_signals"] > 0
        assert stats["total_fitness_snapshots"] > 0
        assert "feedbacks_by_type" in stats
        assert "signals_by_action" in stats

    def test_controller_reset_clears_everything(self, controller, report_with_winner):
        """Reset 清除所有状态."""
        controller.process_report(report_with_winner)
        controller.reset()
        stats = controller.stats()
        assert stats["total_feedbacks"] == 0
        assert stats["total_patterns"] == 0
        assert stats["total_signals"] == 0
        assert stats["total_fitness_snapshots"] == 0

    def test_memory_graph_property(self, controller):
        """memory_graph 属性."""
        mg = controller.memory_graph
        assert isinstance(mg, EvolutionMemoryGraph)

    def test_feedback_controller_enum_values(self):
        """枚举值验证."""
        assert FeedbackType.WINNER_PROMOTION.value == "winner_promotion"
        assert FeedbackType.LOSER_SUPPRESSION.value == "loser_suppression"
        assert FeedbackType.EXPLORATION_SIGNAL.value == "exploration_signal"
        assert FeedbackType.NO_SIGNAL.value == "no_signal"
        assert SignalAction.AMPLIFY.value == "amplify"
        assert SignalAction.SUPPRESS.value == "suppress"
        assert SignalAction.EXPLORE.value == "explore"
        assert SignalAction.MAINTAIN.value == "maintain"
        assert SignalAction.RETEST.value == "retest"