from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class GeneratedIcon:
    icon_id: str
    title: str
    style: str = "cozy"
    elements: List[str] = field(default_factory=list)
    quality_score: float = 0.0


class IconGenerator:
    def __init__(self):
        self.icons: Dict[str, GeneratedIcon] = {}

    def generate(self, game_concept, count: int = 3) -> List[GeneratedIcon]:
        icons = []
        
        if isinstance(game_concept, dict):
            name = game_concept.get("name", "Game")
            genre = game_concept.get("genre", "")
        else:
            name = game_concept.name
            genre = game_concept.genre

        style = self._determine_style(genre)
        elements = self._generate_elements(genre)

        for i in range(count):
            icon = GeneratedIcon(
                icon_id=f"icon_{hash(name + str(i)) % 10000:04d}",
                title=f"{name} - Icon {i+1}",
                style=style,
                elements=elements,
                quality_score=0.92,
            )
            icons.append(icon)
            self.icons[icon.icon_id] = icon
        
        return icons

    def _determine_style(self, genre: str) -> str:
        if "Cozy" in genre or "Witch" in genre:
            return "cozy"
        if "Action" in genre:
            return "dynamic"
        return "modern"

    def _generate_elements(self, genre: str) -> List[str]:
        elements = []
        
        if "Merge" in genre:
            elements.append("Merging Items")
        if "Decoration" in genre:
            elements.append("Home/Garden")
        if "Witch" in genre:
            elements.append("Magic Elements")
        if "Cozy" in genre:
            elements.append("Cute Characters")
        
        if not elements:
            elements.append("Game Logo")
        
        return elements

    def generate_demo(self) -> List[GeneratedIcon]:
        concept = {"name": "Cozy Witch Garden", "genre": "Merge + Decoration"}
        return self.generate(concept, 2)
