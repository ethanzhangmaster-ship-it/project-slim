"""E11.7.5 — Knowledge Builder。

负责将 EvolutionMemoryRecord 转换为 KnowledgeGraph。

输入: EvolutionMemoryRecord（来自 E11.7.4 Memory）
输出: KnowledgeGraph（节点 + 边）

构建规则:
  genome_id       → GENOME 节点
  mutation_type   → MUTATION 节点
  category        → CATEGORY 节点
  outcome         → RESULT 节点
  success_patterns → PATTERN 节点（每个 pattern 一个节点）
  failure_patterns → PATTERN 节点（每个 pattern 一个节点）
  fitness_gain    → FITNESS 节点

关系:
  GENOME -[undergoes]-> MUTATION
  MUTATION -[in_category]-> CATEGORY
  MUTATION -[produced]-> RESULT
  RESULT -[fitness_gain]-> FITNESS
  RESULT -[has_success_pattern]-> PATTERN
  RESULT -[has_failure_pattern]-> PATTERN
  GENOME -[achieved]-> RESULT
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    KnowledgeNode,
    KnowledgeEdge,
    NodeType,
)
from .graph_store import KnowledgeGraphStore
from ..orchestrator.memory.models import (
    EvolutionMemoryRecord,
    MemoryOutcome,
)

logger = logging.getLogger(__name__)


class KnowledgeBuilder:
    """知识图谱构建器。

    将 EvolutionMemoryRecord 转换为 KnowledgeGraph 的节点和边。

    Attributes:
        build_count: 构建次数
    """

    def __init__(
        self,
        graph: KnowledgeGraphStore | None = None,
    ) -> None:
        self._graph = graph if graph is not None else KnowledgeGraphStore()
        self._build_count: int = 0

    # ── 核心接口 ──────────────────────────────────────────

    def build(self, record: EvolutionMemoryRecord) -> dict[str, Any]:
        """从一条 MemoryRecord 构建知识图谱。

        Returns:
            {
                "nodes_added": int,
                "edges_added": int,
                "genome_node_id": str,
                "mutation_node_id": str,
            }
        """
        self._build_count += 1
        nodes_before = self._graph.get_node_count()
        edges_before = self._graph.get_edge_count()

        # 1. 创建节点
        genome_node = self._ensure_node(NodeType.GENOME, record.genome_id)
        mutation_node = self._ensure_node(NodeType.MUTATION, record.mutation_type)
        result_node = self._ensure_node(NodeType.RESULT, record.outcome.value)
        fitness_node = self._ensure_node(
            NodeType.FITNESS,
            f"{record.fitness_gain:+.1f}",
            metadata={"fitness_before": record.fitness_before, "fitness_after": record.fitness_after},
        )

        category_node = None
        if record.category:
            category_node = self._ensure_node(NodeType.CATEGORY, record.category)

        # 2. 创建边
        edges_added: list[str] = []

        # GENOME -[undergoes]-> MUTATION
        edges_added.append(self._ensure_edge(
            genome_node.node_id, mutation_node.node_id,
            "undergoes", weight=1.0,
        ))

        # MUTATION -[produced]-> RESULT
        edges_added.append(self._ensure_edge(
            mutation_node.node_id, result_node.node_id,
            "produced",
            weight=self._outcome_weight(record.outcome),
            metadata={"outcome": record.outcome.value},
        ))

        # RESULT -[fitness_gain]-> FITNESS
        edges_added.append(self._ensure_edge(
            result_node.node_id, fitness_node.node_id,
            "fitness_gain",
            weight=abs(record.fitness_gain) / 100.0,
        ))

        # GENOME -[achieved]-> RESULT
        edges_added.append(self._ensure_edge(
            genome_node.node_id, result_node.node_id,
            "achieved",
            weight=1.0,
        ))

        # MUTATION -[in_category]-> CATEGORY
        if category_node:
            edges_added.append(self._ensure_edge(
                mutation_node.node_id, category_node.node_id,
                "in_category",
                weight=1.0,
            ))

        # RESULT -[has_success_pattern]-> PATTERN
        for pattern in record.success_patterns:
            pattern_node = self._ensure_node(NodeType.PATTERN, pattern)
            edges_added.append(self._ensure_edge(
                result_node.node_id, pattern_node.node_id,
                "has_success_pattern",
                weight=1.0,
            ))

        # RESULT -[has_failure_pattern]-> PATTERN
        for pattern in record.failure_patterns:
            pattern_node = self._ensure_node(NodeType.PATTERN, pattern)
            edges_added.append(self._ensure_edge(
                result_node.node_id, pattern_node.node_id,
                "has_failure_pattern",
                weight=1.0,
            ))

        return {
            "nodes_added": self._graph.get_node_count() - nodes_before,
            "edges_added": self._graph.get_edge_count() - edges_before,
            "genome_node_id": genome_node.node_id,
            "mutation_node_id": mutation_node.node_id,
        }

    def build_from_memory(
        self,
        records: list[EvolutionMemoryRecord],
    ) -> dict[str, Any]:
        """从多条 MemoryRecord 批量构建。

        Returns:
            {"total_nodes_added": int, "total_edges_added": int, "records_processed": int}
        """
        total_nodes = 0
        total_edges = 0
        for record in records:
            result = self.build(record)
            total_nodes += result["nodes_added"]
            total_edges += result["edges_added"]
        return {
            "total_nodes_added": total_nodes,
            "total_edges_added": total_edges,
            "records_processed": len(records),
        }

    # ── 内部 ──────────────────────────────────────────────

    def _ensure_node(
        self,
        node_type: NodeType,
        value: str,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeNode:
        """确保节点存在，不存在则创建。"""
        existing = self._graph.get_node_by_key(node_type, value)
        if existing is not None:
            if metadata:
                existing.metadata.update(metadata)
            return existing

        node = KnowledgeNode(
            node_type=node_type,
            value=value,
            metadata=metadata or {},
        )
        self._graph.add_node(node)
        return node

    def _ensure_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """确保边存在，不存在则创建。"""
        edge = KnowledgeEdge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            weight=weight,
            metadata=metadata or {},
        )
        return self._graph.add_edge(edge)

    @staticmethod
    def _outcome_weight(outcome: MemoryOutcome) -> float:
        """根据 outcome 计算边权重。"""
        weights = {
            MemoryOutcome.SUCCESS: 1.0,
            MemoryOutcome.NEUTRAL: 0.5,
            MemoryOutcome.FAILURE: 0.2,
            MemoryOutcome.RETIRED: 0.1,
        }
        return weights.get(outcome, 0.5)

    # ── 属性 ──────────────────────────────────────────────

    @property
    def graph(self) -> KnowledgeGraphStore:
        return self._graph

    @property
    def build_count(self) -> int:
        return self._build_count

    def get_stats(self) -> dict[str, Any]:
        return {
            "build_count": self._build_count,
            "graph": self._graph.get_stats().to_dict(),
        }

    def reset(self) -> None:
        self._build_count = 0
        self._graph.clear()

    def __repr__(self) -> str:
        return f"KnowledgeBuilder(built={self._build_count}, graph={self._graph})"