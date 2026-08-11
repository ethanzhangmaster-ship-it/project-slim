from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import random


@dataclass
class PlacementPerformance:
    placement_id: str
    name: str
    platform: str
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    spend: float = 0.0
    revenue: float = 0.0
    roas: float = 0.0
    ctr: float = 0.0
    cvr: float = 0.0
    cpm: float = 0.0
    status: str = "active"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "placement_id": self.placement_id,
            "name": self.name,
            "platform": self.platform,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "conversions": self.conversions,
            "spend": self.spend,
            "revenue": self.revenue,
            "roas": self.roas,
            "ctr": self.ctr,
            "cvr": self.cvr,
            "cpm": self.cpm,
            "status": self.status,
        }


@dataclass
class PlacementRecommendation:
    recommendation_id: str
    placement_id: str
    action: str
    reason: str = ""
    confidence: float = 0.0
    expected_impact: float = 0.0
    priority: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "placement_id": self.placement_id,
            "action": self.action,
            "reason": self.reason,
            "confidence": self.confidence,
            "expected_impact": self.expected_impact,
            "priority": self.priority,
        }


@dataclass
class PlacementAnalysis:
    campaign_id: str
    placements: List[PlacementPerformance] = field(default_factory=list)
    total_placements: int = 0
    top_performers: List[str] = field(default_factory=list)
    underperformers: List[str] = field(default_factory=list)
    recommendations: List[PlacementRecommendation] = field(default_factory=list)
    analyzed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "placements": [p.to_dict() for p in self.placements],
            "total_placements": self.total_placements,
            "top_performers": self.top_performers,
            "underperformers": self.underperformers,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "analyzed_at": self.analyzed_at.isoformat(),
        }


class PlacementOptimizer:
    def __init__(self):
        self._placements: Dict[str, PlacementPerformance] = {}
        self._excluded: List[str] = []
        self._analyses: List[PlacementAnalysis] = []

    def add_placement(self, placement: PlacementPerformance):
        self._placements[placement.placement_id] = placement

    def analyze_placements(self, campaign_id: str) -> PlacementAnalysis:
        placements = []
        top_performers = []
        underperformers = []
        recommendations = []

        for i in range(5):
            placement_id = f"place_{campaign_id}_{i}"
            roas = random.uniform(0.5, 3.0)
            placement = PlacementPerformance(
                placement_id=placement_id,
                name=f"Placement {i}",
                platform=random.choice(["facebook", "instagram", "audience_network"]),
                impressions=random.randint(10000, 100000),
                clicks=random.randint(100, 1000),
                conversions=random.randint(10, 100),
                spend=random.uniform(100, 1000),
                revenue=random.uniform(100, 2000),
                roas=roas,
                ctr=random.uniform(0.01, 0.05),
                cvr=random.uniform(0.1, 0.3),
                cpm=random.uniform(5, 20),
            )
            placements.append(placement)

            if roas > 1.5:
                top_performers.append(placement_id)
            elif roas < 0.8:
                underperformers.append(placement_id)
                recommendations.append(PlacementRecommendation(
                    recommendation_id=f"rec_{placement_id}",
                    placement_id=placement_id,
                    action="exclude",
                    reason=f"ROAS {roas:.2f} below threshold",
                    confidence=0.85,
                    expected_impact=-0.2,
                    priority=2,
                ))

        analysis = PlacementAnalysis(
            campaign_id=campaign_id,
            placements=placements,
            total_placements=len(placements),
            top_performers=top_performers,
            underperformers=underperformers,
            recommendations=recommendations,
        )
        self._analyses.append(analysis)
        return analysis

    def get_placement_recommendations(self, campaign_id: str = None) -> List[PlacementRecommendation]:
        if campaign_id:
            for analysis in self._analyses:
                if analysis.campaign_id == campaign_id:
                    return analysis.recommendations
        recs = []
        for analysis in self._analyses:
            recs.extend(analysis.recommendations)
        return recs

    def exclude_placement(self, placement_id: str) -> bool:
        if placement_id in self._placements:
            self._placements[placement_id].status = "excluded"
            self._excluded.append(placement_id)
            return True
        return False

    def include_placement(self, placement_id: str) -> bool:
        if placement_id in self._placements:
            self._placements[placement_id].status = "active"
            if placement_id in self._excluded:
                self._excluded.remove(placement_id)
            return True
        return False

    def get_placement(self, placement_id: str) -> Optional[PlacementPerformance]:
        return self._placements.get(placement_id)

    def get_placements(self, campaign_id: str = None) -> List[PlacementPerformance]:
        return list(self._placements.values())

    def get_excluded(self) -> List[str]:
        return list(self._excluded)

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._placements)
        active = sum(1 for p in self._placements.values() if p.status == "active")
        avg_roas = sum(p.roas for p in self._placements.values()) / total if total > 0 else 0
        return {
            "total_placements": total,
            "active_placements": active,
            "excluded_placements": len(self._excluded),
            "avg_roas": avg_roas,
            "total_analyses": len(self._analyses),
        }