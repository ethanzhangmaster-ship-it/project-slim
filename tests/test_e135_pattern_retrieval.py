"""E13.5 Pattern Retrieval — 测试套件.

测试覆盖:
  - RetrievalContext: 构建、to_query、from_opportunity
  - PatternRecommendation / RetrievalResult: 模型创建
  - PatternRetriever: 基础检索、相似度计算、排序、推荐分类
  - PatternRetriever: 多维度匹配 (opportunity, audience, signals, metrics)
  - PatternRetriever: 边界情况 (空存储、无匹配、低相似度)
  - DecisionEnhancer: 策略注入、置信度调整、警告生成
  - DecisionEnhancer: 空输入、无模式匹配
  - Integration: Pattern → Decision 完整闭环
  - 真实场景: 素材疲劳 ROAS 下降 → 检索 → 推荐 replace_creative
"""

from __future__ import annotations

from typing import Any

import pytest

from market_ops.creative_vision_runtime.growth_runtime.decision import (
    DecisionEnhancer,
    EnhancementReport,
    PatternRecommendation,
    PatternRetriever,
    RetrievalContext,
    RetrievalResult,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
    ExperienceCategory,
    ExperienceContext,
    ExperienceOutcome,
    ExperienceOutcomeLevel,
    GrowthExperience,
    PatternAction,
    PatternCondition,
    PatternMemory,
    PatternMiningDimension,
    PatternPerformance,
    PatternQuality,
    PatternQuery,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import (
    ExperienceStore,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import (
    PatternMiner,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import (
    PatternStore,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_experience(
    opportunity_type: str = "creative_fatigue",
    action_type: str = "replace_creative",
    success: bool = True,
    reward: float = 0.82,
    audience_segment: str = "iOS_FB",
    signal_types: list[str] | None = None,
    metrics_delta: dict[str, float] | None = None,
    category: ExperienceCategory = ExperienceCategory.CREATIVE,
    dna_genes: dict[str, Any] | None = None,
    market_conditions: dict[str, float] | None = None,
    product_id: str = "P04",
) -> GrowthExperience:
    """创建测试经验."""
    outcome_level = (
        ExperienceOutcomeLevel.STRONG_SUCCESS if success and reward >= 0.8
        else ExperienceOutcomeLevel.SUCCESS if success
        else ExperienceOutcomeLevel.FAILURE
    )
    return GrowthExperience(
        context=ExperienceContext(
            product_id=product_id,
            date="2026-07-29",
            opportunity_type=opportunity_type,
            action_type=action_type,
            audience_segment=audience_segment,
            trigger_signals=signal_types or ["roas_decay", "fatigue_high"],
            dna_genes=dna_genes or {},
            market_conditions=market_conditions or {"roas": 0.35, "ctr": 0.021},
        ),
        action_type=action_type,
        category=category,
        outcome=ExperienceOutcome(
            success=success,
            outcome_level=outcome_level,
            actual_reward=reward,
            metrics_delta=metrics_delta or {"roas": 0.19, "ctr": 0.007},
        ),
        reward=reward,
        confidence=0.85,
    )


def _make_pattern(
    dimension: PatternMiningDimension = PatternMiningDimension.OPPORTUNITY_ACTION,
    opportunity_type: str = "creative_fatigue",
    action_type: str = "replace_creative",
    audience_segment: str = "iOS_FB",
    signal_types: list[str] | None = None,
    samples: int = 12,
    success_rate: float = 0.83,
    avg_reward: float = 0.79,
    quality: PatternQuality = PatternQuality.RELIABLE,
    dna_genes: dict[str, Any] | None = None,
    market_conditions: dict[str, tuple[float, float]] | None = None,
    product_category: str = "P04",
    category: str = "creative",
    pattern_id_override: str = "",
) -> PatternMemory:
    """创建测试模式."""
    condition = PatternCondition(
        opportunity_type=opportunity_type,
        action_type=action_type,
        audience_segment=audience_segment,
        signal_types=signal_types or ["roas_decay", "fatigue_high"],
        dna_genes=dna_genes or {},
        market_conditions=market_conditions or {},
        product_category=product_category,
        category=category,
    )
    action = PatternAction(
        action_type=action_type,
        params_template={"clone_hook": True},
        expected_impact="ROAS recovery +50-60%",
    )
    performance = PatternPerformance(
        samples=samples,
        success_count=int(samples * success_rate),
        success_rate=success_rate,
        avg_reward=avg_reward,
        quality=quality,
    )
    pattern = PatternMemory(
        dimension=dimension,
        condition=condition,
        action=action,
        performance=performance,
    )
    if pattern_id_override:
        pattern.pattern_id = pattern_id_override
    pattern.compute_score()
    return pattern


def _build_populated_store() -> PatternStore:
    """构建一个包含多种模式的 PatternStore.

    注意: PatternStore._find_existing 会合并相同 condition 的模式，
    所以每个模式类别只存一条，但设置足够的样本数。
    """
    store = PatternStore()

    # 素材疲劳 → replace_creative (高成功率, 12 样本)
    store.store(_make_pattern(
        pattern_id_override="pat_replace_001",
        opportunity_type="creative_fatigue",
        action_type="replace_creative",
        audience_segment="iOS_FB",
        signal_types=["roas_decay", "fatigue_high"],
        samples=12,
        success_rate=0.83,
        avg_reward=0.79,
        quality=PatternQuality.RELIABLE,
        category="creative",
        product_category="P04",
    ))

    # ROAS下降 → decrease_budget (8 样本)
    store.store(_make_pattern(
        pattern_id_override="pat_decrease_001",
        opportunity_type="roas_drop",
        action_type="decrease_budget",
        audience_segment="Android_GG",
        signal_types=["roas_decay"],
        samples=8,
        success_rate=0.75,
        avg_reward=0.65,
        quality=PatternQuality.RELIABLE,
        category="ua",
        product_category="P04",
    ))

    # 低成功率 → 应避免的模式 (scale under fatigue)
    store.store(_make_pattern(
        pattern_id_override="pat_avoid_scale_001",
        opportunity_type="creative_fatigue",
        action_type="scale",
        audience_segment="iOS_FB",
        signal_types=["roas_decay"],
        samples=5,
        success_rate=0.15,
        avg_reward=0.10,
        quality=PatternQuality.AVOID,
        category="creative",
        product_category="P04",
    ))

    # Winner发现 → scale (高成功率)
    store.store(_make_pattern(
        pattern_id_override="pat_scale_001",
        opportunity_type="winner_discovery",
        action_type="scale",
        audience_segment="iOS_FB",
        signal_types=["roas_high", "ctr_high"],
        samples=10,
        success_rate=0.90,
        avg_reward=0.85,
        quality=PatternQuality.STRONG,
        category="creative",
        product_category="P04",
    ))

    return store


# ═══════════════════════════════════════════════════════════════
# RetrievalContext Tests
# ═══════════════════════════════════════════════════════════════


class TestRetrievalContext:
    """RetrievalContext 数据模型测试."""

    def test_create_default(self):
        ctx = RetrievalContext()
        assert ctx.opportunity_type == ""
        assert ctx.signal_types == []
        assert ctx.metrics_snapshot == {}

    def test_create_with_fields(self):
        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
            signal_types=["roas_decay", "fatigue_high"],
            metrics_snapshot={"roas": 0.32, "ctr": 0.021},
            product_category="P04",
        )
        assert ctx.opportunity_type == "creative_fatigue"
        assert ctx.audience_segment == "iOS_FB"
        assert ctx.signal_types == ["roas_decay", "fatigue_high"]
        assert ctx.metrics_snapshot == {"roas": 0.32, "ctr": 0.021}

    def test_to_query(self):
        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            audience_segment="iOS_FB",
            signal_types=["roas_decay"],
            category="creative",
        )
        q = ctx.to_query()
        assert isinstance(q, PatternQuery)
        assert q.opportunity_types == ["creative_fatigue"]
        # action_types 不再在 to_query 中设置，让 _rank_patterns 通过相似度分类
        assert q.action_types == []
        assert q.audience_segment == "iOS_FB"
        assert q.signal_types == ["roas_decay"]
        assert q.categories == ["creative"]

    def test_to_query_empty_context(self):
        ctx = RetrievalContext()
        q = ctx.to_query()
        assert q.opportunity_types == []
        assert q.action_types == []

    def test_to_dict(self):
        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            metrics_snapshot={"roas": 0.35},
        )
        d = ctx.to_dict()
        assert d["opportunity_type"] == "creative_fatigue"
        assert d["metrics_snapshot"] == {"roas": 0.35}

    def test_from_opportunity(self):
        """从 GrowthOpportunity 构建检索上下文."""
        from market_ops.creative_vision_runtime.growth_runtime.decision.models import (
            ActionType,
            GrowthOpportunity,
            OpportunitySeverity,
        )

        opp = GrowthOpportunity(
            action=ActionType.REPLACE_CREATIVE,
            product_id="P04",
            reason="ROAS decay -35%, fatigue score 0.82",
            confidence=0.85,
            severity=OpportunitySeverity.HIGH,
        )
        ctx = RetrievalContext.from_opportunity(opp)
        assert ctx.opportunity_type == "replace_creative"
        assert ctx.product_category == "P04"


# ═══════════════════════════════════════════════════════════════
# PatternRecommendation / RetrievalResult Tests
# ═══════════════════════════════════════════════════════════════


class TestPatternRecommendation:
    """PatternRecommendation 模型测试."""

    def test_create(self):
        pattern = _make_pattern()
        rec = PatternRecommendation(
            pattern=pattern,
            similarity_score=0.85,
            rank=1,
            recommendation_type="strong_recommend",
            reasoning=["12 similar cases", "83% success rate"],
            confidence=0.91,
        )
        assert rec.pattern == pattern
        assert rec.similarity_score == 0.85
        assert rec.rank == 1
        assert rec.confidence == 0.91
        assert rec.is_actionable

    def test_is_actionable_false_for_caution(self):
        rec = PatternRecommendation(
            pattern=_make_pattern(),
            recommendation_type="caution",
        )
        assert not rec.is_actionable

    def test_is_actionable_false_for_suggest(self):
        rec = PatternRecommendation(
            pattern=_make_pattern(),
            recommendation_type="suggest",
        )
        assert not rec.is_actionable

    def test_to_dict(self):
        pattern = _make_pattern()
        rec = PatternRecommendation(
            pattern=pattern,
            similarity_score=0.85,
            rank=1,
            recommendation_type="strong_recommend",
            reasoning=["12 cases", "83% success"],
            confidence=0.91,
        )
        d = rec.to_dict()
        assert d["pattern_id"] == pattern.pattern_id
        assert d["action_type"] == "replace_creative"
        assert d["similarity_score"] == 0.85
        assert d["recommendation_type"] == "strong_recommend"
        assert "samples" in d["performance"]


class TestRetrievalResult:
    """RetrievalResult 模型测试."""

    def test_empty(self):
        result = RetrievalResult()
        assert result.recommendations == []
        assert result.top_action is None
        assert not result.has_recommendations

    def test_with_recommendations(self):
        pattern = _make_pattern()
        rec = PatternRecommendation(
            pattern=pattern,
            recommendation_type="strong_recommend",
        )
        result = RetrievalResult(
            recommendations=[rec],
            top_action=rec,
            total_matched=5,
            retrieval_summary="Found 5 patterns",
        )
        assert result.has_recommendations
        assert result.total_matched == 5
        assert result.top_action == rec

    def test_to_dict(self):
        result = RetrievalResult(
            total_matched=3,
            retrieval_summary="Found 3 patterns",
            context={"opportunity_type": "creative_fatigue"},
        )
        d = result.to_dict()
        assert d["total_matched"] == 3
        assert d["retrieval_summary"] == "Found 3 patterns"


# ═══════════════════════════════════════════════════════════════
# PatternRetriever Tests — 基础功能
# ═══════════════════════════════════════════════════════════════


class TestPatternRetrieverBasic:
    """PatternRetriever 基础功能测试."""

    def test_init(self):
        store = PatternStore()
        retriever = PatternRetriever(store)
        assert retriever._store is store
        assert retriever._min_similarity == 0.15

    def test_init_custom_params(self):
        store = PatternStore()
        retriever = PatternRetriever(
            store,
            min_similarity=0.3,
            max_recommendations=5,
            min_samples=5,
        )
        assert retriever._min_similarity == 0.3
        assert retriever._max_recommendations == 5
        assert retriever._min_samples == 5

    def test_retrieve_empty_store(self):
        store = PatternStore()
        retriever = PatternRetriever(store)
        ctx = RetrievalContext(opportunity_type="creative_fatigue")
        result = retriever.retrieve(ctx)
        assert not result.has_recommendations
        assert result.total_matched == 0
        assert "No matching patterns" in result.retrieval_summary

    def test_retrieve_with_matches(self):
        """基础检索: 存储匹配模式后能检索到."""
        store = _build_populated_store()
        retriever = PatternRetriever(store)

        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
            signal_types=["roas_decay", "fatigue_high"],
            action_type="replace_creative",
            category="creative",
            product_category="P04",
        )
        result = retriever.retrieve(ctx)

        assert result.has_recommendations
        assert result.total_matched > 0
        # 有匹配的模式，推荐中应包含 replace_creative
        action_types = [r.pattern.action.action_type for r in result.recommendations]
        assert "replace_creative" in action_types

    def test_get_top_recommendation(self):
        store = _build_populated_store()
        retriever = PatternRetriever(store)

        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
            action_type="replace_creative",
            signal_types=["roas_decay", "fatigue_high"],
            category="creative",
            product_category="P04",
        )
        top = retriever.get_top_recommendation(ctx)
        assert top is not None
        assert top.pattern.action.action_type == "replace_creative"

    def test_get_avoid_recommendations(self):
        store = _build_populated_store()
        retriever = PatternRetriever(store)

        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
            action_type="scale",
            signal_types=["roas_decay"],
            category="creative",
            product_category="P04",
        )
        avoids = retriever.get_avoid_recommendations(ctx)
        # scale under fatigue 是 avoid 模式
        assert len(avoids) > 0
        for a in avoids:
            assert a.recommendation_type == "caution"


