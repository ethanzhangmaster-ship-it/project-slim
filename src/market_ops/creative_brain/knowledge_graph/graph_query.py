"""V4.1 Graph Query — advanced query for Knowledge Graph."""

from __future__ import annotations

from typing import Any

from .graph_builder import GraphBuilder, GraphNode, GraphEdge


class GraphQuery:
    """Advanced graph query operations."""

    def __init__(self, graph: GraphBuilder) -> None:
        self._graph = graph

    def find_path(self, source_id: str, target_id: str,
                  max_depth: int = 5) -> list[list[str]]:
        """Find all paths between two nodes."""
        if source_id not in self._graph.nodes or target_id not in self._graph.nodes:
            return []

        paths = []
        visited: set[str] = set()

        def dfs(current: str, path: list[str], depth: int) -> None:
            if depth > max_depth:
                return
            if current == target_id:
                paths.append(path[:])
                return
            for edge in self._graph.get_edges(current):
                if edge.target_id not in visited:
                    visited.add(edge.target_id)
                    dfs(edge.target_id, path + [edge.target_id], depth + 1)
                    visited.discard(edge.target_id)

        visited.add(source_id)
        dfs(source_id, [source_id], 1)
        return paths

    def find_related(self, node_id: str, edge_type: str = "",
                     max_hops: int = 2) -> list[GraphNode]:
        """Find related nodes within N hops."""
        if node_id not in self._graph.nodes:
            return []

        visited: set[str] = {node_id}
        frontier = [node_id]
        related = []

        for _ in range(max_hops):
            next_frontier = []
            for nid in frontier:
                for edge in self._graph.get_edges(nid):
                    if edge_type and edge.edge_type != edge_type:
                        continue
                    if edge.target_id not in visited:
                        visited.add(edge.target_id)
                        node = self._graph.get_node(edge.target_id)
                        if node:
                            related.append(node)
                        next_frontier.append(edge.target_id)
            frontier = next_frontier

        return related

    def count_by_type(self, node_type: str) -> int:
        return len(self._graph.query(node_type=node_type))

    def get_subgraph(self, node_ids: list[str]) -> GraphBuilder:
        """Extract a subgraph containing only the specified nodes."""
        sub = GraphBuilder()
        for nid in node_ids:
            node = self._graph.get_node(nid)
            if node:
                sub.add_node(node.node_id, node.node_type, dict(node.properties))
        for edge in self._graph.edges:
            if edge.source_id in node_ids and edge.target_id in node_ids:
                sub.add_edge(
                    edge.source_id, edge.target_id, edge.edge_type,
                    weight=edge.weight, properties=dict(edge.properties),
                )
        return sub