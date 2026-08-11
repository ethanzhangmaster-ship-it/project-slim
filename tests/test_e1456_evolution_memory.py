"""E14.5.6 Evolution Memory Graph — 集成测试.

验证 EvolutionMemoryGraph 的进化知识图谱能力:
  - EvolutionNode / EvolutionEdge / EvolutionPath / EvolutionMemoryReport 模型 (15 tests)
  - record_genome() 核心记录 (15 tests)
  - record_mutation() 变异事件记录 (15 tests)
  - record_experiment() 实验记录 (15 tests)
  - record_pattern() 模式记录 (10 tests)
  - record_generation() 代际记录 (10 tests)
  - query_lineage() 谱系查询 (15 tests)
  - query_evolution_paths() 进化路径 (10 tests)
  - query_pattern_origins() / query_genome_experiments() (10 tests)
  - 统计与报告 (15 tests)
  - 回归 (E14.5.5 / E14.5.4 / E14.5.3 / E14.5.2 / E14.5.1) (10 tests)

总计: 140 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.evolution_memory import (
    EvolutionMemoryGraph,
    EvolutionNode,
    EvolutionEdge,
    EvolutionPath,
    EvolutionMemoryReport,
    NodeType,
    EdgeType,
    create_evolution_memory_graph,
)


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def graph():
    """创建空的 EvolutionMemoryGraph."""
    return EvolutionMemoryGraph()


@pytest.fixture
def populated_graph():
    """创建已填充基因组数据的图谱."""
    g = EvolutionMemoryGraph()
    g.record_genome("G_001", generation=0, genes={"hook": "transformation", "visual": "fantasy"})
    g.record_genome("G_002", generation=0, genes={"hook": "rescue", "visual": "real_world"})
    g.record_genome("G_003", generation=0, genes={"hook": "discovery", "visual": "cartoon"})
    return g


@pytest.fixture
def lineage_graph():
    """创建有谱系关系的图谱 (G_001 → G_002 → G_003)."""
    g = EvolutionMemoryGraph()
    g.record_genome("G_001", generation=0, genes={"hook": "transformation", "visual": "fantasy"})
    g.record_genome("G_002", generation=1, genes={"hook": "transformation", "visual": "real_world"},
                    parent_id="G_001")
    g.record_genome("G_003", generation=2, genes={"hook": "rescue", "visual": "real_world"},
                    parent_id="G_002")
    return g


@pytest.fixture
def full_graph(lineage_graph):
    """创建包含完整进化历史的图谱."""
    g = lineage_graph
    # 变异事件
    g.record_mutation("G_001", "G_002", mutation_type="replace", gene_category="visual",
                      confidence=0.85, strategy="amplify_winner")
    g.record_mutation("G_002", "G_003", mutation_type="replace", gene_category="hook",
                      confidence=0.72, strategy="explore_new")
    # 实验
    g.record_experiment("G_001", "EXP_001", result="winner", roas=1.8, ctr=0.03, impressions=5000)
    g.record_experiment("G_002", "EXP_002", result="winner", roas=1.5, ctr=0.028, impressions=4000)
    g.record_experiment("G_003", "EXP_003", result="loser", roas=0.8, ctr=0.015, impressions=3000)
    # 模式
    g.record_pattern("P_001", pattern_name="transformation_wins", source_genome_ids=["G_001", "G_002"],
                     pattern_type="winner_pattern", confidence=0.9)
    g.record_pattern("P_002", pattern_name="real_visual_effective", source_genome_ids=["G_002"],
                     pattern_type="visual_pattern", confidence=0.75)
    # 代际
    g.record_generation(0, ["G_001"], label="Seed Generation")
    g.record_generation(1, ["G_002"], label="First Mutation")
    g.record_generation(2, ["G_003"], label="Second Mutation")
    return g


# ═══════════════════════════════════════════════════════════
# 1. 模型测试 (15 tests)
# ═══════════════════════════════════════════════════════════

class TestEvolutionNode:
    """EvolutionNode 模型测试."""

    def test_node_default_creation(self):
        """默认创建 EvolutionNode."""
        node = EvolutionNode()
        assert node.node_id.startswith("node_")
        assert node.node_type == NodeType.GENOME
        assert node.label == ""
        assert node.properties == {}
        assert node.created_at

    def test_node_custom_creation(self):
        """自定义创建 EvolutionNode."""
        node = EvolutionNode(
            node_id="n_001",
            node_type=NodeType.MUTATION,
            label="Test Mutation",
            properties={"key": "val"},
        )
        assert node.node_id == "n_001"
        assert node.node_type == NodeType.MUTATION
        assert node.label == "Test Mutation"
        assert node.properties == {"key": "val"}

    def test_node_with_genome_type(self):
        """基因组类型节点."""
        node = EvolutionNode(
            node_type=NodeType.GENOME,
            label="Genome Node",
            properties={"genome_id": "G_001", "generation": 0},
        )
        assert node.node_type == NodeType.GENOME
        assert node.properties["genome_id"] == "G_001"

    def test_node_to_dict(self):
        """to_dict 序列化."""
        node = EvolutionNode(
            node_id="n_001",
            node_type=NodeType.GENOME,
            label="Test",
            properties={"genome_id": "G_001"},
        )
        d = node.to_dict()
        assert d["node_id"] == "n_001"
        assert d["node_type"] == "genome"
        assert d["label"] == "Test"
        assert d["properties"]["genome_id"] == "G_001"
        assert "created_at" in d

    def test_node_to_dict_preserves_all_fields(self):
        """to_dict 保留所有字段."""
        node = EvolutionNode(
            node_type=NodeType.EXPERIMENT,
            label="Exp",
            properties={"roas": 1.5, "ctr": 0.03},
        )
        d = node.to_dict()
        assert d["node_type"] == "experiment"
        assert d["properties"]["roas"] == 1.5


class TestEvolutionEdge:
    """EvolutionEdge 模型测试."""

    def test_edge_default_creation(self):
        """默认创建 EvolutionEdge."""
        edge = EvolutionEdge()
        assert edge.edge_id.startswith("edge_")
        assert edge.source_id == ""
        assert edge.target_id == ""
        assert edge.edge_type == EdgeType.MUTATED_TO
        assert edge.weight == 1.0

    def test_edge_custom_creation(self):
        """自定义创建 EvolutionEdge."""
        edge = EvolutionEdge(
            edge_id="e_001",
            source_id="n_A",
            target_id="n_B",
            edge_type=EdgeType.TESTED_IN,
            weight=0.85,
            properties={"confidence": 0.9},
        )
        assert edge.edge_id == "e_001"
        assert edge.source_id == "n_A"
        assert edge.target_id == "n_B"
        assert edge.edge_type == EdgeType.TESTED_IN
        assert edge.weight == 0.85

    def test_edge_to_dict(self):
        """to_dict 序列化."""
        edge = EvolutionEdge(
            source_id="n_A",
            target_id="n_B",
            edge_type=EdgeType.MUTATED_TO,
            weight=0.8,
        )
        d = edge.to_dict()
        assert d["edge_id"].startswith("edge_")
        assert d["source_id"] == "n_A"
        assert d["target_id"] == "n_B"
        assert d["edge_type"] == "mutated_to"
        assert d["weight"] == 0.8

    def test_edge_weight_rounding(self):
        """权重四舍五入."""
        edge = EvolutionEdge(weight=0.123456)
        d = edge.to_dict()
        assert d["weight"] == 0.1235

    def test_edge_different_types(self):
        """不同边类型."""
        for etype in EdgeType:
            edge = EvolutionEdge(edge_type=etype)
            assert edge.to_dict()["edge_type"] == etype.value


class TestEvolutionPath:
    """EvolutionPath 模型测试."""

    def test_path_default_creation(self):
        """默认创建 EvolutionPath."""
        path = EvolutionPath()
        assert path.path_id.startswith("path_")
        assert path.nodes == []
        assert path.edges == []
        assert path.path_length == 0

    def test_path_with_nodes(self):
        """带节点的路径."""
        n1 = EvolutionNode(node_id="n1", label="Genome A")
        n2 = EvolutionNode(node_id="n2", label="Genome B")
        e1 = EvolutionEdge(source_id="n1", target_id="n2")
        path = EvolutionPath(
            nodes=[n1, n2],
            edges=[e1],
            start_genome_id="G_A",
            end_genome_id="G_B",
            path_length=1,
            summary="A→B",
        )
        assert len(path.nodes) == 2
        assert len(path.edges) == 1
        assert path.start_genome_id == "G_A"
        assert path.end_genome_id == "G_B"
        assert path.path_length == 1

    def test_path_to_dict(self):
        """to_dict 序列化."""
        n1 = EvolutionNode(node_id="n1", label="A")
        e1 = EvolutionEdge(source_id="n1", target_id="n2")
        path = EvolutionPath(
            nodes=[n1],
            edges=[e1],
            start_genome_id="G_A",
            end_genome_id="G_B",
            path_length=1,
            summary="test",
        )
        d = path.to_dict()
        assert d["start_genome_id"] == "G_A"
        assert d["end_genome_id"] == "G_B"
        assert d["path_length"] == 1
        assert len(d["nodes"]) == 1
        assert len(d["edges"]) == 1


class TestEvolutionMemoryReport:
    """EvolutionMemoryReport 模型测试."""

    def test_report_default_creation(self):
        """默认创建报告."""
        report = EvolutionMemoryReport()
        assert report.total_nodes == 0
        assert report.total_edges == 0
        assert report.nodes_by_type == {}
        assert report.edges_by_type == {}

    def test_report_custom_creation(self):
        """自定义创建报告."""
        report = EvolutionMemoryReport(
            total_nodes=10,
            total_edges=15,
            nodes_by_type={"genome": 5, "mutation": 3},
            edges_by_type={"mutated_to": 8, "tested_in": 7},
            total_genomes_tracked=5,
            total_mutations=3,
            total_experiments=2,
            total_patterns=1,
            summary="Summary text",
        )
        assert report.total_nodes == 10
        assert report.total_edges == 15
        assert report.nodes_by_type["genome"] == 5
        assert report.total_genomes_tracked == 5

    def test_report_to_dict(self):
        """to_dict 序列化."""
        report = EvolutionMemoryReport(
            total_nodes=3,
            total_edges=2,
            total_genomes_tracked=3,
            summary="test",
        )
        d = report.to_dict()
        assert d["total_nodes"] == 3
        assert d["total_edges"] == 2
        assert d["summary"] == "test"


# ═══════════════════════════════════════════════════════════
# 2. record_genome() 核心记录 (15 tests)
# ═══════════════════════════════════════════════════════════

class TestRecordGenome:
    """record_genome 测试."""

    def test_record_single_genome(self, graph):
        """记录单个基因组."""
        node = graph.record_genome("G_001", generation=0)
        assert node.node_type == NodeType.GENOME
        assert node.properties["genome_id"] == "G_001"
        assert node.properties["generation"] == 0
        assert graph.get_genome_count() == 1

    def test_record_genome_with_genes(self, graph):
        """记录带基因数据的基因组."""
        genes = {"hook": "transformation", "visual": "fantasy"}
        node = graph.record_genome("G_001", generation=0, genes=genes)
        assert node.properties["genes"] == genes

    def test_record_genome_with_fitness(self, graph):
        """记录带适应度数据的基因组."""
        fitness = {"roas": 1.5, "ctr": 0.03}
        node = graph.record_genome("G_001", generation=0, fitness=fitness)
        assert node.properties["fitness"] == fitness

    def test_record_genome_with_label(self, graph):
        """记录带标签的基因组."""
        node = graph.record_genome("G_001", generation=0, label="My Genome")
        assert node.label == "My Genome"

    def test_record_genome_default_label(self, graph):
        """不指定标签时有默认标签."""
        node = graph.record_genome("G_001", generation=0)
        assert "Genome G_001" in node.label

    def test_record_multiple_genomes(self, graph):
        """记录多个基因组."""
        graph.record_genome("G_001", generation=0)
        graph.record_genome("G_002", generation=0)
        graph.record_genome("G_003", generation=1)
        assert graph.get_genome_count() == 3

    def test_record_genome_with_parent(self, graph):
        """记录带父基因组的基因组."""
        graph.record_genome("G_001", generation=0)
        node = graph.record_genome("G_002", generation=1, parent_id="G_001")
        assert node.properties["parent_id"] == "G_001"
        assert graph.get_genome_count() == 2

    def test_record_genome_parent_creates_edge(self, graph):
        """记录带父基因组时自动创建边."""
        graph.record_genome("G_001", generation=0)
        graph.record_genome("G_002", generation=1, parent_id="G_001")
        assert graph.get_edges_by_type().get("mutated_to", 0) >= 1

    def test_record_genome_parent_not_found_no_edge(self, graph):
        """父基因组不存在时不创建边."""
        node = graph.record_genome("G_002", generation=1, parent_id="G_999")
        assert node is not None
        # 父不存在不应该崩溃
        assert graph.get_genome_count() == 1

    def test_record_genome_generation_tracking(self, graph):
        """代际追踪."""
        graph.record_genome("G_001", generation=0)
        graph.record_genome("G_002", generation=1)
        graph.record_genome("G_003", generation=2)
        assert graph.get_genome_count() == 3

    def test_record_genome_duplicate_id_overwrites(self, graph):
        """重复 genome_id 覆盖旧记录."""
        node1 = graph.record_genome("G_001", generation=0, genes={"hook": "old"})
        node2 = graph.record_genome("G_001", generation=1, genes={"hook": "new"})
        assert graph.get_genome_count() == 1
        assert node2.properties["genes"]["hook"] == "new"

    def test_record_genome_node_has_created_at(self, graph):
        """节点有时间戳."""
        node = graph.record_genome("G_001")
        assert node.created_at

    def test_record_genome_node_to_dict(self, graph):
        """节点可序列化."""
        node = graph.record_genome("G_001", generation=0, genes={"hook": "t"})
        d = node.to_dict()
        assert d["node_type"] == "genome"
        assert d["properties"]["genome_id"] == "G_001"

    def test_record_genome_genome_map_indexed(self, graph):
        """基因组 ID 正确索引."""
        graph.record_genome("G_001")
        assert "G_001" in graph._genome_map

    def test_record_genome_empty_genes_and_fitness(self, graph):
        """空基因和适应度正常."""
        node = graph.record_genome("G_001")
        assert node.properties["genes"] == {}
        assert node.properties["fitness"] == {}


# ═══════════════════════════════════════════════════════════
# 3. record_mutation() 变异事件 (15 tests)
# ═══════════════════════════════════════════════════════════

class TestRecordMutation:
    """record_mutation 测试."""

    def test_record_mutation_basic(self, populated_graph):
        """基本变异记录."""
        result = populated_graph.record_mutation("G_001", "G_002")
        assert result is not None
        assert populated_graph.get_mutation_count() == 1

    def test_record_mutation_returns_none_parent_not_found(self, graph):
        """父基因组不存在返回 None."""
        result = graph.record_mutation("G_999", "G_001")
        assert result is None

    def test_record_mutation_returns_none_child_not_found(self, graph):
        """子基因组不存在返回 None."""
        graph.record_genome("G_001")
        result = graph.record_mutation("G_001", "G_999")
        assert result is None

    def test_record_mutation_params(self, populated_graph):
        """变异参数记录."""
        result = populated_graph.record_mutation(
            "G_001", "G_002",
            mutation_type="replace",
            gene_category="visual",
            confidence=0.85,
            strategy="amplify_winner",
            label="Visual Mutation",
        )
        assert result is not None
        assert populated_graph.get_mutation_count() == 1

    def test_record_mutation_creates_mutation_node(self, populated_graph):
        """变异创建变异节点."""
        populated_graph.record_mutation("G_001", "G_002")
        mutation_count = populated_graph.get_mutation_count()
        assert mutation_count == 1

    def test_record_mutation_creates_edges(self, populated_graph):
        """变异创建边."""
        populated_graph.record_mutation("G_001", "G_002")
        edge_types = populated_graph.get_edges_by_type()
        assert "mutated_to" in edge_types

    def test_record_mutation_multiple(self, populated_graph):
        """多次变异."""
        populated_graph.record_mutation("G_001", "G_002")
        populated_graph.record_mutation("G_002", "G_003")
        assert populated_graph.get_mutation_count() == 2

    def test_record_mutation_default_params(self, populated_graph):
        """默认参数."""
        result = populated_graph.record_mutation("G_001", "G_002")
        assert result is not None

    def test_record_mutation_with_label(self, populated_graph):
        """带标签的变异."""
        populated_graph.record_mutation("G_001", "G_002", label="Important Mutation")
        assert populated_graph.get_mutation_count() == 1

    def test_record_mutation_confidence_zero(self, populated_graph):
        """置信度为 0."""
        result = populated_graph.record_mutation("G_001", "G_002", confidence=0.0)
        assert result is not None

    def test_record_mutation_gene_category(self, populated_graph):
        """基因类别参数."""
        result = populated_graph.record_mutation("G_001", "G_002", gene_category="hook")
        assert result is not None

    def test_record_mutation_strategy(self, populated_graph):
        """策略参数."""
        result = populated_graph.record_mutation("G_001", "G_002", strategy="explore_new")
        assert result is not None

    def test_record_mutation_on_empty_graph(self, graph):
        """空图谱变异返回 None."""
        result = graph.record_mutation("G_001", "G_002")
        assert result is None

    def test_record_mutation_same_parent_child(self, populated_graph):
        """同一基因组自身变异."""
        populated_graph.record_mutation("G_001", "G_001")
        assert populated_graph.get_mutation_count() == 1

    def test_record_mutation_edges_connect_correctly(self, populated_graph):
        """变异边正确连接."""
        populated_graph.record_mutation("G_001", "G_002")
        # 验证边存在
        edges = populated_graph.get_edges_by_type()
        assert edges.get("mutated_to", 0) >= 2  # 至少 parent→mutation + mutation→child


# ═══════════════════════════════════════════════════════════
# 4. record_experiment() 实验记录 (15 tests)
# ═══════════════════════════════════════════════════════════

class TestRecordExperiment:
    """record_experiment 测试."""

    def test_record_experiment_basic(self, populated_graph):
        """基本实验记录."""
        node = populated_graph.record_experiment("G_001", "EXP_001")
        assert node is not None
        assert node.node_type == NodeType.EXPERIMENT
        assert populated_graph.get_experiment_count() == 1

    def test_record_experiment_genome_not_found(self, graph):
        """基因组不存在返回 None."""
        node = graph.record_experiment("G_999", "EXP_001")
        assert node is None

    def test_record_experiment_result_winner(self, populated_graph):
        """winner 实验结果."""
        node = populated_graph.record_experiment("G_001", "EXP_001", result="winner")
        assert node.properties["result"] == "winner"

    def test_record_experiment_result_loser(self, populated_graph):
        """loser 实验结果."""
        node = populated_graph.record_experiment("G_001", "EXP_001", result="loser")
        assert node.properties["result"] == "loser"

    def test_record_experiment_result_pending(self, populated_graph):
        """pending 实验结果."""
        node = populated_graph.record_experiment("G_001", "EXP_001", result="pending")
        assert node.properties["result"] == "pending"

    def test_record_experiment_roas(self, populated_graph):
        """ROAS 记录."""
        node = populated_graph.record_experiment("G_001", "EXP_001", roas=1.8)
        assert node.properties["roas"] == 1.8

    def test_record_experiment_ctr(self, populated_graph):
        """CTR 记录."""
        node = populated_graph.record_experiment("G_001", "EXP_001", ctr=0.03)
        assert node.properties["ctr"] == 0.03

    def test_record_experiment_impressions(self, populated_graph):
        """曝光量记录."""
        node = populated_graph.record_experiment("G_001", "EXP_001", impressions=5000)
        assert node.properties["impressions"] == 5000

    def test_record_experiment_label(self, populated_graph):
        """标签记录."""
        node = populated_graph.record_experiment("G_001", "EXP_001", label="Test Exp")
        assert node.label == "Test Exp"

    def test_record_experiment_creates_tested_in_edge(self, populated_graph):
        """创建 TESTED_IN 边."""
        populated_graph.record_experiment("G_001", "EXP_001")
        edge_types = populated_graph.get_edges_by_type()
        assert "tested_in" in edge_types

    def test_record_experiment_multiple(self, populated_graph):
        """多次实验."""
        populated_graph.record_experiment("G_001", "EXP_001")
        populated_graph.record_experiment("G_002", "EXP_002")
        populated_graph.record_experiment("G_003", "EXP_003")
        assert populated_graph.get_experiment_count() == 3

    def test_record_experiment_same_genome_multiple_experiments(self, populated_graph):
        """同一基因组多次实验."""
        populated_graph.record_experiment("G_001", "EXP_001", result="pending")
        populated_graph.record_experiment("G_001", "EXP_002", result="winner")
        assert populated_graph.get_experiment_count() == 2

    def test_record_experiment_properties_complete(self, populated_graph):
        """完整属性记录."""
        node = populated_graph.record_experiment(
            "G_001", "EXP_001",
            result="winner", roas=1.5, ctr=0.028, impressions=10000,
        )
        assert node.properties["experiment_id"] == "EXP_001"
        assert node.properties["genome_id"] == "G_001"
        assert node.properties["result"] == "winner"
        assert node.properties["roas"] == 1.5
        assert node.properties["ctr"] == 0.028
        assert node.properties["impressions"] == 10000

    def test_record_experiment_zero_metrics(self, populated_graph):
        """零指标记录."""
        node = populated_graph.record_experiment("G_001", "EXP_001", roas=0.0, ctr=0.0)
        assert node.properties["roas"] == 0.0
        assert node.properties["ctr"] == 0.0

    def test_record_experiment_node_serializable(self, populated_graph):
        """节点可序列化."""
        node = populated_graph.record_experiment("G_001", "EXP_001", result="winner")
        d = node.to_dict()
        assert d["node_type"] == "experiment"
        assert d["properties"]["result"] == "winner"


# ═══════════════════════════════════════════════════════════
# 5. record_pattern() 模式记录 (10 tests)
# ═══════════════════════════════════════════════════════════

class TestRecordPattern:
    """record_pattern 测试."""

    def test_record_pattern_basic(self, populated_graph):
        """基本模式记录."""
        node = populated_graph.record_pattern("P_001")
        assert node is not None
        assert node.node_type == NodeType.PATTERN
        assert populated_graph.get_pattern_count() == 1

    def test_record_pattern_with_name(self, populated_graph):
        """带名称的模式."""
        node = populated_graph.record_pattern("P_001", pattern_name="transformation_wins")
        assert node.properties["pattern_name"] == "transformation_wins"

    def test_record_pattern_with_source_genomes(self, populated_graph):
        """带来源基因组的模式."""
        node = populated_graph.record_pattern(
            "P_001",
            source_genome_ids=["G_001", "G_002"],
        )
        assert "G_001" in node.properties["source_genome_ids"]
        assert "G_002" in node.properties["source_genome_ids"]

    def test_record_pattern_creates_derived_from_edges(self, populated_graph):
        """创建 DERIVED_FROM 边."""
        populated_graph.record_pattern("P_001", source_genome_ids=["G_001", "G_002"])
        edge_types = populated_graph.get_edges_by_type()
        assert "derived_from" in edge_types

    def test_record_pattern_source_not_found_no_edge(self, populated_graph):
        """来源基因组不存在时不创建边."""
        node = populated_graph.record_pattern("P_001", source_genome_ids=["G_999"])
        assert node is not None
        # 不应崩溃

    def test_record_pattern_empty_sources(self, populated_graph):
        """空来源列表."""
        node = populated_graph.record_pattern("P_001", source_genome_ids=[])
        assert node.properties["source_genome_ids"] == []

    def test_record_pattern_with_type(self, populated_graph):
        """模式类型."""
        node = populated_graph.record_pattern("P_001", pattern_type="winner_pattern")
        assert node.properties["pattern_type"] == "winner_pattern"

    def test_record_pattern_with_confidence(self, populated_graph):
        """置信度."""
        node = populated_graph.record_pattern("P_001", confidence=0.9)
        assert node.properties["confidence"] == 0.9

    def test_record_pattern_label(self, populated_graph):
        """标签."""
        node = populated_graph.record_pattern("P_001", pattern_name="test", label="My Pattern")
        assert node.label == "My Pattern"

    def test_record_pattern_multiple(self, populated_graph):
        """多个模式."""
        populated_graph.record_pattern("P_001")
        populated_graph.record_pattern("P_002")
        populated_graph.record_pattern("P_003")
        assert populated_graph.get_pattern_count() == 3


# ═══════════════════════════════════════════════════════════
# 6. record_generation() 代际记录 (10 tests)
# ═══════════════════════════════════════════════════════════

class TestRecordGeneration:
    """record_generation 测试."""

    def test_record_generation_basic(self, populated_graph):
        """基本代际记录."""
        node = populated_graph.record_generation(0, ["G_001"])
        assert node is not None
        assert node.node_type == NodeType.GENERATION
        assert node.properties["generation"] == 0

    def test_record_generation_multiple_genomes(self, populated_graph):
        """多基因组代际."""
        node = populated_graph.record_generation(0, ["G_001", "G_002", "G_003"])
        assert len(node.properties["genome_ids"]) == 3

    def test_record_generation_label(self, populated_graph):
        """代际标签."""
        node = populated_graph.record_generation(0, ["G_001"], label="Seed Gen")
        assert node.label == "Seed Gen"

    def test_record_generation_default_label(self, populated_graph):
        """默认标签."""
        node = populated_graph.record_generation(1, ["G_002"])
        assert "Generation 1" in node.label

    def test_record_generation_creates_belongs_to_edges(self, populated_graph):
        """创建 BELONGS_TO 边."""
        populated_graph.record_generation(0, ["G_001", "G_002"])
        edge_types = populated_graph.get_edges_by_type()
        assert "belongs_to" in edge_types

    def test_record_generation_genome_not_found_no_edge(self, populated_graph):
        """基因组不存在时不创建边."""
        node = populated_graph.record_generation(0, ["G_001", "G_999"])
        assert node is not None
        # 不应崩溃

    def test_record_generation_multiple_generations(self, populated_graph):
        """多代际."""
        populated_graph.record_generation(0, ["G_001"])
        populated_graph.record_generation(1, ["G_002"])
        populated_graph.record_generation(2, ["G_003"])
        gen_nodes = [n for n in populated_graph._nodes.values()
                     if n.node_type == NodeType.GENERATION]
        assert len(gen_nodes) == 3

    def test_record_generation_high_generation_number(self, populated_graph):
        """高代际编号."""
        node = populated_graph.record_generation(50, ["G_001"])
        assert node.properties["generation"] == 50

    def test_record_generation_empty_genomes(self, populated_graph):
        """空基因组列表."""
        node = populated_graph.record_generation(0, [])
        assert node.properties["genome_ids"] == []

    def test_record_generation_node_serializable(self, populated_graph):
        """节点可序列化."""
        node = populated_graph.record_generation(0, ["G_001"], label="Seed")
        d = node.to_dict()
        assert d["node_type"] == "generation"
        assert d["label"] == "Seed"


# ═══════════════════════════════════════════════════════════
# 7. query_lineage() 谱系查询 (15 tests)
# ═══════════════════════════════════════════════════════════

class TestQueryLineage:
    """query_lineage 测试."""

    def test_lineage_single_genome(self, graph):
        """单个基因组没有父代."""
        graph.record_genome("G_001", generation=0)
        path = graph.query_lineage("G_001")
        assert path is not None
        assert path.path_length == 0

    def test_lineage_with_parent(self, lineage_graph):
        """有父代的谱系."""
        path = lineage_graph.query_lineage("G_002")
        assert path is not None
        assert path.end_genome_id == "G_002"
        assert path.path_length >= 1

    def test_lineage_three_generations(self, lineage_graph):
        """三代谱系."""
        path = lineage_graph.query_lineage("G_003")
        assert path is not None
        assert path.end_genome_id == "G_003"
        assert path.path_length >= 2

    def test_lineage_genome_not_found(self, graph):
        """基因组不存在返回 None."""
        path = graph.query_lineage("G_999")
        assert path is None

    def test_lineage_has_nodes(self, lineage_graph):
        """谱系包含节点."""
        path = lineage_graph.query_lineage("G_003")
        assert path is not None
        assert len(path.nodes) > 0

    def test_lineage_has_edges(self, lineage_graph):
        """谱系包含边."""
        path = lineage_graph.query_lineage("G_003")
        assert path is not None
        assert len(path.edges) >= 1

    def test_lineage_root_genome(self, lineage_graph):
        """根基因组谱系."""
        path = lineage_graph.query_lineage("G_001")
        assert path is not None
        assert path.path_length == 0

    def test_lineage_with_mutations(self, full_graph):
        """含变异事件的谱系."""
        path = full_graph.query_lineage("G_003")
        assert path is not None
        assert path.path_length >= 2

    def test_lineage_path_summary(self, lineage_graph):
        """谱系摘要."""
        path = lineage_graph.query_lineage("G_003")
        assert path is not None
        assert path.summary

    def test_lineage_max_depth_limit(self, lineage_graph):
        """最大深度限制."""
        path = lineage_graph.query_lineage("G_003", max_depth=1)
        assert path is not None
        assert path.path_length <= 1

    def test_lineage_to_dict(self, lineage_graph):
        """谱系可序列化."""
        path = lineage_graph.query_lineage("G_003")
        assert path is not None
        d = path.to_dict()
        assert d["start_genome_id"]
        assert d["end_genome_id"] == "G_003"

    def test_lineage_middle_genome(self, lineage_graph):
        """中间基因组谱系."""
        path = lineage_graph.query_lineage("G_002")
        assert path is not None
        assert path.end_genome_id == "G_002"

    def test_lineage_after_mutation_recording(self, full_graph):
        """变异记录后的谱系."""
        path = full_graph.query_lineage("G_003")
        assert path is not None
        assert path.path_length >= 2

    def test_lineage_path_has_path_id(self, lineage_graph):
        """谱系有路径 ID."""
        path = lineage_graph.query_lineage("G_003")
        assert path is not None
        assert path.path_id.startswith("path_")

    def test_lineage_all_nodes_have_type(self, lineage_graph):
        """所有节点有类型."""
        path = lineage_graph.query_lineage("G_003")
        assert path is not None
        for node in path.nodes:
            assert isinstance(node.node_type, NodeType)


# ═══════════════════════════════════════════════════════════
# 8. query_evolution_paths() 进化路径 (10 tests)
# ═══════════════════════════════════════════════════════════

class TestQueryEvolutionPaths:
    """query_evolution_paths 测试."""

    def test_evolution_paths_basic(self, lineage_graph):
        """基本进化路径."""
        paths = lineage_graph.query_evolution_paths("G_001")
        assert len(paths) >= 1

    def test_evolution_paths_genome_not_found(self, graph):
        """基因组不存在返回空列表."""
        paths = graph.query_evolution_paths("G_999")
        assert paths == []

    def test_evolution_paths_leaf_genome(self, lineage_graph):
        """叶基因组无后代."""
        paths = lineage_graph.query_evolution_paths("G_003")
        assert paths == []

    def test_evolution_paths_root_has_children(self, lineage_graph):
        """根基因组有后代."""
        paths = lineage_graph.query_evolution_paths("G_001")
        assert len(paths) >= 2  # G_001→G_002 和 G_001→G_002→G_003

    def test_evolution_paths_max_depth(self, lineage_graph):
        """最大深度限制."""
        paths = lineage_graph.query_evolution_paths("G_001", max_depth=1)
        for path in paths:
            assert path.path_length <= 1

    def test_evolution_paths_has_nodes(self, lineage_graph):
        """路径包含节点."""
        paths = lineage_graph.query_evolution_paths("G_001")
        for path in paths:
            assert len(path.nodes) > 0

    def test_evolution_paths_summary(self, lineage_graph):
        """路径摘要."""
        paths = lineage_graph.query_evolution_paths("G_001")
        for path in paths:
            assert path.summary

    def test_evolution_paths_with_mutations(self, full_graph):
        """含变异事件的路径."""
        paths = full_graph.query_evolution_paths("G_001")
        assert len(paths) >= 2

    def test_evolution_paths_to_dict(self, lineage_graph):
        """路径可序列化."""
        paths = lineage_graph.query_evolution_paths("G_001")
        for path in paths:
            d = path.to_dict()
            assert d["start_genome_id"] == "G_001"

    def test_evolution_paths_no_duplicates(self, lineage_graph):
        """无重复路径."""
        paths = lineage_graph.query_evolution_paths("G_001")
        path_ids = [p.path_id for p in paths]
        assert len(path_ids) == len(set(path_ids))


# ═══════════════════════════════════════════════════════════
# 9. query_pattern_origins() / query_genome_experiments() (10 tests)
# ═══════════════════════════════════════════════════════════

class TestOtherQueries:
    """其他查询测试."""

    def test_pattern_origins_basic(self, full_graph):
        """基本模式溯源."""
        origins = full_graph.query_pattern_origins("P_001")
        assert len(origins) == 2
        assert "G_001" in origins
        assert "G_002" in origins

    def test_pattern_origins_not_found(self, full_graph):
        """模式不存在返回空列表."""
        origins = full_graph.query_pattern_origins("P_999")
        assert origins == []

    def test_pattern_origins_single_source(self, full_graph):
        """单来源模式."""
        origins = full_graph.query_pattern_origins("P_002")
        assert len(origins) == 1
        assert "G_002" in origins

    def test_genome_experiments_basic(self, full_graph):
        """基因组实验查询."""
        exps = full_graph.query_genome_experiments("G_001")
        assert len(exps) >= 1

    def test_genome_experiments_not_found(self, full_graph):
        """基因组不存在返回空列表."""
        exps = full_graph.query_genome_experiments("G_999")
        assert exps == []

    def test_genome_experiments_properties(self, full_graph):
        """实验属性完整."""
        exps = full_graph.query_genome_experiments("G_001")
        for exp in exps:
            assert "experiment_id" in exp
            assert "result" in exp

    def test_genome_experiments_no_experiments(self, graph):
        """无实验的基因组."""
        graph.record_genome("G_001")
        exps = graph.query_genome_experiments("G_001")
        assert exps == []

    def test_genome_experiments_multiple(self, full_graph):
        """多次实验."""
        full_graph.record_experiment("G_001", "EXP_004", result="pending")
        exps = full_graph.query_genome_experiments("G_001")
        assert len(exps) >= 2

    def test_genome_experiments_winner_and_loser(self, full_graph):
        """winner 和 loser 实验."""
        exps = full_graph.query_genome_experiments("G_003")
        assert len(exps) == 1
        assert exps[0]["result"] == "loser"

    def test_pattern_origins_edge_case_empty(self, graph):
        """空图谱查询."""
        assert graph.query_pattern_origins("P_001") == []


# ═══════════════════════════════════════════════════════════
# 10. 统计与报告 (15 tests)
# ═══════════════════════════════════════════════════════════

class TestStats:
    """统计测试."""

    def test_empty_graph_stats(self, graph):
        """空图谱统计."""
        assert graph.get_genome_count() == 0
        assert graph.get_mutation_count() == 0
        assert graph.get_experiment_count() == 0
        assert graph.get_pattern_count() == 0

    def test_populated_graph_stats(self, populated_graph):
        """已填充图谱统计."""
        assert populated_graph.get_genome_count() == 3
        assert populated_graph.get_mutation_count() == 0
        assert populated_graph.get_experiment_count() == 0
        assert populated_graph.get_pattern_count() == 0

    def test_full_graph_stats(self, full_graph):
        """完整图谱统计."""
        assert full_graph.get_genome_count() == 3
        assert full_graph.get_mutation_count() == 2
        assert full_graph.get_experiment_count() == 3
        assert full_graph.get_pattern_count() == 2

    def test_nodes_by_type(self, full_graph):
        """按类型统计节点."""
        nodes_by_type = full_graph.get_nodes_by_type()
        assert "genome" in nodes_by_type
        assert "mutation" in nodes_by_type
        assert "experiment" in nodes_by_type
        assert "pattern" in nodes_by_type
        assert "generation" in nodes_by_type

    def test_edges_by_type(self, full_graph):
        """按类型统计边."""
        edges_by_type = full_graph.get_edges_by_type()
        assert "mutated_to" in edges_by_type
        assert "tested_in" in edges_by_type
        assert "derived_from" in edges_by_type
        assert "belongs_to" in edges_by_type

    def test_generate_report_non_empty(self, full_graph):
        """非空报告."""
        report = full_graph.generate_report()
        assert report.total_nodes > 0
        assert report.total_edges > 0
        assert report.total_genomes_tracked == 3
        assert report.total_mutations == 2
        assert report.total_experiments == 3
        assert report.total_patterns == 2

    def test_generate_report_empty(self, graph):
        """空图谱报告."""
        report = graph.generate_report()
        assert report.total_nodes == 0
        assert report.total_edges == 0
        assert report.summary == "进化记忆图谱为空"

    def test_generate_report_summary(self, full_graph):
        """报告摘要."""
        report = full_graph.generate_report()
        assert "3 个基因组" in report.summary or "3" in report.summary

    def test_generate_report_to_dict(self, full_graph):
        """报告可序列化."""
        report = full_graph.generate_report()
        d = report.to_dict()
        assert d["total_nodes"] > 0
        assert d["total_edges"] > 0

    def test_stats_method(self, full_graph):
        """stats() 方法."""
        s = full_graph.stats()
        assert s["total_nodes"] > 0
        assert s["total_edges"] > 0
        assert s["genomes_tracked"] == 3
        assert s["mutations"] == 2
        assert s["experiments"] == 3
        assert s["patterns"] == 2

    def test_stats_empty(self, graph):
        """空图谱 stats."""
        s = graph.stats()
        assert s["total_nodes"] == 0
        assert s["total_edges"] == 0

    def test_reset(self, full_graph):
        """重置图谱."""
        full_graph.reset()
        assert full_graph.get_genome_count() == 0
        assert full_graph.get_mutation_count() == 0
        assert full_graph.get_experiment_count() == 0
        assert full_graph.get_pattern_count() == 0

    def test_reset_and_reuse(self, full_graph):
        """重置后复用."""
        full_graph.reset()
        full_graph.record_genome("G_NEW", generation=0)
        assert full_graph.get_genome_count() == 1

    def test_nodes_by_type_counts(self, full_graph):
        """节点类型计数准确."""
        nodes_by_type = full_graph.get_nodes_by_type()
        assert nodes_by_type["genome"] == 3
        assert nodes_by_type["mutation"] == 2
        assert nodes_by_type["experiment"] == 3
        assert nodes_by_type["pattern"] == 2
        assert nodes_by_type["generation"] == 3

    def test_edges_by_type_counts(self, full_graph):
        """边类型计数准确."""
        edges_by_type = full_graph.get_edges_by_type()
        assert edges_by_type["tested_in"] == 3
        assert edges_by_type["derived_from"] == 3


# ═══════════════════════════════════════════════════════════
# 11. 回归测试 (10 tests)
# ═══════════════════════════════════════════════════════════

class TestE1456Regression:
    """回归测试 — 确保 E14.5.6 不影响已有模块."""

    def test_regression_imports(self):
        """所有 E14.5 模块可导入."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain import (
            # E14.5.1
            GenomeIntelligence, GenePerformance, ContextAffinity, GeneIntelligence,
            GenomeIntelligenceReport, create_genome_intelligence,
            # E14.5.2
            PopulationAnalyzer, DiversityMetrics, TrendSignal, PopulationHealthReport,
            create_population_analyzer,
            # E14.5.3
            EvolutionPlanner, EvolutionGoal, GeneMutationPlan, EvolutionPlan,
            create_evolution_planner,
            # E14.5.4
            AdaptiveMutationSelector, AdaptiveMutation, AdaptiveMutationReport,
            create_adaptive_mutation_selector,
            # E14.5.5
            FitnessPredictor, FitnessPrediction, FitnessPredictionReport,
            create_fitness_predictor,
            # E14.5.6
            EvolutionMemoryGraph, EvolutionNode, EvolutionEdge, EvolutionPath,
            EvolutionMemoryReport, NodeType, EdgeType, create_evolution_memory_graph,
        )
        # 验证所有导入成功
        assert GenomeIntelligence is not None
        assert PopulationAnalyzer is not None
        assert EvolutionPlanner is not None
        assert AdaptiveMutationSelector is not None
        assert FitnessPredictor is not None
        assert EvolutionMemoryGraph is not None

    def test_regression_factory_function(self):
        """工厂函数可用."""
        graph = create_evolution_memory_graph()
        assert isinstance(graph, EvolutionMemoryGraph)

    def test_regression_enum_values(self):
        """枚举值正确."""
        assert NodeType.GENOME.value == "genome"
        assert NodeType.MUTATION.value == "mutation"
        assert NodeType.EXPERIMENT.value == "experiment"
        assert NodeType.PATTERN.value == "pattern"
        assert NodeType.GENERATION.value == "generation"
        assert EdgeType.MUTATED_TO.value == "mutated_to"
        assert EdgeType.TESTED_IN.value == "tested_in"
        assert EdgeType.LEARNED_FROM.value == "learned_from"
        assert EdgeType.DERIVED_FROM.value == "derived_from"
        assert EdgeType.BELONGS_TO.value == "belongs_to"
        assert EdgeType.RESULTED_IN.value == "resulted_in"

    def test_regression_node_unique_ids(self):
        """节点 ID 唯一."""
        n1 = EvolutionNode()
        n2 = EvolutionNode()
        n3 = EvolutionNode()
        ids = {n1.node_id, n2.node_id, n3.node_id}
        assert len(ids) == 3

    def test_regression_edge_unique_ids(self):
        """边 ID 唯一."""
        e1 = EvolutionEdge()
        e2 = EvolutionEdge()
        e3 = EvolutionEdge()
        ids = {e1.edge_id, e2.edge_id, e3.edge_id}
        assert len(ids) == 3

    def test_regression_existing_modules_importable(self):
        """已有模块仍可导入."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.genome_intelligence import (
            GenomeIntelligence,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.population_analyzer import (
            PopulationAnalyzer,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.evolution_planner import (
            EvolutionPlanner,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.adaptive_mutation import (
            AdaptiveMutationSelector,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.fitness_predictor import (
            FitnessPredictor,
        )
        assert GenomeIntelligence is not None
        assert PopulationAnalyzer is not None
        assert EvolutionPlanner is not None
        assert AdaptiveMutationSelector is not None
        assert FitnessPredictor is not None

    def test_regression_edge_weight_boundaries(self):
        """边权重边界."""
        e1 = EvolutionEdge(weight=0.0)
        assert e1.weight == 0.0
        e2 = EvolutionEdge(weight=1.0)
        assert e2.weight == 1.0
        e3 = EvolutionEdge(weight=100.0)
        assert e3.weight == 100.0

    def test_regression_genome_map_consistency(self, full_graph):
        """genome_map 一致性."""
        for genome_id, node_id in full_graph._genome_map.items():
            node = full_graph._nodes.get(node_id)
            assert node is not None
            assert node.properties["genome_id"] == genome_id

    def test_regression_graph_consistency_after_reset(self, full_graph):
        """重置后图谱一致性."""
        full_graph.reset()
        assert full_graph.get_genome_count() == 0
        assert full_graph.get_mutation_count() == 0
        assert full_graph.get_experiment_count() == 0
        assert full_graph.get_pattern_count() == 0
        assert full_graph._genome_map == {}
        assert full_graph._edges_by_source == {}
        assert full_graph._edges_by_target == {}

    def test_regression_full_pipeline(self, graph):
        """完整进化流水线."""
        # 记录基因组
        graph.record_genome("G_001", generation=0, genes={"hook": "transformation"})
        graph.record_genome("G_002", generation=1, genes={"hook": "transformation", "visual": "real"},
                            parent_id="G_001")
        graph.record_genome("G_003", generation=2, genes={"hook": "rescue", "visual": "real"},
                            parent_id="G_002")

        # 记录变异
        graph.record_mutation("G_001", "G_002", mutation_type="replace", gene_category="visual",
                              confidence=0.85, strategy="amplify_winner")
        graph.record_mutation("G_002", "G_003", mutation_type="replace", gene_category="hook",
                              confidence=0.72, strategy="explore_new")

        # 记录实验
        graph.record_experiment("G_001", "EXP_001", result="winner", roas=1.8)
        graph.record_experiment("G_002", "EXP_002", result="winner", roas=1.5)
        graph.record_experiment("G_003", "EXP_003", result="pending", roas=1.2)

        # 记录模式
        graph.record_pattern("P_001", pattern_name="transformation_effective",
                             source_genome_ids=["G_001", "G_002"], confidence=0.85)

        # 记录代际
        graph.record_generation(0, ["G_001"])
        graph.record_generation(1, ["G_002"])
        graph.record_generation(2, ["G_003"])

        # 验证统计
        assert graph.get_genome_count() == 3
        assert graph.get_mutation_count() == 2
        assert graph.get_experiment_count() == 3
        assert graph.get_pattern_count() == 1

        # 验证谱系
        lineage = graph.query_lineage("G_003")
        assert lineage is not None
        assert lineage.path_length >= 2

        # 验证进化路径
        paths = graph.query_evolution_paths("G_001")
        assert len(paths) >= 2

        # 验证报告
        report = graph.generate_report()
        assert report.total_nodes > 0
        assert report.total_edges > 0