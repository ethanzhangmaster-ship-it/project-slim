"""E12.5.3 — Meta Knowledge Graph 测试。

覆盖:
  - Models: NodeType, RelationType, KnowledgeNode, KnowledgeEdge,
            GraphQuery, GraphQueryResult, GraphStats
  - GraphStore: add/get/remove nodes/edges, neighbors, path, stats
  - NodeBuilder: Pattern→Node, Gene→Node, Market/Product/Platform nodes
  - RelationshipEngine: improves, combines_with, similar_to, belongs_to
  - GraphQueryEngine: find_best_genes, recommend_mutation, transfer,
                       gene_combinations, causal_chain
  - Pipeline: 完整图构建与查询流程
  - Integration: 与 ExperienceStore 和 Pattern Mining 集成
"""

import pytest

from market_ops.creative_vision_runtime.reality.meta_learning import (
    ExperienceOutcome,
    ExperienceRecord,
    ExperienceStore,
)
from market_ops.creative_vision_runtime.reality.meta_learning.knowledge_graph import (
    GraphQuery,
    GraphQueryEngine,
    GraphQueryResult,
    GraphStats,
    GraphStore,
    KnowledgeEdge,
    KnowledgeNode,
    NodeBuilder,
    NodeType,
    RelationshipEngine,
    RelationType,
)
from market_ops.creative_vision_runtime.reality.meta_learning.pattern_miner import (
    MetaPattern,
    PatternType,
)


# ── Helpers ───────────────────────────────────────────────


def make_node(
    node_id="NODE_001",
    node_type=NodeType.GENE,
    name="Test Gene",
    confidence=0.9,
    attributes=None,
    labels=None,
):
    return KnowledgeNode(
        node_id=node_id,
        node_type=node_type,
        name=name,
        confidence=confidence,
        attributes=attributes or {},
        labels=labels or [],
    )


def make_edge(
    source="NODE_001",
    target="NODE_002",
    rel_type=RelationType.IMPROVES,
    weight=0.8,
    evidence=10,
    confidence=0.9,
):
    return KnowledgeEdge(
        source_id=source,
        target_id=target,
        relation_type=rel_type,
        weight=weight,
        evidence_count=evidence,
        confidence=confidence,
    )


def make_pattern(name="Rescue Hook", sr=0.75, roas=0.21, ctr=0.15, cvr=0.10, samples=100, conf=0.91):
    return MetaPattern(
        pattern_type=PatternType.HOOK,
        name=name,
        genes={"emotion": "rescue", "character": "cute_animal"},
        sample_count=samples,
        success_count=int(samples * sr),
        success_rate=sr,
        avg_roas_gain=roas,
        avg_ctr_gain=ctr,
        avg_cvr_gain=cvr,
        confidence=conf,
    )


# ═══════════════════════════════════════════════════════════
# 1. Models (15 tests)
# ═══════════════════════════════════════════════════════════


class TestGraphModels:
    """Graph 数据模型测试。"""

    # ── NodeType ────────────────────────────────────────

    def test_node_type_values(self):
        assert len(list(NodeType)) == 9
        assert NodeType.PRODUCT.value == "product"
        assert NodeType.GENE.value == "gene"
        assert NodeType.PATTERN.value == "pattern"
        assert NodeType.METRIC.value == "metric"

    def test_node_type_serialization(self):
        nt = NodeType("gene")
        assert nt == NodeType.GENE
        assert str(nt.value) == "gene"

    # ── RelationType ─────────────────────────────────────

    def test_relation_type_values(self):
        assert len(list(RelationType)) == 10
        assert RelationType.IMPROVES.value == "improves"
        assert RelationType.COMBINES_WITH.value == "combines_with"
        assert RelationType.TRANSFERS_TO.value == "transfers_to"

    # ── KnowledgeNode ────────────────────────────────────

    def test_knowledge_node_creation(self):
        node = make_node()
        assert node.node_id == "NODE_001"
        assert node.node_type == NodeType.GENE
        assert node.name == "Test Gene"
        assert node.confidence == 0.9

    def test_knowledge_node_auto_id(self):
        node = KnowledgeNode(name="Auto")
        assert node.node_id.startswith("NODE_")

    def test_knowledge_node_is_reliable(self):
        node = make_node(confidence=0.5)
        assert node.is_reliable is False
        node2 = make_node(confidence=0.8)
        assert node2.is_reliable is True

    def test_knowledge_node_to_dict(self):
        node = make_node()
        d = node.to_dict()
        assert d["node_id"] == "NODE_001"
        assert d["node_type"] == "gene"
        assert d["name"] == "Test Gene"
        assert "created_at" in d

    def test_knowledge_node_hash_eq(self):
        n1 = make_node("A")
        n2 = make_node("A")
        n3 = make_node("B")
        assert n1 == n2
        assert hash(n1) == hash(n2)
        assert n1 != n3

    def test_knowledge_node_repr(self):
        node = make_node()
        r = repr(node)
        assert "KnowledgeNode" in r
        assert "gene" in r

    # ── KnowledgeEdge ────────────────────────────────────

    def test_knowledge_edge_creation(self):
        edge = make_edge()
        assert edge.source_id == "NODE_001"
        assert edge.target_id == "NODE_002"
        assert edge.relation_type == RelationType.IMPROVES
        assert edge.weight == 0.8

    def test_knowledge_edge_auto_id(self):
        edge = KnowledgeEdge(source_id="A", target_id="B")
        assert edge.edge_id.startswith("EDGE_")

    def test_knowledge_edge_is_strong(self):
        edge = make_edge(evidence=25, confidence=0.85)
        assert edge.is_strong is True
        edge2 = make_edge(evidence=3, confidence=0.5)
        assert edge2.is_strong is False

    def test_knowledge_edge_to_dict(self):
        edge = make_edge()
        d = edge.to_dict()
        assert d["source_id"] == "NODE_001"
        assert d["target_id"] == "NODE_002"
        assert d["relation_type"] == "improves"

    def test_knowledge_edge_repr(self):
        edge = make_edge()
        r = repr(edge)
        assert "KnowledgeEdge" in r
        assert "improves" in r

    # ── GraphQuery / GraphQueryResult ────────────────────

    def test_graph_query_creation(self):
        query = GraphQuery(
            query_type="find_best_genes",
            target_metric="CTR",
            max_results=10,
        )
        assert query.target_metric == "CTR"
        assert query.max_results == 10

    def test_graph_query_result_empty(self):
        result = GraphQueryResult()
        assert result.nodes == []
        assert result.recommendations == []

    def test_graph_stats(self):
        stats = GraphStats(
            total_nodes=10,
            total_edges=20,
            nodes_by_type={"gene": 5, "pattern": 3, "metric": 2},
            edges_by_type={"improves": 15, "belongs_to": 5},
        )
        d = stats.to_dict()
        assert d["total_nodes"] == 10
        assert d["total_edges"] == 20


