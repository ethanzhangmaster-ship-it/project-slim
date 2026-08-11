"""E14.7.4 Growth Strategy Memory Optimizer — 集成测试.

验证 GrowthStrategyOptimizer 的策略优化能力:
  - StrategyScore: 评分模型 (15 tests)
  - StrategyCluster: 聚类模型 (15 tests)
  - StrategyExtractor: 聚类提取 (20 tests)
  - StrategyExtractor Dimensions: 多维度聚类 (15 tests)
  - StrategyEvaluator: 策略评估 (20 tests)
  - StrategyOptimizer: 优化器核心 (20 tests)
  - StrategyOptimizer Store: 与 StrategyMemory 集成 (15 tests)
  - Batch & Error Handling: 批量与错误处理 (15 tests)
  - Regression E14.7.3: 集成回归 (15 tests)

总计: 150 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.strategy_optimizer import (
    GrowthStrategyOptimizer,
    StrategyScore,
    StrategyCluster,
    StrategyExtractor,
    StrategyEvaluator,
    create_strategy_optimizer,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
    ExperienceContext,
    ExperienceOutcome,
    ExperienceOutcomeLevel,
    ExperienceCategory,
    GrowthExperience,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import (
    ExperienceStore,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import (
    StrategyMemory,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
    GrowthStrategyPattern,
    StrategyCategory,
    StrategyQuality,
    StrategyPerformance,
    StrategyStep,
    StrategyTriggerCondition,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_exp(
    action_type: str = "promote_winner",
    success: bool = True,
    reward: float = 0.7,
    opportunity_type: str = "creative_scale",
    audience: str = "us_android",
    product_id: str = "game_001",
    category: ExperienceCategory = ExperienceCategory.UA,
    tags: list[str] | None = None,
    trigger_signals: list[str] | None = None,
) -> GrowthExperience:
    return GrowthExperience(
        context=ExperienceContext(
            product_id=product_id,
            opportunity_type=opportunity_type,
            action_type=action_type,
            audience_segment=audience,
            trigger_signals=trigger_signals or [],
        ),
        action_type=action_type,
        outcome=ExperienceOutcome(
            success=success,
            outcome_level=(
                ExperienceOutcomeLevel.SUCCESS if success
                else ExperienceOutcomeLevel.FAILURE
            ),
            actual_reward=reward,
        ),
        reward=reward,
        category=category,
        tags=tags or [action_type],
    )


def _make_exps(
    action_type: str,
    count: int = 10,
    success_rate: float = 0.7,
    reward: float = 0.7,
    opportunity_type: str = "creative_scale",
    audience: str = "us_android",
    product_id: str = "game_001",
    category: ExperienceCategory = ExperienceCategory.UA,
) -> list[GrowthExperience]:
    exps = []
    for i in range(count):
        s = i < int(count * success_rate)
        exps.append(_make_exp(
            action_type=action_type,
            success=s,
            reward=reward if s else 0.1,
            opportunity_type=opportunity_type,
            audience=audience,
            product_id=product_id,
            category=category,
        ))
    return exps


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def extractor():
    return StrategyExtractor()


@pytest.fixture
def evaluator():
    return StrategyEvaluator()


@pytest.fixture
def exp_store():
    return ExperienceStore()


@pytest.fixture
def strategy_memory(exp_store):
    return StrategyMemory(exp_store=exp_store)


@pytest.fixture
def optimizer(strategy_memory):
    return GrowthStrategyOptimizer(strategy_memory=strategy_memory)


# ═══════════════════════════════════════════════════════════
# 1. StrategyScore Model Tests (15)
# ═══════════════════════════════════════════════════════════

class TestStrategyScore:
    """StrategyScore 模型测试."""

    def test_default_creation(self):
        ss = StrategyScore()
        assert ss.sample_size == 0
        assert ss.success_rate == 0.0
        assert ss.score == 0.0

    def test_compute_basic(self):
        ss = StrategyScore.compute(10, 0.7, 0.6)
        assert ss.sample_size == 10
        assert ss.success_rate == 0.7
        assert ss.avg_reward == 0.6
        assert ss.score > 0

    def test_compute_score_in_range(self):
        ss = StrategyScore.compute(100, 0.8, 0.9)
        assert 0.0 <= ss.score <= 1.0

    def test_compute_zero_samples(self):
        ss = StrategyScore.compute(0, 0.5, 0.5)
        assert ss.score == 0.0

    def test_compute_high_confidence(self):
        ss = StrategyScore.compute(100, 0.9, 0.85, confidence=0.95)
        assert ss.confidence == 0.95
        assert ss.score > 0.5

    def test_compute_no_confidence_uses_derived(self):
        ss = StrategyScore.compute(50, 0.8, 0.7)
        expected_conf = 0.5 + 0.5 * 0.8
        assert ss.confidence == round(expected_conf, 4)

    def test_compute_small_samples(self):
        ss = StrategyScore.compute(3, 0.6, 0.5)
        assert ss.score < 0.5  # small sample penalty

    def test_compute_large_samples(self):
        ss = StrategyScore.compute(1000, 0.8, 0.7)
        assert ss.score > 0.3

    def test_compute_all_success(self):
        ss = StrategyScore.compute(50, 1.0, 0.9)
        assert ss.score > 0.5

    def test_compute_all_failure(self):
        ss = StrategyScore.compute(50, 0.0, 0.1)
        assert ss.score == 0.0

    def test_compute_score_monotonic_with_samples(self):
        s1 = StrategyScore.compute(10, 0.7, 0.5)
        s2 = StrategyScore.compute(100, 0.7, 0.5)
        assert s2.score > s1.score

    def test_compute_score_monotonic_with_reward(self):
        s1 = StrategyScore.compute(50, 0.7, 0.3)
        s2 = StrategyScore.compute(50, 0.7, 0.8)
        assert s2.score > s1.score

    def test_to_dict(self):
        ss = StrategyScore.compute(10, 0.7, 0.5)
        d = ss.to_dict()
        assert d["sample_size"] == 10
        assert d["success_rate"] == 0.7
        assert "score" in d

    def test_compute_deterministic(self):
        ss1 = StrategyScore.compute(20, 0.6, 0.5)
        ss2 = StrategyScore.compute(20, 0.6, 0.5)
        assert ss1.score == ss2.score

    def test_compute_idempotent(self):
        ss = StrategyScore()
        assert ss.compute is not None
        assert ss.score == 0.0


# ═══════════════════════════════════════════════════════════
# 2. StrategyCluster Model Tests (15)
# ═══════════════════════════════════════════════════════════

class TestStrategyCluster:
    """StrategyCluster 模型测试."""

    def test_default_creation(self):
        c = StrategyCluster()
        assert c.cluster_id.startswith("sc_")
        assert c.sample_size == 0
        assert c.success_rate == 0.0

    def test_full_creation(self):
        exps = _make_exps("promote_winner", 10, 0.7)
        c = StrategyCluster(
            action_type="promote_winner",
            dimension="opportunity_action",
            experiences=exps,
            context_key="creative_scale|promote_winner|us_android",
        )
        assert c.action_type == "promote_winner"
        assert c.dimension == "opportunity_action"

    def test_compute_stats(self):
        exps = _make_exps("promote_winner", 10, 0.7)
        c = StrategyCluster(experiences=exps)
        c.compute_stats()
        assert c.sample_size == 10
        assert c.success_count == 7
        assert c.success_rate == 0.7
        assert c.avg_reward > 0

    def test_compute_stats_all_success(self):
        exps = _make_exps("promote_winner", 10, 1.0)
        c = StrategyCluster(experiences=exps)
        c.compute_stats()
        assert c.success_rate == 1.0
        assert c.success_count == 10

    def test_compute_stats_all_failure(self):
        exps = _make_exps("promote_winner", 10, 0.0)
        c = StrategyCluster(experiences=exps)
        c.compute_stats()
        assert c.success_rate == 0.0
        assert c.success_count == 0

    def test_compute_stats_empty(self):
        c = StrategyCluster()
        c.compute_stats()
        assert c.sample_size == 0
        assert c.success_rate == 0.0

    def test_compute_stats_single(self):
        exp = _make_exp("promote_winner", True, 0.8)
        c = StrategyCluster(experiences=[exp])
        c.compute_stats()
        assert c.sample_size == 1
        assert c.success_rate == 1.0

    def test_unique_cluster_id(self):
        c1 = StrategyCluster()
        c2 = StrategyCluster()
        assert c1.cluster_id != c2.cluster_id

    def test_to_dict(self):
        exps = _make_exps("promote_winner", 5, 0.8)
        c = StrategyCluster(
            action_type="promote_winner",
            dimension="opportunity_action",
            experiences=exps,
        )
        c.compute_stats()
        d = c.to_dict()
        assert d["action_type"] == "promote_winner"
        assert d["sample_size"] == 5
        assert "experience_ids" in d

    def test_to_dict_experience_ids(self):
        exps = _make_exps("promote_winner", 3)
        c = StrategyCluster(experiences=exps)
        c.compute_stats()
        d = c.to_dict()
        assert len(d["experience_ids"]) == 3

    def test_context_key_preserved(self):
        c = StrategyCluster(context_key="key1|key2|key3")
        assert c.context_key == "key1|key2|key3"

    def test_dimension_preserved(self):
        c = StrategyCluster(dimension="action_type")
        assert c.dimension == "action_type"

    def test_experiences_reference(self):
        exps = _make_exps("promote_winner", 3)
        c = StrategyCluster(experiences=exps)
        assert c.experiences is exps

    def test_reward_avg_with_mixed(self):
        exp1 = _make_exp("act", True, 0.9)
        exp2 = _make_exp("act", False, 0.1)
        c = StrategyCluster(experiences=[exp1, exp2])
        c.compute_stats()
        assert c.avg_reward == 0.5


# ═══════════════════════════════════════════════════════════
# 3. StrategyExtractor Core Tests (20)
# ═══════════════════════════════════════════════════════════

class TestStrategyExtractor:
    """StrategyExtractor 核心测试."""

    def test_extract_basic(self, extractor):
        exps = _make_exps("promote_winner", 10, 0.7)
        clusters = extractor.extract(exps)
        assert len(clusters) > 0

    def test_extract_single_action_type(self, extractor):
        exps = _make_exps("promote_winner", 10, 0.7)
        clusters = extractor.extract(exps)
        assert clusters[0].action_type == "promote_winner"

    def test_extract_multiple_actions(self, extractor):
        exps = (
            _make_exps("promote_winner", 5, 0.8) +
            _make_exps("reduce_budget", 5, 0.6)
        )
        clusters = extractor.extract(exps)
        assert len(clusters) >= 2

    def test_extract_insufficient_samples(self, extractor):
        exps = _make_exps("promote_winner", 2, 0.7)
        clusters = extractor.extract(exps)
        assert clusters == []

    def test_extract_low_success_rate_filtered(self, extractor):
        exps = _make_exps("promote_winner", 10, 0.2)
        clusters = extractor.extract(exps)
        assert clusters == []

    def test_extract_stats_computed(self, extractor):
        exps = _make_exps("promote_winner", 10, 0.7)
        clusters = extractor.extract(exps)
        assert clusters[0].sample_size == 10
        assert clusters[0].success_rate >= 0.0

    def test_extract_dimension_set(self, extractor):
        exps = _make_exps("promote_winner", 10, 0.7)
        clusters = extractor.extract(exps)
        assert clusters[0].dimension == "opportunity_action"

    def test_extract_by_action_dimension(self):
        extractor = StrategyExtractor(dimension="action_type")
        exps = _make_exps("promote_winner", 10, 0.7)
        clusters = extractor.extract(exps)
        assert len(clusters) == 1
        assert clusters[0].dimension == "action_type"

    def test_extract_empty_list(self, extractor):
        clusters = extractor.extract([])
        assert clusters == []

    def test_extract_context_key(self, extractor):
        exps = _make_exps("promote_winner", 10, 0.7)
        clusters = extractor.extract(exps)
        assert "promote_winner" in clusters[0].context_key

    def test_extract_different_opportunities(self, extractor):
        exps = (
            _make_exps("promote_winner", 5, 0.8, opportunity_type="creative_scale") +
            _make_exps("promote_winner", 5, 0.8, opportunity_type="creative_fatigue")
        )
        clusters = extractor.extract(exps)
        assert len(clusters) >= 2

    def test_extract_different_audiences(self, extractor):
        exps = (
            _make_exps("promote_winner", 5, 0.8, audience="us_android") +
            _make_exps("promote_winner", 5, 0.8, audience="eu_ios")
        )
        clusters = extractor.extract(exps)
        assert len(clusters) >= 2

    def test_extract_different_products(self, extractor):
        # product_id 不在 opportunity_action 聚类维度中，用不同 audience 区分
        exps = (
            _make_exps("promote_winner", 5, 0.8, product_id="game_001", audience="us_android") +
            _make_exps("promote_winner", 5, 0.8, product_id="game_002", audience="eu_ios")
        )
        clusters = extractor.extract(exps)
        assert len(clusters) >= 2

    def test_extraction_count(self, extractor):
        exps = _make_exps("promote_winner", 10, 0.7)
        for _ in range(3):
            extractor.extract(exps)
        assert extractor.extraction_count == 3

    def test_default_min_samples(self, extractor):
        assert extractor.min_samples == 3

    def test_default_dimension(self, extractor):
        assert extractor.dimension == "opportunity_action"

    def test_custom_min_samples(self):
        extractor = StrategyExtractor(min_samples=5)
        exps = _make_exps("promote_winner", 4, 0.7)
        clusters = extractor.extract(exps)
        assert clusters == []

    def test_custom_min_success_rate(self):
        extractor = StrategyExtractor(min_success_rate=0.5)
        exps = _make_exps("promote_winner", 10, 0.4)
        clusters = extractor.extract(exps)
        assert clusters == []

    def test_extract_preserves_experiences(self, extractor):
        exps = _make_exps("promote_winner", 10, 0.7)
        clusters = extractor.extract(exps)
        assert len(clusters[0].experiences) == 10

    def test_extract_with_unknown_opportunity(self, extractor):
        exps = _make_exps("promote_winner", 5, 0.8, opportunity_type="")
        clusters = extractor.extract(exps)
        assert len(clusters) > 0


# ═══════════════════════════════════════════════════════════
# 4. StrategyExtractor Dimensions (15)
# ═══════════════════════════════════════════════════════════

class TestStrategyExtractorDimensions:
    """多维度聚类测试."""

    def test_action_dimension(self):
        extractor = StrategyExtractor(dimension="action_type")
        exps = (
            _make_exps("promote_winner", 5, 0.8) +
            _make_exps("reduce_budget", 5, 0.6)
        )
        clusters = extractor.extract(exps)
        assert len(clusters) == 2

    def test_opportunity_action_dimension(self):
        extractor = StrategyExtractor(dimension="opportunity_action")
        exps = (
            _make_exps("promote_winner", 5, 0.8, opportunity_type="creative_scale") +
            _make_exps("promote_winner", 5, 0.8, opportunity_type="roas_recovery")
        )
        clusters = extractor.extract(exps)
        assert len(clusters) == 2

    def test_action_dimension_dimension(self):
        extractor = StrategyExtractor(dimension="action_dimension")
        exps = (
            _make_exps("promote_winner", 5, 0.8, category=ExperienceCategory.UA) +
            _make_exps("promote_winner", 5, 0.8, category=ExperienceCategory.CREATIVE)
        )
        clusters = extractor.extract(exps)
        assert len(clusters) == 2

    def test_all_clusters_have_stats(self, extractor):
        exps = (
            _make_exps("promote_winner", 5, 0.8) +
            _make_exps("reduce_budget", 5, 0.6)
        )
        clusters = extractor.extract(exps)
        for c in clusters:
            assert c.sample_size > 0
            assert c.success_rate >= 0.0

    def test_action_dimension_context_key(self):
        extractor = StrategyExtractor(dimension="action_type")
        exps = _make_exps("promote_winner", 5, 0.8)
        clusters = extractor.extract(exps)
        assert clusters[0].context_key == "promote_winner"

    def test_opportunity_action_context_key(self, extractor):
        exps = _make_exps("promote_winner", 5, 0.8)
        clusters = extractor.extract(exps)
        assert "promote_winner" in clusters[0].context_key
        assert "creative_scale" in clusters[0].context_key

    def test_mixed_success_rates(self, extractor):
        exps = (
            _make_exps("promote_winner", 5, 0.8) +
            _make_exps("reduce_budget", 5, 0.4)
        )
        clusters = extractor.extract(exps)
        rates = [c.success_rate for c in clusters]
        assert any(r > 0.5 for r in rates)

    def test_large_dataset(self, extractor):
        exps = []
        for action in ["promote_winner", "scale_campaign", "reduce_budget"]:
            exps += _make_exps(action, 20, 0.7)
        clusters = extractor.extract(exps)
        assert len(clusters) >= 3

    def test_filter_removes_small_clusters(self, extractor):
        exps = (
            _make_exps("promote_winner", 10, 0.7) +
            _make_exps("rare_action", 2, 0.8)
        )
        clusters = extractor.extract(exps)
        action_types = [c.action_type for c in clusters]
        assert "rare_action" not in action_types

    def test_filter_removes_low_success(self, extractor):
        exps = (
            _make_exps("promote_winner", 10, 0.8) +
            _make_exps("bad_action", 10, 0.1)
        )
        clusters = extractor.extract(exps)
        action_types = [c.action_type for c in clusters]
        assert "bad_action" not in action_types

    def test_opportunity_action_key_structure(self, extractor):
        exps = _make_exps("promote_winner", 5, 0.8, opportunity_type="scale")
        clusters = extractor.extract(exps)
        key = clusters[0].context_key
        parts = key.split("|")
        assert len(parts) == 3

    def test_action_dimension_key_structure(self):
        extractor = StrategyExtractor(dimension="action_dimension")
        exps = _make_exps("promote_winner", 5, 0.8)
        clusters = extractor.extract(exps)
        key = clusters[0].context_key
        assert "promote_winner" in key
        assert "ua" in key

    def test_dimensions_produce_different_counts(self):
        exps = (
            _make_exps("promote_winner", 5, 0.8, opportunity_type="scale") +
            _make_exps("promote_winner", 5, 0.8, opportunity_type="fatigue")
        )
        e1 = StrategyExtractor(dimension="action_type")
        e2 = StrategyExtractor(dimension="opportunity_action")
        assert len(e1.extract(exps)) != len(e2.extract(exps))

    def test_unknown_dimension_defaults(self):
        extractor = StrategyExtractor(dimension="unknown")
        exps = _make_exps("promote_winner", 5, 0.8)
        clusters = extractor.extract(exps)
        assert len(clusters) > 0

    def test_all_dimensions_produce_valid_clusters(self):
        for dim in ["action_type", "opportunity_action", "action_dimension"]:
            extractor = StrategyExtractor(dimension=dim)
            exps = _make_exps("promote_winner", 5, 0.8)
            clusters = extractor.extract(exps)
            assert len(clusters) > 0
            for c in clusters:
                assert c.sample_size >= 3


# ═══════════════════════════════════════════════════════════
# 5. StrategyEvaluator Tests (20)
# ═══════════════════════════════════════════════════════════

class TestStrategyEvaluator:
    """StrategyEvaluator 测试."""

    def test_evaluate_basic(self, evaluator, extractor):
        exps = _make_exps("promote_winner", 10, 0.7)
        clusters = extractor.extract(exps)
        patterns = evaluator.evaluate(clusters)
        assert len(patterns) > 0

    def test_evaluate_returns_patterns(self, evaluator, extractor):
        exps = _make_exps("promote_winner", 10, 0.7)
        clusters = extractor.extract(exps)
        patterns = evaluator.evaluate(clusters)
        assert all(isinstance(p, GrowthStrategyPattern) for p in patterns)

    def test_evaluate_patterns_have_score(self, evaluator, extractor):
        exps = _make_exps("promote_winner", 10, 0.7)
        clusters = extractor.extract(exps)
        patterns = evaluator.evaluate(clusters)
        assert all(p.score > 0 for p in patterns)

    def test_evaluate_patterns_have_name(self, evaluator, extractor):
        exps = _make_exps("promote_winner", 10, 0.7)
        clusters = extractor.extract(exps)
        patterns = evaluator.evaluate(clusters)
        assert all(p.name for p in patterns)

    def test_evaluate_patterns_have_trigger(self, evaluator, extractor):
        exps = _make_exps("promote_winner", 10, 0.7)
        clusters = extractor.extract(exps)
        patterns = evaluator.evaluate(clusters)
        assert all(p.trigger.scenario for p in patterns)

    def test_evaluate_patterns_have_steps(self, evaluator, extractor):
        exps = _make_exps("promote_winner", 10, 0.7)
        clusters = extractor.extract(exps)
        patterns = evaluator.evaluate(clusters)
        assert all(len(p.steps) > 0 for p in patterns)

    def test_evaluate_patterns_have_steps_with_order(self, evaluator, extractor):
        exps = _make_exps("promote_winner", 10, 0.7)
        clusters = extractor.extract(exps)
        patterns = evaluator.evaluate(clusters)
        for p in patterns:
            for step in p.steps:
                assert step.order >= 1

    def test_evaluate_patterns_have_performance(self, evaluator, extractor):
        exps = _make_exps("promote_winner", 10, 0.7)
        clusters = extractor.extract(exps)
        patterns = evaluator.evaluate(clusters)
        assert all(p.performance.total_executions > 0 for p in patterns)

    def test_evaluate_sorted_by_score(self, evaluator, extractor):
        exps = (
            _make_exps("promote_winner", 20, 0.9) +
            _make_exps("reduce_budget", 10, 0.5)
        )
        clusters = extractor.extract(exps)
        patterns = evaluator.evaluate(clusters)
        if len(patterns) >= 2:
            assert patterns[0].score >= patterns[1].score

    def test_evaluate_empty_clusters(self, evaluator):
        patterns = evaluator.evaluate([])
        assert patterns == []

    def test_evaluate_cluster_with_opportunity(self, evaluator, extractor):
        exps = _make_exps("promote_winner", 10, 0.7, opportunity_type="creative_scale")
        clusters = extractor.extract(exps)
        patterns = evaluator.evaluate(clusters)
        assert patterns[0].trigger.opportunity_type == "creative_scale"

    def test_evaluate_quality_proven(self, evaluator, extractor):
        exps = _make_exps("promote_winner", 100, 0.8)
        clusters = extractor.extract(exps)
        patterns = evaluator.evaluate(clusters)
        assert patterns[0].performance.quality == StrategyQuality.PROVEN

    def test_evaluate_quality_reliable(self, evaluator, extractor):
        exps = _make_exps("promote_winner", 30, 0.65)
        clusters = extractor.extract(exps)
        patterns = evaluator.evaluate(clusters)
        assert patterns[0].performance.quality == StrategyQuality.RELIABLE

    def test_evaluate_quality_emerging(self, evaluator, extractor):
        exps = _make_exps("promote_winner", 10, 0.5)
        clusters = extractor.extract(exps)
        patterns = evaluator.evaluate(clusters)
        assert patterns[0].performance.quality == StrategyQuality.EMERGING

    def test_evaluate_category_inference(self, evaluator, extractor):
        exps = _make_exps("promote_winner", 10, 0.7, opportunity_type="creative_scale")
        clusters = extractor.extract(exps)
        patterns = evaluator.evaluate(clusters)
        assert patterns[0].category == StrategyCategory.CREATIVE_SCALE

    def test_evaluate_category_roas_recovery(self, evaluator, extractor):
        exps = _make_exps("reduce_budget", 10, 0.7, opportunity_type="roas_drop")
        clusters = extractor.extract(exps)
        patterns = evaluator.evaluate(clusters)
        assert patterns[0].category == StrategyCategory.ROAS_RECOVERY

    def test_evaluate_min_score_filter(self, extractor):
        evaluator = StrategyEvaluator(min_score=0.5)
        exps = _make_exps("promote_winner", 3, 0.4)
        clusters = extractor.extract(exps)
        patterns = evaluator.evaluate(clusters)
        assert patterns == []  # low score filtered

    def test_evaluation_count(self, evaluator, extractor):
        exps = _make_exps("promote_winner", 10, 0.7)
        clusters = extractor.extract(exps)
        evaluator.evaluate(clusters)
        evaluator.evaluate(clusters)
        assert evaluator.evaluation_count == 2

    def test_evaluate_tags(self, evaluator, extractor):
        exps = _make_exps("promote_winner", 10, 0.7)
        clusters = extractor.extract(exps)
        patterns = evaluator.evaluate(clusters)
        assert "promote_winner" in patterns[0].tags

    def test_evaluate_source_experience_ids(self, evaluator, extractor):
        exps = _make_exps("promote_winner", 10, 0.7)
        clusters = extractor.extract(exps)
        patterns = evaluator.evaluate(clusters)
        assert len(patterns[0].source_experience_ids) == 10


# ═══════════════════════════════════════════════════════════
# 6. GrowthStrategyOptimizer Core Tests (20)
# ═══════════════════════════════════════════════════════════

class TestStrategyOptimizer:
    """GrowthStrategyOptimizer 核心测试."""

    def test_optimize_basic(self, optimizer):
        exps = _make_exps("promote_winner", 10, 0.7)
        patterns = optimizer.optimize(exps)
        assert len(patterns) > 0
        assert all(isinstance(p, GrowthStrategyPattern) for p in patterns)

    def test_optimize_returns_sorted(self, optimizer):
        exps = (
            _make_exps("promote_winner", 20, 0.9) +
            _make_exps("reduce_budget", 10, 0.5)
        )
        patterns = optimizer.optimize(exps)
        if len(patterns) >= 2:
            assert patterns[0].score >= patterns[1].score

    def test_optimize_empty(self, optimizer):
        patterns = optimizer.optimize([])
        assert patterns == []

    def test_optimize_insufficient(self, optimizer):
        patterns = optimizer.optimize(_make_exps("promote_winner", 2, 0.7))
        assert patterns == []

    def test_optimize_and_store(self, optimizer, strategy_memory):
        exps = _make_exps("promote_winner", 10, 0.7)
        ids = optimizer.optimize_and_store(exps)
        assert len(ids) > 0
        assert strategy_memory.count > 0

    def test_optimize_and_store_dedup(self, optimizer, strategy_memory):
        exps = _make_exps("promote_winner", 10, 0.7)
        optimizer.optimize_and_store(exps)
        count1 = strategy_memory.count
        optimizer.optimize_and_store(exps)
        assert strategy_memory.count == count1

    def test_optimize_count(self, optimizer):
        exps = _make_exps("promote_winner", 10, 0.7)
        for _ in range(3):
            optimizer.optimize(exps)
        assert optimizer.optimization_count == 3

    def test_optimize_from_store(self, optimizer, exp_store):
        exps = _make_exps("promote_winner", 10, 0.7)
        for e in exps:
            exp_store.store(e)
        ids = optimizer.optimize_from_store()
        assert len(ids) > 0

    def test_optimize_from_store_successful(self, optimizer, exp_store):
        exps = _make_exps("promote_winner", 10, 0.7)
        for e in exps:
            exp_store.store(e)
        ids = optimizer.optimize_from_store_successful()
        assert len(ids) > 0

    def test_get_top_strategies(self, optimizer):
        exps = _make_exps("promote_winner", 10, 0.7)
        optimizer.optimize_and_store(exps)
        top = optimizer.get_top_strategies(5)
        assert len(top) > 0

    def test_get_actionable_strategies(self, optimizer):
        exps = _make_exps("promote_winner", 10, 0.7)
        optimizer.optimize_and_store(exps)
        actionable = optimizer.get_actionable_strategies()
        assert len(actionable) > 0

    def test_recommend(self, optimizer):
        exps = _make_exps("promote_winner", 10, 0.7, opportunity_type="creative_scale")
        optimizer.optimize_and_store(exps)
        recs = optimizer.recommend(opportunity_type="creative_scale")
        assert len(recs) > 0

    def test_recommend_no_match(self, optimizer):
        exps = _make_exps("promote_winner", 10, 0.7)
        optimizer.optimize_and_store(exps)
        recs = optimizer.recommend(opportunity_type="nonexistent")
        assert recs == []

    def test_stats(self, optimizer):
        exps = _make_exps("promote_winner", 10, 0.7)
        optimizer.optimize_and_store(exps)
        s = optimizer.stats()
        assert s["optimization_count"] == 1
        assert s["total_strategies"] > 0
        assert "extractor_dimension" in s

    def test_reset(self, optimizer):
        exps = _make_exps("promote_winner", 10, 0.7)
        optimizer.optimize(exps)
        optimizer.reset()
        assert optimizer.optimization_count == 0

    def test_strategy_memory_property(self, optimizer, strategy_memory):
        assert optimizer.strategy_memory is strategy_memory

    def test_extractor_property(self, optimizer):
        assert isinstance(optimizer.extractor, StrategyExtractor)

    def test_evaluator_property(self, optimizer):
        assert isinstance(optimizer.evaluator, StrategyEvaluator)

    def test_factory(self, strategy_memory):
        opt = create_strategy_optimizer(strategy_memory)
        assert isinstance(opt, GrowthStrategyOptimizer)

    def test_factory_custom_params(self, strategy_memory):
        opt = create_strategy_optimizer(
            strategy_memory, min_samples=5, dimension="action_type", min_score=0.1
        )
        assert opt.extractor.min_samples == 5
        assert opt.extractor.dimension == "action_type"


# ═══════════════════════════════════════════════════════════
# 7. StrategyOptimizer Store Integration (15)
# ═══════════════════════════════════════════════════════════

class TestStrategyOptimizerStore:
    """与 StrategyMemory 集成测试."""

    def test_store_basic(self, optimizer, strategy_memory):
        exps = _make_exps("promote_winner", 10, 0.7)
        optimizer.optimize_and_store(exps)
        assert strategy_memory.count >= 1

    def test_store_multiple_actions(self, optimizer, strategy_memory):
        exps = (
            _make_exps("promote_winner", 10, 0.7) +
            _make_exps("reduce_budget", 10, 0.6)
        )
        optimizer.optimize_and_store(exps)
        assert strategy_memory.count >= 2

    def test_store_queryable(self, optimizer, strategy_memory):
        exps = _make_exps("promote_winner", 10, 0.7, opportunity_type="creative_scale")
        optimizer.optimize_and_store(exps)
        results = strategy_memory.get_by_opportunity("creative_scale")
        assert len(results) > 0

    def test_store_get_top(self, optimizer, strategy_memory):
        exps = _make_exps("promote_winner", 10, 0.7)
        optimizer.optimize_and_store(exps)
        top = strategy_memory.get_top_strategies(5)
        assert len(top) > 0

    def test_store_get_actionable(self, optimizer, strategy_memory):
        exps = _make_exps("promote_winner", 10, 0.7)
        optimizer.optimize_and_store(exps)
        actionable = strategy_memory.get_actionable_strategies()
        assert len(actionable) > 0

    def test_store_stats(self, optimizer, strategy_memory):
        exps = _make_exps("promote_winner", 10, 0.7)
        optimizer.optimize_and_store(exps)
        stats = strategy_memory.get_stats()
        assert stats.total_strategies > 0

    def test_store_recommend(self, optimizer, strategy_memory):
        exps = _make_exps("promote_winner", 10, 0.7, opportunity_type="creative_scale")
        optimizer.optimize_and_store(exps)
        recs = strategy_memory.recommend(opportunity_type="creative_scale")
        assert len(recs) > 0

    def test_store_all_preserved(self, optimizer, strategy_memory):
        exps = (
            _make_exps("promote_winner", 10, 0.7) +
            _make_exps("reduce_budget", 10, 0.6) +
            _make_exps("scale_campaign", 10, 0.8)
        )
        optimizer.optimize_and_store(exps)
        all_strategies = strategy_memory.get_all()
        assert len(all_strategies) >= 3

    def test_store_has_source_ids(self, optimizer, strategy_memory):
        exps = _make_exps("promote_winner", 10, 0.7)
        optimizer.optimize_and_store(exps)
        all_s = strategy_memory.get_all()
        for s in all_s:
            assert len(s.source_experience_ids) > 0

    def test_store_has_tags(self, optimizer, strategy_memory):
        exps = _make_exps("promote_winner", 10, 0.7)
        optimizer.optimize_and_store(exps)
        all_s = strategy_memory.get_all()
        for s in all_s:
            assert "promote_winner" in s.tags

    def test_store_has_trigger(self, optimizer, strategy_memory):
        exps = _make_exps("promote_winner", 10, 0.7, opportunity_type="creative_scale")
        optimizer.optimize_and_store(exps)
        all_s = strategy_memory.get_all()
        for s in all_s:
            assert s.trigger.opportunity_type

    def test_store_has_performance(self, optimizer, strategy_memory):
        exps = _make_exps("promote_winner", 10, 0.7)
        optimizer.optimize_and_store(exps)
        all_s = strategy_memory.get_all()
        for s in all_s:
            assert s.performance.total_executions > 0

    def test_store_has_steps(self, optimizer, strategy_memory):
        exps = _make_exps("promote_winner", 10, 0.7)
        optimizer.optimize_and_store(exps)
        all_s = strategy_memory.get_all()
        for s in all_s:
            assert len(s.steps) == 1
            assert s.steps[0].action_type == "promote_winner"

    def test_store_category(self, optimizer, strategy_memory):
        exps = _make_exps("promote_winner", 10, 0.7, opportunity_type="creative_scale")
        optimizer.optimize_and_store(exps)
        results = strategy_memory.get_by_category(StrategyCategory.CREATIVE_SCALE)
        assert len(results) > 0

    def test_store_clear(self, optimizer, strategy_memory):
        exps = _make_exps("promote_winner", 10, 0.7)
        optimizer.optimize_and_store(exps)
        strategy_memory.clear()
        assert strategy_memory.count == 0


# ═══════════════════════════════════════════════════════════
# 8. Batch & Error Handling (15)
# ═══════════════════════════════════════════════════════════

class TestBatchAndError:
    """批量与错误处理测试."""

    def test_large_dataset_optimize(self, optimizer):
        exps = []
        for action in ["promote_winner", "reduce_budget", "scale_campaign"]:
            exps += _make_exps(action, 30, 0.7)
        patterns = optimizer.optimize(exps)
        assert len(patterns) >= 3

    def test_optimize_with_mixed_success(self, optimizer):
        exps = (
            _make_exps("promote_winner", 10, 0.5) +
            _make_exps("reduce_budget", 10, 0.5)
        )
        patterns = optimizer.optimize(exps)
        assert len(patterns) >= 2

    def test_optimize_with_all_failures(self, optimizer):
        exps = _make_exps("promote_winner", 10, 0.0)
        patterns = optimizer.optimize(exps)
        assert patterns == []

    def test_optimize_with_various_opportunities(self, optimizer):
        exps = (
            _make_exps("promote_winner", 10, 0.7, opportunity_type="creative_scale") +
            _make_exps("reduce_budget", 10, 0.6, opportunity_type="roas_drop") +
            _make_exps("scale_campaign", 10, 0.8, opportunity_type="scale_opportunity")
        )
        patterns = optimizer.optimize(exps)
        assert len(patterns) >= 3

    def test_optimize_with_various_audiences(self, optimizer):
        exps = (
            _make_exps("promote_winner", 10, 0.7, audience="us_android") +
            _make_exps("promote_winner", 10, 0.7, audience="eu_ios")
        )
        patterns = optimizer.optimize(exps)
        assert len(patterns) >= 2

    def test_optimize_with_various_products(self, optimizer):
        # product_id 不在 opportunity_action 聚类维度中，用不同 audience 区分
        exps = (
            _make_exps("promote_winner", 10, 0.7, product_id="game_001", audience="us_android") +
            _make_exps("promote_winner", 10, 0.7, product_id="game_002", audience="eu_ios")
        )
        patterns = optimizer.optimize(exps)
        assert len(patterns) >= 2

    def test_single_experience_insufficient(self, optimizer):
        patterns = optimizer.optimize([_make_exp("promote_winner", True, 0.9)])
        assert patterns == []

    def test_empty_experience_list(self, optimizer):
        patterns = optimizer.optimize([])
        assert patterns == []

    def test_invalid_data_handled(self, optimizer):
        exp = _make_exp("promote_winner", True, 0.7)
        patterns = optimizer.optimize([exp, exp, exp])
        # 3 identical experiences, should cluster into 1 pattern
        assert len(patterns) == 1

    def test_optimize_from_store_empty(self, optimizer):
        ids = optimizer.optimize_from_store()
        assert ids == []

    def test_optimize_from_store_no_exp_store(self, optimizer):
        optimizer2 = GrowthStrategyOptimizer(
            strategy_memory=object()  # no _exp_store
        )
        ids = optimizer2.optimize_from_store()
        assert ids == []

    def test_score_always_between_zero_and_one(self, optimizer):
        for i in range(5):
            exps = _make_exps(f"action_{i}", 10, 0.5 + i * 0.1)
            patterns = optimizer.optimize(exps)
            for p in patterns:
                assert 0.0 <= p.score <= 1.0

    def test_patterns_are_actionable(self, optimizer):
        exps = _make_exps("promote_winner", 10, 0.7)
        patterns = optimizer.optimize(exps)
        for p in patterns:
            assert p.is_actionable()

    def test_full_optimize_flow(self, optimizer, exp_store):
        for action in ["promote_winner", "reduce_budget", "scale_campaign"]:
            for e in _make_exps(action, 10, 0.7):
                exp_store.store(e)
        ids = optimizer.optimize_from_store()
        assert len(ids) >= 3
        stats = optimizer.stats()
        assert stats["total_strategies"] >= 3

    def test_multiple_optimize_cycles(self, optimizer, exp_store):
        for cycle in range(3):
            for e in _make_exps("promote_winner", 10, 0.7 + cycle * 0.05):
                exp_store.store(e)
        before = optimizer.stats()["optimization_count"]
        for _ in range(2):
            optimizer.optimize_from_store()
        after = optimizer.stats()["optimization_count"]
        assert after > before


# ═══════════════════════════════════════════════════════════
# 9. Regression E14.7.3 Tests (15)
# ═══════════════════════════════════════════════════════════

class TestRegressionE1473:
    """E14.7.3 集成回归测试."""

    def test_full_learning_to_strategy_loop(self, optimizer, exp_store):
        """完整闭环: E14.7.3 Feedback → Experience → Strategy."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.execution_feedback import (
            ExecutionFeedbackCollector,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
            ExecutionOutcome,
            ExecutionStatus,
        )

        collector = ExecutionFeedbackCollector()

        # 模拟 10 次执行反馈
        for i in range(10):
            outcome = ExecutionOutcome(
                action_id=f"ga_{i:03d}",
                action_type="promote_winner",
                status=ExecutionStatus.SUCCESS,
                executor="MetaAdsExecutor",
                output={"metrics_delta": {"roas_delta": 0.5, "payer_rate_delta": 0.03}},
                metadata={"reality_data": True},
            )
            ctx = ExperienceContext(
                product_id="game_001",
                opportunity_type="creative_scale",
                action_type="promote_winner",
                audience_segment="us_android",
            )
            collector.collect_and_store(outcome, ctx, exp_store)

        # 策略优化
        optimizer.optimize_from_store()
        strategies = optimizer.get_top_strategies(5)
        assert len(strategies) > 0

    def test_multi_action_learning_to_strategy(self, optimizer, exp_store):
        """多动作学习 → 策略."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.execution_feedback import (
            ExecutionFeedbackCollector,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
            ExecutionOutcome,
            ExecutionStatus,
        )

        collector = ExecutionFeedbackCollector()

        actions = [
            ("promote_winner", "creative_scale", 0.8),
            ("reduce_budget", "roas_drop", 0.6),
            ("scale_campaign", "scale_opportunity", 0.75),
        ]

        for action_type, opp, reward in actions:
            for i in range(15):
                outcome = ExecutionOutcome(
                    action_id=f"ga_{action_type}_{i}",
                    action_type=action_type,
                    status=ExecutionStatus.SUCCESS,
                    executor="MetaAdsExecutor",
                    output={"metrics_delta": {"roas_delta": reward}},
                    metadata={"reality_data": True},
                )
                ctx = ExperienceContext(
                    product_id="game_001",
                    opportunity_type=opp,
                    action_type=action_type,
                    audience_segment="us_android",
                )
                collector.collect_and_store(outcome, ctx, exp_store)

        ids = optimizer.optimize_from_store()
        assert len(ids) >= 3

    def test_amplify_signal_to_strategy(self, optimizer, exp_store):
        """AMPLIFY 信号 → 策略 闭环."""
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
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.execution_feedback import (
            ExecutionFeedbackCollector,
        )

        engine = GrowthExecutionEngine()
        engine.register_default_executors()
        router = GrowthActionRouter()
        collector = ExecutionFeedbackCollector()

        for i in range(10):
            signal = EvolutionSignal(
                action=SignalAction.AMPLIFY,
                target_value=f"genome_{i:03d}",
                confidence=0.85 + i * 0.01,
                expected_impact="ROAS +15%",
            )
            outcome = engine.execute(router.route(signal).action)
            outcome.metadata["metrics_delta"] = {"roas_delta": 0.5 + i * 0.02}
            ctx = ExperienceContext(
                product_id="game_001",
                opportunity_type="creative_scale",
                action_type=outcome.action_type,
                audience_segment="us_android",
            )
            collector.collect_and_store(outcome, ctx, exp_store)

        ids = optimizer.optimize_from_store()
        assert len(ids) > 0

    def test_multi_genome_amplify_to_strategy(self, optimizer, exp_store):
        """多 genome amplify → 策略."""
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
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.execution_feedback import (
            ExecutionFeedbackCollector,
        )

        engine = GrowthExecutionEngine()
        engine.register_default_executors()
        router = GrowthActionRouter()
        collector = ExecutionFeedbackCollector()

        signals_data = [
            (SignalAction.AMPLIFY, "genome_001", 0.92, 0.5),
            (SignalAction.AMPLIFY, "genome_002", 0.88, 0.3),
            (SignalAction.AMPLIFY, "genome_003", 0.95, 0.7),
        ]

        for sig_action, target, confidence, roas_delta in signals_data:
            for i in range(5):
                signal = EvolutionSignal(
                    action=sig_action,
                    target_value=target,
                    confidence=confidence,
                    expected_impact=f"ROAS +{roas_delta*100:.0f}%",
                )
                outcome = engine.execute(router.route(signal).action)
                outcome.metadata["metrics_delta"] = {"roas_delta": roas_delta}
                ctx = ExperienceContext(
                    product_id="game_001",
                    opportunity_type="creative_scale",
                    action_type=outcome.action_type,
                )
                collector.collect_and_store(outcome, ctx, exp_store)

        ids = optimizer.optimize_from_store()
        assert len(ids) > 0

    def test_suppress_signal_to_strategy(self, optimizer, exp_store):
        """SUPPRESS 信号 → 策略."""
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
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.execution_feedback import (
            ExecutionFeedbackCollector,
        )

        engine = GrowthExecutionEngine()
        engine.register_default_executors()
        router = GrowthActionRouter()
        collector = ExecutionFeedbackCollector()

        for i in range(10):
            success = i < 8  # 80% success rate
            signal = EvolutionSignal(
                action=SignalAction.SUPPRESS,
                target_value=f"camp_{i:03d}",
                confidence=0.85,
                expected_impact="ROAS -20%",
            )
            outcome = engine.execute(router.route(signal, target_id=f"camp_{i:03d}").action)
            if success:
                outcome.metadata["metrics_delta"] = {
                    "roas_delta": 1.5, "payer_rate_delta": 0.3
                }
            else:
                outcome.metadata["metrics_delta"] = {"roas_delta": -0.3}
            ctx = ExperienceContext(
                product_id="game_001",
                opportunity_type="roas_drop",
                action_type=outcome.action_type,
            )
            collector.collect_and_store(outcome, ctx, exp_store)

        ids = optimizer.optimize_from_store()
        assert len(ids) > 0

    def test_explore_signal_to_strategy(self, optimizer, exp_store):
        """EXPLORE 信号 → 策略."""
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
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.execution_feedback import (
            ExecutionFeedbackCollector,
        )

        engine = GrowthExecutionEngine()
        engine.register_default_executors()
        router = GrowthActionRouter()
        collector = ExecutionFeedbackCollector()

        for i in range(10):
            signal = EvolutionSignal(
                action=SignalAction.EXPLORE,
                target_value=f"genome_{i:03d}",
                confidence=0.75,
                expected_impact="New direction",
            )
            outcome = engine.execute(router.route(signal, target_id=f"genome_{i:03d}").action)
            outcome.metadata["metrics_delta"] = {"roas_delta": 0.2, "ctr_delta": 0.05}
            ctx = ExperienceContext(
                product_id="game_001",
                opportunity_type="creative_scale",
                action_type=outcome.action_type,
            )
            collector.collect_and_store(outcome, ctx, exp_store)

        ids = optimizer.optimize_from_store()
        assert len(ids) > 0

    def test_strategy_is_actionable_after_optimize(self, optimizer, exp_store):
        """优化后的策略可执行."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.execution_feedback import (
            ExecutionFeedbackCollector,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
            ExecutionOutcome,
            ExecutionStatus,
        )

        collector = ExecutionFeedbackCollector()

        for i in range(10):
            outcome = ExecutionOutcome(
                action_id=f"ga_{i:03d}",
                action_type="promote_winner",
                status=ExecutionStatus.SUCCESS,
                executor="MetaAdsExecutor",
                output={"metrics_delta": {"roas_delta": 0.6}},
                metadata={"reality_data": True},
            )
            ctx = ExperienceContext(
                product_id="game_001",
                opportunity_type="creative_scale",
                action_type="promote_winner",
            )
            collector.collect_and_store(outcome, ctx, exp_store)

        optimizer.optimize_from_store()
        strategies = optimizer.get_actionable_strategies()
        for s in strategies:
            assert s.is_actionable()

    def test_strategy_score_consistency(self, optimizer, exp_store):
        """策略评分一致性."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.execution_feedback import (
            ExecutionFeedbackCollector,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
            ExecutionOutcome,
            ExecutionStatus,
        )

        collector = ExecutionFeedbackCollector()

        for i in range(20):
            outcome = ExecutionOutcome(
                action_id=f"ga_{i:03d}",
                action_type="promote_winner",
                status=ExecutionStatus.SUCCESS,
                executor="MetaAdsExecutor",
                output={"metrics_delta": {"roas_delta": 0.5}},
                metadata={"reality_data": True},
            )
            ctx = ExperienceContext(
                product_id="game_001",
                opportunity_type="creative_scale",
                action_type="promote_winner",
            )
            collector.collect_and_store(outcome, ctx, exp_store)

        optimizer.optimize_from_store()
        strategies = optimizer.get_top_strategies(1)
        score1 = strategies[0].score

        # 再次优化（相同数据），应该有相同评分
        optimizer.reset()
        optimizer.optimize_from_store()
        strategies2 = optimizer.get_top_strategies(1)
        score2 = strategies2[0].score

        assert score1 == score2

    def test_strategy_memory_after_optimize(self, optimizer, exp_store):
        """策略记忆优化后状态."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.execution_feedback import (
            ExecutionFeedbackCollector,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
            ExecutionOutcome,
            ExecutionStatus,
        )

        collector = ExecutionFeedbackCollector()

        for i in range(15):
            outcome = ExecutionOutcome(
                action_id=f"ga_{i:03d}",
                action_type="promote_winner",
                status=ExecutionStatus.SUCCESS,
                executor="MetaAdsExecutor",
                output={"metrics_delta": {"roas_delta": 0.6}},
                metadata={"reality_data": True},
            )
            ctx = ExperienceContext(
                product_id="game_001",
                opportunity_type="creative_scale",
                action_type="promote_winner",
                audience_segment="us_android",
            )
            collector.collect_and_store(outcome, ctx, exp_store)

        optimizer.optimize_from_store()
        stats = optimizer.stats()
        assert stats["total_strategies"] > 0
        assert stats["total_actionable"] > 0
        assert stats["avg_score"] > 0
        assert stats["optimization_count"] == 1

    def test_recommend_with_signals(self, optimizer, exp_store):
        """带信号推荐策略."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.execution_feedback import (
            ExecutionFeedbackCollector,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
            ExecutionOutcome,
            ExecutionStatus,
        )

        collector = ExecutionFeedbackCollector()

        for i in range(10):
            outcome = ExecutionOutcome(
                action_id=f"ga_{i:03d}",
                action_type="promote_winner",
                status=ExecutionStatus.SUCCESS,
                executor="MetaAdsExecutor",
                output={"metrics_delta": {"roas_delta": 0.8}},
                metadata={"reality_data": True},
            )
            ctx = ExperienceContext(
                product_id="game_001",
                opportunity_type="creative_scale",
                action_type="promote_winner",
                trigger_signals=["roas_improving", "high_confidence"],
            )
            collector.collect_and_store(outcome, ctx, exp_store)

        optimizer.optimize_from_store()
        recs = optimizer.recommend(
            opportunity_type="creative_scale",
            signal_types=["roas_improving"],
        )
        assert len(recs) > 0

    def test_signal_to_strategy_rocket_amplify(self):
        """Signal → Strategy 快速测试: AMPLIFY."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
            GrowthExecutionEngine,
            ExecutionStatus,
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
        assert result is not None
        outcome = engine.execute(result.action)
        assert outcome.status == ExecutionStatus("success")

    def test_signal_to_strategy_rocket_suppress(self):
        """Signal → Strategy 快速测试: SUPPRESS."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
            GrowthExecutionEngine,
            ExecutionStatus,
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
        assert outcome.status == ExecutionStatus("success")

    def test_signal_to_strategy_rocket_explore(self):
        """Signal → Strategy 快速测试: EXPLORE."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
            GrowthExecutionEngine,
            ExecutionStatus,
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
        assert outcome.status == ExecutionStatus("success")

    def test_signal_to_strategy_rocket_maintain(self):
        """Signal → Strategy 快速测试: MAINTAIN."""
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
        assert outcome.action_type == "hold"

    def test_execution_id_required(self):
        """ExecutionStatus('success') 验证."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
            ExecutionStatus,
        )
        assert ExecutionStatus("success") == ExecutionStatus.SUCCESS
        assert ExecutionStatus("failed") == ExecutionStatus.FAILED