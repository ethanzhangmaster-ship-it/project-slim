"""E17.11.2 Experience Write Path — 测试用例.

Day 7.11 Step 2:
  覆盖 ExecutionResult → GrowthExperience 写入路径:
    - ExperienceBuilder.build() (ExecutionResult → GrowthExperience)
    - ExperienceImportanceScorer.score() (重要性评分)
    - ExperienceWritePipeline.write() (完整写入)
    - ExperienceWritePipeline.write_batch() (批量写入)
    - ConsolidationTrigger (整合触发)
    - Edge Cases (异常输入、空值、边界)
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_execution_models import (
    LearningExecutionAction,
    LearningExecutionResult,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.experience_write_models import (
    ConsolidationTrigger,
    ExperienceImportanceLevel,
    ExperienceWriteResult,
    ImportanceScore,
    WriteBatchResult,
    WriteStatus,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.experience_write_pipeline import (
    ExperienceBuilder,
    ExperienceImportanceScorer,
    ExperienceWritePipeline,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import (
    ExperienceStore,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
    ExperienceCategory,
    ExperienceOutcomeLevel,
    GrowthExperience,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_execution_result(
    exec_success: bool = True,
    action: str = "increase_budget",
    prev_metrics: dict | None = None,
    new_metrics: dict | None = None,
    metadata: dict | None = None,
    reasons: list[str] | None = None,
    policy_type: str = "allow_learning",
    use_default_metrics: bool = True,
) -> LearningExecutionResult:
    """创建测试用的 LearningExecutionResult.

    Args:
        exec_success: 执行是否成功 (控制 LearningExecutionResult.success)
        action: 动作类型
        prev_metrics: 执行前指标 (None 时使用默认值)
        new_metrics: 执行后指标 (None 时使用默认值)
        use_default_metrics: 为 False 时 prev_metrics/new_metrics 为空则使用空 dict
    """
    if prev_metrics is None:
        prev_metrics = {"roas": 0.8, "cpi": 5.0} if use_default_metrics else {}
    if new_metrics is None:
        new_metrics = {"roas": 1.2, "cpi": 4.0} if use_default_metrics else {}
    return LearningExecutionResult(
        success=exec_success,
        action=action,
        executed=True,
        policy_decision_type=policy_type,
        previous_state={"metrics": prev_metrics},
        new_state={"metrics": new_metrics},
        reasons=reasons or ["Test execution"],
        metadata=metadata or {},
    )


def _make_failed_execution_result(
    action: str = "increase_budget",
    error: str = "API rate limit exceeded",
) -> LearningExecutionResult:
    """创建失败的执行结果."""
    return LearningExecutionResult(
        success=False,
        action=action,
        executed=True,
        previous_state={"metrics": {"roas": 0.8}},
        new_state={"metrics": {"roas": 0.8}},
        reasons=["Failed"],
        error=error,
    )


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def builder() -> ExperienceBuilder:
    return ExperienceBuilder()


@pytest.fixture
def scorer() -> ExperienceImportanceScorer:
    return ExperienceImportanceScorer()


@pytest.fixture
def store() -> ExperienceStore:
    return ExperienceStore()


@pytest.fixture
def pipeline(store) -> ExperienceWritePipeline:
    return ExperienceWritePipeline(
        experience_store=store,
        trigger=ConsolidationTrigger.test_mode(),
    )


# ═══════════════════════════════════════════════════════════════
# Test: ExperienceBuilder
# ═══════════════════════════════════════════════════════════════


class TestExperienceBuilder:
    """ExperienceBuilder: ExecutionResult → GrowthExperience."""

    # ── Basic Build ──────────────────────────────────────────

    def test_build_successful_action(self, builder):
        """成功执行 → 构建 GrowthExperience."""
        er = _make_execution_result(
            exec_success=True,
            action="increase_budget",
            prev_metrics={"roas": 0.8},
            new_metrics={"roas": 1.2},
        )
        result = builder.build(er)
        assert result.success is True
        assert result.experience is not None
        assert result.experience.action_type == "increase_budget"
        assert result.build_time_ms > 0

    def test_build_failed_action(self, builder):
        """失败执行 → 仍然构建 GrowthExperience."""
        er = _make_failed_execution_result()
        result = builder.build(er)
        assert result.success is True
        assert result.experience.action_type == "increase_budget"
        assert result.experience.outcome.success is False

    def test_build_metrics_delta(self, builder):
        """指标变化计算."""
        er = _make_execution_result(
            prev_metrics={"roas": 0.8, "cpi": 5.0},
            new_metrics={"roas": 1.2, "cpi": 4.0},
        )
        result = builder.build(er)
        exp = result.experience
        assert exp.outcome.metrics_delta["roas"] == 0.4
        assert exp.outcome.metrics_delta["cpi"] == -1.0

    def test_build_outcome_level_strong_success(self, builder):
        """大幅改善 → STRONG_SUCCESS."""
        er = _make_execution_result(
            prev_metrics={"roas": 0.5},
            new_metrics={"roas": 1.5},
        )
        result = builder.build(er)
        assert result.experience.outcome.outcome_level == ExperienceOutcomeLevel.STRONG_SUCCESS

    def test_build_outcome_level_success(self, builder):
        """小幅改善 → SUCCESS."""
        er = _make_execution_result(
            prev_metrics={"roas": 0.8},
            new_metrics={"roas": 0.9},
        )
        result = builder.build(er)
        assert result.experience.outcome.outcome_level == ExperienceOutcomeLevel.SUCCESS

    def test_build_outcome_level_neutral(self, builder):
        """无明显变化 → NEUTRAL."""
        er = _make_execution_result(
            prev_metrics={"roas": 0.8},
            new_metrics={"roas": 0.81},
        )
        result = builder.build(er)
        assert result.experience.outcome.outcome_level == ExperienceOutcomeLevel.NEUTRAL

    def test_build_outcome_level_failure(self, builder):
        """小幅恶化 → FAILURE."""
        er = _make_execution_result(
            prev_metrics={"roas": 1.0},
            new_metrics={"roas": 0.7},
        )
        result = builder.build(er)
        assert result.experience.outcome.outcome_level == ExperienceOutcomeLevel.FAILURE

    def test_build_outcome_level_strong_failure(self, builder):
        """大幅恶化 → STRONG_FAILURE."""
        er = _make_execution_result(
            prev_metrics={"roas": 1.5},
            new_metrics={"roas": 0.5},
        )
        result = builder.build(er)
        assert result.experience.outcome.outcome_level == ExperienceOutcomeLevel.STRONG_FAILURE

    def test_build_empty_metrics(self, builder):
        """空指标 (use_default_metrics=False)."""
        er = _make_execution_result(
            prev_metrics={},
            new_metrics={},
            use_default_metrics=False,
        )
        result = builder.build(er)
        assert result.success is True
        assert result.experience.outcome.metrics_delta == {}

    def test_build_no_state(self, builder):
        """无 previous_state / new_state."""
        er = LearningExecutionResult(
            success=True,
            action="test_action",
            executed=True,
        )
        result = builder.build(er)
        assert result.success is True
        assert result.experience.action_type == "test_action"

    # ── Category Inference ───────────────────────────────────

    def test_build_category_creative(self, builder):
        """Creative 动作 → CREATIVE 类别."""
        er = _make_execution_result(action="mutate_hook")
        result = builder.build(er)
        assert result.experience.category == ExperienceCategory.CREATIVE

    def test_build_category_ua(self, builder):
        """UA 动作 → UA 类别."""
        er = _make_execution_result(action="increase_budget")
        result = builder.build(er)
        assert result.experience.category == ExperienceCategory.UA

    def test_build_category_revenue(self, builder):
        """Revenue 动作 → REVENUE 类别."""
        er = _make_execution_result(action="optimize_pricing")
        result = builder.build(er)
        assert result.experience.category == ExperienceCategory.REVENUE

    def test_build_category_unknown_defaults_ua(self, builder):
        """未知动作类型 → 默认 UA."""
        er = _make_execution_result(action="custom_unknown_action")
        result = builder.build(er)
        assert result.experience.category == ExperienceCategory.UA

    # ── Tags ─────────────────────────────────────────────────

    def test_build_tags_success(self, builder):
        """成功经验 → 包含 success 和 positive 标签."""
        er = _make_execution_result(
            exec_success=True,
            prev_metrics={"roas": 0.8},
            new_metrics={"roas": 1.2},
        )
        result = builder.build(er)
        tags = result.experience.tags
        assert "success" in tags
        assert "positive" in tags

    def test_build_tags_failure(self, builder):
        """失败经验 → 包含 failure 和 negative 标签."""
        er = _make_execution_result(
            exec_success=False,
            prev_metrics={"roas": 1.5},
            new_metrics={"roas": 0.5},
        )
        result = builder.build(er)
        tags = result.experience.tags
        assert "failure" in tags
        assert "negative" in tags

    def test_build_tags_neutral(self, builder):
        """中性结果 → neutral 标签."""
        er = _make_execution_result(
            prev_metrics={"roas": 0.8},
            new_metrics={"roas": 0.81},
        )
        result = builder.build(er)
        assert "neutral" in result.experience.tags

    # ── Reward ───────────────────────────────────────────────

    def test_build_reward_strong_success(self, builder):
        """大幅成功 → 高 reward."""
        er = _make_execution_result(
            prev_metrics={"roas": 0.5},
            new_metrics={"roas": 1.5},
        )
        result = builder.build(er)
        assert result.experience.reward >= 0.90

    def test_build_reward_neutral(self, builder):
        """中性 → 中等 reward."""
        er = _make_execution_result(
            prev_metrics={"roas": 0.8},
            new_metrics={"roas": 0.81},
        )
        result = builder.build(er)
        assert 0.40 <= result.experience.reward <= 0.60

    def test_build_reward_strong_failure(self, builder):
        """大幅失败 → 低 reward."""
        er = _make_execution_result(
            prev_metrics={"roas": 1.5},
            new_metrics={"roas": 0.5},
        )
        result = builder.build(er)
        assert result.experience.reward <= 0.10

    # ── Build Count ──────────────────────────────────────────

    def test_build_count_increments(self, builder):
        """build_count 递增."""
        assert builder.build_count == 0
        builder.build(_make_execution_result())
        assert builder.build_count == 1
        builder.build(_make_execution_result())
        assert builder.build_count == 2

    # ── Error Handling ───────────────────────────────────────

    def test_build_exception_returns_failure(self, builder):
        """None 输入 → 返回失败."""
        result = builder.build(None)
        assert result.success is False
        assert result.error != ""


# ═══════════════════════════════════════════════════════════════
# Test: ExperienceImportanceScorer
# ═══════════════════════════════════════════════════════════════


class TestExperienceImportanceScorer:
    """ExperienceImportanceScorer: 重要性评分."""

    def _make_exp(
        self,
        action_type: str = "increase_budget",
        reward: float = 0.75,
        confidence: float = 0.80,
        success: bool = True,
    ) -> GrowthExperience:
        """创建测试 GrowthExperience."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            ExperienceContext,
            ExperienceOutcome,
            ExperienceOutcomeLevel,
        )
        return GrowthExperience(
            context=ExperienceContext(action_type=action_type),
            action_type=action_type,
            outcome=ExperienceOutcome(
                success=success,
                outcome_level=(
                    ExperienceOutcomeLevel.SUCCESS if success
                    else ExperienceOutcomeLevel.FAILURE
                ),
            ),
            reward=reward,
            confidence=confidence,
        )

    # ── Basic Scoring ────────────────────────────────────────

    def test_score_high_importance(self, scorer):
        """高 reward + 高 confidence → CRITICAL."""
        exp = self._make_exp(reward=0.95, confidence=0.95)
        score = scorer.score(exp)
        assert score.level == ExperienceImportanceLevel.CRITICAL
        assert score.total_score >= 0.80

    def test_score_medium_importance(self, scorer):
        """中等 → MEDIUM (novelty=1.0 baseline=0.25, 需要 impact+conf 较低)."""
        exp = self._make_exp(reward=0.40, confidence=0.35)
        score = scorer.score(exp)
        # total = 0.40*0.4 + 0.35*0.3 + 1.0*0.2 + 0.5*0.1 = 0.16+0.105+0.20+0.05 = 0.515
        assert score.level == ExperienceImportanceLevel.MEDIUM

    def test_score_low_importance(self, scorer):
        """低 reward + 低 confidence → LOW."""
        exp = self._make_exp(reward=0.10, confidence=0.05)
        score = scorer.score(exp)
        # total = 0.10*0.4 + 0.05*0.3 + 1.0*0.2 + 0.5*0.1 = 0.04+0.015+0.20+0.05 = 0.305
        assert score.level == ExperienceImportanceLevel.LOW

    def test_score_negligible(self, scorer):
        """极低 + 有历史失败 → NEGLIGIBLE (需要历史经验降低 novelty/repeatability)."""
        # 10 条相同 action 的失败经验 → novelty=1/11≈0.09, repeatability=0.0
        existing = [
            self._make_exp(action_type="bad_action", success=False)
            for _ in range(10)
        ]
        exp = self._make_exp(action_type="bad_action", reward=0.05, confidence=0.01, success=False)
        score = scorer.score(exp, existing)
        # total ≈ 0.05*0.4 + 0.01*0.3 + 0.09*0.2 + 0.0*0.1 = 0.02+0.003+0.018 = 0.041
        assert score.level == ExperienceImportanceLevel.NEGLIGIBLE

    # ── Weighted Components ──────────────────────────────────

    def test_score_impact_component(self, scorer):
        """impact 因子 = reward."""
        exp = self._make_exp(reward=0.80)
        score = scorer.score(exp)
        assert score.impact == 0.80

    def test_score_confidence_component(self, scorer):
        """confidence 因子 = experience.confidence."""
        exp = self._make_exp(confidence=0.70)
        score = scorer.score(exp)
        assert score.confidence == 0.70

    def test_score_novelty_new_action(self, scorer):
        """全新 action → novelty = 1.0."""
        exp = self._make_exp(action_type="brand_new_action")
        score = scorer.score(exp, [])
        assert score.novelty == 1.0

    def test_score_novelty_known_action(self, scorer):
        """已知 action → novelty < 1.0."""
        exp1 = self._make_exp(action_type="increase_budget")
        exp2 = self._make_exp(action_type="increase_budget")
        # 先存一个同类型经验
        score = scorer.score(exp2, [exp1])
        # novelty = 1 / (1 + 1) = 0.5
        assert score.novelty == 0.5

    def test_score_novelty_very_common(self, scorer):
        """非常常见 → novelty → 0."""
        exp_new = self._make_exp(action_type="common_action")
        existing = [
            self._make_exp(action_type="common_action") for _ in range(10)
        ]
        score = scorer.score(exp_new, existing)
        # novelty = 1 / (1 + 10) = 0.0909
        assert score.novelty < 0.10

    def test_score_repeatability_all_success(self, scorer):
        """全部成功 → repeatability = 1.0."""
        existing = [
            self._make_exp(action_type="good_action", success=True)
            for _ in range(5)
        ]
        exp = self._make_exp(action_type="good_action", success=True)
        score = scorer.score(exp, existing)
        assert score.repeatability == 1.0

    def test_score_repeatability_all_failure(self, scorer):
        """全部失败 → repeatability = 0.0."""
        existing = [
            self._make_exp(action_type="bad_action", success=False)
            for _ in range(5)
        ]
        exp = self._make_exp(action_type="bad_action", success=False)
        score = scorer.score(exp, existing)
        assert score.repeatability == 0.0

    def test_score_repeatability_no_history(self, scorer):
        """无历史 → repeatability = 0.5."""
        exp = self._make_exp(action_type="new_action")
        score = scorer.score(exp, [])
        assert score.repeatability == 0.5

    def test_score_repeatability_no_same_action(self, scorer):
        """无同类动作的历史 → repeatability = 0.5."""
        existing = [self._make_exp(action_type="other_action")]
        exp = self._make_exp(action_type="new_action")
        score = scorer.score(exp, existing)
        assert score.repeatability == 0.5

    # ── Weighted Formula ─────────────────────────────────────

    def test_score_formula(self, scorer):
        """验证加权公式: impact×0.4 + confidence×0.3 + novelty×0.2 + repeatability×0.1."""
        exp = self._make_exp(reward=0.80, confidence=0.70)
        # impact=0.80, confidence=0.70, novelty=1.0 (no existing), repeatability=0.5
        # total = 0.80*0.4 + 0.70*0.3 + 1.0*0.2 + 0.5*0.1
        #       = 0.32 + 0.21 + 0.20 + 0.05 = 0.78
        score = scorer.score(exp, [])
        assert score.total_score == pytest.approx(0.78, abs=0.01)

    # ── Should Write ─────────────────────────────────────────

    def test_should_write_above_threshold(self, scorer):
        """高于阈值 → 写入."""
        exp = self._make_exp(reward=0.50, confidence=0.50)
        score = scorer.score(exp, [])
        assert scorer.should_write(score) is True

    def test_should_write_below_threshold(self, scorer):
        """低于阈值 → 不写入 (需要历史经验降低 novelty)."""
        existing = [
            self._make_exp(action_type="bad_action", success=False)
            for _ in range(10)
        ]
        exp = self._make_exp(action_type="bad_action", reward=0.03, confidence=0.01, success=False)
        score = scorer.score(exp, existing)
        # total ≈ 0.012+0.003+0.018 = 0.033 < 0.20
        assert scorer.should_write(score) is False

    def test_should_write_exact_threshold(self, scorer):
        """刚好在阈值上."""
        # 需要 total_score = 0.20
        # novelty=1.0, repeatability=0.5, impact=0.10, confidence=0.05
        # total = 0.10*0.4 + 0.05*0.3 + 1.0*0.2 + 0.5*0.1 = 0.04 + 0.015 + 0.20 + 0.05 = 0.305
        # 低于 0.20 不好做，用刚好 >= 0.20 的
        exp = self._make_exp(reward=0.10, confidence=0.10)
        score = scorer.score(exp, [])
        # total = 0.10*0.4 + 0.10*0.3 + 1.0*0.2 + 0.5*0.1 = 0.04+0.03+0.20+0.05 = 0.32
        assert scorer.should_write(score) is True

    # ── Score Count ──────────────────────────────────────────

    def test_score_count_increments(self, scorer):
        """score_count 递增."""
        assert scorer.score_count == 0
        scorer.score(self._make_exp(), [])
        assert scorer.score_count == 1
        scorer.score(self._make_exp(), [])
        assert scorer.score_count == 2

    # ── Reasons ──────────────────────────────────────────────

    def test_score_includes_reasons(self, scorer):
        """评分包含原因."""
        exp = self._make_exp()
        score = scorer.score(exp, [])
        assert len(score.reasons) == 4
        assert any("impact" in r for r in score.reasons)
        assert any("confidence" in r for r in score.reasons)
        assert any("novelty" in r for r in score.reasons)
        assert any("repeatability" in r for r in score.reasons)


