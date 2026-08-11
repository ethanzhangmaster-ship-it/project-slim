"""E13.7.9 Knowledge Graph Updater — 知识图谱更新引擎.

Day 7.9 Step 5:
  将 Memory Consolidation Pipeline 的结果同步到 KnowledgeGraph，
  建立 Pattern → Node + Edge 的可追溯知识网络。

核心职责:
  1. Pattern → KnowledgeGraphNode 转换
  2. Reinforcement → strengthen edges (强化成功关系)
  3. Decay → weaken edges (衰减失效关系)
  4. 连接相关 Pattern (相似条件/动作)
  5. 与现有 evolution_models.KnowledgeGraph 集成

流程:
  PatternStore
      │
      ▼
  for each pattern:
      │
      ├─→ 创建/更新 KnowledgeGraphNode
      ├─→ 应用 Reinforcement → strengthen
      ├─→ 应用 Decay → weaken
      └─→ 连接相关模式 → edges
      │
      ▼
  GraphBatchUpdateResult

连接:
  PatternStore → PatternDecayEngine → PatternReinforcementBridge
       │                                    │
       └──────── KnowledgeGraphUpdater ─────┘
                        │
                        ▼
               evolution_models.KnowledgeGraph

设计原则:
  - 与 evolution_models.KnowledgeGraph 互补 (节点层 vs 拓扑层)
  - 不修改已有模块
  - 确定性更新，可解释
  - 支持增量更新 (不每次重建全图)
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any

from .models.knowledge_graph_models import (
    EdgeType,
    GraphBatchUpdateResult,
    GraphUpdateResult,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    NodeType,
)


class KnowledgeGraphUpdater:
    """知识图谱更新引擎 — 同步 PatternStore 到 KnowledgeGraph.

    核心操作:
      1. sync_patterns:    Pattern → Node
      2. strengthen:       Reinforcement → 增强节点/边
      3. weaken:           Decay → 削弱节点/边
      4. connect:          相似 Pattern → 建边

    用法:
        updater = KnowledgeGraphUpdater()
        batch = updater.update_graph(
            patterns=patterns,
            reinforcement_results=reinforcement_results,
            decay_results=decay_results,
        )
    """

    # 强化参数
    BOOST_FACTOR = 0.05          # 每次强化提升
    MAX_BOOST = 0.30             # 最大单次提升
    MIN_CONFIDENCE = 0.05        # 最低置信度

    # 衰减参数
    WEAKEN_FACTOR = 0.10         # 每次衰减降低
    MAX_WEAKEN = 0.40            # 最大单次降低

    # 相似度阈值
    SIMILARITY_THRESHOLD = 0.50  # 创建 SIMILAR_TO 边的最低相似度

    def __init__(self):
        self._nodes: dict[str, KnowledgeGraphNode] = {}
        self._edges: list[KnowledgeGraphEdge] = []
        self._update_count: int = 0
        self._total_created: int = 0
        self._total_strengthened: int = 0
        self._total_weakened: int = 0

    # ── Properties ───────────────────────────────────────────────

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    @property
    def update_count(self) -> int:
        return self._update_count

    # ── Public API ───────────────────────────────────────────────

    def update_graph(
        self,
        patterns: list[Any],  # list[PatternMemory]
        reinforcement_results: list[Any] | None = None,
        decay_results: list[Any] | None = None,
    ) -> GraphBatchUpdateResult:
        """完整图谱更新周期 — 主入口.

        Args:
            patterns: PatternMemory 列表
            reinforcement_results: PatternReinforcementResult 列表 (可选)
            decay_results: PatternDecayResult 列表 (可选)

        Returns:
            GraphBatchUpdateResult: 批量更新结果
        """
        self._update_count += 1
        results: list[GraphUpdateResult] = []

        # Step 1: Sync patterns → nodes
        sync_results = self.sync_patterns(patterns)
        results.extend(sync_results)

        # Step 2: Apply reinforcement → strengthen
        if reinforcement_results:
            strengthen_results = self.strengthen_from_reinforcement(reinforcement_results)
            results.extend(strengthen_results)

        # Step 3: Apply decay → weaken
        if decay_results:
            weaken_results = self.weaken_from_decay(decay_results)
            results.extend(weaken_results)

        # Step 4: Connect related patterns
        connect_results = self.connect_related_patterns(patterns)
        results.extend(connect_results)

        total_edges = len(self._edges)
        return GraphBatchUpdateResult.from_results(results, total_edges=total_edges)

    def sync_patterns(
        self,
        patterns: list[Any],  # list[PatternMemory]
    ) -> list[GraphUpdateResult]:
        """将 PatternMemory 同步到知识图谱节点.

        新 Pattern → 创建节点
        已有 Pattern → 更新节点置信度/权重
        """
        results: list[GraphUpdateResult] = []
        for pattern in patterns:
            existing = self._find_node_by_pattern_ref(pattern.pattern_id)
            if existing is None:
                result = self._create_node(pattern)
                self._total_created += 1
            else:
                result = self._update_node(existing, pattern)
            results.append(result)
        return results

    def strengthen_from_reinforcement(
        self,
        reinforcement_results: list[Any],
    ) -> list[GraphUpdateResult]:
        """从强化结果中增强图谱节点和边.

        成功 Pattern → 提升节点置信度 + 创建/增强 REINFORCES 边
        """
        results: list[GraphUpdateResult] = []
        for rr in reinforcement_results:
            pattern_id = getattr(rr, "pattern_id", "")
            node = self._find_node_by_pattern_ref(pattern_id)
            if node is None:
                continue

            confidence_before = node.confidence
            weight_before = node.weight

            # 增强节点置信度
            boost = min(self.MAX_BOOST, self.BOOST_FACTOR)
            node.confidence = round(min(1.0, node.confidence + boost), 4)
            node.weight = round(min(1.0, node.weight + boost * 0.5), 4)
            node.updated_at = datetime.now(timezone.utc).isoformat()
            node.metadata["last_strengthened"] = node.updated_at
            node.metadata["strengthen_count"] = node.metadata.get("strengthen_count", 0) + 1

            self._total_strengthened += 1

            # 创建/增强 REINFORCES 边
            edges_added = self._ensure_edge(
                node.node_id, node.node_id,
                EdgeType.REINFORCES, boost,
            )

            results.append(GraphUpdateResult(
                pattern_id=pattern_id,
                node_id=node.node_id,
                action="strengthened",
                node_confidence_before=confidence_before,
                node_confidence_after=node.confidence,
                node_weight_before=weight_before,
                node_weight_after=node.weight,
                edges_added=edges_added,
                edges_updated=0,
                changed=True,
                reason=f"Reinforcement boost: +{boost:.2f} confidence",
            ))
        return results

    def weaken_from_decay(
        self,
        decay_results: list[Any],
    ) -> list[GraphUpdateResult]:
        """从衰减结果中削弱图谱节点和边.

        衰减 Pattern → 降低节点置信度 + 创建/增强 DECAYS_TO 边
        """
        results: list[GraphUpdateResult] = []
        for dr in decay_results:
            pattern_id = getattr(dr, "pattern_id", "")
            node = self._find_node_by_pattern_ref(pattern_id)
            if node is None:
                continue

            confidence_before = node.confidence
            weight_before = node.weight

            # 削弱节点置信度
            weaken = min(self.MAX_WEAKEN, self.WEAKEN_FACTOR)
            node.confidence = round(max(self.MIN_CONFIDENCE, node.confidence - weaken), 4)
            node.weight = round(max(0.1, node.weight - weaken * 0.5), 4)
            node.updated_at = datetime.now(timezone.utc).isoformat()
            node.metadata["last_weakened"] = node.updated_at
            node.metadata["weaken_count"] = node.metadata.get("weaken_count", 0) + 1

            self._total_weakened += 1

            # 创建/增强 DECAYS_TO 边
            edges_added = self._ensure_edge(
                node.node_id, node.node_id,
                EdgeType.DECAYS_TO, weaken,
            )

            results.append(GraphUpdateResult(
                pattern_id=pattern_id,
                node_id=node.node_id,
                action="weakened",
                node_confidence_before=confidence_before,
                node_confidence_after=node.confidence,
                node_weight_before=weight_before,
                node_weight_after=node.weight,
                edges_added=edges_added,
                edges_updated=0,
                changed=True,
                reason=f"Decay weaken: -{weaken:.2f} confidence",
            ))
        return results

    def connect_related_patterns(
        self,
        patterns: list[Any],  # list[PatternMemory]
    ) -> list[GraphUpdateResult]:
        """连接相关模式 — 基于条件/动作相似度创建边.

        相似条件 → SIMILAR_TO 边
        相同动作 → EVIDENCE_FOR 边
        """
        results: list[GraphUpdateResult] = []
        n = len(patterns)

        for i in range(n):
            for j in range(i + 1, n):
                pa = patterns[i]
                pb = patterns[j]

                node_a = self._find_node_by_pattern_ref(pa.pattern_id)
                node_b = self._find_node_by_pattern_ref(pb.pattern_id)
                if node_a is None or node_b is None:
                    continue

                similarity = self._compute_pattern_similarity(pa, pb)

                if similarity >= self.SIMILARITY_THRESHOLD:
                    # 相似 → SIMILAR_TO 边
                    edges_added = self._ensure_edge(
                        node_a.node_id, node_b.node_id,
                        EdgeType.SIMILAR_TO, similarity,
                    )
                    if edges_added > 0:
                        node_a.edge_count = self._count_edges_for_node(node_a.node_id)
                        node_b.edge_count = self._count_edges_for_node(node_b.node_id)
                        results.append(GraphUpdateResult(
                            pattern_id=pa.pattern_id,
                            node_id=node_a.node_id,
                            action="updated",
                            node_confidence_before=node_a.confidence,
                            node_confidence_after=node_a.confidence,
                            node_weight_before=1.0,
                            node_weight_after=1.0,
                            edges_added=edges_added,
                            changed=True,
                            reason=f"Connected to similar pattern {pb.pattern_id[:8]} "
                                   f"(similarity={similarity:.2f})",
                        ))

                # 相同动作类型 → EVIDENCE_FOR 边
                if (hasattr(pa.action, "action_type")
                        and hasattr(pb.action, "action_type")
                        and pa.action.action_type == pb.action.action_type):
                    edges_added = self._ensure_edge(
                        node_a.node_id, node_b.node_id,
                        EdgeType.EVIDENCE_FOR, 0.3,
                    )
                    if edges_added > 0:
                        node_a.edge_count = self._count_edges_for_node(node_a.node_id)
                        node_b.edge_count = self._count_edges_for_node(node_b.node_id)

        return results

    # ── Node Operations ──────────────────────────────────────────

    def _create_node(self, pattern: Any) -> GraphUpdateResult:
        """从 PatternMemory 创建新的 KnowledgeGraphNode."""
        node = KnowledgeGraphNode(
            node_id=str(uuid.uuid4()),
            node_type=NodeType.PATTERN,
            label=self._build_label(pattern),
            pattern_ref=pattern.pattern_id,
            confidence=pattern.confidence,
            weight=min(1.0, max(0.1, pattern.score)),
            tags=list(pattern.tags) if pattern.tags else [],
            edge_count=0,
            metadata={
                "source": "pattern_decay_engine",
                "action_type": pattern.action.action_type if hasattr(pattern.action, "action_type") else "",
                "opportunity_type": pattern.condition.opportunity_type if hasattr(pattern.condition, "opportunity_type") else "",
                "success_rate": pattern.performance.success_rate if hasattr(pattern.performance, "success_rate") else 0.0,
                "samples": pattern.performance.samples if hasattr(pattern.performance, "samples") else 0,
            },
        )
        self._nodes[node.node_id] = node
        return GraphUpdateResult(
            pattern_id=pattern.pattern_id,
            node_id=node.node_id,
            action="created",
            node_confidence_before=0.0,
            node_confidence_after=node.confidence,
            node_weight_before=0.0,
            node_weight_after=node.weight,
            changed=True,
            reason=f"Created node for pattern {pattern.pattern_id[:8]}",
        )

    def _update_node(
        self,
        node: KnowledgeGraphNode,
        pattern: Any,
    ) -> GraphUpdateResult:
        """更新已有节点的置信度和权重."""
        confidence_before = node.confidence
        weight_before = node.weight

        node.confidence = pattern.confidence
        node.weight = min(1.0, max(0.1, pattern.score))
        node.updated_at = datetime.now(timezone.utc).isoformat()
        node.tags = list(pattern.tags) if pattern.tags else node.tags
        node.metadata["success_rate"] = (
            pattern.performance.success_rate
            if hasattr(pattern.performance, "success_rate") else 0.0
        )
        node.metadata["samples"] = (
            pattern.performance.samples
            if hasattr(pattern.performance, "samples") else 0
        )

        changed = (
            abs(confidence_before - node.confidence) > 0.001
            or abs(weight_before - node.weight) > 0.001
        )

        return GraphUpdateResult(
            pattern_id=pattern.pattern_id,
            node_id=node.node_id,
            action="updated",
            node_confidence_before=confidence_before,
            node_confidence_after=node.confidence,
            node_weight_before=weight_before,
            node_weight_after=node.weight,
            changed=changed,
            reason=f"Updated node from pattern {pattern.pattern_id[:8]}",
        )

    # ── Edge Operations ──────────────────────────────────────────

    def _ensure_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        weight: float,
    ) -> int:
        """确保边存在 — 不存在则创建，存在则更新权重.

        Returns:
            int: 1 if created, 0 if updated
        """
        existing = self._find_edge(source_id, target_id, edge_type)
        if existing is not None:
            # 更新已有边
            existing.weight = round(min(1.0, existing.weight + weight * 0.3), 4)
            existing.evidence_count += 1
            existing.updated_at = datetime.now(timezone.utc).isoformat()
            return 0  # updated, not added

        # 创建新边
        edge = KnowledgeGraphEdge(
            edge_id=str(uuid.uuid4()),
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=round(weight, 4),
            confidence=round(weight * 0.8, 4),
            evidence_count=1,
        )
        self._edges.append(edge)
        return 1  # created

    def _find_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
    ) -> KnowledgeGraphEdge | None:
        """查找指定边."""
        for edge in self._edges:
            if (edge.source_id == source_id
                    and edge.target_id == target_id
                    and edge.edge_type == edge_type):
                return edge
        return None

    def _count_edges_for_node(self, node_id: str) -> int:
        """统计节点的边数."""
        return sum(
            1 for e in self._edges
            if e.source_id == node_id or e.target_id == node_id
        )

    # ── Node Lookup ──────────────────────────────────────────────

    def _find_node_by_pattern_ref(self, pattern_id: str) -> KnowledgeGraphNode | None:
        """通过 pattern_id 查找节点."""
        for node in self._nodes.values():
            if node.pattern_ref == pattern_id:
                return node
        return None

    def get_node(self, node_id: str) -> KnowledgeGraphNode | None:
        """获取节点."""
        return self._nodes.get(node_id)

    def get_all_nodes(self) -> list[KnowledgeGraphNode]:
        """获取所有节点."""
        return list(self._nodes.values())

    def get_all_edges(self) -> list[KnowledgeGraphEdge]:
        """获取所有边."""
        return list(self._edges)

    # ── Similarity ───────────────────────────────────────────────

    def _compute_pattern_similarity(
        self,
        pa: Any,
        pb: Any,
    ) -> float:
        """计算两个 Pattern 的相似度.

        维度:
          - action_type 相同: +0.40
          - opportunity_type 相同: +0.30
          - category 相同: +0.15
          - audience_segment 相同: +0.15
        """
        score = 0.0

        # 动作类型
        if (hasattr(pa.action, "action_type")
                and hasattr(pb.action, "action_type")
                and pa.action.action_type == pb.action.action_type):
            score += 0.40

        # 机会类型
        if (hasattr(pa.condition, "opportunity_type")
                and hasattr(pb.condition, "opportunity_type")
                and pa.condition.opportunity_type == pb.condition.opportunity_type):
            score += 0.30

        # 类别
        if (hasattr(pa.condition, "category")
                and hasattr(pb.condition, "category")
                and pa.condition.category == pb.condition.category):
            score += 0.15

        # 受众
        if (hasattr(pa.condition, "audience_segment")
                and hasattr(pb.condition, "audience_segment")
                and pa.condition.audience_segment == pb.condition.audience_segment):
            score += 0.15

        return round(score, 4)

    # ── Label ────────────────────────────────────────────────────

    def _build_label(self, pattern: Any) -> str:
        """从 Pattern 构建可读标签."""
        parts = []
        if hasattr(pattern.action, "action_type") and pattern.action.action_type:
            parts.append(pattern.action.action_type)
        if hasattr(pattern.condition, "opportunity_type") and pattern.condition.opportunity_type:
            parts.append(f"@ {pattern.condition.opportunity_type}")
        if hasattr(pattern.performance, "success_rate"):
            parts.append(f"({pattern.performance.success_rate:.0%})")
        return " ".join(parts) if parts else f"Pattern-{pattern.pattern_id[:8]}"

    # ── Statistics ───────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取引擎统计."""
        return {
            "update_count": self._update_count,
            "node_count": len(self._nodes),
            "edge_count": len(self._edges),
            "total_created": self._total_created,
            "total_strengthened": self._total_strengthened,
            "total_weakened": self._total_weakened,
            "isolated_nodes": sum(1 for n in self._nodes.values() if n.is_isolated),
            "high_confidence_nodes": sum(1 for n in self._nodes.values() if n.is_high_confidence),
            "low_confidence_nodes": sum(1 for n in self._nodes.values() if n.is_low_confidence),
        }

    def reset_stats(self) -> None:
        """重置统计."""
        self._update_count = 0
        self._total_created = 0
        self._total_strengthened = 0
        self._total_weakened = 0
        self._nodes.clear()
        self._edges.clear()


__all__ = [
    "KnowledgeGraphUpdater",
]