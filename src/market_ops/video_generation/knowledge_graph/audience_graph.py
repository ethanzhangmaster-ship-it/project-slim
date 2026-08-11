from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class AudienceRelation:
    relation_id: str
    segment_id: str
    attribute: str
    value: str
    confidence: float = 0.0


class AudienceGraph:
    def __init__(self):
        self.segments: Dict[str, Dict[str, Any]] = {}
        self.relations: List[AudienceRelation] = []

    def add_segment(self, segment_id: str, profile: Dict[str, str], performance: Dict[str, float] = None) -> None:
        self.segments[segment_id] = {
            "profile": profile,
            "performance": performance or {},
        }
        
        for key, value in profile.items():
            self.add_relation(segment_id, key, value, 0.95)

    def add_relation(self, segment_id: str, attribute: str, value: str, confidence: float) -> None:
        relation_id = f"arel_{hash(f'{segment_id}_{attribute}_{value}') % 10000:04d}"
        self.relations.append(AudienceRelation(
            relation_id=relation_id,
            segment_id=segment_id,
            attribute=attribute,
            value=value,
            confidence=confidence,
        ))

    def find_compatible_creatives(self, segment_id: str, creative_dna: Dict[str, str]) -> float:
        segment = self.segments.get(segment_id)
        if not segment:
            return 0.0

        profile = segment["profile"]
        score = 0.0

        genre_preferences = {
            "casual": ["cute", "relax", "simple"],
            "midcore": ["strategy", "challenge", "progression"],
            "hardcore": ["competitive", "complex", "skill"],
        }

        game_genre = profile.get("game_genre", "casual")
        preferences = genre_preferences.get(game_genre, [])

        for dna_key, dna_value in creative_dna.items():
            if dna_value in preferences:
                score += 0.2

        if profile.get("gender") == "female":
            if creative_dna.get("emotion") in ["cute", "happy", "surprise"]:
                score += 0.2

        if profile.get("age_range") in ["25-34", "30-44"]:
            score += 0.1

        return min(score, 1.0)

    def find_high_ltv_segments(self) -> List[Dict[str, Any]]:
        results = []
        for segment_id, data in self.segments.items():
            ltv = data.get("performance", {}).get("ltv", 0)
            if ltv > 3.0:
                results.append({
                    "segment_id": segment_id,
                    "ltv": ltv,
                    "profile": data["profile"],
                })
        return sorted(results, key=lambda x: x["ltv"], reverse=True)

    def add_demo(self) -> None:
        self.add_segment(
            "US_Female_25-34",
            {"country": "US", "gender": "female", "age_range": "25-34", "os": "iOS", "game_genre": "casual"},
            {"ltv": 3.5, "conversion_rate": 0.08},
        )
        self.add_segment(
            "US_Male_18-24",
            {"country": "US", "gender": "male", "age_range": "18-24", "os": "Android", "game_genre": "midcore"},
            {"ltv": 2.8, "conversion_rate": 0.06},
        )

    def find_compatible_demo(self) -> float:
        self.add_demo()
        dna = {"emotion": "cute", "hook": "close_up"}
        return self.find_compatible_creatives("US_Female_25-34", dna)
