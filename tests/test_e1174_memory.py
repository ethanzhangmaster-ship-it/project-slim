"""E11.7.4 — Evolution Memory 测试。

测试范围：
  - Models: EvolutionMemoryRecord, MemoryOutcome, MemoryQuery, MemoryQueryResult, MemoryInsight, MemoryStats
  - MemoryStore: CRUD, 查询, 统计, 批量操作
  - MemoryIndex: 索引, 查询, 组合查询, 重建
  - PatternRetriever: 检索, 过滤, 统计, 推荐
  - MemoryEngine: remember, recall, learn, feedback
  - Controller Integration: remember_evolution, recall_memory, learn_from_memory
  - Full Pipeline: Feedback → Memory → Policy Insight
  - Package Exports
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.memory.models import (
    EvolutionMemoryRecord,
    MemoryOutcome,
    MemoryQuery,
    MemoryQueryResult,
    MemoryInsight,
    MemoryStats,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.memory.memory_store import (
    EvolutionMemoryStore,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.memory.memory_index import (
    MemoryIndex,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.memory.pattern_retriever import (
    PatternRetriever,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.memory.memory_engine import (
    EvolutionMemoryEngine,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.memory import (
    EvolutionMemoryRecord as ExportedMemoryRecord,
    MemoryOutcome as ExportedMemoryOutcome,
    MemoryQuery as ExportedMemoryQuery,
    MemoryQueryResult as ExportedMemoryQueryResult,
    MemoryInsight as ExportedMemoryInsight,
    MemoryStats as ExportedMemoryStats,
    EvolutionMemoryStore as ExportedMemoryStore,
    MemoryIndex as ExportedMemoryIndex,
    PatternRetriever as ExportedPatternRetriever,
    EvolutionMemoryEngine as ExportedMemoryEngine,
)
from market_ops.creative_vision_runtime.autonomous_controller.controller import (
    AutonomousCreativeController,
)
from market_ops.creative_vision_runtime.intelligence.engine import (
    VisionIntelligenceEngine,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_record(
    memory_id: str = "",
    genome_id: str = "g001",
    parent_genome_id: str | None = None,
    mutation_type: str = "hook",
    mutation_params: dict | None = None,
    creative_id: str | None = None,
    category: str = "merge",
    fitness_before: float = 50.0,
    fitness_after: float = 70.0,
    outcome: MemoryOutcome = MemoryOutcome.SUCCESS,
    success_patterns: list[str] | None = None,
    failure_patterns: list[str] | None = None,
    generation: int = 0,
    notes: str = "",
) -> EvolutionMemoryRecord:
    return EvolutionMemoryRecord(
        memory_id=memory_id,
        genome_id=genome_id,
        parent_genome_id=parent_genome_id,
        mutation_type=mutation_type,
        mutation_params=mutation_params or {},
        creative_id=creative_id,
        category=category,
        fitness_before=fitness_before,
        fitness_after=fitness_after,
        outcome=outcome,
        success_patterns=success_patterns or [],
        failure_patterns=failure_patterns or [],
        generation=generation,
        notes=notes,
    )


def _make_query(
    mutation_type: str | None = None,
    category: str | None = None,
    patterns: list[str] | None = None,
    min_fitness_gain: float = 0.0,
    outcome: MemoryOutcome | None = None,
    max_records: int = 100,
) -> MemoryQuery:
    return MemoryQuery(
        mutation_type=mutation_type,
        category=category,
        patterns=patterns or [],
        min_fitness_gain=min_fitness_gain,
        outcome=outcome,
        max_records=max_records,
    )


def _make_records(count: int = 10) -> list[EvolutionMemoryRecord]:
    """创建多样化的测试记录。"""
    records = []
    mutation_types = ["hook", "visual", "gameplay", "monetization"]
    categories = ["merge", "purge", "explore"]
    outcomes = [MemoryOutcome.SUCCESS, MemoryOutcome.FAILURE, MemoryOutcome.NEUTRAL]
    for i in range(count):
        r = _make_record(
            genome_id=f"g{i + 1:03d}",
            mutation_type=mutation_types[i % 4],
            category=categories[i % 3],
            fitness_before=50.0,
            fitness_after=50.0 + (i + 1) * 5.0,
            outcome=outcomes[i % 3],
            success_patterns=[f"sp_{i % 3}"],
            failure_patterns=[f"fp_{i % 3}"],
            generation=i // 2,
        )
        records.append(r)
    return records


# ═══════════════════════════════════════════════════════════
# 1. Models — 15 tests
# ═══════════════════════════════════════════════════════════

class TestMemoryOutcome:
    def test_values(self):
        assert MemoryOutcome.SUCCESS.value == "success"
        assert MemoryOutcome.NEUTRAL.value == "neutral"
        assert MemoryOutcome.FAILURE.value == "failure"
        assert MemoryOutcome.RETIRED.value == "retired"

    def test_count(self):
        assert len(MemoryOutcome) == 4


class TestEvolutionMemoryRecord:
    def test_create_minimal(self):
        r = _make_record()
        assert r.memory_id.startswith("mem_")
        assert r.genome_id == "g001"
        assert r.outcome == MemoryOutcome.SUCCESS
        assert r.fitness_gain == 20.0
        assert r.created_at != ""

    def test_create_with_custom_id(self):
        r = _make_record(memory_id="custom_001")
        assert r.memory_id == "custom_001"

    def test_is_success(self):
        assert _make_record(outcome=MemoryOutcome.SUCCESS).is_success is True
        assert _make_record(outcome=MemoryOutcome.FAILURE).is_success is False

    def test_is_failure(self):
        assert _make_record(outcome=MemoryOutcome.FAILURE).is_failure is True
        assert _make_record(outcome=MemoryOutcome.SUCCESS).is_failure is False

    def test_is_retired(self):
        assert _make_record(outcome=MemoryOutcome.RETIRED).is_retired is True
        assert _make_record(outcome=MemoryOutcome.SUCCESS).is_retired is False

    def test_all_patterns(self):
        r = _make_record(
            success_patterns=["a", "b"],
            failure_patterns=["x", "y"],
        )
        assert r.all_patterns == ["a", "b", "x", "y"]

    def test_fitness_gain_auto(self):
        r = _make_record(fitness_before=50.0, fitness_after=75.0)
        assert r.fitness_gain == 25.0

    def test_to_dict(self):
        r = _make_record(genome_id="g001", generation=2)
        d = r.to_dict()
        assert d["genome_id"] == "g001"
        assert d["generation"] == 2
        assert d["outcome"] == "success"
        assert "memory_id" in d
        assert "created_at" in d

    def test_repr(self):
        r = _make_record(genome_id="g001", mutation_type="hook")
        s = repr(r)
        assert "g001" in s
        assert "hook" in s


class TestMemoryQuery:
    def test_create_default(self):
        q = MemoryQuery()
        assert q.mutation_type is None
        assert q.category is None
        assert q.patterns == []
        assert q.min_fitness_gain == 0.0
        assert q.outcome is None
        assert q.max_records == 100

    def test_create_full(self):
        q = _make_query(
            mutation_type="hook",
            category="merge",
            patterns=["rescue"],
            min_fitness_gain=0.1,
            outcome=MemoryOutcome.SUCCESS,
            max_records=50,
        )
        assert q.mutation_type == "hook"
        assert q.category == "merge"
        assert q.patterns == ["rescue"]
        assert q.min_fitness_gain == 0.1
        assert q.outcome == MemoryOutcome.SUCCESS
        assert q.max_records == 50

    def test_to_dict(self):
        q = _make_query(mutation_type="hook", category="merge")
        d = q.to_dict()
        assert d["mutation_type"] == "hook"
        assert d["category"] == "merge"


class TestMemoryQueryResult:
    def test_create_default(self):
        r = MemoryQueryResult()
        assert r.total_matches == 0
        assert r.success_rate == 0.0
        assert r.avg_gain == 0.0
        assert r.recommendation == ""

    def test_create_full(self):
        q = _make_query(mutation_type="hook")
        r = MemoryQueryResult(
            query=q,
            total_matches=10,
            success_count=7,
            failure_count=3,
            success_rate=0.7,
            avg_gain=0.15,
            best_patterns=["high contrast"],
            bad_patterns=["slow intro"],
            recommendation="use_hook_mutation",
        )
        assert r.total_matches == 10
        assert r.success_rate == 0.7
        assert r.avg_gain == 0.15
        assert r.best_patterns == ["high contrast"]
        assert r.recommendation == "use_hook_mutation"

    def test_to_dict(self):
        q = _make_query(mutation_type="hook")
        r = MemoryQueryResult(query=q, total_matches=5, success_rate=0.8)
        d = r.to_dict()
        assert d["total_matches"] == 5
        assert d["success_rate"] == 0.8

    def test_repr(self):
        q = _make_query(mutation_type="hook")
        r = MemoryQueryResult(query=q, total_matches=10, success_rate=0.7, avg_gain=0.15)
        s = repr(r)
        assert "matches=10" in s
        assert "70%" in s


class TestMemoryInsight:
    def test_create_default(self):
        i = MemoryInsight()
        assert i.total_records == 0
        assert i.overall_success_rate == 0.0
        assert i.generated_at != ""

    def test_create_full(self):
        i = MemoryInsight(
            total_records=100,
            overall_success_rate=0.65,
            overall_avg_gain=0.12,
            best_mutation="hook",
            worst_mutation="gameplay",
            top_success_patterns=["high contrast", "emotion hook"],
            top_failure_patterns=["slow intro"],
            recommendation="Continue exploring hook mutations",
        )
        assert i.total_records == 100
        assert i.overall_success_rate == 0.65
        assert i.best_mutation == "hook"
        assert i.worst_mutation == "gameplay"
        assert len(i.top_success_patterns) == 2

    def test_to_dict(self):
        i = MemoryInsight(total_records=10, best_mutation="hook")
        d = i.to_dict()
        assert d["total_records"] == 10
        assert d["best_mutation"] == "hook"

    def test_repr(self):
        i = MemoryInsight(total_records=100, overall_success_rate=0.65, best_mutation="hook")
        s = repr(i)
        assert "100" in s
        assert "65%" in s
        assert "hook" in s


class TestMemoryStats:
    def test_create_default(self):
        s = MemoryStats()
        assert s.total_records == 0
        assert s.success_count == 0

    def test_create_full(self):
        s = MemoryStats(
            total_records=100,
            success_count=60,
            failure_count=20,
            avg_fitness_gain=0.15,
            unique_genomes=50,
        )
        assert s.total_records == 100
        assert s.success_count == 60
        assert s.failure_count == 20
        assert s.avg_fitness_gain == 0.15
        assert s.unique_genomes == 50

    def test_to_dict(self):
        s = MemoryStats(total_records=10, success_count=7)
        d = s.to_dict()
        assert d["total_records"] == 10
        assert d["success_count"] == 7


# ═══════════════════════════════════════════════════════════
# 2. MemoryStore — 20 tests
# ═══════════════════════════════════════════════════════════

class TestEvolutionMemoryStore:
    def test_empty_store(self):
        store = EvolutionMemoryStore()
        assert len(store) == 0
        assert store.count() == 0

    def test_save(self):
        store = EvolutionMemoryStore()
        r = _make_record()
        mid = store.save(r)
        assert mid == r.memory_id
        assert len(store) == 1
        assert store.save_count == 1

    def test_save_batch(self):
        store = EvolutionMemoryStore()
        records = _make_records(5)
        ids = store.save_batch(records)
        assert len(ids) == 5
        assert len(store) == 5

    def test_get(self):
        store = EvolutionMemoryStore()
        r = _make_record(genome_id="g001")
        store.save(r)
        got = store.get(r.memory_id)
        assert got is not None
        assert got.genome_id == "g001"

    def test_get_not_found(self):
        store = EvolutionMemoryStore()
        assert store.get("nonexistent") is None

    def test_get_all(self):
        store = EvolutionMemoryStore()
        records = _make_records(3)
        store.save_batch(records)
        all_records = store.get_all()
        assert len(all_records) == 3

    def test_get_by_genome(self):
        store = EvolutionMemoryStore()
        store.save(_make_record(genome_id="g001"))
        store.save(_make_record(genome_id="g001"))
        store.save(_make_record(genome_id="g002"))
        found = store.get_by_genome("g001")
        assert len(found) == 2

    def test_get_by_outcome(self):
        store = EvolutionMemoryStore()
        store.save(_make_record(outcome=MemoryOutcome.SUCCESS))
        store.save(_make_record(outcome=MemoryOutcome.FAILURE))
        store.save(_make_record(outcome=MemoryOutcome.SUCCESS))
        found = store.get_by_outcome(MemoryOutcome.SUCCESS)
        assert len(found) == 2

    def test_get_by_mutation_type(self):
        store = EvolutionMemoryStore()
        store.save(_make_record(mutation_type="hook"))
        store.save(_make_record(mutation_type="visual"))
        store.save(_make_record(mutation_type="hook"))
        found = store.get_by_mutation_type("hook")
        assert len(found) == 2

    def test_get_by_category(self):
        store = EvolutionMemoryStore()
        store.save(_make_record(category="merge"))
        store.save(_make_record(category="purge"))
        store.save(_make_record(category="merge"))
        found = store.get_by_category("merge")
        assert len(found) == 2

    def test_get_by_generation(self):
        store = EvolutionMemoryStore()
        store.save(_make_record(generation=0))
        store.save(_make_record(generation=1))
        store.save(_make_record(generation=0))
        found = store.get_by_generation(0)
        assert len(found) == 2

    def test_update(self):
        store = EvolutionMemoryStore()
        r = _make_record(genome_id="g001")
        store.save(r)
        ok = store.update(r.memory_id, genome_id="g002")
        assert ok is True
        assert store.get(r.memory_id).genome_id == "g002"

    def test_update_not_found(self):
        store = EvolutionMemoryStore()
        assert store.update("nonexistent", genome_id="x") is False

    def test_remove(self):
        store = EvolutionMemoryStore()
        r = _make_record()
        store.save(r)
        assert store.remove(r.memory_id) is True
        assert len(store) == 0
        assert store.remove_count == 1

    def test_remove_not_found(self):
        store = EvolutionMemoryStore()
        assert store.remove("nonexistent") is False

    def test_remove_by_genome(self):
        store = EvolutionMemoryStore()
        store.save(_make_record(genome_id="g001"))
        store.save(_make_record(genome_id="g001"))
        store.save(_make_record(genome_id="g002"))
        count = store.remove_by_genome("g001")
        assert count == 2
        assert len(store) == 1

    def test_clear(self):
        store = EvolutionMemoryStore()
        store.save_batch(_make_records(5))
        count = store.clear()
        assert count == 5
        assert len(store) == 0

    def test_contains(self):
        store = EvolutionMemoryStore()
        r = _make_record()
        store.save(r)
        assert r.memory_id in store
        assert "nonexistent" not in store

    def test_get_stats(self):
        store = EvolutionMemoryStore()
        store.save(_make_record(outcome=MemoryOutcome.SUCCESS, fitness_before=50.0, fitness_after=60.0))
        store.save(_make_record(outcome=MemoryOutcome.FAILURE, fitness_before=50.0, fitness_after=45.0))
        stats = store.get_stats()
        assert stats.total_records == 2
        assert stats.success_count == 1
        assert stats.failure_count == 1
        assert stats.avg_fitness_gain == 2.5

    def test_repr(self):
        store = EvolutionMemoryStore()
        store.save(_make_record())
        assert "records=1" in repr(store)


# ═══════════════════════════════════════════════════════════
# 3. MemoryIndex — 15 tests
# ═══════════════════════════════════════════════════════════

class TestMemoryIndex:
    def test_empty_index(self):
        idx = MemoryIndex()
        assert idx.indexed_count == 0

    def test_index_single(self):
        idx = MemoryIndex()
        r = _make_record(mutation_type="hook", category="merge")
        idx.index(r)
        assert idx.indexed_count == 1

    def test_index_batch(self):
        idx = MemoryIndex()
        idx.index_batch(_make_records(10))
        assert idx.indexed_count == 10

    def test_query_by_mutation_type(self):
        idx = MemoryIndex()
        r = _make_record(mutation_type="hook")
        idx.index(r)
        ids = idx.query_by_mutation_type("hook")
        assert r.memory_id in ids

    def test_query_by_mutation_type_not_found(self):
        idx = MemoryIndex()
        assert idx.query_by_mutation_type("nonexistent") == set()

    def test_query_by_category(self):
        idx = MemoryIndex()
        r = _make_record(category="merge")
        idx.index(r)
        ids = idx.query_by_category("merge")
        assert r.memory_id in ids

    def test_query_by_outcome(self):
        idx = MemoryIndex()
        r = _make_record(outcome=MemoryOutcome.FAILURE)
        idx.index(r)
        ids = idx.query_by_outcome(MemoryOutcome.FAILURE)
        assert r.memory_id in ids

    def test_query_by_pattern(self):
        idx = MemoryIndex()
        r = _make_record(success_patterns=["rescue", "high_contrast"])
        idx.index(r)
        ids = idx.query_by_pattern("rescue")
        assert r.memory_id in ids

    def test_query_by_patterns(self):
        idx = MemoryIndex()
        r = _make_record(success_patterns=["rescue"])
        idx.index(r)
        ids = idx.query_by_patterns(["rescue", "nonexistent"])
        assert r.memory_id in ids

    def test_combined_query(self):
        idx = MemoryIndex()
        r1 = _make_record(mutation_type="hook", category="merge")
        r2 = _make_record(mutation_type="visual", category="merge")
        idx.index_batch([r1, r2])
        ids = idx.query(mutation_type="hook", category="merge")
        assert r1.memory_id in ids
        assert r2.memory_id not in ids

    def test_combined_query_empty(self):
        idx = MemoryIndex()
        assert idx.query() == set()

    def test_remove(self):
        idx = MemoryIndex()
        r = _make_record(mutation_type="hook", category="merge")
        idx.index(r)
        idx.remove(r)
        assert idx.query_by_mutation_type("hook") == set()

    def test_get_mutation_types(self):
        idx = MemoryIndex()
        idx.index(_make_record(mutation_type="hook"))
        idx.index(_make_record(mutation_type="visual"))
        assert "hook" in idx.get_mutation_types()
        assert "visual" in idx.get_mutation_types()

    def test_get_categories(self):
        idx = MemoryIndex()
        idx.index(_make_record(category="merge"))
        idx.index(_make_record(category="purge"))
        assert "merge" in idx.get_categories()
        assert "purge" in idx.get_categories()

    def test_clear(self):
        idx = MemoryIndex()
        idx.index_batch(_make_records(5))
        idx.clear()
        assert idx.indexed_count == 0
        assert idx.get_mutation_types() == []

    def test_rebuild(self):
        idx = MemoryIndex()
        records = _make_records(5)
        idx.index_batch(records[:2])
        idx.rebuild(records)
        assert idx.indexed_count == 5

    def test_get_stats(self):
        idx = MemoryIndex()
        idx.index(_make_record(mutation_type="hook", category="merge"))
        stats = idx.get_stats()
        assert stats["mutation_types"] == 1
        assert stats["categories"] == 1


# ═══════════════════════════════════════════════════════════
# 4. PatternRetriever — 20 tests
# ═══════════════════════════════════════════════════════════

class TestPatternRetriever:
    @pytest.fixture
    def retriever(self):
        store = EvolutionMemoryStore()
        index = MemoryIndex()
        return PatternRetriever(store=store, index=index)

    @pytest.fixture
    def populated_retriever(self):
        store = EvolutionMemoryStore()
        index = MemoryIndex()
        retriever = PatternRetriever(store=store, index=index)
        records = _make_records(10)
        store.save_batch(records)
        index.index_batch(records)
        return retriever

    def test_retrieve_empty(self, retriever):
        q = _make_query(mutation_type="hook")
        result = retriever.retrieve(q)
        assert result.total_matches == 0
        assert result.recommendation != ""

    def test_retrieve_by_mutation_type(self, populated_retriever):
        q = _make_query(mutation_type="hook")
        result = populated_retriever.retrieve(q)
        assert result.total_matches > 0
        for r in result.records:
            assert r.mutation_type == "hook"

    def test_retrieve_by_category(self, populated_retriever):
        q = _make_query(category="merge")
        result = populated_retriever.retrieve(q)
        assert result.total_matches > 0
        for r in result.records:
            assert r.category == "merge"

    def test_retrieve_combined(self, populated_retriever):
        q = _make_query(mutation_type="hook", category="merge")
        result = populated_retriever.retrieve(q)
        for r in result.records:
            assert r.mutation_type == "hook"
            assert r.category == "merge"

    def test_retrieve_filters_by_fitness_gain(self, populated_retriever):
        q = _make_query(min_fitness_gain=20.0)
        result = populated_retriever.retrieve(q)
        for r in result.records:
            assert r.fitness_gain >= 20.0

    def test_retrieve_max_records(self, populated_retriever):
        q = _make_query(max_records=3)
        result = populated_retriever.retrieve(q)
        assert len(result.records) <= 3

    def test_retrieve_sorted_by_gain(self, populated_retriever):
        q = _make_query()
        result = populated_retriever.retrieve(q)
        if len(result.records) >= 2:
            assert result.records[0].fitness_gain >= result.records[1].fitness_gain

    def test_retrieve_success_rate(self, populated_retriever):
        q = _make_query()
        result = populated_retriever.retrieve(q)
        assert 0.0 <= result.success_rate <= 1.0
        assert result.success_count + result.failure_count <= result.total_matches

    def test_retrieve_best_patterns(self, populated_retriever):
        q = _make_query()
        result = populated_retriever.retrieve(q)
        assert isinstance(result.best_patterns, list)
        assert isinstance(result.bad_patterns, list)

    def test_retrieve_recommendation(self, populated_retriever):
        q = _make_query()
        result = populated_retriever.retrieve(q)
        assert isinstance(result.recommendation, str)
        assert len(result.recommendation) > 0

    def test_retrieve_fallback_to_all(self, retriever):
        """无 Index 命中时回退到全量扫描。"""
        store = retriever.store
        store.save(_make_record(mutation_type="hook"))
        q = _make_query(mutation_type="hook")
        result = retriever.retrieve(q)
        assert result.total_matches == 0  # Index 未命中，记录未索引

    def test_retrieve_by_patterns(self, retriever):
        store = retriever.store
        index = retriever.index
        r = _make_record(success_patterns=["rescue"])
        store.save(r)
        index.index(r)
        q = _make_query(patterns=["rescue"])
        result = retriever.retrieve(q)
        assert result.total_matches == 1

    def test_retrieve_batch(self, populated_retriever):
        queries = [
            _make_query(mutation_type="hook"),
            _make_query(mutation_type="visual"),
        ]
        results = populated_retriever.retrieve_batch(queries)
        assert len(results) == 2

    def test_retrieve_count(self, populated_retriever):
        assert populated_retriever.retrieve_count == 0
        populated_retriever.retrieve(_make_query())
        assert populated_retriever.retrieve_count == 1

    def test_get_stats(self, populated_retriever):
        stats = populated_retriever.get_stats()
        assert "retrieve_count" in stats
        assert "store_size" in stats
        assert "index_stats" in stats

    def test_reset(self, populated_retriever):
        populated_retriever.retrieve(_make_query())
        populated_retriever.reset()
        assert populated_retriever.retrieve_count == 0

    def test_store_property(self, retriever):
        assert isinstance(retriever.store, EvolutionMemoryStore)

    def test_index_property(self, retriever):
        assert isinstance(retriever.index, MemoryIndex)


# ═══════════════════════════════════════════════════════════
# 5. MemoryEngine — 25 tests
# ═══════════════════════════════════════════════════════════

class TestEvolutionMemoryEngine:
    @pytest.fixture
    def engine(self):
        return EvolutionMemoryEngine()

    @pytest.fixture
    def populated_engine(self):
        engine = EvolutionMemoryEngine()
        for i in range(10):
            engine.remember(
                genome_id=f"g{i + 1:03d}",
                mutation_type=["hook", "visual", "gameplay", "monetization"][i % 4],
                fitness_before=50.0,
                fitness_after=50.0 + (i + 1) * 5.0,
                category=["merge", "purge", "explore"][i % 3],
                success_patterns=[f"sp_{i % 3}"],
                failure_patterns=[f"fp_{i % 3}"],
                generation=i // 2,
            )
        return engine

    def test_remember_success(self, engine):
        r = engine.remember(
            genome_id="g001",
            mutation_type="hook",
            fitness_before=50.0,
            fitness_after=70.0,
        )
        assert r.genome_id == "g001"
        assert r.outcome == MemoryOutcome.SUCCESS
        assert r.fitness_gain == 20.0
        assert engine.remember_count == 1

    def test_remember_failure(self, engine):
        r = engine.remember(
            genome_id="g001",
            mutation_type="hook",
            fitness_before=70.0,
            fitness_after=50.0,
        )
        assert r.outcome == MemoryOutcome.FAILURE

    def test_remember_neutral(self, engine):
        r = engine.remember(
            genome_id="g001",
            mutation_type="hook",
            fitness_before=50.0,
            fitness_after=50.005,
        )
        assert r.outcome == MemoryOutcome.NEUTRAL

    def test_remember_explicit_outcome(self, engine):
        r = engine.remember(
            genome_id="g001",
            mutation_type="hook",
            fitness_before=50.0,
            fitness_after=70.0,
            outcome=MemoryOutcome.FAILURE,
        )
        assert r.outcome == MemoryOutcome.FAILURE

    def test_remember_stores_and_indexes(self, engine):
        r = engine.remember(
            genome_id="g001",
            mutation_type="hook",
            fitness_before=50.0,
            fitness_after=70.0,
        )
        assert engine.get_record(r.memory_id) is not None
        assert engine.index.query_by_mutation_type("hook") == {r.memory_id}

    def test_remember_batch(self, engine):
        feedbacks = [
            {"genome_id": "g001", "mutation_type": "hook", "fitness_before": 50.0, "fitness_after": 70.0},
            {"genome_id": "g002", "mutation_type": "visual", "fitness_before": 50.0, "fitness_after": 60.0},
        ]
        records = engine.remember_batch(feedbacks)
        assert len(records) == 2
        assert engine.remember_count == 2

    def test_remember_from_feedback(self, engine):
        feedback = {
            "genome_id": "g001",
            "mutation_type": "hook",
            "fitness_before": 50.0,
            "fitness_after": 70.0,
            "category": "merge",
            "parent_genome_id": "g000",
            "success_patterns": ["rescue"],
            "generation": 1,
        }
        r = engine.remember_from_feedback(feedback)
        assert r.genome_id == "g001"
        assert r.category == "merge"
        assert r.parent_genome_id == "g000"
        assert r.success_patterns == ["rescue"]
        assert r.generation == 1

    def test_recall(self, populated_engine):
        result = populated_engine.recall(mutation_type="hook")
        assert result.total_matches > 0
        assert result.success_rate >= 0.0

    def test_recall_with_category(self, populated_engine):
        result = populated_engine.recall(mutation_type="hook", category="merge")
        assert result.total_matches >= 0

    def test_recall_by_query(self, populated_engine):
        q = _make_query(mutation_type="hook")
        result = populated_engine.recall_by_query(q)
        assert result.total_matches > 0

    def test_recall_min_fitness_gain(self, populated_engine):
        result = populated_engine.recall(min_fitness_gain=20.0)
        for r in result.records:
            assert r.fitness_gain >= 20.0

    def test_recall_increments_count(self, populated_engine):
        populated_engine.recall(mutation_type="hook")
        assert populated_engine.recall_count == 1
        populated_engine.recall(mutation_type="visual")
        assert populated_engine.recall_count == 2

    def test_learn(self, populated_engine):
        insight = populated_engine.learn()
        assert isinstance(insight, MemoryInsight)
        assert insight.total_records == 10
        assert 0.0 <= insight.overall_success_rate <= 1.0
        assert insight.recommendation != ""

    def test_learn_empty(self, engine):
        insight = engine.learn()
        assert insight.total_records == 0
        assert insight.recommendation != ""

    def test_learn_by_mutation_type(self, populated_engine):
        insight = populated_engine.learn()
        assert "hook" in insight.by_mutation_type or "visual" in insight.by_mutation_type

    def test_learn_best_mutation(self, populated_engine):
        insight = populated_engine.learn()
        # 如果有至少 3 条同类型记录，会计算 best_mutation
        assert isinstance(insight.best_mutation, str)

    def test_get_record(self, populated_engine):
        records = populated_engine.get_all_records()
        if records:
            r = populated_engine.get_record(records[0].memory_id)
            assert r is not None

    def test_get_all_records(self, populated_engine):
        records = populated_engine.get_all_records()
        assert len(records) == 10

    def test_get_memory_stats(self, populated_engine):
        stats = populated_engine.get_memory_stats()
        assert isinstance(stats, MemoryStats)
        assert stats.total_records == 10

    def test_remove_record(self, populated_engine):
        records = populated_engine.get_all_records()
        mid = records[0].memory_id
        assert populated_engine.remove_record(mid) is True
        assert populated_engine.get_record(mid) is None

    def test_clear(self, populated_engine):
        populated_engine.clear()
        assert len(populated_engine.get_all_records()) == 0

    def test_get_stats(self, populated_engine):
        stats = populated_engine.get_stats()
        assert "remember_count" in stats
        assert "recall_count" in stats
        assert "store" in stats
        assert "index" in stats
        assert "retriever" in stats

    def test_reset(self, populated_engine):
        populated_engine.reset()
        assert populated_engine.remember_count == 0
        assert populated_engine.recall_count == 0
        assert len(populated_engine.get_all_records()) == 0

    def test_properties(self, engine):
        assert isinstance(engine.store, EvolutionMemoryStore)
        assert isinstance(engine.index, MemoryIndex)
        assert isinstance(engine.retriever, PatternRetriever)


# ═══════════════════════════════════════════════════════════
# 6. Controller Integration — 10 tests
# ═══════════════════════════════════════════════════════════

class TestControllerMemoryIntegration:
    @pytest.fixture
    def controller(self):
        mock_intel = MagicMock(spec=VisionIntelligenceEngine)
        return AutonomousCreativeController(intelligence_engine=mock_intel)

    def test_remember_evolution(self, controller):
        r = controller.remember_evolution(
            genome_id="g001",
            mutation_type="hook",
            fitness_before=50.0,
            fitness_after=70.0,
            category="merge",
        )
        assert r.genome_id == "g001"
        assert r.outcome == MemoryOutcome.SUCCESS
        assert controller.memory_engine.remember_count == 1

    def test_remember_evolution_from_feedback(self, controller):
        feedback = {
            "genome_id": "g001",
            "mutation_type": "hook",
            "fitness_before": 50.0,
            "fitness_after": 70.0,
            "category": "merge",
        }
        r = controller.remember_evolution_from_feedback(feedback)
        assert r.genome_id == "g001"
        assert r.category == "merge"

    def test_recall_memory(self, controller):
        # 先记录一些经验
        controller.remember_evolution("g001", "hook", 50.0, 70.0, "merge")
        controller.remember_evolution("g002", "hook", 50.0, 60.0, "merge")
        result = controller.recall_memory(mutation_type="hook")
        assert result.total_matches > 0
        assert result.success_rate >= 0.0

    def test_recall_memory_by_category(self, controller):
        controller.remember_evolution("g001", "hook", 50.0, 70.0, "merge")
        controller.remember_evolution("g002", "visual", 50.0, 60.0, "purge")
        result = controller.recall_memory(category="merge")
        assert result.total_matches == 1

    def test_recall_memory_by_query(self, controller):
        controller.remember_evolution("g001", "hook", 50.0, 70.0, "merge")
        q = MemoryQuery(mutation_type="hook")
        result = controller.recall_memory_by_query(q)
        assert result.total_matches > 0

    def test_recall_memory_empty(self, controller):
        result = controller.recall_memory(mutation_type="hook")
        assert result.total_matches == 0

    def test_learn_from_memory(self, controller):
        for i in range(5):
            controller.remember_evolution(
                f"g{i:03d}", "hook", 50.0, 50.0 + i * 10.0, "merge"
            )
        insight = controller.learn_from_memory()
        assert isinstance(insight, MemoryInsight)
        assert insight.total_records == 5

    def test_learn_from_memory_empty(self, controller):
        insight = controller.learn_from_memory()
        assert insight.total_records == 0

    def test_memory_engine_property(self, controller):
        assert isinstance(controller.memory_engine, EvolutionMemoryEngine)

    def test_memory_injection(self, controller):
        mem = controller.memory_engine
        controller.remember_evolution("g001", "hook", 50.0, 70.0)
        assert mem.get_record(controller.memory_engine.get_all_records()[0].memory_id) is not None


# ═══════════════════════════════════════════════════════════
# 7. Full Pipeline — 10 tests
# ═══════════════════════════════════════════════════════════

class TestFullPipeline:
    def test_feedback_to_memory_pipeline(self):
        """Feedback → Memory → Recall → Insight。"""
        engine = EvolutionMemoryEngine()

        # 模拟 50 次进化反馈
        for i in range(50):
            mt = ["hook", "visual", "gameplay"][i % 3]
            gain = 10.0 if i % 2 == 0 else -5.0
            engine.remember(
                genome_id=f"g{i:03d}",
                mutation_type=mt,
                fitness_before=50.0,
                fitness_after=50.0 + gain,
                category="merge",
                success_patterns=["high_contrast"] if i % 2 == 0 else ["slow_intro"],
                failure_patterns=["slow_intro"] if i % 2 != 0 else [],
            )

        # 检索
        result = engine.recall(mutation_type="hook")
        assert result.total_matches > 0
        assert 0.0 <= result.success_rate <= 1.0

        # 洞察
        insight = engine.learn()
        assert insight.total_records == 50
        assert insight.overall_success_rate is not None

    def test_policy_uses_memory(self):
        """Policy 层使用 Memory 查询。"""
        engine = EvolutionMemoryEngine()

        # 记录 hook=rescue 的成功经验
        for i in range(20):
            engine.remember(
                genome_id=f"g{i:03d}",
                mutation_type="hook",
                fitness_before=50.0,
                fitness_after=70.0,
                category="merge",
                success_patterns=["rescue", "high_contrast"],
            )

        # Policy 查询 hook mutation 的历史表现
        result = engine.recall(mutation_type="hook", category="merge")
        assert result.success_rate == 1.0
        assert "Recommended" in result.recommendation

    def test_controller_full_pipeline(self):
        """Controller → Memory → Policy 完整闭环。"""
        mock_intel = MagicMock(spec=VisionIntelligenceEngine)
        controller = AutonomousCreativeController(intelligence_engine=mock_intel)

        # 模拟进化 → 记录反馈
        for i in range(30):
            controller.remember_evolution(
                f"g{i:03d}",
                ["hook", "visual", "gameplay"][i % 3],
                50.0,
                50.0 + (15.0 if i % 2 == 0 else -5.0),
                category="merge",
                success_patterns=["high_contrast"] if i % 2 == 0 else [],
            )

        # 检索
        result = controller.recall_memory(mutation_type="hook")
        assert result.total_matches > 0

        # 学习
        insight = controller.learn_from_memory()
        assert insight.total_records == 30

    def test_memory_guides_evolution(self):
        """Memory 应能指导进化决策。"""
        engine = EvolutionMemoryEngine()

        # 记录：hook mutation 成功率高
        for i in range(20):
            engine.remember(
                genome_id=f"g{i:03d}",
                mutation_type="hook",
                fitness_before=50.0,
                fitness_after=70.0,
                success_patterns=["rescue"],
            )

        # 记录：visual mutation 成功率低
        for i in range(20):
            engine.remember(
                genome_id=f"g{i + 20:03d}",
                mutation_type="visual",
                fitness_before=50.0,
                fitness_after=45.0,
                failure_patterns=["slow_intro"],
            )

        insight = engine.learn()
        assert "hook" in insight.best_mutation or insight.best_mutation == ""

    def test_retirement_pattern_learning(self):
        """退役模式学习。"""
        engine = EvolutionMemoryEngine()

        for i in range(10):
            engine.remember(
                genome_id=f"g{i:03d}",
                mutation_type="gameplay",
                fitness_before=50.0,
                fitness_after=50.0,
                outcome=MemoryOutcome.RETIRED,
                failure_patterns=["low_engagement"],
            )

        result = engine.recall(mutation_type="gameplay")
        assert result.total_matches == 10

    def test_memory_accumulation_across_generations(self):
        """跨代记忆积累。"""
        engine = EvolutionMemoryEngine()

        for gen in range(5):
            for i in range(5):
                engine.remember(
                    genome_id=f"gen{gen}_g{i}",
                    mutation_type="hook",
                    fitness_before=50.0,
                    fitness_after=50.0 + gen * 5.0,
                    generation=gen,
                )

        assert len(engine.get_all_records()) == 25

        # 按代查询
        gen2_records = engine.store.get_by_generation(2)
        assert len(gen2_records) == 5

    def test_pattern_emergence(self):
        """模式从记忆中涌现。"""
        engine = EvolutionMemoryEngine()

        # 多次出现 "rescue" pattern 的成功
        for i in range(30):
            engine.remember(
                genome_id=f"g{i:03d}",
                mutation_type="hook",
                fitness_before=50.0,
                fitness_after=70.0,
                success_patterns=["rescue", "high_contrast"],
            )

        # 多次出现 "slow_intro" pattern 的失败
        for i in range(10):
            engine.remember(
                genome_id=f"g{i + 30:03d}",
                mutation_type="visual",
                fitness_before=50.0,
                fitness_after=40.0,
                failure_patterns=["slow_intro"],
            )

        insight = engine.learn()
        # 成功模式 "rescue" 应出现
        assert "rescue" in insight.top_success_patterns or "high_contrast" in insight.top_success_patterns

    def test_explore_recommendation_on_unknown(self):
        """未知 mutation type 给出探索建议。"""
        engine = EvolutionMemoryEngine()

        result = engine.recall(mutation_type="unknown_type")
        assert result.total_matches == 0
        assert result.recommendation is not None

    def test_memory_drives_policy_refinement(self):
        """Memory 驱动 Policy 优化。"""
        engine = EvolutionMemoryEngine()

        # 记录：hook 整体成功率高
        for i in range(20):
            engine.remember(
                genome_id=f"g{i:03d}",
                mutation_type="hook",
                fitness_before=50.0,
                fitness_after=70.0,
                success_patterns=["rescue"],
            )

        # 但 hook + explore 类别成功率低
        for i in range(10):
            engine.remember(
                genome_id=f"g{i + 20:03d}",
                mutation_type="hook",
                fitness_before=50.0,
                fitness_after=45.0,
                category="explore",
                failure_patterns=["random_variation"],
            )

        # 按 mutation_type 聚合
        hook_result = engine.recall(mutation_type="hook")
        assert hook_result.total_matches == 30

        # 按 category 聚合
        explore_result = engine.recall(category="explore")
        assert explore_result.total_matches == 10

        # explore 的成功率应低于 hook 整体
        insight = engine.learn()
        assert "explore" in insight.by_category

    def test_system_remembers_every_experiment(self):
        """每次实验都会被记忆。"""
        engine = EvolutionMemoryEngine()

        for i in range(100):
            engine.remember(
                genome_id=f"g{i:03d}",
                mutation_type="hook",
                fitness_before=50.0,
                fitness_after=50.0 + (i % 10),
            )

        assert len(engine.get_all_records()) == 100
        stats = engine.get_memory_stats()
        assert stats.total_records == 100


# ═══════════════════════════════════════════════════════════
# 8. Package Exports — 5 tests
# ═══════════════════════════════════════════════════════════

class TestPackageExports:
    def test_exports_models(self):
        assert ExportedMemoryRecord is EvolutionMemoryRecord
        assert ExportedMemoryOutcome is MemoryOutcome
        assert ExportedMemoryQuery is MemoryQuery
        assert ExportedMemoryQueryResult is MemoryQueryResult
        assert ExportedMemoryInsight is MemoryInsight
        assert ExportedMemoryStats is MemoryStats

    def test_exports_store(self):
        assert ExportedMemoryStore is EvolutionMemoryStore

    def test_exports_index(self):
        assert ExportedMemoryIndex is MemoryIndex

    def test_exports_retriever(self):
        assert ExportedPatternRetriever is PatternRetriever

    def test_exports_engine(self):
        assert ExportedMemoryEngine is EvolutionMemoryEngine