from dataclasses import dataclass
from typing import List, Dict, Any
import random


@dataclass
class CompetitorProfile:
    name: str
    market_share: float
    active_games: int
    avg_rating: float
    monthly_revenue: float
    user_base: int


@dataclass
class PredictedMove:
    competitor: str
    move_type: str
    probability: float
    expected_timeline: str
    potential_impact: str


@dataclass
class StrengthAssessment:
    competitor: str
    strengths: List[str]
    weaknesses: List[str]
    threat_level: str
    score: float


class CompetitorPrediction:
    """Track competitors and predict their strategic moves."""

    _competitors: Dict[str, CompetitorProfile] = {}

    def __init__(self):
        self._competitors = {
            f"Competitor {i}": CompetitorProfile(
                name=f"Competitor {i}",
                market_share=round(random.uniform(1.0, 25.0), 2),
                active_games=random.randint(1, 20),
                avg_rating=round(random.uniform(3.5, 4.9), 2),
                monthly_revenue=round(random.uniform(100000, 10000000), 2),
                user_base=random.randint(50000, 5000000),
            )
            for i in range(1, 6)
        }

    def track(self, competitor: str) -> Dict[str, Any]:
        """Track a competitor's current status."""
        profile = self._competitors.get(competitor)
        if not profile:
            profile = CompetitorProfile(
                name=competitor,
                market_share=round(random.uniform(1.0, 25.0), 2),
                active_games=random.randint(1, 20),
                avg_rating=round(random.uniform(3.5, 4.9), 2),
                monthly_revenue=round(random.uniform(100000, 10000000), 2),
                user_base=random.randint(50000, 5000000),
            )
            self._competitors[competitor] = profile
        return {
            "competitor": competitor,
            "profile": profile,
            "recent_activities": [f"Launched new feature {i}" for i in range(random.randint(1, 4))],
        }

    def predict_next_move(self, competitor: str) -> PredictedMove:
        """Predict the next strategic move of a competitor."""
        move_types = ["new_game_launch", "acquisition", "price_change", "marketing_push", "partnership"]
        impacts = ["low", "medium", "high", "critical"]
        return PredictedMove(
            competitor=competitor,
            move_type=random.choice(move_types),
            probability=round(random.uniform(0.3, 0.9), 2),
            expected_timeline=f"{random.randint(1, 6)} months",
            potential_impact=random.choice(impacts),
        )

    def get_strengths(self, competitor: str) -> StrengthAssessment:
        """Analyze strengths and weaknesses of a competitor."""
        strengths = ["strong_ip", "large_user_base", "high_retention", "innovative_mechanics"]
        weaknesses = ["limited_genres", "high_churn", "poor_monetization", "weak_marketing"]
        threat_levels = ["low", "medium", "high", "critical"]
        return StrengthAssessment(
            competitor=competitor,
            strengths=random.sample(strengths, k=random.randint(1, len(strengths))),
            weaknesses=random.sample(weaknesses, k=random.randint(1, len(weaknesses))),
            threat_level=random.choice(threat_levels),
            score=round(random.uniform(0, 100), 2),
        )
