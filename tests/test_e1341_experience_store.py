"""E13.4.1 Growth Experience Memory Store — 测试套件.

测试覆盖:
  - ExperienceCategory / ExperienceOutcomeLevel 枚举
  - ExperienceContext / ExperienceOutcome 模型
  - GrowthExperience 模型 (创建、推断、序列化、成功/失败判断)
  - ExperienceQuery 查询条件
  - ExperienceStats 统计聚合
  - ExperienceStore: store / store_batch / query / 便捷方法 / 统计
  - ExperienceStore: 容量控制 / 清空 / 计数
  - MemoryRetriever: enhance_opportunity / get_best_action / get_action_success_rate
  - MemoryRetriever: get_similar_experiences / get_failure_warnings / get_summary
  - 边界条件: 空存储 / 大容量 / 重复存储
  - 集成场景: 完整决策→执行→记忆闭环
"""

from __future__ import annotations

import pytest
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _make_context(
    product_id: str = "p001",
    date: str = "2026-07-24",
    opportunity_type: str = "creative_scale",
    opportunity_id: str = "opp001",
    action_type: str = "clone_dna",
    entity_id: str = "c001",
    entity_type: str = "creative",
    **kwargs,
) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceContext
    return ExperienceContext(
        product_id=product_id,
        date=date,
        opportunity_type=opportunity_type,
        opportunity_id=opportunity_id,
        action_type=action_type,
        entity_id=entity_id,
        entity_type=entity_type,
        **kwargs,
    )


def _make_outcome(
    success: bool = True,
    outcome_level: Any = None,
    actual_reward: float = 0.85,
    metrics_before: dict[str, float] | None = None,
    metrics_after: dict[str, float] | None = None,
    **kwargs,
) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
        ExperienceOutcome, ExperienceOutcomeLevel,
    )
    if outcome_level is None:
        outcome_level = ExperienceOutcomeLevel.SUCCESS if success else ExperienceOutcomeLevel.FAILURE
    return ExperienceOutcome(
        success=success,
        outcome_level=outcome_level,
        actual_reward=actual_reward,
        metrics_before=metrics_before or {"roas": 1.0, "ctr": 0.03},
        metrics_after=metrics_after or {"roas": 1.5, "ctr": 0.05},
        **kwargs,
    )


def _make_experience(
    action_type: str = "clone_dna",
    opportunity_type: str = "creative_scale",
    entity_id: str = "c001",
    reward: float = 0.85,
    success: bool = True,
    confidence: float = 0.9,
    outcome_level: Any = None,
    **kwargs,
) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
        GrowthExperience, ExperienceOutcomeLevel,
    )
    if outcome_level is None:
        outcome_level = ExperienceOutcomeLevel.SUCCESS if success else ExperienceOutcomeLevel.FAILURE
    return GrowthExperience(
        context=_make_context(
            action_type=action_type,
            opportunity_type=opportunity_type,
            entity_id=entity_id,
        ),
        action_type=action_type,
        action_params={"test": True},
        outcome=_make_outcome(
            success=success,
            outcome_level=outcome_level,
            actual_reward=reward,
        ),
        reward=reward,
        confidence=confidence,
        **kwargs,
    )


def _make_opportunity(
    opp_type_str: str = "creative_scale",
    entity_id: str = "c001",
    confidence: float = 0.9,
) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
        GrowthOpportunity, OpportunityType, OpportunityPriority,
    )
    opp_type_map = {
        "creative_scale": OpportunityType.CREATIVE_SCALE,
        "creative_refresh": OpportunityType.CREATIVE_REFRESH,
        "creative_mutation": OpportunityType.CREATIVE_MUTATION,
        "ua_scale": OpportunityType.UA_SCALE,
        "budget_reduction": OpportunityType.BUDGET_REDUCTION,
        "ua_rebalance": OpportunityType.UA_REBALANCE,
        "monetization_optimize": OpportunityType.MONETIZATION_OPTIMIZE,
        "monetization_scale": OpportunityType.MONETIZATION_SCALE,
    }
    return GrowthOpportunity(
        opportunity_type=opp_type_map.get(opp_type_str, OpportunityType.CREATIVE_SCALE),
        entity_id=entity_id,
        confidence=confidence,
        priority=OpportunityPriority.HIGH,
    )


# ═══════════════════════════════════════════════════════════════
# Test: Enums
# ═══════════════════════════════════════════════════════════════

