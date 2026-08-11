"""E11.7.5 — Graph Query Engine。

核心查询能力：
  - 查询成功模式：哪些 mutation + category 组合成功率高
  - 查询失败模式：哪些组合失败率高
  - 查询相关模式：某 mutation 关联的所有 pattern
  - 推荐：基于知识图谱的策略推荐
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from .models import (
    KnowledgeNode,
    KnowledgeEdge,
    KnowledgePath,
    KnowledgeQuery,
    KnowledgeQueryResult,
    NodeType,
)
from .graph_store import KnowledgeGraphStore

logger = logging.getLogger(__name__)


class GraphQueryEngine:
    """知识图谱查询引擎。

    基于 KnowledgeGraphStore 提供高级查询能力。
    """

    def __init__(
        self,
        graph: KnowledgeGraphStore | None = None,
    ) -> None:
        self._graph = graph if graph is not None else KnowledgeGraphStore()
        self._query_count: int = 0

    # ── 核心查询 ──────────────────────────────────────────

    def query(self, query: KnowledgeQuery) -> KnowledgeQueryResult:
        """执行知识图谱查询。

        支持按 node_type/value 查找节点，然后遍历邻居和路径。
        """
        self._query_count += 1

        # 查找匹配节点
        nodes = self._graph.find_nodes(
            node_type=query.node_type,
            value=query.value,
        )

        if not nodes:
            return KnowledgeQueryResult(
                query=query,
                recommendation="No matching nodes found in knowledge graph",
            )

        # 收集边和路径
        all_edges: list[KnowledgeEdge] = []
        all_paths: list[KnowledgePath] = []
        seen_edges: set[str] = set()

        for node in nodes:
            edges = self._collect_edges(
                node.node_id,
                direction=query.direction,
                relation=query.relation,
            )
            for edge in edges:
                if edge.key not in seen_edges:
                    all_edges.append(edge)
                    seen_edges.add(edge.key)

            # 路径查询（如指定了 target）
            if query.target_type and query.target_value:
                target = self._graph.get_node_by_key(
                    query.target_type, query.target_value
                )
                if target:
                    paths = self._graph.find_path(
                        node.node_id, target.node_id, query.max_depth
                    )
                    all_paths.extend(paths)

        # 计算成功率
        success_rate, avg_fitness = self._compute_success_metrics(all_edges)

        # 生成推荐
        recommendation = self._generate_recommendation(
            nodes, all_edges, success_rate, avg_fitness
        )

        return KnowledgeQueryResult(
            query=query,
            nodes=nodes,
            edges=all_edges,
            paths=all_paths,
            total_nodes=len(nodes),
            total_edges=len(all_edges),
            success_rate=success_rate,
            avg_fitness_gain=avg_fitness,
            recommendation=recommendation,
        )

    def query_success_patterns(
        self,
        node_type: NodeType | None = None,
        value: str | None = None,
    ) -> KnowledgeQueryResult:
        """查询成功模式：哪些模式成功率高。

        查找 RESULT:success 节点，跟踪其连接的 PATTERN 节点。
        """
        query = KnowledgeQuery(
            node_type=NodeType.RESULT,
            value="success",
            direction="outgoing",
            relation="has_success_pattern",
        )
        return self.query(query)

    def query_failure_patterns(
        self,
        node_type: NodeType | None = None,
        value: str | None = None,
    ) -> KnowledgeQueryResult:
        """查询失败模式。"""
        query = KnowledgeQuery(
            node_type=NodeType.RESULT,
            value="failure",
            direction="outgoing",
            relation="has_failure_pattern",
        )
        return self.query(query)

    def query_mutation_outcomes(
        self,
        mutation_type: str,
    ) -> KnowledgeQueryResult:
        """查询某 mutation 的所有结果模式。

        查找 MUTATION:{mutation_type} → RESULT 的边。
        """
        query = KnowledgeQuery(
            node_type=NodeType.MUTATION,
            value=mutation_type,
            direction="outgoing",
            relation="produced",
        )
        return self.query(query)

    def query_related_patterns(
        self,
        mutation_type: str,
    ) -> KnowledgeQueryResult:
        """查询某 mutation 关联的所有 pattern。

        路径: MUTATION → RESULT → PATTERN。
        """
        query = KnowledgeQuery(
            node_type=NodeType.MUTATION,
            value=mutation_type,
            direction="outgoing",
            max_depth=2,
        )
        return self.query(query)

    # ── 统计 ──────────────────────────────────────────────

    def _compute_success_metrics(
        self,
        edges: list[KnowledgeEdge],
    ) -> tuple[float | None, float | None]:
        """从边中计算成功率和平均适应度。"""
        success_count = 0
        total_count = 0
        fitness_gains: list[float] = []

        for edge in edges:
            if edge.relation == "produced":
                total_count += 1
                outcome = edge.metadata.get("outcome", "")
                if outcome == "success":
                    success_count += 1

            if edge.relation == "fitness_gain":
                # 从 FITNESS 节点中提取值
                fitness_node = self._graph.get_node(edge.target_id)
                if fitness_node:
                    try:
                        fitness_gains.append(float(fitness_node.value))
                    except ValueError:
                        pass

        success_rate = success_count / total_count if total_count > 0 else None
        avg_fitness = (
            sum(fitness_gains) / len(fitness_gains) if fitness_gains else None
        )

        return success_rate, avg_fitness

    @staticmethod
    def _generate_recommendation(
        nodes: list[KnowledgeNode],
        edges: list[KnowledgeEdge],
        success_rate: float | None,
        avg_fitness: float | None,
    ) -> str:
        parts: list[str] = []

        if success_rate is not None:
            if success_rate >= 0.7:
                parts.append(f"High success rate ({success_rate:.0%}) — EXPLOIT")
            elif success_rate >= 0.4:
                parts.append(f"Moderate success rate ({success_rate:.0%}) — explore with caution")
            elif success_rate > 0:
                parts.append(f"Low success rate ({success_rate:.0%}) — AVOID unless experimenting")
            else:
                parts.append("No success records — insufficient data")

        if avg_fitness is not None:
            parts.append(f"avg fitness gain: {avg_fitness:+.1f}")

        if not parts:
            parts.append("Insufficient knowledge — recommend EXPLORE")

        return "; ".join(parts)

    # ── 内部 ──────────────────────────────────────────────

    def _collect_edges(
        self,
        node_id: str,
        direction: str = "outgoing",
        relation: str | None = None,
    ) -> list[KnowledgeEdge]:
        """收集节点的边。"""
        edges: list[KnowledgeEdge] = []

        if direction in ("outgoing", "both"):
            edges.extend(self._graph.get_outgoing_edges(node_id))
        if direction in ("incoming", "both"):
            edges.extend(self._graph.get_incoming_edges(node_id))

        if relation:
            edges = [e for e in edges if e.relation == relation]

        return edges

    # ── 属性 ──────────────────────────────────────────────

    @property
    def graph(self) -> KnowledgeGraphStore:
        return self._graph

    @property
    def query_count(self) -> int:
        return self._query_count

    def get_stats(self) -> dict[str, Any]:
        return {
            "query_count": self._query_count,
            "graph_stats": self._graph.get_stats().to_dict(),
        }

    def reset(self) -> None:
        self._query_count = 0

    def __repr__(self) -> str:
        return f"GraphQueryEngine(queries={self._query_count})"