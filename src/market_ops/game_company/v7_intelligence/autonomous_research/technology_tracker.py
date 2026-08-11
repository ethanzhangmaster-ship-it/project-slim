"""Technology tracker module for autonomous research."""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class ImpactLevel(Enum):
    """Impact level classification for technology."""
    MINIMAL = "minimal"
    MODERATE = "moderate"
    SIGNIFICANT = "significant"
    TRANSFORMATIVE = "transformative"


@dataclass
class TechTrend:
    """A technology trend observation."""
    technology: str
    trend_direction: str
    maturity: str
    adoption_rate: float = 0.0
    key_players: List[str] = field(default_factory=list)
    description: str = ""
    observed_at: datetime = field(default_factory=datetime.now)


@dataclass
class TechAssessment:
    """Assessment of a technology's impact."""
    technology: str
    impact_level: ImpactLevel
    time_to_mainstream: str = "unknown"
    investment_recommended: bool = False
    risks: List[str] = field(default_factory=list)
    opportunities: List[str] = field(default_factory=list)
    overall_score: float = 0.0


class TechnologyTracker:
    """Tracks technology trends and assesses their impact."""

    def __init__(self):
        self._tracked: List[str] = []
        self._trends: List[TechTrend] = []
        self._assessments: dict = {}

    def track_technology(self, tech: str) -> TechTrend:
        """Start tracking a technology and return its current trend."""
        self._tracked.append(tech)
        trend = TechTrend(
            technology=tech,
            trend_direction="rising",
            maturity="early_adoption",
            adoption_rate=0.15,
            key_players=["Industry Leader A", "Startup B"],
            description=f"Emerging developments in {tech} showing promise for game applications",
        )
        self._trends.append(trend)
        return trend

    def get_tech_trends(self) -> List[TechTrend]:
        """Get all tracked technology trends."""
        if not self._trends:
            self._trends = [
                TechTrend(
                    technology="Generative AI for Assets",
                    trend_direction="rapidly_rising",
                    maturity="early_majority",
                    adoption_rate=0.35,
                    key_players=["NVIDIA", "Unity", "Adobe"],
                    description="AI-generated 2D/3D assets becoming production-ready",
                ),
                TechTrend(
                    technology="Cloud Native Game Engines",
                    trend_direction="rising",
                    maturity="early_adoption",
                    adoption_rate=0.08,
                    key_players=["Improbable", "Hadean"],
                    description="Distributed simulation enabling massive persistent worlds",
                ),
                TechTrend(
                    technology="Neural Rendering",
                    trend_direction="stable",
                    maturity="innovators",
                    adoption_rate=0.03,
                    key_players=["NVIDIA", "Intel"],
                    description="Real-time neural radiance fields for rendering",
                ),
            ]
        return self._trends

    def assess_impact(self, tech: str) -> TechAssessment:
        """Assess the impact of a specific technology."""
        if tech in self._assessments:
            return self._assessments[tech]

        assessment = TechAssessment(
            technology=tech,
            impact_level=ImpactLevel.SIGNIFICANT,
            time_to_mainstream="2-3 years",
            investment_recommended=True,
            risks=["Talent scarcity", "Rapid standard evolution", "Compute costs"],
            opportunities=["Cost reduction", "Faster iteration", "New gameplay possibilities"],
            overall_score=7.5,
        )
        self._assessments[tech] = assessment
        return assessment

    def get_recommendations(self) -> List[str]:
        """Get technology investment recommendations."""
        return [
            "Prioritize Generative AI tooling for art pipeline — high ROI expected within 12 months",
            "Monitor Cloud Native Game Engines for future MMO projects",
            "Begin Neural Rendering R&D with small prototype team",
            "Evaluate WebGPU for next-gen browser-based experiences",
            "Invest in AI-driven QA automation to reduce testing cycles",
        ]
