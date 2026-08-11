"""E6.1: Market Knowledge Graph — Why Trends Happen.

Not just "what is trending" but "why is it trending and how do we exploit it?"

Knowledge graph nodes:
  - CategoryNode: game category with lifecycle state
  - MechanicNode: core loop (merge, sort, puzzle)
  - HookNode: ad hook pattern (rescue, mess-to-clean)
  - SignalNode: raw market signal with evidence chain
  - OpportunityNode: synthesized opportunity with causal reasoning

Edges:
  - CAUSES: signal → trend
  - ENABLES: mechanic → hook
  - COMPLEMENTS: mechanic ↔ mechanic (hybrid opportunities)
  - COMPETES: category ↔ category (competition density)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class NodeType(Enum):
    CATEGORY = "category"
    MECHANIC = "mechanic"
    HOOK = "hook"
    SIGNAL = "signal"
    OPPORTUNITY = "opportunity"
    TREND = "trend"


class EdgeType(Enum):
    CAUSES = "causes"           # signal → trend
    ENABLES = "enables"         # mechanic → hook
    COMPLEMENTS = "complements"  # mechanic ↔ mechanic
    COMPETES = "competes"       # category ↔ category
    DERIVES_FROM = "derives_from"  # opportunity → trend


@dataclass
class GraphNode:
    """A node in the knowledge graph."""
    node_id: str = ""
    node_type: NodeType = NodeType.SIGNAL
    name: str = ""
    strength: float = 0.0       # 0-100, current relevance
    evidence: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.node_id, "type": self.node_type.value,
                "name": self.name, "strength": self.strength}


@dataclass
class GraphEdge:
    """A directed edge between nodes."""
    source: str
    target: str
    edge_type: EdgeType
    weight: float = 1.0
    evidence: str = ""


@dataclass
class CategoryNode(GraphNode):
    """A game category with lifecycle tracking."""
    lifecycle_stage: str = ""    # "emerging", "growing", "mature", "declining"
    growth_rate: float = 0.0
    competition_density: float = 0.0
    dominant_mechanics: list[str] = field(default_factory=list)
    breakout_games: list[str] = field(default_factory=list)
    # WHY this category is trending
    causal_factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d.update({"lifecycle": self.lifecycle_stage, "growth": self.growth_rate,
                   "dominant_mechanics": self.dominant_mechanics})
        return d


class MarketKnowledgeGraph:
    """The accumulated market intelligence — knows why trends happen.

    Usage:
        graph = MarketKnowledgeGraph()
        graph.ingest_trend(trend_signal)
        graph.ingest_competitor(profile)
        explanation = graph.explain("sort")
        # → "Sort trending because 3D physics visual + rescue hook + TikTok UGC format"
    """

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._category_lifecycle: dict[str, CategoryNode] = {}
        self._signal_index: dict[str, list[str]] = {}  # category → signal_ids

    # ── Ingestion ───────────────────────────────────────────

    def ingest_category(self, category: str, heat: float, opportunity_gap: float,
                        mechanics: list[str], competition: float) -> CategoryNode:
        """Register or update a category."""
        # Derive lifecycle from heat + competition
        growth = opportunity_gap  # Use opportunity gap as growth proxy
        node = CategoryNode(
            node_id=f"cat_{category}",
            node_type=NodeType.CATEGORY,
            name=category,
            strength=heat,
            growth_rate=growth,
            competition_density=competition,
            dominant_mechanics=mechanics,
            lifecycle_stage=self._classify_lifecycle(growth, competition),
            causal_factors=[],
        )
        self._nodes[node.node_id] = node
        self._category_lifecycle[category] = node
        return node

    def ingest_signal(self, signal: Any, category: str) -> GraphNode:
        """Ingest a raw signal (trend, competitor move, social spike)."""
        node_id = getattr(signal, 'signal_id', f"sig_{category}_{datetime.now().isoformat()}")
        node = GraphNode(
            node_id=node_id,
            node_type=NodeType.SIGNAL,
            name=f"{category}:{getattr(signal, 'subcategory', 'signal')}",
            strength=getattr(signal, 'velocity_score', 50),
            evidence=getattr(signal, 'evidence', []),
        )
        self._nodes[node_id] = node
        self._signal_index.setdefault(category, []).append(node_id)

        # Relate to category
        cat_id = f"cat_{category}"
        if cat_id in self._nodes:
            self._edges.append(GraphEdge(
                source=node_id, target=cat_id,
                edge_type=EdgeType.CAUSES,
                weight=node.strength / 100,
                evidence=f"Signal contributed to {category} trend",
            ))
        return node

    def ingest_opportunity(self, opp: Any, parent_trends: list[str]) -> GraphNode:
        """Record a discovered opportunity and its causal chain."""
        node = GraphNode(
            node_id=getattr(opp, 'opportunity_id', f"opp_{datetime.now().isoformat()}"),
            node_type=NodeType.OPPORTUNITY,
            name=getattr(opp, 'name', 'opportunity'),
            strength=getattr(opp, 'score', 50),
            evidence=getattr(opp, 'supporting_trends', []),
        )
        self._nodes[node.node_id] = node

        for trend in parent_trends:
            self._edges.append(GraphEdge(
                source=node.node_id, target=f"trend_{trend}",
                edge_type=EdgeType.DERIVES_FROM, weight=0.7,
            ))
        return node

    # ── Reasoning: WHY is this happening? ────────────────────

    def explain(self, category: str) -> dict[str, Any]:
        """Explain WHY a category is trending.

        Returns causal chain: signals → mechanics → success factors.
        """
        cat = self._category_lifecycle.get(category)
        if not cat:
            return {"category": category, "status": "unknown",
                    "causal_analysis": ["No data for this category"],
                    "lifecycle": "unknown", "growth": 0,
                    "driving_signals": [], "action": "Monitor for signals"}

        # Find signals driving this category
        signals = self._signal_index.get(category, [])
        top_signals = sorted(
            [self._nodes[s] for s in signals if s in self._nodes],
            key=lambda n: n.strength, reverse=True,
        )[:5]

        # Causal synthesis
        causes = []
        if cat.growth_rate > 100:
            causes.append(f"Explosive growth at +{cat.growth_rate}% — new market forming")
        elif cat.growth_rate > 50:
            causes.append(f"Strong growth at +{cat.growth_rate}% — category expanding")
        else:
            causes.append(f"Stable/moderate growth at +{cat.growth_rate}%")

        if cat.competition_density < 50:
            causes.append(f"Low competition ({cat.competition_density}% density) — first-mover advantage")
        elif cat.competition_density > 80:
            causes.append(f"High competition ({cat.competition_density}% density) — need clear differentiator")

        if cat.dominant_mechanics:
            causes.append(f"Mechanics: {', '.join(cat.dominant_mechanics)} are proven in this category")

        return {
            "category": category,
            "lifecycle": cat.lifecycle_stage,
            "growth": cat.growth_rate,
            "causal_analysis": causes,
            "driving_signals": [s.to_dict() for s in top_signals],
            "action": self._recommend_action(cat),
        }

    def find_hybrid_opportunities(self) -> list[dict[str, Any]]:
        """Find cross-category hybridization opportunities.

        Looks for mechanics that complement each other across categories.
        """
        opportunities = []
        # Find complementarity: a mechanic from category A + mechanic from category B
        cats = list(self._category_lifecycle.values())
        for i in range(len(cats)):
            for j in range(i + 1, len(cats)):
                c1, c2 = cats[i], cats[j]
                shared = set(c1.dominant_mechanics) & set(c2.dominant_mechanics)
                diff = set(c1.dominant_mechanics) ^ set(c2.dominant_mechanics)

                if shared and diff:
                    opp_score = (c1.strength + c2.strength) / 2
                    opportunities.append({
                        "categories": [c1.name, c2.name],
                        "shared_dna": list(shared),
                        "differential_dna": list(diff),
                        "opportunity_score": round(opp_score, 1),
                        "rationale": f"Combine {c1.name} strength ({c1.growth_rate}% growth) "
                                     f"with {c2.name} differentiation ({c2.lifecycle_stage})",
                    })

        return sorted(opportunities, key=lambda o: o["opportunity_score"], reverse=True)

    # ── Internal ────────────────────────────────────────────

    @staticmethod
    def _classify_lifecycle(growth: float, competition: float) -> str:
        if growth > 100 and competition < 50:
            return "emerging"
        if growth > 50:
            return "growing"
        if growth > 10:
            return "mature"
        return "declining"

    @staticmethod
    def _recommend_action(cat: CategoryNode) -> str:
        if cat.lifecycle_stage == "emerging":
            return "First-mover advantage. Build prototype immediately."
        if cat.lifecycle_stage == "growing":
            return "Growing category. Differentiate with hybrid mechanics."
        if cat.lifecycle_stage == "mature":
            return "Find niche sub-category or premium positioning."
        return "Avoid. Declining category with limited upside."
