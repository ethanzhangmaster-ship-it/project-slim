"""Competitor watcher module for autonomous research."""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class ThreatLevel(Enum):
    """Threat level classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CompetitorMove:
    """A move made by a competitor."""
    competitor: str
    action: str
    description: str
    date: datetime = field(default_factory=datetime.now)
    category: str = "general"
    expected_impact: str = "unknown"
    source_url: str = ""


@dataclass
class CompetitorAnalysis:
    """Analysis of a competitor."""
    competitor: str
    threat_level: ThreatLevel
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recent_moves: List[CompetitorMove] = field(default_factory=list)
    market_position: str = "unknown"
    recommended_response: str = "monitor"


class CompetitorWatcher:
    """Watches competitors and analyzes their strategies."""

    def __init__(self):
        self._watched: List[str] = []
        self._moves: List[CompetitorMove] = []
        self._analyses: dict = {}

    def watch(self, competitor: str) -> CompetitorAnalysis:
        """Start watching a competitor and return initial analysis."""
        self._watched.append(competitor)
        analysis = CompetitorAnalysis(
            competitor=competitor,
            threat_level=ThreatLevel.MEDIUM,
            strengths=["Strong IP portfolio", "Global distribution network"],
            weaknesses=["High operating costs", "Slow decision making"],
            market_position="top_5",
            recommended_response="monitor",
        )
        self._analyses[competitor] = analysis
        return analysis

    def get_latest_moves(self) -> List[CompetitorMove]:
        """Get the latest moves from all watched competitors."""
        if not self._moves:
            self._moves = [
                CompetitorMove(
                    competitor="RivalGames Inc",
                    action="launched_new_title",
                    description="Released AAA open-world RPG targeting our core demographic",
                    category="product",
                    expected_impact="high",
                ),
                CompetitorMove(
                    competitor="NextGen Studios",
                    action="acquired_studio",
                    description="Acquired indie studio with breakthrough AI tech for $120M",
                    category="m&a",
                    expected_impact="medium",
                ),
                CompetitorMove(
                    competitor="RivalGames Inc",
                    action="pricing_change",
                    description="Reduced battle pass price by 30% in APAC region",
                    category="pricing",
                    expected_impact="medium",
                ),
            ]
        return self._moves

    def analyze_strategy(self, competitor: str) -> CompetitorAnalysis:
        """Analyze the strategy of a specific competitor."""
        if competitor in self._analyses:
            return self._analyses[competitor]
        return CompetitorAnalysis(
            competitor=competitor,
            threat_level=ThreatLevel.LOW,
            strengths=["Agile development", "Strong community engagement"],
            weaknesses=["Limited funding", "Narrow genre focus"],
            market_position="challenger",
            recommended_response="observe",
        )

    def get_threat_level(self, competitor: str) -> ThreatLevel:
        """Get the threat level of a competitor."""
        analysis = self.analyze_strategy(competitor)
        return analysis.threat_level