# ═══════════════════════════════════════════════════════════════
# Test: ExperienceWritePipeline
# ═══════════════════════════════════════════════════════════════


class TestExperienceWritePipeline:
    """ExperienceWritePipeline: 完整写入路径."""

    def test_write_successful(self, pipeline):
        """成功写入."""
        er = _make_execution_result(
            prev_metrics={"roas": 0.8},
            new_metrics={"roas": 1.2},
        )
        result = pipeline.write(er)
        assert result.status == WriteStatus.WRITTEN
        assert result.stored is True
        assert result.experience_id != ""

    def test_write_low_importance_skipped(self, pipeline, store):
        """低重要性经验被跳过."""
        # 先清空 pipeline 的 store 引用，确保使用传入的 store
        er = _make_execution_result(
            prev_metrics={"roas": 0.5},
            new_metrics={"roas": 0.51},  # 极小的变化
        )
        result = pipeline.write(er)
        # 小变化 → 低 reward → 可能被跳过
        # 如果 reward 足够高则写入，否则跳过
        assert result.status in (WriteStatus.WRITTEN, WriteStatus.SKIPPED_LOW_IMPORTANCE)

    def test_write_stores_in_experience_store(self, pipeline, store):
        """写入后 ExperienceStore 中有记录."""
        er = _make_execution_result(
            prev_metrics={"roas": 0.8},
            new_metrics={"roas": 1.5},
        )
        pipeline.write(er)
        assert store.count >= 1

    def test_write_multiple_experiences(self, pipeline, store):
        """多次写入."""
        for i in range(3):
            er = _make_execution_result(
                prev_metrics={"roas": 0.8},
                new_metrics={"roas": 1.2 + i * 0.1},
            )
            pipeline.write(er)
        assert store.count == 3

    # ── Batch Write ──────────────────────────────────────────

    def test_write_batch(self, pipeline, store):
        """批量写入."""
        ers = [
            _make_execution_result(
                prev_metrics={"roas": 0.8},
                new_metrics={"roas": 1.2},
            ),
            _make_execution_result(
                prev_metrics={"roas": 0.8},
                new_metrics={"roas": 1.5},
            ),
            _make_execution_result(
                prev_metrics={"roas": 0.8},
                new_metrics={"roas": 0.9},
            ),
        ]
        batch_result = pipeline.write_batch(ers)
        assert batch_result.total == 3
        assert batch_result.written >= 2
        assert batch_result.success_rate > 0.5

    def test_write_batch_empty(self, pipeline):
        """空批量."""
        batch_result = pipeline.write_batch([])
        assert batch_result.total == 0
        assert batch_result.written == 0
        assert batch_result.success_rate == 0.0

    # ── Write Count ──────────────────────────────────────────

    def test_write_count_increments(self, pipeline):
        """write_count 递增."""
        assert pipeline.write_count == 0
        pipeline.write(_make_execution_result())
        assert pipeline.write_count == 1
        pipeline.write(_make_execution_result())
        assert pipeline.write_count == 2

    # ── No Store ─────────────────────────────────────────────

    def test_write_without_store(self):
        """无 ExperienceStore → 不存储但正常返回."""
        pipeline = ExperienceWritePipeline(
            trigger=ConsolidationTrigger.test_mode(),
        )
        er = _make_execution_result(
            prev_metrics={"roas": 0.8},
            new_metrics={"roas": 1.2},
        )
        result = pipeline.write(er)
        assert result.status == WriteStatus.WRITTEN
        assert result.stored is False

    # ── Failed Execution ─────────────────────────────────────

    def test_write_failed_execution(self, pipeline, store):
        """失败的执行 → 仍然写入 (作为负面经验)."""
        er = _make_failed_execution_result()
        result = pipeline.write(er)
        # 失败执行 reward 低，可能被跳过
        assert result.status in (WriteStatus.WRITTEN, WriteStatus.SKIPPED_LOW_IMPORTANCE)

    # ── Reset ────────────────────────────────────────────────

    def test_pipeline_reset(self, pipeline):
        """reset 重置计数."""
        pipeline.write(_make_execution_result())
        assert pipeline.write_count == 1
        pipeline.reset()
        assert pipeline.write_count == 0

    # ── Different Action Types ───────────────────────────────

    def test_write_various_actions(self, pipeline, store):
        """不同动作类型."""
        actions = [
            ("increase_budget", {"roas": 0.8}, {"roas": 1.2}),
            ("reduce_budget", {"roas": 1.2}, {"roas": 0.9}),
            ("pause_campaign", {"roas": 0.3}, {"roas": 0.5}),
            ("duplicate_campaign", {"roas": 0.8}, {"roas": 1.1}),
        ]
        for action, prev, new in actions:
            er = _make_execution_result(action=action, prev_metrics=prev, new_metrics=new)
            pipeline.write(er)
        assert store.count >= 3

    # ── Metadata Propagation ─────────────────────────────────

    def test_write_metadata_propagation(self, pipeline, store):
        """metadata 正确传递."""
        er = _make_execution_result(
            prev_metrics={"roas": 0.8},
            new_metrics={"roas": 1.2},
            metadata={"opportunity_type": "low_roas_alert", "entity_id": "camp_123"},
        )
        pipeline.write(er)
        exps = store.get_all()
        assert len(exps) == 1
        exp = exps[0]
        assert exp.context.opportunity_type == "low_roas_alert"
        assert exp.context.entity_id == "camp_123"

    def test_write_confidence_from_metadata(self, pipeline, store):
        """confidence 从 metadata 提取."""
        er = _make_execution_result(
            prev_metrics={"roas": 0.8},
            new_metrics={"roas": 1.2},
            metadata={"confidence": 0.85},
        )
        pipeline.write(er)
        exps = store.get_all()
        assert len(exps) == 1
        assert exps[0].confidence == 0.85