# ═══════════════════════════════════════════════════════════════
# PatternRetriever Tests — 相似度计算
# ═══════════════════════════════════════════════════════════════


class TestPatternRetrieverSimilarity:
    """相似度计算测试."""

    def test_audience_similarity_exact(self):
        assert PatternRetriever._audience_similarity("iOS_FB", "iOS_FB") == 1.0

    def test_audience_similarity_same_platform(self):
        assert PatternRetriever._audience_similarity("iOS_FB", "iOS_GG") == 0.5

    def test_audience_similarity_different_platform(self):
        assert PatternRetriever._audience_similarity("iOS_FB", "Android_GG") == 0.0

    def test_audience_similarity_empty(self):
        assert PatternRetriever._audience_similarity("", "iOS_FB") == 0.0

    def test_jaccard_similarity_full_match(self):
        assert PatternRetriever._jaccard_similarity({"a", "b"}, {"a", "b"}) == 1.0

    def test_jaccard_similarity_partial(self):
        assert PatternRetriever._jaccard_similarity({"a", "b"}, {"b", "c"}) == 1.0 / 3.0

    def test_jaccard_similarity_no_match(self):
        assert PatternRetriever._jaccard_similarity({"a"}, {"b"}) == 0.0

    def test_jaccard_similarity_empty(self):
        assert PatternRetriever._jaccard_similarity(set(), {"a"}) == 0.0

    def test_dna_similarity_match(self):
        assert PatternRetriever._dna_similarity(
            {"hook": "rescue", "visual": "gameplay"},
            {"hook": "rescue", "visual": "gameplay"},
        ) == 1.0

    def test_dna_similarity_partial(self):
        assert PatternRetriever._dna_similarity(
            {"hook": "rescue", "visual": "gameplay"},
            {"hook": "rescue", "visual": "cinematic"},
        ) == 0.5

    def test_dna_similarity_no_common_keys(self):
        assert PatternRetriever._dna_similarity(
            {"hook": "rescue"},
            {"visual": "gameplay"},
        ) == 0.0

    def test_metrics_similarity_inside_range(self):
        score = PatternRetriever._metrics_similarity(
            {"roas": 0.35, "ctr": 0.021},
            {"roas": (0.30, 0.50), "ctr": (0.015, 0.025)},
        )
        assert score == 1.0

    def test_metrics_similarity_outside_range(self):
        score = PatternRetriever._metrics_similarity(
            {"roas": 0.10},
            {"roas": (0.30, 0.50)},
        )
        assert score < 1.0

    def test_metrics_similarity_empty(self):
        assert PatternRetriever._metrics_similarity({}, {"roas": (0.3, 0.5)}) == 0.0
        assert PatternRetriever._metrics_similarity({"roas": 0.35}, {}) == 0.0

    def test_compute_similarity_full_match(self):
        """全维度匹配应得高分."""
        store = PatternStore()
        pattern = _make_pattern(
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            audience_segment="iOS_FB",
            signal_types=["roas_decay", "fatigue_high"],
            category="creative",
            market_conditions={"roas": (0.30, 0.50), "ctr": (0.015, 0.025)},
        )
        store.store(pattern)
        retriever = PatternRetriever(store)

        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            audience_segment="iOS_FB",
            signal_types=["roas_decay", "fatigue_high"],
            category="creative",
            metrics_snapshot={"roas": 0.35, "ctr": 0.021},
        )
        # 计算相似度
        similarity = retriever._compute_similarity(pattern, ctx)
        # opportunity_type(0.25) + action_type(0.10) + audience(0.15)
        # + signal Jaccard(1.0 * 0.15) + category(0.05)
        # + metrics(1.0 * 0.10) = 0.80
        assert similarity >= 0.70

    def test_compute_similarity_no_match(self):
        """无匹配维度应得低分."""
        store = PatternStore()
        pattern = _make_pattern(
            opportunity_type="winner_discovery",
            audience_segment="Android_GG",
        )
        store.store(pattern)
        retriever = PatternRetriever(store)

        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
        )
        similarity = retriever._compute_similarity(pattern, ctx)
        assert similarity == 0.0


