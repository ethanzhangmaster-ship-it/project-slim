from dataclasses import dataclass
from typing import List, Dict, Any
import random


@dataclass
class MarketGap:
    gap_id: str
    genre: str
    sub_genre: str
    underserved_segment: str
    estimated_demand: int
    competition_level: str
    barrier_to_entry: str
    description: str
    score: float = 0.0


@dataclass
class ScoredGap:
    gap: MarketGap
    score: float
    confidence: float
    reasoning: str


@dataclass
class Opportunity:
    opportunity_id: str
    gap: MarketGap
    recommended_action: str
    expected_roi: float
    time_to_market: str
    priority: str


class MarketGapAI:
    """Identify and score market gaps using AI analysis."""

    _gaps: List[MarketGap] = []

    def __init__(self):
        self._gaps = self._generate_mock_gaps()

    def _generate_mock_gaps(self) -> List[MarketGap]:
        genres = ["RPG", "Strategy", "Puzzle", "Action", "Simulation", "Casual", "Sports"]
        sub_genres = ["mid-core", "hyper-casual", "narrative", "social", "competitive"]
        segments = ["seniors", "gen_z", "families", "hardcore", "casual_commuters"]
        competition_levels = ["low", "medium", "high"]
        barriers = ["low", "medium", "high"]
        gaps = []
        for i in range(10):
            gaps.append(
                MarketGap(
                    gap_id=f"gap_{i:03d}",
                    genre=random.choice(genres),
                    sub_genre=random.choice(sub_genres),
                    underserved_segment=random.choice(segments),
                    estimated_demand=random.randint(100000, 5000000),
                    competition_level=random.choice(competition_levels),
                    barrier_to_entry=random.choice(barriers),
                    description=f"Underserved opportunity in {random.choice(genres)} for {random.choice(segments)}.",
                )
            )
        return gaps

    def find_gaps(self) -> List[MarketGap]:
        """Find potential market gaps."""
        return self._gaps

    def score_gap(self, gap: MarketGap) -> ScoredGap:
        """Score a specific market gap."""
        score = round(random.uniform(30, 95), 2)
        confidence = round(random.uniform(0.5, 0.95), 2)
        reasoning = (
            f"High demand ({gap.estimated_demand}) with {gap.competition_level} competition "
            f"and {gap.barrier_to_entry} barriers."
        )
        return ScoredGap(gap=gap, score=score, confidence=confidence, reasoning=reasoning)

    def get_opportunities(self) -> List[Opportunity]:
        """Return scored opportunities based on gaps."""
        opportunities = []
        for gap in self._gaps[:5]:
            scored = self.score_gap(gap)
            opportunities.append(
                Opportunity(
                    opportunity_id=f"opp_{gap.gap_id}",
                    gap=gap,
                    recommended_action=random.choice(["develop_game", "acquire_studio", "partner", "wait_and_see"]),
                    expected_roi=round(random.uniform(1.2, 5.0), 2),
                    time_to_market=f"{random.randint(3, 18)} months",
                    priority="high" if scored.score > 70 else "medium" if scored.score > 50 else "low",
                )
            )
        return opportunities
