"""E13.4.5 Memory Evolution — 测试套件.

测试覆盖:
  - EvolutionEventType / EvolutionTarget 枚举
  - EvolutionEvent: 创建、序列化
  - ConsolidationResult: 创建、合并结果
  - KnowledgeGraph: 创建、序列化
  - EvolutionMetrics: 创建、序列化
  - EvolutionConfig: 默认值、自定义
  - MemoryEvolution: 初始化、evolve、consolidate
  - MemoryEvolution: cross_reference、decay、metrics
  - MemoryEvolution: history、summary
  - 集成场景: 全量进化→知识图谱→指标
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
    action_type: str = "increase_budget",
    entity_id: str = "c001",
    audience_segment: str = "",
    trigger_signals: list[str] | None = None,
    **kwargs,
) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceContext
    return ExperienceContext(
        product_id=product_id,
        date=date,
        opportunity_type=opportunity_type,
        action_type=action_type,
        entity_id=entity_id,
        audience_segment=audience_segment,
        trigger_signals=trigger_signals or [],
        **kwargs,
    )


def _make_outcome(
    success: bool = True,
    actual_reward: float = 0.85,
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
        **kwargs,
    )


def _make_experience(
    action_type: str = "increase_budget",
    opportunity_type: str = "creative_scale",
    entity_id: str = "c001",
    reward: float = 0.85,
    success: bool = True,
    audience_segment: str = "",
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
    )
    return GrowthExperience(
        context=ctx,
        action_type=action_type,
        action_params={},
        outcome=_make_outcome(success=success, actual_reward=reward),
        reward=reward,
        **kwargs,
    )


def _make_pattern(
    pattern_id: str = "p001",
    action_type: str = "increase_budget",
    opportunity_type: str = "creative_scale",
    success_rate: float = 0.8,
    samples: int = 20,
    success_count: int = 16,
    audience_segment: str = "",
    **kwargs,
) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
        PatternMemory, PatternCondition, PatternPerformance, PatternAction,
    )
    from datetime import datetime, timezone
    return PatternMemory(
        pattern_id=pattern_id,
        condition=PatternCondition(
            action_type=action_type,
            opportunity_type=opportunity_type,
            audience_segment=audience_segment,
        ),
        action=PatternAction(action_type=action_type),
        performance=PatternPerformance(
            samples=samples,
            success_count=success_count,
            success_rate=success_rate,
            avg_reward=0.75,
            last_seen=datetime.now(timezone.utc).isoformat(),
        ),
        **kwargs,
    )


def _make_strategy(
    strategy_id: str = "s001",
    name: str = "Test Strategy",
    opportunity_type: str = "creative_scale",
    steps: list[Any] | None = None,
    **kwargs,
) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
        GrowthStrategyPattern, StrategyStep, StrategyTriggerCondition,
    )
    if steps is None:
        steps = [
            StrategyStep(order=1, action_type="clone_dna"),
            StrategyStep(order=2, action_type="scale_winner"),
        ]
    return GrowthStrategyPattern(
        strategy_id=strategy_id,
        name=name,
        trigger=StrategyTriggerCondition(opportunity_type=opportunity_type),
        steps=steps,
        **kwargs,
    )


# ═══════════════════════════════════════════════════════════════
# Test: Enums
# ═══════════════════════════════════════════════════════════════

class TestEvolutionEventType:
    """EvolutionEventType 枚举."""

    def test_event_types_exist(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionEventType
        assert EvolutionEventType.CONSOLIDATE.value == "consolidate"
        assert EvolutionEventType.UPGRADE.value == "upgrade"
        assert EvolutionEventType.DOWNGRADE.value == "downgrade"
        assert EvolutionEventType.DECAY.value == "decay"
        assert EvolutionEventType.CONFLICT_RESOLVE.value == "conflict_resolve"
        assert EvolutionEventType.CROSS_REFERENCE.value == "cross_reference"
        assert EvolutionEventType.NEW_KNOWLEDGE.value == "new_knowledge"
        assert EvolutionEventType.DEPRECATE.value == "deprecate"
        assert EvolutionEventType.MERGE.value == "merge"


class TestEvolutionTarget:
    """EvolutionTarget 枚举."""

    def test_targets_exist(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionTarget
        assert EvolutionTarget.PATTERN.value == "pattern"
        assert EvolutionTarget.STRATEGY.value == "strategy"
        assert EvolutionTarget.FAILURE.value == "failure"
        assert EvolutionTarget.CROSS_LAYER.value == "cross_layer"


# ═══════════════════════════════════════════════════════════════
# Test: EvolutionEvent
# ═══════════════════════════════════════════════════════════════

class TestEvolutionEvent:
    """EvolutionEvent 模型."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import (
            EvolutionEvent, EvolutionEventType, EvolutionTarget,
        )
        e = EvolutionEvent()
        assert e.event_id != ""
        assert e.event_type == EvolutionEventType.UPGRADE
        assert e.target_type == EvolutionTarget.PATTERN
        assert e.timestamp != ""

    def test_full_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import (
            EvolutionEvent, EvolutionEventType, EvolutionTarget,
        )
        e = EvolutionEvent(
            event_type=EvolutionEventType.CONSOLIDATE,
            target_type=EvolutionTarget.PATTERN,
            source_ids=["p1", "p2"],
            target_id="p1",
            before_state={"confidence": 0.7},
            after_state={"confidence": 0.85},
            delta={"confidence": 0.15},
            reason="Merged 2 patterns",
        )
        assert e.event_type == EvolutionEventType.CONSOLIDATE
        assert len(e.source_ids) == 2
        assert e.delta["confidence"] == 0.15

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import (
            EvolutionEvent, EvolutionEventType, EvolutionTarget,
        )
        e = EvolutionEvent(
            event_type=EvolutionEventType.UPGRADE,
            target_type=EvolutionTarget.PATTERN,
            source_ids=["p1"],
            target_id="p1",
            before_state={"conf": 0.8},
            after_state={"conf": 0.9},
            delta={"conf": 0.1},
            reason="test",
        )
        d = e.to_dict()
        assert d["event_type"] == "upgrade"
        assert d["target_type"] == "pattern"
        assert d["delta"]["conf"] == 0.1

    def test_unique_ids(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionEvent
        ids = {EvolutionEvent().event_id for _ in range(10)}
        assert len(ids) == 10


# ═══════════════════════════════════════════════════════════════
# Test: ConsolidationResult
# ═══════════════════════════════════════════════════════════════

class TestConsolidationResult:
    """ConsolidationResult 模型."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import (
            ConsolidationResult, EvolutionTarget,
        )
        cr = ConsolidationResult()
        assert cr.consolidated_id == ""
        assert cr.target_type == EvolutionTarget.PATTERN
        assert cr.confidence_before == 0.0

    def test_full_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import ConsolidationResult
        cr = ConsolidationResult(
            consolidated_id="merged_001",
            source_ids=["p1", "p2"],
            confidence_before=0.7,
            confidence_after=0.85,
            total_evidence=50,
            improvement=0.15,
        )
        assert cr.source_ids == ["p1", "p2"]
        assert cr.total_evidence == 50
        assert cr.improvement == 0.15

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import ConsolidationResult
        cr = ConsolidationResult(
            consolidated_id="m1",
            source_ids=["p1"],
            confidence_before=0.7,
            confidence_after=0.8,
            total_evidence=30,
            improvement=0.1,
        )
        d = cr.to_dict()
        assert d["consolidated_id"] == "m1"
        assert d["improvement"] == 0.1


# ═══════════════════════════════════════════════════════════════
# Test: KnowledgeGraph
# ═══════════════════════════════════════════════════════════════

class TestKnowledgeGraph:
    """KnowledgeGraph 模型."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import KnowledgeGraph
        kg = KnowledgeGraph()
        assert kg.cross_references == 0
        assert kg.graph_density == 0.0
        assert kg.isolated_patterns == []
        assert kg.isolated_strategies == []

    def test_populated(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import KnowledgeGraph
        kg = KnowledgeGraph(
            pattern_to_strategies={"p1": [{"strategy_id": "s1", "strategy_name": "S1", "step_order": 1}]},
            strategy_to_patterns={"s1": ["p1"]},
            cross_references=1,
            graph_density=0.5,
            isolated_patterns=["p2"],
            isolated_strategies=["s2:step_1"],
        )
        assert kg.cross_references == 1
        assert len(kg.isolated_patterns) == 1
        assert len(kg.isolated_strategies) == 1

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import KnowledgeGraph
        kg = KnowledgeGraph(cross_references=5, graph_density=0.3)
        d = kg.to_dict()
        assert d["cross_references"] == 5
        assert d["graph_density"] == 0.3


# ═══════════════════════════════════════════════════════════════
# Test: EvolutionMetrics
# ═══════════════════════════════════════════════════════════════

class TestEvolutionMetrics:
    """EvolutionMetrics 模型."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionMetrics
        m = EvolutionMetrics()
        assert m.total_events == 0
        assert m.evolution_score == 0.0

    def test_populated(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionMetrics
        m = EvolutionMetrics(
            total_events=10,
            consolidations=3,
            upgrades=5,
            downgrades=1,
            decays=1,
            avg_confidence_before=0.7,
            avg_confidence_after=0.82,
            confidence_improvement=0.12,
            evolution_score=0.65,
        )
        assert m.total_events == 10
        assert m.confidence_improvement == 0.12

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionMetrics
        m = EvolutionMetrics(total_events=5, upgrades=3, evolution_score=0.5)
        d = m.to_dict()
        assert d["total_events"] == 5
        assert d["upgrades"] == 3


# ═══════════════════════════════════════════════════════════════
# Test: EvolutionConfig
# ═══════════════════════════════════════════════════════════════

class TestEvolutionConfig:
    """EvolutionConfig 模型."""

    def test_defaults(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionConfig
        c = EvolutionConfig()
        assert c.consolidation_threshold == 0.7
        assert c.min_confidence_improvement == 0.05
        assert c.decay_days == 30
        assert c.decay_rate == 0.01
        assert c.auto_consolidate is True
        assert c.auto_upgrade is True
        assert c.auto_decay is True
        assert c.auto_cross_reference is True

    def test_custom(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionConfig
        c = EvolutionConfig(
            consolidation_threshold=0.8,
            decay_days=14,
            auto_consolidate=False,
        )
        assert c.consolidation_threshold == 0.8
        assert c.decay_days == 14
        assert c.auto_consolidate is False

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionConfig
        c = EvolutionConfig(decay_days=20)
        d = c.to_dict()
        assert d["decay_days"] == 20


# ═══════════════════════════════════════════════════════════════
# Test: MemoryEvolution - Init
# ═══════════════════════════════════════════════════════════════

class TestMemoryEvolutionInit:
    """MemoryEvolution 初始化."""

    def test_init_empty(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        evo = MemoryEvolution()
        assert evo.history_count == 0
        assert evo.config is not None

    def test_init_with_config(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionConfig
        config = EvolutionConfig(consolidation_threshold=0.85)
        evo = MemoryEvolution(config=config)
        assert evo.config.consolidation_threshold == 0.85

    def test_init_with_all_stores(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        evo = MemoryEvolution(
            pattern_store=None,
            strategy_memory=None,
            failure_memory=FailureMemory(ExperienceStore()),
        )
        assert evo.history_count == 0


# ═══════════════════════════════════════════════════════════════
# Test: MemoryEvolution - Evolve (empty stores)
# ═══════════════════════════════════════════════════════════════

class TestMemoryEvolutionEvolveEmpty:
    """MemoryEvolution evolve 空存储."""

    def test_evolve_empty_all(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        evo = MemoryEvolution()
        metrics = evo.evolve()
        assert metrics.total_events == 0
        assert metrics.evolution_score == 0.0

    def test_evolve_empty_stores_no_events(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        evo = MemoryEvolution()
        metrics = evo.evolve(ExperienceStore())
        assert metrics.total_events == 0

    def test_evolve_with_disabled_config(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionConfig
        config = EvolutionConfig(
            auto_consolidate=False,
            auto_upgrade=False,
            auto_decay=False,
            auto_cross_reference=False,
        )
        evo = MemoryEvolution(config=config)
        metrics = evo.evolve()
        assert metrics.total_events == 0


# ═══════════════════════════════════════════════════════════════
# Test: MemoryEvolution - Consolidate
# ═══════════════════════════════════════════════════════════════

class TestMemoryEvolutionConsolidate:
    """MemoryEvolution 合并功能."""

    def _setup(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        ps = PatternStore()
        evo = MemoryEvolution(pattern_store=ps)
        return evo, ps

    def test_consolidate_two_similar_patterns(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionConfig
        evo, ps = self._setup()
        evo._config = EvolutionConfig(min_confidence_improvement=0.0, auto_consolidate=True)

        p1 = _make_pattern(pattern_id="p1", success_rate=0.7, samples=10, success_count=7)
        p2 = _make_pattern(pattern_id="p2", success_rate=0.9, samples=10, success_count=9)
        # 绕过 PatternStore.store() 去重逻辑 (同 condition 会覆盖)
        ps._patterns.append(p1)
        ps._patterns.append(p2)

        result = evo._consolidate_patterns()
        assert len(result) >= 1
        # 合并后应该只剩1个
        remaining = ps.get_all()
        assert len(remaining) == 1
        # 合并后置信度应该是加权平均: (0.7*10 + 0.9*10) / 20 = 0.8
        assert remaining[0].performance.success_rate == 0.8

    def test_consolidate_no_improvement(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionConfig
        evo, ps = self._setup()
        evo._config = EvolutionConfig(min_confidence_improvement=0.3, auto_consolidate=True)

        p1 = _make_pattern(pattern_id="p1", success_rate=0.7, samples=10, success_count=7)
        p2 = _make_pattern(pattern_id="p2", success_rate=0.71, samples=10, success_count=7)
        # 绕过 PatternStore.store() 去重逻辑
        ps._patterns.append(p1)
        ps._patterns.append(p2)

        result = evo._consolidate_patterns()
        assert result == []  # 提升太小，不合并
        assert len(ps.get_all()) == 2

    def test_consolidate_single_pattern_noop(self):
        evo, ps = self._setup()
        p1 = _make_pattern()
        ps.store(p1)
        result = evo._consolidate_patterns()
        assert result == []

    def test_consolidate_different_actions_no_merge(self):
        evo, ps = self._setup()
        p1 = _make_pattern(pattern_id="p1", action_type="increase_budget")
        p2 = _make_pattern(pattern_id="p2", action_type="scale_winner")
        ps.store(p1)
        ps.store(p2)
        result = evo._consolidate_patterns()
        assert result == []  # 不同动作不合并
        assert len(ps.get_all()) == 2


# ═══════════════════════════════════════════════════════════════
# Test: MemoryEvolution - Cross Reference
# ═══════════════════════════════════════════════════════════════

class TestMemoryEvolutionCrossReference:
    """MemoryEvolution 跨层引用."""

    def _setup(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        ps = PatternStore()
        sm = StrategyMemory(ExperienceStore())
        evo = MemoryEvolution(pattern_store=ps, strategy_memory=sm)
        return evo, ps, sm

    def test_build_cross_references_empty(self):
        evo, ps, sm = self._setup()
        events = evo._build_cross_references()
        kg = evo.get_knowledge_graph()
        assert kg.cross_references == 0

    def test_build_cross_references_with_patterns(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyStep
        evo, ps, sm = self._setup()

        p = _make_pattern(pattern_id="p1", action_type="scale_winner")
        ps.store(p)

        strategy = _make_strategy(
            strategy_id="s1",
            steps=[
                StrategyStep(order=1, action_type="clone_dna"),
                StrategyStep(order=2, action_type="scale_winner", pattern_id="p1"),
            ],
        )
        sm.store(strategy)

        events = evo._build_cross_references()
        kg = evo.get_knowledge_graph()
        assert kg.cross_references >= 1
        assert "p1" in kg.pattern_to_strategies

    def test_isolated_patterns_detected(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyStep
        evo, ps, sm = self._setup()
        p1 = _make_pattern(pattern_id="p1", action_type="isolated_action")
        ps.store(p1)

        strategy = _make_strategy(
            strategy_id="s1",
            steps=[
                StrategyStep(order=1, action_type="clone_dna"),  # 没有 pattern_id
            ],
        )
        sm.store(strategy)

        evo._build_cross_references()
        isolated = evo.get_isolated_knowledge()
        assert "p1" in isolated["isolated_patterns"]
        assert len(isolated["isolated_strategies"]) >= 1


# ═══════════════════════════════════════════════════════════════
# Test: MemoryEvolution - Decay
# ═══════════════════════════════════════════════════════════════

class TestMemoryEvolutionDecay:
    """MemoryEvolution 衰减功能."""

    def test_decay_no_stores(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        evo = MemoryEvolution()
        events = evo._apply_decay()
        assert events == []

    def test_decay_recent_pattern_no_decay(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from datetime import datetime, timezone
        ps = PatternStore()
        p = _make_pattern(success_rate=0.8)
        p.performance.last_seen = datetime.now(timezone.utc).isoformat()
        ps.store(p)

        evo = MemoryEvolution(pattern_store=ps)
        events = evo._apply_decay()
        assert events == []  # 最近使用，不衰减
        assert ps.get_all()[0].performance.success_rate == 0.8

    def test_decay_old_pattern(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionConfig
        from datetime import datetime, timedelta, timezone
        ps = PatternStore()
        p = _make_pattern(success_rate=0.8)
        # 设置 60 天前最后使用
        old_date = datetime.now(timezone.utc) - timedelta(days=60)
        p.performance.last_seen = old_date.isoformat()
        ps.store(p)

        config = EvolutionConfig(decay_days=30, decay_rate=0.01)
        evo = MemoryEvolution(pattern_store=ps, config=config)
        events = evo._apply_decay()
        assert len(events) >= 1
        assert events[0].event_type.value == "decay"
        # 衰减后置信度应该降低
        decayed = ps.get_all()[0].performance.success_rate
        assert decayed < 0.8

    def test_decay_disabled(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionConfig
        config = EvolutionConfig(auto_decay=False)
        evo = MemoryEvolution(config=config)
        metrics = evo.evolve()
        assert metrics.decays == 0


# ═══════════════════════════════════════════════════════════════
# Test: MemoryEvolution - Metrics
# ═══════════════════════════════════════════════════════════════

class TestMemoryEvolutionMetrics:
    """MemoryEvolution 指标计算."""

    def test_metrics_empty(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        evo = MemoryEvolution()
        m = evo.get_metrics()
        assert m.total_events == 0
        assert m.evolution_score == 0.0

    def test_metrics_after_evolve(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionConfig
        from datetime import datetime, timedelta, timezone

        ps = PatternStore()
        # 添加两个相似模式 (绕过去重)
        p1 = _make_pattern(pattern_id="p1", success_rate=0.7, samples=10, success_count=7)
        p2 = _make_pattern(pattern_id="p2", success_rate=0.9, samples=10, success_count=9)

        # 添加一个旧模式用于衰减 (不同 action_type 避免去重)
        p3 = _make_pattern(
            pattern_id="p3", action_type="scale_winner",
            success_rate=0.6, samples=5, success_count=3,
        )
        old_date = datetime.now(timezone.utc) - timedelta(days=60)
        p3.performance.last_seen = old_date.isoformat()

        ps._patterns.append(p1)
        ps._patterns.append(p2)
        ps._patterns.append(p3)

        config = EvolutionConfig(
            min_confidence_improvement=0.0,
            decay_days=30,
            auto_consolidate=True,
            auto_decay=True,
            auto_cross_reference=True,
        )
        evo = MemoryEvolution(pattern_store=ps, config=config)
        metrics = evo.evolve()

        assert metrics.total_events >= 1
        assert metrics.consolidations >= 1  # 合并了 p1+p2
        assert metrics.decays >= 1  # 衰减了 p3

    def test_evolution_score_with_events(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import (
            EvolutionEvent, EvolutionEventType, EvolutionTarget,
        )
        evo = MemoryEvolution()
        # 手动添加升级事件
        evo._history = [
            EvolutionEvent(
                event_type=EvolutionEventType.UPGRADE,
                target_type=EvolutionTarget.PATTERN,
                before_state={"confidence": 0.7},
                after_state={"confidence": 0.85},
                delta={"confidence": 0.15},
            ),
            EvolutionEvent(
                event_type=EvolutionEventType.UPGRADE,
                target_type=EvolutionTarget.PATTERN,
                before_state={"confidence": 0.6},
                after_state={"confidence": 0.75},
                delta={"confidence": 0.15},
            ),
        ]
        m = evo.get_metrics()
        assert m.upgrades == 2
        assert m.avg_confidence_before == 0.65
        assert m.avg_confidence_after == 0.8
        assert m.evolution_score > 0


# ═══════════════════════════════════════════════════════════════
# Test: MemoryEvolution - History
# ═══════════════════════════════════════════════════════════════

class TestMemoryEvolutionHistory:
    """MemoryEvolution 历史记录."""

    def test_history_empty(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        evo = MemoryEvolution()
        assert evo.get_history() == []

    def test_history_after_evolve(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionConfig

        ps = PatternStore()
        p1 = _make_pattern(pattern_id="p1", success_rate=0.7, samples=10, success_count=7)
        p2 = _make_pattern(pattern_id="p2", success_rate=0.9, samples=10, success_count=9)
        ps._patterns.append(p1)
        ps._patterns.append(p2)

        config = EvolutionConfig(min_confidence_improvement=0.0)
        evo = MemoryEvolution(pattern_store=ps, config=config)
        evo.evolve()

        history = evo.get_history()
        assert len(history) >= 1

    def test_history_by_type(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import (
            EvolutionEvent, EvolutionEventType, EvolutionTarget,
        )
        evo = MemoryEvolution()
        evo._history = [
            EvolutionEvent(event_type=EvolutionEventType.UPGRADE, target_type=EvolutionTarget.PATTERN),
            EvolutionEvent(event_type=EvolutionEventType.DECAY, target_type=EvolutionTarget.PATTERN),
            EvolutionEvent(event_type=EvolutionEventType.UPGRADE, target_type=EvolutionTarget.STRATEGY),
        ]
        assert len(evo.get_history_by_type(EvolutionEventType.UPGRADE)) == 2
        assert len(evo.get_history_by_type(EvolutionEventType.DECAY)) == 1
        assert len(evo.get_history_by_type(EvolutionEventType.CONSOLIDATE)) == 0

    def test_clear_history(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import (
            EvolutionEvent, EvolutionEventType, EvolutionTarget,
        )
        evo = MemoryEvolution()
        evo._history = [EvolutionEvent(event_type=EvolutionEventType.UPGRADE, target_type=EvolutionTarget.PATTERN)]
        evo.clear_history()
        assert evo.history_count == 0

    def test_history_limit(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import (
            EvolutionEvent, EvolutionEventType, EvolutionTarget,
        )
        evo = MemoryEvolution()
        for i in range(50):
            evo._history.append(EvolutionEvent(
                event_type=EvolutionEventType.UPGRADE,
                target_type=EvolutionTarget.PATTERN,
            ))
        assert len(evo.get_history(limit=10)) == 10


# ═══════════════════════════════════════════════════════════════
# Test: MemoryEvolution - Summary
# ═══════════════════════════════════════════════════════════════

class TestMemoryEvolutionSummary:
    """MemoryEvolution summary."""

    def test_summary_empty(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        evo = MemoryEvolution()
        s = evo.summary()
        assert "Memory Evolution Summary" in s
        assert "Total Events:       0" in s

    def test_summary_with_events(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionConfig

        ps = PatternStore()
        p1 = _make_pattern(pattern_id="p1", success_rate=0.7, samples=10, success_count=7)
        p2 = _make_pattern(pattern_id="p2", success_rate=0.9, samples=10, success_count=9)
        ps._patterns.append(p1)
        ps._patterns.append(p2)

        config = EvolutionConfig(min_confidence_improvement=0.0)
        evo = MemoryEvolution(pattern_store=ps, config=config)
        evo.evolve()

        s = evo.summary()
        assert "Evolution Score" in s


# ═══════════════════════════════════════════════════════════════
# Test: MemoryEvolution - Strategy Evolution
# ═══════════════════════════════════════════════════════════════

class TestMemoryEvolutionStrategyEvolution:
    """MemoryEvolution 策略进化."""

    def test_evolve_strategies_links_patterns(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyStep

        ps = PatternStore()
        sm = StrategyMemory(ExperienceStore())

        # 添加高质量模式
        p = _make_pattern(pattern_id="p1", action_type="scale_winner", success_rate=0.85, samples=20, success_count=17)
        ps.store(p)

        # 添加策略，步骤没有 pattern_id
        strategy = _make_strategy(
            strategy_id="s1",
            steps=[
                StrategyStep(order=1, action_type="clone_dna"),
                StrategyStep(order=2, action_type="scale_winner"),  # 无 pattern_id
            ],
        )
        sm.store(strategy)

        evo = MemoryEvolution(pattern_store=ps, strategy_memory=sm)
        events = evo._evolve_strategies()

        assert len(events) >= 1
        # 策略步骤应该被链接到 pattern
        updated = sm.get_all()[0]
        assert updated.steps[1].pattern_id == "p1"

    def test_evolve_strategies_no_matching_pattern(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore

        ps = PatternStore()
        sm = StrategyMemory(ExperienceStore())

        # 添加不匹配的模式
        p = _make_pattern(pattern_id="p1", action_type="other_action", success_rate=0.85, samples=20)
        ps.store(p)

        strategy = _make_strategy()
        sm.store(strategy)

        evo = MemoryEvolution(pattern_store=ps, strategy_memory=sm)
        events = evo._evolve_strategies()
        assert events == []  # 没有匹配的模式

    def test_evolve_strategies_auto_approval(self):
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyStep

        ps = PatternStore()
        sm = StrategyMemory(ExperienceStore())

        # 高质量模式 (>0.7 success rate)
        p = _make_pattern(pattern_id="p1", action_type="scale_winner", success_rate=0.85, samples=20, success_count=17)
        ps.store(p)

        strategy = _make_strategy(
            strategy_id="s1",
            steps=[
                StrategyStep(order=1, action_type="scale_winner", pattern_id="p1", approval_level="manual"),
            ],
        )
        sm.store(strategy)

        evo = MemoryEvolution(pattern_store=ps, strategy_memory=sm)
        evo._evolve_strategies()

        updated = sm.get_all()[0]
        assert updated.steps[0].approval_level == "auto"


# ═══════════════════════════════════════════════════════════════
# Test: Integration
# ═══════════════════════════════════════════════════════════════

class TestIntegration:
    """集成测试."""

    def test_full_evolution_cycle(self):
        """完整进化周期: 模式合并 + 知识图谱 + 指标."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionConfig
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyStep

        ps = PatternStore()
        sm = StrategyMemory(ExperienceStore())
        exp_store = ExperienceStore()

        # 添加两个相似模式 (触发合并，绕过去重)
        p1 = _make_pattern(pattern_id="p1", action_type="clone_dna", success_rate=0.7, samples=10, success_count=7)
        p2 = _make_pattern(pattern_id="p2", action_type="clone_dna", success_rate=0.9, samples=10, success_count=9)
        ps._patterns.append(p1)
        ps._patterns.append(p2)

        # 添加策略
        strategy = _make_strategy(
            strategy_id="s1",
            steps=[
                StrategyStep(order=1, action_type="clone_dna"),
                StrategyStep(order=2, action_type="scale_winner"),
            ],
        )
        sm.store(strategy)

        config = EvolutionConfig(min_confidence_improvement=0.0)
        evo = MemoryEvolution(
            pattern_store=ps,
            strategy_memory=sm,
            config=config,
        )

        # 执行进化
        metrics = evo.evolve(exp_store)

        # 验证
        assert metrics.total_events >= 1
        assert metrics.consolidations >= 1  # 合并了 p1+p2
        assert metrics.cross_references >= 1  # 建立了跨层引用

        # 验证知识图谱
        kg = evo.get_knowledge_graph()
        assert kg.cross_references >= 1

        # 验证 summary
        summary = evo.summary()
        assert "Memory Evolution Summary" in summary

    def test_evolution_with_experience_upgrade(self):
        """进化 + 经验升级完整流程."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionConfig

        ps = PatternStore()
        exp_store = ExperienceStore()

        # 已有模式: 成功率 0.7
        p = _make_pattern(
            pattern_id="p1", action_type="increase_budget",
            success_rate=0.7, samples=10, success_count=7,
        )
        ps.store(p)

        # 新经验: 全部成功
        for i in range(10):
            exp_store.store(_make_experience(
                action_type="increase_budget",
                opportunity_type="creative_scale",
                entity_id=f"c{i:03d}",
                success=True, reward=0.9,
            ))

        config = EvolutionConfig(min_confidence_improvement=0.0)
        evo = MemoryEvolution(pattern_store=ps, config=config)
        metrics = evo.evolve(exp_store)

        # 应该有升级事件
        assert metrics.upgrades >= 1

        # 验证模式被升级
        updated = ps.get_all()[0]
        assert updated.performance.samples > 10  # 增加了新经验
        assert updated.performance.success_rate > 0.7  # 成功率提升

    def test_evolution_config_controls(self):
        """进化配置控制测试."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionConfig

        ps = PatternStore()
        p1 = _make_pattern(pattern_id="p1", success_rate=0.7, samples=10, success_count=7)
        p2 = _make_pattern(pattern_id="p2", success_rate=0.9, samples=10, success_count=9)
        ps._patterns.append(p1)
        ps._patterns.append(p2)

        # 禁用合并
        config = EvolutionConfig(auto_consolidate=False)
        evo = MemoryEvolution(pattern_store=ps, config=config)
        metrics = evo.evolve()
        assert metrics.consolidations == 0
        # 模式应该保持不变
        assert len(ps.get_all()) == 2

    def test_knowledge_graph_after_full_evolution(self):
        """全量进化后知识图谱完整性."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.memory_evolution import MemoryEvolution
        from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import PatternStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_memory import StrategyMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.failure_memory import FailureMemory
        from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import ExperienceStore
        from market_ops.creative_vision_runtime.growth_runtime.memory.evolution_models import EvolutionConfig
        from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import StrategyStep

        ps = PatternStore()
        sm = StrategyMemory(ExperienceStore())
        fm = FailureMemory(ExperienceStore())
        exp_store = ExperienceStore()

        # 添加模式
        p = _make_pattern(pattern_id="p1", action_type="scale_winner", success_rate=0.8, samples=20, success_count=16)
        ps.store(p)

        # 添加引用该模式的策略
        strategy = _make_strategy(
            strategy_id="s1",
            steps=[
                StrategyStep(order=1, action_type="clone_dna"),
                StrategyStep(order=2, action_type="scale_winner", pattern_id="p1"),
            ],
        )
        sm.store(strategy)

        config = EvolutionConfig(min_confidence_improvement=0.0)
        evo = MemoryEvolution(
            pattern_store=ps,
            strategy_memory=sm,
            failure_memory=fm,
            config=config,
        )
        evo.evolve(exp_store)

        kg = evo.get_knowledge_graph()
        assert kg.cross_references >= 1
        assert "p1" in kg.pattern_to_strategies
        assert "s1" in kg.strategy_to_patterns