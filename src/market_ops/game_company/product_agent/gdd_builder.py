from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class GameDesignDoc:
    gdd_id: str
    game_name: str
    genre: str
    target_audience: str = ""
    core_loop: List[str] = field(default_factory=list)
    mechanics: List[Dict[str, Any]] = field(default_factory=list)
    economy: Dict[str, Any] = field(default_factory=dict)
    levels: List[str] = field(default_factory=list)
    art_style: str = ""
    monetization: Dict[str, Any] = field(default_factory=dict)
    retention_features: List[str] = field(default_factory=list)


class GDDBuilder:
    def __init__(self):
        self.gdds: Dict[str, GameDesignDoc] = {}

    def build(self, concept) -> GameDesignDoc:
        if isinstance(concept, dict):
            name = concept.get("name", "Game")
            genre = concept.get("genre", "Casual")
            audience = concept.get("target_audience", "")
            core_loop = concept.get("core_loop", [])
        else:
            name = concept.name
            genre = concept.genre
            audience = concept.target_audience
            core_loop = concept.core_loop

        gdd = GameDesignDoc(
            gdd_id=f"gdd_{hash(name) % 10000:04d}",
            game_name=name,
            genre=genre,
            target_audience=audience,
            core_loop=core_loop,
            mechanics=self._build_mechanics(genre),
            economy=self._build_economy(genre),
            levels=self._build_levels(genre),
            art_style=self._build_art_style(genre),
            monetization=self._build_monetization(genre),
            retention_features=self._build_retention_features(genre),
        )

        self.gdds[gdd.gdd_id] = gdd
        return gdd

    def _build_mechanics(self, genre: str) -> List[Dict[str, Any]]:
        mechanics_map = {
            "Merge + Decoration": [
                {"name": "Merge", "description": "Combine 3+ items to create new items"},
                {"name": "Collection", "description": "Collect rare items and complete sets"},
                {"name": "Decoration", "description": "Place items to decorate your space"},
                {"name": "Quests", "description": "Complete objectives for rewards"},
            ],
            "Cozy Games": [
                {"name": "Exploration", "description": "Discover new areas and secrets"},
                {"name": "Crafting", "description": "Create items from collected materials"},
                {"name": "Social", "description": "Visit friends' spaces"},
            ],
        }
        return mechanics_map.get(genre, [{"name": "Core", "description": "Main gameplay"}])

    def _build_economy(self, genre: str) -> Dict[str, Any]:
        return {
            "currencies": ["Coins", "Gems"],
            "resources": ["Energy", "Materials"],
            "progression": "Level-based",
        }

    def _build_levels(self, genre: str) -> List[str]:
        return [f"Level {i}" for i in range(1, 51)]

    def _build_art_style(self, genre: str) -> str:
        if "Cozy" in genre or "Witch" in genre:
            return "Charming 2D, pastel colors, cute characters"
        return "Modern 2D, vibrant colors"

    def _build_monetization(self, genre: str) -> Dict[str, Any]:
        return {
            "iap": ["Starter Pack", "Gem Bundles", "Monthly Pass", "Decoration Packs"],
            "ads": ["Reward Video", "Interstitial", "Banner"],
        }

    def _build_retention_features(self, genre: str) -> List[str]:
        return [
            "Daily Rewards",
            "Events",
            "Social Features",
            "Achievements",
            "Push Notifications",
        ]

    def build_demo(self) -> GameDesignDoc:
        concept = {"name": "Cozy Witch Garden", "genre": "Merge + Decoration", "target_audience": "US Female 25-44"}
        return self.build(concept)