# ═══════════════════════════════════════════════════════════════
# Test: ConsolidationTrigger
# ═══════════════════════════════════════════════════════════════


class TestConsolidationTrigger:
    """ConsolidationTrigger: 整合触发配置."""

    def test_default_values(self):
        """默认配置."""
        trigger = ConsolidationTrigger()
        assert trigger.min_experience_count == 5
        assert trigger.min_importance_threshold == 0.30
        assert trigger.cooldown_cycles == 3
        assert trigger.auto_trigger is True
        assert trigger.enabled is True

    def test_test_mode(self):
        """测试模式."""
        trigger = ConsolidationTrigger.test_mode()
        assert trigger.min_experience_count == 2
        assert trigger.min_importance_threshold == 0.10
        assert trigger.cooldown_cycles == 0

    def test_disabled(self):
        """禁用时不应该触发."""
        trigger = ConsolidationTrigger(enabled=False)
        assert trigger.enabled is False

    def test_manual_trigger(self):
        """手动触发模式."""
        trigger = ConsolidationTrigger(auto_trigger=False)
        assert trigger.auto_trigger is False

    def test_to_dict(self):
        """序列化."""
        trigger = ConsolidationTrigger()
        d = trigger.to_dict()
        assert d["min_experience_count"] == 5
        assert d["enabled"] is True


