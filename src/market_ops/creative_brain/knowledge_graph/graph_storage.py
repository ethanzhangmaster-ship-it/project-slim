"""V4.1 Graph Storage — persistence for Knowledge Graph."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .graph_builder import GraphBuilder, GraphNode, GraphEdge


class GraphStorage:
    """Persists and loads the Knowledge Graph to/from disk."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._path = Path(storage_path or "output/creative_brain/knowledge_graph.json")

    def save(self, graph: GraphBuilder) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(graph.export(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load(self) -> GraphBuilder:
        graph = GraphBuilder()
        if not self._path.exists():
            return graph
        data = json.loads(self._path.read_text(encoding="utf-8"))
        for n in data.get("nodes", []):
            graph.add_node(n["node_id"], n["node_type"], n.get("properties", {}))
        for e in data.get("edges", []):
            graph.add_edge(
                e["source_id"], e["target_id"], e["edge_type"],
                weight=e.get("weight", 1.0),
                properties=e.get("properties", {}),
            )
        return graph