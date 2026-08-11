from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class CompetitorProfile:
    competitor_id: str
    name: str
    genre: str
    rank: int
    downloads: int = 0
    revenue_estimate: float = 0.0
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    threat_level: str = "medium"


class CompetitorAnalyzer:
    def __init__(self):
        self.competitors: Dict[str, CompetitorProfile] = {}

    def analyze(self, genre: str, regions=None) -> List[CompetitorProfile]:
        if regions is None:
            regions = ["US"]
        if isinstance(regions, str):
            regions = [regions]
        
        all_competitors = []
        for region in regions:
            competitors = self._get_competitors(genre, region)
            for comp in competitors:
                comp.threat_level = self._assess_threat(comp)
                comp.strengths, comp.weaknesses = self._analyze_strengths_weaknesses(comp)
                self.competitors[comp.competitor_id] = comp
            all_competitors.extend(competitors)
        
        return all_competitors

    def _get_competitors(self, genre: str, region: str) -> List[CompetitorProfile]:
        competitor_database = {
            "Merge + Decoration": [
                {"name": "Merge Mansion", "rank": 1, "downloads": 100_000_000, "revenue": 500_000_000},
                {"name": "Homescapes", "rank": 2, "downloads": 80_000_000, "revenue": 400_000_000},
                {"name": "Matchington Mansion", "rank": 3, "downloads": 50_000_000, "revenue": 200_000_000},
                {"name": "Cozy Merge", "rank": 15, "downloads": 5_000_000, "revenue": 15_000_000},
            ],
            "Cozy Games": [
                {"name": "Stardew Valley", "rank": 1, "downloads": 20_000_000, "revenue": 100_000_000},
                {"name": "Animal Crossing", "rank": 2, "downloads": 15_000_000, "revenue": 80_000_000},
            ],
            "Merge": [
                {"name": "Merge Mansion", "rank": 1, "downloads": 100_000_000, "revenue": 500_000_000},
                {"name": "Merge Game", "rank": 5, "downloads": 30_000_000, "revenue": 100_000_000},
            ],
            "Merge Game": [
                {"name": "Merge Mansion", "rank": 1, "downloads": 100_000_000, "revenue": 500_000_000},
                {"name": "Merge Game", "rank": 5, "downloads": 30_000_000, "revenue": 100_000_000},
            ],
        }
        
        entries = competitor_database.get(genre, [])
        
        if not entries:
            for key in competitor_database:
                if key.lower() in genre.lower() or genre.lower() in key.lower():
                    entries = competitor_database[key]
                    break
        
        if not entries:
            entries = [
                {"name": f"{genre} Competitor 1", "rank": 5, "downloads": 10_000_000, "revenue": 50_000_000},
                {"name": f"{genre} Competitor 2", "rank": 10, "downloads": 5_000_000, "revenue": 25_000_000},
            ]
        return [
            CompetitorProfile(
                competitor_id=f"comp_{hash(c['name']) % 1000:03d}",
                name=c["name"],
                genre=genre,
                rank=c["rank"],
                downloads=c["downloads"],
                revenue_estimate=c["revenue"],
            )
            for c in entries
        ]

    def _assess_threat(self, competitor: CompetitorProfile) -> str:
        if competitor.rank <= 5:
            return "high"
        elif competitor.rank <= 15:
            return "medium"
        else:
            return "low"

    def _analyze_strengths_weaknesses(self, competitor: CompetitorProfile) -> tuple:
        strengths = []
        weaknesses = []
        
        if competitor.rank <= 3:
            strengths.append("Strong brand")
            strengths.append("High retention")
            weaknesses.append("Potential fatigue")
            weaknesses.append("Slow innovation")
        else:
            strengths.append("Niche audience")
            strengths.append("Agile updates")
            weaknesses.append("Low brand awareness")
            weaknesses.append("Limited marketing budget")
        
        return strengths, weaknesses

    def get_competitors(self, genre: str) -> List[CompetitorProfile]:
        return self.analyze(genre)
    
    def get_competition_level(self, genre: str) -> str:
        competitors = self.analyze(genre)
        high_threat = sum(1 for c in competitors if c.threat_level == "high")
        
        if high_threat >= 3:
            return "high"
        elif high_threat >= 1:
            return "medium"
        else:
            return "low"

    def analyze_demo(self) -> List[CompetitorProfile]:
        return self.analyze("Merge + Decoration")