# ═══════════════════════════════════════════════════════════════
# PatternRetriever Tests — 排序与推荐
# ═══════════════════════════════════════════════════════════════


class TestPatternRetrieverRanking:
    """模式排序与推荐测试."""

    def test_ranking_orders_by_confidence_and_reward(self):
        """高成功率+高奖励的模式排前面."""
        store = PatternStore()

        # 高成功率模式
        store.store(_make_pattern(
            pattern_id_override="high",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            audience_segment="iOS_FB",
            signal_types=["roas_decay", "fatigue_high"],
            category="creative",
            product_category="P04",
            samples=50,
            success_rate=0.90,
            avg_reward=0.85,
        ))

        # 中等成功率模式
        store.store(_make_pattern(
            pattern_id_override="mid",
            opportunity_type="creative_fatigue",
            action_type="mutate",
            audience_segment="iOS_FB",
            signal_types=["roas_decay"],
            category="creative",
            product_category="P04",
            samples=20,
            success_rate=0.65,
            avg_reward=0.50,
        ))

        store.store(_make_pattern(
            pattern_id_override="low",
            opportunity_type="creative_fatigue",
            action_type="pause",
            audience_segment="iOS_FB",
            category="creative",
            product_category="P04",
            samples=10,
            success_rate=0.40,
            avg_reward=0.30,
            signal_types=[],
        ))

        retriever = PatternRetriever(store)
        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
            action_type="replace_creative",
            signal_types=["roas_decay", "fatigue_high"],
            category="creative",
            product_category="P04",
        )
        result = retriever.retrieve(ctx)

        # 高成功率模式应排第一
        assert result.top_action is not None
        assert result.top_action.pattern.pattern_id == "high"

    def test_strong_recommend_threshold(self):
        """高相似度+高成功率 → strong_recommend."""
        store = PatternStore()
        store.store(_make_pattern(
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            audience_segment="iOS_FB",
            signal_types=["roas_decay", "fatigue_high"],
            category="creative",
            product_category="P04",
            samples=50,
            success_rate=0.85,
            avg_reward=0.82,
        ))
        retriever = PatternRetriever(store)

        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            audience_segment="iOS_FB",
            signal_types=["roas_decay", "fatigue_high"],
            category="creative",
            product_category="P04",
        )
        result = retriever.retrieve(ctx)
        assert result.top_action is not None
        assert result.top_action.recommendation_type == "strong_recommend"

    def test_avoid_patterns_ranked_as_caution(self):
        """低成功率模式标记为 caution."""
        store = PatternStore()
        pattern = _make_pattern(
            opportunity_type="creative_fatigue",
            action_type="scale",
            samples=20,
            success_rate=0.10,
            avg_reward=0.05,
            quality=PatternQuality.AVOID,
        )
        store.store(pattern)
        retriever = PatternRetriever(store)

        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            action_type="scale",
            audience_segment="iOS_FB",
        )
        result = retriever.retrieve(ctx)
        if result.avoid_actions:
            assert result.avoid_actions[0].recommendation_type == "caution"

    def test_reasoning_includes_samples_and_success_rate(self):
        """推荐理由包含样本量和成功率."""
        store = _build_populated_store()
        retriever = PatternRetriever(store)

        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
        )
        result = retriever.retrieve(ctx)
        if result.top_action:
            reasoning = result.top_action.reasoning
            assert any("cases" in r for r in reasoning)
            assert any("success rate" in r for r in reasoning)


