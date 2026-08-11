from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class ASORecommendation:
    aso_id: str
    title: str = ""
    subtitle: str = ""
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)
    optimization_score: float = 0.0


class ASOOptimizer:
    def __init__(self):
        self.recommendations: Dict[str, ASORecommendation] = {}

    def optimize(self, game_data: Dict[str, Any], keywords: List[str]) -> ASORecommendation:
        name = game_data.get("name", "Game")
        genre = game_data.get("genre", "Casual")
        
        title = self._generate_title(name, keywords)
        subtitle = self._generate_subtitle(genre)
        description = self._generate_description(game_data)
        optimized_keywords = self._optimize_keywords(keywords)

        score = self._calculate_score(len(optimized_keywords), len(title))

        recommendation = ASORecommendation(
            aso_id=f"aso_{hash(name) % 10000:04d}",
            title=title,
            subtitle=subtitle,
            description=description,
            keywords=optimized_keywords,
            metadata={"primary_category": genre, "secondary_category": "Games"},
            optimization_score=round(score, 1),
        )

        self.recommendations[recommendation.aso_id] = recommendation
        return recommendation

    def _generate_title(self, name: str, keywords: List[str]) -> str:
        main_keywords = keywords[:3]
        return f"{name}: {' '.join(main_keywords)}"

    def _generate_subtitle(self, genre: str) -> str:
        genre_map = {
            "Merge": "Merge & Match Puzzle",
            "Casual": "Fun Casual Game",
            "Decoration": "Design & Decorate",
        }
        return genre_map.get(genre, "Mobile Game")

    def _generate_description(self, game_data: Dict[str, Any]) -> str:
        name = game_data.get("name", "Game")
        core_loop = game_data.get("core_loop", ["Play"])
        return f"Play {name}! {', '.join(core_loop)}. Fun for all ages!"

    def _optimize_keywords(self, keywords: List[str]) -> List[str]:
        return sorted(keywords, key=len, reverse=True)[:10]

    def _calculate_score(self, keyword_count: int, title_length: int) -> float:
        score = 70
        if keyword_count >= 5:
            score += 15
        if title_length >= 20:
            score += 10
        return min(score, 95)

    def optimize_demo(self) -> ASORecommendation:
        game_data = {"name": "Cozy Witch Garden", "genre": "Merge", "core_loop": ["Merge", "Reward", "Decorate"]}
        keywords = ["merge game", "match puzzle", "decorate", "cozy game", "witch", "garden"]
        return self.optimize(game_data, keywords)
