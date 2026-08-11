from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class GameMechanic:
    mechanic_id: str
    name: str
    description: str
    complexity: str = "medium"
    fun_factor: float = 0.0
    implementation_effort: int = 1
    retention_impact: float = 0.0


class MechanicDesigner:
    def __init__(self):
        self.mechanics: Dict[str, GameMechanic] = {}

    def design(self, genre: str, target_audience: str = "Female 25-44") -> List[GameMechanic]:
        mechanics = self._get_genre_mechanics(genre)
        
        for mechanic in mechanics:
            mechanic.complexity = self._determine_complexity(target_audience)
            mechanic.fun_factor = self._calculate_fun_factor(mechanic, genre)
            mechanic.retention_impact = self._calculate_retention_impact(mechanic)
            self.mechanics[mechanic.mechanic_id] = mechanic
        
        return mechanics

    def _get_genre_mechanics(self, genre: str) -> List[GameMechanic]:
        mechanics_map = {
            "Merge + Decoration": [
                GameMechanic("merge_3", "3-Way Merge", "Combine 3 identical items"),
                GameMechanic("merge_5", "5-Way Merge", "Combine 5 for rare items"),
                GameMechanic("collection", "Collection System", "Complete item sets"),
                GameMechanic("decoration", "Decoration Mode", "Place items freely"),
                GameMechanic("quests", "Quest System", "Story-driven objectives"),
            ],
            "Cozy Games": [
                GameMechanic("explore", "Exploration", "Discover new areas"),
                GameMechanic("craft", "Crafting", "Create items from materials"),
                GameMechanic("social", "Social Visits", "Visit friends"),
                GameMechanic("farm", "Farming", "Grow plants"),
            ],
        }
        return mechanics_map.get(genre, [GameMechanic("core", "Core Gameplay", "Main mechanic")])

    def _determine_complexity(self, audience: str) -> str:
        if "Female" in audience and ("35" in audience or "40" in audience):
            return "low"
        return "medium"

    def _calculate_fun_factor(self, mechanic: GameMechanic, genre: str) -> float:
        fun_scores = {
            "merge_3": 0.85,
            "merge_5": 0.9,
            "collection": 0.8,
            "decoration": 0.85,
            "quests": 0.75,
            "explore": 0.8,
            "craft": 0.75,
            "social": 0.7,
            "farm": 0.75,
        }
        return fun_scores.get(mechanic.mechanic_id, 0.7)

    def _calculate_retention_impact(self, mechanic: GameMechanic) -> float:
        if "collection" in mechanic.mechanic_id or "quest" in mechanic.mechanic_id:
            return 0.85
        if "social" in mechanic.mechanic_id:
            return 0.75
        return 0.65

    def design_demo(self) -> List[GameMechanic]:
        return self.design("Merge + Decoration", "US Female 25-44")