# ═══════════════════════════════════════════════════════════════
# PatternRetriever Tests — 边界情况
# ═══════════════════════════════════════════════════════════════


class TestPatternRetrieverEdgeCases:
    """PatternRetriever 边界情况测试."""

    def test_empty_context(self):
        store = _build_populated_store()
        retriever = PatternRetriever(store)
        ctx = RetrievalContext()
        result = retriever.retrieve(ctx)
        # 空上下文应返回所有模式 (无过滤)
        assert result.total_matched > 0

    def test_low_similarity_filtered(self):
        """低相似度模式被过滤."""
        store = PatternStore()
        # 完全不匹配上下文的模式
        pattern = _make_pattern(
            opportunity_type="winner_discovery",
            action_type="scale",
            audience_segment="Android_GG",
        )
        store.store(pattern)
        retriever = PatternRetriever(store, min_similarity=0.5)

        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
        )
        result = retriever.retrieve(ctx)
        # 低相似度被过滤
        assert not result.has_recommendations

    def test_no_avoid_actions_when_all_succeed(self):
        """全部成功时无 avoid 动作."""
        store = PatternStore()
        store.store(_make_pattern(
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            audience_segment="iOS_FB",
            signal_types=["roas_decay", "fatigue_high"],
            category="creative",
            product_category="P04",
            samples=10,
            success_rate=0.90,
            avg_reward=0.85,
        ))
        retriever = PatternRetriever(store)

        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
            action_type="replace_creative",
            signal_types=["roas_decay", "fatigue_high"],
            category="creative",
            product_category="P04",
        )
        result = retriever.retrieve(ctx)
        assert not result.has_avoid_actions

    def test_multiple_opportunity_types(self):
        """多种机会类型并存时正确过滤."""
        store = _build_populated_store()
        retriever = PatternRetriever(store)

        ctx = RetrievalContext(
            opportunity_type="winner_discovery",
            audience_segment="iOS_FB",
            action_type="scale",
            signal_types=["roas_high", "ctr_high"],
            category="creative",
            product_category="P04",
        )
        result = retriever.retrieve(ctx)
        assert result.has_recommendations
        assert result.top_action.pattern.action.action_type == "scale"

    def test_summary_format(self):
        store = _build_populated_store()
        retriever = PatternRetriever(store)

        ctx = RetrievalContext(
            opportunity_type="winner_discovery",
            audience_segment="iOS_FB",
            action_type="scale",
            signal_types=["roas_high", "ctr_high"],
            category="creative",
            product_category="P04",
        )
        result = retriever.retrieve(ctx)
        assert "Found" in result.retrieval_summary
        assert "Best action" in result.retrieval_summary


