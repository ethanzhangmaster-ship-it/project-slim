"""
E16.6.14 — ASO OS Memory: Knowledge Graph & Pattern Store.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.aso_os.kernel.models import (
    KnowledgeNode,
    KnowledgeEdge,
)
from src.aso_intelligence.experiment_memory.experiment_store import (
    ASOExperimentStore,
)
from src.aso_intelligence.experiment_memory.experiment_models import (
    ASOPattern,
)


class KnowledgeGraph:
    """ASO knowledge graph — connects genre → pattern → market → keyword → result."""

    def __init__(self):
        self._nodes: Dict[str, KnowledgeNode] = {}
        self._edges: List[KnowledgeEdge] = []

    def add_node(self, node: KnowledgeNode) -> None:
        self._nodes[node.node_id] = node

    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        return self._nodes.get(node_id)

    def add_edge(self, edge: KnowledgeEdge) -> None:
        self._edges.append(edge)

    def query_memory(
        self, genre: str, market: str, change_type: str
    ) -> List[Dict[str, Any]]:
        """Query the knowledge graph for relevant past patterns."""
        results = []
        for edge in self._edges:
            if edge.relation == "has_pattern":
                src = self._nodes.get(edge.source_id)
                tgt = self._nodes.get(edge.target_id)
                if src and tgt:
                    sg = src.properties.get("genre", "")
                    sm = tgt.properties.get("market", "")
                    if sg == genre and sm == market:
                        results.append({
                            "pattern": tgt.label,
                            "weight": edge.weight,
                            "source": src.label,
                            "market": sm,
                        })
        return results

    def recommend_for_genre(self, genre: str) -> List[str]:
        """Recommend patterns based on genre history."""
        recommendations = set()
        for edge in self._edges:
            if edge.relation == "has_pattern":
                src = self._nodes.get(edge.source_id)
                if src and src.properties.get("genre") == genre:
                    tgt = self._nodes.get(edge.target_id)
                    if tgt:
                        recommendations.add(tgt.label)
        return sorted(recommendations)


class PatternStore:
    """Bridge to E16.6.4 experiment memory store."""

    def __init__(self, store: Optional[ASOExperimentStore] = None):
        self.store = store

    def record_pattern(
        self, genre: str, market: str, action: str,
        cvr_uplift: float, revenue_uplift: float,
    ) -> bool:
        if not self.store:
            return False
        pattern = ASOPattern(
            category=f"os:{genre}",
            condition=f"os:{market}:{action}",
            action=action,
            result=f"CVR {cvr_uplift:+.0%}, Revenue {revenue_uplift:+.0%} (OS)",
            confidence=min(0.95, 0.3 + (cvr_uplift + revenue_uplift)),
            sample_size=1,
            success_rate=1.0 if revenue_uplift > 0 else 0.0,
            reward=revenue_uplift,
            pattern_id=f"os:{genre}:{market}:{action}",
        )
        self.store.record_pattern(pattern)
        return True


__all__ = ["KnowledgeGraph", "PatternStore"]
