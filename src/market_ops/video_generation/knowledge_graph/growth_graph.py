from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class GrowthRelation:
    relation_id: str
    source: str
    target: str
    relation_type: str
    confidence: float = 0.0
    weight: float = 0.0


class GrowthGraph:
    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.relations: List[GrowthRelation] = []

    def add_node(self, node_id: str, node_type: str, properties: Dict[str, Any] = None) -> None:
        self.nodes[node_id] = {
            "type": node_type,
            "properties": properties or {},
        }

    def add_relation(self, source: str, target: str, relation_type: str, confidence: float = 0.5) -> None:
        relation_id = f"rel_{hash(f'{source}_{target}_{relation_type}') % 10000:04d}"
        self.relations.append(GrowthRelation(
            relation_id=relation_id,
            source=source,
            target=target,
            relation_type=relation_type,
            confidence=confidence,
            weight=confidence,
        ))

    def get_relations(self, node_id: str) -> List[GrowthRelation]:
        return [
            r for r in self.relations
            if r.source == node_id or r.target == node_id
        ]

    def predict_revenue(self, creative: str, audience: str, platform: str) -> float:
        creative_relations = self.get_relations(creative)
        audience_relations = self.get_relations(audience)
        platform_relations = self.get_relations(platform)

        base_score = 0.3
        for rel in creative_relations:
            if rel.target == audience or rel.target == platform:
                base_score += rel.confidence * 0.2
        
        for rel in audience_relations:
            if rel.target == platform:
                base_score += rel.confidence * 0.2

        return min(base_score, 0.95)

    def build_demo(self) -> None:
        self.add_node("creative_A", "creative", {"dna": {"hook": "close_up", "emotion": "surprise"}})
        self.add_node("audience_F25-34", "audience", {"country": "US", "gender": "female", "age": "25-34"})
        self.add_node("platform_meta_ios", "platform", {"platform": "meta", "os": "iOS"})
        self.add_node("outcome_high_purchase", "outcome", {"type": "high_purchase"})

        self.add_relation("creative_A", "audience_F25-34", "matches", 0.9)
        self.add_relation("creative_A", "platform_meta_ios", "performs_on", 0.85)
        self.add_relation("audience_F25-34", "platform_meta_ios", "uses", 0.8)
        self.add_relation("creative_A", "outcome_high_purchase", "leads_to", 0.88)

    def predict_demo(self) -> float:
        self.build_demo()
        return self.predict_revenue("creative_A", "audience_F25-34", "platform_meta_ios")
