"""V4.3.5 Graph Updater — update knowledge graph edges.

Discovers new relationships:
  Dragon → Merge → Collection → Reward → ROAS

Automatically adds, strengthens, or weakens edges based on
Validation feedback and new evidence.
"""

from __future__ import annotations

from typing import Any

from .schemas import GraphUpdate


class GraphUpdater:
    """Update knowledge graph edges based on new evidence."""

    def __init__(self) -> None:
        self._edges: dict[str, dict[str, float]] = {}  # source → {target → weight}
        self._update_history: list[GraphUpdate] = []

    def add_edge(self, source: str, target: str, relation: str,
                 weight: float = 0.5, evidence: list[str] | None = None) -> GraphUpdate:
        """Add or strengthen an edge between two nodes.

        If edge exists, strength is increased.
        """
        if source not in self._edges:
            self._edges[source] = {}

        old_weight = self._edges[source].get(target, 0.0)
        new_weight = min(1.0, old_weight + weight)

        self._edges[source][target] = new_weight

        update = GraphUpdate(
            source_node=source,
            target_node=target,
            relation=relation,
            action="add" if old_weight == 0.0 else "strengthen",
            weight=new_weight,
            weight_change=new_weight - old_weight,
            evidence=evidence or [],
            reason=f"Edge {'added' if old_weight == 0.0 else 'strengthened'}: "
                   f"{source} → {target} ({relation})",
        )

        self._update_history.append(update)
        return update

    def weaken_edge(self, source: str, target: str, relation: str,
                    decay: float = 0.2) -> GraphUpdate | None:
        """Weaken an edge between two nodes.

        If weight drops below threshold, edge is removed.
        """
        if source not in self._edges or target not in self._edges[source]:
            return None

        old_weight = self._edges[source][target]
        new_weight = max(0.0, old_weight - decay)

        if new_weight <= 0.05:
            del self._edges[source][target]
            if not self._edges[source]:
                del self._edges[source]
            action = "remove"
        else:
            self._edges[source][target] = new_weight
            action = "weaken"

        update = GraphUpdate(
            source_node=source,
            target_node=target,
            relation=relation,
            action=action,
            weight=new_weight,
            weight_change=new_weight - old_weight,
            reason=f"Edge {action}d: {source} → {target} ({relation})",
        )

        self._update_history.append(update)
        return update

    def update_from_validation(self, validation_results: list[dict[str, Any]]
                               ) -> list[GraphUpdate]:
        """Update graph based on validation feedback.

        Args:
            validation_results: List of dicts with keys:
                source, target, relation, accuracy, should_strengthen.

        Returns:
            List of GraphUpdate applied.
        """
        updates = []
        for vr in validation_results:
            source = vr.get("source", "")
            target = vr.get("target", "")
            relation = vr.get("relation", "")
            accuracy = vr.get("accuracy", 0.5)

            if vr.get("should_strengthen", True):
                update = self.add_edge(source, target, relation, weight=accuracy * 0.3)
            else:
                update = self.weaken_edge(source, target, relation, decay=0.2)
                if update is None:
                    # Edge doesn't exist yet — add with low weight
                    update = self.add_edge(source, target, relation, weight=accuracy * 0.15)

            if update:
                updates.append(update)

        return updates

    def get_edges(self) -> dict[str, dict[str, float]]:
        """Get all edges."""
        return dict(self._edges)

    def get_node_count(self) -> int:
        """Get total unique nodes."""
        nodes = set()
        for source, targets in self._edges.items():
            nodes.add(source)
            nodes.update(targets.keys())
        return len(nodes)

    def get_edge_count(self) -> int:
        """Get total edges."""
        return sum(len(targets) for targets in self._edges.values())

    def get_update_history(self) -> list[GraphUpdate]:
        return list(self._update_history)

    def get_strongest_edges(self, top_k: int = 10) -> list[dict[str, Any]]:
        """Get the strongest edges in the graph."""
        all_edges = []
        for source, targets in self._edges.items():
            for target, weight in targets.items():
                all_edges.append({
                    "source": source,
                    "target": target,
                    "weight": weight,
                })
        all_edges.sort(key=lambda e: -e["weight"])
        return all_edges[:top_k]