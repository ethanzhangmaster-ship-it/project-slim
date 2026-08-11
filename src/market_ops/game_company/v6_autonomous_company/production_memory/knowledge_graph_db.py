from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Set, Tuple
from datetime import datetime
from enum import Enum


class NodeType(Enum):
    GAME = "game"
    GENRE = "genre"
    AUDIENCE = "audience"
    MECHANIC = "mechanic"
    CREATIVE = "creative"
    STRATEGY = "strategy"
    MARKET = "market"
    INSIGHT = "insight"


class EdgeType(Enum):
    BELONGS_TO = "belongs_to"
    TARGETS = "targets"
    USES = "uses"
    RELATED_TO = "related_to"
    PERFORMS_WELL = "performs_well"
    PERFORMS_POORLY = "performs_poorly"
    DERIVED_FROM = "derived_from"
    COMPETES_WITH = "competes_with"


@dataclass
class GraphNode:
    node_id: str
    node_type: NodeType
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "name": self.name,
            "properties": self.properties,
        }


@dataclass
class GraphEdge:
    edge_id: str
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


class KnowledgeGraphDB:
    def __init__(self):
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: Dict[str, GraphEdge] = {}
        self._outgoing: Dict[str, List[str]] = {}
        self._incoming: Dict[str, List[str]] = {}
        self._type_index: Dict[str, List[str]] = {}

    def add_node(
        self,
        node_type: NodeType,
        name: str,
        properties: Dict[str, Any] = None,
    ) -> GraphNode:
        node_id = f"node_{hash(name + node_type.value) % 100000:05d}"

        existing = self._nodes.get(node_id)
        if existing:
            if properties:
                existing.properties.update(properties)
            return existing

        node = GraphNode(
            node_id=node_id,
            node_type=node_type,
            name=name,
            properties=properties or {},
        )

        self._nodes[node_id] = node
        self._outgoing[node_id] = []
        self._incoming[node_id] = []

        type_key = node_type.value
        if type_key not in self._type_index:
            self._type_index[type_key] = []
        self._type_index[type_key].append(node_id)

        return node

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        weight: float = 1.0,
        properties: Dict[str, Any] = None,
    ) -> Optional[GraphEdge]:
        if source_id not in self._nodes or target_id not in self._nodes:
            return None

        edge_id = f"edge_{hash(source_id + target_id + edge_type.value) % 100000:05d}"

        edge = GraphEdge(
            edge_id=edge_id,
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
            properties=properties or {},
        )

        self._edges[edge_id] = edge
        self._outgoing[source_id].append(edge_id)
        self._incoming[target_id].append(edge_id)

        return edge

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self._nodes.get(node_id)

    def get_node_by_name(self, name: str, node_type: NodeType = None) -> Optional[GraphNode]:
        for node in self._nodes.values():
            if node.name == name:
                if node_type is None or node.node_type == node_type:
                    return node
        return None

    def get_neighbors(
        self,
        node_id: str,
        edge_type: EdgeType = None,
        direction: str = "both",
    ) -> List[Tuple[GraphNode, GraphEdge]]:
        results = []

        if direction in ("out", "both"):
            for edge_id in self._outgoing.get(node_id, []):
                edge = self._edges[edge_id]
                if edge_type and edge.edge_type != edge_type:
                    continue
                target = self._nodes.get(edge.target_id)
                if target:
                    results.append((target, edge))

        if direction in ("in", "both"):
            for edge_id in self._incoming.get(node_id, []):
                edge = self._edges[edge_id]
                if edge_type and edge.edge_type != edge_type:
                    continue
                source = self._nodes.get(edge.source_id)
                if source:
                    results.append((source, edge))

        return results

    def find_path(
        self,
        start_id: str,
        end_id: str,
        max_depth: int = 3,
    ) -> List[GraphEdge]:
        if start_id not in self._nodes or end_id not in self._nodes:
            return []

        visited = set()
        queue = [(start_id, [])]

        while queue:
            current, path = queue.pop(0)
            if current == end_id:
                return path
            if len(path) >= max_depth:
                continue
            if current in visited:
                continue
            visited.add(current)

            for edge_id in self._outgoing.get(current, []):
                edge = self._edges[edge_id]
                if edge.target_id not in visited:
                    queue.append((edge.target_id, path + [edge]))

        return []

    def get_nodes_by_type(self, node_type: NodeType) -> List[GraphNode]:
        ids = self._type_index.get(node_type.value, [])
        return [self._nodes[nid] for nid in ids if nid in self._nodes]

    def get_related_insights(self, node_id: str) -> List[GraphNode]:
        neighbors = self.get_neighbors(node_id, edge_type=EdgeType.RELATED_TO)
        insight_nodes = [n for n, e in neighbors if n.node_type == NodeType.INSIGHT]
        return insight_nodes

    def find_patterns(self, anchor_type: NodeType, related_type: NodeType, min_weight: float = 0.5) -> List[Dict[str, Any]]:
        patterns = []
        anchor_nodes = self.get_nodes_by_type(anchor_type)

        for anchor in anchor_nodes:
            related = []
            neighbors = self.get_neighbors(anchor.node_id)
            for node, edge in neighbors:
                if node.node_type == related_type and edge.weight >= min_weight:
                    related.append({"node": node, "edge": edge})

            if related:
                patterns.append({
                    "anchor": anchor,
                    "related": related,
                })

        return patterns

    def get_stats(self) -> Dict[str, Any]:
        type_counts = {ntype: len(ids) for ntype, ids in self._type_index.items()}
        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "node_type_counts": type_counts,
            "density": round(len(self._edges) / (len(self._nodes) * (len(self._nodes) - 1)) if len(self._nodes) > 1 else 0, 4),
        }