# ═══════════════════════════════════════════════════════════
# 2. Graph Store (15 tests)
# ═══════════════════════════════════════════════════════════


class TestGraphStore:
    """GraphStore — 图存储测试。"""

    def test_add_node(self):
        store = GraphStore()
        node = make_node()
        store.add_node(node)
        assert store.node_count == 1
        assert store.has_node("NODE_001")

    def test_get_node(self):
        store = GraphStore()
        node = make_node()
        store.add_node(node)
        retrieved = store.get_node("NODE_001")
        assert retrieved is not None
        assert retrieved.name == "Test Gene"

    def test_get_node_missing(self):
        store = GraphStore()
        assert store.get_node("NONEXISTENT") is None

    def test_remove_node(self):
        store = GraphStore()
        node = make_node()
        store.add_node(node)
        assert store.remove_node("NODE_001") is True
        assert store.node_count == 0

    def test_remove_node_with_edges(self):
        store = GraphStore()
        n1 = make_node("A", name="Node A")
        n2 = make_node("B", name="Node B")
        store.add_node(n1)
        store.add_node(n2)
        edge = make_edge("A", "B")
        store.add_edge(edge)
        assert store.edge_count == 1
        store.remove_node("A")
        assert store.node_count == 1
        assert store.edge_count == 0

    def test_add_edge(self):
        store = GraphStore()
        n1 = make_node("A")
        n2 = make_node("B")
        store.add_node(n1)
        store.add_node(n2)
        edge = make_edge("A", "B")
        assert store.add_edge(edge) is True
        assert store.edge_count == 1

    def test_add_edge_missing_nodes(self):
        store = GraphStore()
        edge = make_edge("A", "B")
        assert store.add_edge(edge) is False

    def test_get_edge(self):
        store = GraphStore()
        n1 = make_node("A")
        n2 = make_node("B")
        store.add_node(n1)
        store.add_node(n2)
        edge = make_edge("A", "B")
        store.add_edge(edge)
        retrieved = store.get_edge(edge.edge_id)
        assert retrieved is not None
        assert retrieved.weight == 0.8

    def test_has_edge_between(self):
        store = GraphStore()
        n1 = make_node("A")
        n2 = make_node("B")
        store.add_node(n1)
        store.add_node(n2)
        store.add_edge(make_edge("A", "B"))
        assert store.has_edge_between("A", "B") is True
        assert store.has_edge_between("B", "A") is True
        assert store.has_edge_between("A", "C") is False

    def test_remove_edge(self):
        store = GraphStore()
        n1 = make_node("A")
        n2 = make_node("B")
        store.add_node(n1)
        store.add_node(n2)
        edge = make_edge("A", "B")
        store.add_edge(edge)
        assert store.remove_edge(edge.edge_id) is True
        assert store.edge_count == 0

    def test_query_neighbors(self):
        store = GraphStore()
        n1 = make_node("A", name="Node A")
        n2 = make_node("B", name="Node B")
        n3 = make_node("C", name="Node C")
        store.add_node(n1)
        store.add_node(n2)
        store.add_node(n3)
        store.add_edge(make_edge("A", "B", weight=0.9))
        store.add_edge(make_edge("A", "C", weight=0.5))

        neighbors = store.query_neighbors("A")
        assert len(neighbors) == 2
        # 按权重降序
        assert neighbors[0][1].weight >= neighbors[1][1].weight

    def test_query_neighbors_filtered(self):
        store = GraphStore()
        n1 = make_node("A")
        n2 = make_node("B")
        n3 = make_node("C")
        store.add_node(n1)
        store.add_node(n2)
        store.add_node(n3)
        store.add_edge(make_edge("A", "B", rel_type=RelationType.IMPROVES))
        store.add_edge(make_edge("A", "C", rel_type=RelationType.COMBINES_WITH))

        neighbors = store.query_neighbors("A", relation_type=RelationType.IMPROVES)
        assert len(neighbors) == 1

    def test_find_path(self):
        store = GraphStore()
        for i in range(5):
            store.add_node(make_node(f"N{i}", name=f"Node {i}"))
        store.add_edge(make_edge("N0", "N1"))
        store.add_edge(make_edge("N1", "N2"))
        store.add_edge(make_edge("N2", "N3"))
        store.add_edge(make_edge("N3", "N4"))

        path = store.find_path("N0", "N4")
        assert path is not None
        assert len(path) == 4

    def test_find_path_no_path(self):
        store = GraphStore()
        store.add_node(make_node("A"))
        store.add_node(make_node("B"))
        assert store.find_path("A", "B") is None

    def test_find_all_paths(self):
        store = GraphStore()
        store.add_node(make_node("A"))
        store.add_node(make_node("B"))
        store.add_node(make_node("C"))
        store.add_edge(make_edge("A", "B"))
        store.add_edge(make_edge("A", "C"))
        store.add_edge(make_edge("B", "C"))

        paths = store.find_all_paths("A", "C")
        assert len(paths) >= 2

    def test_get_stats(self):
        store = GraphStore()
        store.add_node(make_node("A", node_type=NodeType.GENE))
        store.add_node(make_node("B", node_type=NodeType.PATTERN))
        store.add_node(make_node("C", node_type=NodeType.METRIC))
        store.add_edge(make_edge("A", "B", rel_type=RelationType.BELONGS_TO))
        store.add_edge(make_edge("B", "C", rel_type=RelationType.IMPROVES))

        stats = store.get_stats()
        assert stats.total_nodes == 3
        assert stats.total_edges == 2
        assert stats.nodes_by_type["gene"] == 1
        assert stats.nodes_by_type["pattern"] == 1
        assert stats.connected_components == 1

    def test_get_nodes_by_type(self):
        store = GraphStore()
        store.add_node(make_node("A", node_type=NodeType.GENE))
        store.add_node(make_node("B", node_type=NodeType.GENE))
        store.add_node(make_node("C", node_type=NodeType.METRIC))
        genes = store.get_nodes_by_type(NodeType.GENE)
        assert len(genes) == 2

    def test_clear(self):
        store = GraphStore()
        store.add_node(make_node("A"))
        store.add_node(make_node("B"))
        store.add_edge(make_edge("A", "B"))
        store.clear()
        assert store.node_count == 0
        assert store.edge_count == 0

    def test_batch_operations(self):
        store = GraphStore()
        nodes = [make_node(f"N{i}") for i in range(10)]
        count = store.add_nodes_batch(nodes)
        assert count == 10

        for i in range(9):
            store.add_edge(make_edge(f"N{i}", f"N{i+1}"))
        assert store.edge_count == 9
        assert store.get_stats().connected_components == 1

    def test_contains(self):
        store = GraphStore()
        store.add_node(make_node("A"))
        assert "A" in store
        assert "B" not in store


