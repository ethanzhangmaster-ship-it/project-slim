"""E12.5.3 — Graph Store。

内存图存储引擎，支持节点和边的增删查改，
以及邻居查询、路径搜索等图操作。

基于邻接表实现，轻量级无外部依赖。

核心操作:
  - add_node / add_edge: 添加节点和边
  - get_node / get_edge: 按 ID 查询
  - query_neighbors:      查询邻居
  - find_path:            BFS 最短路径
  - get_stats:            图统计信息
"""

from __future__ import annotations

from collections import defaultdict, deque

from .models import (
    GraphStats,
    KnowledgeEdge,
    KnowledgeNode,
    NodeType,
    RelationType,
)


class GraphStore:
    """图存储引擎 —— 内存邻接表实现。

    Usage:
        >>> store = GraphStore()
        >>> store.add_node(node)
        >>> store.add_edge(edge)
        >>> neighbors = store.query_neighbors("NODE_001")
        >>> path = store.find_path("NODE_001", "NODE_005")
    """

    def __init__(self) -> None:
        self._nodes: dict[str, KnowledgeNode] = {}
        self._edges: dict[str, KnowledgeEdge] = {}
        # 邻接表: {node_id: [(edge_id, target_node_id), ...]}
        self._adjacency: dict[str, list[tuple[str, str]]] = defaultdict(list)

    # ── Node Operations ────────────────────────────────────

    def add_node(self, node: KnowledgeNode) -> None:
        """添加节点（重复 ID 会覆盖）。"""
        self._nodes[node.node_id] = node
        if node.node_id not in self._adjacency:
            self._adjacency[node.node_id] = []

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        """按 ID 获取节点。"""
        return self._nodes.get(node_id)

    def has_node(self, node_id: str) -> bool:
        """检查节点是否存在。"""
        return node_id in self._nodes

    def remove_node(self, node_id: str) -> bool:
        """删除节点及其关联边。"""
        if node_id not in self._nodes:
            return False

        # 删除关联边
        edges_to_remove = []
        for edge_id, edge in self._edges.items():
            if edge.source_id == node_id or edge.target_id == node_id:
                edges_to_remove.append(edge_id)

        for edge_id in edges_to_remove:
            self.remove_edge(edge_id)

        del self._nodes[node_id]
        if node_id in self._adjacency:
            del self._adjacency[node_id]

        # 清理其他节点的邻接引用
        for adj_list in self._adjacency.values():
            adj_list[:] = [(eid, tid) for eid, tid in adj_list if tid != node_id]

        return True

    def get_nodes_by_type(self, node_type: NodeType) -> list[KnowledgeNode]:
        """按类型获取所有节点。"""
        return [n for n in self._nodes.values() if n.node_type == node_type]

    def get_all_nodes(self) -> list[KnowledgeNode]:
        """获取所有节点。"""
        return list(self._nodes.values())

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    # ── Edge Operations ────────────────────────────────────

    def add_edge(self, edge: KnowledgeEdge) -> bool:
        """添加边。源和目标节点必须存在。"""
        if edge.source_id not in self._nodes or edge.target_id not in self._nodes:
            return False

        self._edges[edge.edge_id] = edge
        self._adjacency[edge.source_id].append((edge.edge_id, edge.target_id))
        # 双向邻接（无向图视角）
        self._adjacency[edge.target_id].append((edge.edge_id, edge.source_id))
        return True

    def get_edge(self, edge_id: str) -> KnowledgeEdge | None:
        """按 ID 获取边。"""
        return self._edges.get(edge_id)

    def has_edge_between(self, source_id: str, target_id: str) -> bool:
        """检查两个节点之间是否存在边。"""
        for edge in self._edges.values():
            if (edge.source_id == source_id and edge.target_id == target_id) or \
               (edge.source_id == target_id and edge.target_id == source_id):
                return True
        return False

    def remove_edge(self, edge_id: str) -> bool:
        """删除边。"""
        edge = self._edges.pop(edge_id, None)
        if edge is None:
            return False

        # 清理邻接表
        for adj_list in self._adjacency.values():
            adj_list[:] = [(eid, tid) for eid, tid in adj_list if eid != edge_id]
        return True

    def get_edges_by_type(self, relation_type: RelationType) -> list[KnowledgeEdge]:
        """按关系类型获取边。"""
        return [e for e in self._edges.values() if e.relation_type == relation_type]

    def get_all_edges(self) -> list[KnowledgeEdge]:
        """获取所有边。"""
        return list(self._edges.values())

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    # ── Query Operations ───────────────────────────────────

    def query_neighbors(
        self,
        node_id: str,
        relation_type: RelationType | None = None,
        max_results: int = 50,
    ) -> list[tuple[KnowledgeNode, KnowledgeEdge]]:
        """查询节点的邻居。

        Args:
            node_id:       节点 ID
            relation_type: 关系类型筛选（None = 全部）
            max_results:   最大返回数

        Returns:
            [(邻居节点, 连接边), ...] 按权重降序
        """
        if node_id not in self._nodes:
            return []

        results: list[tuple[KnowledgeNode, KnowledgeEdge]] = []
        for edge_id, target_id in self._adjacency.get(node_id, []):
            edge = self._edges.get(edge_id)
            if edge is None:
                continue
            if relation_type and edge.relation_type != relation_type:
                continue
            neighbor = self._nodes.get(target_id)
            if neighbor is None:
                continue
            results.append((neighbor, edge))

        # 按权重降序
        results.sort(key=lambda x: x[1].weight, reverse=True)
        return results[:max_results]

    def query_edges_from(
        self,
        source_id: str,
        relation_type: RelationType | None = None,
    ) -> list[KnowledgeEdge]:
        """查询从某节点出发的所有边。

        Args:
            source_id:     源节点 ID
            relation_type: 关系类型筛选

        Returns:
            KnowledgeEdge 列表
        """
        edges: list[KnowledgeEdge] = []
        for edge_id, _ in self._adjacency.get(source_id, []):
            edge = self._edges.get(edge_id)
            if edge is None:
                continue
            if edge.source_id == source_id:
                if relation_type is None or edge.relation_type == relation_type:
                    edges.append(edge)
        return edges

    def query_edges_to(
        self,
        target_id: str,
        relation_type: RelationType | None = None,
    ) -> list[KnowledgeEdge]:
        """查询指向某节点的所有边。

        Args:
            target_id:     目标节点 ID
            relation_type: 关系类型筛选

        Returns:
            KnowledgeEdge 列表
        """
        edges: list[KnowledgeEdge] = []
        for edge_id, _ in self._adjacency.get(target_id, []):
            edge = self._edges.get(edge_id)
            if edge is None:
                continue
            if edge.target_id == target_id:
                if relation_type is None or edge.relation_type == relation_type:
                    edges.append(edge)
        return edges

    # ── Path Operations ────────────────────────────────────

    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> list[KnowledgeEdge] | None:
        """BFS 最短路径搜索。

        Args:
            source_id:  源节点 ID
            target_id:  目标节点 ID
            max_depth:  最大搜索深度

        Returns:
            路径边列表（按顺序），找不到返回 None
        """
        if source_id not in self._nodes or target_id not in self._nodes:
            return None

        if source_id == target_id:
            return []

        visited = {source_id}
        queue: deque[tuple[str, list[KnowledgeEdge]]] = deque()
        queue.append((source_id, []))

        while queue:
            current_id, path = queue.popleft()

            if len(path) >= max_depth:
                continue

            for edge_id, neighbor_id in self._adjacency.get(current_id, []):
                if neighbor_id in visited:
                    continue

                edge = self._edges.get(edge_id)
                if edge is None:
                    continue

                new_path = list(path) + [edge]
                if neighbor_id == target_id:
                    return new_path

                visited.add(neighbor_id)
                queue.append((neighbor_id, new_path))

        return None

    def find_all_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
        max_paths: int = 10,
    ) -> list[list[KnowledgeEdge]]:
        """DFS 查找所有路径（限制数量）。

        Args:
            source_id:  源节点 ID
            target_id:  目标节点 ID
            max_depth:  最大搜索深度
            max_paths:  最大路径数

        Returns:
            路径列表
        """
        if source_id not in self._nodes or target_id not in self._nodes:
            return []

        paths: list[list[KnowledgeEdge]] = []

        def dfs(current: str, visited: set[str], path: list[KnowledgeEdge]) -> None:
            if len(paths) >= max_paths:
                return
            if len(path) >= max_depth:
                return
            if current == target_id and path:
                paths.append(list(path))
                return

            for edge_id, neighbor_id in self._adjacency.get(current, []):
                if neighbor_id in visited:
                    continue
                edge = self._edges.get(edge_id)
                if edge is None:
                    continue
                visited.add(neighbor_id)
                path.append(edge)
                dfs(neighbor_id, visited, path)
                path.pop()
                visited.discard(neighbor_id)

        dfs(source_id, {source_id}, [])
        return paths

    # ── Stats ──────────────────────────────────────────────

    def get_stats(self) -> GraphStats:
        """获取图统计信息。"""
        nodes_by_type: dict[str, int] = defaultdict(int)
        for node in self._nodes.values():
            nodes_by_type[node.node_type.value] += 1

        edges_by_type: dict[str, int] = defaultdict(int)
        for edge in self._edges.values():
            edges_by_type[edge.relation_type.value] += 1

        confidences = [n.confidence for n in self._nodes.values()]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return GraphStats(
            total_nodes=len(self._nodes),
            total_edges=len(self._edges),
            nodes_by_type=dict(nodes_by_type),
            edges_by_type=dict(edges_by_type),
            avg_confidence=avg_confidence,
            connected_components=self._count_components(),
        )

    def _count_components(self) -> int:
        """计算连通分量数。"""
        visited: set[str] = set()
        components = 0

        for node_id in self._nodes:
            if node_id in visited:
                continue
            components += 1
            # BFS
            queue = deque([node_id])
            visited.add(node_id)
            while queue:
                current = queue.popleft()
                for _, neighbor_id in self._adjacency.get(current, []):
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        queue.append(neighbor_id)

        return components

    # ── Bulk Operations ────────────────────────────────────

    def add_nodes_batch(self, nodes: list[KnowledgeNode]) -> int:
        """批量添加节点。"""
        count = 0
        for node in nodes:
            self.add_node(node)
            count += 1
        return count

    def add_edges_batch(self, edges: list[KnowledgeEdge]) -> tuple[int, int]:
        """批量添加边。返回 (成功数, 总数)。"""
        success = 0
        for edge in edges:
            if self.add_edge(edge):
                success += 1
        return success, len(edges)

    def clear(self) -> None:
        """清空图。"""
        self._nodes.clear()
        self._edges.clear()
        self._adjacency.clear()

    def to_dict(self) -> dict:
        """导出为字典。"""
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges.values()],
        }

    def __len__(self) -> int:
        return len(self._nodes)

    def __contains__(self, node_id: str) -> bool:
        return node_id in self._nodes

    def __repr__(self) -> str:
        return (
            f"GraphStore(nodes={len(self._nodes)}, "
            f"edges={len(self._edges)})"
        )