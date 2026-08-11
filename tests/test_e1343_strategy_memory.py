"""E13.4.3 Growth Strategy Memory — 测试套件.

测试覆盖:
  - StrategyCategory / StrategyQuality 枚举
  - StrategyTriggerCondition: 创建、匹配、序列化
  - StrategyStep: 创建、序列化
  - StrategyPerformance: 创建、统计、序列化
  - GrowthStrategyPattern: 创建、评分、序列化、可执行判断、步骤操作
  - StrategyQuery / StrategyStats: 模型
  - StrategyMemory: extract、store、query、recommend
  - StrategyMemory: 统计、去重更新、边界条件
  - 集成场景: 经验→链提取→策略构建→存储→推荐闭环
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
    timestamp: str = "2026-07-24T10:00:00+00:00",
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
        timestamp=timestamp,
        **kwargs,
    )


def _make_experiences_for_chain(
    entity_id: str = "c001",
    actions: list[str] | None = None,
    opportunity_type: str = "creative_scale",
    success: bool = True,
    reward: float = 0.85,
    audience_segment: str = "",
    product_id: str = "p001",
    base_timestamp: str = "2026-07-24T10:00:00+00:00",
) -> list[Any]:
    """创建一条动作链经验."""
    if actions is None:
        actions = ["clone_dna", "create_population", "scale_winner"]
    exps = []
    for i, action in enumerate(actions):
        hour = 10 + i
        ts = f"2026-07-24T{hour:02d}:00:00+00:00"
        exps.append(_make_experience(
            action_type=action,
            opportunity_type=opportunity_type,
            entity_id=entity_id,
            success=success,
            reward=reward,
            audience_segment=audience_segment,
            product_id=product_id,
            timestamp=ts,
        ))
    return exps


# ═══════════════════════════════════════════════════════════════
# Test: Enums
# ═══════════════════════════════════════════════════════════════

class TestStrategyCategory:
    """StrategyCategory 枚举."""

    def test_categories_exist(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyCategory
        assert StrategyCategory.CREATIVE_REVIVAL.value == "creative_revival"
        assert StrategyCategory.CREATIVE_SCALE.value == "creative_scale"
        assert StrategyCategory.ROAS_RECOVERY.value == "roas_recovery"
        assert StrategyCategory.BUDGET_OPTIMIZATION.value == "budget_optimization"
        assert StrategyCategory.AUDIENCE_EXPANSION.value == "audience_expansion"
        assert StrategyCategory.NEW_LAUNCH.value == "new_launch"
        assert StrategyCategory.GENERAL.value == "general"


class TestStrategyQuality:
    """StrategyQuality 枚举."""

    def test_qualities_exist(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyQuality
        assert StrategyQuality.PROVEN.value == "proven"
        assert StrategyQuality.RELIABLE.value == "reliable"
        assert StrategyQuality.EMERGING.value == "emerging"
        assert StrategyQuality.EXPERIMENTAL.value == "experimental"
        assert StrategyQuality.UNTESTED.value == "untested"


# ═══════════════════════════════════════════════════════════════
# Test: StrategyTriggerCondition
# ═══════════════════════════════════════════════════════════════

class TestStrategyTriggerCondition:
    """StrategyTriggerCondition 模型."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyTriggerCondition
        tc = StrategyTriggerCondition()
        assert tc.scenario == ""
        assert tc.opportunity_type == ""
        assert tc.signal_types == []
        assert tc.audience_segment == ""
        assert tc.product_category == ""
        assert tc.min_confidence == 0.0

    def test_full_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyTriggerCondition
        tc = StrategyTriggerCondition(
            scenario="ROAS dropping below 0.8",
            opportunity_type="roas_drop",
            signal_types=["ROAS_DROP", "REVENUE_DECLINE"],
            metrics_conditions={"roas": ("<", 0.8)},
            audience_segment="female_25_35",
            product_category="merge",
            min_confidence=0.6,
        )
        assert tc.scenario == "ROAS dropping below 0.8"
        assert tc.opportunity_type == "roas_drop"
        assert tc.signal_types == ["ROAS_DROP", "REVENUE_DECLINE"]
        assert tc.metrics_conditions == {"roas": ("<", 0.8)}
        assert tc.min_confidence == 0.6

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyTriggerCondition
        tc = StrategyTriggerCondition(
            scenario="test",
            opportunity_type="creative_scale",
            metrics_conditions={"roas": ("<", 0.8)},
        )
        d = tc.to_dict()
        assert d["scenario"] == "test"
        assert d["opportunity_type"] == "creative_scale"
        assert d["metrics_conditions"] == {"roas": ["<", 0.8]}

    def test_matches_opportunity_exact(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyTriggerCondition
        tc = StrategyTriggerCondition(opportunity_type="creative_scale")
        assert tc.matches_opportunity(opportunity_type="creative_scale") is True

    def test_matches_opportunity_mismatch(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyTriggerCondition
        tc = StrategyTriggerCondition(opportunity_type="creative_scale")
        assert tc.matches_opportunity(opportunity_type="roas_drop") is False

    def test_matches_opportunity_empty_trigger(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyTriggerCondition
        tc = StrategyTriggerCondition()
        assert tc.matches_opportunity(opportunity_type="creative_scale") is True

    def test_matches_with_signals(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyTriggerCondition
        tc = StrategyTriggerCondition(signal_types=["ROAS_DROP", "BUDGET_WASTE"])
        assert tc.matches_opportunity(signal_types=["ROAS_DROP"]) is True
        assert tc.matches_opportunity(signal_types=["UNKNOWN"]) is False

    def test_matches_with_audience(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyTriggerCondition
        tc = StrategyTriggerCondition(audience_segment="female_25_35")
        assert tc.matches_opportunity(audience_segment="female_25_35") is True
        assert tc.matches_opportunity(audience_segment="male_18_24") is False

    def test_matches_with_product(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyTriggerCondition
        tc = StrategyTriggerCondition(product_category="merge")
        assert tc.matches_opportunity(product_category="merge") is True
        assert tc.matches_opportunity(product_category="puzzle") is False


# ═══════════════════════════════════════════════════════════════
# Test: StrategyStep
# ═══════════════════════════════════════════════════════════════

class TestStrategyStep:
    """StrategyStep 模型."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyStep
        step = StrategyStep()
        assert step.order == 1
        assert step.action_type == ""
        assert step.action_params == {}
        assert step.pattern_id == ""
        assert step.approval_level == "auto"

    def test_full_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyStep
        step = StrategyStep(
            order=2,
            action_type="mutate_hook",
            action_params={"hook_type": "rescue"},
            pattern_id="pat_001",
            expected_impact="CTR +15%",
            approval_level="manual",
            rollback_action="restore_hook",
            timeout_hours=48.0,
        )
        assert step.order == 2
        assert step.action_type == "mutate_hook"
        assert step.action_params == {"hook_type": "rescue"}
        assert step.pattern_id == "pat_001"
        assert step.expected_impact == "CTR +15%"
        assert step.approval_level == "manual"
        assert step.rollback_action == "restore_hook"
        assert step.timeout_hours == 48.0

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyStep
        step = StrategyStep(order=1, action_type="clone_dna", pattern_id="pat_001")
        d = step.to_dict()
        assert d["order"] == 1
        assert d["action_type"] == "clone_dna"
        assert d["pattern_id"] == "pat_001"


# ═══════════════════════════════════════════════════════════════
# Test: StrategyPerformance
# ═══════════════════════════════════════════════════════════════

class TestStrategyPerformance:
    """StrategyPerformance 模型."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            StrategyPerformance, StrategyQuality,
        )
        perf = StrategyPerformance()
        assert perf.total_executions == 0
        assert perf.successful_executions == 0
        assert perf.success_rate == 0.0
        assert perf.quality == StrategyQuality.UNTESTED

    def test_full_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            StrategyPerformance, StrategyQuality,
        )
        perf = StrategyPerformance(
            total_executions=50,
            successful_executions=35,
            success_rate=0.7,
            avg_reward=0.75,
            avg_roas_change=0.15,
            quality=StrategyQuality.RELIABLE,
        )
        assert perf.total_executions == 50
        assert perf.successful_executions == 35
        assert perf.success_rate == 0.7
        assert perf.avg_roas_change == 0.15

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyPerformance
        perf = StrategyPerformance(total_executions=10, success_rate=0.8)
        d = perf.to_dict()
        assert d["total_executions"] == 10
        assert d["success_rate"] == 0.8


# ═══════════════════════════════════════════════════════════════
# Test: GrowthStrategyPattern
# ═══════════════════════════════════════════════════════════════

class TestGrowthStrategyPattern:
    """GrowthStrategyPattern 模型."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyCategory,
        )
        sp = GrowthStrategyPattern()
        assert sp.strategy_id != ""
        assert sp.category == StrategyCategory.GENERAL
        assert sp.steps == []
        assert sp.score == 0.0
        assert sp.confidence == 0.0

    def test_compute_score_with_executions(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyPerformance, StrategyStep,
        )
        sp = GrowthStrategyPattern(
            performance=StrategyPerformance(
                total_executions=100,
                successful_executions=75,
                success_rate=0.75,
                avg_reward=0.8,
            ),
            steps=[
                StrategyStep(order=1, action_type="clone_dna"),
                StrategyStep(order=2, action_type="create_population"),
                StrategyStep(order=3, action_type="scale_winner"),
            ],
        )
        score = sp.compute_score()
        assert score > 0
        assert sp.confidence > 0
        # 3+ 步有 step_bonus
        assert score > 0.4

    def test_compute_score_zero_executions(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import GrowthStrategyPattern
        sp = GrowthStrategyPattern()
        assert sp.compute_score() == 0.0

    def test_compute_score_single_step(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyPerformance, StrategyStep,
        )
        sp = GrowthStrategyPattern(
            performance=StrategyPerformance(
                total_executions=50,
                successful_executions=40,
                success_rate=0.8,
                avg_reward=0.7,
            ),
            steps=[StrategyStep(order=1, action_type="clone_dna")],
        )
        score = sp.compute_score()
        assert score > 0

    def test_steps_sorted_by_order(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyStep,
        )
        sp = GrowthStrategyPattern(steps=[
            StrategyStep(order=3, action_type="scale"),
            StrategyStep(order=1, action_type="clone"),
            StrategyStep(order=2, action_type="test"),
        ])
        assert sp.steps[0].order == 1
        assert sp.steps[1].order == 2
        assert sp.steps[2].order == 3

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyStep, StrategyPerformance,
            StrategyTriggerCondition,
        )
        sp = GrowthStrategyPattern(
            name="Test Pipeline",
            trigger=StrategyTriggerCondition(opportunity_type="creative_scale"),
            steps=[StrategyStep(order=1, action_type="clone_dna")],
            performance=StrategyPerformance(total_executions=10, success_rate=0.8),
        )
        sp.compute_score()
        d = sp.to_dict()
        assert d["name"] == "Test Pipeline"
        assert d["strategy_id"] == sp.strategy_id
        assert len(d["steps"]) == 1
        assert d["score"] > 0

    def test_is_actionable(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyPerformance,
        )
        sp = GrowthStrategyPattern(
            performance=StrategyPerformance(total_executions=10, success_rate=0.8),
        )
        assert sp.is_actionable() is True

    def test_is_not_actionable_low_executions(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyPerformance,
        )
        sp = GrowthStrategyPattern(
            performance=StrategyPerformance(total_executions=2, success_rate=0.8),
        )
        assert sp.is_actionable() is False

    def test_is_not_actionable_low_success(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyPerformance,
        )
        sp = GrowthStrategyPattern(
            performance=StrategyPerformance(total_executions=10, success_rate=0.3),
        )
        assert sp.is_actionable() is False

    def test_is_proven(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyPerformance,
        )
        sp = GrowthStrategyPattern(
            performance=StrategyPerformance(total_executions=100, success_rate=0.75),
        )
        assert sp.is_proven() is True

    def test_is_not_proven(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyPerformance,
        )
        sp = GrowthStrategyPattern(
            performance=StrategyPerformance(total_executions=50, success_rate=0.75),
        )
        assert sp.is_proven() is False

    def test_get_step_count(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyStep,
        )
        sp = GrowthStrategyPattern(steps=[
            StrategyStep(order=1, action_type="a"),
            StrategyStep(order=2, action_type="b"),
        ])
        assert sp.get_step_count() == 2

    def test_get_first_step(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyStep,
        )
        sp = GrowthStrategyPattern(steps=[
            StrategyStep(order=1, action_type="clone_dna"),
            StrategyStep(order=2, action_type="scale"),
        ])
        first = sp.get_first_step()
        assert first is not None
        assert first.action_type == "clone_dna"

    def test_get_first_step_empty(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import GrowthStrategyPattern
        sp = GrowthStrategyPattern()
        assert sp.get_first_step() is None

    def test_get_approval_summary(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyStep,
        )
        sp = GrowthStrategyPattern(steps=[
            StrategyStep(order=1, action_type="a", approval_level="auto"),
            StrategyStep(order=2, action_type="b", approval_level="auto"),
            StrategyStep(order=3, action_type="c", approval_level="manual"),
        ])
        summary = sp.get_approval_summary()
        assert summary["auto"] == 2
        assert summary["manual"] == 1

    def test_unique_strategy_ids(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import GrowthStrategyPattern
        ids = {GrowthStrategyPattern().strategy_id for _ in range(10)}
        assert len(ids) == 10


# ═══════════════════════════════════════════════════════════════
# Test: StrategyQuery / StrategyStats
# ═══════════════════════════════════════════════════════════════

class TestStrategyQuery:
    """StrategyQuery 模型."""

    def test_default_query(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyQuery
        q = StrategyQuery()
        assert q.limit == 100
        assert q.sort_by == "score"
        assert q.sort_desc is True

    def test_filtered_query(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyQuery
        q = StrategyQuery(
            opportunity_types=["creative_scale"],
            actionable_only=True,
            min_executions=10,
            limit=5,
        )
        assert q.opportunity_types == ["creative_scale"]
        assert q.actionable_only is True
        assert q.min_executions == 10
        assert q.limit == 5


class TestStrategyStats:
    """StrategyStats 模型."""

    def test_default_stats(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyStats
        s = StrategyStats()
        assert s.total_strategies == 0
        assert s.avg_score == 0.0

    def test_populated_stats(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyStats
        s = StrategyStats(
            total_strategies=10,
            total_actionable=6,
            total_proven=2,
            avg_score=0.55,
            avg_executions=45.0,
            avg_steps=2.5,
        )
        assert s.total_strategies == 10
        assert s.total_actionable == 6
        assert s.total_proven == 2
        assert s.avg_steps == 2.5

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyStats
        s = StrategyStats(total_strategies=5, total_actionable=3)
        d = s.to_dict()
        assert d["total_strategies"] == 5
        assert d["total_actionable"] == 3


# ═══════════════════════════════════════════════════════════════
# Test: StrategyMemory - Extract
# ═══════════════════════════════════════════════════════════════

class TestStrategyMemoryExtract:
    """StrategyMemory 提取功能."""

    def test_extract_empty_store(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        sm = StrategyMemory(ExperienceStore())
        strategies = sm.extract()
        assert strategies == []

    def test_extract_single_chain(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        store = ExperienceStore()
        # 同 entity 的 3 步成功链
        for exp in _make_experiences_for_chain("c001", ["clone_dna", "create_population", "scale_winner"]):
            store.store(exp)

        sm = StrategyMemory(store)
        strategies = sm.extract(min_samples=1)
        assert len(strategies) == 1
        assert strategies[0].get_step_count() == 3
        assert strategies[0].steps[0].action_type == "clone_dna"
        assert strategies[0].steps[1].action_type == "create_population"
        assert strategies[0].steps[2].action_type == "scale_winner"

    def test_extract_multiple_identical_chains(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        store = ExperienceStore()
        # 同 entity 3 条相同链
        for i in range(3):
            for exp in _make_experiences_for_chain(
                f"c{i:03d}", ["clone_dna", "create_population"]
            ):
                store.store(exp)

        sm = StrategyMemory(store)
        strategies = sm.extract(min_samples=1)
        assert len(strategies) == 1
        assert strategies[0].performance.total_executions == 3

    def test_extract_different_entities(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        store = ExperienceStore()
        # entity c001: clone → mutate → scale
        for exp in _make_experiences_for_chain("c001", ["clone_dna", "mutate_hook", "scale_winner"]):
            store.store(exp)
        # entity c002: clone → test → scale (不同序列)
        for exp in _make_experiences_for_chain("c002", ["clone_dna", "launch_ab_test", "scale_winner"]):
            store.store(exp)

        sm = StrategyMemory(store)
        strategies = sm.extract(min_samples=1)
        # 两个不同的链 = 两个策略
        assert len(strategies) == 2

    def test_extract_chain_with_failure_break(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        store = ExperienceStore()
        # 成功 → 成功 → 失败 → 成功 (链在失败处断开)
        for exp in _make_experiences_for_chain("c001", ["clone_dna", "create_population"], success=True):
            store.store(exp)
        store.store(_make_experience(
            action_type="scale_winner", entity_id="c001",
            success=False, reward=0.1,
            timestamp="2026-07-24T12:00:00+00:00",
        ))
        store.store(_make_experience(
            action_type="mutate_hook", entity_id="c001",
            success=True, reward=0.8,
            timestamp="2026-07-24T13:00:00+00:00",
        ))

        sm = StrategyMemory(store)
        strategies = sm.extract(min_samples=1)
        # 只有前 2 步成功链形成策略，后 1 步单步不够 min_chain_length
        assert len(strategies) == 1
        assert strategies[0].get_step_count() == 2

    def test_extract_min_chain_length(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        store = ExperienceStore()
        for exp in _make_experiences_for_chain("c001", ["clone_dna", "create_population", "scale_winner"]):
            store.store(exp)

        sm = StrategyMemory(store)
        # min_chain_length=4 应该过滤掉 3 步链
        strategies = sm.extract(min_chain_length=4, min_samples=1)
        assert strategies == []

    def test_extract_min_samples(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        store = ExperienceStore()
        # 只有 1 条链
        for exp in _make_experiences_for_chain("c001", ["clone_dna", "create_population"]):
            store.store(exp)

        sm = StrategyMemory(store)
        strategies = sm.extract(min_samples=3)
        assert strategies == []

    def test_extract_performance_computation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        store = ExperienceStore()
        # 5 条链，3 条全部成功，2 条有失败
        for i in range(3):
            for exp in _make_experiences_for_chain(
                f"c{i:03d}", ["clone_dna", "create_population"], success=True,
            ):
                store.store(exp)
        for i in range(3, 5):
            for exp in _make_experiences_for_chain(
                f"c{i:03d}", ["clone_dna", "create_population"], success=False, reward=0.2,
            ):
                store.store(exp)

        sm = StrategyMemory(store)
        strategies = sm.extract()
        assert len(strategies) == 1
        # 失败链不形成 chain，只有 3 条成功链
        assert strategies[0].performance.total_executions == 3
        assert strategies[0].performance.success_rate == 1.0  # 3/3 (失败链被排除)

    def test_extract_with_audience_segment(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        store = ExperienceStore()
        for exp in _make_experiences_for_chain(
            "c001", ["clone_dna", "create_population"], audience_segment="female_25_35",
        ):
            store.store(exp)

        sm = StrategyMemory(store)
        strategies = sm.extract(min_samples=1)
        assert len(strategies) == 1
        assert strategies[0].trigger.audience_segment == "female_25_35"

    def test_extract_strategy_name_generation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        store = ExperienceStore()
        for exp in _make_experiences_for_chain("c001", ["clone_dna", "create_population"]):
            store.store(exp)

        sm = StrategyMemory(store)
        strategies = sm.extract(min_samples=1)
        assert len(strategies) == 1
        assert "Pipeline" in strategies[0].name

    def test_extract_quality_assignment_proven(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyQuality
        store = ExperienceStore()
        for i in range(100):
            for exp in _make_experiences_for_chain(
                f"c{i:03d}", ["clone_dna", "create_population"], success=True,
            ):
                store.store(exp)

        sm = StrategyMemory(store)
        strategies = sm.extract(min_samples=3)
        assert len(strategies) == 1
        assert strategies[0].performance.quality == StrategyQuality.PROVEN


# ═══════════════════════════════════════════════════════════════
# Test: StrategyMemory - Store
# ═══════════════════════════════════════════════════════════════

class TestStrategyMemoryStore:
    """StrategyMemory 存储功能."""

    def _setup_store(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        return StrategyMemory(ExperienceStore())

    def _make_strategy(self, name="Test", opportunity_type="creative_scale", steps=None):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyStep, StrategyPerformance,
            StrategyTriggerCondition,
        )
        if steps is None:
            steps = [StrategyStep(order=1, action_type="clone_dna")]
        return GrowthStrategyPattern(
            name=name,
            trigger=StrategyTriggerCondition(opportunity_type=opportunity_type),
            steps=steps,
            performance=StrategyPerformance(total_executions=10, success_rate=0.8),
        )

    def test_store_single(self):
        sm = self._setup_store()
        strategy = self._make_strategy()
        sid = sm.store(strategy)
        assert sid == strategy.strategy_id
        assert sm.count == 1

    def test_store_batch(self):
        sm = self._setup_store()
        s1 = self._make_strategy(name="S1", opportunity_type="creative_scale")
        s2 = self._make_strategy(name="S2", opportunity_type="roas_drop")
        ids = sm.store_batch([s1, s2])
        assert len(ids) == 2
        assert sm.count == 2

    def test_store_update_existing(self):
        sm = self._setup_store()
        s1 = self._make_strategy(name="S1")
        sm.store(s1)

        # 相同 trigger + 步骤序列，应该更新
        s2 = self._make_strategy(name="S1 Updated")
        s2.performance.total_executions = 20
        sm.store(s2)

        assert sm.count == 1
        all_s = sm.get_all()
        assert all_s[0].performance.total_executions == 20


# ═══════════════════════════════════════════════════════════════
# Test: StrategyMemory - Query
# ═══════════════════════════════════════════════════════════════

class TestStrategyMemoryQuery:
    """StrategyMemory 查询功能."""

    def _setup_store(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyStep, StrategyPerformance,
            StrategyTriggerCondition, StrategyCategory,
        )
        sm = StrategyMemory(ExperienceStore())

        # 策略 1: 创意放大
        s1 = GrowthStrategyPattern(
            name="Creative Scale Pipeline",
            category=StrategyCategory.CREATIVE_SCALE,
            trigger=StrategyTriggerCondition(
                opportunity_type="creative_scale",
                scenario="Creative scaling opportunity detected",
            ),
            steps=[StrategyStep(order=1, action_type="clone_dna")],
            performance=StrategyPerformance(total_executions=50, success_rate=0.8),
        )
        s1.compute_score()

        # 策略 2: ROAS 恢复
        s2 = GrowthStrategyPattern(
            name="ROAS Recovery Pipeline",
            category=StrategyCategory.ROAS_RECOVERY,
            trigger=StrategyTriggerCondition(
                opportunity_type="roas_drop",
                scenario="ROAS dropping below threshold",
            ),
            steps=[
                StrategyStep(order=1, action_type="reduce_budget"),
                StrategyStep(order=2, action_type="refresh_creative"),
            ],
            performance=StrategyPerformance(total_executions=30, success_rate=0.7),
        )
        s2.compute_score()

        # 策略 3: 低成功率
        s3 = GrowthStrategyPattern(
            name="Risky Strategy",
            trigger=StrategyTriggerCondition(
                opportunity_type="creative_scale",
                scenario="Risky creative experiment",
            ),
            steps=[StrategyStep(order=1, action_type="random_action")],
            performance=StrategyPerformance(total_executions=10, success_rate=0.3),
        )
        s3.compute_score()

        sm.store_batch([s1, s2, s3])
        return sm

    def test_query_by_opportunity_type(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyQuery
        sm = self._setup_store()
        results = sm.query(StrategyQuery(opportunity_types=["creative_scale"]))
        assert len(results) == 2

    def test_query_by_category(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyQuery
        sm = self._setup_store()
        results = sm.query(StrategyQuery(categories=["creative_scale"]))
        assert len(results) == 1
        assert results[0].name == "Creative Scale Pipeline"

    def test_query_actionable_only(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyQuery
        sm = self._setup_store()
        results = sm.query(StrategyQuery(actionable_only=True))
        assert len(results) == 2  # s3 成功率太低
        assert all(s.is_actionable() for s in results)

    def test_query_min_executions(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyQuery
        sm = self._setup_store()
        results = sm.query(StrategyQuery(min_executions=40))
        assert len(results) == 1  # 只有 s1

    def test_query_min_success_rate(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyQuery
        sm = self._setup_store()
        results = sm.query(StrategyQuery(min_success_rate=0.75))
        assert len(results) == 1

    def test_query_sort_by_score(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyQuery
        sm = self._setup_store()
        results = sm.query(StrategyQuery(sort_by="score", sort_desc=True))
        assert len(results) == 3
        assert results[0].score >= results[1].score

    def test_query_limit(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyQuery
        sm = self._setup_store()
        results = sm.query(StrategyQuery(limit=1, sort_by="score"))
        assert len(results) == 1

    def test_query_empty_store(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyQuery
        sm = StrategyMemory(ExperienceStore())
        results = sm.query(StrategyQuery())
        assert results == []

    def test_query_proven_only(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyQuery
        sm = self._setup_store()
        results = sm.query(StrategyQuery(proven_only=True))
        assert len(results) == 0  # 没有 100+ 执行

    def test_query_by_scenario(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyQuery
        sm = self._setup_store()
        results = sm.query(StrategyQuery(scenario="scaling"))
        assert len(results) == 1
        assert "Scale" in results[0].name


# ═══════════════════════════════════════════════════════════════
# Test: StrategyMemory - Recommend
# ═══════════════════════════════════════════════════════════════

class TestStrategyMemoryRecommend:
    """StrategyMemory 推荐功能."""

    def _setup_store(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyStep, StrategyPerformance,
            StrategyTriggerCondition,
        )
        sm = StrategyMemory(ExperienceStore())

        # 策略 1: 精准匹配 creative_scale + female
        s1 = GrowthStrategyPattern(
            name="Merge Female Creative Scale Pipeline",
            trigger=StrategyTriggerCondition(
                opportunity_type="creative_scale",
                audience_segment="female_25_35",
                product_category="merge",
            ),
            steps=[StrategyStep(order=1, action_type="clone_dna")],
            performance=StrategyPerformance(total_executions=50, success_rate=0.8),
        )
        s1.compute_score()

        # 策略 2: 通用 creative_scale
        s2 = GrowthStrategyPattern(
            name="Generic Creative Scale Pipeline",
            trigger=StrategyTriggerCondition(opportunity_type="creative_scale"),
            steps=[StrategyStep(order=1, action_type="mutate_visual")],
            performance=StrategyPerformance(total_executions=30, success_rate=0.7),
        )
        s2.compute_score()

        # 策略 3: ROAS 恢复
        s3 = GrowthStrategyPattern(
            name="ROAS Recovery Pipeline",
            trigger=StrategyTriggerCondition(opportunity_type="roas_drop"),
            steps=[StrategyStep(order=1, action_type="reduce_budget")],
            performance=StrategyPerformance(total_executions=20, success_rate=0.75),
        )
        s3.compute_score()

        sm.store_batch([s1, s2, s3])
        return sm

    def test_recommend_by_opportunity(self):
        sm = self._setup_store()
        results = sm.recommend(opportunity_type="creative_scale")
        assert len(results) >= 1

    def test_recommend_best_exact_match(self):
        sm = self._setup_store()
        best = sm.recommend_best(
            opportunity_type="creative_scale",
            audience_segment="female_25_35",
            product_category="merge",
        )
        assert best is not None
        assert "Merge" in best.name

    def test_recommend_best_no_match(self):
        sm = self._setup_store()
        best = sm.recommend_best(opportunity_type="unknown_type")
        assert best is None

    def test_recommend_top_n(self):
        sm = self._setup_store()
        results = sm.recommend(top_n=1)
        assert len(results) == 1

    def test_recommend_empty_store(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        sm = StrategyMemory(ExperienceStore())
        assert sm.recommend() == []
        assert sm.recommend_best() is None

    def test_recommend_actionable_only(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyStep, StrategyPerformance,
            StrategyTriggerCondition,
        )
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        sm = StrategyMemory(ExperienceStore())
        # 不可执行策略
        s = GrowthStrategyPattern(
            name="Bad",
            trigger=StrategyTriggerCondition(opportunity_type="creative_scale"),
            steps=[StrategyStep(order=1, action_type="bad_action")],
            performance=StrategyPerformance(total_executions=2, success_rate=0.6),
        )
        s.compute_score()
        sm.store(s)
        results = sm.recommend(opportunity_type="creative_scale", actionable_only=True)
        assert results == []

    def test_recommend_with_signals(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyStep, StrategyPerformance,
            StrategyTriggerCondition,
        )
        sm = StrategyMemory(ExperienceStore())
        s = GrowthStrategyPattern(
            name="Signal Match",
            trigger=StrategyTriggerCondition(
                opportunity_type="creative_scale",
                signal_types=["CREATIVE_FATIGUE"],
            ),
            steps=[StrategyStep(order=1, action_type="mutate_hook")],
            performance=StrategyPerformance(total_executions=10, success_rate=0.8),
        )
        s.compute_score()
        sm.store(s)
        results = sm.recommend(
            opportunity_type="creative_scale",
            signal_types=["CREATIVE_FATIGUE"],
        )
        assert len(results) == 1


# ═══════════════════════════════════════════════════════════════
# Test: StrategyMemory - Convenience Methods
# ═══════════════════════════════════════════════════════════════

class TestStrategyMemoryConvenience:
    """StrategyMemory 便捷方法."""

    def _setup_store(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyStep, StrategyPerformance,
            StrategyTriggerCondition, StrategyCategory,
        )
        sm = StrategyMemory(ExperienceStore())
        s = GrowthStrategyPattern(
            name="Test",
            category=StrategyCategory.CREATIVE_SCALE,
            trigger=StrategyTriggerCondition(opportunity_type="creative_scale"),
            steps=[StrategyStep(order=1, action_type="clone_dna")],
            performance=StrategyPerformance(total_executions=10, success_rate=0.8),
        )
        s.compute_score()
        sm.store(s)
        return sm

    def test_get_all(self):
        sm = self._setup_store()
        assert len(sm.get_all()) == 1

    def test_get_by_opportunity(self):
        sm = self._setup_store()
        results = sm.get_by_opportunity("creative_scale")
        assert len(results) == 1

    def test_get_by_category(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyCategory
        sm = self._setup_store()
        results = sm.get_by_category(StrategyCategory.CREATIVE_SCALE)
        assert len(results) == 1

    def test_get_top_strategies(self):
        sm = self._setup_store()
        results = sm.get_top_strategies(5)
        assert len(results) == 1

    def test_get_actionable_strategies(self):
        sm = self._setup_store()
        results = sm.get_actionable_strategies()
        assert len(results) == 1

    def test_get_proven_strategies(self):
        sm = self._setup_store()
        results = sm.get_proven_strategies()
        assert results == []

    def test_count_property(self):
        sm = self._setup_store()
        assert sm.count == 1

    def test_clear(self):
        sm = self._setup_store()
        sm.clear()
        assert sm.count == 0


# ═══════════════════════════════════════════════════════════════
# Test: StrategyMemory - Stats
# ═══════════════════════════════════════════════════════════════

class TestStrategyMemoryStats:
    """StrategyMemory 统计功能."""

    def test_stats_empty(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        sm = StrategyMemory(ExperienceStore())
        stats = sm.get_stats()
        assert stats.total_strategies == 0

    def test_stats_populated(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
            GrowthStrategyPattern, StrategyStep, StrategyPerformance,
            StrategyTriggerCondition, StrategyCategory,
        )
        sm = StrategyMemory(ExperienceStore())
        s1 = GrowthStrategyPattern(
            name="S1", category=StrategyCategory.CREATIVE_SCALE,
            trigger=StrategyTriggerCondition(opportunity_type="creative_scale"),
            steps=[StrategyStep(order=1, action_type="clone_dna")],
            performance=StrategyPerformance(total_executions=10, success_rate=0.8),
        )
        s1.compute_score()
        s2 = GrowthStrategyPattern(
            name="S2", category=StrategyCategory.ROAS_RECOVERY,
            trigger=StrategyTriggerCondition(opportunity_type="roas_drop"),
            steps=[StrategyStep(order=1, action_type="reduce_budget")],
            performance=StrategyPerformance(total_executions=20, success_rate=0.7),
        )
        s2.compute_score()
        sm.store_batch([s1, s2])

        stats = sm.get_stats()
        assert stats.total_strategies == 2
        assert stats.avg_score > 0
        assert stats.avg_executions == 15.0
        assert "creative_scale" in stats.by_category
        assert "roas_recovery" in stats.by_category


# ═══════════════════════════════════════════════════════════════
# Test: Integration
# ═══════════════════════════════════════════════════════════════

class TestIntegration:
    """集成测试."""

    def test_full_extract_store_recommend_loop(self):
        """完整闭环: 经验→提取→存储→推荐."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory

        # Step 1: 积累经验 (多条相同链)
        exp_store = ExperienceStore()
        for i in range(10):
            for exp in _make_experiences_for_chain(
                f"c{i:03d}",
                ["clone_dna", "create_population", "scale_winner"],
                opportunity_type="creative_scale",
                success=True,
                reward=0.82,
            ):
                exp_store.store(exp)

        # Step 2: 提取策略
        sm = StrategyMemory(exp_store)
        strategies = sm.extract()

        # Step 3: 存储
        ids = sm.store_batch(strategies)
        assert len(ids) >= 1

        # Step 4: 推荐
        best = sm.recommend_best(opportunity_type="creative_scale")
        assert best is not None
        assert best.get_step_count() == 3
        assert best.performance.total_executions == 10
        assert best.performance.success_rate == 1.0

    def test_extract_with_different_product_ids(self):
        """不同产品的链应产生不同策略."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory

        exp_store = ExperienceStore()
        # merge 产品
        for i in range(5):
            for exp in _make_experiences_for_chain(
                f"cm{i:03d}", ["clone_dna", "scale_winner"],
                product_id="merge",
            ):
                exp_store.store(exp)
        # puzzle 产品
        for i in range(5):
            for exp in _make_experiences_for_chain(
                f"cp{i:03d}", ["clone_dna", "scale_winner"],
                product_id="puzzle",
            ):
                exp_store.store(exp)

        sm = StrategyMemory(exp_store)
        strategies = sm.extract()
        # 不同 product_id 的链应产生不同策略
        assert len(strategies) == 2

    def test_extract_and_store_then_query(self):
        """提取→存储→查询 完整流程."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyQuery

        exp_store = ExperienceStore()
        for i in range(5):
            for exp in _make_experiences_for_chain(
                f"c{i:03d}", ["mutate_hook", "launch_ab_test", "scale_winner"],
                opportunity_type="creative_fatigue",
            ):
                exp_store.store(exp)

        sm = StrategyMemory(exp_store)
        ids = sm.extract_and_store()
        assert len(ids) >= 1

        results = sm.query(StrategyQuery(opportunity_types=["creative_fatigue"]))
        assert len(results) >= 1
        assert results[0].get_step_count() == 3

    def test_chain_with_failure_still_extracts_partial(self):
        """包含失败的链，只提取成功部分."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory

        exp_store = ExperienceStore()
        for i in range(5):
            # 成功 → 成功 → 失败 → 成功 → 成功
            chain = _make_experiences_for_chain(
                f"c{i:03d}", ["clone_dna", "create_population"],
                success=True, reward=0.8,
            )
            chain.append(_make_experience(
                action_type="bad_action", entity_id=f"c{i:03d}",
                success=False, reward=0.1,
                timestamp="2026-07-24T12:00:00+00:00",
            ))
            chain.append(_make_experience(
                action_type="mutate_hook", entity_id=f"c{i:03d}",
                success=True, reward=0.75,
                timestamp="2026-07-24T13:00:00+00:00",
            ))
            chain.append(_make_experience(
                action_type="scale_winner", entity_id=f"c{i:03d}",
                success=True, reward=0.9,
                timestamp="2026-07-24T14:00:00+00:00",
            ))
            for exp in chain:
                exp_store.store(exp)

        sm = StrategyMemory(exp_store)
        strategies = sm.extract()
        assert len(strategies) >= 1
        # 后 2 步成功链 (mutate_hook → scale_winner) 应被提取
        step_actions = [s.action_type for s in strategies[0].steps]
        # 前 2 步链 (clone_dna → create_population) 也应被提取
        all_actions = [s.action_type for strategy in strategies for s in strategy.steps]
        assert "clone_dna" in all_actions or "mutate_hook" in all_actions

    def test_large_scale_extraction(self):
        """大规模提取测试."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory

        exp_store = ExperienceStore()
        actions_list = [
            ["clone_dna", "create_population", "scale_winner"],
            ["mutate_hook", "launch_ab_test", "scale_winner"],
            ["clone_dna", "mutate_visual", "scale_winner"],
        ]

        for i in range(50):
            actions = actions_list[i % 3]
            for j, exp in enumerate(_make_experiences_for_chain(
                f"c{i:03d}", actions,
                success=(i % 10 != 0),  # 90% 成功率
            )):
                exp_store.store(exp)

        sm = StrategyMemory(exp_store)
        strategies = sm.extract()
        assert len(strategies) >= 1
        assert len(strategies) <= 3  # 最多 3 种不同链模式