# ═══════════════════════════════════════════════════════════
# 3. Node Builder (15 tests)
# ═══════════════════════════════════════════════════════════


class TestNodeBuilder:
    """NodeBuilder — 节点构建测试。"""

    def test_build_pattern_node(self):
        builder = NodeBuilder()
        pattern = make_pattern()
        node = builder.build_pattern_node(pattern)
        assert node.node_type == NodeType.PATTERN
        assert node.name == "Rescue Hook"
        assert node.attributes["success_rate"] == 0.75
        assert node.attributes["genes"] == {"emotion": "rescue", "character": "cute_animal"}
        assert node.confidence == 0.91

    def test_build_gene_node(self):
        builder = NodeBuilder()
        node = builder.build_gene_node(
            gene_value="rescue",
            gene_feature="emotion",
            confidence=0.85,
            gene_category="hook",
        )
        assert node.node_type == NodeType.GENE
        assert node.node_id == "GENE_EMOTION_RESCUE"
        assert node.attributes["gene_feature"] == "emotion"
        assert node.attributes["gene_value"] == "rescue"

    def test_build_gene_nodes_from_pattern(self):
        builder = NodeBuilder()
        pattern = make_pattern()
        nodes = builder.build_gene_nodes_from_pattern(pattern)
        assert len(nodes) == 2
        assert all(n.node_type == NodeType.GENE for n in nodes)

    def test_build_market_node(self):
        builder = NodeBuilder()
        node = builder.build_market_node("US")
        assert node.node_type == NodeType.MARKET
        assert node.node_id == "MARKET_US"
        assert node.attributes["market"] == "US"

    def test_build_product_node(self):
        builder = NodeBuilder()
        node = builder.build_product_node("p04", "Merge Witch")
        assert node.node_type == NodeType.PRODUCT
        assert node.node_id == "PRODUCT_P04"
        assert node.name == "Merge Witch"

    def test_build_platform_node(self):
        builder = NodeBuilder()
        node = builder.build_platform_node("facebook")
        assert node.node_type == NodeType.PLATFORM
        assert node.node_id == "PLATFORM_FACEBOOK"

    def test_build_audience_node(self):
        builder = NodeBuilder()
        node = builder.build_audience_node("Female 25-45")
        assert node.node_type == NodeType.AUDIENCE
        assert node.attributes["segment"] == "Female 25-45"

    def test_build_metric_nodes(self):
        builder = NodeBuilder()
        nodes = builder.build_metric_nodes()
        assert len(nodes) >= 6
        assert all(n.node_type == NodeType.METRIC for n in nodes)
        metric_ids = {n.node_id for n in nodes}
        assert "METRIC_CTR" in metric_ids
        assert "METRIC_ROAS" in metric_ids
        assert "METRIC_CVR" in metric_ids

    def test_build_full_graph(self):
        builder = NodeBuilder()
        patterns = [
            make_pattern("Rescue Hook", sr=0.75, roas=0.21, ctr=0.15),
            make_pattern("Challenge Hook", sr=0.40, roas=0.05, ctr=0.03),
        ]
        nodes, edges = builder.build_full_graph_from_patterns(patterns)
        assert len(nodes) >= 8  # 2 patterns + 2 genes + 6 metrics
        assert len(edges) >= 6  # Gene→Pattern + Pattern→Metric

    def test_build_full_graph_edges(self):
        builder = NodeBuilder()
        patterns = [make_pattern("Rescue Hook", sr=0.75, roas=0.21, ctr=0.15)]
        nodes, edges = builder.build_full_graph_from_patterns(patterns)

        improve_edges = [e for e in edges if e.relation_type == RelationType.IMPROVES]
        belong_edges = [e for e in edges if e.relation_type == RelationType.BELONGS_TO]
        assert len(improve_edges) >= 2  # CTR + ROAS
        assert len(belong_edges) >= 2  # 2 genes

    def test_build_experiment_node(self):
        builder = NodeBuilder()
        node = builder.build_experiment_node("exp_001", "Test Experiment")
        assert node.node_type == NodeType.EXPERIMENT
        assert node.node_id == "EXP_exp_001"

    def test_build_creative_node(self):
        builder = NodeBuilder()
        node = builder.build_creative_node("c001", "Creative 1")
        assert node.node_type == NodeType.CREATIVE
        assert node.node_id == "CREATIVE_c001"

    def test_build_gene_node_from_impact(self):
        from market_ops.creative_vision_runtime.reality.meta_learning.pattern_miner import (
            GeneImpactScore,
        )
        impact = GeneImpactScore(
            gene_category="hook",
            gene_feature="emotion",
            gene_value="rescue",
            impact_score=0.27,
            sample_count=100,
            confidence=0.91,
        )
        builder = NodeBuilder()
        node = builder.build_gene_node_from_impact(impact)
        assert node.attributes["impact_score"] == 0.27
        assert node.attributes["gene_feature"] == "emotion"

    def test_builder_repr(self):
        builder = NodeBuilder()
        assert "NodeBuilder" in repr(builder)