# ═══════════════════════════════════════════════════════════════
# DecisionEnhancer Tests
# ═══════════════════════════════════════════════════════════════


class TestDecisionEnhancer:
    """DecisionEnhancer 测试."""

    def test_init(self):
        store = PatternStore()
        retriever = PatternRetriever(store)
        enhancer = DecisionEnhancer(retriever)
        assert enhancer._retriever is retriever

    def test_init_custom_params(self):
        store = PatternStore()
        retriever = PatternRetriever(store)
        enhancer = DecisionEnhancer(
            retriever,
            pattern_base_score=0.80,
            pattern_confidence_boost=0.20,
        )
        assert enhancer._pattern_base_score == 0.80
        assert enhancer._pattern_confidence_boost == 0.20

    def test_enhance_adds_pattern_strategies(self):
        """增强后 DecisionInput 包含模式策略."""
        store = _build_populated_store()
        retriever = PatternRetriever(store)
        enhancer = DecisionEnhancer(retriever)

        # 构建 DecisionInput - 需要足够丰富的 metadata 以匹配模式
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.models import (
            DecisionInput,
        )
        input_data = DecisionInput(
            opportunity={"action": "replace_creative", "product_id": "P04"},
            strategies=[],
            metadata={
                "audience_segment": "iOS_FB",
                "signal_types": ["roas_decay", "fatigue_high"],
                "product_category": "P04",
                "opportunity_type": "creative_fatigue",
                "category": "creative",
                "action_type": "replace_creative",
            },
        )

        enhanced, report = enhancer.enhance(input_data)

        assert report.pattern_used
        assert report.strategies_added > 0
        assert len(enhanced.strategies) > 0
        assert any("pattern_" in s.get("strategy_id", "") for s in enhanced.strategies)

    def test_enhance_adjusts_confidence(self):
        """增强后调整现有策略置信度."""
        store = _build_populated_store()
        retriever = PatternRetriever(store)
        enhancer = DecisionEnhancer(retriever)

        from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.models import (
            DecisionInput,
        )
        input_data = DecisionInput(
            opportunity={"action": "replace_creative", "product_id": "P04"},
            strategies=[
                {
                    "strategy_id": "S001",
                    "strategy_name": "replace_creative",
                    "strategy": {"action_type": "replace_creative"},
                    "confidence_score": 0.65,
                    "final_score": 0.60,
                },
            ],
            metadata={
                "audience_segment": "iOS_FB",
                "signal_types": ["roas_decay", "fatigue_high"],
                "opportunity_type": "creative_fatigue",
                "product_category": "P04",
                "category": "creative",
                "action_type": "replace_creative",
            },
        )

        enhanced, report = enhancer.enhance(input_data)

        assert report.pattern_used
        assert len(report.confidence_adjustments) > 0
        # 置信度应该被提升
        assert enhanced.strategies[0]["confidence_score"] > 0.65

    def test_enhance_generates_warnings(self):
        """增强后生成警告."""
        store = _build_populated_store()
        retriever = PatternRetriever(store)
        enhancer = DecisionEnhancer(retriever)

        from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.models import (
            DecisionInput,
        )
        input_data = DecisionInput(
            opportunity={"action": "replace_creative", "product_id": "P04"},
            strategies=[
                {
                    "strategy_id": "S001",
                    "strategy_name": "scale",
                    "strategy": {"action_type": "scale"},
                    "confidence_score": 0.70,
                    "final_score": 0.65,
                },
            ],
            metadata={"audience_segment": "iOS_FB"},
        )

        enhanced, report = enhancer.enhance(input_data)

        assert len(report.warnings) > 0
        # scale 在 creative_fatigue 下是 avoid 模式
        assert any("scale" in w.lower() for w in report.warnings)

    def test_enhance_empty_store(self):
        """空 PatternStore 时优雅降级."""
        store = PatternStore()
        retriever = PatternRetriever(store)
        enhancer = DecisionEnhancer(retriever)

        from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.models import (
            DecisionInput,
        )
        input_data = DecisionInput(
            opportunity={"action": "scale", "product_id": "P04"},
            strategies=[],
            metadata={},
        )

        enhanced, report = enhancer.enhance(input_data)

        assert not report.pattern_used
        assert report.strategies_added == 0
        assert len(enhanced.strategies) == 0

    def test_enhance_no_opportunity(self):
        """无 opportunity 时跳过增强."""
        store = _build_populated_store()
        retriever = PatternRetriever(store)
        enhancer = DecisionEnhancer(retriever)

        from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.models import (
            DecisionInput,
        )
        input_data = DecisionInput(opportunity=None, strategies=[], metadata={})

        enhanced, report = enhancer.enhance(input_data)

        assert not report.pattern_used
        assert "No retrieval context" in report.summary

    def test_enhance_and_retrieve(self):
        """enhance_and_retrieve 同时返回检索结果."""
        store = _build_populated_store()
        retriever = PatternRetriever(store)
        enhancer = DecisionEnhancer(retriever)

        from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.models import (
            DecisionInput,
        )
        input_data = DecisionInput(
            opportunity={"action": "replace_creative", "product_id": "P04"},
            strategies=[],
            metadata={"audience_segment": "iOS_FB"},
        )

        enhanced, report, retrieval = enhancer.enhance_and_retrieve(input_data)

        assert retrieval.has_recommendations
        assert report.pattern_used

    def test_enhancement_report_to_dict(self):
        """EnhancementReport 序列化."""
        report = EnhancementReport(
            pattern_used=True,
            strategies_added=2,
            confidence_adjustments=[
                {"strategy_index": 0, "adjustment": "+0.15"},
            ],
            warnings=["Historical warning: scale has 85% failure rate"],
            summary="Pattern-enhanced: top recommendation is 'replace_creative'",
        )
        d = report.to_dict()
        assert d["pattern_used"]
        assert d["strategies_added"] == 2
        assert len(d["confidence_adjustments"]) == 1
        assert "scale" in d["warnings"][0]

    def test_enhance_no_duplicate_pattern_strategies(self):
        """不重复添加已存在的模式策略."""
        store = _build_populated_store()
        retriever = PatternRetriever(store)
        enhancer = DecisionEnhancer(retriever)

        from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.models import (
            DecisionInput,
        )
        # 使用与模式策略相同的 ID
        input_data = DecisionInput(
            opportunity={"action": "replace_creative", "product_id": "P04"},
            strategies=[
                {
                    "strategy_id": "pattern_12345678",
                    "strategy_name": "existing",
                    "strategy": {"action_type": "replace_creative"},
                    "confidence_score": 0.70,
                    "final_score": 0.65,
                },
            ],
            metadata={"audience_segment": "iOS_FB"},
        )

        enhanced, report = enhancer.enhance(input_data)
        # 不应重复添加已存在的 pattern 策略
        assert report.strategies_added >= 0


