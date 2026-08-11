"""E14.5.6 Evolution Memory Graph — 创意进化知识图谱.

职责:
  1. 记录基因组的完整进化历史 (Genome → Mutation → Experiment → Pattern)
  2. 构建进化知识图谱 (节点 + 有向边)
  3. 支持谱系查询 (谁变异出谁、谁从谁学习的)
  4. 长期进化记忆 — 跨代际追踪进化路径

与 E14.4.4 StrategyMemory 的区别:
  - StrategyMemory: 记录「策略」层面的决策 (什么策略有效)
  - EvolutionMemoryGraph: 记录「进化」层面的历史 (基因组的谱系演化)

核心概念:
  - EvolutionNode: 进化节点 (GENOME / MUTATION / EXPERIMENT / PATTERN)
  - EvolutionEdge: 有向边 (MUTATED_TO / TESTED_IN / LEARNED_FROM / DERIVED_FROM)
  - 图谱可查询: 追溯某个基因组的完整进化链

数据流:
  Genome created → record_genome()
  Mutation applied → record_mutation(parent, child)
  Experiment run → record_experiment(genome, result)
  Pattern learned → record_pattern(pattern, source_genomes)
       ↓
  EvolutionMemoryGraph (持久化)
       ↓
  query_lineage() / query_evolution_paths() / query_pattern_origins()
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════════════

class NodeType(str, Enum):
    """进化节点类型."""
    GENOME = "genome"         # 基因组
    MUTATION = "mutation"     # 变异事件
    EXPERIMENT = "experiment" # 实验
    PATTERN = "pattern"       # 学习到的模式
    GENERATION = "generation" # 代际


class EdgeType(str, Enum):
    """进化边类型."""
    MUTATED_TO = "mutated_to"        # 变异产生子代
    TESTED_IN = "tested_in"          # 基因组参与实验
    LEARNED_FROM = "learned_from"    # 从基因组学习到模式
    DERIVED_FROM = "derived_from"    # 模式来源于基因组
    BELONGS_TO = "belongs_to"        # 基因组属于某代
    RESULTED_IN = "resulted_in"      # 实验产生结果


# ═══════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════

@dataclass
class EvolutionNode:
    """进化图谱节点.

    Attributes:
        node_id: 节点 ID
        node_type: 节点类型
        label: 节点标签
        properties: 节点属性
        created_at: 创建时间
    """
    node_id: str = field(default_factory=lambda: f"node_{uuid.uuid4().hex[:8]}")
    node_type: NodeType = NodeType.GENOME
    label: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "label": self.label,
            "properties": self.properties,
            "created_at": self.created_at,
        }


@dataclass
class EvolutionEdge:
    """进化图谱有向边.

    Attributes:
        edge_id: 边 ID
        source_id: 源节点 ID
        target_id: 目标节点 ID
        edge_type: 边类型
        weight: 边权重
        properties: 边属性
        created_at: 创建时间
    """
    edge_id: str = field(default_factory=lambda: f"edge_{uuid.uuid4().hex[:8]}")
    source_id: str = ""
    target_id: str = ""
    edge_type: EdgeType = EdgeType.MUTATED_TO
    weight: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type.value,
            "weight": round(self.weight, 4),
            "properties": self.properties,
            "created_at": self.created_at,
        }


@dataclass
class EvolutionPath:
    """进化路径 — 从一个基因组到另一个基因组的完整路径.

    Attributes:
        path_id: 路径 ID
        nodes: 路径上的节点序列
        edges: 路径上的边序列
        start_genome_id: 起始基因组 ID
        end_genome_id: 终点基因组 ID
        path_length: 路径长度 (边的数量)
        summary: 路径摘要
    """
    path_id: str = field(default_factory=lambda: f"path_{uuid.uuid4().hex[:8]}")
    nodes: list[EvolutionNode] = field(default_factory=list)
    edges: list[EvolutionEdge] = field(default_factory=list)
    start_genome_id: str = ""
    end_genome_id: str = ""
    path_length: int = 0
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path_id": self.path_id,
            "start_genome_id": self.start_genome_id,
            "end_genome_id": self.end_genome_id,
            "path_length": self.path_length,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "summary": self.summary,
        }


@dataclass
class EvolutionMemoryReport:
    """进化记忆报告.

    Attributes:
        report_id: 报告 ID
        total_nodes: 总节点数
        total_edges: 总边数
        nodes_by_type: 按类型统计节点
        edges_by_type: 按类型统计边
        total_genomes_tracked: 追踪的基因组数
        total_mutations: 变异事件数
        total_experiments: 实验数
        total_patterns: 模式数
        summary: 报告摘要
        created_at: 创建时间
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    total_nodes: int = 0
    total_edges: int = 0
    nodes_by_type: dict[str, int] = field(default_factory=dict)
    edges_by_type: dict[str, int] = field(default_factory=dict)
    total_genomes_tracked: int = 0
    total_mutations: int = 0
    total_experiments: int = 0
    total_patterns: int = 0
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "nodes_by_type": self.nodes_by_type,
            "edges_by_type": self.edges_by_type,
            "total_genomes_tracked": self.total_genomes_tracked,
            "total_mutations": self.total_mutations,
            "total_experiments": self.total_experiments,
            "total_patterns": self.total_patterns,
            "summary": self.summary,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════