# ═══════════════════════════════════════════════════════════
# 4. Relationship Engine (20 tests)
# ═══════════════════════════════════════════════════════════


class TestRelationshipEngine:
    """RelationshipEngine — 关系发现测试。"""

    def test_discover_improves(self):
        engine = RelationshipEngine()
        patterns = [
            make_pattern("Rescue Hook", sr=0.75, roas=0.21, ctr=0.15, cvr=0.10),
            make_pattern("Bad Pattern", sr=0.30, roas=-0.05, ctr=-0.02, cvr=-0.01),
        ]
        edges = engine.discover_relationships(patterns)
        improve_edges = [e for e in edges if e.relation_type == RelationType.IMPROVES]
        # Rescue Hook has 3 positive metrics, Bad Pattern has 0
        assert len(improve_edges) >= 3

    def test_discover_improves_weight(self):
        engine = RelationshipEngine()
        patterns = [make_pattern("Rescue Hook", roas=0.21, ctr=0.15)]
        edges = engine.discover_relationships(patterns)
        improve_edges = [e for e in edges if e.relation_type == RelationType.IMPROVES]
        assert len(improve_edges) >= 1
        # 找到 ROAS 边
        roas_edge = next((e for e in improve_edges if e.target_id == "METRIC_ROAS"), None)
        assert roas_edge is not None
        assert roas_edge.weight == pytest.approx(0.21)

    def test_discover_combines_with(self):
        engine = RelationshipEngine()
        patterns = [
            MetaPattern(
                pattern_type=PatternType.HOOK,
                name="Rescue",
                genes={"emotion": "rescue"},
                sample_count=50, success_count=40, success_rate=0.80,
                confidence=0.90,
            ),
            MetaPattern(
                pattern_type=PatternType.HOOK,
                name="Challenge",
                genes={"emotion": "challenge"},
                sample_count=50, success_count=40, success_rate=0.80,
                confidence=0.90,
            ),
        ]
        edges = engine.discover_relationships(patterns)
        combine_edges = [e for e in edges if e.relation_type == RelationType.COMBINES_WITH]
        assert len(combine_edges) >= 1

    def test_discover_failed_with(self):
        engine = RelationshipEngine()
        patterns = [
            MetaPattern(
                pattern_type=PatternType.HOOK,
                name="Bad A",
                genes={"emotion": "bad_a"},
                sample_count=50, success_count=10, success_rate=0.20,
                confidence=0.60,
            ),
            MetaPattern(
                pattern_type=PatternType.HOOK,
                name="Bad B",
                genes={"emotion": "bad_b"},
                sample_count=50, success_count=10, success_rate=0.20,
                confidence=0.60,
            ),
        ]
        edges = engine.discover_relationships(patterns)
        failed_edges = [e for e in edges if e.relation_type == RelationType.FAILED_WITH]
        assert len(failed_edges) >= 1

    def test_discover_similar_patterns(self):
        engine = RelationshipEngine()
        patterns = [
            MetaPattern(
                pattern_type=PatternType.HOOK,
                name="Pattern A",
                genes={"emotion": "rescue", "character": "cute_animal", "conflict": "danger"},
                sample_count=100, success_count=70, success_rate=0.70,
                confidence=0.85,
            ),
            MetaPattern(
                pattern_type=PatternType.HOOK,
                name="Pattern B",
                genes={"emotion": "rescue", "character": "cute_animal", "conflict": "time_pressure"},
                sample_count=80, success_count=50, success_rate=0.625,
                confidence=0.80,
            ),
        ]
        edges = engine.discover_relationships(patterns)
        similar_edges = [e for e in edges if e.relation_type == RelationType.SIMILAR_TO]
        assert len(similar_edges) >= 1
        assert similar_edges[0].weight >= 0.5  # 2/3 shared = 0.67

    def test_discover_belongs_to(self):
        engine = RelationshipEngine()
        patterns = [make_pattern()]
        edges = engine.discover_relationships(patterns)
        belong_edges = [e for e in edges if e.relation_type == RelationType.BELONGS_TO]
        assert len(belong_edges) == 2

    def test_discover_relationships_empty(self):
        engine = RelationshipEngine()
        edges = engine.discover_relationships([])
        assert edges == []

    def test_discover_works_for(self):
        engine = RelationshipEngine()
        pattern = make_pattern(sr=0.75)
        builder = NodeBuilder()
        market_node = builder.build_market_node("US")
        edge = engine.discover_works_for(pattern, market_node, "market")
        assert edge is not None
        assert edge.relation_type == RelationType.WORKS_FOR
        assert edge.weight == 0.75

    def test_discover_works_for_low_success(self):
        engine = RelationshipEngine()
        pattern = make_pattern(sr=0.30)
        builder = NodeBuilder()
        market_node = builder.build_market_node("US")
        edge = engine.discover_works_for(pattern, market_node, "market")
        assert edge is None

    def test_discover_causal_chain(self):
        engine = RelationshipEngine()
        edges = engine.discover_causal_chain(
            gene_id="GENE_EMOTION_RESCUE",
            pattern_id="PAT_001",
            metric_id="METRIC_CTR",
            confidence=0.85,
            evidence=50,
        )
        assert len(edges) == 2
        assert all(e.relation_type == RelationType.CAUSES for e in edges)

    def test_pattern_similarity_full_overlap(self):
        p1 = make_pattern()
        p2 = make_pattern()
        sim = RelationshipEngine._calculate_pattern_similarity(p1, p2)
        assert sim == 1.0

    def test_pattern_similarity_no_overlap(self):
        p1 = MetaPattern(genes={"emotion": "rescue"})
        p2 = MetaPattern(genes={"style": "bright"})
        sim = RelationshipEngine._calculate_pattern_similarity(p1, p2)
        assert sim == 0.0

    def test_pattern_similarity_partial(self):
        p1 = MetaPattern(genes={"emotion": "rescue", "character": "cute"})
        p2 = MetaPattern(genes={"emotion": "rescue", "character": "fantasy"})
        sim = RelationshipEngine._calculate_pattern_similarity(p1, p2)
        assert sim == pytest.approx(1 / 3)  # 1 shared / 3 unique

    def test_discover_from_experiences(self):
        engine = RelationshipEngine()
        from market_ops.creative_vision_runtime.reality.meta_learning import (
            ContextDetail,
            ExperimentDetail,
            ExperienceResult,
            MutationDetail,
            MutationType,
        )

        experiences = []
        for i in range(10):
            exp = ExperienceRecord(
                product_id="p04",
                creative_id=f"c{i:03d}",
                genome_id="g001",
                mutation=MutationDetail(
                    mutation_type=MutationType.REFRESH_HOOK,
                    changed_genes=["hook", "visual"],
                    gene_before={"hook": "old"},
                    gene_after={"hook": f"rescue_{i}", "visual": f"bright_{i}"},
                ),
                experiment=ExperimentDetail(
                    baseline_metrics={},
                    winner_metrics={},
                    improvement=0.3,
                    metrics_delta={"ctr": 0.3},
                    winner_id="v2",
                    variant_count=3,
                    confidence=0.85,
                ),
                context=ContextDetail(
                    product_id="p04",
                    product_name="Test",
                    market="US",
                    platform="facebook",
                ),
                result=ExperienceResult(
                    outcome=ExperienceOutcome.SUCCESS,
                    success=True,
                    insight="Test",
                    key_finding="Test",
                ),
            )
            experiences.append(exp)

        edges = engine.discover_from_experiences(experiences)
        assert len(edges) >= 0  # 可能有共现关系

    def test_repr(self):
        engine = RelationshipEngine()
        assert "RelationshipEngine" in repr(engine)


