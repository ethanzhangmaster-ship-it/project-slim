"""E14.7.3 Execution Feedback Collector — 集成测试.

验证 ExecutionFeedbackCollector 的反馈收集能力:
  - Models: RewardMetrics / ExecutionFeedback / FeedbackQuality (15 tests)
  - RewardCalculator: 奖励计算 (20 tests)
  - FeedbackCollector: 核心收集 (20 tests)
  - Collect with Metrics: 指标提取 (15 tests)
  - To Experience: 转化为 GrowthExperience (15 tests)
  - Collect and Store: 收集+存储 (15 tests)
  - FeedbackPipeline: 反馈管道 (15 tests)
  - Batch Collection: 批量收集 (15 tests)
  - Error Handling: 错误处理 (10 tests)
  - Regression E14.7.1/E14.7.2: 集成回归 (10 tests)

总计: 150 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.execution_feedback import (
    ExecutionFeedbackCollector,
    ExecutionFeedback,
    RewardMetrics,
    RewardCalculator,
    FeedbackQuality,
    FeedbackPipeline,
    create_feedback_collector,
    create_feedback_pipeline,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
    ExecutionOutcome,
    ExecutionStatus,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
    ExperienceCategory,
    ExperienceContext,
    ExperienceOutcomeLevel,
    GrowthExperience,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import (
    ExperienceStore,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_outcome(
    status: ExecutionStatus = ExecutionStatus.SUCCESS,
    action_type: str = "promote_winner",
    action_id: str = "ga_001",
    output: dict | None = None,
    metadata: dict | None = None,
    error: str = "",
) -> ExecutionOutcome:
    return ExecutionOutcome(
        action_id=action_id,
        action_type=action_type,
        status=status,
        executor="MetaAdsExecutor",
        output=output or {},
        error=error,
        metadata=metadata or {},
    )


def _make_outcome_with_metrics(
    roas_delta: float = 0.0,
    cpi_delta: float = 0.0,
    ctr_delta: float = 0.0,
    cvr_delta: float = 0.0,
    payer_rate_delta: float = 0.0,
    retention_d7_delta: float = 0.0,
    **kwargs,
) -> ExecutionOutcome:
    return _make_outcome(
        output={"metrics_delta": {
            "roas_delta": roas_delta,
            "cpi_delta": cpi_delta,
            "ctr_delta": ctr_delta,
            "cvr_delta": cvr_delta,
            "payer_rate_delta": payer_rate_delta,
            "retention_d7_delta": retention_d7_delta,
        }},
        **kwargs,
    )


def _make_context(
    product_id: str = "game_001",
    action_type: str = "promote_winner",
    entity_id: str = "camp_001",
) -> ExperienceContext:
    return ExperienceContext(
        product_id=product_id,
        action_type=action_type,
        entity_id=entity_id,
    )


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def calculator():
    return RewardCalculator()


@pytest.fixture
def collector():
    return ExecutionFeedbackCollector()


@pytest.fixture
def store():
    return ExperienceStore()


@pytest.fixture
def pipeline(store):
    return FeedbackPipeline(experience_store=store)


# ═══════════════════════════════════════════════════════════
# 1. Model Tests (15)
# ═══════════════════════════════════════════════════════════

class TestFeedbackQuality:
    """FeedbackQuality 枚举测试."""

    def test_all_qualities_present(self):
        expected = {"strong", "reliable", "weak", "inconclusive"}
        actual = {q.value for q in FeedbackQuality}
        assert actual == expected

    def test_quality_values(self):
        assert FeedbackQuality.STRONG.value == "strong"
        assert FeedbackQuality.RELIABLE.value == "reliable"
        assert FeedbackQuality.WEAK.value == "weak"
        assert FeedbackQuality.INCONCLUSIVE.value == "inconclusive"


class TestRewardMetrics:
    """RewardMetrics 模型测试."""

    def test_default_creation(self):
        m = RewardMetrics()
        assert m.roas_delta == 0.0
        assert m.cpi_delta == 0.0
        assert m.ctr_delta == 0.0
        assert m.cvr_delta == 0.0
        assert m.payer_rate_delta == 0.0

    def test_full_creation(self):
        m = RewardMetrics(
            roas_delta=0.5,
            cpi_delta=-0.1,
            ctr_delta=0.02,
            cvr_delta=0.01,
            payer_rate_delta=0.03,
            ltv_d30_delta=0.5,
        )
        assert m.roas_delta == 0.5
        assert m.cpi_delta == -0.1
        assert m.ltv_d30_delta == 0.5

    def test_to_dict(self):
        m = RewardMetrics(roas_delta=0.3, cpi_delta=-0.05)
        d = m.to_dict()
        assert d["roas_delta"] == 0.3
        assert d["cpi_delta"] == -0.05
        assert "ctr_delta" in d

    def test_from_dict(self):
        m = RewardMetrics.from_dict({"roas_delta": 0.4, "ctr_delta": 0.02})
        assert m.roas_delta == 0.4
        assert m.ctr_delta == 0.02

    def test_from_dict_partial(self):
        m = RewardMetrics.from_dict({"roas_delta": 0.5})
        assert m.roas_delta == 0.5
        assert m.cpi_delta == 0.0


class TestExecutionFeedback:
    """ExecutionFeedback 模型测试."""

    def test_default_creation(self):
        fb = ExecutionFeedback()
        assert fb.feedback_id.startswith("fb_")
        assert fb.success is False
        assert fb.reward == 0.0
        assert fb.insights == []

    def test_full_creation(self):
        m = RewardMetrics(roas_delta=0.5)
        fb = ExecutionFeedback(
            execution_id="exec_001",
            action_id="ga_001",
            action_type="promote_winner",
            success=True,
            outcome_level=ExperienceOutcomeLevel.STRONG_SUCCESS,
            reward=0.85,
            metrics=m,
            quality=FeedbackQuality.STRONG,
            insights=["ROAS improved"],
        )
        assert fb.execution_id == "exec_001"
        assert fb.success is True
        assert fb.reward == 0.85
        assert fb.outcome_level == ExperienceOutcomeLevel.STRONG_SUCCESS
        assert fb.quality == FeedbackQuality.STRONG

    def test_to_dict(self):
        fb = ExecutionFeedback(
            action_id="ga_001",
            action_type="promote_winner",
            success=True,
            reward=0.8,
            insights=["Good result"],
        )
        d = fb.to_dict()
        assert d["action_id"] == "ga_001"
        assert d["success"] is True
        assert d["reward"] == 0.8
        assert "metrics" in d
        assert "insights" in d

    def test_to_experience_outcome(self):
        m = RewardMetrics(roas_delta=0.5)
        fb = ExecutionFeedback(
            success=True,
            outcome_level=ExperienceOutcomeLevel.SUCCESS,
            reward=0.7,
            metrics=m,
            insights=["ROAS improved by +0.50"],
        )
        eo = fb.to_experience_outcome()
        assert eo.success is True
        assert eo.outcome_level == ExperienceOutcomeLevel.SUCCESS
        assert eo.actual_reward == 0.7
        assert eo.metrics_delta["roas_delta"] == 0.5

    def test_to_experience_outcome_failure(self):
        fb = ExecutionFeedback(
            success=False,
            outcome_level=ExperienceOutcomeLevel.FAILURE,
            error="API timeout",
        )
        eo = fb.to_experience_outcome()
        assert eo.success is False
        assert eo.outcome_level == ExperienceOutcomeLevel.FAILURE
        assert eo.error == "API timeout"

    def test_unique_feedback_id(self):
        fb1 = ExecutionFeedback()
        fb2 = ExecutionFeedback()
        assert fb1.feedback_id != fb2.feedback_id

    def test_created_at_auto_set(self):
        fb = ExecutionFeedback()
        assert fb.created_at != ""


# ═══════════════════════════════════════════════════════════
# 2. RewardCalculator Tests (20)
# ═══════════════════════════════════════════════════════════

class TestRewardCalculator:
    """RewardCalculator 测试."""

    def test_default_weights(self, calculator):
        w = calculator.weights
        assert w["roas"] == 0.40
        assert w["payer_rate"] == 0.30
        assert w["ctr"] == 0.075
        assert w["cvr"] == 0.075

    def test_calculate_all_zero(self, calculator):
        m = RewardMetrics()
        reward = calculator.calculate(m)
        assert reward == 0.5  # sigmoid(0) = 0.5 for all = baseline

    def test_calculate_positive_roas(self, calculator):
        m = RewardMetrics(roas_delta=1.0)
        reward = calculator.calculate(m)
        assert reward > 0.5

    def test_calculate_negative_roas(self, calculator):
        m = RewardMetrics(roas_delta=-1.0)
        reward = calculator.calculate(m)
        assert reward < 0.5

    def test_calculate_strong_positive(self, calculator):
        m = RewardMetrics(
            roas_delta=2.0,
            ctr_delta=0.1,
            cvr_delta=0.1,
            payer_rate_delta=0.05,
            cpi_delta=-0.3,
            retention_d7_delta=0.1,
        )
        reward = calculator.calculate(m)
        assert reward > 0.7

    def test_calculate_strong_negative(self, calculator):
        m = RewardMetrics(
            roas_delta=-2.0,
            cpi_delta=0.5,
            payer_rate_delta=-0.05,
        )
        reward = calculator.calculate(m)
        assert reward < 0.5

    def test_calculate_range(self, calculator):
        for roas in [-5.0, -2.0, -1.0, 0.0, 1.0, 2.0, 5.0]:
            m = RewardMetrics(roas_delta=roas)
            reward = calculator.calculate(m)
            assert 0.0 <= reward <= 1.0

    def test_calculate_with_cpi_improvement(self, calculator):
        m = RewardMetrics(cpi_delta=-0.5)  # CPI 下降 = 改善
        reward = calculator.calculate(m)
        assert reward > 0.5

    def test_calculate_with_cpi_worsening(self, calculator):
        m = RewardMetrics(cpi_delta=0.5)  # CPI 上升 = 恶化
        reward = calculator.calculate(m)
        assert reward < 0.5

    def test_custom_weights(self):
        calc = RewardCalculator(weights={
            "roas": 0.8, "ctr": 0.05, "cvr": 0.05, "payer_rate": 0.05,
            "retention_d7": 0.025, "cpi": 0.025,
        })
        m = RewardMetrics(roas_delta=1.0)
        reward = calc.calculate(m)
        assert reward > 0.5  # ROAS 权重更高

    def test_calculation_count(self, calculator):
        for _ in range(5):
            calculator.calculate(RewardMetrics())
        assert calculator.calculation_count == 5

    def test_weights_returns_copy(self, calculator):
        w = calculator.weights
        w["roas"] = 0.99
        assert calculator.weights["roas"] == 0.40

    def test_payer_rate_contribution(self, calculator):
        m_high = RewardMetrics(payer_rate_delta=0.1)
        m_low = RewardMetrics(payer_rate_delta=-0.1)
        assert calculator.calculate(m_high) > calculator.calculate(m_low)

    def test_ctr_contribution(self, calculator):
        m_pos = RewardMetrics(ctr_delta=0.1)
        m_neg = RewardMetrics(ctr_delta=-0.1)
        assert calculator.calculate(m_pos) > calculator.calculate(m_neg)

    def test_cvr_contribution(self, calculator):
        m_pos = RewardMetrics(cvr_delta=0.1)
        m_neg = RewardMetrics(cvr_delta=-0.1)
        assert calculator.calculate(m_pos) > calculator.calculate(m_neg)

    def test_retention_contribution(self, calculator):
        m_pos = RewardMetrics(retention_d7_delta=0.1)
        m_neg = RewardMetrics(retention_d7_delta=-0.1)
        assert calculator.calculate(m_pos) > calculator.calculate(m_neg)

    def test_combined_positive(self, calculator):
        m = RewardMetrics(
            roas_delta=1.5,
            ctr_delta=0.05,
            cvr_delta=0.05,
            payer_rate_delta=0.03,
            retention_d7_delta=0.05,
            cpi_delta=-0.2,
        )
        reward = calculator.calculate(m)
        assert reward > 0.6

    def test_combined_negative(self, calculator):
        m = RewardMetrics(
            roas_delta=-1.5,
            ctr_delta=-0.05,
            cvr_delta=-0.05,
            payer_rate_delta=-0.03,
            cpi_delta=0.2,
        )
        reward = calculator.calculate(m)
        assert reward < 0.4

    def test_calculate_is_deterministic(self, calculator):
        m = RewardMetrics(roas_delta=0.5, payer_rate_delta=0.02)
        r1 = calculator.calculate(m)
        r2 = calculator.calculate(m)
        assert r1 == r2

    def test_ltv_does_not_affect_default(self, calculator):
        """LTV delta 不在默认权重中，不影响结果."""
        m = RewardMetrics(ltv_d30_delta=10.0)
        r = calculator.calculate(m)
        assert r == 0.5  # 所有默认指标=0, 结果=baseline


# ═══════════════════════════════════════════════════════════
# 3. FeedbackCollector Core Tests (20)
# ═══════════════════════════════════════════════════════════

class TestFeedbackCollectorCore:
    """ExecutionFeedbackCollector 核心功能测试."""

    def test_collect_success_outcome(self, collector):
        outcome = _make_outcome(status=ExecutionStatus.SUCCESS)
        fb = collector.collect(outcome)
        assert fb.success is True
        assert fb.execution_id == outcome.execution_id
        assert fb.action_id == outcome.action_id

    def test_collect_failed_outcome(self, collector):
        outcome = _make_outcome(status=ExecutionStatus.FAILED, error="API error")
        fb = collector.collect(outcome)
        assert fb.success is False
        assert fb.error == "API error"

    def test_collect_with_metrics(self, collector):
        outcome = _make_outcome_with_metrics(roas_delta=1.0, payer_rate_delta=0.03)
        fb = collector.collect(outcome)
        assert fb.metrics.roas_delta == 1.0
        assert fb.metrics.payer_rate_delta == 0.03

    def test_collect_tracks_history(self, collector):
        collector.collect(_make_outcome())
        collector.collect(_make_outcome())
        assert len(collector.get_feedback_history()) == 2

    def test_collect_sets_feedback_id(self, collector):
        fb = collector.collect(_make_outcome())
        assert fb.feedback_id.startswith("fb_")

    def test_collect_high_reward_get_strong_success(self, collector):
        outcome = _make_outcome_with_metrics(
            roas_delta=2.0, payer_rate_delta=0.1, cpi_delta=-0.5
        )
        fb = collector.collect(outcome)
        assert fb.outcome_level == ExperienceOutcomeLevel.STRONG_SUCCESS

    def test_collect_moderate_reward_gets_success(self, collector):
        outcome = _make_outcome_with_metrics(roas_delta=0.5, payer_rate_delta=0.02)
        fb = collector.collect(outcome)
        assert fb.outcome_level == ExperienceOutcomeLevel.SUCCESS

    def test_collect_low_reward_gets_failure(self, collector):
        outcome = _make_outcome_with_metrics(roas_delta=-2.0, cpi_delta=1.0)
        fb = collector.collect(outcome)
        assert fb.outcome_level == ExperienceOutcomeLevel.FAILURE

    def test_collect_quality_with_reality_data(self, collector):
        outcome = _make_outcome(metadata={"reality_data": True})
        fb = collector.collect(outcome)
        assert fb.quality == FeedbackQuality.STRONG

    def test_collect_quality_with_metrics(self, collector):
        outcome = _make_outcome_with_metrics(roas_delta=0.5)
        fb = collector.collect(outcome)
        assert fb.quality == FeedbackQuality.RELIABLE

    def test_collect_quality_weak(self, collector):
        outcome = _make_outcome(status=ExecutionStatus.SUCCESS)
        fb = collector.collect(outcome)
        assert fb.quality == FeedbackQuality.WEAK

    def test_collect_quality_inconclusive(self, collector):
        outcome = _make_outcome(status=ExecutionStatus.FAILED)
        fb = collector.collect(outcome)
        assert fb.quality == FeedbackQuality.INCONCLUSIVE

    def test_collect_generates_insights(self, collector):
        outcome = _make_outcome_with_metrics(
            roas_delta=0.5, payer_rate_delta=0.03, cpi_delta=-0.1
        )
        fb = collector.collect(outcome)
        assert len(fb.insights) > 0

    def test_collect_no_insights_without_metrics(self, collector):
        outcome = _make_outcome()
        fb = collector.collect(outcome)
        assert "No significant metric changes detected" in fb.insights

    def test_collect_metadata_from_outcome(self, collector):
        outcome = _make_outcome(metadata={"confidence": 0.9, "source": "test"})
        fb = collector.collect(outcome)
        assert fb.metadata == {}

    def test_collect_uses_metadata_metrics(self, collector):
        outcome = _make_outcome(
            metadata={"metrics_delta": {"roas_delta": 0.8, "cpi_delta": -0.2}}
        )
        fb = collector.collect(outcome)
        assert fb.metrics.roas_delta == 0.8
        assert fb.metrics.cpi_delta == -0.2

    def test_collect_uses_output_metrics_fallback(self, collector):
        outcome = _make_outcome_with_metrics(roas_delta=0.3)
        fb = collector.collect(outcome)
        assert fb.metrics.roas_delta == 0.3

    def test_collection_count(self, collector):
        for _ in range(3):
            collector.collect(_make_outcome())
        assert collector.stats()["total_collected"] == 3

    def test_get_successful_feedbacks(self, collector):
        collector.collect(_make_outcome(status=ExecutionStatus.SUCCESS))
        collector.collect(_make_outcome(status=ExecutionStatus.FAILED))
        assert len(collector.get_successful_feedbacks()) == 1

    def test_get_failed_feedbacks(self, collector):
        collector.collect(_make_outcome(status=ExecutionStatus.SUCCESS))
        collector.collect(_make_outcome(status=ExecutionStatus.FAILED))
        collector.collect(_make_outcome(status=ExecutionStatus.FAILED))
        assert len(collector.get_failed_feedbacks()) == 2


# ═══════════════════════════════════════════════════════════
# 4. Collect with Metrics (15)
# ═══════════════════════════════════════════════════════════

class TestCollectWithMetrics:
    """指标提取测试."""

    def test_roas_positive_generates_insight(self, collector):
        outcome = _make_outcome_with_metrics(roas_delta=0.5)
        fb = collector.collect(outcome)
        assert any("ROAS improved" in i for i in fb.insights)

    def test_roas_negative_generates_insight(self, collector):
        outcome = _make_outcome_with_metrics(roas_delta=-0.5)
        fb = collector.collect(outcome)
        assert any("ROAS declined" in i for i in fb.insights)

    def test_payer_rate_positive_generates_insight(self, collector):
        outcome = _make_outcome_with_metrics(payer_rate_delta=0.05)
        fb = collector.collect(outcome)
        assert any("Payer rate increased" in i for i in fb.insights)

    def test_payer_rate_negative_generates_insight(self, collector):
        outcome = _make_outcome_with_metrics(payer_rate_delta=-0.05)
        fb = collector.collect(outcome)
        assert any("Payer rate decreased" in i for i in fb.insights)

    def test_cpi_improvement_generates_insight(self, collector):
        outcome = _make_outcome_with_metrics(cpi_delta=-0.2)
        fb = collector.collect(outcome)
        assert any("CPI improved" in i for i in fb.insights)

    def test_cpi_worsening_generates_insight(self, collector):
        outcome = _make_outcome_with_metrics(cpi_delta=0.2)
        fb = collector.collect(outcome)
        assert any("CPI worsened" in i for i in fb.insights)

    def test_retention_improvement_generates_insight(self, collector):
        outcome = _make_outcome_with_metrics(retention_d7_delta=0.05)
        fb = collector.collect(outcome)
        assert any("D7 retention improved" in i for i in fb.insights)

    def test_retention_small_not_triggered(self, collector):
        outcome = _make_outcome_with_metrics(retention_d7_delta=0.01)
        fb = collector.collect(outcome)
        # 微小变化不触发
        assert not any("D7 retention" in i for i in fb.insights)

    def test_high_reward_insight(self, collector):
        outcome = _make_outcome_with_metrics(
            roas_delta=3.0, payer_rate_delta=0.1, cpi_delta=-0.5
        )
        fb = collector.collect(outcome)
        assert any("amplifying" in i for i in fb.insights)

    def test_low_reward_insight(self, collector):
        outcome = _make_outcome_with_metrics(
            roas_delta=-3.0, cpi_delta=1.0
        )
        fb = collector.collect(outcome)
        assert any("suppressing" in i for i in fb.insights)

    def test_metrics_from_output(self, collector):
        outcome = _make_outcome(
            output={"roas_delta": 0.7, "ctr_delta": 0.05}
        )
        fb = collector.collect(outcome)
        assert fb.metrics.roas_delta == 0.7
        assert fb.metrics.ctr_delta == 0.05

    def test_metrics_from_metadata_priority(self, collector):
        outcome = _make_outcome(
            output={"roas_delta": 0.3},
            metadata={"metrics_delta": {"roas_delta": 0.9}},
        )
        fb = collector.collect(outcome)
        assert fb.metrics.roas_delta == 0.9  # metadata 优先

    def test_zero_metrics_no_threshold(self, collector):
        outcome = _make_outcome_with_metrics(
            roas_delta=0.05, cpi_delta=-0.01, payer_rate_delta=0.005
        )
        fb = collector.collect(outcome)
        # 低于阈值不触发洞察
        assert not any("ROAS" in i for i in fb.insights)
        assert not any("Payer rate" in i for i in fb.insights)

    def test_multiple_insights_combined(self, collector):
        outcome = _make_outcome_with_metrics(
            roas_delta=0.5, payer_rate_delta=0.05, cpi_delta=-0.3
        )
        fb = collector.collect(outcome)
        assert len(fb.insights) >= 3

    def test_metrics_from_metadata_direct(self, collector):
        outcome = _make_outcome(
            metadata={
                "reality_data": True,
                "metrics_delta": {
                    "roas_delta": 1.5,
                    "payer_rate_delta": 0.04,
                    "ltv_d30_delta": 2.0,
                },
            }
        )
        fb = collector.collect(outcome)
        assert fb.metrics.roas_delta == 1.5
        assert fb.metrics.ltv_d30_delta == 2.0
        assert fb.quality == FeedbackQuality.STRONG


# ═══════════════════════════════════════════════════════════
# 5. To Experience Tests (15)
# ═══════════════════════════════════════════════════════════

class TestToExperience:
    """转化为 GrowthExperience 测试."""

    def test_to_experience_basic(self, collector):
        outcome = _make_outcome_with_metrics(roas_delta=0.5)
        fb = collector.collect(outcome)
        exp = collector.to_experience(fb)
        assert isinstance(exp, GrowthExperience)
        assert exp.action_type == "promote_winner"
        assert exp.reward == fb.reward

    def test_to_experience_with_context(self, collector):
        outcome = _make_outcome_with_metrics(roas_delta=0.5)
        fb = collector.collect(outcome)
        ctx = _make_context(product_id="game_002")
        exp = collector.to_experience(fb, ctx)
        assert exp.context.product_id == "game_002"

    def test_to_experience_category_creative(self, collector):
        fb = collector.collect(_make_outcome(action_type="create_variants"))
        exp = collector.to_experience(fb)
        assert exp.category == ExperienceCategory.CREATIVE

    def test_to_experience_category_ua(self, collector):
        fb = collector.collect(_make_outcome(action_type="promote_winner"))
        exp = collector.to_experience(fb)
        assert exp.category == ExperienceCategory.UA

    def test_to_experience_category_reduce_budget(self, collector):
        fb = collector.collect(_make_outcome(action_type="reduce_budget"))
        exp = collector.to_experience(fb)
        assert exp.category == ExperienceCategory.UA

    def test_to_experience_tags(self, collector):
        fb = collector.collect(_make_outcome_with_metrics(roas_delta=2.0))
        exp = collector.to_experience(fb)
        assert "promote_winner" in exp.tags
        assert "success" in exp.tags
        assert "high_reward" in exp.tags

    def test_to_experience_tags_failure(self, collector):
        outcome = _make_outcome(status=ExecutionStatus.FAILED, error="timeout")
        fb = collector.collect(outcome)
        exp = collector.to_experience(fb)
        assert "failure" in exp.tags
        assert "low_reward" in exp.tags

    def test_to_experience_metadata(self, collector):
        fb = collector.collect(_make_outcome_with_metrics(roas_delta=0.5))
        exp = collector.to_experience(fb)
        assert exp.metadata["feedback_id"] == fb.feedback_id
        assert exp.metadata["execution_id"] == fb.execution_id

    def test_to_experience_outcome(self, collector):
        fb = collector.collect(_make_outcome_with_metrics(roas_delta=0.8))
        exp = collector.to_experience(fb)
        assert exp.outcome.success is True
        assert exp.outcome.actual_reward == fb.reward

    def test_to_experience_is_successful(self, collector):
        fb = collector.collect(_make_outcome_with_metrics(roas_delta=2.0))
        exp = collector.to_experience(fb)
        assert exp.is_successful() is True

    def test_to_experience_is_failure(self, collector):
        outcome = _make_outcome(status=ExecutionStatus.FAILED)
        fb = collector.collect(outcome)
        exp = collector.to_experience(fb)
        assert exp.is_failure() is True

    def test_to_experience_confidence(self, collector):
        fb = collector.collect(_make_outcome())
        fb.metadata["confidence"] = 0.92
        exp = collector.to_experience(fb)
        assert exp.confidence == 0.92

    def test_to_experience_default_confidence(self, collector):
        fb = collector.collect(_make_outcome())
        exp = collector.to_experience(fb)
        assert exp.confidence == 0.5

    def test_to_experience_batch(self, collector):
        outcomes = [
            _make_outcome_with_metrics(roas_delta=0.5),
            _make_outcome_with_metrics(roas_delta=0.3),
        ]
        fbs = collector.collect_batch(outcomes)
        exps = collector.to_experience_batch(fbs)
        assert len(exps) == 2
        assert all(isinstance(e, GrowthExperience) for e in exps)

    def test_to_experience_experiment_action(self, collector):
        fb = collector.collect(_make_outcome(action_type="start_experiment"))
        exp = collector.to_experience(fb)
        assert exp.category == ExperienceCategory.CREATIVE


# ═══════════════════════════════════════════════════════════
# 6. Collect and Store Tests (15)
# ═══════════════════════════════════════════════════════════

class TestCollectAndStore:
    """收集+存储测试."""

    def test_collect_and_store_basic(self, collector, store):
        outcome = _make_outcome_with_metrics(roas_delta=0.5)
        exp = collector.collect_and_store(outcome, None, store)
        assert isinstance(exp, GrowthExperience)
        assert store.count == 1

    def test_collect_and_store_with_context(self, collector, store):
        outcome = _make_outcome_with_metrics(roas_delta=0.5)
        ctx = _make_context(product_id="game_003")
        exp = collector.collect_and_store(outcome, ctx, store)
        assert exp.context.product_id == "game_003"

    def test_collect_and_store_increments(self, collector, store):
        for _ in range(3):
            collector.collect_and_store(
                _make_outcome_with_metrics(roas_delta=0.5), None, store
            )
        assert store.count == 3

    def test_collect_and_store_batch(self, collector, store):
        outcomes = [
            _make_outcome_with_metrics(roas_delta=0.5),
            _make_outcome_with_metrics(roas_delta=0.3, action_type="create_variants"),
        ]
        exps = collector.collect_and_store_batch(outcomes, None, store)
        assert len(exps) == 2
        assert store.count == 2

    def test_store_single(self, collector, store):
        fb = collector.collect(_make_outcome_with_metrics(roas_delta=0.5))
        exp = collector.to_experience(fb)
        eid = collector.store(exp, store)
        assert eid == exp.experience_id
        assert store.count == 1

    def test_store_batch(self, collector, store):
        fbs = collector.collect_batch([
            _make_outcome_with_metrics(roas_delta=0.5),
            _make_outcome_with_metrics(roas_delta=0.3),
        ])
        exps = collector.to_experience_batch(fbs)
        eids = collector.store_batch(exps, store)
        assert len(eids) == 2
        assert store.count == 2

    def test_collect_and_store_feedback_tracked(self, collector, store):
        collector.collect_and_store(
            _make_outcome_with_metrics(roas_delta=0.5), None, store
        )
        assert len(collector.get_feedback_history()) == 1

    def test_store_fills_experience_outcome(self, collector, store):
        outcome = _make_outcome_with_metrics(
            roas_delta=1.0, payer_rate_delta=0.05
        )
        exp = collector.collect_and_store(outcome, _make_context(), store)
        assert exp.outcome.metrics_delta["roas_delta"] == 1.0
        assert exp.outcome.metrics_delta["payer_rate_delta"] == 0.05

    def test_store_preserves_action_id(self, collector, store):
        outcome = _make_outcome(action_id="ga_special", action_type="scale_campaign")
        exp = collector.collect_and_store(outcome, None, store)
        assert exp.action_id == "ga_special"

    def test_store_high_reward_strong_success(self, collector, store):
        outcome = _make_outcome_with_metrics(
            roas_delta=3.0, payer_rate_delta=0.1, cpi_delta=-0.5
        )
        exp = collector.collect_and_store(outcome, None, store)
        assert exp.outcome.outcome_level == ExperienceOutcomeLevel.STRONG_SUCCESS

    def test_store_failed_experience(self, collector, store):
        outcome = _make_outcome(status=ExecutionStatus.FAILED, error="Budget exceeded")
        exp = collector.collect_and_store(outcome, None, store)
        assert exp.outcome.success is False
        assert "failure" in exp.tags

    def test_store_queryable(self, collector, store):
        collector.collect_and_store(
            _make_outcome_with_metrics(roas_delta=0.5), None, store
        )
        results = store.get_by_action_type("promote_winner")
        assert len(results) == 1

    def test_store_stats_after_collect(self, collector, store):
        for _ in range(5):
            collector.collect_and_store(
                _make_outcome_with_metrics(roas_delta=0.5), None, store
            )
        stats = store.get_stats()
        assert stats.total_experiences == 5

    def test_store_multiple_action_types(self, collector, store):
        actions = ["promote_winner", "create_variants", "start_experiment"]
        for at in actions:
            collector.collect_and_store(
                _make_outcome(action_type=at), None, store
            )
        assert store.count == 3

    def test_collect_and_store_diversify(self, collector, store):
        outcome = _make_outcome(action_type="diversify_population")
        exp = collector.collect_and_store(outcome, None, store)
        assert exp.category == ExperienceCategory.CREATIVE


# ═══════════════════════════════════════════════════════════
# 7. FeedbackPipeline Tests (15)
# ═══════════════════════════════════════════════════════════

class TestFeedbackPipeline:
    """FeedbackPipeline 测试."""

    def test_pipeline_feed(self, pipeline, store):
        outcome = _make_outcome_with_metrics(roas_delta=0.5)
        exp = pipeline.feed(outcome)
        assert isinstance(exp, GrowthExperience)
        assert store.count == 1

    def test_pipeline_feed_with_context(self, pipeline, store):
        outcome = _make_outcome_with_metrics(roas_delta=0.5)
        ctx = _make_context(product_id="game_pipe")
        exp = pipeline.feed(outcome, ctx)
        assert exp.context.product_id == "game_pipe"

    def test_pipeline_feed_batch(self, pipeline, store):
        outcomes = [
            _make_outcome_with_metrics(roas_delta=0.5),
            _make_outcome_with_metrics(roas_delta=0.3),
            _make_outcome_with_metrics(roas_delta=0.1),
        ]
        exps = pipeline.feed_batch(outcomes)
        assert len(exps) == 3
        assert store.count == 3

    def test_pipeline_stats(self, pipeline, store):
        pipeline.feed(_make_outcome_with_metrics(roas_delta=0.5))
        pipeline.feed(_make_outcome_with_metrics(roas_delta=0.3))
        stats = pipeline.stats()
        assert stats["pipeline_count"] == 2
        assert stats["experience_store_count"] == 2

    def test_pipeline_reset(self, pipeline, store):
        pipeline.feed(_make_outcome())
        pipeline.reset()
        assert pipeline.stats()["pipeline_count"] == 0

    def test_pipeline_collector_access(self, pipeline):
        assert isinstance(pipeline.collector, ExecutionFeedbackCollector)

    def test_pipeline_mine_patterns_no_store(self, pipeline):
        patterns = pipeline.mine_patterns()
        assert patterns == []

    def test_pipeline_custom_collector(self, store):
        calc = RewardCalculator(weights={"roas": 0.9, "ctr": 0.025, "cvr": 0.025, "payer_rate": 0.025, "retention_d7": 0.0125, "cpi": 0.0125})
        collector = ExecutionFeedbackCollector(reward_calculator=calc)
        pipeline = FeedbackPipeline(experience_store=store, collector=collector)
        exp = pipeline.feed(_make_outcome_with_metrics(roas_delta=1.0))
        assert exp.reward > 0.5

    def test_pipeline_feed_tracks_feedback(self, pipeline, store):
        pipeline.feed(_make_outcome_with_metrics(roas_delta=0.5))
        assert len(pipeline.collector.get_feedback_history()) == 1

    def test_pipeline_feed_batch_empty(self, pipeline, store):
        exps = pipeline.feed_batch([])
        assert exps == []

    def test_pipeline_feed_failed_outcome(self, pipeline, store):
        outcome = _make_outcome(status=ExecutionStatus.FAILED, error="API error")
        exp = pipeline.feed(outcome)
        assert exp.outcome.success is False
        assert store.count == 1

    def test_pipeline_multiple_feed_then_stats(self, pipeline, store):
        for _ in range(5):
            pipeline.feed(_make_outcome_with_metrics(roas_delta=0.5))
        stats = pipeline.stats()
        assert stats["pipeline_count"] == 5
        assert stats["experience_store_count"] == 5

    def test_pipeline_factory(self, store):
        pipeline = create_feedback_pipeline(experience_store=store)
        exp = pipeline.feed(_make_outcome_with_metrics(roas_delta=0.5))
        assert isinstance(exp, GrowthExperience)

    def test_pipeline_factory_with_weights(self, store):
        pipeline = create_feedback_pipeline(
            experience_store=store,
            weights={"roas": 0.9, "ctr": 0.025, "cvr": 0.025, "payer_rate": 0.025, "retention_d7": 0.0125, "cpi": 0.0125},
        )
        exp = pipeline.feed(_make_outcome_with_metrics(roas_delta=1.0))
        assert exp.reward > 0.5

    def test_pipeline_collector_stats(self, pipeline, store):
        pipeline.feed(_make_outcome_with_metrics(roas_delta=0.5))
        cs = pipeline.stats()["collector_stats"]
        assert cs["total_collected"] == 1


# ═══════════════════════════════════════════════════════════
# 8. Batch Collection Tests (15)
# ═══════════════════════════════════════════════════════════

class TestBatchCollection:
    """批量收集测试."""

    def test_collect_batch(self, collector):
        outcomes = [
            _make_outcome_with_metrics(roas_delta=0.5),
            _make_outcome_with_metrics(roas_delta=0.3),
            _make_outcome_with_metrics(roas_delta=0.1),
        ]
        fbs = collector.collect_batch(outcomes)
        assert len(fbs) == 3
        assert all(isinstance(fb, ExecutionFeedback) for fb in fbs)

    def test_collect_batch_empty(self, collector):
        fbs = collector.collect_batch([])
        assert fbs == []

    def test_collect_batch_mixed(self, collector):
        outcomes = [
            _make_outcome_with_metrics(roas_delta=0.5),
            _make_outcome(status=ExecutionStatus.FAILED),
            _make_outcome_with_metrics(roas_delta=2.0),
        ]
        fbs = collector.collect_batch(outcomes)
        assert fbs[0].success is True
        assert fbs[1].success is False
        assert fbs[2].success is True

    def test_collect_batch_tracks_history(self, collector):
        collector.collect_batch([_make_outcome() for _ in range(5)])
        assert len(collector.get_feedback_history()) == 5

    def test_collect_batch_history_distinct(self, collector):
        fbs = collector.collect_batch([
            _make_outcome(action_id="ga_1"),
            _make_outcome(action_id="ga_2"),
        ])
        assert fbs[0].feedback_id != fbs[1].feedback_id

    def test_batch_to_experience_same_context(self, collector):
        fbs = collector.collect_batch([
            _make_outcome_with_metrics(roas_delta=0.5),
            _make_outcome_with_metrics(roas_delta=0.3),
        ])
        ctx = _make_context()
        exps = collector.to_experience_batch(fbs, ctx)
        assert all(e.context.product_id == "game_001" for e in exps)

    def test_batch_store_all_stored(self, collector, store):
        fbs = collector.collect_batch([
            _make_outcome_with_metrics(roas_delta=0.5),
            _make_outcome_with_metrics(roas_delta=0.3),
        ])
        exps = collector.to_experience_batch(fbs)
        eids = collector.store_batch(exps, store)
        assert len(eids) == 2
        assert store.count == 2

    def test_batch_collect_and_store(self, collector, store):
        outcomes = [_make_outcome_with_metrics(roas_delta=0.5) for _ in range(3)]
        exps = collector.collect_and_store_batch(outcomes, None, store)
        assert len(exps) == 3
        assert store.count == 3

    def test_batch_large(self, collector):
        outcomes = [_make_outcome_with_metrics(roas_delta=0.1) for _ in range(50)]
        fbs = collector.collect_batch(outcomes)
        assert len(fbs) == 50

    def test_batch_all_unique_ids(self, collector):
        fbs = collector.collect_batch([_make_outcome() for _ in range(10)])
        ids = {fb.feedback_id for fb in fbs}
        assert len(ids) == 10

    def test_batch_stats_after(self, collector):
        collector.collect_batch([_make_outcome_with_metrics(roas_delta=0.5) for _ in range(3)])
        s = collector.stats()
        assert s["total_collected"] == 3
        assert s["total_feedbacks"] == 3

    def test_batch_stats_avg_reward(self, collector):
        outcomes = [
            _make_outcome_with_metrics(roas_delta=0.5),
            _make_outcome_with_metrics(roas_delta=0.3),
        ]
        collector.collect_batch(outcomes)
        s = collector.stats()
        assert s["avg_reward"] > 0

    def test_batch_stats_by_quality(self, collector):
        outcomes = [
            _make_outcome_with_metrics(roas_delta=0.5),  # reliable
            _make_outcome(status=ExecutionStatus.FAILED),  # inconclusive
        ]
        collector.collect_batch(outcomes)
        s = collector.stats()
        assert "reliable" in s["by_quality"]
        assert "inconclusive" in s["by_quality"]

    def test_batch_reset(self, collector):
        collector.collect_batch([_make_outcome() for _ in range(5)])
        collector.reset()
        assert len(collector.get_feedback_history()) == 0
        assert collector.stats()["total_collected"] == 0

    def test_batch_action_type_distribution(self, collector, store):
        actions = ["promote_winner", "create_variants", "scale_campaign", "reduce_budget"]
        for at in actions:
            collector.collect_and_store(_make_outcome(action_type=at), None, store)
        stats = store.get_stats()
        assert stats.total_experiences == 4


# ═══════════════════════════════════════════════════════════
# 9. Error Handling Tests (10)
# ═══════════════════════════════════════════════════════════

class TestErrorHandling:
    """错误处理测试."""

    def test_collect_failed_with_error(self, collector):
        outcome = _make_outcome(status=ExecutionStatus.FAILED, error="Connection refused")
        fb = collector.collect(outcome)
        assert fb.success is False
        assert fb.error == "Connection refused"

    def test_collect_no_error_on_success(self, collector):
        outcome = _make_outcome(status=ExecutionStatus.SUCCESS)
        fb = collector.collect(outcome)
        assert fb.error == ""

    def test_collect_preserves_error_in_experience(self, collector, store):
        outcome = _make_outcome(status=ExecutionStatus.FAILED, error="Rate limit hit")
        exp = collector.collect_and_store(outcome, None, store)
        assert exp.outcome.error == "Rate limit hit"

    def test_empty_metrics_handled(self, collector):
        outcome = _make_outcome(output={}, metadata={})
        fb = collector.collect(outcome)
        assert fb.metrics.roas_delta == 0.0
        assert fb.reward == 0.5

    def test_invalid_metrics_ignored(self, collector):
        outcome = _make_outcome(
            output={"roas_delta": "invalid"}
        )
        fb = collector.collect(outcome)
        # 字符串值被忽略，默认为 0.0
        assert fb.metrics.roas_delta == 0.0

    def test_collect_partial_status(self, collector):
        outcome = _make_outcome(status=ExecutionStatus.PARTIAL)
        fb = collector.collect(outcome)
        # PARTIAL 不是 SUCCESS
        assert fb.success is False

    def test_collect_running_status(self, collector):
        outcome = _make_outcome(status=ExecutionStatus.RUNNING)
        fb = collector.collect(outcome)
        assert fb.success is False

    def test_collect_pending_status(self, collector):
        outcome = _make_outcome(status=ExecutionStatus.PENDING)
        fb = collector.collect(outcome)
        assert fb.success is False

    def test_to_experience_without_context(self, collector):
        fb = collector.collect(_make_outcome())
        exp = collector.to_experience(fb)
        assert isinstance(exp, GrowthExperience)
        assert exp.context.action_type == "promote_winner"

    def test_feedback_history_immutable(self, collector):
        collector.collect(_make_outcome())
        history = collector.get_feedback_history()
        history.append(ExecutionFeedback())
        assert len(collector.get_feedback_history()) == 1


# ═══════════════════════════════════════════════════════════
# 10. Regression E14.7.1/E14.7.2 Tests (10)
# ═══════════════════════════════════════════════════════════

class TestRegressionE1471E1472:
    """E14.7.1/E14.7.2 集成回归测试."""

    def test_full_autonomous_learning_loop(self, collector, store):
        """完整自主学习闭环: Signal → Router → Engine → Feedback → Store."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
            GrowthExecutionEngine,
        )

        engine = GrowthExecutionEngine()
        engine.register_default_executors()
        router = GrowthActionRouter()

        signal = EvolutionSignal(
            action=SignalAction.AMPLIFY,
            target_value="genome_001",
            confidence=0.92,
            expected_impact="ROAS +15%",
        )
        result = router.route(signal)
        outcome = engine.execute(result.action)

        # 模拟真实指标
        outcome.metadata["metrics_delta"] = {
            "roas_delta": 0.5,
            "payer_rate_delta": 0.03,
            "cpi_delta": -0.1,
            "ctr_delta": 0.02,
        }
        outcome.metadata["reality_data"] = True

        ctx = _make_context(action_type=outcome.action_type)
        exp = collector.collect_and_store(outcome, ctx, store)

        assert exp.is_successful() is True
        assert store.count == 1
        assert collector.get_feedback_history()[0].quality == FeedbackQuality.STRONG

    def test_amplify_learn_loop(self, collector, store):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
            GrowthExecutionEngine,
        )

        engine = GrowthExecutionEngine()
        engine.register_default_executors()
        router = GrowthActionRouter()

        signal = EvolutionSignal(
            action=SignalAction.AMPLIFY,
            target_value="genome_001",
            confidence=0.92,
            expected_impact="ROAS +15%",
        )
        outcome = engine.execute(router.route(signal).action)
        outcome.metadata["metrics_delta"] = {"roas_delta": 0.8, "payer_rate_delta": 0.05}
        exp = collector.collect_and_store(outcome, _make_context(), store)
        assert exp.reward > 0.6

    def test_suppress_learn_loop(self, collector, store):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
            GrowthExecutionEngine,
        )

        engine = GrowthExecutionEngine()
        engine.register_default_executors()
        router = GrowthActionRouter()

        signal = EvolutionSignal(
            action=SignalAction.SUPPRESS,
            target_value="camp_003",
            confidence=0.85,
            expected_impact="ROAS -20%",
        )
        outcome = engine.execute(router.route(signal, target_id="camp_003").action)
        outcome.metadata["metrics_delta"] = {"roas_delta": -0.3, "cpi_delta": 0.2}
        exp = collector.collect_and_store(outcome, _make_context(), store)
        assert exp.reward < 0.5

    def test_explore_learn_loop(self, collector, store):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
            GrowthExecutionEngine,
        )

        engine = GrowthExecutionEngine()
        engine.register_default_executors()
        router = GrowthActionRouter()

        signal = EvolutionSignal(
            action=SignalAction.EXPLORE,
            target_value="genome_005",
            confidence=0.75,
            expected_impact="New direction",
        )
        outcome = engine.execute(router.route(signal, target_id="genome_005").action)
        outcome.metadata["metrics_delta"] = {"roas_delta": 0.2, "ctr_delta": 0.05}
        exp = collector.collect_and_store(outcome, _make_context(), store)
        assert exp.category == ExperienceCategory.CREATIVE

    def test_maintain_learn_loop(self, collector, store):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
            GrowthExecutionEngine,
        )

        engine = GrowthExecutionEngine()
        engine.register_default_executors()
        router = GrowthActionRouter()

        signal = EvolutionSignal(action=SignalAction.MAINTAIN, confidence=0.55)
        outcome = engine.execute(router.route(signal).action)
        exp = collector.collect_and_store(outcome, _make_context(), store)
        assert exp.action_type == "hold"

    def test_multi_signal_learning_loop(self, collector, store):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
            GrowthExecutionEngine,
        )

        engine = GrowthExecutionEngine()
        engine.register_default_executors()
        router = GrowthActionRouter()

        signals = [
            (SignalAction.AMPLIFY, "genome_001", {"roas_delta": 0.5, "payer_rate_delta": 0.03}),
            (SignalAction.AMPLIFY, "genome_002", {"roas_delta": 0.3, "ctr_delta": 0.02}),
            (SignalAction.AMPLIFY, "genome_003", {"roas_delta": 0.7, "cpi_delta": -0.1}),
        ]

        for sig_action, target, metrics in signals:
            signal = EvolutionSignal(
                action=sig_action,
                target_value=target,
                confidence=0.9,
                expected_impact="Test",
            )
            outcome = engine.execute(router.route(signal).action)
            outcome.metadata["metrics_delta"] = metrics
            collector.collect_and_store(outcome, _make_context(), store)

        assert store.count == 3
        assert len(collector.get_feedback_history()) == 3

    def test_learning_loop_then_query(self, collector, store):
        """学习后可以查询经验."""
        for i in range(5):
            outcome = _make_outcome_with_metrics(
                roas_delta=0.5, action_type="promote_winner"
            )
            collector.collect_and_store(outcome, _make_context(), store)

        results = store.get_by_action_type("promote_winner")
        assert len(results) == 5

    def test_learning_loop_stats(self, collector, store):
        for i in range(3):
            outcome = _make_outcome_with_metrics(roas_delta=0.5)
            collector.collect_and_store(outcome, _make_context(), store)
        outcome = _make_outcome(status=ExecutionStatus.FAILED)
        collector.collect_and_store(outcome, _make_context(), store)

        stats = store.get_stats()
        assert stats.total_experiences == 4
        assert stats.total_success == 3
        assert stats.total_failure == 1

    def test_pipeline_with_router_to_engine(self, pipeline, store):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
            GrowthExecutionEngine,
        )

        engine = GrowthExecutionEngine()
        engine.register_default_executors()
        router = GrowthActionRouter()

        signal = EvolutionSignal(
            action=SignalAction.AMPLIFY,
            target_value="genome_001",
            confidence=0.92,
            expected_impact="ROAS +15%",
        )
        outcome = engine.execute(router.route(signal).action)
        outcome.metadata["metrics_delta"] = {"roas_delta": 0.5}

        exp = pipeline.feed(outcome, _make_context())
        assert isinstance(exp, GrowthExperience)
        assert store.count == 1

    def test_pipeline_reset_does_not_affect_store(self, pipeline, store):
        pipeline.feed(_make_outcome_with_metrics(roas_delta=0.5))
        pipeline.reset()
        assert store.count == 1  # Store 不受影响
        assert pipeline.stats()["pipeline_count"] == 0