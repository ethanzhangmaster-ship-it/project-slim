from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class GeneratedScreenshot:
    screenshot_id: str
    title: str
    type: str = "gameplay"
    content: List[str] = field(default_factory=list)
    quality_score: float = 0.0


class ScreenshotGenerator:
    def __init__(self):
        self.screenshots: Dict[str, GeneratedScreenshot] = {}

    def generate(self, game_concept, count: int = 5) -> List[GeneratedScreenshot]:
        screenshots = []
        
        if isinstance(game_concept, dict):
            name = game_concept.get("name", "Game")
            genre = game_concept.get("genre", "")
        else:
            name = game_concept.name
            genre = game_concept.genre

        types = self._generate_types(genre)

        for i in range(count):
            screenshot = GeneratedScreenshot(
                screenshot_id=f"shot_{hash(name + str(i)) % 10000:04d}",
                title=f"{name} - Screenshot {i+1}",
                type=types[i % len(types)],
                content=self._generate_content(types[i % len(types)]),
                quality_score=0.9,
            )
            screenshots.append(screenshot)
            self.screenshots[screenshot.screenshot_id] = screenshot
        
        return screenshots

    def _generate_types(self, genre: str) -> List[str]:
        types = ["gameplay", "gameplay", "ui", "environment"]
        
        if "Decoration" in genre:
            types.append("decoration")
        if "Story" in genre:
            types.append("story")
        
        return types

    def _generate_content(self, screenshot_type: str) -> List[str]:
        content_map = {
            "gameplay": ["Main Gameplay", "Action Shot"],
            "ui": ["Menu", "Inventory"],
            "environment": ["Background", "Level"],
            "decoration": ["Player Home", "Customization"],
            "story": ["Cutscene", "Character"],
        }
        return content_map.get(screenshot_type, ["Gameplay"])

    def generate_demo(self) -> List[GeneratedScreenshot]:
        concept = {"name": "Cozy Witch Garden", "genre": "Merge + Decoration"}
        return self.generate(concept, 5)