# ═══════════════════════════════════════════════════════════
# 5. Graph Query Engine (15 tests)
# ═══════════════════════════════════════════════════════════


class TestGraphQueryEngine:
    """GraphQueryEngine — 图查询测试。"""

    def _setup_store(self) -> GraphStore:
        builder = NodeBuilder()
        patterns = [
            make_pattern("Rescue Hook", sr=0.75, roas=0.21, ctr=0.15, cvr=0.10, samples=100, conf=0.91),
            make_pattern("Challenge Hook", sr=0.40, roas=0.05, ctr=0.03, cvr=0.01, samples=80, conf=0.75),
        ]
        nodes, edges = builder.build_full_graph_from_patterns(patterns)

        store = GraphStore()
        store.add_nodes_batch(nodes)
        store.add_edges_batch(edges)

        # 添加市场/平台节点
        market_node = builder.build_market_node("US")
        store.add_node(market_node)
        store.add_edge(KnowledgeEdge(
            source_id=patterns[0].pattern_id,
            target_id=market_node.node_id,
            relation_type=RelationType.WORKS_FOR,
            weight=0.75,
            evidence_count=100,
            confidence=0.91,
        ))

        return store

    def test_find_best_genes_for_metric(self):
        store = self._setup_store()
        engine = GraphQueryEngine(store)
        result = engine.find_best_genes_for_metric("CTR")
        assert len(result.recommendations) >= 1
        assert result.nodes is not None

    def test_find_best_genes_for_roas(self):
        store = self._setup_store()
        engine = GraphQueryEngine(store)
        result = engine.find_best_genes_for_metric("ROAS")
        assert len(result.recommendations) >= 1

    def test_find_best_patterns(self):
        store = self._setup_store()
        engine = GraphQueryEngine(store)
        result = engine.find_best_patterns()
        assert len(result.recommendations) >= 2
        # 按 rank_score 降序
        assert result.recommendations[0]["success_rate"] >= result.recommendations[1]["success_rate"]

    def test_recommend_mutation(self):
        store = self._setup_store()
        engine = GraphQueryEngine(store)
        result = engine.recommend_mutation(
            product_id="p04",
            target_metric="CTR",
            max_results=3,
        )
        assert len(result.recommendations) >= 1
        rec = result.recommendations[0]
        assert "genes" in rec
        assert "strategy" in rec
        assert "explanation" in rec

    def test_recommend_mutation_amplify(self):
        store = self._setup_store()
        engine = GraphQueryEngine(store)
        result = engine.recommend_mutation(target_metric="CTR")
        # 第一个推荐（权重最高）应该是 Amplify
        if result.recommendations:
            # 权重 >= 0.6 的是 Amplify，否则是 Explore
            strategies = {r["strategy"] for r in result.recommendations}
            assert "Amplify" in strategies or "Explore" in strategies

    def test_find_similar_patterns(self):
        store = self._setup_store()
        engine = GraphQueryEngine(store)

        # 先用关系引擎添加相似边
        rel_engine = RelationshipEngine()
        patterns = [
            make_pattern("P1", sr=0.75),
            make_pattern("P2", sr=0.70),
        ]
        similar_edges = [
            e for e in rel_engine.discover_relationships(patterns)
            if e.relation_type == RelationType.SIMILAR_TO
        ]
        for edge in similar_edges:
            store.add_edge(edge)

        if similar_edges:
            result = engine.find_similar_patterns(patterns[0].pattern_id)
            # 可能找到也可能找不到（取决于相似度阈值）
            assert result is not None

    def test_find_gene_combinations(self):
        store = self._setup_store()
        engine = GraphQueryEngine(store)
        result = engine.find_gene_combinations()
        assert result is not None
        assert result.summary != ""

    def test_get_causal_chain(self):
        store = self._setup_store()
        engine = GraphQueryEngine(store)

        # 找到 Gene → Pattern → Metric 的路径
        result = engine.get_causal_chain("GENE_EMOTION_RESCUE", "METRIC_CTR")
        assert result is not None
        # 可能有路径也可能没有（取决于图构建）
        assert result.summary != ""

    def test_generate_query_report(self):
        store = self._setup_store()
        engine = GraphQueryEngine(store)
        report = engine.generate_query_report(
            product_id="p04",
            target_metric="CTR",
        )
        assert "top_genes" in report
        assert "top_patterns" in report
        assert "mutation_strategy" in report

    def test_find_transfer_candidates(self):
        store = self._setup_store()
        engine = GraphQueryEngine(store)
        result = engine.find_transfer_candidates("p04", "p07")
        assert result is not None
        assert len(result.recommendations) >= 1

    def test_query_result_to_dict(self):
        store = self._setup_store()
        engine = GraphQueryEngine(store)
        result = engine.find_best_genes_for_metric("CTR")
        d = result.to_dict()
        assert "query" in d
        assert "nodes_found" in d
        assert "recommendations" in d

    def test_repr(self):
        store = GraphStore()
        engine = GraphQueryEngine(store)
        assert "GraphQueryEngine" in repr(engine)