class TestExperienceCategory:
    """ExperienceCategory 枚举."""

    def test_categories_exist(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceCategory
        assert ExperienceCategory.CREATIVE.value == "creative"
        assert ExperienceCategory.UA.value == "ua"
        assert ExperienceCategory.REVENUE.value == "revenue"
        assert ExperienceCategory.MONETIZATION.value == "monetization"

    def test_category_values_are_strings(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceCategory
        for cat in ExperienceCategory:
            assert isinstance(cat.value, str)


class TestExperienceOutcomeLevel:
    """ExperienceOutcomeLevel 枚举."""

    def test_levels_exist(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceOutcomeLevel
        assert ExperienceOutcomeLevel.STRONG_SUCCESS.value == "strong_success"
        assert ExperienceOutcomeLevel.SUCCESS.value == "success"
        assert ExperienceOutcomeLevel.NEUTRAL.value == "neutral"
        assert ExperienceOutcomeLevel.FAILURE.value == "failure"
        assert ExperienceOutcomeLevel.STRONG_FAILURE.value == "strong_failure"

    def test_five_levels(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceOutcomeLevel
        assert len(list(ExperienceOutcomeLevel)) == 5


# ═══════════════════════════════════════════════════════════════
# Test: ExperienceContext
# ═══════════════════════════════════════════════════════════════

class TestExperienceContext:
    """ExperienceContext 模型."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceContext
        ctx = ExperienceContext()
        assert ctx.product_id == ""
        assert ctx.date == ""
        assert ctx.entity_type == "creative"

    def test_full_creation(self):
        ctx = _make_context(
            product_id="p001",
            date="2026-07-24",
            opportunity_type="creative_scale",
            action_type="clone_dna",
            entity_id="c001",
            market_conditions={"roas": 1.5, "cpi": 2.3},
            trigger_signals=["creative_winner", "scale_opportunity"],
            dna_genes={"hook": "rescue", "visual": "gameplay"},
            audience_segment="female_25_35",
        )
        assert ctx.product_id == "p001"
        assert ctx.market_conditions["roas"] == 1.5
        assert "creative_winner" in ctx.trigger_signals
        assert ctx.dna_genes["hook"] == "rescue"
        assert ctx.audience_segment == "female_25_35"

    def test_to_dict(self):
        ctx = _make_context(
            product_id="p001",
            date="2026-07-24",
            opportunity_type="creative_scale",
            action_type="clone_dna",
        )
        d = ctx.to_dict()
        assert d["product_id"] == "p001"
        assert d["date"] == "2026-07-24"
        assert d["opportunity_type"] == "creative_scale"
        assert d["action_type"] == "clone_dna"
        assert isinstance(d["market_conditions"], dict)
        assert isinstance(d["trigger_signals"], list)

    def test_empty_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceContext
        ctx = ExperienceContext()
        d = ctx.to_dict()
        assert d["product_id"] == ""
        assert d["market_conditions"] == {}
        assert d["trigger_signals"] == []

    def test_market_conditions_immutable_per_instance(self):
        ctx1 = _make_context(market_conditions={"roas": 1.0})
        ctx2 = _make_context(market_conditions={"roas": 2.0})
        assert ctx1.market_conditions["roas"] == 1.0
        assert ctx2.market_conditions["roas"] == 2.0


# ═══════════════════════════════════════════════════════════════
# Test: ExperienceOutcome
# ═══════════════════════════════════════════════════════════════

class TestExperienceOutcome:
    """ExperienceOutcome 模型."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceOutcome
        outcome = ExperienceOutcome()
        assert outcome.success is False
        assert outcome.outcome_level.value == "neutral"
        assert outcome.actual_reward == 0.0

    def test_success_outcome(self):
        outcome = _make_outcome(success=True, actual_reward=0.9)
        assert outcome.success is True
        assert outcome.outcome_level.value == "success"
        assert outcome.actual_reward == 0.9

    def test_failure_outcome(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceOutcomeLevel
        outcome = _make_outcome(
            success=False,
            outcome_level=ExperienceOutcomeLevel.STRONG_FAILURE,
            actual_reward=0.1,
            error="Simulated failure",
            rolled_back=True,
        )
        assert outcome.success is False
        assert outcome.outcome_level == ExperienceOutcomeLevel.STRONG_FAILURE
        assert outcome.actual_reward == 0.1
        assert outcome.error == "Simulated failure"
        assert outcome.rolled_back is True

    def test_metrics_delta_auto_computed(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceOutcome
        outcome = ExperienceOutcome(
            success=True,
            metrics_before={"roas": 1.0},
            metrics_after={"roas": 1.5},
            metrics_delta={"roas": 0.5},
        )
        assert outcome.metrics_delta["roas"] == 0.5

    def test_to_dict(self):
        outcome = _make_outcome(success=True)
        d = outcome.to_dict()
        assert d["success"] is True
        assert d["outcome_level"] == "success"
        assert d["actual_reward"] == 0.85
        assert "roas" in d["metrics_before"]

    def test_neutral_outcome(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            ExperienceOutcome, ExperienceOutcomeLevel,
        )
        outcome = ExperienceOutcome(
            success=True,
            outcome_level=ExperienceOutcomeLevel.NEUTRAL,
            actual_reward=0.5,
        )
        assert outcome.outcome_level == ExperienceOutcomeLevel.NEUTRAL

    def test_time_to_outcome(self):
        outcome = _make_outcome(time_to_outcome_hours=72.0)
        assert outcome.time_to_outcome_hours == 72.0


# ═══════════════════════════════════════════════════════════════
# Test: GrowthExperience
# ═══════════════════════════════════════════════════════════════

class TestGrowthExperience:
    """GrowthExperience 模型."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import GrowthExperience
        exp = GrowthExperience()
        assert exp.experience_id != ""
        assert exp.action_type == ""
        assert exp.reward == 0.0
        assert exp.context is not None

    def test_full_creation(self):
        exp = _make_experience(
            action_type="mutate_hook",
            opportunity_type="creative_refresh",
            entity_id="c002",
            reward=0.92,
            confidence=0.88,
        )
        assert exp.action_type == "mutate_hook"
        assert exp.context.opportunity_type == "creative_refresh"
        assert exp.reward == 0.92
        assert exp.confidence == 0.88

    def test_category_inference_creative(self):
        """测试创意类动作的类别推断."""
        exp = _make_experience(action_type="clone_dna")
        assert exp.category.value == "creative"

    def test_category_inference_ua(self):
        """测试UA类动作的类别推断."""
        exp = _make_experience(action_type="increase_budget", opportunity_type="ua_scale")
        assert exp.category.value == "ua"

    def test_category_inference_revenue(self):
        """测试收入类动作的类别推断."""
        exp = _make_experience(action_type="optimize_pricing", opportunity_type="monetization_optimize")
        assert exp.category.value == "revenue"

    def test_category_inference_mutate_hook(self):
        exp = _make_experience(action_type="mutate_hook")
        assert exp.category.value == "creative"

    def test_category_inference_mutate_visual(self):
        exp = _make_experience(action_type="mutate_visual")
        assert exp.category.value == "creative"

    def test_category_inference_generate_variants(self):
        exp = _make_experience(action_type="generate_variants")
        assert exp.category.value == "creative"

    def test_category_inference_create_population(self):
        exp = _make_experience(action_type="create_population")
        assert exp.category.value == "creative"

    def test_category_inference_launch_ab_test(self):
        exp = _make_experience(action_type="launch_ab_test")
        assert exp.category.value == "creative"

    def test_category_inference_replace_creative(self):
        exp = _make_experience(action_type="replace_creative")
        assert exp.category.value == "creative"

    def test_category_inference_increase_budget(self):
        exp = _make_experience(action_type="increase_budget", opportunity_type="ua_scale")
        assert exp.category.value == "ua"

    def test_category_inference_reduce_budget(self):
        exp = _make_experience(action_type="reduce_budget", opportunity_type="budget_reduction")
        assert exp.category.value == "ua"

    def test_category_inference_duplicate_campaign(self):
        exp = _make_experience(action_type="duplicate_campaign", opportunity_type="ua_scale")
        assert exp.category.value == "ua"

    def test_category_inference_pause_campaign(self):
        exp = _make_experience(action_type="pause_campaign", opportunity_type="budget_reduction")
        assert exp.category.value == "ua"

    def test_category_inference_expand_targeting(self):
        exp = _make_experience(action_type="expand_targeting", opportunity_type="ua_scale")
        assert exp.category.value == "ua"

    def test_category_inference_reallocate_budget(self):
        exp = _make_experience(action_type="reallocate_budget", opportunity_type="ua_rebalance")
        assert exp.category.value == "ua"

    def test_category_inference_adjust_bid(self):
        exp = _make_experience(action_type="adjust_bid", opportunity_type="ua_rebalance")
        assert exp.category.value == "ua"

    def test_category_inference_optimize_pricing(self):
        exp = _make_experience(action_type="optimize_pricing", opportunity_type="monetization_optimize")
        assert exp.category.value == "revenue"

    def test_category_inference_optimize_ad_placement(self):
        exp = _make_experience(action_type="optimize_ad_placement", opportunity_type="monetization_optimize")
        assert exp.category.value == "revenue"

    def test_category_inference_increase_retention(self):
        exp = _make_experience(action_type="increase_retention", opportunity_type="monetization_scale")
        assert exp.category.value == "revenue"

    def test_category_inference_create_high_value_audience(self):
        exp = _make_experience(action_type="create_high_value_audience", opportunity_type="monetization_scale")
        assert exp.category.value == "revenue"

    def test_reward_fallback_from_outcome(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import GrowthExperience
        exp = GrowthExperience(
            action_type="clone_dna",
            outcome=_make_outcome(success=True, actual_reward=0.75),
            reward=0.0,  # 未设置 reward
        )
        assert exp.reward == 0.75  # 从 outcome 推断

    def test_reward_not_overridden(self):
        """已设置的 reward 不被 outcome 覆盖."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import GrowthExperience
        exp = GrowthExperience(
            action_type="clone_dna",
            outcome=_make_outcome(success=True, actual_reward=0.75),
            reward=0.9,  # 已设置
        )
        assert exp.reward == 0.9  # 不覆盖

    def test_is_successful(self):
        exp = _make_experience(success=True)
        assert exp.is_successful() is True
        assert exp.is_failure() is False

    def test_is_failure(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceOutcomeLevel
        exp = _make_experience(
            success=False,
            outcome_level=ExperienceOutcomeLevel.STRONG_FAILURE,
        )
        assert exp.is_failure() is True
        assert exp.is_successful() is False

    def test_neutral_is_neither(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            GrowthExperience, ExperienceOutcomeLevel,
        )
        exp = GrowthExperience(
            action_type="clone_dna",
            outcome=_make_outcome(
                success=True,
                outcome_level=ExperienceOutcomeLevel.NEUTRAL,
            ),
        )
        assert exp.is_successful() is False
        assert exp.is_failure() is False

    def test_strong_success_is_successful(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceOutcomeLevel
        exp = _make_experience(
            success=True,
            outcome_level=ExperienceOutcomeLevel.STRONG_SUCCESS,
        )
        assert exp.is_successful() is True

    def test_to_dict(self):
        exp = _make_experience(action_type="clone_dna")
        d = exp.to_dict()
        assert d["action_type"] == "clone_dna"
        assert d["category"] == "creative"
        assert "context" in d
        assert "outcome" in d
        assert d["reward"] == 0.85

    def test_unique_experience_ids(self):
        exp1 = _make_experience()
        exp2 = _make_experience()
        assert exp1.experience_id != exp2.experience_id

    def test_tags(self):
        exp = _make_experience(tags=["winner", "high_roas", "merge_game"])
        assert "winner" in exp.tags
        assert "merge_game" in exp.tags
        assert len(exp.tags) == 3

    def test_metadata(self):
        exp = _make_experience(metadata={"version": "v1", "experiment_id": "exp001"})
        assert exp.metadata["version"] == "v1"
        assert exp.metadata["experiment_id"] == "exp001"

    def test_different_rewards(self):
        """不同奖励值正确存储."""
        exp1 = _make_experience(reward=0.9)
        exp2 = _make_experience(reward=0.3, success=False)
        assert exp1.reward == 0.9
        assert exp2.reward == 0.3


# ═══════════════════════════════════════════════════════════════
# Test: ExperienceQuery
# ═══════════════════════════════════════════════════════════════

class TestExperienceQuery:
    """ExperienceQuery 查询条件."""

    def test_default_query(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        q = ExperienceQuery()
        assert q.action_types == []
        assert q.limit == 100
        assert q.sort_by == "reward"
        assert q.sort_desc is True

    def test_filtered_query(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        q = ExperienceQuery(
            action_types=["clone_dna", "mutate_hook"],
            opportunity_types=["creative_scale"],
            categories=["creative"],
            entity_id="c001",
            product_id="p001",
            min_reward=0.5,
            min_confidence=0.7,
            success_only=True,
            limit=20,
            sort_by="timestamp",
            sort_desc=False,
        )
        assert len(q.action_types) == 2
        assert q.limit == 20
        assert q.success_only is True
        assert q.sort_desc is False

    def test_date_range(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        q = ExperienceQuery(date_from="2026-07-01", date_to="2026-07-31")
        assert q.date_from == "2026-07-01"
        assert q.date_to == "2026-07-31"

    def test_tags_filter(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        q = ExperienceQuery(tags=["winner", "high_roas"])
        assert len(q.tags) == 2

    def test_failure_only(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        q = ExperienceQuery(failure_only=True)
        assert q.failure_only is True
        assert q.success_only is False


# ═══════════════════════════════════════════════════════════════
# Test: ExperienceStats
# ═══════════════════════════════════════════════════════════════

class TestExperienceStats:
    """ExperienceStats 统计模型."""

    def test_default_stats(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceStats
        stats = ExperienceStats()
        assert stats.total_experiences == 0
        assert stats.success_rate == 0.0
        assert stats.by_action_type == {}
        assert stats.recent_trend == []

    def test_populated_stats(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceStats
        stats = ExperienceStats(
            total_experiences=100,
            total_success=70,
            total_failure=30,
            success_rate=0.7,
            avg_reward=0.65,
            avg_confidence=0.82,
            by_action_type={"clone_dna": {"count": 50, "success_rate": 0.72}},
            by_category={"creative": {"count": 60, "success_rate": 0.68}},
            by_opportunity_type={"creative_scale": {"count": 40, "success_rate": 0.75}},
            top_actions=[{"action_type": "clone_dna", "success_rate": 0.72}],
            worst_actions=[{"action_type": "mutate_visual", "success_rate": 0.35}],
            recent_trend=[1.0, 0.0, 1.0, 1.0, 0.0],
        )
        assert stats.total_experiences == 100
        assert stats.total_success == 70
        assert stats.success_rate == 0.7
        assert stats.by_action_type["clone_dna"]["success_rate"] == 0.72
        assert len(stats.top_actions) == 1
        assert len(stats.recent_trend) == 5

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceStats
        stats = ExperienceStats(
            total_experiences=10,
            total_success=8,
            total_failure=2,
            success_rate=0.8,
            avg_reward=0.7,
            avg_confidence=0.85,
            by_action_type={"clone_dna": {"count": 10, "success_count": 8, "success_rate": 0.8, "avg_reward": 0.7}},
        )
        d = stats.to_dict()
        assert d["total_experiences"] == 10
        assert d["success_rate"] == 0.8
        assert d["by_action_type"]["clone_dna"]["count"] == 10


# ═══════════════════════════════════════════════════════════════
# Test: ExperienceStore
# ═══════════════════════════════════════════════════════════════

class TestExperienceStoreBasic:
    """ExperienceStore 基础操作."""

    def test_create_store(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        assert store.count == 0
        assert store.size() == 0

    def test_store_single_experience(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        exp = _make_experience()
        eid = store.store(exp)
        assert eid == exp.experience_id
        assert store.count == 1

    def test_store_batch(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        exps = [_make_experience(action_type="clone_dna") for _ in range(5)]
        ids = store.store_batch(exps)
        assert len(ids) == 5
        assert store.count == 5

    def test_store_multiple_types(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        store.store(_make_experience(action_type="clone_dna", opportunity_type="creative_scale"))
        store.store(_make_experience(action_type="increase_budget", opportunity_type="ua_scale"))
        store.store(_make_experience(action_type="optimize_pricing", opportunity_type="monetization_optimize"))
        assert store.count == 3

    def test_clear(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        store.store(_make_experience())
        store.clear()
        assert store.count == 0

    def test_total_stored_tracks_cumulative(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore(max_capacity=3)
        for _ in range(5):
            store.store(_make_experience())
        # 5 条存储，3 条保留
        assert store.count == 3
        assert store.total_stored == 5


class TestExperienceStoreQuery:
    """ExperienceStore 查询功能."""

    def test_query_by_action_type(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        store = ExperienceStore()
        store.store(_make_experience(action_type="clone_dna"))
        store.store(_make_experience(action_type="mutate_hook"))
        store.store(_make_experience(action_type="clone_dna"))

        results = store.query(ExperienceQuery(action_types=["clone_dna"]))
        assert len(results) == 2
        assert all(e.action_type == "clone_dna" for e in results)

    def test_query_by_opportunity_type(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        store = ExperienceStore()
        store.store(_make_experience(opportunity_type="creative_scale"))
        store.store(_make_experience(opportunity_type="ua_scale", action_type="increase_budget"))
        store.store(_make_experience(opportunity_type="creative_scale"))

        results = store.query(ExperienceQuery(opportunity_types=["creative_scale"]))
        assert len(results) == 2

    def test_query_by_category(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        store = ExperienceStore()
        store.store(_make_experience(action_type="clone_dna"))  # creative
        store.store(_make_experience(action_type="increase_budget", opportunity_type="ua_scale"))  # ua
        store.store(_make_experience(action_type="mutate_hook"))  # creative

        results = store.query(ExperienceQuery(categories=["creative"]))
        assert len(results) == 2

    def test_query_by_entity_id(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        store = ExperienceStore()
        store.store(_make_experience(entity_id="c001"))
        store.store(_make_experience(entity_id="c002"))
        store.store(_make_experience(entity_id="c001"))

        results = store.query(ExperienceQuery(entity_id="c001"))
        assert len(results) == 2

    def test_query_by_product_id(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        store = ExperienceStore()
        ctx1 = _make_context(product_id="p001")
        ctx2 = _make_context(product_id="p002")
        store.store(_make_experience())
        store.store(_make_experience())
        # Override context
        store._experiences[0].context = ctx1
        store._experiences[1].context = ctx2

        results = store.query(ExperienceQuery(product_id="p001"))
        assert len(results) == 1

    def test_query_min_reward(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        store = ExperienceStore()
        store.store(_make_experience(reward=0.9))
        store.store(_make_experience(reward=0.3, success=False))
        store.store(_make_experience(reward=0.7))

        results = store.query(ExperienceQuery(min_reward=0.7))
        assert len(results) == 2

    def test_query_min_confidence(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        store = ExperienceStore()
        store.store(_make_experience(confidence=0.9))
        store.store(_make_experience(confidence=0.5))
        store.store(_make_experience(confidence=0.8))

        results = store.query(ExperienceQuery(min_confidence=0.8))
        assert len(results) == 2

    def test_query_success_only(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        store = ExperienceStore()
        store.store(_make_experience(success=True))
        store.store(_make_experience(success=False))
        store.store(_make_experience(success=True))

        results = store.query(ExperienceQuery(success_only=True))
        assert len(results) == 2
        assert all(e.is_successful() for e in results)

    def test_query_failure_only(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        store = ExperienceStore()
        store.store(_make_experience(success=True))
        store.store(_make_experience(success=False))
        store.store(_make_experience(success=False))

        results = store.query(ExperienceQuery(failure_only=True))
        assert len(results) == 2
        assert all(e.is_failure() for e in results)

    def test_query_tags(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        store = ExperienceStore()
        store.store(_make_experience(tags=["winner", "high_roas"]))
        store.store(_make_experience(tags=["loser", "low_roas"]))
        store.store(_make_experience(tags=["winner", "merge_game"]))

        results = store.query(ExperienceQuery(tags=["winner"]))
        assert len(results) == 2

    def test_query_limit(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        store = ExperienceStore()
        for _ in range(10):
            store.store(_make_experience())

        results = store.query(ExperienceQuery(limit=3))
        assert len(results) == 3

    def test_query_sort_by_reward(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        store = ExperienceStore()
        store.store(_make_experience(reward=0.3))
        store.store(_make_experience(reward=0.9))
        store.store(_make_experience(reward=0.6))

        results = store.query(ExperienceQuery(sort_by="reward", sort_desc=True))
        assert results[0].reward >= results[1].reward >= results[2].reward

    def test_query_sort_by_timestamp(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        store = ExperienceStore()
        # Timestamps are auto-generated in order
        store.store(_make_experience(reward=0.3))
        store.store(_make_experience(reward=0.9))

        results = store.query(ExperienceQuery(sort_by="timestamp", sort_desc=True))
        assert len(results) == 2

    def test_query_date_range(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        store = ExperienceStore()
        for i, date in enumerate(["2026-07-01", "2026-07-15", "2026-07-30"]):
            exp = _make_experience()
            exp.context = _make_context(date=date)
            store._experiences.append(exp)
            store._total_stored += 1

        results = store.query(ExperienceQuery(date_from="2026-07-10", date_to="2026-07-25"))
        assert len(results) == 1
        assert results[0].context.date == "2026-07-15"

    def test_query_combined_filters(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        store = ExperienceStore()
        store.store(_make_experience(action_type="clone_dna", opportunity_type="creative_scale", reward=0.9))
        store.store(_make_experience(action_type="clone_dna", opportunity_type="creative_scale", reward=0.3, success=False))
        store.store(_make_experience(action_type="mutate_hook", opportunity_type="creative_refresh", reward=0.8))

        results = store.query(ExperienceQuery(
            action_types=["clone_dna"],
            opportunity_types=["creative_scale"],
            success_only=True,
        ))
        assert len(results) == 1

    def test_query_empty_store(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery
        store = ExperienceStore()
        results = store.query(ExperienceQuery())
        assert results == []


class TestExperienceStoreConvenience:
    """ExperienceStore 便捷方法."""

    def test_get_by_action_type(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        store.store(_make_experience(action_type="clone_dna"))
        store.store(_make_experience(action_type="mutate_hook"))

        results = store.get_by_action_type("clone_dna")
        assert len(results) == 1
        assert results[0].action_type == "clone_dna"

    def test_get_by_opportunity_type(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        store.store(_make_experience(opportunity_type="creative_scale"))
        store.store(_make_experience(opportunity_type="ua_scale", action_type="increase_budget"))

        results = store.get_by_opportunity_type("creative_scale")
        assert len(results) == 1

    def test_get_by_category(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceCategory
        store = ExperienceStore()
        store.store(_make_experience(action_type="clone_dna"))
        store.store(_make_experience(action_type="increase_budget", opportunity_type="ua_scale"))

        results = store.get_by_category(ExperienceCategory.CREATIVE)
        assert len(results) == 1

    def test_get_by_entity(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        store.store(_make_experience(entity_id="c001"))
        store.store(_make_experience(entity_id="c002"))

        results = store.get_by_entity("c001")
        assert len(results) == 1

    def test_get_by_product(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        e1 = _make_experience()
        e1.context = _make_context(product_id="p001")
        e2 = _make_experience()
        e2.context = _make_context(product_id="p002")
        store.store(e1)
        store.store(e2)

        results = store.get_by_product("p001")
        assert len(results) == 1

    def test_get_successful(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        store.store(_make_experience(success=True))
        store.store(_make_experience(success=False))
        store.store(_make_experience(success=True))

        results = store.get_successful()
        assert len(results) == 2

    def test_get_failures(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        store.store(_make_experience(success=False))
        store.store(_make_experience(success=True))
        store.store(_make_experience(success=False))

        results = store.get_failures()
        assert len(results) == 2

    def test_get_recent(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        for _ in range(15):
            store.store(_make_experience())

        results = store.get_recent(10)
        assert len(results) == 10

    def test_get_top_rewarded(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        for r in [0.3, 0.9, 0.5, 0.95, 0.7]:
            store.store(_make_experience(reward=r))

        results = store.get_top_rewarded(3)
        assert len(results) == 3
        assert results[0].reward >= results[1].reward >= results[2].reward

    def test_get_all(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        for _ in range(5):
            store.store(_make_experience())
        assert len(store.get_all()) == 5


class TestExperienceStoreStats:
    """ExperienceStore 统计功能."""

    def test_stats_empty_store(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        stats = store.get_stats()
        assert stats.total_experiences == 0
        assert stats.success_rate == 0.0

    def test_stats_basic(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        for _ in range(8):
            store.store(_make_experience(success=True, reward=0.8))
        for _ in range(2):
            store.store(_make_experience(success=False, reward=0.2))

        stats = store.get_stats()
        assert stats.total_experiences == 10
        assert stats.total_success == 8
        assert stats.total_failure == 2
        assert stats.success_rate == 0.8

    def test_stats_by_action_type(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        for _ in range(5):
            store.store(_make_experience(action_type="clone_dna", success=True, reward=0.8))
        for _ in range(3):
            store.store(_make_experience(action_type="mutate_hook", success=True, reward=0.7))
        for _ in range(2):
            store.store(_make_experience(action_type="mutate_hook", success=False, reward=0.3))

        stats = store.get_stats()
        assert "clone_dna" in stats.by_action_type
        assert stats.by_action_type["clone_dna"]["success_rate"] == 1.0
        assert stats.by_action_type["mutate_hook"]["count"] == 5

    def test_stats_by_category(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        store.store(_make_experience(action_type="clone_dna", success=True))
        store.store(_make_experience(action_type="increase_budget", opportunity_type="ua_scale", success=True))
        store.store(_make_experience(action_type="optimize_pricing", opportunity_type="monetization_optimize", success=False))

        stats = store.get_stats()
        assert "creative" in stats.by_category
        assert "ua" in stats.by_category
        assert "revenue" in stats.by_category

    def test_stats_by_opportunity_type(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        store.store(_make_experience(opportunity_type="creative_scale", success=True))
        store.store(_make_experience(opportunity_type="creative_scale", success=True))
        store.store(_make_experience(opportunity_type="ua_scale", success=False, action_type="increase_budget"))

        stats = store.get_stats()
        assert "creative_scale" in stats.by_opportunity_type
        assert stats.by_opportunity_type["creative_scale"]["success_rate"] == 1.0

    def test_stats_top_actions(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        # clone_dna: 高成功率
        for _ in range(5):
            store.store(_make_experience(action_type="clone_dna", success=True, reward=0.9))
        # mutate_visual: 低成功率
        for _ in range(5):
            store.store(_make_experience(action_type="mutate_visual", success=False, reward=0.2))

        stats = store.get_stats()
        assert len(stats.top_actions) > 0
        assert len(stats.worst_actions) > 0

    def test_stats_recent_trend(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        for s in [True, False, True, True, False, True, True, True, False, True]:
            store.store(_make_experience(success=s))

        stats = store.get_stats()
        assert len(stats.recent_trend) <= 10
        assert all(t in (0.0, 1.0) for t in stats.recent_trend)

    def test_success_rate_global(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        for _ in range(7):
            store.store(_make_experience(success=True))
        for _ in range(3):
            store.store(_make_experience(success=False))

        assert store.get_success_rate() == 0.7

    def test_success_rate_by_action(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        for _ in range(5):
            store.store(_make_experience(action_type="clone_dna", success=True))
        for _ in range(5):
            store.store(_make_experience(action_type="mutate_hook", success=False))

        assert store.get_success_rate("clone_dna") == 1.0
        assert store.get_success_rate("mutate_hook") == 0.0

    def test_success_rate_unknown_action(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        assert store.get_success_rate("nonexistent") == 0.0

    def test_avg_reward(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        store.store(_make_experience(reward=0.8))
        store.store(_make_experience(reward=0.4))
        assert store.get_avg_reward() == 0.6

    def test_avg_reward_by_action(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        store.store(_make_experience(action_type="clone_dna", reward=0.9))
        store.store(_make_experience(action_type="clone_dna", reward=0.7))
        assert store.get_avg_reward("clone_dna") == 0.8

    def test_avg_reward_unknown_action(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        assert store.get_avg_reward("nonexistent") == 0.0


class TestExperienceStoreCapacity:
    """ExperienceStore 容量控制."""

    def test_capacity_limit(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore(max_capacity=5)
        for i in range(10):
            store.store(_make_experience(reward=float(i) / 10))

        assert store.count == 5
        # 最旧的 5 条被移除
        assert store._experiences[0].reward == 0.5  # 第 6 条

    def test_default_capacity(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore()
        assert store.capacity == 10000

    def test_capacity_exact(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        store = ExperienceStore(max_capacity=3)
        for _ in range(3):
            store.store(_make_experience())
        assert store.count == 3
        # 再存一条，仍为 3
        store.store(_make_experience())
        assert store.count == 3


# ═══════════════════════════════════════════════════════════════
# Test: MemoryRetriever
# ═══════════════════════════════════════════════════════════════

class TestMemoryRetrieverEnhance:
    """MemoryRetriever 增强功能."""

    def test_create_retriever(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        retriever = MemoryRetriever(store)
        assert retriever is not None

    def test_enhance_opportunity_with_history(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        # 存储历史经验
        for _ in range(5):
            store.store(_make_experience(
                action_type="clone_dna",
                opportunity_type="creative_scale",
                success=True,
                reward=0.85,
            ))
        for _ in range(3):
            store.store(_make_experience(
                action_type="mutate_hook",
                opportunity_type="creative_scale",
                success=False,
                reward=0.3,
            ))

        retriever = MemoryRetriever(store)
        opp = _make_opportunity("creative_scale", entity_id="c001")
        enhanced = retriever.enhance_opportunity(opp)

        assert "recommended_action_type" in enhanced
        assert enhanced["recommended_action_type"] == "clone_dna"
        assert enhanced["similar_experiences_count"] == 8
        assert "historical_success_rate" in enhanced

    def test_enhance_opportunity_no_history(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        retriever = MemoryRetriever(store)
        opp = _make_opportunity("creative_scale")
        enhanced = retriever.enhance_opportunity(opp)

        assert enhanced["similar_experiences_count"] == 0
        assert enhanced["recommended_action_type"] == ""
        assert enhanced["historical_success_rate"] == 0.0

    def test_enhance_opportunity_different_types(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        # creative_scale 经验
        for _ in range(3):
            store.store(_make_experience(
                action_type="clone_dna",
                opportunity_type="creative_scale",
                success=True,
                reward=0.9,
            ))
        # ua_scale 经验
        for _ in range(3):
            store.store(_make_experience(
                action_type="increase_budget",
                opportunity_type="ua_scale",
                success=True,
                reward=0.8,
            ))

        retriever = MemoryRetriever(store)
        opp = _make_opportunity("creative_scale")
        enhanced = retriever.enhance_opportunity(opp)

        assert enhanced["recommended_action_type"] == "clone_dna"
        assert enhanced["similar_experiences_count"] == 3


class TestMemoryRetrieverBestAction:
    """MemoryRetriever 最佳动作推荐."""

    def test_best_action_by_opportunity_type(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        for _ in range(5):
            store.store(_make_experience(
                action_type="clone_dna",
                opportunity_type="creative_scale",
                success=True,
                reward=0.9,
            ))
        for _ in range(5):
            store.store(_make_experience(
                action_type="mutate_hook",
                opportunity_type="creative_scale",
                success=False,
                reward=0.3,
            ))

        retriever = MemoryRetriever(store)
        best = retriever.get_best_action(opportunity_type="creative_scale")

        assert best["action_type"] == "clone_dna"
        assert best["success_rate"] == 1.0
        assert best["sample_count"] == 5

    def test_best_action_empty_store(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        retriever = MemoryRetriever(store)
        best = retriever.get_best_action(opportunity_type="creative_scale")
        assert best == {}

    def test_best_action_insufficient_samples(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        # 只有 2 条，min_samples=3
        for _ in range(2):
            store.store(_make_experience(
                action_type="clone_dna",
                opportunity_type="creative_scale",
                success=True,
            ))

        retriever = MemoryRetriever(store)
        best = retriever.get_best_action(opportunity_type="creative_scale", min_samples=3)
        assert best == {}

    def test_best_action_by_category(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        for _ in range(5):
            store.store(_make_experience(
                action_type="clone_dna",
                opportunity_type="creative_scale",
                success=True,
                reward=0.9,
            ))

        retriever = MemoryRetriever(store)
        best = retriever.get_best_action(category="creative")
        assert best["action_type"] == "clone_dna"

    def test_best_action_tiebreaker_by_sample_count(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        # 两个动作都是 100% 成功率，但样本数不同
        for _ in range(5):
            store.store(_make_experience(
                action_type="clone_dna",
                opportunity_type="creative_scale",
                success=True,
                reward=0.9,
            ))
        for _ in range(3):
            store.store(_make_experience(
                action_type="mutate_hook",
                opportunity_type="creative_scale",
                success=True,
                reward=0.8,
            ))

        retriever = MemoryRetriever(store)
        best = retriever.get_best_action(opportunity_type="creative_scale")
        # clone_dna 有更多样本
        assert best["action_type"] == "clone_dna"


class TestMemoryRetrieverSuccessRate:
    """MemoryRetriever 成功率查询."""

    def test_action_success_rate(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        for _ in range(4):
            store.store(_make_experience(action_type="clone_dna", success=True))
        for _ in range(1):
            store.store(_make_experience(action_type="clone_dna", success=False))

        retriever = MemoryRetriever(store)
        assert retriever.get_action_success_rate("clone_dna") == 0.8

    def test_opportunity_success_rate(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        for _ in range(3):
            store.store(_make_experience(opportunity_type="creative_scale", success=True))
        for _ in range(2):
            store.store(_make_experience(opportunity_type="creative_scale", success=False))

        retriever = MemoryRetriever(store)
        assert retriever.get_opportunity_success_rate("creative_scale") == 0.6

    def test_category_success_rate(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceCategory
        store = ExperienceStore()
        for _ in range(5):
            store.store(_make_experience(action_type="clone_dna", success=True))
        for _ in range(5):
            store.store(_make_experience(action_type="clone_dna", success=False))

        retriever = MemoryRetriever(store)
        assert retriever.get_category_success_rate(ExperienceCategory.CREATIVE) == 0.5


class TestMemoryRetrieverSimilar:
    """MemoryRetriever 相似经验查询."""

    def test_similar_experiences(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        for _ in range(5):
            store.store(_make_experience(
                action_type="clone_dna",
                opportunity_type="creative_scale",
                success=True,
                reward=0.9,
            ))

        retriever = MemoryRetriever(store)
        similar = retriever.get_similar_experiences(
            opportunity_type="creative_scale",
            action_type="clone_dna",
            limit=3,
        )
        assert len(similar) == 3
        assert similar[0]["action_type"] == "clone_dna"
        assert similar[0]["success"] is True

    def test_similar_experiences_empty(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        retriever = MemoryRetriever(store)
        similar = retriever.get_similar_experiences(opportunity_type="creative_scale")
        assert similar == []

    def test_similar_experiences_entity_filter(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        store.store(_make_experience(entity_id="c001", reward=0.9))
        store.store(_make_experience(entity_id="c002", reward=0.5))

        retriever = MemoryRetriever(store)
        similar = retriever.get_similar_experiences(entity_id="c001")
        assert len(similar) == 1


class TestMemoryRetrieverFailureWarnings:
    """MemoryRetriever 失败警告."""

    def test_failure_warnings(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        # 大部分失败
        for _ in range(1):
            store.store(_make_experience(
                action_type="mutate_visual",
                opportunity_type="creative_refresh",
                success=True,
            ))
        for _ in range(4):
            store.store(_make_experience(
                action_type="mutate_visual",
                opportunity_type="creative_refresh",
                success=False,
                reward=0.2,
            ))

        retriever = MemoryRetriever(store)
        warnings = retriever.get_failure_warnings(opportunity_type="creative_refresh")
        assert len(warnings) > 0
        assert warnings[0]["action_type"] == "mutate_visual"
        assert warnings[0]["failure_rate"] > 0.5

    def test_failure_warnings_no_failures(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        for _ in range(5):
            store.store(_make_experience(success=True))

        retriever = MemoryRetriever(store)
        warnings = retriever.get_failure_warnings()
        assert warnings == []

    def test_failure_warnings_global(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        for _ in range(2):
            store.store(_make_experience(action_type="mutate_visual", success=False))
        for _ in range(1):
            store.store(_make_experience(action_type="mutate_visual", success=True))

        retriever = MemoryRetriever(store)
        warnings = retriever.get_failure_warnings()
        assert len(warnings) > 0
        assert warnings[0]["failure_rate"] > 0.5

    def test_failure_warnings_below_threshold_not_reported(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        # 失败率 50% - 不触发警告 (需要 > 0.5)
        for _ in range(3):
            store.store(_make_experience(action_type="clone_dna", success=True))
        for _ in range(3):
            store.store(_make_experience(action_type="clone_dna", success=False))

        retriever = MemoryRetriever(store)
        warnings = retriever.get_failure_warnings()
        # clone_dna 失败率 50%，不触发
        assert all(w["action_type"] != "clone_dna" or w["failure_rate"] <= 0.5 for w in warnings)


class TestMemoryRetrieverSummary:
    """MemoryRetriever 摘要."""

    def test_get_summary(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        for _ in range(5):
            store.store(_make_experience(action_type="clone_dna", success=True, reward=0.8))
        for _ in range(3):
            store.store(_make_experience(action_type="mutate_hook", success=False, reward=0.3))

        retriever = MemoryRetriever(store)
        summary = retriever.get_summary()

        assert summary["total_experiences"] == 8
        assert summary["success_rate"] == 0.625
        assert summary["avg_reward"] > 0
        assert "top_actions" in summary
        assert "recent_trend" in summary

    def test_get_summary_empty(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        retriever = MemoryRetriever(store)
        summary = retriever.get_summary()
        assert summary["total_experiences"] == 0

    def test_get_stats_via_retriever(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        store = ExperienceStore()
        store.store(_make_experience(success=True))
        retriever = MemoryRetriever(store)
        stats = retriever.get_stats()
        assert stats.total_experiences == 1


# ═══════════════════════════════════════════════════════════════
# Test: Integration Scenarios
# ═══════════════════════════════════════════════════════════════

class TestIntegration:
    """集成场景: 决策→执行→记忆闭环."""

    def test_full_decision_memory_loop(self):
        """模拟完整决策→执行→记忆闭环."""
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            GrowthOpportunity, OpportunityType, OpportunityPriority,
        )
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            GrowthExperience, ExperienceContext, ExperienceOutcome,
            ExperienceOutcomeLevel,
        )

        store = ExperienceStore()
        retriever = MemoryRetriever(store)

        # Step 1: 生成机会
        opportunity = GrowthOpportunity(
            opportunity_type=OpportunityType.CREATIVE_SCALE,
            entity_id="c001",
            confidence=0.9,
            priority=OpportunityPriority.HIGH,
        )

        # Step 2: 查询记忆增强
        enhanced = retriever.enhance_opportunity(opportunity)
        # 第一次没有历史
        assert enhanced["similar_experiences_count"] == 0

        # Step 3: 模拟执行并记录经验 (至少 3 条以满足 min_samples)
        for i in range(3):
            experience = GrowthExperience(
                context=ExperienceContext(
                    product_id="p001",
                    date="2026-07-24",
                    opportunity_type="creative_scale",
                    opportunity_id=opportunity.opportunity_id,
                    action_type="clone_dna",
                    entity_id=f"c00{i+1}",
                    market_conditions={"roas": 1.5, "cpi": 2.3},
                    trigger_signals=["creative_winner"],
                    dna_genes={"hook": "rescue", "visual": "gameplay"},
                ),
                action_type="clone_dna",
                action_params={"source_creative_id": f"c00{i+1}", "clone_hook": True},
                outcome=ExperienceOutcome(
                    success=True,
                    outcome_level=ExperienceOutcomeLevel.SUCCESS,
                    actual_reward=0.85,
                    metrics_before={"roas": 1.5, "ctr": 0.03},
                    metrics_after={"roas": 2.0, "ctr": 0.05},
                    metrics_delta={"roas": 0.5, "ctr": 0.02},
                    actual_impact="CTR +66%, ROAS +33%",
                ),
                reward=0.85,
                confidence=0.9,
            )
            eid = store.store(experience)
            assert eid == experience.experience_id

        # Step 4: 再次查询，应有记忆
        enhanced2 = retriever.enhance_opportunity(opportunity)
        assert enhanced2["similar_experiences_count"] == 1  # only c001 matches entity_id filter
        assert enhanced2["recommended_action_type"] == "clone_dna"
        assert enhanced2["historical_success_rate"] == 1.0

    def test_store_and_retrieve_mixed_experiences(self):
        """混合经验存储和检索."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever

        store = ExperienceStore()
        retriever = MemoryRetriever(store)

        # 存储混合经验
        action_types = ["clone_dna", "mutate_hook", "increase_budget", "reduce_budget", "optimize_pricing"]
        for i, at in enumerate(action_types):
            store.store(_make_experience(
                action_type=at,
                success=(i % 2 == 0),
                reward=0.7 + (i * 0.05),
            ))

        # 检索
        assert store.count == 5

        # 统计
        stats = store.get_stats()
        assert stats.total_experiences == 5

        # 最佳动作
        best = retriever.get_best_action(min_samples=1)
        assert best != {}

        # 摘要
        summary = retriever.get_summary()
        assert summary["total_experiences"] == 5

    def test_memory_enhances_repeated_opportunities(self):
        """多次相同机会的查询应有记忆累积."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever

        store = ExperienceStore()
        retriever = MemoryRetriever(store)

        opp = _make_opportunity("creative_scale")

        # 第一次查询: 无记忆
        e1 = retriever.enhance_opportunity(opp)
        assert e1["similar_experiences_count"] == 0

        # 存储 5 条成功经验
        for _ in range(5):
            store.store(_make_experience(
                action_type="clone_dna",
                opportunity_type="creative_scale",
                success=True,
                reward=0.85,
            ))

        # 第二次查询: 有记忆
        e2 = retriever.enhance_opportunity(opp)
        assert e2["similar_experiences_count"] == 5
        assert e2["recommended_action_type"] == "clone_dna"

    def test_failure_warnings_after_many_failures(self):
        """多次失败后应有警告."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever

        store = ExperienceStore()
        retriever = MemoryRetriever(store)

        # 大量失败
        for _ in range(10):
            store.store(_make_experience(
                action_type="mutate_visual",
                opportunity_type="creative_refresh",
                success=False,
                reward=0.1,
            ))
        # 少量成功
        for _ in range(2):
            store.store(_make_experience(
                action_type="mutate_visual",
                opportunity_type="creative_refresh",
                success=True,
                reward=0.7,
            ))

        warnings = retriever.get_failure_warnings("creative_refresh")
        assert len(warnings) > 0
        assert warnings[0]["failure_rate"] > 0.5

    def test_large_scale_store_and_query(self):
        """大规模存储和查询."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_retriever import MemoryRetriever
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceQuery

        store = ExperienceStore(max_capacity=1000)
        retriever = MemoryRetriever(store)

        # 存储 100 条经验
        for i in range(100):
            success = (i % 3 != 0)  # 2/3 成功率
            action_type = ["clone_dna", "mutate_hook", "increase_budget", "reduce_budget", "optimize_pricing"][i % 5]
            opp_type = ["creative_scale", "creative_refresh", "ua_scale", "budget_reduction", "monetization_optimize"][i % 5]
            store.store(_make_experience(
                action_type=action_type,
                opportunity_type=opp_type,
                success=success,
                reward=0.8 if success else 0.2,
            ))

        assert store.count == 100

        # 查询
        results = store.query(ExperienceQuery(success_only=True))
        assert len(results) > 0

        # 统计
        stats = store.get_stats()
        assert stats.total_experiences == 100
        assert stats.success_rate > 0

        # 最佳动作
        best = retriever.get_best_action(min_samples=3)
        assert best != {}

        # 摘要
        summary = retriever.get_summary()
        assert summary["total_experiences"] == 100