# EvolutionMemoryGraph
# ═══════════════════════════════════════════════════════════

class EvolutionMemoryGraph:
    """创意进化知识图谱 — 记录基因组进化历史.

    核心功能:
      1. 记录基因组创建 (record_genome)
      2. 记录变异事件 (record_mutation: parent → child)
      3. 记录实验结果 (record_experiment)
      4. 记录学习模式 (record_pattern)
      5. 查询进化路径 (query_lineage, query_evolution_paths)

    图谱结构:
      GENOME → MUTATED_TO → GENOME  (变异链)
      GENOME → TESTED_IN → EXPERIMENT  (实验链)
      EXPERIMENT → RESULTED_IN → PATTERN  (学习链)
      PATTERN → DERIVED_FROM → GENOME  (溯源链)

    用法:
        graph = EvolutionMemoryGraph()
        graph.record_genome("genome_001", generation=0, genes={...})
        graph.record_mutation("genome_001", "genome_002", strategy="winner_pattern")
        graph.record_experiment("genome_002", "exp_001", result="winner")
        lineage = graph.query_lineage("genome_002")
    """

    def __init__(self) -> None:
        self._nodes: dict[str, EvolutionNode] = {}
        self._edges: dict[str, EvolutionEdge] = {}
        # 辅助索引
        self._genome_map: dict[str, str] = {}  # genome_id → node_id
        self._edges_by_source: dict[str, list[str]] = defaultdict(list)
        self._edges_by_target: dict[str, list[str]] = defaultdict(list)

    # ── 记录 ──────────────────────────────────────────────

    def record_genome(
        self,
        genome_id: str,
        generation: int = 0,
        genes: dict[str, Any] | None = None,
        fitness: dict[str, float] | None = None,
        parent_id: str | None = None,
        label: str = "",
    ) -> EvolutionNode:
        """记录一个基因组.

        Args:
            genome_id: 基因组 ID
            generation: 代际编号
            genes: 基因数据
            fitness: 适应度数据
            parent_id: 父基因组 ID
            label: 节点标签

        Returns:
            EvolutionNode: 创建的节点
        """
        node = EvolutionNode(
            node_type=NodeType.GENOME,
            label=label or f"Genome {genome_id}",
            properties={
                "genome_id": genome_id,
                "generation": generation,
                "genes": genes or {},
                "fitness": fitness or {},
                "parent_id": parent_id,
            },
        )
        self._nodes[node.node_id] = node
        self._genome_map[genome_id] = node.node_id

        # 如果连接到父基因组
        if parent_id and parent_id in self._genome_map:
            parent_node_id = self._genome_map[parent_id]
            self._add_edge(
                parent_node_id, node.node_id,
                EdgeType.MUTATED_TO,
                weight=1.0,
                properties={"generation": generation},
            )

        return node

    def record_mutation(
        self,
        parent_genome_id: str,
        child_genome_id: str,
        mutation_type: str = "replace",
        gene_category: str = "",
        confidence: float = 0.0,
        strategy: str = "",
        label: str = "",
    ) -> EvolutionEdge | None:
        """记录一次变异事件.

        Args:
            parent_genome_id: 父基因组 ID
            child_genome_id: 子基因组 ID
            mutation_type: 变异类型
            gene_category: 基因类别
            confidence: 置信度
            strategy: 变异策略
            label: 边标签

        Returns:
            EvolutionEdge | None: 创建的边
        """
        if parent_genome_id not in self._genome_map:
            return None
        if child_genome_id not in self._genome_map:
            return None

        source_id = self._genome_map[parent_genome_id]
        target_id = self._genome_map[child_genome_id]

        # 创建变异事件节点
        mutation_node = EvolutionNode(
            node_type=NodeType.MUTATION,
            label=label or f"Mutation {parent_genome_id}→{child_genome_id}",
            properties={
                "parent_genome_id": parent_genome_id,
                "child_genome_id": child_genome_id,
                "mutation_type": mutation_type,
                "gene_category": gene_category,
                "confidence": confidence,
                "strategy": strategy,
            },
        )
        self._nodes[mutation_node.node_id] = mutation_node

        # 父基因组 → 变异节点
        edge1 = self._add_edge(source_id, mutation_node.node_id, EdgeType.MUTATED_TO,
                               weight=confidence if confidence > 0 else 1.0)
        # 变异节点 → 子基因组
        edge2 = self._add_edge(mutation_node.node_id, target_id, EdgeType.MUTATED_TO,
                               weight=confidence if confidence > 0 else 1.0)

        return edge2

    def record_experiment(
        self,
        genome_id: str,
        experiment_id: str,
        result: str = "pending",
        roas: float = 0.0,
        ctr: float = 0.0,
        impressions: int = 0,
        label: str = "",
    ) -> EvolutionNode | None:
        """记录一次实验.

        Args:
            genome_id: 基因组 ID
            experiment_id: 实验 ID
            result: 实验结果 (winner/loser/pending)
            roas: ROAS
            ctr: CTR
            impressions: 曝光量
            label: 节点标签

        Returns:
            EvolutionNode | None: 创建的实验节点
        """
        if genome_id not in self._genome_map:
            return None

        genome_node_id = self._genome_map[genome_id]

        experiment_node = EvolutionNode(
            node_type=NodeType.EXPERIMENT,
            label=label or f"Experiment {experiment_id}",
            properties={
                "experiment_id": experiment_id,
                "genome_id": genome_id,
                "result": result,
                "roas": roas,
                "ctr": ctr,
                "impressions": impressions,
            },
        )
        self._nodes[experiment_node.node_id] = experiment_node

        # 基因组 → 实验
        self._add_edge(genome_node_id, experiment_node.node_id, EdgeType.TESTED_IN)

        return experiment_node

    def record_pattern(
        self,
        pattern_id: str,
        pattern_name: str = "",
        source_genome_ids: list[str] | None = None,
        pattern_type: str = "",
        confidence: float = 0.0,
        label: str = "",
    ) -> EvolutionNode:
        """记录一个学习到的模式.

        Args:
            pattern_id: 模式 ID
            pattern_name: 模式名称
            source_genome_ids: 来源基因组 ID 列表
            pattern_type: 模式类型
            confidence: 置信度
            label: 节点标签

        Returns:
            EvolutionNode: 创建的模式节点
        """
        pattern_node = EvolutionNode(
            node_type=NodeType.PATTERN,
            label=label or f"Pattern {pattern_name or pattern_id}",
            properties={
                "pattern_id": pattern_id,
                "pattern_name": pattern_name,
                "pattern_type": pattern_type,
                "confidence": confidence,
                "source_genome_ids": source_genome_ids or [],
            },
        )
        self._nodes[pattern_node.node_id] = pattern_node

        # 连接来源基因组
        for genome_id in (source_genome_ids or []):
            if genome_id in self._genome_map:
                genome_node_id = self._genome_map[genome_id]
                self._add_edge(
                    pattern_node.node_id, genome_node_id,
                    EdgeType.DERIVED_FROM,
                    weight=confidence if confidence > 0 else 0.5,
                )

        return pattern_node

    def record_generation(
        self,
        generation: int,
        genome_ids: list[str],
        label: str = "",
    ) -> EvolutionNode:
        """记录一个代际.

        Args:
            generation: 代际编号
            genome_ids: 该代包含的基因组 ID 列表
            label: 节点标签

        Returns:
            EvolutionNode: 创建的代际节点
        """
        gen_node = EvolutionNode(
            node_type=NodeType.GENERATION,
            label=label or f"Generation {generation}",
            properties={
                "generation": generation,
                "genome_ids": genome_ids,
            },
        )
        self._nodes[gen_node.node_id] = gen_node

        for genome_id in genome_ids:
            if genome_id in self._genome_map:
                genome_node_id = self._genome_map[genome_id]
                self._add_edge(genome_node_id, gen_node.node_id, EdgeType.BELONGS_TO)

        return gen_node

    # ── 查询: 谱系 ────────────────────────────────────────

    def query_lineage(
        self,
        genome_id: str,
        max_depth: int = 10,
    ) -> EvolutionPath | None:
        """查询基因组的完整进化谱系.

        从当前基因组反向追溯到根基因组.

        Args:
            genome_id: 目标基因组 ID
            max_depth: 最大追溯深度

        Returns:
            EvolutionPath | None: 进化路径
        """
        if genome_id not in self._genome_map:
            return None

        nodes: list[EvolutionNode] = []
        edges: list[EvolutionEdge] = []

        current_genome_id = genome_id
        depth = 0

        while current_genome_id and depth < max_depth:
            node_id = self._genome_map.get(current_genome_id)
            if not node_id:
                break

            node = self._nodes.get(node_id)
            if node:
                nodes.append(node)

            # 找到指向当前基因组的 MUTATED_TO 边 (即父→子)
            parent_edge = self._find_parent_mutation_edge(current_genome_id)
            if parent_edge:
                edges.append(parent_edge)
                # 找父基因组
                parent_node = self._nodes.get(parent_edge.source_id)
                if parent_node and parent_node.node_type == NodeType.GENOME:
                    current_genome_id = parent_node.properties.get("genome_id", "")
                    depth += 1
                    continue
                elif parent_node and parent_node.node_type == NodeType.MUTATION:
                    # 跨过变异节点找父基因组
                    grandparent_edge = self._find_incoming_edge(parent_node.node_id)
                    if grandparent_edge:
                        parent_node2 = self._nodes.get(grandparent_edge.source_id)
                        if parent_node2 and parent_node2.node_type == NodeType.GENOME:
                            current_genome_id = parent_node2.properties.get("genome_id", "")
                            depth += 1
                            continue
            break

        nodes.reverse()
        edges.reverse()

        return EvolutionPath(
            start_genome_id=current_genome_id if current_genome_id else genome_id,
            end_genome_id=genome_id,
            nodes=nodes,
            edges=edges,
            path_length=len(edges),
            summary=f"从 {current_genome_id or 'root'} 到 {genome_id} 的进化路径，经过 {len(edges)} 次变异",
        )

    def query_evolution_paths(
        self,
        genome_id: str,
        max_depth: int = 5,
    ) -> list[EvolutionPath]:
        """查询基因组的进化路径（包含后代）.

        Args:
            genome_id: 起始基因组 ID
            max_depth: 最大深度

        Returns:
            list[EvolutionPath]: 进化路径列表
        """
        if genome_id not in self._genome_map:
            return []

        paths: list[EvolutionPath] = []

        # BFS 遍历后代
        visited = {genome_id}
        queue = [(genome_id, 0, [genome_id])]

        while queue:
            current_id, depth, path_ids = queue.pop(0)
            if depth >= max_depth:
                continue

            # 找当前基因组的子代
            children = self._find_child_genomes(current_id)
            for child_id in children:
                if child_id not in visited:
                    visited.add(child_id)
                    new_path = path_ids + [child_id]
                    queue.append((child_id, depth + 1, new_path))

                    # 构建路径
                    path_nodes = []
                    path_edges = []
                    for i, gid in enumerate(new_path):
                        node_id = self._genome_map.get(gid)
                        if node_id:
                            node = self._nodes.get(node_id)
                            if node:
                                path_nodes.append(node)
                        if i > 0:
                            edge = self._find_mutation_edge(new_path[i - 1], gid)
                            if edge:
                                path_edges.append(edge)

                    paths.append(EvolutionPath(
                        start_genome_id=genome_id,
                        end_genome_id=child_id,
                        nodes=path_nodes,
                        edges=path_edges,
                        path_length=len(path_edges),
                        summary=f"从 {genome_id} 到 {child_id}，{len(path_edges)} 次变异",
                    ))

        return paths

    def query_pattern_origins(
        self,
        pattern_id: str,
    ) -> list[str]:
        """查询模式来源于哪些基因组.

        Args:
            pattern_id: 模式 ID

        Returns:
            list[str]: 基因组 ID 列表
        """
        pattern_node = self._find_node_by_type_and_id(NodeType.PATTERN, pattern_id)
        if not pattern_node:
            return []

        genome_ids = pattern_node.properties.get("source_genome_ids", [])
        return genome_ids

    def query_genome_experiments(
        self,
        genome_id: str,
    ) -> list[dict[str, Any]]:
        """查询基因组参与的所有实验.

        Args:
            genome_id: 基因组 ID

        Returns:
            list[dict]: 实验信息列表
        """
        if genome_id not in self._genome_map:
            return []

        genome_node_id = self._genome_map[genome_id]
        experiments = []

        for edge_id in self._edges_by_source.get(genome_node_id, []):
            edge = self._edges.get(edge_id)
            if edge and edge.edge_type == EdgeType.TESTED_IN:
                exp_node = self._nodes.get(edge.target_id)
                if exp_node:
                    experiments.append(exp_node.properties)

        return experiments

    # ── 查询: 统计 ────────────────────────────────────────

    def get_genome_count(self) -> int:
        """获取追踪的基因组总数."""
        return len(self._genome_map)

    def get_mutation_count(self) -> int:
        """获取变异事件总数."""
        return sum(1 for n in self._nodes.values() if n.node_type == NodeType.MUTATION)

    def get_experiment_count(self) -> int:
        """获取实验总数."""
        return sum(1 for n in self._nodes.values() if n.node_type == NodeType.EXPERIMENT)

    def get_pattern_count(self) -> int:
        """获取模式总数."""
        return sum(1 for n in self._nodes.values() if n.node_type == NodeType.PATTERN)

    def get_nodes_by_type(self) -> dict[str, int]:
        """按类型统计节点."""
        counts: dict[str, int] = defaultdict(int)
        for n in self._nodes.values():
            counts[n.node_type.value] += 1
        return dict(counts)

    def get_edges_by_type(self) -> dict[str, int]:
        """按类型统计边."""
        counts: dict[str, int] = defaultdict(int)
        for e in self._edges.values():
            counts[e.edge_type.value] += 1
        return dict(counts)

    def generate_report(self) -> EvolutionMemoryReport:
        """生成进化记忆报告."""
        nodes_by_type = self.get_nodes_by_type()
        edges_by_type = self.get_edges_by_type()

        total_nodes = len(self._nodes)
        total_edges = len(self._edges)
        genomes = self.get_genome_count()
        mutations = self.get_mutation_count()
        experiments = self.get_experiment_count()
        patterns = self.get_pattern_count()

        if genomes > 0:
            summary = (
                f"追踪 {genomes} 个基因组，{mutations} 次变异，"
                f"{experiments} 次实验，{patterns} 个模式。"
                f"图谱共 {total_nodes} 个节点，{total_edges} 条边"
            )
        else:
            summary = "进化记忆图谱为空"

        return EvolutionMemoryReport(
            total_nodes=total_nodes,
            total_edges=total_edges,
            nodes_by_type=nodes_by_type,
            edges_by_type=edges_by_type,
            total_genomes_tracked=genomes,
            total_mutations=mutations,
            total_experiments=experiments,
            total_patterns=patterns,
            summary=summary,
        )

    def stats(self) -> dict[str, Any]:
        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "nodes_by_type": self.get_nodes_by_type(),
            "edges_by_type": self.get_edges_by_type(),
            "genomes_tracked": self.get_genome_count(),
            "mutations": self.get_mutation_count(),
            "experiments": self.get_experiment_count(),
            "patterns": self.get_pattern_count(),
        }

    def reset(self) -> None:
        self._nodes.clear()
        self._edges.clear()
        self._genome_map.clear()
        self._edges_by_source.clear()
        self._edges_by_target.clear()

    # ── 内部方法 ────────────────────────────────────────────

    def _add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        weight: float = 1.0,
        properties: dict[str, Any] | None = None,
    ) -> EvolutionEdge:
        """添加边."""
        edge = EvolutionEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
            properties=properties or {},
        )
        self._edges[edge.edge_id] = edge
        self._edges_by_source[source_id].append(edge.edge_id)
        self._edges_by_target[target_id].append(edge.edge_id)
        return edge

    def _find_edge(self, source_id: str, target_id: str) -> EvolutionEdge | None:
        """查找指定源和目标之间的边."""
        for edge_id in self._edges_by_source.get(source_id, []):
            edge = self._edges.get(edge_id)
            if edge and edge.target_id == target_id:
                return edge
        return None

    def _find_parent_mutation_edge(self, genome_id: str) -> EvolutionEdge | None:
        """查找指向基因组的变异边."""
        genome_node_id = self._genome_map.get(genome_id)
        if not genome_node_id:
            return None

        # 先找直接连到基因组的 MUTATED_TO 边
        for edge_id in self._edges_by_target.get(genome_node_id, []):
            edge = self._edges.get(edge_id)
            if edge and edge.edge_type == EdgeType.MUTATED_TO:
                return edge

        return None

    def _find_incoming_edge(self, node_id: str) -> EvolutionEdge | None:
        """查找指向节点的第一条边."""
        edge_ids = self._edges_by_target.get(node_id, [])
        if edge_ids:
            return self._edges.get(edge_ids[0])
        return None

    def _find_child_genomes(self, genome_id: str) -> list[str]:
        """查找基因组的子代基因组."""
        genome_node_id = self._genome_map.get(genome_id)
        if not genome_node_id:
            return []

        children = []
        # 从基因组节点出发，找 MUTATED_TO 边
        for edge_id in self._edges_by_source.get(genome_node_id, []):
            edge = self._edges.get(edge_id)
            if edge and edge.edge_type == EdgeType.MUTATED_TO:
                target_node = self._nodes.get(edge.target_id)
                if target_node:
                    if target_node.node_type == NodeType.GENOME:
                        child_id = target_node.properties.get("genome_id", "")
                        if child_id:
                            children.append(child_id)
                    elif target_node.node_type == NodeType.MUTATION:
                        # 跨过变异节点找子基因组
                        for edge_id2 in self._edges_by_source.get(target_node.node_id, []):
                            edge2 = self._edges.get(edge_id2)
                            if edge2 and edge2.edge_type == EdgeType.MUTATED_TO:
                                child_node = self._nodes.get(edge2.target_id)
                                if child_node and child_node.node_type == NodeType.GENOME:
                                    child_id = child_node.properties.get("genome_id", "")
                                    if child_id:
                                        children.append(child_id)

        return children

    def _find_mutation_edge(self, parent_genome_id: str, child_genome_id: str) -> EvolutionEdge | None:
        """查找两个基因组之间的变异边."""
        parent_node_id = self._genome_map.get(parent_genome_id)
        child_node_id = self._genome_map.get(child_genome_id)
        if not parent_node_id or not child_node_id:
            return None

        for edge_id in self._edges_by_source.get(parent_node_id, []):
            edge = self._edges.get(edge_id)
            if edge and edge.edge_type == EdgeType.MUTATED_TO:
                # 直接连接
                if edge.target_id == child_node_id:
                    return edge
                # 通过变异节点连接
                target_node = self._nodes.get(edge.target_id)
                if target_node and target_node.node_type == NodeType.MUTATION:
                    for edge_id2 in self._edges_by_source.get(target_node.node_id, []):
                        edge2 = self._edges.get(edge_id2)
                        if edge2 and edge2.target_id == child_node_id:
                            return edge2
        return None

    def _find_node_by_type_and_id(self, node_type: NodeType, search_id: str) -> EvolutionNode | None:
        """按类型和 ID 查找节点."""
        for node in self._nodes.values():
            if node.node_type == node_type:
                for key, val in node.properties.items():
                    if key.endswith("_id") and val == search_id:
                        return node
        return None


# ═══════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════

def create_evolution_memory_graph() -> EvolutionMemoryGraph:
    """创建默认 EvolutionMemoryGraph."""
    return EvolutionMemoryGraph()