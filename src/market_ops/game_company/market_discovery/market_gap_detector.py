from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class MarketGap:
    gap_id: str
    genre: str
    region: str
    audience: str
    gap_type: str
    opportunity_score: float = 0.0
    description: str = ""


class MarketGapDetector:
    def __init__(self):
        self.gaps: List[MarketGap] = []

    def detect(self, trend_data: List[Any], competitor_data=None, keyword_data=None) -> List[MarketGap]:
        if competitor_data is None:
            competitor_data = []
        if keyword_data is None:
            keyword_data = []
        
        if isinstance(trend_data, list) and len(trend_data) > 0 and isinstance(trend_data[0], str):
            trend_data = [{"genre": g, "avg_score": 85, "avg_growth": 0.3} for g in trend_data]
        
        gaps = []
        
        gaps.extend(self._detect_genre_gaps(trend_data, competitor_data))
        gaps.extend(self._detect_audience_gaps(trend_data))
        gaps.extend(self._detect_keyword_gaps(keyword_data))
        
        for gap in gaps:
            gap.opportunity_score = self._score_gap(gap)
        
        self.gaps.extend(gaps)
        return gaps

    def _detect_genre_gaps(self, trends: List[Dict[str, Any]], competitors: List[Dict[str, Any]]) -> List[MarketGap]:
        gaps = []
        
        for trend in trends:
            if trend["avg_score"] > 75:
                competitor_count = sum(1 for c in competitors if c.get("genre") == trend["genre"])
                if competitor_count < 5:
                    gaps.append(MarketGap(
                        gap_id=f"gap_genre_{hash(trend['genre']) % 1000:03d}",
                        genre=trend["genre"],
                        region="US",
                        audience="Female 25-44",
                        gap_type="genre",
                        description=f"High trend score {trend['avg_score']} but limited competition",
                    ))
        
        return gaps

    def _detect_audience_gaps(self, trends: List[Dict[str, Any]]) -> List[MarketGap]:
        gaps = []
        
        for trend in trends:
            if "Merge" in trend["genre"] and "Decoration" in trend["genre"]:
                gaps.append(MarketGap(
                    gap_id=f"gap_audience_{hash(trend['genre']) % 1000:03d}",
                    genre=trend["genre"],
                    region="US",
                    audience="Female 35-54",
                    gap_type="audience",
                    description="Underserved older female demographic",
                ))
        
        return gaps

    def _detect_keyword_gaps(self, keywords: List[Dict[str, Any]]) -> List[MarketGap]:
        gaps = []
        
        for kw in keywords:
            if isinstance(kw, dict):
                opp_score = kw.get("opportunity_score", 0)
            else:
                opp_score = kw.opportunity_score
            
            if opp_score > 70:
                gaps.append(MarketGap(
                    gap_id=f"gap_keyword_{hash(str(kw)) % 1000:03d}",
                    genre="Merge + Decoration",
                    region="US",
                    audience="Searchers",
                    gap_type="keyword",
                    description=f"High opportunity keyword gap",
                ))
        
        return gaps

    def _score_gap(self, gap: MarketGap) -> float:
        base_score = 50
        
        if gap.gap_type == "genre":
            base_score += 20
        if gap.gap_type == "keyword":
            base_score += 25
        if gap.gap_type == "audience":
            base_score += 15
        
        if "Female" in gap.audience:
            base_score += 10
        
        return min(base_score, 100)

    def detect_demo(self) -> List[MarketGap]:
        trends = [
            {"genre": "Merge + Decoration", "avg_score": 85, "avg_growth": 0.35},
            {"genre": "Cozy Witch", "avg_score": 90, "avg_growth": 0.5},
        ]
        competitors = [{"genre": "Merge + Decoration"}] * 3
        keywords = [{"opportunity_score": 75}]
        
        return self.detect(trends, competitors, keywords)
