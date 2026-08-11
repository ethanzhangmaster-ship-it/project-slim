from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class CreativeRelation:
    relation_id: str
    creative_id: str
    attribute: str
    value: str
    confidence: float = 0.0


class CreativeGraph:
    def __init__(self):
        self.creatives: Dict[str, Dict[str, Any]] = {}
        self.relations: List[CreativeRelation] = []

    def add_creative(self, creative_id: str, dna: Dict[str, str], performance: Dict[str, float] = None) -> None:
        self.creatives[creative_id] = {
            "dna": dna,
            "performance": performance or {},
        }
        
        for key, value in dna.items():
            self.add_relation(creative_id, key, value, 0.9)

    def add_relation(self, creative_id: str, attribute: str, value: str, confidence: float) -> None:
        relation_id = f"crel_{hash(f'{creative_id}_{attribute}_{value}') % 10000:04d}"
        self.relations.append(CreativeRelation(
            relation_id=relation_id,
            creative_id=creative_id,
            attribute=attribute,
            value=value,
            confidence=confidence,
        ))

    def find_similar_creatives(self, creative_id: str, threshold: float = 0.7) -> List[Dict[str, Any]]:
        source_creative = self.creatives.get(creative_id)
        if not source_creative:
            return []

        source_dna = source_creative["dna"]
        results = []

        for other_id, other_data in self.creatives.items():
            if other_id == creative_id:
                continue
            
            other_dna = other_data["dna"]
            similarity = self._calculate_similarity(source_dna, other_dna)
            
            if similarity >= threshold:
                results.append({
                    "creative_id": other_id,
                    "similarity": round(similarity, 2),
                    "dna": other_dna,
                })

        return sorted(results, key=lambda x: x["similarity"], reverse=True)

    def _calculate_similarity(self, dna1: Dict[str, str], dna2: Dict[str, str]) -> float:
        common_keys = set(dna1.keys()) & set(dna2.keys())
        if not common_keys:
            return 0.0

        matches = sum(1 for k in common_keys if dna1[k] == dna2[k])
        return matches / len(common_keys)

    def find_winner_patterns(self) -> List[Dict[str, Any]]:
        winners = [
            (cid, data) for cid, data in self.creatives.items()
            if data.get("performance", {}).get("roas", 0) > 2.0
        ]

        if not winners:
            return []

        patterns = {}
        for cid, data in winners:
            for key, value in data["dna"].items():
                pattern_key = f"{key}_{value}"
                patterns[pattern_key] = patterns.get(pattern_key, 0) + 1

        total_winners = len(winners)
        return [
            {"pattern": pattern, "frequency": count, "percentage": count / total_winners}
            for pattern, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

    def add_demo(self) -> None:
        self.add_creative(
            "creative_A",
            {"hook": "close_up", "emotion": "surprise", "camera": "static"},
            {"roas": 3.2, "ctr": 0.05},
        )
        self.add_creative(
            "creative_B",
            {"hook": "close_up", "emotion": "excitement", "camera": "static"},
            {"roas": 2.8, "ctr": 0.04},
        )
        self.add_creative(
            "creative_C",
            {"hook": "wide", "emotion": "calm", "camera": "dynamic"},
            {"roas": 1.5, "ctr": 0.02},
        )

    def find_similar_demo(self) -> List[Dict[str, Any]]:
        self.add_demo()
        return self.find_similar_creatives("creative_A")