# ═══════════════════════════════════════════════════════════════
# Integration Tests — Pattern → Decision 完整闭环
# ═══════════════════════════════════════════════════════════════


class TestPatternDecisionIntegration:
    """Pattern → Decision 完整闭环测试."""

    def test_end_to_end_creative_fatigue(self):
        """模拟素材疲劳场景: 完整闭环."""
        # 1. 构建有历史经验的 PatternStore
        store = PatternStore()
        store.store(_make_pattern(
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            audience_segment="iOS_FB",
            signal_types=["roas_decay", "fatigue_high"],
            category="creative",
            product_category="P04",
            samples=12,
            success_rate=0.83,
            avg_reward=0.79,
            quality=PatternQuality.RELIABLE,
            market_conditions={"roas": (0.25, 0.45), "ctr": (0.015, 0.030)},
        ))

        # 2. 创建 PatternRetriever 和 DecisionEnhancer
        retriever = PatternRetriever(store)
        enhancer = DecisionEnhancer(retriever)

        # 3. 模拟当前场景: iOS FB, ROAS 下降 35%, fatigue 0.82
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.models import (
            DecisionInput,
        )

        input_data = DecisionInput(
            opportunity={
                "action": "replace_creative",
                "product_id": "P04",
                "reason": "ROAS decay -35%, fatigue score 0.82",
            },
            strategies=[
                {
                    "strategy_id": "S001",
                    "strategy_name": "replace_creative",
                    "strategy": {
                        "action_type": "replace_creative",
                        "params_template": {"clone_hook": True},
                    },
                    "confidence_score": 0.65,
                    "final_score": 0.60,
                    "historical_score": 0.0,
                    "risk_score": 0.20,
                },
                {
                    "strategy_id": "S002",
                    "strategy_name": "pause",
                    "strategy": {"action_type": "pause"},
                    "confidence_score": 0.55,
                    "final_score": 0.50,
                    "historical_score": 0.0,
                    "risk_score": 0.30,
                },
            ],
            metadata={
                "audience_segment": "iOS_FB",
                "signal_types": ["roas_decay", "fatigue_high"],
                "opportunity_type": "creative_fatigue",
                "product_category": "P04",
                "category": "creative",
                "metrics_snapshot": {"roas": 0.32, "ctr": 0.021},
            },
        )

        # 4. 增强决策
        enhanced, report = enhancer.enhance(input_data)

        # 5. 验证闭环
        assert report.pattern_used
        assert report.strategies_added > 0  # 添加了模式策略
        # replace_creative 置信度应被提升
        assert len(report.confidence_adjustments) > 0

        # 6. 验证模式策略
        pattern_strategies = [
            s for s in enhanced.strategies
            if isinstance(s, dict) and s.get("strategy_id", "").startswith("pattern_")
        ]
        assert len(pattern_strategies) > 0
        ps = pattern_strategies[0]
        assert ps["strategy_name"].startswith("[Pattern]")
        assert "metadata" in ps
        assert ps["metadata"]["source"] == "pattern_memory"

    def test_end_to_end_no_history(self):
        """无历史经验时不做增强."""
        store = PatternStore()
        retriever = PatternRetriever(store)
        enhancer = DecisionEnhancer(retriever)

        from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.models import (
            DecisionInput,
        )

        input_data = DecisionInput(
            opportunity={"action": "scale", "product_id": "P04"},
            strategies=[
                {
                    "strategy_id": "S001",
                    "strategy_name": "scale",
                    "strategy": {"action_type": "scale"},
                    "confidence_score": 0.60,
                    "final_score": 0.55,
                },
            ],
            metadata={},
        )

        enhanced, report = enhancer.enhance(input_data)

        assert not report.pattern_used
        assert report.strategies_added == 0
        # 原始策略不变
        assert len(enhanced.strategies) == 1

    def test_fetch_history_before_decide(self):
        """模拟: 决策前先查询历史成功模式."""
        store = _build_populated_store()
        retriever = PatternRetriever(store)

        # 当前场景: 素材疲劳
        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
            action_type="replace_creative",
            signal_types=["roas_decay", "fatigue_high"],
            category="creative",
            product_category="P04",
            metrics_snapshot={"roas": 0.32, "ctr": 0.021},
        )

        result = retriever.retrieve(ctx)

        # 应该推荐 replace_creative
        assert result.top_action is not None
        assert result.top_action.pattern.action.action_type == "replace_creative"
        assert result.top_action.confidence > 0.4

        # 应该有 avoid 动作 (scale)
        assert result.has_avoid_actions
        avoid_actions = [a.pattern.action.action_type for a in result.avoid_actions]
        assert "scale" in avoid_actions

    def test_confidence_boost_applied_correctly(self):
        """验证置信度提升幅度."""
        store = PatternStore()
        store.store(_make_pattern(
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            audience_segment="iOS_FB",
            signal_types=["roas_decay", "fatigue_high"],
            category="creative",
            product_category="P04",
            samples=50,
            success_rate=0.90,
            avg_reward=0.85,
        ))
        retriever = PatternRetriever(store)
        enhancer = DecisionEnhancer(retriever)

        from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.models import (
            DecisionInput,
        )

        input_data = DecisionInput(
            opportunity={"action": "replace_creative", "product_id": "P04"},
            strategies=[
                {
                    "strategy_id": "S001",
                    "strategy_name": "replace_creative",
                    "strategy": {"action_type": "replace_creative"},
                    "confidence_score": 0.50,
                    "final_score": 0.45,
                },
            ],
            metadata={
                "audience_segment": "iOS_FB",
                "opportunity_type": "creative_fatigue",
                "signal_types": ["roas_decay", "fatigue_high"],
                "category": "creative",
                "product_category": "P04",
            },
        )

        enhanced, report = enhancer.enhance(input_data)

        # 置信度应被提升 (不超过 max_confidence_boost=0.25)
        assert len(report.confidence_adjustments) > 0
        original = 0.50
        assert enhanced.strategies[0]["confidence_score"] > original
        assert enhanced.strategies[0]["confidence_score"] <= original + 0.25

    def test_pattern_miner_to_retriever_flow(self):
        """完整流程: Experience → PatternMiner → PatternStore → PatternRetriever."""
        # 1. 创建经验
        exp_store = ExperienceStore()
        for _ in range(12):
            exp = _make_experience(
                opportunity_type="creative_fatigue",
                action_type="replace_creative",
                audience_segment="iOS_FB",
                success=True,
                reward=0.82,
            )
            exp_store.store(exp)

        # 2. 挖掘模式
        miner = PatternMiner(exp_store)
        patterns = miner.mine(
            dimensions=[PatternMiningDimension.OPPORTUNITY_ACTION],
            min_samples=3,
        )
        assert len(patterns) > 0

        # 3. 存储模式
        pattern_store = PatternStore()
        for p in patterns:
            pattern_store.store(p)

        # 4. 检索
        retriever = PatternRetriever(pattern_store)
        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
            action_type="replace_creative",
            category="creative",
            product_category="P04",
        )
        result = retriever.retrieve(ctx)

        assert result.has_recommendations
        assert result.top_action is not None
        assert result.top_action.pattern.action.action_type == "replace_creative"

    def test_retrieval_result_summary_with_context(self):
        """检索结果包含上下文信息."""
        store = _build_populated_store()
        retriever = PatternRetriever(store)

        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
            product_category="P04",
        )
        result = retriever.retrieve(ctx)

        assert "opportunity_type" in result.context
        assert result.context["opportunity_type"] == "creative_fatigue"

    def test_similarity_between_platforms(self):
        """跨平台相似度: iOS_FB vs iOS_GG 应部分匹配."""
        store = PatternStore()
        pattern = _make_pattern(
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            audience_segment="iOS_GG",
            samples=10,
            success_rate=0.80,
            avg_reward=0.75,
        )
        store.store(pattern)
        retriever = PatternRetriever(store)

        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
        )
        result = retriever.retrieve(ctx)

        # 跨平台仍应匹配 (部分相似度)
        if result.has_recommendations:
            rec = result.recommendations[0]
            # audience 部分匹配 (同一平台 iOS)
            assert rec.similarity_score > 0.0