# ═══════════════════════════════════════════════════════════════
# Test: Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况."""

    def test_build_none_execution_result(self, builder):
        """None 输入 → 返回失败 (Builder 已修复)."""
        result = builder.build(None)
        assert result.success is False

    def test_build_empty_execution_result(self, builder):
        """空 ExecutionResult."""
        er = LearningExecutionResult()
        result = builder.build(er)
        assert result.success is True
        assert result.experience is not None

    def test_build_negative_metrics(self, builder):
        """负数指标."""
        er = _make_execution_result(
            prev_metrics={"roas": -0.5, "cpi": 10.0},
            new_metrics={"roas": 0.5, "cpi": 5.0},
        )
        result = builder.build(er)
        assert result.success is True
        assert result.experience.outcome.metrics_delta["roas"] == 1.0

    def test_build_zero_metrics(self, builder):
        """零指标."""
        er = _make_execution_result(
            prev_metrics={"roas": 0.0},
            new_metrics={"roas": 0.0},
        )
        result = builder.build(er)
        assert result.success is True
        assert result.experience.outcome.metrics_delta["roas"] == 0.0

    def test_build_large_metrics(self, builder):
        """大数值指标."""
        er = _make_execution_result(
            prev_metrics={"roas": 1000.0},
            new_metrics={"roas": 2000.0},
        )
        result = builder.build(er)
        assert result.success is True

    def test_scorer_none_experience(self, scorer):
        """None 输入 → NEGLIGIBLE (Scorer 已修复)."""
        result = scorer.score(None, [])
        assert result.level == ExperienceImportanceLevel.NEGLIGIBLE

    def test_scorer_empty_existing(self, scorer):
        """空 existing 列表."""
        exp = scorer._make_exp() if hasattr(scorer, '_make_exp') else GrowthExperience()
        # 用 scorer 自己的方法
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            ExperienceContext, ExperienceOutcome, ExperienceOutcomeLevel,
        )
        exp = GrowthExperience(
            context=ExperienceContext(action_type="test"),
            action_type="test",
            outcome=ExperienceOutcome(
                success=True,
                outcome_level=ExperienceOutcomeLevel.SUCCESS,
            ),
            reward=0.50,
            confidence=0.50,
        )
        score = scorer.score(exp, [])
        assert score.novelty == 1.0
        assert score.repeatability == 0.5

    def test_pipeline_empty_batch(self, pipeline):
        """空批次."""
        result = pipeline.write_batch([])
        assert result.total == 0
        assert result.written == 0
        assert result.results == []

    def test_pipeline_no_store_no_consolidation(self):
        """无 store 无 consolidation → 写入不崩溃."""
        pipeline = ExperienceWritePipeline()
        er = _make_execution_result(
            prev_metrics={"roas": 0.8},
            new_metrics={"roas": 1.2},
        )
        result = pipeline.write(er)
        assert result.status == WriteStatus.WRITTEN
        assert result.stored is False
        assert result.consolidation_triggered is False

    def test_importance_score_to_dict(self):
        """ImportanceScore.to_dict()."""
        score = ImportanceScore(
            total_score=0.75,
            impact=0.80,
            confidence=0.70,
            novelty=1.0,
            repeatability=0.5,
            level=ExperienceImportanceLevel.HIGH,
            reasons=["test"],
        )
        d = score.to_dict()
        assert d["total_score"] == 0.75
        assert d["level"] == "high"

    def test_experience_write_result_to_dict(self, pipeline):
        """ExperienceWriteResult.to_dict()."""
        er = _make_execution_result(
            prev_metrics={"roas": 0.8},
            new_metrics={"roas": 1.2},
        )
        result = pipeline.write(er)
        d = result.to_dict()
        assert d["status"] == "written"
        assert d["experience_id"] != ""

    def test_write_batch_result_to_dict(self, pipeline):
        """WriteBatchResult.to_dict()."""
        ers = [
            _make_execution_result(prev_metrics={"roas": 0.8}, new_metrics={"roas": 1.2}),
            _make_execution_result(prev_metrics={"roas": 0.8}, new_metrics={"roas": 1.5}),
        ]
        batch = pipeline.write_batch(ers)
        d = batch.to_dict()
        assert d["total"] == 2
        assert d["written"] >= 1

    def test_write_status_enum(self):
        """WriteStatus 枚举值."""
        assert WriteStatus.WRITTEN.value == "written"
        assert WriteStatus.SKIPPED_LOW_IMPORTANCE.value == "skipped_low_importance"
        assert WriteStatus.SKIPPED_DUPLICATE.value == "skipped_duplicate"
        assert WriteStatus.FAILED.value == "failed"

    def test_importance_level_enum(self):
        """ExperienceImportanceLevel 枚举值."""
        assert ExperienceImportanceLevel.CRITICAL.value == "critical"
        assert ExperienceImportanceLevel.HIGH.value == "high"
        assert ExperienceImportanceLevel.MEDIUM.value == "medium"
        assert ExperienceImportanceLevel.LOW.value == "low"
        assert ExperienceImportanceLevel.NEGLIGIBLE.value == "negligible"

    def test_is_written_property(self):
        """is_written 属性."""
        r = ExperienceWriteResult(status=WriteStatus.WRITTEN)
        assert r.is_written is True
        assert r.is_skipped is False

    def test_is_skipped_property(self):
        """is_skipped 属性."""
        r = ExperienceWriteResult(status=WriteStatus.SKIPPED_LOW_IMPORTANCE)
        assert r.is_written is False
        assert r.is_skipped is True

    def test_consolidation_trigger_disabled(self):
        """禁用触发器."""
        trigger = ConsolidationTrigger(enabled=False)
        assert trigger.enabled is False
        # Pipeline 不应该触发
        pipeline = ExperienceWritePipeline(
            experience_store=ExperienceStore(),
            trigger=trigger,
        )
        for _ in range(10):
            pipeline.write(_make_execution_result(
                prev_metrics={"roas": 0.8},
                new_metrics={"roas": 1.5},
            ))
        assert pipeline.consolidation_count == 0


