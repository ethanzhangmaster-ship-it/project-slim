"""V4.1 Knowledge Graph — graph builder for creative relationships.

Node types:
  Creative, Prompt, Hook, Reward, Character, Country, Game, Campaign,
  DNA, CTR, IPM, ROAS

Edge types:
  contains, generated_by, similar_to, winner_of, belongs_to, launched_in, uses
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class GraphNode:
    node_id: str
    node_type: str
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "properties": self.properties,
        }


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    edge_type: str
    weight: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type,
            "weight": self.weight,
            "properties": self.properties,
        }


class GraphBuilder:
    """Builds and manages the Creative Knowledge Graph."""

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._adjacency: dict[str, list[GraphEdge]] = {}  # outgoing edges

    def add_node(self, node_id: str, node_type: str,
                 properties: dict[str, Any] | None = None) -> GraphNode:
        node = GraphNode(node_id=node_id, node_type=node_type, properties=properties or {})
        self._nodes[node_id] = node
        self._adjacency.setdefault(node_id, [])
        return node

    def add_edge(self, source_id: str, target_id: str, edge_type: str,
                 weight: float = 1.0, properties: dict[str, Any] | None = None) -> GraphEdge | None:
        if source_id not in self._nodes or target_id not in self._nodes:
            return None
        edge = GraphEdge(
            source_id=source_id, target_id=target_id,
            edge_type=edge_type, weight=weight,
            properties=properties or {},
        )
        self._edges.append(edge)
        self._adjacency.setdefault(source_id, []).append(edge)
        return edge

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def get_edges(self, source_id: str) -> list[GraphEdge]:
        return self._adjacency.get(source_id, [])

    def get_neighbors(self, node_id: str, edge_type: str = "") -> list[GraphNode]:
        edges = self._adjacency.get(node_id, [])
        if edge_type:
            edges = [e for e in edges if e.edge_type == edge_type]
        return [self._nodes[e.target_id] for e in edges if e.target_id in self._nodes]

    def query(self, node_type: str = "", property_filter: dict[str, Any] | None = None) -> list[GraphNode]:
        results = []
        for node in self._nodes.values():
            if node_type and node.node_type != node_type:
                continue
            if property_filter:
                match = True
                for k, v in property_filter.items():
                    if node.properties.get(k) != v:
                        match = False
                if not match:
                    continue
            results.append(node)
        return results

    def update_node(self, node_id: str, **properties) -> bool:
        node = self._nodes.get(node_id)
        if not node:
            return False
        node.properties.update(properties)
        return True

    def merge(self, other: GraphBuilder) -> None:
        """Merge another graph into this one."""
        for node in other._nodes.values():
            if node.node_id not in self._nodes:
                self._nodes[node.node_id] = node
                self._adjacency.setdefault(node.node_id, [])
            else:
                self._nodes[node.node_id].properties.update(node.properties)
        for edge in other._edges:
            if edge.source_id in self._nodes and edge.target_id in self._nodes:
                self._edges.append(edge)
                self._adjacency.setdefault(edge.source_id, []).append(edge)

    def export(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges],
        }

    def to_visualization(self) -> str:
        """Generate a simple text visualization of the graph."""
        lines = ["Knowledge Graph Visualization", "=" * 40]
        for node in self._nodes.values():
            lines.append(f"\n[{node.node_type}] {node.node_id}")
            if node.properties:
                for k, v in node.properties.items():
                    lines.append(f"  {k}: {v}")
            for edge in self._adjacency.get(node.node_id, []):
                lines.append(f"  --[{edge.edge_type}]--> {edge.target_id}")
        return "\n".join(lines)

    @property
    def nodes(self) -> dict[str, GraphNode]:
        return self._nodes

    @property
    def edges(self) -> list[GraphEdge]:
        return self._edges

    def __len__(self) -> int:
        return len(self._nodes)