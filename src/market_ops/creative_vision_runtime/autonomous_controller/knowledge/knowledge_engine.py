"""E11.7.5 — Knowledge Engine。

统一入口：连接 Memory → Knowledge Graph → Policy。

Three core capabilities:
  ingest()     — EvolutionMemoryRecord → KnowledgeGraph
  analyze()    — 查询某 mutation/pattern 的历史表现
  recommend()  — 基于知识图谱的策略推荐

完整链路:
  Memory → KnowledgeBuilder → GraphStore → GraphQuery → Policy
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    KnowledgeNode,
    KnowledgeEdge,
    KnowledgeQuery,
    KnowledgeQueryResult,
    NodeType,
)
from .graph_store import KnowledgeGraphStore
from .knowledge_builder import KnowledgeBuilder
from .graph_query import GraphQueryEngine
from ..orchestrator.memory.models import EvolutionMemoryRecord

logger = logging.getLogger(__name__)


class KnowledgeEngine:
    """知识图谱引擎。

    统一入口：ingest / analyze / recommend。

    Attributes:
        graph:      KnowledgeGraphStore
        builder:    KnowledgeBuilder
        query_engine: GraphQueryEngine
        ingest_count: 摄入次数
        analyze_count: 分析次数
    """

    def __init__(
        self,
        graph: KnowledgeGraphStore | None = None,
        builder: KnowledgeBuilder | None = None,
        query_engine: GraphQueryEngine | None = None,
    ) -> None:
        self._graph = graph if graph is not None else KnowledgeGraphStore()
        self._builder = builder if builder is not None else KnowledgeBuilder(
            graph=self._graph
        )
        self._query_engine = (
            query_engine if query_engine is not None
            else GraphQueryEngine(graph=self._graph)
        )
        self._ingest_count: int = 0
        self._analyze_count: int = 0

    # ── ingest ────────────────────────────────────────────

    def ingest(
        self,
        record: EvolutionMemoryRecord,
    ) -> dict[str, Any]:
        """摄入一条 MemoryRecord，构建知识图谱。

        Args:
            record: EvolutionMemoryRecord（来自 E11.7.4 Memory）

        Returns:
            dict with nodes_added, edges_added
        """
        self._ingest_count += 1
        return self._builder.build(record)

    def ingest_batch(
        self,
        records: list[EvolutionMemoryRecord],
    ) -> dict[str, Any]:
        """批量摄入。"""
        self._ingest_count += len(records)
        return self._builder.build_from_memory(records)

    # ── analyze ───────────────────────────────────────────

    def analyze(
        self,
        mutation_type: str,
    ) -> KnowledgeQueryResult:
        """分析某 mutation 的历史表现。

        查询 MUTATION → RESULT 的所有边，计算成功率。

        Args:
            mutation_type: 突变类型

        Returns:
            KnowledgeQueryResult（含成功率、平均适应度、推荐）
        """
        self._analyze_count += 1
        return self._query_engine.query_mutation_outcomes(mutation_type)

    def analyze_patterns(
        self,
        mutation_type: str,
    ) -> KnowledgeQueryResult:
        """分析某 mutation 关联的所有 pattern。"""
        self._analyze_count += 1
        return self._query_engine.query_related_patterns(mutation_type)

    # ── recommend ─────────────────────────────────────────

    def recommend(
        self,
        mutation_type: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        """基于知识图谱推荐策略。

        Args:
            mutation_type: 突变类型（可选）
            category:      分类（可选）

        Returns:
            {
                "mutation_type": str,
                "success_rate": float | None,
                "avg_fitness_gain": float | None,
                "top_patterns": list[str],
                "avoid_patterns": list[str],
                "recommendation": str,
                "action": str,  # EXPLOIT / EXPLORE / AVOID
            }
        """
        # 查询 mutation 结果
        result = None
        if mutation_type:
            result = self._query_engine.query_mutation_outcomes(mutation_type)

        # 查询关联 pattern
        pattern_result = None
        if mutation_type:
            pattern_result = self._query_engine.query_related_patterns(mutation_type)

        # 提取 top patterns
        top_patterns: list[str] = []
        avoid_patterns: list[str] = []
        if pattern_result:
            for edge in pattern_result.edges:
                if edge.relation == "has_success_pattern":
                    target = self._graph.get_node(edge.target_id)
                    if target:
                        top_patterns.append(target.value)
                elif edge.relation == "has_failure_pattern":
                    target = self._graph.get_node(edge.target_id)
                    if target:
                        avoid_patterns.append(target.value)

        # 确定 action
        success_rate = result.success_rate if result else None
        action = "EXPLORE"
        if success_rate is not None:
            if success_rate >= 0.7:
                action = "EXPLOIT"
            elif success_rate < 0.3:
                action = "AVOID"

        recommendation = ""
        if result:
            recommendation = result.recommendation

        return {
            "mutation_type": mutation_type or "unknown",
            "success_rate": success_rate,
            "avg_fitness_gain": result.avg_fitness_gain if result else None,
            "top_patterns": top_patterns[:5],
            "avoid_patterns": avoid_patterns[:5],
            "recommendation": recommendation,
            "action": action,
        }

    def recommend_all(self) -> dict[str, Any]:
        """对所有已知 mutation 类型进行推荐。

        Returns:
            {mutation_type: recommend_result, ...}
        """
        all_mutations: dict[str, Any] = {}
        mutation_nodes = self._graph.find_nodes(node_type=NodeType.MUTATION)
        for node in mutation_nodes:
            all_mutations[node.value] = self.recommend(node.value)
        return all_mutations

    # ── 查询 ──────────────────────────────────────────────

    def query(self, query: KnowledgeQuery) -> KnowledgeQueryResult:
        return self._query_engine.query(query)

    def get_stats(self) -> dict[str, Any]:
        return {
            "ingest_count": self._ingest_count,
            "analyze_count": self._analyze_count,
            "graph": self._graph.get_stats().to_dict(),
            "builder": self._builder.get_stats(),
            "query_engine": self._query_engine.get_stats(),
        }

    def clear(self) -> None:
        self._graph.clear()
        self._builder.reset()
        self._query_engine.reset()
        self._ingest_count = 0
        self._analyze_count = 0

    # ── 属性 ──────────────────────────────────────────────

    @property
    def graph(self) -> KnowledgeGraphStore:
        return self._graph

    @property
    def builder(self) -> KnowledgeBuilder:
        return self._builder

    @property
    def query_engine(self) -> GraphQueryEngine:
        return self._query_engine

    @property
    def ingest_count(self) -> int:
        return self._ingest_count

    @property
    def analyze_count(self) -> int:
        return self._analyze_count

    def __repr__(self) -> str:
        return (
            f"KnowledgeEngine(ingested={self._ingest_count}, "
            f"analyzed={self._analyze_count}, "
            f"graph={self._graph})"
        )