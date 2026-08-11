"""V4.1 Graph Reasoner — reasoning over the Knowledge Graph.

Infers relationships and patterns from graph structure:
  - "Dragon Reward → CTR +18%"
  - "Character X → Higher ROAS in Country Y"
  - "Hook A + Reward B → Winner combination"
"""

from __future__ import annotations

from typing import Any

from .graph_builder import GraphBuilder, GraphNode


class GraphReasoner:
    """Reasoning engine for the Creative Knowledge Graph."""

    def __init__(self, graph: GraphBuilder) -> None:
        self._graph = graph

    def infer_winner_patterns(self) -> list[dict[str, Any]]:
        """Infer winning patterns from graph structure."""
        patterns = []
        winner_nodes = self._graph.query(node_type="Creative")
        for wn in winner_nodes:
            if wn.properties.get("status") == "winner":
                # Find connected Hook, Reward, Character nodes
                related = self._graph.get_neighbors(wn.node_id)
                hook_nodes = [n for n in related if n.node_type == "Hook"]
                reward_nodes = [n for n in related if n.node_type == "Reward"]
                character_nodes = [n for n in related if n.node_type == "Character"]

                if hook_nodes and reward_nodes:
                    patterns.append({
                        "creative_id": wn.node_id,
                        "hooks": [n.properties.get("value", "") for n in hook_nodes],
                        "rewards": [n.properties.get("value", "") for n in reward_nodes],
                        "characters": [n.properties.get("value", "") for n in character_nodes],
                        "performance": wn.properties.get("performance", {}),
                    })
        return patterns

    def infer_relationships(self) -> list[dict[str, Any]]:
        """Infer new relationships from existing graph data."""
        relationships = []

        # Find co-occurring patterns
        for node in self._graph.nodes.values():
            edges = self._graph.get_edges(node.node_id)
            edge_types = set(e.edge_type for e in edges)
            if len(edge_types) > 1:
                relationships.append({
                    "node_id": node.node_id,
                    "node_type": node.node_type,
                    "connected_types": list(edge_types),
                    "connection_count": len(edges),
                })

        return relationships

    def reason_about(self, node_id: str) -> dict[str, Any]:
        """Reason about a specific node."""
        node = self._graph.get_node(node_id)
        if not node:
            return {"error": "Node not found"}

        neighbors = self._graph.get_neighbors(node_id)
        edges = self._graph.get_edges(node_id)

        return {
            "node": node.to_dict(),
            "neighbor_count": len(neighbors),
            "neighbor_types": list(set(n.node_type for n in neighbors)),
            "edge_types": list(set(e.edge_type for e in edges)),
            "neighbors": [n.to_dict() for n in neighbors],
        }

    def export_insights(self) -> dict[str, Any]:
        """Export all reasoning insights."""
        return {
            "winner_patterns": self.infer_winner_patterns(),
            "relationships": self.infer_relationships(),
            "node_count": len(self._graph),
            "edge_count": len(self._graph.edges),
        }