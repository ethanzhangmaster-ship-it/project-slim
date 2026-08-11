"""E13.4.2 Growth Pattern Memory — 测试套件.

测试覆盖:
  - PatternMiningDimension / PatternQuality 枚举
  - PatternCondition / PatternAction / PatternPerformance 模型
  - PatternMemory 模型 (创建、评分、序列化、可执行判断、避免判断)
  - PatternQuery / PatternStats 模型
  - PatternMiner: 多维度挖掘、质量分配、排序、去重
  - PatternMiner: mine / mine_and_rank / mine_actionable / mine_avoid_patterns
  - PatternStore: store / store_batch / query / 便捷方法
  - PatternStore: get_best_pattern / enhance_decision / get_decision_warnings
  - PatternStore: 统计 / 去重更新
  - 边界条件: 空数据 / 少样本 / 大样本
  - 集成场景: 经验→挖掘→存储→决策增强闭环
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
    action_type: str = "clone_dna",
    entity_id: str = "c001",
    **kwargs,
) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceContext
    return ExperienceContext(
        product_id=product_id,
        date=date,
        opportunity_type=opportunity_type,
        action_type=action_type,
        entity_id=entity_id,
        **kwargs,
    )


def _make_outcome(
    success: bool = True,
    actual_reward: float = 0.85,
    metrics_delta: dict[str, float] | None = None,
    **kwargs,
) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
        ExperienceOutcome, ExperienceOutcomeLevel,
    )
    outcome_level = ExperienceOutcomeLevel.SUCCESS if success else ExperienceOutcomeLevel.FAILURE
    return ExperienceOutcome(
        success=success,
        outcome_level=outcome_level,
        actual_reward=actual_reward,
        metrics_delta=metrics_delta or {},
        **kwargs,
    )


def _make_experience(
    action_type: str = "clone_dna",
    opportunity_type: str = "creative_scale",
    entity_id: str = "c001",
    reward: float = 0.85,
    success: bool = True,
    audience_segment: str = "",
    dna_genes: dict[str, Any] | None = None,
    trigger_signals: list[str] | None = None,
    product_id: str = "p001",
    **kwargs,
) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.memory.models import GrowthExperience
    ctx = _make_context(
        product_id=product_id,
        opportunity_type=opportunity_type,
        action_type=action_type,
        entity_id=entity_id,
        audience_segment=audience_segment,
        dna_genes=dna_genes or {},
        trigger_signals=trigger_signals or [],
    )
    return GrowthExperience(
        context=ctx,
        action_type=action_type,
        action_params={"test": True},
        outcome=_make_outcome(success=success, actual_reward=reward),
        reward=reward,
        **kwargs,
    )


# ═══════════════════════════════════════════════════════════════
# Test: Enums
# ═══════════════════════════════════════════════════════════════

class TestPatternMiningDimension:
    def test_dimensions_exist(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternMiningDimension
        assert PatternMiningDimension.OPPORTUNITY_ACTION.value == "opportunity_action"
        assert PatternMiningDimension.OPPORTUNITY_CATEGORY.value == "opportunity_category"
        assert PatternMiningDimension.ACTION_AUDIENCE.value == "action_audience"
        assert PatternMiningDimension.ACTION_DNA.value == "action_dna"
        assert PatternMiningDimension.SIGNAL_ACTION.value == "signal_action"
        assert PatternMiningDimension.FULL_CONTEXT.value == "full_context"

    def test_six_dimensions(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternMiningDimension
        assert len(list(PatternMiningDimension)) == 6


class TestPatternQuality:
    def test_qualities_exist(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuality
        assert PatternQuality.STRONG.value == "strong"
        assert PatternQuality.RELIABLE.value == "reliable"
        assert PatternQuality.EMERGING.value == "emerging"
        assert PatternQuality.WEAK.value == "weak"
        assert PatternQuality.AVOID.value == "avoid"

    def test_five_qualities(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuality
        assert len(list(PatternQuality)) == 5


# ═══════════════════════════════════════════════════════════════
# Test: PatternCondition
# ═══════════════════════════════════════════════════════════════

class TestPatternCondition:
    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternCondition
        cond = PatternCondition()
        assert cond.opportunity_type == ""
        assert cond.action_type == ""
        assert cond.audience_segment == ""

    def test_full_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternCondition
        cond = PatternCondition(
            opportunity_type="creative_scale",
            action_type="clone_dna",
            category="creative",
            audience_segment="female_25_35",
            dna_genes={"hook": "rescue"},
            signal_types=["creative_winner"],
            product_category="merge",
        )
        assert cond.opportunity_type == "creative_scale"
        assert cond.dna_genes["hook"] == "rescue"

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternCondition
        cond = PatternCondition(
            opportunity_type="creative_scale",
            action_type="clone_dna",
            market_conditions={"roas": (0.5, 2.0)},
        )
        d = cond.to_dict()
        assert d["opportunity_type"] == "creative_scale"
        assert d["market_conditions"]["roas"] == [0.5, 2.0]

    def test_dimension_key_opportunity_action(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternCondition, PatternMiningDimension,
        )
        cond = PatternCondition(opportunity_type="creative_scale", action_type="clone_dna")
        key = cond.dimension_key(PatternMiningDimension.OPPORTUNITY_ACTION)
        assert key == "creative_scale|clone_dna"

    def test_dimension_key_opportunity_category(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternCondition, PatternMiningDimension,
        )
        cond = PatternCondition(opportunity_type="creative_scale", category="creative")
        key = cond.dimension_key(PatternMiningDimension.OPPORTUNITY_CATEGORY)
        assert key == "creative_scale|creative"

    def test_dimension_key_action_audience(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternCondition, PatternMiningDimension,
        )
        cond = PatternCondition(action_type="clone_dna", audience_segment="female_35")
        key = cond.dimension_key(PatternMiningDimension.ACTION_AUDIENCE)
        assert key == "clone_dna|female_35"

    def test_dimension_key_action_dna(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternCondition, PatternMiningDimension,
        )
        cond = PatternCondition(
            action_type="mutate_hook",
            dna_genes={"hook": "rescue", "visual": "gameplay"},
        )
        key = cond.dimension_key(PatternMiningDimension.ACTION_DNA)
        assert "mutate_hook" in key
        assert "hook=rescue" in key
        assert "visual=gameplay" in key

    def test_dimension_key_signal_action(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternCondition, PatternMiningDimension,
        )
        cond = PatternCondition(
            action_type="clone_dna",
            signal_types=["creative_winner", "scale_opportunity"],
        )
        key = cond.dimension_key(PatternMiningDimension.SIGNAL_ACTION)
        assert "creative_winner" in key
        assert "clone_dna" in key

    def test_dimension_key_full_context(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternCondition, PatternMiningDimension,
        )
        cond = PatternCondition(
            opportunity_type="creative_scale",
            action_type="clone_dna",
            category="creative",
            audience_segment="female_35",
            dna_genes={"hook": "rescue"},
        )
        key = cond.dimension_key(PatternMiningDimension.FULL_CONTEXT)
        assert "creative_scale" in key
        assert "clone_dna" in key
        assert "female_35" in key

    def test_dimension_key_empty(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternCondition, PatternMiningDimension,
        )
        cond = PatternCondition()
        key = cond.dimension_key(PatternMiningDimension.OPPORTUNITY_ACTION)
        assert key == "|"


# ═══════════════════════════════════════════════════════════════
# Test: PatternAction
# ═══════════════════════════════════════════════════════════════

class TestPatternAction:
    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternAction
        action = PatternAction()
        assert action.action_type == ""
        assert action.params_template == {}

    def test_full_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternAction
        action = PatternAction(
            action_type="clone_dna",
            params_template={"clone_hook": True, "preserve_psychological_mechanism": True},
            expected_impact="Clone winning DNA for scaling",
            approval_level="auto",
        )
        assert action.action_type == "clone_dna"
        assert action.params_template["clone_hook"] is True

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternAction
        action = PatternAction(action_type="clone_dna", params_template={"x": 1})
        d = action.to_dict()
        assert d["action_type"] == "clone_dna"
        assert d["params_template"]["x"] == 1


# ═══════════════════════════════════════════════════════════════
# Test: PatternPerformance
# ═══════════════════════════════════════════════════════════════

class TestPatternPerformance:
    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternPerformance
        perf = PatternPerformance()
        assert perf.samples == 0
        assert perf.success_rate == 0.0
        assert perf.quality.value == "weak"

    def test_full_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternPerformance, PatternQuality,
        )
        perf = PatternPerformance(
            samples=100,
            success_count=75,
            success_rate=0.75,
            avg_reward=0.82,
            avg_confidence=0.85,
            avg_metrics_delta={"roas": 0.3, "ctr": 0.02},
            std_reward=0.15,
            quality=PatternQuality.STRONG,
            first_seen="2026-01-01",
            last_seen="2026-07-24",
            trend=[1.0, 0.0, 1.0, 1.0],
        )
        assert perf.samples == 100
        assert perf.quality == PatternQuality.STRONG
        assert perf.avg_metrics_delta["roas"] == 0.3

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternPerformance, PatternQuality,
        )
        perf = PatternPerformance(
            samples=50,
            success_count=40,
            success_rate=0.8,
            avg_reward=0.75,
            avg_confidence=0.8,
            quality=PatternQuality.RELIABLE,
        )
        d = perf.to_dict()
        assert d["samples"] == 50
        assert d["success_rate"] == 0.8
        assert d["quality"] == "reliable"


# ═══════════════════════════════════════════════════════════════
# Test: PatternMemory
# ═══════════════════════════════════════════════════════════════

class TestPatternMemory:
    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternMemory
        pattern = PatternMemory()
        assert pattern.pattern_id != ""
        assert pattern.score == 0.0
        assert pattern.confidence == 0.0

    def test_compute_score_strong(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternPerformance, PatternQuality,
        )
        perf = PatternPerformance(
            samples=100,
            success_rate=0.8,
            avg_reward=0.85,
            quality=PatternQuality.STRONG,
        )
        pattern = PatternMemory(performance=perf)
        score = pattern.compute_score()
        assert score > 0.0
        assert pattern.confidence > 0.0

    def test_compute_score_weak(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternPerformance,
        )
        perf = PatternPerformance(samples=3, success_rate=0.2, avg_reward=0.1)
        pattern = PatternMemory(performance=perf)
        score = pattern.compute_score()
        assert score < 0.1  # 低样本+低成功率 = 低分

    def test_compute_score_zero_samples(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternMemory
        pattern = PatternMemory()
        assert pattern.compute_score() == 0.0

    def test_compute_score_higher_samples_higher_score(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternPerformance,
        )
        p1 = PatternMemory(performance=PatternPerformance(samples=10, success_rate=0.8, avg_reward=0.8))
        p2 = PatternMemory(performance=PatternPerformance(samples=100, success_rate=0.8, avg_reward=0.8))
        assert p2.compute_score() > p1.compute_score()

    def test_is_actionable(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternPerformance,
        )
        pattern = PatternMemory(performance=PatternPerformance(samples=10, success_rate=0.7))
        assert pattern.is_actionable(min_samples=5, min_success_rate=0.5) is True

    def test_is_not_actionable_low_samples(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternPerformance,
        )
        pattern = PatternMemory(performance=PatternPerformance(samples=3, success_rate=0.9))
        assert pattern.is_actionable(min_samples=5, min_success_rate=0.5) is False

    def test_is_not_actionable_low_success(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternPerformance,
        )
        pattern = PatternMemory(performance=PatternPerformance(samples=20, success_rate=0.3))
        assert pattern.is_actionable(min_samples=5, min_success_rate=0.5) is False

    def test_is_avoid_pattern(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternPerformance,
        )
        pattern = PatternMemory(performance=PatternPerformance(samples=10, success_rate=0.1))
        assert pattern.is_avoid_pattern(failure_threshold=0.7) is True

    def test_is_not_avoid_pattern(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternPerformance,
        )
        pattern = PatternMemory(performance=PatternPerformance(samples=10, success_rate=0.5))
        assert pattern.is_avoid_pattern(failure_threshold=0.7) is False

    def test_is_avoid_needs_min_samples(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternPerformance,
        )
        pattern = PatternMemory(performance=PatternPerformance(samples=1, success_rate=0.0))
        assert pattern.is_avoid_pattern() is False

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternPerformance, PatternQuality,
        )
        pattern = PatternMemory(
            performance=PatternPerformance(
                samples=50,
                success_rate=0.8,
                avg_reward=0.75,
                quality=PatternQuality.RELIABLE,
            ),
        )
        pattern.compute_score()
        d = pattern.to_dict()
        assert d["performance"]["samples"] == 50
        assert d["score"] > 0
        assert d["confidence"] > 0

    def test_unique_pattern_ids(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternMemory
        p1 = PatternMemory()
        p2 = PatternMemory()
        assert p1.pattern_id != p2.pattern_id

    def test_tags_and_source_ids(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternMemory
        pattern = PatternMemory(
            tags=["winner", "high_roas"],
            source_experience_ids=["e001", "e002", "e003"],
        )
        assert len(pattern.tags) == 2
        assert len(pattern.source_experience_ids) == 3


# ═══════════════════════════════════════════════════════════════
# Test: PatternQuery
# ═══════════════════════════════════════════════════════════════

class TestPatternQuery:
    def test_default_query(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuery
        q = PatternQuery()
        assert q.opportunity_types == []
        assert q.limit == 100
        assert q.sort_by == "score"

    def test_filtered_query(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuery
        q = PatternQuery(
            opportunity_types=["creative_scale"],
            action_types=["clone_dna"],
            min_samples=10,
            min_success_rate=0.6,
            actionable_only=True,
            limit=5,
        )
        assert q.actionable_only is True
        assert q.min_samples == 10

    def test_avoid_only(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuery
        q = PatternQuery(avoid_only=True)
        assert q.avoid_only is True


# ═══════════════════════════════════════════════════════════════
# Test: PatternStats
# ═══════════════════════════════════════════════════════════════

class TestPatternStats:
    def test_default_stats(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternStats
        stats = PatternStats()
        assert stats.total_patterns == 0
        assert stats.avg_score == 0.0

    def test_populated_stats(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternStats
        stats = PatternStats(
            total_patterns=50,
            total_actionable=30,
            total_avoid=5,
            by_quality={"strong": 10, "reliable": 20},
            avg_score=0.65,
            avg_samples=45.0,
        )
        assert stats.total_patterns == 50
        assert stats.total_avoid == 5
        assert stats.by_quality["strong"] == 10

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternStats
        stats = PatternStats(total_patterns=10, avg_score=0.7)
        d = stats.to_dict()
        assert d["total_patterns"] == 10
        assert d["avg_score"] == 0.7


# ═══════════════════════════════════════════════════════════════
# Test: PatternMiner
# ═══════════════════════════════════════════════════════════════

class TestPatternMinerMine:
    """PatternMiner 挖掘功能."""

    def test_mine_empty_store(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        store = ExperienceStore()
        miner = PatternMiner(store)
        patterns = miner.mine()
        assert patterns == []

    def test_mine_insufficient_samples(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        store = ExperienceStore()
        store.store(_make_experience(action_type="clone_dna", opportunity_type="creative_scale"))
        store.store(_make_experience(action_type="clone_dna", opportunity_type="creative_scale"))
        miner = PatternMiner(store)
        patterns = miner.mine(min_samples=3)
        assert patterns == []

    def test_mine_opportunity_action(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternMiningDimension
        store = ExperienceStore()
        for _ in range(5):
            store.store(_make_experience(action_type="clone_dna", opportunity_type="creative_scale", success=True, reward=0.85))
        for _ in range(3):
            store.store(_make_experience(action_type="mutate_hook", opportunity_type="creative_refresh", success=False, reward=0.3))

        miner = PatternMiner(store)
        patterns = miner.mine(dimensions=[PatternMiningDimension.OPPORTUNITY_ACTION], min_samples=3)
        assert len(patterns) == 2  # clone_dna × creative_scale, mutate_hook × creative_refresh

        # 检查第一个模式 (clone_dna 应该分数更高)
        assert patterns[0].condition.opportunity_type == "creative_scale"
        assert patterns[0].action.action_type == "clone_dna"
        assert patterns[0].performance.success_rate == 1.0

    def test_mine_action_audience(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternMiningDimension
        store = ExperienceStore()
        for _ in range(5):
            store.store(_make_experience(
                action_type="clone_dna", opportunity_type="creative_scale",
                audience_segment="female_25_35", success=True, reward=0.85,
            ))
        for _ in range(3):
            store.store(_make_experience(
                action_type="clone_dna", opportunity_type="creative_scale",
                audience_segment="male_18_24", success=False, reward=0.2,
            ))

        miner = PatternMiner(store)
        patterns = miner.mine(dimensions=[PatternMiningDimension.ACTION_AUDIENCE], min_samples=3)
        assert len(patterns) == 2
        assert patterns[0].condition.audience_segment == "female_25_35"

    def test_mine_action_dna(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternMiningDimension
        store = ExperienceStore()
        for _ in range(5):
            store.store(_make_experience(
                action_type="mutate_hook", opportunity_type="creative_refresh",
                dna_genes={"hook": "rescue", "visual": "gameplay"},
                success=True, reward=0.9,
            ))

        miner = PatternMiner(store)
        patterns = miner.mine(dimensions=[PatternMiningDimension.ACTION_DNA], min_samples=3)
        assert len(patterns) >= 1
        assert patterns[0].condition.dna_genes["hook"] == "rescue"

    def test_mine_signal_action(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternMiningDimension
        store = ExperienceStore()
        for _ in range(5):
            store.store(_make_experience(
                action_type="increase_budget", opportunity_type="ua_scale",
                trigger_signals=["scale_opportunity"],
                success=True, reward=0.8,
            ))

        miner = PatternMiner(store)
        patterns = miner.mine(dimensions=[PatternMiningDimension.SIGNAL_ACTION], min_samples=3)
        assert len(patterns) >= 1
        assert "scale_opportunity" in patterns[0].condition.signal_types

    def test_mine_multiple_dimensions(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        store = ExperienceStore()
        for _ in range(5):
            store.store(_make_experience(action_type="clone_dna", opportunity_type="creative_scale", success=True, reward=0.8))

        miner = PatternMiner(store)
        patterns = miner.mine(min_samples=3)
        # 多个维度可能产生相同模式，但去重后只保留一个
        assert len(patterns) >= 1

    def test_mine_and_rank(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        store = ExperienceStore()
        for _ in range(10):
            store.store(_make_experience(action_type="clone_dna", opportunity_type="creative_scale", success=True, reward=0.9))
        for _ in range(5):
            store.store(_make_experience(action_type="mutate_hook", opportunity_type="creative_refresh", success=False, reward=0.2))

        miner = PatternMiner(store)
        patterns = miner.mine_and_rank(top_n=1)
        assert len(patterns) == 1
        assert patterns[0].action.action_type == "clone_dna"

    def test_mine_actionable(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        store = ExperienceStore()
        # 可执行: 5+ 样本, 高成功率
        for _ in range(10):
            store.store(_make_experience(action_type="clone_dna", opportunity_type="creative_scale", success=True, reward=0.9))
        # 不可执行: 低成功率
        for _ in range(5):
            store.store(_make_experience(action_type="mutate_visual", opportunity_type="creative_refresh", success=False, reward=0.1))

        miner = PatternMiner(store)
        patterns = miner.mine_actionable(min_samples=5, min_success_rate=0.5)
        assert len(patterns) >= 1
        assert all(p.is_actionable(5, 0.5) for p in patterns)

    def test_mine_avoid_patterns(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        store = ExperienceStore()
        for _ in range(10):
            store.store(_make_experience(
                action_type="increase_budget", opportunity_type="ua_scale",
                success=False, reward=0.05,
            ))

        miner = PatternMiner(store)
        patterns = miner.mine_avoid_patterns(min_samples=3, failure_threshold=0.5)
        assert len(patterns) >= 1
        assert all(p.is_avoid_pattern() for p in patterns)

    def test_mine_with_custom_experiences(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternMiningDimension
        store = ExperienceStore()
        exps = [_make_experience(action_type="clone_dna", opportunity_type="creative_scale", success=True) for _ in range(5)]

        miner = PatternMiner(store)
        patterns = miner.mine(
            dimensions=[PatternMiningDimension.OPPORTUNITY_ACTION],
            min_samples=3,
            experiences=exps,
        )
        assert len(patterns) == 1

    def test_mine_quality_assignment_strong(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternMiningDimension
        store = ExperienceStore()
        for _ in range(50):
            store.store(_make_experience(action_type="clone_dna", opportunity_type="creative_scale", success=True, reward=0.9))

        miner = PatternMiner(store)
        patterns = miner.mine(dimensions=[PatternMiningDimension.OPPORTUNITY_ACTION], min_samples=3)
        assert len(patterns) == 1
        assert patterns[0].performance.quality.value == "strong"

    def test_mine_quality_assignment_avoid(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternMiningDimension
        store = ExperienceStore()
        for _ in range(10):
            store.store(_make_experience(action_type="mutate_visual", opportunity_type="creative_refresh", success=False, reward=0.05))

        miner = PatternMiner(store)
        patterns = miner.mine(dimensions=[PatternMiningDimension.OPPORTUNITY_ACTION], min_samples=3)
        assert len(patterns) == 1
        assert patterns[0].performance.quality.value == "avoid"

    def test_mine_deduplication(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        store = ExperienceStore()
        for _ in range(5):
            store.store(_make_experience(action_type="clone_dna", opportunity_type="creative_scale", success=True, reward=0.8))

        miner = PatternMiner(store)
        # 多维度挖掘可能产生重复，去重后只保留一个
        patterns = miner.mine(min_samples=3)
        # 检查没有重复的 opportunity_type + action_type
        keys = [f"{p.condition.opportunity_type}|{p.action.action_type}" for p in patterns]
        assert len(keys) == len(set(keys))


# ═══════════════════════════════════════════════════════════════
# Test: PatternStore
# ═══════════════════════════════════════════════════════════════

class TestPatternStoreStore:
    """PatternStore 存储功能."""

    def test_create_store(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        store = PatternStore()
        assert store.count == 0

    def test_store_single(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternCondition, PatternAction, PatternPerformance,
        )
        store = PatternStore()
        pattern = PatternMemory(
            condition=PatternCondition(opportunity_type="creative_scale", action_type="clone_dna"),
            action=PatternAction(action_type="clone_dna"),
            performance=PatternPerformance(samples=10, success_rate=0.8, avg_reward=0.75),
        )
        pattern.compute_score()
        pid = store.store(pattern)
        assert pid == pattern.pattern_id
        assert store.count == 1

    def test_store_batch(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternCondition, PatternAction, PatternPerformance,
        )
        store = PatternStore()
        patterns = []
        for i in range(5):
            p = PatternMemory(
                condition=PatternCondition(opportunity_type=f"type_{i}", action_type=f"action_{i}"),
                action=PatternAction(action_type=f"action_{i}"),
                performance=PatternPerformance(samples=10, success_rate=0.8, avg_reward=0.75),
            )
            p.compute_score()
            patterns.append(p)

        ids = store.store_batch(patterns)
        assert len(ids) == 5
        assert store.count == 5

    def test_store_update_existing(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternCondition, PatternAction, PatternPerformance,
        )
        store = PatternStore()
        p1 = PatternMemory(
            condition=PatternCondition(opportunity_type="creative_scale", action_type="clone_dna"),
            action=PatternAction(action_type="clone_dna"),
            performance=PatternPerformance(samples=10, success_rate=0.8, avg_reward=0.75),
        )
        p1.compute_score()
        store.store(p1)

        p2 = PatternMemory(
            condition=PatternCondition(opportunity_type="creative_scale", action_type="clone_dna"),
            action=PatternAction(action_type="clone_dna"),
            performance=PatternPerformance(samples=50, success_rate=0.9, avg_reward=0.85),
        )
        p2.compute_score()
        store.store(p2)

        # 应该更新而非新增
        assert store.count == 1
        assert store.get_all()[0].performance.samples == 50


class TestPatternStoreQuery:
    """PatternStore 查询功能."""

    def _setup_store(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternCondition, PatternAction, PatternPerformance, PatternQuality,
        )
        store = PatternStore()
        for i, (opp, act, samples, sr, reward, quality) in enumerate([
            ("creative_scale", "clone_dna", 50, 0.8, 0.85, PatternQuality.STRONG),
            ("creative_refresh", "mutate_hook", 30, 0.7, 0.75, PatternQuality.RELIABLE),
            ("creative_refresh", "mutate_visual", 10, 0.2, 0.15, PatternQuality.AVOID),
            ("ua_scale", "increase_budget", 40, 0.75, 0.8, PatternQuality.STRONG),
            ("budget_reduction", "reduce_budget", 20, 0.6, 0.65, PatternQuality.RELIABLE),
        ]):
            p = PatternMemory(
                condition=PatternCondition(opportunity_type=opp, action_type=act, category="creative" if "creative" in opp else "ua"),
                action=PatternAction(action_type=act),
                performance=PatternPerformance(samples=samples, success_rate=sr, avg_reward=reward, quality=quality),
            )
            p.compute_score()
            store.store(p)
        return store

    def test_query_by_opportunity_type(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuery
        store = self._setup_store()
        results = store.query(PatternQuery(opportunity_types=["creative_scale"]))
        assert len(results) == 1
        assert results[0].condition.opportunity_type == "creative_scale"

    def test_query_by_action_type(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuery
        store = self._setup_store()
        results = store.query(PatternQuery(action_types=["clone_dna"]))
        assert len(results) == 1
        assert results[0].action.action_type == "clone_dna"

    def test_query_by_category(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuery
        store = self._setup_store()
        results = store.query(PatternQuery(categories=["creative"]))
        assert len(results) == 3

    def test_query_min_samples(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuery
        store = self._setup_store()
        results = store.query(PatternQuery(min_samples=30))
        assert len(results) == 3
        assert all(p.performance.samples >= 30 for p in results)

    def test_query_min_success_rate(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuery
        store = self._setup_store()
        results = store.query(PatternQuery(min_success_rate=0.7))
        assert len(results) == 3

    def test_query_min_score(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuery
        store = self._setup_store()
        results = store.query(PatternQuery(min_score=0.1))
        assert len(results) >= 1

    def test_query_actionable_only(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuery
        store = self._setup_store()
        results = store.query(PatternQuery(actionable_only=True))
        assert len(results) >= 3
        assert all(p.is_actionable() for p in results)

    def test_query_avoid_only(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuery
        store = self._setup_store()
        results = store.query(PatternQuery(avoid_only=True))
        assert len(results) == 1
        assert results[0].condition.action_type == "mutate_visual"

    def test_query_quality_levels(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuery
        store = self._setup_store()
        results = store.query(PatternQuery(quality_levels=["strong"]))
        assert len(results) == 2

    def test_query_sort_by_score(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuery
        store = self._setup_store()
        results = store.query(PatternQuery(sort_by="score", sort_desc=True))
        assert results[0].score >= results[-1].score

    def test_query_limit(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuery
        store = self._setup_store()
        results = store.query(PatternQuery(limit=2))
        assert len(results) == 2

    def test_query_empty_store(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuery
        store = PatternStore()
        results = store.query(PatternQuery())
        assert results == []

    def test_query_dna_match(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternCondition, PatternAction, PatternPerformance, PatternQuery,
        )
        store = PatternStore()
        p = PatternMemory(
            condition=PatternCondition(
                opportunity_type="creative_refresh",
                action_type="mutate_hook",
                dna_genes={"hook": "rescue", "visual": "gameplay"},
            ),
            action=PatternAction(action_type="mutate_hook"),
            performance=PatternPerformance(samples=10, success_rate=0.8, avg_reward=0.75),
        )
        p.compute_score()
        store.store(p)

        # 完全匹配
        results = store.query(PatternQuery(dna_genes={"hook": "rescue"}))
        assert len(results) == 1

        # 不匹配
        results = store.query(PatternQuery(dna_genes={"hook": "nonexistent"}))
        assert len(results) == 0


class TestPatternStoreConvenience:
    """PatternStore 便捷方法."""

    def _setup_store(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternCondition, PatternAction, PatternPerformance, PatternQuality,
        )
        store = PatternStore()
        for opp, act, samples, sr, reward, quality in [
            ("creative_scale", "clone_dna", 50, 0.8, 0.85, PatternQuality.STRONG),
            ("creative_refresh", "mutate_hook", 30, 0.7, 0.75, PatternQuality.RELIABLE),
            ("ua_scale", "increase_budget", 40, 0.75, 0.8, PatternQuality.STRONG),
        ]:
            p = PatternMemory(
                condition=PatternCondition(opportunity_type=opp, action_type=act),
                action=PatternAction(action_type=act),
                performance=PatternPerformance(samples=samples, success_rate=sr, avg_reward=reward, quality=quality),
            )
            p.compute_score()
            store.store(p)
        return store

    def test_get_best_pattern(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternCondition
        store = self._setup_store()
        cond = PatternCondition(opportunity_type="creative_scale")
        best = store.get_best_pattern(condition=cond)
        assert best is not None
        assert best.action.action_type == "clone_dna"

    def test_get_best_pattern_shortcut(self):
        store = self._setup_store()
        best = store.get_best_pattern(opportunity_type="creative_scale")
        assert best is not None
        assert best.condition.opportunity_type == "creative_scale"

    def test_get_best_pattern_none(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        store = PatternStore()
        best = store.get_best_pattern(opportunity_type="nonexistent")
        assert best is None

    def test_get_avoid_patterns(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternCondition, PatternAction, PatternPerformance, PatternQuality,
        )
        store = PatternStore()
        p = PatternMemory(
            condition=PatternCondition(opportunity_type="creative_refresh", action_type="mutate_visual"),
            action=PatternAction(action_type="mutate_visual"),
            performance=PatternPerformance(samples=10, success_rate=0.1, avg_reward=0.05, quality=PatternQuality.AVOID),
        )
        p.compute_score()
        store.store(p)

        avoid = store.get_avoid_patterns()
        assert len(avoid) == 1

    def test_get_by_opportunity_type(self):
        store = self._setup_store()
        results = store.get_by_opportunity_type("creative_scale")
        assert len(results) == 1

    def test_get_by_action_type(self):
        store = self._setup_store()
        results = store.get_by_action_type("clone_dna")
        assert len(results) == 1

    def test_get_top_patterns(self):
        store = self._setup_store()
        results = store.get_top_patterns(2)
        assert len(results) == 2

    def test_get_actionable_patterns(self):
        store = self._setup_store()
        results = store.get_actionable_patterns()
        assert len(results) >= 3

    def test_get_all(self):
        store = self._setup_store()
        assert len(store.get_all()) == 3


class TestPatternStoreDecisionEnhancement:
    """PatternStore 决策增强."""

    def _setup_store(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternCondition, PatternAction, PatternPerformance, PatternQuality,
        )
        store = PatternStore()
        p = PatternMemory(
            condition=PatternCondition(opportunity_type="creative_scale", action_type="clone_dna", category="creative"),
            action=PatternAction(action_type="clone_dna"),
            performance=PatternPerformance(samples=50, success_rate=0.8, avg_reward=0.85, quality=PatternQuality.STRONG),
        )
        p.compute_score()
        store.store(p)
        return store

    def test_enhance_decision_with_pattern(self):
        store = self._setup_store()
        enhanced = store.enhance_decision(
            opportunity_type="creative_scale",
            action_type="clone_dna",
            base_confidence=0.6,
        )
        assert enhanced["enhanced_confidence"] > 0.6
        assert enhanced["matched_pattern"] is not None
        assert enhanced["historical_success_rate"] == 0.8
        assert enhanced["samples"] == 50

    def test_enhance_decision_no_pattern(self):
        store = self._setup_store()
        enhanced = store.enhance_decision(
            opportunity_type="nonexistent",
            action_type="nonexistent",
            base_confidence=0.6,
        )
        assert enhanced["enhanced_confidence"] == 0.6
        assert enhanced["matched_pattern"] is None
        assert enhanced["recommendation"] == "no_matching_pattern"

    def test_enhance_decision_no_base_confidence(self):
        store = self._setup_store()
        enhanced = store.enhance_decision(
            opportunity_type="creative_scale",
            action_type="clone_dna",
        )
        assert enhanced["enhanced_confidence"] > 0
        assert enhanced["pattern_confidence"] > 0

    def test_enhance_decision_recommendation_levels(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternCondition, PatternAction, PatternPerformance, PatternQuality,
        )
        store = PatternStore()

        # 强推荐: 高成功率
        p1 = PatternMemory(
            condition=PatternCondition(opportunity_type="creative_scale", action_type="clone_dna"),
            action=PatternAction(action_type="clone_dna"),
            performance=PatternPerformance(samples=100, success_rate=0.9, avg_reward=0.9, quality=PatternQuality.STRONG),
        )
        p1.compute_score()
        store.store(p1)

        enhanced = store.enhance_decision("creative_scale", "clone_dna", 0.7)
        assert enhanced["recommendation"] == "strong_recommend"

    def test_get_decision_warnings(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternCondition, PatternAction, PatternPerformance, PatternQuality,
        )
        store = PatternStore()
        p = PatternMemory(
            condition=PatternCondition(opportunity_type="creative_refresh", action_type="mutate_visual"),
            action=PatternAction(action_type="mutate_visual"),
            performance=PatternPerformance(samples=10, success_rate=0.1, avg_reward=0.05, quality=PatternQuality.AVOID),
        )
        p.compute_score()
        store.store(p)

        warnings = store.get_decision_warnings("creative_refresh", "mutate_visual")
        assert len(warnings) == 1
        assert warnings[0]["failure_rate"] > 0.5

    def test_get_decision_warnings_none(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        store = PatternStore()
        warnings = store.get_decision_warnings("creative_scale")
        assert warnings == []


class TestPatternStoreStats:
    """PatternStore 统计功能."""

    def test_stats_empty(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        store = PatternStore()
        stats = store.get_stats()
        assert stats.total_patterns == 0

    def test_stats_populated(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternCondition, PatternAction, PatternPerformance, PatternQuality,
        )
        store = PatternStore()
        for opp, act, samples, sr, reward, quality in [
            ("creative_scale", "clone_dna", 50, 0.8, 0.85, PatternQuality.STRONG),
            ("creative_refresh", "mutate_hook", 30, 0.7, 0.75, PatternQuality.RELIABLE),
            ("creative_refresh", "mutate_visual", 10, 0.1, 0.05, PatternQuality.AVOID),
        ]:
            p = PatternMemory(
                condition=PatternCondition(opportunity_type=opp, action_type=act),
                action=PatternAction(action_type=act),
                performance=PatternPerformance(samples=samples, success_rate=sr, avg_reward=reward, quality=quality),
            )
            p.compute_score()
            store.store(p)

        stats = store.get_stats()
        assert stats.total_patterns == 3
        assert stats.total_actionable == 2
        assert stats.total_avoid == 1
        assert "strong" in stats.by_quality
        assert stats.avg_score > 0
        assert len(stats.top_patterns) > 0
        assert len(stats.avoid_patterns) == 1

    def test_stats_clear(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternMemory, PatternPerformance,
        )
        store = PatternStore()
        p = PatternMemory(performance=PatternPerformance(samples=10, success_rate=0.8, avg_reward=0.75))
        p.compute_score()
        store.store(p)
        store.clear()
        assert store.count == 0


# ═══════════════════════════════════════════════════════════════
# Test: Integration Scenarios
# ═══════════════════════════════════════════════════════════════

class TestIntegration:
    """集成场景: 经验→挖掘→存储→决策增强."""

    def test_full_pattern_mining_pipeline(self):
        """完整挖掘流水线."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternMiningDimension

        # Step 1: 创建经验库
        exp_store = ExperienceStore()
        # clone_dna × creative_scale: 高成功率
        for _ in range(20):
            exp_store.store(_make_experience(
                action_type="clone_dna", opportunity_type="creative_scale",
                success=True, reward=0.85, audience_segment="female_25_35",
            ))
        # mutate_hook × creative_refresh: 中等成功率
        for _ in range(10):
            exp_store.store(_make_experience(
                action_type="mutate_hook", opportunity_type="creative_refresh",
                success=True, reward=0.75,
            ))
        for _ in range(5):
            exp_store.store(_make_experience(
                action_type="mutate_hook", opportunity_type="creative_refresh",
                success=False, reward=0.2,
            ))
        # increase_budget × ua_scale: 低成功率
        for _ in range(10):
            exp_store.store(_make_experience(
                action_type="increase_budget", opportunity_type="ua_scale",
                success=False, reward=0.1,
            ))

        # Step 2: 挖掘模式
        miner = PatternMiner(exp_store)
        patterns = miner.mine(
            dimensions=[PatternMiningDimension.OPPORTUNITY_ACTION],
            min_samples=3,
        )

        # Step 3: 存储到 PatternStore
        pattern_store = PatternStore()
        pattern_store.store_batch(patterns)

        # Step 4: 验证
        assert pattern_store.count >= 3

        # clone_dna 应该是最佳模式
        best = pattern_store.get_best_pattern(opportunity_type="creative_scale")
        assert best is not None
        assert best.action.action_type == "clone_dna"
        assert best.performance.success_rate == 1.0

        # increase_budget 应该是 avoid pattern
        avoid = pattern_store.get_avoid_patterns()
        assert len(avoid) >= 1

    def test_decision_enhancement_loop(self):
        """决策增强闭环."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            GrowthOpportunity, OpportunityType, OpportunityPriority,
        )

        # Step 1: 积累经验 (100 样本确保 pattern_confidence >= 0.92)
        exp_store = ExperienceStore()
        for _ in range(100):
            exp_store.store(_make_experience(
                action_type="clone_dna", opportunity_type="creative_scale",
                success=True, reward=0.82,
            ))

        # Step 2: 挖掘模式
        miner = PatternMiner(exp_store)
        patterns = miner.mine(min_samples=5)

        # Step 3: 存储模式
        pattern_store = PatternStore()
        pattern_store.store_batch(patterns)

        # Step 4: 模拟新机会
        opportunity = GrowthOpportunity(
            opportunity_type=OpportunityType.CREATIVE_SCALE,
            entity_id="c001",
            confidence=0.62,
            priority=OpportunityPriority.HIGH,
        )

        # Step 5: 用模式记忆增强决策
        enhanced = pattern_store.enhance_decision(
            opportunity_type="creative_scale",
            action_type="clone_dna",
            base_confidence=opportunity.confidence,
        )

        assert enhanced["enhanced_confidence"] > 0.62
        assert enhanced["historical_success_rate"] == 1.0
        assert enhanced["samples"] == 100
        assert enhanced["recommendation"] == "strong_recommend"

    def test_mine_then_re_mine_with_more_data(self):
        """更多数据后重新挖掘，模式应更新."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternMiningDimension

        exp_store = ExperienceStore()
        pattern_store = PatternStore()

        # 第一批: 5 条经验
        for _ in range(5):
            exp_store.store(_make_experience(
                action_type="clone_dna", opportunity_type="creative_scale",
                success=True, reward=0.8,
            ))

        miner = PatternMiner(exp_store)
        patterns1 = miner.mine(dimensions=[PatternMiningDimension.OPPORTUNITY_ACTION], min_samples=3)
        pattern_store.store_batch(patterns1)
        samples1 = pattern_store.get_best_pattern(opportunity_type="creative_scale").performance.samples

        # 第二批: 再加 20 条经验
        for _ in range(20):
            exp_store.store(_make_experience(
                action_type="clone_dna", opportunity_type="creative_scale",
                success=True, reward=0.85,
            ))

        patterns2 = miner.mine(dimensions=[PatternMiningDimension.OPPORTUNITY_ACTION], min_samples=3)
        pattern_store.store_batch(patterns2)
        samples2 = pattern_store.get_best_pattern(opportunity_type="creative_scale").performance.samples

        assert samples2 > samples1

    def test_large_scale_mining(self):
        """大规模挖掘."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_miner import PatternMiner
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore

        exp_store = ExperienceStore()
        action_types = ["clone_dna", "mutate_hook", "mutate_visual", "increase_budget", "reduce_budget"]
        opp_types = ["creative_scale", "creative_refresh", "ua_scale", "budget_reduction"]

        for i in range(200):
            at = action_types[i % len(action_types)]
            ot = opp_types[i % len(opp_types)]
            success = (i % 4 != 0)  # 75% 成功率
            exp_store.store(_make_experience(
                action_type=at,
                opportunity_type=ot,
                success=success,
                reward=0.8 if success else 0.2,
            ))

        miner = PatternMiner(exp_store)
        patterns = miner.mine(min_samples=3)

        pattern_store = PatternStore()
        pattern_store.store_batch(patterns)

        assert pattern_store.count > 0
        stats = pattern_store.get_stats()
        assert stats.total_patterns > 0
        assert stats.avg_score > 0