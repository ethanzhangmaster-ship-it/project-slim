from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class KeywordOpportunity:
    keyword_id: str
    keyword: str
    volume: int = 0
    difficulty: float = 0.0
    opportunity_score: float = 0.0
    related_keywords: List[str] = field(default_factory=list)


class KeywordMiner:
    def __init__(self):
        self.keywords: Dict[str, KeywordOpportunity] = {}

    def mine(self, genre: str, regions=None) -> List[KeywordOpportunity]:
        if regions is None:
            regions = ["US"]
        if isinstance(regions, str):
            regions = [regions]
        
        all_keywords = []
        for region in regions:
            keywords = self._get_keywords(genre, region)
            for kw in keywords:
                kw.opportunity_score = self._calculate_opportunity(kw)
                self.keywords[kw.keyword_id] = kw
            all_keywords.extend(keywords)
        
        return all_keywords

    def _get_keywords(self, genre: str, region: str) -> List[KeywordOpportunity]:
        keyword_database = {
            "Merge + Decoration": {
                "US": [
                    {"keyword": "merge mansion", "volume": 500000, "difficulty": 0.95},
                    {"keyword": "cozy merge game", "volume": 150000, "difficulty": 0.55},
                    {"keyword": "merge decoration", "volume": 80000, "difficulty": 0.45},
                ],
                "JP": [
                    {"keyword": "マージマンション", "volume": 100000, "difficulty": 0.85},
                    {"keyword": "マージゲーム", "volume": 80000, "difficulty": 0.6},
                    {"keyword": "コジーマージ", "volume": 40000, "difficulty": 0.4},
                ],
                "DE": [
                    {"keyword": "merge mansion", "volume": 60000, "difficulty": 0.8},
                    {"keyword": "cozy merge", "volume": 30000, "difficulty": 0.5},
                    {"keyword": "merge spiel", "volume": 25000, "difficulty": 0.45},
                ],
            },
            "Cozy Games": {
                "US": [
                    {"keyword": "cozy games", "volume": 200000, "difficulty": 0.7},
                    {"keyword": "cozy witch game", "volume": 40000, "difficulty": 0.3},
                ],
                "JP": [
                    {"keyword": "コジーゲーム", "volume": 30000, "difficulty": 0.5},
                ],
                "DE": [
                    {"keyword": "cozy games", "volume": 25000, "difficulty": 0.55},
                ],
            },
            "Merge": {
                "US": [
                    {"keyword": "merge game", "volume": 300000, "difficulty": 0.75},
                    {"keyword": "merge puzzle", "volume": 120000, "difficulty": 0.5},
                    {"keyword": "merge 3", "volume": 80000, "difficulty": 0.6},
                ],
                "JP": [
                    {"keyword": "マージゲーム", "volume": 150000, "difficulty": 0.65},
                    {"keyword": "マージパズル", "volume": 60000, "difficulty": 0.45},
                ],
                "DE": [
                    {"keyword": "merge spiel", "volume": 50000, "difficulty": 0.5},
                    {"keyword": "merge puzzle", "volume": 30000, "difficulty": 0.4},
                ],
            },
        }
        
        genre_data = keyword_database.get(genre, {})
        entries = genre_data.get(region, genre_data.get("US", []))
        
        if not entries:
            entries = [
                {"keyword": f"{genre} game", "volume": 50000, "difficulty": 0.5},
                {"keyword": f"best {genre}", "volume": 30000, "difficulty": 0.6},
            ]
        
        return [
            KeywordOpportunity(
                keyword_id=f"kw_{hash(k['keyword'] + region) % 1000:03d}",
                keyword=k["keyword"],
                volume=k["volume"],
                difficulty=k["difficulty"],
                related_keywords=self._find_related(k["keyword"], entries),
            )
            for k in entries
        ]

    def get_keywords(self, genre: str) -> List[KeywordOpportunity]:
        return self.mine(genre)

    def _find_related(self, keyword: str, all_keywords: List[Dict[str, Any]]) -> List[str]:
        related = []
        for kw in all_keywords:
            if kw["keyword"] != keyword and len(set(keyword.split()) & set(kw["keyword"].split())) > 0:
                related.append(kw["keyword"])
        return related[:3]

    def _calculate_opportunity(self, keyword: KeywordOpportunity) -> float:
        volume_score = min(keyword.volume / 100000, 1)
        difficulty_score = 1 - keyword.difficulty
        
        return round((volume_score * 0.6 + difficulty_score * 0.4) * 100, 1)

    def get_gap_keywords(self, threshold: float = 70) -> List[KeywordOpportunity]:
        return [kw for kw in self.keywords.values() if kw.opportunity_score >= threshold]

    def mine_demo(self) -> List[KeywordOpportunity]:
        return self.mine("Merge + Decoration")
