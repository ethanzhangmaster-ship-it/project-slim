"""E11.7.5 — Knowledge Graph Store。

内存图存储：节点 + 边 + 邻居查询 + 路径查找。

第一版使用内存 dict，后续可替换为 Neo4j / NetworkX。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from .models import (
    KnowledgeNode,
    KnowledgeEdge,
    KnowledgePath,
    KnowledgeStats,
    NodeType,
)

logger = logging.getLogger(__name__)


class KnowledgeGraphStore:
    """知识图谱存储。

    基于内存邻接表实现。

    Attributes:
        add_node_count: 添加节点次数
        add_edge_count: 添加边次数
    """

    def __init__(self) -> None:
        # node_id → KnowledgeNode
        self._nodes: dict[str, KnowledgeNode] = {}
        # key → KnowledgeNode（用于快速查找 node_type:value）
        self._nodes_by_key: dict[str, KnowledgeNode] = {}
        # source_id → list[KnowledgeEdge]
        self._outgoing: dict[str, list[KnowledgeEdge]] = defaultdict(list)
        # target_id → list[KnowledgeEdge]
        self._incoming: dict[str, list[KnowledgeEdge]] = defaultdict(list)
        # edge_key → KnowledgeEdge
        self._edges: dict[str, KnowledgeEdge] = {}
        self._add_node_count: int = 0
        self._add_edge_count: int = 0

    # ── 节点操作 ──────────────────────────────────────────

    def add_node(self, node: KnowledgeNode) -> str:
        """添加节点。如果已存在同 key 节点，返回已有节点 ID。"""
        existing = self._nodes_by_key.get(node.key)
        if existing is not None:
            return existing.node_id

        self._nodes[node.node_id] = node
        self._nodes_by_key[node.key] = node
        self._add_node_count += 1
        return node.node_id

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        return self._nodes.get(node_id)

    def get_node_by_key(self, node_type: NodeType, value: str) -> KnowledgeNode | None:
        key = f"{node_type.value}:{value}"
        return self._nodes_by_key.get(key)

    def find_nodes(
        self,
        node_type: NodeType | None = None,
        value: str | None = None,
    ) -> list[KnowledgeNode]:
        """按类型和值查找节点。"""
        results: list[KnowledgeNode] = []
        for node in self._nodes.values():
            if node_type is not None and node.node_type != node_type:
                continue
            if value is not None and node.value != value:
                continue
            results.append(node)
        return results

    def get_all_nodes(self) -> list[KnowledgeNode]:
        return list(self._nodes.values())

    def get_node_count(self) -> int:
        return len(self._nodes)

    # ── 边操作 ────────────────────────────────────────────

    def add_edge(self, edge: KnowledgeEdge) -> str:
        """添加边。如果已存在同 key 边，增加权重和计数。"""
        existing = self._edges.get(edge.key)
        if existing is not None:
            existing.weight = max(existing.weight, edge.weight)
            existing.count += edge.count
            existing.metadata.update(edge.metadata)
            return existing.key

        self._edges[edge.key] = edge
        self._outgoing[edge.source_id].append(edge)
        self._incoming[edge.target_id].append(edge)
        self._add_edge_count += 1
        return edge.key

    def get_edge(self, source_id: str, target_id: str, relation: str) -> KnowledgeEdge | None:
        key = f"{source_id}→{target_id}:{relation}"
        return self._edges.get(key)

    def get_outgoing_edges(self, node_id: str) -> list[KnowledgeEdge]:
        return self._outgoing.get(node_id, [])

    def get_incoming_edges(self, node_id: str) -> list[KnowledgeEdge]:
        return self._incoming.get(node_id, [])

    def get_all_edges(self) -> list[KnowledgeEdge]:
        return list(self._edges.values())

    def get_edge_count(self) -> int:
        return len(self._edges)

    # ── 邻居查询 ──────────────────────────────────────────

    def find_neighbors(
        self,
        node_id: str,
        direction: str = "outgoing",
        relation: str | None = None,
    ) -> list[KnowledgeNode]:
        """查找邻居节点。

        Args:
            node_id:   源节点 ID
            direction: outgoing / incoming / both
            relation:  关系过滤

        Returns:
            邻居节点列表
        """
        neighbors: list[KnowledgeNode] = []
        seen: set[str] = set()

        edges: list[KnowledgeEdge] = []
        if direction in ("outgoing", "both"):
            edges.extend(self._outgoing.get(node_id, []))
        if direction in ("incoming", "both"):
            edges.extend(self._incoming.get(node_id, []))

        for edge in edges:
            if relation is not None and edge.relation != relation:
                continue
            # 确定邻居节点 ID
            neighbor_id = (
                edge.target_id if edge.source_id == node_id else edge.source_id
            )
            if neighbor_id not in seen:
                node = self._nodes.get(neighbor_id)
                if node:
                    neighbors.append(node)
                    seen.add(neighbor_id)

        return neighbors

    def find_neighbors_by_key(
        self,
        node_type: NodeType,
        value: str,
        direction: str = "outgoing",
        relation: str | None = None,
    ) -> list[KnowledgeNode]:
        """通过 node_type:value 查找邻居。"""
        node = self.get_node_by_key(node_type, value)
        if node is None:
            return []
        return self.find_neighbors(node.node_id, direction, relation)

    # ── 路径查询 ──────────────────────────────────────────

    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 3,
    ) -> list[KnowledgePath]:
        """BFS 查找两点间路径。

        Args:
            source_id:  源节点 ID
            target_id:  目标节点 ID
            max_depth:  最大深度

        Returns:
            路径列表，按总权重降序
        """
        if source_id not in self._nodes or target_id not in self._nodes:
            return []

        # BFS: (current_node_id, path_nodes, path_edges, total_weight)
        paths: list[KnowledgePath] = []
        visited: set[tuple[str, int]] = set()  # (node_id, depth)

        queue: list[tuple[str, list[KnowledgeNode], list[KnowledgeEdge], float]] = [
            (source_id, [self._nodes[source_id]], [], 0.0)
        ]

        while queue:
            current_id, path_nodes, path_edges, total_weight = queue.pop(0)

            if len(path_nodes) > max_depth + 1:
                continue

            state = (current_id, len(path_nodes))
            if state in visited:
                continue
            visited.add(state)

            if current_id == target_id and len(path_nodes) > 1:
                paths.append(KnowledgePath(
                    nodes=path_nodes,
                    edges=path_edges,
                    total_weight=total_weight,
                ))

            for edge in self._outgoing.get(current_id, []):
                next_id = edge.target_id
                if next_id not in self._nodes:
                    continue
                next_node = self._nodes[next_id]
                if next_node in path_nodes:
                    continue  # 避免循环
                queue.append((
                    next_id,
                    path_nodes + [next_node],
                    path_edges + [edge],
                    total_weight + edge.weight,
                ))

        # 按权重降序
        paths.sort(key=lambda p: p.total_weight, reverse=True)
        return paths

    def find_path_by_key(
        self,
        source_type: NodeType,
        source_value: str,
        target_type: NodeType,
        target_value: str,
        max_depth: int = 3,
    ) -> list[KnowledgePath]:
        """通过 key 查找路径。"""
        source = self.get_node_by_key(source_type, source_value)
        target = self.get_node_by_key(target_type, target_value)
        if source is None or target is None:
            return []
        return self.find_path(source.node_id, target.node_id, max_depth)

    # ── 统计 ──────────────────────────────────────────────

    def get_stats(self) -> KnowledgeStats:
        node_types: dict[str, int] = {}
        for node in self._nodes.values():
            t = node.node_type.value
            node_types[t] = node_types.get(t, 0) + 1

        edge_relations: dict[str, int] = {}
        total_weight = 0.0
        for edge in self._edges.values():
            edge_relations[edge.relation] = edge_relations.get(edge.relation, 0) + 1
            total_weight += edge.weight

        avg_weight = total_weight / len(self._edges) if self._edges else 0.0

        return KnowledgeStats(
            total_nodes=len(self._nodes),
            total_edges=len(self._edges),
            node_types=node_types,
            edge_relations=edge_relations,
            avg_weight=round(avg_weight, 4),
        )

    # ── 管理 ──────────────────────────────────────────────

    def clear(self) -> None:
        self._nodes.clear()
        self._nodes_by_key.clear()
        self._outgoing.clear()
        self._incoming.clear()
        self._edges.clear()
        self._add_node_count = 0
        self._add_edge_count = 0

    # ── 属性 ──────────────────────────────────────────────

    @property
    def add_node_count(self) -> int:
        return self._add_node_count

    @property
    def add_edge_count(self) -> int:
        return self._add_edge_count

    def __len__(self) -> int:
        return len(self._nodes)

    def __repr__(self) -> str:
        return (
            f"KnowledgeGraphStore(nodes={len(self._nodes)}, "
            f"edges={len(self._edges)})"
        )