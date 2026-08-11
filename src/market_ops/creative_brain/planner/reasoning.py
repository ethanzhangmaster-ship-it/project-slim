"""V4.1 Reasoning — logical reasoning over knowledge graph."""

from __future__ import annotations

from typing import Any

from ..knowledge_graph.graph_builder import GraphBuilder
from ..knowledge_graph.graph_reasoner import GraphReasoner


class Reasoner:
    """Reasons over the Knowledge Graph to generate creative insights."""

    def __init__(self, graph: GraphBuilder, reasoner: GraphReasoner) -> None:
        self._graph = graph
        self._reasoner = reasoner

    def reason(self, query: str, retrieved: list[dict[str, Any]],
               max_insights: int = 5) -> str:
        """Generate reasoning insights from graph and retrieved data."""
        insights = []

        # Graph-based reasoning
        relationships = self._reasoner.infer_relationships()
        if relationships:
            insights.append(
                f"Graph has {len(self._graph)} nodes and {len(self._graph.edges)} edges"
            )
            top_rel = relationships[:3]
            for rel in top_rel:
                insights.append(
                    f"  [{rel['node_type']}] {rel['node_id']} "
                    f"connected to {rel['connection_count']} items"
                )

        # Pattern-based reasoning
        if retrieved:
            types = set(r.get("type", "") for r in retrieved)
            insights.append(
                f"Retrieved {len(retrieved)} items across {len(types)} types: {', '.join(types)}"
            )

        # Winner patterns
        winner_patterns = self._reasoner.infer_winner_patterns()
        if winner_patterns:
            insights.append(
                f"Found {len(winner_patterns)} winning patterns from graph"
            )

        return "\n".join(insights[:max_insights]) if insights else "No reasoning available"