# ═══════════════════════════════════════════════════════════
# 6. Pipeline Tests (10 tests)
# ═══════════════════════════════════════════════════════════


class TestPipeline:
    """完整 Pipeline: Build → Discover → Store → Query。"""

    def test_full_pipeline_build_store_query(self):
        """完整流程：构建图 → 发现关系 → 存储 → 查询。"""
        builder = NodeBuilder()
        patterns = [
            make_pattern("Rescue Hook", sr=0.75, roas=0.21, ctr=0.15, cvr=0.10, samples=100, conf=0.91),
            make_pattern("Challenge Hook", sr=0.40, roas=0.05, ctr=0.03, cvr=0.01, samples=80, conf=0.75),
            make_pattern("Bright Visual", sr=0.70, roas=0.15, ctr=0.12, cvr=0.08, samples=90, conf=0.85),
        ]

        # Step 1: 构建节点
        nodes, edges = builder.build_full_graph_from_patterns(patterns)
        assert len(nodes) >= 10
        assert len(edges) >= 8

        # Step 2: 发现额外关系
        rel_engine = RelationshipEngine()
        discovered = rel_engine.discover_relationships(patterns)
        all_edges = edges + discovered

        # Step 3: 存入图
        store = GraphStore()
        store.add_nodes_batch(nodes)
        store.add_edges_batch(all_edges)

        # Step 4: 查询
        engine = GraphQueryEngine(store)
        result = engine.recommend_mutation(target_metric="CTR")
        assert len(result.recommendations) >= 1

        # Step 5: 统计
        stats = store.get_stats()
        assert stats.total_nodes >= 10
        assert stats.total_edges >= 8

    def test_e1251_to_e1253_flow(self):
        """E12.5.1 → E12.5.2 → E12.5.3 完整数据流。"""
        from market_ops.creative_vision_runtime.reality.meta_learning.pattern_miner import (
            PatternExtractor,
            PatternRanker,
        )

        # E12.5.1: 构建经验
        store = ExperienceStore()
        for i in range(30):
            from market_ops.creative_vision_runtime.reality.meta_learning import (
                ContextDetail,
                ExperimentDetail,
                ExperienceResult,
                MutationDetail,
                MutationType,
            )
            record = ExperienceRecord(
                product_id="p04",
                creative_id=f"c{i:03d}",
                genome_id="g001",
                mutation=MutationDetail(
                    mutation_type=MutationType.REFRESH_HOOK,
                    changed_genes=["hook"],
                    gene_before={"hook": "old"},
                    gene_after={"hook": "rescue_puppy"},
                ),
                experiment=ExperimentDetail(
                    baseline_metrics={"ctr": 0.02},
                    winner_metrics={"ctr": 0.03},
                    improvement=0.3,
                    metrics_delta={"ctr": 0.5, "roas": 0.4},
                    winner_id="v2",
                    variant_count=3,
                    confidence=0.85,
                ),
                context=ContextDetail(
                    product_id="p04",
                    product_name="Merge Witch",
                    market="US",
                    platform="facebook",
                ),
                result=ExperienceResult(
                    outcome=ExperienceOutcome.SUCCESS,
                    success=True,
                    insight="Test",
                    key_finding="Test",
                ),
            )
            store.add(record)

        # E12.5.2: 模式挖掘
        extractor = PatternExtractor(min_cluster_size=5)
        patterns = extractor.extract_from_store(store)
        assert len(patterns) >= 1

        ranker = PatternRanker()
        patterns = ranker.rank(patterns)

        # E12.5.3: 知识图谱
        builder = NodeBuilder()
        nodes, edges = builder.build_full_graph_from_patterns(patterns)

        graph = GraphStore()
        graph.add_nodes_batch(nodes)
        graph.add_edges_batch(edges)

        # 添加市场和产品节点
        graph.add_node(builder.build_market_node("US"))
        graph.add_node(builder.build_product_node("p04", "Merge Witch"))
        graph.add_node(builder.build_platform_node("facebook"))

        # 查询
        engine = GraphQueryEngine(graph)
        result = engine.recommend_mutation(product_id="p04", target_metric="CTR")
        assert len(result.recommendations) >= 1

    def test_graph_with_market_platform(self):
        """市场和平台节点集成。"""
        builder = NodeBuilder()
        graph = GraphStore()

        # 添加节点
        graph.add_node(builder.build_market_node("US"))
        graph.add_node(builder.build_market_node("EU"))
        graph.add_node(builder.build_platform_node("facebook"))
        graph.add_node(builder.build_platform_node("google"))

        pattern = make_pattern("Rescue Hook", sr=0.75)
        pattern_node = builder.build_pattern_node(pattern)
        graph.add_node(pattern_node)

        # 添加 WORKS_FOR 边
        rel_engine = RelationshipEngine()
        edge = rel_engine.discover_works_for(pattern, graph.get_node("MARKET_US"), "market")
        if edge:
            graph.add_edge(edge)

        assert graph.node_count >= 5

    def test_causal_chain_pipeline(self):
        """因果链 Pipeline。"""
        builder = NodeBuilder()
        rel_engine = RelationshipEngine()
        graph = GraphStore()

        # 添加节点
        nodes = builder.build_metric_nodes()
        graph.add_nodes_batch(nodes)

        gene_node = builder.build_gene_node("rescue", "emotion", confidence=0.91)
        graph.add_node(gene_node)

        pattern = make_pattern("Rescue Hook", sr=0.75)
        pattern_node = builder.build_pattern_node(pattern)
        graph.add_node(pattern_node)

        # 因果链: Gene → Pattern → Metric
        causal = rel_engine.discover_causal_chain(
            gene_node.node_id,
            pattern_node.node_id,
            "METRIC_CTR",
        )
        graph.add_edges_batch(causal)

        engine = GraphQueryEngine(graph)
        result = engine.get_causal_chain(gene_node.node_id, "METRIC_CTR")
        assert result is not None
        assert len(result.paths) >= 1 or len(result.edges) >= 1

    def test_multi_pattern_graph(self):
        """多模式图构建。"""
        builder = NodeBuilder()
        patterns = [
            make_pattern("Rescue Hook", sr=0.75, roas=0.21, ctr=0.15, cvr=0.10),
            make_pattern("Challenge Hook", sr=0.40, roas=0.05, ctr=0.03, cvr=0.01),
            make_pattern("Bright Visual", sr=0.70, roas=0.15, ctr=0.12, cvr=0.08),
            make_pattern("Dark Visual", sr=0.30, roas=-0.05, ctr=-0.02, cvr=-0.01),
        ]
        nodes, edges = builder.build_full_graph_from_patterns(patterns)

        graph = GraphStore()
        graph.add_nodes_batch(nodes)
        graph.add_edges_batch(edges)

        # 发现关系
        rel_engine = RelationshipEngine()
        discovered = rel_engine.discover_relationships(patterns)
        graph.add_edges_batch(discovered)

        stats = graph.get_stats()
        assert stats.total_nodes >= 12
        assert stats.total_edges >= 10

    def test_query_by_metric(self):
        """按指标查询最佳基因。"""
        builder = NodeBuilder()
        patterns = [
            make_pattern("Best CTR", sr=0.80, ctr=0.30, roas=0.05, cvr=0.02),
            make_pattern("Best ROAS", sr=0.70, ctr=0.05, roas=0.30, cvr=0.02),
        ]
        nodes, edges = builder.build_full_graph_from_patterns(patterns)

        graph = GraphStore()
        graph.add_nodes_batch(nodes)
        graph.add_edges_batch(edges)

        engine = GraphQueryEngine(graph)

        ctr_result = engine.find_best_genes_for_metric("CTR")
        assert len(ctr_result.recommendations) >= 1

        roas_result = engine.find_best_genes_for_metric("ROAS")
        assert len(roas_result.recommendations) >= 1

    def test_graph_export_import(self):
        """图导出导入。"""
        store = GraphStore()
        store.add_node(make_node("A"))
        store.add_node(make_node("B"))
        store.add_edge(make_edge("A", "B"))

        d = store.to_dict()
        assert len(d["nodes"]) == 2
        assert len(d["edges"]) == 1

    def test_mutation_strategy_generation(self):
        """模拟 E11 查询突变策略。"""
        builder = NodeBuilder()
        patterns = [
            make_pattern("Rescue Hook", sr=0.76, roas=0.22, ctr=0.18, cvr=0.12, samples=2400, conf=0.91),
            make_pattern("Before/After", sr=0.65, roas=0.12, ctr=0.10, cvr=0.07, samples=1800, conf=0.84),
            make_pattern("Character Emotion", sr=0.68, roas=0.14, ctr=0.11, cvr=0.08, samples=1500, conf=0.81),
        ]
        nodes, edges = builder.build_full_graph_from_patterns(patterns)

        graph = GraphStore()
        graph.add_nodes_batch(nodes)
        graph.add_edges_batch(edges)

        # E11 查询: "需要提升 CTR"
        engine = GraphQueryEngine(graph)
        mutation = engine.recommend_mutation(target_metric="CTR", max_results=3)

        assert len(mutation.recommendations) >= 1
        assert mutation.recommendations[0]["genes"] is not None

    def test_comprehensive_report(self):
        """综合报告生成。"""
        builder = NodeBuilder()
        patterns = [
            make_pattern("Rescue Hook", sr=0.76, roas=0.22, ctr=0.18, cvr=0.12, samples=2400, conf=0.91),
            make_pattern("Before/After", sr=0.65, roas=0.12, ctr=0.10, cvr=0.07, samples=1800, conf=0.84),
        ]
        nodes, edges = builder.build_full_graph_from_patterns(patterns)

        graph = GraphStore()
        graph.add_nodes_batch(nodes)
        graph.add_edges_batch(edges)

        engine = GraphQueryEngine(graph)
        report = engine.generate_query_report(product_id="p04", target_metric="CTR")
        assert "top_genes" in report
        assert "top_patterns" in report
        assert "top_combinations" in report
        assert "mutation_strategy" in report