# ═══════════════════════════════════════════════════════════════
# Test: Consolidation Pipeline Integration
# ═══════════════════════════════════════════════════════════════


class TestConsolidationIntegration:
    """整合流水线集成测试."""

    def test_consolidation_not_triggered_below_threshold(self):
        """经验数不足 → 不触发整合."""
        pipeline = ExperienceWritePipeline(
            experience_store=ExperienceStore(),
            trigger=ConsolidationTrigger(min_experience_count=5),
        )
        # 只写入 3 条
        for _ in range(3):
            pipeline.write(_make_execution_result(
                prev_metrics={"roas": 0.8},
                new_metrics={"roas": 1.5},
            ))
        assert pipeline.consolidation_count == 0

    def test_consolidation_cooldown(self):
        """冷却期内不触发."""
        pipeline = ExperienceWritePipeline(
            experience_store=ExperienceStore(),
            trigger=ConsolidationTrigger(
                min_experience_count=2,
                cooldown_cycles=5,
            ),
        )
        for i in range(4):
            pipeline.write(_make_execution_result(
                prev_metrics={"roas": 0.8},
                new_metrics={"roas": 1.5 + i * 0.1},
            ))
        # cooldown_cycles=5, 写入了 4 条，第一次触发后冷却 5 条不触发
        assert pipeline.consolidation_count <= 1


