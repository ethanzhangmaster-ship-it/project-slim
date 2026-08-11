from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class GameConcept:
    concept_id: str
    name: str
    genre: str
    core_loop: List[str] = field(default_factory=list)
    target_audience: str = ""
    unique_selling_points: List[str] = field(default_factory=list)
    market_fit_score: float = 0.0
    confidence: float = 0.0


class ConceptGenerator:
    def __init__(self):
        self.concepts: List[GameConcept] = []

    def generate(self, market_opportunity: Dict[str, Any]) -> GameConcept:
        genre = market_opportunity.get("genre", "Casual")
        audience = market_opportunity.get("audience", "Female 25-44")
        opportunity_score = market_opportunity.get("opportunity_score", 70)

        name = self._generate_name(genre)
        core_loop = self._generate_core_loop(genre)
        usps = self._generate_usps(genre, opportunity_score)

        concept = GameConcept(
            concept_id=f"concept_{hash(name) % 10000:04d}",
            name=name,
            genre=genre,
            core_loop=core_loop,
            target_audience=audience,
            unique_selling_points=usps,
            market_fit_score=opportunity_score,
            confidence=self._calculate_confidence(opportunity_score),
        )

        self.concepts.append(concept)
        return concept

    def _generate_name(self, genre: str) -> str:
        name_map = {
            "Merge + Decoration": ["Cozy Witch Garden", "Enchanted Merge", "Magical Home Merge"],
            "Cozy Games": ["Witchy Haven", "Cozy Cottage", "Dreamy Days"],
            "Merge + Story": ["Merge Tale", "Story Merge", "Fable Merge"],
        }
        return name_map.get(genre, ["Casual Game"])[0]

    def _generate_core_loop(self, genre: str) -> List[str]:
        loop_map = {
            "Merge + Decoration": ["Merge", "Reward", "Decoration", "Retention"],
            "Cozy Games": ["Explore", "Create", "Interact", "Relax"],
            "Merge + Story": ["Merge", "Progress", "Story", "Unlock"],
        }
        return loop_map.get(genre, ["Play", "Reward", "Repeat"])

    def _generate_usps(self, genre: str, score: float) -> List[str]:
        usps = []
        
        if "Merge" in genre:
            usps.append("Unique merge mechanics")
            usps.append("Satisfying progression")
        
        if "Decoration" in genre:
            usps.append("Customizable home")
            usps.append("Creative expression")
        
        if "Cozy" in genre:
            usps.append("Relaxing gameplay")
            usps.append("Charming art style")
        
        if score > 80:
            usps.append("Proven market demand")
        
        return usps

    def _calculate_confidence(self, opportunity_score: float) -> float:
        return min(opportunity_score / 100, 0.95)

    def generate_demo(self) -> GameConcept:
        opportunity = {
            "genre": "Merge + Decoration",
            "audience": "US Female 25-44",
            "opportunity_score": 87,
        }
        return self.generate(opportunity)