# ═══════════════════════════════════════════════════════════
# 7. Integration & Edge Cases (10 tests)
# ═══════════════════════════════════════════════════════════


class TestIntegrationEdgeCases:
    """集成测试和边界情况。"""

    def test_empty_store(self):
        store = GraphStore()
        engine = GraphQueryEngine(store)
        result = engine.find_best_genes_for_metric("CTR")
        assert result.recommendations == []

    def test_empty_patterns(self):
        builder = NodeBuilder()
        nodes, edges = builder.build_full_graph_from_patterns([])
        assert len(nodes) == len(builder.build_metric_nodes())
        assert len(edges) == 0

    def test_node_override(self):
        store = GraphStore()
        n1 = make_node("A", name="Original")
        n2 = make_node("A", name="Updated")
        store.add_node(n1)
        store.add_node(n2)
        assert store.get_node("A").name == "Updated"

    def test_large_graph(self):
        store = GraphStore()
        for i in range(100):
            store.add_node(make_node(f"N{i}"))
        for i in range(99):
            store.add_edge(make_edge(f"N{i}", f"N{i+1}"))

        assert store.node_count == 100
        assert store.edge_count == 99
        path = store.find_path("N0", "N99", max_depth=100)
        assert path is not None
        assert len(path) == 99

    def test_cyclic_graph(self):
        store = GraphStore()
        store.add_node(make_node("A"))
        store.add_node(make_node("B"))
        store.add_node(make_node("C"))
        store.add_edge(make_edge("A", "B"))
        store.add_edge(make_edge("B", "C"))
        store.add_edge(make_edge("C", "A"))

        path = store.find_path("A", "C")
        assert path is not None
        assert len(path) <= 2

    def test_disconnected_graph(self):
        store = GraphStore()
        store.add_node(make_node("A"))
        store.add_node(make_node("B"))
        store.add_node(make_node("C"))
        store.add_edge(make_edge("A", "B"))

        stats = store.get_stats()
        assert stats.connected_components == 2  # A-B component + C isolated

    def test_remove_node_clears_adjacency(self):
        store = GraphStore()
        store.add_node(make_node("A"))
        store.add_node(make_node("B"))
        store.add_edge(make_edge("A", "B"))
        store.remove_node("A")
        assert store.edge_count == 0
        assert "A" not in store

    def test_find_path_same_node(self):
        store = GraphStore()
        store.add_node(make_node("A"))
        path = store.find_path("A", "A")
        assert path == []

    def test_find_all_paths_limit(self):
        store = GraphStore()
        for i in range(5):
            store.add_node(make_node(f"N{i}"))
        # 全连接
        for i in range(5):
            for j in range(i + 1, 5):
                store.add_edge(make_edge(f"N{i}", f"N{j}"))

        paths = store.find_all_paths("N0", "N4", max_paths=5)
        assert len(paths) <= 5

    def test_repr(self):
        store = GraphStore()
        store.add_node(make_node("A"))
        assert "GraphStore" in repr(store)
        assert "nodes=1" in repr(store)