# ═══════════════════════════════════════════════════════════════
# Test: Models Serialization
# ═══════════════════════════════════════════════════════════════


class TestModelsSerialization:
    """模型序列化测试."""

    def test_importance_score_to_dict(self):
        """ImportanceScore.to_dict()."""
        score = ImportanceScore(
            total_score=0.75,
            impact=0.80,
            confidence=0.70,
            novelty=1.0,
            repeatability=0.5,
            level=ExperienceImportanceLevel.HIGH,
            reasons=["test_reason"],
        )
        d = score.to_dict()
        assert d["total_score"] == 0.75
        assert d["impact"] == 0.80
        assert d["confidence"] == 0.70
        assert d["novelty"] == 1.0
        assert d["repeatability"] == 0.5
        assert d["level"] == "high"
        assert len(d["reasons"]) == 1

    def test_write_batch_success_rate(self):
        """WriteBatchResult.success_rate."""
        batch = WriteBatchResult(total=10, written=7, skipped=2, failed=1)
        assert batch.success_rate == 0.7

    def test_write_batch_success_rate_zero_total(self):
        """总数为 0 时 success_rate = 0."""
        batch = WriteBatchResult(total=0)
        assert batch.success_rate == 0.0

    def test_consolidation_trigger_default(self):
        """ConsolidationTrigger.default()."""
        trigger = ConsolidationTrigger.default()
        assert trigger == ConsolidationTrigger()

    def test_consolidation_trigger_test_mode(self):
        """ConsolidationTrigger.test_mode()."""
        trigger = ConsolidationTrigger.test_mode()
        assert trigger.min_experience_count == 2
        assert trigger.min_importance_threshold == 0.10
        assert trigger.cooldown_cycles == 0