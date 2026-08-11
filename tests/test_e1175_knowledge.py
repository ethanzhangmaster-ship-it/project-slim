"""E11.7.5 — Evolution Knowledge Graph 测试。

测试范围:
  - Models: KnowledgeNode, NodeType, KnowledgeEdge, KnowledgePath, KnowledgeQuery, KnowledgeQueryResult, KnowledgeStats
  - GraphStore: 节点/边 CRUD, 邻居查询, 路径查找, 统计
  - KnowledgeBuilder: MemoryRecord → KnowledgeGraph 构建
  - GraphQueryEngine: 查询, 成功/失败模式, 推荐
  - KnowledgeEngine: ingest, analyze, recommend
  - Controller Integration: update_knowledge, query_knowledge
  - Full Pipeline: Memory → Knowledge → Policy
  - Package Exports
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from market_ops.creative_vision_runtime.autonomous_controller.knowledge.models import (
    KnowledgeNode,
    NodeType,
    KnowledgeEdge,
    KnowledgePath,
    KnowledgeQuery,
    KnowledgeQueryResult,
    KnowledgeStats,
)
from market_ops.creative_vision_runtime.autonomous_controller.knowledge.graph_store import (
    KnowledgeGraphStore,
)
from market_ops.creative_vision_runtime.autonomous_controller.knowledge.knowledge_builder import (
    KnowledgeBuilder,
)
from market_ops.creative_vision_runtime.autonomous_controller.knowledge.graph_query import (
    GraphQueryEngine,
)
from market_ops.creative_vision_runtime.autonomous_controller.knowledge.knowledge_engine import (
    KnowledgeEngine,
)
from market_ops.creative_vision_runtime.autonomous_controller.knowledge import (
    KnowledgeNode as ExportedNode,
    NodeType as ExportedNodeType,
    KnowledgeEdge as ExportedEdge,
    KnowledgePath as ExportedPath,
    KnowledgeQuery as ExportedQuery,
    KnowledgeQueryResult as ExportedQueryResult,
    KnowledgeStats as ExportedStats,
    KnowledgeGraphStore as ExportedGraphStore,
    KnowledgeBuilder as ExportedBuilder,
    GraphQueryEngine as ExportedGraphQueryEngine,
    KnowledgeEngine as ExportedKnowledgeEngine,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.memory.models import (
    EvolutionMemoryRecord,
    MemoryOutcome,
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

def _make_node(
    node_type: NodeType = NodeType.MUTATION,
    value: str = "hook",
    metadata: dict | None = None,
) -> KnowledgeNode:
    return KnowledgeNode(
        node_type=node_type,
        value=value,
        metadata=metadata or {},
    )


def _make_edge(
    source_id: str = "src",
    target_id: str = "tgt",
    relation: str = "produced",
    weight: float = 1.0,
    metadata: dict | None = None,
) -> KnowledgeEdge:
    return KnowledgeEdge(
        source_id=source_id,
        target_id=target_id,
        relation=relation,
        weight=weight,
        metadata=metadata or {},
    )


def _make_memory_record(
    genome_id: str = "g001",
    mutation_type: str = "hook",
    category: str = "merge",
    fitness_before: float = 50.0,
    fitness_after: float = 70.0,
    outcome: MemoryOutcome = MemoryOutcome.SUCCESS,
    success_patterns: list[str] | None = None,
    failure_patterns: list[str] | None = None,
    generation: int = 0,
) -> EvolutionMemoryRecord:
    return EvolutionMemoryRecord(
        genome_id=genome_id,
        mutation_type=mutation_type,
        category=category,
        fitness_before=fitness_before,
        fitness_after=fitness_after,
        outcome=outcome,
        success_patterns=success_patterns or [],
        failure_patterns=failure_patterns or [],
        generation=generation,
    )


def _make_records(count: int = 10) -> list[EvolutionMemoryRecord]:
    """创建多样化的 MemoryRecord。"""
    records = []
    mts = ["hook", "visual", "gameplay", "monetization"]
    cats = ["merge", "purge", "explore"]
    outcomes = [MemoryOutcome.SUCCESS, MemoryOutcome.FAILURE, MemoryOutcome.NEUTRAL]
    for i in range(count):
        r = _make_memory_record(
            genome_id=f"g{i + 1:03d}",
            mutation_type=mts[i % 4],
            category=cats[i % 3],
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

class TestNodeType:
    def test_values(self):
        assert NodeType.GENOME.value == "genome"
        assert NodeType.MUTATION.value == "mutation"
        assert NodeType.PATTERN.value == "pattern"
        assert NodeType.STRATEGY.value == "strategy"
        assert NodeType.RESULT.value == "result"
        assert NodeType.CATEGORY.value == "category"
        assert NodeType.FITNESS.value == "fitness"
        assert NodeType.CREATIVE.value == "creative"

    def test_count(self):
        assert len(NodeType) == 8


class TestKnowledgeNode:
    def test_create_default(self):
        n = _make_node()
        assert n.node_id.startswith("node_")
        assert n.node_type == NodeType.MUTATION
        assert n.value == "hook"
        assert n.created_at != ""

    def test_key(self):
        n = _make_node(NodeType.MUTATION, "hook")
        assert n.key == "mutation:hook"

    def test_hash_equality(self):
        n1 = _make_node(NodeType.MUTATION, "hook")
        n2 = _make_node(NodeType.MUTATION, "hook")
        assert hash(n1) == hash(n2)
        assert n1 == n2

    def test_hash_inequality(self):
        n1 = _make_node(NodeType.MUTATION, "hook")
        n2 = _make_node(NodeType.MUTATION, "visual")
        assert n1 != n2

    def test_to_dict(self):
        n = _make_node(NodeType.RESULT, "success")
        d = n.to_dict()
        assert d["node_type"] == "result"
        assert d["value"] == "success"

    def test_repr(self):
        n = _make_node(NodeType.MUTATION, "hook")
        assert "mutation:hook" in repr(n)


class TestKnowledgeEdge:
    def test_create_default(self):
        e = _make_edge()
        assert e.source_id == "src"
        assert e.target_id == "tgt"
        assert e.relation == "produced"
        assert e.weight == 1.0
        assert e.count == 1

    def test_key(self):
        e = _make_edge("src", "tgt", "produced")
        assert "src→tgt:produced" in e.key

    def test_hash_equality(self):
        e1 = _make_edge("n1", "n2", "produced")
        e2 = _make_edge("n1", "n2", "produced")
        assert hash(e1) == hash(e2)
        assert e1 == e2

    def test_to_dict(self):
        e = _make_edge("n1", "n2", "produced", 0.8)
        d = e.to_dict()
        assert d["source_id"] == "n1"
        assert d["weight"] == 0.8

    def test_repr(self):
        e = _make_edge("n1", "n2", "produced", 0.5)
        r = repr(e)
        assert "n1" in r
        assert "produced" in r
        assert "n2" in r


class TestKnowledgePath:
    def test_create_empty(self):
        p = KnowledgePath()
        assert p.length == 0
        assert p.total_weight == 0.0

    def test_create_with_data(self):
        n1 = _make_node(NodeType.MUTATION, "hook")
        n2 = _make_node(NodeType.RESULT, "success")
        e = _make_edge(n1.node_id, n2.node_id, "produced", 0.8)
        p = KnowledgePath(nodes=[n1, n2], edges=[e], total_weight=0.8)
        assert p.length == 1
        assert p.total_weight == 0.8

    def test_to_dict(self):
        p = KnowledgePath(total_weight=0.5)
        d = p.to_dict()
        assert d["length"] == 0
        assert d["total_weight"] == 0.5


class TestKnowledgeQuery:
    def test_create_default(self):
        q = KnowledgeQuery()
        assert q.node_type is None
        assert q.direction == "outgoing"
        assert q.max_depth == 1

    def test_create_full(self):
        q = KnowledgeQuery(
            node_type=NodeType.MUTATION,
            value="hook",
            direction="outgoing",
            max_depth=2,
        )
        assert q.node_type == NodeType.MUTATION
        assert q.value == "hook"
        assert q.max_depth == 2

    def test_to_dict(self):
        q = KnowledgeQuery(node_type=NodeType.MUTATION, value="hook")
        d = q.to_dict()
        assert d["value"] == "hook"


class TestKnowledgeQueryResult:
    def test_create_default(self):
        r = KnowledgeQueryResult()
        assert r.total_nodes == 0
        assert r.recommendation == ""

    def test_create_full(self):
        r = KnowledgeQueryResult(
            total_nodes=5,
            total_edges=10,
            success_rate=0.7,
            avg_fitness_gain=15.0,
            recommendation="EXPLOIT",
        )
        assert r.total_nodes == 5
        assert r.success_rate == 0.7
        assert r.avg_fitness_gain == 15.0

    def test_to_dict(self):
        r = KnowledgeQueryResult(total_nodes=3, success_rate=0.8)
        d = r.to_dict()
        assert d["total_nodes"] == 3
        assert d["success_rate"] == 0.8


class TestKnowledgeStats:
    def test_create_default(self):
        s = KnowledgeStats()
        assert s.total_nodes == 0
        assert s.total_edges == 0

    def test_create_full(self):
        s = KnowledgeStats(
            total_nodes=10,
            total_edges=20,
            node_types={"mutation": 5, "result": 3},
            edge_relations={"produced": 10},
            avg_weight=0.5,
        )
        assert s.total_nodes == 10
        assert s.node_types["mutation"] == 5


# ═══════════════════════════════════════════════════════════
# 2. GraphStore — 25 tests
# ═══════════════════════════════════════════════════════════

class TestKnowledgeGraphStore:
    @pytest.fixture
    def graph(self):
        return KnowledgeGraphStore()

    def test_empty(self, graph):
        assert graph.get_node_count() == 0
        assert graph.get_edge_count() == 0

    def test_add_node(self, graph):
        n = _make_node(NodeType.MUTATION, "hook")
        nid = graph.add_node(n)
        assert nid == n.node_id
        assert graph.get_node_count() == 1
        assert graph.add_node_count == 1

    def test_add_node_dedup(self, graph):
        """同 key 节点不应重复添加。"""
        n1 = _make_node(NodeType.MUTATION, "hook")
        n2 = _make_node(NodeType.MUTATION, "hook")
        id1 = graph.add_node(n1)
        id2 = graph.add_node(n2)
        assert id1 == id2
        assert graph.get_node_count() == 1

    def test_get_node(self, graph):
        n = _make_node(NodeType.MUTATION, "hook")
        graph.add_node(n)
        got = graph.get_node(n.node_id)
        assert got is not None
        assert got.value == "hook"

    def test_get_node_not_found(self, graph):
        assert graph.get_node("nonexistent") is None

    def test_get_node_by_key(self, graph):
        n = _make_node(NodeType.RESULT, "success")
        graph.add_node(n)
        got = graph.get_node_by_key(NodeType.RESULT, "success")
        assert got is not None
        assert got.node_type == NodeType.RESULT

    def test_get_node_by_key_not_found(self, graph):
        assert graph.get_node_by_key(NodeType.MUTATION, "nonexistent") is None

    def test_find_nodes_by_type(self, graph):
        graph.add_node(_make_node(NodeType.MUTATION, "hook"))
        graph.add_node(_make_node(NodeType.MUTATION, "visual"))
        graph.add_node(_make_node(NodeType.RESULT, "success"))
        found = graph.find_nodes(node_type=NodeType.MUTATION)
        assert len(found) == 2

    def test_find_nodes_by_value(self, graph):
        graph.add_node(_make_node(NodeType.MUTATION, "hook"))
        graph.add_node(_make_node(NodeType.RESULT, "hook"))
        found = graph.find_nodes(value="hook")
        assert len(found) == 2

    def test_get_all_nodes(self, graph):
        graph.add_node(_make_node(NodeType.MUTATION, "hook"))
        graph.add_node(_make_node(NodeType.RESULT, "success"))
        assert len(graph.get_all_nodes()) == 2

    def test_add_edge(self, graph):
        n1 = _make_node(NodeType.MUTATION, "hook")
        n2 = _make_node(NodeType.RESULT, "success")
        graph.add_node(n1)
        graph.add_node(n2)
        e = _make_edge(n1.node_id, n2.node_id, "produced")
        graph.add_edge(e)
        assert graph.get_edge_count() == 1

    def test_add_edge_dedup_increments_count(self, graph):
        n1 = _make_node(NodeType.MUTATION, "hook")
        n2 = _make_node(NodeType.RESULT, "success")
        graph.add_node(n1)
        graph.add_node(n2)
        e1 = _make_edge(n1.node_id, n2.node_id, "produced")
        e2 = _make_edge(n1.node_id, n2.node_id, "produced")
        graph.add_edge(e1)
        graph.add_edge(e2)
        edge = graph.get_edge(n1.node_id, n2.node_id, "produced")
        assert edge is not None
        assert edge.count == 2

    def test_get_edge(self, graph):
        n1 = _make_node(NodeType.MUTATION, "hook")
        n2 = _make_node(NodeType.RESULT, "success")
        graph.add_node(n1)
        graph.add_node(n2)
        e = _make_edge(n1.node_id, n2.node_id, "produced")
        graph.add_edge(e)
        got = graph.get_edge(n1.node_id, n2.node_id, "produced")
        assert got is not None

    def test_get_outgoing_edges(self, graph):
        n1 = _make_node(NodeType.MUTATION, "hook")
        n2 = _make_node(NodeType.RESULT, "success")
        n3 = _make_node(NodeType.RESULT, "failure")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_node(n3)
        graph.add_edge(_make_edge(n1.node_id, n2.node_id, "produced"))
        graph.add_edge(_make_edge(n1.node_id, n3.node_id, "produced"))
        edges = graph.get_outgoing_edges(n1.node_id)
        assert len(edges) == 2

    def test_get_incoming_edges(self, graph):
        n1 = _make_node(NodeType.MUTATION, "hook")
        n2 = _make_node(NodeType.RESULT, "success")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_edge(_make_edge(n1.node_id, n2.node_id, "produced"))
        edges = graph.get_incoming_edges(n2.node_id)
        assert len(edges) == 1

    def test_find_neighbors_outgoing(self, graph):
        n1 = _make_node(NodeType.MUTATION, "hook")
        n2 = _make_node(NodeType.RESULT, "success")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_edge(_make_edge(n1.node_id, n2.node_id, "produced"))
        neighbors = graph.find_neighbors(n1.node_id)
        assert len(neighbors) == 1
        assert neighbors[0].node_type == NodeType.RESULT

    def test_find_neighbors_by_relation(self, graph):
        n1 = _make_node(NodeType.MUTATION, "hook")
        n2 = _make_node(NodeType.RESULT, "success")
        n3 = _make_node(NodeType.CATEGORY, "merge")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_node(n3)
        graph.add_edge(_make_edge(n1.node_id, n2.node_id, "produced"))
        graph.add_edge(_make_edge(n1.node_id, n3.node_id, "in_category"))
        neighbors = graph.find_neighbors(n1.node_id, relation="produced")
        assert len(neighbors) == 1

    def test_find_neighbors_by_key(self, graph):
        n1 = _make_node(NodeType.MUTATION, "hook")
        n2 = _make_node(NodeType.RESULT, "success")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_edge(_make_edge(n1.node_id, n2.node_id, "produced"))
        neighbors = graph.find_neighbors_by_key(NodeType.MUTATION, "hook")
        assert len(neighbors) == 1

    def test_find_path(self, graph):
        n1 = _make_node(NodeType.MUTATION, "hook")
        n2 = _make_node(NodeType.RESULT, "success")
        n3 = _make_node(NodeType.FITNESS, "+20.0")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_node(n3)
        graph.add_edge(_make_edge(n1.node_id, n2.node_id, "produced", 1.0))
        graph.add_edge(_make_edge(n2.node_id, n3.node_id, "fitness_gain", 0.2))
        paths = graph.find_path(n1.node_id, n3.node_id, max_depth=3)
        assert len(paths) == 1
        assert paths[0].length == 2

    def test_find_path_not_found(self, graph):
        n1 = _make_node(NodeType.MUTATION, "hook")
        n2 = _make_node(NodeType.MUTATION, "visual")
        graph.add_node(n1)
        graph.add_node(n2)
        paths = graph.find_path(n1.node_id, n2.node_id)
        assert len(paths) == 0

    def test_find_path_by_key(self, graph):
        n1 = _make_node(NodeType.MUTATION, "hook")
        n2 = _make_node(NodeType.RESULT, "success")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_edge(_make_edge(n1.node_id, n2.node_id, "produced", 1.0))
        paths = graph.find_path_by_key(
            NodeType.MUTATION, "hook",
            NodeType.RESULT, "success",
        )
        assert len(paths) == 1

    def test_get_stats(self, graph):
        n1 = _make_node(NodeType.MUTATION, "hook")
        n2 = _make_node(NodeType.RESULT, "success")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_edge(_make_edge(n1.node_id, n2.node_id, "produced"))
        stats = graph.get_stats()
        assert stats.total_nodes == 2
        assert stats.total_edges == 1
        assert "mutation" in stats.node_types

    def test_clear(self, graph):
        n = _make_node(NodeType.MUTATION, "hook")
        graph.add_node(n)
        graph.clear()
        assert graph.get_node_count() == 0
        assert graph.add_node_count == 0

    def test_repr(self, graph):
        n = _make_node(NodeType.MUTATION, "hook")
        graph.add_node(n)
        assert "nodes=1" in repr(graph)

    def test_len(self, graph):
        graph.add_node(_make_node(NodeType.MUTATION, "hook"))
        graph.add_node(_make_node(NodeType.RESULT, "success"))
        assert len(graph) == 2


# ═══════════════════════════════════════════════════════════
# 3. KnowledgeBuilder — 20 tests
# ═══════════════════════════════════════════════════════════

class TestKnowledgeBuilder:
    @pytest.fixture
    def builder(self):
        return KnowledgeBuilder()

    def test_build_single_record(self, builder):
        record = _make_memory_record(
            genome_id="g001",
            mutation_type="hook",
            category="merge",
            outcome=MemoryOutcome.SUCCESS,
            success_patterns=["rescue"],
        )
        result = builder.build(record)
        assert result["nodes_added"] > 0
        assert result["edges_added"] > 0
        assert builder.build_count == 1

    def test_build_creates_genome_node(self, builder):
        record = _make_memory_record(genome_id="g001")
        builder.build(record)
        node = builder.graph.get_node_by_key(NodeType.GENOME, "g001")
        assert node is not None

    def test_build_creates_mutation_node(self, builder):
        record = _make_memory_record(mutation_type="hook")
        builder.build(record)
        node = builder.graph.get_node_by_key(NodeType.MUTATION, "hook")
        assert node is not None

    def test_build_creates_result_node(self, builder):
        record = _make_memory_record(outcome=MemoryOutcome.SUCCESS)
        builder.build(record)
        node = builder.graph.get_node_by_key(NodeType.RESULT, "success")
        assert node is not None

    def test_build_creates_category_node(self, builder):
        record = _make_memory_record(category="merge")
        builder.build(record)
        node = builder.graph.get_node_by_key(NodeType.CATEGORY, "merge")
        assert node is not None

    def test_build_creates_fitness_node(self, builder):
        record = _make_memory_record(fitness_before=50.0, fitness_after=70.0)
        builder.build(record)
        node = builder.graph.get_node_by_key(NodeType.FITNESS, "+20.0")
        assert node is not None

    def test_build_creates_pattern_nodes(self, builder):
        record = _make_memory_record(
            success_patterns=["rescue", "high_contrast"],
            failure_patterns=["slow_intro"],
        )
        builder.build(record)
        assert builder.graph.get_node_by_key(NodeType.PATTERN, "rescue") is not None
        assert builder.graph.get_node_by_key(NodeType.PATTERN, "high_contrast") is not None
        assert builder.graph.get_node_by_key(NodeType.PATTERN, "slow_intro") is not None

    def test_build_creates_genome_mutation_edge(self, builder):
        record = _make_memory_record(genome_id="g001", mutation_type="hook")
        builder.build(record)
        genome = builder.graph.get_node_by_key(NodeType.GENOME, "g001")
        mutation = builder.graph.get_node_by_key(NodeType.MUTATION, "hook")
        edge = builder.graph.get_edge(genome.node_id, mutation.node_id, "undergoes")
        assert edge is not None

    def test_build_creates_mutation_result_edge(self, builder):
        record = _make_memory_record(mutation_type="hook", outcome=MemoryOutcome.SUCCESS)
        builder.build(record)
        mutation = builder.graph.get_node_by_key(NodeType.MUTATION, "hook")
        result = builder.graph.get_node_by_key(NodeType.RESULT, "success")
        edge = builder.graph.get_edge(mutation.node_id, result.node_id, "produced")
        assert edge is not None

    def test_build_success_edge_has_weight_1(self, builder):
        record = _make_memory_record(outcome=MemoryOutcome.SUCCESS)
        builder.build(record)
        mutation = builder.graph.get_node_by_key(NodeType.MUTATION, "hook")
        result = builder.graph.get_node_by_key(NodeType.RESULT, "success")
        edge = builder.graph.get_edge(mutation.node_id, result.node_id, "produced")
        assert edge.weight == 1.0

    def test_build_failure_edge_has_weight_02(self, builder):
        record = _make_memory_record(outcome=MemoryOutcome.FAILURE)
        builder.build(record)
        mutation = builder.graph.get_node_by_key(NodeType.MUTATION, "hook")
        result = builder.graph.get_node_by_key(NodeType.RESULT, "failure")
        edge = builder.graph.get_edge(mutation.node_id, result.node_id, "produced")
        assert edge.weight == 0.2

    def test_build_from_memory(self, builder):
        records = _make_records(10)
        result = builder.build_from_memory(records)
        assert result["records_processed"] == 10
        assert result["total_nodes_added"] > 0
        assert result["total_edges_added"] > 0

    def test_build_dedup_nodes(self, builder):
        """多次构建同 key 节点不重复。"""
        r1 = _make_memory_record(mutation_type="hook")
        r2 = _make_memory_record(mutation_type="hook")
        builder.build(r1)
        builder.build(r2)
        nodes = builder.graph.find_nodes(node_type=NodeType.MUTATION, value="hook")
        assert len(nodes) == 1

    def test_build_dedup_edges_increments_count(self, builder):
        r1 = _make_memory_record(mutation_type="hook", outcome=MemoryOutcome.SUCCESS)
        r2 = _make_memory_record(mutation_type="hook", outcome=MemoryOutcome.SUCCESS)
        builder.build(r1)
        builder.build(r2)
        mutation = builder.graph.get_node_by_key(NodeType.MUTATION, "hook")
        result = builder.graph.get_node_by_key(NodeType.RESULT, "success")
        edge = builder.graph.get_edge(mutation.node_id, result.node_id, "produced")
        assert edge.count == 2

    def test_build_no_category(self, builder):
        record = _make_memory_record(category="")
        builder.build(record)
        nodes = builder.graph.find_nodes(node_type=NodeType.CATEGORY)
        assert len(nodes) == 0

    def test_build_no_patterns(self, builder):
        record = _make_memory_record(success_patterns=[], failure_patterns=[])
        builder.build(record)
        nodes = builder.graph.find_nodes(node_type=NodeType.PATTERN)
        assert len(nodes) == 0

    def test_get_stats(self, builder):
        builder.build(_make_memory_record())
        stats = builder.get_stats()
        assert stats["build_count"] == 1
        assert "graph" in stats

    def test_reset(self, builder):
        builder.build(_make_memory_record())
        builder.reset()
        assert builder.build_count == 0
        assert builder.graph.get_node_count() == 0

    def test_graph_property(self, builder):
        assert isinstance(builder.graph, KnowledgeGraphStore)

    def test_repr(self, builder):
        builder.build(_make_memory_record())
        assert "built=1" in repr(builder)


# ═══════════════════════════════════════════════════════════
# 4. GraphQueryEngine — 15 tests
# ═══════════════════════════════════════════════════════════

class TestGraphQueryEngine:
    @pytest.fixture
    def engine(self):
        builder = KnowledgeBuilder()
        records = _make_records(20)
        builder.build_from_memory(records)
        return GraphQueryEngine(graph=builder.graph)

    def test_query_by_node_type(self, engine):
        q = KnowledgeQuery(node_type=NodeType.MUTATION)
        result = engine.query(q)
        assert result.total_nodes > 0

    def test_query_by_value(self, engine):
        q = KnowledgeQuery(node_type=NodeType.MUTATION, value="hook")
        result = engine.query(q)
        assert result.total_nodes == 1

    def test_query_not_found(self, engine):
        q = KnowledgeQuery(node_type=NodeType.MUTATION, value="nonexistent")
        result = engine.query(q)
        assert result.total_nodes == 0

    def test_query_collects_edges(self, engine):
        q = KnowledgeQuery(node_type=NodeType.MUTATION, value="hook")
        result = engine.query(q)
        assert result.total_edges > 0

    def test_query_success_patterns(self, engine):
        result = engine.query_success_patterns()
        assert result.total_nodes > 0

    def test_query_failure_patterns(self, engine):
        result = engine.query_failure_patterns()
        assert result is not None

    def test_query_mutation_outcomes(self, engine):
        result = engine.query_mutation_outcomes("hook")
        assert result.total_nodes == 1
        assert result.total_edges > 0

    def test_query_related_patterns(self, engine):
        result = engine.query_related_patterns("hook")
        assert result is not None

    def test_query_with_recommendation(self, engine):
        q = KnowledgeQuery(node_type=NodeType.MUTATION, value="hook")
        result = engine.query(q)
        assert isinstance(result.recommendation, str)
        assert len(result.recommendation) > 0

    def test_query_success_rate(self, engine):
        q = KnowledgeQuery(node_type=NodeType.MUTATION, value="hook")
        result = engine.query(q)
        if result.success_rate is not None:
            assert 0.0 <= result.success_rate <= 1.0

    def test_query_count(self, engine):
        engine.query(KnowledgeQuery(node_type=NodeType.MUTATION))
        assert engine.query_count == 1

    def test_get_stats(self, engine):
        stats = engine.get_stats()
        assert "query_count" in stats
        assert "graph_stats" in stats

    def test_reset(self, engine):
        engine.query(KnowledgeQuery())
        engine.reset()
        assert engine.query_count == 0

    def test_graph_property(self, engine):
        assert isinstance(engine.graph, KnowledgeGraphStore)

    def test_repr(self, engine):
        engine.query(KnowledgeQuery())
        assert "queries=1" in repr(engine)


# ═══════════════════════════════════════════════════════════
# 5. KnowledgeEngine — 15 tests
# ═══════════════════════════════════════════════════════════

class TestKnowledgeEngine:
    @pytest.fixture
    def engine(self):
        return KnowledgeEngine()

    @pytest.fixture
    def populated_engine(self):
        engine = KnowledgeEngine()
        records = _make_records(20)
        engine.ingest_batch(records)
        return engine

    def test_ingest(self, engine):
        record = _make_memory_record()
        result = engine.ingest(record)
        assert result["nodes_added"] > 0
        assert result["edges_added"] > 0
        assert engine.ingest_count == 1

    def test_ingest_batch(self, engine):
        records = _make_records(10)
        result = engine.ingest_batch(records)
        assert result["records_processed"] == 10
        assert engine.ingest_count == 10

    def test_analyze(self, populated_engine):
        result = populated_engine.analyze("hook")
        assert result.total_nodes == 1
        assert result.total_edges > 0

    def test_analyze_patterns(self, populated_engine):
        result = populated_engine.analyze_patterns("hook")
        assert result is not None

    def test_recommend_success(self, populated_engine):
        result = populated_engine.recommend("hook")
        assert result["mutation_type"] == "hook"
        assert result["action"] in ("EXPLOIT", "EXPLORE", "AVOID")
        assert "success_rate" in result
        assert "top_patterns" in result

    def test_recommend_unknown(self, engine):
        result = engine.recommend("nonexistent")
        assert result["mutation_type"] == "nonexistent"
        assert result["action"] == "EXPLORE"
        assert result["success_rate"] is None

    def test_recommend_all(self, populated_engine):
        result = populated_engine.recommend_all()
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_query(self, populated_engine):
        q = KnowledgeQuery(node_type=NodeType.MUTATION, value="hook")
        result = populated_engine.query(q)
        assert result.total_nodes == 1

    def test_get_stats(self, populated_engine):
        stats = populated_engine.get_stats()
        assert stats["ingest_count"] == 20
        assert "graph" in stats

    def test_clear(self, populated_engine):
        populated_engine.clear()
        assert populated_engine.ingest_count == 0
        assert populated_engine.graph.get_node_count() == 0

    def test_properties(self, engine):
        assert isinstance(engine.graph, KnowledgeGraphStore)
        assert isinstance(engine.builder, KnowledgeBuilder)
        assert isinstance(engine.query_engine, GraphQueryEngine)

    def test_analyze_count(self, populated_engine):
        populated_engine.analyze("hook")
        assert populated_engine.analyze_count == 1

    def test_ingest_many_mutations(self, engine):
        """摄入大量不同 mutation 的记录。"""
        mts = ["hook", "visual", "gameplay", "monetization", "audio"]
        for i, mt in enumerate(mts):
            for j in range(5):
                engine.ingest(_make_memory_record(
                    genome_id=f"g{i}_{j}",
                    mutation_type=mt,
                    outcome=MemoryOutcome.SUCCESS if j < 3 else MemoryOutcome.FAILURE,
                ))
        rec = engine.recommend("hook")
        # hook 有 3 成功 2 失败 → 成功率 60%
        assert rec["success_rate"] is not None

    def test_repr(self, engine):
        engine.ingest(_make_memory_record())
        assert "ingested=1" in repr(engine)


# ═══════════════════════════════════════════════════════════
# 6. Controller Integration — 5 tests
# ═══════════════════════════════════════════════════════════

class TestControllerKnowledgeIntegration:
    @pytest.fixture
    def controller(self):
        mock_intel = MagicMock(spec=VisionIntelligenceEngine)
        return AutonomousCreativeController(intelligence_engine=mock_intel)

    def test_update_knowledge(self, controller):
        record = _make_memory_record()
        result = controller.update_knowledge(record)
        assert result["nodes_added"] > 0
        assert result["edges_added"] > 0

    def test_update_knowledge_from_memory(self, controller):
        records = _make_records(5)
        result = controller.update_knowledge_from_memory(records)
        assert result["records_processed"] == 5

    def test_query_knowledge(self, controller):
        controller.update_knowledge(_make_memory_record(mutation_type="hook"))
        result = controller.query_knowledge(mutation_type="hook")
        assert result["mutation_type"] == "hook"
        assert "action" in result
        assert "success_rate" in result

    def test_analyze_knowledge(self, controller):
        controller.update_knowledge(_make_memory_record(mutation_type="hook"))
        result = controller.analyze_knowledge("hook")
        assert result.total_nodes == 1

    def test_knowledge_engine_property(self, controller):
        assert isinstance(controller.knowledge_engine, KnowledgeEngine)


# ═══════════════════════════════════════════════════════════
# 7. Full Pipeline — 5 tests
# ═══════════════════════════════════════════════════════════

class TestFullPipeline:
    def test_memory_to_knowledge_pipeline(self):
        """Memory → Knowledge Builder → Graph → Query。"""
        engine = KnowledgeEngine()

        # 摄入 50 条记录
        for i in range(50):
            mt = ["hook", "visual", "gameplay"][i % 3]
            engine.ingest(_make_memory_record(
                genome_id=f"g{i:03d}",
                mutation_type=mt,
                outcome=MemoryOutcome.SUCCESS if i % 2 == 0 else MemoryOutcome.FAILURE,
                success_patterns=["rescue"] if i % 2 == 0 else [],
                failure_patterns=["slow_intro"] if i % 2 != 0 else [],
            ))

        # 分析
        result = engine.analyze("hook")
        assert result.total_nodes == 1
        assert result.success_rate is not None

        # 推荐
        rec = engine.recommend("hook")
        assert rec["action"] in ("EXPLOIT", "EXPLORE", "AVOID")

    def test_knowledge_drives_policy(self):
        """Knowledge Graph 为 Policy 提供决策依据。"""
        engine = KnowledgeEngine()

        # hook 成功率高
        for i in range(20):
            engine.ingest(_make_memory_record(
                genome_id=f"g{i:03d}",
                mutation_type="hook",
                outcome=MemoryOutcome.SUCCESS,
                success_patterns=["rescue", "high_contrast"],
            ))

        # visual 成功率低
        for i in range(20):
            engine.ingest(_make_memory_record(
                genome_id=f"g{i + 20:03d}",
                mutation_type="visual",
                outcome=MemoryOutcome.FAILURE,
                failure_patterns=["slow_intro"],
            ))

        hook_rec = engine.recommend("hook")
        visual_rec = engine.recommend("visual")

        assert hook_rec["action"] == "EXPLOIT"
        assert visual_rec["action"] == "AVOID"

    def test_controller_full_knowledge_pipeline(self):
        """Controller → Memory → Knowledge → Policy。"""
        mock_intel = MagicMock(spec=VisionIntelligenceEngine)
        controller = AutonomousCreativeController(intelligence_engine=mock_intel)

        # 记录并构建知识图谱
        for i in range(30):
            record = controller.remember_evolution(
                f"g{i:03d}",
                ["hook", "visual", "gameplay"][i % 3],
                50.0,
                50.0 + (15.0 if i % 2 == 0 else -5.0),
                category="merge",
                success_patterns=["rescue"] if i % 2 == 0 else [],
            )
            controller.update_knowledge(record)

        # 查询知识
        result = controller.query_knowledge(mutation_type="hook")
        assert "action" in result
        assert result["success_rate"] is not None

    def test_explore_on_insufficient_data(self):
        """数据不足时建议 EXPLORE。"""
        engine = KnowledgeEngine()

        engine.ingest(_make_memory_record(
            mutation_type="new_type",
            outcome=MemoryOutcome.SUCCESS,
        ))
        engine.ingest(_make_memory_record(
            mutation_type="new_type",
            outcome=MemoryOutcome.FAILURE,
        ))
        engine.ingest(_make_memory_record(
            mutation_type="new_type",
            outcome=MemoryOutcome.FAILURE,
        ))

        rec = engine.recommend("new_type")
        # 1/3 成功 → 33% → 不低于 30% 阈值 → EXPLORE
        assert rec["action"] == "EXPLORE"

    def test_graph_path_from_mutation_to_pattern(self):
        """MUTATION → RESULT → PATTERN 路径。"""
        engine = KnowledgeEngine()

        engine.ingest(_make_memory_record(
            mutation_type="hook",
            outcome=MemoryOutcome.SUCCESS,
            success_patterns=["rescue"],
        ))

        mutation = engine.graph.get_node_by_key(NodeType.MUTATION, "hook")
        pattern = engine.graph.get_node_by_key(NodeType.PATTERN, "rescue")

        paths = engine.graph.find_path(mutation.node_id, pattern.node_id)
        assert len(paths) == 1
        assert paths[0].length == 2  # MUTATION → RESULT → PATTERN


# ═══════════════════════════════════════════════════════════
# 8. Package Exports — 5 tests
# ═══════════════════════════════════════════════════════════

class TestPackageExports:
    def test_exports_models(self):
        assert ExportedNode is KnowledgeNode
        assert ExportedNodeType is NodeType
        assert ExportedEdge is KnowledgeEdge
        assert ExportedPath is KnowledgePath
        assert ExportedQuery is KnowledgeQuery
        assert ExportedQueryResult is KnowledgeQueryResult
        assert ExportedStats is KnowledgeStats

    def test_exports_graph_store(self):
        assert ExportedGraphStore is KnowledgeGraphStore

    def test_exports_builder(self):
        assert ExportedBuilder is KnowledgeBuilder

    def test_exports_query_engine(self):
        assert ExportedGraphQueryEngine is GraphQueryEngine

    def test_exports_engine(self):
        assert ExportedKnowledgeEngine is KnowledgeEngine